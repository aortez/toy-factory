#!/usr/bin/env python3
"""Frozen-finalist, same-weight input ablations on a fixed development panel."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import time
import zlib

import garden_landing_training as training
from garden_experiments import digest, source_files, snapshot_sources, write_json
from garden_gallery import artifact, contact_sheet, rgb565be_to_rgb888, write_png
from garden_resources import require

ROOT = Path(__file__).resolve().parents[1]
RULE = "garden-landing-frozen-validation-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-validation-protocol.md"
INPUTS = {
    "landing-training-models.json.gz": "d35e471f91313198dbd2725987e01744dc6ce0ff400a1fa5f88435b11c78f73d",
    "landing-training-summary.json": "342ae4e2c6349edf67ff926b7dce161ec2a56c84bf36411e2ffaddd66b8aa277",
}
SEEDS = ("25185eeb", "d60c94c0", "8377cb18", "30358096")
FINALISTS = {
    0x6d697833: ("g2-c2", "g1-c0", "g1-c2"),
    0x6d697834: ("g2-c1", "g1-c2", "g2-c2"),
    0x6d697835: ("g2-c0", "g1-c1", "g2-c0"),
}
BASELINE = "initial-as-off"


def conditions():
    return [case for seed in SEEDS for case in training.conditions(seed)]


def variant_plan():
    plan = [{"id": BASELINE, "controller": "initial", "trained_mode": "off", "mode": "off",
             "source": "initial.tgm", "champion": None}]
    for seed, champions in FINALISTS.items():
        for mode, champion in zip(training.MODES, champions, strict=True):
            controller = f"s{seed:08x}-{mode}"
            for target in reversed(training.MODES[:training.MODES.index(mode) + 1]):
                plan.append({"id": f"{controller}-as-{target}", "controller": controller,
                             "trained_mode": mode, "mode": target, "champion": champion,
                             "source": f"{controller}/models/{champion}.tgl"})
    return plan


def load_inputs(root):
    for name, sha in INPUTS.items():
        require(digest(root / name) == sha, "wrong frozen pilot input: " + name)
    archive = json.loads(gzip.decompress((root / "landing-training-models.json.gz").read_bytes()))
    summary = json.loads((root / "landing-training-summary.json").read_text())
    models = {name: bytes.fromhex(value) for name, value in archive.items()}
    require(hashlib.sha256(models["initial.tgm"]).hexdigest() == training.BASE_SHA,
            "wrong initial controller")
    for item in variant_plan()[1:]:
        run = summary["searches"][item["controller"]]
        final = run["generations"][-1]
        require(final["champion"] == item["champion"] and run["mode"] == item["trained_mode"]
                and hashlib.sha256(models[item["source"]]).hexdigest() == final["sha256"],
                "not the frozen training-selected finalist")
    return models


def ablated_bytes(source, mode):
    """Independent canonical-byte oracle, not the native file-writing path."""
    require(len(source) == 1448 and source[:4] == b"TGL2" and mode in training.MODES,
            "invalid ablation input")
    target = training.MODES.index(mode)
    require(target <= source[1237] < 3, "ablation cannot enable inputs")
    changed = bytearray(source)
    changed[1237] = target
    struct.pack_into("<I", changed, 12, zlib.crc32(changed[16:]))
    return bytes(changed)


def prepare_models(binary, inputs, root):
    archive = load_inputs(inputs)
    (root / "models").mkdir(parents=True)
    with (root / "initial.tgm").open("xb") as stream:
        stream.write(archive["initial.tgm"])
    models = []
    for item in variant_plan():
        model = f"models/{item['id']}.tgl"
        path = root / model
        if item["id"] == BASELINE:
            metadata = training.native(binary, root, "import", "initial.tgm", model, "--mode", "off")["model"]
            data = path.read_bytes()
            require(data[16:1236] == archive["initial.tgm"] and not any(data[1240:]),
                    "initial import altered weights")
        else:
            source = archive[item["source"]]
            if item["trained_mode"] == item["mode"]:
                with path.open("xb") as stream:
                    stream.write(source)
                metadata = training.native(binary, root, "inspect", model)["model"]
            else:
                original = f"models/{item['controller']}-as-{item['trained_mode']}.tgl"
                receipt = training.native(binary, root, "ablate", original, model, item["mode"])
                require(receipt["source_mode"] == item["trained_mode"], "wrong ablation source")
                metadata = receipt["model"]
            require(path.read_bytes() == ablated_bytes(source, item["mode"]),
                    "ablation changed weights or other configuration")
        require(metadata["mode"] == item["mode"] and metadata["omit_dead_only"] is False,
                "wrong feature mask")
        models.append({**item, "model": model, "sha256": digest(path), "metadata": metadata})
    return models


def slices():
    cases = conditions()
    return {"all": [c["id"] for c in cases], **{
        f"{field}/{value}": [c["id"] for c in cases if c[field] == value]
        for field in ("seed", "scenario", "climate")
        for value in dict.fromkeys(c[field] for c in cases)}}


def comparisons(evaluations):
    pairs = []
    for seed in FINALISTS:
        for mode in training.MODES:
            original = f"s{seed:08x}-{mode}-as-{mode}"
            pairs.append(("baseline", BASELINE, original))
            if mode != "off":
                pairs.append(("training-arm", f"s{seed:08x}-off-as-off", original))
            for reduced in training.MODES[:training.MODES.index(mode)]:
                pairs.append(("input-ablation", f"s{seed:08x}-{mode}-as-{reduced}", original))
    result = []
    for kind, control, candidate in pairs:
        a, b = ({k: w["history"] for k, w in evaluations[identity]["worlds"].items()}
                for identity in (control, candidate))
        result.append({"kind": kind, "control": control, "candidate": candidate,
                       "slices": {name: training.individual.pair_group(a, b, ids)
                                  for name, ids in slices().items()}})
    return result


def evaluate(binary, root, model, jobs):
    cases = conditions()
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(lambda c: training.run_world(binary, root, model["model"], c), cases))
    worlds = {c["id"]: {"result": r, "history": training.score_world(r, c, model["metadata"])}
              for c, r in zip(cases, results, strict=True)}
    return {"worlds": worlds, "aggregate": training.individual.aggregate(
        {k: w["history"] for k, w in worlds.items()}, [c["id"] for c in cases])}


def frame_plan(models):
    return [{**c, "id": f"{m['id']}-{c['id']}-day-{day}", "variant": m["id"],
             "controller": m["controller"], "model": m["model"], "day": day}
            for m in models for c in training.conditions(SEEDS[0]) if c["climate"] == "seasonal"
            for day in (16, 192)]


def capture(binary, root, result):
    (root / "frames").mkdir()
    frames = []
    models = {m["id"]: m for m in result["models"]}
    for item in frame_plan(result["models"]):
        raw, png = f"frames/{item['id']}.rgb565be", f"frames/{item['id']}.png"
        outcome = training.run_world(binary, root, item["model"], item, item["day"] * training.DAY, raw)
        pixels = (root / raw).read_bytes()
        training.replay.check_result(outcome, item, item["day"] * training.DAY,
                                     models[item["variant"]]["metadata"], 0, pixels)
        if item["day"] == 192:
            case_id = f"{item['scenario']}-{item['climate']}-{item['seed']}"
            require({**outcome, "framebuffer_crc32": None} ==
                    result["evaluations"][item["variant"]]["worlds"][case_id]["result"],
                    "capture changed evaluation")
        write_png(root / png, 240, 240, rgb565be_to_rgb888(pixels))
        frames.append({**item, "framebuffer": raw, "png": png, "result": outcome})
    sheets = {}
    for controller in dict.fromkeys(m["controller"] for m in result["models"]):
        selected = [{**f, "framebuffer": str(root / f["framebuffer"])}
                    for f in frames if f["controller"] == controller]
        output = root / "gallery" / controller
        output.mkdir(parents=True)
        metadata = contact_sheet(output, [selected[i:i + 2] for i in range(0, len(selected), 2)])
        sheets[controller] = {"path": f"gallery/{controller}/contact-sheet.png", "metadata": metadata}
    return {"frames": frames, "sheets": sheets}


def run_panel(binary, inputs, root, jobs, images):
    require(1 <= jobs <= 8, "jobs must be 1..8")
    require(not root.exists(), "panel output must be fresh")
    models = prepare_models(binary, inputs, root)
    evaluations = {}
    for model in models:
        value = evaluate(binary, root, model, jobs)
        evaluations[model["id"]] = value
        write_json(root / (model["id"] + ".json"), value)
        print(f"{model['id']}: key={value['aggregate']['key']} "
              f"zero windows={value['aggregate']['zero_world_periods']}/64", flush=True)
    result = {"schema_version": 1, "rule": RULE, "objective": training.individual.RULE,
              "conditions": conditions(), "models": models, "evaluations": evaluations,
              "comparisons": comparisons(evaluations)}
    write_json(root / "results.json", result)
    if images:
        write_json(root / "gallery.json", capture(binary, root, result))
    return result


def collect(build, inputs, output, jobs):
    require(1 <= jobs <= 8, "jobs must be 1..8")
    require(not output.exists() and (output.is_relative_to(ROOT / "artifacts") or
            not output.is_relative_to(ROOT)), "choose a fresh artifacts/ or external output directory")
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
        print("Repeating all conditions with one worker and capture disabled...", flush=True)
        repeated = run_panel(frozen, output / "inputs", output / "repeat", 1, False)
        require(result == repeated, "worker count/capture changed results")
        for model in result["models"]:
            require(digest(output / "panel" / model["model"]) == model["sha256"] ==
                    digest(output / "repeat" / model["model"]), "derived model changed")
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
    require(manifest["rule"] == RULE and manifest["status"] == "complete"
            and manifest["repeat_verified"] is True, "wrong/incomplete validation")
    for name in manifest["artifacts"]:
        artifact(output, manifest, name)
    binary = artifact(output, manifest, "bin/garden-landing")
    require(training.check_flags(output / "CMakeCache.txt") == manifest["build_flags"], "wrong ecology")
    require(manifest["inputs"] == {"binary": digest(binary), "cache": digest(output / "CMakeCache.txt"), **INPUTS}
            and digest(output / "protocol.md") == manifest["source_sha256_at_collection"][PROTOCOL],
            "input/protocol provenance mismatch")
    expected = json.loads(artifact(output, manifest, "panel/results.json").read_text())
    require(expected == json.loads(artifact(output, manifest, "repeat/results.json").read_text()),
            "saved repetition differs")
    gallery = json.loads(artifact(output, manifest, "panel/gallery.json").read_text())
    for model in expected["models"]:
        for run in ("panel", "repeat"):
            require(digest(artifact(output, manifest, run + "/" + model["model"])) == model["sha256"],
                    "saved derived model changed")
    with tempfile.TemporaryDirectory(prefix="landing-validation-verify-") as temporary:
        fresh = Path(temporary) / "panel"
        actual = run_panel(binary, output / "inputs", fresh, 2, True)
        require(actual == expected, "frozen panel is not reproducible")
        require(json.loads((fresh / "gallery.json").read_text()) == gallery, "gallery plan/replay differs")
        for path in fresh.rglob("*"):
            if path.is_file():
                original = artifact(output, manifest, "panel/" + str(path.relative_to(fresh)))
                require(path.read_bytes() == original.read_bytes(), "panel artifact differs")
    for name in manifest["artifacts"]:
        artifact(output, manifest, name)
    print("Verified all 304 worlds, derived models, scores, and 76 frames.", flush=True)


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
                    args.out.resolve(), 2 if args.jobs is None else args.jobs)
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print(f"landing validation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
