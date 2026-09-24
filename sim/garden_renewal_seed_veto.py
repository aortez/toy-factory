#!/usr/bin/env python3
"""Fixed fourth-seed counterfactual, retaining exact native controls and repeats."""
from __future__ import annotations

import argparse
from itertools import zip_longest
from pathlib import Path
import shutil
import tempfile
import time

import garden_renewal_neighbors as neighbors

prior, startup = neighbors.prior, neighbors.startup
experiment, require, gallery = neighbors.experiment, neighbors.require, neighbors.gallery
RULE = "garden-renewal-seed-veto-v1"
VETO_RULE = "founder-2-second-day-three-seeds-v1"
OPTION = "TOY_FACTORY_GARDEN_FOCAL_SEED_VETO:BOOL"
BASELINE_SHA = "ca91af24f73667e34f686d6a97ce0a5613b94f9f0aea55f5be7dffe7b41fbdcc"
PROTOCOL = "benchmarks/garden-longevity/renewal-seed-veto-protocol.md"
CASES = ("control", "veto")
ROUTE = neighbors.Case("neighbor-5-w", 5)
FRAME_TICKS = (4800, 6720, 7680, startup.STOP)
FIRST_VETO = 4620


def settings():
    return {"rule": RULE, "veto_rule": VETO_RULE, "baseline_manifest_sha256": BASELINE_SHA,
            "cases": list(CASES), "routing": neighbors.routing(ROUTE),
            "models": {k: m.crc for k, m in prior.MODELS.items()},
            "observed_founder": 2, "daylight_interval": [2880, 4800], "purchase_limit": 3,
            "world_seed": startup.SEED, "patch_seed": startup.PATCH, "stop": startup.STOP,
            "frame_ticks": list(FRAME_TICKS), "expected_first_veto": FIRST_VETO,
            "budget": {"traces": 4, "frame_replays": 16, "native_calls": 20,
                       "training_calls": 0, "mutation_calls": 0},
            "role": "single-world purchase suppression with ordinary downstream feedback"}


def copies():
    result = {"input/native-source.tar.gz": "source.tar.gz",
              "input/prior-CMakeCache.txt": "input/CMakeCache.txt",
              "input/prior-results.json": "results.json",
              "input/control.jsonl.gz": "traces/neighbor-5-w.jsonl.gz"}
    result.update({f"models/{name}.tgm": f"models/{name}.tgm" for name in prior.MODELS})
    for tick in (7680, startup.STOP):
        for extension in ("json", "rgb565"):
            result[f"input/control.{tick}.{extension}"] = f"frames/neighbor-5-w.{tick}.{extension}"
    return result


def commands():
    result = []
    base = ["models/r2-n.tgm", "rainfed-crowded", experiment.NIGHT_POLICY,
            "0x" + startup.SEED, "--leaf-policy", "selective", "--disturbance-seed", "0x" + startup.PATCH,
            "--focal-model", "models/r2-w.tgm", "--focal-founder", "5"]
    for case in CASES:
        for suffix in ("", ".repeat"):
            result.append((f"traces/{case}{suffix}.jsonl.gz",
                [f"bin/{case}-inspect", *base, "--ecology", "--ticks", str(startup.STOP)]))
        for tick in FRAME_TICKS:
            for suffix in ("", ".repeat"):
                stem = f"frames/{case}.{tick}{suffix}"
                result.append((stem + ".json", [f"bin/{case}-replay", *base, "--ticks", str(tick),
                                               "--framebuffer", stem + ".rgb565"]))
    return result


def without_veto(row):
    return {k: v for k, v in row.items() if k != "seed_veto_rule"}


def check_metadata(rows, case):
    count = 0
    for row in rows:
        tagged = case == "veto" and row["type"] == "world"
        require((row.get("seed_veto_rule") == VETO_RULE) if tagged else "seed_veto_rule" not in row,
                "wrong veto metadata")
        count += int(tagged)
    return count


def check_control(actual, expected):
    count = 0
    for a, b in zip_longest(actual, expected):
        require(a is not None and b is not None and a == b, f"rebuilt control changed at record {count}")
        count += 1
    require(count > 0, "empty control")
    return count


def check_prefix(control, veto):
    count = 0
    for a, b in zip_longest(control, veto):
        require(a is not None and b is not None, "missing first veto")
        if a != without_veto(b):
            require(a["type"] == b["type"] == "world" and a["tick"] == b["tick"] == FIRST_VETO,
                    "intervention diverged before/after the declared fourth purchase")
            left = next(p for p in a["plants"] if p["id"] == 2)
            right = next(p for p in b["plants"] if p["id"] == 2)
            require(right["energy"] - left["energy"] == 48 and right["water"] - left["water"] == 24 and
                    left["spent_flowers"] == 4 and right["spent_flowers"] == 3 and
                    left["reproduction_cooldown"] == 16 and right["reproduction_cooldown"] == 0,
                    "first veto does not isolate the seed debit")
            return {"matching_records": count, "tick": FIRST_VETO, "control": a, "veto": b}
        count += 1
    raise RuntimeError("no purchase suppressed")


