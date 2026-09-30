#!/usr/bin/env python3
"""Offline accounting, same-age comparisons, unchanged scores and no-clobber."""

import copy
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import garden_landing_establishment as audit

PORTABLE = audit.ROOT / "benchmarks/garden-seasons/landing-establishment-results.json.gz"


class EstablishmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = audit.load(audit.ROOT / audit.INPUT)
        cls.result = audit.analyze(cls.data)

    def test_all_portable_evidence_and_scores_recompute(self):
        self.assertEqual(json.loads(gzip.decompress(PORTABLE.read_bytes())), self.result)
        self.assertEqual(self.result["input_sha256"], audit.INPUT_SHA)
        self.assertEqual(self.result["groups"]["all"]["all"]["outcomes"], {"confirmed": 55, "died": 72})
        for old, new in zip(self.data["worlds"], self.result["worlds"], strict=True):
            self.assertEqual(old["id"], new["id"])
            self.assertEqual(old["trace_sha256"], new["trace_sha256"])
            self.assertEqual(new["unchanged_history"], audit.prior.training.score_world(
                old["result"], old["case"], self.data["models"][old["model"]]["metadata"]))
            self.assertEqual(new["summary"]["resources"], old["audit"]["summary"]["late_children"]["resources"])
            for p in new["children"]:
                for j, resource in enumerate(audit.RESOURCES):
                    self.assertEqual(sum(g["cost"][j] for g in p["growth"]), p["resources"][resource]["growth"])
                self.assertEqual(len(p["root_growth_ticks"]), p["last_living_body"]["roots"] - 2)
                self.assertTrue(62 * audit.DAY < p["birth_tick"] <= 190 * audit.DAY)
                self.assertNotEqual(p["outcome"], "pending")

    def test_landmark_does_not_discard_early_deaths_or_late_root_successes(self):
        groups = self.result["groups"]["all"]
        self.assertEqual(groups["all"]["landmarks"]["480"],
                         {"expanded_roots": 55, "initial_roots": 72, "not_living": 0})
        self.assertEqual(groups["confirmed"]["landmarks"]["480"]["expanded_roots"], 47)
        self.assertEqual(groups["confirmed"]["landmarks"]["480"]["initial_roots"], 8)
        self.assertEqual(groups["died"]["landmarks"]["480"]["expanded_roots"], 8)
        self.assertEqual(groups["all"]["landmarks"]["960"]["not_living"], 27)
        for group in (groups["all"], groups["died"], groups["confirmed"]):
            for values in group["landmarks"].values():
                self.assertEqual(sum(values.values()), group["children"])

    def test_root_spending_and_energy_timing_include_contrary_outcomes(self):
        groups = self.result["groups"]["all"]
        water = groups["by_death_shortage"]["water"]
        self.assertEqual((water["children"], water["no_root_expansion"]), (43, 42))
        self.assertEqual(water["growth"]["shoot"]["water"], 2050)
        self.assertEqual(water["growth"]["root"]["water"], 5)
        self.assertEqual(water["resources"]["water"]["initial"] + water["resources"]["water"]["income"], 2815)
        self.assertEqual(water["resources"]["water"]["growth"], 2070)
        for cause, n in (("energy", 22), ("energy+water", 7)):
            self.assertEqual(groups["by_death_shortage"][cause]["deaths_with_globally_unavailable_energy"], n)
        # A reserve crossing is not proof of death: five eventual survivors
        # cross that threshold before their first actual water shortage.
        self.assertEqual(groups["confirmed"]["pre_shortage_growth_crossed_one_payment"]["water"], 5)
        self.assertEqual(groups["died"]["pre_shortage_growth_crossed_one_payment"]["water"], 38)

    def test_one_payment_boundaries_use_post_growth_body_without_predicting_income(self):
        self.assertEqual(audit.due(8, 2), (1, 1))
        self.assertEqual(audit.due(9, 2), (2, 1))
        self.assertEqual(audit.due(11, 2), (2, 2))
        exact = audit.payment_exposure([10, 7], [2, 2], 11, 2)
        self.assertEqual(exact["below_payment"], [])
        self.assertEqual(exact["crossed_payment"], [])
        low = audit.payment_exposure([10, 7], [1, 1], 11, 2)
        self.assertEqual(low["crossed_payment"], ["energy", "water"])
        already_low = audit.payment_exposure([1, 7], [0, 1], 11, 2)
        self.assertEqual(already_low["crossed_payment"], ["water"])
        self.assertEqual(already_low["below_payment"], ["energy", "water"])
        for args in (([1, 7], [2, 1], 11, 2), ([1, 7], [0, -1], 11, 2),
                     ([1], [0], 11, 2), ([10, 7], [1, 1], 11, 12)):
            with self.assertRaises(RuntimeError):
                audit.payment_exposure(*args)

    def test_sun_ceiling_and_cadence_are_not_local_leaf_light(self):
        strength = lambda p: audit.maximum_sun(((p - 64) % 256) * audit.STEP)
        self.assertEqual(strength(64), 255)
        for p in (0, 10, 118, 128, 255):
            self.assertLess(strength(p), 64)
        for p in (11, 117):
            self.assertGreaterEqual(strength(p), 64)
        # Stored shortage flags persist between payments; only fresh cadence
        # checks belong in the event list.
        ps = [p for w in self.result["worlds"] for p in w["children"]]
        self.assertTrue(any(p["shortages"] for p in ps))
        self.assertTrue(all(s["tick"] % 60 == 0 for p in ps for s in p["shortages"]))

    def test_missing_rows_corrupt_transfers_stress_or_morphology_are_rejected(self):
        original = next(p for w in self.data["worlds"] for p in w["audit"]["plants"]
                        if p["outcome"] == "died" and len(p["rows"]) > 10)
        for kind in ("gap", "income", "stress", "roots", "wrong_summary", "death_due"):
            broken = copy.deepcopy(original)
            if kind == "gap":
                del broken["rows"][2]
            elif kind == "income":
                broken["rows"][2]["uptake"][0][1] += 1
            elif kind == "stress":
                broken["rows"][2]["stages"][1][2] += 1
            elif kind == "roots":
                broken["rows"][2]["roots"] += 2
            elif kind == "wrong_summary":
                broken["resources"]["water"]["growth"] += 1
            else:
                broken["rows"][-1]["uptake"][0][3] += 1
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                audit.summarize_child(broken, audit.prior.STOP)
        before = copy.deepcopy(original)
        audit.summarize_child(original, audit.prior.STOP)
        self.assertEqual(original, before)

    def test_pending_followup_and_death_row_leaf_reset_are_not_success(self):
        original = next(p for w in self.data["worlds"] for p in w["audit"]["plants"]
                        if p["outcome"] == "died" and p["rows"][-2]["active_leaves"] > 0)
        result = audit.summarize_child(original, audit.prior.STOP)
        self.assertEqual(result["last_living_body"]["active_leaves"], original["rows"][-2]["active_leaves"])
        partial = copy.deepcopy(original)
        partial["rows"] = partial["rows"][:3]
        horizon = partial["rows"][-1]["tick"]
        with self.assertRaises(RuntimeError):
            audit.summarize_child(partial, horizon)
        partial["death_tick"] = None
        audit.prior.analyze_child(partial, horizon)
        result = audit.summarize_child(partial, horizon)
        self.assertEqual(result["outcome"], "pending")
        self.assertIsNone(result["landmarks"]["480"])

    def test_cli_no_clobber_wrong_input_and_tampered_output(self):
        script = audit.ROOT / "sim/garden_landing_establishment.py"
        def run(*args):
            return subprocess.run([sys.executable, "-W", "error", str(script), *map(str, args)],
                                  capture_output=True, timeout=30)
        with tempfile.TemporaryDirectory(prefix="landing-establishment-test-") as directory:
            out = Path(directory) / "audit.json.gz"
            self.assertEqual(run("--out", out).returncode, 0)
            old = out.read_bytes()
            self.assertNotEqual(run("--out", out).returncode, 0)
            self.assertEqual(out.read_bytes(), old)
            self.assertEqual(run("--verify", out).returncode, 0)
            bad = Path(directory) / "bad.json"
            bad.write_text("{}\n")
            self.assertNotEqual(run("--verify", bad).returncode, 0)
            unused = Path(directory) / "unused.json"
            self.assertNotEqual(run("--input", bad, "--out", unused).returncode, 0)
            self.assertFalse(unused.exists())


if __name__ == "__main__":
    unittest.main()
