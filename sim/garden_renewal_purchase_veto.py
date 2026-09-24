#!/usr/bin/env python3
"""Two predeclared one-shot purchases, independent from the unchanged dark guard."""
from __future__ import annotations

import argparse
import copy
from itertools import zip_longest
import json
from pathlib import Path
import shutil
import tempfile
import time

import garden_renewal_dark_failures as failures

panel, guard = failures.panel, failures.guard
experiment, startup, gallery, require = panel.experiment, panel.startup, panel.gallery, panel.require
RULE, VETO = "garden-renewal-purchase-veto-v1", "isolated-purchase-veto-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-purchase-veto-protocol.md"
BASELINE_SHA = failures.BASELINE_SHA
CASE = panel.Case("abf7af73", "patch", "guard")
ARMS, FRAMES = ("control", "extension", "finish"), (72960, 122880, panel.STOP)
TARGETS = {
    "extension": {"tick": 66060, "id": 21, "action": 1, "node": 323, "energy": 151,
                  "water": 510, "nodes_before": 32, "nodes_after": 33},
    "finish": {"tick": 69885, "id": 22, "action": 2, "node": 271, "energy": 92,
               "water": 152, "nodes_before": 21, "nodes_after": 21},
}


def settings():
    return {"rule": RULE, "veto_rule": VETO, "baseline_manifest_sha256": BASELINE_SHA,
            "world_seed": CASE.seed, "patch_seed": CASE.patch, "targets": TARGETS,
            "arms": list(ARMS), "stop": panel.STOP, "late_start": panel.LATE,
            "models": guard.settings()["models"], "routing": guard.settings()["routing"],
            "guard_rule": guard.GUARD, "frame_ticks": list(FRAMES),
            "budget": {"traces": 6, "frame_replays": 18, "native_calls": 24, "training_calls": 0},
            "role": "selected adverse world; isolated purchases, not policy qualification"}


def commands():
    calls = []
    for arm in ARMS:
        base = ["models/r2-n.tgm", "rainfed-crowded", experiment.NIGHT_POLICY, "0x"+CASE.seed,
                "--leaf-policy", "selective", "--focal-model", "models/r2-w.tgm", "--focal-founder", "5",
                "--disturbance-seed", "0x"+CASE.patch]
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


def without_veto(row):
    return {k: v for k, v in row.items() if k != "purchase_veto"}


def check_metadata(row, arm):
    if arm == "control":
        require("purchase_veto" not in row, "disabled hook emitted metadata")
        return
    t = TARGETS[arm]
    expected = {"rule": VETO, "arm": arm, "tick": t["tick"], "id": t["id"],
                "hits": int(row["tick"] >= t["tick"])}
    require(row.get("purchase_veto") == expected, "wrong/missing purchase receipt counter")


def check_prefix(control, treated, arm):
    t = TARGETS[arm]
    for count, (a, b) in enumerate(zip_longest(control, treated)):
        require(a is not None and b is not None, "truncated purchase prefix")
        if b["type"] == "world":
            check_metadata(b, arm)
        clean = without_veto(b)
        if a == clean:
            require(a["tick"] <= t["tick"], "missing purchase divergence")
            continue
        require(a["type"] == b["type"] == "world" and a["tick"] == b["tick"] == t["tick"],
                "purchase diverged before/after selected transaction")
        left, right = [{p["id"]: p for p in r["plants"]} for r in (a, b)]
        require(left.keys() == right.keys() and all(left[i] == right[i] for i in left if i != t["id"]),
                "another plant changed at isolated purchase")
        a_plant, b_plant = left[t["id"]], right[t["id"]]
        require(a["dark_guard"] == b["dark_guard"], "ordinary guard changed at purchase")
        receipt = [e for e in b["dark_guard"]["events"] if e["id"] == t["id"] and e["kind"] == "growth"]
        require(len(receipt) == 1 and all(receipt[0][k] == v for k, v in t.items() if k not in ("tick", "action"))
                and not receipt[0]["denied"] and not receipt[0]["invalid"] and receipt[0]["stress"] == 0
                and (receipt[0]["energy_cost"], receipt[0]["water_cost"]) == (9, 5), "wrong selected purchase")
        require((b_plant["energy"], b_plant["water"], b_plant["nodes"]) ==
                (t["energy"], t["water"], t["nodes_before"]) and
                (a_plant["energy"], a_plant["water"], a_plant["nodes"]) ==
                (t["energy"]-9, t["water"]-5, t["nodes_after"]), "wrong immediate cost/body delta")
        action = "extend" if arm == "extension" else "finish"
        require(a_plant["agent"][action] == b_plant["agent"][action]+1 and
                a_plant["agent"]["decisions"] == b_plant["agent"]["decisions"]+1 and
                b_plant["tips"] == a_plant["tips"] + (arm == "finish"), "wrong tip/action delta")
        return {"matching_records": count, "tick": t["tick"], "receipt": receipt[0],
                "control": a_plant, "treated": b_plant}
    raise RuntimeError("missing purchase intervention")


