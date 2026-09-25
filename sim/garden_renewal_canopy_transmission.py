#!/usr/bin/env python3
"""One frozen fractional-canopy A/B on the saved two-column spacing world."""
from __future__ import annotations

import argparse
from collections import defaultdict
from itertools import zip_longest
from pathlib import Path
import shutil
import tempfile
import time

import garden_renewal_establishment_light as light_audit
import garden_renewal_seed_spacing as prior

gap, experiment, require, native = prior.gap, prior.experiment, prior.require, prior.native
order = prior.prior
RULE, NATIVE = "garden-renewal-canopy-transmission-v1", "post-noon-fractional-transmission-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-canopy-transmission-protocol.md"
BASELINE_SHA = "f230a7eeb305eb9bef28381ea618cb8fec44a3da4d5885bd5978eeb675507007"
PORTABLE = "benchmarks/garden-longevity/renewal-seed-spacing-summary.json"
PORTABLE_SHA = "bdd740f2b1a2b74488c3e2aed8b674b750a516a13dd9b56fd2b656deafc6fb0e"
AUDIT = "benchmarks/garden-longevity/renewal-establishment-light-summary.json"
AUDIT_SHA = "cc8db979c33e7e93fd23ccb0a53784bff4da6daaad828188e9e851fa3c6570e6"
AFTER, STOP, LATE, DAY = prior.AFTER, prior.STOP, prior.LATE, prior.DAY
ARMS, FRAMES = ("control", "transmission"), prior.FRAMES


def settings():
    return {"rule": RULE, "native_rule": NATIVE, "arms": list(ARMS), "after_inclusive": AFTER,
            "first_ecology_tick": AFTER+15, "stop": STOP, "late": LATE, "frames": list(FRAMES),
            "formula": "beam=(beam*(255-shade)+127)//255 per target-to-sky ray cell; light=24+beam",
            "models": prior.settings()["models"], "routing": prior.settings()["routing"],
            "parent_manifest_sha256": BASELINE_SHA, "parent_portable_sha256": PORTABLE_SHA,
            "light_audit_sha256": AUDIT_SHA, "budget": {"native_calls": 20, "training_calls": 0},
            "role": "selected-world optical diagnostic, not qualified sustained renewal"}


def commands():
    # The parent treatment is the new control, not its older three-column arm.
    baseline = [(p, cmd) for p, cmd in prior.commands() if "/two." in p]
    calls = []
    for arm in ARMS:
        for path, command in baseline:
            target = path.replace("/two.", "/"+arm+".")
            cmd = [s.replace("frames/two.", "frames/"+arm+".") for s in command]
            if arm == "transmission":
                cmd += ["--canopy-transmission", "fractional"]
            calls.append((target, cmd))
    return calls


def check_rule(row, arm):
    require(arm in ARMS and type(row["tick"]) is int and row["tick"] >= 0, "invalid optical scope")
    prior.minimum(row, "two")
    if arm == "control":
        require("canopy_transmission" not in row, "control unexpectedly changes optics")
    else:
        require(row.get("canopy_transmission") == {"rule": NATIVE, "after": AFTER, "active": row["tick"] > AFTER},
                "missing/incorrect optical metadata")


def check_prefix(control, candidate):
    for count, (a, b) in enumerate(zip_longest(control, candidate), 1):
        require(a is not None and b is not None, "truncated optical prefix")
        if a["type"] in ("world", "seed-sites"):
            check_rule(a, "control")
            check_rule(b, "transmission")
        require(a == {k: v for k, v in b.items() if k != "canopy_transmission"}, "physical prefix changed")
        if a["type"] in ("world", "seed-sites") and a["tick"] == AFTER:
            return count
    raise RuntimeError("prefix did not reach optical boundary")


