#!/usr/bin/env python3
"""Bounded FINISH retries until the unchanged dark guard becomes applicable."""
from __future__ import annotations

import argparse
import copy
from itertools import zip_longest
import json
from pathlib import Path
import shutil
import tempfile
import time

import garden_renewal_purchase_veto as prior

panel, guard, failures = prior.panel, prior.guard, prior.failures
experiment, startup, gallery, require = prior.experiment, prior.startup, prior.gallery, prior.require
RULE, VETO = "garden-renewal-finish-retry-v1", "finish-retry-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-finish-retry-protocol.md"
BASELINE_SHA = "4a2c01588a204bbd4794d55da6b16cbd96948c0827e7cb3e7339fbd82dea5e4d"
ARMS, FRAMES = ("control", "finish", "finish-retry"), prior.FRAMES
TARGETS = (prior.TARGETS["finish"], {**prior.TARGETS["finish"], "tick": 69900, "energy": 90, "water": 161})
HANDOFF = 69915


def settings():
    return {"rule": RULE, "veto_rule": VETO, "baseline_manifest_sha256": BASELINE_SHA,
            "arms": list(ARMS), "receipts": list(TARGETS), "handoff": HANDOFF,
            "world_seed": prior.CASE.seed, "patch_seed": prior.CASE.patch,
            "stop": panel.STOP, "late_start": panel.LATE, "frame_ticks": list(FRAMES),
            "models": prior.settings()["models"], "routing": prior.settings()["routing"],
            "guard_rule": guard.GUARD,
            "budget": {"native_calls": 24, "traces": 6, "frame_replays": 18, "training_calls": 0},
            "role": "selected-world retry diagnostic; no policy qualification"}


def commands():
    calls = []
    for arm in ARMS:
        base = ["models/r2-n.tgm", "rainfed-crowded", experiment.NIGHT_POLICY, "0x"+prior.CASE.seed,
                "--leaf-policy", "selective", "--focal-model", "models/r2-w.tgm", "--focal-founder", "5",
                "--disturbance-seed", "0x"+prior.CASE.patch]
        if arm != "control":
            base += ["--purchase-veto", arm]
        for suffix in ("", ".repeat"):
            calls.append((f"traces/{arm}{suffix}.jsonl.gz",
                          ["bin/inspect", *base, "--ecology", "--ticks", str(panel.STOP)]))
        for tick in FRAMES:
            for suffix in ("", ".repeat"):
                stem = f"frames/{arm}.{tick}{suffix}"
                calls.append((stem+".json", ["bin/replay", *base, "--ticks", str(tick),
                                            "--framebuffer", stem+".rgb565"]))
    return calls


def check_metadata(row):
    expected = {"rule": VETO, "arm": "finish-retry", "tick": TARGETS[0]["tick"], "id": 22,
                "hits": sum(row["tick"] >= t["tick"] for t in TARGETS), "stop_tick": HANDOFF}
    require(row.get("purchase_veto") == expected, "wrong retry counter/handoff metadata")


def check_prefix(baseline, treated, target):
    """Compare complete raw prefixes against control or the frozen first veto."""
    for count, (a,b) in enumerate(zip_longest(baseline, treated)):
        require(a is not None and b is not None, "truncated retry prefix")
        if b["type"] == "world":
            check_metadata(b)
        if prior.without_veto(a) == prior.without_veto(b):
            require(a["tick"] <= target["tick"], "missing retry divergence")
            continue
        require(a["type"] == b["type"] == "world" and a["tick"] == b["tick"] == target["tick"],
                "retry diverged outside selected transaction")
        left, right = [{p["id"]:p for p in r["plants"]} for r in (a,b)]
        require(left.keys() == right.keys() and all(left[i] == right[i] for i in left if i != 22),
                "non-target changed at retry")
        require(a["dark_guard"] == b["dark_guard"], "ordinary guard changed at retry")
        events = [e for e in b["dark_guard"]["events"] if e["id"] == 22 and e["kind"] == "growth"]
        require(len(events) == 1, "missing winning receipt")
        event = events[0]
        require(all(event[k] == v for k,v in target.items() if k not in ("tick", "action")) and
                not event["denied"] and not event["invalid"] and event["stress"] == 0 and
                (event["energy_cost"], event["water_cost"]) == (9,5), "wrong retry receipt")
        a,b = left[22],right[22]
        require((a["energy"],a["water"],a["nodes"]) == (target["energy"]-9,target["water"]-5,21)
                and (b["energy"],b["water"],b["nodes"]) == (target["energy"],target["water"],21),
                "wrong retry cost/body delta")
        require(b["tips"] == a["tips"]+1 and a["agent"]["finish"] == b["agent"]["finish"]+1
                and a["agent"]["decisions"] == b["agent"]["decisions"]+1, "retry committed tip/action")
        return {"tick": target["tick"], "matching_records": count, "receipt": event,
                "baseline": a, "treated": b}
    raise RuntimeError("retry never diverged")


