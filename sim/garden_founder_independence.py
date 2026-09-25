#!/usr/bin/env python3
"""Fixed founder-exit pairs, ancestry outcomes and native screenshots; no training."""
from __future__ import annotations

import argparse
from collections import Counter
import copy
from pathlib import Path
import shutil
import time
import zlib

import garden_renewal_stalls as stalls

mixed, pilot, fitness = stalls.mixed, stalls.pilot, stalls.fitness
experiment, require, gallery = stalls.experiment, stalls.require, stalls.gallery
DAY, STEP = stalls.DAY, stalls.STEP
START, MID, END, STOP = 64*DAY, 96*DAY, 128*DAY, 130*DAY
RULE = "garden-founder-independence-v1"
PROTOCOL = "benchmarks/garden-longevity/founder-independence-protocol.md"
MODELS = {"g0": "dc5e849d", "g2": "556a5dd2", "g3": "c7c1b31e", "narrow": "449c35fe"}
SEEDS = mixed.COVERAGE.review
PATCHES = mixed.PATCHES
ARMS = ("control", "exit")
FRAME_DAYS = (64, 80, 128)
FRAME_SEED, FRAME_SCHEDULE = "eb300b12", "fresh-2"


def case_id(model, schedule, seed):
    return f"{model}.{schedule}.{seed}"


def projection(trial, tick):
    return fitness.project(trial["lineages"], trial["seeds"], min(START, tick-STEP), tick, trial["start"], trial["stop"])


def validate(trial, model, schedule, seed, arm):
    require(arm in ARMS and ("founder_exit" in trial) == (arm == "exit"), "wrong intervention arm")
    legacy = {0, 480, 2880, START, END, STOP}
    checkpoints = trial["checkpoints"]
    expected = legacy | (set(range(DAY, STOP+1, DAY)) if arm == "exit" else set())
    require([c["tick"] for c in checkpoints] == sorted(expected), "wrong/duplicate checkpoint coverage")
    ordinary = {**trial, "checkpoints": [c for c in checkpoints if c["tick"] in legacy]}
    pilot.validate_trial(ordinary, seed, MODELS[model], START, END, patch=PATCHES[schedule])
    for c in checkpoints:
        counts = stalls.counts(trial, c["tick"])
        require(all(c[k] == counts[k] for k in ("living", "births", "deaths")) and
                c["seeds"] == counts["seed_bank"] and 0 <= c["nodes"] <= 512, "checkpoint/ledger disagreement")
    if arm == "exit":
        e = trial["founder_exit"]
        require(e["rule"] == "founder-exit-v1" and e["tick"] == START and
                len(e["killed"]) == len(set(e["killed"])) <= 8, "invalid exit record")
        require(e["after_hash"] == next(c["hash"] for c in checkpoints if c["tick"] == START), "exit/checkpoint hash mismatch")
        for p in trial["lineages"]:
            if p["id"] in e["killed"]:
                require(p["parent"] == 0 and p["death_tick"] == START and p["environmental_death"], "wrong exit victim")
            require(p["parent"] != 0 or p["death_tick"] is not None and p["death_tick"] <= START, "founder survived exit")


def pair_check(control, removed, original):
    event = removed["founder_exit"]
    victims = [p["id"] for p in control["lineages"] if not p["parent"] and stalls.alive(p, START)]
    require(event["killed"] == victims, "exit retargeted founders")
    c = next(c for c in control["checkpoints"] if c["tick"] == START)
    e = next(c for c in removed["checkpoints"] if c["tick"] == START)
    require(event["before_hash"] == c["hash"] and c["nodes"] == e["nodes"] and c["seeds"] == e["seeds"] and
            c["births"] == e["births"] and e["deaths"] == c["deaths"]+len(victims) and
            e["living"] == c["living"]-len(victims), "intervention boundary mismatch")
    before = copy.deepcopy(removed)
    for p in before["lineages"]:
        if p["id"] in victims:
            p.update(death_tick=None, environmental_death=False)
    require(projection(control, START) == projection(before, START), "prefix seed/lineage state differs")
    require(projection(control, STOP) == fitness.project(original["lineages"], original["seeds"],
            START, STOP, original["start"], original["stop"]), "control differs from saved full history")
    if not victims:
        require(control["lineages"] == removed["lineages"] and control["seeds"] == removed["seeds"] and
                control["key"] == removed["key"] and event["before_hash"] == event["after_hash"], "no-op pair diverged")


