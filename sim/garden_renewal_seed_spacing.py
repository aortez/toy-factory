#!/usr/bin/env python3
"""Frozen three-versus-two-column establishment A/B; rotating purchases in both."""
from __future__ import annotations

import argparse
from collections import Counter
from itertools import zip_longest
from pathlib import Path
from garden_plant_slots import plant_capacity
import shutil
import tempfile
import time

import garden_renewal_seed_order as prior

gap, experiment, require, native = prior.gap, prior.experiment, prior.require, prior.native
RULE, NATIVE = "garden-renewal-seed-spacing-v1", "post-noon-spacing-two-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-seed-spacing-protocol.md"
BASELINE_SHA = "1910c4d9b739692e7fc1bb2d7433cce866603237a32b471709f0b036614aea61"
PORTABLE = "benchmarks/garden-longevity/renewal-seed-order-summary.json"
PORTABLE_SHA = "3b8d9554080e014eeb1f82430b33791919ee27846b81896ecdac46af02db0cea"
AFTER, STOP, LATE, DAY = prior.AFTER, prior.STOP, prior.LATE, gap.panel.DAY
ARMS, FRAMES = ("control", "two"), (AFTER, AFTER+DAY, STOP)


def settings():
    return {"rule": RULE, "native_rule": NATIVE, "arms": list(ARMS), "after_inclusive": AFTER,
            "minimum_before": 3, "minimum_after": 2, "first_ecology_tick": AFTER+15,
            "stop": STOP, "late": LATE, "frames": list(FRAMES),
            "models": prior.settings()["models"], "routing": prior.settings()["routing"],
            "parent_manifest_sha256": BASELINE_SHA, "parent_portable_sha256": PORTABLE_SHA,
            "budget": {"native_calls": 20, "training_calls": 0},
            "role": "selected saved-world establishment diagnostic; not sustained-renewal qualification"}


def commands():
    calls = []
    for arm in ARMS:
        base = ["models/r2-n.tgm", "rainfed-crowded", experiment.NIGHT_POLICY, "0x"+gap.SEED,
                "--leaf-policy", "selective", "--focal-model", "models/r2-w.tgm", "--focal-founder", "5",
                "--gap-at", str(gap.AT), "--gap-lineage", str(gap.REMOVED),
                "--wet-germination-after", str(gap.AT), "--dawn-finish", "reserve",
                "--seed-order", "rotating"]
        if arm == "two":
            base += ["--seed-spacing", "2"]
        for kind, flag in (("world", "--ecology"), ("sites", "--seed-sites")):
            for suffix in ("", ".repeat"):
                calls.append((f"traces/{arm}.{kind}{suffix}.jsonl.gz",
                              ["bin/inspect", *base, flag, "--ticks", str(STOP)]))
        for tick in FRAMES:
            for suffix in ("", ".repeat"):
                stem = f"frames/{arm}.{tick}{suffix}"
                calls.append((stem+".json", ["bin/replay", *base, "--ticks", str(tick),
                                             "--framebuffer", stem+".rgb565"]))
    return calls


def minimum(row, arm):
    require(arm in ARMS and type(row["tick"]) is int and row["tick"] >= 0, "invalid spacing scope")
    if arm == "control":
        require("seed_spacing" not in row, "unexpected control spacing override")
        return 3
    value = 2 if row["tick"] > AFTER else 3
    require(row.get("seed_spacing") == {"rule": NATIVE, "after": AFTER, "minimum": value},
            "missing/incorrect spacing metadata")
    return value


def check_prefix(control, candidate):
    for count, (a, b) in enumerate(zip_longest(control, candidate), 1):
        require(a is not None and b is not None, "truncated prefix")
        if a["type"] in ("world", "seed-sites"):
            minimum(a, "control")
            minimum(b, "two")
        require(a == {k: v for k, v in b.items() if k != "seed_spacing"}, "physical prefix changed")
        if a["type"] in ("world", "seed-sites") and a["tick"] == AFTER:
            return count
    raise RuntimeError("prefix did not reach boundary")