def light_followup(rows, records):
    """Use exact live budgets/carries, not an alternative simulation of light."""
    histories, previous, pending, offered, anchor = defaultdict(list), {}, {}, defaultdict(list), None
    for row in rows:
        if row["type"] == "leaf-bid":
            require(row["id"] not in pending, "duplicate sampled leaf")
            pending[row["id"]] = row
            continue
        if row["type"] == "bid":
            offered[row["id"]].append(row)
            continue
        tick = row["tick"]
        current = {p["id"]: p for p in row["plants"]}
        if tick == AFTER:
            anchor = light_audit.failures.point(tick, current[5])
        for identity, p in current.items():
            old = previous.get(identity)
            bid, growth_bids = pending.pop(identity, None), offered.pop(identity, [])
            if tick <= AFTER or (old and old["dead"]):
                continue
            if p["dead"]:
                require(old and not old["dead"] and not bid and not growth_bids and
                        tick == records[identity]["death_tick"], "invalid terminal light step")
                entry = {"state": light_audit.failures.point(tick, p), "budget": None, "terminal": "natural",
                         "light": None, "growth": None, "maintenance": None}
            else:
                values = light_audit.resources.budget(old, p, tick)
                light_audit.check_leaf(old, p)
                if old:
                    light_audit.check_stress(old, p, tick, values)
                entry = {"state": light_audit.failures.point(tick, p), "budget": values, "terminal": None,
                         "light": light_audit.photometry(old, p, tick, bid, values),
                         "growth": light_audit.growth(old, p, tick, growth_bids, values),
                         "maintenance": light_audit.seedlings.maintenance(old, {**p, "tick": tick}, values)}
            if identity == 5 or records[identity]["birth_tick"] > AFTER:
                histories[identity].append(entry)
        require(not pending and not offered, "unmatched light/growth observation")
        previous = current
    require(anchor is not None, "flower absent at split")
    children = []
    for identity, record in records.items():
        if record["birth_tick"] <= AFTER:
            continue
        history = histories[identity]
        end = record["death_tick"] or STOP
        require([e["state"]["tick"] for e in history] == list(range(record["birth_tick"], end+15, 15)),
                "incomplete new seedling light history")
        children.append(light_audit.describe_child(record, history))
    flower = histories[5]
    end = records[5]["death_tick"] or STOP
    require([e["state"]["tick"] for e in flower] == list(range(AFTER+15, end+15, 15)), "incomplete flower light history")
    days, origin = [], anchor
    for start in range(AFTER, end, DAY):
        part = [e for e in flower if start < e["state"]["tick"] <= start+DAY]
        days.append(light_audit.summarize(part, origin))
        origin = part[-1]["state"]
    return {"children": children, "flower": {"lineage": records[5], "whole_post_boundary": light_audit.summarize(flower, anchor),
            "days": days, "stress_episodes": light_audit.seedlings.stress_episodes(flower)}}


