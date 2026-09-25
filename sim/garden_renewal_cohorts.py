#!/usr/bin/env python3
"""Offline attribution of frozen old-RR renewal outcomes; no native execution."""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import shutil
import time

import garden_renewal_return as previous
import garden_renewal_stalls as lifetimes

experiment, require, pilot = previous.experiment, previous.require, previous.pilot
scoring, mixed = previous.scoring, previous.mixed
rolling, fitness = scoring.rolling, pilot.fitness
descendants = fitness.descendants
DAY, STEP = pilot.DAY, fitness.STEP
RULE = "garden-renewal-cohorts-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-cohorts-protocol.md"
BASELINE_SHA = "7b20a1dc42516b6d5c13cb2e5335fea9133cb6084c7811049c3d8c263d3c2b98"
MODELS, PAIRS = previous.MODELS, previous.PAIRS
CELL = "rr"
GROUP_FIELDS = ("count", "positive_count", "available_ticks", "live_ticks", "timing_removed_ticks",
                "natural_loss_ticks", "patch_loss_ticks")


def settings():
    return {"rule": RULE, "source_manifest_sha256": BASELINE_SHA, "native_calls": 0,
            "models": [dict(m.__dict__) for m in MODELS], "cell": CELL,
            "conditions": [list(c) for c in previous.conditions(CELL)],
            "periods": [list(p) for p in rolling.PERIODS], "credit_age_ticks": rolling.CREDIT_AGE,
            "histories": 40, "world_periods": 160, "daily_days": [0,192],
            "examples": "per R1/R2 W/N: max/min minimum delta and min v2 late delta; lexical ties",
            "role": "explanatory accounting on inspected evidence; not causal or a new selector"}


def copies():
    return {"input/return-results.json": "results.json", **{
        previous.ledger(m,CELL,k): previous.ledger(m,CELL,k)
        for m in MODELS for k,*_ in previous.conditions(CELL)}}


def family_ids(plants):
    families = {}
    for p in sorted(plants, key=lambda p: (p["birth_tick"],p["id"])):
        require(p["species"] in range(len(pilot.SPECIES)), "unknown species")
        families[p["id"]] = families[p["parent"]] if p["parent"] else p["id"]
    return families


def credit_group(rows, width):
    require(width > 0 and width <= rolling.CREDIT_AGE and width % STEP == 0, "invalid period width")
    result = dict.fromkeys(GROUP_FIELDS,0)
    for row in rows:
        available, live, lost = (row[k] for k in ("available_ticks","live_ticks","death_lost_ticks"))
        require(all(type(v) is int and v >= 0 and v % STEP == 0 for v in (available,live,lost)) and
                available <= width and live+lost == available, "invalid child credit accounting")
        require(not lost or row["death_tick"] is not None, "unexplained death loss")
        result["count"] += 1
        result["positive_count"] += live > 0
        result["available_ticks"] += available
        result["live_ticks"] += live
        result["timing_removed_ticks"] += width-available
        result["patch_loss_ticks" if row["environmental_death"] else "natural_loss_ticks"] += lost
    require(result["live_ticks"] == result["count"]*width-result["timing_removed_ticks"]-
            result["natural_loss_ticks"]-result["patch_loss_ticks"], "credit group does not reconcile")
    return result


def add_groups(groups):
    return {k: sum(g[k] for g in groups) for k in GROUP_FIELDS}


def delta_group(a,b,width):
    result = {k:b[k]-a[k] for k in GROUP_FIELDS}
    result["count_width_ticks"] = result["count"]*width
    require(result["live_ticks"] == result["count_width_ticks"]-result["timing_removed_ticks"]-
            result["natural_loss_ticks"]-result["patch_loss_ticks"], "paired attribution differs")
    return result


