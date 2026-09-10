#!/usr/bin/env python3
"""Run one existing Toy Factory sequence against the native simulator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zlib


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts" / "container"))

from framebuffer_capture import rgb565be_to_rgb888, write_png  # noqa: E402
from sequence_runner import load_sequence_spec  # noqa: E402


FRAMEBUFFER_BYTE_COUNT = 240 * 240 * 2


def build_command(binary: Path, sequence: Path, framebuffer: Path | None) -> list[str]:
    spec = load_sequence_spec(sequence)
    command = [str(binary), "--scene", spec.scene]

    for segment in spec.segments:
        if segment.action is not None:
            command.extend(("--action", segment.action))
        else:
            command.extend(("--step", segment.input_name or "none", str(segment.ticks)))

    if spec.expected_hash is not None:
        command.extend(("--expect-hash", f"{spec.expected_hash:08x}"))
    if spec.expected_framebuffer_crc32 is not None:
        command.extend(("--expect-crc", f"{spec.expected_framebuffer_crc32:08x}"))
    if framebuffer is not None:
        command.extend(("--framebuffer", str(framebuffer)))
    return command


def parse_result(output: str) -> dict[str, object]:
    lines = [line for line in output.splitlines() if line]
    if len(lines) != 1:
        raise RuntimeError(f"expected one simulator result, received {len(lines)}")
    value = json.loads(lines[0])
    if not isinstance(value, dict):
        raise RuntimeError("simulator result is not a JSON object")
    return value


def run_sequence(binary: Path, sequence: Path, output: Path | None) -> dict[str, object]:
    binary = binary.resolve()
    if not binary.is_file():
        raise RuntimeError(f"simulator executable does not exist: {binary}")

    with tempfile.TemporaryDirectory(prefix="toy-factory-host-") as temporary:
        framebuffer = Path(temporary) / "framebuffer.rgb565be" if output is not None else None
        completed = subprocess.run(
            build_command(binary, sequence, framebuffer),
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(
                f"simulator exited with status {completed.returncode}: {detail}"
            )

        result = parse_result(completed.stdout)
        if output is not None and framebuffer is not None:
            data = framebuffer.read_bytes()
            if len(data) != FRAMEBUFFER_BYTE_COUNT:
                raise RuntimeError(
                    f"expected {FRAMEBUFFER_BYTE_COUNT} framebuffer bytes, received {len(data)}"
                )
            reported_crc = result.get("framebuffer_crc32")
            actual_crc = zlib.crc32(data) & 0xFFFFFFFF
            if reported_crc != f"{actual_crc:08x}":
                raise RuntimeError(
                    f"framebuffer CRC mismatch: result={reported_crc}, data={actual_crc:08x}"
                )
            write_png(output, 240, 240, rgb565be_to_rgb888(data))
            result["output"] = str(output)

    return result


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--sequence", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    try:
        result = run_sequence(arguments.binary, arguments.sequence, arguments.output)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"host sequence failed: {error}", file=sys.stderr)
        return 1

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
