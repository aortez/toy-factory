#!/usr/bin/env python3
"""Fixed three-arm test of retaining one upkeep bill at the dawn FINISH handoff."""
from __future__ import annotations

import argparse
from itertools import zip_longest
from pathlib import Path
import shutil
import tempfile
import time

import garden_renewal_dawn_finish as parent

gap, experiment, require, native = parent.gap, parent.experiment, parent.require, parent.native
RULE, NATIVE = "garden-renewal-dawn-reserve-v1", "dawn-finish-reserve-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-dawn-reserve-protocol.md"
BASELINE_SHA = "ae0c428ba07359a56cda2cea5441b71b7deb5ab79cdde5fdffdade36a2f5e910"
PORTABLE = "benchmarks/garden-longevity/renewal-dawn-finish-summary.json"
PORTABLE_SHA = "cef6b7d4b4d38958faf4adb07c8ac82a594074455dd1870a784e058e021b6fce"
FIRST, LAST, ID = parent.FIRST, parent.LAST, parent.ID
NOON, RESERVE, DIVERGENCE = 69120, 8, 68385
STOP, LATE, FRAMES, ARMS = parent.STOP, parent.LATE, parent.FRAMES, ("control", "defer", "reserve")


def settings():
    return {**parent.settings(), "rule": RULE, "native_rule": NATIVE,
            "old_last_inclusive": LAST, "last_inclusive": NOON-15,
            "cutoff_exclusive": NOON, "reserve_energy": RESERVE, "arms": list(ARMS),
            "budget": {"native_calls": 36, "training_calls": 0}}


def commands():
    old = parent.commands()
    new = []
    for target, command in old:
        if "/defer." not in target:
            continue
        new.append((target.replace("/defer.", "/reserve."),
                    [c.replace("/defer.", "/reserve.") if c != "defer" else "reserve" for c in command]))
    return [*old, *new]


def metadata(hits=0, tick=0, node=0, *, handoff_tick=0, handoff_energy=0, handoff_node=0):
    return {"rule": NATIVE, "id": ID, "first": FIRST, "last": NOON-15,
            "hits": hits, "last_tick": tick, "last_node": node, "cutoff_tick": NOON,
            "reserve": RESERVE, "handoff_tick": handoff_tick,
            "handoff_energy": handoff_energy, "handoff_node": handoff_node}


