"""Run deterministic input sequences against Toy Factory over one USB session."""

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Callable, NamedTuple

import serial

from framebuffer_capture import CaptureError, capture_to_png
from serial_shell import SerialShellError, SerialShellSession


DEVICE_MAX_STEP_TICKS = 120
MAX_SEQUENCE_SEGMENTS = 256
MAX_SEQUENCE_TICKS = 100_000
EXPECTED_FRAMEBUFFER_SIZE = (240, 240)
VALID_INPUTS = {
    "none": (0, 0),
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
    "up-left": (-1, -1),
    "up-right": (1, -1),
    "down-left": (-1, 1),
    "down-right": (1, 1),
}
ACTION_COMMANDS = {
    "flip": "picosystem game flip",
    "primary": "picosystem game action",
}
VALID_ACTIONS = set(ACTION_COMMANDS)
VALID_SCENES = {"clockwork", "hourglass", "marble-machine"}
NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
HEX32_PATTERN = re.compile(r"^[0-9a-fA-F]{8}$")
GAME_STATE_PATTERN = re.compile(
    r"^mode=(paused|running) tick=(\d+) hash=([0-9a-fA-F]{8})$"
)
INPUT_STATE_PATTERN = re.compile(
    r"^input_source=(physical|remote) input_x=(-?\d+) input_y=(-?\d+)$"
)
SCENE_STATE_PATTERN = re.compile(
    r"^scene=(clockwork|hourglass|marble-machine) scene_id=(\d+)$"
)
CHECKSUM_PATTERN = re.compile(
    r"^width=(\d+) height=(\d+) format=([a-z0-9]+) bytes=(\d+) "
    r"sequence=(\d+) crc32=([0-9a-fA-F]{8})$"
)


class SequenceError(RuntimeError):
    """A sequence definition, command result, or deterministic assertion failed."""


class SequenceSegment(NamedTuple):
    input_name: str | None
    ticks: int
    action: str | None


class SequenceSpec(NamedTuple):
    name: str
    scene: str
    segments: tuple[SequenceSegment, ...]
    expected_hash: int | None
    expected_framebuffer_crc32: int | None


class GameState(NamedTuple):
    scene: str
    scene_id: int
    mode: str
    tick: int
    state_hash: int
    input_source: str
    input_x: int
    input_y: int


class FramebufferChecksum(NamedTuple):
    width: int
    height: int
    pixel_format: str
    byte_count: int
    sequence: int
    crc32: int


class SequenceResult(NamedTuple):
    name: str
    state: GameState
    framebuffer_crc32: int | None


def require_object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise SequenceError(f"{label} must be a JSON object with string keys")
    return value


