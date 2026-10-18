#!/usr/bin/env python3
"""Offline ordered bank access, residence boundaries and frozen-panel checks."""

import copy
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_bank_access as audit

D, S = audit.DAY, audit.STEP
PORTABLE = audit.ROOT / "benchmarks/garden-seasons/landing-bank-access-results.json.gz"


def fixture(release=True, buyer=1):
    tick = 40 * D
    seeds = [{"parent": 1, "birth_tick": 8 * D + 60 * (i + int(not release)),
              "end_tick": tick + 60 * (i + int(not release)), "lifetime_ecology_ticks": 8192,
              "outcome": "expired", "child_id": None, "column": 1, "generation": 1, "species": 0}
             for i in range(8)]
    if release:
        seeds.append({**seeds[0], "parent": buyer, "birth_tick": tick, "end_tick": None, "outcome": "pending"})
    plants = [{"id": i, "parent": 0, "birth_tick": 0, "death_tick": None, "generation": 0,
               "column": i, "species": 0, "seeds_created": sum(s["parent"] == i for s in seeds),
               "late_seeds_created": sum(s["parent"] == i for s in seeds)} for i in (1, 2)]

    def visit(i, bank, mask, *, produced=False, energy=200):
        return [i, mask, energy, 300, 48, 24, 0, 0, 1, 10, 0, bank, 0, 255, produced]

    if not release:
        first = [visit(1, 8, 4), visit(2, 8, 4)]
    elif buyer == 1:
        first = [visit(1, 7, 0, produced=True), visit(2, 8, 4)]
    else:
        first = [visit(1, 7, 128, energy=0), visit(2, 7, 0, produced=True)]
    return {"tick": 42 * D, "lineages": plants, "seeds": seeds}, [
        [tick, first], [tick + S, [visit(1, 8, 6), visit(2, 8, 6)]]]


