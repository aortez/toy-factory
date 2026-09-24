#!/usr/bin/env python3
"""Saved-trace seed outcomes and conservative spacing witnesses for two rescues."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

import garden_renewal_capacity_guard as parent
import garden_renewal_recruitment as ledger

experiment, panel, require = parent.experiment, parent.panel, parent.require
STEP, STOP, LATE = ledger.STEP, panel.STOP, panel.LATE
RULE = "garden-renewal-rescued-seeds-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-rescued-seeds-protocol.md"
BASELINE_SHA = "f8e7237a0db166e15fe802c12e78b5a0f76b539fd853888d7fbc2efdc7a33d2f"
PORTABLE = "benchmarks/garden-longevity/renewal-capacity-guard-summary.json"
PORTABLE_SHA = "25a11c7b3033aaecdc6f6f5e388953ebe551be2d1072a6c5edf715231052a03e"
CASES = parent.CASES[:2]
WINDOWS = ("whole", "since_refusal", "late")
SCALARS = ("samples", "stable_spacing", "stable_plant_capacity", "stable_structural_blocker",
           "newborn_spacing_only", "self_spacing", "dead_spacing", "founder_spacing")


def dispersal_support(column, trait):
    """Unchanged wide-v1 placement support, not landing probabilities."""
    require(type(column) is int and 0 <= column < 28 and type(trait) is int and -2 <= trait <= 2,
            "invalid dispersal inputs")
    columns = set()
    for distance in range(3+trait,10+trait):
        for direction in (-1,1):
            destination = column+direction*distance
            if not 0 <= destination < 28:
                destination = column-direction*distance
            columns.add(min(27,max(0,destination)))
    return sorted(columns)


def spacing_witness(row, seed, record, records):
    """Non-newborn post-step occupants existed throughout the seed-check loop.

    No claim of exact light/water gates or availability when the witness is empty.
    Ordinary post-step rows precede any external patch at the same tick.
    """
    point = ledger.snapshot(row,seed,record)
    require(point["age"] >= 8, "spacing evidence requires a mature seed")
    stable, occupants = [], []
    for p in row["plants"]:
        identity = records[p["id"]]
        require(identity["column"] == p["column"] and identity["birth_tick"] <= row["tick"],
                "occupant location/birth disagrees with lineage")
        if identity["birth_tick"] < row["tick"]:
            stable.append(p)
            if abs(p["column"]-seed["column"]) < 3:
                occupants.append({"id":p["id"],"column":p["column"],"dead":p["dead"],
                                  "founder":identity["parent"] == 0,"self":p["id"] == seed["parent"]})
    require(not occupants or point["blockers"]&32, "stable witness lacks observed spacing blocker")
    require(len(stable) != 8 or point["blockers"]&8, "stable full bank lacks plant-capacity blocker")
    return {**point,"stable_spacing_occupants":occupants,"stable_plant_slots":len(stable)}


def empty_stats():
    return {**dict.fromkeys(SCALARS,0),"masks":Counter(),"witness_ids":Counter()}


def observe(stats, point):
    occupants = point["stable_spacing_occupants"]
    spacing, full = bool(occupants), point["stable_plant_slots"] == 8
    stats["samples"] += 1
    stats["masks"][str(point["blockers"])] += 1
    stats["stable_spacing"] += spacing
    stats["stable_plant_capacity"] += full
    stats["stable_structural_blocker"] += spacing or full
    stats["newborn_spacing_only"] += bool(point["blockers"]&32) and not spacing
    stats["self_spacing"] += any(p["self"] for p in occupants)
    stats["dead_spacing"] += any(p["dead"] for p in occupants)
    stats["founder_spacing"] += any(p["founder"] for p in occupants)
    stats["witness_ids"].update(str(p["id"]) for p in occupants)


def merge_stats(values):
    result = empty_stats()
    for value in values:
        for key in SCALARS:
            result[key] += value[key]
        for key in ("masks","witness_ids"):
            result[key].update(value[key])
    return {**result,"observed_blockers":{name:sum(n for mask,n in result["masks"].items() if int(mask)&bit)
                                          for name,bit in ledger.BLOCKERS.items()},
            "no_observed_blockers":result["masks"]["0"],
            "all_mature_stably_spacing_blocked":result["stable_spacing"] == result["samples"] if result["samples"] else None}


def outcome_summary(seeds):
    outcomes = Counter(s["outcome"] for s in seeds)
    require(not outcomes.keys()-{"germinated","expired","pending"},"unknown seed outcome")
    return {"purchases":len(seeds),**{k:outcomes[k] for k in ("germinated","expired","pending")},
            "landing_columns":dict(sorted(Counter(str(s["column"]) for s in seeds).items())),
            "mature_snapshots":sum(s["mature_snapshots"] for s in seeds),
            "child_ids":sorted(s["child_id"] for s in seeds if s["child_id"] is not None)}


def seed_key(seed):
    return seed["parent"],seed["birth_tick"]


def focused_observations(worlds, seeds, records, identity, cutoff, end=STOP):
    """Attach focused evidence without editing the historical ledger's results."""
    selected = [{**s,"observations":{w:empty_stats() for w in WINDOWS},"first_mature_witness":None,
                 "last_mature_witness":None,"witnesses":{},"pending_age":
                    (end-s["birth_tick"])//STEP if s["outcome"] == "pending" else None}
                for s in seeds if s["parent"] == identity]
    lookup = {seed_key(s):s for s in selected}
    require(len(lookup) == len(selected),"duplicate target seed identity")
    births = defaultdict(list)
    for s in seeds:
        births[s["birth_tick"]].append(s)
        require(s["birth_tick"] >= 0 and s["birth_tick"] % STEP == 0 and s["birth_tick"] <= end,
                "invalid seed creation time")
        if s["outcome"] == "expired":
            require(s["end_tick"] == s["birth_tick"]+256*STEP,"incorrect seed expiry age")
        elif s["outcome"] == "germinated":
            require(8*STEP <= s["end_tick"]-s["birth_tick"] < 256*STEP,"incorrect germination age")
        else:
            require(s["outcome"] == "pending" and s["end_tick"] is None and end-s["birth_tick"] < 256*STEP,
                    "incorrect seed censoring")
        require(s["end_tick"] is None or s["end_tick"] <= end,"seed outcome beyond horizon")
    active, last = [], -STEP
    support = dispersal_support(records[identity]["column"],records[identity]["genome"][7])
    require(all(s["column"] in support for s in selected),"target seed outside native dispersal support")
    for row in worlds:
        tick = row["tick"]
        require(row["type"] == "world" and tick == last+STEP and tick <= end,"missing/reordered focused census")
        last = tick
        active = [s for s in active if s["end_tick"] is None or s["end_tick"] > tick]
        active.extend(births.get(tick,[]))
        require([ledger.signature(s) for s in active] == [ledger.signature(s) for s in row["seeds"]],
                "focused reconstruction differs from bank order")
        for s,observed in zip(active,row["seeds"],strict=True):
            if s["parent"] != identity:
                continue
            point = ledger.snapshot(row,observed,s)
            if point["age"] < 8:
                continue
            point = spacing_witness(row,observed,s,records)
            target = lookup[seed_key(s)]
            target["first_mature_witness"] = target["first_mature_witness"] or point
            target["last_mature_witness"] = point
            for window,include in (("whole",True),("since_refusal",tick >= cutoff),("late",tick > LATE)):
                if include:
                    observe(target["observations"][window],point)
            for p in point["stable_spacing_occupants"]:
                witness = target["witnesses"].setdefault(str(p["id"]),
                    {"lineage":records[p["id"]],"self":p["self"],"first_tick":tick,"last_tick":tick,
                     "samples":0,"living_samples":0,"dead_samples":0,"sole_witness_samples":0})
                witness["last_tick"] = tick
                witness["samples"] += 1
                witness["dead_samples" if p["dead"] else "living_samples"] += 1
                witness["sole_witness_samples"] += len(point["stable_spacing_occupants"]) == 1
    require(last == end,"truncated focused census")
    for s in selected:
        stats = s["observations"]["whole"]
        require(stats["samples"] == s["mature_snapshots"] and stats["masks"] == s["mature_blockers"],
                "focused mature coverage differs from complete ledger")
        stop = s["end_tick"]-STEP if s["end_tick"] is not None else end
        require(stats["samples"] == max(0,(stop-s["birth_tick"])//STEP-7),"missing mature seed observations")
    return selected,support


def focused_summary(selected):
    return {**outcome_summary(selected),"observations":{w:merge_stats(s["observations"][w] for s in selected)
                                                       for w in WINDOWS}}


def analyze_case(root,case,arm,saved):
    name = f"{case.name}.{arm}"
    raw = (r for r in parent.startup.read_trace(root/f"traces/{name}.jsonl.gz") if r["type"] in ("world","disturbance"))
    worlds,boundaries = panel.split_rows(raw,case.baseline.patch)
    require(worlds == list(parent.startup.read_trace(root/f"traces/{name}.worlds.jsonl.gz")),"derived census differs")
    records = {p["id"]:p for p in saved["lineages"]}
    full = ledger.seed_ledger(worlds,boundaries,records)
    # These two fields belong to the historical FINISH experiment, not this audit.
    seeds = [{k:v for k,v in s.items() if k not in ("post_cutoff_blockers","sole_spacing_22")} for s in full["seeds"]]
    summary = outcome_summary(seeds)
    whole = saved["summary"]["windows"]["whole"]
    require((summary["purchases"],summary["expired"],summary["germinated"],summary["pending"]) ==
            (whole["seeds_created"],whole["seeds_expired"],whole["births"],len(worlds[-1]["seeds"])),"whole-world funnel differs")
    selected,support = focused_observations(worlds,seeds,records,case.target_id,case.first_tick)
    require(len(selected) == saved["target"]["lineage"]["seeds_created"] and
            {s["child_id"] for s in selected if s["child_id"] is not None} ==
            {p["id"] for p in records.values() if p["parent"] == case.target_id},"target seed/child totals differ")
    print("Audited rescued-parent seeds:",name,flush=True)
    return {"target":records[case.target_id],"cutoff":case.first_tick,"support_columns":support,
            "target_summary":focused_summary(selected),"target_seeds":selected,
            "target_purchase_windows":{w:outcome_summary([s for s in selected if
                w == "whole" or (w == "since_refusal" and s["birth_tick"] >= case.first_tick) or
                (w == "late" and s["birth_tick"] > LATE)]) for w in WINDOWS},
            "target_columns":{str(c):focused_summary([s for s in selected if s["column"] == c])
                              for c in sorted({s["column"] for s in selected})},
            "seed_ledger":{**full,"seeds":seeds},"all_seed_summary":summary,
            "lineages":saved["lineages"],"context":saved["summary"]}


def analyze(root,saved):
    cases = {f"{c.name}.{a}":analyze_case(root,c,a,saved["cases"][f"{c.name}.{a}"])
             for c in CASES for a in parent.ARMS}
    treated = [s for c in CASES for s in cases[f"{c.name}.capacity"]["target_seeds"]]
    require([len(cases[f"{c.name}.capacity"]["target_seeds"]) for c in CASES] == [15,28],
            "predeclared target purchase totals differ")
    return {"rule":RULE,"baseline_manifest_sha256":BASELINE_SHA,"portable_input_sha256":PORTABLE_SHA,
            "native_calls":0,"stop":STOP,"late_start":LATE,"cases":cases,
            "treated_targets":focused_summary(treated),
            "notes":["Seed identity/age is reconstructed from ordered transitions, not logged IDs.",
                     "Masks are post-step queries. Non-newborn spacing witnesses are conservative code-order inferences.",
                     "No stable witness does not prove a free site or a successful counterfactual.",
                     "Mature seed snapshots are repeated exposure, not independent germination probabilities.",
                     "Selected development trajectories; no matching of later newborn IDs across arms."]}


def analysis_sources():
    paths = sorted((experiment.ROOT/"sim").glob("*.py"))+[experiment.ROOT/PROTOCOL,experiment.ROOT/"sim/CMakeLists.txt"]
    return {str(p.relative_to(experiment.ROOT)):experiment.digest(p) for p in paths}


def verify(root):
    require(experiment.digest(root/"manifest.json") == BASELINE_SHA,"wrong or changed parent manifest")
    require(experiment.digest(experiment.ROOT/PORTABLE) == PORTABLE_SHA,"changed portable parent")
    sources = analysis_sources()
    native = parent.guard.prior.prior.native_hashes(root/"source.tar.gz")
    require(all(experiment.digest(experiment.ROOT/n) == sha for n,sha in native.items()),"native sources changed")
    saved = parent.verify(root)
    portable = {**saved,"manifest_sha256":BASELINE_SHA,"full_results_sha256":experiment.digest(root/"results.json"),
                "exporter_sha256":experiment.digest(Path(parent.__file__)),"timing":experiment.read_json(root/"timings.json")}
    require(experiment.read_json(experiment.ROOT/PORTABLE) == portable,"portable parent results differ")
    prefix = experiment.ROOT/"benchmarks/garden-longevity/renewal-capacity-guard"
    require(experiment.digest(prefix.with_suffix(".png")) == experiment.digest(root/"contact-sheet.png"),"portable overview differs")
    for f in saved["frames"]:
        require(experiment.digest(prefix.with_name(prefix.name+"-frames")/(f["id"]+".png")) ==
                experiment.digest(root/f["png"]),"portable frame differs")
    result = analyze(root,saved)
    require(result == analyze(root,saved),"rescued seed analysis repeat differs")
    require(sources == analysis_sources() and all(experiment.digest(experiment.ROOT/n) == sha for n,sha in native.items()),
            "analysis/native source changed")
    parent.shadow.check_frozen(root,BASELINE_SHA)
    require(experiment.digest(experiment.ROOT/PORTABLE) == PORTABLE_SHA,"portable input changed")
    result.update(analysis_sources=sources,native_sources=native)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline",type=Path,default=experiment.ROOT/"artifacts/garden-renewal-capacity-guard-v1")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--output",type=Path)
    target.add_argument("--check",type=Path)
    args = parser.parse_args()
    root = args.baseline.resolve()
    if args.output:
        require(not args.output.exists() and not args.output.resolve().is_relative_to(root),"choose fresh output outside parent")
    result = verify(root)
    if args.output:
        experiment.write_json(args.output,result)
    else:
        require(experiment.read_json(args.check) == result,"portable rescued-seed audit differs")
    print("Verified rescued-parent seed audit; zero new experimental native calls",flush=True)


if __name__ == "__main__":
    main()
