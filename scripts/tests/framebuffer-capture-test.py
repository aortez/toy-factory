#!/usr/bin/env python3

"""Native tests for framebuffer transfer validation and PNG conversion."""

import base64
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib


sys.dont_write_bytecode = True
CONTAINER_DIR = Path(__file__).parents[1] / "container"
sys.path.insert(0, str(CONTAINER_DIR))
MODULE_PATH = CONTAINER_DIR / "framebuffer_capture.py"
MODULE_SPEC = importlib.util.spec_from_file_location("framebuffer_capture", MODULE_PATH)
if MODULE_SPEC is None or MODULE_SPEC.loader is None:
    raise RuntimeError(f"could not load {MODULE_PATH}")

framebuffer_capture = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(framebuffer_capture)


def capture_output(data: bytes, *, crc32: int | None = None) -> str:
    first = data[:4]
    second = data[4:]
    checksum = zlib.crc32(data) & 0xFFFFFFFF if crc32 is None else crc32
    return "\n".join(
        (
            f"FRAMEBUFFER_BEGIN width=2 height=2 format=rgb565be bytes={len(data)}",
            f"FRAMEBUFFER_DATA offset=0 data={base64.b64encode(first).decode()}",
            "an asynchronous log line that the transfer parser ignores",
            f"FRAMEBUFFER_DATA offset=4 data={base64.b64encode(second).decode()}",
            f"FRAMEBUFFER_END sequence=17 crc32={checksum:08x}",
        )
    )


class FramebufferCaptureTest(unittest.TestCase):
    PIXELS = bytes.fromhex("f800 07e0 001f ffff")

    def test_parses_valid_chunked_capture(self) -> None:
        capture = framebuffer_capture.parse_capture(capture_output(self.PIXELS))

        self.assertEqual((capture.width, capture.height), (2, 2))
        self.assertEqual(capture.pixel_format, "rgb565be")
        self.assertEqual(capture.data, self.PIXELS)
        self.assertEqual(capture.sequence, 17)
        self.assertEqual(capture.crc32, zlib.crc32(self.PIXELS) & 0xFFFFFFFF)

    def test_rejects_noncontiguous_chunk(self) -> None:
        output = capture_output(self.PIXELS).replace("offset=4", "offset=5")
        with self.assertRaisesRegex(framebuffer_capture.CaptureError, "expected.*offset"):
            framebuffer_capture.parse_capture(output)

    def test_rejects_crc_mismatch(self) -> None:
        with self.assertRaisesRegex(framebuffer_capture.CaptureError, "CRC mismatch"):
            framebuffer_capture.parse_capture(capture_output(self.PIXELS, crc32=0))

    def test_rejects_data_after_trailer(self) -> None:
        lines = capture_output(self.PIXELS).splitlines()
        lines[2], lines[4] = lines[4], lines[2]
        with self.assertRaisesRegex(framebuffer_capture.CaptureError, "after its trailer"):
            framebuffer_capture.parse_capture("\n".join(lines))

    def test_converts_rgb565_primaries(self) -> None:
        converted = framebuffer_capture.rgb565be_to_rgb888(self.PIXELS)
        self.assertEqual(converted, bytes.fromhex("ff0000 00ff00 0000ff ffffff"))

    def test_writes_standard_rgb_png(self) -> None:
        rgb_data = framebuffer_capture.rgb565be_to_rgb888(self.PIXELS)
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "frame.png"
            framebuffer_capture.write_png(output, 2, 2, rgb_data)
            png = output.read_bytes()

        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(png[12:16], b"IHDR")
        self.assertEqual(struct.unpack(">II", png[16:24]), (2, 2))


if __name__ == "__main__":
    unittest.main()
