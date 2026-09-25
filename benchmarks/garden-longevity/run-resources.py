#!/usr/bin/env python3
"""Reproduce fixed-model resource traces and explicitly separate policy probes."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from resources import analyze, require


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def world_hashes(path):
    with path.open() as stream:
        for line in stream:
            value = json.loads(line)
            if value["type"] == "world":
                yield value["tick"], value["hash"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=Path("artifacts/garden-resource-inspect"))
    parser.add_argument("--reference", type=Path, default=Path("artifacts/garden-lifetimes"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    model = args.reference / "champion.tgm"
    require(digest(model) == "bd9f9c6ba7f5fd17309f917972da5f759c305c077798e1d4ba9a52701e2cd48b",
            "this investigation requires the frozen dc5e849d model")
    reference = {}
    for cycles in (2, 4, 8, 16, 24):
        reference[cycles] = json.loads((args.reference / f"cycles-{cycles:02d}.json").read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    sources = sorted(Path("src").glob("*.[ch]")) + sorted(Path("sim").glob("*.[ch]"))
    sources += [Path(__file__), Path(__file__).with_name("resources.py"),
                Path("sim/garden_resources.py")]
    provenance = {
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "git_status": subprocess.check_output(["git", "status", "--short"], text=True),
        "source_sha256": {str(path): digest(path) for path in sources},
        "binary_sha256": digest(args.binary), "model_sha256": digest(model),
        "reference_sha256": {str(path): digest(path) for path in sorted(args.reference.glob("cycles-*.json"))},
        "commands": [],
    }
    cases = [(scenario, policy, "a7b5ccea", ())
             for scenario in ("irrigated", "crowded")
             for policy in ("baseline", "adaptive", "neural-candidate")]
    cases.append(("irrigated", "neural-candidate", "cef5afdf", ()))
    cases += [("crowded", "neural-candidate", "a7b5ccea", options) for options in (
        ("--root-first", "7"), ("--night-wait", "8"),
        ("--root-first", "7", "--night-wait", "7"),
    )]
    results = []
    baseline_path = None
    for index, (scenario_name, policy_name, seed, options) in enumerate(cases):
        path = args.output / f"trace-{index:02d}.jsonl"
        command = [str(args.binary.resolve()), str(model.resolve()), scenario_name, policy_name,
                   f"0x{seed}", "--ecology", *options]
        provenance["commands"].append(command)
        with path.open("x") as stream:
            subprocess.run(command, stdout=stream, check=True)
        result = analyze(path)
        require(result["end_tick"] == 92160, "incomplete resource trace")
        result.update(scenario=scenario_name, policy=policy_name, seed=seed, overrides=options)
        if not options:
            require(result["changed_bids"] == 0, "observational trace changed a bid")
            for cycles, report in reference.items():
                scenario = next(s for s in report["scenarios"] if s["name"] == scenario_name)
                policy = next(p for p in scenario["policies"] if p["name"] == policy_name)
                trial = next(t for t in policy["trials"] if t["seed"] == seed)
                require(result["cycle_hashes"][str(cycles)] == trial["hash"], "reference hash mismatch")
            result["reference_hashes_checked"] = len(reference)
            if scenario_name == "crowded" and policy_name == "neural-candidate":
                baseline_path = path
        else:
            require(baseline_path is not None, "missing unmodified probe control")
            require(result["changed_bids"] > 0, "probe did not change any bids")
            require(result["changed_lineages"] == [int(options[1])], "probe changed another lineage's bids")
            first_difference = next((a[0] for a, b in zip(world_hashes(baseline_path), world_hashes(path), strict=True)
                                     if a != b), None)
            require(first_difference == result["first_changed_bid_tick"], "probe diverged before/after its first intervention")
            result["first_world_difference_tick"] = first_difference
        result["trace_sha256"] = digest(path)
        results.append(result)
        print(f"{index:02d} {scenario_name} {policy_name} {seed} {options or 'unchanged'}: verified", flush=True)
    (args.output / "summary.json").write_text(json.dumps(results, indent=2) + "\n")
    (args.output / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
