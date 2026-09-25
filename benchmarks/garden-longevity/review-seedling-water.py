#!/usr/bin/env python3
"""Verify frozen water audit inputs/results and export a compact repo summary."""
import argparse
import gzip
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sim"))
import garden_seedling_water as audit


def compact_point(point):
    if point is None:
        return None
    return {k: point[k] for k in ("tick", "phase", "rain_rate", "root_post_water", "deepest_root_row",
        "pre_growth_water", "earlier_live_root_overlap")} | {
        "plant": {k: point["plant"][k] for k in ("energy", "water", "nodes", "roots", "stress", "root_cells")}}


def compact(result):
    return {k: v for k, v in result.items() if k != "seedlings"} | {"seedlings": [
        {k: (compact_point(v) if k in ("birth", "last_alive", "first_root_extension",
            "first_deeper_root", "first_water_shortage") else v) for k, v in plant.items()}
        for plant in result["seedlings"]]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=audit.trial.experiment.ROOT / "artifacts/garden-seedling-water")
    parser.add_argument("--baseline", type=Path, default=audit.trial.experiment.ROOT / "artifacts/garden-seed-reserve-v3")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--reanalyze", action="store_true")
    args = parser.parse_args()
    root, baseline = args.bundle.resolve(), args.baseline.resolve()
    experiment = audit.trial.experiment
    manifest = experiment.read_json(root / "manifest.json")
    audit.require(manifest["kind"] == "garden-seedling-water" and manifest["status"] == "complete" and
                  manifest["input_manifest_sha256"] == audit.BASELINE_SHA ==
                  experiment.digest(baseline / "manifest.json"), "wrong/incomplete bundle")
    old_manifest = experiment.read_json(baseline / "manifest.json")
    for name in manifest["artifacts"]:
        audit.trial.bank.establishment.verified(root, manifest, name)
    for name, value in manifest["inputs"].items():
        path = audit.trial.bank.establishment.verified(baseline, old_manifest, name)
        audit.require(experiment.digest(path) == value, "input changed")
    audit.require(all(manifest["source_sha256"].get(k) == v for k, v in old_manifest["source_sha256"].items()
                      if k.endswith((".c", ".h"))), "native source changed between audits")
    summary = experiment.read_json(root / "summary.json")
    audit.require([(r["key"], r["gate"]) for r in summary["runs"]] ==
                  [(k, g) for k in audit.trial.KEYS for g in ("off", "on")], "wrong panel")
    for r in summary["runs"]:
        name = f"{r['key']}.{r['gate']}"
        audit.require(r == experiment.read_json(root / f"{name}.json"), "summary mismatch")
        if args.reanalyze:
            reference = experiment.read_json(baseline / f"analyses/{name}.json")
            bounds = experiment.read_json(baseline / f"analyses/{name}.boundaries.json")
            with gzip.open(baseline / f"traces/{name}.world.gz", "rt") as stream:
                fresh, histories = audit.analyze_stream(stream, bounds, reference["world"], r["key"], r["gate"])
            audit.require(json.loads(json.dumps(fresh)) == r, "reanalysis mismatch")
            with gzip.open(root / f"{name}.histories.json.gz", "rt") as stream:
                audit.require(json.loads(json.dumps(histories)) == json.load(stream), "history mismatch")
        print(name, r["outcomes"], r["water_failures"], flush=True)
    if args.output:
        experiment.write_json(args.output, {"manifest_sha256": experiment.digest(root / "manifest.json"),
            "input_manifest_sha256": audit.BASELINE_SHA, "runs": [compact(r) for r in summary["runs"]]})
    print(f"Verified {len(manifest['artifacts'])} outputs and {len(manifest['inputs'])} inputs")


if __name__ == "__main__":
    main()
