#!/usr/bin/env python3
"""Fixed, host-only reciprocal founder-controller swap with neutral controls."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
from itertools import zip_longest
from pathlib import Path
import shutil
import tarfile
import tempfile
import time

import garden_renewal_startup as startup

experiment, require, gallery = startup.experiment, startup.require, startup.gallery
RULE = "garden-renewal-swap-v1"
ROUTING_RULE = "founder-policy-swap-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-swap-protocol.md"
BASELINE_SHA = "301d0df74768bd4c1a8a3fbe2b26dbc2f5a10025c40c76dd213b0f7b5fbd3467"
FOUNDER = 2
MODELS = {m.name: m for m in startup.MODELS if m.name != "original"}


@dataclass(frozen=True)
class Case:
    name: str
    focal: str
    background: str


CASES = (Case("n-in-n", "r2-n", "r2-n"), Case("w-in-n", "r2-w", "r2-n"),
         Case("n-in-w", "r2-n", "r2-w"), Case("w-in-w", "r2-w", "r2-w"))


def routing(case):
    return {"rule": ROUTING_RULE, "founder": FOUNDER, "model_crc32": MODELS[case.focal].crc}


def settings():
    return {"rule": RULE, "baseline_manifest_sha256": BASELINE_SHA,
            "cases": [asdict(c) for c in CASES], "founder": FOUNDER,
            "models": {k: m.crc for k, m in MODELS.items()},
            "world_seed": startup.SEED, "patch_seed": startup.PATCH,
            "stop": startup.STOP, "frame_ticks": list(startup.FRAME_TICKS),
            "descendants": "background controller, including focal offspring",
            "budget": {"traces": 8, "frame_replays": 32, "native_calls": 40,
                       "training_calls": 0, "mutation_calls": 0},
            "role": "causal focal intervention in one inspected world; ecological feedback permitted"}


def copies():
    result = {"input/baseline-native-source.tar.gz": "input/native-source.tar.gz",
              "input/baseline-CMakeCache.txt": "input/CMakeCache.txt"}
    for name in MODELS:
        result[f"models/{name}.tgm"] = f"models/{name}.tgm"
        result[f"input/controls/{name}.jsonl.gz"] = f"traces/{name}.jsonl.gz"
        for tick in startup.FRAME_TICKS:
            for extension in ("json", "rgb565"):
                result[f"input/controls/{name}.{tick}.{extension}"] = f"frames/{name}.{tick}.{extension}"
    return result


def commands():
    result = []
    for case in CASES:
        base = [f"models/{case.background}.tgm", "rainfed-crowded", experiment.NIGHT_POLICY,
                "0x" + startup.SEED, "--leaf-policy", "selective", "--disturbance-seed", "0x" + startup.PATCH,
                "--focal-model", f"models/{case.focal}.tgm", "--focal-founder", str(FOUNDER)]
        for repeat in (False, True):
            suffix = ".repeat" if repeat else ""
            result.append((f"traces/{case.name}{suffix}.jsonl.gz",
                           ["bin/garden-inspect", *base, "--ecology", "--ticks", str(startup.STOP)]))
        for tick in startup.FRAME_TICKS:
            for repeat in (False, True):
                stem = f"frames/{case.name}.{tick}" + (".repeat" if repeat else "")
                result.append((stem + ".json", ["bin/garden-replay", *base, "--ticks", str(tick),
                                               "--framebuffer", stem + ".rgb565"]))
    return result


def without_routing(row):
    # Never discard other metadata or state to make a failed control pass.
    return {k: v for k, v in row.items() if k not in ("focal_policy", "controller_model_crc32")}


def check_routing(rows, case):
    counts = Counter()
    for row in rows:
        if row["type"] == "world":
            require(row.get("focal_policy") == routing(case), "wrong focal configuration")
            if row["tick"] == 0:
                plants = [p for p in row["plants"] if p["id"] == FOUNDER]
                require(len(plants) == 1 and all(plants[0].get(k) == v for k, v in
                        {"parent": 0, "generation": 0, "species": "shrub", "column": 8, "dead": False}.items()),
                        "wrong reset founder")
                counts["reset"] += 1
            counts["worlds"] += 1
        elif row["type"] == "bid":
            focal = row["id"] == FOUNDER
            expected = MODELS[case.focal if focal else case.background].crc
            require(row.get("controller_model_crc32") == expected, "wrong routed growth bid")
            counts["focal_bids" if focal else "background_bids"] += 1
        else:
            require(row["type"] == "leaf-bid" and "controller_model_crc32" not in row,
                    "unexpected record or neural leaf routing")
    require(counts["reset"] == 1 and counts["focal_bids"] > 0 and counts["background_bids"] > 0,
            "incomplete routing evidence")
    return dict(counts)


def check_control(new, old):
    count = 0
    for actual, expected in zip_longest(new, old):
        require(actual is not None and expected is not None and without_routing(actual) == expected,
                f"same-model control changed at record {count}")
        count += 1
    require(count > 0, "empty control")
    return count


def focal_summary(result, samples):
    focal = next(p for p in result["lineages"] if p["id"] == FOUNDER)
    checkpoints = {}
    for tick in (960, 2880, 4800, 6240, 6600, 6705, 6840, 6900, 7140, 7680, startup.STOP):
        plant = next((p for p in samples[tick]["plants"] if p["id"] == FOUNDER), None)
        checkpoints[str(tick)] = None if plant is None else startup.snapshot(samples[tick], plant)
    end = samples[startup.STOP]
    return {"focal": focal, "focal_checkpoints": checkpoints,
            "offspring": [{k: p[k] for k in ("id", "parent", "species", "generation", "column",
                          "birth_tick", "death_tick", "death_shortage", "alive_at_end")}
                          for p in result["lineages"] if p["parent"] == FOUNDER],
            "final": {**{k: end[k] for k in ("tick", "hash", "living", "nodes", "births", "deaths")},
                      "living_by_species": dict(Counter(p["species"] for p in end["plants"] if not p["dead"])),
                      "living_founders": [p["id"] for p in end["plants"] if not p["dead"] and p["parent"] == 0]}}


def analyze(root):
    results, frames, initial = {}, [], None
    for case in CASES:
        trace = root / f"traces/{case.name}.jsonl.gz"
        require(experiment.digest(trace) == experiment.digest(root / f"traces/{case.name}.repeat.jsonl.gz"),
                "full native trace repeat differs")
        routed = check_routing(startup.read_trace(trace), case)
        neutral = None
        if case.focal == case.background:
            neutral = check_control(startup.read_trace(trace),
                startup.read_trace(root / f"input/controls/{case.background}.jsonl.gz"))
        result, samples = startup.analyze_trace(trace, [])
        reset = without_routing(samples[0])
        if initial is None:
            initial = reset
        require(reset == initial, "different reset worlds")
        results[case.name] = {"case": asdict(case), "routing": routed,
            "neutral_control_records": neutral, "counts": result["counts"],
            "resource_totals": result["resource_totals"], "tip_audit": result["tip_audit"],
            "lineages": [{k: v for k, v in p.items() if k != "decisions"} for p in result["lineages"]],
            "quarter_days": result["quarter_days"], **focal_summary(result, samples)}
        for tick in startup.FRAME_TICKS:
            stem = f"{case.name}.{tick}"
            value = experiment.read_json(root / f"frames/{stem}.json")
            raw = (root / f"frames/{stem}.rgb565").read_bytes()
            require(value.get("focal_policy") == routing(case), "wrong replay routing")
            startup.check_frame(value, samples[tick], MODELS[case.background], tick, raw)
            require(value == experiment.read_json(root / f"frames/{stem}.repeat.json") and
                    raw == (root / f"frames/{stem}.repeat.rgb565").read_bytes(), "native frame repeat differs")
            if neutral is not None:
                old = root / f"input/controls/{case.background}.{tick}"
                require(without_routing(value) == experiment.read_json(old.with_suffix(old.suffix + ".json"))
                        and raw == old.with_suffix(old.suffix + ".rgb565").read_bytes(), "same-model frame changed")
            frames.append({"id": stem, "case": case.name, "tick": tick, "result": value,
                           "framebuffer": f"frames/{stem}.rgb565", "png": f"frames/{stem}.png"})
    return {"rule": RULE, "settings": settings(), "cases": results, "frames": frames}


def native_hashes(path):
    with tarfile.open(path) as archive:
        result = {}
        for member in archive.getmembers():
            if member.isfile() and member.name.endswith((".c", ".h")):
                with archive.extractfile(member) as stream:
                    result[member.name] = hashlib.sha256(stream.read()).hexdigest()
        return result


def cache_settings(path):
    result = {}
    for line in path.read_text().splitlines():
        if line.startswith(("TOY_FACTORY_", "CMAKE_BUILD_TYPE:", "CMAKE_C_FLAGS:",
                            "CMAKE_C_FLAGS_RELWITHDEBINFO:", "CMAKE_C_COMPILER:")):
            key, value = line.split("=", 1)
            result[key] = value
    return result


def check_inputs(root):
    require(experiment.digest(root / "input/baseline-manifest.json") == BASELINE_SHA, "wrong startup baseline")
    manifest = experiment.read_json(root / "input/baseline-manifest.json")
    for target, source in copies().items():
        require(experiment.digest(root / target) == manifest["artifacts"][source], "changed frozen input")
    for name, model in MODELS.items():
        require(startup.pilot.model_crc(root / f"models/{name}.tgm") == model.crc, "changed model identity")
    require(experiment.read_json(root / "input/settings.json") == settings(), "changed swap contract")
    require(cache_settings(root / "input/CMakeCache.txt") == cache_settings(root / "input/baseline-CMakeCache.txt"),
            "native build configuration differs")
    old, new = native_hashes(root / "input/baseline-native-source.tar.gz"), native_hashes(root / "source.tar.gz")
    # Existing founder-exit plumbing is inactive, explicitly rejected with a swap.
    # The changed persistence trial is not linked into either diagnostic tool.
    allowed_changes = {"sim/garden_inspect.c", "sim/garden_replay.c", "sim/garden_persistence_trial.c"}
    allowed_additions = {f"sim/garden_{name}.{suffix}" for name in
        ("focal_policy", "founder_exit") for suffix in ("c", "h")} | {
        "sim/garden_focal_policy_test.c", "sim/garden_founder_exit_test.c"}
    require(old.keys() <= new.keys() and new.keys() - old.keys() <= allowed_additions,
            "unexpected added or removed native sources")
    changed = {n for n in old if old[n] != new[n]}
    require(changed <= allowed_changes, "shared native mechanics changed")
    started = experiment.read_json(root / "started.json")
    require(all(started["sources"].get(n) == sha for n, sha in new.items()), "native source freeze differs")
    require(experiment.digest(root / "input/protocol.md") == started["sources"][PROTOCOL], "protocol freeze differs")


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
    started = experiment.read_json(root / "started.json")
    require(all(experiment.digest(root / n) == sha for n, sha in started["frozen"].items()), "frozen capture input changed")
    check_inputs(root)
    return capture


def verify(root):
    manifest = experiment.read_json(root / "manifest.json")
    require(manifest["rule"] == RULE and manifest["status"] == "complete", "incomplete swap bundle")
    require(set(manifest["artifacts"]) == {str(p.relative_to(root)) for p in root.rglob("*")
            if p.is_file() and p != root / "manifest.json"}, "extra or missing artifacts")
    for name in manifest["artifacts"]:
        gallery.artifact(root, manifest, name)
    capture = check_capture(root)
    require(manifest["sources"] == experiment.read_json(root / "started.json")["sources"] and
            experiment.read_json(root / "timings.json")["calls"] == capture["calls"], "source/call record differs")
    result = analyze(root)
    require(result == experiment.read_json(root / "results.json"), "swap reanalysis differs")
    print("Verified four repeated traces, both complete old controls, routing and 16 repeated native frames", flush=True)
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


def collect(baseline, build, output):
    require(not output.exists() and output.is_relative_to(experiment.ROOT / "artifacts") and
            not any(output.is_relative_to(p) for p in (baseline, build)), "choose fresh separate artifact output")
    require(experiment.digest(baseline / "manifest.json") == BASELINE_SHA, "wrong source bundle")
    sources = experiment.source_files()
    output.mkdir(parents=True)
    experiment.snapshot_sources(output, sources)
    for name in ("input", "bin", "models", "traces", "frames"):
        (output / name).mkdir()
    for target, source in copies().items():
        (output / target).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(baseline / source, output / target)
    shutil.copy2(baseline / "manifest.json", output / "input/baseline-manifest.json")
    shutil.copy2(build / "CMakeCache.txt", output / "input/CMakeCache.txt")
    shutil.copy2(build / "build.ninja", output / "input/build.ninja")
    for name in ("inspect", "replay"):
        shutil.copy2(build / f"toy-factory-garden-{name}", output / f"bin/garden-{name}")
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
                with tempfile.TemporaryDirectory(prefix="garden-swap-") as temporary:
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
    require(experiment.read_json(target) == value and experiment.digest(image) == experiment.digest(root / "contact-sheet.png"),
            "portable swap evidence differs")
    print("Portable swap summary and native contact sheet match verified evidence", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT / "artifacts/garden-renewal-startup-v1")
    parser.add_argument("--build", type=Path, default=experiment.ROOT / "artifacts/build-host-renewal-swap")
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
        collect(args.baseline.resolve(), args.build.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
