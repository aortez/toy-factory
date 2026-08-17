"""Validate, convert, and save Toy Factory framebuffer captures."""

import base64
import os
from pathlib import Path
import re
import struct
from typing import NamedTuple
import zlib

from serial_shell import SerialShellSession


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


def capture_framebuffer(
    session: SerialShellSession,
    timeout_seconds: float = 60.0,
) -> FramebufferCapture:
    response = session.run(CAPTURE_COMMAND, timeout_seconds=timeout_seconds)
    return parse_capture(response)


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


def capture_to_png(
    session: SerialShellSession,
    path: Path,
    timeout_seconds: float = 60.0,
    owner_uid: int | None = None,
    owner_gid: int | None = None,
) -> FramebufferCapture:
    capture = capture_framebuffer(session, timeout_seconds=timeout_seconds)
    write_png(
        path,
        capture.width,
        capture.height,
        rgb565be_to_rgb888(capture.data),
        owner_uid=owner_uid,
        owner_gid=owner_gid,
    )
    return capture
