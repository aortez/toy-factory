#!/usr/bin/env python3
"""Offline survival-confirmed purchase rescore; no training or new simulation."""
from __future__ import annotations

import argparse
from collections import Counter
import copy
from fractions import Fraction
from pathlib import Path
import shutil

import garden_allocation_objectives as original

experiment, allocation, require = original.experiment, original.allocation, original.require
RULE = "allocation-survival-v1"
BASELINE_SHA = "59a22c88d87bb7f66c6509f02d7efcb97ded37ce692284e851deafa645c4aa49"


def unpack(value):
    return Fraction(value["numerator"], value["denominator"])


def production(evidence):
    """Count observed parent survival, independently of resource-shortage flags."""
    measures = original.features(evidence)
    require(measures["scorable"], "cannot score censored establishment as zero")
    events = [{"tick": e["tick"], "age_day": e["age_day"],
               "confirmation_tick": e["confirmation_tick"],
               "status": original.confirmation_survival(e, evidence)}
              for e in measures["seed_events"]]
    bins = sorted({e["age_day"] for e in events if e["status"] == "alive"})
    return {"seed_events": events, "confirmed_day_bins": bins,
            "confirmed_seeds": sum(e["status"] == "alive" for e in events),
            "status_counts": dict(sorted(Counter(e["status"] for e in events).items())),
            "capped_fraction": original.exact(Fraction(min(original.CAP, len(bins)), original.CAP))}


def scores(evidence):
    measures = original.features(evidence)
    result = original.scores(measures)
    p = unpack(production(evidence)["capped_fraction"])
    for weight in original.WEIGHTS:
        result[f"survival-confirmed-days:{weight}"] = result["survival"] + weight * measures["gate"] * p
    return result


def loss_budget(window):
    """Break-even observed survival loss; descriptive, not an adopted tolerance."""
    duration = Fraction(window["through"] - window["birth"], original.DAY)
    return {str(w): {str(bins): original.exact(w * Fraction(bins, original.CAP) * duration)
                    for bins in (1, original.CAP)} for w in original.WEIGHTS}


def arithmetic_fixtures():
    fixtures = original.arithmetic_fixtures()
    base = fixtures["inactive"]["evidence"]
    day = original.DAY
    extra = {
        "repeated-shortages-survivor": base | {
            "seed_ticks": [2 * day, 3 * day, 4 * day, 5 * day],
            "shortage_ticks": list(range(60, 8 * day + 1, 60))},
        "burst-across-day-boundary": base | {"seed_ticks": [2 * day - original.STEP, 2 * day]},
    }
    fixtures.update({name: {"kind": "arithmetic-only-not-native", "evidence": e,
                           "features": original.features(e)} for name, e in extra.items()})
    for f in fixtures.values():
        f["survival_production"] = production(f["evidence"])
        f["scores"] = {k: original.exact(v) for k, v in scores(f["evidence"]).items()}
    return fixtures


def rescore(baseline):
    """Preserve all original evidence and scores; append three new variants."""
    result = copy.deepcopy(baseline)
    matrices = []
    for case in result["cases"]:
        matrix = {}
        for arm, data in case["arms"].items():
            values = scores(data["evidence"])
            require(all(values[k] == unpack(v) for k, v in data["scores"].items()),
                    "original arm scores changed")
            data["survival_production"] = production(data["evidence"])
            data["scores"] = {k: original.exact(v) for k, v in values.items()}
            data["delta_from_zero_shortage"] = {str(w): original.exact(
                values[f"survival-confirmed-days:{w}"] - values[f"confirmed-days:{w}"])
                for w in original.WEIGHTS}
            matrix[arm] = values
        case["rankings"] = {v: original.ranking({a: matrix[a][v] for a in allocation.ARMS})
                            for v in matrix["reference"]}
        case["break_even_lost_alive_days"] = loss_budget(case["window"])
        matrices.append(matrix)

    def pool(indexes):
        pooled = {}
        for variant in matrices[0]["reference"]:
            means = {arm: sum((matrices[i][arm][variant] for i in indexes), Fraction()) / len(indexes)
                     for arm in allocation.ARMS}
            pooled[variant] = {"means": {a: original.exact(v) for a, v in means.items()},
                               "ranking": original.ranking(means)}
        return pooled

    result.update(rule=RULE, baseline_manifest_sha256=BASELINE_SHA,
                  equal_case_means=pool(list(range(len(matrices)))),
                  leave_one_case_out={case["spec"]["name"]: pool([j for j in range(len(matrices)) if i != j])
                                      for i, case in enumerate(result["cases"])},
                  arithmetic_fixtures=arithmetic_fixtures())
    require(all(result["equal_case_means"][k] == v for k, v in baseline["equal_case_means"].items()),
            "original aggregate scores changed")
    require(all(result["leave_one_case_out"][name][k] == v
                for name, variants in baseline["leave_one_case_out"].items() for k, v in variants.items()),
            "original leave-one-out scores changed")
    return result


