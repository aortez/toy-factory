#!/usr/bin/env python3
"""Budget closure, invalid inputs, and unchanged daily simulation identity."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import garden_water_budget as water
from test_garden_leaf_competition import rejects


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build",type=Path,required=True)
    parser.add_argument("--drainage", action="store_true")
    args = parser.parse_args()
    build = args.build.resolve()
    rule = "bottom-drain-v1" if args.drainage else None
    def analyze(rows, horizon):
        return water.analyze(rows, horizon, rule)
    with tempfile.TemporaryDirectory(prefix="garden-water-test-") as temporary:
        root = Path(temporary)
        model = root/"model.tgm"
        subprocess.run([str(build/"toy-factory-garden-water-audit-test"),str(model)],
                       check=True,capture_output=True,timeout=60)
        binary = str(build/"toy-factory-garden-water-budget")
        for schedule in (0,0xe4d65e6f):
            command = [binary,str(model),"rainfed","0x9c530b07",str(schedule),"92160"]
            rows = [json.loads(line) for line in subprocess.check_output(command,text=True,timeout=60).splitlines()]
            analyze(rows,92160)
            inspect = [str(build/"toy-factory-garden-inspect"),str(model),"rainfed",water.experiment.NIGHT_POLICY,
                       "0x9c530b07","--leaf-policy","selective","--population","--ticks","92160"]
            if schedule:
                inspect += ["--disturbance-seed",str(schedule)]
            worlds = {}
            for line in subprocess.check_output(inspect,text=True,timeout=60).splitlines():
                r = json.loads(line)
                if r["type"]=="world" and r["tick"]%water.DAY==0:
                    worlds[r["tick"]]=r
            for r in rows:
                w = worlds[r["tick"]]
                assert r["hash"]==w["hash"] and sum(r["soil_rows"])==w["soil"]["water"]
                assert r["plants"]==sum(p["water"] for p in w["plants"])
            rejects(lambda:analyze(rows[:-1],92160))
            for key in ("plants","rain","births","environmental_loss","seeds","steps","shortage_samples"):
                wrong = copy.deepcopy(rows)
                wrong[-1][key] += 999999
                rejects(lambda:analyze(wrong,92160))
            wrong = copy.deepcopy(rows)
            wrong[-1]["stage_soil"][4] += 1
            rejects(lambda:analyze(wrong,92160))
            assert len(analyze(rows[:1],0)["daily"])==1
            if rule:
                rejects(lambda:water.analyze(rows,92160))
                wrong = copy.deepcopy(rows)
                wrong[-1]["drainage"] += 99999999
                rejects(lambda:analyze(wrong,92160))
        for index,values in ((3,("0","-1","+1","4294967296","1x","")),
                             (4,("-1","1x","4294967296")),(5,("1","737281","-1","4294967296")),
                             (2,("irrigated","bogus"))):
            for value in values:
                bad=command.copy();bad[index]=value
                assert subprocess.run(bad,capture_output=True,timeout=10).returncode==2
        print("Water budget and unchanged daily replay checks passed")


if __name__=="__main__":
    main()
