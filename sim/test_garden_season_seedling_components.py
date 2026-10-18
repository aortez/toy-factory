#!/usr/bin/env python3
"""Component truth table, CLI boundaries and retained four-arm evidence."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import subprocess
import sys
import unittest

import garden_season_seedling_components as trial
from test_garden_season_seedling_reserve import bid

BUILD = None


class ComponentTests(unittest.TestCase):
    def test_fixed_inputs(self):
        prior, specs = trial.inputs()
        self.assertEqual([s["record"]["id"] for s in specs], [35, 41, 39])
        self.assertEqual([s["key"] for s in specs], [c["key"] for c in prior["cases"]])
        self.assertEqual(trial.ARMS, ("control", "both", "energy", "water"))

    def test_effective_component_truth_table_and_tampering(self):
        spec = {"record": {"id": 35, "birth_tick": 15}}
        for energy in (0, 256):
            for water in (0, 13):
                for component in trial.ARMS[1:]:
                    b = bid()
                    b.update(energy=energy, water=water)
                    f = trial.reserve.forecast(b)
                    expected = f["allowed"] if component == "both" else f[component + "_allowed"]
                    if component != "both":
                        b["seedling_reserve"]["component"] = component
                    f["allowed"] = expected
                    b["seedling_reserve"].update(f)
                    b["action"] = 1 if expected else 0
                    b["seedling_reserve"]["order"] = list(range(5)) if expected else []
                    counts = trial.reserve.check_bid(b, spec, True, component)
                    self.assertEqual(counts["veto_bids"], int(not expected))
                    if not expected and component != "both":
                        self.assertEqual(counts["veto_" + component], 1)
                    for mutate in (lambda p: p["seedling_reserve"].update(component="wrong"),
                                   lambda p: p["seedling_reserve"].update(allowed=not expected),
                                   lambda p: p.update(priority=8), lambda p: p.update(id=36)):
                        bad = copy.deepcopy(b)
                        mutate(bad)
                        with self.assertRaises(RuntimeError):
                            trial.reserve.check_bid(bad, spec, True, component)
        with self.assertRaisesRegex(RuntimeError, "component"):
            trial.reserve.treatment_identity(spec, "unknown")

    def test_water_only_retains_root_exception_without_energy_gate(self):
        b = bid()
        b.update(tissue=1, water=6, energy=0)
        b["seedling_reserve"].update(component="water", sun_phase=128)
        b["tick"] = 960
        b["seedling_reserve"]["maintenance_phase"] = 0
        f = trial.reserve.forecast(b)
        self.assertFalse(f["allowed"])
        self.assertTrue(f["wet_root"] and f["water_allowed"])
        f["allowed"] = f["water_allowed"]
        b["seedling_reserve"].update(f)
        counts = trial.reserve.check_bid(b, {"record": {"id": 35, "birth_tick": 960}}, True, "water")
        self.assertEqual(counts["wet_root_exception_bids"], 1)
        self.assertEqual(counts["veto_bids"], 0)

    def test_retained_evidence(self):
        evidence = trial.ROOT / "benchmarks/garden-seasons"
        report = json.loads(gzip.decompress((evidence / "seedling-components-histories.json.gz").read_bytes()))
        self.assertEqual(report["protocol"], trial.RULE)
        self.assertEqual(report["input_sha256"], trial.PRIOR_SHA)
        self.assertEqual(trial.compact(report), json.loads((evidence / "seedling-components-summary.json").read_text()))
        prior, specs = trial.inputs()
        self.assertEqual(len(report["cases"]), 3)
        for spec, old, case in zip(specs, prior["cases"], report["cases"]):
            self.assertEqual((case["key"], case["case"]), (old["key"], old["case"]))
            self.assertEqual(set(case["arms"]), set(trial.ARMS))
            self.assertEqual(case["arms"]["control"], old["control"])
            self.assertEqual(case["arms"]["both"], old["guard"])
            self.assertEqual(case["traces"]["control"], old["traces"]["control"])
            self.assertEqual(case["traces"]["both"], old["traces"]["guard"])
            for name, arm in case["arms"].items():
                steps = arm["steps"]
                self.assertEqual(trial.reserve.ledger(steps), arm["two_days"])
                first = [s for s in steps if s["tick"] <= spec["record"]["birth_tick"] + trial.reserve.DAY]
                self.assertEqual(trial.reserve.ledger(first), arm["first_day"])
                for step in steps:
                    for proposal in step["bids"]:
                        trial.reserve.check_bid(proposal, spec, name != "control",
                                                "both" if name == "control" else name)
                for tick, world in arm["checkpoints"].items():
                    self.assertEqual(world.get("seedling_reserve"), None if name == "control" else
                                     trial.reserve.treatment_identity(spec, name))
                    self.assertIn(int(tick), (spec["record"]["birth_tick"] + trial.reserve.DAY,
                                             spec["record"]["birth_tick"] + 2 * trial.reserve.DAY))
            trial.verify_frames(evidence, spec, case)

    def test_native_cli(self):
        if BUILD is None:
            self.skipTest("native build not supplied")
        option = "--seedling-reserve-component"
        for name in ("toy-factory-garden-inspect", "toy-factory-garden-replay"):
            binary = str(BUILD / name)
            maintenance = "--leaf-policy" in subprocess.check_output([binary, "--help"], text=True)
            command = [binary, "-", "rainfed", "baseline", "123", "--ticks", "120", "--climate", "seasonal"]
            if name.endswith("inspect"):
                command += ["--death-audit"]
            for suffix in ([option], [option, "energy"], [option, "both"],
                           ["--seedling-reserve", "9", option, ""],
                           ["--seedling-reserve", "9", option, "unknown"],
                           ["--seedling-reserve", "9", option, "energy", option, "water"],
                           ["--seedling-reserve", "9", option, "both", option, "both"]):
                self.assertEqual(subprocess.run(command + suffix, capture_output=True, timeout=30).returncode, 2)
            baseline = subprocess.check_output(command, text=True, timeout=30)
            for lineage in (1, 4294967295):
                combined = command + ["--seedling-reserve", str(lineage)]
                for component in trial.ARMS[1:]:
                    run = subprocess.run(combined + [option, component], text=True, capture_output=True, timeout=30)
                    if maintenance:
                        self.assertEqual(run.returncode, 2)
                        continue
                    self.assertEqual(run.returncode, 0, run.stderr)
                    if component == "both":
                        self.assertEqual(run.stdout, subprocess.check_output(combined, text=True, timeout=30))
                    rows = [json.loads(line) for line in run.stdout.splitlines()]
                    self.assertEqual([{k: v for k, v in row.items() if k != "seedling_reserve"} for row in rows],
                                     [json.loads(line) for line in baseline.splitlines()])
                    for row in rows:
                        if row.get("type", "world") == "world":
                            self.assertEqual(row["seedling_reserve"], trial.reserve.treatment_identity(
                                {"record": {"id": lineage}}, component))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    args, remaining = parser.parse_known_args()
    BUILD = args.build.resolve() if args.build else None
    unittest.main(argv=[sys.argv[0], *remaining])
