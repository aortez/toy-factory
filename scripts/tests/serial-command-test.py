#!/usr/bin/env python3

"""Native tests for Toy Factory's serial-shell response handling."""

import importlib.util
from pathlib import Path
import sys
import unittest


sys.dont_write_bytecode = True
MODULE_PATH = Path(__file__).parents[1] / "container" / "serial-command.py"
MODULE_SPEC = importlib.util.spec_from_file_location("serial_command", MODULE_PATH)
if MODULE_SPEC is None or MODULE_SPEC.loader is None:
    raise RuntimeError(f"could not load {MODULE_PATH}")

serial_command = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(serial_command)


class SerialCommandTest(unittest.TestCase):
    def test_finds_current_prompt(self) -> None:
        self.assertEqual(
            serial_command.find_prompt(b"\r\ntoy-factory:~$ "),
            b"toy-factory:~$ ",
        )

    def test_finds_legacy_prompt_for_first_upgrade(self) -> None:
        self.assertEqual(
            serial_command.find_prompt(bytearray(b"\r\npicosystem:~$ ")),
            b"picosystem:~$ ",
        )

    def test_rejects_unrelated_output(self) -> None:
        self.assertIsNone(serial_command.find_prompt(b"booting\r\n"))

    def test_cleans_current_prompt(self) -> None:
        response = (
            b"toy-factory:~$ picosystem status\r\n"
            b"uptime: 123 ms\r\n"
            b"toy-factory:~$ "
        )
        self.assertEqual(
            serial_command.clean_response(response, "picosystem status"),
            "uptime: 123 ms",
        )

    def test_cleans_legacy_prompt(self) -> None:
        response = (
            b"picosystem:~$ picosystem reboot bootloader\r\n"
            b"Rebooting into the RP2040 ROM USB bootloader\r\n"
            b"picosystem:~$ "
        )
        self.assertEqual(
            serial_command.clean_response(response, "picosystem reboot bootloader"),
            "Rebooting into the RP2040 ROM USB bootloader",
        )


if __name__ == "__main__":
    unittest.main()
