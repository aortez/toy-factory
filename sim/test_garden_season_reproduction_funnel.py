#!/usr/bin/env python3
"""Seed transitions, posthumous ancestry, stage boundaries and portable funnels."""

import copy
import gzip
import json
import unittest

import garden_season_reproduction_funnel as audit


def plant(ident=1, parent=0, generation=0, column=4, dead=False):
    return {"id": ident, "parent": parent, "generation": generation, "column": column,
            "species": "flower", "dead": dead, "flowers": 1, "reproduction_cooldown": 0}


def seed(tick, parent=1, column=10, created=60):
    age = (tick - created) // 15
    return {"parent": parent, "generation": 1, "species": "flower", "column": column,
            "age": age, "blockers": 1 if age < audit.DORMANCY else 32}


def world(tick, plants, seeds, created=0, expired=0, births=0, deaths=0):
    return {"tick": tick, "seed_lifetime_ecology_ticks": audit.LIFETIME,
            "nodes": 4 * len(plants), "plants": plants, "seeds": seeds,
            "seeds_created": created, "seeds_expired": expired, "births": births, "deaths": deaths}


def posthumous_trace():
    rows = []
    for tick in range(0, 211, 15):
        parents = [plant(dead=tick >= 120)] if tick < 135 else []
        if tick == 60:
            parents[0]["reproduction_cooldown"] = 16
        if tick >= 180:
            parents.append(plant(2, 1, 1, 10))
        rows.append(world(tick, parents, [seed(tick)] if 60 <= tick < 180 else [],
                          int(tick >= 60), births=int(tick >= 180), deaths=int(tick >= 120)))
    return rows


def event_fixture(born=60, created=120, child_born=240):
    parent = {"plant": {"id": 2, "parent": 1, "species": "flower", "generation": 1,
                       "family": 1, "birth_tick": born, "death_tick": None},
              "column": 4, "children": [3], "seed_indices": [0], "first_flower_tick": created,
              "max_flowers": 1}
    child = {"plant": {"id": 3, "parent": 2, "species": "flower", "generation": 2,
                       "family": 1, "birth_tick": child_born, "death_tick": None},
             "column": 10, "children": [], "seed_indices": [], "first_flower_tick": None,
             "max_flowers": 0}
    record = {"parent": 2, "generation": 2, "species": "flower", "column": 10,
              "created_tick": created, "resolved_tick": child_born, "child": 3,
              "outcome": "germinated", "post_blockers": {}, "mature_post_samples": 0}
    return {"parents": [parent, child], "seeds": [record]}


