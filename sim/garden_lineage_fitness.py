#!/usr/bin/env python3
"""Candidate lexicographic lineage fitness; offline reference, not trainer wiring."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import shutil

import garden_descendants as descendants

experiment, require = descendants.experiment, descendants.require
DAY, STEP = descendants.DAY, descendants.STEP
RULE = "garden-lineage-fitness-v1"
BASELINE_SHA = "529c8ce6cda02dd720c1bac7d6d9a5fdfd316e9cdb4ba84707b1c260f3b11ae1"
COMPONENTS = ("terminal_tier", "renewing_parents", "new_establishments", "descendant_live_ticks")


def world(lineages, seeds, start, end):
    """Maximize the returned integer key; a seed-only endpoint has no comparable key."""
    records, _ = descendants.index_records(lineages, seeds, start, end)
    established = {identity for identity, p in records.items()
                   if descendants.confirmation(p, p["birth_tick"], end) == "confirmed"}
    living = [p for p in records.values() if descendants.state_at(p, end) == "alive"]
    pending = sum(s["outcome"] == "pending" for s in seeds)
    alive_descendants = sorted(p["id"] for p in living if p["parent"] and p["id"] in established)
    terminal_tier = 1 if alive_descendants else 0 if living else -1
    unresolved = not living and pending > 0
    events, coverage = [], []
    candidates = Counter()
    for identity, p in sorted(records.items()):
        if not p["parent"]:
            continue
        due = p["birth_tick"] + DAY
        status = descendants.confirmation(p, p["birth_tick"], end)
        if due > start:
            candidates[status] += 1
        if start < due <= end and identity in established:
            parent = records[p["parent"]]
            events.append({"child": identity, "parent": parent["id"], "confirmation_tick": due,
                "parent_is_founder": parent["parent"] == 0,
                "parent_established": parent["id"] in established,
                "parent_state_at_confirmation": descendants.state_at(parent, due)})
        if identity in established:
            first = max(start + STEP, due)
            last = min(end, p["death_tick"] - STEP if p["death_tick"] is not None else end)
            samples = max(0, (last - first) // STEP + 1)
            if samples:
                coverage.append({"id": identity, "first_sample": first, "last_sample": last,
                                 "samples": samples, "live_ticks": samples * STEP})
    renewing = sorted({e["parent"] for e in events if not e["parent_is_founder"] and e["parent_established"]})
    components = {"terminal_tier": None if unresolved else terminal_tier,
                  "renewing_parents": len(renewing), "new_establishments": len(events),
                  "descendant_live_ticks": sum(c["live_ticks"] for c in coverage)}
    deaths = Counter()
    for p in records.values():
        if p["death_tick"] is not None and start < p["death_tick"] <= end:
            deaths["patch" if p.get("environmental_death", False) else "natural"] += 1
    return {"status": "needs-followup" if unresolved else "complete", "components": components,
            "key": None if unresolved else [components[k] for k in COMPONENTS],
            "window": {"start_exclusive": start, "end_inclusive": end},
            "terminal": {"living_founders": sum(not p["parent"] for p in living),
                         "young_descendants": sorted(p["id"] for p in living if p["parent"] and p["id"] not in established),
                         "established_descendants": alive_descendants, "pending_seeds": pending,
                         "observed_extinct": not living and not pending},
            "renewing_parent_ids": renewing, "establishment_events": events, "occupancy": coverage,
            "diagnostics": {"confirmation_cohort_outcomes": dict(candidates), "closing_deaths": dict(deaths),
                            "closing_purchases": sum(s["birth_tick"] > start for s in seeds)}}


def compare(left, right):
    require(left["status"] == right["status"] == "complete" and
            left["key"] is not None and right["key"] is not None, "cannot rank unresolved follow-up")
    require(left["window"] == right["window"], "mismatched scoring windows")
    return (left["key"] > right["key"]) - (left["key"] < right["key"])


def aggregate(cases):
    require(bool(cases), "empty evaluation suite")
    window = next(iter(cases.values()))["window"]
    require(all(c["window"] == window for c in cases.values()), "mixed scoring windows")
    if any(c["status"] != "complete" for c in cases.values()):
        return {"status": "needs-followup", "key": None, "window": window,
                "unresolved": sorted(k for k, c in cases.items() if c["status"] != "complete")}
    keys = [c["key"] for c in cases.values()]
    return {"status": "complete", "window": window, "key": [min(k[0] for k in keys),
            *[sum(k[i] for k in keys) for i in range(len(COMPONENTS))]]}


def paired(left, right):
    require(left.keys() == right.keys() and bool(left), "mismatched suite conditions")
    a, b = aggregate(left), aggregate(right)
    return {"neural": a, "reserve": b, "comparison": compare(a, b)
            if a["status"] == b["status"] == "complete" else None}


def arithmetic_fixtures():
    """Hand-built histories for score semantics, not native reachable trajectories."""
    start, end = 4 * DAY, 8 * DAY
    # (id, parent, birth, death, patch); seed-to-child delay is 120 ticks.
    founder = (1, 0, 0, None, False)
    old = (2, 1, DAY, None, False)
    child = (2, 1, 5 * DAY, None, False)
    grandchild = (3, 2, 6 * DAY, None, False)
    specs = {
        "founder-only": ([founder], []),
        "sterile-seed-producer": ([founder], [5 * DAY, 6 * DAY]),
        "old-sterile-descendant": ([founder, old], []),
        "productive-lineage": ([founder, child, grandchild], []),
        "productive-parent-later-dies": ([founder, (2, 1, 5 * DAY, 7 * DAY + STEP, False), grandchild], []),
        "extinct-reproductive-burst": ([(i, p, b, 7 * DAY + 60, False)
                                         for i, p, b, _, _ in (founder, child, grandchild)], []),
        "descendants-lost-founder-remains": ([founder, (2, 1, 5 * DAY, 7 * DAY + 60, False),
                                               (3, 2, 6 * DAY, 7 * DAY + 60, False)], []),
        "late-seed-burst": ([founder], [end - 30, end - 15]),
        "seed-only-ending": ([(1, 0, 0, end, False)], [end - 15]),
        "endpoint-descendant-death": ([founder, (2, 1, DAY, end, False)], []),
        "steady-offspring": ([founder, old, (3, 2, 5 * DAY, None, False)], []),
        "brief-established-offspring": ([founder, old,
            *[(i, 2, 6 * DAY + i * 60, 7 * DAY + i * 60 + STEP, False) for i in range(3, 7)]], []),
    }
    result = {}
    for name, (plants, extra) in specs.items():
        lineages = [{"id": i, "parent": p, "birth_tick": b, "death_tick": d,
                     "environmental_death": patch, "column": i, "generation": i - 1}
                    for i, p, b, d, patch in plants]
        seeds = [{"parent": p, "birth_tick": b - 120, "child_id": i, "end_tick": b,
                  "column": i, "generation": i - 1, "outcome": "germinated"}
                 for i, p, b, _, _ in plants if p]
        seeds.extend({"parent": 1, "birth_tick": t, "child_id": None,
                      "end_tick": t + DAY if t + DAY <= end else None, "column": 1,
                      "generation": 1, "outcome": "expired" if t + DAY <= end else "pending"} for t in extra)
        for p in lineages:
            p["seeds_created"] = sum(s["parent"] == p["id"] for s in seeds)
            p["late_seeds_created"] = sum(s["parent"] == p["id"] and s["birth_tick"] > start for s in seeds)
        result[name] = {"kind": "synthetic-arithmetic-not-native", "lineages": lineages, "seeds": seeds,
                        "evaluation": world(lineages, seeds, start, end)}
    return result


def evaluate(baseline, roots):
    require(experiment.digest(baseline / "manifest.json") == BASELINE_SHA, "wrong frozen descendant bundle")
    m = experiment.read_json(baseline / "manifest.json")
    require(m["rule"] == descendants.RULE and m["status"] == "complete", "incomplete descendant baseline")
    for name in m["artifacts"]:
        descendants.recruitment.establishment.verified(baseline, m, name)
    prior = descendants.evaluate(roots)
    require(prior == experiment.read_json(baseline / "results.json"), "descendant baseline reproduction differs")
    cases, suites = [], defaultdict(dict)
    for c in prior["cases"]:
        saved = experiment.read_json(roots["recruitment"] / f"analyses/{c['key']}.json")
        score = world(saved["world"]["lineages"], saved["seeds"]["seeds"], descendants.START, descendants.END)
        condition = f"{c['capacity']}.{c['seed']}.{c['schedule']}"
        require(condition not in suites[c["policy"]], "duplicate condition")
        suites[c["policy"]][condition] = score
        cases.append({"case": c["key"], "condition": condition, "policy": c["policy"],
                      "evaluation": score, "original_seed_creation_funnel": c["all"]["counts"],
                      "final_hash": c["final_hash"]})
        print("Lineage score", c["key"], score["key"], flush=True)
    require(set(suites) == {"neural", "reserve"} and len(suites["neural"]) == 4, "wrong fixed panel")
    left, right = suites["neural"], suites["reserve"]
    result = {"rule": RULE, "role": "candidate-fitness-offline-not-adopted", "baseline_manifest_sha256": BASELINE_SHA,
        "native_runs": 0, "training_runs": 0, "components": COMPONENTS,
        "aggregate_components": ("minimum_terminal_tier", *COMPONENTS),
        "cases": cases, "paired": {k: paired({k: left[k]}, {k: right[k]}) for k in sorted(left)},
        "aggregate": paired(left, right), "leave_one_out": {k: paired(
            {j: v for j, v in left.items() if j != k}, {j: v for j, v in right.items() if j != k}) for k in sorted(left)},
        "fixtures": arithmetic_fixtures(), "checks": prior["checks"]}
    # Store JSON-shaped sequences so verification compares the same representation.
    result["components"] = list(result["components"])
    result["aggregate_components"] = list(result["aggregate_components"])
    require(experiment.digest(baseline / "manifest.json") == BASELINE_SHA, "baseline changed during analysis")
    return result


def collect(baseline, roots, output):
    require(output.is_relative_to(experiment.ROOT / "artifacts") and not output.exists() and
            all(not output.is_relative_to(r) for r in [baseline, *roots.values()]), "choose new artifacts output")
    sources = experiment.source_files()
    output.mkdir(parents=True)
    experiment.snapshot_sources(output, sources)
    shutil.copy2(experiment.ROOT / "benchmarks/garden-longevity/lineage-fitness-protocol.md", output / "protocol.md")
    started = {"rule": RULE, "baseline_manifest_sha256": BASELINE_SHA,
               "input_manifests": descendants.INPUTS, "source_sha256": sources}
    experiment.write_json(output / "started.json", started)
    try:
        result = evaluate(baseline, roots)
        experiment.write_json(output / "results.json", result)
        require(experiment.source_files() == sources, "source changed during analysis")
        experiment.write_json(output / "manifest.json", started | {"status": "complete", "artifacts": {
            str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}})
    except BaseException as error:
        experiment.write_json(output / "failure.json", {"error": str(error)})
        raise


def verify(baseline, roots, output, export=None):
    m = experiment.read_json(output / "manifest.json")
    require(m["rule"] == RULE and m["status"] == "complete" and m["baseline_manifest_sha256"] == BASELINE_SHA and
            m["input_manifests"] == descendants.INPUTS, "wrong/incomplete fitness bundle")
    for name in m["artifacts"]:
        descendants.recruitment.establishment.verified(output, m, name)
    result = evaluate(baseline, roots)
    require(result == experiment.read_json(output / "results.json"), "lineage fitness reanalysis differs")
    if export is not None:
        experiment.write_json(export, result | {"manifest_sha256": experiment.digest(output / "manifest.json")})
    print("Verified candidate fitness, paired/aggregate rankings and arithmetic challenges; no training")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path)
    group.add_argument("--verify", type=Path)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT / "artifacts/garden-descendant-outcomes-v1")
    parser.add_argument("--recruitment", type=Path, default=experiment.ROOT / "artifacts/garden-crowded-recruitment")
    parser.add_argument("--attempts", type=Path, default=experiment.ROOT / "artifacts/garden-seed-attempts")
    parser.add_argument("--export", type=Path)
    args = parser.parse_args()
    require(args.export is None or args.verify is not None, "export requires verification")
    roots = {name: getattr(args, name).resolve() for name in descendants.INPUTS}
    if args.verify:
        verify(args.baseline.resolve(), roots, args.verify.resolve(), args.export)
    else:
        collect(args.baseline.resolve(), roots, args.output.resolve())


if __name__ == "__main__":
    main()
