#!/usr/bin/env python3

"""Shared USB CDC shell transport for Toy Factory host tools."""

import re
import time

import serial


PROMPTS = (b"toy-factory:~$ ", b"picosystem:~$ ")
ANSI_ESCAPE = re.compile(rb"\x1b(?:\[[0-?]*[ -/]*[@-~]|[@-_])")


class SerialShellError(RuntimeError):
    """The device did not complete a shell exchange as requested."""


def find_prompt(data: bytes | bytearray) -> bytes | None:
    return next((prompt for prompt in PROMPTS if prompt in data), None)


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
            if find_prompt(received) is not None:
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

    for prompt in PROMPTS:
        decoded_prompt = prompt.decode()
        if lines and lines[0].startswith(decoded_prompt):
            lines[0] = lines[0][len(decoded_prompt) :]
            break

    if lines and lines[0].strip() == command:
        lines.pop(0)

    prompt_texts = {prompt.decode().strip() for prompt in PROMPTS}
    while lines and (not lines[-1] or lines[-1].strip() in prompt_texts):
        lines.pop()

    return "\n".join(lines)


def has_line_prefix(output: str, prefix: str) -> bool:
    return any(line.startswith(prefix) for line in output.splitlines())


def run_command(
    port: str,
    command: str,
    timeout_seconds: float = 3.0,
    expect_disconnect: bool = False,
) -> str:
    with serial.Serial(
        port,
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

        greeting = read_until_prompt(connection, timeout_seconds, settle_seconds=0.2)
        if find_prompt(greeting) is None:
            raise SerialShellError(f"no Toy Factory shell prompt received from {port}")

        connection.reset_input_buffer()
        try:
            connection.write(command.encode("utf-8") + b"\r")
            connection.flush()
        except (OSError, serial.SerialException):
            if expect_disconnect:
                return ""
            raise

        if expect_disconnect:
            response, disconnected = read_until_disconnect(connection, timeout_seconds)
        else:
            response = read_until_prompt(connection, timeout_seconds)
            disconnected = False

        output = clean_response(response, command)
        if expect_disconnect:
            if not disconnected:
                raise SerialShellError(f"'{command}' did not disconnect {port}")
        elif find_prompt(response) is None:
            raise SerialShellError(f"timed out waiting for '{command}' on {port}")

        return output
