#!/usr/bin/env python3
"""Exact stage water inventories for the unchanged 192-day disturbance panel."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil

import garden_diversity as diversity
import garden_establishment as establishment
import garden_experiments as experiment
from garden_resources import require

DAY = diversity.DAY
HORIZON = diversity.HORIZON
STAGES = ("start", "rain", "transport", "uptake", "decomposition", "maintenance_and_death",
          "germination", "growth_and_renewal", "reproduction")
CUMULATIVE = ("rain", "runoff", "births", "seeds_created", "seeds_expired", "events",
              "environmental_loss", "steps", "soil_samples", "capped_steps", "saturated_samples",
              "root_samples", "dry_root_samples", "living_samples", "shortage_samples")


def analyze(rows, horizon=HORIZON, drainage=None):
    require(0 <= horizon <= HORIZON and horizon % DAY == 0, "invalid horizon")
    require([r["tick"] for r in rows] == list(range(0, horizon+1, DAY)), "missing daily budget")
    initial = rows[0]
    require(drainage in (None, "bottom-drain-v1"), "unknown drainage rule")
    start_soil = sum(initial["soil_rows"])
    for i, r in enumerate(rows):
        require(r["schema_version"] == 1 and r["node_capacity"] in (256, 512), "unknown budget")
        require(all(r[k] == initial[k] for k in ("model_crc32", "schedule", "node_capacity")), "identity drift")
        require(r.get("drainage_rule") == drainage, "wrong drainage environment")
        drained = r.get("drainage", 0)
        require(type(drained) is int and 0 <= drained <= r["steps"]//16*28, "invalid drainage")
        require(drainage is not None or drained == 0, "drainage in control")
        require(drained >= rows[i-1].get("drainage",0) if i else drained == 0, "drainage counter reversed")
        require(len(r["soil_rows"]) == 11 and all(0 <= v <= 28*255 for v in r["soil_rows"]), "invalid soil")
        s, p = r["stage_soil"], r["stage_plants"]
        require(len(s) == len(p) == len(STAGES) and all(type(v) is int for v in s+p), "invalid stages")
        require(all(type(r[k]) is int and r[k] >= 0 for k in CUMULATIVE), "invalid counter")
        require(r["steps"] == r["tick"]//15, "missed ecology steps")
        require(all(r[k] >= rows[i-1][k] for k in CUMULATIVE) if i else all(r[k] == 0 for k in CUMULATIVE), "nonmonotone/initial counter")
        require(all(s[j] == 0 for j in (0,4,5,7,8)) and all(p[j] == 0 for j in (0,1,2,4)), "unexpected stage transfer")
        require(s[1] == r["rain"] and s[2] <= 0 and s[3] <= 0 and p[3] == -s[3], "rain/uptake mismatch")
        require(p[5] <= 0 and p[7] <= 0 and p[8] == -24*r["seeds_created"], "invalid expenditure")
        require(s[6] == -12*r["births"] and p[6] == 24*r["births"], "germination mismatch")
        require(r["seeds"] == initial["seeds"] + r["seeds_created"]-r["seeds_expired"]-r["births"], "seed balance")
        require(sum(r["soil_rows"]) == start_soil+sum(s), "soil balance does not close")
        require(r["plants"] == initial["plants"]+sum(p)-r["environmental_loss"], "plant balance does not close")
        # Seeds have no stored_water field. A 24-unit bookkeeping endowment
        # accounts for reproduction -> bank -> seedling without double counting.
        before = start_soil + initial["plants"] + 24*initial["seeds"]
        after = sum(r["soil_rows"]) + r["plants"] + 24*r["seeds"]
        require(after == before+r["rain"]+s[2]+s[6]+p[5]+p[7]
                -24*r["seeds_expired"]-r["environmental_loss"], "combined seed-account balance")
        require(0 <= -s[2]-drained <= r["steps"]//4*28, "evaporation bound")
        require(0 <= r["dry_root_cells"] <= r["root_cells"] <= 308 and
                0 <= r["root_water"] <= min(sum(r["soil_rows"]), r["root_cells"]*255), "root inventory")
        require(r["dry_root_samples"] <= r["root_samples"] <= r["steps"]*308 and
                r["shortage_samples"] <= r["living_samples"] <= r["steps"]*8 and
                r["capped_steps"] <= r["steps"] and r["saturated_samples"] <= r["steps"]*308,
                "exposure bounds")
        if i:
            prior = rows[i-1]
            require(all(s[j] >= prior["stage_soil"][j] for j in (1,)) and
                    all(s[j] <= prior["stage_soil"][j] for j in (2,3,6)) and
                    all(p[j] <= prior["stage_plants"][j] for j in (5,7,8)), "stage counters reversed")
    windows = {}
    for end in (64,128,192):
        if end*DAY > horizon:
            continue
        a, b = rows[end-32], rows[end]
        delta = {k: b[k]-a[k] for k in CUMULATIVE}
        s = [y-x for x,y in zip(a["stage_soil"],b["stage_soil"],strict=True)]
        p = [y-x for x,y in zip(a["stage_plants"],b["stage_plants"],strict=True)]
        drained = b.get("drainage",0)-a.get("drainage",0)
        windows[str(end)] = {**delta,
            "soil_change": sum(b["soil_rows"])-sum(a["soil_rows"]),
            "soil_final": sum(b["soil_rows"]), "rain_available": delta["rain"]+delta["runoff"],
            "evaporation": -s[2]-drained, "drainage": drained,
            "uptake": -s[3], "germination_soil": -s[6],
            "maintenance_and_death": -p[5], "growth_and_renewal": -p[7],
            "reproduction_to_bank": -p[8], "expired_seed_endowment": delta["seeds_expired"]*24,
            "soil_mean": delta["soil_samples"]/delta["steps"],
            "dry_root_fraction": delta["dry_root_samples"]/delta["root_samples"] if delta["root_samples"] else None,
            "water_shortage_fraction": delta["shortage_samples"]/delta["living_samples"] if delta["living_samples"] else None,
            "summary_capped_fraction": delta["capped_steps"]/delta["steps"],
            "root_cells_final": b["root_cells"], "root_water_final": b["root_water"],
            "soil_rows_final": b["soil_rows"]}
    return {"daily": rows, "windows": windows}


def summarize(cases):
    result = {}
    for arm in diversity.SCHEDULES:
        selected = [c for c in cases if c["arm"] == arm]
        require(len(selected) == 16, "incomplete arm")
        result[arm] = {str(day): {key: diversity.distribution([c["data"]["windows"][str(day)][key] for c in selected])
            for key,value in selected[0]["data"]["windows"][str(day)].items()
            if isinstance(value,(int,float)) and all(c["data"]["windows"][str(day)][key] is not None for c in selected)}
            for day in (64,128,192)}
    return result


def collect(bundle, build, output, jobs):
    bundle, build, output = bundle.resolve(), build.resolve(), output.resolve()
    m = experiment.read_json(bundle/"manifest.json")
    require(m["kind"] == "garden-disturbance-longevity" and m["status"] == "complete" and m["horizon"] == HORIZON, "wrong input bundle")
    capacity = m["node_capacity"]
    require(capacity in (256,512), "wrong capacity")
    require(not output.is_relative_to(experiment.ROOT) or output.is_relative_to(experiment.ROOT/"artifacts"), "unsafe output")
    old_cases = experiment.read_json(establishment.verified(bundle,m,"cases.json"))
    expected = {(scenario,seed,arm) for scenario in experiment.SCENARIOS
                for seed in experiment.trial_seeds(0x6d617463,8) for arm in diversity.SCHEDULES}
    require(len(old_cases)==80 and {(c["scenario"],c["seed"],c["arm"]) for c in old_cases}==expected, "wrong panel")
    output.mkdir(parents=True,exist_ok=False)
    for name in ("input","traces","analyses","bin"):
        (output/name).mkdir()
    sources = experiment.source_files()
    experiment.snapshot_sources(output,sources)
    shutil.copy2(bundle/"manifest.json",output/"input/manifest.json")
    shutil.copy2(establishment.verified(bundle,m,"model.tgm"),output/"model.tgm")
    require(experiment.digest(output/"model.tgm")==diversity.maintenance.MODEL_SHA,"wrong frozen model")
    shutil.copy2(build/"toy-factory-garden-water-budget",output/"bin/water-budget")
    shutil.copy2(build/"CMakeCache.txt",output/"build-cache.txt")
    for c in old_cases:
        name = f"{c['id']}.{c['arm']}.json"
        shutil.copy2(establishment.verified(bundle,m,f"analyses/{name}"),output/f"input/{name}")
    frozen = {str(p.relative_to(output)):experiment.digest(p) for p in output.rglob("*") if p.is_file()}
    record = {"schema_version":1,"kind":"garden-water-budget","status":"running","node_capacity":capacity,
              "horizon":HORIZON,"stages":list(STAGES),"source_sha256":sources,
              "input_manifest_sha256":experiment.digest(output/"input/manifest.json")}
    experiment.write_json(output/"started.json",record)

    def run(c):
        name = f"{c['id']}.{c['arm']}"
        schedule = diversity.SCHEDULES[c["arm"]] or 0
        command = ["bin/water-budget","model.tgm",c["scenario"],"0x"+c["seed"],str(schedule),str(HORIZON)]
        dest = output/f"traces/{name}.jsonl"
        experiment.command_run(command,dest,output,300)
        rows = [json.loads(line) for line in dest.read_text().splitlines()]
        data = analyze(rows)
        old = experiment.read_json(output/f"input/{name}.json")
        require(len(rows)==len(old["daily"]) and all(r["hash"]==d["hash"] and r["tick"]==d["tick"]
                for r,d in zip(rows,old["daily"],strict=True)),"frozen daily replay mismatch")
        require(all(r["model_crc32"]=="dc5e849d" and r["schedule"]==schedule and r["node_capacity"]==capacity for r in rows),"wrong binary/model/schedule")
        for r in rows:
            due = [e for e in old["events"] if e["tick"]<=r["tick"]]
            require(r["events"]==len(due) and r["environmental_loss"]==sum(e["water"] for e in due),"environmental loss mismatch")
        require(sum(rows[-1]["soil_rows"])==old["final"]["soil"]["water"],"frozen soil mismatch")
        experiment.write_json(output/f"analyses/{name}.json",data)
        print(f"{capacity}/{name}: final-32-day soil change={data['windows']['192']['soil_change']}",flush=True)
        return {**{k:c[k] for k in ("id","scenario","seed","arm")},"command":command,"data":data}

    try:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            cases = list(pool.map(run,old_cases))
        experiment.write_json(output/"cases.json",[{k:v for k,v in c.items() if k!="data"} for c in cases])
        experiment.write_json(output/"summary.json",summarize(cases))
        require(experiment.source_files()==sources,"source changed during collection")
        require(all(experiment.digest(output/name)==sha for name,sha in frozen.items()),"frozen input changed")
        record.update(status="complete",artifacts={str(p.relative_to(output)):experiment.digest(p) for p in output.rglob("*") if p.is_file()})
        experiment.write_json(output/"manifest.json",record)
        print(f"Complete {output}; manifest sha256={experiment.digest(output/'manifest.json')}",flush=True)
    except BaseException as error:
        experiment.write_json(output/"failure.json",{"error":str(error)})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle",type=Path,required=True)
    parser.add_argument("--build",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--jobs",type=int,choices=(1,2,4),default=4)
    args = parser.parse_args()
    collect(args.bundle,args.build,args.output,args.jobs)


if __name__ == "__main__":
    main()