class BoundaryTests(unittest.TestCase):
    def test_slot_is_released_then_bought_before_focal_turn(self):
        result, rows = fixture()
        original = copy.deepcopy((result, rows))
        a = audit.analyze_visits(rows, result, rows[0][0], rows[-1][0])
        p = {p["id"]: p for p in a["plants"]}
        self.assertEqual(p[1]["access"], dict(ineligible=1, full_at_entry=0, earlier_buyers_fill=0, purchased=1))
        self.assertEqual(p[2]["access"], dict(ineligible=1, full_at_entry=0, earlier_buyers_fill=1, purchased=0))
        self.assertEqual(p[2]["missed_openings"][0]["earlier_buyers"], [1])
        self.assertEqual(p[2]["missed_openings"][0]["released_seeds"], [[1, 8 * D]])
        self.assertEqual(a["bank"]["released_outcomes"], {"expired": 1})
        self.assertEqual(a["bank"]["initial"], a["bank"]["final"])
        self.assertEqual(a["bank"]["release_steps_ending_full"], 1)
        self.assertEqual((result, rows), original)

    def test_full_entry_is_distinct_from_order_and_an_eligible_later_buyer(self):
        for release, buyer in ((False, 1), (True, 2)):
            result, rows = fixture(release, buyer)
            a = audit.analyze_visits(rows, result, rows[0][0], rows[-1][0])
            p = {p["id"]: p for p in a["plants"]}
            if release:
                self.assertEqual(p[1]["access"]["ineligible"], 2)
                self.assertEqual(p[2]["access"]["purchased"], 1)
            else:
                self.assertEqual(a["bank"]["access"]["full_at_entry"], 2)
                self.assertEqual(a["bank"]["releases"], 0)
            self.assertEqual(a["bank"]["access"]["earlier_buyers_fill"], 0)

    def test_opening_can_carry_forward_from_an_earlier_step(self):
        result, original = fixture()
        tick = original[0][0]
        for i, s in enumerate(result["seeds"][:-1]):
            s["birth_tick"], s["end_tick"] = 8 * D + 120 * i, tick + 120 * i
        result["seeds"][-1]["birth_tick"] = tick + 60
        rows = []
        for t in range(tick, tick + 60, S):
            visits = copy.deepcopy(original[0][1])
            for v in visits:
                v[1], v[11], v[13], v[-1] = 32 + (2 if t % 60 else 0), 7, 0, False
            rows.append([t, visits])
        rows.append([tick + 60, copy.deepcopy(original[0][1])])
        a = audit.analyze_visits(rows, result, tick, tick + 60)
        miss = a["plants"][1]["missed_openings"][0]
        self.assertEqual(miss["earlier_buyers"], [1])
        self.assertEqual(miss["released_seeds"], [])
        self.assertEqual(a["release_events"][0]["tick"], tick)
        self.assertEqual(a["release_events"][0]["bank_after"], 7)

    def test_corrupt_clock_order_identity_bank_gate_and_purchase_fail(self):
        for fault in ("gap", "clock", "order", "duplicate", "bank", "gate", "purchase", "bool"):
            result, rows = fixture()
            if fault == "gap":
                rows.pop()
            elif fault == "clock":
                rows[1][0] = rows[0][0]
            elif fault == "order":
                rows[0][1].reverse()
            elif fault == "duplicate":
                rows[0][1][1][0] = 1
            elif fault == "bank":
                rows[0][1][0][11] = 8
            elif fault == "gate":
                rows[0][1][0][1] = 128
            elif fault == "purchase":
                rows[0][1][0][-1] = False
            else:
                rows[0][1][0][-1] = 1
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                audit.analyze_visits(rows, result, 40 * D, 40 * D + S)

    def test_residence_matches_sample_oracle_and_exit_boundary(self):
        result, _ = fixture()
        start, stop = 39 * D, 41 * D
        a = audit.residence(result, start, stop, [1], [2])
        expected = {(s["parent"], s["birth_tick"]): sum(s["birth_tick"] <= t < (s["end_tick"] or result["tick"] + S)
                    for t in range(start, stop + S, S)) for s in result["seeds"]}
        self.assertEqual({(s["parent"], s["birth_tick"]): s["slot_samples"] for s in a["seeds"]},
                         {k: n for k, n in expected.items() if n})
        self.assertEqual(a["summary"]["occupied_slot_samples"], sum(expected.values()))
        self.assertEqual(a["seeds"][0]["last_sample"], 40 * D - S)
        self.assertEqual(a["summary"]["age_samples"]["16to32"], sum(n for (i,t),n in expected.items() if t < start))
        pending = next(s for s in a["seeds"] if s["right_censored"])
        self.assertIsNone(pending["end_tick"])
        self.assertIsNone(pending["parent_at_exit"])

    def test_death_export_and_child_censoring_are_separate(self):
        plants = [{"id": i, "birth_tick": b * D, "death_tick": d * D if d else None}
                  for i, b, d in ((1,0,2), (2,0,None), (3,3,None), (4,3,4))]
        plants[1]["removal_tick"] = 2 * D
        seeds = [{"parent": p, "birth_tick": D, "end_tick": 3 * D, "child_id": c, "outcome": "germinated"}
                 for p, c in ((1,3), (2,4))]
        value = audit.residence({"tick": 4 * D, "lineages": plants, "seeds": seeds}, D, 3 * D, [1,2], [])
        self.assertEqual(value["summary"]["parent_status_samples"], {"living": 512, "dead": 256, "exported": 256})
        self.assertEqual(value["summary"]["germination"], {"living": {}, "dead": {"confirmed": 1}, "exported": {"died": 1}})
        self.assertEqual(audit.child_status(plants[2], 4 * D - S), "pending")
        self.assertEqual(audit.child_status(plants[2], 4 * D), "confirmed")
        self.assertEqual(audit.child_status({**plants[2], "removal_tick": 4 * D}, 4 * D), "exported")

    def test_cli_preserves_existing_output_and_rejects_unknown_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "keep.json.gz"
            path.write_bytes(b"preserve")
            command = [sys.executable, audit.__file__, "--out", str(path)]
            result = subprocess.run(command, capture_output=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(path.read_bytes(), b"preserve")
            missing = Path(tmp) / "new.json.gz"
            result = subprocess.run([sys.executable, audit.__file__, "--out", str(missing), "--input", str(path)],
                                    capture_output=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(missing.exists())


class FrozenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = audit.load(audit.ROOT / audit.INPUT, audit.INPUT_SHA)
        cls.visits = audit.load(audit.ROOT / audit.VISITS, audit.VISITS_SHA)

        def state_hash():
            return hashlib.sha256(json.dumps((cls.data, cls.visits), sort_keys=True).encode()).hexdigest()

        before = state_hash()
        with patch.object(audit.previous.training, "native", side_effect=AssertionError("ran simulation")), \
                patch.object(subprocess, "run", side_effect=AssertionError("ran subprocess")):
            cls.result = audit.analyze(cls.data, cls.visits)
        if before != state_hash():
            raise AssertionError("audit changed frozen inputs")

    def test_complete_portable_panel_and_no_native_calls(self):
        with gzip.open(PORTABLE, "rt") as stream:
            self.assertEqual(self.result, json.load(stream))
        self.assertEqual((self.result["native_runs"], self.result["training_runs"]), (0, 0))
        self.assertEqual(len(self.result["worlds"]), 6)
        for old, new in zip(self.data["worlds"], self.result["worlds"], strict=True):
            self.assertEqual(new["cohorts"], old["cohorts"])
            for arm, a in new["arms"].items():
                bank, stock = a["access"]["bank"], a["residence"]["summary"]
                self.assertEqual(a["result_run_hash"], old["arms"][arm]["result"]["run_hash"])
                self.assertEqual(bank["initial"] + bank["purchases"] - bank["releases"], bank["final"])
                self.assertEqual(stock["samples"], 15360)
                for field in ("outcome_samples", "cohort_samples", "age_samples", "parent_status_samples"):
                    self.assertEqual(sum(stock[field].values()), stock["occupied_slot_samples"])

    def test_bank_only_checks_are_partitioned_without_dropping_negative_world(self):
        checks, windows, focal_count = 0, 0, 0
        for w in self.result["worlds"]:
            a = w["arms"]["vacancy"]
            ps = {p["id"]: p for p in a["access"]["plants"]}
            self.assertEqual([s["id"] for s in a["focal_residence"]], w["cohorts"]["early_vacancy"])
            for i in w["cohorts"]["early_vacancy"]:
                p = ps[i]
                focal_count += 1
                checks += p["access"]["full_at_entry"] + p["access"]["earlier_buyers_fill"]
                windows += sum(p["ready_window_masks"].values())
                self.assertEqual(p["purchases"], [])
                self.assertEqual(len(p["missed_openings"]), p["access"]["earlier_buyers_fill"])
                for event in p["missed_openings"]:
                    self.assertEqual(event["bank_at_entry"] + len(event["earlier_buyers"]), 8)
                    self.assertEqual(event["visit"][1], 4)
        self.assertEqual((focal_count, checks, windows), (5, 3394, 5223))

    def test_raw_summary_corruption_or_missing_world_is_rejected(self):
        bad = copy.deepcopy(self.visits)
        bad["worlds"].pop()
        with self.assertRaises(RuntimeError):
            audit.analyze(self.data, bad)
        bad = copy.deepcopy(self.visits["worlds"][0]["arms"]["control"]["rows"])
        bad[0][1].pop()
        with self.assertRaises(RuntimeError):
            audit.analyze_visits(bad, self.data["worlds"][0]["arms"]["control"]["result"])

    def test_focal_ownership_and_posthumous_recruitment_are_preserved(self):
        full, lost, stocks, misses = [], [], [], []
        for w in self.result["worlds"]:
            a = w["arms"]["vacancy"]
            stocks.extend(a["focal_residence"])
            for p in a["access"]["plants"]:
                if p["id"] in w["cohorts"]["early_vacancy"]:
                    full.append(p["access"]["full_at_entry"])
                    lost.append(p["access"]["earlier_buyers_fill"])
                    misses.extend(p["missed_openings"])
        self.assertEqual(full, [749, 562, 857, 460, 750])
        self.assertEqual(lost, [3, 2, 4, 1, 6])
        self.assertEqual(sum(bool(m["released_seeds"]) for m in misses), 15)
        self.assertTrue(all(m["bank_at_entry"] == 7 and len(m["earlier_buyers"]) == 1 for m in misses))
        self.assertEqual(sum(s["summary"]["empty_slot_samples"] for s in stocks), 46)
        self.assertEqual(sum(s["summary"]["occupied_slot_samples"] for s in stocks), 347498)
        seeds = [p for s in stocks for p in s["seeds"]]
        self.assertEqual(len(seeds), 73)
        self.assertTrue(all(s["owner_cohort"] == "incumbent" for s in seeds))
        germinated = [s for s in seeds if s["outcome"] == "germinated"]
        posthumous = [s for s in germinated if s["parent_at_exit"] == "dead"]
        self.assertEqual(len(germinated), 24)
        self.assertEqual(len(posthumous), 23)
        self.assertEqual(sum(s["child_first_day"] == "confirmed" for s in posthumous), 19)
        long_waits = [s for s in germinated if s["end_tick"] - s["birth_tick"] >= 16 * D]
        self.assertEqual(len(long_waits), 20)
        self.assertEqual(sum(s["child_first_day"] == "confirmed" for s in long_waits), 16)


if __name__ == "__main__":
    unittest.main()
