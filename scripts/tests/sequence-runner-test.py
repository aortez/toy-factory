#!/usr/bin/env python3

"""Native tests for deterministic device-sequence validation and execution."""

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest import mock


sys.dont_write_bytecode = True
CONTAINER_DIR = Path(__file__).parents[1] / "container"
sys.path.insert(0, str(CONTAINER_DIR))
MODULE_PATH = CONTAINER_DIR / "sequence_runner.py"
MODULE_SPEC = importlib.util.spec_from_file_location("sequence_runner", MODULE_PATH)
if MODULE_SPEC is None or MODULE_SPEC.loader is None:
    raise RuntimeError(f"could not load {MODULE_PATH}")

sequence_runner = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(sequence_runner)


class FakeSession:
    def __init__(self) -> None:
        self.mode = "running"
        self.tick = 900
        self.input_source = "physical"
        self.input_name = "none"
        self.commands = []

    def __enter__(self) -> "FakeSession":
        return self

    def __exit__(self, _exception_type: object, _exception: object, _traceback: object) -> None:
        pass

    def state_hash(self) -> int:
        return 0xABC00000 | self.tick

    def state_output(self) -> str:
        input_x, input_y = sequence_runner.VALID_INPUTS[self.input_name]
        return "\n".join(
            (
                f"mode={self.mode} tick={self.tick} hash={self.state_hash():08x}",
                f"input_source={self.input_source} input_x={input_x} input_y={input_y}",
                "focus_id=1 focus_x_q16=1 focus_y_q16=2 "
                "velocity_x_q16_per_tick=3 velocity_y_q16_per_tick=4",
                "published_snapshot=5 presented_snapshot=5",
            )
        )

    def run(self, command: str, timeout_seconds: float | None = None) -> str:
        del timeout_seconds
        self.commands.append(command)
        if command == "picosystem game pause":
            self.mode = "paused"
        elif command == "picosystem game reset":
            if self.mode != "paused":
                raise AssertionError("test reset must be paused")
            self.tick = 0
            self.input_source = "remote"
            self.input_name = "none"
        elif command.startswith("picosystem game input "):
            self.input_name = command.rsplit(" ", 1)[1]
            self.input_source = "physical" if self.input_name == "physical" else "remote"
            if self.input_source == "physical":
                self.input_name = "none"
        elif command.startswith("picosystem game step "):
            self.tick += int(command.rsplit(" ", 1)[1])
        elif command == "picosystem game state":
            pass
        elif command == "picosystem game run":
            self.mode = "running"
        elif command == "picosystem display checksum":
            return (
                "width=240 height=240 format=rgb565be bytes=115200 "
                "sequence=77 crc32=1234abcd"
            )
        else:
            raise AssertionError(f"unexpected command {command}")
        return self.state_output()


def valid_spec(*, expected_hash: str = "abc000fa") -> dict[str, object]:
    return {
        "name": "long-step-test",
        "steps": [{"input": "right", "ticks": 250}],
        "expect": {
            "hash": expected_hash,
            "framebuffer_crc32": "1234abcd",
        },
    }


class SequenceRunnerTest(unittest.TestCase):
    def test_parses_and_runs_bounded_step_chunks(self) -> None:
        spec = sequence_runner.parse_sequence_spec(valid_spec())
        session = FakeSession()

        result = sequence_runner.run_sequence(session, spec)

        self.assertEqual(result.state.tick, 250)
        self.assertEqual(result.state.state_hash, 0xABC000FA)
        self.assertEqual(result.framebuffer_crc32, 0x1234ABCD)
        self.assertEqual(
            [command for command in session.commands if " game step " in command],
            [
                "picosystem game step 120",
                "picosystem game step 120",
                "picosystem game step 10",
            ],
        )

    def test_rejects_hash_mismatch(self) -> None:
        spec = sequence_runner.parse_sequence_spec(valid_spec(expected_hash="00000000"))
        with self.assertRaisesRegex(sequence_runner.SequenceError, "hash mismatch"):
            sequence_runner.run_sequence(FakeSession(), spec)

    def test_rejects_physical_input_in_deterministic_sequence(self) -> None:
        value = valid_spec()
        value["steps"] = [{"input": "physical", "ticks": 1}]
        with self.assertRaisesRegex(sequence_runner.SequenceError, "must be one of"):
            sequence_runner.parse_sequence_spec(value)

    def test_rejects_boolean_tick_count(self) -> None:
        value = valid_spec()
        value["steps"] = [{"input": "none", "ticks": True}]
        with self.assertRaisesRegex(sequence_runner.SequenceError, "positive integer"):
            sequence_runner.parse_sequence_spec(value)

    def test_rejects_one_tick_over_sequence_limit(self) -> None:
        value = valid_spec()
        value["steps"] = [
            {
                "input": "none",
                "ticks": sequence_runner.MAX_SEQUENCE_TICKS + 1,
            }
        ]
        with self.assertRaisesRegex(sequence_runner.SequenceError, "safety limit"):
            sequence_runner.parse_sequence_spec(value)

    def test_rejects_unknown_key(self) -> None:
        value = valid_spec()
        value["typo"] = 1
        with self.assertRaisesRegex(sequence_runner.SequenceError, "unknown key"):
            sequence_runner.parse_sequence_spec(value)

    def test_rejects_inconsistent_checksum_size(self) -> None:
        output = (
            "width=240 height=240 format=rgb565be bytes=1 "
            "sequence=77 crc32=1234abcd"
        )
        with self.assertRaisesRegex(sequence_runner.SequenceError, "does not match"):
            sequence_runner.parse_framebuffer_checksum(output)

    def test_main_captures_failure_screenshot_before_cleanup(self) -> None:
        session = FakeSession()
        capture_calls = []

        def fake_capture(_session: FakeSession, path: Path, **_arguments: object) -> object:
            capture_calls.append((path, list(_session.commands)))
            return SimpleNamespace(sequence=88, crc32=0xDEADBEEF)

        arguments = SimpleNamespace(
            port="/dev/fake",
            sequence=Path("unused.json"),
            failure_screenshot=Path("artifacts/failure.png"),
            owner_uid=1000,
            owner_gid=1000,
            leave_paused=False,
        )
        spec = sequence_runner.parse_sequence_spec(valid_spec(expected_hash="00000000"))
        standard_error = io.StringIO()
        standard_output = io.StringIO()
        with (
            mock.patch.object(sequence_runner, "parse_args", return_value=arguments),
            mock.patch.object(sequence_runner, "load_sequence_spec", return_value=spec),
            mock.patch.object(sequence_runner, "SerialShellSession", return_value=session),
            mock.patch.object(sequence_runner, "capture_to_png", side_effect=fake_capture),
            redirect_stderr(standard_error),
            redirect_stdout(standard_output),
        ):
            result = sequence_runner.main()

        self.assertEqual(result, 1)
        self.assertEqual(capture_calls[0][0], Path("artifacts/failure.png"))
        commands_at_capture = capture_calls[0][1]
        self.assertNotIn("picosystem game input physical", commands_at_capture)
        self.assertEqual(session.commands[-2:], [
            "picosystem game input physical",
            "picosystem game run",
        ])
        self.assertIn("failure screenshot", standard_error.getvalue())


if __name__ == "__main__":
    unittest.main()
