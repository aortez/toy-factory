#!/usr/bin/env python3
"""Synthetic checks for saved allocation evidence; no simulation execution."""
import copy
import hashlib
from pathlib import Path
import unittest
from unittest import mock

import garden_renewal_allocation_blockers as audit


def fixture(*, moisture=12, light=24, nodes=100, slots=8, age=8, dead=False, newborn=False):
    tick = 70140
    records = {i: {"id": i, "parent": 0, "generation": 0, "column": (i-1)*2,
                   "species": "shrub", "birth_tick": 0, "death_tick": None} for i in range(1, slots+1)}
    if dead:
        records[slots]["death_tick"] = tick-60
    if newborn:
        records[slots].update(parent=1, generation=1, birth_tick=tick)
    plants = [{**{k: p[k] for k in ("id", "parent", "generation", "column")},
               "species": 1, "dead": p["death_tick"] is not None} for p in records.values()]
    sites = []
    for column in range(28):
        mask = (8 if slots == 8 else 0) | (2 if moisture < 12 else 0) | (16 if nodes > 508 else 0)
        if any(abs(column-p["column"]) < 2 for p in plants):
            mask |= 32
        sites.append([mask, moisture, light])
    observed = {"parent": 1, "generation": 1, "column": 20, "species": 1,
                "age": age, "blockers": sites[20][0] | int(age < 8)}
    row = {"type": "seed-sites", "tick": tick, "nodes": nodes, "plants": plants,
           "sites": sites, "seeds": [observed], "births": int(newborn),
           "germination_rule": "wet-germination-v1"}
    seed = {"parent": 1, "generation": 1, "column": 20, "species": "shrub", "birth_tick": tick-age*15}
    return row, records, seed


def point(**kwargs):
    row, records, seed = fixture(**kwargs)
    context = audit.validate_sites(row, records, 0)
    audit.aligned_bank(row, [seed], records)
    return audit.witness(row, row["seeds"][0], context)


class GateTests(unittest.TestCase):
    def test_exclusive_allocation_with_node_slack_and_ignored_wet_light(self):
        for light in (0, 24, 79, 80, 255):
            for nodes in (4, 508):
                p = point(light=light, nodes=nodes)
                self.assertTrue(p["confirmed_plant_only"])
                self.assertEqual(p["mask"], 8)

    def test_other_gates_are_not_exclusive_allocation(self):
        for kwargs, mask in (({"moisture": 11}, 10), ({"nodes": 509}, 24), ({"slots": 7}, 0)):
            p = point(**kwargs)
            self.assertEqual(p["mask"], mask)
            self.assertFalse(p["confirmed_plant_only"])
        row, records, seed = fixture()
        row["seeds"][0].update(column=0, blockers=row["sites"][0][0])
        seed["column"] = 0
        context = audit.validate_sites(row, records, 0)
        audit.aligned_bank(row, [seed], records)
        p = audit.witness(row, row["seeds"][0], context)
        self.assertEqual(p["mask"], 40)
        self.assertEqual(p["stable_spacing_occupants"], [1])
        self.assertFalse(p["confirmed_plant_only"])

    def test_newborn_fullness_is_only_post_step_evidence(self):
        p = point(newborn=True)
        self.assertEqual(p["mask"], 8)
        self.assertEqual(len(p["stable_occupants"]), 7)
        self.assertFalse(p["confirmed_plant_only"])
        stats = audit.empty_stats()
        audit.observe(stats, p)
        audit.check_stats(stats)
        self.assertEqual(stats["counts"]["birth_step_plant_only"], 1)

    def test_dead_occupants_still_consume_slots(self):
        p = point(dead=True)
        self.assertTrue(p["confirmed_plant_only"])
        stats = audit.empty_stats()
        audit.observe(stats, p)
        audit.check_stats(stats)
        self.assertEqual(stats["counts"]["confirmed_with_dead"], 1)
        self.assertEqual(stats["counts"]["confirmed_all_live"], 0)

    def test_dormancy_and_expiry_edges(self):
        for age in (7, 8, 255):
            p = point(age=age)
            self.assertEqual(p["confirmed_plant_only"], age >= 8)
            stats = audit.empty_stats()
            audit.observe(stats, p)
            audit.check_stats(stats)
            self.assertEqual(stats["counts"]["mature_samples"], int(age >= 8))
        row, records, seed = fixture(age=256)
        with self.assertRaises(RuntimeError): audit.aligned_bank(row, [seed], records)

    def test_invalid_native_site_masks_and_values_fail_closed(self):
        for bad in ("water", "light", "mask", "age_bit", "node", "slots", "wet", "births", "duplicate"):
            row, records, _ = fixture()
            if bad == "water": row["sites"][20][1] = 11
            if bad == "light": row["sites"][20][2] = 256
            if bad == "mask": row["sites"][20][0] = 64
            if bad == "age_bit": row["sites"][20][0] |= 1
            if bad == "node": row["nodes"] = 509
            if bad == "slots": row["plants"].pop()
            if bad == "wet": row.pop("germination_rule")
            if bad == "births": row["births"] = 1
            if bad == "duplicate": row["plants"][-1] = row["plants"][0]
            with self.subTest(bad=bad), self.assertRaises(RuntimeError):
                audit.validate_sites(row, records, 0)

    def test_scope_excludes_boundary_and_dry_rule(self):
        row, records, _ = fixture()
        context = audit.validate_sites(row, records, 0)
        for tick, wet in ((audit.AFTER, True), (audit.AFTER+15, False)):
            row["tick"], context["wet"] = tick, wet
            with self.assertRaises(RuntimeError): audit.witness(row, row["seeds"][0], context)


