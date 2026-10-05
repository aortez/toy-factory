#!/usr/bin/env python3
"""Offline illumination, whole-lifetime budgets, dawns and frozen provenance."""

import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_light_audit as audit

RESULTS = "benchmarks/garden-seasons/landing-light-audit-results.json.gz"
RESULTS_SHA = "80d7c070d41bf0d7c6d6836e342d830fe98b9436cc82ba09a5231bf0f9c5975b"


class ArithmeticTests(unittest.TestCase):
    def test_sun_curve_and_integer_season_scaling(self):
        phases = (0, 11, 12, 64, 116, 117, 128, 192, 255)
        self.assertEqual([audit.strength(p, 100) for p in phases], [24, 64, 67, 255, 67, 64, 24, 24, 24])
        self.assertEqual([audit.strength(p, 52) for p in (97, 98, 106, 107, 108)], [82, 80, 65, 63, 61])
        self.assertEqual([audit.strength(p, 53) for p in (106, 107, 108)], [65, 64, 62])
        self.assertEqual([audit.ray_step(p) for p in (0, 64, 128, 192, 255)], [12, 0, -12, 0, 12])
        for phase, percent in ((-1, 100), (256, 100), (True, 100), (0, -1), (0, 101)):
            with self.subTest(phase=phase, percent=percent), self.assertRaises(RuntimeError):
                audit.strength(phase, percent)

    def test_current_only_diagnostic_and_morning_unchanged(self):
        self.assertEqual(audit.diagnostic(97, 82, 5), {"applies": True, "useful_steps": 9, "credit": 22})
        for p in (0, 1, 32, 63):
            self.assertEqual(audit.diagnostic(p, 100, 3),
                             {"applies": False, "useful_steps": None, "credit": 3 * (127 - p) // 2})
        for phase, sun in ((64, 24), (106, 63), (107, 64), (127, 255)):
            self.assertEqual(audit.diagnostic(phase, sun, 5)["credit"], 0)
        with self.assertRaises(RuntimeError):
            audit.diagnostic(128, 24, 0)
        # No division by zero at phase zero; no tomorrow's weather argument.
        self.assertEqual(audit.diagnostic(0, 24, 0)["credit"], 0)
        with self.assertRaises(TypeError):
            audit.diagnostic(97, 82, 5, future_light_percent=55)

    def test_half_energy_partition_keeps_rounding_and_underestimates(self):
        self.assertEqual(audit.half_error(5, 10, 20, 18),
                         {"globally_dim": 100, "lit_window_remainder": 14, "integer_rounding": 0})
        self.assertEqual(audit.half_error(3, 2, 1, 8),
                         {"globally_dim": 3, "lit_window_remainder": -10, "integer_rounding": -1})

    def test_birth_and_terminal_leaf_bounds_are_not_used(self):
        life = {"birth_tick": 15, "death_tick": 45}
        for tick in (15, 30, 45):
            phase = (64 + tick // audit.STEP) % 256
            step = {"tick": tick, "sun": [phase, audit.strength(phase, 100)],
                    "climate": {"light_percent": 100}, "plant": {"active_leaves": 0}}
            if tick == 30:
                with self.assertRaisesRegex(RuntimeError, "unshaded bound"):
                    audit.illumination(step, life, {"income": 1})
            else:
                self.assertIsNone(audit.illumination(step, life, {"income": int(tick == 45)})["open_sky_upper"])
        step.update(tick=960, sun=[128, 24])
        life["death_tick"] = 960
        with self.assertRaisesRegex(RuntimeError, "globally unproductive"):
            audit.illumination(step, life, {"income": 1})

    def test_combined_winner_includes_afternoon_gate(self):
        def bid(tip, afternoon):
            return {"tip": tip, "priority": 7, "budget": {"allowed": True}, "water_gate": {"allowed": True},
                    "energy_gate": {"allowed": True}, "afternoon_gate": {"allowed": afternoon}}
        a, b = bid(1, False), bid(2, True)
        self.assertEqual(audit.select_bid({"bids": [a, b]}), (b, True))
        b["afternoon_gate"]["allowed"] = False
        self.assertEqual(audit.select_bid({"bids": [a, b]}), (a, False))
        self.assertEqual(audit.select_bid({"bids": []}), (None, False))

    def test_output_no_clobber_and_wrong_bundle_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            with patch.object(audit.energy, "source_files", side_effect=AssertionError("read before validation")):
                for out in (path, audit.ROOT / "sim" / "not-an-output"):
                    with self.assertRaisesRegex(RuntimeError, "fresh output"):
                        audit.export(out)
            audit.energy.write_json(path / "manifest.json", {"rule": audit.energy.RULE, "status": "complete",
                                                           "artifacts": dict.fromkeys(audit.energy.BUNDLE_FILES, "0" * 64)})
            with self.assertRaisesRegex(RuntimeError, "incomplete/wrong audit bundle"):
                audit.verify(path)


class FrozenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.object(audit.previous.order.training, "native", side_effect=AssertionError("ran simulation")):
            cls.data = audit.load_input()
            cls.analysis = audit.analyze(cls.data)
        cls.histories = {h["id"]: h for h in cls.analysis["histories"]}

    def test_all_lifetimes_and_duplicate_accounting(self):
        raw, unique = (self.analysis[k] for k in ("all_histories", "unique_histories"))
        self.assertEqual((raw["histories"], raw["samples"], raw["night_purchases"]), (10, 49152, 2))
        self.assertEqual((unique["histories"], unique["samples"], unique["night_purchases"]), (6, 25091, 2))
        self.assertEqual([h["id"] for h in self.histories.values() if h["id"] != h["canonical_history"]],
                         ["fixed-45/candidate", "fixed-46/candidate", "rotating-48/candidate", "rotating-50/candidate"])
        self.assertEqual(sum(p["purchases"] for p in raw["by_phase"].values()), 298)
        self.assertEqual(sum(p["purchases"] for p in unique["by_phase"].values()), 178)
        for h in self.histories.values():
            checks = h["light_checks"]
            self.assertEqual(checks["bounded_samples"] + checks["birth_excluded"] + checks["death_excluded"], h["saved_samples"])
            self.assertLessEqual(checks["bounded_income"], checks["actual_body_open_sky_upper"])
            self.assertEqual(h["life"]["seeds_created"], 0)
            for budget in h["totals"].values():
                self.assertEqual(budget["initial"] + budget["income"],
                                 sum(v for k, v in budget.items() if k not in ("initial", "income")))

    def test_last_failure_is_mostly_credit_in_globally_dim_interval(self):
        event = self.histories["rotating-49/candidate"]["events"][-1]
        self.assertEqual((event["tick"], event["bid"]["energy_gate"]["daylight_credit"], event["sunset"]["transfers"]["income"]),
                         (914415, 75, 18))
        light = event["illumination"]
        self.assertEqual((light["lit_steps"], light["dim_steps"]), (10, 20))
        self.assertEqual(light["income_error_half_units"], {"globally_dim": 100, "lit_window_remainder": 14, "integer_rounding": 0})
        self.assertEqual((light["actual_body_open_sky_upper"], light["actual_body_bound_minus_income"]), (80, 62))
        self.assertEqual((light["leaves_min"], light["leaves_max"], light["light_percent_min"], light["light_percent_max"]), (8, 8, 52, 55))
        self.assertTrue(event["clean_interval"])
        self.assertEqual(event["diagnostic"]["credit"], 22)
        self.assertEqual(event["diagnostic"]["income_error"], 4)
        self.assertTrue(event["diagnostic"]["changes_active_gate"])
        self.assertEqual(event["night"]["status"], "dead")

    def test_complete_partitions_and_future_sample_exclusions(self):
        for h in self.histories.values():
            for e in h["events"]:
                self.assertEqual(e["sunset"]["status"], "alive")
                self.assertEqual(sum(e["illumination"]["income_error_half_units"].values()), 2 * e["error"]["terms"]["income"])
                self.assertEqual(e["future_light"][0]["tick"], e["tick"] + audit.STEP)
                self.assertEqual(e["future_light"][-1]["phase"], 128)
                self.assertEqual(sum(r["income"] for r in e["future_light"]), e["sunset"]["transfers"]["income"])
                if e["phase"] < 64:
                    self.assertEqual(e["diagnostic"]["credit"], e["bid"]["energy_gate"]["daylight_credit"])
                self.assertLessEqual(e["diagnostic"]["credit"], e["bid"]["energy_gate"]["daylight_credit"])

    def test_incomplete_sunset_never_gets_complete_error_partition(self):
        entry = self.data["cases"][3]
        rows, receipts, lights, _ = audit.check_history(entry["case"], entry["arms"]["candidate"]["analysis"])
        index = next(i for i, r in enumerate(rows) if r["tick"] == 914415)
        life = entry["arms"]["candidate"]["analysis"]["focal"]["life"]
        bid, eligible = audit.select_bid(rows[index])
        self.assertTrue(eligible)
        end = index + 4
        event = audit.daylight_event(rows[:end], receipts[:end], lights[:end], life, index, bid)
        self.assertEqual(event["sunset"]["status"], "censored")
        self.assertEqual(len(event["future_light"]), 3)
        self.assertIsNone(event["error"])
        self.assertIsNone(event["illumination"]["income_error_half_units"])
        self.assertIsNone(event["diagnostic"]["income_error"])
        self.assertIsNone(event["night"])

    def test_successful_purchase_rejection_is_not_hidden(self):
        unique = self.analysis["unique_histories"]["by_phase"]["noon-or-afternoon"]
        self.assertEqual((unique["purchases"], unique["old_income_overestimates"], unique["new_income_overestimates"]), (116, 65, 5))
        self.assertEqual((unique["diagnostic_nonbirth_rejections"], unique["diagnostic_nonbirth_survivor_rejections"]), (10, 1))
        h = self.histories["rotating-50/control"]
        self.assertIsNone(h["life"]["death_tick"])
        rejected, = [e for e in h["events"] if e["diagnostic"]["newly_rejects_nonbirth_purchase"]]
        self.assertEqual(rejected["tick"], 910170)
        self.assertFalse(rejected["diagnostic"]["birth_exempt"])
        self.assertTrue(rejected["sunset_covers_nominal_night"])

    def test_fewer_overestimates_does_not_mean_better_overall_accuracy(self):
        result = self.analysis["unique_histories"]["income_errors"]["noon-or-afternoon"]
        self.assertEqual(result["complete_windows"], 116)
        self.assertEqual((result["original"]["absolute_total"], result["diagnostic"]["absolute_total"]), (4746, 6128))
        self.assertEqual((result["original"]["largest_underestimate"], result["diagnostic"]["largest_underestimate"]), (187, 265))
        self.assertEqual((result["smaller_absolute_error"], result["larger_absolute_error"]), (39, 66))

    def test_exact_night_funding_does_not_cover_dark_dawn(self):
        dawn = self.histories["rotating-49/candidate"]["dawns"][1]
        self.assertEqual((dawn["tick"], dawn["initial_after_dawn"], dawn["observed_tick"], dawn["stop_reason"]),
                         (912960, 0, 913290, "first-income"))
        dark = dawn["before_first_income"]
        self.assertEqual((dark["maintenance_due"], dark["maintenance_paid"], dark["maintenance_unpaid"]), (20, 0, 20))
        self.assertEqual(dark["shortages"], [913020, 913080, 913140, 913200, 913260])
        self.assertEqual(dawn["samples"][-1]["income"], 1)
        self.assertEqual(self.analysis["unique_histories"]["dawns_with_dark_shortage"], 1)

    def test_dawn_capture_end_death_and_noon_are_explicit(self):
        entry = self.data["cases"][3]
        rows, receipts, lights, _ = audit.check_history(entry["case"], entry["arms"]["candidate"]["analysis"])
        index = next(i for i, r in enumerate(rows) if r["tick"] == 912960)
        life = entry["arms"]["candidate"]["analysis"]["focal"]["life"]
        d = audit.dawn_window(rows[:index + 3], receipts[:index + 3], lights[:index + 3], life, index)
        self.assertEqual(d["stop_reason"], "capture-end")
        self.assertEqual(d["observed_tick"], 912990)
        d = audit.dawn_window(rows[:index + 1], receipts[:index + 1], lights[:index + 1], life, index)
        self.assertIsNone(d["balance"])
        # Endpoint recognition is independent of balance validation, which the
        # shared window tests exercise for terminal discard and censored income.
        with patch.object(audit.energy, "window", return_value=None):
            d = audit.dawn_window(rows, receipts, lights, {**life, "death_tick": 912990}, index)
            self.assertEqual((d["stop_reason"], d["observed_tick"]), ("death", 912990))
            altered = copy.deepcopy(receipts)
            for r in altered[index:index + 65]:
                r["income"] = 0
            d = audit.dawn_window(rows, altered, lights, life, index)
            self.assertEqual((d["stop_reason"], d["observed_tick"]), ("noon-without-income", 913920))

    def test_unsupported_build_or_capture_sources_rejected(self):
        for fault in ("source", "build"):
            d = {**self.data, "settings": dict(self.data["settings"]), "source_sha256": dict(self.data["source_sha256"])}
            if fault == "source": d["source_sha256"]["src/garden_light.c"] = "0" * 64
            else: d["settings"]["TOY_FACTORY_GARDEN_LEAF_MAINTENANCE"] = "ON"
            with self.subTest(fault=fault), self.assertRaisesRegex(RuntimeError, "unsupported captured"):
                audit.check_capture(d)

    def test_corrupt_coverage_clock_sun_bound_and_budget_rejected(self):
        entry = self.data["cases"][3]
        for fault in ("coverage", "clock", "sun", "bound", "budget"):
            a = copy.deepcopy(entry["arms"]["candidate"]["analysis"])
            step = a["focal"]["steps"][1]
            if fault == "coverage": a["followup_steps"].pop()
            elif fault == "clock": step["sun"][0] += 1
            elif fault == "sun": step["sun"][1] += 1
            elif fault == "bound":
                step = next(s for s in audit.previous.steps(a) if s["plant"]["uptake"] and s["plant"]["uptake"][0][1] > 0)
                step["plant"]["active_leaves"] = 0
            else: step["plant"]["stages"][3][0] -= 1
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                audit.check_history(entry["case"], a)

    def test_recomputation_is_read_only_without_native_calls(self):
        before = audit.energy.identity(self.data)
        with patch.object(audit.previous.order.training, "native", side_effect=AssertionError("ran simulation")):
            self.assertEqual(audit.analyze(self.data), self.analysis)
        self.assertEqual(audit.energy.identity(self.data), before)

    def test_saved_reanalysis_and_corruption_rejected(self):
        path = audit.ROOT / RESULTS
        if not path.exists():
            self.skipTest("offline export not completed yet")
        self.assertEqual(audit.digest(path), RESULTS_SHA)
        with gzip.open(path, "rt") as stream:
            value = json.load(stream)
        with patch.object(audit.previous.order.training, "native", side_effect=AssertionError("ran simulation")):
            audit.check_value(value)
            for fault in ("input", "protocol", "native", "dedup", "light", "partition", "diagnostic", "dawn", "source"):
                bad = copy.deepcopy(value)
                h = bad["analysis"]["histories"][0]
                if fault == "input": bad["input_sha256"] = "0" * 64
                elif fault == "protocol": bad["protocol_sha256"] = "0" * 64
                elif fault == "native": bad["native_calls"] = 1
                elif fault == "dedup": h["canonical_history"] = "invented"
                elif fault == "light": h["events"][0]["future_light"][0]["strength"] += 1
                elif fault == "partition": h["events"][0]["illumination"]["income_error_half_units"]["globally_dim"] += 1
                elif fault == "diagnostic": h["events"][0]["diagnostic"]["credit"] += 1
                elif fault == "dawn": h["dawns"][0]["initial_after_dawn"] += 1
                else: bad["source_sha256"][audit.INPUT] = "0" * 64
                with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                    audit.check_value(bad)


if __name__ == "__main__":
    unittest.main()
