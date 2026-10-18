#!/usr/bin/env python3
"""Prespecified signal-group and fixed-value probes; no training or promotion."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time

import garden_landing_validation as previous
from garden_experiments import digest, source_files, snapshot_sources, write_json
from garden_gallery import artifact, contact_sheet, rgb565be_to_rgb888, write_png
from garden_resources import require

ROOT = Path(__file__).resolve().parents[1]
RULE = "garden-landing-signal-content-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-signals-protocol.md"
INPUTS = {**previous.INPUTS, "landing-validation-results.json.gz":
          "091e263598ffe6cb20c668152299e71e18d203c670d024c740a2955f55e2927d"}
PROBES = [
    {"id": name, "occupancy": occupancy, "resources": resources}
    for name, occupancy, resources in (
        ("live", "live", "live"),
        ("water-light-only", "neutral", "live"),
        ("occupancy-only", "live", "mid"),
        ("neutral", "neutral", "mid"),
        ("occupied", "occupied", "live"),
        ("open", "open", "live"),
        ("low-resources", "live", "low"),
        ("high-resources", "live", "high"),
        ("fixed-occupied", "occupied", "mid"),
        ("fixed-open", "open", "mid"),
    )]
training = previous.training


def model_plan():
    return [{**m, "id": m["controller"], "model": f"models/{m['controller']}.tgl"}
            for m in previous.variant_plan() if m["trained_mode"] == m["mode"] == "current"]


def load_inputs(root):
    for name, sha in INPUTS.items():
        require(digest(root / name) == sha, "wrong frozen signal input: " + name)
    archive = previous.load_inputs(root)
    control = json.loads(gzip.decompress((root / "landing-validation-results.json.gz").read_bytes()))
    require(control["rule"] == previous.RULE and control["conditions"] == previous.conditions(),
            "wrong prior validation panel")
    return archive, control


def prepare_models(binary, inputs, root):
    archive, control = load_inputs(inputs)
    (root / "models").mkdir(parents=True)
    models = []
    for item in model_plan():
        path = root / item["model"]
        with path.open("xb") as stream:
            stream.write(archive[item["source"]])
        metadata = training.native(binary, root, "inspect", item["model"])["model"]
        old = next(m for m in control["models"] if m["id"] == item["id"] + "-as-current")
        require(digest(path) == old["sha256"] and metadata == old["metadata"]
                and metadata["mode"] == "current" and metadata["omit_dead_only"] is False,
                "controller changed or unsupported model")
        models.append({**item, "sha256": digest(path), "metadata": metadata})
    return models, control


def run_world(binary, root, model, case, probe, frame=None, ticks=training.STOP):
    return training.native(binary, root, "probe-replay", model, case["scenario"], "0x" + case["seed"],
                           "--ticks", ticks, "--climate", case["climate"], "--ledger",
                           "--occupancy", probe["occupancy"], "--resources", probe["resources"],
                           *(["--framebuffer", frame] if frame else []))


def scoring_view(result, probe):
    """Validate the explicit intervention before using the unchanged old scorer."""
    require(result["kind"] == "landing-signal-replay" and result["signal_probe"] == {
        "version": 1, "occupancy": probe["occupancy"], "resources": probe["resources"]},
        "wrong/missing signal intervention")
    require(result["model"]["mode"] == "current" and result["model"]["omit_dead_only"] is False,
            "unsupported probe controller")
    return {**{k: v for k, v in result.items() if k != "signal_probe"}, "kind": "landing-replay"}


def evaluate(binary, root, model, probe, jobs):
    cases = previous.conditions()
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(lambda c: run_world(binary, root, model["model"], c, probe), cases))
    worlds = {c["id"]: {"result": r, "history": training.score_world(scoring_view(r, probe), c, model["metadata"])}
              for c, r in zip(cases, results, strict=True)}
    return {"worlds": worlds, "aggregate": training.individual.aggregate(
        {k: w["history"] for k, w in worlds.items()}, [c["id"] for c in cases])}


def check_control(evaluation, model, probe, reference):
    if probe["id"] not in ("live", "neutral"):
        return
    mode = "current" if probe["id"] == "live" else "off"
    expected = reference["evaluations"][model["id"] + "-as-" + mode]
    require(set(evaluation["worlds"]) == set(expected["worlds"]) and
            evaluation["aggregate"] == expected["aggregate"], "control score/conditions changed")
    for key, world in evaluation["worlds"].items():
        old = expected["worlds"][key]
        require(world["history"] == old["history"] and
                training.biological(scoring_view(world["result"], probe)) == training.biological(old["result"]),
                "live/neutral control changed biological trajectory")


def comparisons(evaluations, models):
    result = []
    for model in models:
        control = model["id"] + "--live"
        for probe in PROBES[1:]:
            candidate = model["id"] + "--" + probe["id"]
            a, b = ({k: w["history"] for k, w in evaluations[identity]["worlds"].items()}
                    for identity in (control, candidate))
            result.append({"control": control, "candidate": candidate,
                           "slices": {name: training.individual.pair_group(a, b, ids)
                                      for name, ids in previous.slices().items()}})
    return result


def frame_plan(models):
    return [{**c, "id": f"{m['id']}--{p['id']}-{c['id']}-day-192", "controller": m["id"],
             "variant": m["id"] + "--" + p["id"], "model": m["model"], "probe": p, "day": 192}
            for m in models for p in PROBES for c in training.conditions(previous.SEEDS[0])
            if c["climate"] == "seasonal"]


def capture(binary, root, result):
    (root / "frames").mkdir()
    models = {m["id"]: m for m in result["models"]}
    frames = []
    for frame in frame_plan(result["models"]):
        raw, png = f"frames/{frame['id']}.rgb565be", f"frames/{frame['id']}.png"
        outcome = run_world(binary, root, frame["model"], frame, frame["probe"], raw)
        pixels = (root / raw).read_bytes()
        training.replay.check_result(scoring_view(outcome, frame["probe"]), frame, training.STOP,
                                     models[frame["controller"]]["metadata"], 0, pixels)
        key = f"{frame['scenario']}-{frame['climate']}-{frame['seed']}"
        require({**outcome, "framebuffer_crc32": None} ==
                result["evaluations"][frame["variant"]]["worlds"][key]["result"], "capture changed probe result")
        write_png(root / png, 240, 240, rgb565be_to_rgb888(pixels))
        frames.append({**frame, "framebuffer": raw, "png": png, "result": outcome})
    sheets = {}
    for model in result["models"]:
        selected = [{**f, "framebuffer": str(root / f["framebuffer"])}
                    for f in frames if f["controller"] == model["id"]]
        for part in range(2):
            key = model["id"] + f"-part-{part + 1}"
            output = root / "gallery" / key
            output.mkdir(parents=True)
            section = selected[part * 10:(part + 1) * 10]
            metadata = contact_sheet(output, [section[i:i + 2] for i in range(0, len(section), 2)])
            sheets[key] = {"path": f"gallery/{key}/contact-sheet.png", "metadata": metadata}
    return {"frames": frames, "sheets": sheets}


def run_panel(binary, inputs, root, jobs, images):
    require(1 <= jobs <= 8 and not root.exists(), "jobs must be 1..8 and output fresh")
    models, reference = prepare_models(binary, inputs, root)
    evaluations = {}
    for model in models:
        for probe in PROBES:
            identity = model["id"] + "--" + probe["id"]
            evaluation = evaluate(binary, root, model, probe, jobs)
            check_control(evaluation, model, probe, reference)
            evaluations[identity] = evaluation
            write_json(root / (identity + ".json"), evaluation)
            print(f"{identity}: key={evaluation['aggregate']['key']} "
                  f"zero windows={evaluation['aggregate']['zero_world_periods']}/64", flush=True)
    for model in models:
        require(digest(root / model["model"]) == model["sha256"], "probe changed model bytes")
    result = {"schema_version": 1, "rule": RULE, "objective": training.individual.RULE,
              "models": models, "probes": PROBES, "conditions": previous.conditions(),
              "evaluations": evaluations, "comparisons": comparisons(evaluations, models)}
    write_json(root / "results.json", result)
    if images:
        write_json(root / "gallery.json", capture(binary, root, result))
    return result


def collect(build, inputs, output, jobs):
    require(1 <= jobs <= 8, "jobs must be 1..8")
    require(not output.exists() and (output.is_relative_to(ROOT / "artifacts") or
            not output.is_relative_to(ROOT)), "choose a fresh artifacts/ or external directory")
    load_inputs(inputs)
    cache, binary = build / "CMakeCache.txt", build / "toy-factory-garden-landing"
    flags = training.check_flags(cache)
    identities = {"binary": digest(binary), "cache": digest(cache), **INPUTS}
    sources = source_files()
    output.mkdir(parents=True)
    start = time.monotonic()
    try:
        (output / "bin").mkdir()
        (output / "inputs").mkdir()
        shutil.copy2(binary, output / "bin/garden-landing")
        shutil.copy2(cache, output / "CMakeCache.txt")
        shutil.copy2(ROOT / PROTOCOL, output / "protocol.md")
        for name in INPUTS:
            shutil.copy2(inputs / name, output / "inputs" / name)
        for path in (ROOT / "sim").glob("*.py"):
            target = output / "sim" / path.name
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(path, target)
        for name in ("framebuffer_capture.py", "serial_shell.py"):
            target = output / "scripts/container" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / "scripts/container" / name, target)
        snapshot_sources(output, sources)
        require(digest(output / "protocol.md") == sources[PROTOCOL], "protocol changed during copy")
        write_json(output / "started.json", {"rule": RULE, "inputs": identities, "flags": flags,
                   "protocol_sha256": digest(output / "protocol.md"), "sources": sources})
        frozen = output / "bin/garden-landing"
        require(digest(frozen) == identities["binary"] and digest(output / "CMakeCache.txt") == identities["cache"],
                "build changed during copy")
        result = run_panel(frozen, output / "inputs", output / "panel", jobs, True)
        print("Repeating the entire signal panel with one worker and capture disabled...", flush=True)
        repeated = run_panel(frozen, output / "inputs", output / "repeat", 1, False)
        require(result == repeated, "worker count/capture changed signal panel")
        for model in result["models"]:
            require(digest(output / "panel" / model["model"]) == model["sha256"] ==
                    digest(output / "repeat" / model["model"]), "model bytes changed")
        require(sources == source_files(), "sources changed during collection")
        require(digest(binary) == digest(frozen) == identities["binary"] and
                digest(cache) == digest(output / "CMakeCache.txt") == identities["cache"],
                "build changed during collection")
        load_inputs(inputs)
        load_inputs(output / "inputs")
        write_json(output / "timings.json", {"collection_and_repeat_seconds": time.monotonic() - start})
        artifacts = {str(p.relative_to(output)): digest(p) for p in sorted(output.rglob("*")) if p.is_file()}
        write_json(output / "manifest.json", {"rule": RULE, "status": "complete", "repeat_verified": True,
                   "inputs": identities, "source_sha256_at_collection": sources, "build_flags": flags,
                   "artifacts": artifacts})
    except BaseException as error:
        with (output / "FAILED.txt").open("x") as stream:
            stream.write(str(error) + "\n")
        raise
    return result


def verify(output):
    require(not (output / "FAILED.txt").exists(), "incomplete bundle")
    manifest = json.loads((output / "manifest.json").read_text())
    require(manifest["rule"] == RULE and manifest["status"] == "complete" and
            manifest["repeat_verified"] is True, "wrong/incomplete signal panel")
    for name in manifest["artifacts"]:
        artifact(output, manifest, name)
    binary = artifact(output, manifest, "bin/garden-landing")
    require(training.check_flags(output / "CMakeCache.txt") == manifest["build_flags"] and
            manifest["inputs"] == {"binary": digest(binary), "cache": digest(output / "CMakeCache.txt"), **INPUTS}
            and digest(output / "protocol.md") == manifest["source_sha256_at_collection"][PROTOCOL],
            "build/input/protocol mismatch")
    expected = json.loads(artifact(output, manifest, "panel/results.json").read_text())
    require(expected == json.loads(artifact(output, manifest, "repeat/results.json").read_text()), "saved repeat differs")
    for model in expected["models"]:
        for run in ("panel", "repeat"):
            require(digest(artifact(output, manifest, run + "/" + model["model"])) == model["sha256"],
                    "saved model changed")
    with tempfile.TemporaryDirectory(prefix="landing-signals-verify-") as temporary:
        fresh = Path(temporary) / "panel"
        actual = run_panel(binary, output / "inputs", fresh, 4, True)
        require(actual == expected, "signal panel is not reproducible")
        for path in fresh.rglob("*"):
            if path.is_file():
                original = artifact(output, manifest, "panel/" + str(path.relative_to(fresh)))
                require(path.read_bytes() == original.read_bytes(), "signal artifact differs")
    for name in manifest["artifacts"]:
        artifact(output, manifest, name)
    print("Verified all 480 signal worlds, unchanged models, scores, and 60 frames.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path)
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--jobs", type=int)
    parser.add_argument("--verify", type=Path, help="execute a trusted local frozen bundle")
    args = parser.parse_args()
    try:
        if args.verify:
            require(args.build is None and args.inputs is None and args.out is None and args.jobs is None,
                    "verify takes no collection overrides")
            verify(args.verify.resolve())
        else:
            require(args.out is not None, "collection requires --out")
            collect((args.build or ROOT / "build-host").resolve(),
                    (args.inputs or ROOT / "benchmarks/garden-seasons").resolve(),
                    args.out.resolve(), 4 if args.jobs is None else args.jobs)
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print(f"signal panel failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