class IdentityTests(unittest.TestCase):
    def test_export_tick_is_pre_removal_not_a_dead_occupant(self):
        row, records, _ = fixture()
        records[1].update(removal_tick=row["tick"], death_tick=row["tick"])
        context = audit.validate_sites(row, records, 0)
        self.assertFalse(context["stable"][0]["dead"])
        row["plants"][0]["dead"] = True
        with self.assertRaises(RuntimeError): audit.validate_sites(row, records, 0)
        row["plants"][0]["dead"] = False
        row["tick"] += 15
        with self.assertRaises(RuntimeError): audit.validate_sites(row, records, 0)

    def test_seed_order_age_and_identity_are_preserved(self):
        row, records, seed = fixture()
        second = {**seed, "parent": 2}
        row["seeds"].append({**row["seeds"][0], "parent": 2})
        active = [seed, second]
        before = copy.deepcopy((row, records, active))
        audit.aligned_bank(row, active, records)
        self.assertEqual((row, records, active), before)
        for values in (active[:1], active[::-1], [seed, seed]):
            with self.assertRaises(RuntimeError): audit.aligned_bank(row, values, records)
        row["seeds"][0]["age"] += 1
        with self.assertRaises(RuntimeError): audit.aligned_bank(row, active, records)

    def test_removed_seeds_have_no_terminal_post_sample(self):
        expired = {"birth_tick": 0, "end_tick": 3840, "outcome": "expired", "child_id": None,
                   "mature_snapshots": 248, "mature_blockers": {"8": 248}}
        audit.check_lifetime(expired, 256, {"8": 248})
        with self.assertRaises(RuntimeError): audit.check_lifetime(expired, 257, {"8": 249})
        germinated = {**expired, "end_tick": 120, "outcome": "germinated", "child_id": 10,
                      "mature_snapshots": 0, "mature_blockers": {}}
        audit.check_lifetime(germinated, 8, {})
        with self.assertRaises(RuntimeError): audit.check_lifetime(germinated, 9, {"0": 1})

    def test_pending_seeds_remain_censored(self):
        pending = {"birth_tick": audit.STOP-105, "end_tick": None, "outcome": "pending", "child_id": None,
                   "mature_snapshots": 0, "mature_blockers": {}}
        audit.check_lifetime(pending, 8, {})
        pending["birth_tick"] = audit.STOP-3840
        with self.assertRaises(RuntimeError): audit.check_lifetime(pending, 257, {"8": 249})


