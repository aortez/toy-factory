#!/usr/bin/env python3
"""Summarize exact soil water and checked live-step budgets from frozen uptake experiments."""

import argparse
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sim"))
import garden_ecology as ecology
import garden_establishment as establishment
import garden_experiments as experiment
from garden_resources import budget, require


def soil_summary(root: Path, input_sha: str, late_cycles: int) -> dict:
    manifest = experiment.read_json(root / "manifest.json")
    require(manifest["status"] == "complete" and manifest["kind"] == "garden-establishment"
            and manifest["input_manifest_sha256"] == input_sha
            and manifest["late_cycles"] == late_cycles, "wrong/incomplete seed census")
    for name in manifest["artifacts"]:
        establishment.verified(root, manifest, name)
    cases = experiment.read_json(root / "summary.json")["cases"]
    groups = defaultdict(Counter)
    trials = []
    for case in cases:
        analysis = experiment.read_json(root / case["analysis_path"])
        end = analysis["end_tick"]
        start = end - late_cycles * experiment.CYCLE_TICKS
        values = Counter()
        expected_tick = 0
        with gzip.open(root / "traces" / f"{case['id']}.jsonl.gz", "rt") as stream:
            for line in stream:
                row = json.loads(line)
                require(row["tick"] == expected_tick, "incomplete soil timeline")
                expected_tick += 15
                soil = row["soil"]
                require(0 <= soil["water"] <= 28*11*255
                        and 0 <= soil["saturated_cells"] <= 28*11, "invalid soil totals")
                values["max_water"] = max(values["max_water"], soil["water"])
                values["max_saturated_cells"] = max(values["max_saturated_cells"], soil["saturated_cells"])
                if row["tick"] > start:
                    values["late_samples"] += 1
                    values["late_water_sum"] += soil["water"]
                    values["late_clipped_summary_samples"] += soil["water"] > 65535
        require(expected_tick == end+15 and values["late_samples"] > 0, "wrong soil horizon")
        values["final_water"] = soil["water"]
        group = groups[case["policy"]]
        for name, value in values.items():
            group[name] = max(group[name], value) if name.startswith("max_") else group[name]+value
        group["trials"] += 1
        trials.append({"scenario": case["scenario"], "policy": case["policy"], "seed": case["seed"],
                       **values})
    for values in groups.values():
        values["late_mean_water"] = values["late_water_sum"] / values["late_samples"]
        values["final_mean_water"] = values["final_water"] / values["trials"]
    return {"manifest_sha256": experiment.digest(root / "manifest.json"),
            "aggregate": groups, "trials": trials}


def budgets(root: Path, late_cycles: int, capped: bool) -> list[dict]:
    manifest = experiment.read_json(root / "manifest.json")
    start = (manifest["cycles"]-late_cycles)*experiment.CYCLE_TICKS
    results = []
    for case in experiment.read_json(root / "cases.json")["cases"]:
        previous = {}
        whole, late = Counter(), Counter()
        terminal = 0
        with gzip.open(root / "traces" / f"{case['id']}.jsonl.gz", "rt") as stream:
            for line in stream:
                row = json.loads(line)
                if row["type"] != "world":
                    continue
                if row["tick"]:
                    for plant in row["plants"]:
                        old = previous.get(plant["id"])
                        if plant["dead"]:
                            terminal += old is not None and not old["dead"]
                            continue
                        values = budget(old, plant, row["tick"])
                        require(not capped or values["water_overflow"] == 0,
                                "capped extraction still discards water")
                        values["checked_live_steps"] = 1
                        whole.update(values)
                        if row["tick"] > start:
                            late.update(values)
                previous = {p["id"]: p for p in row["plants"]}
        results.append({"id": case["id"], "scenario": case["scenario"], "policy": case["policy"],
                        "seed": case["seed"], "whole": whole, "late": late,
                        "terminal_steps_not_reconstructed": terminal})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--capped", type=Path, required=True)
    parser.add_argument("--late-cycles", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "output already exists")
    # This verifies the complete matched experiment artifacts before reading budgets.
    result = ecology.compare(args.control.resolve(), args.capped.resolve(),
                             experiment.WATER_ENVIRONMENT, args.late_cycles)
    for name, root in (("control", args.control.resolve()), ("candidate", args.capped.resolve())):
        result[name]["soil"] = soil_summary(root.with_name(root.name+"-audit"),
                                            result[name]["input_manifest_sha256"], args.late_cycles)
        result[name]["selected_budgets"] = budgets(root, args.late_cycles, name == "candidate")
    result["resource_analysis_sha256"] = experiment.digest(Path(__file__))
    result["notes"] += ["Selected resource cases differ across batches; they are not an unbiased paired sample.",
                        "Budgets reconcile live steps only; terminal-step income is cleared and excluded.",
                        "Soil means sample every ecology step, not just sunny or occupied worlds."]
    experiment.write_json(args.output, result)
    print(f"Checked soil censuses and selected live-step budgets: {args.output}")


if __name__ == "__main__":
    main()
