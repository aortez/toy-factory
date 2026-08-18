#!/usr/bin/env python3

"""Run the device dense-rendering profile and save a versioned JSON artifact."""

import argparse
import json
import math
import os
from pathlib import Path
import re
import sys

import serial

from serial_shell import SerialShellError, SerialShellSession


CASE_NAMES = {
    "band-10",
    "tiles-10",
    "band-25",
    "tiles-25",
    "band-50",
    "tiles-50",
    "band-75",
    "tiles-75",
    "band-100",
    "tiles-100",
    "full-100",
}
STAGE_NAMES = {"draw", "te_wait", "present", "total"}
TRANSPORT_NAMES = {"pl022", "pl022-dma", "pio-polling", "pio-dma"}
GAME_STATE_PATTERN = re.compile(r"^mode=(paused|running) tick=\d+ hash=[0-9a-fA-F]{8}$")


class RenderProfileError(RuntimeError):
    """The device render-profile output or requested operation was invalid."""


def parse_fields(line: str, prefix: str) -> dict[str, str] | None:
    marker = f"{prefix} "
    if not line.startswith(marker):
        return None

    fields: dict[str, str] = {}
    for token in line[len(marker) :].split():
        if "=" not in token:
            raise RenderProfileError(f"malformed {prefix} token '{token}'")
        key, value = token.split("=", 1)
        if not key or not value or key in fields:
            raise RenderProfileError(f"malformed or duplicate {prefix} field '{token}'")
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
        raise RenderProfileError(f"{label} fields are invalid: {'; '.join(details)}")
    return fields


def parse_unsigned(value: str, label: str) -> int:
    if not value.isdigit():
        raise RenderProfileError(f"{label} must be an unsigned decimal integer")
    return int(value)


def parse_yes_no(value: str, label: str) -> bool:
    if value not in {"yes", "no"}:
        raise RenderProfileError(f"{label} must be yes or no")
    return value == "yes"


def parse_crc32(value: str, label: str) -> str:
    if len(value) != 8:
        raise RenderProfileError(f"{label} must contain eight hexadecimal digits")
    try:
        return f"{int(value, 16):08x}"
    except ValueError as error:
        raise RenderProfileError(f"{label} must contain eight hexadecimal digits") from error


def one_line(output: str, prefix: str) -> dict[str, str]:
    matches = [fields for line in output.splitlines() if (fields := parse_fields(line, prefix))]
    if len(matches) != 1:
        raise RenderProfileError(f"expected one {prefix} line, received {len(matches)}")
    return matches[0]


def parse_timing_summary(fields: dict[str, str], label: str, sample_count: int) -> dict[str, int]:
    values = {
        "samples": parse_unsigned(fields["samples"], f"{label} samples"),
        "mean_us": parse_unsigned(fields["mean_us"], f"{label} mean_us"),
        "minimum_us": parse_unsigned(fields["min_us"], f"{label} min_us"),
        "p50_us": parse_unsigned(fields["p50_us"], f"{label} p50_us"),
        "p95_us": parse_unsigned(fields["p95_us"], f"{label} p95_us"),
        "p99_us": parse_unsigned(fields["p99_us"], f"{label} p99_us"),
        "maximum_us": parse_unsigned(fields["max_us"], f"{label} max_us"),
    }
    if values["samples"] != sample_count:
        raise RenderProfileError(
            f"{label} has {values['samples']} samples, expected {sample_count}"
        )
    ordered = [
        values["minimum_us"],
        values["p50_us"],
        values["p95_us"],
        values["p99_us"],
        values["maximum_us"],
    ]
    if ordered != sorted(ordered):
        raise RenderProfileError(f"{label} percentile timing is not monotonic")
    if not values["minimum_us"] <= values["mean_us"] <= values["maximum_us"]:
        raise RenderProfileError(f"{label} mean timing is outside its measured range")
    return values


