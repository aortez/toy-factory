#!/usr/bin/env python3
"""Capture and verify one fixed, host-only dark-spending-guard comparison."""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
from itertools import zip_longest
import json
from pathlib import Path
from garden_plant_slots import plant_capacity
import shutil
import tempfile
import time

import garden_renewal_dark_budget as reference
import garden_renewal_seed_veto as prior
import garden_disturbance as disturbance

experiment, startup, gallery, require = prior.experiment, prior.startup, prior.gallery, prior.require
RULE, GUARD = "garden-renewal-dark-guard-v1", "dark-spending-guard-v1"
OPTION = "TOY_FACTORY_GARDEN_DARK_GUARD:BOOL"
PROTOCOL = "benchmarks/garden-longevity/renewal-dark-guard-protocol.md"
BASELINE_SHA = reference.BASELINE_SHA
AUDIT = "benchmarks/garden-longevity/renewal-dark-budget-summary.json"
AUDIT_SHA = "73e02cc1c4a3455dd50d1ef56f36d37fc2ef1844cc1ed01268f122cdff1549f7"
CASES, FRAME_TICKS = ("control", "guard"), prior.FRAME_TICKS
KINDS = reference.KINDS


def settings():
    return {"rule": RULE, "guard_rule": GUARD, "cases": list(CASES),
            "baseline_manifest_sha256": BASELINE_SHA, "dark_audit_sha256": AUDIT_SHA,
            "world_seed": startup.SEED, "patch_seed": startup.PATCH, "stop": startup.STOP,
            "models": {k: m.crc for k, m in prior.prior.MODELS.items()},
            "routing": prior.neighbors.routing(prior.ROUTE), "frame_ticks": list(FRAME_TICKS),
            "expected_first_divergence": {"tick": 945, "id": 5, "kind": "growth"},
            "budget": {"traces": 4, "frame_replays": 16, "native_calls": 20,
                       "training_calls": 0, "mutation_calls": 0},
            "role": "selected-world paired diagnostic; no firmware/default promotion"}


def commands():
    return [(name.replace("veto.", "guard."), [part.replace("bin/veto-", "bin/guard-").replace(
             "frames/veto.", "frames/guard.") for part in command]) for name, command in prior.commands()]


def copies():
    result = {"input/native-source.tar.gz": "source.tar.gz",
              "input/prior-CMakeCache.txt": "input/control-CMakeCache.txt",
              "input/control.jsonl.gz": "traces/control.jsonl.gz"}
    result.update({f"models/{name}.tgm": f"models/{name}.tgm" for name in prior.prior.MODELS})
    for tick in FRAME_TICKS:
        for extension in ("json", "rgb565"):
            result[f"input/control.{tick}.{extension}"] = f"frames/control.{tick}.{extension}"
    return result