def analyze_case(root, arm, create=False):
    path = root/f"traces/{arm}.jsonl.gz"
    require(experiment.digest(path) == experiment.digest(root/f"traces/{arm}.repeat.jsonl.gz"), "native repeat differs")
    prefix = None
    if arm == "control":
        require(experiment.digest(path) == experiment.digest(root/"input/control.jsonl.gz"), "frozen control changed")
    else:
        prefix = check_prefix(startup.read_trace(root/"input/control.jsonl.gz"), startup.read_trace(path), arm)
    raw, boundaries = panel.split_rows(startup.read_trace(path), CASE.patch)
    if arm != "control":
        target = TARGETS[arm]
        bids = [r for r in raw if r["type"] == "bid" and r["tick"] == target["tick"] and r["id"] == target["id"]]
        require(bool(bids), "missing purchase candidates")
        winner = max(bids, key=lambda b: b["priority"])
        require((winner["action"], winner["tip_index"]) == (target["action"], target["node"]), "wrong selected action")
    for row in raw:
        if row["type"] == "world":
            check_metadata(row, arm)
    routed, _ = guard.prior.neighbors.check_routing(iter(raw), guard.prior.ROUTE)
    vetoes = set() if arm == "control" else {(TARGETS[arm]["tick"], TARGETS[arm]["id"])}
    accounted, audit = guard.accounting_rows(iter(raw), "guard", stop=panel.STOP, boundaries=boundaries,
                                             retain_events=False, growth_vetoes=vetoes)
    worlds = [r for r in accounted if r["type"] == "world"]
    for name, rows in (("accounting", accounted), ("worlds", worlds)):
        target = root/f"traces/{arm}.{name}.jsonl.gz"
        if create:
            guard.write_accounting(target, rows)
        require(rows == list(startup.read_trace(target)), "derived trace changed")
    world, _ = panel.competition.world_analysis(root/f"traces/{arm}.worlds.jsonl.gz", "selective", 512,
                                               panel.STOP, panel.LATE, disturbances=boundaries)
    tips = startup.tips.analyze_stream((json.dumps(r) for r in accounted if r["type"] != "leaf-bid"),
                                       panel.STOP, panel.LATE, 512, disturbances=boundaries)
    records = {p["id"]: p for p in world["lineages"]}
    for p in tips["lineages"]:
        require(all(p[k] == records[p["id"]][k] for k in ("parent", "species", "birth_tick", "death_tick")),
                "tip/resource lifetimes differ")
    extra = panel.supplementary(worlds, boundaries, records, CASE)
    for window in ("whole", "late"):
        require(all(tips["windows"][window][k] == extra["exposure"][window][k]
                    for k in ("living_steps", "tipless_steps", "world_steps")), "independent exposure differs")
    histories, checked = failures.histories(worlds, boundaries, records, panel.STOP)
    targets = {}
    for name, target in TARGETS.items():
        if arm not in ("control", name):
            continue  # IDs assigned after divergence are not matched counterfactuals.
        identity = target["id"]
        targets[name] = {"lineage": records[identity], "history": histories[identity]}
    frames, events = [], [b["event"] for b in boundaries.values()]
    samples = {w["tick"]: boundaries.get(w["tick"], {}).get("after", w) for w in worlds if w["tick"] in FRAMES}
    for tick in FRAMES:
        stem = f"frames/{arm}.{tick}"
        value = experiment.read_json(root/(stem+".json"))
        pixels = (root/(stem+".rgb565")).read_bytes()
        check_metadata(value, arm)
        panel.check_frame(value, samples[tick], CASE, tick, pixels, events)
        require(value == experiment.read_json(root/(stem+".repeat.json")) and
                pixels == (root/(stem+".repeat.rgb565")).read_bytes(), "frame repeat differs")
        if arm == "control" and tick in (122880, panel.STOP):
            require(pixels == (root/f"input/control.{tick}.rgb565").read_bytes() and
                    value == experiment.read_json(root/f"input/control.{tick}.json"), "frozen control frame changed")
        frames.append({"id": f"{arm}.{tick}", "arm": arm, "tick": tick, "result": value,
                       "framebuffer": stem+".rgb565", "png": stem+".png"})
    return {"summary": panel.summary(world, extra, audit), "prefix": prefix, "targets": targets,
            "lineages": world["lineages"], "daily": extra["daily"], "events": events, "routing": routed,
            "checked_live_histories": checked, "tip_audit": {k: tips[k] for k in ("totals", "windows")}}, frames


