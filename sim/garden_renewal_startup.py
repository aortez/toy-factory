#!/usr/bin/env python3
"""Explain eight startup days using frozen models and native diagnostic tools."""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import time
import zlib

import garden_renewal_cohorts as prior
import garden_leaf_experiment as leaf
import garden_node_audit as nodes
import garden_resources as resources
import garden_tip_audit as tips

experiment, require, pilot = prior.experiment, prior.require, prior.pilot
gallery = pilot.gallery
RULE = "garden-renewal-startup-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-startup-protocol.md"
INPUTS = {"return": prior.BASELINE_SHA,
          "inspector": "7e2b0136cfc43babd2d8ffd9442fefe6239eaa3a5ce1a73e588df58ddcb7c1ca"}
MODELS = tuple(m for m in prior.MODELS if m.name in ("original", "r2-n", "r2-w"))
SEED, PATCH = "0d983a80", "05d87ca0"
DAY, STEP, STOP = prior.DAY, prior.STEP, 8 * prior.DAY
FRAME_TICKS = (960, 2880, 7680, STOP)
WINDOWS = {"startup_daylight": (0, 960), "first_night": (960, 2865),
           "second_daylight": (2880, 4800), "second_night": (4800, 6705)}
SHORTAGES = {0: "other", 2: "energy", 4: "water", 6: "energy-and-water"}


def settings():
    return {"rule": RULE, "inputs": INPUTS, "models": [dict(m.__dict__) for m in MODELS],
            "world_seed": SEED, "patch_seed": PATCH, "stop": STOP,
            "frame_ticks": list(FRAME_TICKS), "resource_windows": {k: list(v) for k, v in WINDOWS.items()},
            "budget": {"traces": 6, "frame_replays": 24, "native_calls": 30,
                       "training_calls": 0, "mutation_calls": 0},
            "role": "outcome-selected startup explanation, not held-out or causal qualification"}


def copies():
    result = {"bin/garden-inspect": ["inspector", "bin/garden-inspect"],
              "bin/garden-replay": ["return", "bin/garden-replay"],
              "input/native-source.tar.gz": ["return", "input/native-source.tar.gz"],
              "input/CMakeCache.txt": ["return", "input/CMakeCache.txt"]}
    for model in MODELS:
        result[f"models/{model.name}.tgm"] = ["return", f"models/{model.name}.tgm"]
        for schedule in ("review-1", "review-2"):
            result[f"input/{model.name}.{schedule}.json"] = [
                "return", prior.previous.ledger(model, "rr", f"{schedule}.{SEED}")]
    return result


def read_trace(path):
    with gzip.open(path, "rt") as stream:
        for line in stream:
            yield json.loads(line)


def snapshot(row, plant):
    return {"tick": row["tick"], "sun_phase": row["sun_phase"],
            "sun_strength": row["sun_strength"], **plant}


def check_leaf(old, plant):
    before = old["leaf"] if old else {"conditions": [], "restored": 0, "worn": 0}
    expected = (sum(before["conditions"]) + 255 * (plant["leaves"] - (old["leaves"] if old else 0))
                + plant["leaf"]["restored"] - before["restored"]
                - plant["leaf"]["worn"] + before["worn"])
    require(sum(plant["leaf"]["conditions"]) == expected, "leaf condition budget differs")


def check_history(records, samples, trial):
    """Compare only observed events; later deaths are right-censored, not absent."""
    expected = {p["id"]: p for p in trial["lineages"] if p["birth_tick"] <= STOP}
    require(set(records) == set(expected), "startup lineage set differs from saved history")
    for identity, record in records.items():
        p = expected[identity]
        require(all(record[k] == p[k] for k in ("id", "parent", "birth_tick", "generation", "column"))
                and record["species"] == pilot.SPECIES[p["species"]], "startup lineage identity differs")
        death = p["death_tick"] if p["death_tick"] is not None and p["death_tick"] <= STOP else None
        require(record["death_tick"] == death and not (death is not None and p["environmental_death"]),
                "startup mortality differs or unexpected patch death")
    checked = 0
    for reference in trial["checkpoints"]:
        if reference["tick"] > STOP:
            continue
        sample = samples[reference["tick"]]
        require(all(sample[k] == reference[k] for k in ("hash", "living", "nodes", "births", "deaths"))
                and len(sample["seeds"]) == reference["seeds"], "saved startup checkpoint differs")
        checked += 1
    require(checked > 0, "no saved startup checkpoint")
    return checked


