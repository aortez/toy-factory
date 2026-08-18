#!/usr/bin/env python3

"""Run an isolated device physics A/B profile and save a versioned JSON artifact."""

import argparse
import json
import os
from pathlib import Path
import re
import sys

import serial

from serial_shell import SerialShellError, SerialShellSession


MODE_NAMES = {"grid", "reference"}
STAGE_NAMES = {
    "force_integrate",
    "box_geometry",
    "broad_phase",
    "narrow_body_body",
    "narrow_body_segment",
    "position_correction",
    "velocity_solver",
    "final_clamp",
    "other",
    "total",
}
WORK_NAMES = {
    "possible_pairs",
    "candidate_pairs",
    "grid_cell_insertions",
    "occupied_grid_cells",
    "maximum_grid_cell_occupancy",
    "body_body_tests",
    "body_segment_tests",
    "manifolds",
    "contact_points",
    "position_correction_visits",
    "solver_iterations",
    "solver_contact_visits",
    "solver_changed_contacts",
    "distance_joints",
    "joint_position_correction_visits",
    "joint_solver_visits",
    "joint_solver_changes",
    "broad_phase_fallbacks",
}
GAME_STATE_PATTERN = re.compile(r"^mode=(paused|running) tick=\d+ hash=[0-9a-fA-F]{8}$")


class ProfileError(RuntimeError):
    """The device profile output or requested operation was invalid."""


def parse_fields(line: str, prefix: str) -> dict[str, str] | None:
    marker = f"{prefix} "
    if not line.startswith(marker):
        return None

    fields: dict[str, str] = {}
    for token in line[len(marker) :].split():
        if "=" not in token:
            raise ProfileError(f"malformed {prefix} token '{token}'")
        key, value = token.split("=", 1)
        if not key or not value or key in fields:
            raise ProfileError(f"malformed or duplicate {prefix} field '{token}'")
        fields[key] = value
    return fields


def require_keys(
    fields: dict[str, str], expected: set[str], label: str
) -> dict[str, str]:
    missing = sorted(expected - fields.keys())
    unknown = sorted(fields.keys() - expected)
    if missing or unknown:
        details = []
        if missing:
            details.append(f"missing {', '.join(missing)}")
        if unknown:
            details.append(f"unknown {', '.join(unknown)}")
        raise ProfileError(f"{label} fields are invalid: {'; '.join(details)}")
    return fields


def parse_unsigned(value: str, label: str) -> int:
    if not value.isdigit():
        raise ProfileError(f"{label} must be an unsigned decimal integer")
    return int(value)


def parse_yes_no(value: str, label: str) -> bool:
    if value not in {"yes", "no"}:
        raise ProfileError(f"{label} must be yes or no")
    return value == "yes"


def one_line(output: str, prefix: str) -> dict[str, str]:
    matches = [fields for line in output.splitlines() if (fields := parse_fields(line, prefix))]
    if len(matches) != 1:
        raise ProfileError(f"expected one {prefix} line, received {len(matches)}")
    return matches[0]


