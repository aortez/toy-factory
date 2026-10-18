#!/usr/bin/env python3
"""Explain frozen landing-training renewal outcomes without native execution."""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import shutil
import sys

import garden_landing_multiseed as multi
import garden_renewal_stalls as lifetimes
from garden_experiments import digest, source_files, snapshot_sources, write_json
from garden_gallery import artifact
from garden_resources import require

ROOT = Path(__file__).resolve().parents[1]
RULE = "garden-landing-renewal-audit-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-renewal-audit-protocol.md"
INPUT = "landing-multiseed-results.json.gz"
INPUT_SHA = "c68d070a6f6a1859cb88fb90934f68e1928d22d2a79c94ffc9cdece631915bd4"
training, controls = multi.training, multi.controls
rolling = training.rolling
fitness, descendants = rolling.fitness, rolling.descendants
DAY, STEP = rolling.DAY, rolling.STEP
BUCKETS = ("founder", "unconfirmed_descendant", "founder_child", "unconfirmed_parent_child",
           "credit_eligible", "aged_out_eligible")
FUNNEL_FIELDS = ("seeds", "germinated", "expired", "pending", "confirmed", "child_died",
                 "child_unconfirmed", "renewal_eligible", "full_possible_followup")


def load_panel(path):
    require(digest(path) == INPUT_SHA, "wrong frozen input")
    return json.loads(gzip.decompress(path.read_bytes()))


def bucket_at(plant, records, tick):
    if not lifetimes.alive(plant, tick):
        return None
    if not plant["parent"]:
        return "founder"
    if not lifetimes.confirmed(plant, tick):
        return "unconfirmed_descendant"
    parent = records[plant["parent"]]
    if not parent["parent"]:
        return "founder_child"
    if not lifetimes.confirmed(parent, plant["birth_tick"] + DAY):
        return "unconfirmed_parent_child"
    return "credit_eligible" if tick < plant["birth_tick"] + DAY + rolling.CREDIT_AGE else "aged_out_eligible"


def occupancy(plants, start, end):
    """Partition every sampled living-plant tick using exact change boundaries."""
    require(0 <= start < end and start % STEP == end % STEP == 0, "invalid occupancy interval")
    records, rows = {p["id"]: p for p in plants}, []
    for p in sorted(plants, key=lambda p: p["id"]):
        a, z = start + STEP, end + STEP
        due = p["birth_tick"] + DAY
        cuts = sorted({a, z, *(t for t in (p["birth_tick"], p["death_tick"], due, due + rolling.CREDIT_AGE)
                               if t is not None and a < t < z)})
        counts = dict.fromkeys(BUCKETS, 0)
        for left, right in zip(cuts, cuts[1:]):
            bucket = bucket_at(p, records, left)
            if bucket:
                counts[bucket] += right - left
        if sum(counts.values()):
            rows.append({"id": p["id"], "parent": p["parent"], "ticks": counts})
    return {"ticks": {b: sum(p["ticks"][b] for p in rows) for b in BUCKETS}, "plants": rows}


def snapshot(plants, seeds, tick):
    records = {p["id"]: p for p in plants}
    groups = {b: sorted(p["id"] for p in plants if bucket_at(p, records, tick) == b) for b in BUCKETS}
    return {"tick": tick, "living": sum(map(len, groups.values())), "plants": groups,
            "pending_seeds": sorted([s["parent"], s["birth_tick"]] for s in seeds if s["birth_tick"] <= tick and
                                     (s["end_tick"] is None or s["end_tick"] > tick))}


def funnel(rows):
    counts = dict.fromkeys(FUNNEL_FIELDS, 0)
    for r in rows:
        counts["seeds"] += 1
        counts[r["outcome"]] += 1
        if r["child"] is not None:
            field = {"confirmed": "confirmed", "natural-failure": "child_died",
                     "patch-censored": "child_died", "horizon-censored": "child_unconfirmed"}[r["confirmation"]]
            counts[field] += 1
        counts["renewal_eligible"] += r["renewal_eligible"]
        counts["full_possible_followup"] += r["full_possible_followup"]
    require(counts["seeds"] == sum(counts[k] for k in ("germinated", "expired", "pending")) and
            counts["germinated"] == sum(counts[k] for k in ("confirmed", "child_died", "child_unconfirmed")) and
            counts["renewal_eligible"] <= counts["confirmed"], "seed funnel does not reconcile")
    return counts


