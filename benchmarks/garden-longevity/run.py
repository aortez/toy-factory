#!/usr/bin/env python3
"""Evaluate a frozen Garden model on held-out seeds over several horizons."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import statistics
import struct
import subprocess
import time
import zlib


CYCLES = (2, 4, 8, 16, 24)
TICKS_PER_CYCLE = 3840
POLICIES = {"baseline", "adaptive", "neural-candidate"}
SCENARIOS = {"unassisted", "irrigated", "crowded"}
COUNTERS = (
    "living_plant_ticks",
    "descendant_plant_ticks",
    "established_offspring",
    "deaths",
    "seeds_created",
    "germinations",
    "seeds_expired",
)


def trial_seed(base: int, index: int) -> str:
    mask = (1 << 32) - 1
    value = base ^ (((index + 1) * 0x9E3779B9) & mask)
    value ^= (value << 13) & mask
    value ^= value >> 17
    value ^= (value << 5) & mask
    return f"{value or 0x6576616C:08x}"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(report: dict, previous: dict | None) -> list[dict]:
    rows = []
    previous_by_key = {}
    if previous is not None:
        previous_by_key = {
            (scenario["name"], policy["name"], trial["seed"]): trial
            for scenario in previous["scenarios"]
            for policy in scenario["policies"]
            for trial in policy["trials"]
        }
    interval_ticks = report["tick_count"] - (previous["tick_count"] if previous else 0)
    count = report["trial_count"]
    for scenario in report["scenarios"]:
        for policy in scenario["policies"]:
            trials = policy["trials"]
            assert len(trials) == count
            row = {
                "cycles": report["tick_count"] // TICKS_PER_CYCLE,
                "scenario": scenario["name"],
                "policy": policy["name"],
                "trials": count,
                "surviving_trials": sum(t["extinction_tick"] is None for t in trials),
                "living_trials": sum(t["living"] > 0 for t in trials),
                "seed_only_trials": sum(t["living"] == 0 and t["seed_bank"] > 0 for t in trials),
                "final_living": sum(t["living"] for t in trials),
                "final_living_mean": statistics.mean(t["living"] for t in trials),
                "final_living_range": [
                    min(t["living"] for t in trials), max(t["living"] for t in trials)
                ],
                "final_seeds": sum(t["seed_bank"] for t in trials),
                "maximum_generation": max(t["maximum_generation"] for t in trials),
                "max_lineages": max(t["lineages"] for t in trials),
                "maximum_nodes": max(t["maximum_nodes"] for t in trials),
                "final_nodes": sum(t["nodes"] for t in trials),
                "death_causes": policy["totals"]["death_causes"],
                "seed_blockers": policy["totals"]["seed_germination_blockers"],
                "agent": policy["totals"]["agent"],
                "species": [],
                "interval": {"from_cycles": previous["tick_count"] // TICKS_PER_CYCLE if previous else 0},
            }
            for species in range(3):
                values = [t["species"][species] for t in trials]
                row["species"].append({
                    "name": values[0]["name"],
                    "final_living": sum(v["final_living"] for v in values),
                    "surviving_trials": sum(v["extinction_tick"] is None for v in values),
                    "established_offspring": sum(v["established_offspring"] for v in values),
                    "maximum_generation": max(v["maximum_generation"] for v in values),
                })
            for name in COUNTERS:
                total = sum(t[name] for t in trials)
                assert total == policy["totals"][name], (name, total)
                row[name] = total
                old_total = sum(
                    previous_by_key[(scenario["name"], policy["name"], t["seed"])][name]
                    for t in trials
                ) if previous else 0
                assert total >= old_total, (name, total, old_total)
                row["interval"][name] = total - old_total
            row["interval"]["mean_living"] = row["interval"]["living_plant_ticks"] / (count * interval_ticks)
            row["interval"]["mean_descendants"] = row["interval"]["descendant_plant_ticks"] / (count * interval_ticks)
            row["interval"]["trials_with_germinations"] = sum(
                t["germinations"] > (
                    previous_by_key[(scenario["name"], policy["name"], t["seed"])]["germinations"]
                    if previous else 0
                ) for t in trials
            )
            extinctions = [t["extinction_tick"] / TICKS_PER_CYCLE for t in trials if t["extinction_tick"] is not None]
            row["extinction_cycles_among_extinct"] = {
                "min": min(extinctions), "median": statistics.median(extinctions),
                "max": max(extinctions),
            } if extinctions else None
            for trial in trials:
                assert (trial["extinction_tick"] is None) == (trial["living"] + trial["seed_bank"] > 0)
                if previous:
                    old = previous_by_key[(scenario["name"], policy["name"], trial["seed"])]
                    if old["extinction_tick"] is not None:
                        assert trial["extinction_tick"] == old["extinction_tick"]
            rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=Path("build-host/toy-factory-garden-eval"))
    parser.add_argument("--model", type=Path, default=Path("artifacts/garden-champion.tgm"))
    parser.add_argument("--training", type=Path, default=Path("artifacts/garden-training.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trials", type=int, default=32, choices=range(1, 65), metavar="1-64")
    parser.add_argument("--seed", type=lambda v: int(v, 0), default=0x686F6C64)
    parser.add_argument("--jobs", type=int, default=3, choices=range(1, 6))
    args = parser.parse_args()
    if not 0 < args.seed <= 0xFFFFFFFF:
        parser.error("seed must be a nonzero uint32")
    training = json.loads(args.training.read_text())
    training_seeds = {
        trial_seed(int(training["base_seed"], 16), index)
        for index in range(training["settings"]["trials_per_scenario"])
    }
    held_out_seeds = [trial_seed(args.seed, index) for index in range(args.trials)]
    assert not training_seeds.intersection(held_out_seeds), "training/validation seed overlap"
    model_data = args.model.read_bytes()
    assert len(model_data) == 1220
    magic, version, header_size, payload_size, crc = struct.unpack_from("<IHHII", model_data)
    assert (magic, version, header_size, payload_size) == (0x314D4754, 1, 16, 1204)
    assert crc == zlib.crc32(model_data[16:])
    assert f"{crc:08x}" == training["final"]["model_crc32"]
    args.output.mkdir(parents=True, exist_ok=False)
    model_path = args.output / "champion.tgm"
    model_path.write_bytes(model_data)
    (args.output / "training.json").write_bytes(args.training.read_bytes())
    tracked_sources = sorted(Path("src").glob("*.[ch]")) + sorted(Path("sim").glob("*.[ch]"))
    provenance = {
        "schema_version": 1,
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "git_status": subprocess.check_output(["git", "status", "--short"], text=True),
        "source_sha256": {str(p): sha256(p) for p in tracked_sources},
        "runner_sha256": sha256(Path(__file__)),
        "binary_sha256": sha256(args.binary),
        "model_sha256": sha256(model_path),
        "model_crc32": f"{crc:08x}",
        "base_seed": f"{args.seed:08x}",
        "training_seeds": sorted(training_seeds),
        "held_out_seeds": held_out_seeds,
        "cycles": CYCLES,
        "ticks_per_cycle": TICKS_PER_CYCLE,
        "trial_count": args.trials,
    }
    (args.output / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")

    def evaluate(cycles: int) -> tuple[int, dict]:
        command = [
            str(args.binary.resolve()), "--model", str(model_path.resolve()),
            "--trials", str(args.trials), "--ticks", str(cycles * TICKS_PER_CYCLE),
            "--seed", hex(args.seed),
        ]
        started = time.monotonic()
        completed = subprocess.run(command, capture_output=True, text=True, check=True)
        report = json.loads(completed.stdout)
        assert report["candidate_model_crc32"] == f"{crc:08x}"
        assert report["tick_count"] == cycles * TICKS_PER_CYCLE
        assert {s["name"] for s in report["scenarios"]} == SCENARIOS
        for scenario in report["scenarios"]:
            assert {p["name"] for p in scenario["policies"]} == POLICIES
            for policy in scenario["policies"]:
                assert [t["seed"] for t in policy["trials"]] == held_out_seeds
        (args.output / f"cycles-{cycles:02d}.json").write_text(completed.stdout)
        print(f"{cycles:2d} cycles finished in {time.monotonic() - started:.2f}s", flush=True)
        return cycles, report

    reports = {}
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for future in as_completed([pool.submit(evaluate, cycles) for cycles in CYCLES]):
            cycles, report = future.result()
            reports[cycles] = report
    summary = []
    previous = None
    for cycles in CYCLES:
        summary.extend(summarize(reports[cycles], previous))
        previous = reports[cycles]
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("cycles scenario    policy             survive living-mean estab maxgen late-births")
    for row in summary:
        print(f'{row["cycles"]:6d} {row["scenario"]:11s} {row["policy"]:18s}'
              f' {row["surviving_trials"]:2d}/{row["trials"]:<2d}'
              f' {row["final_living_mean"]:11.2f} {row["established_offspring"]:5d}'
              f' {row["maximum_generation"]:6d} {row["interval"]["germinations"]:11d}')
    print(f"total elapsed: {time.monotonic() - started:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
