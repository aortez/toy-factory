#!/usr/bin/env python3
"""Reserve rule arithmetic, trace neutrality and independent replay checks."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import zlib

import garden_policy_diagnostic as diagnostic
from test_garden_leaf_competition import rejects


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build",type=Path,required=True)
    build=parser.parse_args().build.resolve()
    with tempfile.TemporaryDirectory(prefix="garden-reserve-test-") as temp:
        root=Path(temp)
        model=root/"model.tgm"
        subprocess.run([str(build/"toy-factory-garden-water-audit-test"),str(model)],check=True,timeout=60)
        inspector=str(build/"toy-factory-garden-inspect")
        replayer=str(build/"toy-factory-garden-replay")
        for scenario,schedule in ((s,d) for s in sorted(diagnostic.experiment.SCENARIOS)
                for d in (None,0x17c29444)):
            folder=root/f"{scenario}-{schedule}";folder.mkdir()
            args=[str(model),scenario,diagnostic.RESERVE,"0x9c530b07","--leaf-policy","selective"]
            if schedule:args += ["--disturbance-seed",str(schedule)]
            horizon=18*diagnostic.DAY
            raw=folder/"full.jsonl"
            diagnostic.experiment.command_run([inspector,*args,"--ecology","--ticks",str(horizon)],raw,root,60)
            with raw.open() as source:first=json.loads(next(source))
            cap=first.get("node_capacity",256)
            rule=first.get("drainage_rule")
            setting="on" if rule else "off"
            detail=diagnostic.diagnose(raw,setting,"reserve",schedule,horizon,cap)
            assert detail["checked"]["reserve_checked_bids"]>0 and detail["checked"]["reserve_vetoed_bids"]>0
            sparse=folder/"sparse.gz"
            bounds=diagnostic.diversity.disturbance.capture([inspector,*args,"--population","--ticks",str(horizon)],
                sparse,root,"world",schedule,horizon)
            population=diagnostic.diversity.analyze(sparse,bounds,cap,horizon,schedule,rule,diagnostic.RESERVE)
            assert all(detail["daily"][str(d*diagnostic.DAY)]==r["hash"] for d,r in enumerate(population["daily"]))
            rejects(lambda:diagnostic.diversity.maintenance.check_identity(first,"selective",cap,rule))
            frame=folder/"frame.raw"
            visual=json.loads(subprocess.check_output([replayer,*args,"--ticks",str(horizon),"--framebuffer",str(frame)],text=True,timeout=60))
            plain=json.loads(subprocess.check_output([replayer,*args,"--ticks",str(horizon)],text=True,timeout=60))
            assert {**visual,"framebuffer_crc32":None}==plain and plain["hash"]==population["final"]["hash"]
            assert plain["policy"]==diagnostic.RESERVE and plain["model_crc32"] is not None
            assert len(frame.read_bytes())==115200 and visual["framebuffer_crc32"]==f"{zlib.crc32(frame.read_bytes()):08x}"
            with raw.open() as source:
                bid=next(json.loads(line) for line in source if '"reserve":' in line)
            diagnostic.check_reserve_bid(bid)
            bad=copy.deepcopy(bid);bad["reserve"]["daylight_credit"]+=1
            rejects(lambda:diagnostic.check_reserve_bid(bad))
            bad=copy.deepcopy(bid);bad["priority"]+=1
            rejects(lambda:diagnostic.check_reserve_bid(bad))
            bad=copy.deepcopy(bid);bad["action"]=(bad["action"]+1)%3
            rejects(lambda:diagnostic.check_reserve_bid(bad))
        print("Reserve rule, resource budgets and independent replay checks passed")


if __name__=="__main__":
    main()
