#!/usr/bin/env python3
"""Saved-only leaf identity, storage bounds, censoring and provenance fixtures."""
import copy
import hashlib
import unittest
from unittest import mock

import garden_renewal_shedding_audit as audit
from test_garden_renewal_full_pool import row as metadata


def plant(identity=1, *, nodes=12, roots=2, conditions=(255,)):
    return {"id": identity, "parent": 0, "nodes": nodes, "roots": roots, "tips": 0,
            "leaves": len(conditions), "active_leaves": len(conditions), "flowers": 0,
            "spent_flowers": 0, "dead": False, "root_cells": [[1, 0, 1, 0]]*roots,
            "leaf": {"conditions": list(conditions), "renewals": 0, "restored": 0, "worn": 0}}


def row(plants, tick=0):
    return {**metadata(tick, "control"), "type": "world", "tick": tick, "hash": "fixture",
            "plants": plants, "living": sum(not p["dead"] for p in plants),
            "nodes": sum(p["nodes"] for p in plants), "node_capacity": 512, "seeds": [], "births": 0}


class LeafTests(unittest.TestCase):
    def test_inventory_distinguishes_maturity_from_condition(self):
        p = plant(conditions=(0, 100, 255))
        self.assertEqual(audit.inventory(p).count(0), 1)
        p["active_leaves"] = 2
        self.assertEqual(audit.inventory(p).count(0), 1)
        for field, value in (("active_leaves", 4), ("leaves", 2), ("nodes", True), ("flowers", 13)):
            with self.subTest(field=field), self.assertRaises(RuntimeError): audit.inventory({**p, field: value})
        for value in (False, -1, 256):
            bad = copy.deepcopy(p)
            bad["leaf"]["conditions"][0] = value
            with self.assertRaises(RuntimeError): audit.inventory(bad)

    def test_newborn_and_appended_leaf_are_fresh(self):
        p = plant()
        self.assertEqual(audit.leaf_transition(None, p, 0)["checked_ordinals"], 0)
        q = copy.deepcopy(p)
        q.update(nodes=13, leaves=2)
        q["leaf"]["conditions"].append(255)
        self.assertEqual(audit.leaf_transition(p, q, 15)["checked_ordinals"], 1)
        q["leaf"]["conditions"][-1] = 0
        with self.assertRaises(RuntimeError): audit.leaf_transition(p, q, 15)
        with self.assertRaises(RuntimeError): audit.leaf_transition(None, plant(conditions=(0,)), 0)

    def test_position_specific_wear_and_renewal(self):
        p = plant(conditions=(1, 100, 0))
        q = copy.deepcopy(p)
        q["leaf"].update(conditions=[0, 99, 255], worn=2, renewals=1, restored=255)
        frozen = copy.deepcopy((p, q))
        self.assertEqual(audit.leaf_transition(p, q, 60)["renewed_ordinals"], [2])
        self.assertEqual((p, q), frozen)
        for bad in ("order", "worn", "renewals", "wrong_leaf", "shrink"):
            r = copy.deepcopy(q)
            if bad == "order": r["leaf"]["conditions"] = [99, 0, 255]
            if bad in ("worn", "renewals"): r["leaf"][bad] += 1
            if bad == "wrong_leaf": r["leaf"].update(conditions=[255, 99, 0])
            if bad == "shrink": r["leaves"] -= 1; r["leaf"]["conditions"].pop()
            with self.subTest(bad=bad), self.assertRaises(RuntimeError): audit.leaf_transition(p, r, 60)

    def test_death_is_not_live_leaf_recovery(self):
        p = plant(conditions=(1, 0))
        q = copy.deepcopy(p)
        q["dead"] = True
        q["leaf"].update(conditions=[0, 0], worn=1)
        self.assertEqual(audit.leaf_transition(p, q, 60)["renewed_ordinals"], [])
        self.assertEqual(audit.leaf_transition(q, q, 75)["checked_ordinals"], 2)
        bad = copy.deepcopy(q)
        bad["leaf"]["conditions"][0] = 255
        with self.assertRaises(RuntimeError): audit.leaf_transition(q, bad, 75)


