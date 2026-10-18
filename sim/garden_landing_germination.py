#!/usr/bin/env python3
"""Offline final-period seed checks from the frozen shoot-budget comparison."""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import sys

import garden_landing_budget as previous
from garden_experiments import digest
from garden_resources import require

ROOT, DAY, STEP, STOP = previous.ROOT, previous.DAY, previous.STEP, previous.STOP
START, END = 158 * DAY, 190 * DAY
ARMS = ("eligible", "reserve")
RULE = "garden-landing-budget-germination-v1"
WINDOW_RULE = RULE + "-windows"
INPUT = "benchmarks/garden-seasons/landing-budget-results.json.gz"
INPUT_SHA = "bad5297fa26ad52b93a899e3d0f0fcd3255a6b5e214e1120f68bc3902e455640"
MANIFEST_SHA = "35ee02313a8ed5adb0ad86ce31094b5109941d50bccbd3de3f6eaebc27bf8ec2"
WINDOWS = "benchmarks/garden-seasons/landing-budget-germination-windows.json.gz"
WINDOWS_SHA = "9de2ef4f06c7f435c666d11c75fc7f0211351bdd246161cded3dbbcd6fc61099"
recruitment = previous.growth.recruitment
turnover = previous.growth.turnover
renewal, lifetimes = turnover.renewal, turnover.lifetimes


def load(path, expected):
    require(digest(path) == expected, "wrong frozen input: " + str(path))
    with gzip.open(path, "rt") as stream:
        return json.load(stream)


def panel(data):
    require(data["rule"] == previous.RULE and data["training_runs"] == 0 and
            len(data["worlds"]) == 12, "wrong budget panel")
    worlds = [w for w in data["worlds"] if w["case"]["climate"] == "seasonal"]
    require(len(worlds) == 6 and len({w["id"] for w in worlds}) == 6, "wrong seasonal panel")
    return worlds


def extract(bundle, data):
    """Copy exact seed rows only; never start a native executable."""
    require(not (bundle / "FAILED.txt").exists() and
            digest(bundle / "manifest.json") == MANIFEST_SHA, "wrong/incomplete source bundle")
    manifest = json.loads((bundle / "manifest.json").read_text())
    require(manifest["rule"] == previous.RULE and manifest["status"] == "complete" and
            digest(bundle / "results.json.gz") == INPUT_SHA, "bundle result differs")
    worlds = []
    for w in panel(data):
        arms = {}
        for arm in ARMS:
            name = arm + "--" + w["id"] + "-children.jsonl.gz"
            sha = w["arms"][arm]["trace_sha256"]
            path = bundle / name
            require(manifest["artifacts"][name] == digest(path) == sha, "source trace differs")
            rows = []
            with gzip.open(path, "rt") as stream:
                require(json.loads(next(stream)) == {"schema": "landing-recruitment-trace-v1"},
                        "wrong source schema")
                for tick in range(STEP, STOP + STEP, STEP):
                    row = json.loads(next(stream))
                    require(set(row) == {"tick", "seeds", "plants"} and row["tick"] == tick,
                            "source trace clock differs")
                    if START < tick <= END:
                        rows.append({"tick": tick, "seeds": row["seeds"]})
                require(json.loads(next(stream)) == {"complete": True, "tick": STOP} and
                        stream.read() == "", "incomplete/trailing source trace")
            require(digest(path) == sha, "source trace changed during extraction")
            arms[arm] = {"trace_sha256": sha, "rows": rows}
            print(w["id"] + " / " + arm + ": extracted fixed seed window", flush=True)
        worlds.append({"id": w["id"], "arms": arms})
    require(digest(bundle / "manifest.json") == MANIFEST_SHA, "source manifest changed")
    return {"rule": WINDOW_RULE, "input_sha256": INPUT_SHA, "manifest_sha256": MANIFEST_SHA,
            "window_ticks": [START, END], "sample_step": STEP, "worlds": worlds}


def masks_summary(hist):
    """Overlapping reasons, not mutually exclusive causal attributions."""
    counts = {b: sum(n for m, n in hist.items() if int(m) & (1 << i))
              for i, b in enumerate(recruitment.BLOCKERS)}
    return {"mature_checks": sum(hist.values()), "mature_masks": dict(sorted(hist.items(), key=lambda x: int(x[0]))),
            "blocker_checks": counts,
            "sole_blocker_checks": {b: hist.get(str(1 << i), 0) for i, b in enumerate(recruitment.BLOCKERS)},
            "always_mature_blockers": [b for b, n in counts.items() if n and n == sum(hist.values())]}


def living_before_seed_check(plants, tick, newborns):
    # Resource deaths/decomposition precede germination; earlier successful
    # seed checks in this same step have already installed their new plant.
    # Dead bodies can still occupy slots: this is a living-witness lower bound,
    # not reconstruction of every retained dead slot.
    return [p for p in plants if (p["birth_tick"] < tick or p["id"] in newborns) and
            (p["death_tick"] is None or p["death_tick"] > tick)]