def seed_funnels(plants, seeds, start, end):
    records = {p["id"]:p for p in plants}
    fields = ("purchases","germinated","expired","pending","confirmed","natural_failure",
              "patch_censored","horizon_censored","qualifying")
    groups = {"all":dict.fromkeys(fields,0), **{n:dict.fromkeys(fields,0) for n in pilot.SPECIES},
              **{n:dict.fromkeys(fields,0) for n in lifetimes.PARENT_CLASSES}}
    for seed in seeds:
        if not start < seed["birth_tick"] <= end:
            continue
        p = records[seed["parent"]]
        names = ("all",pilot.SPECIES[p["species"]],lifetimes.parent_class(p,seed["birth_tick"]))
        require(seed["outcome"] != "pending" and seed["end_tick"] <= end+fitness.FOLLOWUP,
                "purchase cohort lacks complete follow-up")
        for name in names:
            groups[name]["purchases"] += 1
            groups[name][seed["outcome"]] += 1
        if seed["child_id"] is not None:
            child = records[seed["child_id"]]
            status = descendants.confirmation(child,child["birth_tick"],end+fitness.FOLLOWUP).replace("-","_")
            for name in names:
                groups[name][status] += 1
                groups[name]["qualifying"] += lifetimes.qualifies(child,records,end+fitness.FOLLOWUP)
    for g in groups.values():
        require(g["purchases"] == g["germinated"]+g["expired"] and g["germinated"] ==
                g["confirmed"]+g["natural_failure"]+g["patch_censored"] and not g["horizon_censored"],
                "purchase funnel does not reconcile")
    for names in (pilot.SPECIES,lifetimes.PARENT_CLASSES):
        require(groups["all"] == {f:sum(groups[n][f] for n in names) for f in fields}, "funnel partition differs")
    return groups


def period_audit(trial, block, families):
    start,end = block["window_ticks"]
    plants,seeds = fitness.project(trial["lineages"],trial["seeds"],start,end+fitness.FOLLOWUP,trial["start"],trial["stop"])
    records = {p["id"]:p for p in plants}
    score = fitness.world(plants,seeds,start,end,end+fitness.FOLLOWUP)
    require(score["key"] == block["v2_key"] and rolling.credit(plants,start,end) == block["rolling"], "period projection differs")
    cohort = mixed.validation.cohorts(plants,seeds,score)
    rows = []
    for row in block["rolling"]["children"]:
        p = records[row["id"]]
        rows.append({**row, **{k:p[k] for k in ("birth_tick","death_tick","environmental_death","generation","column")},
                     "species":pilot.SPECIES[p["species"]],"founder_family":families[p["id"]]})
    width = end-start
    groups = {name:credit_group([r for r in rows if r["carry_in"] == carry],width)
              for name,carry in (("fresh",False),("carry_in",True))}
    all_credit = credit_group(rows,width)
    species = {n:credit_group([r for r in rows if r["species"] == n],width) for n in pilot.SPECIES}
    require(add_groups(groups.values()) == all_credit == add_groups(species.values()) and
            all_credit["live_ticks"] == block["rolling"]["ticks"] and
            groups["fresh"]["live_ticks"] == score["key"][1] == cohort["live_ticks"] and
            groups["fresh"]["count"] == cohort["credited_children"], "credit/cohort totals differ")
    funnels = seed_funnels(plants,seeds,start,end)
    require({k:v for k,v in funnels["all"].items() if k != "qualifying"} == cohort["purchase_cohort_followed_to_stop"],
            "purchase cohort differs from existing validation")
    return {"days":block["days"],"width_ticks":width,"terminal_tier":block["v2_key"][0],
            "groups":groups,"all_credit":all_credit,"by_species":species,"credit_children":rows,
            "confirmation_cohort":cohort,"purchase_funnels":funnels}


def census(trial,tick,families):
    living = [p for p in trial["lineages"] if lifetimes.alive(p,tick)]
    records = {p["id"]:p for p in trial["lineages"]}
    pending = [s for s in trial["seeds"] if s["birth_tick"] <= tick and (s["end_tick"] is None or s["end_tick"] > tick)]
    return {"tick":tick,"living":len(living),
            "species":dict(Counter(pilot.SPECIES[p["species"]] for p in living)),
            "families":dict(Counter(str(families[p["id"]]) for p in living)),
            "pending_by_species":dict(Counter(pilot.SPECIES[records[s["parent"]]["species"]] for s in pending)),
            "qualifying_young_alive":sum(lifetimes.qualifies(p,records,tick) and
                tick < p["birth_tick"]+DAY+rolling.CREDIT_AGE for p in living),
            "qualifying_confirmations_today":[p["id"] for p in trial["lineages"] if
                tick-DAY < p["birth_tick"]+DAY <= tick and lifetimes.qualifies(p,records,tick)]}