def state(trial, tick):
    records = trial["lineages"]
    living = [p for p in records if stalls.alive(p, tick)]
    pending = stalls.counts(trial, tick)["seed_bank"]
    return {"tick": tick, "living": len(living), "founders": sum(not p["parent"] for p in living),
            "established_descendants": [p["id"] for p in living if p["parent"] and stalls.confirmed(p, tick)],
            "pending_seeds": pending, "classification": "living" if living else "seed-only" if pending else "extinct"}


def seed_funnel(trial):
    records = {p["id"]: p for p in trial["lineages"]}
    groups = {name: Counter() for name in ("founder_carry_in", "descendant_carry_in", "new_founder", "new_descendant")}
    children = []
    for s in trial["seeds"]:
        carry = s["birth_tick"] <= START and (s["end_tick"] is None or s["end_tick"] > START)
        if not carry and not START < s["birth_tick"] <= END:
            continue
        founder = records[s["parent"]]["parent"] == 0
        name = ("founder_carry_in" if founder else "descendant_carry_in") if carry else ("new_founder" if founder else "new_descendant")
        group = groups[name]
        group["seeds"] += 1
        group[s["outcome"]] += 1
        require(s["outcome"] != "pending", "fixed seed cohort lacks complete follow-up")
        if s["child_id"] is None:
            continue
        p = records[s["child_id"]]
        due = p["birth_tick"]+DAY
        require(due <= STOP, "child exceeds fixed follow-up")
        confirmed = stalls.confirmed(p, due)
        kind = "confirmed" if confirmed else "exit_failure" if p["id"] in trial.get("founder_exit", {}).get("killed", []) else \
               "patch_failure" if p["environmental_death"] else "natural_failure"
        group[kind] += 1
        q = stalls.qualifies(p, records, due)
        group["qualifying"] += q
        children.append({"id": p["id"], "parent": p["parent"], "seed_tick": s["birth_tick"],
            "birth_tick": p["birth_tick"], "confirmation_tick": due, "cohort": name, "status": kind, "qualifying": q})
    further = []
    new_children = {c["id"] for c in children if c["cohort"] == "new_descendant" and c["status"] == "confirmed"}
    for c in children:
        if c["parent"] in new_children and c["status"] == "confirmed" and c["qualifying"]:
            further.append({"parent": c["parent"], "child": c["id"], "confirmation_tick": c["confirmation_tick"]})
    return {"groups": {k: dict(v) for k,v in groups.items()}, "children": children, "further_generation_links": further}


def outcomes(trial):
    records = {p["id"]: p for p in trial["lineages"]}
    qualified = [p for p in records.values() if p["parent"] and START < p["birth_tick"]+DAY <= END and
                 stalls.qualifies(p, records, p["birth_tick"]+DAY)]
    bands = []
    for lo, hi in ((START, MID), (MID, END)):
        score = stalls.sustained.score_block(trial["lineages"], trial["seeds"], lo, hi, START, STOP)[0]
        bands.append({"start": lo, "end": hi, "confirmations": [p["id"] for p in qualified if lo < p["birth_tick"]+DAY <= hi],
                      "bounded_renewal_ticks": score["rolling"]["ticks"]})
    killed = set(trial.get("founder_exit", {}).get("killed", []))
    deaths = Counter()
    for p in records.values():
        if p["death_tick"] is not None and START <= p["death_tick"] <= END:
            deaths["founder_exit" if p["id"] in killed else "scheduled_patch" if p["environmental_death"] else "natural"] += 1
    funnel = seed_funnel(trial)
    first = min((c["confirmation_tick"] for c in funnel["children"] if c["cohort"] == "new_descendant" and c["qualifying"]), default=None)
    return {"states": [state(trial,t) for t in (START, MID, END, STOP)], "seed_funnel": funnel,
            "bands": bands, "first_new_descendant_confirmation": first, "deaths": dict(deaths)}


