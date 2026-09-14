#!/usr/bin/env python3
"""Recheck allocation evidence; optionally compare the telemetry-only rerun/export."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sim"))
import garden_allocation as audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=audit.experiment.ROOT / "artifacts/garden-allocation-v2")
    parser.add_argument("--previous-bundle", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.bundle.resolve()
    audit.verify(root)
    manifest = audit.experiment.read_json(root / "manifest.json")
    summary = audit.experiment.read_json(root / "summary.json") | {
        "manifest_sha256": audit.experiment.digest(root / "manifest.json"),
        "input_manifest_sha256": manifest["input_manifest_sha256"],
        "candidate_sha256": manifest["candidate_sha256"],
        "candidate_is_frozen_reference": manifest["candidate_is_frozen_reference"]}
    if args.previous_bundle:
        old = args.previous_bundle.resolve()
        om = audit.experiment.read_json(old / "manifest.json")
        audit.require(om["status"] == "complete" and om["rule"] == audit.RULE and
                      om["specs"] == manifest["specs"] and
                      om["candidate_sha256"] == manifest["candidate_sha256"] and
                      om["input_manifest_sha256"] == manifest["input_manifest_sha256"], "different prior trial")
        rows_checked = frames_checked = 0
        for spec in audit.SPECS:
            name = f"{spec['name']}/trace.jsonl"
            with audit.artifact(old, om, name).open() as a, (root / name).open() as b:
                for left, right in zip(a, b, strict=True):
                    left, right = json.loads(left), json.loads(right)
                    right.pop("new_children", None)
                    audit.require(left == right, "telemetry changed simulation output")
                    rows_checked += 1
        for name in manifest["artifacts"]:
            if name.endswith(".rgb565"):
                audit.require(audit.artifact(old, om, name).read_bytes() == (root / name).read_bytes(),
                              "telemetry changed pixels")
                frames_checked += 1
        summary["telemetry_rerun"] = {"previous_manifest_sha256": audit.experiment.digest(old / "manifest.json"),
            "matching_rows_except_new_children": rows_checked, "identical_native_frames": frames_checked}
        print(f"Telemetry-only rerun: {rows_checked} matching rows, {frames_checked} identical frames")
    if args.output:
        audit.experiment.write_json(args.output, summary)


if __name__ == "__main__":
    main()
