#!/usr/bin/env python3
"""One fixed last-tip FINISH deferral through dawn, with day-64 follow-up."""
from __future__ import annotations

import argparse
from itertools import zip_longest
from pathlib import Path
import shutil
import tempfile
import time

import garden_renewal_wet_germination as parent
import garden_renewal_seedling_budget as budget

gap, experiment, require, native = parent.gap, parent.experiment, parent.require, parent.native
RULE, NATIVE = "garden-renewal-dawn-finish-v1", "dawn-finish-deferral-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-dawn-finish-protocol.md"
BASELINE_SHA = "645ea3d984e064d56263238955188b3efd5eee9b9bc9de5a4c96d4e8f4349cef"
AUDIT = "benchmarks/garden-longevity/renewal-seedling-budget-summary.json"
AUDIT_SHA = "da2a89751ebc77727ec77c339149ba961ab161281f18bd2c76ea70cef40725e6"
FIRST, LAST, ID = 66090, 68340, 12
STOP, LATE, ARMS, FRAMES = parent.STOP, parent.LATE, ("control", "defer"), (66075, 68340, 69120, parent.STOP)


def settings():
    return {"rule": RULE, "native_rule": NATIVE, "target": ID, "first": FIRST, "last_inclusive": LAST,
            "seed": gap.SEED, "models": gap.settings()["models"], "routing": gap.settings()["routing"],
            "gap_tick": gap.AT, "removed": gap.REMOVED, "wet_after": gap.AT,
            "stop": STOP, "late": LATE, "frames": list(FRAMES),
            "budget": {"native_calls": 24, "training_calls": 0}}


def commands():
    calls = []
    for arm in ARMS:
        base = ["models/r2-n.tgm", "rainfed-crowded", experiment.NIGHT_POLICY, "0x"+gap.SEED,
                "--leaf-policy", "selective", "--focal-model", "models/r2-w.tgm", "--focal-founder", "5",
                "--gap-at", str(gap.AT), "--gap-lineage", str(gap.REMOVED),
                "--wet-germination-after", str(gap.AT)]
        if arm == "defer":
            base += ["--dawn-finish", "defer"]
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


def metadata(hits=0, tick=0, node=0):
    return {"rule": NATIVE, "id": ID, "first": FIRST, "last": LAST,
            "hits": hits, "last_tick": tick, "last_node": node}


def clean(row):
    return {k: v for k, v in row.items() if k != "dawn_finish"}


def check_prefix(control, deferred):
    previous = None
    for count, (a, b) in enumerate(zip_longest(control, deferred)):
        require(a is not None and b is not None, "truncated common prefix")
        if a == clean(b):
            require(a["tick"] <= FIRST, "missing FINISH divergence")
            if a["type"] == "world":
                previous = a
            continue
        require(a["type"] == b["type"] == "world" and a["tick"] == b["tick"] == FIRST,
                "divergence outside the selected transaction")
        require({k: v for k, v in a.items() if k not in ("hash", "plants")} ==
                {k: v for k, v in clean(b).items() if k not in ("hash", "plants")}, "non-target world state changed")
        left, right = [{p["id"]: p for p in row["plants"]} for row in (a, b)]
        require(left.keys() == right.keys() and all(left[i] == right[i] for i in left if i != ID),
                "another lineage changed at first FINISH")
        p, q = left[ID], right[ID]
        require(previous is not None and previous["tick"] == FIRST-15, "missing pre-purchase state")
        old = next(p for p in previous["plants"] if p["id"] == ID)
        require({k: v for k, v in p.items() if k not in ("energy", "water", "tips", "agent")} ==
                {k: v for k, v in q.items() if k not in ("energy", "water", "tips", "agent")},
                "unexpected focal state change")
        require((p["energy"], p["water"], p["tips"], q["energy"], q["water"], q["tips"]) ==
                (243, 507, 0, 251, 512, 1), "wrong cost/tip delta")
        require(q["agent"] == old["agent"] and p["agent"]["decisions"] == q["agent"]["decisions"]+1 and
                p["agent"]["finish"] == q["agent"]["finish"]+1, "refused FINISH committed telemetry")
        require(b["dawn_finish"] == metadata(1, FIRST, 378) and a["hash"] == "e0b8351f" and
                a["hash"] != b["hash"], "wrong initial receipt/hash")
        return {"matching_raw_records": count, "tick": FIRST, "control": p, "deferred": q,
                "ordinary_guard": a["dark_guard"]}
    raise RuntimeError("missing intervention")


