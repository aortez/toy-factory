#!/usr/bin/env python3
"""Fixed eight-versus-sixteen admission experiment on the saved fractional canopy."""
from __future__ import annotations

import argparse
from collections import Counter
from itertools import zip_longest
from pathlib import Path
import shutil
import tempfile
import time

import garden_renewal_canopy_transmission as parent
from garden_plant_slots import plant_capacity

prior = parent.prior

gap, experiment, require, native = prior.gap, prior.experiment, prior.require, prior.native
order = prior.prior
RULE, NATIVE = "garden-renewal-plant-slots-v1", "post-noon-sixteen-plant-slots-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-plant-slots-protocol.md"
BASELINE_SHA = "ea243a36dccd49eda1db5cbfc30956ebf281e81013fec5a4adc8e69bc7212b69"
PORTABLE = "benchmarks/garden-longevity/renewal-canopy-transmission-summary.json"
PORTABLE_SHA = "ad7c804d94fb9ac687a7d0c5175982579ba2b118336f425b1316fb3a857ccc60"
AUDIT = "benchmarks/garden-longevity/renewal-allocation-blockers-summary.json"
AUDIT_SHA = "e7c591c0b094c94e788ae9ca91992bbd6f1214123353dd0f38d64c5e7ca7ef37"
AFTER, STOP, LATE, DAY = prior.AFTER, prior.STOP, prior.LATE, prior.DAY
ARMS, FRAMES = ("control", "sixteen"), prior.FRAMES


def settings():
    return {"rule": RULE, "native_rule": NATIVE, "arms": list(ARMS), "after_inclusive": AFTER,
            "first_ecology_tick": AFTER+15, "stop": STOP, "late": LATE, "frames": list(FRAMES),
            "limits": {"before": 8, "control_after": 8, "sixteen_after": 16, "nodes": 512, "seeds": 8},
            "models": parent.settings()["models"], "routing": parent.settings()["routing"],
            "parent_manifest_sha256": BASELINE_SHA, "parent_portable_sha256": PORTABLE_SHA,
            "allocation_audit_sha256": AUDIT_SHA, "budget": {"native_calls": 20, "training_calls": 0},
            "role": "selected-world admission diagnostic, not qualified sustained renewal"}

def commands():
    baseline = [(p, c) for p, c in parent.commands() if "/transmission." in p]
    calls = []
    for arm in ARMS:
        for path, command in baseline:
            target = path.replace("/transmission.", "/"+arm+".")
            cmd = [s.replace("frames/transmission.", "frames/"+arm+".") for s in command]
            if arm == "sixteen":
                cmd += ["--plant-slots", "16"]
            calls.append((target, cmd))
    return calls

def check_rule(row, arm):
    require(arm in ARMS, "invalid admission arm")
    parent.check_rule(row, "transmission")
    if arm == "control":
        require("plant_admission" not in row, "control unexpectedly changes admission")
    else:
        require("plant_admission" in row, "missing admission metadata")
    return plant_capacity(row)

def check_prefix(control, candidate):
    for count, (a, b) in enumerate(zip_longest(control, candidate), 1):
        require(a is not None and b is not None, "truncated admission prefix")
        if a["type"] in ("world", "seed-sites"):
            check_rule(a, "control")
            check_rule(b, "sixteen")
        require(a == {k: v for k, v in b.items() if k != "plant_admission"}, "physical prefix changed")
        if a["type"] in ("world", "seed-sites") and a["tick"] == AFTER:
            return count
    raise RuntimeError("prefix did not reach admission boundary")

def pressure(worlds, sites):
    windows = {}
    for name, start in (("after", AFTER), ("late", LATE)):
        rows = [r for r in sites if start < r["tick"] <= STOP]
        counters, populations, masks = Counter(), Counter(), Counter()
        for row in rows:
            slots, count = plant_capacity(row), len(row["plants"])
            require(count <= slots and row["nodes"] <= 512 and len(row["seeds"]) <= 8, "capacity exceeded")
            counters.update(checkpoints=1, full_actual_limit=count == slots, at_least_eight=count >= 8,
                            more_than_eight=count > 8, node_seedling_gate=row["nodes"]+4 > 512,
                            node_full=row["nodes"] == 512, dead_present=any(p["dead"] for p in row["plants"]))
            populations[str(count)] += 1
            for seed in row["seeds"]:
                if seed["age"] >= 8:
                    masks[str(seed["blockers"])] += 1
        windows[name] = {"counts": counters, "plant_slot_histogram": populations, "mature_seed_masks": masks,
                         "peak_slots": max(len(r["plants"]) for r in rows),
                         "peak_nodes": max(r["nodes"] for r in rows)}
    return windows


