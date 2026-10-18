#!/usr/bin/env python3
"""Offline turnover boundaries, independent census checks and frozen counterexamples."""

import copy
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_turnover as audit

PORTABLE = audit.ROOT / "benchmarks/garden-seasons/landing-turnover-results.json.gz"
D, S = audit.DAY, audit.STEP


class TurnoverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = audit.load(audit.ROOT / audit.INPUT)
        with patch.object(audit.previous.training, "native", side_effect=AssertionError("offline audit ran simulation")):
            cls.result = audit.analyze(cls.data)

    def world(self, model, arm):
        return next(w for w in self.result["worlds"] if w["model"] == model and
                    w["case"]["climate"] == "seasonal")["arms"][arm]

    def test_portable_recomputes_without_changing_scores_or_inputs(self):
        self.assertEqual(json.loads(gzip.decompress(PORTABLE.read_bytes())), self.result)
        self.assertEqual(self.result["unchanged_comparison"], self.data["comparison"])
        self.assertEqual(audit.digest(audit.ROOT / audit.INPUT), audit.INPUT_SHA)
        self.assertEqual((self.result["native_runs"], self.result["training_runs"]), (0, 0))
        for old, new in zip(self.data["worlds"], self.result["worlds"], strict=True):
            self.assertEqual(new["id"], old["id"])
            for arm in audit.ARMS:
                for dest, source in (("unchanged_history", "history"), ("trace_sha256", "trace_sha256"),
                                     ("arbitration_trace_sha256", "arbitration_trace_sha256")):
                    self.assertEqual(new["arms"][arm][dest], old["arms"][arm][source])
                self.assertEqual(len(new["arms"][arm]["periods"]), 4)

    def test_independent_sampled_census_and_credit_all_worlds(self):
        # Direct timestamp arithmetic, not the production interval/bucket helpers.
        for old, new in zip(self.data["worlds"], self.result["worlds"], strict=True):
            for arm in audit.ARMS:
                result, saved = old["arms"][arm]["result"], new["arms"][arm]
                records = {p["id"]: p for p in result["lineages"]}
                absent, empty = [], 0
                credits = [0] * 4
                for t in range(audit.START, audit.STOP + S, S):
                    living = [p for p in records.values() if p["birth_tick"] <= t and
                              (p["death_tick"] is None or t < p["death_tick"])]
                    established = [p for p in living if p["parent"] and p["birth_tick"] + D <= t]
                    if not established:
                        absent.append(t)
                    if not living and not any(s["birth_tick"] <= t and
                            (s["end_tick"] is None or t < s["end_tick"]) for s in result["seeds"]):
                        empty += S
                    for i, (a, z) in enumerate(audit.rolling.PERIODS):
                        if a * D < t <= z * D:
                            for p in established:
                                parent = records[p["parent"]]
                                due = p["birth_tick"] + D
                                if parent["parent"] and parent["birth_tick"] + D <= due and \
                                        (parent["death_tick"] is None or parent["death_tick"] > parent["birth_tick"] + D) and \
                                        t < due + 32 * D:
                                    credits[i] += S
                from_intervals = [t for g in saved["gaps"] for t in range(g["first_tick"], g["end_exclusive"], S)]
                self.assertEqual(from_intervals, absent, (old["id"], arm))
                self.assertEqual(saved["population_stats"]["biologically_empty_ticks"], empty)
                self.assertEqual([p["credit"]["earned_ticks"] for p in saved["periods"]], credits)

    def test_gap_checkpoint_and_seed_only_recovery_are_not_extinction(self):
        a = self.world("single-s6d697834-live", "eligible")
        g = next(g for g in a["gaps"] if 128 * D in g["checkpoints"])
        self.assertEqual((g["first_tick"], g["end_exclusive"]), (486960, 494790))
        self.assertEqual(g["stats"], {"sample_ticks": 7830, "samples": 522, "minimum_seed_bank": 3,
            "maximum_seed_bank": 8, "zero_seed_bank_ticks": 0, "no_living_plant_ticks": 1905,
            "biologically_empty_ticks": 0})
        self.assertEqual(g["first"]["terminal"]["classification"], "seed-only-unconfirmed")
        self.assertEqual(g["deaths_at_start"], [28])
        self.assertEqual(g["restoring_ids"], [32])
        self.assertEqual(g["children_seen"], [29, 30, 31, 32, 33, 34])
        children = {p["id"]: p for p in a["children"]}
        self.assertEqual([children[i]["death_shortage"] for i in (29, 30, 31)],
                         ["energy+water", "energy", "energy"])
        for i in (29, 30, 31):
            self.assertTrue(children[i]["global_light_ceiling_insufficient_at_death"])
        # With these observed births and older deaths fixed, even rescuing the
        # first wave cannot establish a descendant by the day-128 checkpoint.
        self.assertGreater(min(children[i]["birth_tick"] + D for i in g["children_seen"]), 128 * D)
        self.assertEqual(a["periods"][1]["terminal"]["young_descendants"], [32, 33])
        self.assertEqual(self.world("single-s6d697834-live", "veto")["periods"][1]
                         ["terminal"]["established_descendants"], [28, 29])
        self.assertFalse(any(g["checkpoints"] for g in self.world("single-s6d697835-live", "eligible")["gaps"]))
        self.assertTrue(any(g["checkpoints"] for g in self.world("single-s6d697835-live", "veto")["gaps"]))

    def test_all_gaps_and_contrary_cases_are_retained(self):
        for arm, count, ticks in (("veto", 6, 43515), ("eligible", 8, 60375)):
            self.assertEqual(self.result["groups"]["seasonal"][arm]["gaps"], count)
            self.assertEqual(self.result["groups"]["seasonal"][arm]["gap_sample_ticks"], ticks)
            self.assertEqual(self.result["groups"]["steady"][arm]["gaps"], 0)
            self.assertEqual(self.result["groups"]["all"][arm]["biologically_empty_ticks"], 0)
        single = [self.world("single-s6d697835-live", arm)["periods"][2]["birth_cohort"] for arm in audit.ARMS]
        multi = [self.world("multi-s6d697835-live", arm)["periods"][2]["birth_cohort"] for arm in audit.ARMS]
        self.assertEqual([(p["births"], p["confirmed"], p["died"]) for p in single], [(17, 8, 9), (3, 1, 2)])
        self.assertEqual([(p["births"], p["confirmed"], p["died"]) for p in multi], [(14, 1, 13), (11, 5, 6)])

    def test_seed_supply_and_complete_in_spell_blockers(self):
        a = self.world("single-s6d697835-live", "eligible")
        s = max(a["no_birth_spells"], key=lambda r: r["stats"]["sample_ticks"])
        self.assertEqual((s["previous_birth_tick"], s["next_birth_tick"]), (491010, 649665))
        self.assertEqual((s["purchases"], s["expiries"], s["stats"]["minimum_seed_bank"]), (13, 12, 7))
        self.assertEqual(len(s["complete_seed_lifetimes"]), 5)
        for seed in s["complete_seed_lifetimes"]:
            self.assertEqual(seed["outcome"], "expired")
            self.assertEqual(seed["always_mature_blockers"], ["spacing"])
            self.assertEqual(seed["mature_checks"], 8184)
            self.assertTrue(s["first_tick"] <= seed["birth_tick"] < seed["end_tick"] < s["end_exclusive"])
        # Another arm's late no-birth spell is right-censored, not a known recovery.
        tail = max(self.world("multi-s6d697835-live", "veto")["no_birth_spells"],
                   key=lambda r: r["stats"]["sample_ticks"])
        self.assertIsNone(tail["next_birth_tick"])
        self.assertEqual(tail["end_exclusive"], audit.STOP + S)

    def test_exact_birth_death_confirmation_credit_expiry_and_seed_boundaries(self):
        result = {"tick": 36 * D, "lineages": [
            {"id": 1, "parent": 0, "birth_tick": 0, "death_tick": D},
            {"id": 2, "parent": 1, "birth_tick": S, "death_tick": D + S},
            {"id": 3, "parent": 1, "birth_tick": D // 2, "death_tick": 2 * D},
            {"id": 4, "parent": 3, "birth_tick": 2 * D, "death_tick": None}],
            "seeds": [{"parent": 1, "birth_tick": S, "end_tick": 2 * D}]}
        self.assertEqual(audit.population(result, S)["terminal"]["pending_seeds"], 1)
        self.assertNotIn(2, audit.population(result, D + S)["terminal"]["established_descendants"])
        self.assertEqual(audit.population(result, 2 * D)["terminal"]["pending_seeds"], 0)
        self.assertEqual(audit.population(result, 3 * D)["plants"]["credit_eligible"], [4])
        self.assertEqual(audit.population(result, 35 * D - S)["plants"]["credit_eligible"], [4])
        self.assertEqual(audit.population(result, 35 * D)["plants"]["aged_out_eligible"], [4])
        spans = audit.segments(result, 0, 3 * D)
        self.assertEqual([(g["first_tick"], g["end_exclusive"]) for g in audit.gaps(result, spans)],
                         [(0, 3 * D // 2), (2 * D, 3 * D)])
        censored = audit.gaps(result, audit.segments(result, 2 * D, 3 * D - S))[0]
        # An interval truncated by the view can still have recovery in the known ledger.
        self.assertEqual(censored["after"]["tick"], 3 * D)
        final = dict(result, tick=3 * D - S)
        self.assertTrue(audit.gaps(final, audit.segments(final, 2 * D, 3 * D - S))[0]["recovery_censored"])
        self.assertTrue(audit.gaps(result, audit.segments(result, 2 * D, 5 * D // 2))[0]["recovery_censored"])
        for bad in (-S, 1, True, result["tick"] + S):
            with self.assertRaises(RuntimeError):
                audit.population(result, bad)
        with self.assertRaises(RuntimeError):
            audit.interval_stats(spans, 0, 4 * D)

    def test_corrupt_saved_ledgers_resources_and_history_are_rejected(self):
        original = self.data["worlds"][0]["arms"]["eligible"]
        for field in ("history", "lineage", "seed", "duplicate", "resource"):
            broken = copy.deepcopy(original)
            if field == "history":
                broken["history"]["combined_ticks"] += S
            elif field == "lineage":
                broken["audit"]["plants"][0]["parent"] += 1
            elif field == "seed":
                broken["audit"]["seeds"][0]["column"] += 1
            elif field == "duplicate":
                broken["audit"]["plants"].append(broken["audit"]["plants"][0])
            else:
                broken["audit"]["plants"][0]["resources"]["energy"]["growth"] += 1
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                audit.analyze_arm(broken, "eligible")

    def test_cli_roundtrip_no_clobber_and_input_identity(self):
        def run(*args):
            return subprocess.run([sys.executable, "-W", "error", str(audit.ROOT / "sim/garden_landing_turnover.py"),
                                   *map(str, args)], capture_output=True, timeout=60)
        with tempfile.TemporaryDirectory(prefix="landing-turnover-") as directory:
            output = Path(directory) / "audit.json.gz"
            self.assertEqual(run("--out", output).returncode, 0)
            self.assertEqual(output.read_bytes(), PORTABLE.read_bytes())
            self.assertNotEqual(run("--out", output).returncode, 0)
            self.assertEqual(output.read_bytes(), PORTABLE.read_bytes())
            self.assertEqual(run("--verify", output).returncode, 0)
            bad = Path(directory) / "bad.json"
            bad.write_text("{}\n")
            self.assertNotEqual(run("--verify", bad).returncode, 0)
            absent = Path(directory) / "absent.json"
            self.assertNotEqual(run("--input", bad, "--out", absent).returncode, 0)
            self.assertFalse(absent.exists())


if __name__ == "__main__":
    unittest.main()
