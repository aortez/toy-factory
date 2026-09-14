#!/usr/bin/env python3
"""Offline bounded-age renewal candidate; no trainer integration or native runs."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import time

import garden_window_stability as previous

mixed, fitness, experiment, require = previous.mixed, previous.fitness, previous.experiment, previous.require
pilot, descendants = mixed.pilot, fitness.descendants
DAY, STEP = previous.DAY, previous.STEP
RULE = "garden-sustained-renewal-candidate-v1"
PROTOCOL = "benchmarks/garden-longevity/sustained-renewal-protocol.md"
PERIODS = ((62, 94), (94, 126), (126, 158), (158, 190))
CREDIT_AGE = 32 * DAY
VIEWS = ("v2-primary", "v2-multi", "rolling-primary", "rolling-multi")
MODELS, SEEDS, PAIRS, BASELINE_SHA = previous.MODELS, previous.SEEDS, previous.PAIRS, previous.BASELINE_SHA


def credit(lineages, start, end):
    """Intersect validated lifetimes with sample-aligned periods and age limits."""
    require(0 <= start < end and start % STEP == end % STEP == 0, "invalid credit interval")
    records = {p["id"]: p for p in lineages}
    children = []
    for p in sorted(lineages, key=lambda p: p["id"]):
        if not p["parent"]:
            continue
        parent = records[p["parent"]]
        due = p["birth_tick"] + DAY
        if not parent["parent"] or due > end:
            continue
        if descendants.confirmation(p, p["birth_tick"], end) != "confirmed" or \
                descendants.confirmation(parent, parent["birth_tick"], due) != "confirmed":
            continue
        first = max(start + STEP, due)
        available_last = min(end, due + CREDIT_AGE - STEP)
        if first > available_last:
            continue
        last = min(available_last, p["death_tick"] - STEP if p["death_tick"] is not None else available_last)
        available = available_last - first + STEP
        live = max(0, last - first + STEP)
        children.append({"id": p["id"], "parent": p["parent"], "confirmation_tick": due,
                         "expires_exclusive": due + CREDIT_AGE, "carry_in": due <= start,
                         "first_sample": first, "available_last_sample": available_last,
                         "last_live_sample": last if live else None,
                         "available_ticks": available, "live_ticks": live, "death_lost_ticks": available - live})
    return {"ticks": sum(p["live_ticks"] for p in children),
            "carry_in_ticks": sum(p["live_ticks"] for p in children if p["carry_in"]),
            "fresh_ticks": sum(p["live_ticks"] for p in children if not p["carry_in"]),
            "available_ticks": sum(p["available_ticks"] for p in children),
            "death_lost_ticks": sum(p["death_lost_ticks"] for p in children), "children": children}


def sampled_credit(lineages, start, end):
    """Independent direct sampled oracle on full timestamps; no interval helpers."""
    records = {p["id"]: p for p in lineages}
    total = 0
    for p in lineages:
        if not p["parent"]:
            continue
        parent = records[p["parent"]]
        due, parent_due = p["birth_tick"] + DAY, parent["birth_tick"] + DAY
        if not parent["parent"] or due > end or \
                (parent["death_tick"] is not None and parent["death_tick"] <= parent_due) or \
                (p["death_tick"] is not None and p["death_tick"] <= due):
            continue
        total += STEP * sum(due <= t < due + CREDIT_AGE and
                            (p["death_tick"] is None or t < p["death_tick"])
                            for t in range(start + STEP, end + STEP, STEP))
    return total


def score_block(lineages, seeds, start, end, source_start, source_stop):
    require(0 < end - start <= CREDIT_AGE and end + fitness.FOLLOWUP <= source_stop,
            "invalid period or unavailable complete follow-up")
    plants, purchases = fitness.project(lineages, seeds, start, end + fitness.FOLLOWUP, source_start, source_stop)
    old = fitness.world(plants, purchases, start, end, end + fitness.FOLLOWUP)
    value = credit(plants, start, end)
    require(value["ticks"] == sampled_credit(lineages, start, end), "interval/sampled credit differs")
    require(old["key"] == previous.direct_key(lineages, seeds, start, end), "v2 direct arithmetic differs")
    require(value["fresh_ticks"] == old["key"][1] and
            value["ticks"] == value["fresh_ticks"] + value["carry_in_ticks"], "carry-in attribution differs")
    return {"days": [start // DAY, end // DAY], "window_ticks": [start, end],
            "status": old["status"], "v2_key": old["key"], "terminal": old["terminal"],
            "followup_deadline": end + fitness.FOLLOWUP, "rolling": value}, old


def history(lineages, seeds, source_start, source_stop):
    blocks = [score_block(lineages, seeds, a * DAY, b * DAY, source_start, source_stop)[0] for a, b in PERIODS]
    combined = credit(lineages, PERIODS[0][0] * DAY, PERIODS[-1][1] * DAY)["ticks"]
    require(sum(b["rolling"]["ticks"] for b in blocks) == combined, "non-additive period credit")
    return {"rule": RULE, "credit_age_ticks": CREDIT_AGE, "blocks": blocks, "combined_ticks": combined}


def aggregate(worlds, expected, view="rolling-multi"):
    require(view in VIEWS and bool(expected) and len(expected) == len(set(expected)) and
            set(worlds) == set(expected), "wrong view or missing/extra/duplicate conditions")
    for w in worlds.values():
        require(w["rule"] == RULE and w["credit_age_ticks"] == CREDIT_AGE and
                [tuple(b["days"]) for b in w["blocks"]] == list(PERIODS), "mismatched candidate contract")
        for b, (a, z) in zip(w["blocks"], PERIODS, strict=True):
            require(b["status"] == "complete" and b["window_ticks"] == [a * DAY, z * DAY] and
                    b["followup_deadline"] == (z + 2) * DAY and b["v2_key"][0] in (-1, 0, 1),
                    "incomplete or misaligned block")
    selected = [len(PERIODS) - 1] if view.endswith("primary") else list(range(len(PERIODS)))
    rolling = view.startswith("rolling")
    totals = [sum(worlds[k]["blocks"][i]["rolling"]["ticks"] if rolling else
                  worlds[k]["blocks"][i]["v2_key"][1] for k in expected) for i in selected]
    tiers = [worlds[k]["blocks"][i]["v2_key"][0] for k in expected for i in selected]
    if view == "v2-primary":
        keys = [worlds[k]["blocks"][-1]["v2_key"] for k in expected]
        key = [min(tiers), *[sum(k[i] for k in keys) for i in range(len(fitness.COMPONENTS))]]
    elif view == "rolling-primary":
        key = [min(tiers), sum(tiers), totals[0]]
    else:
        key = [min(tiers), sum(tiers), min(totals), sum(totals)]
    values = [worlds[k]["blocks"][i]["rolling"]["ticks"] if rolling else
              worlds[k]["blocks"][i]["v2_key"][1] for k in expected for i in selected]
    return {"view": view, "key": key, "world_count": len(expected), "period_sums": totals,
            "mean_denominator": len(expected), "weakest_periods": [list(PERIODS[i]) for i, v in
                zip(selected, totals, strict=True) if v == min(totals)],
            "minimum_world_period_ticks": min(values), "zero_renewal_world_periods": values.count(0),
            "terminal_tier_counts": {str(t): tiers.count(t) for t in (-1, 0, 1)}}


def comparison(control, candidate, view):
    items = mixed.conditions(SEEDS)
    expected = [c[0] for c in items]
    aggregate(control, expected, view)
    aggregate(candidate, expected, view)

    def group(keys):
        a, b = (aggregate({k: worlds[k] for k in keys}, keys, view) for worlds in (control, candidate))
        pairs = []
        for k in keys:
            x, y = (aggregate({k: worlds[k]}, [k], view)["key"] for worlds in (control, candidate))
            pairs.append({"condition": k, "control_key": x, "candidate_key": y,
                          "comparison": (y > x) - (y < x)})
        return {"control": a, "candidate": b, "comparison": (b["key"] > a["key"]) - (b["key"] < a["key"]),
                "pairs": pairs, "paired_counts": {name: sum(p["comparison"] == v for p in pairs)
                    for name, v in (("wins", 1), ("ties", 0), ("losses", -1))}}

    return {"overall": group(expected),
            "schedules": {p: group([k for k, schedule, *_ in items if schedule == p]) for p in mixed.PATCHES},
            "leave_one_world_seed_out": {s: group([k for k, _, seed, _ in items if seed != s]) for s in SEEDS}}


def arithmetic_cases():
    """Constructed histories, not native-reachable behavior or empirical evidence."""
    founder, parent = (1, 0, 0, None, False), (2, 1, DAY, None, False)
    specs = {"steady-replacement": [founder, parent, *[(i + 3, 2, (62 + i * 32) * DAY, None, False) for i in range(4)]],
             "large-single-burst": [founder, parent, *[(i + 3, 2, 62 * DAY + i * STEP, None, False) for i in range(24)]],
             "old-sterile": [founder, parent, (3, 2, 3 * DAY, None, False)],
             "alternating-a": [founder, parent, (3, 2, 61 * DAY + STEP, None, False),
                               (4, 2, 125 * DAY + STEP, None, False)],
             "alternating-b": [founder, parent, (3, 2, 93 * DAY + STEP, None, False),
                               (4, 2, 157 * DAY + STEP, None, False)],
             "founder-only": [founder],
             "pre-confirmation-death": [founder, parent, (3, 2, 70 * DAY, 71 * DAY, False)],
             "seed-only-recovered": [(1, 0, 0, 190 * DAY, False), (2, 1, 190 * DAY + 90, None, False)],
             "seed-only-extinct": [(1, 0, 0, 190 * DAY, False)],
             "seed-only-unconfirmed": [(1, 0, 0, 190 * DAY, False),
                (2, 1, 190 * DAY + 90, 191 * DAY, False), (3, 2, 191 * DAY + 90, 192 * DAY, False)]}
    cases = {}
    for name, plants in specs.items():
        extra = [(3, 192 * DAY - STEP)] if name == "seed-only-unconfirmed" else \
                [(1, 190 * DAY - STEP)] if name == "seed-only-extinct" else []
        f = fitness.fixture(plants, extra, start=62 * DAY, end=190 * DAY)
        h = history(f["lineages"], f["seeds"], 62 * DAY, 192 * DAY)
        cases[name] = {"kind": f["kind"], "lineages": f["lineages"], "seeds": f["seeds"], "history": h,
                       "aggregate": aggregate({"synthetic": h}, ["synthetic"])}
    a, b = (cases[k]["aggregate"] for k in ("steady-replacement", "large-single-burst"))
    require(a["key"] > b["key"] and a["key"][-1] < b["key"][-1], "steady/burst challenge failed")
    require(cases["old-sterile"]["aggregate"]["key"] == [1, 4, 0, 0], "sterile survivors rewarded")
    require(cases["founder-only"]["aggregate"]["key"] == [0, 0, 0, 0], "founder renewal rewarded")
    require(cases["pre-confirmation-death"]["aggregate"]["key"] == [1, 4, 0, 0], "brief child credited")
    for name, tier in (("recovered", 1), ("extinct", -1), ("unconfirmed", 0)):
        require(cases["seed-only-" + name]["history"]["blocks"][-1]["v2_key"][0] == tier,
                "seed-only terminal challenge failed")
    masked = aggregate({name: cases[name]["history"] for name in ("alternating-a", "alternating-b")},
                       ["alternating-a", "alternating-b"])
    require(masked["key"] == [1, 8, 32 * DAY, 128 * DAY] and masked["zero_renewal_world_periods"] == 4,
            "complementary-slump challenge differs")
    return cases


def analyze(root):
    challenges = arithmetic_cases()
    frozen = experiment.read_json(root / "input/coverage-results.json")
    models = {}
    keys = [c[0] for c in mixed.conditions(SEEDS)]
    for model, (name, crc) in MODELS.items():
        reference = frozen["narrow_review"] if name == "narrow" else frozen["review"][int(name[1:])]
        worlds = {}
        for key, _, seed, patch in mixed.conditions(SEEDS):
            trial = experiment.read_json(root / "input" / f"{name}.{key}.json")
            original = pilot.validate_trial(trial, seed, crc, patch=patch)
            require(original == reference["worlds"][key], "changed original evaluation")
            h = history(trial["lineages"], trial["seeds"], pilot.START, pilot.STOP)
            _, primary = score_block(trial["lineages"], trial["seeds"], pilot.START, pilot.END, pilot.START, pilot.STOP)
            require(primary == original["evaluation"], "primary full evaluation changed")
            worlds[key] = h
        models[model] = {"model_crc32": crc, "worlds": worlds,
                         "views": {v: aggregate(worlds, keys, v) for v in VIEWS}}
        require(models[model]["views"]["v2-primary"]["key"] == reference["aggregate"]["key"],
                "primary aggregate changed")
    comparisons = {v: {name: comparison(models[a]["worlds"], models[b]["worlds"], v)
                      for name, (a, b) in PAIRS.items()} for v in VIEWS}
    return {"rule": RULE, "role": "candidate-evaluation-offline-not-adopted", "native_runs": 0, "training_runs": 0,
            "world_period_cases": 128, "source_manifest_sha256": BASELINE_SHA,
            "periods": [list(p) for p in PERIODS], "credit_age_ticks": CREDIT_AGE,
            "models": models, "comparisons": comparisons, "arithmetic_cases": challenges,
            "complementary_slump_panel": aggregate({k: challenges[k]["history"] for k in
                ("alternating-a", "alternating-b")}, ["alternating-a", "alternating-b"])}


def verify(root):
    m = experiment.read_json(root / "manifest.json")
    require(m["rule"] == RULE and m["status"] == "complete" and m["source_manifest_sha256"] == BASELINE_SHA,
            "wrong/incomplete sustained-renewal bundle")
    for name in m["artifacts"]:
        pilot.gallery.artifact(root, m, name)
    baseline = experiment.read_json(root / "input/coverage-manifest.json")
    require(experiment.digest(root / "input/coverage-manifest.json") == BASELINE_SHA, "changed baseline manifest")
    require(experiment.digest(root / "input/coverage-results.json") == baseline["artifacts"]["results.json"],
            "changed original scores")
    for name, _ in MODELS.values():
        for key, *_ in mixed.conditions(SEEDS):
            file = f"{name}.{key}.json"
            require(experiment.digest(root / "input" / file) == baseline["artifacts"][f"review/{file}"],
                    "changed original history")
    result = analyze(root)
    require(result == experiment.read_json(root / "results.json"), "sustained-renewal reanalysis differs")
    print("Verified 128 candidate/v2 cases, sampled-credit parity, additivity and unchanged primary", flush=True)
    return result


def collect(baseline, output):
    require(output.is_relative_to(experiment.ROOT / "artifacts") and not output.exists() and
            not output.is_relative_to(baseline), "choose a fresh separate artifacts output")
    require(experiment.digest(baseline / "manifest.json") == BASELINE_SHA, "wrong coverage input")
    mixed.verify(baseline)
    m = experiment.read_json(baseline / "manifest.json")
    sources = experiment.source_files()
    output.mkdir(parents=True)
    experiment.snapshot_sources(output, sources)
    (output / "input").mkdir()
    copies = {"manifest.json": "coverage-manifest.json", "results.json": "coverage-results.json",
              **{f"review/{name}.{key}.json": f"{name}.{key}.json"
                 for name, _ in MODELS.values() for key, *_ in mixed.conditions(SEEDS)}}
    for src, dest in copies.items():
        shutil.copyfile(baseline / src, output / "input" / dest)
        require(experiment.digest(output / "input" / dest) == (BASELINE_SHA if src == "manifest.json" else m["artifacts"][src]),
                "input copy differs")
    shutil.copyfile(experiment.ROOT / PROTOCOL, output / "protocol.md")
    frozen = {str(p.relative_to(output)): experiment.digest(p) for p in (output / "input").iterdir()}
    experiment.write_json(output / "started.json", {"rule": RULE, "source_manifest_sha256": BASELINE_SHA,
                                                   "sources": sources, "frozen": frozen})
    begin = time.monotonic()
    try:
        result = analyze(output)
        require(result == analyze(output), "repeat analysis differs")
        require(experiment.source_files() == sources, "sources changed during analysis")
        require(all(experiment.digest(output / n) == sha for n, sha in frozen.items()), "analysis inputs changed")
        require(experiment.digest(baseline / "manifest.json") == BASELINE_SHA, "baseline changed")
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
    parser.add_argument("--coverage", type=Path, default=experiment.ROOT / "artifacts/garden-training-coverage-v1")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--export", type=Path, help="export a verified result to a fresh JSON path")
    parser.add_argument("--check-export", type=Path, help="check an existing portable JSON")
    args = parser.parse_args()
    require(not (args.export and args.check_export) and
            (args.verify or not (args.export or args.check_export)), "export/check-export requires verify")
    root = args.output.resolve()
    if not args.verify:
        collect(args.coverage.resolve(), root)
        return
    result = verify(root)
    portable = result | {"manifest_sha256": experiment.digest(root / "manifest.json"),
                         "timing": experiment.read_json(root / "timings.json")}
    if args.export:
        require(not args.export.resolve().is_relative_to(root), "do not export inside frozen evidence")
        experiment.write_json(args.export, portable)
    if args.check_export:
        require(experiment.read_json(args.check_export) == portable, "portable export differs")
        print("Portable sustained-renewal summary matches verified evidence")


if __name__ == "__main__":
    main()
