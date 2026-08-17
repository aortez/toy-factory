#!/usr/bin/env python3

"""Native tests for Toy Factory's serial-shell response handling."""

import importlib.util
from pathlib import Path
import sys
import unittest


sys.dont_write_bytecode = True
MODULE_PATH = Path(__file__).parents[1] / "container" / "serial_shell.py"
MODULE_SPEC = importlib.util.spec_from_file_location("serial_shell", MODULE_PATH)
if MODULE_SPEC is None or MODULE_SPEC.loader is None:
    raise RuntimeError(f"could not load {MODULE_PATH}")

serial_shell = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(serial_shell)


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

            @property
            def in_waiting(self) -> int:
                return len(self.response)

            def reset_input_buffer(self) -> None:
                self.response.clear()

            def write(self, data: bytes) -> None:
                command = data.decode().strip()
                self.commands.append(command)
                self.response.extend(
                    f"{command}\r\nresult={len(self.commands)}\r\ntoy-factory:~$ ".encode()
                )

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