def compare(control, treated, arm):
    a, b = [{p["id"]: p for p in result["lineages"]} for result in (control, treated)]
    cutoff = TARGETS[arm]["tick"]
    shared = [i for i, p in a.items() if p["birth_tick"] < cutoff]
    fields = ("birth_tick", "parent", "species", "generation", "founder", "genome")
    for i in shared:
        require(i in b and all(a[i][k] == b[i][k] for k in fields), "shared pre-veto identity differs")
    changed = [{"id": i, "control": a[i], "treated": b[i]} for i in shared if a[i] != b[i]]
    fields = ("births", "natural_deaths", "environmental_deaths", "seeds_created", "seeds_expired",
              "descendant_seeds", "seed_producing_descendant_parents")
    return {"shared_pre_veto_lineages": shared, "changed_shared_lineages": changed,
            "later_lineage_ids_not_matched": True,
            "window_delta": {w: {k: treated["summary"]["windows"][w][k]-control["summary"]["windows"][w][k]
                                 for k in fields} for w in ("whole", "late")}}


def analyze(root, create=False):
    results, frames = {}, []
    for arm in ARMS:
        results[arm], captures = analyze_case(root, arm, create)
        frames += captures
        print("Audited", arm, flush=True)
    return {"rule": RULE, "settings": settings(), "cases": results, "frames": frames,
            "comparisons": {a: compare(results["control"], results[a], a) for a in TARGETS}}


def baseline_copies():
    result = {"input/control.jsonl.gz": f"traces/{CASE.name}.jsonl.gz"}
    result.update({f"models/{n}.tgm": f"models/{n}.tgm" for n in settings()["models"]})
    for tick in (122880, panel.STOP):
        for extension in ("json", "rgb565"):
            result[f"input/control.{tick}.{extension}"] = f"frames/{CASE.name}.{tick}.{extension}"
    return result


def check_inputs(root):
    require(experiment.digest(root/"input/baseline-manifest.json") == BASELINE_SHA, "wrong parent manifest")
    baseline = experiment.read_json(root/"input/baseline-manifest.json")
    for dest, source in baseline_copies().items():
        require(experiment.digest(root/dest) == baseline["artifacts"][source], "wrong frozen input")
    started = experiment.read_json(root/"started.json")
    require(started["rule"] == RULE and started["settings"] == settings(), "settings changed")
    require(experiment.digest(root/"input/protocol.md") == started["sources"][PROTOCOL], "protocol changed")
    for name, sha in started["frozen"].items():
        require(experiment.digest(root/name) == sha, "frozen executable/source/build input changed")
    cache = (root/"input/CMakeCache.txt").read_text()
    required = {"DARK_GUARD": "ON", "PURCHASE_VETO": "ON", "WIDE_DISPERSAL": "ON", "WATER_HEADROOM": "ON",
                "COMBINED_EXPERIMENT": "ON", "LARGE_POOL": "ON", "LEAF_MAINTENANCE": "ON",
                "BOTTOM_DRAINAGE": "OFF", "LARGE_SEED_BANK": "OFF", "SEED_RESERVE": "OFF", "FOCAL_SEED_VETO": "OFF"}
    require(all(f"TOY_FACTORY_GARDEN_{k}:BOOL={v}\n" in cache for k,v in required.items()), "wrong build flags")
    require("TOY_FACTORY_SIMULATOR_SANITIZERS:BOOL=ON\n" in cache and
            "CMAKE_C_FLAGS_RELWITHDEBINFO:STRING=-O2 -g\n" in cache, "wrong sanitizer/optimization build")
    native = guard.prior.prior.native_hashes(root/"source.tar.gz")
    require(all(started["sources"].get(k) == v for k,v in native.items()), "native source archive differs")


