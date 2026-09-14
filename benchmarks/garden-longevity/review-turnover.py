#!/usr/bin/env python3
"""Verify the offline turnover audit and export compact tables/death records."""
import argparse
from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"sim"))
import garden_turnover as audit


def compact(value):
    result={"overview":value["overview"],"focus":{}}
    for key,r in value["focus"].items():
        deaths=r["closing_natural_deaths"]
        groups={}
        for name,flag in (("energy",3),("water",5),("both",7)):
            selected=[d for d in deaths if d["death_flags"]==flag]
            groups[name]={"count":len(selected),"ids":[d["id"] for d in selected],
                "phases":dict(Counter(d["death_phase"] for d in selected)),
                "seed_producers":sum(d["seeds_produced"]>0 for d in selected),
                "seed_spend_last_day":sum(d["last_day_budget"].get("energy_seeds",0) for d in selected),
                "day_old":sum(d["age_ticks"]>=audit.DAY for d in selected)}
        result["focus"][key]={"checked_live_steps":r["checked_live_steps"],
            "checked_world_rows":r["checked_world_rows"],"death_groups":groups,
            "deaths":[{k:v for k,v in d.items() if k not in ("last_day_maintenance","first_day_points")}
                      for d in deaths], "windows":{}}
        for start in (0,32,64,96,128,160):
            rows=[r["daily"][str(day)] for day in range(start+1,start+33)]
            totals=Counter()
            for row in rows:totals.update(row)
            result["focus"][key]["windows"][f"{start}-{start+32}"]=dict(totals)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle",type=Path,default=audit.bank.experiment.ROOT/"artifacts/garden-turnover")
    parser.add_argument("--output",type=Path)
    parser.add_argument("--reanalyze",action="store_true")
    args=parser.parse_args();root=args.bundle.resolve()
    m=audit.bank.experiment.read_json(root/"manifest.json")
    audit.require(m["kind"]=="garden-turnover" and m["status"]=="complete","wrong audit")
    for name in m["artifacts"]:audit.bank.establishment.verified(root,m,name)
    data=audit.bank.experiment.read_json(root/"summary.json")
    audit.require(set(data["focus"])==set(audit.FOCUS) and len(data["overview"])==8,"incomplete panel")
    for key,life in data["overview"].items():
        old=audit.bank.experiment.read_json(root/f"input/{key}.json")
        world=old["analysis"]["world"]
        audit.require(audit.summary_lifetimes(world["lineages"])==life,"lifetime summary changed")
        if args.reanalyze and key in audit.FOCUS:
            bounds=audit.bank.experiment.read_json(root/f"input/{key}.boundaries.json")
            new=audit.resource_trace(root/f"input/{key}.world.gz",bounds,world,old["bank"])
            new["checked_world_rows"]=audit.END//15+1
            # JSON object keys from lineage IDs are strings in the saved form.
            import json
            audit.require(json.loads(json.dumps(new))==data["focus"][key],"resource reanalysis changed")
        print(key,{d:(v["survived"],v["eligible"]) for d,v in life["closing"]["ages"].items()})
    if args.output:
        audit.require(not args.output.exists(),"output exists")
        audit.bank.experiment.write_json(args.output,compact(data)|{
            "manifest_sha256":audit.bank.experiment.digest(root/"manifest.json")})
    print(f"Verified {len(m['artifacts'])} artifacts; {audit.bank.experiment.digest(root/'manifest.json')}")


if __name__=="__main__":main()
