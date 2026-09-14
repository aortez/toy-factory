#!/usr/bin/env python3
"""Verify wet-root A/B provenance, controls and ledgers; optionally reanalyze worlds."""
import argparse
import gzip
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sim"))
import garden_root_bootstrap as audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=audit.experiment.ROOT / "artifacts/garden-root-bootstrap")
    parser.add_argument("--baseline", type=Path, default=audit.experiment.ROOT / "artifacts/garden-seed-reserve-v3")
    parser.add_argument("--observations", type=Path, default=audit.experiment.ROOT / "artifacts/garden-root-bids")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--reanalyze", action="store_true")
    args = parser.parse_args()
    root, baseline, observations = args.bundle.resolve(), args.baseline.resolve(), args.observations.resolve()
    ex, require = audit.experiment, audit.require
    manifest = ex.read_json(root / "manifest.json")
    require(manifest["kind"] == "garden-root-bootstrap" and manifest["status"] == "complete" and
            manifest["expected_runs"] == 16 and manifest["input_manifest_sha256"] == audit.water.BASELINE_SHA ==
            ex.digest(baseline / "manifest.json"), "wrong/incomplete A/B")
    om = ex.read_json(observations / "manifest.json")
    require(om["kind"] == "garden-root-bids" and om["status"] == "complete" and
            ex.digest(observations / "manifest.json") == manifest["observational_manifest_sha256"], "wrong bid audit")
    for folder, m in ((root, manifest), (observations, om)):
        for name in m["artifacts"]:
            audit.trial.bank.establishment.verified(folder, m, name)
        for name, value in m["inputs"].items():
            require(ex.digest(baseline / name) == value, "frozen input changed")
    summary = ex.read_json(root / "summary.json")
    require([(r["key"], r["arm"]) for r in summary["runs"]] ==
            [(key, arm) for key in audit.trial.KEYS for arm in ("off", "on")], "wrong panel")
    for r in summary["runs"]:
        name = f"{r['key']}.{r['arm']}"
        saved = ex.read_json(root / f"analyses/{name}.json")
        require(audit.compact(saved) == r and
                audit.trial.turnover.summary_lifetimes(saved["world"]["lineages"]) == r["lifetimes"], "summary/lifetime mismatch")
        if r["arm"] == "off":
            require(saved["world"] == ex.read_json(baseline / f"analyses/{r['key']}.on.json")["world"], "control changed")
        for event in saved["audit"]["overrides"]:
            require(audit.expected_override(event["winner"], event["plant_after"]), "recorded winner not modified")
        if args.reanalyze:
            bounds = ex.read_json(root / f"analyses/{name}.boundaries.json")
            side, capacity = r["key"].split(".")[1:]
            after = audit.START if r["arm"] == "on" else None
            path = root / f"traces/{name}.world.gz"
            world, _ = audit.trial.bank.competition.world_analysis(path, "selective", 512, audit.END, audit.START,
                disturbances={b["event"]["tick"]: b for b in bounds},
                growth_policy=audit.trial.bank.recruitment.policy.RESERVE if side == "reserve" else None,
                seed_capacity=int(capacity), seed_reserve=audit.trial.RULE, root_bootstrap_after=after)
            require(world == saved["world"], "world resource reanalysis mismatch")
            with gzip.open(path, "rt") as stream:
                seedlings, histories = audit.water.analyze_stream(stream, bounds, world, r["key"], "on", root_bootstrap_after=after)
            require(json.loads(json.dumps(seedlings)) == saved["seedlings"], "seedling reanalysis mismatch")
            with gzip.open(root / f"analyses/{name}.seedlings.gz", "rt") as stream:
                require(json.loads(json.dumps(histories)) == json.load(stream), "history mismatch")
        print(name, r["first_day_outcomes"], "natural", r["windows"]["late"].get("natural_deaths", 0), flush=True)
    if args.output:
        ex.write_json(args.output, summary | {"manifest_sha256": ex.digest(root / "manifest.json"),
            "input_manifest_sha256": audit.water.BASELINE_SHA,
            "observational_manifest_sha256": manifest["observational_manifest_sha256"]})
    print(f"Verified {len(manifest['artifacts'])} A/B outputs, {len(om['artifacts'])} observational outputs and their inputs")


if __name__ == "__main__":
    main()
