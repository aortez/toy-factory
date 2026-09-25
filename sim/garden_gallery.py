#!/usr/bin/env python3
"""Make a fixed-panel, hash-verified screenshot gallery from a Garden experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zlib

import garden_experiments as experiment
from garden_resources import require

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/container"))
from framebuffer_capture import rgb565be_to_rgb888, write_png  # noqa: E402

WIDTH = HEIGHT = 240
FRAME_BYTES = WIDTH * HEIGHT * 2
POLICIES = {"baseline", "adaptive", "neural-reference"} | experiment.MODEL_POLICIES


def artifact(root: Path, manifest: dict, name: str) -> Path:
    require(isinstance(name, str) and name in manifest["artifacts"], "unrecorded artifact")
    relative = Path(name)
    require(not relative.is_absolute() and ".." not in relative.parts, "unsafe artifact path")
    path = (root / relative).resolve()
    require(path.is_relative_to(root) and path.is_file(), "artifact missing or outside bundle")
    require(experiment.digest(path) == manifest["artifacts"][name], f"artifact changed: {name}")
    return path


def frame_command(frame: dict) -> list[str]:
    require(frame["policy"] in POLICIES and frame["scenario"] in experiment.SCENARIOS,
            "unsupported replay scenario/policy")
    require(re.fullmatch("[0-9a-f]{8}", frame["seed"]) is not None
            and int(frame["seed"], 16) != 0, "invalid replay seed")
    require(isinstance(frame["tick"], int) and 0 <= frame["tick"] <= 100000, "invalid replay tick")
    return ["bin/garden-replay", frame["model"] or "-", frame["scenario"], frame["policy"],
            "0x" + frame["seed"], "--ticks", str(frame["tick"])]


def check_frame(result: dict, reference: dict, model_crc: str | None, raw: bytes) -> None:
    require(result.get("schema_version") == 1, "unsupported replay schema")
    for key in ("scenario", "policy", "seed", "tick", "hash", "sun_phase", "sun_strength",
                "rain_rate", "rain_deposited", "rain_runoff", "living", "descendants",
                "plant_slots", "nodes", "seed_bank", "births", "deaths", "moisture"):
        require(result[key] == reference[key], f"replay/timeline mismatch: {key}")
    if result["policy"] in experiment.MODEL_POLICIES:
        require(result["model_crc32"] == model_crc, "replay used a different model")
    require(len(raw) == FRAME_BYTES, "wrong framebuffer size")
    require(f"{zlib.crc32(raw):08x}" == result["framebuffer_crc32"], "framebuffer CRC mismatch")


def run_frame(root: Path, frame: dict, framebuffer: Path, timeout: int) -> tuple[dict, bytes]:
    result = subprocess.run(frame_command(frame) + ["--framebuffer", str(framebuffer)],
                            cwd=root, capture_output=True, text=True, timeout=timeout, check=False)
    require(result.returncode == 0, f"replay failed: {result.stderr.strip()}")
    value = json.loads(result.stdout)
    require(value.get("node_capacity", 256) == frame.get("node_capacity", 256), "wrong replay node capacity")
    require(value.get("seed_dispersal", "narrow-v1") == frame.get("seed_dispersal", "narrow-v1"),
            "replayer uses a different dispersal rule")
    require(value.get("water_uptake", "legacy-v1") == frame.get("water_uptake", "legacy-v1"),
            "replayer uses a different water uptake rule")
    raw = framebuffer.read_bytes()
    check_frame(value, frame["reference"], frame["model_crc32"], raw)
    return value, raw


def checkpoints(horizon: int, requested: list[int]) -> list[int]:
    ticks = sorted(set(requested or (min(480, horizon), min(2880, horizon), horizon)))
    require(1 <= len(ticks) <= 6 and all(0 <= tick <= horizon for tick in ticks),
            "choose 1-6 checkpoint ticks within the experiment horizon")
    return ticks


def contact_sheet(output: Path, groups: list[list[dict]]) -> dict:
    gap = 8
    columns = len(groups[0])
    width, height = columns * (WIDTH + gap) + gap, len(groups) * (HEIGHT + gap) + gap
    pixels = bytearray(bytes((32, 36, 42)) * (width * height))
    for row, frames in enumerate(groups):
        for column, frame in enumerate(frames):
            rgb = rgb565be_to_rgb888((output / frame["framebuffer"]).read_bytes())
            for y in range(HEIGHT):
                start = ((gap + row * (HEIGHT + gap) + y) * width
                         + gap + column * (WIDTH + gap)) * 3
                pixels[start:start + WIDTH * 3] = rgb[y * WIDTH * 3:(y + 1) * WIDTH * 3]
    write_png(output / "contact-sheet.png", width, height, bytes(pixels))
    return {"width": width, "height": height, "gap": gap,
            "rows": [[frame["id"] for frame in frames] for frames in groups]}


def gallery_markdown(groups: list[list[dict]], seeds: list[str], ticks: list[int]) -> str:
    lines = ["# Garden visual baseline", "",
             "Fixed manual-review panel, not an untouched test set or a training-generation gallery.",
             "Every frame matches its recorded evaluator state and uses the production renderer.",
             "", "Seeds: " + ", ".join(f"`{seed}`" for seed in seeds) + ".",
             "Columns show ticks " + ", ".join(str(t) for t in ticks) + " (60 ticks/second).",
             "Reset starts at noon; first dawn is tick 2880. Rows are identified below.",
             "", "![Fixed-panel overview](contact-sheet.png)", "",
             "| Row | Layout / seed | Policy / model | End living / seeds | Full-cycle offspring survivors / eligible | Durable parents |",
             "|---|---|---|---:|---:|---:|"]
    for index, frames in enumerate(groups, 1):
        frame = frames[0]
        end = frame["final_trial"]
        metrics = experiment.measures(end)
        lines.append(f"| {index} | {frame['scenario']} / `{frame['seed']}` | "
                     f"{frame['side']}: {frame['policy']} / `{frame['model_crc32'] or 'built-in'}` | "
                     f"{end['living']} / {end['seed_bank']} | "
                     f"{metrics['cycle_survivors']} / {metrics['eligible_offspring']} | "
                     f"{metrics['durable_parents']} |")
    lines += ["", "End metrics refer to the full experiment horizon, even if custom image checkpoints end earlier.",
              "An eligible offspring had a full cycle of potential follow-up; an empty cohort is not a zero-percent success rate.",
              "A durable parent and at least one child each survived a full cycle. These are cumulative counts, not rates.",
              "Empty/failed worlds are retained. Images alone do not establish healthy reproduction.", ""]
    for frames in groups:
        first = frames[0]
        lines += [f"## {first['scenario']} / {first['side']} / {first['seed']}", "",
                  "| " + " | ".join(f"Tick {f['tick']} ({f['tick']/60:g}s)" for f in frames) + " |",
                  "|" + "|".join("---" for _ in frames) + "|",
                  "| " + " | ".join(f"![Frame {f['id']}]({f['png']})" for f in frames) + " |"]
        labels = []
        for frame in frames:
            r = frame["result"]
            labels.append(f"Alive {r['living']} ({r['descendants']} descendants); "
                          f"seeds {r['seed_bank']}; births/deaths {r['births']}/{r['deaths']}; "
                          f"sun {r['sun_phase']}; hash `{r['hash']}`; CRC `{r['framebuffer_crc32']}`")
        lines += ["| " + " | ".join(labels) + " |", ""]
    lines += ["[Frame metadata and reference metrics](frames.json) · [Provenance](manifest.json)", "",
              "Recheck the saved frames using the frozen executable, from this directory inside the builder container:", "",
              "```sh", "python3 tools/garden_gallery.py --verify .", "```", ""]
    return "\n".join(lines)


def collect(args: argparse.Namespace) -> None:
    bundle, output = args.bundle.resolve(), args.output.resolve()
    require(output != ROOT and (not output.is_relative_to(ROOT) or output.is_relative_to(ROOT / "artifacts")),
            "put galleries outside the source tree or under artifacts/")
    require(not output.exists(), "output already exists; choose a new gallery directory")
    input_digest = experiment.digest(bundle / "manifest.json")
    manifest = experiment.read_json(bundle / "manifest.json")
    require(experiment.digest(bundle / "manifest.json") == input_digest,
            "input manifest changed while reading")
    require(manifest["status"] == "complete" and manifest["schema_version"] == 1, "incomplete/unsupported experiment")
    experiment.validate_environment(manifest["environment"])
    require(manifest["split"] != "test", "do not use untouched test bundles for manual model selection")
    seeds = args.seed or manifest["seeds"][:1]
    require(1 <= len(seeds) <= 4 and len(seeds) == len(set(seeds))
            and all(seed in manifest["seeds"] for seed in seeds), "choose 1-4 distinct seeds in the bundle")
    ticks = checkpoints(manifest["cycles"] * experiment.CYCLE_TICKS, args.checkpoint)
    references, models, jobs = {}, {}, {}
    roles = dict(manifest["roles"])
    if args.include_adaptive:
        roles["adaptive"] = {"job": "candidate", "policy": "adaptive", "model_crc32": None}
    for side, role in roles.items():
        job = role["job"]
        require(job in ("candidate", "control") and role["policy"] in POLICIES, "invalid experiment role")
        report_path = artifact(bundle, manifest, f"reports/{job}.json")
        timeline_path = artifact(bundle, manifest, f"timelines/{job}.jsonl.gz")
        model = manifest["models"].get(job) if role["policy"] in experiment.MODEL_POLICIES else None
        require(role["policy"] not in experiment.MODEL_POLICIES or model is not None,
                "external replay policy missing model")
        if model:
            path = artifact(bundle, manifest, model["path"])
            require(experiment.digest(path) == model["sha256"]
                    and model["crc32"] == role["model_crc32"], "model identity mismatch")
            models[side] = {"source": path, "path": f"models/{side}.tgm",
                            "sha256": model["sha256"], "crc32": model["crc32"]}
        if job not in jobs:
            report = experiment.read_json(report_path)
            experiment.validate_report(report, manifest["seeds"], manifest["cycles"] * experiment.CYCLE_TICKS,
                                       manifest["models"].get(job),
                                       manifest.get("candidate_probe") if job == "candidate" else None,
                                       manifest["environment"])
            jobs[job] = (experiment.load_timelines(timeline_path, report), experiment.report_trials(report))
        references[side] = (role, *jobs[job])

    frames, groups = [], []
    for seed in seeds:
        for scenario in sorted(experiment.SCENARIOS):
            for side in roles:
                role, timelines, trials = references[side]
                key = scenario, role["policy"], seed
                indexed = {row["tick"]: row for row in timelines[key]}
                group = []
                for tick in ticks:
                    require(tick in indexed, f"checkpoint {tick} absent from evaluator timeline")
                    frame_id = f"{len(frames) + 1:03d}"
                    model = models.get(side)
                    frame = {"id": frame_id, "side": side, "scenario": scenario, "seed": seed,
                             "policy": role["policy"], "tick": tick,
                             "seed_dispersal": manifest["environment"].get("seed_dispersal", "narrow-v1"),
                             "water_uptake": manifest["environment"].get("water_uptake", "legacy-v1"),
                             "node_capacity": manifest["environment"].get("node_capacity", 256),
                             "model": model["path"] if model else None,
                             "model_crc32": model["crc32"] if model else None,
                             "reference": indexed[tick], "final_trial": trials[key],
                             "framebuffer": f"frames/{frame_id}.rgb565be", "png": f"frames/{frame_id}.png"}
                    frames.append(frame)
                    group.append(frame)
                groups.append(group)

    sources = experiment.source_files()
    replay_digest = experiment.digest(args.replayer)
    record = {"schema_version": 1, "kind": "garden-visual-review", "status": "running",
              "input_manifest_sha256": input_digest,
              "input_split": manifest["split"], "review_seeds": seeds, "checkpoints": ticks,
              "roles": roles,
              "panel_selection": "explicit seeds" if args.seed else "first recorded seed, not outcome-ranked",
              "source_sha256": sources, "environment": manifest["environment"],
              "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "source_note": "Current working tree is archived; replay executable is frozen by hash. Evaluator provenance is recorded separately."}
    output.mkdir(parents=True, exist_ok=False)
    experiment.write_json(output / "started.json", record)
    try:
        for name in ("bin", "models", "frames", "tools"):
            (output / name).mkdir()
        experiment.snapshot_sources(output, sources)
        shutil.copy2(bundle / "manifest.json", output / "input-manifest.json")
        require(experiment.digest(output / "input-manifest.json") == record["input_manifest_sha256"],
                "input manifest changed while freezing")
        shutil.copy2(args.replayer, output / "bin/garden-replay")
        require(experiment.digest(output / "bin/garden-replay") == replay_digest, "replayer changed while freezing")
        for model in models.values():
            shutil.copy2(model["source"], output / model["path"])
            require(experiment.digest(output / model["path"]) == model["sha256"], "model changed while freezing")
        for name in ("garden_gallery.py", "garden_experiments.py", "garden_resources.py"):
            shutil.copy2(Path(__file__).with_name(name), output / "tools" / name)
        for name in ("framebuffer_capture.py", "serial_shell.py"):
            shutil.copy2(ROOT / "scripts/container" / name, output / "tools" / name)
        for frame in frames:
            value, raw = run_frame(output, frame, output / frame["framebuffer"], args.timeout)
            frame["result"] = value
            write_png(output / frame["png"], WIDTH, HEIGHT, rgb565be_to_rgb888(raw))
            print(f"Frame {frame['id']}: {frame['scenario']} {frame['side']} tick {frame['tick']} verified",
                  flush=True)
        sheet = contact_sheet(output, groups)
        experiment.write_json(output / "frames.json", {"frames": frames, "contact_sheet": sheet})
        with (output / "index.md").open("x") as stream:
            stream.write(gallery_markdown(groups, seeds, ticks))
        require(experiment.source_files() == sources, "source changed during capture; mixed provenance")
        record["status"] = "complete"
        record["artifacts"] = {str(p.relative_to(output)): experiment.digest(p)
                               for p in sorted(output.rglob("*")) if p.is_file()}
        experiment.write_json(output / "manifest.json", record)
        print(f"Complete: {output / 'index.md'}")
    except Exception as error:
        experiment.write_json(output / "failure.json", {"status": "failed", "error": str(error)})
        raise


def verify(output: Path, timeout: int) -> None:
    manifest = experiment.read_json(output / "manifest.json")
    require(manifest["status"] == "complete" and manifest["kind"] == "garden-visual-review"
            and manifest["schema_version"] == 1, "incomplete/unsupported gallery")
    for name in manifest["artifacts"]:
        artifact(output, manifest, name)
    frames = experiment.read_json(output / "frames.json")["frames"]
    with tempfile.TemporaryDirectory(prefix="garden-visual-replay-") as temporary:
        for frame in frames:
            if frame["model"]:
                artifact(output, manifest, frame["model"])
            expected = artifact(output, manifest, frame["framebuffer"]).read_bytes()
            value, raw = run_frame(output, frame, Path(temporary) / (frame["id"] + ".raw"), timeout)
            require(value == frame["result"] and raw == expected, "frozen replay changed state or pixels")
    print(f"PASS: {len(frames)} frames reproduce recorded state and exact framebuffer bytes")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, help="Completed matched experiment (never modified)")
    parser.add_argument("--output", type=Path, help="New gallery directory")
    parser.add_argument("--verify", type=Path, help="Read-only verification using a gallery's frozen executable")
    parser.add_argument("--replayer", type=Path, default=ROOT / "build-host/toy-factory-garden-replay")
    parser.add_argument("--seed", action="append", default=[], help="Exact eight-hex-digit world seed; repeat up to four")
    parser.add_argument("--checkpoint", type=int, action="append", default=[], help="Recorded timeline tick; repeat up to six")
    parser.add_argument("--include-adaptive", action="store_true", help="Add the built-in adaptive control to each panel")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    if args.timeout <= 0 or len(args.checkpoint) > 6:
        parser.error("positive timeout and at most six checkpoints required")
    if args.verify:
        if args.bundle or args.output or args.seed or args.checkpoint or args.include_adaptive:
            parser.error("--verify cannot be combined with collection options")
    elif not args.bundle or not args.output:
        parser.error("--bundle and --output are required for collection")
    try:
        if args.verify:
            verify(args.verify.resolve(), args.timeout)
        else:
            collect(args)
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f"Garden gallery failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
