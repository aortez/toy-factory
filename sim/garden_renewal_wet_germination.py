#!/usr/bin/env python3
"""One post-gap germination-light A/B, with exact receipts and lifetime follow-up."""
from __future__ import annotations

import argparse
from collections import Counter
from itertools import zip_longest
from pathlib import Path
from garden_plant_slots import plant_capacity
import shutil
import tempfile
import time

import garden_renewal_germination_trace as trace

gap, audit = trace.gap, trace.audit
experiment, require, native = trace.experiment, trace.require, trace.native
RULE, NATIVE = "garden-renewal-wet-germination-v1", "wet-germination-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-wet-germination-protocol.md"
DIAGNOSTIC_SHA = "57655928565878aabc170f71c59dee54841a859b96915c99c1a2b0cd0b04d635"
DIAGNOSTIC_PORTABLE = "benchmarks/garden-longevity/renewal-germination-trace-summary.json"
DIAGNOSTIC_PORTABLE_SHA = "fecaa15ec70fd9d619eb73313c8907454126146dc03d02d01a4843e523564f4b"
ARMS = ("required", "optional")
AT, STOP, LATE, FRAMES = gap.AT, gap.STOP, gap.LATE, gap.FRAMES


def settings():
    return {"rule": RULE, "native_rule": NATIVE, "seed": gap.SEED, "activation_tick": AT,
            "stop": STOP, "late": LATE, "frames": list(FRAMES), "models": gap.settings()["models"],
            "routing": gap.settings()["routing"], "budget": {"native_calls": 28, "training_calls": 0}}


def commands():
    result = []
    for arm in ARMS:
        base = ["models/r2-n.tgm", "rainfed-crowded", experiment.NIGHT_POLICY, "0x"+gap.SEED]
        options = ["--focal-model", "models/r2-w.tgm", "--focal-founder", "5",
                   "--gap-at", str(AT), "--gap-lineage", str(gap.REMOVED)]
        if arm == "optional":
            options += ["--wet-germination-after", str(AT)]
        for kind, flag in (("world", "--ecology"), ("sites", "--seed-sites"), ("attempts", None)):
            cmd = (["bin/seed-attempts", *base, "0", "0", str(STOP), *options] if flag is None else
                   ["bin/inspect", *base, "--leaf-policy", "selective", *options, flag, "--ticks", str(STOP)])
            for suffix in ("", ".repeat"):
                result.append((f"traces/{arm}.{kind}{suffix}.jsonl.gz", cmd.copy()))
        for tick in FRAMES:
            for suffix in ("", ".repeat"):
                stem = f"frames/{arm}.{tick}{suffix}"
                result.append((stem+".json", ["bin/replay", *base, "--leaf-policy", "selective", *options,
                    "--ticks", str(tick), "--framebuffer", stem+".rgb565"]))
    return result


def check_rule(row, active):
    require(row.get("germination_rule") == (NATIVE if active else None), "wrong/missing germination rule")


def normalize(row):
    """Remove only the declared rule/hash/query difference, never physical state."""
    result = {k: v for k, v in row.items() if k not in ("hash", "germination_rule", "seeds", "sites")}
    result["seeds"] = [{**s, "blockers": s["blockers"] & ~4} for s in row["seeds"]]
    if "sites" in row:
        result["sites"] = [[s[0] & ~4, *s[1:]] for s in row["sites"]]
    return result


def activation(before, after, event, at=AT):
    require(set(event) == {"type", "rule", "tick", "before_hash", "after_hash"} and
            (event["type"], event["rule"], event["tick"]) == ("germination-rule", NATIVE, at), "wrong activation")
    require(before["tick"] == after["tick"] == at and before["type"] == after["type"] and
            before["hash"] == event["before_hash"] and after["hash"] == event["after_hash"] and
            before["hash"] != after["hash"], "wrong activation hash/boundary")
    check_rule(before, False)
    check_rule(after, True)
    require(normalize(before) == normalize(after), "activation changed physical/counter/agent state")
    require(after["seeds"] == [{**s, "blockers": s["blockers"] & ~4} for s in before["seeds"]],
            "activation changed a non-light seed gate")
    if "sites" in before:
        require(after["sites"] == [[s[0] & ~4, *s[1:]] for s in before["sites"]], "activation changed site resources/gates")