def check_refusals(rows, arm, *, audit=None):
    require(arm == "reserve", "reserve checker applied to another arm")
    current, previous, pending, receipts, vetoes, handoff = metadata(), {}, [], [], set(), None
    for row in rows:
        if row["type"] in ("bid", "leaf-bid"):
            pending.append(row)
            continue
        tick = row["tick"]
        require("dawn_finish" in row, "missing reserve diagnostics")
        events = [e for e in row["dark_guard"]["events"] if e["id"] == ID and e["kind"] == "growth"]
        require(len(events) <= 1, "duplicate target expense")
        if FIRST <= tick < NOON and not current["handoff_tick"] and events and not events[0]["denied"]:
            candidates = [b for b in pending if b["type"] == "bid" and b["id"] == ID]
            require(bool(candidates) and ID in previous, "missing winning bid/previous target")
            winner, event = max(candidates, key=lambda b: b["priority"]), events[0]
            require(winner["tick"] == tick and all(winner[k] == v for k, v in
                {"action": 2, "priority": 32767, "x": 47, "y": 193, "depth": 9,
                 "maximum_depth": 9, "tissue": 1, "tip_flags": 1}.items()), "wrong reserved tip")
            require(event["node"] == winner["tip_index"] and not event["invalid"] and
                    all(event[k] == v for k, v in {"nodes_before": 61, "nodes_after": 61,
                                                 "energy_cost": 8, "water_cost": 5}.items()),
                    "wrong reserve expense")
            upkeep = (event["nodes_before"]+7)//8
            require(upkeep == RESERVE and 8 <= event["energy"] <= 256 and
                    5 <= event["water"] <= 512 and 0 <= event["stress"] < 8, "wrong reserve resources")
            plant = next(p for p in row["plants"] if p["id"] == ID)
            require(not plant["dead"] and plant["nodes"] == 61, "target changed body/life state")
            receipt = {"tick": tick, "phase": row["sun_phase"], "expense": event, "bid": winner}
            if tick > LAST and event["energy"] >= event["energy_cost"]+upkeep:
                require(plant["energy"] == event["energy"]-8 and plant["water"] == event["water"]-5 and
                        plant["tips"] == 0 and plant["agent"]["decisions"] == previous[ID]["agent"]["decisions"]+1 and
                        plant["agent"]["finish"] == previous[ID]["agent"]["finish"]+1,
                        "qualifying handoff did not commit/pay")
                current.update(handoff_tick=tick, handoff_energy=event["energy"], handoff_node=event["node"])
                handoff = {**receipt, "upkeep_energy": upkeep, "remaining_energy": plant["energy"],
                           "committed": plant}
            else:
                require(plant["agent"] == previous[ID]["agent"] and plant["tips"] == 1 and
                        (plant["energy"], plant["water"]) == (event["energy"], event["water"]),
                        "refusal spent resources or committed a decision")
                if not receipts:
                    require(tick == FIRST and event["node"] == 378 and event["energy"] == 251 and
                            event["water"] == 512 and event["stress"] == 0 and
                            all(event[k]["supported"] and not event[k]["death_step"] for k in ("before", "after")),
                            "wrong first receipt")
                current.update(hits=current["hits"]+1, last_tick=tick, last_node=event["node"])
                receipts.append(receipt)
                vetoes.add((tick, ID))
        require(row["dawn_finish"] == current, "missing/extra/out-of-window reserve receipt")
        previous, pending = {p["id"]: p for p in row["plants"]}, []
    require(not pending and bool(receipts), "missing/incomplete reserve receipts")
    if audit is not None:
        audit.update(handoff=handoff, final_receipt=current, cutoff_tick=NOON,
                     disposition="handed-off" if handoff else "no-handoff-before-cutoff")
    return vetoes, receipts


def check_prefix(deferred, reserved):
    previous = None
    for count, (a, b) in enumerate(zip_longest(deferred, reserved)):
        require(a is not None and b is not None, "truncated reserve prefix")
        if parent.clean(a) == parent.clean(b):
            require(a["tick"] <= DIVERGENCE, "missing handoff divergence")
            if a["type"] == "world":
                previous = a
            continue
        require(a["type"] == b["type"] == "world" and a["tick"] == b["tick"] == DIVERGENCE,
                "divergence outside the dawn handoff")
        require({k: v for k, v in parent.clean(a).items() if k not in ("hash", "plants")} ==
                {k: v for k, v in parent.clean(b).items() if k not in ("hash", "plants")},
                "non-target world state changed")
        left, right = [{p["id"]: p for p in row["plants"]} for row in (a, b)]
        require(left.keys() == right.keys() and all(left[i] == right[i] for i in left if i != ID),
                "another lineage changed at reserve divergence")
        p, q = left[ID], right[ID]
        require(previous is not None and previous["tick"] == DIVERGENCE-15, "missing pre-handoff state")
        old = next(p for p in previous["plants"] if p["id"] == ID)
        require({k: v for k, v in p.items() if k not in ("energy", "water", "tips", "agent")} ==
                {k: v for k, v in q.items() if k not in ("energy", "water", "tips", "agent")},
                "unexpected reserve state change")
        require((p["energy"], p["water"], p["tips"], q["energy"], q["water"], q["tips"], q["stress"]) ==
                (1, 507, 0, 9, 512, 1, 7), "wrong reserve delta")
        require(q["agent"] == old["agent"] and p["agent"]["decisions"] == q["agent"]["decisions"]+1 and
                p["agent"]["finish"] == q["agent"]["finish"]+1, "reserve refusal committed telemetry")
        require(b["dawn_finish"] == metadata(11, DIVERGENCE, 378) and a["hash"] != b["hash"],
                "wrong initial reserve receipt/hash")
        return {"matching_raw_records": count, "tick": DIVERGENCE, "deferred": p, "reserved": q,
                "ordinary_guard": a["dark_guard"]}
    raise RuntimeError("missing reserve intervention")