def summarize(cases):
    expected = {(m,a,s) for m in MODELS for a in PATCHES for s in SEEDS}
    require(len(cases) == len(expected) and {(c["model"],c["schedule"],c["seed"]) for c in cases} == expected, "incomplete/duplicate panel")
    groups = {}
    for model in MODELS:
        groups[model] = {}
        for schedule in ("all", *PATCHES):
            selected = [c for c in cases if c["model"] == model and (schedule == "all" or c["schedule"] == schedule)]
            group = {"pairs": len(selected), "removed_founders": sum(len(c["exit_event"]["killed"]) for c in selected), "arms": {}}
            for arm in ARMS:
                total = Counter(worlds=len(selected))
                for c in selected:
                    o = c[arm]
                    f = o["seed_funnel"]
                    desc = f["groups"]["new_descendant"]
                    total.update({"living_at_128": o["states"][2]["living"],
                        "extinct_worlds_at_130": o["states"][-1]["classification"] == "extinct",
                        "seed_only_worlds_at_130": o["states"][-1]["classification"] == "seed-only",
                        "established_worlds_at_130": bool(o["states"][-1]["established_descendants"]),
                        "new_descendant_seeds": desc.get("seeds",0), "new_descendant_confirmed": desc.get("confirmed",0),
                        "new_descendant_qualifying": desc.get("qualifying",0), "recruiting_worlds": desc.get("qualifying",0)>0,
                        "further_generation_links": len(f["further_generation_links"]),
                        "further_generation_worlds": bool(f["further_generation_links"]),
                        "first_period_renewal_ticks": o["bands"][0]["bounded_renewal_ticks"],
                        "second_period_renewal_ticks": o["bands"][1]["bounded_renewal_ticks"]})
                group["arms"][arm] = dict(total)
            groups[model][schedule] = group
    return groups


def frame_check(root, frame, trial):
    stem = frame["id"]
    value = experiment.read_json(root / "frames" / f"{stem}.json")
    raw = (root/frame["framebuffer"]).read_bytes()
    require(value == experiment.read_json(root / "frames" / f"{stem}.repeat.json") and
            raw == (root / "frames" / f"{stem}.repeat.rgb565").read_bytes(), "frame replay not deterministic")
    counts = stalls.counts(trial, frame["day"]*DAY)
    required = {"model_crc32": MODELS[frame["model"]], "seed": FRAME_SEED,
        "scenario": "rainfed-crowded", "policy": "neural-no-night-growth", "tick": frame["day"]*DAY,
        "node_capacity": 512, "leaf_environment": "leaf-maintenance-v1", "leaf_policy": "selective",
        "seed_dispersal": "wide-v1", "water_uptake": "headroom-v1", "disturbance_seed": PATCHES[FRAME_SCHEDULE],
        "living": counts["living"], "births": counts["births"], "deaths": counts["deaths"], "seed_bank": counts["seed_bank"]}
    require(all(value.get(k)==v for k,v in required.items()) and not any(k in value for k in ("root_bootstrap_rule","gap_protocol","drainage_rule","seed_reserve_rule")), "frame identity differs")
    require(value.get("founder_exit") == trial.get("founder_exit"), "frame exit event differs")
    checkpoints = [c for c in trial["checkpoints"] if c["tick"] == value["tick"]]
    if checkpoints:
        require(value["hash"] == checkpoints[0]["hash"] and value["nodes"] == checkpoints[0]["nodes"], "frame checkpoint differs")
    require(len(raw)==gallery.FRAME_BYTES and value["framebuffer_crc32"]==f"{zlib.crc32(raw):08x}", "frame CRC/size differs")
    return {**frame,"hash":value["hash"],"framebuffer_crc32":value["framebuffer_crc32"],"ledger_hash_matched":bool(checkpoints)}


