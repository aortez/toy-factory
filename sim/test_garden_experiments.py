#!/usr/bin/env python3
"""Exercise experiment selection, capture invariants, frozen replay, and failure handling."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import garden_experiments as experiment


class SelectionTests(unittest.TestCase):
    def test_seasonal_environment_is_explicit_and_versioned(self):
        for mode in experiment.CLIMATES:
            value = experiment.requested_environment("narrow-v1", "legacy-v1", False, climate=mode)
            experiment.validate_environment(value)
            self.assertEqual(value["climate"], mode)
            if mode != "steady":
                for bad in ({k: v for k, v in value.items() if k != "climate_version"},
                            {**value, "climate_version": 2}, {**value, "climate": "snow"}):
                    with self.assertRaises(RuntimeError):
                        experiment.validate_environment(bad)

    def test_only_known_environments_are_accepted(self):
        experiment.validate_environment(experiment.ENVIRONMENT)
        experiment.validate_environment(experiment.WIDE_ENVIRONMENT)
        experiment.validate_environment(experiment.WATER_ENVIRONMENT)
        experiment.validate_environment(experiment.COMBINED_ENVIRONMENT)
        experiment.validate_environment(experiment.LARGE_POOL_ENVIRONMENT)
        for invalid in ({}, {**experiment.WIDE_ENVIRONMENT, "gardener": True},
                        {**experiment.ENVIRONMENT, "seed_dispersal": "unknown"},
                        {**experiment.COMBINED_ENVIRONMENT, "water_uptake": "unknown"}):
            with self.assertRaisesRegex(RuntimeError, "unexpected experiment environment"):
                experiment.validate_environment(invalid)

    def test_combined_environment_requires_exact_opt_in(self):
        for wide in (False, True):
            for capped in (False, True):
                for opt_in in (False, True):
                    args = ("wide-v1" if wide else "narrow-v1",
                            "headroom-v1" if capped else "legacy-v1", opt_in)
                    if opt_in != (wide and capped):
                        with self.assertRaisesRegex(RuntimeError, "requires"):
                            experiment.requested_environment(*args)
                    else:
                        result = experiment.requested_environment(*args)
                        experiment.validate_environment(result)
                        self.assertEqual(result.get("seed_dispersal") == "wide-v1", wide)
                        self.assertEqual(result.get("water_uptake") == "headroom-v1", capped)

    @staticmethod
    def pair(seed, delta, extinction=None):
        control = dict.fromkeys(experiment.SELECTION_ORDER, 0)
        control.update(viable=1, extinction_tick=None)
        candidate = {**control, "descendant_plant_ticks": delta, "extinction_tick": extinction}
        return {"scenario": "rainfed", "seed": seed, "candidate": candidate, "control": control,
                "delta": {**dict.fromkeys(experiment.SELECTION_ORDER, 0), "descendant_plant_ticks": delta},
                "result": "win" if delta > 0 else "loss" if delta < 0 else "tie"}

    def test_selection_has_typical_gains_losses_and_early_failure(self):
        pairs = [self.pair("a", -10), self.pair("b", 0), self.pair("c", 20), self.pair("d", 1, 60)]
        selected = experiment.select_pairs(pairs, 5)
        self.assertEqual(selected, experiment.select_pairs(list(reversed(pairs)), 5))
        reasons = {reason for pair in selected for reason in pair["reasons"]}
        self.assertTrue({"median paired outcome", "largest paired improvement",
                         "largest paired regression", "earliest extinction"} <= reasons)
        self.assertEqual(len(experiment.select_pairs(pairs, 1)), 1)

    def test_ties_have_no_invented_gains_losses_or_extinctions(self):
        selected = experiment.select_pairs([self.pair("a", 0)], 5)
        self.assertEqual(selected[0]["reasons"], ["median paired outcome", "best candidate outcome"])

    def test_trace_verification_rejects_mismatch_and_truncation(self):
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / "trace.gz"
            rows = [{"type": "world", "tick": 0, "hash": "00000000"},
                    {"type": "world", "tick": 15, "hash": "00000001"}]
            with gzip.open(trace, "wt") as stream:
                stream.write("\n".join(json.dumps(row) for row in rows) + "\n")
            self.assertEqual(experiment.verify_trace(trace, rows), 2)
            bad = copy.deepcopy(rows)
            bad[1]["hash"] = "00000002"
            with self.assertRaisesRegex(RuntimeError, "hash mismatch"):
                experiment.verify_trace(trace, bad)
            bad = rows + [{"tick": 30, "hash": "00000003"}]
            with self.assertRaisesRegex(RuntimeError, "cover every"):
                experiment.verify_trace(trace, bad)

    def test_empty_observations_do_not_invent_failures(self):
        self.assertEqual(experiment.diagnostic_signals({"lineages": []}),
                         {"first_death": None, "first_cycle_night_growth_without_income": []})


def run(command, expected=0):
    result = subprocess.run(list(map(str, command)), text=True, capture_output=True, check=False)
    if result.returncode != expected:
        raise RuntimeError(f"unexpected return {result.returncode} from {command}:\n{result.stdout}\n{result.stderr}")
    return result


def integration(args):
    script = Path(__file__).with_name("garden_experiments.py")
    with tempfile.TemporaryDirectory(prefix="garden-bundle-test-") as temporary:
        root = Path(temporary)
        for ticks in (1, 17, 3840):
            command = [args.evaluator, "--rainfed", "--trials", "1", "--ticks", str(ticks)]
            ordinary = run(command).stdout
            path = root / f"timeline-{ticks}.jsonl"
            observed = run(command + ["--timeline", path]).stdout
            if observed != ordinary:
                raise RuntimeError("timeline collection changed the evaluator report")
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            groups = {}
            for row in rows:
                groups.setdefault((row["scenario"], row["policy"], row["seed"]), []).append(row)
            if len(groups) != 6 or any(values[0]["tick"] != 0 or values[-1]["tick"] != ticks
                                       for values in groups.values()):
                raise RuntimeError("timeline omitted reset or exact final tick")
            before = path.read_bytes()
            run(command + ["--timeline", path], expected=1)
            if before != path.read_bytes():
                raise RuntimeError("existing timeline overwritten")
        bundle = root / "builtin"
        command = [sys.executable, script, "--output", bundle, "--evaluator", args.evaluator,
                   "--inspector", args.inspector, "--trials", "1", "--cycles", "1", "--trace-pairs", "1"]
        run(command)
        manifest = experiment.read_json(bundle / "manifest.json")
        if manifest["status"] != "complete" or len(experiment.read_json(bundle / "cases.json")["cases"]) != 2:
            raise RuntimeError("bundle did not finish with both sides traced")
        run([sys.executable, bundle / "tools/garden_experiments.py", "--replay", bundle, "--case", "01"])
        original = (bundle / "manifest.json").read_bytes()
        run(command, expected=1)
        if (bundle / "manifest.json").read_bytes() != original:
            raise RuntimeError("existing experiment overwritten")
        with (bundle / "cases.json").open("a") as stream:
            stream.write(" ")
        run([sys.executable, script, "--replay", bundle], expected=1)

        model = root / "model.tgm"
        training = root / "training.json"
        result = run([args.trainer, "--generations", "0", "--trials", "1", "--ticks", "3840",
                      "--output", model, "--c-output", root / "model.c", "--seed", "0x1234"])
        training.write_text(result.stdout)
        bundle = root / "models"
        command = [sys.executable, script, "--output", bundle, "--evaluator", args.evaluator,
                   "--inspector", args.inspector, "--trials", "1", "--cycles", "1", "--trace-pairs", "1",
                   "--candidate-model", model, "--control-model", model, "--training-report", training,
                   "--split", "validation"]
        run(command)
        pairs = experiment.read_json(bundle / "comparisons.json")["pairs"]
        if any(pair["result"] != "tie" for pair in pairs):
            raise RuntimeError("identical external models did not tie")
        run([sys.executable, script, "--replay", bundle, "--case", "02"])
        run([*command[:3], root / "overlap", *command[4:], "--seed", "0x1234"], expected=1)
        if (root / "overlap").exists():
            raise RuntimeError("overlapping seeds were not rejected before collection")

        # A replay executable mismatch must not leave a completed bundle.
        failed = root / "failed"
        run([sys.executable, script, "--output", failed, "--evaluator", args.evaluator,
             "--inspector", args.evaluator, "--trials", "1", "--cycles", "1", "--trace-pairs", "1"], expected=1)
        if (failed / "manifest.json").exists() or not (failed / "failure.json").exists():
            raise RuntimeError("failed collection was marked complete")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluator", type=Path, required=True)
    parser.add_argument("--inspector", type=Path, required=True)
    parser.add_argument("--trainer", type=Path, required=True)
    args = parser.parse_args()
    for name in ("evaluator", "inspector", "trainer"):
        setattr(args, name, getattr(args, name).resolve())
    result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(SelectionTests))
    if not result.wasSuccessful():
        return 1
    integration(args)
    print("Experiment capture, model pairing, frozen replay, and failure handling passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
