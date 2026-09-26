#!/usr/bin/env python3
"""Offline persistence-first lineage candidate with fixed terminal follow-up."""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import shutil

import garden_lineage_fitness as v1

experiment, require, descendants = v1.experiment, v1.require, v1.descendants
DAY, STEP = v1.DAY, v1.STEP
RULE = "garden-lineage-persistence-v2"
BASELINE_SHA = "3229d3962af2298a303a9b68cfe43a390112a185c3edad7a5091f1fd64fcb3e8"
START, END, FOLLOWUP = 158 * DAY, 190 * DAY, 2 * DAY
COMPONENTS = ("terminal_tier", "renewing_child_live_ticks", "descendant_live_ticks",
              "renewing_parents", "new_establishments")


def _project(lineages, seeds, start, end):
    """Project already validated lifetimes, not a native world snapshot."""
    plants = [dict(p) for p in lineages if p["birth_tick"] <= end]
    selected = [dict(s) for s in seeds if s["birth_tick"] <= end]
    for p in plants:
        if p["death_tick"] is not None and p["death_tick"] > end:
            p.update(death_tick=None, environmental_death=False)
    for s in selected:
        if s["end_tick"] is not None and s["end_tick"] > end:
            s.update(end_tick=None, child_id=None, outcome="pending")
    counts = Counter(s["parent"] for s in selected)
    closing = Counter(s["parent"] for s in selected if s["birth_tick"] > start)
    for p in plants:
        p.update(seeds_created=counts[p["id"]], late_seeds_created=closing[p["id"]])
    descendants.index_records(plants, selected, start, end)
    return plants, selected


def project(lineages, seeds, start, end, source_start, observed_end):
    require(0 <= start < end <= observed_end, "invalid projection clocks")
    descendants.index_records(lineages, seeds, source_start, observed_end)
    return _project(lineages, seeds, start, end)


