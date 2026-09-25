#!/usr/bin/env python3
"""Verify frozen seed-reserve A/B artifacts; optionally reanalyze all native worlds."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/"sim"))
import garden_seed_reserve as trial


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=trial.experiment.ROOT/"artifacts/garden-seed-reserve-v3")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--reanalyze", action="store_true")
    args = parser.parse_args()
    root = args.bundle.resolve()
    m = trial.experiment.read_json(root/"manifest.json")
    trial.require(m["kind"] == "garden-seed-reserve" and m["status"] == "complete" and
                  m["expected_runs"] == 16 and m["baseline_manifest_sha256"] == trial.BASELINE_SHA,
                  "wrong/incomplete comparison")
    for name in m["artifacts"]:
        trial.bank.establishment.verified(root, m, name)
    summary = trial.experiment.read_json(root/"summary.json")
    trial.require([(r["key"], r["gate"]) for r in summary["runs"]] ==
                  [(key, gate) for key in trial.KEYS for gate in ("off", "on")], "wrong panel")
    details = {}
    for r in summary["runs"]:
        key, gate = r["key"], r["gate"]
        name = f"{key}.{gate}"
        full = trial.experiment.read_json(root/f"analyses/{name}.json")
        trial.require(trial.compact(full) == r, "summary mismatch")
        trial.require(trial.turnover.summary_lifetimes(full["world"]["lineages"]) == full["lifetimes"],
                      "lifetime mismatch")
        if args.reanalyze:
            bounds = trial.experiment.read_json(root/f"analyses/{name}.boundaries.json")
            fresh = trial.analyze(root/f"traces/{name}.world.gz", bounds, key, gate)
            trial.require(json.loads(json.dumps(fresh)) ==
                          {k: full[k] for k in fresh}, "resource/world reanalysis mismatch")
            if gate == "on":
                trial.require(trial.compare_prefix(root/f"input/{key}.world.gz",
                    root/f"traces/{name}.world.gz") == full["prefix"], "purchase audit mismatch")
        detail = {"prefix": full.get("prefix")}
        if "resource_trace" in full:
            detail["deaths"] = [{k: v for k, v in d.items() if k not in ("last_day_maintenance", "first_day_points")}
                for d in full["resource_trace"]["closing_natural_deaths"]]
        details[name] = detail
        print(name, "late natural", r["windows"]["late"].get("natural_deaths", 0),
              "survival", {d: (v["survived"], v["eligible"]) for d, v in r["lifetimes"]["closing"]["ages"].items()}, flush=True)
    if args.output:
        trial.require(not args.output.exists(), "output exists")
        trial.experiment.write_json(args.output, summary | {"details": details,
            "manifest_sha256": trial.experiment.digest(root/"manifest.json")})
    print(f"Verified {len(m['artifacts'])} artifacts; {trial.experiment.digest(root/'manifest.json')}")


if __name__ == "__main__":
    main()