def seed_cohorts(plants, seeds, start, end, cutoff):
    records = {p["id"]: p for p in plants}
    cohorts = {"carry_in": [], "purchased": []}
    for s in sorted(seeds, key=lambda s: (s["birth_tick"], s["parent"])):
        if s["birth_tick"] > end or (s["end_tick"] is not None and s["end_tick"] <= start):
            continue
        child = records.get(s["child_id"])
        row = {"parent": s["parent"], "purchase_tick": s["birth_tick"], "end_tick": s["end_tick"],
               "outcome": s["outcome"], "child": s["child_id"],
               "parent_class": lifetimes.parent_class(records[s["parent"]], s["birth_tick"]),
               "confirmation": descendants.confirmation(child, child["birth_tick"], cutoff) if child else None,
               "renewal_eligible": bool(child and lifetimes.qualifies(child, records, cutoff)),
               "full_possible_followup": s["birth_tick"] + s.get("lifetime_ecology_ticks", DAY // STEP) * STEP + DAY <= cutoff}
        cohorts["purchased" if s["birth_tick"] > start else "carry_in"].append(row)
    return {key: {"rows": rows, "counts": funnel(rows), "parent_classes": {
        name: funnel([r for r in rows if r["parent_class"] == name]) for name in lifetimes.PARENT_CLASSES}}
        for key, rows in cohorts.items()}


def credit_accounting(block):
    width = block["window_ticks"][1] - block["window_ticks"][0]
    children = block["rolling"]["children"]
    value = {"children": len(children), "count_width_ticks": len(children) * width,
             "timing_excluded_ticks": sum(width - p["available_ticks"] for p in children),
             "death_lost_ticks": sum(p["death_lost_ticks"] for p in children),
             "earned_ticks": block["rolling"]["ticks"]}
    require(value["earned_ticks"] == value["count_width_ticks"] - value["timing_excluded_ticks"] -
            value["death_lost_ticks"], "credit accounting differs")
    return value


def audit_period(result, block):
    start, end = block["window_ticks"]
    cutoff = end + fitness.FOLLOWUP
    plants, seeds = fitness.project(result["lineages"], result["seeds"], start, cutoff, 0, training.STOP)
    records = {p["id"]: p for p in plants}
    population = occupancy(plants, start, end)
    require(population["ticks"]["credit_eligible"] == block["rolling"]["ticks"], "occupancy/credit mismatch")
    cohorts = seed_cohorts(plants, seeds, start, end, cutoff)
    births = [{"id": p["id"], "parent": p["parent"], "tick": p["birth_tick"]} for p in plants
              if p["parent"] and start < p["birth_tick"] <= end]
    germinations = [r for c in cohorts.values() for r in c["rows"] if r["outcome"] == "germinated" and
                   start < r["end_tick"] <= end]
    require({p["id"] for p in births} == {r["child"] for r in germinations}, "carry-in germination mismatch")
    confirmations = [{"id": p["id"], "parent": p["parent"], "tick": p["birth_tick"] + DAY,
                      "renewal_eligible": lifetimes.qualifies(p, records, end)} for p in plants
                     if p["parent"] and start < p["birth_tick"] + DAY <= end and lifetimes.confirmed(p, end)]
    require({r["id"] for r in confirmations if r["renewal_eligible"]} ==
            {r["id"] for r in block["rolling"]["children"] if not r["carry_in"]}, "confirmation/credit mismatch")
    ticks, zero = population["ticks"], block["rolling"]["ticks"] == 0
    established = sum(ticks[b] for b in BUCKETS[2:])
    signatures = {
        "endpoint_established": block["v2_key"][0] == 1,
        "no_purchases": cohorts["purchased"]["counts"]["seeds"] == 0,
        "purchases_no_germinations": cohorts["purchased"]["counts"]["seeds"] > 0 and not births,
        "founder_child_only_established_occupancy": established > 0 and established == ticks["founder_child"],
        "aged_out_eligible_occupancy": ticks["aged_out_eligible"] > 0,
        "no_established_occupancy": established == 0,
    }
    return {"days": block["days"], "terminal": block["terminal"], "terminal_tier": block["v2_key"][0],
            "followup_tick": cutoff, "credit": credit_accounting(block), "occupancy": population,
            "seed_cohorts": cohorts, "births": births, "confirmations": confirmations,
            "zero_credit_signatures": [k for k, value in signatures.items() if zero and value],
            "snapshots": [snapshot(plants, seeds, t) for t in (start, end, cutoff)]}


def summarize(periods):
    return {"world_windows": len(periods), "zero_credit_windows": sum(p["credit"]["earned_ticks"] == 0 for p in periods),
            "zero_signatures": dict(sorted(Counter(s for p in periods for s in p["zero_credit_signatures"]).items())),
            "credit": {k: sum(p["credit"][k] for p in periods) for k in
                       ("children", "count_width_ticks", "timing_excluded_ticks", "death_lost_ticks", "earned_ticks")},
            "occupancy_ticks": {b: sum(p["occupancy"]["ticks"][b] for p in periods) for b in BUCKETS},
            "seed_cohorts": {cohort: {f: sum(p["seed_cohorts"][cohort]["counts"][f] for p in periods)
                                     for f in FUNNEL_FIELDS} for cohort in ("carry_in", "purchased")},
            "births": sum(len(p["births"]) for p in periods),
            "confirmations": sum(len(p["confirmations"]) for p in periods),
            "renewal_confirmations": sum(c["renewal_eligible"] for p in periods for c in p["confirmations"])}


def paired_audit(worlds, pair):
    a, b = (worlds[pair[k]] for k in ("control", "candidate"))
    rows = []
    for case in multi.evaluation_conditions():
        left, right = a[case["id"]]["periods"], b[case["id"]]["periods"]
        i, j = (min(range(4), key=lambda n: periods[n]["credit"]["earned_ticks"]) for periods in (left, right))
        delta = {k: right[j]["credit"][k] - left[i]["credit"][k] for k in left[i]["credit"]}
        require(delta["earned_ticks"] == delta["count_width_ticks"] - delta["timing_excluded_ticks"] -
                delta["death_lost_ticks"], "minimum delta accounting differs")
        rows.append({**case, "control_weakest_days": left[i]["days"], "candidate_weakest_days": right[j]["days"],
                     "same_weakest_window": i == j, "minimum_delta": delta,
                     "matched_window_deltas": [y["credit"]["earned_ticks"] - x["credit"]["earned_ticks"]
                                               for x, y in zip(left, right, strict=True)]})
    summed = {k: sum(r["minimum_delta"][k] for r in rows) for k in rows[0]["minimum_delta"]}
    require(summed["earned_ticks"] == pair["slices"]["all"]["minimum_delta"], "paired minimum score differs")
    return {"kind": pair["kind"], "control": pair["control"], "candidate": pair["candidate"],
            "minimum_delta": summed, "worlds": rows}


def analyze(panel):
    require(panel["rule"] == multi.RULE and panel["objective"] == training.individual.RULE and
            panel["evaluation_conditions"] == multi.evaluation_conditions() and panel["profiles"] == list(multi.PROFILES),
            "wrong evaluation panel contract")
    identities = {"initial-live", "initial-fixed"} | {
        f"{cohort}-s{s:08x}-{p['id']}" for cohort in ("single", "multi")
        for s in training.SEARCH_SEEDS for p in multi.PROFILES}
    require(set(panel["evaluations"]) == identities and len(panel["models"]) == 14 and
            {m["id"] for m in panel["models"]} == identities, "missing/duplicate evaluated model")
    worlds, summaries = {}, {}
    for model in sorted(panel["models"], key=lambda m: m["id"]):
        evaluation = panel["evaluations"][model["id"]]
        require(set(evaluation["worlds"]) == {c["id"] for c in multi.evaluation_conditions()}, "wrong world inventory")
        histories, audited = {}, {}
        for case in multi.evaluation_conditions():
            saved = evaluation["worlds"][case["id"]]
            history = training.score_world(controls.signals.scoring_view(saved["result"], model["profile"]),
                                           case, model["metadata"])
            require(history == saved["history"], "saved score history differs")
            histories[case["id"]] = history
            audited[case["id"]] = {**case, "world_hash": saved["result"]["world_hash"],
                                  "run_hash": saved["result"]["run_hash"],
                                  "periods": [audit_period(saved["result"], b) for b in history["blocks"]]}
        require(evaluation["aggregate"] == training.individual.aggregate(histories, list(histories)), "saved aggregate differs")
        worlds[model["id"]] = audited
        summaries[model["id"]] = {}
        for climate in ("all", "steady", "seasonal"):
            periods = [p for w in audited.values() if climate == "all" or w["climate"] == climate for p in w["periods"]]
            summaries[model["id"]][climate] = {
                "all": summarize(periods), "zero": summarize([p for p in periods if not p["credit"]["earned_ticks"]]),
                "persistent_zero": summarize([p for p in periods if not p["credit"]["earned_ticks"] and p["terminal_tier"] == 1])}
    comparisons = multi.comparisons(panel["evaluations"])
    require(comparisons == panel["comparisons"] and multi.support_gates(comparisons) == panel["support_gates"],
            "saved comparison/gate differs")
    return {"schema_version": 1, "rule": RULE, "source_sha256": INPUT_SHA, "native_calls": 0,
            "histories": 224, "world_windows": 896, "models": panel["models"],
            "conditions": multi.evaluation_conditions(), "summaries": summaries, "worlds": worlds,
            "pairs": [paired_audit(worlds, p) for p in comparisons if p["kind"].startswith("breadth-")]}


def collect(input_path, output):
    require(not output.exists() and (output.is_relative_to(ROOT / "artifacts") or not output.is_relative_to(ROOT)),
            "fresh artifacts/external output required")
    panel = load_panel(input_path)
    before = json.dumps(panel, sort_keys=True)
    sources = source_files()
    output.mkdir(parents=True)
    try:
        shutil.copy2(input_path, output / INPUT)
        shutil.copy2(ROOT / PROTOCOL, output / "protocol.md")
        for path in (ROOT / "sim").glob("*.py"):
            (output / "sim").mkdir(exist_ok=True)
            shutil.copy2(path, output / "sim" / path.name)
        for name in ("framebuffer_capture.py", "serial_shell.py"):
            path = output / "scripts/container" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / "scripts/container" / name, path)
        snapshot_sources(output, sources)
        result = analyze(panel)
        require(json.dumps(panel, sort_keys=True) == before, "analysis mutated input")
        require(result == analyze(load_panel(output / INPUT)), "analysis does not repeat")
        require(sources == source_files() and digest(input_path) == INPUT_SHA and
                digest(output / "protocol.md") == sources[PROTOCOL], "source/input changed during analysis")
        write_json(output / "results.json", result)
        write_json(output / "manifest.json", {"rule": RULE, "status": "complete", "repeat_verified": True,
            "source_sha256_at_collection": sources, "artifacts": {
                str(p.relative_to(output)): digest(p) for p in sorted(output.rglob("*")) if p.is_file()}})
    except BaseException as error:
        (output / "FAILED.txt").write_text(str(error) + "\n")
        raise
    print("Audited 224 histories / 896 windows; zero native calls; exact repeated analysis.")


def verify(output):
    require(not (output / "FAILED.txt").exists(), "incomplete audit")
    manifest = json.loads((output / "manifest.json").read_text())
    require(manifest["rule"] == RULE and manifest["status"] == "complete" and manifest["repeat_verified"], "wrong audit bundle")
    for name in manifest["artifacts"]:
        artifact(output, manifest, name)
    require(digest(output / "protocol.md") == manifest["source_sha256_at_collection"][PROTOCOL], "protocol mismatch")
    expected = json.loads(artifact(output, manifest, "results.json").read_text())
    require(analyze(load_panel(output / INPUT)) == expected, "frozen audit changed")
    for name in manifest["artifacts"]:
        artifact(output, manifest, name)
    print("Verified all 224 histories, 896 windows and six paired credit decompositions.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    try:
        if args.verify:
            require(args.input is None and args.out is None, "verify takes no overrides")
            verify(args.verify.resolve())
        else:
            require(args.out is not None, "analysis requires --out")
            collect((args.input or ROOT / "benchmarks/garden-seasons" / INPUT).resolve(), args.out.resolve())
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print("renewal audit failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