def check_refusals(rows, arm):
    current, pending, previous, receipts, vetoes = metadata(), [], {}, [], set()
    for row in rows:
        if row["type"] in ("bid", "leaf-bid"):
            pending.append(row)
            continue
        tick = row["tick"]
        if arm == "control":
            require("dawn_finish" not in row, "control unexpectedly selected")
        else:
            require("dawn_finish" in row, "missing experiment receipt")
            candidates = [b for b in pending if b["type"] == "bid" and b["id"] == ID]
            events = [e for e in row["dark_guard"]["events"] if e["id"] == ID and e["kind"] == "growth"]
            require(len(events) <= 1, "duplicate target expense")
            expected = FIRST <= tick <= LAST and events and not events[0]["denied"]
            if expected:
                require(bool(candidates), "missing winning bid")
                winner, event = max(candidates, key=lambda b: b["priority"]), events[0]
                require(all(winner[k] == v for k, v in
                    {"action": 2, "priority": 32767, "x": 47, "y": 193, "depth": 9,
                     "maximum_depth": 9, "tissue": 1, "tip_flags": 1}.items()), "wrong deferred tip")
                require(event["node"] == winner["tip_index"] and not event["invalid"] and
                        all(event[k] == v for k, v in {"nodes_before": 61, "nodes_after": 61,
                                                     "energy_cost": 8, "water_cost": 5}.items()), "wrong expense")
                plant = next(p for p in row["plants"] if p["id"] == ID)
                require(not plant["dead"] and plant["agent"] == previous[ID]["agent"] and plant["tips"] == 1 and
                        (plant["energy"], plant["water"]) == (event["energy"], event["water"]),
                        "refusal spent resources or committed a decision")
                if not receipts:
                    require(tick == FIRST and event["node"] == 378 and event["energy"] == 251 and
                            event["water"] == 512 and event["stress"] == 0 and
                            all(event[k]["supported"] and not event[k]["death_step"] for k in ("before", "after")),
                            "wrong first receipt")
                current = metadata(current["hits"]+1, tick, event["node"])
                receipts.append({"tick": tick, "phase": row["sun_phase"], "expense": event, "bid": winner})
                vetoes.add((tick, ID))
            require(row["dawn_finish"] == current, "missing/extra/out-of-window refusal")
        previous, pending = {p["id"]: p for p in row["plants"]}, []
    require(not pending and (bool(receipts) == (arm == "defer")), "missing/incomplete refusal receipts")
    return vetoes, receipts


def derived_census(path, worlds, create):
    """Resume by verifying existing derived data, never overwriting observations."""
    if create and not path.exists():
        gap.guard.write_accounting(path, worlds)
    require(worlds == list(gap.read_trace(path)), "derived census differs")