def historical_files(arm):
    return [*(f"traces/{arm}.{kind}.jsonl.gz" for kind in ("world", "sites")),
            *(f"frames/{arm}.{tick}.{ext}" for tick in FRAMES for ext in ("json", "rgb565"))]


def check_historical(root, arm):
    require(arm in parent.ARMS, "not a historical arm")
    for name in historical_files(arm):
        require(experiment.digest(root/name) == experiment.digest(root/"input/history"/name),
                "historical trace/frame drift: "+name)
        repeated = name.replace(".jsonl.gz", ".repeat.jsonl.gz") if name.endswith(".gz") else (
            name.rsplit(".", 1)[0]+".repeat."+name.rsplit(".", 1)[1])
        require(experiment.digest(root/repeated) == experiment.digest(root/name), "historical repeat drift")


def analyze(root, create=False):
    for arm in parent.ARMS:
        check_historical(root, arm)
    original_prefix = parent.check_prefix(*(gap.read_trace(root/f"traces/{arm}.world.jsonl.gz") for arm in parent.ARMS))
    prefix = check_prefix(*(gap.read_trace(root/f"traces/{arm}.world.jsonl.gz") for arm in ("defer", "reserve")))
    cases, frames, audit = {}, [], {}
    for arm in ARMS:
        checker = (lambda rows, name: check_refusals(rows, name, audit=audit)) if arm == "reserve" else None
        cases[arm], samples = parent.analyze_case(root, arm, create, refusal_check=checker)
        frames.extend(samples)
    prior = experiment.read_json(root/"input/dawn-results.json")
    require(all(cases[arm] == prior["cases"][arm] for arm in parent.ARMS) and
            original_prefix == prior["prefix"], "historical derived outcomes drift")
    require(cases["reserve"]["refusals"][:len(cases["defer"]["refusals"])] == cases["defer"]["refusals"],
            "old-window refusal receipts changed")
    for tick in FRAMES[:2]:
        require((root/f"frames/defer.{tick}.rgb565").read_bytes() ==
                (root/f"frames/reserve.{tick}.rgb565").read_bytes(), "reserve prefix pixels differ")
    if audit["handoff"]:
        paid = cases["reserve"]["target"]["first_paid_growth_after_release"]
        require(paid is not None and paid["state"]["tick"] == audit["handoff"]["tick"] and
                paid["budget"]["energy_growth"] == 8 and paid["budget"]["water_growth"] == 5,
                "handoff receipt and independently reconstructed cost differ")
    return {"settings": settings(), "original_prefix": original_prefix, "prefix": prefix,
            "reserve_audit": audit, "cases": cases, "frames": frames}


def copies():
    return {"input/dawn-results.json": "results.json", "input/prior-cache.txt": "input/CMakeCache.txt",
            "input/native-source.tar.gz": "source.tar.gz",
            **{f"models/{name}.tgm": f"models/{name}.tgm" for name in settings()["models"]},
            **{f"input/{name}": f"input/{name}" for name in
               ("prior-results.json", "prior-world.jsonl.gz", "prior-sites.jsonl.gz",
                "prior-final.json", "prior-final.rgb565")},
            **{f"input/history/{name}": name for arm in parent.ARMS for name in historical_files(arm)}}