def analyze(root):
    cases = []
    for model in MODELS:
        for schedule in PATCHES:
            for seed in SEEDS:
                name = case_id(model,schedule,seed)
                arms = {arm: experiment.read_json(root/"trials"/f"{name}.{arm}.json") for arm in ARMS}
                for arm in ARMS:
                    validate(arms[arm],model,schedule,seed,arm)
                require(arms["control"] == experiment.read_json(root/"trials"/f"{name}.frozen.json"), "ordinary trial changed from frozen binary")
                pair_check(arms["control"],arms["exit"],experiment.read_json(root/"input"/f"{name}.json"))
                cases.append({"id":name,"model":model,"seed":seed,"schedule":schedule,"exit_event":arms["exit"]["founder_exit"],
                              **{arm:outcomes(arms[arm]) for arm in ARMS}})
    frames, groups = [], []
    for model in MODELS:
        for arm in ARMS:
            row = []
            trial = experiment.read_json(root/"trials"/f"{case_id(model,FRAME_SCHEDULE,FRAME_SEED)}.{arm}.json")
            for day in FRAME_DAYS:
                stem=f"{model}.{arm}.{day}"
                frame = frame_check(root,{"id":stem,"model":model,"arm":arm,"day":day,"framebuffer":f"frames/{stem}.rgb565","png":f"frames/{stem}.png"},trial)
                frames.append(frame); row.append(frame)
            groups.append(row)
    return {"rule":RULE,"native_processes":144,"training_runs":0,"cases":cases,"summary":summarize(cases),"frames":frames,"frame_groups":groups}


def verify(root):
    manifest=experiment.read_json(root/"manifest.json")
    require(manifest["status"]=="complete" and manifest["rule"]==RULE,"wrong/incomplete bundle")
    for name in manifest["artifacts"]:
        gallery.artifact(root,manifest,name)
    require(experiment.digest(root/"input/coverage-manifest.json")==stalls.BASELINE_SHA,"changed coverage manifest")
    prior=experiment.read_json(root/"input/coverage-manifest.json")
    for dest,src in manifest["copied"].items():
        require(experiment.digest(root/dest)==prior["artifacts"][src],"changed baseline copy")
    result=analyze(root)
    require(result==experiment.read_json(root/"results.json"),"founder challenge reanalysis differs")
    print("Verified 32 matched founder-exit pairs, frozen controls and 24 repeated frames",flush=True)
    return result