def analyze_case(root, arm, create=False, *, refusal_check=None):
    for kind in ("world", "sites"):
        path = root/f"traces/{arm}.{kind}.jsonl.gz"
        require(experiment.digest(path) == experiment.digest(root/f"traces/{arm}.{kind}.repeat.jsonl.gz"),
                "native repeat differs")
        if arm == "control":
            require(experiment.digest(path) == experiment.digest(root/f"input/prior-{kind}.jsonl.gz"),
                    "historical control drift")
    raw, exported, active = parent.split_census(gap.read_trace(root/f"traces/{arm}.world.jsonl.gz"), "optional")
    sites, site_export, site_active = parent.split_census(gap.read_trace(root/f"traces/{arm}.sites.jsonl.gz"), "optional", "seed-sites")
    require(exported["event"] == site_export["event"] and active["event"] == site_active["event"],
            "world/site boundary differs")
    vetoes, receipts = (refusal_check or check_refusals)(raw, arm)
    capacity_vetoes, capacity = gap.parent.audit_capacity(raw, "capacity")
    routing, _ = gap.guard.prior.neighbors.check_routing(iter(raw), gap.guard.prior.ROUTE)
    accounted, ordinary_guard = gap.guard.accounting_rows(raw, "guard", stop=STOP, retain_events=False,
                                                         growth_vetoes=vetoes | capacity_vetoes)
    worlds = [r for r in accounted if r["type"] == "world"]
    path = root/f"traces/{arm}.worlds.jsonl.gz"
    derived_census(path, worlds, create)
    world, _ = gap.panel.competition.world_analysis(path, "selective", 512, STOP, LATE, removal=exported["event"])
    records = {p["id"]: p for p in world["lineages"]}
    extra = gap.panel.supplementary(worlds, {gap.AT: {"after": active["after"]}}, records, gap.parent.CASES[0].baseline)
    full = gap.ledger.seed_ledger(worlds, {}, records)
    seeds = [{k: v for k, v in s.items() if k not in ("post_cutoff_blockers", "sole_spacing_22")} for s in full["seeds"]]
    checked = gap.check_sites(worlds, sites, seeds, records)
    require(all(w.get("dawn_finish") == s.get("dawn_finish") for w, s in zip(worlds, sites, strict=True)),
            "site renderer did not run the same intervention")
    outcomes = gap.outcomes(world, extra, seeds, worlds)
    for child in outcomes["post_export_children"]:
        identity = child["lineage"]["id"]
        child["own_seeds"] = gap.seed_audit.outcome_summary([s for s in seeds if s["parent"] == identity])
        child["offspring"] = gap.cohort(records, -1, {i for i, p in records.items() if p["parent"] == identity})
    chosen = {ID: records[ID]}
    histories, focal_checked = budget.failures.histories(budget.focal_rows(worlds, chosen, {}), {}, chosen, STOP)
    history = histories[ID]
    live = [e for e in history if e["budget"] is not None]
    totals = budget.failures.budget_sum(history)
    budget.failures.balance(budget.ORIGIN, live[-1]["state"], totals)
    later = next((e for e in history if e["state"]["tick"] > LAST and
                  e["budget"] is not None and e["budget"]["energy_growth"]), None)
    target = {"lineage": records[ID], "history": history, "budget": totals,
              "checked_live_steps": focal_checked, "terminal_budget": "cleared-not-reconstructed" if records[ID]["death_tick"] else None,
              "last_live": live[-1]["state"], "first_paid_growth_after_release": later,
              "stress_episodes": budget.stress_episodes(history),
              "own_seeds": gap.seed_audit.outcome_summary([s for s in seeds if s["parent"] == ID]),
              "offspring": gap.cohort(records, -1, {i for i, p in records.items() if p["parent"] == ID})}
    frames, by_tick = [], {w["tick"]: w for w in worlds}
    for tick in FRAMES:
        stem = f"frames/{arm}.{tick}"
        value = experiment.read_json(root/(stem+".json"))
        pixels = (root/(stem+".rgb565")).read_bytes()
        sample = by_tick[tick]
        gap.panel.check_frame(value, sample, gap.parent.CASES[0].baseline, tick, pixels, [])
        require(value.get("dawn_finish") == sample.get("dawn_finish") and value["night_capacity"] == sample["night_capacity"],
                "frame diagnostics disagree")
        parent.check_rule(value, True)
        require((value.get("gap_protocol"), value.get("gap_tick"), value.get("removed_id")) ==
                (gap.NATIVE, gap.AT, gap.REMOVED), "frame export changed")
        require(value == experiment.read_json(root/(stem+".repeat.json")) and
                pixels == (root/(stem+".repeat.rgb565")).read_bytes(), "frame repeat differs")
        if arm == "control" and tick == STOP:
            require(value == experiment.read_json(root/"input/prior-final.json") and
                    pixels == (root/"input/prior-final.rgb565").read_bytes(), "historical control pixels changed")
        frames.append({"id": f"{arm}.{tick}", "arm": arm, "tick": tick, "result": value,
                       "framebuffer": stem+".rgb565", "png": stem+".png"})
    if arm == "control":
        saved = experiment.read_json(root/"input/prior-results.json")["cases"]["optional"]
        require(world["lineages"] == saved["lineages"] and seeds == saved["seeds"], "historical lifetimes drift")
        for key in ("whole", "late", "final", "post_export"):
            require(outcomes[key] == saved["outcomes"][key], "control outcome drift")
    print("Audited dawn-FINISH arm:", arm, flush=True)
    return {"outcomes": outcomes, "target": target, "lineages": world["lineages"], "seeds": seeds,
            "refusals": receipts, "ordinary_guard": ordinary_guard, "capacity": capacity, "routing": routing,
            "export": exported, "activation": active, "daily": extra["daily"],
            "site_checkpoints": checked, "occupancy": parent.occupancy(worlds, active["after"]),
            "checked_live_budgets": world["windows"]["whole"]["budget_checked_live_steps"]}, frames