class BoundTests(unittest.TestCase):
    def test_upkeep_quantization_and_no_fake_guarantee(self):
        p = plant(nodes=17, roots=5, conditions=(0, 0))
        self.assertEqual(audit.upper_savings(p, 0), {"energy": 0, "water": 0})
        self.assertEqual(audit.upper_savings(p, 1), {"energy": 1, "water": 0})
        self.assertEqual(audit.upper_savings(p, 2), {"energy": 1, "water": 0})
        with self.assertRaises(RuntimeError): audit.upper_savings(p, 3)
        q = plant(nodes=8, roots=1, conditions=(0,))
        self.assertEqual(audit.upper_savings(q, 1), {"energy": 0, "water": 0})

    def test_round_per_owner_not_combined_world(self):
        plants = [plant(i, nodes=9, conditions=(0,)) for i in (1, 2)]
        result = audit.checkpoint(row(plants, audit.DAY), {(1, 0): 0, (2, 0): 0})
        self.assertEqual(result["zero_savings_upper"]["energy"], 2)
        self.assertNotEqual(result["zero_savings_upper"]["energy"], (18+7)//8-(16+7)//8)
        self.assertEqual(result["safe_removals_lower"], 0)
        self.assertIsNone(result["safe_removals_exact"])

    def test_day_span_boundary_and_dead_exclusion(self):
        p, dead = plant(conditions=(0, 0, 200)), plant(2, conditions=(0, 0))
        dead["dead"] = True
        starts = {(1, 0): 0, (1, 1): 15}
        result = audit.checkpoint(row([p, dead], audit.DAY), starts)
        self.assertEqual((result["zero"], result["day_zero"]), (2, 1))
        with self.assertRaises(RuntimeError): audit.checkpoint(row([p], audit.DAY), {(1, 0): 0})

    def test_night_or_immaturity_is_not_zero_condition(self):
        p = plant(conditions=(255, 200))
        p.update(active_leaves=0, energy_income=0)
        r = row([p], 15)
        r["sun_strength"] = 24
        result = audit.checkpoint(r, {})
        self.assertEqual((result["zero"], result["day_zero"]), (0, 0))

    def test_four_slots_are_only_an_optimistic_node_bound(self):
        from collections import Counter
        p = plant(nodes=512, roots=100, conditions=(0, 0, 0, 0))
        r = audit.checkpoint(row([p], audit.DAY), {(1, i): 0 for i in range(4)})
        w = {"counts": Counter(), "zero_histogram": Counter()}
        audit.window_add(w, r)
        self.assertEqual(w["counts"]["zero_seed_gate_relief_upper"], 1)
        self.assertEqual(r["safe_removals_lower"], 0)
        self.assertIsNone(r["safe_removals_exact"])


class HistoryTests(unittest.TestCase):
    def test_export_is_after_the_saved_boundary_census(self):
        p = plant(conditions=(0,))
        previous = row([p], 46080)
        record = {"removal_tick": 46080}
        exported = {"event": {"id": 1, "tick": 46080, "before_hash": "fixture"}}
        self.assertEqual(audit.removal_boundary(p, record, previous, 46095, exported),
                         (46080, 46080, "manual_export"))
        for bad in ({}, {"event": {**exported["event"], "tick": 46095}},
                    {"event": {**exported["event"], "before_hash": "wrong"}},
                    {"event": {**exported["event"], "id": 2}}):
            with self.assertRaises(RuntimeError): audit.removal_boundary(p, record, previous, 46095, bad)

    def fixture(self, ending="endpoint"):
        rows, p = [], plant()
        for tick in range(0, 15360+15, 15):
            if tick and tick % 60 == 0 and p["leaf"]["conditions"][0] > 0:
                p["leaf"]["conditions"][0] -= 1
                p["leaf"]["worn"] += 1
            if tick == 15360:
                if ending == "renewal": p["leaf"].update(conditions=[255], restored=255, renewals=1)
                if ending == "owner_death": p["dead"] = True
            rows.append(row([copy.deepcopy(p)], tick))
        return rows, {"lineages": [{"id": 1, "birth_tick": 0}]}

    def analyze(self, rows, saved):
        with mock.patch.object(audit, "AFTER", 15), mock.patch.object(audit, "LATE", 15000), \
                mock.patch.object(audit, "STOP", 15360), mock.patch.object(audit, "DAY", 30), \
                mock.patch.object(audit.parent.ownership, "AFTER", 15):
            return audit.analyze_rows(rows, saved, "control")

    def test_spells_close_by_renewal_death_or_endpoint(self):
        for ending in ("renewal", "owner_death", "endpoint"):
            rows, saved = self.fixture(ending)
            frozen = copy.deepcopy(rows)
            result = self.analyze(rows, saved)
            self.assertEqual(rows, frozen)
            episode = result["zero_spells"]["episodes"][0]
            self.assertEqual(episode["first_tick"], 15300)
            self.assertEqual(episode["last_zero_tick"], 15360 if ending == "endpoint" else 15345)
            self.assertEqual(episode["exit_tick"], None if ending == "endpoint" else 15360)
            self.assertEqual(result["zero_spells"]["counts"][ending], 1)
            self.assertEqual(result["zero_spells"]["counts"]["full_day_episodes"], 1)

    def test_missing_duplicate_wrong_metadata_and_unexplained_removal_fail(self):
        for bad in ("missing", "duplicate", "metadata", "removal", "truncated", "owner"):
            rows, saved = self.fixture()
            if bad == "missing": rows.pop(1)
            if bad == "duplicate": rows.insert(1, rows[0])
            if bad == "metadata": rows[0]["full_pool"] = {}
            if bad == "removal": rows[1] = row([], 15)
            if bad == "truncated": rows.pop()
            if bad == "owner": rows[0]["plants"].append(rows[0]["plants"][0])
            with self.subTest(bad=bad), self.assertRaises(RuntimeError): self.analyze(rows, saved)


class ScopeTests(unittest.TestCase):
    def test_exact_build_registration_only(self):
        original = ("prefix"+audit.REGISTRATION_ANCHOR+"suffix").encode()
        current = original.replace(audit.REGISTRATION_ANCHOR.encode(),
                                   (audit.REGISTRATION+audit.REGISTRATION_ANCHOR).encode())
        sha = hashlib.sha256(original).hexdigest()
        audit.check_build_registration(original, current, sha)
        for bad in (original, current+b"unrelated", current.replace(b"prefix", b"changed")):
            with self.assertRaises(RuntimeError): audit.check_build_registration(original, bad, sha)

    def test_cli_does_not_offer_native_capture(self):
        with mock.patch("sys.argv", ["audit", "--collect"]), mock.patch("sys.stderr"), self.assertRaises(SystemExit):
            audit.main()


if __name__ == "__main__":
    unittest.main()