def root_exposure(previous, row, identity):
    """Uptake uses pre-growth roots. Post-step dryness does not attribute extraction."""
    before = previous["plants"]
    position = next((i for i, p in enumerate(before) if p["id"] == identity), None)
    if position is None or before[position]["dead"]:
        return {"uptake_steps": 0}
    cells = {tuple(c[:2]) for c in before[position]["root_cells"]}
    others = [(i, p, cells & {tuple(c[:2]) for c in p["root_cells"]})
              for i, p in enumerate(before) if i != position and not p["dead"]]
    shared = set().union(*(overlap for _, _, overlap in others))
    current = next(p for p in row["plants"] if p["id"] == identity)
    water = {tuple(c[:2]): c[3] for c in current["root_cells"]}
    require(cells <= water.keys(), "living roots disappeared before uptake audit")
    return {"uptake_steps": 1, "array_rank_"+str(position): 1,
            "shared_root_steps": int(bool(shared)), "shared_cell_samples": len(shared),
            "shared_dry_poststep_samples": sum(water[c] == 0 for c in shared),
            "earlier_competitor_samples": sum(i < position and bool(overlap) for i, _, overlap in others)}


def resource_followup(worlds, records):
    boundary = next(w for w in worlds if w["tick"] == AFTER)
    incumbents = {p["id"] for p in boundary["plants"] if not p["dead"]}
    selected = incumbents | {i for i, p in records.items() if p["birth_tick"] > AFTER}
    data = {str(i): {"lineage": records[i], "incumbent": i in incumbents,
        "boundary_state": next((p for p in boundary["plants"] if p["id"] == i), None),
        "budget": Counter(), "first_day_budget": Counter(), "live_steps": 0, "terminal_steps": 0,
        "stress_peak": 0, "energy_shortage_steps": 0, "water_shortage_steps": 0,
        "first_shortage": None, "last_live": None, "first_day_last_live": None,
        "roots": Counter(), "daily": []} for i in sorted(selected)}
    for old, row in zip(worlds, worlds[1:]):
        if row["tick"] <= AFTER:
            continue
        previous = {p["id"]: p for p in old["plants"]}
        for p in row["plants"]:
            if p["id"] not in selected:
                continue
            entry, earlier, tick = data[str(p["id"])], previous.get(p["id"]), row["tick"]
            if p["dead"]:
                entry["terminal_steps"] += earlier is not None and not earlier["dead"]
                continue
            budget = prior.access.resources.budget(earlier, p, tick)
            entry["budget"].update(budget)
            entry["live_steps"] += 1
            entry["stress_peak"] = max(entry["stress_peak"], p["stress"])
            entry["energy_shortage_steps"] += bool(p["flags"] & 2)
            entry["water_shortage_steps"] += bool(p["flags"] & 4)
            point = {"tick": tick, "phase": row["sun_phase"], **p}
            entry["last_live"] = point
            if p["flags"] & 6 and entry["first_shortage"] is None:
                entry["first_shortage"] = point
            if records[p["id"]]["birth_tick"] > AFTER and tick <= records[p["id"]]["birth_tick"]+DAY:
                entry["first_day_budget"].update(budget)
                entry["first_day_last_live"] = point
            entry["roots"].update(root_exposure(old, row, p["id"]))
            if tick % DAY == 0:
                entry["daily"].append({k: point[k] for k in
                    ("tick", "energy", "water", "nodes", "roots", "leaves", "stress", "flags", "tips")})
    for entry in data.values():
        identity = entry["lineage"]["id"]
        entry["offspring"] = gap.cohort(records, -1, {i for i, p in records.items() if p["parent"] == identity})
    return data