class FunnelTests(unittest.TestCase):
    def read_trace(self, rows):
        ledger = audit.SeedLedger()
        for row in rows:
            ledger.accept(row)
        return ledger.result(rows[-1]["tick"])

    def test_exact_creation_and_posthumous_germination_after_reclamation(self):
        result = self.read_trace(posthumous_trace())
        self.assertEqual(result["worlds"], 15)
        self.assertEqual(result["parents"][0]["plant"]["death_tick"], 120)
        self.assertEqual(result["parents"][0]["children"], [2])
        self.assertEqual(result["seeds"][0]["created_tick"], 60)
        self.assertEqual(result["seeds"][0]["resolved_tick"], 180)
        self.assertEqual(result["seeds"][0]["child"], 2)
        self.assertEqual(result["seeds"][0]["mature_post_samples"], 0)

    def test_missing_steps_seed_collisions_metadata_and_counters_fail(self):
        mutations = (lambda r: r.pop(6), lambda r: r[4]["seeds"].append(copy.deepcopy(r[4]["seeds"][0])),
                     lambda r: r[6]["seeds"].clear(), lambda r: r[5]["seeds"][0].update(age=2),
                     lambda r: r[5]["seeds"][0].update(column=11),
                     lambda r: r[5]["seeds"][0].update(generation=2),
                     lambda r: r[5].update(seeds_created=2),
                     lambda r: r[12]["plants"][0].update(parent=99),
                     lambda r: r[4]["plants"][0].update(flowers=0))
        for mutate in mutations:
            rows = posthumous_trace()
            mutate(rows)
            with self.assertRaises(RuntimeError):
                self.read_trace(rows)

    def test_bank_order_and_sequential_child_attribution_are_required(self):
        rows = []
        for tick in range(0, 196, 15):
            parents = [plant(), plant(2, column=20)]
            if tick == 60:
                for p in parents:
                    p["reproduction_cooldown"] = 16
            if tick >= 180:
                parents += [plant(3, 1, 1, 10), plant(4, 2, 1, 18)]
            seeds = [seed(tick), seed(tick, 2, 18)] if 60 <= tick < 180 else []
            rows.append(world(tick, parents, seeds, 2 * int(tick >= 60), births=2 * int(tick >= 180)))
        self.assertEqual([s["child"] for s in self.read_trace(rows)["seeds"]], [3, 4])
        for position, key in ((4, "seeds"), (5, "seeds")):
            changed = copy.deepcopy(rows)
            changed[position][key].reverse()
            with self.assertRaises(RuntimeError):
                self.read_trace(changed)
        changed = copy.deepcopy(rows)
        changed[12]["plants"][2:] = [plant(3, 2, 1, 18), plant(4, 1, 1, 10)]
        with self.assertRaises(RuntimeError):
            self.read_trace(changed)

    def test_expiry_is_exact_and_pending_mature_samples_are_post_step_only(self):
        end = 60 + 15 * audit.LIFETIME
        ledger = audit.SeedLedger()
        for tick in range(0, end + 1, 15):
            p = plant()
            if tick == 60:
                p["reproduction_cooldown"] = 16
            seeds = [seed(tick)] if 60 <= tick < end else []
            if tick == 180:
                seeds[0]["blockers"] = 0  # Post-step eligibility is not an actual germination receipt.
            ledger.accept(world(tick, [p], seeds, int(tick >= 60), int(tick == end)))
        record = ledger.result(end)["seeds"][0]
        self.assertEqual((record["outcome"], record["resolved_tick"], record["child"]), ("expired", end, None))
        self.assertEqual(record["mature_post_samples"], audit.LIFETIME - audit.DORMANCY)
        self.assertEqual(record["post_blockers"]["0"], 1)
        with self.assertRaises(RuntimeError):
            audit.seed_key(seed(end), end)
        early = posthumous_trace()
        early[11]["seeds"].clear()
        early[11]["plants"].append(plant(2, 1, 1, 10))
        early[11]["births"] = 1
        with self.assertRaises(RuntimeError):
            self.read_trace(early)

    def test_stage_priority_young_living_dead_and_exact_day_boundary(self):
        ledger = event_fixture()
        parent, child = ledger["parents"]
        self.assertEqual(audit.stage(parent, ledger, 105)[0], "no_seed")
        self.assertEqual(audit.stage(parent, ledger, 120)[0], "seeds_pending")
        self.assertEqual(audit.stage(parent, ledger, 240)[0], "children_pending")
        boundary = 240 + audit.DAY
        self.assertEqual(audit.stage(parent, ledger, boundary)[0], "durable")
        child["plant"]["death_tick"] = boundary
        self.assertEqual(audit.stage(parent, ledger, boundary)[0], "children_failed")
        child["plant"]["death_tick"] = 300
        counts = audit.stage(parent, ledger, 300)[1]
        self.assertEqual(counts["child_young_dead"], 1)
        self.assertEqual(counts["child_eligible"], 0)
        child["plant"]["death_tick"] = boundary + 60
        self.assertEqual(audit.stage(parent, ledger, boundary)[0], "durable")
        parent["children"] = []
        ledger["seeds"][0].update(outcome="expired", child=None, resolved_tick=120 + 15 * audit.LIFETIME)
        self.assertEqual(audit.stage(parent, ledger, 120 + 15 * audit.LIFETIME - 15)[0], "seeds_pending")
        self.assertEqual(audit.stage(parent, ledger, 120 + 15 * audit.LIFETIME)[0], "seeds_expired")

    def test_age_landmarks_keep_deaths_censor_followup_and_do_not_leak_future(self):
        born = audit.END - 2 * audit.DAY
        ledger = event_fixture(born, born + audit.DAY + 60, born + audit.DAY + 180)
        parent = ledger["parents"][0]
        parent["plant"]["death_tick"] = born + audit.DAY + 120
        first = audit.census([parent], ledger, 1)
        self.assertEqual((first["parents"], first["alive"], first["stage_no_seed"],
                          first["no_seed_no_observed_flower"]), (1, 1, 1, 1))
        second = audit.census([parent], ledger, 2)
        self.assertEqual((second["parents"], second["dead"], second["stage_children_pending"]), (1, 1, 1))
        fourth = audit.census([parent], ledger, 4)
        self.assertEqual((fourth["parents"], fourth["followup_censored_dead"]), (0, 1))
        parent["plant"]["death_tick"] = None
        self.assertEqual(audit.census([parent], ledger, 4)["followup_censored_alive"], 1)
        parent["plant"]["death_tick"] = born + audit.DAY
        self.assertFalse(audit.survived_day(parent["plant"], audit.END))
        parent["plant"]["death_tick"] += 15
        self.assertTrue(audit.survived_day(parent["plant"], audit.END))

    def test_portable_evidence_and_parent_seed_tampering(self):
        folder = audit.ROOT / "benchmarks/garden-seasons"
        report = json.loads(gzip.decompress((folder / "reproduction-funnel-ledgers.json.gz").read_bytes()))
        original = audit.load_input()
        audit.validate_report(report, original)
        self.assertEqual(audit.compact(report), json.loads((folder / "reproduction-funnel-summary.json").read_text()))
        with self.assertRaises(RuntimeError):
            audit.analysis(report["cases"][:-1])
        mutations = (lambda r: r["seeds"][0].update(created_tick=15),
                     lambda r: r["seeds"].pop(), lambda r: r["parents"][0]["seed_indices"].append(999),
                     lambda r: r["seeds"][0].update(mature_post_samples=-1))
        for mutate in mutations:
            ledger = copy.deepcopy(report["cases"][0]["ledger"])
            mutate(ledger)
            with self.assertRaises(RuntimeError):
                audit.validate_ledger(ledger, original["cases"][0]["arms"]["control"])


if __name__ == "__main__":
    unittest.main()
