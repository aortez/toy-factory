#!/usr/bin/env python3
"""Matched, unassisted seasonal trials; daily censuses and natural-death observations."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zlib

DAY_TICKS = 256 * 15
MODES = ("steady", "winter", "drought", "seasonal")


def source_hashes(root: Path) -> dict:
    files = [p for folder in ("src", "sim") for p in sorted((root / folder).glob("*"))
             if p.suffix in (".c", ".h")]
    files.append(Path(__file__).resolve())
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def screenshots(build: Path, output: Path, results: list[dict], seed: int) -> list[dict]:
    # Fixed first-seed panel, not a search for attractive survivors.
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts/container"))
    from framebuffer_capture import rgb565be_to_rgb888, write_png

    frames = []
    output.mkdir()
    for case in results:
        if case["scenario"] != "rainfed" or case["policy"] != "adaptive" or case["seed"] != f"{seed:08x}":
            continue
        for day in (3, 5, 14, 16):
            name = f"{case['mode']}-day-{day:02}"
            raw = output / (name + ".rgb565be")
            command = [build / "toy-factory-garden-replay", "-", case["scenario"], case["policy"],
                       str(seed), "--ticks", str(day * DAY_TICKS), "--climate", case["mode"],
                       "--framebuffer", raw]
            result = json.loads(subprocess.check_output(list(map(str, command)), text=True))
            data = raw.read_bytes()
            if (result["hash"] != case["daily"][day]["hash"] or len(data) != 240 * 240 * 2 or
                    result["framebuffer_crc32"] != f"{zlib.crc32(data):08x}"):
                raise RuntimeError("Screenshot replay mismatch")
            png = output / (name + ".png")
            write_png(png, 240, 240, rgb565be_to_rgb888(data))
            frames.append({"png": str(png.relative_to(output.parent)), "day": day,
                           "mode": case["mode"], "hash": result["hash"],
                           "framebuffer_crc32": result["framebuffer_crc32"]})
    return frames


def run_case(inspector: Path, days: int, scenario: str, policy: str, seed: int, mode: str) -> dict:
    command = [str(inspector), "-", scenario, policy, str(seed), "--ticks", str(days * DAY_TICKS),
               "--climate", mode]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    rows = [row for line in result.stdout.splitlines() if (row := json.loads(line))["type"] == "world"]
    if not rows or rows[0]["tick"] != 0 or rows[-1]["tick"] != days * DAY_TICKS:
        raise RuntimeError("Incomplete seasonal trial")
    daily, deaths, seen_dead = [], [], set()
    for row in rows:
        if row["climate"]["mode"] != mode or row["seed_lifetime_ecology_ticks"] != 8192:
            raise RuntimeError("Unexpected environment contract")
        for plant in row["plants"]:
            if plant["dead"] and plant["id"] not in seen_dead:
                seen_dead.add(plant["id"])
                deaths.append({"tick": row["tick"], "id": plant["id"],
                               "generation": plant["generation"], "flags": plant["flags"],
                               "climate": row["climate"]})
        if row["tick"] % DAY_TICKS == 0:
            daily.append({"day": row["tick"] // DAY_TICKS,
                          **{key: row[key] for key in ("hash", "living", "nodes", "births", "deaths",
                             "seeds_created", "seeds_expired", "moisture", "rain_deposited",
                             "rain_runoff", "max_generation", "climate")},
                          "seed_bank": len(row["seeds"]),
                          "oldest_seed": max((s["age"] for s in row["seeds"]), default=0),
                          "species": sorted({p["species"] for p in row["plants"] if not p["dead"]})})
    if len(daily) != days + 1 or len(deaths) != rows[-1]["deaths"]:
        raise RuntimeError("Missing daily census or natural-death transition")
    final = daily[-1]
    return {"scenario": scenario, "policy": policy, "seed": f"{seed:08x}", "mode": mode,
            "environment": {"node_capacity": rows[0].get("node_capacity", 256),
                            "seed_capacity": rows[0].get("seed_capacity", 8),
                            "seed_lifetime_ecology_ticks": rows[0]["seed_lifetime_ecology_ticks"],
                            "leaf_environment": rows[0].get("leaf_environment")},
            "daily": daily, "deaths": deaths,
            "closing_births": final["births"] - daily[max(0, days - 16)]["births"],
            "empty_day": next((r["day"] for r in daily if not r["living"] and not r["seed_bank"]), None)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=Path("build-host"))
    parser.add_argument("--out", type=Path, required=True, help="New output directory")
    parser.add_argument("--days", type=int, default=64)
    parser.add_argument("--trials", type=int, default=2)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--screenshots", action="store_true", help="Capture a fixed, hash-verified first-seed panel")
    args = parser.parse_args()
    if not 32 <= args.days <= 256 or not 1 <= args.trials <= 16 or not 1 <= args.jobs <= 16:
        parser.error("Require 32–256 days, 1–16 trials and 1–16 jobs")
    inspector = (args.build / "toy-factory-garden-inspect").resolve()
    if not inspector.is_file():
        parser.error("Build the host inspector first")
    args.out.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    sources = source_hashes(root)
    binary_hash = hashlib.sha256(inspector.read_bytes()).hexdigest()
    replayer = (args.build / "toy-factory-garden-replay").resolve()
    replay_hash = hashlib.sha256(replayer.read_bytes()).hexdigest() if args.screenshots else None
    seeds = [(0x6576616c ^ ((i + 1) * 0x9e3779b9)) & 0xffffffff for i in range(args.trials)]
    cases = [(scenario, policy, seed, mode) for scenario in ("rainfed", "rainfed-crowded")
             for policy in ("baseline", "adaptive") for seed in seeds for mode in MODES]
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(lambda case: run_case(inspector, args.days, *case), cases))
    frames = screenshots(args.build.resolve(), args.out / "frames", results, seeds[0]) if args.screenshots else []
    if source_hashes(root) != sources or hashlib.sha256(inspector.read_bytes()).hexdigest() != binary_hash:
        raise RuntimeError("Sources or inspector changed during the experiment")
    if args.screenshots and hashlib.sha256(replayer.read_bytes()).hexdigest() != replay_hash:
        raise RuntimeError("Replayer changed during the experiment")
    report = {"protocol": "garden-seasons-v1", "days": args.days, "trials": args.trials,
              "gardener": False, "irrigation": False, "source_sha256": sources,
              "inspector_sha256": binary_hash, "replayer_sha256": replay_hash,
              "frames": frames, "cases": results}
    (args.out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print("mode worlds living-at-end extinct births closing-births deaths")
    for mode in MODES:
        group = [r for r in results if r["mode"] == mode]
        print(mode, len(group), sum(r["daily"][-1]["living"] > 0 for r in group),
              sum(r["empty_day"] is not None for r in group),
              sum(r["daily"][-1]["births"] for r in group), sum(r["closing_births"] for r in group),
              sum(len(r["deaths"]) for r in group))


if __name__ == "__main__":
    main()