def parse_profile(output: str) -> dict[str, object]:
    begin = require_keys(
        one_line(output, "DISPLAY_PROFILE_BEGIN"),
        {
            "schema",
            "samples",
            "warmup",
            "clock_hz",
            "configured_spi_hz",
            "width",
            "height",
            "bpp",
            "transport",
            "cases",
        },
        "DISPLAY_PROFILE_BEGIN",
    )
    schema_version = parse_unsigned(begin["schema"], "schema")
    if schema_version != 1:
        raise RenderProfileError(f"unsupported render-profile schema {schema_version}")
    sample_count = parse_unsigned(begin["samples"], "samples")
    if sample_count == 0:
        raise RenderProfileError("samples must be positive")
    width = parse_unsigned(begin["width"], "width")
    height = parse_unsigned(begin["height"], "height")
    bytes_per_pixel = parse_unsigned(begin["bpp"], "bpp")
    configured_spi_frequency_hz = parse_unsigned(
        begin["configured_spi_hz"], "configured_spi_hz"
    )
    if (
        width == 0
        or height == 0
        or bytes_per_pixel == 0
        or configured_spi_frequency_hz == 0
    ):
        raise RenderProfileError("display dimensions, pixel size, and SPI frequency must be positive")
    transport = begin["transport"]
    if transport not in TRANSPORT_NAMES:
        raise RenderProfileError(f"unknown display transport '{transport}'")
    reported_case_count = parse_unsigned(begin["cases"], "cases")
    if reported_case_count != len(CASE_NAMES):
        raise RenderProfileError(
            f"device reports {reported_case_count} cases, expected {len(CASE_NAMES)}"
        )

    cases: dict[str, dict[str, object]] = {}
    for line in output.splitlines():
        fields = parse_fields(line, "DISPLAY_PROFILE_CASE")
        if fields is None:
            continue
        require_keys(
            fields,
            {"name", "coverage", "payload_bytes", "regions", "writes", "synchronized"},
            line,
        )
        name = fields["name"]
        if name not in CASE_NAMES or name in cases:
            raise RenderProfileError(f"unexpected or duplicate render-profile case '{name}'")
        coverage = parse_unsigned(fields["coverage"], f"{name} coverage")
        payload_bytes = parse_unsigned(fields["payload_bytes"], f"{name} payload_bytes")
        expected_payload = width * height * bytes_per_pixel * coverage // 100
        if payload_bytes != expected_payload:
            raise RenderProfileError(
                f"{name} payload is {payload_bytes} bytes, expected {expected_payload}"
            )
        synchronized = parse_unsigned(fields["synchronized"], f"{name} synchronized")
        if synchronized > sample_count:
            raise RenderProfileError(f"{name} synchronized count exceeds its samples")
        regions = parse_unsigned(fields["regions"], f"{name} regions")
        writes = parse_unsigned(fields["writes"], f"{name} writes")
        if regions == 0 or writes == 0:
            raise RenderProfileError(f"{name} must issue at least one region and display write")
        cases[name] = {
            "coverage_percent": coverage,
            "payload_bytes": payload_bytes,
            "application_regions_per_frame": regions,
            "display_writes_per_frame": writes,
            "te_synchronized_samples": synchronized,
            "all_samples_te_synchronized": synchronized == sample_count,
            "stages": {},
        }
    if set(cases) != CASE_NAMES:
        raise RenderProfileError("render profile does not contain every workload case")

    stage_keys = {
        "name",
        "stage",
        "samples",
        "mean_us",
        "min_us",
        "p50_us",
        "p95_us",
        "p99_us",
        "max_us",
    }
    for line in output.splitlines():
        fields = parse_fields(line, "DISPLAY_PROFILE_STAGE")
        if fields is None:
            continue
        require_keys(fields, stage_keys, line)
        name = fields["name"]
        stage = fields["stage"]
        if name not in cases or stage not in STAGE_NAMES:
            raise RenderProfileError(f"unexpected render-profile stage '{name}/{stage}'")
        stages = cases[name]["stages"]
        assert isinstance(stages, dict)
        if stage in stages:
            raise RenderProfileError(f"duplicate render-profile stage '{name}/{stage}'")
        stages[stage] = parse_timing_summary(fields, f"{name}/{stage}", sample_count)

    for name, case in cases.items():
        stages = case["stages"]
        assert isinstance(stages, dict)
        if set(stages) != STAGE_NAMES:
            raise RenderProfileError(f"{name} does not contain every timing stage")
        payload_bytes = case["payload_bytes"]
        assert isinstance(payload_bytes, int)
        ideal_wire_time_us = math.ceil(
            payload_bytes * 8_000_000 / configured_spi_frequency_hz
        )
        present_mean_us = stages["present"]["mean_us"]
        draw_mean_us = stages["draw"]["mean_us"]
        total_mean_us = stages["total"]["mean_us"]
        case["derived"] = {
            "configured_bus_ideal_payload_time_us": ideal_wire_time_us,
            "mean_time_above_configured_bus_ideal_us": present_mean_us - ideal_wire_time_us,
            "mean_configured_bus_efficiency_percent": round(
                ideal_wire_time_us * 100 / max(present_mean_us, 1), 3
            ),
            "mean_unpaced_draw_plus_present_us": draw_mean_us + present_mean_us,
            "mean_unpaced_frames_per_second": round(
                1_000_000 / max(draw_mean_us + present_mean_us, 1), 3
            ),
            "mean_te_paced_frames_per_second": round(
                1_000_000 / max(total_mean_us, 1), 3
            ),
        }

    verify = require_keys(
        one_line(output, "DISPLAY_PROFILE_VERIFY"),
        {"original_crc32", "restored_crc32", "framebuffer_restored"},
        "DISPLAY_PROFILE_VERIFY",
    )
    framebuffer_restored = parse_yes_no(
        verify["framebuffer_restored"], "framebuffer_restored"
    )
    if not framebuffer_restored:
        raise RenderProfileError("the profiler did not restore the original framebuffer")
    original_crc32 = parse_crc32(verify["original_crc32"], "original_crc32")
    restored_crc32 = parse_crc32(verify["restored_crc32"], "restored_crc32")
    if original_crc32 != restored_crc32:
        raise RenderProfileError("restored framebuffer checksum does not match the original")

    resource = require_keys(
        one_line(output, "DISPLAY_PROFILE_RESOURCE"),
        {"shell_stack_used_bytes", "shell_stack_size_bytes"},
        "DISPLAY_PROFILE_RESOURCE",
    )
    shell_stack_used = parse_unsigned(resource["shell_stack_used_bytes"], "shell_stack_used_bytes")
    shell_stack_size = parse_unsigned(resource["shell_stack_size_bytes"], "shell_stack_size_bytes")
    if shell_stack_used > shell_stack_size:
        raise RenderProfileError("shell stack high-water exceeds its configured size")

    end = require_keys(one_line(output, "DISPLAY_PROFILE_END"), {"status"}, "DISPLAY_PROFILE_END")
    if end["status"] != "ok":
        raise RenderProfileError(f"device render profile ended with status '{end['status']}'")

    return {
        "schema_version": schema_version,
        "benchmark": "dense-display-throughput",
        "samples_per_case": sample_count,
        "warmup_samples_per_case": parse_unsigned(begin["warmup"], "warmup"),
        "clock_frequency_hz": parse_unsigned(begin["clock_hz"], "clock_hz"),
        "display": {
            "transport": transport,
            "configured_spi_frequency_hz": configured_spi_frequency_hz,
            "width": width,
            "height": height,
            "bytes_per_pixel": bytes_per_pixel,
            "framebuffer_bytes": width * height * bytes_per_pixel,
        },
        "verification": {
            "original_framebuffer_crc32": original_crc32,
            "restored_framebuffer_crc32": restored_crc32,
            "framebuffer_restored": framebuffer_restored,
        },
        "resources": {
            "shell_stack_used_bytes": shell_stack_used,
            "shell_stack_size_bytes": shell_stack_size,
        },
        "cases": cases,
    }