def analyze(root):
    old = experiment.read_json(root / "input/prior-results.json")["cases"][ROUTE.name]
    control_path, veto_path = (root / f"traces/{c}.jsonl.gz" for c in CASES)
    matched = check_control(startup.read_trace(control_path), startup.read_trace(root / "input/control.jsonl.gz"))
    prefix = check_prefix(startup.read_trace(control_path), startup.read_trace(veto_path))
    results, surveys, frames = {}, {}, []
    for case in CASES:
        trace = root / f"traces/{case}.jsonl.gz"
        require(experiment.digest(trace) == experiment.digest(root / f"traces/{case}.repeat.jsonl.gz"), "trace repeat differs")
        tagged = check_metadata(startup.read_trace(trace), case)
        routed, bids = neighbors.check_routing(startup.read_trace(trace), ROUTE)
        result, samples = startup.analyze_trace(trace, [])
        common = {"counts": result["counts"], "resource_totals": result["resource_totals"],
            "tip_audit": result["tip_audit"], "lineages": [{k: v for k, v in p.items() if k != "decisions"}
                for p in result["lineages"]], "quarter_days": result["quarter_days"],
            **prior.focal_summary(result, samples)}
        if case == "control":
            require(all(old[k] == v for k, v in common.items()), "saved control analysis differs")
        plants = {t: next((p for p in s["plants"] if p["id"] == 2), None) for t, s in samples.items()}
        seeds = neighbors.seed_events(plants)
        require(sum(e["energy_spent"] for e in seeds) == common["focal"]["budgets"]["all"]["energy_seeds"], "seed ledger differs")
        daylight = [e["tick"] for e in seeds if 2880 <= e["tick"] < 4800]
        require(daylight == ([3720, 4020, 4260, 4620] if case == "control" else [3720, 4020, 4260]),
                "daylight purchases violate the scoped counterfactual")
        results[case] = {**common, "routing": routed, "veto_tagged_worlds": tagged, "seed_events": seeds,
            "inspection_checkpoints": {str(t): None if plants[t] is None else startup.snapshot(samples[t], plants[t])
                for t in (2880, 4245, 4260, 4605, 4620, 4800, 6420, 6600, 6720, 6840, 7140, 7680, startup.STOP)}}
        surveys[case] = {"plants": plants, "bids": bids, "seed_events": seeds}
        for tick in FRAME_TICKS:
            stem = f"{case}.{tick}"
            value = experiment.read_json(root / f"frames/{stem}.json")
            raw = (root / f"frames/{stem}.rgb565").read_bytes()
            require(value.get("focal_policy") == neighbors.routing(ROUTE), "wrong replay route")
            require(value.get("seed_veto_rule") == VETO_RULE if case == "veto" else "seed_veto_rule" not in value,
                    "wrong replay veto metadata")
            startup.check_frame(value, samples[tick], prior.MODELS["r2-n"], tick, raw)
            require(value == experiment.read_json(root / f"frames/{stem}.repeat.json") and
                    raw == (root / f"frames/{stem}.repeat.rgb565").read_bytes(), "frame repeat differs")
            if case == "control" and tick in (7680, startup.STOP):
                require(value == experiment.read_json(root / f"input/control.{tick}.json") and
                        raw == (root / f"input/control.{tick}.rgb565").read_bytes(), "saved control frame changed")
            frames.append({"id": stem, "case": case, "tick": tick, "result": value,
                           "framebuffer": f"frames/{stem}.rgb565", "png": f"frames/{stem}.png"})
    return {"rule": RULE, "settings": settings(), "cases": results, "frames": frames,
            "exact_control_records": matched, "first_divergence": prefix,
            "comparison": neighbors.compare(surveys["control"], surveys["veto"])}


def check_inputs(root):
    require(experiment.digest(root / "input/baseline-manifest.json") == BASELINE_SHA, "wrong neighbor baseline")
    manifest = experiment.read_json(root / "input/baseline-manifest.json")
    for target, source in copies().items():
        require(experiment.digest(root / target) == manifest["artifacts"][source], "changed frozen input")
    for name, model in prior.MODELS.items():
        require(startup.pilot.model_crc(root / f"models/{name}.tgm") == model.crc, "changed model identity")
    require(experiment.read_json(root / "input/settings.json") == settings(), "changed protocol settings")
    previous = prior.cache_settings(root / "input/prior-CMakeCache.txt")
    for case in CASES:
        cache = prior.cache_settings(root / f"input/{case}-CMakeCache.txt")
        require(cache.pop(OPTION, None) == ("ON" if case == "veto" else "OFF") and cache == previous,
                "unexpected build configuration")
    old, new = prior.native_hashes(root / "input/native-source.tar.gz"), prior.native_hashes(root / "source.tar.gz")
    require(new.keys() - old.keys() == {"sim/garden_seed_veto_test.c"} and old.keys() <= new.keys(),
            "unexpected native source additions/removals")
    require({n for n in old if old[n] != new[n]} == {
        "src/garden_world.c", "src/garden_world.h", "sim/garden_inspect.c", "sim/garden_replay.c"},
        "unexpected native source changes")
    started = experiment.read_json(root / "started.json")
    require(all(started["sources"].get(n) == sha for n, sha in new.items()) and
            experiment.digest(root / "input/protocol.md") == started["sources"][PROTOCOL], "source/protocol freeze differs")