def site_followup(sites, arm):
    values = {name: Counter() for name in ("after", "late")}
    first_open = None
    for row in sites:
        spacing = minimum(row, arm)
        gap.panel.competition.spatial_snapshot(row, minimum_spacing=spacing)
        wet = row.get("germination_rule") == "wet-germination-v1"
        for mask, moisture, light in row["sites"]:
            require(0 <= moisture <= 255 and 0 <= light <= 255 and
                    bool(mask & 2) == (moisture < 12) and bool(mask & 4) == (not wet and light < 80) and
                    bool(mask & 8) == (len(row["plants"]) == plant_capacity(row)) and bool(mask & 16) == (row["nodes"]+4 > 512),
                    "site resource/allocation gates disagree")
        if row["tick"] <= AFTER:
            continue
        masks = [s[0] for s in row["sites"]]
        sample = {"checkpoints": 1, "spacing_free_column_samples": sum(not m & 32 for m in masks),
                  "open_column_samples": sum(m == 0 for m in masks), "plant_full": int(len(row["plants"]) == plant_capacity(row)),
                  "node_full_for_seedling": int(row["nodes"]+4 > 512),
                  "all_spacing_blocked": int(all(m & 32 for m in masks))}
        values["after"].update(sample)
        if row["tick"] > LATE:
            values["late"].update(sample)
        if first_open is None and any(m == 0 for m in masks):
            first_open = row
    return {"windows": values, "first_poststep_open": first_open,
            "first_after": next(r for r in sites if r["tick"] > AFTER), "last": sites[-1]}


def analyze_case(root, arm, create=False):
    for kind in ("world", "sites"):
        path = root/f"traces/{arm}.{kind}.jsonl.gz"
        require(experiment.digest(path) == experiment.digest(root/f"traces/{arm}.{kind}.repeat.jsonl.gz"), "trace repeat differs")
    split = prior.parent.parent.parent.split_census
    raw, exported, active = split(gap.read_trace(root/f"traces/{arm}.world.jsonl.gz"), "optional")
    sites, site_export, site_active = split(gap.read_trace(root/f"traces/{arm}.sites.jsonl.gz"), "optional", "seed-sites")
    require(exported["event"] == site_export["event"] and active["event"] == site_active["event"], "boundary disagreement")
    handoff = {}
    vetoes, receipts = prior.parent.check_refusals(raw, "reserve", audit=handoff)
    capacity_vetoes, capacity = gap.parent.audit_capacity(raw, "capacity")
    routing, _ = gap.guard.prior.neighbors.check_routing(iter(raw), gap.guard.prior.ROUTE)
    accounted, ordinary = gap.guard.accounting_rows(raw, "guard", stop=STOP, retain_events=False,
        growth_vetoes=vetoes | capacity_vetoes)
    worlds = [r for r in accounted if r["type"] == "world"]
    for row in worlds+sites:
        minimum(row, arm)
        prior.check_order(row, "rotating")
    path = root/f"traces/{arm}.worlds.jsonl.gz"
    prior.parent.parent.derived_census(path, worlds, create)
    world, _ = gap.panel.competition.world_analysis(path, "selective", 512, STOP, LATE, removal=exported["event"])
    records = {p["id"]: p for p in world["lineages"]}
    extra = gap.panel.supplementary(worlds, {gap.AT: {"after": active["after"]}}, records, gap.parent.CASES[0].baseline)
    ledger = gap.ledger.seed_ledger(worlds, {}, records, spacing_at=lambda r: minimum(r, arm),
                                  reproduction_order=lambda r: prior.visit_view(r, "rotating")["plants"])
    seeds = [{k: v for k, v in s.items() if k not in ("post_cutoff_blockers", "sole_spacing_22")} for s in ledger["seeds"]]
    checked = gap.check_sites(worlds, sites, seeds, records, spacing_at=lambda r: minimum(r, arm))
    require(all(w.get("seed_spacing") == s.get("seed_spacing") and w["seed_order"] == s["seed_order"] and
                w["dawn_finish"] == s["dawn_finish"] for w, s in zip(worlds, sites, strict=True)), "site metadata differs")
    outcomes = gap.outcomes(world, extra, seeds, worlds)
    resources = resource_followup(worlds, records)
    frames, by_tick = [], {w["tick"]: w for w in worlds}
    for tick in FRAMES:
        stem = f"frames/{arm}.{tick}"
        value = experiment.read_json(root/(stem+".json"))
        pixels = (root/(stem+".rgb565")).read_bytes()
        sample = by_tick[tick]
        gap.panel.check_frame(value, sample, gap.parent.CASES[0].baseline, tick, pixels, [])
        minimum(value, arm)
        prior.check_order(value, "rotating", len(sample["plants"]))
        require(value["dawn_finish"] == sample["dawn_finish"] and value["night_capacity"] == sample["night_capacity"], "frame receipts differ")
        prior.parent.parent.parent.check_rule(value, True)
        require((value.get("gap_protocol"), value.get("gap_tick"), value.get("removed_id")) ==
                (gap.NATIVE, gap.AT, gap.REMOVED), "frame export differs")
        require(value == experiment.read_json(root/(stem+".repeat.json")) and pixels == (root/(stem+".repeat.rgb565")).read_bytes(), "frame repeat differs")
        frames.append({"id": f"{arm}.{tick}", "arm": arm, "tick": tick, "result": value,
                       "framebuffer": stem+".rgb565", "png": stem+".png"})
    result = {"outcomes": outcomes, "lineages": world["lineages"], "seeds": seeds,
        "handoff": handoff, "refusals": receipts, "ordinary_guard": ordinary, "capacity": capacity,
        "routing": routing, "export": exported, "activation": active, "daily": extra["daily"],
        "checked_live_budgets": world["windows"]["whole"]["budget_checked_live_steps"],
        "terminal_steps_not_reconstructed": world["windows"]["whole"]["terminal_steps"],
        "site_checkpoints": checked, "sites": site_followup(sites, arm), "resources": resources,
        "new_cohort": gap.cohort(records, AFTER),
        "occupancy": prior.parent.parent.parent.occupancy(worlds, active["after"])}
    print("Audited spacing arm:", arm, flush=True)
    return result, frames, worlds


