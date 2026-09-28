#!/usr/bin/env python3
"""Fixed energy/water ablation of the three retained first-day reserve cases."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zlib

import garden_season_seedling_reserve as reserve
from garden_seasons import require

ROOT = reserve.ROOT
RULE = "seedling-reserve-components-v1"
PROTOCOL = "benchmarks/garden-seasons/seedling-components-protocol.md"
PRIOR_SHA = "703aaaccc6570635b5247b001b4f275124fdf5d7dd9d6e9da61c07aabfd3165d"
ARMS = ("control", "both", "energy", "water")


def inputs() -> tuple[dict, list[dict]]:
    _, specs = reserve.inputs()
    raw = gzip.decompress((ROOT / "benchmarks/garden-seasons/seedling-reserve-histories.json.gz").read_bytes())
    require(hashlib.sha256(raw).hexdigest() == PRIOR_SHA, "Changed combined evidence")
    prior = json.loads(raw)
    require([case["key"] for case in prior["cases"]] == [s["key"] for s in specs], "Changed fixed panel")
    return prior, specs


def trace_path(output: Path, spec: dict, arm: str, repeat: bool = False) -> Path:
    return output / f"{spec['key']}-{arm}{'.repeat' if repeat else ''}.jsonl.gz"


def analyze(output: Path, spec: dict, old: dict) -> dict:
    result = {"key": spec["key"], "case": old["case"], "contrasts": {}, "arms": {},
              "traces": {}, "terminal_events": {}}
    for arm in ARMS:
        path = trace_path(output, spec, arm)
        sha = reserve.digest(path)
        require(sha == reserve.digest(trace_path(output, spec, arm, True)), "Nonrepeatable/changed trace")
        result["traces"][arm] = sha
        if arm in ("control", "both"):
            require(sha == old["traces"]["control" if arm == "control" else "guard"],
                    "Changed frozen control/combined native trace")
    for component in ARMS[1:]:
        pair = reserve.analyze_pair(trace_path(output, spec, "control"),
                                    trace_path(output, spec, component), spec, component)
        require(pair["control"] == old["control"], "Changed control analysis")
        if component == "both":
            require(all(old[key] == value for key, value in pair.items()), "Changed combined analysis")
        result["arms"]["control"] = pair["control"]
        result["arms"][component] = pair["guard"]
        result["contrasts"][component] = {key: value for key, value in pair.items()
                                          if key not in ("control", "guard", "key", "case")}
    # Preserve exact deaths of the focal and every matched pre-birth neighbor,
    # including deaths after the detailed two-day focal accounting window.
    selected = set(result["arms"]["control"]["neighbors"]) | {spec["record"]["id"]}
    for arm in ARMS:
        events = []
        for world, _, receipts in reserve.groups(trace_path(output, spec, arm)):
            events += [{"receipt": row, "climate": world["climate"], "hash": world["hash"]}
                       for row in receipts if row["id"] in selected]
        deaths = {p["id"]: p["death_tick"] for p in result["arms"][arm]["history"]["plants"]
                  if p["id"] in selected and p["death_tick"] is not None}
        require({e["receipt"]["id"]: e["receipt"]["tick"] for e in events} == deaths and
                len(events) == len(deaths), "Incomplete matched terminal events")
        result["terminal_events"][arm] = events
    return result


def render(build: Path, spec: dict, case: dict, output: Path) -> list[dict]:
    sys.path.insert(0, str(ROOT / "scripts/container"))
    from framebuffer_capture import rgb565be_to_rgb888, write_png
    frames = []
    for component in ("energy", "water"):
        for tick, world in case["arms"][component]["checkpoints"].items():
            raw_path = output / f"components-{spec['key']}-{component}-{tick}.rgb565be"
            command = [build / "toy-factory-garden-replay", "-", spec["case"]["scenario"],
                       spec["case"]["policy"], str(int(spec["case"]["seed"], 16)), "--climate", "seasonal",
                       "--ticks", tick, "--framebuffer", raw_path, "--seedling-reserve", str(spec["record"]["id"]),
                       "--seedling-reserve-component", component]
            row = json.loads(subprocess.check_output(list(map(str, command)), text=True, timeout=300))
            raw = raw_path.read_bytes()
            require(len(raw) == 115200 and row["hash"] == world["hash"] and
                    row["framebuffer_crc32"] == f"{zlib.crc32(raw):08x}" and
                    row["seedling_reserve"] == world["seedling_reserve"], "Render/state/CRC mismatch")
            png = raw_path.with_suffix(".png")
            write_png(png, 240, 240, rgb565be_to_rgb888(raw))
            frames.append({"png": "frames/" + png.name, "png_sha256": reserve.digest(png),
                           "tick": int(tick), "arm": component, "hash": row["hash"],
                           "framebuffer_crc32": row["framebuffer_crc32"]})
    require(len(frames) == 4, "Incomplete component captures")
    return frames


def verify_frames(output: Path, spec: dict, case: dict) -> None:
    expected = {(arm, spec["record"]["birth_tick"] + days * reserve.DAY)
                for arm in ("energy", "water") for days in (1, 2)}
    frames = case["frames"]
    require(len(frames) == 4 and {(f["arm"], f["tick"]) for f in frames} == expected,
            "Changed frame selection")
    for frame in frames:
        require(reserve.digest(output / frame["png"]) == frame["png_sha256"], "Changed PNG")
        require(frame["hash"] == case["arms"][frame["arm"]]["checkpoints"][str(frame["tick"])]["hash"],
                "Changed rendered checkpoint")


def compact(report: dict) -> dict:
    result = json.loads(json.dumps(report))
    for case in result["cases"]:
        for arm in case["arms"].values():
            steps = arm.pop("steps")
            arm["steps_sha256"] = hashlib.sha256(json.dumps(steps, sort_keys=True).encode()).hexdigest()
    return result


def frozen(build: Path) -> dict:
    result = reserve.frozen(build)
    for name in (PROTOCOL, "sim/garden_season_seedling_components.py",
                 "sim/test_garden_season_seedling_components.py", "sim/test_garden_season_seedling_reserve.py"):
        result["sources"][name] = reserve.digest(ROOT / name)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "verify"))
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--build", type=Path, default=Path("artifacts/build-host-seasonal-seedling-components"))
    args = parser.parse_args()
    prior, specs = inputs()
    if args.command == "verify":
        report = json.loads((args.out / "results.json").read_text())
        require(report["protocol"] == RULE and report["input_sha256"] == PRIOR_SHA and
                len(report["cases"]) == 3, "Changed comparison identity")
        for spec, old, saved in zip(specs, prior["cases"], report["cases"]):
            actual = analyze(args.out, spec, old)
            require(all(saved[key] == value for key, value in actual.items()), "Changed paired analysis")
            verify_frames(args.out, spec, saved)
            for frame in saved["frames"]:
                raw = (args.out / frame["png"]).with_suffix(".rgb565be").read_bytes()
                require(len(raw) == 115200 and f"{zlib.crc32(raw):08x}" == frame["framebuffer_crc32"],
                        "Changed raw framebuffer")
        require(compact(report) == json.loads((args.out / "summary.json").read_text()), "Changed summary")
        print("Verified all twelve repeated traces, old controls, components, budgets, neighbors and images")
        return
    build = args.build.resolve()
    provenance = frozen(build)
    require(provenance["flags"] == prior["frozen"]["flags"], "Changed ecology flags")
    allowed = {"sim/garden_inspect.c", "sim/garden_replay.c", "sim/garden_seedling_reserve.c",
               "sim/garden_seedling_reserve.h", "sim/garden_seedling_reserve_test.c",
               "sim/garden_season_seedling_reserve.py", "sim/CMakeLists.txt"}
    for name, sha in prior["frozen"]["sources"].items():
        if name not in allowed:
            require(reserve.digest(ROOT / name) == sha, "Changed frozen dependency: " + name)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "frames").mkdir()

    def run(item):
        spec, old = item
        for arm in ARMS:
            component = "both" if arm == "control" else arm
            for repeat in (False, True):
                path = trace_path(args.out, spec, arm, repeat)
                reserve.capture(build, spec, arm != "control", path, component)
                if arm in ("control", "both"):
                    require(reserve.digest(path) == old["traces"]["control" if arm == "control" else "guard"],
                            "Changed frozen native trace")
            require(reserve.digest(trace_path(args.out, spec, arm)) ==
                    reserve.digest(trace_path(args.out, spec, arm, True)), "Nonrepeatable trace")
            print(f"Repeated {spec['key']} / {arm}", flush=True)
        case = analyze(args.out, spec, old)
        case["frames"] = render(build, spec, case, args.out / "frames")
        verify_frames(args.out, spec, case)
        print("Audited " + spec["key"], flush=True)
        return case

    with ThreadPoolExecutor(max_workers=2) as pool:
        cases = list(pool.map(run, zip(specs, prior["cases"])))
    require(provenance == frozen(build), "Inputs changed during experiment")
    report = {"protocol": RULE, "input_sha256": PRIOR_SHA, "frozen": provenance, "cases": cases}
    (args.out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.out / "summary.json").write_text(json.dumps(compact(report), indent=2) + "\n")
    print("Completed fixed four-arm component panel")


if __name__ == "__main__":
    main()
