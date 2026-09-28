#!/usr/bin/env python3
"""All-offspring cohort boundaries, CLI isolation and fixed population evidence."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import garden_season_seedling_population as trial
from test_garden_season_offspring import fixture

BUILD = None


class PopulationTests(unittest.TestCase):
    def test_fixed_panel_and_two_day_censoring(self):
        cases = trial.inputs()
        self.assertEqual(len(cases), 32)
        self.assertEqual({c["seed"] for c in cases}, set(trial.SEEDS))
        self.assertTrue(all(c["mode"] == "seasonal" for c in cases))
        result = trial.outcomes(fixture())
        self.assertEqual(result["two_day"]["whole"], {"eligible": 5, "censored": 2, "survivors": 4})
        self.assertEqual(result["two_day"]["closing"], {"eligible": 1, "censored": 2, "survivors": 1})
        self.assertEqual(result["cohorts"]["whole"]["totals"]["durable_parents"], 1)
        self.assertEqual(len(result["founders"]), 1)

    def test_fraction_boundaries_and_zero_denominators(self):
        def counts(survivors, eligible):
            return {"closing_survivors": survivors, "closing_eligible": eligible}
        self.assertTrue(trial.fraction_retained(counts(2, 4), counts(3, 6)))
        self.assertFalse(trial.fraction_retained(counts(2, 4), counts(3, 7)))
        self.assertTrue(trial.fraction_retained(counts(0, 0), counts(0, 0)))
        self.assertTrue(trial.fraction_retained(counts(0, 0), counts(0, 1)))
        self.assertFalse(trial.fraction_retained(counts(0, 4), counts(0, 0)))

    def test_screen_retains_reproduction_and_reports_adverse_pairs(self):
        cases = []
        for old in trial.inputs():
            arm = {"history": old, "outcomes": trial.outcomes(old), "first_empty_tick": None}
            cases.append({"case": {k: old[k] for k in ("mode", "scenario", "policy", "seed")},
                          "arms": {name: copy.deepcopy(arm) for name in trial.ARMS}})
        before = trial.analysis(cases)
        self.assertFalse(before["passes_screen"])
        self.assertFalse(before["gates"]["improve_closing_renewal"])
        for key, passed in before["gates"].items():
            if key != "improve_closing_renewal":
                self.assertTrue(passed, key)
        candidate = next(c for c in cases if c["arms"]["guard"]["history"]["lifetimes"]["durable_parents"])
        candidate["arms"]["guard"]["history"]["lifetimes"]["durable_parents"] -= 1
        candidate["arms"]["guard"]["first_empty_tick"] = 15
        after = trial.analysis(cases)
        self.assertFalse(after["gates"]["retain_historical_durable_parents"])
        self.assertFalse(after["gates"]["no_new_empty_world"])
        self.assertEqual(after["paired"]["historical_durable_parents"]["decreased"], 1)
        with self.assertRaises(RuntimeError):
            trial.analysis(cases[:-1])
        with self.assertRaises(RuntimeError):
            trial.analysis(cases[:-1] + [cases[0]])

    def test_changed_prefix_is_rejected(self):
        world = {"tick": 0, "climate": {}, "rain_rate": 0, "sun_strength": 255,
                 "rain_deposited": 0, "rain_runoff": 0, "hash": "a"}
        with patch.object(trial.reserve, "groups", side_effect=[iter([(world, [], [])]),
                          iter([({**world, "hash": "b"}, [], [])])]):
            with self.assertRaisesRegex(RuntimeError, "prefix"):
                trial.analyze_pair(Path("before"), Path("after"), {})

    def test_native_selection_is_explicit_and_mutually_exclusive(self):
        if BUILD is None:
            self.skipTest("native build not supplied")
        for name in ("toy-factory-garden-inspect", "toy-factory-garden-replay"):
            binary = str(BUILD / name)
            maintenance = "--leaf-policy" in subprocess.check_output([binary, "--help"], text=True)
            command = [binary, "-", "rainfed", "baseline", "123", "--ticks", "120", "--climate", "seasonal"]
            if name.endswith("inspect"):
                command += ["--death-audit"]
            for suffix in (["--seedling-reserve", "all", "--seedling-reserve", "1"],
                           ["--seedling-reserve", "1", "--seedling-reserve", "all"],
                           ["--seedling-reserve", "all", "--seedling-reserve", "all"],
                           ["--seedling-reserve", "all", "--seedling-reserve-component", "water"],
                           ["--seedling-reserve-component", "energy", "--seedling-reserve", "all"]):
                self.assertEqual(subprocess.run(command + suffix, capture_output=True, timeout=30).returncode, 2)
            base = subprocess.check_output(command, text=True, timeout=30)
            for extra in ([], ["--seedling-reserve-component", "both"]):
                run = subprocess.run(command + ["--seedling-reserve", "all"] + extra,
                                     capture_output=True, text=True, timeout=30)
                if maintenance:
                    self.assertEqual(run.returncode, 2)
                    continue
                self.assertEqual(run.returncode, 0, run.stderr)
                rows = [json.loads(line) for line in run.stdout.splitlines()]
                self.assertEqual([{k: v for k, v in row.items() if k != "seedling_reserve"} for row in rows],
                                 [json.loads(line) for line in base.splitlines()])
                for row in rows:
                    if row.get("type", "world") == "world":
                        self.assertEqual(row["seedling_reserve"], trial.METADATA)
                    else:
                        self.assertNotIn("seedling_reserve", row)
            incompatible = command.copy()
            incompatible[3] = "neural-reference"
            self.assertEqual(subprocess.run(incompatible + ["--seedling-reserve", "all"],
                                           capture_output=True, timeout=30).returncode, 2)

    def test_native_active_trace_audit_and_tampering(self):
        if BUILD is None:
            self.skipTest("native build not supplied")
        binary = BUILD / "toy-factory-garden-inspect"
        if "--leaf-policy" in subprocess.check_output([binary, "--help"], text=True):
            return  # Explicit rejection is checked in the preceding CLI test.
        command = [str(binary), "-", "rainfed", "baseline", str(int(trial.SEEDS[0], 16)),
                   "--ticks", "12240", "--climate", "seasonal", "--death-audit", "--seedling-reserve", "all"]
        rows = [json.loads(line) for line in subprocess.check_output(command, text=True, timeout=30).splitlines()]
        groups, bids, deaths = [], [], []
        for row in rows:
            if row["type"] == "bid":
                bids.append(row)
            elif row["type"] == "death":
                deaths.append(row)
            else:
                groups.append((row, bids, deaths))
                bids, deaths = [], []
        capacity = groups[0][0].get("seed_capacity", 8)
        audit = trial.Audit(True, capacity)
        for item in groups:
            audit.accept(*item)
        self.assertGreater(audit.counts["guard_bids"], 0)
        self.assertGreater(audit.counts["veto_commits"], 0)
        focal = next(i for i, (_, b, _) in enumerate(groups) if any("seedling_reserve" in p for p in b))
        for mutation in ("age", "scope", "water_reserve", "missing"):
            changed = copy.deepcopy(groups[focal])
            proposal = next(b for b in changed[1] if "seedling_reserve" in b)
            if mutation == "missing":
                proposal.pop("seedling_reserve")
            elif mutation == "scope":
                proposal["seedling_reserve"]["scope"] = "founders"
            else:
                proposal["seedling_reserve"][mutation] += 1
            bad = trial.Audit(True, capacity)
            for item in groups[:focal]:
                bad.accept(*item)
            with self.assertRaises(RuntimeError):
                bad.accept(*changed)

    def test_retained_panel(self):
        evidence = trial.ROOT / "benchmarks/garden-seasons"
        report = json.loads(gzip.decompress((evidence / "seedling-population-histories.json.gz").read_bytes()))
        self.assertEqual(report["protocol"], trial.RULE)
        self.assertEqual(report["input_sha256"], trial.INPUT_SHA256)
        self.assertEqual(trial.analysis(report["cases"]), report["analysis"])
        self.assertEqual(trial.compact(report), json.loads((evidence / "seedling-population-summary.json").read_text()))
        originals = {trial.identity(c): c for c in trial.inputs()}
        frames = []
        for case in report["cases"]:
            old = originals[trial.identity(case["case"])]
            for key, value in case["arms"]["control"]["history"].items():
                self.assertEqual(value, old[key])
            for arm in trial.ARMS:
                detail = case["arms"][arm]
                self.assertEqual(trial.outcomes(detail["history"]), detail["outcomes"])
                self.assertEqual(detail["counts"]["worlds"], trial.END // 15 + 1)
                self.assertEqual(len(detail["terminals"]), detail["counts"]["terminal_receipts"])
                for receipt in detail["terminals"]:
                    event = next(d for d in detail["history"]["deaths"] if d["id"] == receipt["receipt"]["id"])
                    self.assertEqual(event["tick"], receipt["receipt"]["tick"])
                    self.assertEqual(event["climate"], receipt["climate"])
            for frame in case["frames"]:
                frames.append((case["case"]["scenario"], frame["arm"], frame["day"]))
                self.assertEqual((case["case"]["seed"], case["case"]["policy"]), (trial.SEEDS[0], "baseline"))
                self.assertEqual(trial.digest(evidence / frame["png"]), frame["png_sha256"])
                self.assertEqual(frame["hash"], case["arms"][frame["arm"]]["history"]["daily"][frame["day"]]["hash"])
        self.assertEqual(set(frames), {(layout, arm, day) for layout in trial.LAYOUTS
                                      for arm in trial.ARMS for day in (16, 128)})
        self.assertEqual(len(frames), 8)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    args, remaining = parser.parse_known_args()
    BUILD = args.build.resolve() if args.build else None
    unittest.main(argv=[sys.argv[0], *remaining])
