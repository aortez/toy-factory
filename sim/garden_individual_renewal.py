#!/usr/bin/env python3
"""Reaggregate frozen bounded-age credit by each garden's weakest period."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import time

import garden_sustained_renewal as previous

experiment, require = previous.experiment, previous.require
DAY, STEP = previous.DAY, previous.STEP
RULE = "garden-individual-renewal-candidate-v1"
PROTOCOL = "benchmarks/garden-longevity/individual-renewal-protocol.md"
BASELINE_SHA = "37b3a11704b365b3bcfee1b043188739a0b96642a331f9e6a8cbf091eef77a75"
PERIODS, MODELS, SEEDS, PAIRS = previous.PERIODS, previous.MODELS, previous.SEEDS, previous.PAIRS


def validate_credit(worlds):
    """Check numeric/ledger consistency in addition to the inherited contract."""
    def ticks(value):
        require(type(value) is int and value >= 0 and value % STEP == 0, "invalid credit ticks")

    for w in worlds.values():
        ticks(w["combined_ticks"])
        require(w["combined_ticks"] == sum(b["rolling"]["ticks"] for b in w["blocks"]), "combined credit differs")
        for b in w["blocks"]:
            require(len(b["v2_key"]) == len(previous.fitness.COMPONENTS) and
                    all(type(v) is int for v in b["v2_key"]), "invalid legacy key")
            r = b["rolling"]
            for k in ("ticks", "carry_in_ticks", "fresh_ticks", "available_ticks", "death_lost_ticks"):
                ticks(r[k])
            children = r["children"]
            ids = [c["id"] for c in children]
            require(len(ids) == len(set(ids)) and all(type(i) is int and i > 0 for i in ids), "duplicate/invalid credit child")
            for c in children:
                require(type(c["carry_in"]) is bool, "invalid carry-in flag")
                for k in ("live_ticks", "available_ticks", "death_lost_ticks"):
                    ticks(c[k])
                require(c["live_ticks"] + c["death_lost_ticks"] == c["available_ticks"], "child credit differs")
            require(r["ticks"] == sum(c["live_ticks"] for c in children) and
                    r["available_ticks"] == sum(c["available_ticks"] for c in children) and
                    r["death_lost_ticks"] == sum(c["death_lost_ticks"] for c in children), "credit ledger differs")
            require(r["ticks"] == r["fresh_ticks"] + r["carry_in_ticks"] and
                    r["fresh_ticks"] == b["v2_key"][1] and
                    r["carry_in_ticks"] == sum(c["live_ticks"] for c in children if c["carry_in"]),
                    "carry-in/legacy attribution differs")


def aggregate(worlds, expected):
    pooled = previous.aggregate(worlds, expected, "rolling-multi")
    validate_credit(worlds)
    rows = {}
    for k in sorted(expected):
        h = worlds[k]
        credits = [b["rolling"]["ticks"] for b in h["blocks"]]
        rows[k] = {"period_ticks": credits, "minimum_ticks": min(credits), "total_ticks": sum(credits),
                   "zero_periods": credits.count(0), "terminal_tiers": [b["v2_key"][0] for b in h["blocks"]],
                   "weakest_periods": [list(p) for p, v in zip(PERIODS, credits, strict=True) if v == min(credits)]}
    minimum_sum = sum(w["minimum_ticks"] for w in rows.values())
    total = sum(w["total_ticks"] for w in rows.values())
    gap = pooled["key"][2] - minimum_sum
    require(gap >= 0 and total == pooled["key"][3], "invalid pooling gap or changed total")
    key = [*pooled["key"][:2], minimum_sum, total]
    if len(expected) == 1:
        require(key == pooled["key"], "single-world ordering changed")
    return {"rule": RULE, "key": key, "pooled_key": pooled["key"], "pooling_gap_ticks": gap,
            "world_count": len(expected), "mean_denominator": len(expected), "worlds": rows,
            "period_sums": pooled["period_sums"],
            "sorted_world_minima": sorted(w["minimum_ticks"] for w in rows.values()),
            "zero_minimum_worlds": [k for k, w in rows.items() if w["minimum_ticks"] == 0],
            "zero_world_periods": sum(w["zero_periods"] for w in rows.values()),
            "terminal_tier_counts": pooled["terminal_tier_counts"]}


def partition_check(worlds, keys, partitions):
    require(sorted(k for group in partitions for k in group) == sorted(keys), "invalid disjoint partition")
    whole = aggregate(worlds, keys)
    groups = [aggregate({k: worlds[k] for k in group}, group) for group in partitions]
    require(whole["key"][2:] == [sum(g["key"][i] for g in groups) for i in (2, 3)],
            "individual credit is not partition additive")
    return {"whole_credit": whole["key"][2:], "partition_credits": [g["key"][2:] for g in groups]}


def pair_group(control, candidate, keys):
    a, b = (aggregate({k: w[k] for k in keys}, keys) for w in (control, candidate))
    pairs = []
    for k in keys:
        x, y = (aggregate({k: w[k]}, [k])["key"] for w in (control, candidate))
        pairs.append({"condition": k, "control_key": x, "candidate_key": y,
                      "comparison": (y > x) - (y < x), "minimum_delta": y[2] - x[2]})
    delta = b["key"][2] - a["key"][2]
    old_delta = b["pooled_key"][2] - a["pooled_key"][2]
    gap_delta = b["pooling_gap_ticks"] - a["pooling_gap_ticks"]
    require(delta == sum(p["minimum_delta"] for p in pairs) and delta == old_delta - gap_delta,
            "paired minimum delta attribution differs")
    return {"control": a, "candidate": b, "comparison": (b["key"] > a["key"]) - (b["key"] < a["key"]),
            "pairs": pairs, "paired_counts": {name: sum(p["comparison"] == v for p in pairs)
                for name, v in (("wins", 1), ("ties", 0), ("losses", -1))},
            "minimum_delta": delta, "pooled_minimum_delta": old_delta, "pooling_gap_delta": gap_delta}


def comparison(control, candidate):
    items = previous.mixed.conditions(SEEDS)
    keys = [c[0] for c in items]
    aggregate(control, keys)
    aggregate(candidate, keys)
    result = {"overall": pair_group(control, candidate, keys),
              "schedules": {p: pair_group(control, candidate, [k for k, s, *_ in items if s == p])
                            for p in previous.mixed.PATCHES},
              "leave_one_world_seed_out": {s: pair_group(control, candidate, [k for k, _, seed, _ in items if seed != s])
                                           for s in SEEDS}}
    schedules = list(result["schedules"].values())
    if all(p["control"]["key"][:2] == p["candidate"]["key"][:2] for p in schedules):
        signs = [p["comparison"] for p in schedules]
        if all(s <= 0 for s in signs) and any(s < 0 for s in signs):
            require(result["overall"]["comparison"] == -1, "schedule loss became a pooled win")
        if all(s >= 0 for s in signs) and any(s > 0 for s in signs):
            require(result["overall"]["comparison"] == 1, "schedule win became a pooled loss")
    return result


def arithmetic_cases(frozen):
    inherited = frozen["arithmetic_cases"]
    require(inherited == previous.arithmetic_cases(), "original arithmetic cases changed")
    cases = {name: aggregate({"synthetic": c["history"]}, ["synthetic"]) for name, c in inherited.items()}
    for name, value in cases.items():
        require(value["key"] == inherited[name]["aggregate"]["key"], "inherited single-world challenge changed")
    founder, parent = (1, 0, 0, None, False), (2, 1, DAY, None, False)
    plants = [founder, parent, *[(3 + 3 * i + j, 2, (62 + i * 32) * DAY + j * STEP, None, False)
                                for i in range(4) for j in range(3)]]
    fixture = previous.fitness.fixture(plants, start=62 * DAY, end=190 * DAY)
    boosted = previous.history(fixture["lineages"], fixture["seeds"], 62 * DAY, 192 * DAY)
    steady, sterile = (inherited[n]["history"] for n in ("steady-replacement", "old-sterile"))
    complementary = aggregate({n: inherited[n]["history"] for n in ("alternating-a", "alternating-b")},
                              ["alternating-a", "alternating-b"])
    compensation = aggregate({"a": boosted, "b": sterile}, ["a", "b"])
    balanced = aggregate({"a": steady, "b": steady}, ["a", "b"])
    require(complementary["key"][2] == 0 and complementary["pooling_gap_ticks"] == 32 * DAY,
            "complementary slumps still receive continuity credit")
    require(compensation["key"] > balanced["key"] and compensation["zero_minimum_worlds"] == ["b"],
            "declared cross-world compensation challenge differs")
    return {"inherited": cases, "complementary": complementary,
            "threefold_fixture": {"kind": fixture["kind"], "lineages": fixture["lineages"],
                                  "seeds": fixture["seeds"], "history": boosted},
            "compensation": compensation, "balanced": balanced}


def analyze(root):
    frozen = experiment.read_json(root / "input/sustained-results.json")
    require(frozen["rule"] == previous.RULE and frozen["world_period_cases"] == 128 and
            frozen["periods"] == [list(p) for p in PERIODS] and
            frozen["credit_age_ticks"] == previous.CREDIT_AGE and set(frozen["models"]) == set(MODELS),
            "wrong frozen candidate input")
    challenges = arithmetic_cases(frozen)
    items = previous.mixed.conditions(SEEDS)
    keys = [c[0] for c in items]
    schedules = [[k for k, s, *_ in items if s == p] for p in previous.mixed.PATCHES]
    models = {}
    for name, (_, crc) in MODELS.items():
        source = frozen["models"][name]
        require(source["model_crc32"] == crc, "changed model identity")
        worlds = source["worlds"]
        for view in previous.VIEWS:
            require(previous.aggregate(worlds, keys, view) == source["views"][view], "old view changed")
        models[name] = {"model_crc32": crc, "aggregate": aggregate(worlds, keys),
                        "previous_views": source["views"], "partition_check": partition_check(worlds, keys, schedules)}
    comparisons = {}
    for name, (a, b) in PAIRS.items():
        x, y = (frozen["models"][m]["worlds"] for m in (a, b))
        old = previous.comparison(x, y, "rolling-multi")
        require(old == frozen["comparisons"]["rolling-multi"][name], "old paired comparison changed")
        proposed = comparison(x, y)
        groups = [(proposed["overall"], old["overall"]),
                  *[(proposed[field][k], old[field][k]) for field in ("schedules", "leave_one_world_seed_out")
                    for k in old[field]]]
        for group, saved in groups:
            require([{k: v for k, v in p.items() if k != "minimum_delta"} for p in group["pairs"]] == saved["pairs"] and
                    group["paired_counts"] == saved["paired_counts"], "individual comparisons changed")
            for side in ("control", "candidate"):
                require(group[side]["pooled_key"] == saved[side]["key"], "old group key changed")
        comparisons[name] = {"previous": old, "proposed": proposed}
    return {"rule": RULE, "role": "candidate-aggregation-offline-not-adopted", "native_runs": 0,
            "training_runs": 0, "unchanged_world_period_inputs": 128, "source_manifest_sha256": BASELINE_SHA,
            "periods": [list(p) for p in PERIODS], "credit_age_ticks": previous.CREDIT_AGE,
            "models": models, "comparisons": comparisons, "arithmetic_cases": challenges}


def verify(root):
    m = experiment.read_json(root / "manifest.json")
    require(m["rule"] == RULE and m["status"] == "complete" and m["source_manifest_sha256"] == BASELINE_SHA,
            "wrong/incomplete individual-renewal bundle")
    for name in m["artifacts"]:
        previous.pilot.gallery.artifact(root, m, name)
    require(experiment.digest(root / "input/sustained-manifest.json") == BASELINE_SHA, "changed source manifest")
    baseline = experiment.read_json(root / "input/sustained-manifest.json")
    require(experiment.digest(root / "input/sustained-results.json") == baseline["artifacts"]["results.json"],
            "changed frozen score ledger")
    result = analyze(root)
    require(result == experiment.read_json(root / "results.json"), "individual-renewal reanalysis differs")
    print("Verified individual-minimum aggregation of 128 unchanged inputs, prior keys and paired/partition identities", flush=True)
    return result


def collect(baseline, output):
    require(output.is_relative_to(experiment.ROOT / "artifacts") and not output.exists() and
            not output.is_relative_to(baseline), "choose a fresh separate artifacts output")
    require(experiment.digest(baseline / "manifest.json") == BASELINE_SHA, "wrong sustained-renewal input")
    previous.verify(baseline)
    manifest = experiment.read_json(baseline / "manifest.json")
    sources = experiment.source_files()
    output.mkdir(parents=True)
    experiment.snapshot_sources(output, sources)
    (output / "input").mkdir()
    for name in ("manifest.json", "results.json"):
        target = output / "input" / f"sustained-{name}"
        shutil.copyfile(baseline / name, target)
        require(experiment.digest(target) == (BASELINE_SHA if name == "manifest.json" else manifest["artifacts"][name]),
                "frozen score copy differs")
    shutil.copyfile(experiment.ROOT / PROTOCOL, output / "protocol.md")
    frozen = {str(p.relative_to(output)): experiment.digest(p) for p in (output / "input").iterdir()}
    experiment.write_json(output / "started.json", {"rule": RULE, "source_manifest_sha256": BASELINE_SHA,
                                                   "sources": sources, "frozen": frozen})
    begin = time.monotonic()
    try:
        result = analyze(output)
        require(result == analyze(output), "repeat aggregation differs")
        require(experiment.source_files() == sources, "sources changed during analysis")
        require(all(experiment.digest(output / n) == sha for n, sha in frozen.items()), "frozen score inputs changed")
        require(experiment.digest(baseline / "manifest.json") == BASELINE_SHA, "source bundle changed")
        experiment.write_json(output / "results.json", result)
        experiment.write_json(output / "timings.json", {"analysis_and_repeat_seconds": time.monotonic() - begin})
        artifacts = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
        experiment.write_json(output / "manifest.json", {"rule": RULE, "status": "complete", "sources": sources,
            "source_manifest_sha256": BASELINE_SHA, "artifacts": artifacts,
            "artifact_bytes": sum((output / n).stat().st_size for n in artifacts)})
    except BaseException as error:
        experiment.write_json(output / "failure.json", {"error": str(error)})
        raise
    verify(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT / "artifacts/garden-sustained-renewal-v1")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--export", type=Path)
    parser.add_argument("--check-export", type=Path)
    args = parser.parse_args()
    require(not (args.export and args.check_export) and
            (args.verify or not (args.export or args.check_export)), "export/check-export requires verify")
    root = args.output.resolve()
    if not args.verify:
        collect(args.baseline.resolve(), root)
        return
    result = verify(root)
    portable = result | {"manifest_sha256": experiment.digest(root / "manifest.json"),
                         "timing": experiment.read_json(root / "timings.json")}
    if args.export:
        require(not args.export.resolve().is_relative_to(root), "do not export inside frozen evidence")
        experiment.write_json(args.export, portable)
    if args.check_export:
        require(experiment.read_json(args.check_export) == portable, "portable export differs")
        print("Portable individual-renewal summary matches verified evidence")


if __name__ == "__main__":
    main()
