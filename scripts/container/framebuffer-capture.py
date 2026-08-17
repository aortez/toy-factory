#!/usr/bin/env python3

"""Capture Toy Factory's presented framebuffer over USB and write a PNG."""

import argparse
import base64
import os
from pathlib import Path
import re
import struct
import sys
from typing import NamedTuple
import zlib

import serial

from serial_shell import SerialShellError, run_command


CAPTURE_COMMAND = "picosystem display capture"
BEGIN_PATTERN = re.compile(
    r"^FRAMEBUFFER_BEGIN width=(\d+) height=(\d+) format=([a-z0-9]+) bytes=(\d+)$"
)
DATA_PATTERN = re.compile(r"^FRAMEBUFFER_DATA offset=(\d+) data=([A-Za-z0-9+/=]+)$")
END_PATTERN = re.compile(r"^FRAMEBUFFER_END sequence=(\d+) crc32=([0-9a-fA-F]{8})$")


class CaptureError(RuntimeError):
    """A framebuffer transfer was malformed or failed validation."""


class FramebufferCapture(NamedTuple):
    width: int
    height: int
    pixel_format: str
    data: bytes
    sequence: int
    crc32: int


def parse_capture(output: str) -> FramebufferCapture:
    width = 0
    height = 0
    pixel_format = ""
    expected_bytes = 0
    payload = bytearray()
    sequence: int | None = None
    reported_crc32: int | None = None
    began = False
    ended = False

    for line in output.splitlines():
        begin_match = BEGIN_PATTERN.fullmatch(line)
        if begin_match:
            if began:
                raise CaptureError("received more than one framebuffer header")
            width = int(begin_match.group(1))
            height = int(begin_match.group(2))
            pixel_format = begin_match.group(3)
            expected_bytes = int(begin_match.group(4))
            began = True
            continue

        data_match = DATA_PATTERN.fullmatch(line)
        if data_match:
            if not began:
                raise CaptureError("received framebuffer data before its header")
            if ended:
                raise CaptureError("received framebuffer data after its trailer")
            offset = int(data_match.group(1))
            if offset != len(payload):
                raise CaptureError(
                    f"expected framebuffer offset {len(payload)}, received {offset}"
                )
            try:
                payload.extend(base64.b64decode(data_match.group(2), validate=True))
            except ValueError as error:
                raise CaptureError(f"invalid base64 at offset {offset}") from error
            continue

        end_match = END_PATTERN.fullmatch(line)
        if end_match:
            if not began:
                raise CaptureError("received framebuffer trailer before its header")
            if ended:
                raise CaptureError("received more than one framebuffer trailer")
            sequence = int(end_match.group(1))
            reported_crc32 = int(end_match.group(2), 16)
            ended = True

    if not began:
        raise CaptureError("framebuffer header was not received")
    if sequence is None or reported_crc32 is None:
        raise CaptureError("framebuffer trailer was not received")
    if pixel_format != "rgb565be":
        raise CaptureError(f"unsupported framebuffer format '{pixel_format}'")
    if expected_bytes != width * height * 2:
        raise CaptureError(
            f"header size {expected_bytes} does not match {width}x{height} RGB565"
        )
    if len(payload) != expected_bytes:
        raise CaptureError(f"expected {expected_bytes} framebuffer bytes, received {len(payload)}")

    actual_crc32 = zlib.crc32(payload) & 0xFFFFFFFF
    if actual_crc32 != reported_crc32:
        raise CaptureError(
            f"framebuffer CRC mismatch: expected {reported_crc32:08x}, got {actual_crc32:08x}"
        )

    return FramebufferCapture(
        width=width,
        height=height,
        pixel_format=pixel_format,
        data=bytes(payload),
        sequence=sequence,
        crc32=reported_crc32,
    )


def rgb565be_to_rgb888(data: bytes) -> bytes:
    if len(data) % 2 != 0:
        raise CaptureError("RGB565 data length must be even")

    converted = bytearray(len(data) // 2 * 3)
    destination = 0
    for source in range(0, len(data), 2):
        pixel = (data[source] << 8) | data[source + 1]
        red = (pixel >> 11) & 0x1F
        green = (pixel >> 5) & 0x3F
        blue = pixel & 0x1F
        converted[destination] = (red << 3) | (red >> 2)
        converted[destination + 1] = (green << 2) | (green >> 4)
        converted[destination + 2] = (blue << 3) | (blue >> 2)
        destination += 3

    return bytes(converted)


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(chunk_type)
    checksum = zlib.crc32(data, checksum) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", checksum)


def write_png(
    path: Path,
    width: int,
    height: int,
    rgb_data: bytes,
    owner_uid: int | None = None,
    owner_gid: int | None = None,
) -> None:
    expected_bytes = width * height * 3
    if len(rgb_data) != expected_bytes:
        raise CaptureError(f"expected {expected_bytes} RGB bytes, received {len(rgb_data)}")

    stride = width * 3
    scanlines = b"".join(
        b"\x00" + rgb_data[row * stride : (row + 1) * stride] for row in range(height)
    )
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", header)
        + png_chunk(b"IDAT", zlib.compress(scanlines, level=9))
        + png_chunk(b"IEND", b"")
    )

    if (owner_uid is None) != (owner_gid is None):
        raise CaptureError("output owner requires both a UID and GID")

    missing_parents = []
    parent = path.parent
    while not parent.exists():
        missing_parents.append(parent)
        parent = parent.parent

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
    if owner_uid is not None and owner_gid is not None:
        os.chown(path, owner_uid, owner_gid)
        for created_parent in missing_parents:
            os.chown(created_parent, owner_uid, owner_gid)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", help="USB CDC ACM device")
    parser.add_argument("output", type=Path, help="PNG output path")
    parser.add_argument("--timeout", type=float, default=60.0, help="transfer timeout in seconds")
    parser.add_argument("--owner-uid", type=int, help="set the output owner UID")
    parser.add_argument("--owner-gid", type=int, help="set the output owner GID")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        response = run_command(args.port, CAPTURE_COMMAND, timeout_seconds=args.timeout)
        capture = parse_capture(response)
        rgb_data = rgb565be_to_rgb888(capture.data)
        write_png(
            args.output,
            capture.width,
            capture.height,
            rgb_data,
            owner_uid=args.owner_uid,
            owner_gid=args.owner_gid,
        )
    except (CaptureError, OSError, serial.SerialException, SerialShellError) as error:
        print(f"framebuffer capture failed: {error}", file=sys.stderr)
        return 1

    print(
        f"captured {capture.width}x{capture.height} frame {capture.sequence} "
        f"(crc32={capture.crc32:08x}) to {args.output}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
