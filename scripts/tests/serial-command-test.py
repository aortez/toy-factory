#!/usr/bin/env python3

"""Native tests for Toy Factory's serial-shell response handling."""

import importlib.util
from collections import deque
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


sys.dont_write_bytecode = True
MODULE_PATH = Path(__file__).parents[1] / "container" / "serial_shell.py"
MODULE_SPEC = importlib.util.spec_from_file_location("serial_shell", MODULE_PATH)
if MODULE_SPEC is None or MODULE_SPEC.loader is None:
    raise RuntimeError(f"could not load {MODULE_PATH}")

serial_shell = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(serial_shell)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now


class TimedConnection:
    """Deliver serial fragments at deterministic times without wall-clock sleeps."""

    def __init__(self, clock: FakeClock, fragments: list[tuple[float, bytes]]) -> None:
        self.clock = clock
        self.fragments = deque(fragments)
        self.buffer = bytearray()

    def release_ready(self) -> None:
        while self.fragments and self.fragments[0][0] <= self.clock.now:
            _, data = self.fragments.popleft()
            self.buffer.extend(data)

    @property
    def in_waiting(self) -> int:
        self.release_ready()
        return len(self.buffer)

    def read(self, size: int) -> bytes:
        self.release_ready()
        if not self.buffer:
            deadline = self.clock.now + 0.05
            if self.fragments:
                deadline = min(deadline, self.fragments[0][0])
            self.clock.now = deadline
            self.release_ready()
        chunk = bytes(self.buffer[:size])
        del self.buffer[:size]
        return chunk


class CommandConnection(TimedConnection):
    def __init__(self, clock: FakeClock, reply: list[tuple[float, bytes]]) -> None:
        super().__init__(clock, [])
        self.reply = reply
        self.writes = []

    def reset_input_buffer(self) -> None:
        self.release_ready()
        self.buffer.clear()

    def write(self, data: bytes) -> None:
        self.writes.append(data)
        if data == b"\r":
            self.fragments.extend(
                (self.clock.now + delay, fragment) for delay, fragment in self.reply
            )
        else:
            self.buffer.extend(data)

    def flush(self) -> None:
        pass