def parse_game_mode(output: str) -> str:
    matches = [match for line in output.splitlines() if (match := GAME_STATE_PATTERN.fullmatch(line))]
    if len(matches) != 1:
        raise RenderProfileError(f"expected one game-state line, received {len(matches)}")
    return matches[0].group(1)


def write_artifact(
    path: Path, result: dict[str, object], owner_uid: int | None, owner_gid: int | None
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if owner_uid is not None or owner_gid is not None:
        os.chown(path, -1 if owner_uid is None else owner_uid, -1 if owner_gid is None else owner_gid)


def print_summary(result: dict[str, object], output_path: Path) -> None:
    display = result["display"]
    cases = result["cases"]
    assert isinstance(display, dict) and isinstance(cases, dict)
    print(
        f"{display['transport']} at "
        f"{display['configured_spi_frequency_hz'] / 1_000_000:.3f} MHz configured"
    )
    print("case       bytes   windows  draw us  present us  unpaced fps  efficiency")
    for name in sorted(cases, key=lambda item: (cases[item]["coverage_percent"], item)):
        case = cases[name]
        stages = case["stages"]
        derived = case["derived"]
        print(
            f"{name:10} {case['payload_bytes']:7} {case['display_writes_per_frame']:8} "
            f"{stages['draw']['mean_us']:8} {stages['present']['mean_us']:11} "
            f"{derived['mean_unpaced_frames_per_second']:12.2f} "
            f"{derived['mean_configured_bus_efficiency_percent']:9.1f}%"
        )
    print(f"artifact: {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", help="USB CDC ACM device")
    parser.add_argument("output", type=Path, help="versioned JSON artifact path")
    parser.add_argument("--samples", type=int, default=16, help="measured samples per case")
    parser.add_argument("--owner-uid", type=int, help="set artifact owner UID")
    parser.add_argument("--owner-gid", type=int, help="set artifact owner GID")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.samples <= 64:
        print("samples must be 1-64", file=sys.stderr)
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
                        raise RenderProfileError("simulation did not pause")
                    paused_by_us = True
                output = session.run(
                    f"picosystem display profile {args.samples}", timeout_seconds=180.0
                )
                result = parse_profile(output)
                write_artifact(args.output, result, args.owner_uid, args.owner_gid)
            except (
                OSError,
                RenderProfileError,
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
                            raise RenderProfileError("simulation did not resume")
                    except (
                        OSError,
                        RenderProfileError,
                        SerialShellError,
                        serial.SerialException,
                    ) as cleanup_error:
                        if failure is None:
                            failure = cleanup_error
                        else:
                            print(f"render-profile cleanup also failed: {cleanup_error}", file=sys.stderr)
    except (OSError, SerialShellError, serial.SerialException, ValueError) as error:
        failure = error

    if failure is not None or result is None:
        print(f"render profile failed: {failure}", file=sys.stderr)
        return 1

    print_summary(result, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