def analyze_case(root, arm, create=False):
    result, frames, worlds = parent.analyze_case(root, arm, create, rule_check=check_rule)
    sites, _, _ = order.parent.parent.parent.split_census(
        gap.read_trace(root/f"traces/{arm}.sites.jsonl.gz"), "optional", "seed-sites")
    require(all(w.get("plant_admission") == s.get("plant_admission") for w, s in zip(worlds, sites, strict=True)),
            "world/site admission differs")
    by_tick = {w["tick"]: w for w in worlds}
    require(all(f["result"].get("plant_admission") == by_tick[f["tick"]].get("plant_admission") for f in frames),
            "frame admission differs")
    result["admission_pressure"] = pressure(worlds, sites)
    return result, frames, worlds

def historical_files():
    return [*(f"traces/control.{k}.jsonl.gz" for k in ("world", "sites")),
            *(f"frames/control.{t}.{ext}" for t in FRAMES for ext in ("json", "rgb565"))]


def check_historical(root):
    for name in historical_files():
        require(experiment.digest(root/name) == experiment.digest(root/"input/history"/name), "historical control drift: "+name)
        repeated = name.replace(".jsonl.gz", ".repeat.jsonl.gz") if name.endswith(".gz") else (
            name.rsplit(".", 1)[0]+".repeat."+name.rsplit(".", 1)[1])
        require(experiment.digest(root/repeated) == experiment.digest(root/name), "historical repeat drift")


def decision(cases):
    metrics = {}
    for arm, case in cases.items():
        final = case["outcomes"]["final"]
        incumbents = [p for p in case["resources"].values() if p["incumbent"]]
        metrics[arm] = {"new_full_day_survivors": case["new_cohort"]["cycle_survivors"],
            "new_full_day_parents_with_full_day_child": case["new_cohort"]["cycle_survivors_with_surviving_child"],
            "incumbent_deaths": sum(p["lineage"]["death_tick"] is not None for p in incumbents),
            "endpoint_species": len(final["species"]), "endpoint_families": len(final["families"])}
    a, b = metrics["control"], metrics["sixteen"]
    require(a == {"new_full_day_survivors": 2, "new_full_day_parents_with_full_day_child": 0,
                  "incumbent_deaths": 1, "endpoint_species": 2, "endpoint_families": 3},
            "changed historical outcome anchors")
    gates = {"more_new_full_day_survivors": b["new_full_day_survivors"] > 2,
             "new_durable_parent": b["new_full_day_parents_with_full_day_child"] > 0,
             "no_extra_incumbent_deaths": b["incumbent_deaths"] <= 1,
             "species_not_reduced": b["endpoint_species"] >= a["endpoint_species"],
             "families_not_reduced": b["endpoint_families"] >= a["endpoint_families"]}
    return {"metrics": metrics, "gates": gates, "positive_selected_world_signal": all(gates.values()),
            "broader_environment_qualified": False}

def analyze(root, create=False):
    check_historical(root)
    prefixes = {kind: check_prefix(*(gap.read_trace(root/f"traces/{a}.{kind}.jsonl.gz") for a in ARMS))
                for kind in ("world", "sites")}
    cases, frames, worlds = {}, [], {}
    for arm in ARMS:
        cases[arm], images, worlds[arm] = analyze_case(root, arm, create)
        frames.extend(images)
    old = experiment.read_json(root/"input/parent-results.json")["cases"]["transmission"]
    require(all(cases["control"][k] == v for k, v in old.items()), "historical derived outcomes changed")
    require((root/f"frames/control.{AFTER}.rgb565").read_bytes() ==
            (root/f"frames/sixteen.{AFTER}.rgb565").read_bytes(), "boundary pixels differ")
    divergence = next(({"tick": a["tick"], "control": a, "sixteen": b}
                       for a, b in zip(worlds["control"], worlds["sixteen"], strict=True)
                       if a["hash"] != b["hash"]), None)
    require(divergence is None or divergence["tick"] >= AFTER+15, "premature physical divergence")
    return {"settings": settings(), "prefixes": prefixes, "first_hash_divergence": divergence,
            "cases": cases, "frames": frames, "decision": decision(cases)}

def copies():
    return {"input/parent-results.json": "results.json", "input/prior-cache.txt": "input/CMakeCache.txt",
            "input/native-source.tar.gz": "source.tar.gz",
            **{f"models/{n}.tgm": f"models/{n}.tgm" for n in settings()["models"]},
            **{f"input/history/{n}": n.replace("control.", "transmission.") for n in historical_files()}}


