#!/usr/bin/env python3
"""Fixed full-pool non-allocating-action comparison against saved sixteen-slot control."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from itertools import zip_longest
from pathlib import Path
import shutil
import tempfile
import time

import garden_renewal_plant_slots as parent
import garden_renewal_node_pressure as ownership

prior = parent.prior

gap, experiment, require, native = prior.gap, prior.experiment, prior.require, prior.native
order = prior.prior
RULE, NATIVE = "garden-renewal-full-pool-v1", "post-noon-nonallocating-actions-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-full-pool-protocol.md"
BASELINE_SHA = "1cec5406f4f595972fde3cfea355d9f8c6c712fb279112d81f8e0ec3a77e0d3b"
PORTABLE = "benchmarks/garden-longevity/renewal-plant-slots-summary.json"
PORTABLE_SHA = "5aca6ec16c07185aeb857f9267537e7346b0510b2dd7abd7f8f4977395059c82"
AUDIT = "benchmarks/garden-longevity/renewal-node-pressure-summary.json"
AUDIT_SHA = "f9f90fc58ac6976ef9c4d62144a7067370fe09a713600e94768d9c376381f778"
AFTER, STOP, LATE, DAY = prior.AFTER, prior.STOP, prior.LATE, prior.DAY
ARMS, FRAMES = ("control", "nonallocating"), prior.FRAMES


def settings():
    return {"rule": RULE, "native_rule": NATIVE, "arms": list(ARMS), "after_inclusive": AFTER,
            "first_ecology_tick": AFTER+15, "stop": STOP, "late": LATE, "frames": list(FRAMES),
            "limits": {"before": 8, "both_after": 16, "nodes": 512, "seeds": 8},
            "models": parent.settings()["models"], "routing": parent.settings()["routing"],
            "parent_manifest_sha256": BASELINE_SHA, "parent_portable_sha256": PORTABLE_SHA,
            "node_audit_sha256": AUDIT_SHA, "budget": {"native_calls": 20, "training_calls": 0},
            "role": "selected-world full-pool action diagnostic, not qualified sustained renewal"}

def commands():
    baseline = [(p, c) for p, c in parent.commands() if "/sixteen." in p]
    calls = []
    for arm in ARMS:
        for path, command in baseline:
            target = path.replace("/sixteen.", "/"+arm+".")
            cmd = [s.replace("frames/sixteen.", "frames/"+arm+".") for s in command]
            if arm == "nonallocating":
                cmd += ["--full-pool", "nonallocating"]
            calls.append((target, cmd))
    return calls


def check_rule(row, arm):
    require(arm in ARMS, "invalid full-pool arm")
    parent.check_rule(row, "sixteen")
    if arm == "control":
        require("full_pool" not in row, "control unexpectedly changes actions")
        return
    rule = row.get("full_pool")
    require(isinstance(rule, dict) and set(rule) ==
            {"rule", "after", "active", "evaluated", "denied", "overflow", "events"},
            "missing/extra full-pool metadata")
    require(rule["rule"] == NATIVE and type(rule["after"]) is int and rule["after"] == AFTER and
            type(rule["active"]) is bool and rule["active"] == (row["tick"] > AFTER) and
            rule["overflow"] is False and isinstance(rule["evaluated"], list) and
            len(rule["evaluated"]) == 3 and
            all(type(v) is int and 0 <= v <= 0xffffffff for v in rule["evaluated"]) and
            type(rule["denied"]) is int and 0 <= rule["denied"] <= rule["evaluated"][1] and
            isinstance(rule["events"], list) and len(rule["events"]) <= 16, "invalid full-pool metadata")
    require(row["tick"] > AFTER or (rule["evaluated"] == [0, 0, 0] and
            rule["denied"] == 0 and rule["events"] == []), "premature full-pool actions")


def check_prefix(control, candidate):
    for count, (a, b) in enumerate(zip_longest(control, candidate), 1):
        require(a is not None and b is not None, "truncated full-pool prefix")
        if a["type"] in ("world", "seed-sites"):
            check_rule(a, "control")
            check_rule(b, "nonallocating")
        require(a == {k: v for k, v in b.items() if k != "full_pool"}, "physical prefix changed")
        if a["type"] in ("world", "seed-sites") and a["tick"] == AFTER:
            return count
    raise RuntimeError("prefix did not reach full-pool boundary")


def check_selected(event, winner):
    require(set(event) == {"id", "node", "action", "allocates"} and
            type(event["id"]) is int and event["id"] > 0 and
            type(event["node"]) is int and 0 <= event["node"] < 512 and
            type(event["action"]) is int and event["action"] in (0, 1, 2) and
            type(event["allocates"]) is bool, "invalid full-pool event")
    allocates = winner["action"] == 1 and any(c["flags"] & 2 for c in winner["candidates"])
    require((event["id"], event["node"], event["action"], event["allocates"]) ==
            (winner["id"], winner["tip_index"], winner["action"], allocates),
            "full-pool receipt differs from winning proposal")
    return allocates


def audit_actions(rows, arm):
    """Remove only independently verified pre-expense allocation refusals."""
    output, pending, previous, last = [], [], None, -15
    evaluated, denied = [0, 0, 0], 0
    counts, by_plant, first = Counter(), defaultdict(Counter), {}
    for row in rows:
        if row["type"] in ("bid", "leaf-bid"):
            pending.append(row)
            continue
        tick = row["tick"]
        require(row["type"] == "world" and tick == last+15 and tick <= STOP, "missing full-pool census")
        check_rule(row, arm)
        before = {} if previous is None else {p["id"]: p for p in previous["plants"]}
        current = {p["id"]: p for p in row["plants"]}
        stages = ownership.ledger(previous, row) if tick > AFTER else None
        bids = defaultdict(list)
        for bid in pending:
            require(bid["tick"] == tick and bid["id"] in current, "unaligned proposal")
            if bid["type"] == "bid":
                bids[bid["id"]].append(bid)
        events = row.get("full_pool", {}).get("events", [])
        require(len({e["id"] for e in events}) == len(events), "duplicate full-pool winner")
        event_ids = {e["id"] for e in events}
        expected = {i for i in bids if stages and stages["plant_entry_nodes"][i] == 512}
        require(event_ids == (expected if arm == "nonallocating" else set()), "missing/extra full-entry receipt")
        if arm == "control":
            require(not expected, "historical full-node policy unexpectedly ran")
        removed = set()
        for event in events:
            identity = event["id"]
            p, old = current[identity], before.get(identity)
            require(not p["dead"] and stages and stages["plant_entry_nodes"][identity] == 512,
                    "receipt outside live full-pool stage")
            winner = max(bids[identity], key=lambda b: b["priority"])
            allocates = check_selected(event, winner)
            action = event["action"]
            evaluated[action] += 1
            denied += int(allocates)
            values = ownership.light.resources.budget(old, p, tick)
            commits = sum(values[k] for k in ("waits", "extensions", "finishes"))
            require(values["energy_renewal"] == 0 and p["nodes"] == (old["nodes"] if old else 4),
                    "full-pool winner renewed or allocated")
            if allocates:
                require(commits == 0 and values["energy_growth"] == values["water_growth"] == 0 and
                        p["agent"] == (old["agent"] if old else dict.fromkeys(p["agent"], 0)) and
                        p["tips"] == (old["tips"] if old else 3) and
                        not any(e["id"] == identity and e["kind"] == "growth" for e in row["dark_guard"]["events"]),
                        "allocation refusal committed state/expense or reached later guard")
                removed.add(identity)
                label = "allocation_refused"
            elif commits:
                require(values[("waits", "extensions", "finishes")[action]] == 1,
                        "committed full-pool action differs")
                ownership.light.growth(old, p, tick, bids[identity], values)
                label = ("committed_wait", "committed_exhausted_extend", "committed_finish")[action]
            else:
                require(action != 0 and values["energy_growth"] == 0, "uncommitted WAIT or charged refusal")
                label = "later_guard_refused"
            for stats in (counts, by_plant[str(identity)]):
                stats["selected"] += 1
                stats[label] += 1
            if label not in first:
                first[label] = {"tick": tick, "event": event, "bid": winner}
        if arm == "nonallocating":
            require(row["full_pool"]["evaluated"] == evaluated and row["full_pool"]["denied"] == denied,
                    "full-pool counters do not reconcile")
        output.extend(b for b in pending if not (b["type"] == "bid" and b["id"] in removed))
        counts["uncommitted_bids_removed"] += sum(len(bids[i]) for i in removed)
        output.append(row)
        pending, previous, last = [], row, tick
    require(last == STOP and not pending, "truncated full-pool receipts")
    counts.update({k: 0 for k in ("selected", "allocation_refused", "committed_wait", "committed_finish",
                                 "committed_exhausted_extend", "later_guard_refused")})
    return output, {"counts": counts, "by_plant": dict(by_plant), "first": first}


def analyze_case(root, arm, create=False):
    actions = {}
    def prepare(rows):
        # Retain complete routing evidence even for uncommitted allocation bids.
        actions["raw_routing"], _ = gap.guard.prior.neighbors.check_routing(iter(rows), gap.guard.prior.ROUTE)
        filtered, actions["receipts"] = audit_actions(rows, arm)
        return filtered
    result, frames, worlds = parent.parent.analyze_case(root, arm, create, rule_check=check_rule, preaccount=prepare)
    sites, _, _ = order.parent.parent.parent.split_census(
        gap.read_trace(root/f"traces/{arm}.sites.jsonl.gz"), "optional", "seed-sites")
    require(all(all(w.get(k) == s.get(k) for k in ("plant_admission", "full_pool"))
                for w, s in zip(worlds, sites, strict=True)), "world/site metadata differs")
    by_tick = {w["tick"]: w for w in worlds}
    require(all(all(f["result"].get(k) == by_tick[f["tick"]].get(k) for k in ("plant_admission", "full_pool"))
                for f in frames), "frame metadata differs")
    result["admission_pressure"] = parent.pressure(worlds, sites)
    result["full_pool_actions"] = actions
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
    a, b = metrics["control"], metrics["nonallocating"]
    require(a == {"new_full_day_survivors": 17, "new_full_day_parents_with_full_day_child": 6,
                  "incumbent_deaths": 6, "endpoint_species": 2, "endpoint_families": 2},
            "changed historical outcome anchors")
    gates = {"nonallocating_tip_completion": sum(cases["nonallocating"]["full_pool_actions"]["receipts"]["counts"][k]
                for k in ("committed_finish", "committed_exhausted_extend")) > 0,
             "survivors_not_reduced": b["new_full_day_survivors"] >= 17,
             "durable_parents_not_reduced": b["new_full_day_parents_with_full_day_child"] >= 6,
             "no_extra_incumbent_deaths": b["incumbent_deaths"] <= 6,
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
    old = experiment.read_json(root/"input/parent-results.json")["cases"]["sixteen"]
    require(all(cases["control"][k] == v for k, v in old.items()), "historical derived outcomes changed")
    require((root/f"frames/control.{AFTER}.rgb565").read_bytes() ==
            (root/f"frames/nonallocating.{AFTER}.rgb565").read_bytes(), "boundary pixels differ")
    divergence = next(({"tick": a["tick"], "control": a, "nonallocating": b}
                       for a, b in zip(worlds["control"], worlds["nonallocating"], strict=True)
                       if a["hash"] != b["hash"]), None)
    require(divergence is None or divergence["tick"] >= AFTER+15, "premature physical divergence")
    return {"settings": settings(), "prefixes": prefixes, "first_hash_divergence": divergence,
            "cases": cases, "frames": frames, "decision": decision(cases)}

def copies():
    return {"input/parent-results.json": "results.json", "input/prior-cache.txt": "input/CMakeCache.txt",
            "input/native-source.tar.gz": "source.tar.gz",
            **{f"models/{n}.tgm": f"models/{n}.tgm" for n in settings()["models"]},
            **{f"input/history/{n}": n.replace("control.", "sixteen.") for n in historical_files()}}


def check_inputs(root):
    require(experiment.digest(root/"input/parent-manifest.json") == BASELINE_SHA and
            experiment.digest(root/"input/parent-summary.json") == PORTABLE_SHA and
            experiment.digest(root/"input/node-audit.json") == AUDIT_SHA, "changed parent evidence")
    manifest = experiment.read_json(root/"input/parent-manifest.json")
    for dest, source in copies().items():
        require(experiment.digest(root/dest) == manifest["artifacts"][source], "changed parent copy")
    started = experiment.read_json(root/"started.json")
    require(started["settings"] == settings() and experiment.digest(root/"input/protocol.md") == started["sources"][PROTOCOL],
            "changed protocol/settings")
    for name, sha in started["frozen"].items():
        require(experiment.digest(root/name) == sha, "frozen input changed")
    old, new = [native.native_hashes(root/p) for p in ("input/native-source.tar.gz", "source.tar.gz")]
    added = {"src/garden_full_pool.h", "sim/garden_full_pool.c", "sim/garden_full_pool_test.c"}
    changed = {"src/garden_world.c", "src/garden_world.h", "sim/garden_inspect.c", "sim/garden_replay.c"}

    require(new.keys()-old.keys() == added and not old.keys()-new.keys() and
            {n for n in old if old[n] != new[n]} <= changed, "unrelated native changes")
    require(all(started["sources"].get(n) == sha for n, sha in new.items()), "native archive mismatch")
    a, b = [native.cache_settings(root/p) for p in ("input/prior-cache.txt", "input/CMakeCache.txt")]
    require(b.pop("TOY_FACTORY_GARDEN_FULL_POOL:BOOL", None) == "ON" and a == b, "wrong build configuration")


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
            (experiment.ROOT/AUDIT, "input/node-audit.json")):
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
                with tempfile.TemporaryDirectory(prefix="garden-full-pool-") as temporary:
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
                print("Historical sixteen-slot control traces and frames match exactly", flush=True)
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
    print("Verified portable full-pool comparison and six native frames", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT/"artifacts/garden-renewal-plant-slots-v1")
    parser.add_argument("--build", type=Path, default=experiment.ROOT/"artifacts/build-host-full-pool-docker")
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
