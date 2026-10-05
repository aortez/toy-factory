#!/usr/bin/env python3
"""Late trace provenance, first-day budgets, failure causes and censoring."""

import copy
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_late as trace

RESULT = "benchmarks/garden-seasons/landing-late-resources-results.json.gz"
SHA = "6e30507abd1262163afc4e975a7f9e261ca3633c998d799a1aecbf9464ae4f89"


class LateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = trace.prior.load(trace.ROOT / RESULT, SHA)

    def child(self, arm, identity):
        return next(p for p in self.data["arms"][arm]["analysis"]["children"] if p["life"]["id"] == identity)

    def test_portable_verification_never_replays_or_mutates(self):
        before = copy.deepcopy(self.data)
        with patch.object(trace.order.training, "native", side_effect=AssertionError("unexpected replay")), patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(trace.verify(trace.ROOT / RESULT), self.data)
            trace.check_value(self.data)
        self.assertEqual(self.data, before)

    def test_four_calls_and_unchanged_outcomes(self):
        _, world, _, _ = trace.load_inputs()
        self.assertEqual((self.data["full_replays"], self.data["checkpoint_replays"], self.data["training_runs"]), (4, 0, 0))
        for arm, a in self.data["arms"].items():
            self.assertEqual(len(a["calls"]), 2)
            self.assertEqual(a["result"], world["contexts"]["control"][arm]["result"])
            for label in trace.LABELS:
                args = trace.arguments(world, arm, label)
                self.assertEqual(args[args.index("--stand-start") + 1], str(218 * trace.DAY))
                self.assertEqual(args[args.index("--adult-stop") + 1], str(256 * trace.DAY))
                self.assertEqual("--seed-order" in args, arm == "rotating")

    def test_all_eleven_births_and_exact_first_day_accounting(self):
        self.assertEqual([len(self.data["arms"][a]["analysis"]["children"]) for a in trace.ARMS], [3, 8])
        for a in self.data["arms"].values():
            for p in a["analysis"]["children"]:
                f = p["first_day"]
                self.assertEqual(f, trace.history_summary(p["life"], p["steps"]))
                for b in f["resources"].values():
                    self.assertEqual(b["initial"] + b["income"], sum(b[k] for k in trace.adults.FIELDS if k not in ("initial", "income")))
                self.assertEqual((f["resources"]["energy"]["initial"], f["resources"]["water"]["initial"]), (64, 24))

    def test_closing_deaths_start_with_water_and_reach_terminal_stress(self):
        for identity, cause, growth, income, upkeep in ((48, "energy+water", 45, 38, 17),
                (49, "energy+water", 60, 56, 20), (50, "water", 30, 25, 19)):
            p = self.child("rotating", identity)
            f, w = p["first_day"], p["first_day"]["resources"]["water"]
            self.assertEqual((f["status"], f["first_shortage"]["cause"], f["death_shortage"]), ("died", "water", cause))
            self.assertEqual([s["stress"] for s in f["shortages"]], list(range(1, 9)))
            self.assertEqual((w["growth"], w["income"], w["upkeep"], w["reproduction"]), (growth, income, upkeep, 0))
            self.assertTrue(all(s["plant"]["roots"] == 2 for s in p["steps"]))

    def test_death_discard_is_not_an_energy_shortage(self):
        p = self.child("rotating", 50)
        f, terminal = p["first_day"], p["steps"][-1]["plant"]
        self.assertEqual(f["death_shortage"], "water")
        self.assertEqual(f["resources"]["energy"], {"initial": 64, "income": 51, "overflow": 0,
            "upkeep": 52, "growth": 54, "reproduction": 0, "discarded": 9, "final": 0})
        self.assertEqual(terminal["uptake"][0], [11, 0, 0, 2, 2, 9])

    def test_fixed_successes_and_unresolved_tail_are_not_pooled(self):
        for identity in (45, 46):
            p = self.child("fixed", identity)
            self.assertEqual((p["first_day"]["status"], p["first_day"]["samples"], p["first_day"]["first_shortage"]), ("confirmed", 257, None))
            self.assertEqual(p["steps"][-1]["plant"]["roots"], 16)
        for identity in (51, 52):
            p = self.child("rotating", identity)
            self.assertEqual((p["first_day"]["status"], p["first_day"]["samples"], p["first_day"]["right_censored"]), ("pending", 36, True))
            self.assertIsNone(p["first_day"]["first_shortage"])
            self.assertIsNone(p["first_day"]["death_shortage"])
            self.assertEqual(p["first_day"]["window"][1], trace.STOP)

    def test_root_opportunities_exist_without_budget_denial(self):
        for identity in (48, 49, 50):
            p = self.child("rotating", identity)
            roots = [b for s in p["steps"] for b in s["bids"] if b["tissue"] == 1]
            self.assertTrue(roots)
            self.assertTrue(all(b["available"] > 0 and b["budget"]["allowed"] for b in roots))
            self.assertTrue(any(b["action"] == 1 for b in roots))
            self.assertTrue(any(b["action"] == 0 for b in roots))

    def test_early_root_bids_pass_even_the_stricter_water_bound(self):
        # Independently bound the existing water guard. Destination moisture
        # can lower a root's reserve from four upkeep payments to one; it
        # cannot require more. Do not guess when the missing field matters.
        for identity, expected in ((48, (4, 0)), (49, (7, 0)), (50, (6, 1))):
            p = self.child("rotating", identity)
            self.assertEqual(p["life"]["species"], 0)  # Species-0 growth costs five water.
            shoots, waits = 0, 0
            for s in p["steps"]:
                roots = [b for b in s["bids"] if b["tissue"] == 1 and b["action"] == 1 and
                         b["available"] and b["budget"]["allowed"]]
                if not roots:
                    continue
                self.assertLess(s["tick"] - p["life"]["birth_tick"], trace.DAY)
                allowed = []
                for b in s["bids"]:
                    extends = b["action"] == 1 and b["available"] > 0
                    upkeep = (b["shoots"] + int(b["tissue"] == 0 and extends) + 7) // 8
                    high = 5 + 4 * upkeep
                    low = 5 + upkeep if b["tissue"] == 1 and extends else high
                    if b in roots:
                        self.assertGreaterEqual(b["water"], high)
                    if b["action"] == 0 or b["water"] >= high:
                        if b["budget"]["allowed"]:
                            allowed.append(b)
                    else:
                        self.assertLess(b["water"], low, "wet-destination detail is needed here")
                winner = max(allowed, key=lambda b: b["priority"])
                debit = trace.adults.transfers({"tick": s["tick"], **s["plant"]}, p["life"])
                if winner["tissue"] == 0 and winner["action"] == 1:
                    shoots += 1
                    self.assertEqual(debit["water"]["growth"], 5)
                else:
                    self.assertEqual((winner["tissue"], winner["action"]), (1, 0))
                    waits += 1
                    self.assertEqual(debit["water"]["growth"], 0)
            self.assertEqual((shoots, waits), expected)

    def test_birth_checks_and_ancestry_are_within_run(self):
        for a in self.data["arms"].values():
            for p in a["analysis"]["children"]:
                self.assertEqual(p["ancestry"], trace.prior.ancestry(a, p["life"]["id"]))
                self.assertEqual(p["seed"]["end_tick"], p["steps"][0]["tick"])
                self.assertEqual(p["birth_check"][3], 0)
                self.assertEqual(p["birth_check"][9], p["life"]["id"])
        self.assertNotEqual(self.child("fixed", 45)["seed"], self.child("rotating", 45)["seed"])

    def test_missing_reordered_discontinuous_or_fee_corrupt_receipts_fail(self):
        original = self.child("rotating", 48)
        for fault in ("missing", "order", "identity", "continuity", "fee", "sun"):
            p = copy.deepcopy(original)
            steps = p["steps"]
            if fault == "missing":
                steps.pop()
            elif fault == "order":
                steps[0], steps[1] = steps[1], steps[0]
            elif fault == "identity":
                steps[0]["plant"]["id"] += 1
            elif fault == "continuity":
                steps[1]["plant"]["uptake"][0][0] += 1
            elif fault == "fee":
                steps[0]["visit"]["produced"] = True
                steps[0]["visit"]["blockers"] = 0
            else:
                steps[0]["sun"][0] += 1
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                trace.history_summary(p["life"], steps)

    def test_provenance_budget_trajectory_and_censoring_corruption_fail(self):
        for fault in ("protocol", "calls", "trajectory", "censoring"):
            bad = copy.deepcopy(self.data)
            if fault == "protocol":
                bad["protocol_sha256"] = "0" * 64
            elif fault == "calls":
                bad["full_replays"] = 5
            elif fault == "trajectory":
                bad["arms"]["fixed"]["result"]["run_hash"] = "00000000"
            else:
                bad["arms"]["rotating"]["analysis"]["children"][-1]["first_day"]["status"] = "died"
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                trace.check_value(bad)

    def test_no_clobber_and_wrong_original_bundle_fail_before_native(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(trace, "load_inputs", side_effect=AssertionError("read before no-clobber")), self.assertRaises(RuntimeError):
                trace.collect(root, root, root)
            with patch.object(trace, "digest", return_value="bad"), self.assertRaises(RuntimeError):
                trace.historical_boundary(root, {})


if __name__ == "__main__":
    unittest.main()
