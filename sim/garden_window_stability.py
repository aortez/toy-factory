#!/usr/bin/env python3
"""Fixed late-window sensitivity analysis of saved coverage-pilot review histories."""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import shutil
import time

import garden_mixed_training as mixed

pilot, fitness, experiment, require = mixed.pilot, mixed.fitness, mixed.experiment, mixed.require
DAY, STEP = fitness.DAY, fitness.STEP
RULE = "garden-window-stability-v1"
PROTOCOL = "benchmarks/garden-longevity/window-stability-protocol.md"
BASELINE_SHA = "a9142bff1570b3912b7f7d5dc71dbf4575c3db6df10249cf9b3539643abaf460"
WINDOWS = ((126, 158), (134, 166), (142, 174), (150, 182), (158, 190))
MODELS = {"original": ("g0", "dc5e849d"), "broad-g2": ("g2", "556a5dd2"),
          "broad-final": ("g3", "c7c1b31e"), "narrow-final": ("narrow", "449c35fe")}
PAIRS = {"g2-vs-original": ("original", "broad-g2"),
         "broad-vs-original": ("original", "broad-final"),
         "narrow-vs-original": ("original", "narrow-final"),
         "broad-vs-narrow": ("narrow-final", "broad-final"),
         "broad-vs-g2": ("broad-g2", "broad-final")}
SEEDS = mixed.COVERAGE.review