class SummaryTests(unittest.TestCase):
    def test_contiguous_runs_split_at_gap_and_counts_partition(self):
        stats, p = audit.empty_stats(), point()
        for tick in (70140, 70155, 70185):
            audit.observe(stats, {**p, "tick": tick})
        audit.observe(stats, point(newborn=True))
        audit.observe(stats, point(moisture=11))
        audit.observe(stats, point(age=7))
        audit.check_stats(stats)
        self.assertEqual(stats["confirmed_runs"], [
            {"first_tick": 70140, "last_tick": 70155, "samples": 2},
            {"first_tick": 70185, "last_tick": 70185, "samples": 1}])
        self.assertEqual(stats["counts"]["retained_samples"], 6)
        self.assertEqual(stats["counts"]["mature_samples"], 5)
        self.assertEqual(stats["counts"]["plant_with_other"], 1)

    def test_distinct_seeds_are_not_repeated_samples_or_purchase_cohorts(self):
        stats, p = audit.empty_stats(), point()
        for tick in (70140, 70155, 70170):
            audit.observe(stats, {**p, "tick": tick})
        seeds = [{"seed": {"parent": 1, "birth_tick": audit.AFTER-60, "column": 20, "outcome": "expired"},
                  "windows": {"after": stats}}]
        result = audit.summary(seeds, "after")
        self.assertEqual(result["counts"]["confirmed_plant_only"], 3)
        self.assertEqual(result["distinct_confirmed_plant_only"], 1)
        self.assertEqual(result["confirmed_seed_outcomes"], {"expired": 1})
        self.assertEqual(result["purchase_cohort"]["purchases"], 0)
        self.assertNotIn("probability", result)

    def test_no_observation_does_not_become_a_failed_seed(self):
        seeds = [{"seed": {"parent": 1, "birth_tick": audit.STOP, "column": 20, "outcome": "pending"},
                  "windows": {"after": audit.empty_stats()}}]
        result = audit.summary(seeds, "after")
        self.assertEqual(result["distinct_mature_seeds"], 0)
        self.assertEqual(result["purchase_cohort"], {"purchases": 1, "outcomes": {"pending": 1}})

    def test_contradictory_partition_is_rejected(self):
        stats = audit.empty_stats()
        audit.observe(stats, point())
        stats["counts"]["confirmed_plant_only"] = 2
        with self.assertRaises(RuntimeError): audit.check_stats(stats)


class ProvenanceTests(unittest.TestCase):
    def test_only_exact_shared_cmake_registration_is_allowed(self):
        old = b"before\n"+audit.REGISTRATION_ANCHOR.encode()+b"\nafter\n"
        sha = hashlib.sha256(old).hexdigest()
        new = old.replace(audit.REGISTRATION_ANCHOR.encode(), (audit.REGISTRATION+audit.REGISTRATION_ANCHOR).encode())
        audit.check_build_registration(old, new, sha)
        for bad in (old, new+b"\n", b"unrelated\n"+new):
            with self.assertRaises(RuntimeError): audit.check_build_registration(old, bad, sha)

    def test_verification_is_analysis_only_and_repeats(self):
        with mock.patch.object(audit, "analysis_sources", return_value={}), \
                mock.patch.object(audit, "check_parent", return_value=({}, {})), \
                mock.patch.object(audit, "analyze", return_value={"audit": "ok"}) as analyze, \
                mock.patch.object(audit.gap.parent.shadow, "check_frozen"), \
                mock.patch.object(audit.experiment, "digest", return_value=audit.PORTABLE_SHA), \
                mock.patch.object(audit.experiment, "command_run", side_effect=AssertionError("native call")) as run:
            result = audit.verify(Path("/unused-synthetic-parent"))
            self.assertEqual(result["audit"], "ok")
            self.assertEqual(analyze.call_count, 2)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
