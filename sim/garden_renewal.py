#!/usr/bin/env python3
"""Summarize a matched night-growth probe without changing training fitness or ecology."""

import argparse
import json
from pathlib import Path
import statistics
import sys

import garden_experiments as experiment
from garden_resources import require


def trial_metrics(rows: list[dict], trial: dict, late_cycles: int) -> dict:
    end = rows[-1]["tick"]
    start = end - late_cycles * experiment.CYCLE_TICKS
    require(0 <= start < end and end % experiment.CYCLE_TICKS == 0, "invalid late window")
    indexed = {row["tick"]: row for row in rows}
    require(start in indexed and "lifetimes" in indexed[start], "missing lifetime boundary")
    first, last = indexed[start], rows[-1]
    require("lifetimes" in last, "missing final lifetime boundary")
    lifetime = trial["lifetimes"]
    result = {
        "start_tick": start, "end_tick": end,
        "living": trial["living"], "seed_bank": trial["seed_bank"],
        "nonviable": int(trial["living"] + trial["seed_bank"] == 0),
        "births": trial["germinations"], "deaths": trial["deaths"],
        "death_causes": trial["death_causes"], "seed_blockers": trial["seed_germination_blockers"],
        "eligible_offspring": lifetime["eligible_offspring"],
        "cycle_survivors": lifetime["cycle_survivors"],
        "durable_parents": lifetime["cycle_survivors_with_surviving_child"],
        "first_dawn_living": indexed[2880]["living"],
        "first_dawn_seed_bank": indexed[2880]["seed_bank"],
    }
    for name in ("births", "deaths", "seeds_created", "seeds_expired"):
        result[f"late_{name}"] = last[name] - first[name]
    for name in ("eligible_offspring", "cycle_survivors", "cycle_survivors_with_surviving_child"):
        result[f"late_qualified_{name}"] = last["lifetimes"][name] - first["lifetimes"][name]
    # Birth/death transitions are recorded exactly. Seed/node occupancy and stores
    # are sampled at <=1 s intervals; hold the previous sample until the next one.
    # Normalize resource pressure by living-plant exposure, not by all-empty samples.
    sums = dict.fromkeys(("living_ticks", "seed_only_ticks", "node_full_ticks", "plant_full_ticks",
                         "seed_full_ticks", "energy_ticks", "water_ticks", "stress_ticks",
                         "live_plant_ticks"), 0)
    for row, following in zip(rows, rows[1:]):
        duration = max(0, following["tick"] - max(start, row["tick"]))
        sums["living_ticks"] += duration * (row["living"] > 0)
        sums["seed_only_ticks"] += duration * (row["living"] == 0 and row["seed_bank"] > 0)
        sums["node_full_ticks"] += duration * (row["nodes"] == 256)
        sums["plant_full_ticks"] += duration * (row["plant_slots"] == 8)
        sums["seed_full_ticks"] += duration * (row["seed_bank"] == 8)
        sums["live_plant_ticks"] += duration * row["living"]
        for name in ("energy", "water", "stress"):
            sums[f"{name}_ticks"] += duration * row[name]
    for name in ("living", "seed_only", "node_full", "plant_full", "seed_full"):
        result[f"late_{name}_fraction"] = sums[f"{name}_ticks"] / (end - start)
    for name in ("energy", "water", "stress"):
        result[f"late_mean_{name}_per_living_plant"] = (
            sums[f"{name}_ticks"] / sums["live_plant_ticks"] if sums["live_plant_ticks"] else None)
    return result


def aggregate(trials: list[dict]) -> dict:
    metrics = {}
    for name, value in trials[0]["metrics"].items():
        if name in ("start_tick", "end_tick") or isinstance(value, dict):
            continue
        values = [trial["metrics"][name] for trial in trials if trial["metrics"][name] is not None]
        metrics[name] = {"count": len(values), "sum": sum(values),
                         "mean": statistics.mean(values) if values else None,
                         "median": statistics.median(values) if values else None,
                         "min": min(values) if values else None, "max": max(values) if values else None}
    return metrics