def historical_files():
    return [*(f"traces/control.{kind}.jsonl.gz" for kind in ("world", "sites")),
            *(f"frames/control.{t}.{ext}" for t in (AFTER, STOP) for ext in ("json", "rgb565"))]


def check_historical(root):
    for name in historical_files():
        require(experiment.digest(root/name) == experiment.digest(root/"input/history"/name), "historical control drift: "+name)
        repeat = name.replace(".jsonl.gz", ".repeat.jsonl.gz") if name.endswith(".gz") else (
            name.rsplit(".", 1)[0]+".repeat."+name.rsplit(".", 1)[1])
        require(experiment.digest(root/repeat) == experiment.digest(root/name), "historical repeat drift")


def canonical_seed(record):
    """Witness sets are unordered; seed order, ages, masks and identities are not."""
    result = dict(record)
    for field in ("first_mature", "last_snapshot"):
        point = record[field]
        if point is not None:
            result[field] = {**point, "spacing_occupants": sorted(point["spacing_occupants"], key=lambda p: p["id"])}
    return result


def analyze(root, create=False):
    check_historical(root)
    prefixes = {kind: check_prefix(*(gap.read_trace(root/f"traces/{a}.{kind}.jsonl.gz") for a in ARMS)) for kind in ("world", "sites")}
    cases, frames, worlds = {}, [], {}
    for arm in ARMS:
        cases[arm], images, worlds[arm] = analyze_case(root, arm, create)
        frames.extend(images)
    old = experiment.read_json(root/"input/parent-results.json")["cases"]["rotating"]
    for key in ("lineages", "refusals", "ordinary_guard", "capacity", "routing", "daily", "occupancy", "checked_live_budgets"):
        require(cases["control"][key] == old[key], "historical derived drift: "+key)
    require([canonical_seed(s) for s in cases["control"]["seeds"]] ==
            [canonical_seed(s) for s in old["seeds"]], "historical seed lifetimes/masks/witnesses differ")
    require((root/f"frames/control.{AFTER}.rgb565").read_bytes() == (root/f"frames/two.{AFTER}.rgb565").read_bytes(), "boundary pixels differ")
    divergent = next(({"tick": a["tick"], "control": a, "two": b}
                      for a, b in zip(worlds["control"], worlds["two"], strict=True) if a["hash"] != b["hash"]), None)
    require(divergent is None or divergent["tick"] > AFTER, "early physical divergence")
    return {"settings": settings(), "prefixes": prefixes, "first_hash_divergence": divergent, "cases": cases, "frames": frames}