def check_receipts(raw):
    for target in TARGETS:
        bids = [r for r in raw if r["type"] == "bid" and r["id"] == 22 and r["tick"] == target["tick"]]
        require(bool(bids), "missing FINISH retry candidates")
        winner = max(bids, key=lambda b:b["priority"])
        require((winner["action"], winner["tip_index"]) == (2,271), "retry selected different action/tip")
    handoff = next((r for r in raw if r["type"] == "world" and r["tick"] == HANDOFF),None)
    require(handoff is not None,"missing handoff census")
    check_metadata(handoff)
    receipts = [e for e in handoff["dark_guard"]["events"] if e["id"] == 22 and e["kind"] == "growth"]
    require(len(receipts) == 1 and receipts[0]["node"] == 271 and receipts[0]["before"]["supported"]
            and receipts[0]["after"]["supported"], "missing ordinary-guard handoff")
    return {"tick": HANDOFF, "receipt": receipts[0], "plant": next(p for p in handoff["plants"] if p["id"] == 22)}


def analyze_retry(root, create=False):
    arm = "finish-retry"
    path = root/f"traces/{arm}.jsonl.gz"
    require(experiment.digest(path) == experiment.digest(root/f"traces/{arm}.repeat.jsonl.gz"), "retry repeat differs")
    prefixes = {name: check_prefix(startup.read_trace(root/f"input/{name}.jsonl.gz"), startup.read_trace(path), t)
                for name,t in zip(("control","finish"), TARGETS)}
    raw, boundaries = panel.split_rows(startup.read_trace(path), prior.CASE.patch)
    for row in raw:
        if row["type"] == "world":
            check_metadata(row)
    routed, _ = guard.prior.neighbors.check_routing(iter(raw), guard.prior.ROUTE)
    handoff = check_receipts(raw)
    accounted, audit = guard.accounting_rows(iter(raw), "guard", stop=panel.STOP, boundaries=boundaries,
        retain_events=False, growth_vetoes={(t["tick"],22) for t in TARGETS})
    worlds = [r for r in accounted if r["type"] == "world"]
    for name, rows in (("accounting",accounted),("worlds",worlds)):
        target = root/f"traces/{arm}.{name}.jsonl.gz"
        if create:
            guard.write_accounting(target, rows)
        require(rows == list(startup.read_trace(target)), "derived retry trace changed")
    world, _ = panel.competition.world_analysis(root/f"traces/{arm}.worlds.jsonl.gz", "selective",512,
                                               panel.STOP,panel.LATE,disturbances=boundaries)
    tips = startup.tips.analyze_stream((json.dumps(r) for r in accounted if r["type"] != "leaf-bid"),
                                       panel.STOP,panel.LATE,512,disturbances=boundaries)
    records = {p["id"]:p for p in world["lineages"]}
    for p in tips["lineages"]:
        require(all(p[k] == records[p["id"]][k] for k in ("parent","species","birth_tick","death_tick")),
                "tip/resource lifetimes differ")
    extra = panel.supplementary(worlds,boundaries,records,prior.CASE)
    for window in ("whole","late"):
        require(all(tips["windows"][window][k] == extra["exposure"][window][k]
                    for k in ("living_steps","tipless_steps","world_steps")), "exposure differs")
    histories, checked = failures.histories(worlds,boundaries,records,panel.STOP)
    events, frames = [b["event"] for b in boundaries.values()], []
    samples = {w["tick"]:boundaries.get(w["tick"],{}).get("after",w) for w in worlds if w["tick"] in FRAMES}
    for tick in FRAMES:
        stem = f"frames/{arm}.{tick}"
        value = experiment.read_json(root/(stem+".json"))
        pixels = (root/(stem+".rgb565")).read_bytes()
        check_metadata(value)
        panel.check_frame(value,samples[tick],prior.CASE,tick,pixels,events)
        require(value == experiment.read_json(root/(stem+".repeat.json")) and
                pixels == (root/(stem+".repeat.rgb565")).read_bytes(), "retry frame repeat differs")
        frames.append({"id":f"{arm}.{tick}","arm":arm,"tick":tick,"result":value,
                       "framebuffer":stem+".rgb565","png":stem+".png"})
    return {"summary":panel.summary(world,extra,audit),"prefixes":prefixes,"handoff":handoff,
            "targets":{"finish":{"lineage":records[22],"history":histories[22]}},
            "lineages":world["lineages"],"daily":extra["daily"],"events":events,"routing":routed,
            "checked_live_histories":checked,"tip_audit":{k:tips[k] for k in ("totals","windows")}},frames


