#!/usr/bin/env python3
"""One frozen post-noon purchase-order A/B; no changes to costs or capacity."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from itertools import zip_longest
from pathlib import Path
from garden_plant_slots import plant_capacity
import shutil
import tempfile
import time

import garden_renewal_reproduction_access as access

parent = access.parent
gap, experiment, require, native = parent.gap, parent.experiment, parent.require, parent.native
RULE, NATIVE = "garden-renewal-seed-order-v1", "maintenance-seed-rotation-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-seed-order-protocol.md"
BASELINE_SHA, PORTABLE, PORTABLE_SHA = access.BASELINE_SHA, access.PORTABLE, access.PORTABLE_SHA
AUDIT = "benchmarks/garden-longevity/renewal-reproduction-access-summary.json"
AUDIT_SHA = "6a64a9792486ab03267b0d077514c84978e58b062743624625291830cf86fae3"
AFTER, STOP, LATE, ID = parent.NOON, parent.STOP, parent.LATE, parent.ID
ARMS, FRAMES = ("fixed", "rotating"), (AFTER, STOP)


def settings():
    return {**parent.settings(), "rule": RULE, "native_rule": NATIVE, "arms": list(ARMS),
            "after_inclusive": AFTER, "first_rotation_tick": AFTER+60,
            "rotation": "((tick-69120)//60)%current_plant_count on maintenance ticks only",
            "frames": list(FRAMES), "budget": {"native_calls": 16, "training_calls": 0},
            "parent_manifest_sha256": BASELINE_SHA, "access_audit_sha256": AUDIT_SHA}


def commands():
    calls = []
    for arm in ARMS:
        base = ["models/r2-n.tgm", "rainfed-crowded", experiment.NIGHT_POLICY, "0x"+gap.SEED,
                "--leaf-policy", "selective", "--focal-model", "models/r2-w.tgm", "--focal-founder", "5",
                "--gap-at", str(gap.AT), "--gap-lineage", str(gap.REMOVED),
                "--wet-germination-after", str(gap.AT), "--dawn-finish", "reserve"]
        if arm == "rotating":
            base += ["--seed-order", "rotating"]
        for kind, flag in (("world", "--ecology"), ("sites", "--seed-sites")):
            for repeat in ("", ".repeat"):
                calls.append((f"traces/{arm}.{kind}{repeat}.jsonl.gz",
                              ["bin/inspect", *base, flag, "--ticks", str(STOP)]))
        for tick in FRAMES:
            for repeat in ("", ".repeat"):
                stem = f"frames/{arm}.{tick}{repeat}"
                calls.append((stem+".json", ["bin/replay", *base, "--ticks", str(tick),
                                             "--framebuffer", stem+".rgb565"]))
    return calls


def start_index(tick, count, capacity=8):
    require(type(capacity) is int and capacity in (8, 16), "invalid traversal capacity")
    require(type(tick) is int and tick >= 0 and type(count) is int and 0 <= count <= capacity, "invalid traversal")
    return ((tick-AFTER)//60)%count if tick > AFTER and tick%60 == 0 and count else 0


def check_order(row, arm, count=None):
    require(arm in ARMS, "unknown arm")
    if arm == "fixed":
        require("seed_order" not in row, "fixed order unexpectedly enabled")
        return 0
    count = len(row["plants"]) if count is None else count
    first = start_index(row["tick"], count, plant_capacity(row))
    require(row.get("seed_order") == {"rule": NATIVE, "after": AFTER, "start": first},
            "missing/incorrect rotation metadata")
    return first


def visit_view(row, arm):
    """Read-only projection for order-sensitive audits, never a stored census.

    Authoritative arrays and every census hash remain in their original order.
    Only the seed ledger/access checker consumes this traversal-order view.
    """
    first = check_order(row, arm)
    return {**row, "plants": row["plants"][first:]+row["plants"][:first]}


def check_prefix(fixed, rotated):
    for count, (a, b) in enumerate(zip_longest(fixed, rotated), 1):
        require(a is not None and b is not None and
                a == {k: v for k, v in b.items() if k != "seed_order"}, "physical prefix changed before noon")
        if a["type"] in ("world", "seed-sites") and a["tick"] == AFTER:
            return count
    raise RuntimeError("prefix never reached noon")


def access_analysis(worlds, records, seeds, arm):
    parents = {str(i): {"lineage": p, "windows": {w: access.empty_access() for w in access.WINDOWS}}
               for i, p in records.items()}
    bank_stats = {w: Counter() for w in access.WINDOWS}
    phases = {w: Counter() for w in access.WINDOWS}
    focal, releases, checked, terminals = [], [], 0, 0
    births, endings = defaultdict(list), defaultdict(list)
    for seed in seeds:
        births[seed["birth_tick"]].append(seed)
        if seed["end_tick"] is not None:
            endings[seed["end_tick"]].append(seed)
    for previous, row in zip(worlds, worlds[1:]):
        bank = access.bank_step(previous, visit_view(row, arm))
        tick = row["tick"]
        require(bank["buyers"] == [s["parent"] for s in births[tick]] and
                bank["expired"] == sum(s["outcome"] == "expired" for s in endings[tick]) and
                bank["germinated"] == sum(s["outcome"] == "germinated" for s in endings[tick]), "ledger/access mismatch")
        old = {p["id"]: p for p in previous["plants"]}
        earlier, turns = [], {}
        for rank, plant in enumerate(visit_view(row, arm)["plants"]):
            identity = plant["id"]
            if plant["dead"]:
                terminals += identity in old and not old[identity]["dead"]
                require(identity not in bank["events"], "dead plant seed expense")
                continue
            turn = access.plant_turn(old.get(identity), plant, row, bank, rank, earlier)
            checked += 1
            turns[str(identity)] = {k: turn[k] for k in
                ("category", "failures", "bank_at_turn", "energy_before", "water_before", "required", "maturity")}
            for window in access.windows(tick):
                access.observe(parents[str(identity)]["windows"][window], turn)
            if identity == ID and tick%60 == 0:
                focal.append({k: v for k, v in turn.items() if k != "budget"} |
                    {"array_index": next(i for i, p in enumerate(row["plants"]) if p["id"] == identity)})
            if turn["category"] == "purchase":
                earlier.append(identity)
        require(earlier == bank["buyers"] and bank["entry"]+len(earlier) == bank["final"], "wrong bank exit")
        for window in access.windows(tick):
            bank_stats[window].update(steps=1, maintenance_steps=int(tick%60 == 0),
                full_at_entry=int(bank["entry"] == 8), full_at_exit=int(bank["final"] == 8),
                purchases=bank["purchases"], expired=bank["expired"], germinated=bank["germinated"],
                steps_with_release=int(bank["expired"]+bank["germinated"] > 0),
                release_refilled_same_step=int(bank["expired"]+bank["germinated"] > 0 and bank["final"] == 8))
            if bank["purchases"]:
                phases[window][str(bank["phase"])] += bank["purchases"]
        if bank["purchases"] or bank["expired"] or bank["germinated"]:
            releases.append({k: v for k, v in bank.items() if k != "events"} | {"parent_turns": turns,
                "removed": [{"parent": s["parent"], "birth_tick": s["birth_tick"], "outcome": s["outcome"]}
                            for s in endings[tick]]})
    for entry in parents.values():
        whole = entry["windows"]["whole"]
        purchases = entry["lineage"]["seeds_created"]
        require(whole["categories"]["purchase"] == purchases and whole["budget"]["energy_seeds"] == 48*purchases and
                whole["budget"]["water_seeds"] == 24*purchases, "parent seed debit mismatch")
        for s in entry["windows"].values():
            require(sum(s["categories"].values()) == s["maintenance_steps"], "nonpartitioned categories")
    selected, support = gap.seed_audit.focused_observations(worlds, seeds, records, ID, AFTER)
    for s in selected:
        s["observations"]["after_noon"] = s["observations"].pop("since_refusal")
    return {"parents": parents, "bank": bank_stats, "purchase_phases": phases, "releases_and_purchases": releases,
            "target_maintenance_steps": focal, "target_seeds": selected, "target_dispersal_support": support,
            "checked_live_budgets": checked, "terminal_steps_not_reconstructed": terminals}


def analyze_case(root, arm, create=False):
    for kind in ("world", "sites"):
        path = root/f"traces/{arm}.{kind}.jsonl.gz"
        require(experiment.digest(path) == experiment.digest(root/f"traces/{arm}.{kind}.repeat.jsonl.gz"), "trace repeat differs")
    raw, exported, active = parent.parent.parent.split_census(gap.read_trace(root/f"traces/{arm}.world.jsonl.gz"), "optional")
    sites, site_export, site_active = parent.parent.parent.split_census(
        gap.read_trace(root/f"traces/{arm}.sites.jsonl.gz"), "optional", "seed-sites")
    require(exported["event"] == site_export["event"] and active["event"] == site_active["event"], "boundary disagreement")
    handoff = {}
    vetoes, receipts = parent.check_refusals(raw, "reserve", audit=handoff)
    capacity_vetoes, capacity = gap.parent.audit_capacity(raw, "capacity")
    routing, _ = gap.guard.prior.neighbors.check_routing(iter(raw), gap.guard.prior.ROUTE)
    accounted, ordinary = gap.guard.accounting_rows(raw, "guard", stop=STOP, retain_events=False,
        growth_vetoes=vetoes | capacity_vetoes)
    worlds = [r for r in accounted if r["type"] == "world"]
    for row in worlds+sites:
        check_order(row, arm)
    path = root/f"traces/{arm}.worlds.jsonl.gz"
    parent.parent.derived_census(path, worlds, create)
    world, _ = gap.panel.competition.world_analysis(path, "selective", 512, STOP, LATE, removal=exported["event"])
    records = {p["id"]: p for p in world["lineages"]}
    extra = gap.panel.supplementary(worlds, {gap.AT: {"after": active["after"]}}, records, gap.parent.CASES[0].baseline)
    ledger = gap.ledger.seed_ledger((visit_view(w, arm) for w in worlds), {}, records)
    seeds = [{k: v for k, v in s.items() if k not in ("post_cutoff_blockers", "sole_spacing_22")} for s in ledger["seeds"]]
    checked = gap.check_sites(worlds, sites, seeds, records)
    require(all(w.get("seed_order") == s.get("seed_order") and w.get("dawn_finish") == s.get("dawn_finish")
                for w, s in zip(worlds, sites, strict=True)), "site rule disagreement")
    outcomes = gap.outcomes(world, extra, seeds, worlds)
    for child in outcomes["post_export_children"]:
        i = child["lineage"]["id"]
        child["own_seeds"] = gap.seed_audit.outcome_summary([s for s in seeds if s["parent"] == i])
        child["offspring"] = gap.cohort(records, -1, {j for j, p in records.items() if p["parent"] == i})
    detail = access_analysis(worlds, records, seeds, arm)
    require(detail["checked_live_budgets"] == world["windows"]["whole"]["budget_checked_live_steps"], "budget coverage mismatch")
    budget = parent.parent.budget
    histories, count = budget.failures.histories(budget.focal_rows(worlds, {ID: records[ID]}, {}), {}, {ID: records[ID]}, STOP)
    history = histories[ID]
    totals = budget.failures.budget_sum(history)
    last = next(e["state"] for e in reversed(history) if e["budget"] is not None)
    budget.failures.balance(budget.ORIGIN, last, totals)
    require(totals == detail["parents"][str(ID)]["windows"]["whole"]["budget"], "focal accounting differs")
    frames, by_tick = [], {w["tick"]: w for w in worlds}
    for tick in FRAMES:
        stem = f"frames/{arm}.{tick}"
        value = experiment.read_json(root/(stem+".json"))
        pixels = (root/(stem+".rgb565")).read_bytes()
        sample = by_tick[tick]
        gap.panel.check_frame(value, sample, gap.parent.CASES[0].baseline, tick, pixels, [])
        check_order({**value, "tick": tick}, arm, len(sample["plants"]))
        require(value.get("dawn_finish") == sample.get("dawn_finish") and value["night_capacity"] == sample["night_capacity"], "frame receipts differ")
        parent.parent.parent.check_rule(value, True)
        require((value.get("gap_protocol"), value.get("gap_tick"), value.get("removed_id")) ==
                (gap.NATIVE, gap.AT, gap.REMOVED), "frame gap differs")
        require(value == experiment.read_json(root/(stem+".repeat.json")) and pixels == (root/(stem+".repeat.rgb565")).read_bytes(), "frame repeat differs")
        frames.append({"id": f"{arm}.{tick}", "arm": arm, "tick": tick, "result": value,
                       "framebuffer": stem+".rgb565", "png": stem+".png"})
    result = {"outcomes": outcomes, "lineages": world["lineages"], "seeds": seeds,
        "access": detail, "handoff": handoff, "refusals": receipts, "ordinary_guard": ordinary,
        "capacity": capacity, "routing": routing, "export": exported, "activation": active,
        "daily": extra["daily"], "site_checkpoints": checked,
        "occupancy": parent.parent.parent.occupancy(worlds, active["after"]),
        "checked_live_budgets": detail["checked_live_budgets"],
        "target": {"lineage": records[ID], "history": history, "budget": totals, "last_live": last,
                   "checked_live_steps": count, "stress_episodes": budget.stress_episodes(history),
                   "offspring": gap.cohort(records, -1, {i for i, p in records.items() if p["parent"] == ID})}}
    print("Audited seed-order arm:", arm, flush=True)
    return result, frames, worlds


def historical_files():
    return [*(f"traces/fixed.{kind}.jsonl.gz" for kind in ("world", "sites")),
            *(f"frames/fixed.{t}.{ext}" for t in FRAMES for ext in ("json", "rgb565"))]


def check_historical(root):
    for name in historical_files():
        require(experiment.digest(root/name) == experiment.digest(root/"input/history"/name), "historical control drift: "+name)
        repeat = name.replace(".jsonl.gz", ".repeat.jsonl.gz") if name.endswith(".gz") else (
            name.rsplit(".", 1)[0]+".repeat."+name.rsplit(".", 1)[1])
        require(experiment.digest(root/repeat) == experiment.digest(root/name), "historical repeat drift")


def analyze(root, create=False):
    check_historical(root)
    prefixes = {kind: check_prefix(*(gap.read_trace(root/f"traces/{a}.{kind}.jsonl.gz") for a in ARMS)) for kind in ("world", "sites")}
    cases, frames, worlds = {}, [], {}
    for arm in ARMS:
        cases[arm], images, worlds[arm] = analyze_case(root, arm, create)
        frames.extend(images)
    old = experiment.read_json(root/"input/parent-results.json")["cases"]["reserve"]
    for key in ("outcomes", "lineages", "seeds", "refusals", "ordinary_guard", "capacity", "routing", "daily", "occupancy", "checked_live_budgets"):
        require(cases["fixed"][key] == old[key], "historical derived result differs: "+key)
    prior = experiment.read_json(root/"input/access.json")["cases"]["reserve"]
    for key in ("parents", "bank", "purchase_phases", "releases_and_purchases", "target_seeds", "target_dispersal_support", "checked_live_budgets", "terminal_steps_not_reconstructed"):
        require(cases["fixed"]["access"][key] == prior[key], "historical access differs: "+key)
    require((root/f"frames/fixed.{AFTER}.rgb565").read_bytes() == (root/f"frames/rotating.{AFTER}.rgb565").read_bytes(), "noon prefix pixels changed")
    divergent = next(({"tick": a["tick"], "fixed": a, "rotating": b} for a, b in zip(worlds["fixed"], worlds["rotating"], strict=True)
                      if a["hash"] != b["hash"]), None)
    require(divergent is None or divergent["tick"] > AFTER, "early physical divergence")
    return {"settings": settings(), "prefixes": prefixes, "first_hash_divergence": divergent, "cases": cases, "frames": frames}


def copies():
    return {"input/parent-results.json": "results.json", "input/prior-cache.txt": "input/CMakeCache.txt",
            "input/native-source.tar.gz": "source.tar.gz",
            **{f"models/{n}.tgm": f"models/{n}.tgm" for n in settings()["models"]},
            **{f"input/history/{n}": n.replace("fixed.", "reserve.") for n in historical_files()}}


def check_inputs(root):
    require(experiment.digest(root/"input/parent-manifest.json") == BASELINE_SHA and
            experiment.digest(root/"input/parent-summary.json") == PORTABLE_SHA and
            experiment.digest(root/"input/access.json") == AUDIT_SHA, "changed parent evidence")
    manifest = experiment.read_json(root/"input/parent-manifest.json")
    for dest, source in copies().items():
        require(experiment.digest(root/dest) == manifest["artifacts"][source], "changed parent copy")
    started = experiment.read_json(root/"started.json")
    require(started["settings"] == settings() and experiment.digest(root/"input/protocol.md") ==
            started["sources"][PROTOCOL], "changed protocol/settings")
    for name, sha in started["frozen"].items():
        require(experiment.digest(root/name) == sha, "frozen input changed")
    old, new = [native.native_hashes(root/p) for p in ("input/native-source.tar.gz", "source.tar.gz")]
    added = {"src/garden_seed_order.h", "sim/garden_seed_order.c", "sim/garden_seed_order_test.c"}
    changed = {"src/garden_world.c", "src/garden_world.h", "sim/garden_inspect.c", "sim/garden_replay.c"}
    require(new.keys()-old.keys() == added and not old.keys()-new.keys() and
            {n for n in old if old[n] != new[n]} <= changed, "unrelated native changes")
    require(all(started["sources"].get(n) == sha for n, sha in new.items()), "native archive mismatch")
    a, b = [native.cache_settings(root/p) for p in ("input/prior-cache.txt", "input/CMakeCache.txt")]
    require(b.pop("TOY_FACTORY_GARDEN_SEED_ORDER:BOOL", None) == "ON" and a == b, "wrong build configuration")


def check_capture(root):
    check_inputs(root)
    capture = experiment.read_json(root/"capture.json")
    require(capture["settings"] == settings() and
            [(c["artifact"], c["command"]) for c in capture["calls"]] == commands(), "wrong call inventory")
    for name in capture["artifacts"]:
        gap.gallery.artifact(root, capture, name)
    return capture


def analysis_sources():
    paths = sorted((experiment.ROOT/"sim").glob("*.py"))+[experiment.ROOT/PROTOCOL, experiment.ROOT/"sim/CMakeLists.txt"]
    return {str(p.relative_to(experiment.ROOT)): experiment.digest(p) for p in paths}


def finish(root):
    """Saved-data recovery only: no captured executable is called here."""
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
            (experiment.ROOT/PORTABLE, "input/parent-summary.json"), (experiment.ROOT/AUDIT, "input/access.json"),
            (experiment.ROOT/PROTOCOL, "input/protocol.md")):
        shutil.copy2(source, output/dest)
    for name in ("CMakeCache.txt", "build.ninja"):
        shutil.copy2(build/name, output/"input"/name)
    for name in ("inspect", "replay"):
        shutil.copy2(build/("toy-factory-garden-"+name), output/"bin"/name)
    frozen = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
    experiment.write_json(output/"started.json", {"settings": settings(), "sources": sources, "frozen": frozen})
    calls, begin = [], time.monotonic()
    try:
        check_inputs(output)
        for target, command in commands():
            start = time.monotonic()
            if target.endswith(".gz"):
                with tempfile.TemporaryDirectory(prefix="garden-seed-order-") as temporary:
                    raw = Path(temporary)/"trace.jsonl"
                    try:
                        experiment.command_run(command, raw, output, 180)
                    finally:
                        if raw.exists():
                            experiment.compress(raw, output/target)
            else:
                experiment.command_run(command, output/target, output, 180)
            calls.append({"artifact": target, "command": command, "seconds": time.monotonic()-start})
            if target == f"frames/fixed.{STOP}.repeat.json":
                check_historical(output)
                print("Exact historical reserve traces and both frames", flush=True)
            print(f"Captured {len(calls)}/16: {target}", flush=True)
        require(experiment.source_files() == sources, "sources changed during capture")
        artifacts = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
        experiment.write_json(output/"capture.json", {"settings": settings(), "calls": calls,
            "artifacts": artifacts, "capture_seconds": time.monotonic()-begin})
    except BaseException as error:
        experiment.write_json(output/"capture-failure.json", {"error": str(error), "completed_calls": calls})
        raise
    finish(output)


def verify(root):
    manifest = experiment.read_json(root/"manifest.json")
    require(manifest["rule"] == RULE and manifest["status"] == "complete" and manifest["native_calls"] == 16, "incomplete bundle")
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
    print("Verified portable seed-order comparison and four native frames", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT/"artifacts/garden-renewal-dawn-reserve-v1")
    parser.add_argument("--build", type=Path, default=experiment.ROOT/"artifacts/build-host-seed-order-docker")
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
