#!/usr/bin/env python3
"""Offline energy accounting, censored endpoints, selection and frozen evidence."""

import copy
import gzip
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_energy_audit as audit

RESULTS = "benchmarks/garden-seasons/landing-energy-audit-results.json.gz"
RESULTS_SHA = "7943e9edb3b2e4c1f8f30925d46bbce1a7d5a5ca8ed7f70ee228f2694fd4e14b"


class AccountingTests(unittest.TestCase):
    def fixture(self):
        steps = [{"tick": tick, "plant": {"stages": [[0, 0, 0, 0, 1] for _ in range(5)]}}
                 for tick in (15, 30, 45)]
        for step, final in zip(steps, (7, 9, 12), strict=True):
            step["plant"]["stages"][3][0] = final
            step["plant"]["stages"][4][0] = final
        steps[0]["plant"]["stages"][3][0] = 10
        receipts = [dict.fromkeys(audit.TRANSFER_FIELDS, 0) for _ in steps]
        receipts[0]["reproduction"] = 3
        receipts[1].update(income=5, upkeep=1, growth=2)
        receipts[2].update(income=4, upkeep=1)
        return steps, receipts, {"death_tick": None}

    def test_post_growth_includes_same_tick_reproduction_but_not_old_income(self):
        steps, receipts, life = self.fixture()
        receipts[0]["income"] = 99
        after = audit.window(steps, receipts, life, 0, 45, after_growth=True)
        night = audit.window(steps, receipts, life, 0, 45, after_growth=False)
        self.assertEqual((after["initial"], after["final"], after["status"]), (10, 12, "alive"))
        self.assertEqual(after["transfers"], dict(income=9, upkeep=2, growth=2, reproduction=3, overflow=0, discarded=0))
        self.assertEqual((night["initial"], night["transfers"]["reproduction"]), (7, 0))

    def test_death_at_endpoint_and_missing_followup_are_not_full_windows(self):
        steps, receipts, life = self.fixture()
        censored = audit.window(steps[:2], receipts[:2], life, 0, 45, after_growth=True)
        self.assertEqual((censored["status"], censored["observed_tick"], censored["final"]), ("censored", 30, 9))
        life["death_tick"] = 45
        steps[-1]["plant"]["stages"][-1][0] = 0
        receipts[-1]["discarded"] = 12
        for target in (45, 60):
            dead = audit.window(steps, receipts, life, 0, target, after_growth=True)
            self.assertEqual((dead["status"], dead["observed_tick"], dead["final"]), ("dead", 45, 0))
            self.assertEqual(dead["transfers"]["income"], 9)
        self.assertEqual(audit.window(steps, receipts, life, 0, 30, after_growth=True)["status"], "alive")

    def test_missing_sample_bad_endpoint_and_unbalanced_window_rejected(self):
        steps, receipts, life = self.fixture()
        for target in (15, 31):
            with self.assertRaises(RuntimeError):
                audit.window(steps, receipts, life, 0, target, after_growth=True)
        with self.assertRaisesRegex(RuntimeError, "missing sample"):
            audit.window(steps[::2], receipts[::2], life, 0, 45, after_growth=True)
        receipts[-1]["income"] += 1
        with self.assertRaisesRegex(RuntimeError, "budget differs"):
            audit.window(steps, receipts, life, 0, 45, after_growth=True)

    def test_first_wins_ties_and_all_ineligible_are_not_paid_actions(self):
        def bid(tip, allowed=True):
            return {"tip": tip, "priority": 7, "budget": {"allowed": True},
                    "water_gate": {"allowed": True}, "energy_gate": {"allowed": allowed}}
        self.assertEqual(audit.select_bid({"bids": []}), (None, False))
        a, b = bid(1), bid(2)
        self.assertEqual(audit.select_bid({"bids": [a, b]}), (a, True))
        a["energy_gate"]["allowed"] = False
        self.assertEqual(audit.select_bid({"bids": [a, b]}), (b, True))
        b["energy_gate"]["allowed"] = False
        self.assertEqual(audit.select_bid({"bids": [a, b]}), (a, False))

    def test_phase_boundaries(self):
        self.assertEqual([audit.phase_band(p) for p in (0, 63, 64, 127, 128, 255)],
                         ["before-noon"] * 2 + ["noon-or-afternoon"] * 2 + ["night"] * 2)

    def test_no_clobber_or_export_inside_source_tree(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(
                audit, "source_files", side_effect=AssertionError("read before path validation")):
            existing = Path(temporary) / "existing"
            existing.mkdir()
            marker = existing / "keep"
            marker.write_bytes(b"preserve")
            for path in (existing, audit.ROOT / "sim" / "not-an-output"):
                with self.assertRaisesRegex(RuntimeError, "fresh output"):
                    audit.export(path)
            self.assertEqual(marker.read_bytes(), b"preserve")

    def test_source_archive_rejects_duplicates_links_and_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "source.tar.gz"
            for names in (("valid", "valid"), ("../outside",), ("/outside",), ("link",)):
                with tarfile.open(path, "w:gz") as archive:
                    for name in names:
                        entry = tarfile.TarInfo(name)
                        if name == "link":
                            entry.type = tarfile.SYMTYPE
                            entry.linkname = "outside"
                        archive.addfile(entry)
                with self.subTest(names=names), self.assertRaises(RuntimeError):
                    audit.archived_sources(path)
            with tarfile.open(path, "w:gz") as archive:
                entry = tarfile.TarInfo("valid")
                entry.size = 4
                archive.addfile(entry, io.BytesIO(b"test"))
            self.assertEqual(audit.archived_sources(path), {"valid": audit.hashlib.sha256(b"test").hexdigest()})

    def test_bundle_cannot_omit_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            audit.write_json(path / "manifest.json", {"rule": audit.RULE, "status": "complete", "artifacts": {}})
            with self.assertRaisesRegex(RuntimeError, "incomplete/wrong audit bundle"):
                audit.verify(path)


class FrozenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.object(audit.previous.order.training, "native", side_effect=AssertionError("ran simulation")):
            cls.data = audit.load_input()
            cls.analysis = audit.analyze(cls.data)
        cls.histories = {h["id"]: h for h in cls.analysis["histories"]}

    def test_complete_panel_and_exact_duplicate_accounting(self):
        all_histories, unique = (self.analysis[k] for k in ("all_histories", "unique_histories"))
        self.assertEqual((all_histories["histories"], all_histories["paid_events"], all_histories["step_ups"]), (10, 194, 21))
        self.assertEqual((unique["histories"], unique["paid_events"], unique["step_ups"]), (8, 134, 15))
        self.assertEqual(unique["by_threshold"], {"9": 8, "17": 4, "25": 3})
        self.assertEqual((all_histories["opportunities"], unique["opportunities"], unique["energy_rejected_opportunities"]), (175, 169, 154))
        duplicates = [h["id"] for h in self.histories.values() if h["canonical_history"] != h["id"]]
        self.assertEqual(duplicates, ["fixed-45/candidate", "fixed-46/candidate"])
        for h in self.histories.values():
            self.assertTrue(all(h["case"]["tick"] <= e["tick"] < h["case"]["tick"] + audit.DAY for e in h["events"]))

    def test_two_clean_failures_are_income_error_not_growth_or_cap(self):
        for name, credit, income, final, error in (("rotating-49/candidate", 49, 26, 43, 23),
                                                   ("rotating-50/candidate", 25, 6, 45, 19)):
            event, = [e for e in self.histories[name]["events"] if e["step_up"]]
            self.assertTrue(event["clean_interval"])
            self.assertEqual(event["bid"]["energy_gate"]["daylight_credit"], credit)
            self.assertEqual((event["sunset"]["transfers"]["income"], event["sunset"]["final"]), (income, final))
            self.assertEqual(event["error"]["predicted_minus_actual"], error)
            self.assertEqual(event["error"]["terms"], dict(income=error, maintenance=0, later_growth=0,
                                                           reproduction=0, overflow=0, discard=0, forecast_cap=0))
            self.assertEqual(event["sunset"]["status"], "alive")
            self.assertEqual(event["night"]["status"], "dead")
            self.assertFalse(event["sunset_covers_nominal_night"])
            self.assertEqual((64 + event["sunset"]["target_tick"] // audit.STEP) % 256, 128)
            self.assertEqual((64 + event["night"]["target_tick"] // audit.STEP) % 256, 0)
            self.assertEqual(event["night"]["target_tick"] - event["sunset"]["target_tick"], 128 * audit.STEP)
            self.assertTrue(event["night"]["energy_shortages"])

    def test_successful_growth_cap_and_overflow_are_not_income_only_error(self):
        event = next(e for e in self.histories["fixed-45/control"]["events"] if e["step_up"])
        self.assertFalse(event["clean_interval"])
        self.assertEqual(event["error"], {"predicted_minus_actual": 13, "terms": {
            "income": -374, "maintenance": 26, "later_growth": 200, "reproduction": 0,
            "overflow": 189, "discard": 0, "forecast_cap": -28}})
        self.assertEqual(event["night"]["status"], "alive")
        for h in self.histories.values():
            for e in h["events"]:
                if e["error"] is not None:
                    self.assertEqual(sum(e["error"]["terms"].values()), e["error"]["predicted_minus_actual"])

    def test_zero_income_would_reject_successful_morning_steps(self):
        phase = self.analysis["unique_histories"]["by_phase"]
        morning, afternoon = phase["before-noon"], phase["noon-or-afternoon"]
        self.assertEqual((morning["events"], morning["confirmed_first_day"], morning["cash_only_rejects_confirmed"]), (6, 6, 6))
        self.assertEqual((afternoon["events"], afternoon["confirmed_first_day"], afternoon["cash_only_rejects_confirmed"]), (9, 3, 0))
        self.assertEqual((morning["night_alive"], afternoon["night_alive"], afternoon["night_dead"]), (6, 3, 6))

    def test_opportunity_is_per_decision_not_tip_and_includes_denials(self):
        h = self.histories["rotating-48/candidate"]
        self.assertEqual(len(h["opportunities"]), 151)
        self.assertEqual(len({o["tick"] for o in h["opportunities"]}), 151)
        self.assertTrue(any(len(o["tips"]) > 1 for o in h["opportunities"]))
        self.assertEqual(sum(o["executed_step_up"] for o in h["opportunities"]), 3)
        self.assertEqual(sum(o["energy_rejects_opportunity"] for o in h["opportunities"]), 148)
        self.assertTrue(any(o["phase_band"] == "night" and o["energy_rejects_opportunity"] for o in h["opportunities"]))

    def test_complete_offline_recomputation_and_no_input_mutation(self):
        before = audit.identity(self.data)
        with patch.object(audit.previous.order.training, "native", side_effect=AssertionError("ran simulation")):
            self.assertEqual(audit.analyze(self.data), self.analysis)
        self.assertEqual(audit.identity(self.data), before)

    def test_bad_history_clock_identity_and_price_rejected(self):
        entry = self.data["cases"][0]
        for fault in ("sample", "identity", "clock", "price"):
            a = copy.deepcopy(entry["arms"]["control"]["analysis"])
            step = a["focal"]["steps"][1]
            if fault == "sample": a["followup_steps"].pop()
            elif fault == "identity": step["plant"]["id"] += 1
            elif fault == "clock": step["sun"][0] += 1
            else: step["plant"]["stages"][3][0] -= 1
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                audit.check_history(entry["case"], "control", a)

    def test_portable_reanalysis_and_corrupt_evidence_rejected(self):
        path = audit.ROOT / RESULTS
        if not path.exists():
            self.skipTest("offline export not completed yet")
        self.assertEqual(audit.digest(path), RESULTS_SHA)
        with gzip.open(path, "rt") as stream:
            value = json.load(stream)
        with patch.object(audit.previous.order.training, "native", side_effect=AssertionError("ran simulation")):
            audit.check_value(value)
            for fault in ("input", "protocol", "native", "summary", "event", "opportunity", "duplicate", "source"):
                bad = copy.deepcopy(value)
                h = bad["analysis"]["histories"][0]
                if fault == "input": bad["input_sha256"] = "0" * 64
                elif fault == "protocol": bad["protocol_sha256"] = "0" * 64
                elif fault == "native": bad["native_calls"] = 1
                elif fault == "summary": bad["analysis"]["unique_histories"]["histories"] += 1
                elif fault == "event": h["events"][0]["sunset"]["final"] += 1
                elif fault == "opportunity": h["opportunities"].pop()
                elif fault == "duplicate": h["canonical_history"] = "invented"
                else: bad["source_sha256"][audit.INPUT] = "0" * 64
                with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                    audit.check_value(bad)


if __name__ == "__main__":
    unittest.main()
