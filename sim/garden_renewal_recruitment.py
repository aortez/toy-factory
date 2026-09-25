#!/usr/bin/env python3
"""Offline seed/offspring attribution of the frozen retry-aware FINISH pair."""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import garden_renewal_finish_retry as parent
from garden_plant_slots import plant_capacity

experiment, panel, require = parent.experiment, parent.panel, parent.require
startup, failures = parent.startup, parent.failures
DAY, STOP, LATE, STEP = panel.DAY, panel.STOP, panel.LATE, 15
CUTOFF = 69885
RULE = "garden-renewal-recruitment-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-recruitment-protocol.md"
BASELINE_SHA = "7e3fd0628912287cdd36954d3f9b38e7471d012f1df31b87cfacde009d044d45"
ARMS = ("control", "finish-retry")
BLOCKERS = {"dormant":1, "moisture":2, "light":4, "plant_capacity":8, "node_capacity":16, "spacing":32}
SIGNATURE = ("parent", "generation", "column")


def signature(seed):
    return tuple(seed[k] for k in SIGNATURE)


def transition(active, observed, newborns, tick):
    """Reconstruct ordered removals before appended purchases, without RNG replay.

    Mature seeds at the same column share the same germination gates. An earlier
    one cannot fail and a later one succeed in this loop: checks can only become
    more restrictive as seedlings consume space/water. Dormant/expired entries
    are excluded. Thus indistinguishable eligible duplicates use native FIFO,
    not a guessed alignment against the final bank.
    """
    children = list(newborns)
    require([p["id"] for p in children] == sorted({p["id"] for p in children}), "unordered children")
    survivors, removals, skipped_columns = [], [], set()
    for seed in active:
        age = (tick-seed["birth_tick"])//STEP
        require(tick > seed["birth_tick"] and (tick-seed["birth_tick"]) % STEP == 0 and age <= 256,
                "invalid reconstructed seed age")
        if age == 256:
            removals.append((seed,"expired",None))
        elif children and signature(seed) == signature(children[0]) and age >= 8:
            require(seed["column"] not in skipped_columns, "ambiguous/impossible same-column germination")
            removals.append((seed,"germinated",children.pop(0)["id"]))
        else:
            survivors.append(seed)
            if age >= 8:
                skipped_columns.add(seed["column"])
    require(not children, "newborn has no eligible ordered seed")
    require([signature(s) for s in survivors] == [signature(s) for s in observed[:len(survivors)]],
            "seed bank order or unobserved removal changed")
    return survivors, removals, observed[len(survivors):]


def snapshot(row, seed, record, *, minimum_spacing=3):
    require(type(minimum_spacing) is int and minimum_spacing in (2, 3), "unsupported spacing")
    mask, tick = seed["blockers"], row["tick"]
    age = (tick-record["birth_tick"])//STEP
    occupants = [p for p in row["plants"] if abs(p["column"]-seed["column"]) < minimum_spacing]
    require(0 <= mask < 64 and 0 <= age < 256 and bool(mask&1) == (age < 8), "wrong seed dormancy/mask")
    require(bool(mask&8) == (len(row["plants"]) == plant_capacity(row)) and bool(mask&16) == (row["nodes"]+4 > 512)
            and bool(mask&32) == bool(occupants), "post-step capacity/spacing disagrees with native query")
    return {"tick":tick, "age":age, "blockers":mask, "plant_slots":len(row["plants"]),
            "nodes":row["nodes"], "spacing_occupants":[{"id":p["id"],"dead":p["dead"]} for p in occupants]}