def analyze_case(root, arm, create=False, *, rule_check=None, preaccount=None):
    rule_check = check_rule if rule_check is None else rule_check
    for kind in ("world", "sites"):
        require(experiment.digest(root/f"traces/{arm}.{kind}.jsonl.gz") ==
                experiment.digest(root/f"traces/{arm}.{kind}.repeat.jsonl.gz"), "trace repeat differs")
    split = order.parent.parent.parent.split_census
    raw, exported, active = split(gap.read_trace(root/f"traces/{arm}.world.jsonl.gz"), "optional")
    sites, site_export, site_active = split(gap.read_trace(root/f"traces/{arm}.sites.jsonl.gz"), "optional", "seed-sites")
    require(exported["event"] == site_export["event"] and active["event"] == site_active["event"], "boundary disagreement")
    if preaccount is not None:
        # A later, independently checked pre-expense refusal can omit only its
        # uncommitted bids. Never change census state or leaf observations.
        prepared = preaccount(raw)
        require([r for r in prepared if r["type"] != "bid"] ==
                [r for r in raw if r["type"] != "bid"], "preaccount changed authoritative observations")
        raw = prepared
    handoff = {}
    vetoes, receipts = order.parent.check_refusals(raw, "reserve", audit=handoff)
    capacity_vetoes, capacity = gap.parent.audit_capacity(raw, "capacity")
    routing, _ = gap.guard.prior.neighbors.check_routing(iter(raw), gap.guard.prior.ROUTE)
    accounted, ordinary = gap.guard.accounting_rows(raw, "guard", stop=STOP, retain_events=False,
                                                   growth_vetoes=vetoes | capacity_vetoes)
    worlds = [r for r in accounted if r["type"] == "world"]
    for row in worlds+sites:
        rule_check(row, arm)
        order.check_order(row, "rotating")
    path = root/f"traces/{arm}.worlds.jsonl.gz"
    order.parent.parent.derived_census(path, worlds, create)
    world, _ = gap.panel.competition.world_analysis(path, "selective", 512, STOP, LATE, removal=exported["event"])
    records = {p["id"]: p for p in world["lineages"]}
    extra = gap.panel.supplementary(worlds, {gap.AT: {"after": active["after"]}}, records, gap.parent.CASES[0].baseline)
    ledger = gap.ledger.seed_ledger(worlds, {}, records, spacing_at=lambda r: prior.minimum(r, "two"),
                                  reproduction_order=lambda r: order.visit_view(r, "rotating")["plants"])
    seeds = [{k: v for k, v in s.items() if k not in ("post_cutoff_blockers", "sole_spacing_22")} for s in ledger["seeds"]]
    checked = gap.check_sites(worlds, sites, seeds, records, spacing_at=lambda r: prior.minimum(r, "two"))
    require(all(w.get("canopy_transmission") == s.get("canopy_transmission") and
                all(w[k] == s[k] for k in ("seed_spacing", "seed_order", "dawn_finish"))
                for w, s in zip(worlds, sites, strict=True)), "site metadata differs")
    outcomes = gap.outcomes(world, extra, seeds, worlds)
    resources = prior.resource_followup(worlds, records)
    frames, by_tick = [], {w["tick"]: w for w in worlds}
    for tick in FRAMES:
        stem = f"frames/{arm}.{tick}"
        value = experiment.read_json(root/(stem+".json"))
        pixels = (root/(stem+".rgb565")).read_bytes()
        sample = by_tick[tick]
        gap.panel.check_frame(value, sample, gap.parent.CASES[0].baseline, tick, pixels, [])
        rule_check(value, arm)
        order.check_order(value, "rotating", len(sample["plants"]))
        require(value.get("canopy_transmission") == sample.get("canopy_transmission") and
                all(value[k] == sample[k] for k in ("dawn_finish", "night_capacity")), "frame receipts differ")
        order.parent.parent.parent.check_rule(value, True)
        require((value.get("gap_protocol"), value.get("gap_tick"), value.get("removed_id")) ==
                (gap.NATIVE, gap.AT, gap.REMOVED), "frame export differs")
        require(value == experiment.read_json(root/(stem+".repeat.json")) and
                pixels == (root/(stem+".repeat.rgb565")).read_bytes(), "frame repeat differs")
        frames.append({"id": f"{arm}.{tick}", "arm": arm, "tick": tick, "result": value,
                       "framebuffer": stem+".rgb565", "png": stem+".png"})
    result = {"outcomes": outcomes, "lineages": world["lineages"], "seeds": seeds,
        "handoff": handoff, "refusals": receipts, "ordinary_guard": ordinary, "capacity": capacity,
        "routing": routing, "export": exported, "activation": active, "daily": extra["daily"],
        "checked_live_budgets": world["windows"]["whole"]["budget_checked_live_steps"],
        "terminal_steps_not_reconstructed": world["windows"]["whole"]["terminal_steps"],
        "site_checkpoints": checked, "sites": prior.site_followup(sites, "two"), "resources": resources,
        "new_cohort": gap.cohort(records, AFTER),
        "occupancy": order.parent.parent.parent.occupancy(worlds, active["after"]),
        "light_followup": light_followup(accounted, records)}
    print("Audited renewal arm:", arm, flush=True)
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
    a, b = metrics["control"], metrics["transmission"]
    require((a["new_full_day_survivors"], a["new_full_day_parents_with_full_day_child"], a["incumbent_deaths"]) ==
            (6, 0, 3), "changed historical outcome anchors")
    gates = {"more_new_full_day_survivors": b["new_full_day_survivors"] > 6,
             "new_durable_parent": b["new_full_day_parents_with_full_day_child"] > 0,
             "no_extra_incumbent_deaths": b["incumbent_deaths"] <= 3,
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
    old = experiment.read_json(root/"input/parent-results.json")["cases"]["two"]
    require(all(cases["control"][k] == v for k, v in old.items()), "historical derived outcomes changed")
    saved_light = experiment.read_json(root/"input/light-audit.json")
    require(cases["control"]["light_followup"]["children"] == saved_light["children"], "historical seedling light audit changed")
    require((root/f"frames/control.{AFTER}.rgb565").read_bytes() ==
            (root/f"frames/transmission.{AFTER}.rgb565").read_bytes(), "boundary pixels differ")
    divergence = next(({"tick": a["tick"], "control": a, "transmission": b}
                       for a, b in zip(worlds["control"], worlds["transmission"], strict=True) if a["hash"] != b["hash"]), None)
    require(divergence is not None and divergence["tick"] == AFTER+15, "wrong first optical divergence")
    return {"settings": settings(), "prefixes": prefixes, "first_hash_divergence": divergence,
            "cases": cases, "frames": frames, "decision": decision(cases)}


def copies():
    return {"input/parent-results.json": "results.json", "input/prior-cache.txt": "input/CMakeCache.txt",
            "input/native-source.tar.gz": "source.tar.gz",
            **{f"models/{n}.tgm": f"models/{n}.tgm" for n in settings()["models"]},
            **{f"input/history/{n}": n.replace("control.", "two.") for n in historical_files()}}


def check_inputs(root):
    require(experiment.digest(root/"input/parent-manifest.json") == BASELINE_SHA and
            experiment.digest(root/"input/parent-summary.json") == PORTABLE_SHA and
            experiment.digest(root/"input/light-audit.json") == AUDIT_SHA, "changed parent evidence")
    manifest = experiment.read_json(root/"input/parent-manifest.json")
    for dest, source in copies().items():
        require(experiment.digest(root/dest) == manifest["artifacts"][source], "changed parent copy")
    started = experiment.read_json(root/"started.json")
    require(started["settings"] == settings() and experiment.digest(root/"input/protocol.md") == started["sources"][PROTOCOL],
            "changed protocol/settings")
    for name, sha in started["frozen"].items():
        require(experiment.digest(root/name) == sha, "frozen input changed")
    old, new = [native.native_hashes(root/p) for p in ("input/native-source.tar.gz", "source.tar.gz")]
    added = {"src/garden_canopy_transmission.h", "sim/garden_canopy_transmission.c", "sim/garden_canopy_transmission_test.c"}
    changed = {"src/garden_light.c", "src/garden_light.h", "src/garden_world.c", "src/garden_world.h",
               "sim/garden_inspect.c", "sim/garden_replay.c"}
    require(new.keys()-old.keys() == added and not old.keys()-new.keys() and
            {n for n in old if old[n] != new[n]} <= changed, "unrelated native changes")
    require(all(started["sources"].get(n) == sha for n, sha in new.items()), "native archive mismatch")
    a, b = [native.cache_settings(root/p) for p in ("input/prior-cache.txt", "input/CMakeCache.txt")]
    require(b.pop("TOY_FACTORY_GARDEN_CANOPY_TRANSMISSION:BOOL", None) == "ON" and a == b, "wrong build configuration")


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
            (experiment.ROOT/AUDIT, "input/light-audit.json")):
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
                with tempfile.TemporaryDirectory(prefix="garden-canopy-transmission-") as temporary:
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
                print("Historical two-column control traces and frames match exactly", flush=True)
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
    print("Verified portable canopy comparison and six native frames", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT/"artifacts/garden-renewal-seed-spacing-v1")
    parser.add_argument("--build", type=Path, default=experiment.ROOT/"artifacts/build-host-canopy-transmission-docker")
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