def species_turnover(trial,families):
    plants = trial["lineages"]
    ticks = sorted({0,trial["stop"], *[p["birth_tick"] for p in plants],
                    *[p["death_tick"] for p in plants if p["death_tick"] is not None]})
    snapshots = [census(trial,t,families) for t in ticks]
    result = {}
    for species in pilot.SPECIES:
        own = [p for p in plants if pilot.SPECIES[p["species"]] == species]
        gaps = []
        for before,after in zip(snapshots,snapshots[1:]):
            was,now = before["species"].get(species,0),after["species"].get(species,0)
            if was and not now:
                deaths = [p for p in own if p["death_tick"] == after["tick"]]
                require(bool(deaths), "living-species loss without recorded death")
                gaps.append({"loss_tick":after["tick"],"pending_seeds_at_loss":after["pending_by_species"].get(species,0),
                    "last_deaths":[{"id":p["id"],"cause":"patch" if p["environmental_death"] else "natural"} for p in deaths],
                    "recovery_tick":None})
            elif not was and now and gaps:
                require(gaps[-1]["recovery_tick"] is None, "duplicate recovery")
                gaps[-1]["recovery_tick"] = after["tick"]
        result[species] = {"initial_living":snapshots[0]["species"].get(species,0),
            "terminal_living":snapshots[-1]["species"].get(species,0),
            "terminal_pending_seeds":snapshots[-1]["pending_by_species"].get(species,0),
            "births":sum(bool(p["parent"]) for p in own),
            "confirmed_births":sum(bool(p["parent"]) and lifetimes.confirmed(p,trial["stop"]) for p in own),
            "natural_deaths":sum(p["death_tick"] is not None and not p["environmental_death"] for p in own),
            "patch_deaths":sum(p["environmental_death"] for p in own),"living_absences":gaps}
    return result


def audit_trial(trial,annotated):
    families = family_ids(trial["lineages"])
    history = rolling.history(trial["lineages"],trial["seeds"],trial["start"],trial["stop"])
    require(history == annotated["renewal_history"], "changed saved history")
    daily = [census(trial,day*DAY,families) for day in range(193)]
    require(daily[-1]["species"] == annotated["terminal_species"] and
            daily[-1]["families"] == annotated["terminal_families"] and
            daily[-1]["living"] == annotated["final"]["living"], "endpoint census differs")
    return {"periods":[period_audit(trial,b,families) for b in history["blocks"]],
            "daily":daily,"species_turnover":species_turnover(trial,families)}


def minimum_bridge(a,b):
    require(len(a) == len(b) == len(rolling.PERIODS) and
            all(type(v) is int and v >= 0 for v in (*a,*b)), "invalid period panel")
    i,j = a.index(min(a)),b.index(min(b))
    delta = min(b)-min(a)
    left,right = b[i]-a[i],b[j]-a[j]
    candidate_penalty,control_penalty = b[i]-b[j],a[j]-a[i]
    require(delta == left-candidate_penalty == right+control_penalty, "minimum bridge differs")
    return {"minimum_delta":delta,"control_minimum_periods":[list(p) for p,v in zip(rolling.PERIODS,a) if v == min(a)],
            "candidate_minimum_periods":[list(p) for p,v in zip(rolling.PERIODS,b) if v == min(b)],
            "at_control_minimum":{"period":list(rolling.PERIODS[i]),"same_period_delta":left,"candidate_switch_penalty":candidate_penalty},
            "at_candidate_minimum":{"period":list(rolling.PERIODS[j]),"same_period_delta":right,"control_switch_penalty":control_penalty}}


def paired_case(a,b):
    periods = []
    for pa,pb in zip(a["periods"],b["periods"],strict=True):
        require(pa["days"] == pb["days"] and pa["width_ticks"] == pb["width_ticks"], "mismatched audit periods")
        periods.append({"days":pa["days"],"groups":{g:delta_group(pa["groups"][g],pb["groups"][g],pa["width_ticks"])
                                                  for g in ("fresh","carry_in")},
                        "live_delta":pb["all_credit"]["live_ticks"]-pa["all_credit"]["live_ticks"]})
    bridge = minimum_bridge([p["all_credit"]["live_ticks"] for p in a["periods"]],
                            [p["all_credit"]["live_ticks"] for p in b["periods"]])
    return {"minimum_bridge":bridge,"period_deltas":periods}


