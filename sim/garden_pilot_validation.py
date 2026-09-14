#!/usr/bin/env python3
"""Fixed paired evaluation of the original controller and persistence pilot winner."""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import shutil
import tempfile
import time

import garden_training_pilot as pilot

experiment, fitness, require = pilot.experiment, pilot.fitness, pilot.require
DAY, START, END, STOP = pilot.DAY, pilot.START, pilot.END, pilot.STOP
RULE = "garden-pilot-validation-v1"
BASELINE_SHA = "9c9dc94e44cee155b4d8a83276339936d17e97cce4b995259faed4cd31059950"
SEEDS = ("a5a3bb6c", "56b77147", "03cc2e9f", "b08e6511", "2f7ac3ab", "1a685a80", "0d113458", "7cfc4d9c")
PATCHES = {"fresh-1": "e4d65e6f", "fresh-2": "17c29444"}
MODELS = {"control": ("initial", "dc5e849d"), "winner": ("g1-c3", "fa0c2cd8")}
PROTOCOL = "benchmarks/garden-longevity/pilot-validation-protocol.md"


def cohorts(lineages, seeds, score):
    """Exact score attribution, not a new objective or cross-controller ID matching."""
    start, end = score["window"]["start_exclusive"], score["window"]["end_inclusive"]
    stop = score["followup_deadline"]
    records, _ = fitness.descendants.index_records(lineages, seeds, start, stop)
    expected = fitness.world(lineages, seeds, start, end, stop)
    require(score == expected, "cohort score/ledger mismatch")
    credits = {c["id"]: c for c in score["renewing_child_occupancy"]}
    children, outcomes = [], Counter()
    # Use four equal confirmation-time bins for any test window divisible by four steps.
    require((end - start) % (4 * fitness.STEP) == 0, "cohort window must split into four aligned bins")
    width = (end - start) // 4
    bins = [{"start_exclusive": start + i * width, "end_inclusive": start + (i + 1) * width,
             "credited_children": 0, "available_ticks": 0, "live_ticks": 0, "lost_ticks": 0} for i in range(4)]
    for p in lineages:
        due = p["birth_tick"] + DAY
        if not p["parent"] or not start < due <= end:
            continue
        status = fitness.descendants.confirmation(p, p["birth_tick"], end)
        outcomes[status] += 1
        c = credits.get(p["id"])
        parent = records[p["parent"]]
        parent_class = ("founder" if records[p["parent"]]["parent"] == 0 else
                        "established-descendant" if fitness.descendants.confirmation(
                            parent, parent["birth_tick"], end) == "confirmed" else
                        "unconfirmed-descendant")
        live = c["live_ticks"] if c else 0
        available = end - due + fitness.STEP if c else 0
        row = {"id": p["id"], "parent": p["parent"], "birth_tick": p["birth_tick"],
               "confirmation_tick": due, "confirmation": status, "parent_class": parent_class,
               "credited": c is not None, "available_ticks": available, "live_ticks": live,
               "lost_ticks": available - live, "death_tick": p["death_tick"],
               "main_end_state": fitness.descendants.state_at(p, end),
               "followup_state": fitness.descendants.state_at(p, stop)}
        if c:
            bucket = bins[(due - start - fitness.STEP) // width]
            bucket["credited_children"] += 1
            bucket["available_ticks"] += available
            bucket["live_ticks"] += live
            bucket["lost_ticks"] += available - live
        children.append(row)
    require(sum(c["live_ticks"] for c in children) == score["key"][1], "credited child sum differs")
    require(sum(c["live_ticks"] for c in bins) == score["key"][1], "confirmation bin sum differs")
    require(set(credits) <= {c["id"] for c in children}, "unaccounted rewarded child")
    purchases = [s for s in seeds if start < s["birth_tick"] <= end]
    funnel = Counter(purchases=len(purchases), germinated=0, expired=0, pending=0,
                     confirmed=0, natural_failure=0, patch_censored=0, horizon_censored=0)
    for s in purchases:
        funnel[s["outcome"]] += 1
        if s["child_id"] is not None:
            child = records[s["child_id"]]
            status = fitness.descendants.confirmation(child, child["birth_tick"], stop)
            funnel[status.replace("-", "_")] += 1
    require(funnel["pending"] == 0 and funnel["horizon_censored"] == 0 and
            funnel["germinated"] + funnel["expired"] == len(purchases) and
            funnel["germinated"] == sum(funnel[k] for k in ("confirmed", "natural_failure", "patch_censored")),
            "fixed purchase follow-up does not reconcile")
    credited = [c for c in children if c["credited"]]
    return {"confirmation_cohort": dict(outcomes), "children": children, "confirmation_bins": bins,
            "credited_children": len(credited), "available_ticks": sum(c["available_ticks"] for c in credited),
            "live_ticks": sum(c["live_ticks"] for c in credited),
            "lost_ticks": sum(c["lost_ticks"] for c in credited),
            "credited_main_end_states": dict(Counter(c["main_end_state"] for c in credited)),
            "other_descendant_ticks": score["key"][2] - score["key"][1],
            "late_births_not_main_confirmable": sum(p["parent"] != 0 and
                 end < p["birth_tick"] + DAY <= stop + DAY for p in lineages),
            "purchase_cohort_followed_to_stop": dict(funnel)}


def summarize(cases):
    require(len(cases) == 32, "wrong panel size")
    indexed = {(c["schedule"], c["seed"], c["side"]): c for c in cases}
    expected = {(a, s, side) for a in PATCHES for s in SEEDS for side in MODELS}
    require(set(indexed) == expected and len(indexed) == len(cases), "missing/duplicate panel condition")

    def aggregate(keys):
        scores = {side: fitness.aggregate({f"{a}.{s}": indexed[a, s, side]["evaluation"]
                                          for a, s in keys}) for side in MODELS}
        return scores | {"comparison": fitness.compare(scores["winner"], scores["control"])}

    pairs = []
    for schedule in PATCHES:
        for seed in SEEDS:
            a, b = (indexed[schedule, seed, side]["evaluation"] for side in MODELS)
            pairs.append({"schedule": schedule, "seed": seed, "control": a["key"], "winner": b["key"],
                          "comparison": fitness.compare(b, a), "renewal_delta": b["key"][1] - a["key"][1]})
    keys = [(a, s) for a in PATCHES for s in SEEDS]
    selected = []
    for schedule in PATCHES:
        group = [p for p in pairs if p["schedule"] == schedule]
        for label, reverse in (("largest-gain", True), ("largest-loss", False)):
            item = sorted(group, key=lambda p: ((-1 if reverse else 1) * p["renewal_delta"], p["seed"]))[0]
            selected.append({"label": label, "schedule": schedule, "seed": item["seed"], "renewal_delta": item["renewal_delta"]})
    counts = lambda group: {name: sum(p["comparison"] == n for p in group)
                           for name, n in (("wins", 1), ("ties", 0), ("losses", -1))}
    return {"pairs": pairs, "overall": aggregate(keys), "paired_counts": counts(pairs),
            "schedules": {a: {"aggregate": aggregate([(a, s) for s in SEEDS]),
                               "paired_counts": counts([p for p in pairs if p["schedule"] == a])} for a in PATCHES},
            "leave_one_world_seed_out": {s: aggregate([(a, v) for a, v in keys if v != s]) for s in SEEDS},
            "selected": selected}


def analyze_trial(trial, schedule, seed, side):
    value = pilot.validate_trial(trial, seed, MODELS[side][1], patch=PATCHES[schedule])
    return {"schedule": schedule, "seed": seed, "side": side, **value,
            "cohorts": cohorts(trial["lineages"], trial["seeds"], value["evaluation"])}


def case_name(schedule, seed, side):
    return f"{schedule}.{seed}.{side}"


def render(root, selected, cases):
    indexed = {(c["schedule"], c["seed"], c["side"]): c for c in cases}
    rows = []
    for pair in selected:
        frames = []
        for side in MODELS:
            schedule, seed = pair["schedule"], pair["seed"]
            name = case_name(schedule, seed, side)
            identity = f"{pair['label']}.{name}"
            raw, png = root / "images" / f"{identity}.rgb565", root / "images" / f"{identity}.png"
            model = root / "input" / f"{side}.tgm"
            value, _ = pilot.run_json(pilot.replay_command(root, model, seed, STOP, raw, patch=PATCHES[schedule]),
                                      root / "images" / f"{identity}.json")
            trial = experiment.read_json(root / "trials" / f"{name}.json")
            pilot.check_replay(value, trial, seed, MODELS[side][1], STOP, raw.read_bytes(), patch=PATCHES[schedule])
            pilot.gallery.write_png(png, 240, 240, pilot.gallery.rgb565be_to_rgb888(raw.read_bytes()))
            with tempfile.TemporaryDirectory(prefix="paired-frame-") as temp:
                other = Path(temp) / "raw.rgb565"
                repeated, _ = pilot.run_json(pilot.replay_command(root, model, seed, STOP, other, patch=PATCHES[schedule]),
                                             Path(temp) / "replay.json")
                require(repeated == value and other.read_bytes() == raw.read_bytes(), "frame repeat differs")
            c = indexed[schedule, seed, side]
            frames.append({"id": identity, "side": side, "schedule": schedule, "seed": seed,
                           "model_crc32": MODELS[side][1], "tick": STOP, "hash": value["hash"],
                           "framebuffer_crc32": value["framebuffer_crc32"], "key": c["evaluation"]["key"],
                           "framebuffer": str(raw.relative_to(root)), "png": str(png.relative_to(root))})
        rows.append(frames)
    return {"frames": rows, "contact_sheet": pilot.gallery.contact_sheet(root, rows)}


def historical(root):
    result = []
    for seed in pilot.REVIEW:
        for side in MODELS:
            trial = experiment.read_json(root / "input" / f"historical.{seed}.{side}.json")
            result.append(analyze_trial(trial, "fresh-1", seed, side))
    return result


def verify(root):
    m = experiment.read_json(root / "manifest.json")
    require(m["rule"] == RULE and m["status"] == "complete" and m["pilot_manifest_sha256"] == BASELINE_SHA,
            "wrong/incomplete follow-up bundle")
    for name in m["artifacts"]:
        pilot.gallery.artifact(root, m, name)
    baseline = experiment.read_json(root / "input/pilot-manifest.json")
    require(experiment.digest(root / "input/pilot-manifest.json") == BASELINE_SHA, "changed pilot manifest")
    for name in ("garden-persistence-trial", "garden-replay"):
        require(experiment.digest(root / "bin" / name) == baseline["artifacts"][f"bin/{name}"],
                "native executable differs from the frozen pilot")
    for side, (model_id, crc) in MODELS.items():
        model = root / "input" / f"{side}.tgm"
        require(pilot.model_crc(model) == crc and experiment.digest(model) == baseline["artifacts"][f"search/{model_id}.tgm"],
                "changed frozen controller")
    result = experiment.read_json(root / "results.json")
    check_results(root, result)
    print("Verified 32 full ledger/score/cohort/replay comparisons and eight selected frames", flush=True)
    return result


def check_results(root, result):
    recomputed = []
    for schedule in PATCHES:
        for seed in SEEDS:
            for side in MODELS:
                name = case_name(schedule, seed, side)
                trial = experiment.read_json(root / "trials" / f"{name}.json")
                recomputed.append(analyze_trial(trial, schedule, seed, side))
                replay = experiment.read_json(root / "replays" / f"{name}.json")
                pilot.check_replay(replay, trial, seed, MODELS[side][1], STOP, patch=PATCHES[schedule])
    require(recomputed == result["cases"] and summarize(recomputed) == result["panel"], "panel reanalysis differs")
    require(historical(root) == result["historical_review"], "historical reanalysis differs")
    require(len(result["gallery"]["frames"]) == 4, "missing selected pair gallery")
    for pair, row in zip(result["panel"]["selected"], result["gallery"]["frames"], strict=True):
        require([f["side"] for f in row] == list(MODELS), "missing selected controller frame")
        for f in row:
            require(f["schedule"] == pair["schedule"] and f["seed"] == pair["seed"], "wrong selected frame")
            trial = experiment.read_json(root / "trials" / f"{case_name(f['schedule'], f['seed'], f['side'])}.json")
            value = experiment.read_json(root / "images" / f"{f['id']}.json")
            pilot.check_replay(value, trial, f["seed"], f["model_crc32"], STOP,
                               (root / f["framebuffer"]).read_bytes(), patch=PATCHES[f["schedule"]])
            require(f["hash"] == value["hash"] and f["framebuffer_crc32"] == value["framebuffer_crc32"],
                    "frame metadata differs")


def collect(baseline, output):
    require(output.is_relative_to(experiment.ROOT / "artifacts") and not output.exists() and
            not output.is_relative_to(baseline), "choose a fresh artifacts output directory")
    require(experiment.digest(baseline / "manifest.json") == BASELINE_SHA, "wrong frozen pilot")
    pilot.verify(baseline)
    m = experiment.read_json(baseline / "manifest.json")
    output.mkdir(parents=True)
    sources = experiment.source_files()
    experiment.snapshot_sources(output, sources)
    for folder in ("bin", "input", "trials", "replays", "images"):
        (output / folder).mkdir()
    copies = {"manifest.json": "input/pilot-manifest.json", "input/CMakeCache.txt": "input/CMakeCache.txt",
              **{f"bin/{n}": f"bin/{n}" for n in ("garden-persistence-trial", "garden-replay")},
              **{f"search/{model}.tgm": f"input/{side}.tgm" for side, (model, _) in MODELS.items()},
              **{f"review/g{g}.{seed}.json": f"input/historical.{seed}.{side}.json"
                 for seed in pilot.REVIEW for side, g in (("control", 0), ("winner", 1))}}
    for source, destination in copies.items():
        shutil.copy2(baseline / source, output / destination)
        require(experiment.digest(output / destination) ==
                (BASELINE_SHA if source == "manifest.json" else m["artifacts"][source]), "input copy changed")
    shutil.copyfile(experiment.ROOT / PROTOCOL, output / "protocol.md")
    frozen = {str(p.relative_to(output)): experiment.digest(p) for folder in ("bin", "input")
              for p in (output / folder).iterdir()}
    cases, timings = [], []
    begin = time.monotonic()
    experiment.write_json(output / "started.json", {"rule": RULE, "sources": sources, "frozen": frozen})
    try:
        for schedule, patch in PATCHES.items():
            for seed in SEEDS:
                for side, (_, crc) in MODELS.items():
                    name = case_name(schedule, seed, side)
                    model = output / "input" / f"{side}.tgm"
                    trial, elapsed = pilot.run_json([output / "bin/garden-persistence-trial", model, "neural",
                                                     "0x" + seed, "0x" + patch, START, END],
                                                    output / "trials" / f"{name}.json")
                    cases.append(analyze_trial(trial, schedule, seed, side))
                    replay, replay_time = pilot.run_json(pilot.replay_command(output, model, seed, STOP, patch=patch),
                                                        output / "replays" / f"{name}.json")
                    pilot.check_replay(replay, trial, seed, crc, STOP, patch=patch)
                    timings.append({"case": name, "trial_seconds": elapsed, "replay_seconds": replay_time})
                    print(name, trial["key"], f"{elapsed:.2f}s", flush=True)
        panel = summarize(cases)
        result = {"rule": RULE, "cases": cases, "panel": panel, "historical_review": historical(output),
                  "gallery": render(output, panel["selected"], cases)}
        check_results(output, result)
        require(experiment.source_files() == sources, "sources changed during collection")
        require(all(experiment.digest(output / n) == d for n, d in frozen.items()), "frozen inputs changed")
        require(experiment.digest(baseline / "manifest.json") == BASELINE_SHA, "pilot changed during comparison")
        experiment.write_json(output / "results.json", result)
        experiment.write_json(output / "timings.json", {"wall_seconds": time.monotonic() - begin, "calls": timings})
        artifacts = {str(p.relative_to(output)): experiment.digest(p) for p in sorted(output.rglob("*")) if p.is_file()}
        experiment.write_json(output / "manifest.json", {"rule": RULE, "status": "complete", "sources": sources,
            "pilot_manifest_sha256": BASELINE_SHA, "artifacts": artifacts,
            "artifact_bytes": sum((output / n).stat().st_size for n in artifacts)})
    except BaseException as error:
        experiment.write_json(output / "failure.json", {"error": str(error)})
        raise
    verify(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, default=experiment.ROOT / "artifacts/garden-training-pilot-v1")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        verify(args.output.resolve())
    else:
        collect(args.pilot.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