def analyze(root, create=False):
    prefix = check_prefix(*(gap.read_trace(root/f"traces/{arm}.world.jsonl.gz") for arm in ARMS))
    cases, frames = {}, []
    for arm in ARMS:
        cases[arm], samples = analyze_case(root, arm, create)
        frames.extend(samples)
    require((root/f"frames/control.{FRAMES[0]}.rgb565").read_bytes() ==
            (root/f"frames/defer.{FRAMES[0]}.rgb565").read_bytes(), "prefix pixels differ")
    return {"settings": settings(), "prefix": prefix, "cases": cases, "frames": frames}


def copies():
    return {"input/prior-results.json": "results.json", "input/prior-cache.txt": "input/CMakeCache.txt",
            "input/native-source.tar.gz": "source.tar.gz",
            **{f"models/{name}.tgm": f"models/{name}.tgm" for name in settings()["models"]},
            **{f"input/prior-{kind}.jsonl.gz": f"traces/optional.{kind}.jsonl.gz" for kind in ("world", "sites")},
            **{f"input/prior-final.{ext}": f"frames/optional.{STOP}.{ext}" for ext in ("json", "rgb565")}}


def check_inputs(root):
    require(experiment.digest(root/"input/parent-manifest.json") == BASELINE_SHA and
            experiment.digest(root/"input/budget-summary.json") == AUDIT_SHA, "changed parent evidence")
    manifest = experiment.read_json(root/"input/parent-manifest.json")
    for dest, source in copies().items():
        require(experiment.digest(root/dest) == manifest["artifacts"][source], "changed parent copy")
    started = experiment.read_json(root/"started.json")
    require(started["settings"] == settings() and
            experiment.digest(root/"input/protocol.md") == started["sources"][PROTOCOL], "changed protocol/settings")
    for path, sha in started["frozen"].items():
        require(experiment.digest(root/path) == sha, "frozen input changed")
    old, new = [native.native_hashes(root/p) for p in ("input/native-source.tar.gz", "source.tar.gz")]
    allowed = {"src/garden_world.c", "src/garden_world.h", "sim/garden_inspect.c", "sim/garden_replay.c"}
    added = {"src/garden_dawn_finish.h", "sim/garden_dawn_finish.c", "sim/garden_dawn_finish_test.c"}
    require(old.keys() <= new.keys() and new.keys()-old.keys() == added and
            {n for n in old if old[n] != new[n]} <= allowed, "unrelated native source change")
    require(all(started["sources"].get(n) == sha for n, sha in new.items()), "native archive mismatch")
    a, b = [native.cache_settings(root/p) for p in ("input/prior-cache.txt", "input/CMakeCache.txt")]
    require(b.pop("TOY_FACTORY_GARDEN_DAWN_FINISH:BOOL", None) == "ON" and a == b, "build changed beyond opt-in hook")


