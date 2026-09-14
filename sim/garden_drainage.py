#!/usr/bin/env python3
"""Frozen, paired bottom-drain-v1 trial; no training or firmware promotion."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import zlib

import garden_diversity as diversity
import garden_water_budget as water
import garden_experiments as experiment
import garden_establishment as establishment
from garden_resources import require
from garden_gallery import contact_sheet, rgb565be_to_rgb888, write_png

RULE = "bottom-drain-v1"
DAY, HORIZON = diversity.DAY, diversity.HORIZON


def paired(before, after, before_water, after_water):
    result = {}
    for day in (64,128,192):
        tick = str(day*DAY)
        a,b = before["milestones"][tick],after["milestones"][tick]
        x,y = before_water["windows"][str(day)],after_water["windows"][str(day)]
        p,q = a["population"],b["population"]
        delta = {"living":q["living"]-p["living"],
                 "extant_families":len(q["extant_families"])-len(p["extant_families"]),
                 "extant_species":len(q["extant_species"])-len(p["extant_species"]),
                 "living_genotypes":q["living_genotypes"]-p["living_genotypes"],
                 "natural_deaths":b["closing_natural_deaths"]-a["closing_natural_deaths"]}
        for prefix in ("closing","post_establishment"):
            delta.update({prefix+"_"+key:b[prefix][key]-a[prefix][key] for key in a[prefix]})
        for key in ("soil_final","soil_change","uptake","runoff","evaporation","drainage",
                    "water_shortage_fraction","dry_root_fraction"):
            delta[key] = y[key]-x[key] if x[key] is not None and y[key] is not None else None
        result[str(day)] = {"delta":delta,"before_extinct":p["extinct"],"after_extinct":q["extinct"]}
    return result


def compare_summary(cases):
    result = {}
    for arm in diversity.SCHEDULES:
        selected = [c for c in cases if c["arm"]==arm]
        require(len(selected)==16,"incomplete comparison arm")
        result[arm] = {}
        for day in ("64","128","192"):
            metrics = {}
            for key in selected[0]["comparison"][day]["delta"]:
                values = [c["comparison"][day]["delta"][key] for c in selected]
                valid = [v for v in values if v is not None]
                metrics[key] = {"paired_worlds":len(valid),"undefined_pairs":len(values)-len(valid),
                                "lower":sum(v<0 for v in valid),"same":sum(v==0 for v in valid),
                                "higher":sum(v>0 for v in valid),
                                "distribution":diversity.distribution(valid) if valid else None}
            result[arm][day] = metrics
    return result


def collect(baseline, population_bundle, off_build, on_build, output, jobs):
    baseline,population_bundle,off_build,on_build,output = [p.resolve() for p in
        (baseline,population_bundle,off_build,on_build,output)]
    m = experiment.read_json(baseline/"manifest.json")
    pm = experiment.read_json(population_bundle/"manifest.json")
    require(m["status"]==pm["status"]=="complete" and m["kind"]=="garden-water-budget"
            and pm["kind"]=="garden-disturbance-longevity", "wrong baseline bundles")
    require(experiment.digest(population_bundle/"manifest.json")==m["input_manifest_sha256"],"mismatched baseline chain")
    cap = m["node_capacity"]
    require(cap in (256,512) and pm["node_capacity"]==cap and m["horizon"]==pm["horizon"]==HORIZON,"wrong capacity/horizon")
    cases = experiment.read_json(establishment.verified(baseline,m,"cases.json"))
    expected = {(s,seed,a) for s in experiment.SCENARIOS for seed in experiment.trial_seeds(0x6d617463,8)
                for a in diversity.SCHEDULES}
    require(len(cases)==80 and {(c["scenario"],c["seed"],c["arm"]) for c in cases}==expected,"incomplete baseline")
    require(not output.is_relative_to(experiment.ROOT) or output.is_relative_to(experiment.ROOT/"artifacts"),"unsafe output")
    output.mkdir(parents=True,exist_ok=False)
    for folder in ("input","bin","traces","analyses","frames"):
        (output/folder).mkdir()
    sources = experiment.source_files()
    experiment.snapshot_sources(output,sources)
    shutil.copy2(baseline/"manifest.json",output/"input/water-manifest.json")
    shutil.copy2(population_bundle/"manifest.json",output/"input/population-manifest.json")
    shutil.copy2(establishment.verified(baseline,m,"model.tgm"),output/"model.tgm")
    require(experiment.digest(output/"model.tgm")==diversity.maintenance.MODEL_SHA,"wrong model")
    for c in cases:
        name=f"{c['id']}.{c['arm']}"
        shutil.copy2(establishment.verified(baseline,m,f"traces/{name}.jsonl"),output/f"input/{name}.water.jsonl")
        shutil.copy2(establishment.verified(baseline,m,f"input/{name}.json"),output/f"input/{name}.population.json")
    for arm in diversity.SCHEDULES:
        for day in (16,64,128,192):
            for suffix in ("rgb565","json"):
                source = establishment.verified(population_bundle,pm,f"frames/{arm}-{day}.{suffix}")
                shutil.copy2(source,output/f"frames/off-{arm}-{day}.{suffix}")
    for label,build,tools in (("off",off_build,("water-budget",)),("on",on_build,("water-budget","inspect","replay"))):
        for tool in tools:
            shutil.copy2(build/f"toy-factory-garden-{tool}",output/f"bin/{label}-{tool}")
        shutil.copy2(build/"CMakeCache.txt",output/f"{label}-build-cache.txt")
    frozen={str(p.relative_to(output)):experiment.digest(p) for p in output.rglob("*") if p.is_file()}
    record={"schema_version":1,"kind":"garden-bottom-drainage","rule":RULE,"horizon":HORIZON,
            "node_capacity":cap,"source_sha256":sources,
            "baseline_water_manifest_sha256":experiment.digest(baseline/"manifest.json"),
            "baseline_population_manifest_sha256":experiment.digest(population_bundle/"manifest.json")}
    experiment.write_json(output/"started.json",record)

    def run(c):
        name=f"{c['id']}.{c['arm']}"
        schedule=diversity.SCHEDULES[c["arm"]]
        water_args=["model.tgm",c["scenario"],"0x"+c["seed"],str(schedule or 0),str(HORIZON)]
        old_rows=[json.loads(line) for line in (output/f"input/{name}.water.jsonl").read_text().splitlines()]
        commands=[]
        budgets={}
        for label in ("off","on"):
            cmd=[f"bin/{label}-water-budget",*water_args]
            path=output/f"traces/{name}.{label}.water.jsonl"
            experiment.command_run(cmd,path,output,300)
            rows=[json.loads(line) for line in path.read_text().splitlines()]
            if label=="off":
                require(rows==old_rows,"off branch changed from frozen baseline")
            budgets[label]=water.analyze(rows,drainage=RULE if label=="on" else None)
            require(all(r["model_crc32"]=="dc5e849d" and r["node_capacity"]==cap and
                        r["schedule"]==(schedule or 0) for r in rows),"wrong model/build/schedule")
            commands.append(cmd)
        common=["model.tgm",c["scenario"],experiment.NIGHT_POLICY,"0x"+c["seed"],"--leaf-policy","selective"]
        if schedule is not None:
            common += ["--disturbance-seed",str(schedule)]
        cmd=["bin/on-inspect",*common,"--population","--ticks",str(HORIZON)]
        path=output/f"traces/{name}.on.world.gz"
        bounds=diversity.disturbance.capture(cmd,path,output,"world",schedule,HORIZON)
        after=diversity.analyze(path,bounds,cap,HORIZON,schedule,RULE)
        before=experiment.read_json(output/f"input/{name}.population.json")
        for r,p,old in zip(budgets["on"]["daily"],after["daily"],old_rows,strict=True):
            require(r["tick"]==p["tick"] and r["hash"]==p["hash"] and r["births"]==p["births"]
                    and r["seeds"]==p["seeds"],"independent daily replay mismatch")
            require(r["rain"]+r["runoff"]==old["rain"]+old["runoff"],"rainfall changed")
            due=[e for e in after["events"] if e["tick"]<=r["tick"]]
            require(r["events"]==len(due) and r["environmental_loss"]==sum(e["water"] for e in due),"event loss mismatch")
        require(sum(budgets["on"]["daily"][-1]["soil_rows"])==after["final"]["soil"]["water"],"soil mismatch")
        commands.append(cmd)
        experiment.write_json(output/f"analyses/{name}.boundaries.json",bounds)
        experiment.write_json(output/f"analyses/{name}.population.json",after)
        experiment.write_json(output/f"analyses/{name}.water.json",budgets["on"])
        comparison=paired(before,after,budgets["off"],budgets["on"])
        experiment.write_json(output/f"analyses/{name}.paired.json",comparison)
        d=comparison["192"]["delta"]
        print(f"{cap}/{name}: soil delta={d['soil_final']}, closing birth delta={d['closing_offspring_born']}",flush=True)
        return {**{k:c[k] for k in ("id","scenario","seed","arm")},"commands":commands,
                "before":before,"after":after,"water":budgets,"comparison":comparison}

    try:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            results=list(pool.map(run,cases))
        summary={"paired":compare_summary(results)}
        for label,key in (("off","before"),("on","after")):
            summary[label]={"population":diversity.summarize([{**c,"analysis":c[key]} for c in results]),
                            "water":water.summarize([{**c,"data":c["water"][label]} for c in results])}
        experiment.write_json(output/"summary.json",summary)
        experiment.write_json(output/"cases.json",[{k:c[k] for k in ("id","scenario","seed","arm","commands")} for c in results])
        groups=[]
        frame_records=[]
        for arm,schedule in diversity.SCHEDULES.items():
            c=next(c for c in results if c["scenario"]=="rainfed" and c["seed"]==diversity.maintenance.FRAME_SEED and c["arm"]==arm)
            group=[]
            for day in (16,64,128,192):
                for label in ("off","on"):
                    name=f"{label}-{arm}-{day}"
                    frame=f"frames/{name}.rgb565"
                    cmd=None
                    if label=="on":
                        cmd=["bin/on-replay","model.tgm","rainfed",experiment.NIGHT_POLICY,"0x"+c["seed"],
                             "--leaf-policy","selective","--ticks",str(day*DAY),"--framebuffer",frame]
                        if schedule is not None:
                            cmd += ["--disturbance-seed",str(schedule)]
                        experiment.command_run(cmd,output/f"frames/{name}.json",output,300)
                    r=experiment.read_json(output/f"frames/{name}.json")
                    raw=(output/frame).read_bytes()
                    require(r.get("drainage_rule")== (RULE if label=="on" else None),"wrong frame environment")
                    require(r["hash"]==c["water"][label]["daily"][day]["hash"] and len(raw)==115200
                            and r["framebuffer_crc32"]==f"{zlib.crc32(raw):08x}","frame verification failed")
                    write_png(output/f"frames/{name}.png",240,240,rgb565be_to_rgb888(raw))
                    frame_records.append({"id":name,"framebuffer":frame,"command":cmd,"result":r})
                    if day in (64,192):
                        group.append({"id":name,"tick":day*DAY,"framebuffer":frame})
            groups.append(group)
        experiment.write_json(output/"frames.json",{"frames":frame_records,"groups":groups,"sheet":contact_sheet(output,groups)})
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
    for name in ("baseline","population-bundle","off-build","on-build","output"):
        parser.add_argument("--"+name,type=Path,required=True)
    parser.add_argument("--jobs",type=int,choices=(1,2,4),default=4)
    args=parser.parse_args()
    collect(args.baseline,args.population_bundle,args.off_build,args.on_build,args.output,args.jobs)


if __name__=="__main__":
    main()
