#!/usr/bin/env python3
"""Reserve arithmetic, malformed evidence and explicit/default CLI behavior."""

import argparse
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

import garden_season_seedling_reserve as trial
from test_garden_season_seedlings import live_history

BUILD = None


def bid():
    return {"id": 35, "tick": 15, "original_action": 1, "action": 1, "original_priority": 9,
            "priority": 9, "energy": 256, "water": 13, "tissue": 0,
            "candidates": [{"flags": 3, "moisture": 20, "y": 144} for _ in range(5)],
            "seedling_reserve": {"age": 1, "species": 0, "vigor": 0, "nodes": 10, "roots": 2,
                                 "sun_phase": 65, "maintenance_phase": 1, "income": 4,
                                 "tip_moisture": 1, "original_order": list(range(5)), "order": list(range(5))}}


class ReserveTests(unittest.TestCase):
    def test_fixed_panel_and_prior_integrity(self):
        prior, specs = trial.inputs()
        self.assertEqual([(s["key"], s["record"]["id"]) for s in specs],
                         [("energy", 35), ("water", 41), ("survivor", 39)])
        self.assertEqual(len(prior["cases"]), 6)
        self.assertTrue(all(s["record"]["birth_tick"] + 2 * trial.DAY < trial.END for s in specs))

    def test_energy_water_and_order_boundaries(self):
        b = bid()
        f = trial.forecast(b)
        self.assertTrue(f["allowed"])
        self.assertEqual((f["water_upkeep"], f["water_reserve"], f["growth_cost"]), (2, 8, 9))
        b["water"] = 12
        self.assertFalse(trial.forecast(b)["water_allowed"])
        b["tissue"] = 1
        b["water"] = 6
        f = trial.forecast(b)
        self.assertTrue(f["allowed"] and f["wet_root"])
        self.assertEqual(f["water_reserve"], 1)
        b["candidates"][0]["moisture"] = 1
        self.assertFalse(trial.forecast(b)["allowed"])
        b["seedling_reserve"]["original_order"] = [1, 0, 2, 3, 4]
        self.assertTrue(trial.forecast(b)["allowed"])
        b["seedling_reserve"]["sun_phase"] = 128
        self.assertFalse(trial.forecast(b)["energy_allowed"])
        b["original_action"] = 0
        b["seedling_reserve"]["original_order"] = []
        self.assertTrue(trial.forecast(b)["allowed"])
        b["original_action"] = 1
        b["seedling_reserve"]["original_order"] = [0, 0, 2, 3, 4]
        with self.assertRaisesRegex(RuntimeError, "permutation"):
            trial.forecast(b)

    def test_recorded_forecast_and_scope_cannot_be_changed(self):
        b = bid()
        b["seedling_reserve"].update(trial.forecast(b))
        spec = {"record": {"id": 35, "birth_tick": 15}}
        self.assertEqual(trial.check_bid(b, spec, True)["guard_bids"], 1)
        for mutate in (lambda p: p["seedling_reserve"].update(water_reserve=7),
                       lambda p: p.update(id=36), lambda p: p.update(tick=15 + trial.DAY),
                       lambda p: p.update(priority=8), lambda p: p.update(action=0),
                       lambda p: p["seedling_reserve"].update(age=2),
                       lambda p: p["seedling_reserve"].update(order=[])):
            bad = copy.deepcopy(b)
            mutate(bad)
            with self.assertRaises(RuntimeError):
                trial.check_bid(bad, spec, True)
        b["water"] = 12
        b["seedling_reserve"].update(trial.forecast(b))
        b["seedling_reserve"]["order"] = []
        b["action"] = 0
        self.assertEqual(trial.check_bid(b, spec, True)["veto_water"], 1)
        b.pop("seedling_reserve")
        with self.assertRaises(RuntimeError):
            trial.check_bid(b, spec, False)

    def test_ledger_reconciles_and_rejects_changed_samples(self):
        steps = live_history()
        result = trial.ledger(steps)
        self.assertEqual(result["samples"], 257)
        self.assertEqual(result["totals"]["energy_income"], 512)
        for mutate in (lambda h: h.pop(20), lambda h: h[20]["budget"].update(water_income=99),
                       lambda h: h[20]["plant"].update(energy=0),
                       lambda h: h[20].update(terminal={})):
            bad = copy.deepcopy(steps)
            mutate(bad)
            with self.assertRaises(RuntimeError):
                trial.ledger(bad)

    def test_missing_unknown_and_changed_prefix_records_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trace.gz"
            for rows in ([], [{"type": "bid", "tick": 15}], [{"type": "unknown", "tick": 0}],
                         [{"type": "world", "tick": 0, "death_audit_version": 1}]):
                with gzip.open(path, "wt") as stream:
                    for row in rows:
                        stream.write(json.dumps(row) + "\n")
                with self.assertRaises(RuntimeError):
                    list(trial.groups(path))
        world = {"tick": 0, "climate": {}, "rain_rate": 0, "sun_strength": 200, "hash": "a"}
        with patch.object(trial, "groups", side_effect=[iter([(world, [], [])]),
                          iter([({**world, "hash": "b"}, [], [])])]):
            with self.assertRaisesRegex(RuntimeError, "prefix"):
                trial.analyze_pair(Path("off"), Path("on"), {})

    def test_retained_panel_ledgers_forecasts_and_images(self):
        evidence = trial.ROOT / "benchmarks/garden-seasons"
        raw = gzip.decompress((evidence / "seedling-reserve-histories.json.gz").read_bytes())
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         "703aaaccc6570635b5247b001b4f275124fdf5d7dd9d6e9da61c07aabfd3165d")
        report = json.loads(raw)
        self.assertEqual(trial.compact(report), json.loads((evidence / "seedling-reserve-summary.json").read_text()))
        _, specs = trial.inputs()
        self.assertEqual(len(report["cases"]), len(specs))
        for spec, case in zip(specs, report["cases"]):
            self.assertEqual(case["key"], spec["key"])
            self.assertEqual(case["traces"]["control"], spec["prior"]["trace_sha256"])
            for arm in ("control", "guard"):
                steps = case[arm]["steps"]
                self.assertEqual(trial.ledger(steps), case[arm]["two_days"])
                first_day = [s for s in steps if s["tick"] <= spec["record"]["birth_tick"] + trial.DAY]
                self.assertEqual(trial.ledger(first_day), case[arm]["first_day"])
                for step in steps:
                    for proposal in step["bids"]:
                        trial.check_bid(proposal, spec, arm == "guard")
            for frame in case["frames"]:
                self.assertEqual(trial.digest(evidence / frame["png"]), frame["png_sha256"])

    def test_native_cli_is_explicit_and_inactive_targets_are_identical(self):
        if BUILD is None:
            self.skipTest("native build not supplied")
        for name in ("toy-factory-garden-inspect", "toy-factory-garden-replay"):
            binary = BUILD / name
            maintenance = "--leaf-policy" in subprocess.check_output([binary, "--help"], text=True)
            command = [str(binary), "-", "rainfed", "baseline", "123", "--ticks", "120", "--climate", "seasonal"]
            if name.endswith("inspect"):
                command += ["--death-audit"]
            for extra in (["--seedling-reserve", value] for value in ("0", "-1", "4294967296", "x", "")):
                self.assertEqual(subprocess.run(command + extra, capture_output=True, timeout=30).returncode, 2)
            duplicate = command + ["--seedling-reserve", "9", "--seedling-reserve", "10"]
            self.assertEqual(subprocess.run(duplicate, capture_output=True, timeout=30).returncode, 2)
            incompatible = command.copy()
            incompatible[3] = "neural-reference"
            self.assertEqual(subprocess.run(incompatible + ["--seedling-reserve", "9"],
                                           capture_output=True, timeout=30).returncode, 2)
            base = [json.loads(line) for line in subprocess.check_output(command, text=True, timeout=30).splitlines()]
            for lineage in (1, 4294967295):
                run = subprocess.run(command + ["--seedling-reserve", str(lineage)], capture_output=True,
                                     text=True, timeout=30)
                if maintenance:
                    self.assertEqual(run.returncode, 2)
                    continue
                self.assertEqual(run.returncode, 0, run.stderr)
                rows = [json.loads(line) for line in run.stdout.splitlines()]
                self.assertEqual([{k: v for k, v in row.items() if k != "seedling_reserve"} for row in rows], base)
                for row in rows:
                    if row.get("type", "world") == "world":
                        self.assertEqual(row["seedling_reserve"], {"rule": trial.RULE, "lineage": lineage})
                    else:
                        self.assertNotIn("seedling_reserve", row)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    args, remaining = parser.parse_known_args()
    BUILD = args.build.resolve() if args.build else None
    unittest.main(argv=[sys.argv[0], *remaining])