def seed_window(result, rows, start=START, end=END):
    require(type(start) is int and type(end) is int and 0 <= start < end <= result["tick"] and
            start % STEP == end % STEP == 0, "invalid seed window")
    require(len(rows) == (end - start) // STEP, "missing/extra window samples")
    plants = result["lineages"]
    seeds = {(s["parent"], s["birth_tick"]): s for s in result["seeds"]}
    require(len(seeds) == len(result["seeds"]), "duplicate seed ledger")
    selected = {k: {**s, "cohort": "carry_in" if s["birth_tick"] <= start else "purchased",
        "outcome_at_window_end": s["outcome"] if s["end_tick"] is not None and s["end_tick"] <= end else "pending",
        "samples": 0, "checks": 0, "dormant_checks": 0, "expiry_samples": 0,
        "mature_masks": Counter(), "open_elsewhere_checks": 0,
        "spacing_with_living_witness": 0, "spacing_without_living_witness": 0,
        "parent_spacing_checks": 0, "other_spacing_checks": 0, "living_witnesses": Counter()}
        for k, s in seeds.items() if s["birth_tick"] <= end and (s["end_tick"] is None or s["end_tick"] > start)}
    open_ticks, mature_ticks, sole_spacing_ticks = set(), set(), set()
    germinations = []
    for tick, row in zip(range(start + STEP, end + STEP, STEP), rows, strict=True):
        require(set(row) == {"tick", "seeds"} and type(row["tick"]) is int and row["tick"] == tick,
                "missing/reordered window sample")
        seen, newborns = set(), set()
        for values in row["seeds"]:
            require(len(values) == 11 and all(type(v) is int for v in values), "invalid seed receipt")
            parent, age, column, mask, moisture, light, slots, nodes, outcome, child, opened = values
            key = parent, tick - age * STEP
            require(key in selected and key not in seen, "unknown/duplicate seed receipt")
            seen.add(key)
            s = selected[key]
            require(s["birth_tick"] < tick <= (s["end_tick"] or result["tick"]) and
                    age > 0 and 0 <= column < 28 and column == s["column"] and
                    0 <= mask < 128 and 0 <= moisture <= 255 and 0 <= light <= 255 and
                    0 <= slots <= 8 and 0 <= nodes <= 256, "invalid seed identity/resources")
            expected = 0 if s["end_tick"] != tick else {"expired": 1, "germinated": 2}[s["outcome"]]
            require(outcome == expected and child == (s["child_id"] if outcome == 2 else 0), "seed fate differs")
            s["samples"] += 1
            if outcome == 1:
                require(age == s["lifetime_ecology_ticks"] and mask == moisture == light == 0 and opened == -1,
                        "expiry is not a germination check")
                s["expiry_samples"] += 1
                continue
            require(age < s["lifetime_ecology_ticks"] and 0 <= opened <= 28 and
                    bool(mask & 1) == (age < 8) and (mask == 0) == (outcome == 2), "invalid maturity/outcome")
            require(bool(mask & 2) == (moisture < 12) and bool(mask & 4) == (light < 80) and
                    bool(mask & 8) == (slots >= 8) and bool(mask & 16) == (nodes + 4 > 256),
                    "gate disagrees with resource/capacity receipt")
            living = living_before_seed_check(plants, tick, newborns)
            witnesses = [p["id"] for p in living if abs(p["column"] - column) < 3]
            require(len(living) <= slots and (not witnesses or mask & 32),
                    "spacing/slots contradict living plants")
            s["checks"] += 1
            if mask & 1:
                s["dormant_checks"] += 1
            else:
                s["mature_masks"][str(mask)] += 1
                mature_ticks.add(tick)
                if opened and mask:
                    s["open_elsewhere_checks"] += 1
                    open_ticks.add(tick)
                if mask == 32:
                    sole_spacing_ticks.add(tick)
                if mask & 32:
                    s["spacing_with_living_witness" if witnesses else "spacing_without_living_witness"] += 1
                    s["living_witnesses"].update(map(str, witnesses))
                    s["parent_spacing_checks"] += parent in witnesses
                    s["other_spacing_checks"] += any(i != parent for i in witnesses)
            if outcome == 2:
                newborns.add(child)
                germinations.append({"tick": tick, "child": child, "seed": list(key), "column": column})
        require(seen == {k for k, s in selected.items() if s["birth_tick"] < tick <=
                         (s["end_tick"] or result["tick"])}, "incomplete seed inventory")
        require(newborns == {p["id"] for p in plants if p["parent"] and p["birth_tick"] == tick},
                "births differ from seed germinations")
    stats = []
    for key, s in selected.items():
        require(s["samples"] == (min(s["end_tick"] or end, end) - max(s["birth_tick"], start)) // STEP,
                "seed sample coverage differs")
        s.update(masks_summary(s["mature_masks"]))
        s["living_witnesses"] = dict(sorted(s["living_witnesses"].items(), key=lambda x: int(x[0])))
        require(s["samples"] == s["checks"] + s["expiry_samples"] and
                s["checks"] == s["dormant_checks"] + s["mature_checks"], "seed counts do not reconcile")
        stats.append(s)
    hist = Counter()
    for s in stats:
        hist.update(s["mature_masks"])
    fields = ("samples", "checks", "dormant_checks", "expiry_samples", "open_elsewhere_checks",
              "spacing_with_living_witness", "spacing_without_living_witness",
              "parent_spacing_checks", "other_spacing_checks")
    return {"window_ticks": [start, end], "seeds": stats, "germinations": germinations,
            "summary": {**masks_summary(hist), **{k: sum(s[k] for s in stats) for k in fields},
                "seed_count": len(stats), "ecology_samples": len(rows),
                "samples_with_mature_seeds": len(mature_ticks),
                "samples_with_blocked_seed_and_open_elsewhere": len(open_ticks),
                "samples_with_spacing_only_seed": len(sole_spacing_ticks),
                "cohorts": {name: {"seeds": sum(s["cohort"] == name for s in stats),
                    "outcomes_at_window_end": dict(sorted(Counter(s["outcome_at_window_end"] for s in stats
                                                        if s["cohort"] == name).items()))}
                           for name in ("carry_in", "purchased")}}}


def analyze(data, windows):
    worlds = panel(data)
    require(windows["rule"] == WINDOW_RULE and windows["input_sha256"] == INPUT_SHA and
            windows["manifest_sha256"] == MANIFEST_SHA and windows["window_ticks"] == [START, END] and
            windows["sample_step"] == STEP and [w["id"] for w in windows["worlds"]] == [w["id"] for w in worlds],
            "wrong window panel")
    analyzed = []
    for w, excerpt in zip(worlds, windows["worlds"], strict=True):
        require(set(excerpt["arms"]) == set(ARMS), "missing/extra window arm")
        arms = {}
        for arm in ARMS:
            source, trace = w["arms"][arm], excerpt["arms"][arm]
            result = source["result"]
            normalized = previous.common_view(result, arm)
            require(result["tick"] == STOP and result["ledger_start_tick"] == 0 and
                    trace["trace_sha256"] == source["trace_sha256"], "wrong window provenance")
            history = previous.training.score_world(normalized, w["case"], data["models"][w["model"]]["metadata"])
            require(history == source["history"] and
                    source["metrics"] == previous.growth.scoring.metrics(result, source["audit"], history),
                    "saved history/metrics differ")
            period = renewal.audit_period(result, history["blocks"][-1])
            require(history["blocks"][-1]["window_ticks"] == [START, END], "wrong final period")
            checks = seed_window(result, trace["rows"])
            children = []
            for p in source["audit"]["plants"]:
                if not START < p["birth_tick"] <= END:
                    continue
                checked = dict(p)
                recruitment.analyze_child(checked, STOP)
                require(checked == p, "first-day resource audit differs")
                children.append(turnover.child_receipt(p, STOP))
            require({p["id"] for p in children} == {p["child"] for p in checks["germinations"]},
                    "child cohort differs")
            spans = turnover.segments(result, START + STEP, END)
            arms[arm] = {"trace_sha256": trace["trace_sha256"], "unchanged_history": history,
                "unchanged_metrics": source["metrics"], "period": period, "seed_window": checks,
                "birth_cohort": turnover.cohort(children), "children": children,
                "bank": turnover.interval_stats(spans, START + STEP, END + STEP)}
        analyzed.append({k: w[k] for k in ("id", "model", "case")} | {"arms": arms})
    return {"rule": RULE, "input_sha256": INPUT_SHA, "windows_sha256": WINDOWS_SHA,
            "native_runs": 0, "training_runs": 0, "worlds": analyzed,
            "unchanged_comparison": data["comparison"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / INPUT)
    parser.add_argument("--windows", type=Path, default=ROOT / WINDOWS)
    parser.add_argument("--extract-from", type=Path, help="extract from the frozen local bundle, without simulation")
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument("--out", type=Path)
    output.add_argument("--verify", type=Path)
    args = parser.parse_args()
    try:
        require(not args.out or not args.out.exists(), "output already exists")
        data = load(args.input, INPUT_SHA)
        value = extract(args.extract_from, data) if args.extract_from else analyze(data, load(args.windows, WINDOWS_SHA))
        require(digest(args.input) == INPUT_SHA and (args.extract_from or digest(args.windows) == WINDOWS_SHA),
                "input changed during audit")
        if args.verify:
            with gzip.open(args.verify, "rt") as stream:
                require(json.load(stream) == value, "saved germination audit differs")
            print("Verified exact windows against frozen source traces; no simulation." if args.extract_from else
                  "Verified twelve final periods, exact seed checks, first-day outcomes and unchanged renewal scores; no simulation.")
        else:
            previous.founders.write_gzip(args.out, value)
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, StopIteration) as error:
        print("germination audit failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