def world(lineages, seeds, start, end, observed_end, source_start=None):
    """Require two days of common follow-up; incomplete input is never ranked."""
    require(end <= observed_end <= end + FOLLOWUP, "wrong follow-up observation horizon")
    source_start = start if source_start is None else source_start
    records, indexed = descendants.index_records(lineages, seeds, source_start, observed_end)
    plants, main_seeds = project(lineages, seeds, start, end, source_start, observed_end)
    main = v1.world(plants, main_seeds, start, end)
    renewing_children = {e["child"] for e in main["establishment_events"]
                         if not e["parent_is_founder"] and e["parent_established"]}
    credited = [c for c in main["occupancy"] if c["id"] in renewing_children]
    living = [p for p in records.values() if descendants.state_at(p, observed_end) == "alive"]
    established = sorted(p["id"] for p in living if p["parent"] and
                         descendants.confirmation(p, p["birth_tick"], observed_end) == "confirmed")
    pending = sum(s["outcome"] == "pending" for s in seeds)
    tier = 1 if established else 0 if living or pending else -1
    terminal = {"classification": "established-present" if established else
                "living-unestablished" if living else "seed-only-unconfirmed" if pending else "observed-extinct",
                "living_founders": sum(not p["parent"] for p in living),
                "young_descendants": sorted(p["id"] for p in living if p["parent"] and p["id"] not in established),
                "established_descendants": established, "pending_seeds": pending}
    followup = []
    for seed in sorted(main_seeds, key=lambda s: (s["parent"], s["birth_tick"])):
        if seed["outcome"] != "pending":
            continue
        s = indexed[seed["parent"], seed["birth_tick"]]
        # The fixed two-day scoring follow-up is not a seed-expiry deadline.
        # Longer-lived seeds remain explicitly unconfirmed, including at stop.
        require(observed_end < s["birth_tick"] + s.get("lifetime_ecology_ticks", DAY // STEP) * STEP
                or s["outcome"] != "pending",
                "original seed unresolved after maximum lifetime")
        child = records.get(s["child_id"])
        followup.append({"parent": s["parent"], "purchase_tick": s["birth_tick"],
            "outcome": s["outcome"], "end_tick": s["end_tick"], "child": s["child_id"],
            "child_confirmation": descendants.confirmation(child, child["birth_tick"], observed_end) if child else None,
            "child_terminal": descendants.state_at(child, observed_end) if child else None})
    complete = observed_end == end + FOLLOWUP
    components = {"terminal_tier": tier if complete else None,
                  "renewing_child_live_ticks": sum(c["live_ticks"] for c in credited),
                  **{k: main["components"][k] for k in COMPONENTS[2:]}}
    return {"rule": RULE, "status": "complete" if complete else "needs-followup",
            "window": main["window"], "followup_deadline": end + FOLLOWUP,
            "observed_end": observed_end, "components": components,
            "key": [components[k] for k in COMPONENTS] if complete else None,
            "main_v1": main, "terminal": terminal, "renewing_child_occupancy": credited,
            "pending_seed_followup": followup}


def compare(left, right):
    require(left["status"] == right["status"] == "complete" and
            left["key"] is not None and right["key"] is not None, "cannot rank incomplete follow-up")
    require(all(left[k] == right[k] for k in ("rule", "window", "followup_deadline")),
            "mismatched scoring contract")
    return (left["key"] > right["key"]) - (left["key"] < right["key"])


def aggregate(cases):
    require(bool(cases), "empty evaluation suite")
    first = next(iter(cases.values()))
    contract = {k: first[k] for k in ("rule", "window", "followup_deadline")}
    require(contract["rule"] == RULE and
            all(all(c[k] == v for k, v in contract.items()) for c in cases.values()), "mixed scoring contracts")
    if any(c["status"] != "complete" for c in cases.values()):
        return contract | {"status": "needs-followup", "key": None,
                           "unresolved": sorted(k for k, c in cases.items() if c["status"] != "complete")}
    keys = [c["key"] for c in cases.values()]
    return contract | {"status": "complete", "key": [min(k[0] for k in keys),
        *[sum(k[i] for k in keys) for i in range(len(COMPONENTS))]]}


def paired(left, right):
    require(left.keys() == right.keys() and bool(left), "mismatched suite conditions")
    a, b = aggregate(left), aggregate(right)
    return {"neural": a, "reserve": b, "comparison": compare(a, b)
            if a["status"] == b["status"] == "complete" else None}


def panel(cases, pairing):
    left, right = cases["neural"], cases["reserve"]
    require(left.keys() == right.keys() and len(left) == 4, "wrong fixed panel")
    return {"aggregate": pairing(left, right),
            "paired": {k: pairing({k: left[k]}, {k: right[k]}) for k in sorted(left)},
            "leave_one_out": {k: pairing({j: v for j, v in left.items() if j != k},
                                         {j: v for j, v in right.items() if j != k}) for k in sorted(left)}}


def fixture(plants, extra=(), start=4 * DAY, end=8 * DAY):
    """Synthetic full histories: plant tuples (id, parent, birth, death, patch)."""
    stop = end + FOLLOWUP
    lineages = [{"id": i, "parent": p, "birth_tick": b, "death_tick": d,
                 "environmental_death": patch, "column": i, "generation": i - 1}
                for i, p, b, d, patch in plants]
    seeds = [{"parent": p, "birth_tick": b - 120, "child_id": i, "end_tick": b,
              "column": i, "generation": i - 1, "outcome": "germinated"}
             for i, p, b, _, _ in plants if p]
    seeds.extend({"parent": parent, "birth_tick": tick, "child_id": None,
                  "end_tick": tick + DAY if tick + DAY <= stop else None,
                  "column": parent, "generation": parent, "outcome": "expired" if tick + DAY <= stop else "pending"}
                 for parent, tick in extra)
    for p in lineages:
        p["seeds_created"] = sum(s["parent"] == p["id"] for s in seeds)
        p["late_seeds_created"] = sum(s["parent"] == p["id"] and s["birth_tick"] > start for s in seeds)
    return {"kind": "synthetic-arithmetic-not-native", "lineages": lineages, "seeds": seeds,
            "evaluation": world(lineages, seeds, start, end, stop)}


def arithmetic_fixtures():
    result = {}
    for name, old in v1.arithmetic_fixtures().items():
        plants = [(p["id"], p["parent"], p["birth_tick"], p["death_tick"], p["environmental_death"])
                  for p in old["lineages"]]
        extra = [(s["parent"], s["birth_tick"]) for s in old["seeds"] if s["child_id"] is None]
        f = fixture(plants, extra)
        require(f["evaluation"]["main_v1"] == old["evaluation"], "synthetic continuation changed original prefix")
        result[name] = f
    founder = (1, 0, 0, None, False)
    parents = [(i, 1, DAY + i * 120, None, False) for i in range(2, 6)]
    result["brief-multiple-renewing-parents"] = fixture([founder, *parents,
        *[(i + 4, i, 6 * DAY + i * 60, 7 * DAY + i * 60 + STEP, False) for i in range(2, 6)]])
    for name, death, patch in (("recovered", None, False),
                               ("natural-failure", 9 * DAY + 90, False),
                               ("patch-censored", 9 * DAY + 90, True),
                               ("later-collapse", 9 * DAY + 120, False)):
        result["seed-only-" + name] = fixture([(1, 0, 0, 8 * DAY, False),
            (2, 1, 8 * DAY + 90, death, patch)])
    # A newly born plant can reproduce and die before its own first day. This
    # deliberately leaves a new seed, not the original seed, pending at deadline.
    result["seed-only-new-generation-unconfirmed"] = fixture([
        (1, 0, 0, 8 * DAY, False), (2, 1, 8 * DAY + 90, 9 * DAY, False),
        (3, 2, 9 * DAY + 90, 10 * DAY, False)], [(3, 10 * DAY - STEP)])
    return result


def evaluate(baseline, descendant_baseline, roots):
    require(experiment.digest(baseline / "manifest.json") == BASELINE_SHA, "wrong frozen v1 bundle")
    manifest = experiment.read_json(baseline / "manifest.json")
    require(manifest["rule"] == v1.RULE and manifest["status"] == "complete", "invalid v1 bundle")
    for name in manifest["artifacts"]:
        descendants.recruitment.establishment.verified(baseline, manifest, name)
    previous = v1.evaluate(descendant_baseline, roots)
    require(previous == experiment.read_json(baseline / "results.json"), "original v1 reproduction differs")
    cases, controls, revised = [], {"neural": {}, "reserve": {}}, {"neural": {}, "reserve": {}}
    for old in previous["cases"]:
        saved = experiment.read_json(roots["recruitment"] / f"analyses/{old['case']}.json")
        score = world(saved["world"]["lineages"], saved["seeds"]["seeds"], START, END,
                      END + FOLLOWUP, source_start=descendants.START)
        policy, condition = old["policy"], old["condition"]
        require(condition not in controls[policy], "duplicate condition")
        controls[policy][condition], revised[policy][condition] = score["main_v1"], score
        cases.append({"case": old["case"], "condition": condition, "policy": policy,
                      "original_v1": old["evaluation"]["key"], "evaluation": score,
                      "final_hash": old["final_hash"]})
        print("Persistence score", old["case"], "matched v1", score["main_v1"]["key"], "v2", score["key"], flush=True)
    require(experiment.digest(baseline / "manifest.json") == BASELINE_SHA, "v1 changed during analysis")
    return {"rule": RULE, "role": "candidate-fitness-offline-not-adopted", "baseline_manifest_sha256": BASELINE_SHA,
            "native_runs": 0, "training_runs": 0, "components": list(COMPONENTS),
            "aggregate_components": ["minimum_terminal_tier", *COMPONENTS], "cases": cases,
            "matched_v1": panel(controls, v1.paired), "v2": panel(revised, paired),
            "fixtures": arithmetic_fixtures(), "checks": previous["checks"]}


def run(baseline, descendant_baseline, roots, output, verify=False, export=None):
    identity = {"rule": RULE, "baseline_manifest_sha256": BASELINE_SHA, "input_manifests": descendants.INPUTS}
    if verify:
        manifest = experiment.read_json(output / "manifest.json")
        require(manifest["status"] == "complete" and all(manifest[k] == v for k, v in identity.items()),
                "wrong/incomplete persistence bundle")
        for name in manifest["artifacts"]:
            descendants.recruitment.establishment.verified(output, manifest, name)
    else:
        require(output.is_relative_to(experiment.ROOT / "artifacts") and not output.exists() and
                all(not output.is_relative_to(r) for r in [baseline, descendant_baseline, *roots.values()]),
                "choose new artifacts output")
        sources = experiment.source_files()
        output.mkdir(parents=True)
        experiment.snapshot_sources(output, sources)
        shutil.copy2(experiment.ROOT / "benchmarks/garden-longevity/lineage-persistence-protocol.md", output / "protocol.md")
        experiment.write_json(output / "started.json", identity | {"source_sha256": sources})
    try:
        result = evaluate(baseline, descendant_baseline, roots)
        if verify:
            require(result == experiment.read_json(output / "results.json"), "persistence reanalysis differs")
            if export is not None:
                experiment.write_json(export, result | {"manifest_sha256": experiment.digest(output / "manifest.json")})
            print("Verified persistence scores, fixed follow-up and matched v1 controls; no training")
        else:
            experiment.write_json(output / "results.json", result)
            require(experiment.source_files() == sources, "source changed during analysis")
            experiment.write_json(output / "manifest.json", identity | {"source_sha256": sources, "status": "complete",
                "artifacts": {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}})
    except BaseException as error:
        if not verify:
            experiment.write_json(output / "failure.json", {"error": str(error)})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path)
    group.add_argument("--verify", type=Path)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT / "artifacts/garden-lineage-fitness-v1")
    parser.add_argument("--descendant-baseline", type=Path, default=experiment.ROOT / "artifacts/garden-descendant-outcomes-v1")
    parser.add_argument("--recruitment", type=Path, default=experiment.ROOT / "artifacts/garden-crowded-recruitment")
    parser.add_argument("--attempts", type=Path, default=experiment.ROOT / "artifacts/garden-seed-attempts")
    parser.add_argument("--export", type=Path)
    args = parser.parse_args()
    require(args.export is None or args.verify is not None, "export requires verification")
    run(args.baseline.resolve(), args.descendant_baseline.resolve(),
        {name: getattr(args, name).resolve() for name in descendants.INPUTS},
        (args.verify or args.output).resolve(), bool(args.verify), args.export)


if __name__ == "__main__":
    main()