def select_examples(comparisons):
    selected = []
    for replica in ("r1","r2"):
        name = f"{replica}-w-vs-n"
        comp = comparisons[name]
        for label,view,field,sign in (("minimum-gain","renewal","minimum_delta",-1),
                                      ("minimum-loss","renewal","minimum_delta",1),
                                      ("late-credit-loss","v2","renewal_delta",1)):
            row = min(comp[view]["overall"]["pairs"],key=lambda p:(sign*p[field],p["condition"]))
            selected.append({"pair":name,"label":label,"condition":row["condition"],"score_delta":row[field]})
    return selected


def model_totals(worlds):
    periods = []
    for i,days in enumerate(rolling.PERIODS):
        rows = [w["periods"][i] for w in worlds.values()]
        periods.append({"days":list(days),"groups":{g:add_groups([r["groups"][g] for r in rows]) for g in ("fresh","carry_in")},
            "by_species":{s:add_groups([r["by_species"][s] for r in rows]) for s in pilot.SPECIES},
            "purchases":{name:dict(sum((Counter(r["purchase_funnels"][name]) for r in rows),Counter()))
                         for name in ("all",*pilot.SPECIES,*lifetimes.PARENT_CLASSES)}})
    return {"periods":periods,"single_species_endpoints":sum(len(w["daily"][-1]["species"]) == 1 for w in worlds.values()),
            "single_family_endpoints":sum(len(w["daily"][-1]["families"]) == 1 for w in worlds.values())}


def analyze(root):
    saved = experiment.read_json(root/"input/return-results.json")
    require(saved["rule"] == previous.RULE and saved["settings"] == previous.settings(), "wrong return contract")
    models = {}
    for model in MODELS:
        worlds = {}
        source = saved["models"][model.name]["cells"][CELL]
        for key,_,seed,patch in previous.conditions(CELL):
            trial = experiment.read_json(root/previous.ledger(model,CELL,key))
            annotated = previous.checked_trial(trial,model,seed,patch)
            require(annotated == source["worlds"][key], "source annotation differs")
            worlds[key] = audit_trial(trial,annotated)
            require(worlds[key]["periods"][-1]["confirmation_cohort"] == source["cohorts"]["worlds"][key],
                    "native late cohort differs")
        models[model.name] = {"model_crc32":model.crc,"worlds":worlds,"totals":model_totals(worlds),"views":source["views"]}
    comparisons = {n:saved["comparisons"][n][CELL] for n,_,_ in PAIRS}
    pairs = {}
    for name,a,b in PAIRS:
        cases = {k:paired_case(models[a]["worlds"][k],models[b]["worlds"][k]) for k,*_ in previous.conditions(CELL)}
        expected = {p["condition"]:p["minimum_delta"] for p in comparisons[name]["renewal"]["overall"]["pairs"]}
        require({k:v["minimum_bridge"]["minimum_delta"] for k,v in cases.items()} == expected, "paired score delta differs")
        deltas = [{"days":list(days),"groups":{g:delta_group(models[a]["totals"]["periods"][i]["groups"][g],
            models[b]["totals"]["periods"][i]["groups"][g],(days[1]-days[0])*DAY) for g in ("fresh","carry_in")}}
            for i,days in enumerate(rolling.PERIODS)]
        pairs[name] = {"control":a,"candidate":b,"cases":cases,"period_deltas":deltas}
    return {"rule":RULE,"settings":settings(),"models":models,"paired_audits":pairs,
            "saved_comparisons":comparisons,"selected_examples":select_examples(comparisons)}


def check_inputs(root):
    require(experiment.digest(root/"input/return-manifest.json") == BASELINE_SHA,"changed pinned input manifest")
    source = experiment.read_json(root/"input/return-manifest.json")
    for dest,src in copies().items():
        require(experiment.digest(root/dest) == source["artifacts"][src],"changed copied input")
    require(experiment.read_json(root/"input/settings.json") == settings(),"changed audit contract")


