#!/usr/bin/env python3
"""Drainage census identity, full/sparse equivalence and paired-cohort checks."""
import argparse
import copy
import gzip
import json
from pathlib import Path
import subprocess
import tempfile

import garden_drainage as trial
from test_garden_leaf_competition import rejects


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build",type=Path,required=True)
    build=parser.parse_args().build.resolve()
    with tempfile.TemporaryDirectory(prefix="garden-drainage-test-") as temp:
        root=Path(temp)
        model=root/"model.tgm"
        subprocess.run([str(build/"toy-factory-garden-water-audit-test"),str(model)],check=True,timeout=60)
        report=json.loads(subprocess.check_output([str(build/"toy-factory-garden-eval"),
            "--rainfed","--trials","1","--ticks","60","--leaf-policy","selective"],text=True,timeout=60))
        assert report["drainage_rule"]==report["environment"]["drainage_rule"]==trial.RULE
        for schedule in (None,0xe4d65e6f):
            run_dir=root/str(schedule)
            run_dir.mkdir()
            args=[str(model),"rainfed",trial.experiment.NIGHT_POLICY,"0x9c530b07","--leaf-policy","selective"]
            if schedule:
                args += ["--disturbance-seed",str(schedule)]
            horizon=92160
            bounds={}
            for name,flag in (("sparse","--population"),("full","--ecology")):
                command=[str(build/"toy-factory-garden-inspect"),*args,flag,"--ticks",str(horizon)]
                bounds[name]=trial.diversity.disturbance.capture(command,run_dir/f"{name}.gz",root,"world",schedule,horizon)
            assert bounds["full"]==bounds["sparse"]
            with gzip.open(run_dir/"sparse.gz","rt") as source:
                cap=json.loads(next(source)).get("node_capacity",256)
            a=trial.diversity.analyze(run_dir/"sparse.gz",bounds["sparse"],cap,horizon,schedule,trial.RULE)
            trial.diversity.maintenance.check_identity(a["final"],"selective",cap,trial.RULE)
            rejects(lambda:trial.diversity.maintenance.check_identity(a["final"],"selective",cap))
            trial.diversity.compare_sparse_prefix(run_dir/"sparse.gz",run_dir/"full.gz",horizon)
            replay=json.loads(subprocess.check_output([str(build/"toy-factory-garden-replay"),*args,"--ticks",str(horizon)],text=True,timeout=60))
            assert replay["drainage_rule"]==trial.RULE and replay["hash"]==a["final"]["hash"]
            rows=[json.loads(s) for s in subprocess.check_output([str(build/"toy-factory-garden-water-budget"),
                  str(model),"rainfed","0x9c530b07",str(schedule or 0),str(horizon)],text=True,timeout=60).splitlines()]
            trial.water.analyze(rows,horizon,trial.RULE)
            assert all(r["hash"]==p["hash"] for r,p in zip(rows,a["daily"],strict=True))
            assert rows[-1]["drainage"]>0
        # Pure paired comparison: preserve both adverse deltas and undefined fractions.
        population={"living":2,"extant_families":[1],"extant_species":["flower"],"living_genotypes":2,"extinct":False}
        cohort={"offspring_born":2,"eligible_offspring":1,"cycle_survivors":1}
        before={"milestones":{str(d*trial.DAY):{"population":population,"closing_natural_deaths":0,
                "closing":cohort,"post_establishment":cohort} for d in (64,128,192)}}
        window={k:0 for k in ("soil_final","soil_change","uptake","runoff","evaporation","drainage",
                             "water_shortage_fraction","dry_root_fraction")}
        water={"windows":{str(d):window for d in (64,128,192)}}
        after=copy.deepcopy(before)
        after["milestones"][str(192*trial.DAY)]["closing"]["cycle_survivors"]=0
        other=copy.deepcopy(water);other["windows"]["192"]["water_shortage_fraction"]=None
        delta=trial.paired(before,after,water,other)["192"]["delta"]
        assert delta["closing_cycle_survivors"]==-1 and delta["water_shortage_fraction"] is None
        print("Drainage census and paired comparison checks passed")


if __name__=="__main__":
    main()