def seed_ledger(worlds, boundaries, records, end=STOP, *, spacing_at=None, reproduction_order=None):
    seeds, active, seen_children = [], [], set()
    previous = {"tick":-STEP,"births":0,"seeds_created":0,"seeds_expired":0}
    species_events, old_species, checked = [], None, 0
    seen_boundaries = set()
    for row in worlds:
        tick = row["tick"]
        require(row["type"] == "world" and tick == previous["tick"]+STEP and tick <= end,
                "missing/reordered seed census")
        require(len(row["seeds"]) <= 8 and len(row["plants"]) <= plant_capacity(row), "seed/plant capacity exceeded")
        children = [p for p in row["plants"] if p["parent"] and records[p["id"]]["birth_tick"] == tick]
        require(len(children) == row["births"]-previous["births"] and
                not seen_children.intersection(p["id"] for p in children), "birth counter/identity mismatch")
        seen_children.update(p["id"] for p in children)
        survivors, removals, additions = transition(active,row["seeds"],children,tick)
        expired = 0
        for record,outcome,child in removals:
            require(record["outcome"] == "pending", "seed ended twice")
            record.update(outcome=outcome,end_tick=tick,child_id=child)
            expired += outcome == "expired"
        require(expired == row["seeds_expired"]-previous["seeds_expired"] and
                len(additions) == row["seeds_created"]-previous["seeds_created"], "seed counter mismatch")
        visits = reproduction_order(row) if reproduction_order else row["plants"]
        require(sorted(p["id"] for p in visits) == sorted(p["id"] for p in row["plants"]),
                "reproduction visits must preserve the plant inventory")
        producers = [p["id"] for p in visits if not p["dead"] and p["reproduction_cooldown"] == 16]
        require([s["parent"] for s in additions] == producers, "appended seeds disagree with paid reproduction")
        for s in additions:
            ancestor = records[s["parent"]]
            require(s["generation"] == ancestor["generation"]+1 and 0 <= s["column"] < 28,
                    "wrong seed ancestry/column")
            record = {**{k:s[k] for k in SIGNATURE}, "birth_tick":tick, "species":ancestor["species"],
                      "outcome":"pending", "end_tick":None, "child_id":None,
                      "mature_snapshots":0, "mature_blockers":Counter(), "post_cutoff_blockers":Counter(),
                      "spacing_occupants":Counter(), "sole_spacing_22":0,
                      "first_mature":None, "last_snapshot":None}
            seeds.append(record)
            survivors.append(record)
        require(len({(s["parent"],s["birth_tick"]) for s in seeds}) == len(seeds), "ambiguous creation identity")
        for record,s in zip(survivors,row["seeds"],strict=True):
            require(signature(record) == signature(s), "reconstructed bank differs")
            point = snapshot(row,s,record, minimum_spacing=spacing_at(row) if spacing_at else 3)
            record["last_snapshot"] = point
            if point["age"] >= 8:
                record["first_mature"] = record["first_mature"] or point
                record["mature_snapshots"] += 1
                record["mature_blockers"][str(point["blockers"])] += 1
                if tick >= CUTOFF:
                    record["post_cutoff_blockers"][str(point["blockers"])] += 1
                record["spacing_occupants"].update(str(p["id"]) for p in point["spacing_occupants"])
                record["sole_spacing_22"] += [p["id"] for p in point["spacing_occupants"]] == [22]
                checked += 1
        after = row
        if tick in boundaries:
            b = boundaries[tick]
            require(b["before"] == row and b["after"]["seeds"] == row["seeds"], "patch changed seed bank")
            after = b["after"]
            seen_boundaries.add(tick)
        live = Counter(p["species"] for p in after["plants"] if not p["dead"])
        bank = Counter(s["species"] for s in survivors)
        species = {name:{"living":live[name],"bank":bank[name]} for name in ("flower","shrub","ground-cover")}
        if species != old_species:
            species_events.append({"tick":tick,"species":species})
        old_species, active, previous = species, survivors, row
    require(previous["tick"] == end and seen_boundaries == boundaries.keys(), "truncated seed/patch census")
    require(len(seeds) == previous["seeds_created"] and seen_children == {p["id"] for p in records.values() if p["parent"]},
            "incomplete seed/offspring coverage")
    for p in records.values():
        own = [s for s in seeds if s["parent"] == p["id"]]
        require(len(own) == p["seeds_created"] and sum(s["birth_tick"] > LATE for s in own) == p["late_seeds_created"],
                "seed lineage totals differ")
    return {"seeds":seeds, "mature_snapshots":checked, "species_events":species_events}