def verify(root):
    manifest = experiment.read_json(root/"manifest.json")
    require(manifest["rule"] == RULE and manifest["status"] == "complete" and manifest["copied"] == copies(),"wrong/incomplete audit bundle")
    require(set(manifest["artifacts"]) == {str(p.relative_to(root)) for p in root.rglob("*")
            if p.is_file() and p != root/"manifest.json"},"extra/missing audit artifacts")
    for name in manifest["artifacts"]:
        pilot.gallery.artifact(root,manifest,name)
    check_inputs(root)
    started = experiment.read_json(root/"started.json")
    require(started["sources"] == manifest["sources"] and all(experiment.digest(root/n) == sha for n,sha in started["frozen"].items()) and
            experiment.digest(root/"input/protocol.md") == manifest["sources"][PROTOCOL],"audit freeze differs")
    result = analyze(root)
    require(result == experiment.read_json(root/"results.json"),"offline reanalysis differs")
    print("Verified 40 old-RR histories, 160 period attributions and species timelines; zero native calls",flush=True)
    return result


def collect(baseline,output):
    require(not output.exists() and output.is_relative_to(experiment.ROOT/"artifacts") and not output.is_relative_to(baseline),
            "choose fresh separate audit output")
    require(experiment.digest(baseline/"manifest.json") == BASELINE_SHA,"wrong return input")
    previous.verify(baseline)
    sources = experiment.source_files()
    output.mkdir(parents=True)
    experiment.snapshot_sources(output,sources)
    for dest,src in copies().items():
        (output/dest).parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(baseline/src,output/dest)
    shutil.copy2(baseline/"manifest.json",output/"input/return-manifest.json")
    shutil.copy2(experiment.ROOT/PROTOCOL,output/"input/protocol.md")
    experiment.write_json(output/"input/settings.json",settings())
    check_inputs(output)
    frozen = {str(p.relative_to(output)):experiment.digest(p) for p in output.rglob("*") if p.is_file()}
    experiment.write_json(output/"started.json",{"rule":RULE,"sources":sources,"frozen":frozen})
    begin = time.monotonic()
    try:
        result = analyze(output)
        require(result == analyze(output),"offline repeat differs")
        require(experiment.source_files() == sources and all(experiment.digest(output/n) == sha for n,sha in frozen.items()),
                "source/input changed during audit")
        experiment.write_json(output/"results.json",result)
        experiment.write_json(output/"timings.json",{"analysis_and_repeat_seconds":time.monotonic()-begin,"native_calls":0})
        artifacts = {str(p.relative_to(output)):experiment.digest(p) for p in output.rglob("*") if p.is_file()}
        experiment.write_json(output/"manifest.json",{"rule":RULE,"status":"complete","sources":sources,"copied":copies(),
            "artifacts":artifacts,"artifact_bytes":sum((output/n).stat().st_size for n in artifacts)})
    except BaseException as error:
        experiment.write_json(output/"failure.json",{"error":str(error)})
        raise
    verify(output)


def export(root,target,check=False):
    require(not target.is_relative_to(root),"cannot export into frozen audit")
    result = verify(root)
    value = {**result,"manifest_sha256":experiment.digest(root/"manifest.json"),"timing":experiment.read_json(root/"timings.json")}
    if not check:
        experiment.write_json(target,value)
    require(experiment.read_json(target) == value,"portable audit differs")
    print("Portable cohort attribution matches verified evidence; zero native calls",flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline",type=Path,default=experiment.ROOT/"artifacts/garden-renewal-return-v1")
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--verify",action="store_true")
    parser.add_argument("--export",type=Path)
    parser.add_argument("--check-export",type=Path)
    args = parser.parse_args()
    require(not (args.export and args.check_export) and (args.verify or not (args.export or args.check_export)),"export requires verify")
    if args.export or args.check_export:
        export(args.output.resolve(),(args.export or args.check_export).resolve(),bool(args.check_export))
    elif args.verify:
        verify(args.output.resolve())
    else:
        collect(args.baseline.resolve(),args.output.resolve())


if __name__ == "__main__":
    main()