def analyze_trace(path, trials):
    previous, records, pending, leaf_pending = {}, {}, {}, {}
    samples, counts, all_budgets = {}, Counter(), Counter()
    last_tick = -STEP
    for row in read_trace(path):
        tick = row["tick"]
        require(tick == last_tick + STEP and tick <= STOP, "missing or reordered ecology step")
        if row["type"] in ("bid", "leaf-bid"):
            target = pending if row["type"] == "bid" else leaf_pending
            target.setdefault(row["id"], []).append(row)
            counts[row["type"]] += 1
            continue
        require(row["type"] == "world", "unexpected trace record or disturbance")
        # This pinned inspector names the veto on bids, not on world records.
        # The frozen command/binary and independent replays also bind the policy.
        leaf.check_identity(row, "selective", 512)
        require(row["sun_phase"] == (64 + tick // STEP) % 256, "wrong sun phase")
        nodes.ownership(row, 512)
        samples[tick] = row
        counts["world_samples"] += 1
        current = {p["id"]: p for p in row["plants"]}
        for identity, plant in current.items():
            old = previous.get(identity)
            if identity not in records:
                require(not plant["dead"] and ((tick == 0) == (plant["parent"] == 0)), "invalid birth")
                records[identity] = {k: plant[k] for k in ("id", "parent", "species", "generation", "column")}
                records[identity].update(birth_tick=tick, death_tick=None, death_shortage=None,
                    marks={"birth": snapshot(row, plant)}, budgets={k: Counter() for k in ("all", *WINDOWS)},
                    daily_budgets={str(d): Counter() for d in range(8)}, decisions=[], leaf_bids=Counter())
            record = records[identity]
            require(old is not None or record["birth_tick"] == tick, "reused lineage identity")
            bids, leaves = pending.pop(identity, []), leaf_pending.pop(identity, [])
            require(len(leaves) <= 1, "multiple leaf observations for one plant/step")
            old_leaf = old["leaf"] if old else {}
            require(all(b["action"] in (0, 1) for b in leaves) and
                    plant["leaf"]["observations"] - old_leaf.get("observations", 0) == len(leaves) and
                    plant["leaf"]["proposals"] - old_leaf.get("proposals", 0) == sum(b["action"] == 1 for b in leaves),
                    "unreconciled leaf observation/proposal")
            record["leaf_bids"].update(observations=len(leaves), renew_proposals=sum(b["action"] == 1 for b in leaves))
            for b in bids:
                require(b.get("probe") == experiment.NIGHT_PROBE and b["sun_phase"] == row["sun_phase"]
                        and b["action"] == (0 if row["sun_phase"] >= 128 else b["probe_original_action"])
                        and b["action"] == b["original_action"] and b["priority"] == b["original_priority"],
                        "unexpected growth override or night veto")
            delta = plant["agent"]["decisions"] - (old["agent"]["decisions"] if old else 0)
            require(delta == bool(bids), "unreconciled committed decision")
            if bids:
                winner = max(bids, key=lambda b: b["priority"])
                require(all(winner[k] == plant["agent"]["last_" + k]
                            for k in ("priority", "action", "tissue", "x", "y")), "wrong winning bid")
                require(all((b["energy"], b["water"]) == (winner["energy"], winner["water"]) for b in bids),
                        "bids observed different stores")
                before_nodes = old["nodes"] if old else 4
                record["decisions"].append({"tick": tick, "winner": winner,
                    "nodes_added": plant["nodes"] - before_nodes,
                    "tips_after": plant["tips"], "bids": len(bids)})
                counts["committed_decisions"] += 1
            if plant["dead"]:
                require(not bids and not leaves, "dead plant acted")
                if record["death_tick"] is None:
                    require(old is not None and not old["dead"], "unobserved death")
                    record["death_tick"] = tick
                    record["death_shortage"] = SHORTAGES[plant["flags"] & 6]
                    record["marks"]["death"] = snapshot(row, plant)
                    counts["terminal_steps_not_reconstructed"] += 1
                continue
            require(record["death_tick"] is None, "dead plant revived")
            record["marks"]["last_living"] = snapshot(row, plant)
            for name, condition in (("first_energy_shortage", plant["flags"] & 2),
                                    ("first_water_shortage", plant["flags"] & 4),
                                    ("first_root_extension", plant["agent"]["root_extend"] > 0),
                                    ("first_shoot_extension", plant["agent"]["shoot_extend"] > 0),
                                    ("first_active_leaf", plant["active_leaves"] > 0),
                                    ("tipless", plant["tips"] == 0)):
                if condition and name not in record["marks"]:
                    record["marks"][name] = snapshot(row, plant)
            if tick:
                values = resources.budget(old, plant, tick)
                check_leaf(old, plant)
                counts["checked_live_steps"] += 1
                all_budgets.update(values)
                record["budgets"]["all"].update(values)
                record["daily_budgets"][str((tick - 1) // DAY)].update(values)
                for name, (start, end) in WINDOWS.items():
                    if start < tick <= end:
                        record["budgets"][name].update(values)
        require(not pending and not leaf_pending, "bid without census plant")
        require(all(previous[i]["dead"] for i in previous.keys() - current.keys()), "living plant disappeared")
        if tick:
            require(row["births"] - samples[last_tick]["births"] == len(current.keys() - previous.keys()),
                    "birth counter mismatch")
            require(row["deaths"] == counts["terminal_steps_not_reconstructed"], "death counter mismatch")
        previous, last_tick = current, tick
    require(last_tick == STOP and not pending and not leaf_pending, "truncated trace")
    checked = [check_history(records, samples, trial) for trial in trials]
    # The existing tip reconciler is independent of the resource accounting.
    tip_result = tips.analyze_stream((json.dumps(r) for r in read_trace(path) if r["type"] != "leaf-bid"), STOP, DAY, 512)
    require(tip_result["totals"]["committed"] == counts["committed_decisions"], "tip/decision totals differ")
    for identity, record in records.items():
        record["alive_at_end"] = identity in previous and not previous[identity]["dead"]
    return {"counts": dict(counts), "resource_totals": dict(all_budgets), "saved_checkpoints_checked": checked,
            "lineages": list(records.values()), "tip_audit": tip_result,
            "quarter_days": [samples[t] for t in range(0, STOP + 1, DAY // 4)]}, samples


def check_frame(value, sample, model, tick, raw):
    expected = {"schema_version": 1, "scenario": "rainfed-crowded", "seed": SEED,
                "policy": experiment.NIGHT_POLICY, "model_crc32": model.crc,
                "node_capacity": 512, "seed_dispersal": "wide-v1", "water_uptake": "headroom-v1",
                "leaf_policy": "selective", "leaf_environment": "leaf-maintenance-v1",
                "disturbance_protocol": "patch-death-v1", "disturbance_seed": PATCH, "tick": tick,
                "plant_slots": len(sample["plants"]), "seed_bank": len(sample["seeds"]),
                **{k: sample[k] for k in ("hash", "living", "nodes", "births", "deaths", "sun_phase",
                                         "sun_strength", "rain_rate", "rain_deposited", "rain_runoff", "moisture")}}
    require(all(value.get(k) == v for k, v in expected.items()), "untraced replay differs from trace")
    require(len(raw) == gallery.FRAME_BYTES and f"{zlib.crc32(raw):08x}" == value["framebuffer_crc32"],
            "framebuffer CRC or size differs")


def analyze(root):
    models, frames = {}, []
    for model in MODELS:
        trace = root / "traces" / f"{model.name}.jsonl.gz"
        require(experiment.digest(trace) == experiment.digest(root / "traces" / f"{model.name}.repeat.jsonl.gz"),
                "full native trace repeat differs")
        trials = [experiment.read_json(root / "input" / f"{model.name}.{label}.json") for label in ("review-1", "review-2")]
        for trial, patch in zip(trials, (PATCH, "b69a372e")):
            prior.previous.checked_trial(trial, model, SEED, patch)
        result, samples = analyze_trace(trace, trials)
        models[model.name] = {"model_crc32": model.crc, **result}
        for tick in FRAME_TICKS:
            stem = f"{model.name}.{tick}"
            value = experiment.read_json(root / "frames" / f"{stem}.json")
            raw = (root / "frames" / f"{stem}.rgb565").read_bytes()
            check_frame(value, samples[tick], model, tick, raw)
            require(value == experiment.read_json(root / "frames" / f"{stem}.repeat.json")
                    and raw == (root / "frames" / f"{stem}.repeat.rgb565").read_bytes(), "native frame repeat differs")
            frames.append({"id": stem, "model": model.name, "tick": tick, "result": value,
                           "framebuffer": f"frames/{stem}.rgb565", "png": f"frames/{stem}.png"})
    initial = models[MODELS[0].name]["quarter_days"][0]
    require(all(m["quarter_days"][0] == initial for m in models.values()), "different reset worlds")
    return {"rule": RULE, "settings": settings(), "models": models, "frames": frames}


def check_inputs(root):
    manifests = {}
    for name, sha in INPUTS.items():
        path = root / "input" / f"{name}-manifest.json"
        require(experiment.digest(path) == sha, "changed pinned manifest")
        manifests[name] = experiment.read_json(path)
    for dest, (name, src) in copies().items():
        require(experiment.digest(root / dest) == manifests[name]["artifacts"][src], "changed frozen input")
    for name in ("bin/garden-replay", "input/CMakeCache.txt"):
        require(manifests["return"]["artifacts"][name] == manifests["inspector"]["artifacts"][name],
                "inspector/replayer build mismatch")
    with tarfile.open(root / "input/native-source.tar.gz") as archive:
        for name, sha in manifests["inspector"]["sources"].items():
            if name.endswith((".c", ".h")):
                with archive.extractfile(name) as stream:
                    require(hashlib.sha256(stream.read()).hexdigest() == sha, "native source provenance differs")
    for model in MODELS:
        require(pilot.model_crc(root / "models" / f"{model.name}.tgm") == model.crc, "changed frozen model")
    require(experiment.read_json(root / "input/settings.json") == settings(), "changed diagnostic contract")


def commands():
    result = []
    for model in MODELS:
        base = [f"models/{model.name}.tgm", "rainfed-crowded", experiment.NIGHT_POLICY, "0x" + SEED,
                "--leaf-policy", "selective", "--disturbance-seed", "0x" + PATCH]
        for repeat in (False, True):
            suffix = ".repeat" if repeat else ""
            result.append((f"traces/{model.name}{suffix}.jsonl.gz",
                           ["bin/garden-inspect", *base, "--ecology", "--ticks", str(STOP)]))
        for tick in FRAME_TICKS:
            for repeat in (False, True):
                stem = f"frames/{model.name}.{tick}" + (".repeat" if repeat else "")
                result.append((stem + ".json", ["bin/garden-replay", *base, "--ticks", str(tick),
                                               "--framebuffer", stem + ".rgb565"]))
    return result


def check_capture(root):
    capture = experiment.read_json(root / "capture.json")
    require(capture["rule"] == RULE and capture["settings"] == settings() and
            [(c["artifact"], c["command"]) for c in capture["calls"]] == commands(), "wrong captured panel")
    for name in capture["artifacts"]:
        gallery.artifact(root, capture, name)
    for target, command in commands():
        require(target in capture["artifacts"], "missing captured output")
        if "--framebuffer" in command:
            require(command[-1] in capture["artifacts"], "missing captured framebuffer")
    check_inputs(root)
    started = experiment.read_json(root / "started.json")
    require(all(experiment.digest(root / n) == sha for n, sha in started["frozen"].items()), "capture inputs changed")
    return capture


def verify(root):
    manifest = experiment.read_json(root / "manifest.json")
    require(manifest["rule"] == RULE and manifest["status"] == "complete" and manifest["copied"] == copies(),
            "wrong or incomplete startup bundle")
    require(set(manifest["artifacts"]) == {str(p.relative_to(root)) for p in root.rglob("*")
            if p.is_file() and p != root / "manifest.json"}, "extra or missing artifacts")
    for name in manifest["artifacts"]:
        gallery.artifact(root, manifest, name)
    check_inputs(root)
    capture = check_capture(root)
    started = experiment.read_json(root / "started.json")
    require(started["sources"] == manifest["sources"] and all(experiment.digest(root / n) == sha
            for n, sha in started["frozen"].items()) and
            experiment.digest(root / "input/protocol.md") == manifest["sources"][PROTOCOL], "source/input freeze differs")
    timings = experiment.read_json(root / "timings.json")
    require(timings["calls"] == capture["calls"], "native call budget differs")
    if "analysis_sources" in manifest:
        analysis = experiment.read_json(root / "analysis/started.json")
        require(analysis["sources"] == manifest["analysis_sources"] and
                analysis["capture_sha256"] == experiment.digest(root / "capture.json") and
                analysis["sources"][PROTOCOL] == manifest["sources"][PROTOCOL], "analysis revision changed capture/protocol")
    result = analyze(root)
    require(result == experiment.read_json(root / "results.json"), "startup reanalysis differs")
    print("Verified 3 startup traces and exact repeats, saved history prefixes and 12 repeated native frames", flush=True)
    return result


def finish(root, *, recovered=False):
    """Offline analysis can recover a sealed capture without spending more native calls."""
    require(not (root / "manifest.json").exists() and not (root / "results.json").exists(), "already completed or partly finalized")
    capture = check_capture(root)
    sources = experiment.source_files()
    if recovered:
        require((root / "failure.json").is_file(), "recovery requires a recorded analysis failure")
        (root / "analysis").mkdir()
        experiment.snapshot_sources(root / "analysis", sources)
        experiment.write_json(root / "analysis/started.json", {"sources": sources,
            "capture_sha256": experiment.digest(root / "capture.json"), "native_calls": 0,
            "reason": "Validate the pinned inspector's existing bid-level policy metadata, not absent world-level metadata."})
    else:
        require(sources == experiment.read_json(root / "started.json")["sources"], "sources changed during collection")
    begin = time.monotonic()
    result = analyze(root)
    require(result == analyze(root), "repeated analysis differs")
    for frame in result["frames"]:
        gallery.write_png(root / frame["png"], 240, 240,
                          gallery.rgb565be_to_rgb888((root / frame["framebuffer"]).read_bytes()))
    gallery.contact_sheet(root, [[f for f in result["frames"] if f["tick"] == t] for t in FRAME_TICKS])
    require(experiment.source_files() == sources, "sources changed during analysis")
    check_capture(root)
    experiment.write_json(root / "results.json", result)
    experiment.write_json(root / "timings.json", {"analysis_and_repeat_seconds": time.monotonic() - begin,
        "capture_seconds": capture["capture_seconds"], "calls": capture["calls"],
        "timing_note": capture.get("timing_note"), "recovery_native_calls": 0})
    artifacts = {str(p.relative_to(root)): experiment.digest(p) for p in root.rglob("*") if p.is_file()}
    manifest = {"rule": RULE, "status": "complete", "sources": experiment.read_json(root / "started.json")["sources"],
        "copied": copies(), "artifacts": artifacts, "artifact_bytes": sum((root / n).stat().st_size for n in artifacts)}
    if recovered:
        manifest["analysis_sources"] = sources
    experiment.write_json(root / "manifest.json", manifest)
    verify(root)


def collect(baseline, inspector, output):
    require(not output.exists() and output.is_relative_to(experiment.ROOT / "artifacts") and
            not any(output.is_relative_to(p) for p in (baseline, inspector)), "choose fresh separate artifact output")
    for name, path in (("return", baseline), ("inspector", inspector)):
        require(experiment.digest(path / "manifest.json") == INPUTS[name], "wrong source bundle")
    sources = experiment.source_files()
    output.mkdir(parents=True)
    experiment.snapshot_sources(output, sources)
    for name in ("input", "bin", "models", "traces", "frames"):
        (output / name).mkdir()
    roots = {"return": baseline, "inspector": inspector}
    for dest, (name, src) in copies().items():
        shutil.copy2(roots[name] / src, output / dest)
    for name, path in roots.items():
        shutil.copy2(path / "manifest.json", output / "input" / f"{name}-manifest.json")
    shutil.copy2(experiment.ROOT / PROTOCOL, output / "input/protocol.md")
    experiment.write_json(output / "input/settings.json", settings())
    check_inputs(output)
    frozen = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
    experiment.write_json(output / "started.json", {"rule": RULE, "sources": sources, "frozen": frozen})
    begin, timings = time.monotonic(), []
    try:
        for target, command in commands():
            start = time.monotonic()
            if target.endswith(".gz"):
                with tempfile.TemporaryDirectory(prefix="garden-startup-") as temporary:
                    raw = Path(temporary) / "trace.jsonl"
                    experiment.command_run(command, raw, output, 120)
                    experiment.compress(raw, output / target)
            else:
                experiment.command_run(command, output / target, output, 120)
            timings.append({"artifact": target, "command": command, "seconds": time.monotonic() - start})
            print("Captured", target, flush=True)
        require(experiment.source_files() == sources and all(experiment.digest(output / n) == sha for n, sha in frozen.items()),
                "sources or inputs changed during collection")
        artifacts = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
        experiment.write_json(output / "capture.json", {"rule": RULE, "settings": settings(), "artifacts": artifacts,
            "calls": timings, "capture_seconds": time.monotonic() - begin})
        finish(output)
    except BaseException as error:
        experiment.write_json(output / "failure.json", {"error": str(error)})
        raise


def export(root, prefix, check=False):
    require(not prefix.is_relative_to(root), "cannot export into frozen evidence")
    result = verify(root)
    value = {**result, "manifest_sha256": experiment.digest(root / "manifest.json"),
             "timing": experiment.read_json(root / "timings.json")}
    target, image = prefix.with_name(prefix.name + "-summary.json"), prefix.with_suffix(".png")
    if not check:
        experiment.write_json(target, value)
        require(not image.exists(), "image export already exists")
        shutil.copy2(root / "contact-sheet.png", image)
    require(experiment.read_json(target) == value and experiment.digest(image) == experiment.digest(root / "contact-sheet.png"),
            "portable startup evidence differs")
    print("Portable startup summary and native contact sheet match verified evidence", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT / "artifacts/garden-renewal-return-v1")
    parser.add_argument("--inspector-bundle", type=Path, default=experiment.ROOT / "artifacts/garden-renewal-stalls-v1")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--finish-captured", action="store_true", help="Offline recovery of an intact sealed capture; no native calls")
    parser.add_argument("--export", type=Path)
    parser.add_argument("--check-export", type=Path)
    args = parser.parse_args()
    require(not (args.export and args.check_export) and (args.verify or not (args.export or args.check_export)), "export requires verify")
    require(not args.finish_captured or not (args.verify or args.export or args.check_export), "recovery cannot be combined with verification/export")
    if args.finish_captured:
        finish(args.output.resolve(), recovered=True)
    elif args.export or args.check_export:
        export(args.output.resolve(), (args.export or args.check_export).resolve(), bool(args.check_export))
    elif args.verify:
        verify(args.output.resolve())
    else:
        collect(args.baseline.resolve(), args.inspector_bundle.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