def check_inputs(root):
    require(experiment.digest(root/"input/parent-manifest.json") == BASELINE_SHA and
            experiment.digest(root/"input/parent-summary.json") == PORTABLE_SHA and
            experiment.digest(root/"input/allocation-audit.json") == AUDIT_SHA, "changed parent evidence")
    manifest = experiment.read_json(root/"input/parent-manifest.json")
    for dest, source in copies().items():
        require(experiment.digest(root/dest) == manifest["artifacts"][source], "changed parent copy")
    started = experiment.read_json(root/"started.json")
    require(started["settings"] == settings() and experiment.digest(root/"input/protocol.md") == started["sources"][PROTOCOL],
            "changed protocol/settings")
    for name, sha in started["frozen"].items():
        require(experiment.digest(root/name) == sha, "frozen input changed")
    old, new = [native.native_hashes(root/p) for p in ("input/native-source.tar.gz", "source.tar.gz")]
    added = {"src/garden_plant_slots.h", "sim/garden_plant_slots.c", "sim/garden_plant_slots_test.c"}
    changed = {"src/garden_world.c", "src/garden_world.h", "src/garden_dark_guard.h", "src/garden_night_capacity.h",
               "sim/garden_inspect.c", "sim/garden_replay.c", "sim/garden_seed_audit_test.c",
               "sim/garden_wet_germination_test.c", "sim/garden_seed_sites_test.c"}

    require(new.keys()-old.keys() == added and not old.keys()-new.keys() and
            {n for n in old if old[n] != new[n]} <= changed, "unrelated native changes")
    require(all(started["sources"].get(n) == sha for n, sha in new.items()), "native archive mismatch")
    a, b = [native.cache_settings(root/p) for p in ("input/prior-cache.txt", "input/CMakeCache.txt")]
    require(b.pop("TOY_FACTORY_GARDEN_PLANT_SLOTS:BOOL", None) == "ON" and a == b, "wrong build configuration")


def check_capture(root):
    check_inputs(root)
    capture = experiment.read_json(root/"capture.json")
    require(capture["settings"] == settings() and
            [(c["artifact"], c["command"]) for c in capture["calls"]] == commands(), "wrong capture inventory")
    for name in capture["artifacts"]:
        gap.gallery.artifact(root, capture, name)
    return capture


def analysis_sources():
    paths = sorted((experiment.ROOT/"sim").glob("*.py"))+[experiment.ROOT/PROTOCOL, experiment.ROOT/"sim/CMakeLists.txt"]
    return {str(p.relative_to(experiment.ROOT)): experiment.digest(p) for p in paths}


def finish(root):
    """Analysis-only recovery never reruns or replaces a captured observation."""
    require(not (root/"manifest.json").exists(), "bundle already sealed")
    capture = check_capture(root)
    sources, start = analysis_sources(), time.monotonic()
    result = analyze(root, True)
    require(result == analyze(root), "repeated analysis differs")
    for frame in result["frames"]:
        gap.gallery.write_png(root/frame["png"], 240, 240,
            gap.gallery.rgb565be_to_rgb888((root/frame["framebuffer"]).read_bytes()))
    gap.gallery.contact_sheet(root, [[f for f in result["frames"] if f["arm"] == arm] for arm in ARMS])
    check_capture(root)
    require(analysis_sources() == sources, "analysis changed during finish")
    experiment.write_json(root/"analysis-sources.json", sources)
    experiment.write_json(root/"results.json", result)
    experiment.write_json(root/"timings.json", {"calls": capture["calls"], "analysis_and_repeat_seconds": time.monotonic()-start})
    artifacts = {str(p.relative_to(root)): experiment.digest(p) for p in root.rglob("*") if p.is_file()}
    experiment.write_json(root/"manifest.json", {"rule": RULE, "status": "complete", "native_calls": len(capture["calls"]),
        "artifacts": artifacts, "artifact_bytes": sum((root/n).stat().st_size for n in artifacts)})


