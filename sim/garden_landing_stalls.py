#!/usr/bin/env python3
"""Offline refusal-streak diagnosis; no native runs or policy changes."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path
import statistics
import sys

import garden_landing_water as previous
from garden_experiments import digest
from garden_resources import require

ROOT, DAY, STEP, STOP = previous.ROOT, previous.DAY, previous.STEP, previous.STOP
RULE = "garden-landing-stalls-v1"
INPUT = "benchmarks/garden-seasons/landing-water-results.json.gz"
INPUT_SHA = "9f93b8047cfa6468bb7053d06f11b10dbe459e02fb36d37f1616c1ba56200e9c"


def load(path):
    require(digest(path) == INPUT_SHA, "wrong frozen water panel")
    return json.loads(gzip.decompress(path.read_bytes()))


def consecutive(ticks):
    """Maximal consecutive ecology samples, never bridge an unobserved step."""
    groups = []
    for tick in ticks:
        require(type(tick) is int and tick > 0 and tick % STEP == 0 and
                (not groups or tick > groups[-1][-1]), "unordered/duplicate/unaligned event")
        if not groups or tick != groups[-1][-1] + STEP:
            groups.append([])
        groups[-1].append(tick)
    return groups


def distribution(values):
    return {"count": len(values), "minimum": min(values, default=None),
            "median": statistics.median(values) if values else None, "maximum": max(values, default=None)}


def histogram(values):
    return {str(k): v for k, v in sorted(Counter(values).items())}


def conflict(winner):
    # In control these proposals execute; in treatment they become WAIT.
    return not winner["allowed"] and winner["funded_wet_root_bids"] > 0


def validate_receipts(arm, enabled):
    """Recheck saved winners against their pre-growth body and actual spending."""
    previous.common_view(arm["result"], enabled)
    plants = {p["id"]: p for p in arm["audit"]["plants"]}
    require(len(plants) == len(arm["audit"]["plants"]), "duplicate plant")
    samples = {}
    for p in plants.values():
        require(p["parent"] != 0 and p["generation"] > 0, "not a descendant")
        roots = 2
        for row in p["rows"]:
            samples[row["tick"], p["id"]] = row, roots
            roots = row["roots"]
    seen, by_id, last_tick = set(), defaultdict(list), 0
    for saved in arm["water_audit"]["winners"]:
        tick = saved["tick"]
        w = {k: v for k, v in saved.items() if k != "tick"}
        previous.check_winner(w, enabled)
        key = tick, w["id"]
        require(type(tick) is int and tick >= last_tick and tick % STEP == 0 and key in samples and
                key not in seen, "missing/duplicate/reordered winner")
        last_tick = tick
        seen.add(key)
        p, (row, roots) = plants[w["id"]], samples[key]
        pre, post = row["stages"][2:4]
        require((p["death_tick"] is None or p["death_tick"] > tick) and
                w["age"] == (tick - p["birth_tick"]) // STEP + 1 and w["species"] == p["species"] and
                (w["water"], w["nodes"], w["roots"]) == (pre[1], pre[4], roots), "winner body differs")
        add = int(w["result_action"] == 1 and w["destination"] is not None)
        require(pre[1] - post[1] == (w["cost"] if w["result_action"] else 0) and
                post[4] - pre[4] == add and row["roots"] - roots == (add if w["tissue"] == 1 else 0),
                "winner spending/morphology differs")
        by_id[w["id"]].append(saved)
    for (tick, ident), (row, _) in samples.items():
        if (tick - plants[ident]["birth_tick"]) // STEP < 256 and row["stages"][2][1] > row["stages"][3][1]:
            require((tick, ident) in seen, "paid first-day growth lacks receipt")
    all_winners = arm["water_audit"]["winners"]
    late_winners = [w for w in all_winners if 62 * DAY < plants[w["id"]]["birth_tick"] <= 190 * DAY]
    require(arm["water_audit"]["all"] == previous.winner_summary(all_winners) and
            arm["water_audit"]["late"] == previous.winner_summary(late_winners), "winner summary differs")
    return by_id


def next_sample(tick, birth, rows, winners):
    row, winner = rows.get(tick), winners.get(tick)
    if row is None:
        return {"tick": tick, "classification": "followup_ended", "winner": None}
    if row["stages"][4][3] & 1:
        kind = "died"
    elif (tick - birth) // STEP + 1 > 256:
        kind = "guard_ended"
    elif winner is None:
        kind = "no_recorded_winner"
    elif winner["applied"]:
        kind = "wait_with_root" if conflict(winner) else "wait_without_funded_root"
    elif winner["result_action"] == 1 and winner["destination"] is not None:
        kind = "root_growth" if winner["tissue"] == 1 else "shoot_growth"
    else:
        kind = "policy_wait" if winner["result_action"] == 0 else "paid_no_new_node"
    return {"tick": tick, "classification": kind, "winner": winner,
            "pre_growth": row["stages"][2], "post_step": row["stages"][4], "roots": row["roots"]}


def summarize_child(plant, winners, stop):
    allocation = previous.establishment.summarize_child(plant, stop)
    birth = plant["birth_tick"]
    rows = {r["tick"]: r for r in plant["rows"]}
    by_tick = {w["tick"]: w for w in winners}
    require(len(by_tick) == len(winners) and all(w["id"] == plant["id"] for w in winners), "wrong child winners")
    ticks = [w["tick"] for w in winners if conflict(w)]
    streaks = []
    for group in consecutive(ticks):
        start, end = group[0], group[-1]
        subsequent_root = next((t for t in allocation["root_growth_ticks"] if t > end), None)
        subsequent_growth = next((g for g in allocation["growth"] if g["tick"] > end), None)
        following = next_sample(end + STEP, birth, rows, by_tick)
        require(following["classification"] != "wait_with_root", "nonmaximal conflict streak")
        # Only observed first-day continuation is described. No outcome is
        # assigned to a hypothetical losing root proposal or to an unlogged bid.
        streaks.append({"first_tick": start, "last_tick": end, "samples": len(group),
            "span_ticks": end - start, "first_age": (start - birth) // STEP + 1,
            "last_age": (end - birth) // STEP + 1,
            "first_winner": by_tick[start], "last_winner": by_tick[end],
            "next_sample": following, "next_root_tick": subsequent_root,
            "next_root_delay_ticks": subsequent_root - end if subsequent_root is not None else None,
            "next_growth": {k: subsequent_growth[k] for k in ("tick", "kind", "cost")} if subsequent_growth else None})
    first = ticks[0] if ticks else None
    next_root = next((t for t in allocation["root_growth_ticks"] if first is not None and t > first), None)
    timing = {}
    for resource, shortage in allocation["first_shortage"].items():
        timing[resource] = ("no_conflict" if first is None else "no_shortage" if shortage is None else
                            "before" if first < shortage["tick"] else "same" if first == shortage["tick"] else "after")
    return {k: plant[k] for k in ("id", "parent", "species", "generation", "birth_tick", "death_tick", "outcome", "death_shortage")} | {
        "first_day_end_tick": plant["rows"][-1]["tick"], "winner_count": len(winners),
        "applied_waits": sum(w["applied"] for w in winners),
        "wait_streak_samples": [len(g) for g in consecutive([w["tick"] for w in winners if w["applied"]])],
        "conflict_samples": len(ticks), "streaks": streaks,
        "conflict_water_histogram": histogram(by_tick[t]["water"] for t in ticks),
        "initial_root_conflict_samples": sum(by_tick[t]["roots"] == 2 for t in ticks),
        "first_conflict_tick": first, "first_conflict_age": (first - birth) // STEP + 1 if first is not None else None,
        "first_root_tick": allocation["first_root_tick"],
        "root_expanded_before_conflict": (allocation["first_root_tick"] is not None and
            allocation["first_root_tick"] < first) if first is not None else None,
        "root_after_first_conflict_tick": next_root,
        "root_delay_ticks": next_root - first if next_root is not None else None,
        "first_shortage": allocation["first_shortage"], "conflict_shortage_timing": timing,
        "resource_totals": allocation["resources"]}


def aggregate(children):
    streaks = [s for p in children for s in p["streaks"]]
    affected = [p for p in children if p["conflict_samples"]]
    return {"children": len(children), "outcomes": histogram(p["outcome"] for p in children),
        "death_shortages": histogram(p["death_shortage"] for p in children if p["outcome"] == "died"),
        "affected_children": len(affected), "conflict_samples": sum(p["conflict_samples"] for p in children),
        "applied_waits": sum(p["applied_waits"] for p in children),
        "wait_streak_samples": distribution([n for p in children for n in p["wait_streak_samples"]]),
        "streaks": len(streaks), "streak_sample_distribution": distribution([s["samples"] for s in streaks]),
        "streak_sample_histogram": histogram(s["samples"] for s in streaks),
        "next_sample_classes": histogram(s["next_sample"]["classification"] for s in streaks),
        "streaks_with_later_root": sum(s["next_root_tick"] is not None for s in streaks),
        "first_conflict_age": distribution([p["first_conflict_age"] for p in affected]),
        "samples_per_affected_child": distribution([p["conflict_samples"] for p in affected]),
        "children_with_root_after_conflict": sum(p["root_after_first_conflict_tick"] is not None for p in affected),
        "root_delay_ticks_conditional_on_observed_root": distribution([p["root_delay_ticks"] for p in affected if p["root_delay_ticks"] is not None]),
        "root_expanded_before_conflict": sum(p["root_expanded_before_conflict"] is True for p in affected),
        "children_never_expanding_roots_in_first_day": sum(p["first_root_tick"] is None for p in children),
        "initial_root_conflict_samples": sum(p["initial_root_conflict_samples"] for p in children),
        "conflict_shortage_timing": {r: histogram(p["conflict_shortage_timing"][r] for p in affected) for r in ("energy", "water")},
        "conflict_water_histogram": dict(sorted(sum((Counter(p["conflict_water_histogram"]) for p in children), Counter()).items())),
        "resource_totals": {r: {f: sum(p["resource_totals"][r][f] for p in children) for f in previous.prior.RESOURCE_FIELDS}
                            for r in ("energy", "water")}}


def summarize_groups(children):
    return {"all": aggregate(children),
        "with_conflict": aggregate([p for p in children if p["conflict_samples"]]),
        "without_conflict": aggregate([p for p in children if not p["conflict_samples"]]),
        "affected_outcomes": {f: aggregate([p for p in children if p["conflict_samples"] and
            (p["outcome"] == "confirmed" if f == "survived" else p["death_shortage"] == f)])
            for f in ("survived", "water", "energy", "energy+water")}}


def analyze(data):
    require(data["rule"] == previous.RULE and data["objective"] == previous.training.individual.RULE and
            data["arms"] == previous.ARMS and data["inputs"] == previous.INPUTS and
            len(data["worlds"]) == 12 and len({w["id"] for w in data["worlds"]}) == 12 and
            [{k: w[k] for k in ("id", "model", "case")} for w in data["worlds"]] == data["plan"], "wrong frozen panel contract")
    worlds = []
    for w in data["worlds"]:
        arms = {}
        for arm, enabled in previous.ARMS.items():
            source = w["arms"][arm]
            require(source["result"]["tick"] == STOP and source["result"]["ledger_start_tick"] == 0, "partial replay")
            history = previous.training.rolling.history(source["result"]["lineages"], source["result"]["seeds"], 0, STOP)
            require(history == source["history"] and source["metrics"] == previous.previous.metrics(source["result"], source["audit"], history),
                    "saved score/metrics differ")
            winners = validate_receipts(source, enabled)
            late = [p for p in source["audit"]["plants"] if 62 * DAY < p["birth_tick"] <= 190 * DAY]
            require([previous.establishment.summarize_child(p, STOP) for p in late] == source["late_children"], "saved allocation differs")
            children = [summarize_child(p, winners[p["id"]], STOP) for p in late]
            require(all(p["outcome"] != "pending" for p in children), "late follow-up censored")
            summary = summarize_groups(children)
            require(summary["all"]["resource_totals"] == source["audit"]["summary"]["late_children"]["resources"], "cohort resource budget differs")
            arms[arm] = {"children": children, "summary": summary, "unchanged_history": history,
                         "trace_sha256": source["trace_sha256"], "water_trace_sha256": source["water_trace_sha256"]}
        worlds.append({k: w[k] for k in ("id", "case", "model")} | {"arms": arms})
    require(previous.compare(data["worlds"]) == data["comparison"], "original comparison differs")
    groups = {c: {a: summarize_groups([p for w in worlds if c == "all" or w["case"]["climate"] == c
                                     for p in w["arms"][a]["children"]]) for a in previous.ARMS}
              for c in ("all", "steady", "seasonal")}
    return {"rule": RULE, "input": INPUT, "input_sha256": INPUT_SHA,
            "cohort": {"birth_after": 62 * DAY, "birth_through": 190 * DAY, "followup_ticks": DAY},
            "streak_cadence_ticks": STEP, "worlds": worlds, "groups": groups,
            "unchanged_comparison": data["comparison"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / INPUT)
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument("--out", type=Path)
    output.add_argument("--verify", type=Path)
    args = parser.parse_args()
    try:
        result = analyze(load(args.input))
        require(digest(args.input) == INPUT_SHA, "input changed during diagnosis")
        if args.verify:
            raw = args.verify.read_bytes()
            require(json.loads(gzip.decompress(raw) if args.verify.suffix == ".gz" else raw) == result, "saved diagnosis differs")
            print("Verified all 262 late children, refusal streaks, observed continuations, resource budgets and unchanged scores.")
        else:
            raw = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode()
            with args.out.open("xb") as stream:
                if args.out.suffix == ".gz":
                    with gzip.GzipFile(filename="", fileobj=stream, mode="wb", mtime=0) as zipped:
                        zipped.write(raw)
                else:
                    stream.write(raw)
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
        print("streak diagnosis failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