def seed_group(seeds):
    masks = Counter()
    for s in seeds:
        masks.update(s["post_cutoff_blockers"])
    result = {"purchases":len(seeds), **{k:sum(s["outcome"] == k for s in seeds)
              for k in ("germinated","expired","pending")}, "post_cutoff_mature_masks":masks,
              "post_cutoff_mature_samples":sum(masks.values()),
              "observed_blockers":{name:sum(n for mask,n in masks.items() if int(mask)&bit)
                                   for name,bit in BLOCKERS.items()},
              "landing_columns":dict(sorted(Counter(str(s["column"]) for s in seeds).items()))}
    require(result["purchases"] == sum(result[k] for k in ("germinated","expired","pending")), "seed funnel differs")
    return result


def offspring_group(selected, records, end=STOP):
    ids = {p["id"] for p in selected}
    cohort = panel.competition.lifetime_cohort(records,end,selected_ids=ids)
    return {**cohort, "natural_deaths":sum(p["death_tick"] is not None and not p.get("environmental_death") for p in selected),
            "patch_deaths":sum(bool(p.get("environmental_death")) for p in selected),
            "alive_at_end":sum(p["death_tick"] is None for p in selected),
            "early_natural_deaths":sum(p["death_tick"] is not None and not p.get("environmental_death") and
                                        p["death_tick"] <= p["birth_tick"]+DAY for p in selected)}


def death_partition(records):
    groups = {"founders":[],"pre_intervention_offspring":[],"post_intervention_offspring":[]}
    for p in records.values():
        label = "founders" if not p["parent"] else "pre_intervention_offspring" if p["birth_tick"] < CUTOFF else "post_intervention_offspring"
        groups[label].append(p)
    return {name:{"plants":len(group), "natural_deaths":sum(p["death_tick"] is not None and not p.get("environmental_death") for p in group),
                  "patch_deaths":sum(bool(p.get("environmental_death")) for p in group),
                  "alive":sum(p["death_tick"] is None for p in group)} for name,group in groups.items()}


def child_detail(record, history):
    first_day = [e for e in history if e["state"]["tick"] <= record["birth_tick"]+DAY]
    live = [e for e in first_day if not e["state"]["dead"]]
    first_shortage = next((e["state"] for e in first_day if e["state"]["flags"]&6),None)
    windows = failures.all_windows(history) if history[-1]["terminal"] == "natural" else []
    death = failures.death_record(history,windows,record,True) if windows or history[-1]["terminal"] == "natural" else None
    return {"lineage":record,"birth_state":history[0]["state"],"first_day_last_live":live[-1]["state"],
            "first_day_first_shortage":first_shortage,"first_day_live_budget":failures.budget_sum(first_day),
            "death":death, "dark_windows":windows}