def summarize(bundle: Path, late_cycles: int) -> dict:
    manifest_path = bundle / "manifest.json"
    manifest = experiment.read_json(manifest_path)
    require(manifest["status"] == "complete" and manifest["schema_version"] == 1,
            "incomplete or unsupported bundle")
    require(manifest.get("candidate_probe") == experiment.NIGHT_PROBE, "wrong policy probe")
    require(manifest["models"]["candidate"]["sha256"] == manifest["models"]["control"]["sha256"],
            "probe and original must use identical model bytes")
    require(manifest["roles"]["candidate"]["policy"] == experiment.NIGHT_POLICY
            and manifest["roles"]["control"]["policy"] == "neural-candidate",
            "probe requires an unchanged neural control")
    for name, sha in manifest["artifacts"].items():
        path = (bundle / name).resolve()
        require(path.is_relative_to(bundle) and experiment.digest(path) == sha,
                f"bundle artifact changed: {name}")
    data = {}
    for job in ("candidate", "control"):
        report = experiment.read_json(bundle / f"reports/{job}.json")
        experiment.validate_report(report, manifest["seeds"], manifest["cycles"] * experiment.CYCLE_TICKS,
                                   manifest["models"][job], manifest.get("candidate_probe")
                                   if job == "candidate" else None, manifest["environment"])
        data[job] = (experiment.load_timelines(bundle / f"timelines/{job}.jsonl.gz", report),
                     experiment.report_trials(report))
    a, b = data["candidate"][1], data["control"][1]
    require(all(a[key] == b[key] for key in a if key[1] in ("baseline", "adaptive")),
            "common controls changed")
    trials = []
    for policy, job in ((experiment.NIGHT_POLICY, "candidate"), ("neural-candidate", "control"),
                        ("adaptive", "control")):
        timelines, finals = data[job]
        for key, rows in sorted(timelines.items()):
            if key[1] == policy:
                trials.append({"scenario": key[0], "policy": policy, "seed": key[2],
                               "metrics": trial_metrics(rows, finals[key], late_cycles)})
    policies = sorted({trial["policy"] for trial in trials})
    return {"schema_version": 1, "input_manifest_sha256": experiment.digest(manifest_path),
            "analysis_sha256": experiment.digest(Path(__file__)), "late_cycles": late_cycles,
            "cycles": manifest["cycles"], "seeds": manifest["seeds"], "trials": trials,
            "environment": manifest["environment"],
            "notes": ["Late qualification counts are new lifetime thresholds reached in the window, not a birth cohort.",
                      "A full-cycle survivor can later die; durable parents and children each survived a cycle, not necessarily concurrently.",
                      "Resource and capacity fractions use <=1 s samples, weighted by elapsed time.",
                      "Seed-bank presence is potential viability, not proof of eventual germination.",
                      "Policies within this bundle share the recorded ecology; compare separate bundles for ecology changes."],
            "aggregate": {policy: aggregate([t for t in trials if t["policy"] == policy])
                          for policy in policies},
            "by_layout": {scenario: {policy: aggregate([t for t in trials if t["policy"] == policy
                                                         and t["scenario"] == scenario])
                                      for policy in policies}
                          for scenario in sorted(experiment.SCENARIOS)}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--late-cycles", type=int, default=8)
    parser.add_argument("--output", required=True, type=Path, help="New JSON report; existing files are refused")
    args = parser.parse_args()
    try:
        require(not args.output.exists(), "output already exists")
        result = summarize(args.bundle.resolve(), args.late_cycles)
        experiment.write_json(args.output, result)
        print(f"Summarized {len(result['trials'])} matched trials: {args.output}")
    except (OSError, RuntimeError, KeyError, ValueError, TypeError) as error:
        print(f"Garden renewal analysis failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