def collect(baseline,build,output):
    require(not output.exists() and output.is_relative_to(experiment.ROOT/"artifacts") and not output.is_relative_to(baseline),"choose fresh separate artifact output")
    require(experiment.digest(baseline/"manifest.json")==stalls.BASELINE_SHA,"wrong coverage input")
    mixed.verify(baseline)
    prior=experiment.read_json(baseline/"manifest.json")
    sources=experiment.source_files()
    require(all(sources.get(n)==sha for n,sha in prior["sources"].items() if n.startswith("src/") and n.endswith((".c",".h"))),"simulation core changed")
    output.mkdir(parents=True)
    for folder in ("input","bin","trials","frames"):
        (output/folder).mkdir()
    experiment.snapshot_sources(output,sources)
    copied={"bin/frozen-trial":"bin/garden-persistence-trial"}
    for model in MODELS:
        copied[f"input/{model}.tgm"]=f"review/{model}.tgm"
        for schedule in PATCHES:
            for seed in SEEDS:
                name=case_id(model,schedule,seed)
                copied[f"input/{name}.json"]=f"review/{name}.json"
    for dest,src in copied.items():
        shutil.copy2(baseline/src,output/dest)
        require(experiment.digest(output/dest)==prior["artifacts"][src],"input copy differs")
    shutil.copy2(baseline/"manifest.json",output/"input/coverage-manifest.json")
    for name in ("garden-persistence-trial","garden-replay"):
        shutil.copy2(build/f"toy-factory-{name}",output/"bin"/name)
    shutil.copy2(build/"CMakeCache.txt",output/"input/CMakeCache.txt")
    shutil.copy2(experiment.ROOT/PROTOCOL,output/"protocol.md")
    frozen={str(p.relative_to(output)):experiment.digest(p) for folder in ("input","bin") for p in (output/folder).iterdir()}
    experiment.write_json(output/"started.json",{"rule":RULE,"sources":sources,"copied":copied,"frozen":frozen})
    begin,timings=time.monotonic(),[]
    def run(cmd,target):
        _,elapsed=pilot.run_json(cmd,target)
        timings.append({"artifact":str(target.relative_to(output)),"command":[str(a) for a in cmd],"seconds":elapsed})
    try:
        for model in MODELS:
            require(pilot.model_crc(output/f"input/{model}.tgm")==MODELS[model],"model CRC differs")
            for schedule in PATCHES:
                for seed in SEEDS:
                    name=case_id(model,schedule,seed)
                    args=[output/f"input/{model}.tgm","neural","0x"+seed,"0x"+PATCHES[schedule],START,END]
                    run([output/"bin/frozen-trial",*args],output/"trials"/f"{name}.frozen.json")
                    for arm in ARMS:
                        run([output/"bin/garden-persistence-trial",*args,*(["--founder-exit",START] if arm=="exit" else [])],output/"trials"/f"{name}.{arm}.json")
                    ctrl=experiment.read_json(output/"trials"/f"{name}.control.json")
                    ex=experiment.read_json(output/"trials"/f"{name}.exit.json")
                    for arm,v in (("control",ctrl),("exit",ex)):
                        validate(v,model,schedule,seed,arm)
                    require(ctrl==experiment.read_json(output/"trials"/f"{name}.frozen.json"),"changed ordinary trial")
                    pair_check(ctrl,ex,experiment.read_json(output/"input"/f"{name}.json"))
                    print("Checked",name,"removed",ex["founder_exit"]["killed"],flush=True)
        for model in MODELS:
            for arm in ARMS:
                for day in FRAME_DAYS:
                    stem=f"{model}.{arm}.{day}"
                    for suffix in ("",".repeat"):
                        raw=output/"frames"/f"{stem}{suffix}.rgb565"
                        cmd=[output/"bin/garden-replay",output/f"input/{model}.tgm","rainfed-crowded","neural-no-night-growth",
                             "0x"+FRAME_SEED,"--leaf-policy","selective","--disturbance-seed","0x"+PATCHES[FRAME_SCHEDULE],
                             "--ticks",day*DAY,"--framebuffer",raw,*(["--founder-exit",START] if arm=="exit" else [])]
                        run(cmd,output/"frames"/f"{stem}{suffix}.json")
                    gallery.write_png(output/"frames"/f"{stem}.png",240,240,gallery.rgb565be_to_rgb888((output/"frames"/f"{stem}.rgb565").read_bytes()))
        result=analyze(output)
        require(result==analyze(output) and len(timings)==144,"repeat/process budget differs")
        gallery.contact_sheet(output,result["frame_groups"])
        require(experiment.source_files()==sources and all(experiment.digest(output/n)==sha for n,sha in frozen.items()),"source/input changed during collection")
        experiment.write_json(output/"results.json",result)
        experiment.write_json(output/"timings.json",{"seconds":time.monotonic()-begin,"calls":timings})
        artifacts={str(p.relative_to(output)):experiment.digest(p) for p in output.rglob("*") if p.is_file()}
        experiment.write_json(output/"manifest.json",{"rule":RULE,"status":"complete","sources":sources,"copied":copied,"artifacts":artifacts,
            "artifact_bytes":sum((output/n).stat().st_size for n in artifacts)})
    except BaseException as error:
        experiment.write_json(output/"failure.json",{"error":str(error)})
        raise
    verify(output)


