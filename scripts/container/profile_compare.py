#!/usr/bin/env python3

"""Run isolated device physics A/B profiles and save versioned JSON artifacts."""

import argparse
import json
import os
from pathlib import Path
import re
import sys

import serial

from serial_shell import SerialShellError, SerialShellSession


MODE_NAMES = {"grid", "reference"}
SCHEMA_2_STAGE_NAMES = {
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
SCHEMA_7_STAGE_NAMES = SCHEMA_2_STAGE_NAMES | {"narrow_body_sensor"}
STAGE_NAMES = SCHEMA_7_STAGE_NAMES
SCHEMA_2_WORK_NAMES = {
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
SCHEMA_3_WORK_NAMES = SCHEMA_2_WORK_NAMES | {
    "joint_collision_filters",
    "revolute_joints",
}
SCHEMA_4_WORK_NAMES = SCHEMA_3_WORK_NAMES
SCHEMA_5_WORK_NAMES = SCHEMA_4_WORK_NAMES | {
    "revolute_motors",
    "revolute_limits",
    "joint_limit_position_correction_visits",
    "joint_limit_position_correction_changes",
    "joint_motor_solver_visits",
    "joint_motor_solver_changes",
    "joint_limit_solver_visits",
    "joint_limit_solver_changes",
}
SCHEMA_6_WORK_NAMES = SCHEMA_5_WORK_NAMES | {
    "prismatic_joints",
    "prismatic_motors",
    "prismatic_limits",
    "solver_cached_contacts",
}
SCHEMA_7_WORK_NAMES = SCHEMA_6_WORK_NAMES | {
    "body_sensor_tests",
    "active_contact_pairs",
    "sensor_overlaps",
    "contact_begin_events",
    "contact_stay_events",
    "contact_end_events",
}
SCHEMA_8_WORK_NAMES = SCHEMA_7_WORK_NAMES | {
    "awake_bodies",
    "sleeping_bodies",
    "body_sleep_transitions",
    "body_wake_transitions",
    "sleeping_contacts",
    "sleeping_joints",
}
WORK_NAMES_BY_SCHEMA = {
    2: SCHEMA_2_WORK_NAMES,
    3: SCHEMA_3_WORK_NAMES,
    4: SCHEMA_4_WORK_NAMES,
    5: SCHEMA_5_WORK_NAMES,
    6: SCHEMA_6_WORK_NAMES,
    7: SCHEMA_7_WORK_NAMES,
    8: SCHEMA_8_WORK_NAMES,
}
STAGE_NAMES_BY_SCHEMA = {
    2: SCHEMA_2_STAGE_NAMES,
    3: SCHEMA_2_STAGE_NAMES,
    4: SCHEMA_2_STAGE_NAMES,
    5: SCHEMA_2_STAGE_NAMES,
    6: SCHEMA_2_STAGE_NAMES,
    7: SCHEMA_7_STAGE_NAMES,
    8: SCHEMA_7_STAGE_NAMES,
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
    begin = one_line(output, "PROFILE_BEGIN")
    if "schema" not in begin:
        raise ProfileError("PROFILE_BEGIN fields are invalid: missing schema")
    schema_version = parse_unsigned(begin["schema"], "schema")
    if schema_version not in WORK_NAMES_BY_SCHEMA:
        raise ProfileError(f"unsupported profile schema {schema_version}")
    begin_keys = {
        "schema",
        "ticks",
        "warmup",
        "clock_hz",
        "histogram_fine_bin_us",
        "histogram_fine_bins",
        "histogram_coarse_bin_us",
        "histogram_coarse_bins",
        "clock_delta_cycles",
    }
    if schema_version >= 4:
        begin_keys |= {"fixture", "chain_links"}
    require_keys(begin, begin_keys, "PROFILE_BEGIN")
    work_names = WORK_NAMES_BY_SCHEMA[schema_version]
    stage_names = STAGE_NAMES_BY_SCHEMA[schema_version]
    ticks = parse_unsigned(begin["ticks"], "ticks")
    if ticks == 0:
        raise ProfileError("ticks must be positive")
    fixture = begin.get("fixture", "canonical")
    chain_link_count = parse_unsigned(begin.get("chain_links", "0"), "chain_links")
    if fixture in {"canonical", "canonical_neutral"}:
        if chain_link_count != 0:
            raise ProfileError(f"{fixture} fixture must report zero chain links")
    elif fixture == "revolute_chain":
        if not 1 <= chain_link_count <= 8:
            raise ProfileError("revolute-chain fixture must report 1-8 links")
    else:
        raise ProfileError(f"unsupported profile fixture '{fixture}'")

    modes: dict[str, dict[str, object]] = {}
    mode_keys = {"mode", "hash", "clock_reads_min", "clock_reads_max"}
    if schema_version == 4:
        mode_keys.add("max_revolute_error_q16")
    elif schema_version >= 5:
        mode_keys |= {
            "max_revolute_anchor_error_q16",
            "max_revolute_limit_violation_q16",
        }
        if schema_version >= 6:
            mode_keys |= {
                "max_prismatic_lateral_error_q16",
                "max_prismatic_angular_error_q16",
                "max_prismatic_limit_violation_q16",
            }
    for line in output.splitlines():
        fields = parse_fields(line, "PROFILE_MODE")
        if fields is None:
            continue
        require_keys(fields, mode_keys, line)
        mode = fields["mode"]
        if mode not in MODE_NAMES or mode in modes:
            raise ProfileError(f"unexpected or duplicate profile mode '{mode}'")
        try:
            final_hash = int(fields["hash"], 16)
        except ValueError as error:
            raise ProfileError(f"invalid {mode} hash '{fields['hash']}'") from error
        if len(fields["hash"]) != 8:
            raise ProfileError(f"invalid {mode} hash '{fields['hash']}'")
        maximum_revolute_error_q16 = parse_unsigned(
            fields.get(
                "max_revolute_anchor_error_q16",
                fields.get("max_revolute_error_q16", "0"),
            ),
            "max_revolute_anchor_error_q16",
        )
        maximum_revolute_limit_violation_q16 = parse_unsigned(
            fields.get("max_revolute_limit_violation_q16", "0"),
            "max_revolute_limit_violation_q16",
        )
        maximum_prismatic_lateral_error_q16 = parse_unsigned(
            fields.get("max_prismatic_lateral_error_q16", "0"),
            "max_prismatic_lateral_error_q16",
        )
        maximum_prismatic_angular_error_q16 = parse_unsigned(
            fields.get("max_prismatic_angular_error_q16", "0"),
            "max_prismatic_angular_error_q16",
        )
        maximum_prismatic_limit_violation_q16 = parse_unsigned(
            fields.get("max_prismatic_limit_violation_q16", "0"),
            "max_prismatic_limit_violation_q16",
        )
        modes[mode] = {
            "final_hash": f"{final_hash:08x}",
            "clock_reads_per_step": {
                "minimum": parse_unsigned(fields["clock_reads_min"], "clock_reads_min"),
                "maximum": parse_unsigned(fields["clock_reads_max"], "clock_reads_max"),
            },
            "quality": {
                "maximum_revolute_anchor_error_q16": maximum_revolute_error_q16,
                "maximum_revolute_anchor_error_pixels": round(
                    maximum_revolute_error_q16 / 65536, 6
                ),
                "maximum_revolute_limit_violation_q16": (
                    maximum_revolute_limit_violation_q16
                ),
                "maximum_revolute_limit_violation_radians": round(
                    maximum_revolute_limit_violation_q16 / 65536, 6
                ),
                "maximum_prismatic_lateral_error_q16": (
                    maximum_prismatic_lateral_error_q16
                ),
                "maximum_prismatic_lateral_error_pixels": round(
                    maximum_prismatic_lateral_error_q16 / 65536, 6
                ),
                "maximum_prismatic_angular_error_q16": (
                    maximum_prismatic_angular_error_q16
                ),
                "maximum_prismatic_angular_error_radians": round(
                    maximum_prismatic_angular_error_q16 / 65536, 6
                ),
                "maximum_prismatic_limit_violation_q16": (
                    maximum_prismatic_limit_violation_q16
                ),
                "maximum_prismatic_limit_violation_pixels": round(
                    maximum_prismatic_limit_violation_q16 / 65536, 6
                ),
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
        if mode not in modes or stage not in stage_names:
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
        if mode not in modes or metric not in work_names:
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
        if set(mode_result["stages"]) != stage_names:
            raise ProfileError(f"{mode} does not contain every timing stage")
        if set(mode_result["work"]) != work_names:
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
        "fixture": fixture,
        "chain_link_count": chain_link_count,
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


def parse_chain_link_counts(value: str) -> list[int]:
    tokens = value.split(",")
    if not tokens or any(not token.isdigit() for token in tokens):
        raise ProfileError("chain links must be a comma-separated list of unsigned integers")
    link_counts = [int(token) for token in tokens]
    if any(not 1 <= link_count <= 8 for link_count in link_counts):
        raise ProfileError("chain link counts must be 1-8")
    if len(set(link_counts)) != len(link_counts):
        raise ProfileError("chain link counts must not contain duplicates")
    return link_counts


def chain_scaling_result(
    link_counts: list[int], ticks: int, cases: dict[str, dict[str, object]]
) -> dict[str, object]:
    if set(cases) != {str(link_count) for link_count in link_counts}:
        raise ProfileError("chain profile cases do not match the requested link counts")
    return {
        "schema_version": 1,
        "benchmark": "revolute-chain-scaling",
        "measured_ticks_per_mode": ticks,
        "link_counts": link_counts,
        "cases": cases,
    }


def print_chain_summary(result: dict[str, object], output_path: Path) -> None:
    cases = result["cases"]
    link_counts = result["link_counts"]
    assert isinstance(cases, dict) and isinstance(link_counts, list)
    print("links  grid mean/p95/max      reference mean  pos/vel visits  max error  violations")
    for link_count in link_counts:
        profile = cases[str(link_count)]
        modes = profile["modes"]
        grid = modes["grid"]
        reference = modes["reference"]
        total = grid["stages"]["total"]
        position_visits = grid["work"]["joint_position_correction_visits"][
            "mean_per_tick"
        ]
        velocity_visits = grid["work"]["joint_solver_visits"]["mean_per_tick"]
        maximum_error = grid["quality"]["maximum_revolute_anchor_error_pixels"]
        print(
            f"{link_count:>5}  {total['mean_us']:>4}/{total['p95_us']:>4}/"
            f"{total['maximum_us']:>4} us  {reference['stages']['total']['mean_us']:>8} us"
            f"  {position_visits:>4g}/{velocity_visits:<4g}  {maximum_error:>8.3f}px  "
            f"{total['budget_violations']:>10}"
        )
    print(f"artifact:  {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", help="USB CDC ACM device")
    parser.add_argument("output", type=Path, help="versioned JSON artifact path")
    parser.add_argument("--ticks", type=int, default=2000, help="measured ticks per mode")
    fixture_group = parser.add_mutually_exclusive_group()
    fixture_group.add_argument(
        "--chain-links",
        help="profile comma-separated revolute-chain link counts instead of the canonical world",
    )
    fixture_group.add_argument(
        "--neutral",
        action="store_true",
        help="profile the canonical world settling under neutral input",
    )
    parser.add_argument("--owner-uid", type=int, help="set artifact owner UID")
    parser.add_argument("--owner-gid", type=int, help="set artifact owner GID")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.ticks <= 10000:
        print("ticks must be 1-10000", file=sys.stderr)
        return 1

    try:
        link_counts = (
            parse_chain_link_counts(args.chain_links) if args.chain_links is not None else []
        )
    except ProfileError as error:
        print(f"profile failed: {error}", file=sys.stderr)
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
                if link_counts:
                    cases: dict[str, dict[str, object]] = {}
                    for link_count in link_counts:
                        output = session.run(
                            f"picosystem profile chain {link_count} {args.ticks}",
                            timeout_seconds=120.0,
                        )
                        case = parse_profile(output)
                        if (
                            case["fixture"] != "revolute_chain"
                            or case["chain_link_count"] != link_count
                        ):
                            raise ProfileError(
                                f"device returned the wrong fixture for {link_count} links"
                            )
                        cases[str(link_count)] = case
                    result = chain_scaling_result(link_counts, args.ticks, cases)
                elif args.neutral:
                    output = session.run(
                        f"picosystem profile sleep {args.ticks}", timeout_seconds=120.0
                    )
                    result = parse_profile(output)
                    if result["fixture"] != "canonical_neutral":
                        raise ProfileError("device returned a non-neutral fixture")
                else:
                    output = session.run(
                        f"picosystem profile compare {args.ticks}", timeout_seconds=120.0
                    )
                    result = parse_profile(output)
                    if result["fixture"] != "canonical":
                        raise ProfileError("device returned a non-canonical fixture")
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

    if link_counts:
        print_chain_summary(result, args.output)
    else:
        print_summary(result, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
