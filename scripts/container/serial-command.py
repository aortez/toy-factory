#!/usr/bin/env python3

"""Run one command against the Toy Factory Zephyr shell over USB CDC ACM."""

import argparse
import sys

import serial

from serial_shell import SerialShellError, has_line_prefix, run_command


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expect-disconnect",
        action="store_true",
        help="succeed when the command intentionally disconnects the USB device",
    )
    parser.add_argument("port", help="USB CDC ACM device")
    parser.add_argument("command", nargs="+", help="shell command and arguments")
    parser.add_argument("--timeout", type=float, default=3.0, help="response timeout in seconds")
    parser.add_argument(
        "--require-prefix",
        help="fail unless one response line starts with this success marker",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    command = " ".join(args.command)

    try:
        output = run_command(
            args.port,
            command,
            timeout_seconds=args.timeout,
            expect_disconnect=args.expect_disconnect,
        )
        if output:
            print(output)
        if args.require_prefix and not has_line_prefix(output, args.require_prefix):
            print(
                f"'{command}' did not return the expected '{args.require_prefix}' marker",
                file=sys.stderr,
            )
            return 1
    except (OSError, serial.SerialException, SerialShellError) as error:
        print(f"could not use {args.port}: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
