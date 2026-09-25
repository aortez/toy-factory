#!/usr/bin/env python3
"""Print a compact summary of a Toy Factory Garden training report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    return parser.parse_args()


def require_mapping(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise RuntimeError(f"{name} is not an object")
    return value


def print_row(label: str, accepted: str, record: dict[str, object]) -> None:
    fitness = require_mapping(record.get("fitness"), f"{label} fitness")
    model_crc = record.get("model_crc32")
    fields = (
        fitness.get("extinctions"),
        fitness.get("final_viable"),
        fitness.get("final_living"),
        fitness.get("established_offspring"),
        fitness.get("descendant_plant_ticks"),
        fitness.get("maximum_generation"),
        fitness.get("living_plant_ticks"),
        fitness.get("deaths"),
    )
    if (
        not isinstance(model_crc, str)
        or any(isinstance(value, bool) or not isinstance(value, int) for value in fields)
    ):
        raise RuntimeError(f"{label} contains invalid summary values")
    extinct, viable, living, established, descendants, generation, plant_ticks, deaths = fields
    print(
        f"{label:>7} {accepted:^8} {extinct:>7} {viable:>6} {living:>6} "
        f"{established:>6} {descendants:>10} {generation:>6} "
        f"{plant_ticks:>11} {deaths:>6} {model_crc}"
    )


def main() -> int:
    args = parse_arguments()
    report = require_mapping(json.loads(args.report.read_text()), "report")
    settings = require_mapping(report.get("settings"), "settings")
    generations = report.get("generations")
    initial = require_mapping(report.get("initial"), "initial")
    final = require_mapping(report.get("final"), "final")
    if report.get("schema_version") != 1 or not isinstance(generations, list):
        raise RuntimeError("unexpected Garden training report schema")

    print(
        "Garden neural search: "
        f"{settings.get('generations')} generations, "
        f"{settings.get('population')} population, "
        f"{settings.get('trials_per_scenario')} trials/scenario, "
        f"{settings.get('ticks_per_trial')} ticks/trial"
    )
    print(
        f"{'stage':>7} {'accepted':^8} {'extinct':>7} {'viable':>6} {'living':>6} "
        f"{'estab':>6} {'desc-ticks':>10} {'maxgen':>6} {'plant-ticks':>11} "
        f"{'deaths':>6} model-crc"
    )
    print_row("initial", "-", initial)
    for value in generations:
        generation = require_mapping(value, "generation")
        index = generation.get("index")
        accepted = generation.get("accepted")
        if not isinstance(index, int) or not isinstance(accepted, bool):
            raise RuntimeError("generation metadata is invalid")
        print_row(str(index), "yes" if accepted else "no", generation)
    if generations:
        last = require_mapping(generations[-1], "last generation")
        if (
            last.get("model_crc32") != final.get("model_crc32")
            or last.get("fitness") != final.get("fitness")
        ):
            raise RuntimeError("final model does not match the training trace")
    print(f"evaluations: {report.get('evaluations')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
