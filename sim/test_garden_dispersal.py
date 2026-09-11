#!/usr/bin/env python3
"""Cross-build regression for isolated and explicitly combined ecology experiments."""

import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import garden_dispersal as dispersal
import garden_ecology as ecology
import garden_experiments as experiment


def run(command, expected=0):
    result = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=120)
    if result.returncode != expected:
        raise RuntimeError(f"unexpected result from {command}:\n{result.stdout}\n{result.stderr}")
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--narrow-build", type=Path, required=True)
    variant = parser.add_mutually_exclusive_group(required=True)
    variant.add_argument("--wide-build", type=Path)
    variant.add_argument("--water-build", type=Path)
    variant.add_argument("--combined-build", type=Path)
    args = parser.parse_args()
    changed_build = args.combined_build or args.water_build or args.wide_build
    identity = "--water-uptake" if args.water_build else "--dispersal"
    base_name = "legacy-v1" if args.water_build else "narrow-v1"
    changed_name = "headroom-v1" if args.water_build else "wide-v1"
    environment = experiment.WATER_ENVIRONMENT if args.water_build else experiment.WIDE_ENVIRONMENT
    changed_settings = [identity, changed_name]
    if args.combined_build:
        environment = experiment.COMBINED_ENVIRONMENT
        changed_settings = ["--dispersal", "wide-v1", "--water-uptake", "headroom-v1",
                            "--combined-experiment"]
    scripts = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="garden-dispersal-test-") as temporary:
        root = Path(temporary)
        model = root / "model.tgm"
        run([args.narrow_build / "toy-factory-garden-train", "--generations", "0", "--trials", "1",
             "--ticks", "3840", "--output", model, "--c-output", root / "model.c"])
        for name, build in (("narrow", args.narrow_build), ("changed", changed_build)):
            run([build / "toy-factory-garden-seed-sites-test"])
            if args.water_build or args.combined_build:
                run([build / "toy-factory-garden-water-uptake-test"])
            bundle = root / name
            common = [sys.executable, scripts / "garden_experiments.py", "--output", bundle,
                       "--evaluator", build / "toy-factory-garden-eval",
                       "--inspector", build / "toy-factory-garden-inspect",
                       "--candidate-model", model, "--control-model", model,
                       "--candidate-probe", experiment.NIGHT_PROBE,
                       "--trials", "1", "--cycles", "2", "--trace-pairs", "1"]
            command = common + ([identity, base_name] if name == "narrow" else changed_settings)
            run(command)
            # Wrong declared build identity must fail even before any reproduction.
            run([*common, "--output", root / (name+"-wrong"),
                 *(changed_settings if name == "narrow" else [identity, base_name])], expected=1)
            combined = root / (name+"-combined")
            run([*common, "--output", combined, "--water-uptake", "headroom-v1",
                 "--dispersal", "wide-v1"], expected=1)
            if combined.exists():
                raise RuntimeError("combined experiment was not rejected before collection")
            run([*common, "--output", root / (name+"-incomplete"), "--combined-experiment"], expected=1)
            if (root / (name+"-incomplete")).exists():
                raise RuntimeError("incomplete combined opt-in was accepted")
            if (root / (name+"-wrong") / "manifest.json").exists():
                raise RuntimeError("mismatched ecology was marked complete")
            run([sys.executable, bundle / "tools/garden_experiments.py", "--replay", bundle])
            audit = root / (name+"-audit")
            run([sys.executable, scripts / "garden_establishment.py", "--bundle", bundle,
                 "--output", audit, "--late-cycles", "1",
                 "--inspector", build / "toy-factory-garden-inspect"])
            run([sys.executable, scripts / "garden_establishment.py", "--verify", audit])
            gallery = root / (name+"-gallery")
            command = [sys.executable, scripts / "garden_gallery.py", "--bundle", bundle,
                       "--output", gallery, "--checkpoint", "0", "--checkpoint", "7680",
                       "--replayer", build / "toy-factory-garden-replay"]
            run(command)
            run([sys.executable, scripts / "garden_gallery.py", "--verify", gallery])
            other = args.narrow_build if name == "changed" else changed_build
            run([*command, "--output", root / (name+"-wrong-gallery"), "--replayer",
                 other / "toy-factory-garden-replay"], expected=1)
        a, b = (experiment.read_json(root / name / "manifest.json") for name in ("narrow", "changed"))
        ecology.validate_pair(a, b, environment)
        for field, value in (("seeds", []), ("cycles", 3), ("split", "test"),
                             ("environment", experiment.ENVIRONMENT)):
            bad = copy.deepcopy(b)
            bad[field] = value
            try:
                ecology.validate_pair(a, bad, environment)
            except RuntimeError:
                pass
            else:
                raise RuntimeError(f"invalid paired {field} accepted")
        output = root / "comparison.json"
        command = [sys.executable, scripts / "garden_dispersal.py", "--narrow", root / "narrow",
                   "--wide", root / "changed", "--late-cycles", "1", "--output", output]
        if args.water_build or args.combined_build:
            command = [sys.executable, scripts / "garden_ecology.py", "--control", root / "narrow",
                       "--candidate", root / "changed", "--change",
                       "combined" if args.combined_build else "water-headroom",
                       "--late-cycles", "1", "--output", output]
        else:
            dispersal.validate_pair(a, b)
        run(command)
        if len(json.loads(output.read_text())["pairs"]) != 6:
            raise RuntimeError("comparison lost trials")
        before = output.read_bytes()
        run(command, expected=1)
        if output.read_bytes() != before:
            raise RuntimeError("comparison overwritten")
        # Until scattering, both executables must produce exactly the same worlds.
        for job in ("candidate", "control"):
            timelines = []
            for name in ("narrow", "changed"):
                report = experiment.read_json(root / name / f"reports/{job}.json")
                timelines.append(experiment.load_timelines(root / name / f"timelines/{job}.jsonl.gz", report))
            for key, rows in timelines[0].items():
                other_rows = {row["tick"]: row for row in timelines[1][key]}
                for row in rows:
                    if row["seeds_created"] or ((args.water_build or args.combined_build) and row["tick"] > 60):
                        break
                    if row != other_rows[row["tick"]]:
                        raise RuntimeError("world diverged before the intervention could act")
        print("PASS: two-build ecology boundaries, metadata rejection, audit, screenshots, frozen replay, paired comparison")


if __name__ == "__main__":
    main()