class SerialCommandTest(unittest.TestCase):
    def test_finds_current_prompt(self) -> None:
        self.assertEqual(
            serial_shell.find_prompt(b"\r\ntoy-factory:~$ "),
            b"toy-factory:~$ ",
        )

    def test_finds_legacy_prompt_for_first_upgrade(self) -> None:
        self.assertEqual(
            serial_shell.find_prompt(bytearray(b"\r\npicosystem:~$ ")),
            b"picosystem:~$ ",
        )

    def test_rejects_unrelated_output(self) -> None:
        self.assertIsNone(serial_shell.find_prompt(b"booting\r\n"))

    def test_finds_colored_terminal_prompt(self) -> None:
        response = (
            b"toy-factory:~$ picosystem status\r\nuptime: 123 ms\r\n"
            b"\x1b[1;32mtoy-factory:~$ \x1b[m"
        )
        self.assertEqual(serial_shell.find_prompt(response), b"toy-factory:~$ ")

    def test_finds_prompt_repainted_without_a_newline(self) -> None:
        prompt = b"\x1b[1;32mtoy-factory:~$ \x1b[m"
        response = prompt + b"\x1b[15D\x1b[J" + prompt
        self.assertEqual(serial_shell.find_prompt(response), b"toy-factory:~$ ")

    def test_rejects_repainted_prompt_with_active_command(self) -> None:
        prompt = b"\x1b[1;32mtoy-factory:~$ \x1b[m"
        response = prompt + b"\x1b[15D\x1b[J" + prompt + b"picosystem game step 120"
        self.assertIsNone(serial_shell.find_prompt(response))

    def test_rejects_nonidle_prompts(self) -> None:
        for response in (
            b"toy-factory:~$ picosystem game step 120",
            b"picosystem:~$ picosystem status",
            b"output mentions toy-factory:~$ ",
            b"toy-factory:~$ \r\nresult still arriving",
            b"toy-factory:~$ \x1b[",
            b"toy-factory:~$ \r\n",
        ):
            with self.subTest(response=response):
                self.assertIsNone(serial_shell.find_prompt(response))

    def test_waits_past_battery_log_redraw_for_delayed_result(self) -> None:
        fragments = [
            (
                0.0,
                b"[00:11:31.243,000] <inf> toy_factory: battery: 4206 mV "
                b"(raw mean 1740)\r\ntoy-factory:~$ picosystem game step 120",
            ),
            (0.5, b"\r\nmode=paused tick=38310 hash=697eb956\r\n"),
            (0.6, b"toy-factory:~$ "),
        ]
        clock = FakeClock()
        connection = TimedConnection(clock, fragments)
        with patch.object(serial_shell.time, "monotonic", clock.monotonic):
            response = serial_shell.read_until_prompt(connection, 2.0, settle_seconds=0.1)
        self.assertEqual(response, b"".join(data for _, data in fragments))
        self.assertGreaterEqual(clock.now, 0.7)

    def test_later_echo_fragment_revokes_candidate_prompt(self) -> None:
        fragments = [
            (0.0, b"battery: 4206 mV\r\ntoy-factory:~$ "),
            (0.05, b"picosystem game step 120"),
            (0.5, b"\r\nmode=paused tick=120 hash=12345678\r\n"),
            (0.6, b"toy-factory:~$ "),
        ]
        clock = FakeClock()
        connection = TimedConnection(clock, fragments)
        with patch.object(serial_shell.time, "monotonic", clock.monotonic):
            response = serial_shell.read_until_prompt(connection, 2.0, settle_seconds=0.1)
        self.assertEqual(response, b"".join(data for _, data in fragments))
        self.assertGreaterEqual(clock.now, 0.7)

    def test_waits_for_fragmented_colored_final_prompt(self) -> None:
        fragments = [
            (0.0, b"result=1\r\n\x1b[1;32mtoy-fac"),
            (0.1, b"tory:~$ \x1b["),
            (0.3, b"m"),
        ]
        clock = FakeClock()
        connection = TimedConnection(clock, fragments)
        with patch.object(serial_shell.time, "monotonic", clock.monotonic):
            response = serial_shell.read_until_prompt(connection, 2.0, settle_seconds=0.1)
        self.assertEqual(response, b"".join(data for _, data in fragments))
        self.assertGreaterEqual(clock.now, 0.4)

    def test_incomplete_reply_uses_absolute_timeout(self) -> None:
        fragments = [
            (0.0, b"toy-factory:~$ picosystem game step 120\r\n"),
            (0.2, b"background log\r\n"),
            (0.4, b"another log\r\n"),
            (0.6, b"late output\r\n"),
        ]
        clock = FakeClock()
        connection = TimedConnection(clock, fragments)
        with patch.object(serial_shell.time, "monotonic", clock.monotonic):
            response = serial_shell.read_until_prompt(connection, 0.5, settle_seconds=0.1)
        self.assertIsNone(serial_shell.find_prompt(response))
        self.assertNotIn(b"late output", response)
        self.assertGreaterEqual(clock.now, 0.5)
        self.assertLess(clock.now, 0.6)

    def test_session_waits_for_result_without_resending_step(self) -> None:
        clock = FakeClock()
        command = b"picosystem game step 120"
        connection = CommandConnection(
            clock,
            [
                (0.0, b"battery: 4206 mV\r\ntoy-factory:~$ " + command),
                (0.5, b"\r\nmode=paused tick=120 hash=12345678\r\n"),
                (0.6, b"toy-factory:~$ "),
            ],
        )
        session = serial_shell.SerialShellSession("/dev/fake")
        session.connection = connection
        with patch.object(serial_shell.time, "monotonic", clock.monotonic):
            response = session.run(command.decode())
        self.assertTrue(serial_shell.has_line_prefix(response, "mode=paused tick=120 "))
        self.assertEqual(connection.writes, [command, b"\r"])

    def test_session_fails_closed_without_resending_step(self) -> None:
        clock = FakeClock()
        command = b"picosystem game step 120"
        connection = CommandConnection(
            clock, [(0.0, b"battery: 4206 mV\r\ntoy-factory:~$ " + command)]
        )
        session = serial_shell.SerialShellSession("/dev/fake")
        session.connection = connection
        with patch.object(serial_shell.time, "monotonic", clock.monotonic):
            with self.assertRaisesRegex(serial_shell.SerialShellError, "timed out"):
                session.run(command.decode(), timeout_seconds=0.5)
        self.assertEqual(connection.writes, [command, b"\r"])

    def test_finds_required_line_prefix(self) -> None:
        output = "noise\nmode=paused tick=123\nmore noise"
        self.assertTrue(serial_shell.has_line_prefix(output, "mode="))
        self.assertFalse(serial_shell.has_line_prefix(output, "mode=running"))

    def test_cleans_current_prompt(self) -> None:
        response = (
            b"toy-factory:~$ picosystem status\r\n"
            b"uptime: 123 ms\r\n"
            b"toy-factory:~$ "
        )
        self.assertEqual(
            serial_shell.clean_response(response, "picosystem status"),
            "uptime: 123 ms",
        )

    def test_cleans_legacy_prompt(self) -> None:
        response = (
            b"picosystem:~$ picosystem reboot bootloader\r\n"
            b"Rebooting into the RP2040 ROM USB bootloader\r\n"
            b"picosystem:~$ "
        )
        self.assertEqual(
            serial_shell.clean_response(response, "picosystem reboot bootloader"),
            "Rebooting into the RP2040 ROM USB bootloader",
        )

    def test_session_reuses_one_open_connection(self) -> None:
        class FakeConnection:
            def __init__(self) -> None:
                self.response = bytearray()
                self.commands = []
                self.closed = False
                self.pending_command = bytearray()

            @property
            def in_waiting(self) -> int:
                return len(self.response)

            def reset_input_buffer(self) -> None:
                self.response.clear()

            def write(self, data: bytes) -> None:
                if data == b"\r":
                    command = self.pending_command.decode()
                    self.pending_command.clear()
                    self.commands.append(command)
                    self.response.extend(
                        (
                            f"{command}\r\nresult={len(self.commands)}\r\n"
                            "toy-factory:~$ "
                        ).encode()
                    )
                    return
                self.pending_command.extend(data)
                self.response.extend(b"toy-factory:~$ ")

            def flush(self) -> None:
                pass

            def read(self, size: int) -> bytes:
                chunk = bytes(self.response[:size])
                del self.response[:size]
                return chunk

            def close(self) -> None:
                self.closed = True

        connection = FakeConnection()
        session = serial_shell.SerialShellSession("/dev/fake")
        session.connection = connection
        original_settle = serial_shell.COMMAND_SETTLE_SECONDS
        serial_shell.COMMAND_SETTLE_SECONDS = 0.0
        try:
            self.assertEqual(session.run("first"), "result=1")
            self.assertEqual(session.run("second"), "result=2")
            session.close()
        finally:
            serial_shell.COMMAND_SETTLE_SECONDS = original_settle

        self.assertEqual(connection.commands, ["first", "second"])
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
