#!/usr/bin/env python3
"""Verify and export saved window sensitivity scores; never run native worlds."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sim"))
import garden_window_stability as windows

experiment = windows.experiment


def compact_world(world):
    return {k: v for k, v in world.items() if k != "evaluation"} | {
        "evaluation": {k: v for k, v in world["evaluation"].items() if k != "main_v1"}}


def summary(root, result):
    manifest = experiment.read_json(root / "manifest.json")
    cases = []
    for case in result["windows"]:
        models = {name: {k: v for k, v in model.items() if k != "worlds"} | {
            "worlds": {key: compact_world(w) for key, w in model["worlds"].items()}}
            for name, model in case["models"].items()}
        cases.append({**case, "models": models})
    return {**result, "windows": cases,
            "manifest_sha256": experiment.digest(root / "manifest.json"),
            "artifact_count": len(manifest["artifacts"]), "artifact_bytes": manifest["artifact_bytes"],
            "protocol_sha256": manifest["artifacts"]["protocol.md"],
            "review_seeds": list(windows.SEEDS), "patches": windows.mixed.PATCHES,
            "day_ticks": windows.DAY, "sample_ticks": windows.STEP,
            "repeat_equal": True, "original_primary_equal": True,
            "timing": experiment.read_json(root / "timings.json")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=experiment.ROOT / "artifacts/garden-window-stability-v1")
    parser.add_argument("--export", type=Path, help="fresh portable JSON path (never overwritten)")
    parser.add_argument("--check-export", type=Path, help="verify an existing portable JSON against its bundle")
    args = parser.parse_args()
    windows.require(not (args.export and args.check_export), "choose export or check-export, not both")
    root = args.bundle.resolve()
    result = windows.verify(root)
    portable = summary(root, result)
    if args.export:
        target = args.export.resolve()
        windows.require(not target.is_relative_to(root), "do not write inside the frozen bundle")
        experiment.write_json(target, portable)
        print(f"Exported all 160 scores, cohorts and adjacent-window decompositions: {target}")
    if args.check_export:
        windows.require(experiment.read_json(args.check_export) == portable, "portable export differs")
        print("Portable window summary matches the verified bundle")


if __name__ == "__main__":
    main()