def analyze(root, create=False):
    parent = experiment.read_json(root/"input/baseline-results.json")
    results, frames = {}, []
    for arm in ARMS:
        if arm == "finish-retry":
            results[arm], captured = analyze_retry(root,create)
        else:
            require(experiment.digest(root/f"traces/{arm}.jsonl.gz") == experiment.digest(root/f"input/{arm}.jsonl.gz"),
                    "frozen reference trace changed")
            results[arm], captured = prior.analyze_case(root,arm,create)
            require(results[arm] == parent["cases"][arm], "reference reanalysis changed")
            for tick in FRAMES:
                for extension in ("json","rgb565"):
                    require(experiment.digest(root/f"frames/{arm}.{tick}.{extension}") ==
                            experiment.digest(root/f"input/{arm}.{tick}.{extension}"), "frozen reference frame changed")
            results[arm]["targets"] = {"finish":results[arm]["targets"]["finish"]}
        frames += captured
        print("Audited",arm,flush=True)
    return {"rule":RULE,"settings":settings(),"cases":results,"frames":frames,
            "comparisons":{arm:prior.compare(results[arm],results["finish-retry"],"finish")
                           for arm in ("control","finish")}}


def copies():
    result = {"input/baseline-results.json":"results.json","input/native-source.tar.gz":"source.tar.gz"}
    result.update({f"models/{n}.tgm":f"models/{n}.tgm" for n in settings()["models"]})
    for arm in ("control","finish"):
        result[f"input/{arm}.jsonl.gz"] = f"traces/{arm}.jsonl.gz"
        for tick in FRAMES:
            for extension in ("json","rgb565"):
                result[f"input/{arm}.{tick}.{extension}"] = f"frames/{arm}.{tick}.{extension}"
    return result


def check_inputs(root):
    require(experiment.digest(root/"input/baseline-manifest.json") == BASELINE_SHA,"wrong parent manifest")
    baseline = experiment.read_json(root/"input/baseline-manifest.json")
    for dest,source in copies().items():
        require(experiment.digest(root/dest) == baseline["artifacts"][source],"frozen input changed")
    started = experiment.read_json(root/"started.json")
    require(started["rule"] == RULE and started["settings"] == settings(),"settings changed")
    for name,sha in started["frozen"].items():
        require(experiment.digest(root/name) == sha,"frozen build/source input changed")
    require(experiment.digest(root/"input/protocol.md") == started["sources"][PROTOCOL],"protocol changed")
    cache = (root/"input/CMakeCache.txt").read_text()
    flags = {"DARK_GUARD":"ON","PURCHASE_VETO":"ON","WIDE_DISPERSAL":"ON","WATER_HEADROOM":"ON",
             "COMBINED_EXPERIMENT":"ON","LARGE_POOL":"ON","LEAF_MAINTENANCE":"ON","BOTTOM_DRAINAGE":"OFF",
             "LARGE_SEED_BANK":"OFF","SEED_RESERVE":"OFF","FOCAL_SEED_VETO":"OFF"}
    require(all(f"TOY_FACTORY_GARDEN_{k}:BOOL={v}\n" in cache for k,v in flags.items()),"wrong ecology build")
    require("TOY_FACTORY_SIMULATOR_SANITIZERS:BOOL=ON\n" in cache and
            "CMAKE_C_FLAGS_RELWITHDEBINFO:STRING=-O2 -g\n" in cache,"wrong build checks")
    old,new = [guard.prior.prior.native_hashes(root/n) for n in ("input/native-source.tar.gz","source.tar.gz")]
    allowed = {"sim/garden_purchase_veto.c","sim/garden_purchase_veto_test.c","src/garden_purchase_veto.h",
               "sim/garden_inspect.c","sim/garden_replay.c"}
    require(old.keys() == new.keys() and {k for k in new if new[k] != old[k]} <= allowed,
            "general guard/world/model code changed")
    require(all(started["sources"].get(k) == v for k,v in new.items()),"native archive differs")


