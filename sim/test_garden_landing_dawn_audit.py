#!/usr/bin/env python3
"""Offline capped funding, dawn timing, successful-growth risks and provenance."""

import copy
import gzip
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_dawn_audit as audit

RESULTS = "benchmarks/garden-seasons/landing-dawn-audit-results.json.gz"
RESULTS_SHA = "6cdfc3ae4318042a6d40d983f369463771e9f326f86a3a7c75a2d67003ee3c88"


def flow(income=0, due=0, growth=0, reproduction=0):
    return {"income": income, "due": due, "growth": growth, "reproduction": reproduction}


class ArithmeticTests(unittest.TestCase):
    def test_backward_balance_order_cap_and_zero(self):
        self.assertEqual(audit.required_opening([], spending=True), 0)
        self.assertEqual(audit.required_opening([flow(1, 4), flow(2, 4)], spending=True), 5)
        self.assertEqual(audit.required_opening([flow(0, 4, 9, 12)], spending=True), 25)
        self.assertEqual(audit.required_opening([flow(0, 4, 9, 12)], spending=False), 4)
        # Income arrives before upkeep, so a payment on the first lit step can still fail.
        self.assertEqual(audit.required_opening([flow(1, 4)], spending=True), 3)
        self.assertEqual(audit.required_opening([flow(300, 4)], spending=True), 0)
        self.assertIsNone(audit.required_opening([flow(300), flow(0, 200), flow(0, 57)], spending=True))
        self.assertEqual(audit.required_opening([flow(300), flow(0, 200), flow(0, 56)], spending=True), 0)

    def test_backward_minimum_matches_independent_forward_search(self):
        rng = random.Random(915)
        for _ in range(200):
            samples = [flow(rng.randrange(100), rng.randrange(33), rng.randrange(60), rng.randrange(60))
                       for _ in range(rng.randrange(1, 9))]
            for spending in (False, True):
                def funds(opening):
                    balance = opening
                    for s in samples:
                        balance = min(256, balance + s["income"])
                        balance -= s["due"] + (s["growth"] + s["reproduction"] if spending else 0)
                        if balance < 0:
                            return False
                    return True
                expected = next((n for n in range(257) if funds(n)), None)
                self.assertEqual(audit.required_opening(samples, spending=spending), expected)

    def test_invalid_funding_and_opening_rejected(self):
        for field in flow():
            for bad in (-1, True, 1.5):
                s = flow()
                s[field] = bad
                with self.subTest(field=field, value=bad), self.assertRaises(RuntimeError):
                    audit.required_opening([s], spending=True)
                with self.subTest(field=field, value=bad), self.assertRaises(RuntimeError):
                    audit.required_opening([s, flow(0, 257)], spending=True)
        for bad in (-1, 257, True):
            with self.assertRaises(RuntimeError):
                audit.funding([], bad)

    def test_current_light_estimate_rounding_and_unavailable(self):
        for phase, strength, cost, first, payment, reserve in (
                (64, 255, 4, 11, 12, 12), (124, 32, 4, 20, 20, 20),
                (64, 64, 4, 64, 64, 64), (64, 255, 8192, 11, 12, 24576)):
            self.assertEqual(audit.diagnostic(phase, strength, cost),
                             {"status": "estimated", "first_phase": first, "payment_phase": payment, "reserve": reserve})
        for phase, strength in ((64, 24), (127, 24), (64, 63)):
            self.assertEqual(audit.diagnostic(phase, strength, 4),
                             {"status": "unavailable", "first_phase": None, "payment_phase": None, "reserve": None})
        for args in ((63, 100, 4), (128, 100, 4), (True, 100, 4), (64, 23, 4), (64, 256, 4), (64, 100, 0)):
            with self.assertRaises(RuntimeError):
                audit.diagnostic(*args)
        with self.assertRaises(TypeError):
            audit.diagnostic(64, 100, 4, future_climate=100)

    def test_diagnostic_thresholds_and_monotone_reserve(self):
        for phase in range(64, 128):
            last = None
            for strength in range(24, 256):
                d = audit.diagnostic(phase, strength, 4)
                if d["first_phase"] is None:
                    self.assertLess(24 + 231 * (strength - 24) // audit.light.base_beam(phase), 64)
                    continue
                q = d["first_phase"]
                self.assertGreaterEqual(24 + audit.light.base_beam(q) * (strength - 24) // audit.light.base_beam(phase), 64)
                self.assertLess(24 + audit.light.base_beam(q - 1) * (strength - 24) // audit.light.base_beam(phase), 64)
                self.assertEqual(d["payment_phase"] % 4, 0)
                self.assertTrue(q <= d["payment_phase"] < q + 4)
                if last is not None:
                    self.assertLessEqual(d["reserve"], last)
                last = d["reserve"]

    def test_both_margins_scope_and_no_unknown_verdict(self):
        bid = {"action": 1, "energy_gate": {"sun_phase": 64, "maintenance": 4, "night_upkeep": 128},
               "daylight_gate": {"active": True, "sun_strength": 255, "projected_sunset": 140},
               "afternoon_gate": {"applies": True, "margin": 12}}
        self.assertFalse(audit.assess(bid)["newly_rejects"])
        bid["afternoon_gate"]["margin"] = 11
        self.assertTrue(audit.assess(bid)["newly_rejects"])
        bid["afternoon_gate"]["applies"] = False
        self.assertFalse(audit.assess(bid)["newly_rejects"])
        bid["daylight_gate"]["projected_sunset"] = 139
        self.assertTrue(audit.assess(bid)["newly_rejects"])
        bid["daylight_gate"]["sun_strength"] = 24
        self.assertIsNone(audit.assess(bid)["newly_rejects"])
        bid["daylight_gate"]["active"] = False
        self.assertFalse(audit.assess(bid)["newly_rejects"])
        bid["action"] = 0
        self.assertIsNone(audit.assess(bid)["estimate"])
        bid["action"] = 1
        for phase in (0, 63, 128, 255):
            bid["energy_gate"]["sun_phase"] = phase
            self.assertIsNone(audit.assess(bid)["estimate"])

    def test_no_clobber_and_wrong_bundle_identity(self):
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

    def test_complete_histories_and_two_levels_of_deduplication(self):
        raw, unique = [self.analysis[k] for k in ("all_histories", "unique_histories")]
        self.assertEqual((raw["histories"], raw["samples"], raw["mornings"], raw["sunsets"]), (10, 53880, 210, 211))
        self.assertEqual((unique["histories"], unique["samples"], unique["mornings"]), (7, 34908, 136))
        self.assertEqual(self.analysis["unique_morning_windows"], {"count": 133, "with_shortages": 2})
        self.assertEqual(raw["sunset_status"], {"alive": 210, "dead": 1})
        self.assertEqual(raw["morning_status"], {"alive": 210})
        self.assertEqual(raw["complete_morning_requirements"]["maintenance_only"], raw["complete_morning_requirements"]["recorded_spending"])
        for h in self.histories.values():
            self.assertEqual(h["life"]["seeds_created"], 0)
            for totals in h["totals"].values():
                self.assertEqual(totals["initial"] + totals["income"],
                                 sum(v for k, v in totals.items() if k not in ("initial", "income")))

    def test_first_income_does_not_end_shortages(self):
        for arm in ("control", "candidate"):
            d = next(d for d in self.histories["rotating-49/" + arm]["mornings"] if d["at_dawn"]["tick"] == 912960)
            self.assertEqual(d["funding"]["maintenance_only"], {"required": 21, "shortfall": 21})
            first = d["boundaries"]["income"]
            self.assertEqual((first["tick"], first["phase"], first["income"], first["due_before"]), (913290, 22, 1, 20))
            self.assertEqual(first["funding"]["maintenance_only"]["required"], 20)
            self.assertEqual([s["tick"] for s in d["samples"] if s["unpaid"]],
                             [913020, 913080, 913140, 913200, 913260, 913320])
            self.assertEqual((d["first_fully_paid_after_shortage"], d["shortages_after_first_paid"]), (913380, []))

    def test_sunset_error_and_after_dawn_need_are_separate(self):
        h = self.histories["rotating-49/candidate"]
        n = next(n for n in h["sunsets"] if n["actual"]["start_tick"] == 914880)
        self.assertEqual((n["funding"]["opening"], n["nominal_night"], n["funding"]["maintenance_only"]["required"]), (126, 128, 143))
        self.assertEqual(n["funding"]["maintenance_only"]["shortfall"], 17)
        d = next(d for d in h["mornings"] if d["at_dawn"]["tick"] == n["dawn_tick"])
        self.assertEqual((d["at_dawn"]["unpaid"], d["unpaid"], d["funding"]["maintenance_only"]["required"]), (2, 15, 15))
        self.assertEqual(d["boundaries"]["income"]["tick"], 917040)
        self.assertEqual(d["first_fully_paid_after_shortage"], 917100)
        last = next(e for e in h["purchases"] if e["tick"] == 914400)
        self.assertEqual((last["forecast"]["predicted"], last["forecast"]["error"]), (128, 2))

    def test_successful_growth_risks_and_inactive_controls_retained(self):
        diagnostic = self.analysis["candidate_diagnostic"]
        self.assertEqual(diagnostic["rotating-49/candidate"]["newly_rejected"], [910425, 910980, 914130, 914325, 914400])
        self.assertEqual(diagnostic["rotating-50/candidate"]["newly_rejected"], [910140, 910530])
        self.assertEqual(sum(d["active_purchases"] for d in diagnostic.values()), 78)
        self.assertFalse(any(d["unavailable"] for d in diagnostic.values()))
        for h in self.histories.values():
            for e in h["purchases"]:
                if h["arm"] == "control":
                    self.assertFalse(e["diagnostic"]["active"] or e["diagnostic"]["newly_rejects"])
        h = self.histories["rotating-50/candidate"]
        finish = next(e for e in h["purchases"] if e["tick"] == 910140)
        self.assertEqual((finish["bid"]["action"], finish["forecast"]["predicted"], finish["forecast"]["sunset"]["final"]), (2, 109, 206))
        self.assertIsNone(h["life"]["death_tick"])

    def test_diagnostic_is_not_a_guaranteed_morning_bound(self):
        h = self.histories["rotating-49/candidate"]
        e = next(e for e in h["purchases"] if e["tick"] == 910980)
        self.assertEqual((e["diagnostic"]["estimate"]["reserve"], e["evaluation"]["frozen_morning_requirement"]), (20, 21))
        self.assertEqual((e["diagnostic"]["estimate"]["first_phase"], e["evaluation"]["actual_first_global_phase"]), (20, 22))
        self.assertEqual(e["bid"]["energy_gate"]["post_nodes"], e["evaluation"]["actual_dawn_nodes"])
        errors = [e["evaluation"]["reserve_minus_requirement"] for h in self.histories.values()
                  for e in h["purchases"] if e["diagnostic"]["active"]]
        self.assertEqual((len(errors), sum(v < 0 for v in errors), sum(v == 0 for v in errors),
                          min(errors), max(errors)), (78, 40, 8, -11, 9))

    def test_censored_and_dead_windows_never_invent_the_future(self):
        entry = self.data["cases"][3]
        a = entry["arms"]["candidate"]["analysis"]
        rows, receipts, lights, _ = audit.light.check_history(entry["case"], a)
        samples = [audit.sample(s, r, l) for s, r, l in zip(rows, receipts, lights, strict=True)]
        i = next(i for i, s in enumerate(samples) if s["tick"] == 912960)
        for end in (i + 1, i + 3):
            d = audit.morning(rows[:end], receipts[:end], samples[:end], a["focal"]["life"], i)
            self.assertEqual(d["actual"]["status"], "censored")
            self.assertEqual(len(d["samples"]), end - i - 1)
            self.assertIsNone(d["boundaries"]["income"])
        dead = self.histories["rotating-49/control"]["sunsets"][-1]
        self.assertEqual(dead["actual"]["status"], "dead")
        self.assertEqual(dead["actual"]["observed_tick"], 916440)
        self.assertFalse(dead["morning_observed"])
        self.assertEqual(dead["samples"][-1]["tick"], 916440)

    def test_invalid_sources_build_and_receipts_rejected(self):
        for fault in ("source", "build"):
            value = {**self.data, "settings": dict(self.data["settings"]), "source_sha256": dict(self.data["source_sha256"])}
            if fault == "source": value["source_sha256"]["src/garden_world.c"] = "0" * 64
            else: value["settings"]["TOY_FACTORY_GARDEN_LEAF_MAINTENANCE"] = "ON"
            with self.assertRaisesRegex(RuntimeError, "unsupported captured"):
                audit.check_capture(value)
        entry = self.data["cases"][3]
        rows, receipts, lights, _ = audit.light.check_history(entry["case"], entry["arms"]["candidate"]["analysis"])
        i = next(i for i, r in enumerate(rows) if r["tick"] == 912960)
        for key in ("upkeep", "overflow"):
            bad = {**receipts[i], key: receipts[i][key] + 1}
            with self.assertRaises(RuntimeError):
                audit.sample(rows[i], bad, lights[i])
        bad = copy.deepcopy(rows[i])
        bad["plant"]["stages"][1][3] ^= 2
        with self.assertRaises(RuntimeError):
            audit.sample(bad, receipts[i], lights[i])

    def test_read_only_recomputation_and_no_native_calls(self):
        before = audit.energy.identity(self.data)
        with patch.object(audit.previous.order.training, "native", side_effect=AssertionError("ran simulation")):
            self.assertEqual(audit.analyze(self.data), self.analysis)
        self.assertEqual(audit.energy.identity(self.data), before)

    def test_saved_reanalysis_and_corruption_rejected(self):
        path = audit.ROOT / RESULTS
        self.assertEqual(audit.digest(path), RESULTS_SHA)
        with gzip.open(path, "rt") as stream:
            value = json.load(stream)
        with patch.object(audit.previous.order.training, "native", side_effect=AssertionError("ran simulation")):
            audit.check_value(value)
            for fault in ("input", "protocol", "calls", "source", "dedup", "dawn", "funding", "diagnostic"):
                bad = copy.deepcopy(value)
                h = bad["analysis"]["histories"][0]
                if fault == "input": bad["input_sha256"] = "0" * 64
                elif fault == "protocol": bad["protocol_sha256"] = "0" * 64
                elif fault == "calls": bad["native_calls"] = 1
                elif fault == "source": bad["source_sha256"][audit.INPUT] = "0" * 64
                elif fault == "dedup": h["canonical_history"] = "invented"
                elif fault == "dawn": h["mornings"][0]["at_dawn"]["unpaid"] += 1
                elif fault == "funding": h["mornings"][0]["funding"]["maintenance_only"]["required"] += 1
                else: bad["analysis"]["candidate_diagnostic"]["rotating-50/candidate"]["newly_rejected"] = []
                with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                    audit.check_value(bad)


if __name__ == "__main__":
    unittest.main()