def check_inputs(root):
    require(experiment.digest(root/"input/parent-manifest.json") == BASELINE_SHA and
            experiment.digest(root/"input/parent-summary.json") == PORTABLE_SHA, "changed parent evidence")
    manifest = experiment.read_json(root/"input/parent-manifest.json")
    for dest, source in copies().items():
        require(experiment.digest(root/dest) == manifest["artifacts"][source], "changed parent copy")
    started = experiment.read_json(root/"started.json")
    require(started["settings"] == settings() and
            experiment.digest(root/"input/protocol.md") == started["sources"][PROTOCOL], "changed protocol/settings")
    for path, sha in started["frozen"].items():
        require(experiment.digest(root/path) == sha, "frozen input changed")
    old, new = [native.native_hashes(root/p) for p in ("input/native-source.tar.gz", "source.tar.gz")]
    allowed = {"src/garden_dawn_finish.h", "sim/garden_dawn_finish.c", "sim/garden_dawn_finish_test.c",
               "sim/garden_inspect.c", "sim/garden_replay.c"}
    require(old.keys() == new.keys() and {n for n in old if old[n] != new[n]} <= allowed,
            "unrelated native source change")
    require(all(started["sources"].get(n) == sha for n, sha in new.items()), "native archive mismatch")
    require(native.cache_settings(root/"input/prior-cache.txt") == native.cache_settings(root/"input/CMakeCache.txt"),
            "build configuration changed")


def check_capture(root):
    check_inputs(root)
    capture = experiment.read_json(root/"capture.json")
    require(capture["settings"] == settings() and
            [(c["artifact"], c["command"]) for c in capture["calls"]] == commands(), "wrong native call inventory")
    for name in capture["artifacts"]:
        gap.gallery.artifact(root, capture, name)
    return capture


def finish(root):
    """Analysis-only recovery; never rerun or overwrite captured observations."""
    require(not (root/"manifest.json").exists(), "bundle already sealed")
    capture = check_capture(root)
    sources, start = parent.analysis_sources(), time.monotonic()
    result = analyze(root, True)
    require(result == analyze(root), "analysis repeat differs")
    for frame in result["frames"]:
        gap.gallery.write_png(root/frame["png"], 240, 240,
            gap.gallery.rgb565be_to_rgb888((root/frame["framebuffer"]).read_bytes()))
    gap.gallery.contact_sheet(root, [[f for f in result["frames"] if f["arm"] == arm] for arm in ARMS])
    check_capture(root)
    require(parent.analysis_sources() == sources, "analysis changed while running")
    experiment.write_json(root/"analysis-sources.json", sources)
    experiment.write_json(root/"results.json", result)
    experiment.write_json(root/"timings.json", {"calls": capture["calls"], "analysis_and_repeat_seconds": time.monotonic()-start})
    artifacts = {str(p.relative_to(root)): experiment.digest(p) for p in root.rglob("*") if p.is_file()}
    experiment.write_json(root/"manifest.json", {"rule": RULE, "status": "complete", "artifacts": artifacts,
        "native_calls": len(capture["calls"]), "artifact_bytes": sum((root/n).stat().st_size for n in artifacts)})