def check_capture(root):
    check_inputs(root)
    capture = experiment.read_json(root/"capture.json")
    require(capture["settings"] == settings() and
            [(c["artifact"], c["command"]) for c in capture["calls"]] == commands(), "wrong native call inventory")
    for name in capture["artifacts"]:
        gap.gallery.artifact(root, capture, name)
    return capture


def analysis_sources():
    return {str(p.relative_to(experiment.ROOT)): experiment.digest(p) for p in sorted((experiment.ROOT/"sim").glob("*.py"))}


def finish(root):
    """Analysis-only recovery is allowed; captured observations are never rerun."""
    require(not (root/"manifest.json").exists(), "bundle already sealed")
    capture = check_capture(root)
    sources = analysis_sources()
    start = time.monotonic()
    result = analyze(root, True)
    require(result == analyze(root), "analysis repeat differs")
    for frame in result["frames"]:
        gap.gallery.write_png(root/frame["png"], 240, 240,
            gap.gallery.rgb565be_to_rgb888((root/frame["framebuffer"]).read_bytes()))
    gap.gallery.contact_sheet(root, [[f for f in result["frames"] if f["arm"] == arm] for arm in ARMS])
    check_capture(root)
    require(analysis_sources() == sources, "analysis changed while running")
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
    require(experiment.digest(experiment.ROOT/AUDIT) == AUDIT_SHA, "changed seedling diagnostic")
    sources = experiment.source_files()
    output.mkdir(parents=True)
    experiment.snapshot_sources(output, sources)
    for name in ("input", "models", "bin", "traces", "frames"):
        (output/name).mkdir()
    for dest, source in copies().items():
        shutil.copy2(baseline/source, output/dest)
    for source, dest in ((baseline/"manifest.json", "input/parent-manifest.json"),
            (experiment.ROOT/AUDIT, "input/budget-summary.json"), (experiment.ROOT/PROTOCOL, "input/protocol.md")):
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
                with tempfile.TemporaryDirectory(prefix="garden-dawn-finish-") as temporary:
                    raw = Path(temporary)/"trace.jsonl"
                    try:
                        experiment.command_run(cmd, raw, output, 180)
                    finally:
                        if raw.exists():
                            experiment.compress(raw, output/target)
            else:
                experiment.command_run(cmd, output/target, output, 180)
            timings.append({"artifact": target, "command": cmd, "seconds": time.monotonic()-start})
            if target == "traces/control.world.jsonl.gz":
                require(experiment.digest(output/target) == experiment.digest(output/"input/prior-world.jsonl.gz"),
                        "control drift; stop before treatment")
            print(f"Captured {len(timings)}/24: {target}", flush=True)
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
    require(manifest["rule"] == RULE and manifest["status"] == "complete", "wrong/incomplete bundle")
    require(set(manifest["artifacts"]) == {str(p.relative_to(root)) for p in root.rglob("*")
            if p.is_file() and p != root/"manifest.json"}, "extra/missing artifact")
    for name in manifest["artifacts"]:
        gap.gallery.artifact(root, manifest, name)
    capture = check_capture(root)
    require(experiment.read_json(root/"timings.json")["calls"] == capture["calls"], "timings changed")
    require(experiment.read_json(root/"analysis-sources.json") == analysis_sources(), "analysis sources changed")
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
    require(experiment.read_json(target) == result and all(experiment.digest(p) == experiment.digest(q) for p, q in images.items()),
            "portable evidence differs")
    print("Verified portable dawn-FINISH evidence and eight native frames", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT/"artifacts/garden-renewal-wet-germination-v1")
    parser.add_argument("--build", type=Path, default=experiment.ROOT/"artifacts/build-host-dawn-finish-docker")
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
