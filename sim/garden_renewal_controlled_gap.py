#!/usr/bin/env python3
"""One frozen named-neighbor export, with unchanged control and recruitment follow-up."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from itertools import zip_longest
from pathlib import Path
import shutil
import tempfile
import time

import garden_renewal_rescued_seeds as seed_audit

parent, ledger = seed_audit.parent, seed_audit.ledger
experiment, panel, guard, gallery = parent.experiment, parent.panel, parent.guard, parent.gallery
require, read_trace = parent.require, parent.startup.read_trace
RULE, NATIVE = "garden-renewal-controlled-gap-v1", "named-adult-export-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-controlled-gap-protocol.md"
RESCUED = "benchmarks/garden-longevity/renewal-rescued-seeds-summary.json"
RESCUED_SHA = "5dbf08356e6968cb33e52f835c2f775bdbc7e77b27712d13a37b79612378a913"
BASELINE_SHA = seed_audit.BASELINE_SHA
SEED, TARGET, REMOVED, AT, STOP, LATE = "0d983a80", 7, 1, 46080, panel.STOP, panel.LATE
ARMS, FRAMES, SPECIES = ("control", "gap"), (AT, 49920, 61440, STOP), ("flower", "shrub", "ground-cover")
REFERENCE = "0d983a80.no-patch.capacity"


def settings():
    return {"rule":RULE,"gap_protocol":NATIVE,"seed":SEED,"removed":REMOVED,"target":TARGET,
            "gap_tick":AT,"stop":STOP,"late_start":LATE,"frame_ticks":list(FRAMES),
            "models":parent.settings()["models"],"routing":parent.settings()["routing"],
            "budget":{"native_calls":24,"traces":8,"frame_replays":16,"training_calls":0},
            "role":"selected development-world gap diagnostic; not spacing-only or environment qualification"}


def commands():
    calls = []
    for arm in ARMS:
        base = ["models/r2-n.tgm","rainfed-crowded",experiment.NIGHT_POLICY,"0x"+SEED,
                "--leaf-policy","selective","--focal-model","models/r2-w.tgm","--focal-founder","5"]
        if arm == "gap":
            base += ["--gap-at",str(AT),"--gap-lineage",str(REMOVED)]
        for kind,flag in (("world","--ecology"),("sites","--seed-sites")):
            for suffix in ("",".repeat"):
                calls.append((f"traces/{arm}.{kind}{suffix}.jsonl.gz",
                              ["bin/inspect",*base,flag,"--ticks",str(STOP)]))
        for tick in FRAMES:
            for suffix in ("",".repeat"):
                stem = f"frames/{arm}.{tick}{suffix}"
                calls.append((stem+".json",["bin/replay",*base,"--ticks",str(tick),"--framebuffer",stem+".rgb565"]))
    return calls


def validate_boundary(before, after, event):
    require(set(event) == {"type","protocol","tick","id","column","nodes","energy","water","before_hash","after_hash"}
            and event["type"] == "gap" and event["protocol"] == NATIVE,"wrong export metadata")
    require(before["tick"] == after["tick"] == event["tick"] == AT and event["id"] == REMOVED
            and event["column"] == 3,"wrong named boundary")
    require(before["type"] == after["type"] and before["hash"] == event["before_hash"]
            and after["hash"] == event["after_hash"],"export hash/type mismatch")
    removed = [p for p in before["plants"] if p["id"] == REMOVED]
    require(len(removed) == 1 and not removed[0]["dead"] and removed[0]["parent"] == 0
            and removed[0]["column"] == 3,"missing declared living founder")
    require([p for p in before["plants"] if p["id"] != REMOVED] == after["plants"],"export changed survivor state")
    require(after["nodes"] == before["nodes"]-event["nodes"] and after["living"] == before["living"]-1,
            "wrong exported counts")
    strip = lambda seeds: [{k:v for k,v in s.items() if k != "blockers"} for s in seeds]
    require(strip(before["seeds"]) == strip(after["seeds"]),"export changed seed bank")
    require(before.keys() == after.keys() and all(before[k] == after[k] for k in
            before.keys()-{"hash","nodes","living","plants","seeds","sites"}),"unexpected boundary change")
    if before["type"] == "world":
        p = removed[0]
        require(p["species"] == "flower" and p["generation"] == 0 and p["age_ecology_ticks"] >= 256
                and all(p[k] == event[k] for k in ("nodes","column","energy","water")),"wrong named adult/export costs")
        require(before["hash"] == "5eea8cea" and (event["nodes"],event["energy"],event["water"]) == (36,240,510),
                "saved intervention reference changed")
    else:
        require(before["type"] == "seed-sites" and len(before["sites"]) == len(after["sites"]) == 28,
                "wrong spatial boundary")
        require(all(a[1] == b[1] and a[2] >= b[2] for b,a in zip(before["sites"],after["sites"],strict=True)),
                "export changed soil or reduced light")
        panel.competition.spatial_snapshot(after)


def split_rows(rows, arm, kind="world"):
    require(arm in ARMS and kind in ("world","seed-sites"),"wrong trace scope")
    ordinary, boundary, previous = [], None, None
    iterator = iter(rows)
    for row in iterator:
        if row["type"] != "gap":
            require(row["type"] in (("world","bid","leaf-bid") if kind == "world" else (kind,)),"unknown trace record")
            ordinary.append(row)
            previous = row
            continue
        after = next(iterator,None)
        require(arm == "gap" and boundary is None and previous is not None and previous["type"] == kind
                and after is not None and after["type"] == kind,"missing/repeated/unscheduled export")
        validate_boundary(previous,after,row)
        boundary = {"before":previous,"event":row,"after":after}
    require((boundary is not None) == (arm == "gap"),"missing declared export")
    return ordinary,boundary


def check_prefix(control, treated):
    count = 0
    for a,b in zip_longest(control,treated):
        require(a is not None and b is not None and a == b,"prefix differs before declared removal")
        count += 1
        if a["type"] in ("world","seed-sites") and a["tick"] == AT:
            return count
    raise RuntimeError("prefix never reaches intervention")


def check_sites(worlds, sites, seeds, records, *, spacing_at=None):
    lookup = {(s["parent"],s["birth_tick"]):s for s in seeds}
    require(len(lookup) == len(seeds),"duplicate reconstructed seed key")
    births = defaultdict(list)
    for seed in seeds:
        births[seed["birth_tick"]].append(seed)
    active = []
    checked = 0
    for w,s in zip_longest(worlds,sites):
        require(w is not None and s is not None and all(w[k] == s[k] for k in
                ("tick","hash","nodes","living","births","deaths","seeds_created","seeds_expired")),"world/site state differs")
        require([{k:p[k] for k in ("parent","generation","column","blockers")} for p in w["seeds"]] ==
                [{k:p[k] for k in ("parent","generation","column","blockers")} for p in s["seeds"]],"world/site bank differs")
        require([p["id"] for p in w["plants"]] == [p["id"] for p in s["plants"]],"site occupants differ")
        panel.competition.spatial_snapshot(s, minimum_spacing=spacing_at(s) if spacing_at else 3)
        for a,b in zip(w["plants"],s["plants"],strict=True):
            require(all(a[k] == b[k] for k in ("id","parent","generation","column","dead"))
                    and a["species"] == SPECIES[b["species"]],"site lineage mismatch")
            support = 0 if a["dead"] else sum(1 << c for c in seed_audit.dispersal_support(a["column"],a["genome"][7]))
            require(b["dispersal_columns"] == support,
                    "native dispersal support differs")
        active = [seed for seed in active if seed["end_tick"] is None or seed["end_tick"] > s["tick"]]
        active.extend(births[s["tick"]])
        require(len(active) == len(s["seeds"]),"aged bank size differs from ordered reconstruction")
        for native,expected in zip(s["seeds"],active,strict=True):
            require(type(native["age"]) is int and 0 <= native["age"] < 256,"invalid logged seed age")
            birth = s["tick"]-native["age"]*15
            r = lookup.get((native["parent"],birth))
            require(r is expected and ledger.signature(native) == ledger.signature(r)
                    and SPECIES[native["species"]] == r["species"] == records[native["parent"]]["species"],
                    "logged age/order disagrees with reconstructed seed")
            require(native["blockers"] == (s["sites"][native["column"]][0] | int(native["age"] < 8)),"site/seed mask differs")
        checked += 1
    require(checked == STOP//15+1,"truncated site follow-up")
    return checked


def site_exposure(sites, boundary, seeds):
    columns = {str(c):{"open_steps":0,"spacing_free_steps":0,"first_open":None,"last_open":None,
                       "longest_open_streak":0,"masks":Counter()} for c in range(1,6)}
    streak = Counter()
    masks = {label:Counter() for label in ("all_parents","target","removed_parent")}
    target_seeds = {(s["parent"],s["birth_tick"]):s for s in seeds if s["parent"] == TARGET}
    target = {str(s["birth_tick"]):{"column":s["column"],"outcome":s["outcome"],"samples":0,
                                    "masks":Counter(),"first_reachable_open":None} for s in target_seeds.values()}
    samples = 0
    for ordinary in sites:
        tick = ordinary["tick"]
        # Post-export state owns the following [tick,tick+15) exposure interval.
        row = boundary["after"] if boundary is not None and tick == AT else ordinary
        if AT <= tick < STOP:
            samples += 1
            for c,data in columns.items():
                mask = row["sites"][int(c)][0]
                data["masks"][str(mask)] += 1
                data["open_steps"] += mask == 0
                data["spacing_free_steps"] += not mask&32
                streak[c] = streak[c]+1 if mask == 0 else 0
                data["longest_open_streak"] = max(data["longest_open_streak"],streak[c])
                if mask == 0:
                    data["first_open"] = tick if data["first_open"] is None else data["first_open"]
                    data["last_open"] = tick
        # Seed checks at AT preceded the export; never count its two snapshots twice.
        if tick <= AT:
            continue
        for s in ordinary["seeds"]:
            if s["age"] < 8:
                continue
            masks["all_parents"][str(s["blockers"])] += 1
            if s["parent"] == REMOVED:
                masks["removed_parent"][str(s["blockers"])] += 1
            if s["parent"] != TARGET:
                continue
            masks["target"][str(s["blockers"])] += 1
            birth = tick-s["age"]*15
            data = target[str(birth)]
            data["samples"] += 1
            data["masks"][str(s["blockers"])] += 1
            if data["first_reachable_open"] is None and any(ordinary["sites"][c][0] == 0 for c in range(3,10)):
                data["first_reachable_open"] = tick
    require(samples == (STOP-AT)//15,"wrong post-export interval coverage")
    return {"post_export_intervals":samples,"footprint_columns":columns,"post_export_mature_masks":masks,
            "target_seed_exposure":target}


def cohort(records, start, ids=None):
    selected = [p for p in records.values() if p["parent"] and p["birth_tick"] > start and (ids is None or p["id"] in ids)]
    return {**panel.competition.lifetime_cohort(records,STOP,start,ids),
            "natural_deaths":sum(p["death_tick"] is not None and "removal_tick" not in p for p in selected),
            "alive_at_end":sum(p["death_tick"] is None for p in selected),
            "parents":dict(Counter(str(p["parent"]) for p in selected))}


def outcomes(world, extra, seeds, worlds):
    records = {p["id"]:p for p in world["lineages"]}
    result = {}
    for label,start in (("whole",-1),("post_export",AT),("late",LATE)):
        born = {i for i,p in records.items() if p["parent"] and p["birth_tick"] > start}
        footprint = {i for i in born if abs(records[i]["column"]-3) < 3}
        successful = [s for s in seeds if s["outcome"] == "germinated" and s["end_tick"] > start]
        deaths = [p for p in records.values() if p["death_tick"] is not None and p["death_tick"] > start and "removal_tick" not in p]
        result[label] = {"cohort":cohort(records,start),"footprint_cohort":cohort(records,start,footprint),
            "footprint_children":sorted(footprint),"first_footprint_birth":min((records[i]["birth_tick"] for i in footprint),default=None),
            "natural_deaths":len(deaths),"death_causes":dict(Counter(parent.startup.SHORTAGES[p["death_flags"]&6] for p in deaths)),
            "exports":sum(p.get("removal_tick",-1) > start for p in records.values()),
            "purchased_seeds":seed_audit.outcome_summary([s for s in seeds if s["birth_tick"] > start]),
            "germinated_existing_bank":sum(s["birth_tick"] <= start for s in successful),
            "germinated_new_purchases":sum(s["birth_tick"] > start for s in successful)}
        require(len(successful) == len(born),"recruitment/cohort mismatch")
    children = [p for p in records.values() if p["parent"] and p["birth_tick"] > AT]
    details = []
    for p in children:
        history = [{"tick":r["tick"],"sun_phase":r["sun_phase"],**plant}
                   for r in worlds if p["birth_tick"] <= r["tick"] <= min(STOP,p["birth_tick"]+panel.DAY)
                   for plant in r["plants"] if plant["id"] == p["id"]]
        live = [q for q in history if not q["dead"]]
        details.append({"lineage":p,"birth":history[0],"first_day_last_live":live[-1],
                        "first_shortage":next((q for q in history if q["flags"]&6),None)})
    result.update(final=extra["daily"][-1],target={"lineage":records[TARGET],
        "seeds":seed_audit.outcome_summary([s for s in seeds if s["parent"] == TARGET]),
        "offspring":cohort(records,-1,{i for i,p in records.items() if p["parent"] == TARGET})},
        post_export_children=details)
    return result


def analyze_case(root,arm,create=False):
    for kind in ("world","sites"):
        require(experiment.digest(root/f"traces/{arm}.{kind}.jsonl.gz") == experiment.digest(root/f"traces/{arm}.{kind}.repeat.jsonl.gz"),
                "native trace repeat differs")
    path = root/f"traces/{arm}.world.jsonl.gz"
    raw,boundary = split_rows(read_trace(path),arm)
    sites,site_boundary = split_rows(read_trace(root/f"traces/{arm}.sites.jsonl.gz"),arm,"seed-sites")
    prefix = None
    if arm == "control":
        require(experiment.digest(path) == experiment.digest(root/"input/control.jsonl.gz"),"rebuilt control changed")
    else:
        prefix = {kind:check_prefix(read_trace(root/f"traces/control.{kind}.jsonl.gz"),read_trace(root/f"traces/gap.{kind}.jsonl.gz"))
                  for kind in ("world","sites")}
        require(boundary["event"] == site_boundary["event"],"world/site export differs")
    vetoes,capacity = parent.audit_capacity(raw,"capacity")
    routing,_ = guard.prior.neighbors.check_routing(iter(raw),guard.prior.ROUTE)
    # Surviving plants are unchanged by the export. The ordinary budget adapter
    # iterates current plants, so it never charges an absent exported plant.
    accounted,ordinary = guard.accounting_rows(raw,"guard",stop=STOP,retain_events=False,growth_vetoes=vetoes)
    worlds = [r for r in accounted if r["type"] == "world"]
    world_path = root/f"traces/{arm}.worlds.jsonl.gz"
    if create:
        guard.write_accounting(world_path,worlds)
    require(worlds == list(read_trace(world_path)),"derived census differs")
    removal = boundary["event"] if boundary else None
    world,_ = panel.competition.world_analysis(world_path,"selective",512,STOP,LATE,removal=removal)
    records = {p["id"]:p for p in world["lineages"]}
    extra = panel.supplementary(worlds,{AT:boundary} if boundary else {},records,parent.CASES[0].baseline)
    # The ordered bank is unchanged by export; keep ordinary pre-export snapshots
    # for age/outcome accounting. Population context comes from post-export daily
    # samples, not the historical ledger's patch-only species-event field.
    full = ledger.seed_ledger(worlds,{},records)
    seeds = [{k:v for k,v in s.items() if k not in ("post_cutoff_blockers","sole_spacing_22")} for s in full["seeds"]]
    checked = check_sites(worlds,sites,seeds,records)
    result = outcomes(world,extra,seeds,worlds)
    if arm == "control":
        old = experiment.read_json(root/"input/rescued-seeds.json")["cases"][REFERENCE]
        require(world["lineages"] == old["lineages"] and seeds == old["seed_ledger"]["seeds"],"control lifetimes/seed ledger drift")
    frames = []
    points = {r["tick"]:r for r in worlds if r["tick"] in FRAMES}
    if boundary:
        points[AT] = boundary["after"]
    for tick in FRAMES:
        stem = f"frames/{arm}.{tick}"
        value = experiment.read_json(root/(stem+".json"))
        pixels = (root/(stem+".rgb565")).read_bytes()
        panel.check_frame(value,points[tick],parent.CASES[0].baseline,tick,pixels,[])
        require(value["night_capacity"] == points[tick]["night_capacity"],"frame capacity metadata differs")
        require(value == experiment.read_json(root/(stem+".repeat.json")) and pixels == (root/(stem+".repeat.rgb565")).read_bytes(),"frame repeat differs")
        if arm == "gap":
            require((value.get("gap_protocol"),value.get("gap_tick"),value.get("removed_id")) == (NATIVE,AT,REMOVED),"frame used wrong gap")
        else:
            require(not any(k in value for k in ("gap_protocol","gap_tick","removed_id")),"gap in control replay")
            if tick in (AT,STOP):
                require(value == experiment.read_json(root/f"input/control.{tick}.json") and
                        pixels == (root/f"input/control.{tick}.rgb565").read_bytes(),"old control frame changed")
        frames.append({"id":f"{arm}.{tick}","arm":arm,"tick":tick,"result":value,"png":stem+".png","framebuffer":stem+".rgb565"})
    print("Audited controlled gap:",arm,flush=True)
    return {"outcomes":result,"boundary":boundary,"site_boundary":site_boundary,"prefix":prefix,
            "lineages":world["lineages"],"seeds":seeds,"seed_summary":seed_audit.outcome_summary(seeds),
            "site_exposure":site_exposure(sites,site_boundary,seeds),"site_checkpoints":checked,
            "daily":extra["daily"],"exposure":extra["exposure"],"capacity":capacity,"ordinary_guard":ordinary,
            "routing":routing,"checked_live_budgets":world["windows"]["whole"]["budget_checked_live_steps"]},frames


def analyze(root,create=False):
    cases,frames = {},[]
    for arm in ARMS:
        cases[arm],new = analyze_case(root,arm,create)
        frames.extend(new)
    return {"rule":RULE,"settings":settings(),"cases":cases,"frames":frames}


def copies():
    result = {"input/control.jsonl.gz":f"traces/{REFERENCE}.jsonl.gz","input/native-source.tar.gz":"source.tar.gz",
              "input/prior-CMakeCache.txt":"input/capacity-CMakeCache.txt"}
    result.update({f"models/{n}.tgm":f"models/{n}.tgm" for n in settings()["models"]})
    result.update({f"input/control.{t}.{e}":f"frames/{REFERENCE}.{t}.{e}" for t in (AT,STOP) for e in ("json","rgb565")})
    return result


def check_inputs(root):
    require(experiment.digest(root/"input/parent-manifest.json") == BASELINE_SHA,"wrong parent manifest")
    manifest = experiment.read_json(root/"input/parent-manifest.json")
    for dest,source in copies().items():
        require(experiment.digest(root/dest) == manifest["artifacts"][source],"frozen parent copy changed")
    require(experiment.digest(root/"input/rescued-seeds.json") == RESCUED_SHA,"changed seed audit input")
    started = experiment.read_json(root/"started.json")
    require(started["rule"] == RULE and started["settings"] == settings(),"capture settings changed")
    require(experiment.digest(root/"input/protocol.md") == started["sources"][PROTOCOL],"changed protocol")
    for path,sha in started["frozen"].items():
        require(experiment.digest(root/path) == sha,"frozen input/build/source changed")
    cache = (root/"input/CMakeCache.txt").read_text()
    flags = {"NIGHT_CAPACITY":"ON","DARK_GUARD":"ON","PURCHASE_VETO":"OFF","WIDE_DISPERSAL":"ON",
             "WATER_HEADROOM":"ON","COMBINED_EXPERIMENT":"ON","LARGE_POOL":"ON","LEAF_MAINTENANCE":"ON",
             "BOTTOM_DRAINAGE":"OFF","LARGE_SEED_BANK":"OFF","SEED_RESERVE":"OFF","FOCAL_SEED_VETO":"OFF"}
    require(all(f"TOY_FACTORY_GARDEN_{k}:BOOL={v}\n" in cache for k,v in flags.items()) and
            all(s in cache for s in ("TOY_FACTORY_SIMULATOR_SANITIZERS:BOOL=ON\n","CMAKE_BUILD_TYPE:STRING=RelWithDebInfo\n",
                                     "CMAKE_C_FLAGS_RELWITHDEBINFO:STRING=-O2 -g\n")),"wrong build configuration")
    old,new = [guard.prior.prior.native_hashes(root/p) for p in ("input/native-source.tar.gz","source.tar.gz")]
    allowed = {"sim/garden_gap.c","sim/garden_gap.h","sim/garden_gap_test.c","sim/garden_inspect.c","sim/garden_replay.c"}
    require(old.keys() == new.keys() and {n for n in old if old[n] != new[n]} <= allowed,"unrelated native source change")
    require(all(started["sources"].get(n) == sha for n,sha in new.items()),"native archive differs")


def check_capture(root):
    check_inputs(root)
    capture = experiment.read_json(root/"capture.json")
    require(capture["rule"] == RULE and capture["settings"] == settings() and
            [(c["artifact"],c["command"]) for c in capture["calls"]] == commands(),"wrong call inventory")
    for path in capture["artifacts"]:
        gallery.artifact(root,capture,path)
    for target,command in commands():
        require(target in capture["artifacts"] and ("--framebuffer" not in command or command[-1] in capture["artifacts"]),"missing capture")
    return capture


def finish(root):
    require(not (root/"manifest.json").exists() and not (root/"results.json").exists(),"already finalized")
    capture = check_capture(root)
    sources = experiment.read_json(root/"started.json")["sources"]
    require(experiment.source_files() == sources,"sources changed before analysis")
    begin = time.monotonic()
    result = analyze(root,True)
    require(result == analyze(root),"repeated analysis differs")
    for f in result["frames"]:
        gallery.write_png(root/f["png"],240,240,gallery.rgb565be_to_rgb888((root/f["framebuffer"]).read_bytes()))
    gallery.contact_sheet(root,[[f for f in result["frames"] if f["arm"] == arm] for arm in ARMS])
    require(experiment.source_files() == sources,"sources changed during analysis")
    check_capture(root)
    experiment.write_json(root/"results.json",result)
    experiment.write_json(root/"timings.json",{"analysis_and_repeat_seconds":time.monotonic()-begin,
        "capture_seconds":capture["capture_seconds"],"calls":capture["calls"]})
    artifacts = {str(p.relative_to(root)):experiment.digest(p) for p in root.rglob("*") if p.is_file()}
    experiment.write_json(root/"manifest.json",{"rule":RULE,"status":"complete","sources":sources,
        "artifacts":artifacts,"native_calls":len(capture["calls"]),"artifact_bytes":sum((root/n).stat().st_size for n in artifacts)})
    print("Controlled gap complete: 24 exact repeated captures and repeated analysis verified",flush=True)


def verify(root):
    manifest = experiment.read_json(root/"manifest.json")
    require(manifest["rule"] == RULE and manifest["status"] == "complete","incomplete controlled-gap bundle")
    require(set(manifest["artifacts"]) == {str(p.relative_to(root)) for p in root.rglob("*")
            if p.is_file() and p != root/"manifest.json"},"extra/missing artifact")
    for path in manifest["artifacts"]:
        gallery.artifact(root,manifest,path)
    capture = check_capture(root)
    require(manifest["sources"] == experiment.read_json(root/"started.json")["sources"] and
            experiment.read_json(root/"timings.json")["calls"] == capture["calls"],"source/call provenance differs")
    result = analyze(root)
    require(result == experiment.read_json(root/"results.json"),"saved analysis differs")
    return result


def collect(baseline,build,output):
    require(not output.exists() and output.is_relative_to(experiment.ROOT/"artifacts") and
            not output.is_relative_to(baseline) and not output.is_relative_to(build),"choose fresh output outside inputs/build")
    parent.shadow.check_frozen(baseline,BASELINE_SHA)
    require(experiment.digest(experiment.ROOT/RESCUED) == RESCUED_SHA,"changed seed audit")
    parent.verify(baseline)
    sources = experiment.source_files()
    output.mkdir(parents=True)
    experiment.snapshot_sources(output,sources)
    for name in ("input","models","bin","traces","frames"):
        (output/name).mkdir()
    for dest,source in copies().items():
        shutil.copy2(baseline/source,output/dest)
    shutil.copy2(baseline/"manifest.json",output/"input/parent-manifest.json")
    shutil.copy2(experiment.ROOT/RESCUED,output/"input/rescued-seeds.json")
    shutil.copy2(experiment.ROOT/PROTOCOL,output/"input/protocol.md")
    for name in ("CMakeCache.txt","build.ninja"):
        shutil.copy2(build/name,output/"input"/name)
    for tool in ("inspect","replay"):
        shutil.copy2(build/("toy-factory-garden-"+tool),output/"bin"/tool)
    frozen = {str(p.relative_to(output)):experiment.digest(p) for p in output.rglob("*") if p.is_file()}
    experiment.write_json(output/"started.json",{"rule":RULE,"settings":settings(),"sources":sources,"frozen":frozen})
    begin,timings = time.monotonic(),[]
    try:
        check_inputs(output)
        for target,command in commands():
            start = time.monotonic()
            if target.endswith(".gz"):
                with tempfile.TemporaryDirectory(prefix="garden-controlled-gap-") as temporary:
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
            if target == "traces/control.world.jsonl.gz":
                require(experiment.digest(output/target) == experiment.digest(output/"input/control.jsonl.gz"),"control drift; stop before treatment")
            print(f"Captured {len(timings)}/24: {target}",flush=True)
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
              "full_results_sha256":experiment.digest(root/"results.json"),"exporter_sha256":experiment.digest(Path(__file__)),
              "timing":experiment.read_json(root/"timings.json")}
    target,folder = prefix.with_name(prefix.name+"-summary.json"),prefix.with_name(prefix.name+"-frames")
    images = {prefix.with_suffix(".png"):root/"contact-sheet.png"}
    images.update({folder/(f["id"]+".png"):root/f["png"] for f in result["frames"]})
    if not check:
        require(not target.exists() and not folder.exists() and not any(p.exists() for p in images),"export already exists")
        folder.mkdir(parents=True)
        experiment.write_json(target,result)
        for dest,source in images.items():
            shutil.copy2(source,dest)
    require(experiment.read_json(target) == result and all(experiment.digest(a) == experiment.digest(b) for a,b in images.items()),
            "portable evidence differs")
    print("Verified portable controlled-gap evidence and all eight native images",flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline",type=Path,default=experiment.ROOT/"artifacts/garden-renewal-capacity-guard-v1")
    parser.add_argument("--build",type=Path,default=experiment.ROOT/"artifacts/build-host-controlled-gap-docker")
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
