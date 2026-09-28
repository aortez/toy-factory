#!/usr/bin/env python3
"""Residence boundaries, matched follow-up, conserved receipts and portable evidence."""

import copy
import gzip
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import garden_season_seed_bank_diagnosis as audit


def plant(energy=144, water=64):
    return {"id": 1, "energy": energy, "water": water, "energy_income": 0, "water_income": 0,
            "nodes": 4, "roots": 2, "stress": 0, "flags": 0, "dead": False,
            "species": "flower", "vigor": 0, "reproduction_cooldown": 0,
            "agent": {"extend": 0, "finish": 0, "wait": 0}}


class DiagnosisTests(unittest.TestCase):
    def test_creation_resolution_expiry_and_closing_boundaries(self):
        seed = {"created_tick": 60, "resolved_tick": 180}
        self.assertEqual(audit.samples(seed, 0), 8)
        self.assertEqual(audit.samples(seed, 60), 7)
        self.assertEqual(audit.samples(seed, 165), 0)
        self.assertEqual(audit.samples(seed, 0, low_age=120), 0)
        seed["resolved_tick"] = 60 + 32 * audit.DAY
        self.assertEqual(audit.samples(seed, 0), 8192)
        self.assertEqual(audit.samples(seed, 0, low_age=120), 8184)
        self.assertEqual(sum(audit.samples(seed, 0, low_age=a*audit.DAY, high_age=b*audit.DAY)
                             for a,b in audit.AGES.values()), 8192)
        self.assertEqual(audit.samples(seed, 0, not_before=120), 8188)
        seed = {"created_tick": 112 * audit.DAY, "resolved_tick": None}
        self.assertEqual(audit.samples(seed, 112 * audit.DAY), 4096)
        self.assertEqual(audit.samples(seed, 0), 4097)
        for s in ({"created_tick": 0, "resolved_tick": 60}, {"created_tick": 60, "resolved_tick": 60},
                  {"created_tick": 60, "resolved_tick": 181}, {"created_tick": audit.END+15, "resolved_tick": None}):
            with self.assertRaises(RuntimeError):
                audit.samples(s, 0)

    def test_child_censoring_exact_day_death_and_durable_grandchild(self):
        child = {"plant": {"birth_tick": 60, "death_tick": 60 + audit.DAY}, "children": []}
        parents = {2: child}
        seed = {"outcome": "germinated", "child": 2}
        self.assertEqual(audit.child_outcome(seed, parents), "early_death")
        child["plant"]["death_tick"] += 15
        self.assertEqual(audit.child_outcome(seed, parents), "day_only")
        parents[3] = {"plant": {"birth_tick": 120, "death_tick": None}, "children": []}
        child["children"] = [3]
        self.assertEqual(audit.child_outcome(seed, parents), "durable")
        child["plant"] = {"birth_tick": audit.END - audit.DAY + 15, "death_tick": None}
        self.assertEqual(audit.child_outcome(seed, parents), "young_alive")
        child["plant"]["death_tick"] = audit.END
        self.assertEqual(audit.child_outcome(seed, parents), "young_dead")
        for name in ("pending", "expired"):
            self.assertEqual(audit.child_outcome({"outcome": name}, {}), name)

    def test_closing_masks_cannot_be_sliced_proportionally_or_exceed_whole(self):
        created = audit.END - 15 * 8
        ledger = {"parents": [{"plant": {"id": 1, "family": 1, "parent": 0, "species": "flower", "death_tick": created+60}}],
                  "seeds": [{"parent": 1, "species": "flower", "column": 4, "created_tick": created,
                    "resolved_tick": None, "outcome": "pending", "child": None,
                    "post_blockers": {"36": 1}, "mature_post_samples": 1}]}
        details = audit.seed_details(ledger, [{"36": 1}])
        self.assertEqual(details[0]["windows"]["closing"]["samples"], 9)
        self.assertEqual(details[0]["windows"]["closing"]["posthumous_samples"], 5)
        summary = audit.inventory(details)
        self.assertEqual(summary["windows"]["closing"]["blocker_overlap"]["spacing"], 1)
        self.assertEqual(summary["windows"]["closing"]["blocker_overlap"]["light"], 1)
        for masks in ([], [{}], [{"36": 2}], [{"32": 1}], [{"1": 1}]):
            with self.assertRaises(RuntimeError):
                audit.seed_details(ledger, masks)

    def test_matched_calendar_cutoff_includes_terminal_and_clips_last_day(self):
        incumbent = {"eight_death": 10 * audit.DAY, "sixteen_death": 2 * audit.DAY}
        self.assertEqual(audit.window_limits(incumbent, 60), {
            "since_split": (60, 2 * audit.DAY), "last_day": (audit.DAY + 15, 2 * audit.DAY)})
        incumbent["sixteen_death"] = 120
        self.assertEqual(audit.window_limits(incumbent, 60)["last_day"], (60, 120))
        incumbent.update(eight_death=None, sixteen_death=None)
        self.assertEqual(audit.window_limits(incumbent, 60)["since_split"], (60, audit.END))
        with self.assertRaises(RuntimeError):
            audit.window_limits({"eight_death": 30, "sixteen_death": 60}, 45)

    def test_live_seed_debit_and_terminal_discard_reconcile_separately(self):
        before, after = plant(), plant(95, 39)
        after["reproduction_cooldown"] = 16
        world = {"tick": 60, "sun_strength": 255, "climate": {}}
        record = audit.empty_budget(60, 60)
        audit.add_budget(record, before, after, world, None)
        parent = {"id": 1, "death_tick": None}
        seeds = [{"parent": 1, "created_tick": 60}]
        audit.validate_budget(record, parent, seeds, None)
        self.assertEqual(record["totals"]["energy_seeds"], 48)
        self.assertEqual(record["totals"]["energy_upkeep"], 1)
        for key in ("energy_income", "energy_seeds", "water_upkeep"):
            bad = copy.deepcopy(record)
            bad["totals"][key] += 1
            with self.assertRaises(RuntimeError):
                audit.validate_budget(bad, parent, seeds, None)
        before = plant(0, 10)
        before["stress"] = 7
        after = plant(0, 0)
        after.update(dead=True, stress=8, flags=3)
        receipt = {"version": 1, "type": "death", "id": 1, "tick": 60, "stress_before": 7, "flags": 3,
            "energy": {"before": 0, "income": 0, "overflow": 0, "upkeep_due": 1, "upkeep_paid": 0, "discarded": 0},
            "water": {"before": 10, "income": 2, "overflow": 0, "upkeep_due": 1, "upkeep_paid": 1, "discarded": 11}}
        record = audit.empty_budget(60, 60)
        audit.add_budget(record, before, after, world, receipt)
        audit.validate_budget(record, {"id": 1, "death_tick": 60}, [], {"receipt": receipt, "climate": {}})
        self.assertEqual(record["totals"]["water_discarded"], 11)
        self.assertEqual(record["totals"]["water_upkeep"], 1)
        with self.assertRaises(RuntimeError):
            audit.add_budget(audit.empty_budget(60, 60), before, after, world, None)

    def test_zero_spending_is_kept_in_paired_summary(self):
        a = {"windows": {w: {"totals": dict.fromkeys(audit.FLOW_KEYS, 0)} for w in ("since_split", "last_day")}}
        b = copy.deepcopy(a)
        b["windows"]["since_split"]["totals"]["energy_seeds"] = 48
        result = audit.resource_summary([(a, b), (b, a), (a, a)])
        self.assertEqual(result["plants"], 3)
        self.assertEqual(result["windows"]["since_split"]["changes"]["energy_seeds"], {"more": 1, "same": 1, "less": 1})
        self.assertEqual(result["windows"]["last_day"]["sixteen_no_seed_spending"], 3)

    def test_portable_evidence_recomputes_without_any_native_calls(self):
        folder = audit.ROOT / "benchmarks/garden-seasons"
        path = folder / "seed-bank-diagnosis-details.json.gz"
        if not path.exists():
            self.skipTest("diagnosis not collected yet")
        with patch("subprocess.Popen", side_effect=AssertionError("offline diagnosis invoked a process")):
            original = audit.load_input()
            report = json.loads(gzip.decompress(path.read_bytes()))
            audit.validate_report(report, original)
            self.assertEqual(audit.compact(report), json.loads((folder / "seed-bank-diagnosis-summary.json").read_text()))
            for cases in (report["cases"][:-1], report["cases"][:-1] + [report["cases"][0]]):
                with self.assertRaises(RuntimeError):
                    audit.analysis(cases, original)
            for mutate in (lambda r: r["arms"]["sixteen"]["seeds"][0].update(family=99),
                           lambda r: r["arms"]["eight"]["seeds"].pop(),
                           lambda r: r["arms"]["eight"]["budgets"].pop(),
                           lambda r: r["arms"]["sixteen"]["budgets"][0]["windows"]["since_split"]["totals"].update(energy_seeds=-1),
                           lambda r: r["arms"]["sixteen"]["budgets"][0]["windows"]["last_day"].update(start=15)):
                bad = copy.deepcopy(report["cases"][0])
                mutate(bad)
                with self.assertRaises(RuntimeError):
                    audit.validate_case(bad, original["cases"][0])


if __name__ == "__main__":
    unittest.main()