def analyze_case(root,arm,saved):
    raw = (r for r in startup.read_trace(root/f"traces/{arm}.jsonl.gz") if r["type"] in ("world","disturbance"))
    worlds,boundaries = panel.split_rows(raw,parent.prior.CASE.patch)
    require(worlds == list(startup.read_trace(root/f"traces/{arm}.worlds.jsonl.gz")), "derived census differs")
    records = {p["id"]:p for p in saved["lineages"]}
    ledger = seed_ledger(worlds,boundaries,records)
    histories,checked = failures.histories(worlds,boundaries,records,STOP)
    require(checked == saved["checked_live_histories"], "live history coverage differs")
    partition = death_partition(records)
    require(sum(g["natural_deaths"] for g in partition.values()) == saved["summary"]["windows"]["whole"]["natural_deaths"] and
            sum(g["patch_deaths"] for g in partition.values()) == saved["summary"]["windows"]["whole"]["environmental_deaths"],
            "mortality partition differs")
    cohorts = {}
    for name,start in (("whole",-1),("post_intervention",CUTOFF-1),("late",LATE)):
        selected = [p for p in records.values() if p["parent"] and p["birth_tick"] > start]
        cohorts[name] = {"all":offspring_group(selected,records),
            "species":{s:offspring_group([p for p in selected if p["species"] == s],records)
                       for s in ("flower","shrub","ground-cover")},
            "columns":{str(c):offspring_group([p for p in selected if p["column"] == c],records)
                       for c in sorted({p["column"] for p in selected})}}
        if name != "post_intervention":
            expected = saved["summary"]["windows"][name]["cohort"]
            require(all(cohorts[name]["all"][k] == v for k,v in expected.items()),"saved cohort differs")
    shrubs = [s for s in ledger["seeds"] if s["species"] == "shrub"]
    shrub_groups = {"all":shrubs,"parent_6":[s for s in shrubs if s["parent"] == 6],
        "pending_at_intervention":[s for s in shrubs if s["birth_tick"] < CUTOFF and
                                    (s["end_tick"] is None or s["end_tick"] >= CUTOFF)],
        "purchased_after_intervention":[s for s in shrubs if s["birth_tick"] >= CUTOFF]}
    print("Audited seed transitions and offspring:",arm,flush=True)
    return {"death_partition":partition, "cohorts":cohorts,"seed_ledger":ledger,
            "shrub_seeds":{n:seed_group(g) for n,g in shrub_groups.items()},
            "post_intervention_children":[child_detail(p,histories[p["id"]]) for p in records.values()
                                          if p["parent"] and p["birth_tick"] >= CUTOFF],
            "checked_live_histories":checked}


def analyze(root,saved):
    cases = {arm:analyze_case(root,arm,saved["cases"][arm]) for arm in ARMS}
    partitions = {name:{k:cases["finish-retry"]["death_partition"][name][k]-cases["control"]["death_partition"][name][k]
                        for k in ("plants","natural_deaths","patch_deaths","alive")}
                  for name in cases["control"]["death_partition"]}
    return {"rule":RULE,"baseline_manifest_sha256":BASELINE_SHA,"native_calls":0,
            "cutoff":CUTOFF,"stop":STOP,"late_start":LATE,"cases":cases,"death_partition_delta":partitions,
            "notes":["Seed identity is reconstructed from parent/creation tick and ordered bank transitions; not logged seed IDs.",
                     "Blockers are post-step observations, not pre-germination decisions or counterfactual relaxations.",
                     "Later newborn IDs are not paired individuals. This selected world is not independent validation.",
                     "Cleared terminal resource budgets are not reconstructed. Endpoint survival remains censored."]}


def analysis_sources():
    paths = sorted((experiment.ROOT/"sim").glob("*.py")) + [experiment.ROOT/PROTOCOL,experiment.ROOT/"sim/CMakeLists.txt"]
    return {str(p.relative_to(experiment.ROOT)):experiment.digest(p) for p in paths}


def verify(root):
    require(experiment.digest(root/"manifest.json") == BASELINE_SHA,"wrong frozen parent")
    sources = analysis_sources()
    native = parent.guard.prior.prior.native_hashes(root/"source.tar.gz")
    require(all(experiment.digest(experiment.ROOT/n) == sha for n,sha in native.items()),"native sources changed")
    saved = parent.verify(root)
    result = analyze(root,saved)
    require(result == analyze(root,saved),"recruitment analysis repeat differs")
    require(analysis_sources() == sources,"analysis source changed")
    manifest = experiment.read_json(root/"manifest.json")
    require(experiment.digest(root/"manifest.json") == BASELINE_SHA,"parent manifest changed")
    for name in manifest["artifacts"]:
        parent.gallery.artifact(root,manifest,name)
    result.update(analysis_sources=sources,native_sources=native)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline",type=Path,default=experiment.ROOT/"artifacts/garden-renewal-finish-retry-v1")
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
        require(experiment.read_json(args.check) == result,"portable recruitment audit differs")
    print("Verified frozen recruitment audit; zero new native calls",flush=True)


if __name__ == "__main__":
    main()
