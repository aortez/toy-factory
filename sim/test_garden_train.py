#!/usr/bin/env python3
"""Validate deterministic Garden evolution and portable model artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import zlib


MODEL_FILE_SIZE = 1220
MODEL_FILE_MAGIC = 0x314D4754
MODEL_FILE_VERSION = 1
MODEL_HEADER_SIZE = 16
MODEL_PAYLOAD_SIZE = 1204
FITNESS_ORDER = (
    ("extinctions", False),
    ("final_viable", True),
    ("final_living", True),
    ("established_offspring", True),
    ("descendant_plant_ticks", True),
    ("maximum_generation", True),
    ("living_plant_ticks", True),
    ("deaths", False),
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--evaluator", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--cc", required=True)
    return parser.parse_args()


def run_training(
    binary: Path, directory: Path, *, input_model: Path | None = None
) -> tuple[str, dict[str, object], Path, Path]:
    model = directory / "champion.tgm"
    c_source = directory / "champion.c"
    command = [
        str(binary.resolve()),
        "--generations",
        "2" if input_model is None else "0",
        "--population",
        "8",
        "--trials",
        "1",
        "--ticks",
        "3840",
        "--mutations",
        "32",
        "--seed",
        "0x1234",
        "--output",
        str(model),
        "--c-output",
        str(c_source),
        "--symbol",
        "test_garden_champion",
    ]
    if input_model is not None:
        command.extend(("--input", str(input_model)))
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"Garden trainer failed: {detail}")
    report = json.loads(completed.stdout)
    if not isinstance(report, dict):
        raise RuntimeError("Garden training report is not an object")
    return completed.stdout, report, model, c_source


def fitness_key(value: object) -> tuple[int, ...]:
    if not isinstance(value, dict):
        raise RuntimeError("training fitness is not an object")
    result: list[int] = []
    for name, maximize in FITNESS_ORDER:
        field = value.get(name)
        if isinstance(field, bool) or not isinstance(field, int) or field < 0:
            raise RuntimeError(f"training fitness has invalid {name}")
        result.append(-field if maximize else field)
    digest = value.get("state_digest")
    if not isinstance(digest, str) or len(digest) != 8:
        raise RuntimeError("training fitness has invalid state digest")
    int(digest, 16)
    return tuple(result)


def validate_report(report: dict[str, object]) -> None:
    if report.get("schema_version") != 1:
        raise RuntimeError("unexpected Garden trainer schema")
    if report.get("algorithm") != "deterministic-(1+lambda)":
        raise RuntimeError("unexpected Garden training algorithm")
    if report.get("base_seed") != "00001234":
        raise RuntimeError("Garden training seed changed")
    settings = report.get("settings")
    expected_settings = {
        "generations": 2,
        "population": 8,
        "trials_per_scenario": 1,
        "ticks_per_trial": 3840,
        "mutations_per_offspring": 32,
        "scenario_count": 3,
    }
    if settings != expected_settings:
        raise RuntimeError("Garden training settings are incorrect")
    if report.get("evaluations") != 15:
        raise RuntimeError("Garden training evaluation count is incorrect")
    initial = report.get("initial")
    final = report.get("final")
    generations = report.get("generations")
    if not isinstance(initial, dict) or not isinstance(final, dict):
        raise RuntimeError("Garden training endpoints are missing")
    if not isinstance(generations, list) or len(generations) != 2:
        raise RuntimeError("Garden training generations are missing")

    previous = initial
    accepted_count = 0
    for expected_index, generation in enumerate(generations, start=1):
        if not isinstance(generation, dict) or generation.get("index") != expected_index:
            raise RuntimeError("Garden training generation index is incorrect")
        accepted = generation.get("accepted")
        if not isinstance(accepted, bool):
            raise RuntimeError("Garden training acceptance marker is invalid")
        previous_crc = previous.get("model_crc32")
        generation_crc = generation.get("model_crc32")
        if not isinstance(generation_crc, str) or len(generation_crc) != 8:
            raise RuntimeError("Garden training model CRC is invalid")
        int(generation_crc, 16)
        if accepted != (generation_crc != previous_crc):
            raise RuntimeError("Garden training acceptance and model CRC disagree")
        if fitness_key(generation.get("fitness")) > fitness_key(previous.get("fitness")):
            raise RuntimeError("Garden champion fitness regressed")
        accepted_count += int(accepted)
        previous = generation

    if accepted_count == 0:
        raise RuntimeError("Garden training smoke test never exercised model selection")
    # The generation record also carries its index and acceptance marker.
    if (
        final.get("model_crc32") != previous.get("model_crc32")
        or final.get("fitness") != previous.get("fitness")
    ):
        raise RuntimeError("Garden final model does not match the final generation")


def validate_binary(path: Path, expected_crc: str) -> None:
    data = path.read_bytes()
    if len(data) != MODEL_FILE_SIZE:
        raise RuntimeError("Garden model has the wrong file size")
    magic, version, header_size, payload_size, payload_crc = struct.unpack_from("<IHHII", data)
    if (
        magic != MODEL_FILE_MAGIC
        or version != MODEL_FILE_VERSION
        or header_size != MODEL_HEADER_SIZE
        or payload_size != MODEL_PAYLOAD_SIZE
    ):
        raise RuntimeError("Garden model envelope is invalid")
    if zlib.crc32(data[header_size:]) != payload_crc:
        raise RuntimeError("Garden model payload CRC is invalid")
    if f"{payload_crc:08x}" != expected_crc:
        raise RuntimeError("Garden model artifact and report CRC disagree")


def validate_generated_c(cc: str, source_root: Path, c_source: Path, directory: Path) -> None:
    completed = subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I",
            str((source_root / "src").resolve()),
            "-c",
            str(c_source),
            "-o",
            str(directory / "champion.o"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"generated Garden C model did not compile: {detail}")


def validate_evaluator(evaluator: Path, model: Path, expected_crc: str) -> None:
    completed = subprocess.run(
        [
            str(evaluator.resolve()),
            "--trials",
            "1",
            "--ticks",
            "3840",
            "--seed",
            "0x1234",
            "--model",
            str(model),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"Garden candidate evaluation failed: {detail}")
    report = json.loads(completed.stdout)
    if report.get("candidate_model_crc32") != expected_crc:
        raise RuntimeError("Garden evaluator reported the wrong candidate CRC")
    scenarios = report.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) != 3:
        raise RuntimeError("Garden candidate evaluation scenarios are missing")
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            raise RuntimeError("Garden candidate evaluation scenario is invalid")
        policies = scenario.get("policies")
        if not isinstance(policies, list):
            raise RuntimeError("Garden candidate evaluation policies are missing")
        names = {policy.get("name") for policy in policies if isinstance(policy, dict)}
        if names != {"baseline", "adaptive", "neural-candidate"}:
            raise RuntimeError("Garden candidate evaluation policy names are incorrect")


def validate_corruption_rejected(binary: Path, model: Path, directory: Path) -> None:
    corrupted = bytearray(model.read_bytes())
    corrupted[MODEL_HEADER_SIZE + 31] ^= 0x80
    bad_model = directory / "corrupt.tgm"
    bad_model.write_bytes(corrupted)
    completed = subprocess.run(
        [
            str(binary.resolve()),
            "--generations",
            "0",
            "--population",
            "2",
            "--trials",
            "1",
            "--ticks",
            "1",
            "--mutations",
            "1",
            "--input",
            str(bad_model),
            "--output",
            str(directory / "bad-output.tgm"),
            "--c-output",
            str(directory / "bad-output.c"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode == 0 or "failed to load initial model" not in completed.stderr:
        raise RuntimeError("Garden trainer accepted a corrupt model")


def main() -> int:
    args = parse_arguments()
    with tempfile.TemporaryDirectory(prefix="toy-factory-garden-train-") as temporary:
        root = Path(temporary)
        first_dir = root / "first"
        second_dir = root / "second"
        reload_dir = root / "reload"
        first_dir.mkdir()
        second_dir.mkdir()
        reload_dir.mkdir()

        first_stdout, first_report, first_model, first_c = run_training(
            args.binary, first_dir
        )
        second_stdout, second_report, second_model, second_c = run_training(
            args.binary, second_dir
        )
        if first_stdout != second_stdout or first_report != second_report:
            raise RuntimeError("identical Garden training runs produced different reports")
        if first_model.read_bytes() != second_model.read_bytes():
            raise RuntimeError("identical Garden training runs produced different models")
        if first_c.read_bytes() != second_c.read_bytes():
            raise RuntimeError("identical Garden training runs produced different C definitions")

        validate_report(first_report)
        final = first_report["final"]
        if not isinstance(final, dict) or not isinstance(final.get("model_crc32"), str):
            raise RuntimeError("Garden final model CRC is missing")
        final_crc = final["model_crc32"]
        validate_binary(first_model, final_crc)
        validate_generated_c(args.cc, args.source_root, first_c, first_dir)
        validate_evaluator(args.evaluator, first_model, final_crc)

        _, reload_report, reload_model, _ = run_training(
            args.binary, reload_dir, input_model=first_model
        )
        if reload_report.get("initial") != reload_report.get("final"):
            raise RuntimeError("zero-generation Garden reload changed the model")
        if reload_model.read_bytes() != first_model.read_bytes():
            raise RuntimeError("Garden model did not survive a load/save round trip")
        validate_corruption_rejected(args.binary, first_model, root)
    print("Garden trainer determinism and artifact tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
