#!/usr/bin/env python3
"""Adaptive probe identity, trace neutrality and live resource-accounting checks."""
import argparse
import copy
import gzip
import json
from pathlib import Path
import subprocess
import tempfile

import garden_policy_diagnostic as diagnostic
from test_garden_leaf_competition import rejects


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build",type=Path,required=True)
    build=parser.parse_args().build.resolve()
    inspect=str(build/"toy-factory-garden-inspect")
    replay=str(build/"toy-factory-garden-replay")
    with tempfile.TemporaryDirectory(prefix="garden-policy-test-") as temp:
        root=Path(temp)
        args=["-","rainfed",diagnostic.ADAPTIVE,"0x9c530b07","--leaf-policy","selective"]
        plain=json.loads(subprocess.check_output([replay,*args,"--ticks","945"],text=True))
        original=json.loads(subprocess.check_output([replay,"-","rainfed","adaptive","0x9c530b07",
            "--leaf-policy","selective","--ticks","945"],text=True))
        assert plain=={**original,"policy":diagnostic.ADAPTIVE}
        for tool in (inspect,replay):
            assert subprocess.run([tool,"not-a-model",*args[1:],"--ticks","60"],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==2
        for schedule in (None,0x17c29444):
            folder=root/str(schedule)
            folder.mkdir()
            common=args+(["--disturbance-seed",str(schedule)] if schedule else [])
            horizon=24*diagnostic.DAY
            raw=folder/"full.jsonl"
            diagnostic.experiment.command_run([inspect,*common,"--ecology","--ticks",str(horizon)],raw,root,60)
            first=json.loads(raw.open().readline())
            cap=first.get("node_capacity",256)
            setting="on" if "drainage_rule" in first else "off"
            rule=first.get("drainage_rule")
            detail=diagnostic.diagnose(raw,setting,"adaptive",schedule,horizon,cap)
            assert detail["checked"]["live_steps"]>0 and detail["checked"]["committed_growth_decisions"]>0
            path=folder/"sparse.gz"
            bounds=diagnostic.diversity.disturbance.capture([inspect,*common,"--population","--ticks",str(horizon)],
                path,root,"world",schedule,horizon)
            population=diagnostic.diversity.analyze(path,bounds,cap,horizon,schedule,rule,diagnostic.ADAPTIVE)
            assert all(detail["daily"][str(d*diagnostic.DAY)]==row["hash"] for d,row in enumerate(population["daily"]))
            rejects(lambda:diagnostic.diversity.maintenance.check_identity(first,"selective",cap,rule))
            frame=folder/"frame.raw"
            visual=json.loads(subprocess.check_output([replay,*common,"--ticks",str(horizon),"--framebuffer",str(frame)],text=True))
            headless=json.loads(subprocess.check_output([replay,*common,"--ticks",str(horizon)],text=True))
            assert {**visual,"framebuffer_crc32":None}==headless and visual["hash"]==population["final"]["hash"]
            assert len(frame.read_bytes())==115200
            # Analyze deliberately damaged copies, never silently skipping an event or step.
            rows=[json.loads(line) for line in raw.read_text().splitlines()]
            def bad_test(name, altered):
                path=folder/(name+".jsonl")
                path.write_text("\n".join(map(json.dumps,altered))+"\n")
                rejects(lambda:diagnostic.diagnose(path,setting,"adaptive",schedule,horizon,cap))
            bad_test("truncated",rows[:-1])
            missing=copy.deepcopy(rows)
            missing.pop(next(i for i,r in enumerate(missing) if r["type"]=="world" and r["tick"]==15))
            bad_test("missing-step",missing)
            bad=copy.deepcopy(rows)
            changed=next(r for r in bad if r["type"]=="world" and r["tick"]==15)
            changed["plants"][0]["energy"]+=1
            bad_test("bad-budget",bad)
            bad=copy.deepcopy(rows)
            changed=next(r for r in bad if r["type"]=="bid" and r["sun_phase"]>=128)
            changed["action"]=1
            bad_test("bad-night-veto",bad)
            if schedule:
                bad_test("missing-event",[r for r in rows if r["type"]!="disturbance"])
        print("Adaptive drainage policy and full resource diagnostic checks passed")


if __name__=="__main__":
    main()