def check_capture(root):
    check_inputs(root)
    capture = experiment.read_json(root/"capture.json")
    require([(c["artifact"],c["command"]) for c in capture["calls"]] == commands(),"wrong native inventory")
    for name in capture["artifacts"]:
        gallery.artifact(root,capture,name)
    for target,command in commands():
        require(target in capture["artifacts"] and ("--framebuffer" not in command or command[-1] in capture["artifacts"]),
                "missing capture")
    return capture


def finish(root):
    capture = check_capture(root)
    sources = experiment.source_files()
    require(sources == experiment.read_json(root/"started.json")["sources"],"sources changed before analysis")
    result = analyze(root,True)
    require(result == analyze(root),"repeated analysis differs")
    for f in result["frames"]:
        gallery.write_png(root/f["png"],240,240,gallery.rgb565be_to_rgb888((root/f["framebuffer"]).read_bytes()))
    gallery.contact_sheet(root,[[f for f in result["frames"] if f["arm"] == arm] for arm in ARMS])
    require(experiment.source_files() == sources,"sources changed during analysis")
    check_capture(root)
    experiment.write_json(root/"results.json",result)
    artifacts = {str(p.relative_to(root)):experiment.digest(p) for p in root.rglob("*") if p.is_file()}
    experiment.write_json(root/"manifest.json",{"rule":RULE,"status":"complete","sources":sources,
        "artifacts":artifacts,"native_calls":len(capture["calls"]),"artifact_bytes":sum((root/n).stat().st_size for n in artifacts)})


def verify(root):
    manifest = experiment.read_json(root/"manifest.json")
    require(manifest["rule"] == RULE and manifest["status"] == "complete","incomplete retry bundle")
    require(set(manifest["artifacts"]) == {str(p.relative_to(root)) for p in root.rglob("*")
            if p.is_file() and p != root/"manifest.json"},"extra/missing artifacts")
    for name in manifest["artifacts"]:
        gallery.artifact(root,manifest,name)
    check_capture(root)
    require(manifest["sources"] == experiment.read_json(root/"started.json")["sources"],"source provenance differs")
    result = analyze(root)
    require(result == experiment.read_json(root/"results.json"),"reanalysis differs")
    print("Verified both frozen references, two receipts, guard handoff, repeated ledgers and nine native frames",flush=True)
    return result