def check_capture(root):
    capture = experiment.read_json(root / "capture.json")
    require(capture["rule"] == RULE and capture["settings"] == settings() and
            [(c["artifact"], c["command"]) for c in capture["calls"]] == commands(), "wrong fixed panel")
    for name in capture["artifacts"]:
        gallery.artifact(root, capture, name)
    for target, command in commands():
        require(target in capture["artifacts"] and ("--framebuffer" not in command or command[-1] in capture["artifacts"]), "missing output")
    require(all(experiment.digest(root / n) == sha for n, sha in
        experiment.read_json(root / "started.json")["frozen"].items()), "frozen inputs changed")
    check_inputs(root)
    return capture


def verify(root):
    manifest = experiment.read_json(root / "manifest.json")
    require(manifest["rule"] == RULE and manifest["status"] == "complete", "incomplete counterfactual")
    require(set(manifest["artifacts"]) == {str(p.relative_to(root)) for p in root.rglob("*")
            if p.is_file() and p != root / "manifest.json"}, "extra/missing artifacts")
    for name in manifest["artifacts"]:
        gallery.artifact(root, manifest, name)
    capture = check_capture(root)
    require(manifest["sources"] == experiment.read_json(root / "started.json")["sources"] and
            experiment.read_json(root / "timings.json")["calls"] == capture["calls"], "provenance differs")
    result = analyze(root)
    require(result == experiment.read_json(root / "results.json"), "reanalysis differs")
    print("Verified exact old control, fourth-purchase isolation, routing, resources and eight repeated native frames", flush=True)
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
    gallery.contact_sheet(root, [[f for f in result["frames"] if f["tick"] == t] for t in FRAME_TICKS])
    require(experiment.source_files() == sources, "sources changed during analysis")
    check_capture(root)
    experiment.write_json(root / "results.json", result)
    experiment.write_json(root / "timings.json", {"analysis_and_repeat_seconds": time.monotonic() - begin,
        "capture_seconds": capture["capture_seconds"], "calls": capture["calls"]})
    artifacts = {str(p.relative_to(root)): experiment.digest(p) for p in root.rglob("*") if p.is_file()}
    experiment.write_json(root / "manifest.json", {"rule": RULE, "status": "complete", "sources": sources,
        "artifacts": artifacts, "artifact_bytes": sum((root / n).stat().st_size for n in artifacts)})
    verify(root)


def collect(baseline, builds, output):
    require(not output.exists() and output.is_relative_to(experiment.ROOT / "artifacts") and
            not any(output.is_relative_to(p) for p in (baseline, *builds.values())), "choose fresh separate output")
    require(experiment.digest(baseline / "manifest.json") == BASELINE_SHA, "wrong source bundle")
    sources = experiment.source_files()
    output.mkdir(parents=True)
    experiment.snapshot_sources(output, sources)
    for name in ("input", "bin", "models", "traces", "frames"):
        (output / name).mkdir()
    for target, source in copies().items():
        shutil.copy2(baseline / source, output / target)
    shutil.copy2(baseline / "manifest.json", output / "input/baseline-manifest.json")
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
                with tempfile.TemporaryDirectory(prefix="garden-seed-veto-") as temporary:
                    raw = Path(temporary) / "trace.jsonl"
                    experiment.command_run(command, raw, output, 120)
                    experiment.compress(raw, output / target)
            else:
                experiment.command_run(command, output / target, output, 120)
            timings.append({"artifact": target, "command": command, "seconds": time.monotonic() - start})
            print("Captured", target, flush=True)
        require(experiment.source_files() == sources and all(experiment.digest(output / n) == sha for n, sha in frozen.items()), "sources/inputs changed during capture")
        artifacts = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
        experiment.write_json(output / "capture.json", {"rule": RULE, "settings": settings(), "artifacts": artifacts,
            "calls": timings, "capture_seconds": time.monotonic() - begin})
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
    require(experiment.read_json(target) == value and experiment.digest(image) == experiment.digest(root / "contact-sheet.png"), "portable evidence differs")
    print("Portable seed-veto summary and native contact sheet match verified evidence", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT / "artifacts/garden-renewal-neighbors-v1")
    for case in CASES:
        parser.add_argument(f"--{case}-build", type=Path, default=experiment.ROOT / f"artifacts/build-host-renewal-seed-{case}")
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
