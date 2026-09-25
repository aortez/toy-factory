#!/usr/bin/env python3
"""Frozen focused/full-panel drainage comparisons of host growth policies."""
from __future__ import annotations

import argparse
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import shutil
import tempfile
import zlib

import garden_diversity as diversity
import garden_drainage as drainage
import garden_experiments as experiment
import garden_establishment as establishment
from garden_resources import budget, checkpoint, require
from garden_gallery import contact_sheet, rgb565be_to_rgb888, write_png

ADAPTIVE = "adaptive-no-night-growth"
RESERVE = "neural-reserve-growth"
POLICIES = {"neural":experiment.NIGHT_POLICY, "adaptive":ADAPTIVE, "reserve":RESERVE}
SEEDS = ("b61837dc", "9c530b07")
DAY, HORIZON = diversity.DAY, diversity.HORIZON


def identity(row, setting, policy, capacity=512):
    require(setting in ("off","on") and policy in POLICIES,"unknown diagnostic setting/policy")
    diversity.maintenance.check_identity(row, "selective", capacity,
        drainage.RULE if setting == "on" else None, POLICIES[policy] if policy != "neural" else None)


def check_reserve_bid(row):
    """Independent arithmetic audit; not a second controller used for simulation."""
    r=row["reserve"]
    require(r["rule"]=="energy-reserve-v1" and 0<=r["species"]<3 and
        0<=r["income"]<=255 and r["maintenance_phase"]==row["sun_phase"]%4,"wrong reserve input")
    pre=0 if row["sun_phase"]>=128 else row["probe_original_action"]
    expected={k:0 for k in ("post_nodes","growth_cost","maintenance_cost","daylight_steps",
        "daylight_credit","daylight_upkeep","night_upkeep","projected_sunset")}
    expected["allowed"]=True
    if pre:
        nodes=r["nodes"]+int(pre==1 and any(c["flags"]&2 for c in row["candidates"]))
        cost=(9,8,7)[r["species"]]-int(r["vigor"]>0)
        m=max(1,(nodes+7)//8)
        d=128-row["sun_phase"]
        credit=r["income"]*(d-1)//2
        day_cost=(d+r["maintenance_phase"])//4*m
        sunset=min(256,row["energy"]-cost+credit-day_cost)
        expected.update(post_nodes=nodes,growth_cost=cost,maintenance_cost=m,daylight_steps=d,
            daylight_credit=credit,daylight_upkeep=day_cost,night_upkeep=32*m,projected_sunset=sunset,
            allowed=row["energy"]-cost>=m and sunset>=32*m)
    require(all(r[k]==v for k,v in expected.items()),"reserve forecast mismatch")
    require(row["action"]==(pre if expected["allowed"] else 0) and row["priority"]==r["priority"],
        "reserve action/priority mismatch")
    return not expected["allowed"]


def diagnose(path, setting, policy, schedule, horizon, capacity=512):
    """Read full traces; budgets cover live ordinary steps, never erased death income."""
    prior, records, bids, leaf_bids, tails = {}, {}, {}, {}, {}
    daily, windows, boundaries = {}, {}, []
    previous = None
    event = None
    last_tick = -15
    checked = Counter()
    planned = diversity.disturbance.schedule(schedule, horizon)
    with (gzip.open(path, "rt") if path.suffix == ".gz" else path.open()) as stream:
        for line in stream:
            row = json.loads(line)
            kind = row["type"]
            if kind in ("bid", "leaf-bid"):
                require(event is None and row["tick"] == last_tick + 15, "misplaced decision")
                key = row["id"]
                if kind == "bid":
                    require(row.get("probe") == experiment.NIGHT_PROBE, "missing night veto")
                    require(row["sun_phase"] == (64 + row["tick"]//15) % 256, "wrong bid sun")
                    original = row["probe_original_action"]
                    require(original in (0,1,2),"incorrect original action")
                    if policy=="reserve":
                        checked["reserve_checked_bids"] += 1
                        checked["reserve_vetoed_bids"] += check_reserve_bid(row)
                    else:
                        require("reserve" not in row and row["action"] ==
                            (0 if row["sun_phase"] >= 128 else original), "incorrect night veto")
                    bids.setdefault(key, []).append(row)
                else:
                    require(key not in leaf_bids, "duplicate leaf bid")
                    leaf_bids[key] = row
                continue
            if kind == "disturbance":
                require(event is None and len(boundaries) < len(planned) and
                    all(row[k] == v for k,v in planned[len(boundaries)].items()), "wrong event")
                event = row
                continue
            require(kind == "world", "unexpected record")
            identity(row, setting, policy, capacity)
            tick = row["tick"]
            if event is not None:
                diversity.disturbance.validate_boundary(previous, row, event)
                boundaries.append(event)
                for key in event["killed"]:
                    records[key].update(death_tick=tick, death_flags=1, environmental=True)
                prior = {p["id"]:p for p in row["plants"]}
                previous, event = row, None
                if tick % DAY == 0:
                    daily[str(tick)] = row["hash"]
                continue
            require(tick == last_tick + 15 and tick <= horizon, "missing ecology step")
            require(row["sun_phase"] == (64 + tick//15) % 256, "wrong sun phase")
            current = {p["id"]:p for p in row["plants"]}
            require(len(current) == len(row["plants"]), "duplicate plant")
            values = Counter()
            for key,p in current.items():
                old = prior.get(key)
                if key not in records:
                    require(not p["dead"] and bool(p["parent"]) == bool(tick), "invalid birth")
                    records[key] = {k:p[k] for k in ("id","parent","species","generation","genome")}
                    records[key].update(birth_tick=tick, death_tick=None, death_flags=None,
                        budget=Counter(), first_day=Counter(), night=Counter(), marks={})
                    tails[key] = deque(maxlen=256)
                r = records[key]
                if p["dead"]:
                    if r["death_tick"] is None:
                        require(p["flags"] & 6, "unmarked natural death")
                        r.update(death_tick=tick, death_flags=p["flags"], death=checkpoint(row,p))
                        checked["terminal_steps_not_reconstructed"] += 1
                    require(key not in bids and key not in leaf_bids, "dead plant decision")
                    continue
                require(r["death_tick"] is None, "plant revived")
                growth = bids.pop(key, [])
                leaf = leaf_bids.pop(key, None)
                delta = p["agent"]["decisions"] - (old["agent"]["decisions"] if old else 0)
                require(delta == bool(growth), "unexplained committed decision")
                if growth:
                    winner = max(growth, key=lambda b:b["priority"])
                    require(all(winner[k] == p["agent"]["last_"+k]
                        for k in ("priority","action","tissue","x","y")), "winner mismatch")
                    checked["committed_growth_decisions"] += 1
                    checked["vetoed_bids"] += sum(b["action"] != b["probe_original_action"] for b in growth)
                    if policy=="reserve" and not winner["reserve"]["allowed"]:
                        checked["reserve_rejected_winners"] += 1
                        checked["reserve_blocked_paid_alternatives"] += any(b["action"]!=0 for b in growth)
                renewal = p["leaf"]["renewals"] - (old["leaf"]["renewals"] if old else 0)
                observations = p["leaf"]["observations"] - (old["leaf"]["observations"] if old else 0)
                require(observations == (leaf is not None), "missing leaf observation")
                require(not renewal or (leaf is not None and leaf["action"] == 1 and not growth),
                        "unexplained renewal")
                marks = r["marks"]
                for name,condition in (("water_shortage",p["flags"] & 4),
                        ("energy_shortage",p["flags"] & 2),("active_leaf",p["active_leaves"]),
                        ("first_sunset",row["sun_phase"]==128),("first_dawn",row["sun_phase"]==0)):
                    if condition and name not in marks:
                        marks[name] = checkpoint(row,p)
                amount = budget(old,p,tick) if tick else Counter()
                if tick:
                    checked["live_steps"] += 1
                    r["budget"].update(amount)
                    if tick-r["birth_tick"] <= DAY:
                        r["first_day"].update(amount)
                    if row["sun_phase"] >= 128:
                        r["night"].update(amount)
                    values.update(amount)
                    values.update(living_samples=1, energy=p["energy"], water=p["water"],
                        energy_shortage=bool(p["flags"] & 2), water_shortage=bool(p["flags"] & 4),
                        tipless=p["tips"]==0)
                sample = {**checkpoint(row,p), "budget":dict(amount),
                    "growth":None if not growth else {k:winner[k] for k in ("action","tissue","x","y","depth")},
                    "leaf":leaf}
                if policy=="reserve":
                    sample["reserve"]=winner["reserve"] if growth else None
                tails[key].append(sample)
                r["last_living"] = checkpoint(row,p)
            require(not bids and not leaf_bids, "orphan decision")
            if tick:
                windows.setdefault(str((tick-1)//DAY+1),Counter()).update(values)
            if tick % DAY == 0:
                daily[str(tick)] = row["hash"]
            previous, prior, last_tick = row, current, tick
    require(last_tick == horizon and event is None and len(boundaries)==len(planned), "truncated trace")
    return {"checked":checked,"daily":daily,"windows":windows,"events":boundaries,
        "lineages":[{**r,"last_day_samples":list(tails[k])} for k,r in records.items()]}


def panel_cases(manifest, cases, panel):
    """Validate the complete old panel before selecting either diagnostic scope."""
    require(panel in ("focused", "full"), "invalid panel")
    require(manifest["status"] == "complete" and manifest["kind"] == "garden-bottom-drainage"
        and manifest["node_capacity"] in (256,512) and manifest["horizon"] == HORIZON
        and manifest["rule"] == drainage.RULE, "wrong baseline")
    expected = {(scenario,seed,arm) for scenario in experiment.SCENARIOS
        for seed in experiment.trial_seeds(0x6d617463,8) for arm in diversity.SCHEDULES}
    require(len(cases) == len(expected) and
        {(c["scenario"],c["seed"],c["arm"]) for c in cases} == expected, "incomplete panel")
    worlds = {(c["id"],c["scenario"],c["seed"]) for c in cases}
    require(len(worlds) == 16 and len({w[0] for w in worlds}) == 16 and
        all(isinstance(w[0],str) and w[0].isascii() and w[0].isdigit() for w in worlds),
        "duplicate or invalid world identity")
    selected = cases if panel == "full" else [c for c in cases
        if c["scenario"] == "rainfed" and c["seed"] in SEEDS]
    return sorted(selected, key=lambda c:(int(c["id"]),list(diversity.SCHEDULES).index(c["arm"])))


def frame_groups(results, worlds):
    return [[f for c in results if (c["scenario"],c["seed"]) == world and c["arm"] == arm
        for f in c["frames"]] for world in worlds for arm in diversity.SCHEDULES]


def save_gallery(output, results, panel):
    if panel == "focused":
        groups = frame_groups(results, [("rainfed",seed) for seed in SEEDS])
        return {"groups":groups,"sheet":contact_sheet(output,groups)}
    worlds = sorted({(c["scenario"],c["seed"]) for c in results})
    sheets = []
    for scenario,seed in worlds:
        groups = frame_groups(results, [(scenario,seed)])
        require(all(len(g) == 4 for g in groups), "incomplete frame comparison")
        metadata = contact_sheet(output,groups)
        path = f"sheets/{scenario}-{seed}.png"
        (output/"contact-sheet.png").rename(output/path)
        sheets.append({"scenario":scenario,"seed":seed,"path":path,**metadata})
    review = frame_groups(results, [(s,diversity.maintenance.FRAME_SEED) for s in sorted(experiment.SCENARIOS)])
    return {"groups":frame_groups(results,worlds),"sheets":sheets,
        "review_seed":diversity.maintenance.FRAME_SEED,"sheet":contact_sheet(output,review)}


def collect(baseline, off_build, on_build, output, jobs, reference="adaptive", panel="focused"):
    require(reference in ("adaptive","reserve"),"invalid reference policy")
    baseline,off_build,on_build,output = [p.resolve() for p in (baseline,off_build,on_build,output)]
    old_manifest=experiment.read_json(baseline/"manifest.json")
    old_cases=experiment.read_json(establishment.verified(baseline,old_manifest,"cases.json"))
    cases=panel_cases(old_manifest,old_cases,panel)
    capacity=old_manifest["node_capacity"]
    require(not output.is_relative_to(experiment.ROOT) or output.is_relative_to(experiment.ROOT/"artifacts"),"unsafe output")
    output.mkdir(parents=True,exist_ok=False)
    for folder in ("input","bin","traces","analyses","frames","sheets"):
        (output/folder).mkdir()
    sources=experiment.source_files()
    experiment.snapshot_sources(output,sources)
    shutil.copy2(baseline/"manifest.json",output/"input/manifest.json")
    shutil.copy2(establishment.verified(baseline,old_manifest,"model.tgm"),output/"model.tgm")
    require(experiment.digest(output/"model.tgm")==diversity.maintenance.MODEL_SHA,"wrong frozen model")
    for c in cases:
        name=f"{c['id']}.{c['arm']}"
        for setting,folder in (("off","input"),("on","analyses")):
            shutil.copy2(establishment.verified(baseline,old_manifest,f"{folder}/{name}.population.json"),
                output/f"input/{setting}.{name}.json")
    for setting,build in (("off",off_build),("on",on_build)):
        for tool in ("inspect","replay"):
            shutil.copy2(build/f"toy-factory-garden-{tool}",output/f"bin/{setting}-{tool}")
        shutil.copy2(build/"CMakeCache.txt",output/f"{setting}-build-cache.txt")
    frozen={str(p.relative_to(output)):experiment.digest(p) for p in output.rglob("*") if p.is_file()}
    record={"kind":"garden-drainage-policy","status":"started","horizon":HORIZON,
        "reference_policy":POLICIES[reference],"panel":panel,"node_capacity":capacity,
        "expected_runs":len(cases)*4,
        "source_sha256":sources,"baseline_manifest_sha256":experiment.digest(baseline/"manifest.json")}
    experiment.write_json(output/"started.json",record)

    def run(job):
        c,setting,policy=job
        name=f"{c['id']}.{c['arm']}.{setting}.{policy}"
        rule=drainage.RULE if setting=="on" else None
        schedule=diversity.SCHEDULES[c["arm"]]
        growth=POLICIES[policy]
        args=["-" if policy=="adaptive" else "model.tgm",c["scenario"],growth,"0x"+c["seed"],"--leaf-policy","selective"]
        if schedule:
            args += ["--disturbance-seed",str(schedule)]
        cmd=[f"bin/{setting}-inspect",*args,"--population","--ticks",str(HORIZON)]
        path=output/f"traces/{name}.population.gz"
        bounds=diversity.disturbance.capture(cmd,path,output,"world",schedule,HORIZON)
        a=diversity.analyze(path,bounds,capacity,HORIZON,schedule,rule,growth if policy!="neural" else None)
        commands=[cmd]
        if policy=="neural":
            before=experiment.read_json(output/f"input/{setting}.{c['id']}.{c['arm']}.json")
            require(a==before,"neural baseline changed")
        frames=[]
        for day in (64,128,192):
            cmd=[f"bin/{setting}-replay",*args,"--ticks",str(day*DAY)]
            frame=f"frames/{name}.rgb565"
            if day==192:
                cmd += ["--framebuffer",frame]
            result_path=output/f"frames/{name}.{day}.json"
            experiment.command_run(cmd,result_path,output,300)
            r=experiment.read_json(result_path)
            require(r["hash"]==a["daily"][day]["hash"] and r["policy"]==growth
                and r["model_crc32"]==(None if policy=="adaptive" else "dc5e849d")
                and r.get("drainage_rule")==rule and r.get("node_capacity",256)==capacity
                and r["scenario"]==c["scenario"] and r["seed"]==c["seed"] and r["tick"]==day*DAY
                and r.get("leaf_environment")==diversity.maintenance.ENVIRONMENT
                and r.get("leaf_policy")=="selective","replay identity/hash mismatch")
            if day==192:
                raw=(output/frame).read_bytes()
                require(len(raw)==115200 and r["framebuffer_crc32"]==f"{zlib.crc32(raw):08x}","frame CRC mismatch")
                write_png(output/f"frames/{name}.png",240,240,rgb565be_to_rgb888(raw))
                frames.append({"id":name,"tick":day*DAY,"framebuffer":frame})
            commands.append(cmd)
        if panel=="focused" and c["seed"]==SEEDS[0] and c["arm"]=="fresh-2":
            cmd=[f"bin/{setting}-inspect",*args,"--ecology","--ticks",str(128*DAY)]
            with tempfile.TemporaryDirectory(prefix="garden-policy-detail-") as temp:
                raw=Path(temp)/"trace.jsonl"
                experiment.command_run(cmd,raw,output,300)
                details=diagnose(raw,setting,policy,schedule,128*DAY,capacity)
                require(all(details["daily"][str(d*DAY)]==a["daily"][d]["hash"] for d in range(129)),"detailed replay changed")
                experiment.compress(raw,output/f"traces/{name}.detail.gz")
            experiment.write_json(output/f"analyses/{name}.detail.json",details)
            commands.append(cmd)
        experiment.write_json(output/f"analyses/{name}.population.json",a)
        experiment.write_json(output/f"analyses/{name}.boundaries.json",bounds)
        print(f"{name}: living={a['daily'][-1]['living']}, births={a['daily'][-1]['births']}, extinct={a['first_observed_extinction_tick']}",flush=True)
        return {**{k:c[k] for k in ("id","scenario","seed","arm")},"setting":setting,"policy":policy,
            "name":name,"commands":commands,"frames":frames,"milestones":a["milestones"],
            "first_observed_extinction_tick":a["first_observed_extinction_tick"],"soil_final":a["final"]["soil"]["water"]}
    try:
        jobs_list=[(c,setting,policy) for c in cases for setting in ("off","on") for policy in ("neural",reference)]
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            results=list(pool.map(run,jobs_list))
        experiment.write_json(output/"cases.json",results)
        experiment.write_json(output/"frames.json",save_gallery(output,results,panel))
        require(experiment.source_files()==sources,"source changed during collection")
        require(all(experiment.digest(output/name)==sha for name,sha in frozen.items()),"frozen input changed")
        record.update(status="complete",artifacts={str(p.relative_to(output)):experiment.digest(p) for p in output.rglob("*") if p.is_file()})
        experiment.write_json(output/"manifest.json",record)
        print(f"Complete {output}; manifest sha256={experiment.digest(output/'manifest.json')}",flush=True)
    except BaseException as error:
        experiment.write_json(output/"failure.json",{"error":str(error)})
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("baseline","off-build","on-build","output"):
        parser.add_argument("--"+name,type=Path,required=True)
    parser.add_argument("--jobs",type=int,choices=(1,2,4),default=4)
    parser.add_argument("--reference",choices=("adaptive","reserve"),default="adaptive")
    parser.add_argument("--panel",choices=("focused","full"),default="focused")
    args=parser.parse_args()
    collect(args.baseline,args.off_build,args.on_build,args.output,args.jobs,args.reference,args.panel)


if __name__=="__main__":
    main()