def split_census(rows, arm, kind="world"):
    ordinary, exported, activated, previous = [], None, None, None
    iterator = iter(rows)
    for row in iterator:
        if row["type"] in ("gap", "germination-rule"):
            after = next(iterator, None)
            require(previous is not None and after is not None and previous["type"] == after["type"] == kind,
                    "unbracketed boundary")
            if row["type"] == "gap":
                require(exported is None and activated is None, "repeated/reordered export")
                gap.validate_boundary(previous, after, row)
                exported = {"before": previous, "event": row, "after": after}
            else:
                require(arm == "optional" and activated is None and exported is not None and
                        previous == exported["after"], "activation not immediately after named export")
                activation(previous, after, row)
                activated = {"before": previous, "event": row, "after": after}
            previous = after
            continue
        require(row["type"] in (("world", "bid", "leaf-bid") if kind == "world" else (kind,)), "unknown census record")
        if row["type"] == kind:
            check_rule(row, activated is not None)
        ordinary.append(row)
        previous = row
    require(exported is not None and (activated is not None) == (arm == "optional"), "missing export/activation")
    return ordinary, exported, activated


def check_seed_state(row, world, sites, boundary=False):
    require(row["type"] == "seed-step" and row["tick"] == world["tick"] == sites["tick"] and
            row["hash"] == world["hash"] == sites["hash"], "seed observer changed world")
    require(all(row[k] == sites[k] for k in ("sun_phase", "sun_strength")) and
            all(row[k] == world[k] == sites[k] for k in ("nodes", "births")) and
            row["plants"] == len(world["plants"]) == len(sites["plants"]) and
            row["seeds"] == len(world["seeds"]) == len(sites["seeds"]) and
            row["expired"] == world["seeds_expired"] == sites["seeds_expired"] and
            row["created"] == world["seeds_created"] == sites["seeds_created"], "seed state counters differ")
    check_rule(row, world.get("germination_rule") == NATIVE)
    check_rule(sites, world.get("germination_rule") == NATIVE)
    if boundary:
        require(row["stages"] == row["sites_before"] == row["attempts"] == [], "boundary contains an ecology step")


def seed_receipts(rows, worlds, sites, boundaries, arm, stop=STOP):
    header = {**trace.expected_header("gap"), "from": 0, "end": stop}
    if arm == "optional":
        header["wet_germination_after"] = AT
    iterator = iter(rows)
    require(next(iterator, None) == header, "wrong seed audit header")
    totals = {label: Counter() for label in ("whole", "post_export", "late")}
    masks = {label: Counter() for label in totals}
    births, events, points = [], [], 0
    old = None
    for tick in range(0, stop+1, 15):
        row = next(iterator, None)
        require(row is not None, "truncated seed trace")
        w, s = worlds[tick], sites[tick]
        check_seed_state(row, w, s, tick == 0)
        points += 1
        if old is not None:
            active = row.get("germination_rule") == NATIVE
            values, hist, born = audit.check_step(row, old, w, s, 512, light_required=not active)
            for label, start in (("whole", -1), ("post_export", AT), ("late", LATE)):
                if tick > start:
                    totals[label].update(values)
                    masks[label].update({str(i): n for i, n in enumerate(hist) if n})
            births.extend({"tick": tick, "sun_phase": row["sun_phase"], "sun_strength": row["sun_strength"],
                           "birth_tick": tick-a["age"]*15, "rule": NATIVE if active else "light-required",
                           **a} for a in born)
        old = {**w, "seeds": s["seeds"]}
        for world_boundary, site_boundary in boundaries:
            if world_boundary["event"]["tick"] != tick:
                continue
            event = next(iterator, None)
            require(event == world_boundary["event"] == site_boundary["event"], "seed boundary differs")
            after = next(iterator, None)
            require(after is not None, "missing post-boundary seed state")
            w, s = world_boundary["after"], site_boundary["after"]
            check_seed_state(after, w, s, True)
            old = {**w, "seeds": s["seeds"]}
            points += 1
            events.append(event)
    require(next(iterator, None) is None, "extra seed trace records")
    return {"checkpoints_including_boundaries": points, "totals": totals, "mature_masks": masks,
            "germinations": births, "events": events}