def collect(baseline, build, output):
    require(not output.exists() and output.is_relative_to(experiment.ROOT/"artifacts") and
            not any(output.is_relative_to(p) for p in (baseline, build)), "choose fresh independent output")
    gap.parent.shadow.check_frozen(baseline, BASELINE_SHA)
    require(experiment.digest(experiment.ROOT/PORTABLE) == PORTABLE_SHA, "changed parent summary")
    sources = experiment.source_files()
    output.mkdir(parents=True)
    experiment.snapshot_sources(output, sources)
    for name in ("input", "models", "bin", "traces", "frames"):
        (output/name).mkdir()
    for dest, source in copies().items():
        (output/dest).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(baseline/source, output/dest)
    for source, dest in ((baseline/"manifest.json", "input/parent-manifest.json"),
            (experiment.ROOT/PORTABLE, "input/parent-summary.json"), (experiment.ROOT/PROTOCOL, "input/protocol.md")):
        shutil.copy2(source, output/dest)
    for name in ("CMakeCache.txt", "build.ninja"):
        shutil.copy2(build/name, output/"input"/name)
    for name in ("inspect", "replay"):
        shutil.copy2(build/("toy-factory-garden-"+name), output/"bin"/name)
    frozen = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
    experiment.write_json(output/"started.json", {"settings": settings(), "sources": sources, "frozen": frozen})
    begin, timings = time.monotonic(), []
    try:
        check_inputs(output)
        for target, cmd in commands():
            start = time.monotonic()
            if target.endswith(".gz"):
                with tempfile.TemporaryDirectory(prefix="garden-dawn-reserve-") as temporary:
                    raw = Path(temporary)/"trace.jsonl"
                    try:
                        experiment.command_run(cmd, raw, output, 180)
                    finally:
                        if raw.exists():
                            experiment.compress(raw, output/target)
            else:
                experiment.command_run(cmd, output/target, output, 180)
            timings.append({"artifact": target, "command": cmd, "seconds": time.monotonic()-start})
            for arm in parent.ARMS:
                if target == f"frames/{arm}.{STOP}.repeat.json":
                    check_historical(output, arm)
                    print("Exact historical traces and all frames:", arm, flush=True)
            print(f"Captured {len(timings)}/36: {target}", flush=True)
        require(experiment.source_files() == sources, "sources changed during capture")
        artifacts = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
        experiment.write_json(output/"capture.json", {"settings": settings(), "calls": timings,
            "artifacts": artifacts, "capture_seconds": time.monotonic()-begin})
    except BaseException as error:
        experiment.write_json(output/"capture-failure.json", {"error": str(error), "completed_calls": timings})
        raise
    finish(output)


def verify(root):
    manifest = experiment.read_json(root/"manifest.json")
    require(manifest["rule"] == RULE and manifest["status"] == "complete" and
            manifest["native_calls"] == 36, "wrong/incomplete bundle")
    require(set(manifest["artifacts"]) == {str(p.relative_to(root)) for p in root.rglob("*")
            if p.is_file() and p != root/"manifest.json"}, "extra/missing artifact")
    for name in manifest["artifacts"]:
        gap.gallery.artifact(root, manifest, name)
    capture = check_capture(root)
    require(experiment.read_json(root/"timings.json")["calls"] == capture["calls"], "timings changed")
    require(experiment.read_json(root/"analysis-sources.json") == parent.analysis_sources(), "analysis sources changed")
    result = analyze(root)
    require(result == experiment.read_json(root/"results.json"), "saved analysis differs")
    return result


def export(root, prefix, check=False):
    require(not prefix.is_relative_to(root), "export outside frozen evidence")
    result = {**verify(root), "manifest_sha256": experiment.digest(root/"manifest.json"),
              "full_results_sha256": experiment.digest(root/"results.json"),
              "timing": experiment.read_json(root/"timings.json")}
    target, folder = prefix.with_name(prefix.name+"-summary.json"), prefix.with_name(prefix.name+"-frames")
    images = {prefix.with_suffix(".png"): root/"contact-sheet.png"}
    images.update({folder/(f["id"]+".png"): root/f["png"] for f in result["frames"]})
    if not check:
        require(not target.exists() and not folder.exists() and not any(p.exists() for p in images), "export exists")
        folder.mkdir(parents=True)
        experiment.write_json(target, result)
        for dest, source in images.items():
            shutil.copy2(source, dest)
    require(experiment.read_json(target) == result and
            all(experiment.digest(p) == experiment.digest(q) for p, q in images.items()), "portable evidence differs")
    print("Verified portable reserve-handoff evidence and twelve native frames", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT/"artifacts/garden-renewal-dawn-finish-v1-analysis-v2")
    parser.add_argument("--build", type=Path, default=experiment.ROOT/"artifacts/build-host-dawn-reserve-docker")
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
