#!/usr/bin/env python3
"""Freeze and compare the predeclared host-only leaf-maintenance-v1 panel."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import zlib

import garden_experiments as experiment
from garden_resources import budget, require
from garden_gallery import contact_sheet, rgb565be_to_rgb888, write_png

ENVIRONMENT = "leaf-maintenance-v1"
MODES = ("none", "all", "selective")
TICKS = 92160
FRAME_TICKS = (3840, 15360, 61440, TICKS)
FRAME_SEED = "9c530b07"
MODEL_SHA = "bd9f9c6ba7f5fd17309f917972da5f759c305c077798e1d4ba9a52701e2cd48b"


def check_identity(value: dict, mode: str, capacity: int, drainage: str | None = None,
                   growth_policy: str | None = None, *, seed_capacity: int = 8,
                   seed_reserve: str | None = None,
                   root_bootstrap_after: int | None = None) -> None:
    require(root_bootstrap_after is None or (root_bootstrap_after > 0 and root_bootstrap_after % 15 == 0),
            "invalid root bootstrap boundary")
    require(value.get("root_bootstrap_after") == root_bootstrap_after and
            value.get("root_bootstrap_rule") == ("wet-root-bootstrap-v1" if root_bootstrap_after is not None else None),
            "wrong root bootstrap identity")
    require(seed_reserve in (None, "sunset-seed-reserve-v1") and
            value.get("seed_reserve_rule") == seed_reserve, "wrong seed reserve rule")
    require(value.get("leaf_environment") == ENVIRONMENT and value.get("leaf_policy") == mode,
            "wrong maintenance environment/policy")
    require(value.get("node_capacity", 256) == capacity, "wrong node capacity")
    require(value.get("drainage_rule") == drainage, "wrong drainage environment")
    require(value.get("growth_policy") == growth_policy, "wrong growth policy")
    require(seed_capacity in (8, 16) and value.get("seed_capacity", 8) == seed_capacity,
            "wrong seed capacity")


def audit_trace(path: Path, mode: str, capacity: int, horizon: int = TICKS) -> dict:
    previous = {}
    hashes = {}
    seen_sites = {}
    totals = defaultdict(int)
    latest = None
    with gzip.open(path, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            if row["type"] == "leaf-bid":
                site = (row["id"], row["site_x"], row["site_y"])
                if site in seen_sites:
                    totals["maximum_site_revisit_ticks"] = max(
                        totals["maximum_site_revisit_ticks"], row["tick"] - seen_sites[site])
                seen_sites[site] = row["tick"]
                totals["bids"] += 1
                totals["renewal_bids"] += row["action"] == 1
                totals["maximum_sampled_leaves"] = max(totals["maximum_sampled_leaves"], row["mature_leaves"])
                continue
            if row["type"] != "world":
                continue
            check_identity(row, mode, capacity)
            tick = row["tick"]
            require(latest is None and tick == 0 or latest is not None and tick == latest + 15,
                    "missing ecology sample")
            hashes[tick] = row["hash"]
            for plant in row["plants"]:
                old = previous.get(plant["id"])
                if plant["dead"]:
                    totals["terminal_steps"] += old is not None and not old["dead"]
                    continue
                if tick:
                    for key, value in budget(old, plant, tick).items():
                        totals[key] += value
                    totals["checked_live_steps"] += 1
                    old_leaf = old["leaf"] if old else {"conditions": [], "restored": 0, "worn": 0}
                    expected = (sum(old_leaf["conditions"]) + 255 * (plant["leaves"] - (old["leaves"] if old else 0))
                                + plant["leaf"]["restored"] - old_leaf["restored"]
                                - plant["leaf"]["worn"] + old_leaf["worn"])
                    require(sum(plant["leaf"]["conditions"]) == expected,
                            f"condition budget mismatch at {tick}/{plant['id']}")
                    totals["checked_condition_steps"] += 1
            previous = {plant["id"]: plant for plant in row["plants"]}
            latest = tick
    require(latest == horizon, "truncated trace")
    return {"totals": dict(totals), "hashes": hashes}


def summarize(cases: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for case in cases:
        groups[(case["leaf_policy"], case["growth_policy"])].append(case["trial"])
    result = []
    for (mode, growth), trials in sorted(groups.items()):
        totals = {key: sum(t[key] for t in trials) for key in (
            "germinations", "living", "deaths", "sampled_energy", "sampled_water", "sampled_stress")}
        totals.update({key: sum(t["lifetimes"][key] for t in trials) for key in (
            "eligible_offspring", "cycle_survivors", "cycle_survivors_with_surviving_child")})
        totals.update({key: sum(t["leaf"][key] for t in trials) for key in (
            "observations", "proposals", "renewals", "restored", "worn", "late_renewals", "late_births", "late_deaths")})
        living_samples = sum(t["living_plant_ticks"] for t in trials) / 15
        totals.update({"leaf_policy": mode, "growth_policy": growth,
                       "extinct_worlds": sum(t["living"] == 0 for t in trials),
                       "worlds_with_late_births": sum(t["leaf"]["late_births"] > 0 for t in trials),
                       "maximum_mature_leaves": max(t["leaf"]["maximum_mature_leaves"] for t in trials),
                       "mean_condition": sum(t["leaf"]["condition_sum"] for t in trials)
                                         / max(1, sum(t["leaf"]["samples"] for t in trials)),
                       "mean_energy_per_living_sample_approx": totals["sampled_energy"] / max(1, living_samples),
                       "mean_water_per_living_sample_approx": totals["sampled_water"] / max(1, living_samples)})
        result.append(totals)
    return result


def collect(build: Path, model: Path, output: Path, capacity: int) -> None:
    require(experiment.digest(model) == MODEL_SHA, "use the predeclared frozen growth model")
    output = output.resolve()
    require(not output.is_relative_to(experiment.ROOT) or output.is_relative_to(experiment.ROOT / "artifacts"),
            "output must be outside source or under artifacts/")
    output.mkdir(parents=True, exist_ok=False)
    for folder in ("bin", "reports", "frames", "traces"):
        (output / folder).mkdir()
    sources = experiment.source_files()
    experiment.snapshot_sources(output, sources)
    for name in ("eval", "inspect", "replay"):
        shutil.copy2(build / f"toy-factory-garden-{name}", output / "bin" / name)
    shutil.copy2(build / "CMakeCache.txt", output / "build-cache.txt")
    shutil.copy2(model, output / "model.tgm")
    experiment.write_json(output / "started.json", {"source_sha256": sources, "node_capacity": capacity,
        "environment": ENVIRONMENT, "model_sha256": MODEL_SHA,
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=experiment.ROOT, text=True).strip()})
    frozen = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
    commands = []
    reports = {}

    def evaluate(job: tuple[str, bool]) -> tuple[tuple[str, bool], dict]:
        mode, veto = job
        name = mode + ("-veto" if veto else "-original")
        command = ["bin/eval", "--rainfed", "--trials", "8", "--ticks", str(TICKS), "--seed", "0x6d617463",
                   "--model", "model.tgm", "--leaf-policy", mode, *(["--no-night-growth"] if veto else [])]
        started = time.monotonic()
        experiment.command_run(command, output / "reports" / f"{name}.json", output, 600)
        report = experiment.read_json(output / "reports" / f"{name}.json")
        check_identity(report, mode, capacity)
        environment = {**experiment.COMBINED_ENVIRONMENT, **({"node_capacity": capacity} if capacity == 512 else {})}
        require(report["environment"] == {**environment, "leaf_maintenance": ENVIRONMENT, "leaf_policy": mode},
                "wrong underlying ecology")
        experiment.validate_report({**report, "environment": environment}, experiment.trial_seeds(0x6d617463, 8),
                                   TICKS, {"crc32": "dc5e849d"}, experiment.NIGHT_PROBE if veto else None, environment)
        print(f"{capacity}/{name}: validated 48 trials", flush=True)
        return job, {"report": report, "command": command, "elapsed_seconds": time.monotonic() - started}

    with ThreadPoolExecutor(max_workers=2) as pool:
        reports.update(pool.map(evaluate, [(mode, veto) for mode in MODES for veto in (False, True)]))
    cases = []
    for mode in MODES:
        original = experiment.report_trials(reports[(mode, False)]["report"])
        veto = experiment.report_trials(reports[(mode, True)]["report"])
        for key, trial in veto.items():
            if key[1] in ("adaptive", "baseline"):
                require(trial == original[key], "unrelated growth controls changed between evaluator runs")
        for key, trial in {**original, **veto}.items():
            if key[1] != "baseline":
                cases.append({"leaf_policy": mode, "scenario": key[0], "growth_policy": key[1],
                              "seed": key[2], "trial": trial})
    for data in reports.values():
        commands.append({"command": data["command"], "elapsed_seconds": data["elapsed_seconds"]})
    experiment.write_json(output / "cases.json", cases)
    experiment.write_json(output / "summary.json", summarize(cases))
    frames = []
    trace_totals = {}
    for mode in MODES:
        replay = ["bin/replay", "model.tgm", "rainfed", experiment.NIGHT_POLICY, "0x" + FRAME_SEED,
                  "--leaf-policy", mode]
        inspect = ["bin/inspect", "model.tgm", "rainfed", experiment.NIGHT_POLICY, "0x" + FRAME_SEED,
                   "--leaf-policy", mode, "--ticks", str(TICKS), "--ecology"]
        with tempfile.TemporaryDirectory(prefix="garden-leaf-trace-") as temp:
            raw_trace = Path(temp) / "trace.jsonl"
            experiment.command_run(inspect, raw_trace, output, 600)
            experiment.compress(raw_trace, output / "traces" / f"{mode}.jsonl.gz")
        audit = audit_trace(output / "traces" / f"{mode}.jsonl.gz", mode, capacity)
        trace_totals[mode] = audit["totals"]
        expected = experiment.report_trials(reports[(mode, True)]["report"])[("rainfed", experiment.NIGHT_POLICY, FRAME_SEED)]
        require(audit["hashes"][TICKS] == expected["hash"], "traced evaluator hash mismatch")
        commands.append({"command": inspect})
        group = []
        for tick in FRAME_TICKS:
            name = f"{mode}-{tick}"
            raw_path = f"frames/{name}.rgb565"
            command = replay + ["--ticks", str(tick), "--framebuffer", raw_path]
            experiment.command_run(command, output / "frames" / f"{name}.json", output, 600)
            frame = experiment.read_json(output / "frames" / f"{name}.json")
            check_identity(frame, mode, capacity)
            require(frame["hash"] == audit["hashes"][tick], "frame/inspector hash mismatch")
            raw = (output / raw_path).read_bytes()
            require(len(raw) == 240 * 240 * 2 and f"{zlib.crc32(raw):08x}" == frame["framebuffer_crc32"], "invalid frame")
            write_png(output / "frames" / f"{name}.png", 240, 240, rgb565be_to_rgb888(raw))
            frame.update(id=name, framebuffer=raw_path)
            group.append(frame)
            commands.append({"command": command})
        # Independent headless repeat of each final state, in addition to traced replay.
        repeat = subprocess.check_output(replay + ["--ticks", str(TICKS)], cwd=output, text=True, timeout=600)
        require(json.loads(repeat)["hash"] == expected["hash"], "headless replay mismatch")
        commands.append({"command": replay + ["--ticks", str(TICKS)]})
        frames.append(group)
        print(f"{capacity}/{mode}: exact resource/condition budgets and four native frames verified", flush=True)
    experiment.write_json(output / "trace-budgets.json", trace_totals)
    experiment.write_json(output / "frames.json", {"groups": frames, "sheet": contact_sheet(output, frames)})
    require(experiment.source_files() == sources, "source changed during collection")
    require(all(experiment.digest(output / name) == sha for name, sha in frozen.items()), "frozen input changed")
    artifacts = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
    experiment.write_json(output / "manifest.json", {"schema_version": 1, "status": "complete",
        "environment": ENVIRONMENT, "node_capacity": capacity, "commands": commands, "artifacts": artifacts})
    print(f"Complete: {output} manifest sha256={experiment.digest(output / 'manifest.json')}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--capacity", required=True, type=int, choices=(256, 512))
    args = parser.parse_args()
    collect(args.build.resolve(), args.model.resolve(), args.output, args.capacity)


if __name__ == "__main__":
    main()
