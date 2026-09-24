#!/usr/bin/env python3
"""Fixed four-world host A/B of a full-night structural growth guard."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from functools import lru_cache
from itertools import zip_longest
import json
from pathlib import Path
from garden_plant_slots import plant_capacity
import shutil
import tempfile
import time

import garden_renewal_night_capacity as shadow

panel, failures, experiment, require = shadow.panel, shadow.failures, shadow.experiment, shadow.require
guard, startup, gallery = panel.guard, panel.startup, panel.gallery
RULE, NATIVE = "garden-renewal-capacity-guard-v1", "full-night-capacity-guard-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-capacity-guard-protocol.md"
BASELINE_SHA = shadow.PANEL_SHA
SHADOW = "benchmarks/garden-longevity/renewal-night-capacity-summary.json"
SHADOW_SHA = "fb4d4a628bea19270e8cfea8f5f2e1a5a2ca0dd270d4d40bf64a881033edabae"
ARMS, FRAMES = ("control", "capacity"), (12*panel.DAY,40*panel.DAY,panel.STOP)


@dataclass(frozen=True)
class Case:
    seed: str
    condition: str
    first_tick: int | None
    target_id: int | None

    @property
    def name(self):
        return f"{self.seed}.{self.condition}"

    @property
    def baseline(self):
        return panel.Case(self.seed,self.condition,"guard")


CASES = (Case("0d983a80","no-patch",37605,7), Case("58e36558","patch",134940,12),
         Case("beda710e","patch",138765,15), Case("abf7af73","patch",None,None))


def settings():
    return {"rule":RULE,"capacity_rule":NATIVE,"guard_rule":guard.GUARD,
            "baseline_manifest_sha256":BASELINE_SHA,"shadow_sha256":SHADOW_SHA,
            "cases":[asdict(c) for c in CASES],"arms":list(ARMS),"stop":panel.STOP,"late_start":panel.LATE,
            "frame_ticks":list(FRAMES),"models":guard.settings()["models"],"routing":guard.settings()["routing"],
            "budget":{"native_calls":64,"traces":16,"frame_replays":48,"training_calls":0},
            "role":"selected development-world mechanism comparison; no qualification or default promotion"}


def commands():
    calls = []
    for case in CASES:
        base = ["models/r2-n.tgm","rainfed-crowded",experiment.NIGHT_POLICY,"0x"+case.seed,
                "--leaf-policy","selective","--focal-model","models/r2-w.tgm","--focal-founder","5"]
        if case.baseline.patch:
            base += ["--disturbance-seed","0x"+case.baseline.patch]
        for arm in ARMS:
            name = f"{case.name}.{arm}"
            for suffix in ("",".repeat"):
                calls.append((f"traces/{name}{suffix}.jsonl.gz",
                              [f"bin/{arm}-inspect",*base,"--ecology","--ticks",str(panel.STOP)]))
            for tick in FRAMES:
                for suffix in ("",".repeat"):
                    stem = f"frames/{name}.{tick}{suffix}"
                    calls.append((stem+".json",[f"bin/{arm}-replay",*base,"--ticks",str(tick),"--framebuffer",stem+".rgb565"]))
    return calls


def without_capacity(row):
    return {k:v for k,v in row.items() if k != "night_capacity"}


@lru_cache(maxsize=512)
def expected_budget(nodes):
    return guard.native_budget(shadow.ANCHOR,256,nodes,0)


def audit_capacity(rows, arm, end=panel.STOP):
    """Keep ordinary guard verdicts intact; identify only subsequent refusals."""
    evaluated,denied,last = 0,0,-15
    vetoes,receipts,per_plant = set(),[],{}
    for row in rows:
        if row["type"] != "world":
            continue
        tick = row["tick"]
        require(tick == last+15 and tick <= end,"missing/reordered capacity census")
        last = tick
        if arm == "control":
            require("night_capacity" not in row,"disabled capacity check emitted metadata")
            continue
        require(arm == "capacity","unknown arm")
        audit = row["night_capacity"]
        require(set(audit) == {"rule","evaluated","denied","events"} and audit["rule"] == NATIVE,
                "wrong capacity metadata")
        ordinary = row["dark_guard"]["events"]
        expected = [i for i,e in enumerate(ordinary) if e["kind"] == "growth" and not e["denied"]
                    and e["nodes_after"] > e["nodes_before"]]
        require([e["expense"] for e in audit["events"]] == expected and len(expected) <= plant_capacity(row),
                "capacity did not check exactly the allowed positive-node proposals")
        for receipt,index in zip(audit["events"],expected,strict=True):
            event = ordinary[index]
            require(not event["invalid"] and event["nodes_after"] == event["nodes_before"]+1,
                    "invalid structural proposal")
            predicted = expected_budget(event["nodes_after"])
            refused = not shadow.capacity(event["nodes_after"])["viable_at_cap"]
            require(set(receipt) == {"expense","denied","budget"} and receipt["budget"] == predicted and
                    type(receipt["denied"]) is bool and receipt["denied"] == refused and
                    refused == (predicted["death_step"] != 0),"native/independent capacity verdict differs")
            evaluated += 1
            if not refused:
                continue
            denied += 1
            identity = event["id"]
            require((tick,identity) not in vetoes,"duplicate capacity refusal")
            vetoes.add((tick,identity))
            point = {"tick":tick,"phase":(64+tick//15)%256,**event}
            record = per_plant.setdefault(identity,{"id":identity,"attempts":0,"first":point,"last":point,
                "current_streak":0,"longest_streak":0,"energy_costs_refused":0,"water_costs_refused":0})
            record["current_streak"] = record["current_streak"]+1 if record["attempts"] and record["last"]["tick"]+15 == tick else 1
            record["longest_streak"] = max(record["longest_streak"],record["current_streak"])
            record["attempts"] += 1
            record["last"] = point
            record["energy_costs_refused"] += event["energy_cost"]
            record["water_costs_refused"] += event["water_cost"]
            receipts.append({"tick":tick,"id":identity,"expense":index,"node":event["node"]})
        require(audit["evaluated"] == evaluated and audit["denied"] == denied,
                "capacity counters do not reconcile")
        require(all(p["nodes"] <= 64 for p in row["plants"] if not p["dead"]),"treatment committed unsafe body")
    require(last == end,"truncated capacity audit")
    return vetoes,{"evaluated":evaluated,"denied":denied,"refusals":receipts,
                   "plants":[{k:v for k,v in r.items() if k != "current_streak"} for r in per_plant.values()]}


def check_prefix(control,treated,case):
    matching = 0
    for a,b in zip_longest(control,treated):
        require(a is not None and b is not None,"truncated comparison prefix")
        if a == without_capacity(b):
            require(case.first_tick is None or a["tick"] <= case.first_tick,"missing declared first change")
            matching += 1
            continue
        require(case.first_tick is not None and a["type"] == b["type"] == "world" and
                a["tick"] == b["tick"] == case.first_tick,"divergence outside declared first crossing")
        left,right = [{p["id"]:p for p in r["plants"]} for r in (a,b)]
        require(left.keys() == right.keys(),"plant identities changed at first refusal")
        refused = [e for e in b["night_capacity"]["events"] if e["denied"]]
        require(len(refused) == 1,"first refusal not isolated")
        index = refused[0]["expense"]
        event = b["dark_guard"]["events"][index]
        require(a["dark_guard"]["events"][:index+1] == b["dark_guard"]["events"][:index+1],
                "ordinary expenses changed before the capacity refusal")
        require(event["id"] == case.target_id and (event["nodes_before"],event["nodes_after"]) == (64,65)
                and not event["denied"],"wrong first affected proposal")
        p,q = left[case.target_id],right[case.target_id]
        # Seed production later in this same step can react to the saved purchase.
        # Reconcile both post-stores with their independently observed seed costs.
        seed_a,seed_b = int(p["reproduction_cooldown"] == 16),int(q["reproduction_cooldown"] == 16)
        require(q["nodes"] == 64 and p["nodes"] == 65 and
                q["energy"]+48*seed_b == p["energy"]+48*seed_a+event["energy_cost"] and
                q["water"]+24*seed_b == p["water"]+24*seed_a+event["water_cost"] and
                p["agent"]["extend"] == q["agent"]["extend"]+1 and
                p["agent"]["decisions"] == q["agent"]["decisions"]+1,"wrong first body/payment/action delta")
        return {"tick":case.first_tick,"matching_records":matching,"receipt":event,"control":p,"capacity":q,
                "same_step_other_changed":[i for i in left if i != case.target_id and left[i] != right[i]]}
    require(case.first_tick is None and matching > 0,"expected crossing never occurred or empty control")
    return {"tick":None,"matching_records":matching,"negative_control_identical":True}


def activity(history, first=0):
    total = Counter(extend=0,finish=0,wait=0,renewal=0,seeds=0)
    last = None
    for e in history:
        if e["state"]["tick"] < first or e["budget"] is None:
            continue
        b = e["budget"]
        step = {"extend":b["extensions"],"finish":b["finishes"],"wait":b["waits"],
                "renewal":b.get("energy_renewal",0)//9,"seeds":b["energy_seeds"]//48}
        total.update(step)
        if any(step.values()):
            last = {"tick":e["state"]["tick"],**step}
    return {"counts":total,"last_activity":last}


def analyze_case(root,case,arm,create=False):
    name = f"{case.name}.{arm}"
    path = root/f"traces/{name}.jsonl.gz"
    require(experiment.digest(path) == experiment.digest(root/f"traces/{name}.repeat.jsonl.gz"),"native trace repeat differs")
    if arm == "control":
        require(experiment.digest(path) == experiment.digest(root/f"input/{case.name}.jsonl.gz"),"rebuilt control changed")
    prefix = check_prefix(startup.read_trace(root/f"input/{case.name}.jsonl.gz"),startup.read_trace(path),case) if arm == "capacity" else None
    raw,boundaries = panel.split_rows(startup.read_trace(path),case.baseline.patch)
    vetoes,capacity = audit_capacity(raw,arm)
    routed,_ = guard.prior.neighbors.check_routing(iter(raw),guard.prior.ROUTE)
    accounted,ordinary = guard.accounting_rows(raw,"guard",stop=panel.STOP,boundaries=boundaries,
                                               retain_events=False,growth_vetoes=vetoes)
    worlds = [r for r in accounted if r["type"] == "world"]
    for label,rows in (("accounting",accounted),("worlds",worlds)):
        target = root/f"traces/{name}.{label}.jsonl.gz"
        if create:
            guard.write_accounting(target,rows)
        require(rows == list(startup.read_trace(target)),"derived accounting differs")
    world,_ = panel.competition.world_analysis(root/f"traces/{name}.worlds.jsonl.gz","selective",512,
                                               panel.STOP,panel.LATE,disturbances=boundaries)
    tips = startup.tips.analyze_stream((json.dumps(r) for r in accounted if r["type"] != "leaf-bid"),
                                       panel.STOP,panel.LATE,512,disturbances=boundaries)
    records = {p["id"]:p for p in world["lineages"]}
    for p in tips["lineages"]:
        require(all(p[k] == records[p["id"]][k] for k in ("parent","species","birth_tick","death_tick")),
                "tip/resource lifetimes disagree")
    extra = panel.supplementary(worlds,boundaries,records,case.baseline)
    for window in ("whole","late"):
        require(all(tips["windows"][window][k] == extra["exposure"][window][k]
                    for k in ("living_steps","tipless_steps","world_steps")),"exposure differs")
    histories,checked = failures.histories(worlds,boundaries,records,panel.STOP)
    for p in capacity["plants"]:
        history = histories[p["id"]]
        p.update(lineage=records[p["id"]],after_first_refusal=activity(history,p["first"]["tick"]),
                 outcome=history[-1]["terminal"] or "alive-at-end",last_state=history[-1]["state"])
    targets = None
    if case.target_id is not None:
        history = histories[case.target_id]
        targets = {"lineage":records[case.target_id],"last_state":history[-1]["state"],
                   "first_full_night":shadow.first_full_night(history,{"tick":case.first_tick}),
                   "after_crossing_time":activity(history,case.first_tick),
                   "offspring":panel.competition.lifetime_cohort(records,panel.STOP,selected_ids={i for i,p in records.items() if p["parent"] == case.target_id})}
    summary = panel.summary(world,extra,ordinary)
    if arm == "control":
        expected = experiment.read_json(root/"input/baseline-results.json")["cases"][case.baseline.name]
        require(summary == expected["summary"] and world["lineages"] == expected["lineages"] and
                extra["daily"] == expected["daily"],"rebuilt control analysis differs")
    events,frames = [b["event"] for b in boundaries.values()],[]
    samples = {r["tick"]:boundaries.get(r["tick"],{}).get("after",r) for r in worlds if r["tick"] in FRAMES}
    for tick in FRAMES:
        stem = f"frames/{name}.{tick}"
        value = experiment.read_json(root/(stem+".json"))
        pixels = (root/(stem+".rgb565")).read_bytes()
        panel.check_frame(value,samples[tick],case.baseline,tick,pixels,events)
        require(value.get("night_capacity") == samples[tick].get("night_capacity"),"frame/census capacity metadata differs")
        require(value == experiment.read_json(root/(stem+".repeat.json")) and
                pixels == (root/(stem+".repeat.rgb565")).read_bytes(),"native frame repeat differs")
        if arm == "control" and tick == panel.STOP:
            require(value == experiment.read_json(root/f"input/{case.name}.{tick}.json") and
                    pixels == (root/f"input/{case.name}.{tick}.rgb565").read_bytes(),"saved endpoint frame changed")
        frames.append({"id":f"{name}.{tick}","case":case.name,"arm":arm,"tick":tick,"result":value,
                       "framebuffer":stem+".rgb565","png":stem+".png"})
    activities = {str(i):activity(h) for i,h in histories.items()}
    print("Audited",name,flush=True)
    return {"summary":summary,"prefix":prefix,"capacity":capacity,"target":targets,"lineages":world["lineages"],
            "daily":extra["daily"],"events":events,"routing":routed,"checked_live_histories":checked,
            "activity":activities,"tip_audit":{k:tips[k] for k in ("totals","windows")}},frames


def compare(control,treated):
    fields = ("births","natural_deaths","environmental_deaths","seeds_created","seeds_expired",
              "descendant_seeds","seed_producing_descendant_parents")
    return {"later_newborn_ids_not_matched":True,
            "windows":{w:{"delta":{k:treated["summary"]["windows"][w][k]-control["summary"]["windows"][w][k] for k in fields},
                "cohort_delta":{k:treated["summary"]["windows"][w]["cohort"][k]-control["summary"]["windows"][w]["cohort"][k] for k in control["summary"]["windows"][w]["cohort"]},
                "exposure_delta":{k:treated["summary"]["windows"][w]["exposure"][k]-control["summary"]["windows"][w]["exposure"][k] for k in control["summary"]["windows"][w]["exposure"]}}
                for w in ("whole","late")}}


def analyze(root,create=False):
    results,frames,comparisons = {},[],{}
    for case in CASES:
        for arm in ARMS:
            value,captured = analyze_case(root,case,arm,create)
            results[f"{case.name}.{arm}"] = value
            frames += captured
        comparisons[case.name] = compare(*(results[f"{case.name}.{arm}"] for arm in ARMS))
        if case.first_tick is None:
            a,b = (results[f"{case.name}.{arm}"] for arm in ARMS)
            require(b["capacity"]["denied"] == 0 and all(a[k] == b[k] for k in
                    ("summary","lineages","daily","events","activity","tip_audit")),"negative-control outcome changed")
            for tick in FRAMES:
                left,right = [root/f"frames/{case.name}.{arm}.{tick}.rgb565" for arm in ARMS]
                require(left.read_bytes() == right.read_bytes(),"negative-control image changed")
    return {"rule":RULE,"settings":settings(),"cases":results,"comparisons":comparisons,"frames":frames}


def copies():
    result = {"input/baseline-results.json":"results.json"}
    result.update({f"models/{n}.tgm":f"models/{n}.tgm" for n in settings()["models"]})
    for case in CASES:
        result[f"input/{case.name}.jsonl.gz"] = f"traces/{case.baseline.name}.jsonl.gz"
        for extension in ("json","rgb565"):
            result[f"input/{case.name}.{panel.STOP}.{extension}"] = f"frames/{case.baseline.name}.{panel.STOP}.{extension}"
    return result


def check_inputs(root):
    require(experiment.digest(root/"input/baseline-manifest.json") == BASELINE_SHA,"wrong baseline manifest")
    baseline = experiment.read_json(root/"input/baseline-manifest.json")
    for dest,source in copies().items():
        require(experiment.digest(root/dest) == baseline["artifacts"][source],"frozen baseline copy changed")
    require(experiment.digest(root/"input/shadow.json") == SHADOW_SHA,"wrong shadow evidence")
    started = experiment.read_json(root/"started.json")
    require(started["rule"] == RULE and started["settings"] == settings(),"capture settings changed")
    require(experiment.digest(root/"input/protocol.md") == started["sources"][PROTOCOL],"protocol changed")
    for name,sha in started["frozen"].items():
        require(experiment.digest(root/name) == sha,"source/build/input changed")
    common = {"DARK_GUARD":"ON","PURCHASE_VETO":"OFF","WIDE_DISPERSAL":"ON","WATER_HEADROOM":"ON",
              "COMBINED_EXPERIMENT":"ON","LARGE_POOL":"ON","LEAF_MAINTENANCE":"ON","BOTTOM_DRAINAGE":"OFF",
              "LARGE_SEED_BANK":"OFF","SEED_RESERVE":"OFF","FOCAL_SEED_VETO":"OFF"}
    for arm in ARMS:
        cache = (root/f"input/{arm}-CMakeCache.txt").read_text()
        flags = {**common,"NIGHT_CAPACITY":"ON" if arm == "capacity" else "OFF"}
        require(all(f"TOY_FACTORY_GARDEN_{k}:BOOL={v}\n" in cache for k,v in flags.items()),"wrong experimental build")
        require("TOY_FACTORY_SIMULATOR_SANITIZERS:BOOL=ON\n" in cache and
                "CMAKE_C_FLAGS_RELWITHDEBINFO:STRING=-O2 -g\n" in cache and
                "CMAKE_BUILD_TYPE:STRING=RelWithDebInfo\n" in cache,"wrong build/UBSan settings")
    old = experiment.read_json(root/"input/shadow.json")["native_sources"]
    new = guard.prior.prior.native_hashes(root/"source.tar.gz")
    added = {"src/garden_night_capacity.h","sim/garden_night_capacity.c","sim/garden_night_capacity_test.c"}
    changed = {"src/garden_world.c","src/garden_world.h","sim/garden_inspect.c","sim/garden_replay.c",
               # Existing fixtures must account for ordinary dark-guard receipts/refusals.
               "sim/garden_seed_reserve_test.c","sim/garden_leaf_test.c"}
    require(old.keys() <= new.keys() and new.keys()-old.keys() == added and
            {n for n in old if old[n] != new[n]} <= changed,"unrelated native changes in capacity experiment")
    require(all(started["sources"].get(n) == sha for n,sha in new.items()),"native source archive differs")


def check_capture(root):
    check_inputs(root)
    capture = experiment.read_json(root/"capture.json")
    require(capture["rule"] == RULE and capture["settings"] == settings() and
            [(c["artifact"],c["command"]) for c in capture["calls"]] == commands(),"wrong native call inventory")
    for name in capture["artifacts"]:
        gallery.artifact(root,capture,name)
    for target,command in commands():
        require(target in capture["artifacts"] and ("--framebuffer" not in command or command[-1] in capture["artifacts"]),
                "missing declared native capture")
    return capture


def finish(root):
    require(not (root/"manifest.json").exists() and not (root/"results.json").exists(),"already finalized")
    capture = check_capture(root)
    sources = experiment.read_json(root/"started.json")["sources"]
    require(experiment.source_files() == sources,"sources changed before analysis")
    begin = time.monotonic()
    result = analyze(root,True)
    require(result == analyze(root),"repeated capacity analysis differs")
    for f in result["frames"]:
        gallery.write_png(root/f["png"],240,240,gallery.rgb565be_to_rgb888((root/f["framebuffer"]).read_bytes()))
    gallery.contact_sheet(root,[[f for tick in FRAMES for arm in ARMS for f in result["frames"]
                                if f["case"] == case.name and f["tick"] == tick and f["arm"] == arm] for case in CASES])
    require(experiment.source_files() == sources,"sources changed during analysis")
    check_capture(root)
    experiment.write_json(root/"results.json",result)
    experiment.write_json(root/"timings.json",{"analysis_and_repeat_seconds":time.monotonic()-begin,
        "capture_seconds":capture["capture_seconds"],"calls":capture["calls"]})
    artifacts = {str(p.relative_to(root)):experiment.digest(p) for p in root.rglob("*") if p.is_file()}
    experiment.write_json(root/"manifest.json",{"rule":RULE,"status":"complete","sources":sources,
        "artifacts":artifacts,"native_calls":len(capture["calls"]),"artifact_bytes":sum((root/n).stat().st_size for n in artifacts)})
    print("Capacity A/B complete: exact repeated captures and analysis verified",flush=True)


def verify(root):
    manifest = experiment.read_json(root/"manifest.json")
    require(manifest["rule"] == RULE and manifest["status"] == "complete","incomplete capacity bundle")
    require(set(manifest["artifacts"]) == {str(p.relative_to(root)) for p in root.rglob("*")
            if p.is_file() and p != root/"manifest.json"},"extra/missing artifact")
    for name in manifest["artifacts"]:
        gallery.artifact(root,manifest,name)
    capture = check_capture(root)
    require(manifest["sources"] == experiment.read_json(root/"started.json")["sources"] and
            experiment.read_json(root/"timings.json")["calls"] == capture["calls"],"source/call provenance differs")
    result = analyze(root)
    require(result == experiment.read_json(root/"results.json"),"saved capacity analysis differs")
    print("Verified four controls, isolated prefixes, every capacity decision and 24 repeated frames",flush=True)
    return result


def collect(baseline,builds,output):
    require(not output.exists() and output.is_relative_to(experiment.ROOT/"artifacts") and
            not output.is_relative_to(baseline) and not any(output.is_relative_to(b) for b in builds.values()),
            "choose fresh output outside inputs/builds")
    shadow.check_frozen(baseline,BASELINE_SHA)
    require(experiment.digest(experiment.ROOT/SHADOW) == SHADOW_SHA,"shadow evidence changed")
    sources = experiment.source_files()
    output.mkdir(parents=True)
    experiment.snapshot_sources(output,sources)
    for name in ("input","bin","models","traces","frames"):
        (output/name).mkdir()
    for dest,source in copies().items():
        shutil.copy2(baseline/source,output/dest)
    shutil.copy2(baseline/"manifest.json",output/"input/baseline-manifest.json")
    shutil.copy2(experiment.ROOT/SHADOW,output/"input/shadow.json")
    shutil.copy2(experiment.ROOT/PROTOCOL,output/"input/protocol.md")
    for arm in ARMS:
        for name in ("CMakeCache.txt","build.ninja"):
            shutil.copy2(builds[arm]/name,output/f"input/{arm}-{name}")
        for name in ("inspect","replay"):
            shutil.copy2(builds[arm]/("toy-factory-garden-"+name),output/f"bin/{arm}-{name}")
    frozen = {str(p.relative_to(output)):experiment.digest(p) for p in output.rglob("*") if p.is_file()}
    experiment.write_json(output/"started.json",{"rule":RULE,"settings":settings(),"sources":sources,"frozen":frozen})
    begin,timings = time.monotonic(),[]
    try:
        check_inputs(output)
        for target,command in commands():
            start = time.monotonic()
            if target.endswith(".gz"):
                with tempfile.TemporaryDirectory(prefix="garden-capacity-guard-") as temporary:
                    raw = Path(temporary)/"trace.jsonl"
                    try:
                        experiment.command_run(command,raw,output,180)
                    except BaseException:
                        if raw.exists():
                            shutil.copy2(raw,output/(target+".failed-stdout"))
                        raise
                    experiment.compress(raw,output/target)
            else:
                experiment.command_run(command,output/target,output,180)
            timings.append({"artifact":target,"command":command,"seconds":time.monotonic()-start})
            for case in CASES:
                if target == f"traces/{case.name}.control.jsonl.gz":
                    require(experiment.digest(output/target) == experiment.digest(output/f"input/{case.name}.jsonl.gz"),
                            "rebuilt reference changed; stop before treatment")
            print(f"Captured {len(timings)}/64: {target}",flush=True)
        require(experiment.source_files() == sources,"sources changed during capture")
        artifacts = {str(p.relative_to(output)):experiment.digest(p) for p in output.rglob("*") if p.is_file()}
        experiment.write_json(output/"capture.json",{"rule":RULE,"settings":settings(),"artifacts":artifacts,
            "calls":timings,"capture_seconds":time.monotonic()-begin})
        finish(output)
    except BaseException as error:
        experiment.write_json(output/"failure.json",{"error":str(error),"completed_calls":timings})
        raise


def export(root,prefix,check=False):
    require(not prefix.is_relative_to(root),"export must stay outside frozen evidence")
    result = {**verify(root),"manifest_sha256":experiment.digest(root/"manifest.json"),
              "full_results_sha256":experiment.digest(root/"results.json"),
              "exporter_sha256":experiment.digest(Path(__file__)),
              "timing":experiment.read_json(root/"timings.json")}
    target = prefix.with_name(prefix.name+"-summary.json")
    folder = prefix.with_name(prefix.name+"-frames")
    images = {prefix.with_suffix(".png"):root/"contact-sheet.png"}
    images.update({folder/(f["id"]+".png"):root/f["png"] for f in result["frames"]})
    if not check:
        require(not target.exists() and not folder.exists() and not any(p.exists() for p in images),"export already exists")
        folder.mkdir(parents=True)
        experiment.write_json(target,result)
        for dest,source in images.items():
            shutil.copy2(source,dest)
    require(experiment.read_json(target) == result and all(experiment.digest(p) == experiment.digest(q)
            for p,q in images.items()),"portable capacity evidence differs")
    print("Verified portable capacity results and every fixed native image",flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline",type=Path,default=experiment.ROOT/"artifacts/garden-renewal-dark-panel-v1")
    parser.add_argument("--control-build",type=Path,default=experiment.ROOT/"artifacts/build-host-capacity-control-docker")
    parser.add_argument("--capacity-build",type=Path,default=experiment.ROOT/"artifacts/build-host-capacity-guard-docker")
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
        collect(args.baseline.resolve(),{a:getattr(args,a+"_build").resolve() for a in ARMS},args.output.resolve())


if __name__ == "__main__":
    main()