def direct_key(lineages, seeds, start, end):
    """Independent key arithmetic on full validated timestamps; no projection/helpers."""
    stop = end + 2 * DAY
    indexed = {p["id"]: p for p in lineages}
    alive = lambda p, t: p["birth_tick"] <= t and (p["death_tick"] is None or p["death_tick"] > t)
    established = lambda p, t: p["birth_tick"] + DAY <= t and alive(p, p["birth_tick"] + DAY)
    terminal = [p for p in lineages if alive(p, stop)]
    pending = any(s["birth_tick"] <= stop and (s["end_tick"] is None or s["end_tick"] > stop) for s in seeds)
    tier = 1 if any(p["parent"] and established(p, stop) for p in terminal) else 0 if terminal or pending else -1
    renewal, occupancy, events, parents = 0, 0, 0, set()
    for p in lineages:
        if not p["parent"] or not established(p, end):
            continue
        due = p["birth_tick"] + DAY
        first = max(start + STEP, due)
        last = min(end, p["death_tick"] - STEP if p["death_tick"] is not None else end)
        live = max(0, (last - first) // STEP + 1) * STEP
        occupancy += live
        if start < due <= end:
            events += 1
            parent = indexed[p["parent"]]
            if parent["parent"] and established(parent, end):
                parents.add(parent["id"])
                renewal += live
    return [tier, renewal, occupancy, len(parents), events]


def score_window(lineages, seeds, start, end, source_start, source_stop):
    stop = end + 2 * DAY
    require(0 <= start < end and start % STEP == end % STEP == 0 and stop <= source_stop,
            "invalid or unavailable window follow-up")
    # Validate the unmodified original counters before recounting projected records.
    plants, purchases = fitness.project(lineages, seeds, start, stop, source_start, source_stop)
    score = fitness.world(plants, purchases, start, end, stop)
    require(score["status"] == "complete" and score["key"] == direct_key(lineages, seeds, start, end),
            "projected/reference key mismatch")
    return {"evaluation": score, "cohorts": mixed.validation.cohorts(plants, purchases, score),
            "projected_records": {"lineages": len(plants), "seed_records": len(purchases)}}


def cohort_totals(worlds):
    values = [w["cohorts"] for w in worlds.values()]
    result = {k: sum(c[k] for c in values) for k in ("credited_children", "available_ticks", "live_ticks",
              "lost_ticks", "other_descendant_ticks", "late_births_not_main_confirmable")}
    for key in ("confirmation_cohort", "credited_main_end_states", "purchase_cohort_followed_to_stop"):
        total = Counter()
        for c in values:
            total.update(c[key])
        result[key] = dict(total)
    return result


def contributions(before, after):
    """Compare IDs only within the same history, never across controllers/worlds."""
    a = {c["id"]: c["live_ticks"] for c in before["evaluation"]["renewing_child_occupancy"]}
    b = {c["id"]: c["live_ticks"] for c in after["evaluation"]["renewing_child_occupancy"]}
    leaving, entering, retained = a.keys() - b.keys(), b.keys() - a.keys(), a.keys() & b.keys()
    changes = {"leaving": [{"id": i, "before": a[i], "after": 0} for i in sorted(leaving)],
               "entering": [{"id": i, "before": 0, "after": b[i]} for i in sorted(entering)],
               "retained": [{"id": i, "before": a[i], "after": b[i]} for i in sorted(retained)]}
    sums = {key: sum(c["after"] - c["before"] for c in rows) for key, rows in changes.items()}
    delta = after["evaluation"]["key"][1] - before["evaluation"]["key"][1]
    require(sum(sums.values()) == delta, "adjacent contribution delta does not reconcile")
    return {"children": changes, "ticks": sums, "renewal_delta": delta}


def transitions(windows):
    result = []
    for before, after in zip(windows, windows[1:]):
        models = {}
        for model in MODELS:
            worlds = {key: contributions(before["models"][model]["worlds"][key],
                                          after["models"][model]["worlds"][key]) for key, *_ in mixed.conditions(SEEDS)}
            models[model] = {"worlds": worlds,
                            "ticks": {k: sum(w["ticks"][k] for w in worlds.values()) for k in ("entering", "leaving", "retained")},
                            "renewal_delta": sum(w["renewal_delta"] for w in worlds.values())}
        changes = {}
        for name in ("broad-vs-original", "broad-vs-narrow"):
            control, candidate = PAIRS[name]
            ticks = {k: models[candidate]["ticks"][k] - models[control]["ticks"][k]
                     for k in ("entering", "leaving", "retained")}
            old = before["comparisons"][name]["overall"]
            new = after["comparisons"][name]["overall"]
            margin = lambda pair: pair["candidate"]["key"][2] - pair["control"]["key"][2]
            require(sum(ticks.values()) == margin(new) - margin(old), "paired margin delta differs")
            changes[name] = {"before_margin": margin(old), "after_margin": margin(new), "ticks": ticks}
        result.append({"before": before["days"], "after": after["days"], "models": models, "comparisons": changes})
    return result


def stability(windows):
    require([tuple(w["days"]) for w in windows] == list(WINDOWS), "wrong window set/order")
    result = {}
    for name in PAIRS:
        signs = [w["comparisons"][name]["overall"]["comparison"] for w in windows]
        result[name] = {"signs": signs, "primary": signs[-1],
                        "adjacent_changes": sum(a != b for a, b in zip(signs, signs[1:])),
                        "opposite_to_primary": sum(s == -signs[-1] for s in signs[:-1]) if signs[-1] else None,
                        "ties": signs.count(0)}
    return result


def analyze(root):
    frozen = experiment.read_json(root / "input/coverage-results.json")
    histories = {}
    for model, (name, crc) in MODELS.items():
        reference = frozen["narrow_review"] if name == "narrow" else frozen["review"][int(name[1:])]
        for key, _, seed, patch in mixed.conditions(SEEDS):
            trial = experiment.read_json(root / "input" / f"{name}.{key}.json")
            original = pilot.validate_trial(trial, seed, crc, patch=patch)
            require(original == reference["worlds"][key], "original-score preservation failed")
            histories[model, key] = trial, original["evaluation"]
    windows = []
    for start_day, end_day in WINDOWS:
        models = {}
        for model, (_, crc) in MODELS.items():
            worlds = {}
            for key, *_ in mixed.conditions(SEEDS):
                trial, original = histories[model, key]
                value = score_window(trial["lineages"], trial["seeds"], start_day * DAY, end_day * DAY,
                                     pilot.START, pilot.STOP)
                if (start_day, end_day) == WINDOWS[-1]:
                    require(value["evaluation"] == original, "primary full score differs after projection")
                worlds[key] = value
            models[model] = {"model_crc32": crc, "worlds": worlds, "aggregate": mixed.aggregate(worlds, SEEDS),
                             "cohort_totals": cohort_totals(worlds)}
        comparisons = {name: mixed.comparison(models[a]["worlds"], models[b]["worlds"], SEEDS)
                       for name, (a, b) in PAIRS.items()}
        windows.append({"days": [start_day, end_day], "followup_day": end_day + 2,
                        "primary": (start_day, end_day) == WINDOWS[-1], "models": models, "comparisons": comparisons})
    return {"rule": RULE, "role": "offline-window-sensitivity-not-new-fitness", "native_runs": 0,
            "training_runs": 0, "source_manifest_sha256": BASELINE_SHA, "world_scores": 160,
            "windows": windows, "stability": stability(windows), "transitions": transitions(windows)}


def verify(root):
    m = experiment.read_json(root / "manifest.json")
    require(m["rule"] == RULE and m["status"] == "complete" and m["source_manifest_sha256"] == BASELINE_SHA,
            "wrong/incomplete window analysis")
    for name in m["artifacts"]:
        pilot.gallery.artifact(root, m, name)
    require(experiment.digest(root / "input/coverage-manifest.json") == BASELINE_SHA, "changed source manifest")
    baseline = experiment.read_json(root / "input/coverage-manifest.json")
    require(experiment.digest(root / "input/coverage-results.json") == baseline["artifacts"]["results.json"],
            "changed original results")
    for name, _ in MODELS.values():
        for key, *_ in mixed.conditions(SEEDS):
            file = f"{name}.{key}.json"
            require(experiment.digest(root / "input" / file) == baseline["artifacts"][f"review/{file}"],
                    "changed source history")
    result = analyze(root)
    require(result == experiment.read_json(root / "results.json"), "window reanalysis differs")
    print("Verified 160 offline scores, original primary equality and all adjacent-window decompositions", flush=True)
    return result


def collect(baseline, output):
    require(output.is_relative_to(experiment.ROOT / "artifacts") and not output.exists() and
            not output.is_relative_to(baseline), "choose a fresh separate artifacts output")
    require(experiment.digest(baseline / "manifest.json") == BASELINE_SHA, "wrong frozen coverage bundle")
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
        require(result == analyze(output), "repeat offline analysis differs")
        require(experiment.source_files() == sources, "sources changed during analysis")
        require(all(experiment.digest(output / name) == sha for name, sha in frozen.items()), "changed analysis inputs")
        require(experiment.digest(baseline / "manifest.json") == BASELINE_SHA, "changed baseline")
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
    args = parser.parse_args()
    if args.verify:
        verify(args.output.resolve())
    else:
        collect(args.coverage.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