def occupancy(worlds, after):
    result = {name: Counter() for name in ("whole", "post_export", "late")}
    for ordinary in worlds:
        row = after if ordinary["tick"] == AT else ordinary
        if row["tick"] >= STOP:
            continue
        values = {"steps": 1, "plant_slot_steps": len(row["plants"]), "seed_slot_steps": len(row["seeds"]),
                  "plant_full_steps": int(len(row["plants"]) == plant_capacity(row)), "seed_full_steps": int(len(row["seeds"]) == 8),
                  "living_steps": row["living"], "node_steps": row["nodes"]}
        for name, start in (("whole", 0), ("post_export", AT), ("late", LATE)):
            if row["tick"] >= start:
                result[name].update(values)
    return result


def analyze_case(root, arm, create=False):
    for kind in ("world", "sites", "attempts"):
        require(experiment.digest(root/f"traces/{arm}.{kind}.jsonl.gz") ==
                experiment.digest(root/f"traces/{arm}.{kind}.repeat.jsonl.gz"), "native repeat changed")
    raw, exported, active = split_census(gap.read_trace(root/f"traces/{arm}.world.jsonl.gz"), arm)
    sites, site_export, site_active = split_census(gap.read_trace(root/f"traces/{arm}.sites.jsonl.gz"), arm, "seed-sites")
    require(exported["event"] == site_export["event"] and
            (active is None or active["event"] == site_active["event"]), "world/site boundary differs")
    if arm == "required":
        for kind in ("world", "sites"):
            require(experiment.digest(root/f"traces/{arm}.{kind}.jsonl.gz") ==
                    experiment.digest(root/f"input/prior-{kind}.jsonl.gz"), "saved required-light control changed")
    vetoes, capacity = gap.parent.audit_capacity(raw, "capacity")
    routing, _ = gap.guard.prior.neighbors.check_routing(iter(raw), gap.guard.prior.ROUTE)
    accounted, ordinary_guard = gap.guard.accounting_rows(raw, "guard", stop=STOP, retain_events=False, growth_vetoes=vetoes)
    worlds = [r for r in accounted if r["type"] == "world"]
    path = root/f"traces/{arm}.worlds.jsonl.gz"
    if create:
        gap.guard.write_accounting(path, worlds)
    require(worlds == list(gap.read_trace(path)), "derived census differs")
    world, _ = gap.panel.competition.world_analysis(path, "selective", 512, STOP, LATE, removal=exported["event"])
    records = {p["id"]: p for p in world["lineages"]}
    after = active["after"] if active else exported["after"]
    site_after = site_active["after"] if site_active else site_export["after"]
    extra = gap.panel.supplementary(worlds, {AT: {"after": after}}, records, gap.parent.CASES[0].baseline)
    full = gap.ledger.seed_ledger(worlds, {}, records)
    seeds = [{k: v for k, v in s.items() if k not in ("post_cutoff_blockers", "sole_spacing_22")} for s in full["seeds"]]
    checked = gap.check_sites(worlds, sites, seeds, records)
    outcomes = gap.outcomes(world, extra, seeds, worlds)
    if arm == "required":
        saved = experiment.read_json(root/"input/prior-results.json")["cases"]["gap"]
        require(world["lineages"] == saved["lineages"] and seeds == saved["seeds"] and outcomes == saved["outcomes"],
                "saved control accounting changed")
    world_by_tick, sites_by_tick = ({r["tick"]: r for r in group} for group in (worlds, sites))
    boundaries = [(exported, site_export)] + ([(active, site_active)] if active else [])
    receipts = seed_receipts(gap.read_trace(root/f"traces/{arm}.attempts.jsonl.gz"), world_by_tick, sites_by_tick, boundaries, arm)
    for born in receipts["germinations"]:
        candidates = [s for s in seeds if s["child_id"] == born["child"]]
        require(len(candidates) == 1 and all(candidates[0][k] == born[k] for k in
                ("parent", "generation", "column", "birth_tick")) and candidates[0]["end_tick"] == born["tick"], "birth receipt/ledger mismatch")
    require(len(receipts["germinations"]) == sum(s["outcome"] == "germinated" for s in seeds), "missing birth receipts")
    for child in outcomes["post_export_children"]:
        identity = child["lineage"]["id"]
        child["receipt"] = next(b for b in receipts["germinations"] if b["child"] == identity)
        child["own_seeds"] = gap.seed_audit.outcome_summary([s for s in seeds if s["parent"] == identity])
        child["offspring"] = gap.cohort(records, -1, {i for i, p in records.items() if p["parent"] == identity})
    frames = []
    for tick in FRAMES:
        stem = f"frames/{arm}.{tick}"
        value = experiment.read_json(root/(stem+".json"))
        pixels = (root/(stem+".rgb565")).read_bytes()
        sample = after if tick == AT else world_by_tick[tick]
        gap.panel.check_frame(value, sample, gap.parent.CASES[0].baseline, tick, pixels, [])
        check_rule(value, arm == "optional")
        require(value["night_capacity"] == sample["night_capacity"] and
                (value.get("gap_protocol"), value.get("gap_tick"), value.get("removed_id")) == (gap.NATIVE, AT, gap.REMOVED), "frame rule/export mismatch")
        require(value == experiment.read_json(root/(stem+".repeat.json")) and
                pixels == (root/(stem+".repeat.rgb565")).read_bytes(), "frame repeat differs")
        if arm == "required":
            require(value == experiment.read_json(root/f"input/prior-{tick}.json") and
                    pixels == (root/f"input/prior-{tick}.rgb565").read_bytes(), "saved control frame changed")
        frames.append({"id": f"{arm}.{tick}", "arm": arm, "tick": tick, "result": value,
                       "framebuffer": stem+".rgb565", "png": stem+".png"})
    print("Audited wet-germination arm:", arm, flush=True)
    return {"outcomes": outcomes, "export": exported, "activation": active, "site_export": site_export,
        "site_activation": site_active, "lineages": world["lineages"], "seeds": seeds, "receipts": receipts,
        "occupancy": occupancy(worlds, after), "site_exposure": gap.site_exposure(sites, {"after": site_after}, seeds),
        "site_checkpoints": checked, "daily": extra["daily"], "capacity": capacity, "ordinary_guard": ordinary_guard,
        "routing": routing, "checked_live_budgets": world["windows"]["whole"]["budget_checked_live_steps"]}, frames


