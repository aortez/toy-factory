#!/usr/bin/env python3
"""Offline objective dry-run on frozen allocation controls; never trains or simulates."""
from __future__ import annotations

import argparse
from collections import Counter
from fractions import Fraction
import json
from pathlib import Path
import shutil

import garden_allocation as allocation
from garden_disturbance import schedule
from garden_resources import budget, require

experiment = allocation.experiment
RULE = "allocation-objectives-v1"
INPUT_SHA = "a7cb927521ab5188a1a1622cbfda4ffdd9d930843403fcc9b3cbe43774f98738"
DAY, STEP, CAP = allocation.DAY, 15, 4
WEIGHTS = (Fraction(1, 8), Fraction(1, 4), Fraction(1, 2))


def exact(value):
    value = Fraction(value)
    return {"numerator": value.numerator, "denominator": value.denominator,
            "decimal": round(float(value), 6)}


def common_window(spec, reference):
    require(reference["spec"] == spec, "reference case mismatch")
    events = schedule(0xe4d65e6f, spec["end"])
    planned = [e for e in events if spec["birth"] <= e["tick"] <= spec["end"]]
    require(len(planned) == len(reference["events"]) and all(
        all(saved[k] == v for k, v in event.items())
        for event, saved in zip(planned, reference["events"], strict=True)), "wrong case schedule")
    column = reference["lineage"]["column"]
    hit = next((e for e in planned if e["first_column"] <= column <= e["last_column"]), None)
    through = hit["tick"] - STEP if hit else spec["end"]
    return {"birth": spec["birth"], "through": through, "horizon": spec["end"],
            "reason": "patch" if hit else "horizon", "patch": hit, "column": column,
            "observed_days": exact(Fraction(through - spec["birth"], DAY))}


def seed_status(tick, evidence):
    due, through = tick + DAY, evidence["through"]
    observed_to = min(due, through)
    death = evidence["death"]
    if death is not None and death["cause"] != "patch" and death["tick"] <= observed_to:
        return "natural-failure"
    if any(tick < t <= observed_to for t in evidence["shortage_ticks"]):
        return "resource-shortage"
    if due > through:
        return evidence["reason"] + "-censored"
    return "confirmed"