def collect(baseline, build, output):
    require(not output.exists() and output.is_relative_to(experiment.ROOT/"artifacts") and
            not any(output.is_relative_to(p) for p in (baseline, build)), "choose fresh independent output")
    gap.parent.shadow.check_frozen(baseline, BASELINE_SHA)
    require(experiment.digest(experiment.ROOT/PORTABLE) == PORTABLE_SHA and
            experiment.digest(experiment.ROOT/AUDIT) == AUDIT_SHA, "changed portable input")
    sources = experiment.source_files()
    output.mkdir(parents=True)
    experiment.snapshot_sources(output, sources)
    for name in ("input", "models", "bin", "traces", "frames"):
        (output/name).mkdir()
    for dest, source in copies().items():
        (output/dest).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(baseline/source, output/dest)
    for source, dest in ((baseline/"manifest.json", "input/parent-manifest.json"),
            (experiment.ROOT/PORTABLE, "input/parent-summary.json"), (experiment.ROOT/PROTOCOL, "input/protocol.md"),
            (experiment.ROOT/AUDIT, "input/allocation-audit.json")):
        shutil.copy2(source, output/dest)
    for name in ("CMakeCache.txt", "build.ninja"):
        shutil.copy2(build/name, output/"input"/name)
    for name in ("inspect", "replay"):
        shutil.copy2(build/("toy-factory-garden-"+name), output/"bin"/name)
    frozen = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
    experiment.write_json(output/"started.json", {"settings": settings(), "sources": sources, "frozen": frozen})
    calls, begin, target, command = [], time.monotonic(), None, None
    try:
        check_inputs(output)
        for target, command in commands():
            start = time.monotonic()
            if target.endswith(".gz"):
                with tempfile.TemporaryDirectory(prefix="garden-plant-slots-") as temporary:
                    raw = Path(temporary)/"trace.jsonl"
                    try:
                        experiment.command_run(command, raw, output, 180)
                    finally:
                        if raw.exists():
                            experiment.compress(raw, output/target)
            else:
                experiment.command_run(command, output/target, output, 180)
            calls.append({"artifact": target, "command": command, "seconds": time.monotonic()-start})
            if target == f"frames/control.{STOP}.repeat.json":
                check_historical(output)
                print("Historical fractional-canopy control traces and frames match exactly", flush=True)
            print(f"Captured {len(calls)}/20: {target}", flush=True)
        require(experiment.source_files() == sources, "sources changed during capture")
        artifacts = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
        experiment.write_json(output/"capture.json", {"settings": settings(), "calls": calls,
            "artifacts": artifacts, "capture_seconds": time.monotonic()-begin})
    except BaseException as error:
        experiment.write_json(output/"capture-failure.json",
            {"error": str(error), "completed_calls": calls, "active_artifact": target, "active_command": command})
        raise
    finish(output)


def verify(root):
    manifest = experiment.read_json(root/"manifest.json")
    require(manifest["rule"] == RULE and manifest["status"] == "complete" and manifest["native_calls"] == 20, "incomplete bundle")
    gap.parent.shadow.check_frozen(root, experiment.digest(root/"manifest.json"))
    capture = check_capture(root)
    require(experiment.read_json(root/"timings.json")["calls"] == capture["calls"] and
            experiment.read_json(root/"analysis-sources.json") == analysis_sources(), "analysis provenance changed")
    require(all(experiment.digest(experiment.ROOT/n) == sha for n, sha in native.native_hashes(root/"source.tar.gz").items()),
            "native source changed")
    result = analyze(root)
    require(result == experiment.read_json(root/"results.json"), "saved analysis differs")
    return result


def export(root, prefix, check=False):
    require(not prefix.is_relative_to(root), "export outside frozen evidence")
    result = {**verify(root), "manifest_sha256": experiment.digest(root/"manifest.json"),
              "full_results_sha256": experiment.digest(root/"results.json"), "timing": experiment.read_json(root/"timings.json")}
    target, folder = prefix.with_name(prefix.name+"-summary.json"), prefix.with_name(prefix.name+"-frames")
    images = {prefix.with_suffix(".png"): root/"contact-sheet.png"}
    images.update({folder/(f["id"]+".png"): root/f["png"] for f in result["frames"]})
    if not check:
        require(not target.exists() and not folder.exists() and not any(p.exists() for p in images), "export exists")
        folder.mkdir(parents=True)
        experiment.write_json(target, result)
        for dest, source in images.items():
            shutil.copy2(source, dest)
    require(experiment.read_json(target) == result and all(experiment.digest(p) == experiment.digest(q) for p, q in images.items()),
            "portable evidence differs")
    print("Verified portable plant-admission comparison and six native frames", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT/"artifacts/garden-renewal-canopy-transmission-v1")
    parser.add_argument("--build", type=Path, default=experiment.ROOT/"artifacts/build-host-plant-slots-docker")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--finish", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--export", type=Path)
    parser.add_argument("--check-export", type=Path)
    args = parser.parse_args()
    require(not (args.export and args.check_export) and not (args.finish and args.verify) and
            (args.verify or not (args.export or args.check_export)), "incompatible modes")
    if args.export or args.check_export:
        export(args.output.resolve(), (args.export or args.check_export).resolve(), bool(args.check_export))
    elif args.verify:
        verify(args.output.resolve())
    elif args.finish:
        finish(args.output.resolve())
    else:
        collect(args.baseline.resolve(), args.build.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
