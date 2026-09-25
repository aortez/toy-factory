#!/usr/bin/env python3
"""Swap one neighbor at a time, using frozen native tools and saved controls."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import shutil
import tempfile
import time

import garden_renewal_swap as prior

startup, experiment, require, gallery = prior.startup, prior.experiment, prior.require, prior.gallery
RULE = "garden-renewal-neighbors-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-neighbors-protocol.md"
BASELINE_SHA = "9f2be4fb09b00d2464273b5a53c20c478de8e39a1e060a2c68e51684a6b4d9dd"
FOCAL = 2
FOUNDERS = {1: ("flower", 3), 2: ("shrub", 8), 3: ("ground-cover", 13),
            4: ("shrub", 18), 5: ("flower", 23)}


@dataclass(frozen=True)
class Case:
    name: str
    override_id: int
    override_model: str = "r2-w"
    background: str = "r2-n"
    reference: bool = False


NEW_CASES = tuple(Case(f"neighbor-{identity}-w", identity) for identity in (1, 3, 4, 5))
CASES = (Case("n-in-n", 2, "r2-n", reference=True), *NEW_CASES,
         Case("n-in-w", 2, "r2-n", "r2-w", reference=True))


def routing(case):
    return {"rule": prior.ROUTING_RULE, "founder": case.override_id,
            "model_crc32": prior.MODELS[case.override_model].crc}


def settings():
    return {"rule": RULE, "baseline_manifest_sha256": BASELINE_SHA,
            "cases": [asdict(c) for c in CASES], "observed_founder": FOCAL,
            "models": {name: m.crc for name, m in prior.MODELS.items()},
            "world_seed": startup.SEED, "patch_seed": startup.PATCH, "stop": startup.STOP,
            "frame_ticks": list(startup.FRAME_TICKS),
            "budget": {"new_traces": 8, "new_frame_replays": 32, "native_calls": 40,
                       "training_calls": 0, "mutation_calls": 0, "reference_replays": 0},
            "reference_caveat": "n-in-w also uses W for descendants; not an all-four-founder factorial endpoint",
            "role": "one inspected world, individual neighbor interventions, ordinary feedback permitted"}


def copies():
    result = {"bin/garden-inspect": "bin/garden-inspect", "bin/garden-replay": "bin/garden-replay",
              "input/native-source.tar.gz": "source.tar.gz", "input/CMakeCache.txt": "input/CMakeCache.txt",
              "input/prior-results.json": "results.json"}
    result.update({f"models/{name}.tgm": f"models/{name}.tgm" for name in prior.MODELS})
    for case in CASES:
        if not case.reference:
            continue
        for suffix in ("", ".repeat"):
            trace = f"traces/{case.name}{suffix}.jsonl.gz"
            result[trace] = trace
            for tick in startup.FRAME_TICKS:
                for extension in ("json", "rgb565"):
                    frame = f"frames/{case.name}.{tick}{suffix}.{extension}"
                    result[frame] = frame
    return result


def commands():
    result = []
    for case in NEW_CASES:
        base = [f"models/{case.background}.tgm", "rainfed-crowded", experiment.NIGHT_POLICY,
                "0x" + startup.SEED, "--leaf-policy", "selective", "--disturbance-seed", "0x" + startup.PATCH,
                "--focal-model", f"models/{case.override_model}.tgm", "--focal-founder", str(case.override_id)]
        for suffix in ("", ".repeat"):
            result.append((f"traces/{case.name}{suffix}.jsonl.gz",
                           ["bin/garden-inspect", *base, "--ecology", "--ticks", str(startup.STOP)]))
        for tick in startup.FRAME_TICKS:
            for suffix in ("", ".repeat"):
                stem = f"frames/{case.name}.{tick}{suffix}"
                result.append((stem + ".json", ["bin/garden-replay", *base, "--ticks", str(tick),
                                               "--framebuffer", stem + ".rgb565"]))
    return result


def check_routing(rows, case):
    counts, bids = Counter(), {}
    for row in rows:
        if row["type"] == "world":
            require(row.get("focal_policy") == routing(case), "wrong neighbor routing configuration")
            if row["tick"] == 0:
                plants = {p["id"]: p for p in row["plants"]}
                require(len(plants) == len(row["plants"]) and set(plants) == set(FOUNDERS), "wrong reset founders")
                for identity, (species, column) in FOUNDERS.items():
                    require(all(plants[identity].get(k) == v for k, v in {
                        "parent": 0, "generation": 0, "species": species, "column": column, "dead": False}.items()),
                        "wrong reset founder identity")
                counts["reset"] += 1
            counts["worlds"] += 1
        elif row["type"] == "bid":
            overridden = row["id"] == case.override_id
            expected = prior.MODELS[case.override_model if overridden else case.background].crc
            require(row.get("controller_model_crc32") == expected, "wrong routed growth bid")
            counts["override_bids" if overridden else "background_bids"] += 1
            if row["id"] == FOCAL:
                require(expected == prior.MODELS["r2-n"].crc, "observed shrub must stay N")
                counts["observed_shrub_bids"] += 1
                bids.setdefault(row["tick"], []).append(row)
        else:
            require(row["type"] == "leaf-bid" and "controller_model_crc32" not in row,
                    "unexpected record or neural leaf routing")
    require(counts["reset"] == 1 and min(counts[k] for k in
            ("override_bids", "background_bids", "observed_shrub_bids")) > 0, "incomplete routing evidence")
    return dict(counts), bids


def recorded_bid(bid):
    """Only the declared route CRC and global pool index are nonsemantic here."""
    return {k: v for k, v in bid.items() if k not in ("controller_model_crc32", "tip_index")}


def physical_winner(bid):
    return tuple(bid[k] for k in ("action", "tissue", "x", "y", "depth"))


def bid_comparison(control, changed):
    result = dict.fromkeys(("first_recorded_sequence_difference", "first_physical_winner_difference",
        "first_extend_winner_difference", "first_tied_winner_difference",
        "first_equal_recorded_bids_different_winner"))
    tied, equivalent = 0, 0
    for tick in sorted(control.keys() | changed.keys()):
        left, right = control.get(tick, []), changed.get(tick, [])
        normalized_left, normalized_right = [recorded_bid(b) for b in left], [recorded_bid(b) for b in right]
        if normalized_left != normalized_right and result["first_recorded_sequence_difference"] is None:
            result["first_recorded_sequence_difference"] = {"tick": tick, "control": left, "case": right}
        if not left or not right:
            continue
        a, b = max(left, key=lambda v: v["priority"]), max(right, key=lambda v: v["priority"])
        if physical_winner(a) == physical_winner(b):
            continue
        ties_a = sum(v["priority"] == a["priority"] for v in left)
        ties_b = sum(v["priority"] == b["priority"] for v in right)
        multiset_equal = sorted(json.dumps(v, sort_keys=True) for v in normalized_left) == sorted(
            json.dumps(v, sort_keys=True) for v in normalized_right)
        event = {"tick": tick, "control_winner": a, "case_winner": b,
                 "control_max_priority_ties": ties_a, "case_max_priority_ties": ties_b,
                 "recorded_bid_multiset_equal": multiset_equal, "control_bids": left, "case_bids": right}
        if result["first_physical_winner_difference"] is None:
            result["first_physical_winner_difference"] = event
        if a["action"] == b["action"] == 1 and result["first_extend_winner_difference"] is None:
            result["first_extend_winner_difference"] = event
        if ties_a > 1 and ties_b > 1:
            tied += 1
            if result["first_tied_winner_difference"] is None:
                result["first_tied_winner_difference"] = event
        if multiset_equal:
            require(ties_a == ties_b and ties_a > 1 and a["priority"] == b["priority"], "inconsistent equal-bid tie")
            equivalent += 1
            if result["first_equal_recorded_bids_different_winner"] is None:
                result["first_equal_recorded_bids_different_winner"] = event
    return {**result, "different_winners_with_ties_on_both_sides": tied,
            "equal_recorded_bidsets_with_different_winners": equivalent}


def seed_events(plants):
    result, previous = [], None
    for tick, plant in sorted(plants.items()):
        if plant is None:
            continue
        if tick and not plant["dead"]:
            require(previous is not None and not previous["dead"], "unobserved focal seed budget")
            budget = startup.resources.budget(previous, plant, tick)
            if budget["energy_seeds"]:
                result.append({"tick": tick, "energy_spent": budget["energy_seeds"],
                    "water_spent": budget["water_seeds"], "energy_before": previous["energy"],
                    "energy_after": plant["energy"], "nodes": plant["nodes"],
                    "flowers": plant["flowers"], "spent_flowers": plant["spent_flowers"]})
        previous = plant
    return result


def first_plant_difference(control, changed, fields):
    for tick in sorted(control.keys() & changed.keys()):
        a, b = control[tick], changed[tick]
        if a is None or b is None:
            if a != b:
                return {"tick": tick, "control_present": a is not None, "case_present": b is not None}
            continue
        differences = {k: {"control": a[k], "case": b[k]} for k in fields if a[k] != b[k]}
        if differences:
            return {"tick": tick, "differences": differences}
    return None


def compare(control, changed):
    a, b = control["plants"], changed["plants"]
    seeds_a = {e["tick"]: e["energy_spent"] for e in control["seed_events"]}
    seeds_b = {e["tick"]: e["energy_spent"] for e in changed["seed_events"]}
    seed_difference = next(({"tick": tick, "control_spent": seeds_a.get(tick, 0), "case_spent": seeds_b.get(tick, 0)}
        for tick in sorted(seeds_a.keys() | seeds_b.keys()) if seeds_a.get(tick, 0) != seeds_b.get(tick, 0)), None)
    return {"first_resource_difference": first_plant_difference(a, b, ("energy", "water", "energy_income", "water_income", "stress", "dead")),
            "first_body_count_difference": first_plant_difference(a, b, ("nodes", "roots", "leaves", "tips", "dead")),
            "first_seed_spending_difference": seed_difference,
            "decisions": bid_comparison(control["bids"], changed["bids"])}


def analyze(root):
    results, surveys, frames, initial = {}, {}, [], None
    old_results = experiment.read_json(root / "input/prior-results.json")["cases"]
    for case in CASES:
        trace = root / f"traces/{case.name}.jsonl.gz"
        require(experiment.digest(trace) == experiment.digest(root / f"traces/{case.name}.repeat.jsonl.gz"), "full trace repeat differs")
        routing_counts, bids = check_routing(startup.read_trace(trace), case)
        result, samples = startup.analyze_trace(trace, [])
        reset = prior.without_routing(samples[0])
        if initial is None:
            initial = reset
        require(reset == initial, "different reset worlds")
        common = {"counts": result["counts"], "resource_totals": result["resource_totals"],
            "tip_audit": result["tip_audit"], "lineages": [{k: v for k, v in p.items() if k != "decisions"}
                for p in result["lineages"]], "quarter_days": result["quarter_days"],
            **prior.focal_summary(result, samples)}
        if case.reference:
            require(all(old_results[case.name][k] == v for k, v in common.items()), "saved reference analysis differs")
        plants = {tick: next((p for p in row["plants"] if p["id"] == FOCAL), None) for tick, row in samples.items()}
        seeds = seed_events(plants)
        require(sum(e["energy_spent"] for e in seeds) == common["focal"]["budgets"]["all"]["energy_seeds"], "seed event ledger differs")
        surveys[case.name] = {"plants": plants, "bids": bids, "seed_events": seeds}
        results[case.name] = {"case": asdict(case), "routing": routing_counts, "seed_events": seeds, **common}
        for tick in startup.FRAME_TICKS:
            stem = f"{case.name}.{tick}"
            value = experiment.read_json(root / f"frames/{stem}.json")
            raw = (root / f"frames/{stem}.rgb565").read_bytes()
            require(value.get("focal_policy") == routing(case), "wrong replay routing")
            startup.check_frame(value, samples[tick], prior.MODELS[case.background], tick, raw)
            require(value == experiment.read_json(root / f"frames/{stem}.repeat.json") and
                    raw == (root / f"frames/{stem}.repeat.rgb565").read_bytes(), "frame repeat differs")
            frames.append({"id": stem, "case": case.name, "tick": tick, "copied_reference": case.reference,
                "result": value, "framebuffer": f"frames/{stem}.rgb565", "png": f"frames/{stem}.png"})
    comparisons = {name: compare(surveys["n-in-n"], survey) for name, survey in surveys.items() if name != "n-in-n"}
    return {"rule": RULE, "settings": settings(), "cases": results, "comparisons_to_n_in_n": comparisons, "frames": frames}


def check_inputs(root):
    require(experiment.digest(root / "input/baseline-manifest.json") == BASELINE_SHA, "wrong frozen swap bundle")
    manifest = experiment.read_json(root / "input/baseline-manifest.json")
    for target, source in copies().items():
        require(experiment.digest(root / target) == manifest["artifacts"][source], "changed copied artifact")
    for name, model in prior.MODELS.items():
        require(startup.pilot.model_crc(root / f"models/{name}.tgm") == model.crc, "changed frozen model")
    require(experiment.read_json(root / "input/settings.json") == settings(), "changed experiment contract")
    native = prior.native_hashes(root / "input/native-source.tar.gz")
    require(native == prior.native_hashes(root / "source.tar.gz"), "native sources changed")
    started = experiment.read_json(root / "started.json")
    require(all(started["sources"].get(n) == sha for n, sha in native.items()) and
            experiment.digest(root / "input/protocol.md") == started["sources"][PROTOCOL], "source/protocol freeze differs")


def check_capture(root):
    capture = experiment.read_json(root / "capture.json")
    require(capture["rule"] == RULE and capture["settings"] == settings() and
            [(c["artifact"], c["command"]) for c in capture["calls"]] == commands(), "wrong captured panel")
    for name in capture["artifacts"]:
        gallery.artifact(root, capture, name)
    for target, command in commands():
        require(target in capture["artifacts"] and ("--framebuffer" not in command or command[-1] in capture["artifacts"]), "missing captured output")
    require(all(experiment.digest(root / n) == sha for n, sha in
        experiment.read_json(root / "started.json")["frozen"].items()), "frozen inputs changed")
    check_inputs(root)
    return capture


def verify(root):
    manifest = experiment.read_json(root / "manifest.json")
    require(manifest["rule"] == RULE and manifest["status"] == "complete", "incomplete neighbors bundle")
    require(set(manifest["artifacts"]) == {str(p.relative_to(root)) for p in root.rglob("*")
            if p.is_file() and p != root / "manifest.json"}, "extra or missing artifacts")
    for name in manifest["artifacts"]:
        gallery.artifact(root, manifest, name)
    capture = check_capture(root)
    require(manifest["sources"] == experiment.read_json(root / "started.json")["sources"] and
            experiment.read_json(root / "timings.json")["calls"] == capture["calls"], "source/call record differs")
    result = analyze(root)
    require(result == experiment.read_json(root / "results.json"), "neighbors reanalysis differs")
    print("Verified four new repeated traces, two saved references, routing, resource/tie audits and 24 repeated frames", flush=True)
    return result


def finish(root):
    require(not (root / "manifest.json").exists() and not (root / "results.json").exists(), "already finalized")
    capture = check_capture(root)
    sources = experiment.source_files()
    require(sources == experiment.read_json(root / "started.json")["sources"], "sources changed during collection")
    begin = time.monotonic()
    result = analyze(root)
    require(result == analyze(root), "repeated analysis differs")
    for frame in result["frames"]:
        gallery.write_png(root / frame["png"], 240, 240,
            gallery.rgb565be_to_rgb888((root / frame["framebuffer"]).read_bytes()))
    gallery.contact_sheet(root, [[f for f in result["frames"] if f["tick"] == t] for t in startup.FRAME_TICKS])
    require(experiment.source_files() == sources, "sources changed during analysis")
    check_capture(root)
    experiment.write_json(root / "results.json", result)
    experiment.write_json(root / "timings.json", {"analysis_and_repeat_seconds": time.monotonic() - begin,
        "capture_seconds": capture["capture_seconds"], "calls": capture["calls"]})
    artifacts = {str(p.relative_to(root)): experiment.digest(p) for p in root.rglob("*") if p.is_file()}
    experiment.write_json(root / "manifest.json", {"rule": RULE, "status": "complete", "sources": sources,
        "artifacts": artifacts, "artifact_bytes": sum((root / n).stat().st_size for n in artifacts)})
    verify(root)


def collect(baseline, output):
    require(not output.exists() and output.is_relative_to(experiment.ROOT / "artifacts") and
            not output.is_relative_to(baseline), "choose fresh separate artifact output")
    require(experiment.digest(baseline / "manifest.json") == BASELINE_SHA, "wrong source bundle")
    sources = experiment.source_files()
    output.mkdir(parents=True)
    experiment.snapshot_sources(output, sources)
    for name in ("input", "bin", "models", "traces", "frames"):
        (output / name).mkdir()
    for target, source in copies().items():
        shutil.copy2(baseline / source, output / target)
    shutil.copy2(baseline / "manifest.json", output / "input/baseline-manifest.json")
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
                with tempfile.TemporaryDirectory(prefix="garden-neighbors-") as temporary:
                    raw = Path(temporary) / "trace.jsonl"
                    experiment.command_run(command, raw, output, 120)
                    experiment.compress(raw, output / target)
            else:
                experiment.command_run(command, output / target, output, 120)
            timings.append({"artifact": target, "command": command, "seconds": time.monotonic() - start})
            print("Captured", target, flush=True)
        require(experiment.source_files() == sources and all(experiment.digest(output / n) == sha for n, sha in frozen.items()), "sources or inputs changed during collection")
        artifacts = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
        experiment.write_json(output / "capture.json", {"rule": RULE, "settings": settings(), "artifacts": artifacts,
            "calls": timings, "capture_seconds": time.monotonic() - begin})
        finish(output)
    except BaseException as error:
        experiment.write_json(output / "failure.json", {"error": str(error), "completed_calls": timings})
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
    require(experiment.read_json(target) == value and experiment.digest(image) == experiment.digest(root / "contact-sheet.png"), "portable evidence differs")
    print("Portable neighbor summary and native contact sheet match verified evidence", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT / "artifacts/garden-renewal-swap-v1")
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
        collect(args.baseline.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