def features(evidence):
    """Pure arithmetic layer, also exercised with labeled non-native fixtures."""
    birth, through = evidence["birth"], evidence["through"]
    require(type(birth) is int and type(through) is int and 0 <= birth <= through and
            birth % STEP == through % STEP == 0 and evidence["reason"] in ("patch", "horizon"),
            "invalid observation window")
    death = evidence["death"]
    if death is not None:
        require(death["cause"] in ("water", "energy", "both", "patch") and
                type(death["tick"]) is int and death["tick"] > birth and death["tick"] % STEP == 0,
                "invalid death record")
        require(death["cause"] != "patch" or death["tick"] > through,
                "patch must end the common window, not count as natural failure")
    seeds, shortages = evidence["seed_ticks"], evidence["shortage_ticks"]
    require(seeds == sorted(set(seeds)) and all(type(t) is int and birth <= t <= through and
            t % STEP == 0 and (death is None or t < death["tick"]) for t in seeds),
            "invalid/duplicate/out-of-window seed purchase")
    require(shortages == sorted(set(shortages)) and all(type(t) is int and birth < t <= through and
            t % 60 == 0 for t in shortages), "invalid shortage samples")
    if through - birth < DAY:
        return {"scorable": False, "reason": "less-than-one-day-common-followup"}
    alive = lambda tick: death is None or death["tick"] > tick
    last_live = through if death is None else min(through, death["tick"] - STEP)
    alive_steps = max(0, (last_live - birth) // STEP)
    total_steps = (through - birth) // STEP
    gate = int(alive(birth + DAY) and alive(allocation.dawn_tick(birth)))
    events = [{"tick": tick, "age_day": (tick - birth) // DAY,
               "confirmation_tick": tick + DAY, "status": seed_status(tick, evidence)} for tick in seeds]
    confirmed_days = sorted({e["age_day"] for e in events if e["status"] == "confirmed"})
    return {"scorable": True, "gate": gate, "alive_steps": alive_steps,
            "total_steps": total_steps, "raw_seeds": len(seeds), "seed_events": events,
            "seed_status_counts": dict(sorted(Counter(e["status"] for e in events).items())),
            "confirmed_seeds": sum(e["status"] == "confirmed" for e in events),
            "confirmed_day_bins": confirmed_days,
            "observed_survival": exact(Fraction(alive_steps, total_steps))}


def scores(measures):
    require(measures["scorable"], "cannot score censored establishment as zero")
    base = measures["gate"] + Fraction(measures["alive_steps"], measures["total_steps"])
    result = {"survival": base}
    for weight in WEIGHTS:
        result[f"raw-seeds:{weight}"] = base + weight * measures["gate"] * Fraction(
            min(CAP, measures["raw_seeds"]), CAP)
        result[f"confirmed-days:{weight}"] = base + weight * measures["gate"] * Fraction(
            min(CAP, len(measures["confirmed_day_bins"])), CAP)
    return result


def ranking(values):
    """Ties remain ties, in canonical arm order; decimal rounding never decides."""
    return [[arm for arm in allocation.ARMS if values[arm] == value]
            for value in sorted(set(values.values()), reverse=True)]


def arithmetic_fixtures():
    """Counterexamples for score semantics, NOT reachable simulated trajectories."""
    horizon = 8 * DAY
    base = {"birth": 0, "through": horizon, "reason": "horizon", "death": None,
            "seed_ticks": [], "shortage_ticks": []}
    fixtures = {
        "inactive": base,
        "durable-producer": base | {"seed_ticks": [2 * DAY, 3 * DAY, 4 * DAY, 5 * DAY]},
        "burst-then-die": base | {"seed_ticks": [DAY + 60 * i for i in range(1, 9)],
                                  "death": {"tick": DAY + 600, "cause": "energy"}},
        "early-burst-survives": base | {"seed_ticks": [DAY + 60 * i for i in range(1, 9)]},
        "late-collapse": base | {"seed_ticks": [2 * DAY, 3 * DAY, 4 * DAY, 5 * DAY],
                                  "death": {"tick": horizon - 60, "cause": "water"}},
        "late-unconfirmed-burst": base | {"seed_ticks": [horizon - 60 * i for i in range(8, 0, -1)]},
        "shortage-after-seed": base | {"seed_ticks": [2 * DAY], "shortage_ticks": [2 * DAY + 60]},
    }
    return {name: {"kind": "arithmetic-only-not-native", "evidence": e, "features": features(e),
                   "scores": {k: exact(v) for k, v in scores(features(e)).items()}}
            for name, e in fixtures.items()}


def extract(samples, window, saved):
    seed_rows, shortages, live_ticks, totals = [], [], [], Counter()
    previous = None
    for row in samples:
        p, tick = row["plant"], row["tick"]
        require(p is None or p["column"] == window["column"], "target changed column")
        if row["stage"] == "ecology" and p is not None and not p["dead"]:
            values = budget(previous, p, tick)
            totals.update(values)
            if tick <= window["through"]:
                live_ticks.append(tick)
                if tick > window["birth"] and tick % 60 == 0 and p["flags"] & 6:
                    shortages.append(tick)
                if values["energy_seeds"]:
                    require(values["energy_seeds"] == 48 and values["water_seeds"] == 24,
                            "unexpected seed price")
                    seed_rows.append({"tick": tick, "energy_after": p["energy"],
                                      "water_after": p["water"], "nodes_after": p["nodes"]})
        previous = p
    require(dict(totals) == saved["budget"] and len(seed_rows) <= saved["seeds_created"],
            "seed extraction does not reproduce saved budgets")
    evidence = {"birth": window["birth"], "through": window["through"], "reason": window["reason"],
                "death": saved["death"], "seed_ticks": [r["tick"] for r in seed_rows],
                "shortage_ticks": shortages}
    measures = features(evidence)
    require(measures["scorable"], "fixed panel unexpectedly lacks establishment follow-up")
    require(measures["alive_steps"] == sum(window["birth"] < t <= window["through"] for t in live_ticks),
            "survival arithmetic disagrees with recorded live states")
    for event, row in zip(measures["seed_events"], seed_rows, strict=True):
        event.update(row)
    return {"evidence": evidence, "features": measures,
            "diagnostics": {k: saved[k] for k in ("death", "budget", "actions", "peak_active_leaves",
                                                  "seeds_created", "children_germinated", "followup")}}


def evaluate(bundle):
    require(experiment.digest(bundle / "manifest.json") == INPUT_SHA, "wrong frozen input bundle")
    allocation.verify(bundle)
    cases, matrices, inputs = [], [], {}
    for spec in allocation.SPECS:
        name = spec["name"]
        paths = (f"input/{name}.json", f"{name}/trace.jsonl", f"{name}/result.json")
        inputs.update({p: experiment.digest(bundle / p) for p in paths})
        reference = experiment.read_json(bundle / paths[0])
        saved = experiment.read_json(bundle / paths[2])
        with (bundle / paths[1]).open() as stream:
            rows = [json.loads(line) for line in stream]
        window = common_window(spec, reference)
        arms, matrix = {}, {}
        for arm in allocation.ARMS:
            samples = [r for r in rows if r["type"] == "sample" and r["arm"] == arm]
            result = extract(samples, window, saved["arms"][arm])
            matrix[arm] = scores(result["features"])
            arms[arm] = result | {"scores": {k: exact(v) for k, v in matrix[arm].items()}}
        variants = matrix["reference"].keys()
        cases.append({"spec": spec, "window": window, "arms": arms,
                      "rankings": {v: ranking({a: matrix[a][v] for a in allocation.ARMS}) for v in variants}})
        matrices.append(matrix)
    variants = matrices[0]["reference"].keys()
    def pool(indexes):
        result = {}
        for variant in variants:
            means = {arm: sum((matrices[i][arm][variant] for i in indexes), Fraction()) / len(indexes)
                     for arm in allocation.ARMS}
            result[variant] = {"means": {a: exact(v) for a, v in means.items()}, "ranking": ranking(means)}
        return result
    return {"rule": RULE, "input_manifest_sha256": INPUT_SHA, "role": "exploratory-objective-design",
            "weights": [str(w) for w in WEIGHTS], "cap": CAP, "native_runs": 0, "training_runs": 0,
            "cases": cases, "equal_case_means": pool(list(range(len(cases)))),
            "leave_one_case_out": {spec["name"]: pool([j for j in range(len(cases)) if i != j])
                                   for i, spec in enumerate(allocation.SPECS)},
            "arithmetic_fixtures": arithmetic_fixtures()}, inputs


def collect(bundle, root):
    require(root.is_relative_to(experiment.ROOT / "artifacts") and not root.exists() and
            not root.is_relative_to(bundle), "choose a new artifacts output directory")
    sources = experiment.source_files()
    root.mkdir(parents=True)
    experiment.snapshot_sources(root, sources)
    protocol = experiment.ROOT / "benchmarks/garden-longevity/allocation-objectives-protocol.md"
    shutil.copy2(protocol, root / "protocol.md")
    started = {"rule": RULE, "input_manifest_sha256": INPUT_SHA, "source_sha256": sources}
    experiment.write_json(root / "started.json", started)
    try:
        result, inputs = evaluate(bundle)
        experiment.write_json(root / "results.json", result)
        require(experiment.source_files() == sources, "source changed during offline analysis")
        require(all(experiment.digest(bundle / name) == value for name, value in inputs.items()) and
                experiment.digest(bundle / "manifest.json") == INPUT_SHA, "input changed during analysis")
        experiment.write_json(root / "manifest.json", started | {"status": "complete", "inputs": inputs,
            "artifacts": {str(p.relative_to(root)): experiment.digest(p) for p in root.rglob("*") if p.is_file()}})
    except BaseException as error:
        experiment.write_json(root / "failure.json", {"error": str(error)})
        raise
    show(result)


def show(result):
    for variant, value in result["equal_case_means"].items():
        print(variant, {a: s["decimal"] for a, s in value["means"].items()}, value["ranking"])
    for case in result["cases"]:
        print(case["spec"]["name"], {a: r["features"]["seed_status_counts"] for a, r in case["arms"].items()})


def shortage_summary(rows):
    """Describe observed shortage severity, not a reward component."""
    shortages = [r for r in rows if r["tick"] % 60 == 0 and r["plant"]["flags"] & 6]
    streak = longest = 0
    previous = None
    for row in shortages:
        streak = streak + 1 if previous is not None and row["tick"] == previous + 60 else 1
        longest = max(longest, streak)
        previous = row["tick"]
    return {"maintenance_samples": sum(r["tick"] % 60 == 0 for r in rows),
            "shortage_samples": len(shortages), "longest_consecutive_shortage_samples": longest,
            "peak_observed_stress": max((r["plant"]["stress"] for r in rows), default=None),
            "samples": [{"tick": r["tick"], "sun_phase": r["sun_phase"],
                         **{k: r["plant"][k] for k in ("flags", "stress", "energy", "water")}}
                        for r in shortages]}


def confirmation_survival(event, evidence):
    """Alive-only follow-up diagnostic, intentionally NOT another scored variant."""
    due, through = event["confirmation_tick"], evidence["through"]
    death = evidence["death"]
    if death is not None and death["cause"] != "patch" and death["tick"] <= min(due, through):
        return "natural-failure"
    return "alive" if due <= through else evidence["reason"] + "-censored"


def followup_diagnostic(bundle, result):
    """Post-ranking severity check: no objective formula, cap or weight changes."""
    require(experiment.digest(bundle / "manifest.json") == INPUT_SHA, "follow-up input changed")
    manifest = experiment.read_json(bundle / "manifest.json")
    findings = {}
    for case in result["cases"]:
        name = case["spec"]["name"]
        path = allocation.artifact(bundle, manifest, f"{name}/trace.jsonl")
        with path.open() as stream:
            native = [json.loads(line) for line in stream]
        require(experiment.digest(path) == manifest["artifacts"][f"{name}/trace.jsonl"], "follow-up trace changed")
        findings[name] = {}
        for arm, data in case["arms"].items():
            through = data["evidence"]["through"]
            rows = [r for r in native if r["type"] == "sample" and r["arm"] == arm and
                    r["stage"] == "ecology" and r["tick"] <= through and r["plant"] is not None and
                    not r["plant"]["dead"]]
            events = data["features"]["seed_events"]
            followups = [{"seed_tick": e["tick"], "parent_survival": confirmation_survival(e, data["evidence"]),
                          "shortages": shortage_summary([r for r in rows if
                              e["tick"] < r["tick"] <= min(e["confirmation_tick"], through)])}
                         for e in events]
            findings[name][arm] = {
                "whole_scored_window": shortage_summary(rows),
                "after_first_seed": shortage_summary([r for r in rows if r["tick"] > events[0]["tick"]])
                                    if events else None,
                "parent_confirmation_counts": dict(sorted(Counter(f["parent_survival"] for f in followups).items())),
                "seed_followups": followups}
    return {"role": "post-ranking-observational-diagnostic-not-a-scored-variant",
            "tool_sha256": experiment.digest(Path(__file__)), "cases": findings}


def verify(root, bundle, output=None):
    manifest = experiment.read_json(root / "manifest.json")
    require(manifest["rule"] == RULE and manifest["status"] == "complete" and
            manifest["input_manifest_sha256"] == INPUT_SHA, "wrong/incomplete objective bundle")
    for name in manifest["artifacts"]:
        allocation.artifact(root, manifest, name)
    result, inputs = evaluate(bundle)
    require(result == experiment.read_json(root / "results.json") and inputs == manifest["inputs"],
            "objective reanalysis differs")
    if output is not None:
        experiment.write_json(output, result | {"manifest_sha256": experiment.digest(root / "manifest.json"),
                              "followup_diagnostic": followup_diagnostic(bundle, result)})
    print("Verified all objective scores, seed confirmation, ties, sensitivity and leave-one-out rankings; no simulation")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path)
    group.add_argument("--verify", type=Path)
    parser.add_argument("--bundle", type=Path, default=experiment.ROOT / "artifacts/garden-allocation-v2")
    parser.add_argument("--export", type=Path, help="new compact JSON path; requires --verify")
    args = parser.parse_args()
    require(args.export is None or args.verify is not None, "export requires verification")
    if args.verify:
        verify(args.verify.resolve(), args.bundle.resolve(), args.export)
    else:
        collect(args.bundle.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