def check_capture(root):
    check_inputs(root)
    capture = experiment.read_json(root/"capture.json")
    require([(c["artifact"], c["command"]) for c in capture["calls"]] == commands(), "wrong native call inventory")
    for name in capture["artifacts"]:
        gallery.artifact(root, capture, name)
    for target, command in commands():
        require(target in capture["artifacts"] and ("--framebuffer" not in command or command[-1] in capture["artifacts"]),
                "missing native capture")
    return capture


def finish(root):
    capture = check_capture(root)
    sources = experiment.source_files()
    result = analyze(root, create=True)
    require(result == analyze(root), "repeated offline analysis differs")
    for frame in result["frames"]:
        gallery.write_png(root/frame["png"], 240, 240,
                          gallery.rgb565be_to_rgb888((root/frame["framebuffer"]).read_bytes()))
    gallery.contact_sheet(root, [[f for f in result["frames"] if f["arm"] == arm] for arm in ARMS])
    require(experiment.source_files() == sources, "sources changed during analysis")
    check_capture(root)
    experiment.write_json(root/"results.json", result)
    artifacts = {str(p.relative_to(root)): experiment.digest(p) for p in root.rglob("*") if p.is_file()}
    experiment.write_json(root/"manifest.json", {"rule": RULE, "status": "complete", "artifacts": artifacts,
        "sources": sources, "native_calls": len(capture["calls"]),
        "artifact_bytes": sum((root/n).stat().st_size for n in artifacts)})


def verify(root):
    manifest = experiment.read_json(root/"manifest.json")
    require(manifest["rule"] == RULE and manifest["status"] == "complete", "incomplete counterfactual")
    require(set(manifest["artifacts"]) == {str(p.relative_to(root)) for p in root.rglob("*")
            if p.is_file() and p != root/"manifest.json"}, "extra/missing artifacts")
    for name in manifest["artifacts"]:
        gallery.artifact(root, manifest, name)
    check_capture(root)
    require(manifest["sources"] == experiment.read_json(root/"started.json")["sources"], "source provenance changed")
    result = analyze(root)
    require(result == experiment.read_json(root/"results.json"), "reanalysis differs")
    print("Verified frozen control, exact intervention prefixes, repeated trajectories, ledgers and nine native frames", flush=True)
    return result


def collect(baseline, build, output):
    require(not output.exists() and output.is_relative_to(experiment.ROOT/"artifacts") and
            not output.is_relative_to(baseline) and not output.is_relative_to(build), "choose fresh separate output")
    require(experiment.digest(baseline/"manifest.json") == BASELINE_SHA, "wrong frozen baseline")
    sources = experiment.source_files()
    output.mkdir(parents=True)
    experiment.snapshot_sources(output, sources)
    for name in ("input", "bin", "models", "traces", "frames"):
        (output/name).mkdir()
    for dest, source in baseline_copies().items():
        shutil.copy2(baseline/source, output/dest)
    shutil.copy2(baseline/"manifest.json", output/"input/baseline-manifest.json")
    shutil.copy2(experiment.ROOT/PROTOCOL, output/"input/protocol.md")
    for name in ("CMakeCache.txt", "build.ninja"):
        shutil.copy2(build/name, output/"input"/name)
    for name in ("inspect", "replay"):
        shutil.copy2(build/("toy-factory-garden-"+name), output/"bin"/name)
    frozen = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
    experiment.write_json(output/"started.json", {"rule": RULE, "settings": settings(), "sources": sources, "frozen": frozen})
    begin, timings = time.monotonic(), []
    try:
        check_inputs(output)
        for target, command in commands():
            start = time.monotonic()
            if target.endswith(".gz"):
                with tempfile.TemporaryDirectory(prefix="garden-purchase-") as temporary:
                    raw = Path(temporary)/"trace.jsonl"
                    try:
                        experiment.command_run(command, raw, output, 180)
                    except BaseException:
                        if raw.exists():
                            shutil.copy2(raw, output/(target+".failed-stdout"))
                        raise
                    experiment.compress(raw, output/target)
            else:
                experiment.command_run(command, output/target, output, 180)
            timings.append({"artifact": target, "command": command, "seconds": time.monotonic()-start})
            if target == "traces/control.jsonl.gz":
                require(experiment.digest(output/target) == experiment.digest(output/"input/control.jsonl.gz"),
                        "new disabled-hook control differs from frozen raw trace")
            print(f"Captured {len(timings)}/24: {target}", flush=True)
        require(experiment.source_files() == sources, "sources changed during capture")
        artifacts = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
        experiment.write_json(output/"capture.json", {"artifacts": artifacts, "calls": timings,
                                                     "capture_seconds": time.monotonic()-begin})
        finish(output)
    except BaseException as error:
        experiment.write_json(output/"failure.json", {"error": str(error), "completed_calls": timings})
        raise


