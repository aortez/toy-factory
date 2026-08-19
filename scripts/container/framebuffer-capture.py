#!/usr/bin/env python3

"""Capture Toy Factory's presented framebuffer over USB and write a PNG."""

import argparse
from pathlib import Path
import sys

import serial

from framebuffer_capture import CaptureError, DEFAULT_CAPTURE_TIMEOUT_SECONDS, capture_to_png
from serial_shell import SerialShellError, SerialShellSession


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", help="USB CDC ACM device")
    parser.add_argument("output", type=Path, help="PNG output path")
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_CAPTURE_TIMEOUT_SECONDS,
        help="transfer timeout in seconds",
    )
    parser.add_argument("--owner-uid", type=int, help="set the output owner UID")
    parser.add_argument("--owner-gid", type=int, help="set the output owner GID")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        with SerialShellSession(args.port) as session:
            capture = capture_to_png(
                session,
                args.output,
                timeout_seconds=args.timeout,
                owner_uid=args.owner_uid,
                owner_gid=args.owner_gid,
            )
    except (CaptureError, OSError, serial.SerialException, SerialShellError, ValueError) as error:
        print(f"framebuffer capture failed: {error}", file=sys.stderr)
        return 1

    print(
        f"captured {capture.width}x{capture.height} frame {capture.sequence} "
        f"(crc32={capture.crc32:08x}) to {args.output}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