def evaluate(bundle, baseline):
    require(experiment.digest(baseline / "manifest.json") == BASELINE_SHA, "wrong frozen baseline")
    manifest = experiment.read_json(baseline / "manifest.json")
    require(manifest["rule"] == original.RULE and manifest["status"] == "complete", "invalid baseline")
    for name in manifest["artifacts"]:
        allocation.artifact(baseline, manifest, name)
    old, inputs = original.evaluate(bundle)
    require(old == experiment.read_json(baseline / "results.json") and inputs == manifest["inputs"],
            "baseline score reproduction differs")
    result = rescore(old)
    result["resource_diagnostics"] = original.followup_diagnostic(bundle, old)
    require(experiment.digest(baseline / "manifest.json") == BASELINE_SHA, "baseline changed during analysis")
    return result, inputs


def collect(bundle, baseline, root):
    require(root.is_relative_to(experiment.ROOT / "artifacts") and not root.exists() and
            not root.is_relative_to(bundle) and not root.is_relative_to(baseline),
            "choose a new artifacts output directory")
    sources = experiment.source_files()
    root.mkdir(parents=True)
    experiment.snapshot_sources(root, sources)
    shutil.copy2(experiment.ROOT / "benchmarks/garden-longevity/allocation-survival-protocol.md",
                 root / "protocol.md")
    started = {"rule": RULE, "input_manifest_sha256": original.INPUT_SHA,
               "baseline_manifest_sha256": BASELINE_SHA, "source_sha256": sources}
    experiment.write_json(root / "started.json", started)
    try:
        result, inputs = evaluate(bundle, baseline)
        experiment.write_json(root / "results.json", result)
        require(experiment.source_files() == sources, "source changed during offline analysis")
        require(all(experiment.digest(bundle / name) == value for name, value in inputs.items()) and
                experiment.digest(bundle / "manifest.json") == original.INPUT_SHA and
                experiment.digest(baseline / "manifest.json") == BASELINE_SHA,
                "input changed during analysis")
        experiment.write_json(root / "manifest.json", started | {"status": "complete", "inputs": inputs,
            "artifacts": {str(p.relative_to(root)): experiment.digest(p) for p in root.rglob("*") if p.is_file()}})
    except BaseException as error:
        experiment.write_json(root / "failure.json", {"error": str(error)})
        raise
    original.show(result)


def verify(root, bundle, baseline, output=None):
    manifest = experiment.read_json(root / "manifest.json")
    require(manifest["rule"] == RULE and manifest["status"] == "complete" and
            manifest["input_manifest_sha256"] == original.INPUT_SHA and
            manifest["baseline_manifest_sha256"] == BASELINE_SHA, "wrong/incomplete survival bundle")
    for name in manifest["artifacts"]:
        allocation.artifact(root, manifest, name)
    result, inputs = evaluate(bundle, baseline)
    require(result == experiment.read_json(root / "results.json") and inputs == manifest["inputs"],
            "survival reanalysis differs")
    if output is not None:
        experiment.write_json(output, result | {"manifest_sha256": experiment.digest(root / "manifest.json")})
    print("Verified original and survival-confirmed scores, resource diagnostics and loss budgets; no simulation")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path)
    group.add_argument("--verify", type=Path)
    parser.add_argument("--bundle", type=Path, default=experiment.ROOT / "artifacts/garden-allocation-v2")
    parser.add_argument("--baseline", type=Path,
                        default=experiment.ROOT / "artifacts/garden-allocation-objectives-v1")
    parser.add_argument("--export", type=Path, help="new JSON path; requires --verify")
    args = parser.parse_args()
    require(args.export is None or args.verify is not None, "export requires verification")
    if args.verify:
        verify(args.verify.resolve(), args.bundle.resolve(), args.baseline.resolve(), args.export)
    else:
        collect(args.bundle.resolve(), args.baseline.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