def copies():
    return {"input/parent-results.json": "results.json", "input/prior-cache.txt": "input/CMakeCache.txt",
            "input/native-source.tar.gz": "source.tar.gz",
            **{f"models/{n}.tgm": f"models/{n}.tgm" for n in settings()["models"]},
            **{f"input/history/{n}": n.replace("control.", "rotating.") for n in historical_files()}}


def check_inputs(root):
    require(experiment.digest(root/"input/parent-manifest.json") == BASELINE_SHA and
            experiment.digest(root/"input/parent-summary.json") == PORTABLE_SHA, "changed parent evidence")
    manifest = experiment.read_json(root/"input/parent-manifest.json")
    for dest, source in copies().items():
        require(experiment.digest(root/dest) == manifest["artifacts"][source], "changed parent copy")
    started = experiment.read_json(root/"started.json")
    require(started["settings"] == settings() and experiment.digest(root/"input/protocol.md") ==
            started["sources"][PROTOCOL], "changed protocol/settings")
    for name, sha in started["frozen"].items():
        require(experiment.digest(root/name) == sha, "frozen input changed")
    old, new = [native.native_hashes(root/p) for p in ("input/native-source.tar.gz", "source.tar.gz")]
    added = {"src/garden_seed_spacing.h", "sim/garden_seed_spacing.c", "sim/garden_seed_spacing_test.c"}
    changed = {"src/garden_world.c", "src/garden_world.h", "sim/garden_inspect.c", "sim/garden_replay.c"}
    require(new.keys()-old.keys() == added and not old.keys()-new.keys() and
            {n for n in old if old[n] != new[n]} <= changed, "unrelated native changes")
    require(all(started["sources"].get(n) == sha for n, sha in new.items()), "native archive mismatch")
    a, b = [native.cache_settings(root/p) for p in ("input/prior-cache.txt", "input/CMakeCache.txt")]
    require(b.pop("TOY_FACTORY_GARDEN_SEED_SPACING:BOOL", None) == "ON" and a == b, "wrong build configuration")


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
    """Analysis-only recovery; never calls native binaries or replaces observations."""
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
    require(experiment.digest(experiment.ROOT/PORTABLE) == PORTABLE_SHA, "changed portable input")
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
    calls, begin, target, command = [], time.monotonic(), None, None
    try:
        check_inputs(output)
        for target, command in commands():
            start = time.monotonic()
            if target.endswith(".gz"):
                with tempfile.TemporaryDirectory(prefix="garden-seed-spacing-") as temporary:
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
                print("Historical rotating control traces and frames match exactly", flush=True)
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
    require(set(manifest["artifacts"]) == {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and p != root/"manifest.json"}, "extra/missing artifact")
    for name in manifest["artifacts"]:
        gap.gallery.artifact(root, manifest, name)
    capture = check_capture(root)
    require(experiment.read_json(root/"timings.json")["calls"] == capture["calls"] and
            experiment.read_json(root/"analysis-sources.json") == analysis_sources(), "analysis provenance changed")
    require(all(experiment.digest(experiment.ROOT/n) == sha for n, sha in native.native_hashes(root/"source.tar.gz").items()), "native source changed")
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
    require(experiment.read_json(target) == result and all(experiment.digest(p) == experiment.digest(q) for p, q in images.items()), "portable evidence differs")
    print("Verified portable spacing comparison and six native frames", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT/"artifacts/garden-renewal-seed-order-v1")
    parser.add_argument("--build", type=Path, default=experiment.ROOT/"artifacts/build-host-seed-spacing-docker")
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
