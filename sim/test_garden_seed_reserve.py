#!/usr/bin/env python3
"""Independent forecast, experiment identity and causal-prefix audit boundaries."""
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest

import garden_seed_reserve as trial


class SeedReserveTests(unittest.TestCase):
    def test_forecast(self):
        self.assertEqual(trial.forecast(240, 0, 48, 124), {
            "after_seed": 192, "projected_sunset": 186, "maintenance_cost": 6,
            "night_upkeep": 186, "allowed": True})
        for args in ((239, 0, 48, 124), (240, 0, 49, 124), (248, 255, 65, 124),
                     (248, 30, 64, 124), (248, 255, 64, 127), (48, 255, 4, 64)):
            self.assertFalse(trial.forecast(*args)["allowed"])
        for phase in (0, *range(128, 256)):
            self.assertFalse(trial.forecast(256, 255, 4, phase)["allowed"])
        for args in ((248, 38, 64, 124), (248, 8, 64, 64)):
            self.assertTrue(trial.forecast(*args)["allowed"])
        for args in ((257, 0, 4, 124), (256, 256, 4, 124), (256, 0, 513, 124)):
            with self.assertRaises(RuntimeError):
                trial.forecast(*args)

    def test_rule_identity(self):
        r = {"leaf_environment": "leaf-maintenance-v1", "leaf_policy": "selective",
             "node_capacity": 512, "seed_reserve_rule": trial.RULE}
        check = trial.bank.competition.maintenance.check_identity
        check(r, "selective", 512, seed_reserve=trial.RULE)
        with self.assertRaises(RuntimeError):
            check(r, "selective", 512)
        with self.assertRaises(RuntimeError):
            check({**r, "seed_reserve_rule": None}, "selective", 512, seed_reserve=trial.RULE)
        with self.assertRaises(RuntimeError):
            check({**r, "seed_reserve_rule": "other"}, "selective", 512, seed_reserve="other")

    def test_first_refusal_and_purchases(self):
        p = {"id": 1, "dead": False, "energy": 248, "water": 500, "nodes": 64,
             "energy_income": 0, "reproduction_cooldown": 0, "spent_flowers": 0}
        start = {"tick": 0, "hash": "a", "plants": [p], "seeds": [], "seeds_created": 0,
                 "births": 0, "deaths": 0, "nodes": 64, "sun_phase": 64}
        old = {**start, "tick": 900, "hash": "b", "sun_phase": 124, "seeds": [{"parent": 1}], "seeds_created": 1,
               "plants": [{**p, "energy": 200, "water": 476, "reproduction_cooldown": 16, "spent_flowers": 1}]}
        new = {**start, "tick": 900, "hash": "c", "sun_phase": 124, "seed_reserve_rule": trial.RULE}
        with tempfile.TemporaryDirectory(prefix="seed-reserve-test-") as temp:
            root = Path(temp)
            def run(a, b):
                for path, rows in ((root/"off.gz", a), (root/"on.gz", b)):
                    with gzip.open(path, "wt") as f:
                        for row in rows:
                            f.write(json.dumps(row) + "\n")
                return trial.compare_prefix(root/"off.gz", root/"on.gz")
            prefix = {**start, "seed_reserve_rule": trial.RULE}
            unchanged = run([start], [prefix])
            self.assertIsNone(unchanged["first"])
            self.assertEqual(unchanged["matched_rows"], 1)
            result = run([start, old], [prefix, new])
            self.assertEqual(result["first"]["matched_rows"], 1)
            self.assertEqual(result["first"]["refused"][0]["forecast"]["projected_sunset"], 192)
            # A later plant can consume the last slot left by the first refusal.
            existing = [{"parent": 9}]*7
            later = {**p, "id": 2, "nodes": 4}
            a = {**old, "seeds": existing+old["seeds"], "plants": old["plants"]+[later]}
            b = {**new, "seeds_created": 1, "seeds": existing+[{"parent": 2}],
                 "plants": [p, {**later, "energy": 200, "water": 476,
                                "reproduction_cooldown": 16, "spent_flowers": 1}]}
            transfer = run([start, a], [prefix, b])["first"]
            self.assertEqual([r["id"] for r in transfer["refused"]], [1])
            self.assertEqual([r["id"] for r in transfer["reassigned"]], [2])
            with self.assertRaises(RuntimeError):
                run([start, {**a, "seeds": a["seeds"][1:]}],
                    [prefix, {**b, "seeds": b["seeds"][1:]}])
            for bad in ({**new, "seed_reserve_rule": None}, {**new, "seeds_created": 1},
                        {**new, "births": 1}, {**new, "hash": "b"}):
                with self.assertRaises(RuntimeError):
                    run([start, old], [prefix, bad])
            # After the first difference, native purchases still need a valid forecast.
            purchase = {**new, "tick": 960, "sun_phase": 64, "seeds_created": 1,
                        "plants": [{**p, "energy": 200, "water": 476,
                                    "energy_income": 8, "reproduction_cooldown": 16}]}
            self.assertEqual(run([start, old, {**old, "tick": 960}],
                                 [prefix, new, purchase])["checked_purchases"], 1)
            bad = copy.deepcopy(purchase)
            bad["plants"][0]["energy_income"] = 0
            with self.assertRaises(RuntimeError):
                run([start, old, {**old, "tick": 960}], [prefix, new, bad])
            with self.assertRaises(ValueError):
                run([start, old], [prefix])


if __name__ == "__main__":
    unittest.main()