def collect(baseline,build,output):
    require(not output.exists() and output.is_relative_to(experiment.ROOT/"artifacts") and
            not output.is_relative_to(baseline) and not output.is_relative_to(build),"choose fresh separate output")
    require(experiment.digest(baseline/"manifest.json") == BASELINE_SHA,"wrong frozen parent")
    sources = experiment.source_files()
    output.mkdir(parents=True)
    experiment.snapshot_sources(output,sources)
    for name in ("input","bin","models","traces","frames"):
        (output/name).mkdir()
    for dest,source in copies().items():
        shutil.copy2(baseline/source,output/dest)
    shutil.copy2(baseline/"manifest.json",output/"input/baseline-manifest.json")
    shutil.copy2(experiment.ROOT/PROTOCOL,output/"input/protocol.md")
    for name in ("CMakeCache.txt","build.ninja"):
        shutil.copy2(build/name,output/"input"/name)
    for name in ("inspect","replay"):
        shutil.copy2(build/("toy-factory-garden-"+name),output/"bin"/name)
    frozen = {str(p.relative_to(output)):experiment.digest(p) for p in output.rglob("*") if p.is_file()}
    experiment.write_json(output/"started.json",{"rule":RULE,"settings":settings(),"sources":sources,"frozen":frozen})
    begin,timings = time.monotonic(),[]
    try:
        check_inputs(output)
        for target,command in commands():
            start = time.monotonic()
            if target.endswith(".gz"):
                with tempfile.TemporaryDirectory(prefix="garden-finish-retry-") as temporary:
                    raw = Path(temporary)/"trace.jsonl"
                    try:
                        experiment.command_run(command,raw,output,180)
                    except BaseException:
                        if raw.exists(): shutil.copy2(raw,output/(target+".failed-stdout"))
                        raise
                    experiment.compress(raw,output/target)
            else:
                experiment.command_run(command,output/target,output,180)
            timings.append({"artifact":target,"command":command,"seconds":time.monotonic()-start})
            for arm in ("control","finish"):
                if target == f"traces/{arm}.jsonl.gz":
                    require(experiment.digest(output/target) == experiment.digest(output/f"input/{arm}.jsonl.gz"),
                            "reference trace changed")
            print(f"Captured {len(timings)}/24: {target}",flush=True)
        require(experiment.source_files() == sources,"sources changed during capture")
        artifacts = {str(p.relative_to(output)):experiment.digest(p) for p in output.rglob("*") if p.is_file()}
        experiment.write_json(output/"capture.json",{"artifacts":artifacts,"calls":timings,"capture_seconds":time.monotonic()-begin})
        finish(output)
    except BaseException as error:
        experiment.write_json(output/"failure.json",{"error":str(error),"completed_calls":timings})
        raise


def portable_target(value):
    result = prior.portable_target(value,TARGETS[0])
    # Ordinary guard acceptance is not necessarily an executed purchase: the
    # forced second refusal has a valid, allowed forecast but no actual debit.
    paid = [{"tick":e["state"]["tick"],**r} for e in value["history"]
            if e["state"]["tick"] > TARGETS[0]["tick"] and e["budget"] is not None and e["budget"]["energy_growth"] > 0
            for r in e["events"] if r["kind"] == "growth" and not r["denied"]]
    result["first_later_accepted_growth"] = paid[0] if paid else None
    return result


def export(root,prefix,check=False):
    result = verify(root)
    compact = copy.deepcopy(result)
    for case in compact["cases"].values():
        case["targets"] = {name:portable_target(value) for name,value in case["targets"].items()}
    compact.update(manifest_sha256=experiment.digest(root/"manifest.json"),full_results_sha256=experiment.digest(root/"results.json"),
                   exporter_sha256=experiment.digest(Path(__file__)),capture_seconds=experiment.read_json(root/"capture.json")["capture_seconds"])
    target,folder = prefix.with_name(prefix.name+"-summary.json"),prefix.with_name(prefix.name+"-frames")
    images = {prefix.with_suffix(".png"):root/"contact-sheet.png"}
    images.update({folder/(f["id"]+".png"):root/f["png"] for f in result["frames"]})
    require(not prefix.is_relative_to(root),"export outside frozen evidence")
    if not check:
        require(not target.exists() and not folder.exists() and not any(p.exists() for p in images),"export exists")
        folder.mkdir(parents=True)
        experiment.write_json(target,compact)
        for dest,source in images.items(): shutil.copy2(source,dest)
    require(experiment.read_json(target) == compact and all(experiment.digest(p) == experiment.digest(q)
            for p,q in images.items()),"portable retry evidence differs")
    print("Portable retry summary and fixed native images verified",flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline",type=Path,default=experiment.ROOT/"artifacts/garden-renewal-purchase-veto-v1")
    parser.add_argument("--build",type=Path,default=experiment.ROOT/"artifacts/build-host-finish-retry-docker")
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
        collect(args.baseline.resolve(),args.build.resolve(),args.output.resolve())


if __name__ == "__main__":
    main()
