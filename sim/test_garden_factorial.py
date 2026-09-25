#!/usr/bin/env python3
"""Check factorial identities, contrasts, missing observations and configuration guards."""

import copy
import itertools
from pathlib import Path
import subprocess
import tempfile
import unittest

import garden_ecology as ecology
import garden_experiments as experiment
import garden_factorial as factorial


class FactorialTests(unittest.TestCase):
    def panel(self):
        data = {}
        for name, births in (("baseline", 10), ("wide", 13), ("capped", 11), ("combined", 20)):
            data[name] = {"trials": [
                {"scenario": "rainfed", "policy": "adaptive", "seed": seed,
                 "metrics": {"births": births, "living": 4, "mean_water": None if name == "wide" else 12}}
                for seed in ("00000002", "00000001")]}
        return data

    def test_contrasts_and_interaction(self):
        data = self.panel()
        result = factorial.contrasts(data)
        self.assertEqual(result["combined_versus_capped"][0]["delta"]["births"], 9)
        self.assertEqual(result["combined_versus_wide"][0]["delta"]["births"], 7)
        for row in result["interaction"]:
            self.assertEqual(row["delta"]["births"], 6)
            self.assertEqual(row["delta"]["living"], 0)
            self.assertNotIn("mean_water", row["delta"])
        for condition in data.values():
            condition["trials"].reverse()
        self.assertEqual(factorial.contrasts(data), result)

    def test_missing_and_duplicate_worlds_rejected(self):
        for mode in ("condition", "trial", "duplicate"):
            data = self.panel()
            if mode == "condition":
                del data["capped"]
            elif mode == "trial":
                data["combined"]["trials"].pop()
            else:
                data["combined"]["trials"].append(data["combined"]["trials"][0])
            with self.assertRaises(RuntimeError):
                factorial.contrasts(data)

    def test_wrong_factorial_inputs_rejected(self):
        base = {"environment": experiment.ENVIRONMENT, "split": "exploratory", "cycles": 24,
                "seeds": ["00000001"], "seed": "00000001", "trial_count": 1,
                "roles": {"a": 1}, "candidate_probe": experiment.NIGHT_PROBE,
                "declared_training_seeds": [],
                "models": {k: {"sha256": "same"} for k in ("candidate", "control")}}
        for environment in (experiment.WIDE_ENVIRONMENT, experiment.WATER_ENVIRONMENT,
                            experiment.COMBINED_ENVIRONMENT):
            candidate = {**copy.deepcopy(base), "environment": environment}
            ecology.validate_pair(base, candidate, environment)
            for field, value in (("environment", experiment.ENVIRONMENT), ("cycles", 23),
                                 ("split", "test"), ("seeds", ["00000002"]), ("roles", {})):
                with self.assertRaises(RuntimeError):
                    ecology.validate_pair(base, {**candidate, field: value}, environment)
            candidate["models"]["control"]["sha256"] = "other"
            with self.assertRaises(RuntimeError):
                ecology.validate_pair(base, candidate, environment)

    def test_build_and_header_guards(self):
        source = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(prefix="garden-ecology-config-") as temporary:
            for wide, capped, combined in itertools.product((False, True), repeat=3):
                valid = combined == (wide and capped)
                definitions = [name for name, enabled in (
                    ("TOY_FACTORY_GARDEN_WIDE_DISPERSAL", wide),
                    ("TOY_FACTORY_GARDEN_WATER_HEADROOM", capped),
                    ("TOY_FACTORY_GARDEN_COMBINED_EXPERIMENT", combined)) if enabled]
                # Check the header even when a caller bypasses CMake.
                command = ["cc", "-E", "-x", "c", "-I", str(source.parent / "src"),
                           *["-D"+name+"=1" for name in definitions], "-"]
                code = '#include "garden_world.h"\n'
                result = subprocess.run(command, input=code, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode == 0, valid, result.stderr)
                if wide or capped or combined:
                    result = subprocess.run([*command[:-1], "-D__ZEPHYR__=1", "-"], input=code,
                                            capture_output=True, text=True, timeout=30)
                    self.assertNotEqual(result.returncode, 0)
                if not valid:
                    result = subprocess.run(["cmake", "-S", str(source), "-B",
                                             str(Path(temporary) / f"{wide}-{capped}-{combined}"),
                                             *["-D"+name+"=ON" for name in definitions]],
                                            capture_output=True, text=True, timeout=30)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("Combined", result.stderr)


if __name__ == "__main__":
    unittest.main()
