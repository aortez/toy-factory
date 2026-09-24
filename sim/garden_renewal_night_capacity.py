#!/usr/bin/env python3
"""Shadow-only full-night body-capacity audit of frozen garden trajectories."""
from __future__ import annotations

import argparse
from collections import Counter
from functools import lru_cache
from pathlib import Path

import garden_renewal_finish_retry as retry

panel, failures, experiment, require = retry.panel, retry.failures, retry.experiment, retry.require
reference, startup = failures.reference, panel.startup
RULE = "garden-renewal-night-capacity-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-night-capacity-protocol.md"
PANEL_SHA = "d62a870fea9ecfede3a32cebe1465097c0391f53a0cf781358574fc2db2e4ae8"
RETRY_SHA = "7e3fd0628912287cdd36954d3f9b38e7471d012f1df31b87cfacde009d044d45"
ANCHOR, ENERGY_CAP, MAX_NODES, STEP = 795, 256, 512, 15
LABELS = ("safe", "newly-unsafe", "already-unsafe")


@lru_cache(maxsize=MAX_NODES)
def _capacity(nodes):
    predicted = reference.project(ANCHOR, ENERGY_CAP, nodes, 0)
    bounds = predicted["boundaries"]
    require(bounds["dark_steps"] == 149 and len(bounds["maintenance_ticks"]) == 37,
            "canonical full-night alignment changed")
    upkeep = (nodes+7)//8
    minimum = upkeep*(37-7)
    paid = min(37, ENERGY_CAP//upkeep)
    death = bounds["maintenance_ticks"][paid+7] if 37-paid >= 8 else None
    require((predicted["death_tick"] is None) == (minimum <= ENERGY_CAP) and
            predicted["death_tick"] == death, "closed-form and iterative capacity differ")
    return {"nodes":nodes, "upkeep":upkeep, "minimum_energy":minimum,
            "viable_at_cap":minimum <= ENERGY_CAP, "canonical_death_tick":death}


def capacity(nodes):
    require(type(nodes) is int and 1 <= nodes <= MAX_NODES, "invalid structural body size")
    return dict(_capacity(nodes))


def classify(before, after):
    require(type(before) is int and type(after) is int and after == before+1,
            "capacity query must add exactly one node")
    a,b = capacity(before),capacity(after)
    return "safe" if b["viable_at_cap"] else "newly-unsafe" if a["viable_at_cap"] else "already-unsafe"


def added_node(old, plant):
    """Only committed positive-node EXTENDs enter the shared paid denominator."""
    require(not plant["dead"] and (old is None or not old["dead"]), "growth on a dead plant")
    before = old["nodes"] if old is not None else 4
    delta = plant["nodes"]-before
    count = plant["agent"]["extend"]-(old["agent"]["extend"] if old is not None else 0)
    require(delta in (0,1) and count in (0,1) and (not delta or count == 1),
            "node delta does not match a committed extension")
    return bool(delta)


def event_record(tick, identity, before, after, *, paid, node=None, energy=None, stress=None):
    require(type(tick) is int and tick > 0 and tick % STEP == 0, "invalid extension time")
    result = {"tick":tick, "phase":(64+tick//STEP)%256, "id":identity,
              "nodes_before":before, "nodes_after":after, "paid":paid, "selected_tip":node,
              "classification":classify(before,after), "energy_after_growth":energy, "stress":stress}
    if paid and result["classification"] == "newly-unsafe":
        require(energy is not None and stress is not None, "crossing lacks actual purchase state")
        result["actual_remaining_dark"] = reference.compact(reference.project(tick,energy,after,stress))
    return result


def extension_ledger(worlds, boundaries, guarded, end=panel.STOP):
    paid, denied, previous, seen = [], [], {}, set()
    last = -STEP
    for row in worlds:
        tick = row["tick"]
        require(row["type"] == "world" and tick == last+STEP and tick <= end, "missing extension census")
        require(("dark_guard" in row) == guarded, "wrong guard arm")
        current = {p["id"]:p for p in row["plants"]}
        require(len(current) == len(row["plants"]), "duplicate plant")
        positive = {}
        for receipt in row.get("dark_guard",{}).get("events",[]):
            if receipt["kind"] != "growth" or receipt["nodes_after"] == receipt["nodes_before"]:
                continue
            identity = receipt["id"]
            panel.guard.check_event(receipt,tick)
            require(identity in current and identity not in positive and not current[identity]["dead"],
                    "duplicate/absent/dead positive-node receipt")
            before = previous[identity]["nodes"] if identity in previous else 4
            require(receipt["nodes_before"] == before and receipt["nodes_after"] == before+1,
                    "receipt does not describe the current body")
            positive[identity] = receipt
            if receipt["denied"]:
                denied.append(event_record(tick,identity,before,before+1,paid=False,node=receipt["node"],
                    energy=receipt["energy"]-receipt["energy_cost"],stress=receipt["stress"]))
        for identity,p in current.items():
            old, receipt = previous.get(identity), positive.get(identity)
            if not tick:
                require(p["nodes"] == 4 and p["agent"]["extend"] == 0, "unexpected initial body")
                continue
            if p["dead"]:
                continue
            added = added_node(old,p)
            if guarded:
                require(added == bool(receipt is not None and not receipt["denied"]),
                        "paid growth and positive-node receipt disagree")
            if not added:
                continue
            values = startup.resources.budget(old,p,tick)
            energy = p["energy"]+values["energy_seeds"]
            require(values["extensions"] == 1 and values["finishes"] == 0, "wrong paid action")
            if receipt is not None:
                require(energy == receipt["energy"]-receipt["energy_cost"] and
                        values["energy_growth"] == receipt["energy_cost"] and p["stress"] == receipt["stress"],
                        "paid purchase stores differ from receipt")
            paid.append(event_record(tick,identity,p["nodes"]-1,p["nodes"],paid=True,
                node=receipt["node"] if receipt else None,energy=energy,stress=p["stress"]))
        after = row
        if tick in boundaries:
            boundary = boundaries[tick]
            require(boundary["before"] == row, "wrong extension patch boundary")
            panel.disturbance.validate_boundary(row,boundary["after"],boundary["event"])
            after = boundary["after"]
            seen.add(tick)
        previous, last = {p["id"]:p for p in after["plants"]},tick
    require(last == end and seen == boundaries.keys(), "truncated extension/patch ledger")
    return paid,denied


def event_summary(events):
    return {"total":len(events), "classification":{name:sum(e["classification"] == name for e in events) for name in LABELS},
            "flagged_plants":len({e["id"] for e in events if e["classification"] != "safe"}),
            "flagged_phases":dict(sorted(Counter(str(e["phase"]) for e in events if e["classification"] != "safe").items())),
            "first_flag":next((e for e in events if e["classification"] != "safe"),None),
            "last_flag":next((e for e in reversed(events) if e["classification"] != "safe"),None),
            "late_flagged":sum(e["tick"] > panel.LATE and e["classification"] != "safe" for e in events)}


def denied_groups(events):
    groups = {}
    for event in events:
        if event["classification"] == "safe":
            continue
        key = (event["id"],event["selected_tip"],event["nodes_before"])
        require(event["paid"] is False and event["selected_tip"] is not None, "not a denied selected tip")
        group = groups.setdefault(key,{"id":key[0],"tip":key[1],"nodes_before":key[2],
            "classification":event["classification"],"attempts":0,"first":event,"last":event})
        group["attempts"] += 1
        group["last"] = event
    return list(groups.values())


def first_full_night(history, crossing):
    tick = crossing["tick"]
    require(history and history[0]["state"]["tick"] <= tick <= history[-1]["state"]["tick"],
            "crossing outside lifetime")
    anchor = ANCHOR + max(0,(tick-ANCHOR+panel.DAY-1)//panel.DAY)*panel.DAY
    final = history[-1]
    if final["state"]["tick"] < anchor:
        status = {None:"trace-censored-before-anchor", "natural":"natural-death-before-anchor",
                  "patch":"patch-censored-before-anchor"}[final["terminal"]]
        return {"anchor_tick":anchor,"status":status,"terminal_tick":final["state"]["tick"]}
    index = next((i for i,e in enumerate(history) if e["state"]["tick"] == anchor),None)
    require(index is not None, "missing full-night anchor")
    entry = history[index]
    if entry["terminal"] is not None:
        require(entry["terminal"] == "patch", "natural death outside maintenance")
        return {"anchor_tick":anchor,"status":"patch-censored-at-anchor","terminal_tick":anchor}
    window = failures.audit_window(history,index)
    return {"anchor_tick":anchor,"status":window["status"],"window":window,
            "capacity_at_anchor":capacity(entry["state"]["nodes"])}


def lineage_detail(record, history, paid, denied, records):
    live = [e["state"] for e in history if not e["state"]["dead"]]
    crossings = [e for e in paid if e["classification"] == "newly-unsafe"]
    require(len(crossings) <= 1 and bool(crossings) == (not capacity(max(p["nodes"] for p in live))["viable_at_cap"]),
            "unsafe observed body lacks its one paid crossing")
    terminal = history[-1]
    children = [p for p in records.values() if p["parent"] == record["id"]]
    cohort = panel.competition.lifetime_cohort(records,panel.STOP,selected_ids={p["id"] for p in children})
    return {"lineage":record,"outcome":terminal["terminal"] or "alive-at-end",
            "cause":startup.SHORTAGES[terminal["state"]["flags"]&6] if terminal["terminal"] == "natural" else None,
            "last_live":live[-1],"maximum_nodes":max(p["nodes"] for p in live),
            "paid":event_summary(paid),"denied":event_summary(denied),
            "crossing":crossings[0] if crossings else None,
            "first_full_night":first_full_night(history,crossings[0]) if crossings else None,
            "offspring":cohort}


def summary(lineages, paid, denied):
    natural = [p for p in lineages if p["outcome"] == "natural"]
    crossed = [p for p in lineages if p["crossing"] is not None]
    return {"plants":len(lineages), "paid":event_summary(paid), "denied":event_summary(denied),
            "crossed_plants":len(crossed),
            "crossed_species":dict(Counter(p["lineage"]["species"] for p in crossed)),
            "crossed_founders":sum(p["lineage"]["parent"] == 0 for p in crossed),
            "crossed_outcomes":dict(Counter(p["outcome"] for p in crossed)),
            "crossed_seeds_created":sum(p["lineage"]["seeds_created"] for p in crossed),
            "crossed_first_night":dict(Counter(p["first_full_night"]["status"] for p in crossed)),
            "natural_deaths":len(natural), "natural_with_crossing":sum(p["crossing"] is not None for p in natural),
            "natural_unsafe_last_live":sum(not capacity(p["last_live"]["nodes"])["viable_at_cap"] for p in natural),
            "natural_without_crossing":sum(p["crossing"] is None for p in natural),
            "unflagged_death_causes":dict(Counter(p["cause"] for p in natural if p["crossing"] is None))}


def analyze_case(root,name,patch,guarded,saved):
    raw = (r for r in startup.read_trace(root/f"traces/{name}.jsonl.gz") if r["type"] in ("world","disturbance"))
    worlds,boundaries = panel.split_rows(raw,patch)
    require(worlds == list(startup.read_trace(root/f"traces/{name}.worlds.jsonl.gz")), "derived world census differs")
    records = {p["id"]:p for p in saved["lineages"]}
    histories,checked = failures.histories(worlds,boundaries,records,panel.STOP)
    require(checked == saved["summary"]["windows"]["whole"]["checked_live_steps"], "live-budget coverage differs")
    paid,denied = extension_ledger(worlds,boundaries,guarded)
    lineages = [lineage_detail(p,histories[i],[e for e in paid if e["id"] == i],
                              [e for e in denied if e["id"] == i],records) for i,p in records.items()]
    totals = summary(lineages,paid,denied)
    require(totals["natural_deaths"] == saved["summary"]["windows"]["whole"]["natural_deaths"], "death coverage differs")
    require(sum(p["outcome"] == "patch" for p in lineages) ==
            saved["summary"]["windows"]["whole"]["environmental_deaths"], "patch deaths differ")
    groups = denied_groups(denied)
    print("Audited full-night capacity:",name,flush=True)
    return {"summary":totals,"lineages":lineages,"flagged_denied_groups":groups,
            "repeated_flagged_denials":sum(g["attempts"]-1 for g in groups),"checked_live_histories":checked}


def aggregate(cases):
    result = {}
    scalar = ("plants","crossed_plants","crossed_founders","crossed_seeds_created","natural_deaths",
              "natural_with_crossing","natural_unsafe_last_live","natural_without_crossing")
    counters = ("crossed_species","crossed_outcomes","crossed_first_night","unflagged_death_causes")
    for condition in panel.CONDITIONS:
        result[condition] = {}
        for arm in panel.guard.CASES:
            group = [cases[panel.Case(seed,condition,arm).name]["summary"] for seed in panel.SEEDS]
            totals = {key:sum(g[key] for g in group) for key in scalar}
            for key in counters:
                counts = Counter()
                for g in group:
                    counts.update(g[key])
                totals[key] = counts
            for status in ("paid","denied"):
                totals[status] = {"total":sum(g[status]["total"] for g in group),
                    "classification":{key:sum(g[status]["classification"][key] for g in group) for key in LABELS}}
            result[condition][arm] = totals
    return result


def analyze(panel_root,retry_root,panel_saved,retry_saved):
    cases = {c.name:analyze_case(panel_root,c.name,c.patch,c.arm == "guard",panel_saved["cases"][c.name]) for c in panel.CASES}
    supplemental = analyze_case(retry_root,"finish-retry",retry.prior.CASE.patch,True,retry_saved["cases"]["finish-retry"])
    return {"rule":RULE,"native_calls":0,"panel_manifest_sha256":PANEL_SHA,"retry_manifest_sha256":RETRY_SHA,
            "canonical_anchor_tick":ANCHOR,"energy_cap":ENERGY_CAP,"starting_stress":0,
            "capacity_table":[capacity(n) for n in range(1,MAX_NODES+1)],
            "cases":cases,"aggregate":aggregate(cases),"supplemental_finish_retry":supplemental,
            "notes":["Shared prefixes and repeated trajectories are not independent worlds.",
                     "Only positive-node paid EXTENDs share a denominator across arms; selected denied proposals are separate.",
                     "This predicate ignores current reserves/phase; surviving its full-night energy test is not sufficient to live.",
                     "Follow-up remains the unchanged observed trajectory, not a counterfactual response to refusal.",
                     "Natural terminal budgets are cleared; patch and endpoint censoring remain explicit."]}


def analysis_sources():
    paths = sorted((experiment.ROOT/"sim").glob("*.py"))+[experiment.ROOT/PROTOCOL,experiment.ROOT/"sim/CMakeLists.txt"]
    return {str(p.relative_to(experiment.ROOT)):experiment.digest(p) for p in paths}


def check_frozen(root,sha):
    require(experiment.digest(root/"manifest.json") == sha, "wrong or changed frozen manifest")
    manifest = experiment.read_json(root/"manifest.json")
    require(set(manifest["artifacts"]) == {str(p.relative_to(root)) for p in root.rglob("*")
            if p.is_file() and p != root/"manifest.json"}, "extra/missing frozen artifact")
    for name in manifest["artifacts"]:
        panel.gallery.artifact(root,manifest,name)


def verify(panel_root,retry_root):
    sources = analysis_sources()
    native = retry.guard.prior.prior.native_hashes(retry_root/"source.tar.gz")
    require(all(experiment.digest(experiment.ROOT/n) == sha for n,sha in native.items()), "native sources changed")
    check_frozen(panel_root,PANEL_SHA)
    check_frozen(retry_root,RETRY_SHA)
    panel_saved,retry_saved = panel.verify(panel_root),retry.verify(retry_root)
    result = analyze(panel_root,retry_root,panel_saved,retry_saved)
    require(result == analyze(panel_root,retry_root,panel_saved,retry_saved), "shadow analysis repeat differs")
    require(analysis_sources() == sources and all(experiment.digest(experiment.ROOT/n) == sha for n,sha in native.items()),
            "analysis/native source changed")
    check_frozen(panel_root,PANEL_SHA)
    check_frozen(retry_root,RETRY_SHA)
    result.update(analysis_sources=sources,native_sources=native)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel",type=Path,default=experiment.ROOT/"artifacts/garden-renewal-dark-panel-v1")
    parser.add_argument("--retry",type=Path,default=experiment.ROOT/"artifacts/garden-renewal-finish-retry-v1")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--output",type=Path)
    target.add_argument("--check",type=Path)
    args = parser.parse_args()
    roots = args.panel.resolve(),args.retry.resolve()
    if args.output:
        require(not args.output.exists() and not any(args.output.resolve().is_relative_to(r) for r in roots),
                "choose fresh output outside frozen parents")
    result = verify(*roots)
    if args.output:
        experiment.write_json(args.output,result)
    else:
        require(experiment.read_json(args.check) == result, "portable capacity audit differs")
    print("Verified full-night capacity shadow audit; zero new experimental native calls",flush=True)


if __name__ == "__main__":
    main()
