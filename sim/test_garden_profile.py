#!/usr/bin/env python3
"""Smoke-test the optimized Garden profiler and its deterministic checkpoints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


EXPECTED_CHECKPOINTS = {
    "initial": (0, "902dea55", "e7987083"),
    "growing": (930, "db601a36", "35a6e809"),
    "mature": (3771, "1d376f84", "8261b674"),
}
TIMING_NAMES = ("ordinary_step", "ecology_step", "snapshot", "raster")
PRESENTATION_RATES = {30, 10, 4}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    return parser.parse_args()


def validate_timing(name: str, timing: object) -> None:
    if not isinstance(timing, dict):
        raise RuntimeError(f"{name} timing is not an object")
    samples = timing.get("samples")
    values = [timing.get(key) for key in ("min", "p50", "mean", "p95", "max")]
    if not isinstance(samples, int) or samples <= 0:
        raise RuntimeError(f"{name} has no timing samples")
    if any(not isinstance(value, int) or value < 0 for value in values):
        raise RuntimeError(f"{name} contains invalid timing values")
    minimum, p50, _mean, p95, maximum = values
    if not minimum <= p50 <= p95 <= maximum:
        raise RuntimeError(f"{name} timing percentiles are not ordered")


def validate_counts(name: str, counts: object) -> None:
    if not isinstance(counts, dict):
        raise RuntimeError(f"{name} counts are not an object")
    values = [counts.get(key) for key in ("min", "p50", "mean", "p95", "max")]
    if any(not isinstance(value, int) or value < 0 for value in values):
        raise RuntimeError(f"{name} contains invalid counts")
    minimum, p50, _mean, p95, maximum = values
    if not minimum <= p50 <= p95 <= maximum:
        raise RuntimeError(f"{name} count percentiles are not ordered")


def validate_profile(profile: object) -> None:
    if not isinstance(profile, dict) or profile.get("schema_version") != 1:
        raise RuntimeError("unexpected Garden profile schema")
    validate_timing("clock_overhead", profile.get("clock_overhead_ns"))
    scenarios = profile.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) != len(EXPECTED_CHECKPOINTS):
        raise RuntimeError("unexpected Garden profile scenario count")

    if any(not isinstance(scenario, dict) for scenario in scenarios):
        raise RuntimeError("Garden profile scenarios must be objects")
    by_name = {scenario.get("name"): scenario for scenario in scenarios}
    if set(by_name) != set(EXPECTED_CHECKPOINTS):
        raise RuntimeError("unexpected Garden profile checkpoints")
    for name, (tick, state_hash, framebuffer_crc) in EXPECTED_CHECKPOINTS.items():
        scenario = by_name[name]
        if scenario.get("tick") != tick:
            raise RuntimeError(f"{name} tick does not match its checkpoint")
        if scenario.get("state_hash") != state_hash:
            raise RuntimeError(f"{name} state hash changed")
        if scenario.get("framebuffer_crc32") != framebuffer_crc:
            raise RuntimeError(f"{name} framebuffer CRC changed")

        timings = scenario.get("timing_ns")
        if not isinstance(timings, dict):
            raise RuntimeError(f"{name} has no timing data")
        for timing_name in TIMING_NAMES:
            validate_timing(f"{name}.{timing_name}", timings.get(timing_name))

        raster_work = scenario.get("raster_work")
        if not isinstance(raster_work, dict) or raster_work.get("pixel_writes", 0) <= 0:
            raise RuntimeError(f"{name} has no raster work counts")

        frame_deltas = scenario.get("frame_deltas")
        if not isinstance(frame_deltas, list) or len(frame_deltas) != len(PRESENTATION_RATES):
            raise RuntimeError(f"{name} has invalid frame-delta data")
        if any(not isinstance(delta, dict) for delta in frame_deltas):
            raise RuntimeError(f"{name} frame deltas must be objects")
        rates = {delta.get("presentation_hz") for delta in frame_deltas}
        if rates != PRESENTATION_RATES:
            raise RuntimeError(f"{name} has unexpected frame-delta cadences")
        for delta in frame_deltas:
            for count_name in (
                "changed_pixels",
                "changed_tiles_8x8",
                "bounding_box_pixels",
            ):
                validate_counts(
                    f"{name}.{delta['presentation_hz']}Hz.{count_name}",
                    delta.get(count_name),
                )


def main() -> int:
    arguments = parse_arguments()
    completed = subprocess.run(
        [str(arguments.binary.resolve()), "--repetitions", "1"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"Garden profiler failed: {detail}")
    validate_profile(json.loads(completed.stdout))

    for invalid_repetitions in ("0", "129", "not-a-number"):
        rejected = subprocess.run(
            [
                str(arguments.binary.resolve()),
                "--repetitions",
                invalid_repetitions,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if rejected.returncode != 2:
            raise RuntimeError(
                f"invalid repetition count {invalid_repetitions!r} was not rejected"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