def parse_profile(output: str) -> dict[str, object]:
    begin = require_keys(
        one_line(output, "PROFILE_BEGIN"),
        {
            "schema",
            "ticks",
            "warmup",
            "clock_hz",
            "histogram_fine_bin_us",
            "histogram_fine_bins",
            "histogram_coarse_bin_us",
            "histogram_coarse_bins",
            "clock_delta_cycles",
        },
        "PROFILE_BEGIN",
    )
    schema_version = parse_unsigned(begin["schema"], "schema")
    if schema_version != 2:
        raise ProfileError(f"unsupported profile schema {schema_version}")
    ticks = parse_unsigned(begin["ticks"], "ticks")
    if ticks == 0:
        raise ProfileError("ticks must be positive")

    modes: dict[str, dict[str, object]] = {}
    for line in output.splitlines():
        fields = parse_fields(line, "PROFILE_MODE")
        if fields is None:
            continue
        require_keys(fields, {"mode", "hash", "clock_reads_min", "clock_reads_max"}, line)
        mode = fields["mode"]
        if mode not in MODE_NAMES or mode in modes:
            raise ProfileError(f"unexpected or duplicate profile mode '{mode}'")
        try:
            final_hash = int(fields["hash"], 16)
        except ValueError as error:
            raise ProfileError(f"invalid {mode} hash '{fields['hash']}'") from error
        if len(fields["hash"]) != 8:
            raise ProfileError(f"invalid {mode} hash '{fields['hash']}'")
        modes[mode] = {
            "final_hash": f"{final_hash:08x}",
            "clock_reads_per_step": {
                "minimum": parse_unsigned(fields["clock_reads_min"], "clock_reads_min"),
                "maximum": parse_unsigned(fields["clock_reads_max"], "clock_reads_max"),
            },
            "stages": {},
            "work": {},
        }
    if set(modes) != MODE_NAMES:
        raise ProfileError(f"profile modes must be exactly {', '.join(sorted(MODE_NAMES))}")

    stage_keys = {
        "mode",
        "stage",
        "samples",
        "mean_us",
        "min_us",
        "p50_us",
        "p95_us",
        "p99_us",
        "max_us",
        "budget_violations",
    }
    for line in output.splitlines():
        fields = parse_fields(line, "PROFILE_STAGE")
        if fields is None:
            continue
        require_keys(fields, stage_keys, line)
        mode = fields["mode"]
        stage = fields["stage"]
        if mode not in modes or stage not in STAGE_NAMES:
            raise ProfileError(f"unexpected stage '{mode}/{stage}'")
        stages = modes[mode]["stages"]
        assert isinstance(stages, dict)
        if stage in stages:
            raise ProfileError(f"duplicate stage '{mode}/{stage}'")
        samples = parse_unsigned(fields["samples"], f"{mode}/{stage} samples")
        if samples != ticks:
            raise ProfileError(f"{mode}/{stage} has {samples} samples, expected {ticks}")
        stages[stage] = {
            "samples": samples,
            "mean_us": parse_unsigned(fields["mean_us"], "mean_us"),
            "minimum_us": parse_unsigned(fields["min_us"], "min_us"),
            "p50_us": parse_unsigned(fields["p50_us"], "p50_us"),
            "p95_us": parse_unsigned(fields["p95_us"], "p95_us"),
            "p99_us": parse_unsigned(fields["p99_us"], "p99_us"),
            "maximum_us": parse_unsigned(fields["max_us"], "max_us"),
            "budget_violations": parse_unsigned(
                fields["budget_violations"], "budget_violations"
            ),
        }

    work_keys = {"mode", "metric", "total", "max"}
    for line in output.splitlines():
        fields = parse_fields(line, "PROFILE_WORK")
        if fields is None:
            continue
        require_keys(fields, work_keys, line)
        mode = fields["mode"]
        metric = fields["metric"]
        if mode not in modes or metric not in WORK_NAMES:
            raise ProfileError(f"unexpected work metric '{mode}/{metric}'")
        work = modes[mode]["work"]
        assert isinstance(work, dict)
        if metric in work:
            raise ProfileError(f"duplicate work metric '{mode}/{metric}'")
        total = parse_unsigned(fields["total"], f"{mode}/{metric} total")
        work[metric] = {
            "total": total,
            "mean_per_tick": round(total / ticks, 6),
            "maximum_per_tick": parse_unsigned(fields["max"], f"{mode}/{metric} max"),
        }

    for mode, mode_result in modes.items():
        if set(mode_result["stages"]) != STAGE_NAMES:
            raise ProfileError(f"{mode} does not contain every timing stage")
        if set(mode_result["work"]) != WORK_NAMES:
            raise ProfileError(f"{mode} does not contain every work metric")

    resource = require_keys(
        one_line(output, "PROFILE_RESOURCE"),
        {"shell_stack_used_bytes", "shell_stack_size_bytes"},
        "PROFILE_RESOURCE",
    )
    shell_stack_used_bytes = parse_unsigned(
        resource["shell_stack_used_bytes"], "shell_stack_used_bytes"
    )
    shell_stack_size_bytes = parse_unsigned(
        resource["shell_stack_size_bytes"], "shell_stack_size_bytes"
    )
    if shell_stack_used_bytes > shell_stack_size_bytes:
        raise ProfileError("shell stack high-water exceeds its configured size")

    end = require_keys(
        one_line(output, "PROFILE_END"),
        {"hashes_match", "states_match"},
        "PROFILE_END",
    )
    hashes_match = parse_yes_no(end["hashes_match"], "hashes_match")
    states_match = parse_yes_no(end["states_match"], "states_match")
    if not hashes_match or not states_match:
        raise ProfileError("grid/reference replay did not produce identical authoritative state")

    clock_frequency_hz = parse_unsigned(begin["clock_hz"], "clock_hz")
    clock_delta_cycles = parse_unsigned(begin["clock_delta_cycles"], "clock_delta_cycles")
    maximum_clock_reads = max(
        mode_result["clock_reads_per_step"]["maximum"] for mode_result in modes.values()
    )
    estimated_clock_read_overhead_us = round(
        (clock_delta_cycles * maximum_clock_reads * 1_000_000) / clock_frequency_hz,
        3,
    )

    return {
        "schema_version": schema_version,
        "benchmark": "isolated-physics-grid-reference",
        "measured_ticks_per_mode": ticks,
        "warmup_ticks_per_mode": parse_unsigned(begin["warmup"], "warmup"),
        "clock": {
            "frequency_hz": clock_frequency_hz,
            "histogram": {
                "fine_bin_us": parse_unsigned(
                    begin["histogram_fine_bin_us"], "histogram_fine_bin_us"
                ),
                "fine_bin_count": parse_unsigned(
                    begin["histogram_fine_bins"], "histogram_fine_bins"
                ),
                "coarse_bin_us": parse_unsigned(
                    begin["histogram_coarse_bin_us"], "histogram_coarse_bin_us"
                ),
                "coarse_bin_count": parse_unsigned(
                    begin["histogram_coarse_bins"], "histogram_coarse_bins"
                ),
            },
            "back_to_back_delta_cycles": clock_delta_cycles,
            "estimated_read_overhead_us_per_step": estimated_clock_read_overhead_us,
        },
        "verification": {
            "hashes_match": hashes_match,
            "states_match": states_match,
        },
        "resources": {
            "shell_stack_used_bytes": shell_stack_used_bytes,
            "shell_stack_size_bytes": shell_stack_size_bytes,
        },
        "modes": modes,
    }