def first_difference(root, cases):
    a, b = [list(gap.read_trace(root/f"traces/{arm}.worlds.jsonl.gz")) for arm in ARMS]
    require(cases["required"]["export"] == cases["optional"]["export"], "post-export states differ")
    for left, right in zip(a, b, strict=True):
        if left["tick"] <= AT:
            require(left == right, "pre-activation census differs")
        elif normalize(left) != normalize(right):
            births = [r for r in cases["optional"]["receipts"]["germinations"] if r["tick"] == right["tick"]]
            require(births and any(r["light"] < 80 and r["blockers"] == 0 for r in births), "first physical change is not a newly allowed germination")
            return {"tick": right["tick"], "control": left, "treatment": right, "births": births}
    return None


def analyze(root, create=False):
    cases, frames = {}, []
    for arm in ARMS:
        cases[arm], captured = analyze_case(root, arm, create)
        frames.extend(captured)
    require((root/f"frames/required.{AT}.rgb565").read_bytes() == (root/f"frames/optional.{AT}.rgb565").read_bytes(),
            "activation changed boundary pixels")
    prefixes = {}
    for kind in ("world", "sites"):
        pending, count = False, 0
        for a, b in zip_longest(*(gap.read_trace(root/f"traces/{arm}.{kind}.jsonl.gz") for arm in ARMS)):
            require(a is not None and b is not None and a == b, "raw prefix differs before activation")
            count += 1
            if pending:
                require(a["tick"] == AT and a["type"] in ("world", "seed-sites"), "missing shared post-export snapshot")
                break
            pending = a["type"] == "gap"
        require(pending, "prefix never reaches export")
        prefixes[kind] = count
    return {"settings": settings(), "cases": cases, "frames": frames, "prefix_rows": prefixes,
            "first_difference": first_difference(root, cases)}


def copies():
    result = {"input/prior-results.json": "results.json", "input/prior-CMakeCache.txt": "input/CMakeCache.txt"}
    result.update({f"models/{n}.tgm": f"models/{n}.tgm" for n in settings()["models"]})
    result.update({f"input/prior-{k}.jsonl.gz": f"traces/gap.{k}.jsonl.gz" for k in ("world", "sites")})
    result.update({f"input/prior-{t}.{e}": f"frames/gap.{t}.{e}" for t in FRAMES for e in ("json", "rgb565")})
    return result