def native_budget(tick, energy, nodes, stress):
    p = reference.project(tick, energy, nodes, stress)
    result = {"supported": p["supported"], "energy": energy, "stress": stress,
              "peak_stress": stress, "upkeep": (nodes + 7) // 8,
              "dark_steps": p["boundaries"]["dark_steps"],
              "payments": len(p["boundaries"]["maintenance_ticks"]),
              "first_shortage_step": 0, "death_step": 0}
    if p["supported"]:
        result.update(energy=p["final"]["energy"], stress=p["final"]["stress"], peak_stress=p["peak_stress"],
            first_shortage_step=0 if p["first_shortage_tick"] is None else (p["first_shortage_tick"] - tick) // 15,
            death_step=0 if p["death_tick"] is None else (p["death_tick"] - tick) // 15)
    return result


def check_event(event, tick):
    require(event["kind"] in KINDS and not event["invalid"] and
            0 <= event["node"] < 512 and 0 <= event["energy_cost"] <= event["energy"] <= 256 and
            0 <= event["water_cost"] <= event["water"] <= 512, "invalid native guard event")
    before = native_budget(tick, event["energy"], event["nodes_before"], event["stress"])
    after = native_budget(tick, event["energy"] - event["energy_cost"], event["nodes_after"], event["stress"])
    require(event["before"] == before and event["after"] == after, "native/reference forecast differs")
    require(event["denied"] == (after["supported"] and after["death_step"] != 0), "wrong native guard decision")


def accounting_rows(rows, case, *, stop=None, boundaries=None, retain_events=True, growth_vetoes=frozenset()):
    """Validate raw candidates first; omit only denied/uncommitted growth bids.

    Census states, ordinary committed bids and leaf proposals are never rewritten.
    The derived stream can use the existing independent resource/tip reconciler.
    Optional growth_vetoes must be separately verified (tick, lineage) receipts;
    they never rewrite the ordinary guard's decision or denial counters.
    """
    stop = startup.STOP if stop is None else stop
    boundaries = {} if boundaries is None else boundaries
    require(case in CASES and stop > 0 and stop % 15 == 0, "invalid accounting scope")
    output, records, pending, previous = [], [], [], {}
    seen_boundaries, seen_vetoes = set(), set()
    evaluated, denied, counts, retries = Counter(), Counter(), Counter(), set()
    last_tick = -15
    for row in rows:
        tick = row["tick"]
        require(tick == last_tick + 15 and tick <= stop, "missing/reordered guard census")
        if row["type"] in ("bid", "leaf-bid"):
            pending.append(row)
            continue
        require(row["type"] == "world", "unknown guard trace record")
        current = {p["id"]: p for p in row["plants"]}
        require(len(current) == len(row["plants"]), "duplicate lineage")
        removed = set()
        if case == "control":
            require("dark_guard" not in row, "control unexpectedly guarded")
        else:
            audit = row["dark_guard"]
            require(audit["rule"] == GUARD and not audit["overflow"] and len(audit["events"]) <= 3*plant_capacity(row),
                    "wrong/overflowed native guard audit")
            events = {}
            for event in audit["events"]:
                check_event(event, tick)
                require(event["id"] in current and not current[event["id"]]["dead"], "guard acted on absent/dead plant")
                events.setdefault(event["id"], []).append(event)
                evaluated[event["kind"]] += 1
                denied[event["kind"]] += event["denied"]
                label = ("out-of-scope" if not event["after"]["supported"] else
                         "already-fatal" if event["before"]["death_step"] else
                         "newly-fatal" if event["denied"] else
                         "allowed-shortage" if event["after"]["first_shortage_step"] else "allowed-all-paid")
                counts[label] += 1
                key = (event["id"], event["kind"], event["node"])
                counts["denied_retries_same_selected_node"] += event["denied"] and key in retries
                if event["denied"]:
                    retries.add(key)
                else:
                    retries.discard(key)
                if retain_events:
                    records.append({"tick": tick, "sun_phase": row["sun_phase"], "classification": label, **event})
            require(audit["evaluated"] == [evaluated[k] for k in KINDS] and
                    audit["denied"] == [denied[k] for k in KINDS], "guard counters do not reconcile")
            for identity, plant in current.items():
                if plant["dead"] or tick == 0:
                    continue
                old = previous.get(identity)
                values = startup.resources.budget(old, plant, tick)
                if old is not None:
                    reference.prior.check_stress(old, plant, tick, values)
                energy = plant["energy"] + sum(values[f"energy_{k}"] for k in KINDS)
                water = plant["water"] + sum(values[f"water_{k}"] for k in KINDS)
                nodes = 4 if old is None else old["nodes"]
                group = events.get(identity, [])
                order = [dict(renewal=0, growth=1, seeds=2)[e["kind"]] for e in group]
                require(order == sorted(set(order)), "duplicate/reordered expense stage")
                bids = [b for b in pending if b["id"] == identity and b["type"] == "bid"]
                leaves = [b for b in pending if b["id"] == identity and b["type"] == "leaf-bid"]
                winner = max(bids, key=lambda b: b["priority"]) if bids else None
                require(any(e["kind"] == "growth" for e in group) == bool(winner and winner["action"]),
                        "missing/unexpected growth guard event")
                expected_renewal = any(b["action"] == 1 and b["condition"] < 255 and
                                       b["energy"] >= 9 and b["water"] >= 5 for b in leaves)
                require(any(e["kind"] == "renewal" for e in group) == expected_renewal,
                        "missing/unexpected renewal guard event")
                spending = Counter()
                for event in group:
                    kind = event["kind"]
                    forced = kind == "growth" and (tick, identity) in growth_vetoes
                    if forced:
                        require(not event["denied"], "purchase veto duplicates an ordinary denial")
                        seen_vetoes.add((tick, identity))
                    require((event["energy"], event["water"], event["nodes_before"], event["stress"]) ==
                            (energy, water, nodes, plant["stress"]), "wrong pre-expense state")
                    cost = {"growth": startup.resources.ENERGY_COST[plant["species"]] - (plant["vigor"] > 0),
                            "renewal": 9, "seeds": 48}[kind]
                    wet = {"growth": startup.resources.WATER_COST[plant["species"]], "renewal": 5, "seeds": 24}[kind]
                    require((event["energy_cost"], event["water_cost"]) == (cost, wet), "wrong expense cost")
                    added = 0
                    if kind == "growth":
                        require(winner is not None and event["node"] == winner["tip_index"], "guard did not select winning tip")
                        added = int(winner["action"] == 1 and any(c["flags"] & 2 for c in winner["candidates"]))
                        if event["denied"] or forced:
                            removed.add(identity)
                            require(plant["agent"]["decisions"] == (old["agent"]["decisions"] if old else 0),
                                    "denied growth committed a decision")
                    require(event["nodes_after"] == nodes + added, "wrong prospective body")
                    if not (event["denied"] or forced):
                        energy -= cost
                        water -= wet
                        nodes += added
                        spending[kind] += cost
                require(all(spending[k] == values[f"energy_{k}"] for k in KINDS), "guard/actual spending differs")
                require((energy, water, nodes) == (plant["energy"], plant["water"], plant["nodes"]),
                        "guard stage ledger does not telescope")
        for bid in pending:
            if bid["type"] == "bid" and bid["id"] in removed:
                counts["uncommitted_bids_removed"] += 1
            else:
                output.append(bid)
        output.append(row)
        if tick in boundaries:
            boundary = boundaries[tick]
            require(boundary["before"] == row, "guard boundary differs from ordinary census")
            disturbance.validate_boundary(row, boundary["after"], boundary["event"])
            current = {p["id"]: p for p in boundary["after"]["plants"]}
            seen_boundaries.add(tick)
        pending, previous, last_tick = [], current, tick
    require(last_tick == stop and not pending and seen_boundaries == boundaries.keys(), "incomplete guard trace")
    require(seen_vetoes == set(growth_vetoes), "missing purchase veto receipt")
    return output, {"evaluated": dict(evaluated), "denied": dict(denied), "counts": dict(counts), "events": records}


def check_prefix(control, guarded):
    for count, (a, b) in enumerate(zip_longest(control, guarded)):
        require(a is not None and b is not None, "missing guard divergence")
        if a == {k: v for k, v in b.items() if k != "dark_guard"}:
            continue
        require(a["type"] == b["type"] == "world" and a["tick"] == b["tick"] == 945,
                "guard diverged outside declared first expense")
        left = next(p for p in a["plants"] if p["id"] == 5)
        right = next(p for p in b["plants"] if p["id"] == 5)
        require(right["energy"] == left["energy"] + 9 and right["water"] == left["water"] + 5 and
                right["nodes"] == left["nodes"] - 1, "first denial does not isolate growth cost/body")
        denials = [e for e in b["dark_guard"]["events"] if e["denied"]]
        require(len(denials) == 1 and denials[0]["kind"] == "growth" and denials[0]["id"] == 5,
                "unexpected first denied expense")
        return {"matching_records": count, "tick": 945, "control": a, "guard": b}
    raise RuntimeError("guard never diverged")


def population(samples, lineages):
    end = samples[startup.STOP]
    alive = [p for p in end["plants"] if not p["dead"]]
    return {"living": end["living"], "species": dict(Counter(p["species"] for p in alive)),
            "living_founders": [p["id"] for p in alive if not p["parent"]],
            "living_descendants": len([p for p in alive if p["parent"]]),
            "births": end["births"], "deaths": end["deaths"], "seeds_created": end["seeds_created"],
            "seeds_expired": end["seeds_expired"], "seeds_remaining": len(end["seeds"]),
            "maximum_generation": end["max_generation"],
            "death_causes": dict(Counter(p["death_shortage"] for p in lineages if p["death_tick"] is not None)),
            "founders": [{k: p[k] for k in ("id", "species", "death_tick", "death_shortage", "alive_at_end")}
                         for p in lineages if not p["parent"]],
            "exposure_logic_ticks": {label: {"living": sum(r["living"] * 15 for t, r in samples.items() if start <= t < stop),
                "living_descendants": sum(sum(not p["dead"] and p["parent"] > 0 for p in r["plants"]) * 15
                                          for t, r in samples.items() if start <= t < stop)}
                for label, start, stop in (("all", 0, startup.STOP), ("days_4_to_8", 4*startup.DAY, startup.STOP))}}


def write_accounting(path, rows):
    with path.open("xb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as stream:
        for row in rows:
            stream.write((json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode())


def analyze(root):
    matched = prior.check_control(startup.read_trace(root / "traces/control.jsonl.gz"),
                                  startup.read_trace(root / "input/control.jsonl.gz"))
    prefix = check_prefix(startup.read_trace(root / "traces/control.jsonl.gz"), startup.read_trace(root / "traces/guard.jsonl.gz"))
    results, frames = {}, []
    for case in CASES:
        path = root / f"traces/{case}.jsonl.gz"
        require(experiment.digest(path) == experiment.digest(root / f"traces/{case}.repeat.jsonl.gz"), "native trace repeat differs")
        rows, guard = accounting_rows(startup.read_trace(path), case)
        require(rows == list(startup.read_trace(root / f"traces/{case}.accounting.jsonl.gz")), "derived accounting trace differs")
        routed, _ = prior.neighbors.check_routing(startup.read_trace(path), prior.ROUTE)
        result, samples = startup.analyze_trace(root / f"traces/{case}.accounting.jsonl.gz", [])
        # Independent live stress checking also applies to the ordinary control.
        previous = {}
        for tick, row in samples.items():
            for p in row["plants"]:
                old = previous.get(p["id"])
                if tick and old is not None and not p["dead"]:
                    reference.prior.check_stress(old, p, tick, startup.resources.budget(old, p, tick))
            previous = {p["id"]: p for p in row["plants"]}
        results[case] = {"population": population(samples, result["lineages"]), "routing": routed,
            "guard": guard, **{k: result[k] for k in ("counts", "resource_totals", "tip_audit", "quarter_days")},
            "lineages": [{k: v for k, v in p.items() if k != "decisions"} for p in result["lineages"]]}
        for tick in FRAME_TICKS:
            stem = f"{case}.{tick}"
            value = experiment.read_json(root / f"frames/{stem}.json")
            raw = (root / f"frames/{stem}.rgb565").read_bytes()
            require(value.get("focal_policy") == prior.neighbors.routing(prior.ROUTE) and
                    (value.get("dark_guard_rule") == GUARD if case == "guard" else "dark_guard_rule" not in value),
                    "wrong replay guard/routing metadata")
            startup.check_frame(value, samples[tick], prior.prior.MODELS["r2-n"], tick, raw)
            require(value == experiment.read_json(root / f"frames/{stem}.repeat.json") and
                    raw == (root / f"frames/{stem}.repeat.rgb565").read_bytes(), "native frame repeat differs")
            if case == "control":
                require(value == experiment.read_json(root / f"input/control.{tick}.json") and
                        raw == (root / f"input/control.{tick}.rgb565").read_bytes(), "saved control frame changed")
            frames.append({"id": stem, "case": case, "tick": tick, "result": value,
                           "framebuffer": f"frames/{stem}.rgb565", "png": f"frames/{stem}.png"})
    return {"rule": RULE, "settings": settings(), "exact_control_records": matched,
            "first_divergence": prefix, "cases": results, "frames": frames}


def check_inputs(root):
    require(experiment.digest(root / "input/baseline-manifest.json") == BASELINE_SHA and
            experiment.digest(root / "input/dark-budget-summary.json") == AUDIT_SHA, "wrong frozen baseline/audit")
    manifest = experiment.read_json(root / "input/baseline-manifest.json")
    for target, source in copies().items():
        require(experiment.digest(root / target) == manifest["artifacts"][source], "changed frozen input")
    require(experiment.read_json(root / "input/settings.json") == settings(), "protocol settings changed")
    previous = prior.prior.cache_settings(root / "input/prior-CMakeCache.txt")
    for case in CASES:
        cache = prior.prior.cache_settings(root / f"input/{case}-CMakeCache.txt")
        require(cache.pop(OPTION, None) == ("ON" if case == "guard" else "OFF") and cache == previous,
                "unexpected build configuration")
    old, new = (prior.prior.native_hashes(root / n) for n in ("input/native-source.tar.gz", "source.tar.gz"))
    require(new.keys() - old.keys() == {"src/garden_dark_guard.h", "sim/garden_dark_guard.c", "sim/garden_dark_guard_test.c"}
            and old.keys() <= new.keys(), "unexpected native source additions/removals")
    require({n for n in old if old[n] != new[n]} == {
        "src/garden_world.c", "src/garden_world.h", "sim/garden_inspect.c", "sim/garden_replay.c"},
        "unexpected native source edits")
    started = experiment.read_json(root / "started.json")
    require(all(started["sources"].get(n) == sha for n, sha in new.items()) and
            experiment.digest(root / "input/protocol.md") == started["sources"][PROTOCOL], "source/protocol freeze differs")


def check_capture(root):
    capture = experiment.read_json(root / "capture.json")
    require(capture["rule"] == RULE and capture["settings"] == settings() and
            [(c["artifact"], c["command"]) for c in capture["calls"]] == commands(), "wrong native panel")
    for name in capture["artifacts"]:
        gallery.artifact(root, capture, name)
    for target, command in commands():
        require(target in capture["artifacts"] and ("--framebuffer" not in command or command[-1] in capture["artifacts"]),
                "missing native output")
    require(all(experiment.digest(root / n) == sha for n, sha in
                experiment.read_json(root / "started.json")["frozen"].items()), "frozen inputs changed")
    check_inputs(root)
    return capture


def verify(root):
    manifest = experiment.read_json(root / "manifest.json")
    require(manifest["rule"] == RULE and manifest["status"] == "complete", "incomplete dark-guard experiment")
    require(set(manifest["artifacts"]) == {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and
            p != root / "manifest.json"}, "extra/missing artifacts")
    for name in manifest["artifacts"]:
        gallery.artifact(root, manifest, name)
    capture = check_capture(root)
    require(manifest["sources"] == experiment.read_json(root / "started.json")["sources"] and
            experiment.read_json(root / "timings.json")["calls"] == capture["calls"], "provenance differs")
    result = analyze(root)
    require(result == experiment.read_json(root / "results.json"), "dark-guard reanalysis differs")
    print("Verified exact control, native guard decisions, live ledgers, trace repeats and eight repeated frames", flush=True)
    return result


def finish(root):
    require(not (root / "manifest.json").exists() and not (root / "results.json").exists(), "already finalized")
    capture = check_capture(root)
    sources = experiment.source_files()
    require(sources == experiment.read_json(root / "started.json")["sources"], "sources changed during capture")
    begin = time.monotonic()
    for case in CASES:
        rows, _ = accounting_rows(startup.read_trace(root / f"traces/{case}.jsonl.gz"), case)
        write_accounting(root / f"traces/{case}.accounting.jsonl.gz", rows)
    result = analyze(root)
    require(result == analyze(root), "analysis repeat differs")
    for frame in result["frames"]:
        gallery.write_png(root / frame["png"], 240, 240,
            gallery.rgb565be_to_rgb888((root / frame["framebuffer"]).read_bytes()))
    gallery.contact_sheet(root, [[f for f in result["frames"] if f["tick"] == t] for t in FRAME_TICKS])
    require(experiment.source_files() == sources, "sources changed during analysis")
    check_capture(root)
    experiment.write_json(root / "results.json", result)
    experiment.write_json(root / "timings.json", {"analysis_and_repeat_seconds": time.monotonic()-begin,
        "capture_seconds": capture["capture_seconds"], "calls": capture["calls"]})
    artifacts = {str(p.relative_to(root)): experiment.digest(p) for p in root.rglob("*") if p.is_file()}
    experiment.write_json(root / "manifest.json", {"rule": RULE, "status": "complete", "sources": sources,
        "artifacts": artifacts, "artifact_bytes": sum((root / n).stat().st_size for n in artifacts)})
    verify(root)


def collect(baseline, builds, output):
    require(not output.exists() and output.is_relative_to(experiment.ROOT / "artifacts") and
            not any(output.is_relative_to(p) for p in (baseline, *builds.values())), "choose fresh separate output")
    require(experiment.digest(baseline / "manifest.json") == BASELINE_SHA and
            experiment.digest(experiment.ROOT / AUDIT) == AUDIT_SHA, "wrong previous evidence")
    sources = experiment.source_files()
    output.mkdir(parents=True)
    experiment.snapshot_sources(output, sources)
    for name in ("input", "bin", "models", "traces", "frames"):
        (output / name).mkdir()
    for target, source in copies().items():
        shutil.copy2(baseline / source, output / target)
    shutil.copy2(baseline / "manifest.json", output / "input/baseline-manifest.json")
    shutil.copy2(experiment.ROOT / AUDIT, output / "input/dark-budget-summary.json")
    for case, build in builds.items():
        for name in ("inspect", "replay"):
            shutil.copy2(build / f"toy-factory-garden-{name}", output / f"bin/{case}-{name}")
        for name in ("CMakeCache.txt", "build.ninja"):
            shutil.copy2(build / name, output / f"input/{case}-{name}")
    shutil.copy2(experiment.ROOT / PROTOCOL, output / "input/protocol.md")
    experiment.write_json(output / "input/settings.json", settings())
    frozen = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
    experiment.write_json(output / "started.json", {"rule": RULE, "sources": sources, "frozen": frozen})
    begin, timings = time.monotonic(), []
    try:
        check_inputs(output)
        for target, command in commands():
            start = time.monotonic()
            if target.endswith(".gz"):
                with tempfile.TemporaryDirectory(prefix="garden-dark-guard-") as temporary:
                    raw = Path(temporary) / "trace.jsonl"
                    experiment.command_run(command, raw, output, 120)
                    experiment.compress(raw, output / target)
            else:
                experiment.command_run(command, output / target, output, 120)
            timings.append({"artifact": target, "command": command, "seconds": time.monotonic()-start})
            print("Captured", target, flush=True)
        require(experiment.source_files() == sources and all(experiment.digest(output / n) == sha for n, sha in frozen.items()),
                "sources/inputs changed during capture")
        artifacts = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
        experiment.write_json(output / "capture.json", {"rule": RULE, "settings": settings(), "artifacts": artifacts,
            "calls": timings, "capture_seconds": time.monotonic()-begin})
        finish(output)
    except BaseException as error:
        experiment.write_json(output / "failure.json", {"error": str(error), "completed_calls": timings})
        raise


def export(root, prefix, check=False):
    require(not prefix.is_relative_to(root), "cannot export into frozen evidence")
    value = {**verify(root), "manifest_sha256": experiment.digest(root / "manifest.json"),
             "timing": experiment.read_json(root / "timings.json")}
    target, image = prefix.with_name(prefix.name + "-summary.json"), prefix.with_suffix(".png")
    if not check:
        require(not target.exists() and not image.exists(), "export already exists")
        experiment.write_json(target, value)
        shutil.copy2(root / "contact-sheet.png", image)
    require(experiment.read_json(target) == value and experiment.digest(image) == experiment.digest(root / "contact-sheet.png"),
            "portable dark-guard evidence differs")
    print("Portable dark-guard summary and native contact sheet match verified evidence", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT / "artifacts/garden-renewal-seed-veto-v1")
    for case in CASES:
        parser.add_argument(f"--{case}-build", type=Path, default=experiment.ROOT / f"artifacts/build-host-renewal-dark-{case}-docker")
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
        collect(args.baseline.resolve(), {c: getattr(args, c + "_build").resolve() for c in CASES}, args.output.resolve())


if __name__ == "__main__":
    main()