def parse_game_mode(output: str) -> str:
    matches = [match for line in output.splitlines() if (match := GAME_STATE_PATTERN.fullmatch(line))]
    if len(matches) != 1:
        raise ProfileError(f"expected one game-state line, received {len(matches)}")
    return matches[0].group(1)


def write_artifact(
    path: Path, result: dict[str, object], owner_uid: int | None, owner_gid: int | None
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if owner_uid is not None or owner_gid is not None:
        os.chown(path, -1 if owner_uid is None else owner_uid, -1 if owner_gid is None else owner_gid)


def print_summary(result: dict[str, object], output_path: Path) -> None:
    modes = result["modes"]
    assert isinstance(modes, dict)
    grid = modes["grid"]
    reference = modes["reference"]
    assert isinstance(grid, dict) and isinstance(reference, dict)
    grid_total = grid["stages"]["total"]["mean_us"]
    reference_total = reference["stages"]["total"]["mean_us"]
    speedup = float("inf") if grid_total == 0 else reference_total / grid_total
    grid_candidates = grid["work"]["candidate_pairs"]["mean_per_tick"]
    reference_candidates = reference["work"]["candidate_pairs"]["mean_per_tick"]
    clock = result["clock"]
    assert isinstance(clock, dict)
    resources = result["resources"]
    assert isinstance(resources, dict)
    print(
        f"grid:      mean={grid_total} us/tick, candidates={grid_candidates}/tick, "
        f"hash={grid['final_hash']}"
    )
    print(
        f"reference: mean={reference_total} us/tick, candidates={reference_candidates}/tick, "
        f"hash={reference['final_hash']}"
    )
    print(f"speedup:   {speedup:.2f}x; authoritative hash and state match")
    print(
        "timing:    estimated clock-read overhead "
        f"{clock['estimated_read_overhead_us_per_step']:.3f} us/profiled tick"
    )
    print(
        f"stack:     shell high-water {resources['shell_stack_used_bytes']}/"
        f"{resources['shell_stack_size_bytes']} bytes"
    )
    print(f"artifact:  {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", help="USB CDC ACM device")
    parser.add_argument("output", type=Path, help="versioned JSON artifact path")
    parser.add_argument("--ticks", type=int, default=2000, help="measured ticks per mode")
    parser.add_argument("--owner-uid", type=int, help="set artifact owner UID")
    parser.add_argument("--owner-gid", type=int, help="set artifact owner GID")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.ticks <= 10000:
        print("ticks must be 1-10000", file=sys.stderr)
        return 1

    initially_running = False
    paused_by_us = False
    result = None
    failure: Exception | None = None
    try:
        with SerialShellSession(args.port) as session:
            try:
                initially_running = parse_game_mode(session.run("picosystem game state")) == "running"
                if initially_running:
                    mode = parse_game_mode(session.run("picosystem game pause"))
                    if mode != "paused":
                        raise ProfileError("simulation did not pause")
                    paused_by_us = True
                output = session.run(
                    f"picosystem profile compare {args.ticks}", timeout_seconds=120.0
                )
                result = parse_profile(output)
                write_artifact(args.output, result, args.owner_uid, args.owner_gid)
            except (
                OSError,
                ProfileError,
                SerialShellError,
                serial.SerialException,
                ValueError,
            ) as error:
                failure = error
            finally:
                if paused_by_us:
                    try:
                        mode = parse_game_mode(session.run("picosystem game run"))
                        if mode != "running":
                            raise ProfileError("simulation did not resume")
                    except (
                        OSError,
                        ProfileError,
                        SerialShellError,
                        serial.SerialException,
                    ) as cleanup_error:
                        if failure is None:
                            failure = cleanup_error
                        else:
                            print(f"profile cleanup also failed: {cleanup_error}", file=sys.stderr)
    except (OSError, SerialShellError, serial.SerialException, ValueError) as error:
        failure = error

    if failure is not None or result is None:
        print(f"profile failed: {failure}", file=sys.stderr)
        return 1

    print_summary(result, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
