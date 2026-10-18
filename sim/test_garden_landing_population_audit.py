#!/usr/bin/env python3
"""Offline funding, unbiased window coverage, cohort identity and saved receipts."""

import copy
import gzip
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_population_audit as audit

RESULT = audit.ROOT / "benchmarks/garden-seasons/landing-population-audit-results.json.gz"
RESULT_SHA = "c40da0fc11e0a9e7cb1480faa0cbaaa328c758ddea8681d7f8981084244cf461"


def flow(income=0, due=0, growth=0, reproduction=0):
    return {"income": income, "due": due, "growth": growth, "reproduction": reproduction}


def plant(identity=1, birth=0, death=None, shortages=()):
    return {"life": {"id": identity, "birth_tick": birth, "death_tick": death},
            "shortages": [{"tick": t} for t in shortages]}


class ArithmeticTests(unittest.TestCase):
    def test_funding_caps_order_and_spending_modes(self):
        self.assertEqual(audit.required_opening([flow(1, 4, 7, 48)], 256, "all"), 58)
        self.assertEqual(audit.required_opening([flow(1, 4, 7, 48)], 256, "no_reproduction"), 10)
        self.assertEqual(audit.required_opening([flow(1, 4, 7, 48)], 256, "maintenance_only"), 3)
        self.assertIsNone(audit.required_opening([flow(999), flow(0, 257)], 256, "all"))
        self.assertEqual(audit.required_opening([flow(999), flow(0, 257)], 512, "all"), 0)
        self.assertEqual(audit.required_opening([], 256, "all"), 0)

    def test_reverse_funding_matches_forward_search(self):
        rng = random.Random(1729)
        for _ in range(120):
            samples = [flow(rng.randrange(130), rng.randrange(40), rng.randrange(30), rng.randrange(50))
                       for _ in range(rng.randrange(1, 9))]
            for capacity in (256, 512):
                for mode in ("all", "no_reproduction", "maintenance_only"):
                    def funds(opening):
                        for s in samples:
                            opening = min(capacity, opening + s["income"]) - s["due"]
                            opening -= s["growth"] if mode != "maintenance_only" else 0
                            opening -= s["reproduction"] if mode == "all" else 0
                            if opening < 0:
                                return False
                        return True
                    expected = next((n for n in range(capacity + 1) if funds(n)), None)
                    self.assertEqual(audit.required_opening(samples, capacity, mode), expected)

    def test_invalid_funding_rejected_before_capacity_exit(self):
        for key in flow():
            for value in (-1, True, 1.5):
                sample = flow()
                sample[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(RuntimeError):
                    audit.required_opening([sample, flow(0, 999)], 256, "all")
        for capacity, mode in ((True, "all"), (0, "all"), (256, "maybe")):
            with self.assertRaises(RuntimeError):
                audit.required_opening([], capacity, mode)

    def test_solar_boundary_union_clipping_and_focal(self):
        self.assertEqual(audit.intervals(plant(shortages=[2880])), [[15, 6705]])
        self.assertEqual(audit.intervals(plant(shortages=[2820, 2880, 6720])), [[15, 10545]])
        self.assertEqual(audit.intervals(plant(birth=3000, death=7000, shortages=[6720])), [[3000, 7000]])
        self.assertEqual(audit.intervals(plant(shortages=[2880, 18240])), [[15, 6705], [14400, 22065]])
        self.assertEqual(audit.intervals(plant(identity=9, birth=403365, death=457020)), [[403365, 457020]])
        self.assertEqual(audit.intervals(plant()), [])

    def test_age_boundaries_are_actual_age(self):
        for elapsed, expected in ((0, "through_1_day"), (3840, "through_1_day"),
                                  (3855, "through_16_days"), (61440, "through_16_days"), (61455, "older")):
            self.assertEqual(audit.age_band(10000 + elapsed, 10000), expected)
        with self.assertRaises(RuntimeError):
            audit.age_band(9999, 10000)

    def test_ledger_identity_ignores_ids_and_future_seed_outcomes(self):
        a = {"lineages": [{"id": 1, "parent": 0, "birth_tick": 0, "column": 3, "species": 0, "death_tick": None}],
             "seeds": [{"parent": 1, "birth_tick": 60, "column": 4, "species": 0, "generation": 1,
                        "outcome": "expired", "child_id": None, "end_tick": 300}]}
        b = copy.deepcopy(a)
        b["lineages"][0]["id"] = 8
        b["seeds"][0].update(parent=8, outcome="germinated", child_id=9, end_tick=180)
        self.assertIsNone(audit.first_ledger_difference(a, b, "seed_purchase"))
        self.assertIsNone(audit.first_ledger_difference(a, b, "birth"))
        b["seeds"][0]["column"] = 5
        self.assertEqual(audit.first_ledger_difference(a, b, "seed_purchase")["tick"], 60)
        b["lineages"][0]["death_tick"] = 120
        self.assertEqual(audit.first_ledger_difference(a, b, "death")["tick"], 120)

    def test_export_refuses_existing_output_before_reading_inputs(self):
        with tempfile.TemporaryDirectory() as temporary, self.assertRaisesRegex(RuntimeError, "fresh output"):
            audit.export(Path("/missing"), Path(temporary))


@unittest.skipUnless(RESULT.exists(), "saved population audit not captured yet")
class CapturedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if audit.digest(RESULT) != RESULT_SHA:
            raise RuntimeError("captured audit fixture changed")
        with gzip.open(RESULT, "rt") as stream:
            cls.value = json.load(stream)

    def test_portable_verification_needs_no_process_or_native_binary(self):
        with patch("subprocess.run", side_effect=AssertionError("unexpected process")), \
             patch("subprocess.Popen", side_effect=AssertionError("unexpected process")):
            audit.check_value(self.value)

    def test_missing_window_sample_and_wrong_summary_rejected(self):
        bad = copy.deepcopy(self.value)
        bad["excerpts"][0]["arms"]["control"][0]["segments"][0]["rows"].pop()
        with self.assertRaisesRegex(RuntimeError, "incomplete/reordered"):
            audit.check_value(bad)
        bad = {**self.value, "analysis": []}
        with self.assertRaisesRegex(RuntimeError, "analysis differs"):
            audit.check_value(bad)

    def test_changed_income_and_opening_identity_rejected(self):
        bad = copy.deepcopy(self.value["excerpts"][0]["arms"]["control"])
        segment = bad[0]["segments"][0]
        segment["rows"][0]["plant"]["uptake"][0][1] += 1
        with self.assertRaisesRegex(RuntimeError, "uptake does not balance"):
            audit.analyze_world(audit.cases()[0]["arms"]["control"], bad)
        segment["rows"][0]["plant"]["uptake"][0][1] -= 1
        segment["previous"]["id"] += 99
        with self.assertRaisesRegex(RuntimeError, "preceding identity"):
            audit.analyze_world(audit.cases()[0]["arms"]["control"], bad)

    def test_focal_earlier_flower_not_later_and_different_seed_site(self):
        for entry in self.value["analysis"]:
            focal = [next(p for p in entry["arms"][a]["plants"] if p["life"]["id"] == 9)
                     for a in audit.population.ARMS]
            self.assertEqual([p["focal"]["first_flower"] for p in focal], [406515, 404100])
            self.assertEqual([p["life"]["death_tick"] for p in focal], [457020, 457020])
            self.assertEqual([p["focal"]["seeds"][0]["birth_tick"] for p in focal], [406860, 406860])
            self.assertEqual([p["focal"]["seeds"][0]["column"] for p in focal], [17, 19])

    def test_matched_cohort_improvement_is_not_population_qualification(self):
        for entry in self.value["analysis"]:
            for arm, energy, water in (("control", 11, 177), ("candidate", 0, 168)):
                matched = entry["arms"][arm]["cohorts"]["matched_offspring"]
                self.assertEqual(len(matched["ids"]), 8)
                self.assertEqual(matched["energy"]["unpaid"], energy)
                self.assertEqual(matched["water"]["unpaid"], water)
            self.assertEqual(entry["first_ledger_differences"]["seed_purchase"]["tick"], 406740)
            self.assertEqual(entry["first_ledger_differences"]["birth"]["tick"], 414180)
            self.assertEqual(entry["first_ledger_differences"]["death"]["tick"], 415560)

    def test_late_shortages_are_not_recent_construction_or_seed_debits(self):
        for entry, expected_bills, expected_units in zip(self.value["analysis"], (16, 34), (53, 113), strict=True):
            events = [s for p in entry["arms"]["candidate"]["plants"] if p["life"]["generation"] > 0
                      for s in p["shortages"] if s["event"]["energy"]["unpaid"] > 0 and
                      s["preceding_day"]["resources"]["energy"]["growth"] == 0]
            self.assertEqual(len(events), expected_bills)
            self.assertEqual(sum(s["event"]["energy"]["unpaid"] for s in events), expected_units)
            self.assertTrue(all(s["preceding_day"]["resources"]["energy"]["reproduction"] == 0 for s in events))
        p = next(p for p in self.value["analysis"][0]["arms"]["candidate"]["plants"] if p["life"]["id"] == 28)
        w = p["windows"][0]
        self.assertTrue(w["ends_at_death"])
        self.assertEqual(w["resources"]["energy"], {"initial": 111, "income": 364, "overflow": 2,
                         "upkeep": 473, "growth": 0, "reproduction": 0, "discarded": 0, "final": 0})
        self.assertIsNone(w["funding"]["energy"]["maintenance_only"])

    def test_malformed_focal_forecast_rejected(self):
        bad = copy.deepcopy(self.value["excerpts"][0]["arms"]["candidate"])
        focal = next(p for p in bad if p["id"] == 9)
        row = next(r for r in focal["segments"][0]["rows"] if r["tick"] == 403545)
        row["focal"]["bids"][0]["dawn_gate"]["allowed"] = True
        with self.assertRaises(RuntimeError):
            audit.analyze_world(audit.cases()[0]["arms"]["candidate"], bad)


if __name__ == "__main__":
    unittest.main()
