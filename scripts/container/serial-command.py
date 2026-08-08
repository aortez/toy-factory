#!/usr/bin/env python3

"""Run one command against the PicoSystem Zephyr shell over USB CDC ACM."""

import argparse
import re
import sys
import time

import serial


PROMPT = b"picosystem:~$ "
ANSI_ESCAPE = re.compile(rb"\x1b(?:\[[0-?]*[ -/]*[@-~]|[@-_])")


def read_until_prompt(
    connection: serial.Serial,
    timeout_seconds: float,
    settle_seconds: float = 0.0,
) -> bytes:
    deadline = time.monotonic() + timeout_seconds
    quiet_deadline = deadline
    received = bytearray()
    prompt_seen = False

    while time.monotonic() < deadline:
        chunk = connection.read(max(connection.in_waiting, 1))
        if chunk:
            received.extend(chunk)
            if PROMPT in received:
                prompt_seen = True
                quiet_deadline = time.monotonic() + settle_seconds
        elif prompt_seen and time.monotonic() >= quiet_deadline:
            break

    return bytes(received)


def read_until_disconnect(
    connection: serial.Serial,
    timeout_seconds: float,
) -> tuple[bytes, bool]:
    deadline = time.monotonic() + timeout_seconds
    received = bytearray()

    while time.monotonic() < deadline:
        try:
            chunk = connection.read(max(connection.in_waiting, 1))
        except (OSError, serial.SerialException):
            return bytes(received), True

        if chunk:
            received.extend(chunk)

    return bytes(received), False


def clean_response(response: bytes, command: str) -> str:
    text = ANSI_ESCAPE.sub(b"", response).decode("utf-8", errors="replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.splitlines()]

    while lines and not lines[0]:
        lines.pop(0)

    if lines and lines[0].startswith(PROMPT.decode()):
        lines[0] = lines[0][len(PROMPT.decode()) :]

    if lines and lines[0].strip() == command:
        lines.pop(0)

    while lines and (not lines[-1] or lines[-1].strip() == PROMPT.decode().strip()):
        lines.pop()

    return "\n".join(lines)


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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    command = " ".join(args.command)

    try:
        with serial.Serial(
            args.port,
            baudrate=115200,
            timeout=0.05,
            write_timeout=1.0,
            exclusive=True,
        ) as connection:
            connection.reset_input_buffer()
            # Abort any partially entered line, then wait for all pending shell
            # redraws before sending the real command. Without the quiet period,
            # a stale prompt can make a short-lived client exit too early.
            connection.write(b"\x03\r")
            connection.flush()

            greeting = read_until_prompt(connection, args.timeout, settle_seconds=0.2)
            if PROMPT not in greeting:
                print(f"no PicoSystem shell prompt received from {args.port}", file=sys.stderr)
                return 1

            connection.reset_input_buffer()
            try:
                connection.write(command.encode("utf-8") + b"\r")
                connection.flush()
            except (OSError, serial.SerialException):
                if args.expect_disconnect:
                    return 0
                raise

            if args.expect_disconnect:
                response, disconnected = read_until_disconnect(connection, args.timeout)
            else:
                response = read_until_prompt(connection, args.timeout)
                disconnected = False

            output = clean_response(response, command)
            if output:
                print(output)

            if args.expect_disconnect:
                if not disconnected:
                    print(
                        f"'{command}' did not disconnect {args.port}",
                        file=sys.stderr,
                    )
                    return 1
            elif PROMPT not in response:
                print(f"timed out waiting for '{command}' on {args.port}", file=sys.stderr)
                return 1
    except (OSError, serial.SerialException) as error:
        print(f"could not use {args.port}: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