def reject_unknown_keys(value: dict[str, object], allowed: set[str], label: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise SequenceError(f"{label} contains unknown key(s): {', '.join(unknown)}")


def parse_hex32(value: object, label: str) -> int:
    if not isinstance(value, str) or HEX32_PATTERN.fullmatch(value) is None:
        raise SequenceError(f"{label} must be exactly eight hexadecimal digits")
    return int(value, 16)


def parse_sequence_spec(value: object) -> SequenceSpec:
    root = require_object(value, "sequence")
    reject_unknown_keys(root, {"name", "scene", "steps", "expect"}, "sequence")

    name = root.get("name")
    if not isinstance(name, str) or NAME_PATTERN.fullmatch(name) is None:
        raise SequenceError("sequence.name must use 1-64 letters, digits, '.', '_', or '-'")

    scene = root.get("scene", "hourglass")
    if not isinstance(scene, str) or scene not in VALID_SCENES:
        choices = ", ".join(sorted(VALID_SCENES))
        raise SequenceError(f"sequence.scene must be one of: {choices}")

    raw_steps = root.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise SequenceError("sequence.steps must be a nonempty JSON array")
    if len(raw_steps) > MAX_SEQUENCE_SEGMENTS:
        raise SequenceError(f"sequence.steps exceeds the {MAX_SEQUENCE_SEGMENTS}-segment limit")

    segments = []
    total_ticks = 0
    for index, raw_step in enumerate(raw_steps):
        label = f"sequence.steps[{index}]"
        step = require_object(raw_step, label)
        reject_unknown_keys(step, {"input", "ticks", "action"}, label)

        action = step.get("action")
        if action is not None:
            if set(step) != {"action"}:
                raise SequenceError(f"{label} action cannot be combined with input or ticks")
            if not isinstance(action, str) or action not in VALID_ACTIONS:
                choices = ", ".join(sorted(VALID_ACTIONS))
                raise SequenceError(f"{label}.action must be one of: {choices}")
            segments.append(SequenceSegment(input_name=None, ticks=0, action=action))
            continue

        input_name = step.get("input")
        if not isinstance(input_name, str) or input_name not in VALID_INPUTS:
            choices = ", ".join(sorted(VALID_INPUTS))
            raise SequenceError(f"{label}.input must be one of: {choices}")

        ticks = step.get("ticks")
        if type(ticks) is not int or ticks <= 0:
            raise SequenceError(f"{label}.ticks must be a positive integer")
        total_ticks += ticks
        if total_ticks > MAX_SEQUENCE_TICKS:
            raise SequenceError(
                f"sequence exceeds the {MAX_SEQUENCE_TICKS}-tick safety limit"
            )
        segments.append(SequenceSegment(input_name=input_name, ticks=ticks, action=None))

    expected_hash = None
    expected_framebuffer_crc32 = None
    if "expect" in root:
        expectations = require_object(root["expect"], "sequence.expect")
        reject_unknown_keys(
            expectations,
            {"hash", "framebuffer_crc32"},
            "sequence.expect",
        )
        if "hash" in expectations:
            expected_hash = parse_hex32(expectations["hash"], "sequence.expect.hash")
        if "framebuffer_crc32" in expectations:
            expected_framebuffer_crc32 = parse_hex32(
                expectations["framebuffer_crc32"],
                "sequence.expect.framebuffer_crc32",
            )
        if expected_hash is None and expected_framebuffer_crc32 is None:
            raise SequenceError("sequence.expect must contain at least one assertion")

    return SequenceSpec(
        name=name,
        scene=scene,
        segments=tuple(segments),
        expected_hash=expected_hash,
        expected_framebuffer_crc32=expected_framebuffer_crc32,
    )


def load_sequence_spec(path: Path) -> SequenceSpec:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SequenceError(f"could not read sequence {path}: {error}") from error
    return parse_sequence_spec(value)


def one_matching_line(output: str, pattern: re.Pattern[str], label: str) -> re.Match[str]:
    matches = [match for line in output.splitlines() if (match := pattern.fullmatch(line))]
    if len(matches) != 1:
        raise SequenceError(f"expected one {label} line, received {len(matches)}")
    return matches[0]


def parse_game_state(output: str) -> GameState:
    state_match = one_matching_line(output, GAME_STATE_PATTERN, "game-state")
    input_match = one_matching_line(output, INPUT_STATE_PATTERN, "input-state")
    scene_match = one_matching_line(output, SCENE_STATE_PATTERN, "scene-state")
    input_x = int(input_match.group(2))
    input_y = int(input_match.group(3))
    if not (-1 <= input_x <= 1) or not (-1 <= input_y <= 1):
        raise SequenceError(f"device returned invalid input vector ({input_x}, {input_y})")

    return GameState(
        scene=scene_match.group(1),
        scene_id=int(scene_match.group(2)),
        mode=state_match.group(1),
        tick=int(state_match.group(2)),
        state_hash=int(state_match.group(3), 16),
        input_source=input_match.group(1),
        input_x=input_x,
        input_y=input_y,
    )


def parse_framebuffer_checksum(output: str) -> FramebufferChecksum:
    match = one_matching_line(output, CHECKSUM_PATTERN, "framebuffer-checksum")
    checksum = FramebufferChecksum(
        width=int(match.group(1)),
        height=int(match.group(2)),
        pixel_format=match.group(3),
        byte_count=int(match.group(4)),
        sequence=int(match.group(5)),
        crc32=int(match.group(6), 16),
    )
    if checksum.pixel_format != "rgb565be":
        raise SequenceError(f"unsupported framebuffer format '{checksum.pixel_format}'")
    if (checksum.width, checksum.height) != EXPECTED_FRAMEBUFFER_SIZE:
        raise SequenceError(
            f"unexpected framebuffer dimensions {checksum.width}x{checksum.height}"
        )
    if checksum.byte_count != checksum.width * checksum.height * 2:
        raise SequenceError(
            f"framebuffer size {checksum.byte_count} does not match "
            f"{checksum.width}x{checksum.height} RGB565"
        )
    return checksum


def require_paused_tick(state: GameState, expected_tick: int, context: str) -> None:
    if state.mode != "paused":
        raise SequenceError(f"{context} returned mode={state.mode}, expected paused")
    if state.tick != expected_tick:
        raise SequenceError(
            f"{context} returned tick {state.tick}, expected exact tick {expected_tick}"
        )


def require_remote_input(state: GameState, input_name: str, context: str) -> None:
    expected_vector = VALID_INPUTS[input_name]
    if (state.input_source, state.input_x, state.input_y) != (
        "remote",
        *expected_vector,
    ):
        raise SequenceError(f"{context} did not retain remote input {input_name}")


def require_scene(state: GameState, scene: str, context: str) -> None:
    if state.scene != scene:
        raise SequenceError(f"{context} returned scene={state.scene}, expected {scene}")


def run_sequence(
    session: SerialShellSession,
    spec: SequenceSpec,
    report: Callable[[str], None] | None = None,
) -> SequenceResult:
    emit = report if report is not None else lambda _message: None

    paused_state = parse_game_state(session.run("picosystem game pause"))
    if paused_state.mode != "paused":
        raise SequenceError(f"pause returned mode={paused_state.mode}")

    state = parse_game_state(session.run(f"picosystem game scene {spec.scene}"))
    require_paused_tick(state, 0, "scene selection")
    require_remote_input(state, "none", "scene selection")
    require_scene(state, spec.scene, "scene selection")
    emit(f"scene={spec.scene}: tick=0 hash={state.state_hash:08x}")

    expected_tick = 0
    current_input_name = "none"
    for index, segment in enumerate(spec.segments, start=1):
        if segment.action is not None:
            state = parse_game_state(session.run(ACTION_COMMANDS[segment.action]))
            require_paused_tick(state, expected_tick, f"segment {index} action")
            require_remote_input(state, current_input_name, f"segment {index} action")
            require_scene(state, spec.scene, f"segment {index} action")
            emit(
                f"segment {index}: action={segment.action} tick={state.tick} "
                f"hash={state.state_hash:08x}"
            )
            continue

        if segment.input_name is None:
            raise SequenceError(f"segment {index} has neither input nor action")
        state = parse_game_state(
            session.run(f"picosystem game input {segment.input_name}")
        )
        require_paused_tick(state, expected_tick, f"segment {index} input")
        require_remote_input(state, segment.input_name, f"segment {index} input")
        require_scene(state, spec.scene, f"segment {index} input")
        current_input_name = segment.input_name

        remaining_ticks = segment.ticks
        while remaining_ticks > 0:
            step_ticks = min(remaining_ticks, DEVICE_MAX_STEP_TICKS)
            state = parse_game_state(
                session.run(f"picosystem game step {step_ticks}")
            )
            expected_tick += step_ticks
            require_paused_tick(state, expected_tick, f"segment {index} step")
            require_remote_input(state, segment.input_name, f"segment {index} step")
            require_scene(state, spec.scene, f"segment {index} step")
            remaining_ticks -= step_ticks

        emit(
            f"segment {index}: input={segment.input_name} ticks={segment.ticks} "
            f"tick={state.tick} hash={state.state_hash:08x}"
        )

    state = parse_game_state(session.run("picosystem game state"))
    require_paused_tick(state, expected_tick, "final state")
    require_remote_input(state, current_input_name, "final state")
    require_scene(state, spec.scene, "final state")
    if spec.expected_hash is not None and state.state_hash != spec.expected_hash:
        raise SequenceError(
            f"state hash mismatch: expected {spec.expected_hash:08x}, "
            f"received {state.state_hash:08x} at tick {state.tick}"
        )

    framebuffer_crc32 = None
    if spec.expected_framebuffer_crc32 is not None:
        checksum = parse_framebuffer_checksum(
            session.run("picosystem display checksum", timeout_seconds=5.0)
        )
        framebuffer_crc32 = checksum.crc32
        if checksum.crc32 != spec.expected_framebuffer_crc32:
            raise SequenceError(
                f"framebuffer CRC mismatch: expected {spec.expected_framebuffer_crc32:08x}, "
                f"received {checksum.crc32:08x} at frame {checksum.sequence}"
            )

    return SequenceResult(
        name=spec.name,
        state=state,
        framebuffer_crc32=framebuffer_crc32,
    )


def restore_interactive_mode(session: SerialShellSession) -> None:
    state = parse_game_state(session.run("picosystem game input physical"))
    if state.input_source != "physical":
        raise SequenceError("cleanup did not restore physical input")
    state = parse_game_state(session.run("picosystem game run"))
    if state.mode != "running":
        raise SequenceError("cleanup did not resume real-time simulation")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", help="USB CDC ACM device")
    parser.add_argument("sequence", type=Path, help="deterministic sequence JSON file")
    parser.add_argument(
        "--failure-screenshot",
        type=Path,
        help="capture this PNG before cleanup when the sequence fails",
    )
    parser.add_argument("--owner-uid", type=int, help="set diagnostic PNG owner UID")
    parser.add_argument("--owner-gid", type=int, help="set diagnostic PNG owner GID")
    parser.add_argument(
        "--leave-paused",
        action="store_true",
        help="leave remote input and paused state in place after the run",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        spec = load_sequence_spec(args.sequence)
    except SequenceError as error:
        print(f"sequence definition failed: {error}", file=sys.stderr)
        return 1

    failure: Exception | None = None
    result: SequenceResult | None = None
    try:
        with SerialShellSession(args.port) as session:
            try:
                result = run_sequence(
                    session,
                    spec,
                    report=lambda message: print(message, flush=True),
                )
            except (SequenceError, SerialShellError, OSError, serial.SerialException) as error:
                failure = error
                print(f"FAIL {spec.name}: {error}", file=sys.stderr)
                if args.failure_screenshot is not None:
                    try:
                        capture = capture_to_png(
                            session,
                            args.failure_screenshot,
                            owner_uid=args.owner_uid,
                            owner_gid=args.owner_gid,
                        )
                        print(
                            f"failure screenshot: {args.failure_screenshot} "
                            f"(frame={capture.sequence}, crc32={capture.crc32:08x})",
                            file=sys.stderr,
                        )
                    except (
                        CaptureError,
                        SerialShellError,
                        OSError,
                        serial.SerialException,
                        ValueError,
                    ) as screenshot_error:
                        print(
                            f"failure screenshot also failed: {screenshot_error}",
                            file=sys.stderr,
                        )

            if not args.leave_paused:
                try:
                    restore_interactive_mode(session)
                except (
                    SequenceError,
                    SerialShellError,
                    OSError,
                    serial.SerialException,
                ) as cleanup_error:
                    print(f"sequence cleanup failed: {cleanup_error}", file=sys.stderr)
                    if failure is None:
                        failure = cleanup_error
    except (SerialShellError, OSError, serial.SerialException, ValueError) as error:
        print(f"could not use {args.port}: {error}", file=sys.stderr)
        return 1

    if failure is not None or result is None:
        return 1

    crc_text = (
        "not-asserted"
        if result.framebuffer_crc32 is None
        else f"{result.framebuffer_crc32:08x}"
    )
    print(
        f"PASS {result.name}: tick={result.state.tick} "
        f"hash={result.state.state_hash:08x} framebuffer_crc32={crc_text}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