def check_inputs(root):
    require(experiment.digest(root/"input/parent-manifest.json") == trace.PARENT_SHA and
            experiment.digest(root/"input/diagnostic-manifest.json") == DIAGNOSTIC_SHA and
            experiment.digest(root/"input/diagnostic-summary.json") == DIAGNOSTIC_PORTABLE_SHA, "changed parent evidence")
    parent = experiment.read_json(root/"input/parent-manifest.json")
    for dest, source in copies().items():
        require(experiment.digest(root/dest) == parent["artifacts"][source], "changed parent copy")
    diagnostic = experiment.read_json(root/"input/diagnostic-manifest.json")
    require(experiment.digest(root/"input/native-source.tar.gz") == diagnostic["artifacts"]["source.tar.gz"], "changed native reference")
    started = experiment.read_json(root/"started.json")
    require(started["settings"] == settings() and experiment.digest(root/"input/protocol.md") == started["sources"][PROTOCOL], "changed settings/protocol")
    for path, sha in started["frozen"].items():
        require(experiment.digest(root/path) == sha, "frozen input changed")
    old, new = [native.native_hashes(root/p) for p in ("input/native-source.tar.gz", "source.tar.gz")]
    allowed = {"src/garden_world.c", "src/garden_world.h", "sim/garden_inspect.c", "sim/garden_replay.c", "sim/garden_seed_attempts.c"}
    added = {"sim/garden_wet_germination.c", "sim/garden_wet_germination.h", "sim/garden_wet_germination_test.c"}
    require(old.keys() <= new.keys() and new.keys()-old.keys() == added and {n for n in old if old[n] != new[n]} <= allowed,
            "unrelated native source change")
    require(all(started["sources"].get(n) == sha for n, sha in new.items()), "native archive mismatch")
    old_cache, new_cache = [native.cache_settings(root/p) for p in ("input/prior-CMakeCache.txt", "input/CMakeCache.txt")]
    require(new_cache.pop("TOY_FACTORY_GARDEN_WET_GERMINATION:BOOL", None) == "ON" and old_cache == new_cache,
            "build changed beyond opt-in support")


def check_capture(root):
    check_inputs(root)
    capture = experiment.read_json(root/"capture.json")
    require(capture["settings"] == settings() and [(c["artifact"], c["command"]) for c in capture["calls"]] == commands(), "wrong call inventory")
    for path in capture["artifacts"]:
        gap.gallery.artifact(root, capture, path)
    return capture


def verify(root):
    manifest = experiment.read_json(root/"manifest.json")
    require(manifest["rule"] == RULE and manifest["status"] == "complete", "wrong/incomplete bundle")
    require(set(manifest["artifacts"]) == {str(p.relative_to(root)) for p in root.rglob("*")
            if p.is_file() and p != root/"manifest.json"}, "extra/missing artifact")
    for name in manifest["artifacts"]:
        gap.gallery.artifact(root, manifest, name)
    capture = check_capture(root)
    require(experiment.read_json(root/"timings.json")["calls"] == capture["calls"], "timing inventory differs")
    result = analyze(root)
    require(result == experiment.read_json(root/"results.json"), "saved analysis differs")
    return result