def portable_target(value, target):
    history = value["history"]
    after = [e for e in history if e["state"]["tick"] > target["tick"]]
    entries = [e for e in after if e["state"]["phase"] == 117]
    later_growth = [{"tick": e["state"]["tick"], **r} for e in after for r in e["events"]
                    if r["kind"] == "growth" and not r["denied"]]
    ticks = {target["tick"]+offset for offset in (-15, 0, 15, 30, 45, 60)}
    ticks.update(e["tick"] for e in later_growth[:5])
    return {"lineage": value["lineage"], "history_steps": len(history), "birth_state": history[0]["state"],
            "last_state": history[-1]["state"],
            "last_live_state": next(e["state"] for e in reversed(history) if not e["state"]["dead"]),
            "first_dark_entry": entries[0] if entries else None,
            "first_later_accepted_growth": later_growth[0] if later_growth else None,
            "receipt_checkpoints": [e for e in history if e["state"]["tick"] in ticks],
            "full_history_location": "results.json in the hash-pinned local bundle"}


def export(root, prefix, check=False):
    result = verify(root)
    compact = copy.deepcopy(result)
    for case in compact["cases"].values():
        case["targets"] = {name: portable_target(value, TARGETS[name]) for name,value in case["targets"].items()}
    compact.update(manifest_sha256=experiment.digest(root/"manifest.json"),
                   full_results_sha256=experiment.digest(root/"results.json"),
                   exporter_sha256=experiment.digest(Path(__file__)),
                   capture_seconds=experiment.read_json(root/"capture.json")["capture_seconds"])
    target = prefix.with_name(prefix.name+"-summary.json")
    images = {prefix.with_suffix(".png"): root/"contact-sheet.png"}
    folder = prefix.with_name(prefix.name+"-frames")
    images.update({folder/(f["id"]+".png"): root/f["png"] for f in result["frames"]})
    require(not prefix.is_relative_to(root), "export must stay outside frozen evidence")
    if not check:
        require(not target.exists() and not folder.exists() and not any(p.exists() for p in images), "export exists")
        folder.mkdir(parents=True)
        experiment.write_json(target, compact)
        for dest, source in images.items():
            shutil.copy2(source, dest)
    require(experiment.read_json(target) == compact and all(experiment.digest(p) == experiment.digest(q)
            for p,q in images.items()), "portable evidence differs")
    print("Portable summary and fixed native gallery verified", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT/"artifacts/garden-renewal-dark-panel-v1")
    parser.add_argument("--build", type=Path, default=experiment.ROOT/"artifacts/build-host-purchase-veto-docker")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--export", type=Path)
    parser.add_argument("--check-export", type=Path)
    args = parser.parse_args()
    require(not (args.export and args.check_export) and (args.verify or not (args.export or args.check_export)),
            "choose a single export/check operation with --verify")
    if args.export or args.check_export:
        export(args.output.resolve(), (args.export or args.check_export).resolve(), bool(args.check_export))
    elif args.verify:
        verify(args.output.resolve())
    else:
        collect(args.baseline.resolve(), args.build.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
