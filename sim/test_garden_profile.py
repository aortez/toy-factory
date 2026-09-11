#!/usr/bin/env python3
"""Smoke-test the optimized Garden profiler and its deterministic checkpoints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


EXPECTED_CHECKPOINTS = {
    "initial": (0, "bfb614d6", "c515c869"),
    "growing": (930, "c7492628", "061d06d1"),
    "mature": (3771, "481cbd42", "20d36204"),
}
EXPECTED_STATE = {
    "initial": {
        "plants": 3,
        "living": 3,
        "dead": 0,
        "nodes": 12,
        "blooms": 0,
        "deaths": 0,
        "reclaimed_plants": 0,
        "reclaimed_nodes": 0,
        "seeds": 0,
        "seeds_created": 0,
        "germinations": 0,
        "seeds_expired": 0,
        "mutations": 0,
        "max_generation": 0,
        "moisture": 1536,
    },
    "growing": {
        "plants": 5,
        "living": 5,
        "dead": 0,
        "nodes": 147,
        "blooms": 3,
        "deaths": 0,
        "reclaimed_plants": 0,
        "reclaimed_nodes": 0,
        "seeds": 1,
        "seeds_created": 1,
        "germinations": 0,
        "seeds_expired": 0,
        "mutations": 0,
        "max_generation": 0,
        "moisture": 4652,
    },
    "mature": {
        "plants": 5,
        "living": 5,
        "dead": 0,
        "nodes": 190,
        "blooms": 11,
        "deaths": 1,
        "reclaimed_plants": 1,
        "reclaimed_nodes": 34,
        "seeds": 3,
        "seeds_created": 3,
        "germinations": 0,
        "seeds_expired": 0,
        "mutations": 2,
        "max_generation": 0,
        "moisture": 3520,
    },
}
TIMING_NAMES = ("ordinary_step", "ecology_step", "snapshot", "raster")
PRESENTATION_RATES = {30, 10, 4}
TICKS_PER_FRAME = {30: 2, 10: 6, 4: 15}
DELTA_FRAME_COUNT = 60


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
    if not minimum <= _mean <= maximum:
        raise RuntimeError(f"{name} timing mean is outside its range")


def validate_counts(name: str, counts: object) -> None:
    if not isinstance(counts, dict):
        raise RuntimeError(f"{name} counts are not an object")
    values = [counts.get(key) for key in ("min", "p50", "mean", "p95", "max")]
    if any(not isinstance(value, int) or value < 0 for value in values):
        raise RuntimeError(f"{name} contains invalid counts")
    minimum, p50, _mean, p95, maximum = values
    if not minimum <= p50 <= p95 <= maximum:
        raise RuntimeError(f"{name} count percentiles are not ordered")
    if not minimum <= _mean <= maximum:
        raise RuntimeError(f"{name} count mean is outside its range")


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

        state = scenario.get("state")
        if not isinstance(state, dict):
            raise RuntimeError(f"{name} has no state counts")
        for count_name in (
            "plants",
            "living",
            "dead",
            "nodes",
            "blooms",
            "deaths",
            "reclaimed_plants",
            "reclaimed_nodes",
            "seeds",
            "seeds_created",
            "germinations",
            "seeds_expired",
            "mutations",
            "max_generation",
            "moisture",
        ):
            if not isinstance(state.get(count_name), int) or state[count_name] < 0:
                raise RuntimeError(f"{name} has invalid {count_name} state count")
        if state["plants"] != state["living"] + state["dead"]:
            raise RuntimeError(f"{name} plant lifecycle counts do not add up")
        if state != EXPECTED_STATE[name]:
            raise RuntimeError(f"{name} state counts changed")

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
            rate = delta["presentation_hz"]
            if delta.get("ticks_per_frame") != TICKS_PER_FRAME[rate]:
                raise RuntimeError(f"{name}.{rate}Hz has an unexpected tick cadence")
            if delta.get("frames") != DELTA_FRAME_COUNT:
                raise RuntimeError(f"{name}.{rate}Hz has an unexpected frame count")
            zero_change_frames = delta.get("zero_change_frames")
            if not isinstance(zero_change_frames, int) or not (
                0 <= zero_change_frames <= DELTA_FRAME_COUNT
            ):
                raise RuntimeError(f"{name}.{rate}Hz has an invalid unchanged-frame count")
            for count_name in (
                "changed_pixels",
                "changed_tiles_8x8",
                "bounding_box_pixels",
            ):
                validate_counts(
                    f"{name}.{rate}Hz.{count_name}",
                    delta.get(count_name),
                )

            damage = delta.get("damage_reconstruction")
            if not isinstance(damage, dict):
                raise RuntimeError(f"{name}.{rate}Hz has no damage reconstruction")
            if damage.get("verified_frames") != DELTA_FRAME_COUNT:
                raise RuntimeError(f"{name}.{rate}Hz did not verify every partial frame")
            empty_plan_frames = damage.get("empty_plan_frames")
            if not isinstance(empty_plan_frames, int) or not (
                0 <= empty_plan_frames <= zero_change_frames
            ):
                raise RuntimeError(f"{name}.{rate}Hz has an invalid empty-plan count")
            validate_timing(f"{name}.{rate}Hz.damage.plan", damage.get("plan_timing_ns"))
            validate_timing(
                f"{name}.{rate}Hz.damage.raster", damage.get("raster_timing_ns")
            )
            for count_name in (
                "tiles_8x8",
                "regions",
                "transfer_pixels",
                "raster_pixel_writes",
            ):
                validate_counts(
                    f"{name}.{rate}Hz.damage.{count_name}", damage.get(count_name)
                )
            if damage["tiles_8x8"]["max"] > 900:
                raise RuntimeError(f"{name}.{rate}Hz damages too many tiles")
            if damage["regions"]["max"] > 450:
                raise RuntimeError(f"{name}.{rate}Hz emits too many regions")
            if damage["transfer_pixels"]["max"] > 57_600:
                raise RuntimeError(f"{name}.{rate}Hz transfers too many pixels")


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