def collect(baseline, diagnostic, build, output):
    require(not output.exists() and output.is_relative_to(experiment.ROOT/"artifacts") and
            not any(output.is_relative_to(p) for p in (baseline, diagnostic, build)), "choose fresh independent output")
    gap.parent.shadow.check_frozen(baseline, trace.PARENT_SHA)
    gap.parent.shadow.check_frozen(diagnostic, DIAGNOSTIC_SHA)
    require(experiment.digest(experiment.ROOT/DIAGNOSTIC_PORTABLE) == DIAGNOSTIC_PORTABLE_SHA, "changed diagnostic")
    gap.verify(baseline)
    trace.verify(diagnostic)
    sources = experiment.source_files()
    output.mkdir(parents=True)
    experiment.snapshot_sources(output, sources)
    for name in ("input", "models", "bin", "traces", "frames"):
        (output/name).mkdir()
    for dest, source in copies().items():
        shutil.copy2(baseline/source, output/dest)
    for source, dest in ((baseline/"manifest.json", "input/parent-manifest.json"),
            (diagnostic/"manifest.json", "input/diagnostic-manifest.json"), (diagnostic/"source.tar.gz", "input/native-source.tar.gz"),
            (experiment.ROOT/DIAGNOSTIC_PORTABLE, "input/diagnostic-summary.json"), (experiment.ROOT/PROTOCOL, "input/protocol.md")):
        shutil.copy2(source, output/dest)
    for name in ("CMakeCache.txt", "build.ninja"):
        shutil.copy2(build/name, output/"input"/name)
    for name in ("inspect", "replay", "seed-attempts"):
        shutil.copy2(build/("toy-factory-garden-"+name), output/"bin"/name)
    frozen = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
    experiment.write_json(output/"started.json", {"settings": settings(), "sources": sources, "frozen": frozen})
    begin, timings = time.monotonic(), []
    try:
        check_inputs(output)
        for target, cmd in commands():
            start = time.monotonic()
            if target.endswith(".gz"):
                with tempfile.TemporaryDirectory(prefix="garden-wet-germination-") as temporary:
                    raw = Path(temporary)/"trace.jsonl"
                    try:
                        experiment.command_run(cmd, raw, output, 180)
                    finally:
                        if raw.exists():
                            experiment.compress(raw, output/target)
            else:
                experiment.command_run(cmd, output/target, output, 180)
            timings.append({"artifact": target, "command": cmd, "seconds": time.monotonic()-start})
            if target == "traces/required.world.jsonl.gz":
                require(experiment.digest(output/target) == experiment.digest(output/"input/prior-world.jsonl.gz"), "control drift; stop before treatment")
            print(f"Captured {len(timings)}/28: {target}", flush=True)
        require(experiment.source_files() == sources, "sources changed during capture")
        artifacts = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
        experiment.write_json(output/"capture.json", {"settings": settings(), "calls": timings, "artifacts": artifacts,
                                                   "capture_seconds": time.monotonic()-begin})
        start = time.monotonic()
        result = analyze(output, True)
        require(result == analyze(output), "repeated analysis differs")
        for f in result["frames"]:
            gap.gallery.write_png(output/f["png"], 240, 240, gap.gallery.rgb565be_to_rgb888((output/f["framebuffer"]).read_bytes()))
        gap.gallery.contact_sheet(output, [[f for f in result["frames"] if f["arm"] == arm] for arm in ARMS])
        check_capture(output)
        require(experiment.source_files() == sources, "sources changed during analysis")
        experiment.write_json(output/"results.json", result)
        experiment.write_json(output/"timings.json", {"calls": timings, "analysis_and_repeat_seconds": time.monotonic()-start})
        artifacts = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
        experiment.write_json(output/"manifest.json", {"rule": RULE, "status": "complete", "artifacts": artifacts,
            "native_calls": len(timings), "artifact_bytes": sum((output/n).stat().st_size for n in artifacts)})
    except BaseException as error:
        experiment.write_json(output/"failure.json", {"error": str(error), "completed_calls": timings})
        raise
    print("Wet germination complete: 28 fixed calls, exact repeats and repeated analysis verified", flush=True)


def export(root, prefix, check=False):
    require(not prefix.is_relative_to(root), "export outside frozen evidence")
    result = {**verify(root), "manifest_sha256": experiment.digest(root/"manifest.json"),
              "full_results_sha256": experiment.digest(root/"results.json"), "exporter_sha256": experiment.digest(Path(__file__)),
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
    require(experiment.read_json(target) == result and all(experiment.digest(p) == experiment.digest(q) for p, q in images.items()), "portable evidence differs")
    print("Verified portable wet-germination evidence and all eight native images", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT/"artifacts/garden-renewal-controlled-gap-v1")
    parser.add_argument("--diagnostic", type=Path, default=experiment.ROOT/"artifacts/garden-renewal-germination-trace-v1")
    parser.add_argument("--build", type=Path, default=experiment.ROOT/"artifacts/build-host-wet-germination-docker")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--export", type=Path)
    parser.add_argument("--check-export", type=Path)
    args = parser.parse_args()
    require(not (args.export and args.check_export) and (args.verify or not (args.export or args.check_export)), "export requires verify")
    if args.export or args.check_export:
        export(args.output.resolve(), (args.export or args.check_export).resolve(), bool(args.check_export))
    elif args.verify:
        verify(args.output.resolve())
    else:
        collect(args.baseline.resolve(), args.diagnostic.resolve(), args.build.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