def portable(root, result):
    return {**result, "manifest_sha256": experiment.digest(root/"manifest.json"),
            "timings": experiment.read_json(root/"timings.json")}


def export(root, prefix, check=False):
    result = verify(root)
    require(not prefix.is_relative_to(root), "do not export inside frozen evidence")
    data, overview, markdown, frames = [prefix.with_name(prefix.name+suffix)
        for suffix in ("-summary.json", ".png", "-gallery.md", "-frames")]
    expected = portable(root, result)
    lines = ["# Founder-independence challenge: fixed native frames", "",
        "Fixed visual panel: fresh-2 / eb300b12. Columns: **days 64, 80, 128**.",
        "Rows: original control/exit, broad G2 control/exit, broad final control/exit, narrow control/exit.",
        "Day 64 is immediately after founder death in exit arms; corpses have not yet decomposed.",
        "", f"![Matched native views]({overview.name})", "",
        "| Frame | World hash | Framebuffer CRC32 | Same-tick ledger hash |",
        "|---|---|---|---|"]
    for f in result["frames"]:
        lines.append(f"| [{f['model']} / {f['arm']} / day {f['day']}]({frames.name}/{f['id']}.png) | "
            f"`{f['hash']}` | `{f['framebuffer_crc32']}` | {'yes' if f['ledger_hash_matched'] else 'counts + independent repeat'} |")
    lines += ["", "All 24 images reproduced byte-for-byte after independent resets. Twenty also match",
        "same-tick ledger hashes. Four day-80 control images use ledger population/seed counts",
        "plus independent replay hashes because the unchanged control tool has no day-80 checkpoint.",
        "No images were selected by outcome. Images alone do not establish reproductive health.",
        "See the [report](founder-independence.md) and [fixed protocol](founder-independence-protocol.md).",
        "", f"Manifest SHA-256: `{expected['manifest_sha256']}`.", ""]
    content = "\n".join(lines)
    if not check:
        require(all(not p.exists() for p in (data,overview,markdown,frames)), "export already exists")
        frames.mkdir(parents=True)
        experiment.write_json(data, expected)
        shutil.copyfile(root/"contact-sheet.png",overview)
        with markdown.open("x") as stream:
            stream.write(content)
        for f in result["frames"]:
            shutil.copyfile(root/f["png"],frames/f"{f['id']}.png")
    require(experiment.read_json(data)==expected and markdown.read_text()==content, "portable metadata differs")
    require(experiment.digest(overview)==experiment.digest(root/"contact-sheet.png"), "portable overview differs")
    for f in result["frames"]:
        require(experiment.digest(frames/f"{f['id']}.png")==experiment.digest(root/f["png"]), "portable PNG differs")
    print("Portable founder summary, gallery and 24 PNGs match verified evidence", flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline",type=Path,default=experiment.ROOT/"artifacts/garden-training-coverage-v1")
    parser.add_argument("--build",type=Path,default=experiment.ROOT/"artifacts/founder-independence-build")
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--verify",action="store_true")
    parser.add_argument("--export",type=Path)
    parser.add_argument("--check-export",type=Path)
    args=parser.parse_args()
    require(not (args.export and args.check_export) and
            (args.verify or not (args.export or args.check_export)), "export/check-export requires verify")
    if args.export or args.check_export:
        export(args.output.resolve(),(args.export or args.check_export).resolve(),bool(args.check_export))
    elif args.verify:
        verify(args.output.resolve())
    else:
        collect(args.baseline.resolve(),args.build.resolve(),args.output.resolve())


if __name__=="__main__":
    main()
