#!/usr/bin/env python3
"""Validate deterministic Garden policy experiments and their accounting."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile


SCENARIOS = {
    "unassisted": {
        "plants": 3,
        "initial_water_per_plant": 128,
        "irrigation_pattern": "none",
        "irrigation_period_ticks": 0,
        "irrigation_water_per_column": 0,
    },
    "irrigated": {
        "plants": 3,
        "initial_water_per_plant": 128,
        "irrigation_pattern": "whole-plot",
        "irrigation_period_ticks": 960,
        "irrigation_water_per_column": 8,
    },
    "crowded": {
        "plants": 5,
        "initial_water_per_plant": 96,
        "irrigation_pattern": "whole-plot",
        "irrigation_period_ticks": 960,
        "irrigation_water_per_column": 8,
    },
}
FOUNDERS = {
    "unassisted": [(1, 0, 4), (2, 1, 13), (3, 2, 22)],
    "irrigated": [(1, 0, 4), (2, 1, 13), (3, 2, 22)],
    "crowded": [(1, 0, 3), (2, 1, 8), (3, 2, 13), (4, 1, 18), (5, 0, 23)],
}
SPECIES = {0: "flower", 1: "shrub", 2: "ground-cover"}
POLICY_NAMES = {"baseline", "adaptive", "neural-reference"}
TRIAL_COUNT = 2
TICK_COUNT = 7680


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    return parser.parse_args()


def run_evaluator(binary: Path) -> dict[str, object]:
    completed = subprocess.run(
        [
            str(binary.resolve()),
            "--trials",
            str(TRIAL_COUNT),
            "--ticks",
            str(TICK_COUNT),
            "--seed",
            "0x12345678",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"Garden evaluator failed: {detail}")
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise RuntimeError("Garden evaluator result is not an object")
    return value


def validate_maximum_duration(binary: Path) -> None:
    completed = subprocess.run(
        [
            str(binary.resolve()),
            "--trials",
            "1",
            "--ticks",
            "100000",
            "--seed",
            "0x12345678",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"maximum-duration Garden evaluation failed: {detail}")
    report = json.loads(completed.stdout)
    if not isinstance(report, dict):
        raise RuntimeError("maximum-duration Garden report is not an object")
    capacity = require_nonnegative_integer(report, "tracked_lineage_capacity")
    scenarios = report.get("scenarios")
    if not isinstance(scenarios, list):
        raise RuntimeError("maximum-duration Garden scenarios are missing")
    for scenario in scenarios:
        if not isinstance(scenario, dict) or not isinstance(scenario.get("policies"), list):
            raise RuntimeError("maximum-duration Garden scenario is invalid")
        for policy in scenario["policies"]:
            if not isinstance(policy, dict) or not isinstance(policy.get("trials"), list):
                raise RuntimeError("maximum-duration Garden policy is invalid")
            for trial in policy["trials"]:
                if not isinstance(trial, dict):
                    raise RuntimeError("maximum-duration Garden trial is invalid")
                if require_nonnegative_integer(trial, "lineages") > capacity:
                    raise RuntimeError("maximum-duration Garden trial exceeded lineage capacity")


def require_nonnegative_integer(container: dict[str, object], name: str) -> int:
    value = container.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RuntimeError(f"{name} is not a nonnegative integer")
    return value


def validate_agent(agent: object) -> None:
    if not isinstance(agent, dict):
        raise RuntimeError("agent telemetry is not an object")
    decisions = require_nonnegative_integer(agent, "decisions")
    extend = require_nonnegative_integer(agent, "extend")
    wait = require_nonnegative_integer(agent, "wait")
    finish = require_nonnegative_integer(agent, "finish")
    root = require_nonnegative_integer(agent, "root")
    shoot = require_nonnegative_integer(agent, "shoot")
    root_extend = require_nonnegative_integer(agent, "root_extend")
    shoot_extend = require_nonnegative_integer(agent, "shoot_extend")
    if decisions != extend + wait + finish:
        raise RuntimeError("agent action counts do not sum to decisions")
    if decisions != root + shoot:
        raise RuntimeError("agent tissue counts do not sum to decisions")
    if extend != root_extend + shoot_extend:
        raise RuntimeError("agent extension counts do not sum to extensions")


def require_nullable_tick(container: dict[str, object], name: str) -> int | None:
    value = container.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0 or value > TICK_COUNT:
        raise RuntimeError(f"{name} is not null or a valid trial tick")
    return value


def validate_death_causes(value: object) -> tuple[dict[str, object], int]:
    if not isinstance(value, dict):
        raise RuntimeError("death causes are not an object")
    total = sum(
        require_nonnegative_integer(value, name)
        for name in ("energy", "water", "combined", "other")
    )
    return value, total


def validate_seed_blockers(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise RuntimeError("seed germination blockers are not an object")
    samples = require_nonnegative_integer(value, "samples")
    dormant = require_nonnegative_integer(value, "dormant")
    blocked = require_nonnegative_integer(value, "blocked")
    reasons = [
        require_nonnegative_integer(value, name)
        for name in (
            "moisture",
            "light",
            "plant_capacity",
            "node_capacity",
            "spacing",
        )
    ]
    if samples != dormant + blocked:
        raise RuntimeError("seed samples do not split into dormant and blocked")
    if any(reason > blocked for reason in reasons) or sum(reasons) < blocked:
        raise RuntimeError("seed blocker reason counts are inconsistent")
    return value


def validate_group(value: object) -> tuple[dict[str, object], int]:
    if not isinstance(value, dict):
        raise RuntimeError("lineage group metrics are not an object")
    living = require_nonnegative_integer(value, "living_plant_ticks")
    descendants = require_nonnegative_integer(value, "descendant_plant_ticks")
    if descendants > living:
        raise RuntimeError("descendant plant-time exceeds total plant-time")
    for name in (
        "initial_founders",
        "established_offspring",
        "final_living",
        "maximum_generation",
    ):
        require_nonnegative_integer(value, name)
    extinction_tick = require_nullable_tick(value, "extinction_tick")
    if extinction_tick is not None and value.get("final_living") != 0:
        raise RuntimeError("an extinct group still has living plants")
    _, deaths = validate_death_causes(value.get("death_causes"))
    return value, deaths


def validate_report(report: dict[str, object]) -> None:
    if report.get("schema_version") != 2:
        raise RuntimeError("unexpected Garden experiment schema")
    if report.get("trial_count") != TRIAL_COUNT or report.get("tick_count") != TICK_COUNT:
        raise RuntimeError("Garden experiment dimensions changed")
    if report.get("base_seed") != "12345678":
        raise RuntimeError("Garden experiment seed changed")
    if report.get("tracked_lineage_capacity") != 4096:
        raise RuntimeError("Garden lineage tracking capacity changed")
    if report.get("integral_units") != {
        "living": "plant-ticks",
        "descendants": "plant-ticks",
        "resources": "ecology-samples",
    }:
        raise RuntimeError("Garden experiment units changed")
    if report.get("establishment") != {
        "minimum_age_ecology_ticks": 5,
        "requires_active_leaf": True,
        "requires_zero_stress": True,
    }:
        raise RuntimeError("Garden establishment definition changed")

    scenarios = report.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) != len(SCENARIOS):
        raise RuntimeError("unexpected Garden experiment scenario count")
    if {scenario.get("name") for scenario in scenarios if isinstance(scenario, dict)} != set(
        SCENARIOS
    ):
        raise RuntimeError("unexpected Garden experiment scenarios")

    policy_difference_counts = {
        name: 0 for name in POLICY_NAMES if name != "baseline"
    }
    observed_deaths = 0
    observed_established = 0
    observed_seed_blockers = 0
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            raise RuntimeError("Garden experiment scenario is not an object")
        scenario_name = scenario.get("name")
        if not isinstance(scenario_name, str):
            raise RuntimeError("Garden experiment scenario has no name")
        for name, expected in SCENARIOS[scenario_name].items():
            if scenario.get(name) != expected:
                raise RuntimeError(f"{scenario_name}.{name} changed")
        policies = scenario.get("policies")
        if not isinstance(policies, list) or len(policies) != len(POLICY_NAMES):
            raise RuntimeError("unexpected Garden experiment policy count")
        by_name = {
            policy.get("name"): policy for policy in policies if isinstance(policy, dict)
        }
        if set(by_name) != POLICY_NAMES:
            raise RuntimeError("unexpected Garden experiment policies")

        seeds_by_policy: dict[str, list[object]] = {}
        hashes_by_policy: dict[str, list[object]] = {}
        for policy_name, policy in by_name.items():
            trials = policy.get("trials")
            totals = policy.get("totals")
            if not isinstance(trials, list) or len(trials) != TRIAL_COUNT:
                raise RuntimeError(f"{policy_name} has an unexpected trial count")
            if not isinstance(totals, dict):
                raise RuntimeError(f"{policy_name} has no aggregate totals")

            seeds_by_policy[policy_name] = []
            hashes_by_policy[policy_name] = []
            for trial in trials:
                if not isinstance(trial, dict):
                    raise RuntimeError("Garden experiment trial is not an object")
                seed = trial.get("seed")
                state_hash = trial.get("hash")
                if not isinstance(seed, str) or len(seed) != 8:
                    raise RuntimeError("Garden experiment trial has an invalid seed")
                if not isinstance(state_hash, str) or len(state_hash) != 8:
                    raise RuntimeError("Garden experiment trial has an invalid hash")
                seeds_by_policy[policy_name].append(seed)
                hashes_by_policy[policy_name].append(state_hash)
                if trial.get("resource_samples") != TICK_COUNT // 15:
                    raise RuntimeError("Garden experiment resource cadence changed")
                living_plant_ticks = require_nonnegative_integer(
                    trial, "living_plant_ticks"
                )
                if living_plant_ticks == 0:
                    raise RuntimeError("Garden experiment recorded no living plants")
                descendant_plant_ticks = require_nonnegative_integer(
                    trial, "descendant_plant_ticks"
                )
                if descendant_plant_ticks > living_plant_ticks:
                    raise RuntimeError("descendant plant-time exceeds total plant-time")
                for name in (
                    "sampled_energy",
                    "sampled_water",
                    "sampled_stress",
                    "plants",
                    "living",
                    "dead",
                    "seed_bank",
                    "nodes",
                    "maximum_nodes",
                    "blooms",
                    "deaths",
                    "reclaimed_plants",
                    "reclaimed_nodes",
                    "seeds_created",
                    "germinations",
                    "seeds_expired",
                    "mutations",
                    "established_offspring",
                    "maximum_generation",
                    "lineages",
                    "moisture",
                    "energy",
                    "water",
                    "stress",
                    "maximum_stress",
                    "nonzero_memory_plants",
                ):
                    require_nonnegative_integer(trial, name)
                if trial["plants"] != trial["living"] + trial["dead"]:
                    raise RuntimeError("final plant accounting is inconsistent")
                if trial["lineages"] != scenario["plants"] + trial["germinations"]:
                    raise RuntimeError("lineage accounting is inconsistent")
                if trial["established_offspring"] > trial["germinations"]:
                    raise RuntimeError("more offspring established than germinated")
                extinction_tick = require_nullable_tick(trial, "extinction_tick")
                finally_extinct = trial["living"] == 0 and trial["seed_bank"] == 0
                if (extinction_tick is not None) != finally_extinct:
                    raise RuntimeError("global extinction accounting is inconsistent")
                _, death_total = validate_death_causes(trial.get("death_causes"))
                if death_total != trial["deaths"]:
                    raise RuntimeError("trial death causes do not sum to deaths")
                blockers = validate_seed_blockers(
                    trial.get("seed_germination_blockers")
                )
                validate_agent(trial.get("agent"))

                species = trial.get("species")
                if not isinstance(species, list) or len(species) != len(SPECIES):
                    raise RuntimeError("trial species metrics are incomplete")
                species_by_id = {
                    group.get("id"): group for group in species if isinstance(group, dict)
                }
                if set(species_by_id) != set(SPECIES):
                    raise RuntimeError("trial species IDs are incomplete")
                species_groups: list[dict[str, object]] = []
                species_deaths = 0
                for species_id, species_name in SPECIES.items():
                    group = species_by_id[species_id]
                    if group.get("name") != species_name:
                        raise RuntimeError("trial species name changed")
                    validated, deaths = validate_group(group)
                    species_groups.append(validated)
                    species_deaths += deaths

                founders = trial.get("founders")
                expected_founders = FOUNDERS[scenario_name]
                if not isinstance(founders, list) or len(founders) != len(
                    expected_founders
                ):
                    raise RuntimeError("trial founder metrics are incomplete")
                founder_groups: list[dict[str, object]] = []
                founder_deaths = 0
                for index, (founder, expected) in enumerate(
                    zip(founders, expected_founders, strict=True)
                ):
                    if not isinstance(founder, dict):
                        raise RuntimeError("trial founder metrics are not an object")
                    lineage_id, species_id, column = expected
                    if (
                        founder.get("index") != index
                        or founder.get("lineage_id") != lineage_id
                        or founder.get("species_id") != species_id
                        or founder.get("species") != SPECIES[species_id]
                        or founder.get("column") != column
                    ):
                        raise RuntimeError("trial founder identity changed")
                    validated, deaths = validate_group(founder)
                    if validated.get("initial_founders") != 1:
                        raise RuntimeError("founder group does not contain one founder")
                    founder_groups.append(validated)
                    founder_deaths += deaths

                expected_species_founders = {
                    species_id: sum(
                        founder_species == species_id
                        for _, founder_species, _ in expected_founders
                    )
                    for species_id in SPECIES
                }
                for species_id, expected in expected_species_founders.items():
                    if species_by_id[species_id].get("initial_founders") != expected:
                        raise RuntimeError("species founder count is incorrect")
                for name, trial_name in (
                    ("living_plant_ticks", "living_plant_ticks"),
                    ("descendant_plant_ticks", "descendant_plant_ticks"),
                    ("established_offspring", "established_offspring"),
                    ("final_living", "living"),
                ):
                    expected = require_nonnegative_integer(trial, trial_name)
                    species_total = sum(
                        require_nonnegative_integer(group, name)
                        for group in species_groups
                    )
                    if species_total != expected:
                        raise RuntimeError(f"species {name} partition is incorrect")
                    founder_total = sum(
                        require_nonnegative_integer(group, name)
                        for group in founder_groups
                    )
                    if founder_total != expected:
                        raise RuntimeError(f"founder {name} partition is incorrect")
                if species_deaths != trial["deaths"] or founder_deaths != trial["deaths"]:
                    raise RuntimeError("lineage-group death partition is incorrect")
                if max(
                    require_nonnegative_integer(group, "maximum_generation")
                    for group in species_groups
                ) != trial["maximum_generation"]:
                    raise RuntimeError("species maximum generation is incorrect")

                observed_deaths += trial["deaths"]
                observed_established += trial["established_offspring"]
                observed_seed_blockers += require_nonnegative_integer(blockers, "blocked")

            for name in (
                "living_plant_ticks",
                "descendant_plant_ticks",
                "sampled_energy",
                "sampled_water",
                "sampled_stress",
                "blooms",
                "deaths",
                "seeds_created",
                "germinations",
                "seeds_expired",
                "mutations",
                "established_offspring",
            ):
                expected = sum(require_nonnegative_integer(trial, name) for trial in trials)
                if totals.get(name) != expected:
                    raise RuntimeError(f"{policy_name}.{name} aggregate is incorrect")
            if totals.get("extinctions") != sum(
                trial.get("extinction_tick") is not None
                for trial in trials
                if isinstance(trial, dict)
            ):
                raise RuntimeError(f"{policy_name} extinction aggregate is incorrect")

            total_death_causes, total_deaths = validate_death_causes(
                totals.get("death_causes")
            )
            if total_deaths != totals.get("deaths"):
                raise RuntimeError("aggregate death causes do not sum to deaths")
            for name in ("energy", "water", "combined", "other"):
                expected = sum(
                    require_nonnegative_integer(trial["death_causes"], name)
                    for trial in trials
                    if isinstance(trial, dict)
                    and isinstance(trial.get("death_causes"), dict)
                )
                if total_death_causes.get(name) != expected:
                    raise RuntimeError(f"aggregate death cause {name} is incorrect")

            total_blockers = validate_seed_blockers(
                totals.get("seed_germination_blockers")
            )
            for name in (
                "samples",
                "dormant",
                "blocked",
                "moisture",
                "light",
                "plant_capacity",
                "node_capacity",
                "spacing",
            ):
                expected = sum(
                    require_nonnegative_integer(trial["seed_germination_blockers"], name)
                    for trial in trials
                    if isinstance(trial, dict)
                    and isinstance(trial.get("seed_germination_blockers"), dict)
                )
                if total_blockers.get(name) != expected:
                    raise RuntimeError(f"aggregate seed blocker {name} is incorrect")

            totals_agent = totals.get("agent")
            validate_agent(totals_agent)
            if not isinstance(totals_agent, dict):
                raise RuntimeError("aggregate agent telemetry is not an object")
            for name in (
                "decisions",
                "extend",
                "wait",
                "finish",
                "root",
                "shoot",
                "root_extend",
                "shoot_extend",
            ):
                expected = sum(
                    require_nonnegative_integer(trial["agent"], name)
                    for trial in trials
                    if isinstance(trial, dict) and isinstance(trial.get("agent"), dict)
                )
                if totals_agent.get(name) != expected:
                    raise RuntimeError(
                        f"{policy_name}.agent.{name} aggregate is incorrect"
                    )

            final_living = [
                require_nonnegative_integer(trial, "living") for trial in trials
            ]
            final_nodes = [
                require_nonnegative_integer(trial, "nodes") for trial in trials
            ]
            if totals.get("final_living_range") != [min(final_living), max(final_living)]:
                raise RuntimeError(f"{policy_name} final living range is incorrect")
            if totals.get("final_node_range") != [min(final_nodes), max(final_nodes)]:
                raise RuntimeError(f"{policy_name} final node range is incorrect")
            if totals.get("maximum_generation") != max(
                require_nonnegative_integer(trial, "maximum_generation")
                for trial in trials
            ):
                raise RuntimeError(f"{policy_name} maximum generation is incorrect")
            if totals.get("maximum_stress") != max(
                require_nonnegative_integer(trial, "maximum_stress") for trial in trials
            ):
                raise RuntimeError(f"{policy_name} maximum stress is incorrect")

            memory_counts = [
                require_nonnegative_integer(trial, "nonzero_memory_plants")
                for trial in trials
            ]
            if policy_name == "baseline" and any(memory_counts):
                raise RuntimeError("baseline policy unexpectedly changed recurrent memory")
            if policy_name == "adaptive" and not any(memory_counts):
                raise RuntimeError("adaptive policy did not exercise recurrent memory")

        for policy_name in POLICY_NAMES - {"baseline"}:
            if seeds_by_policy["baseline"] != seeds_by_policy[policy_name]:
                raise RuntimeError("policies did not receive identical trial seeds")
            policy_difference_counts[policy_name] += sum(
                left != right
                for left, right in zip(
                    hashes_by_policy["baseline"],
                    hashes_by_policy[policy_name],
                    strict=True,
                )
            )
    for policy_name, difference_count in policy_difference_counts.items():
        if difference_count == 0:
            raise RuntimeError(
                f"baseline and {policy_name} produced no observable difference"
            )
    if observed_deaths == 0 or observed_established == 0 or observed_seed_blockers == 0:
        raise RuntimeError("Garden evaluator test did not exercise its survival metrics")


def main() -> int:
    arguments = parse_arguments()
    first = run_evaluator(arguments.binary)
    second = run_evaluator(arguments.binary)
    if first != second:
        raise RuntimeError("Garden evaluator is not deterministic")
    validate_report(first)
    validate_maximum_duration(arguments.binary)

    with tempfile.TemporaryDirectory() as directory:
        report_path = Path(directory) / "garden-evaluation.json"
        report_path.write_text(json.dumps(first))
        summary = subprocess.run(
            [sys.executable, str(arguments.summary.resolve()), str(report_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        if summary.returncode != 0:
            detail = summary.stderr.strip() or summary.stdout.strip()
            raise RuntimeError(f"Garden summary failed: {detail}")
        summary_lines = summary.stdout.splitlines()
        if len(summary_lines) != 11 or not summary_lines[0].startswith(
            "Garden policy evaluation:"
        ):
            raise RuntimeError("Garden summary shape changed")

    for options in (
        ("--trials", "0"),
        ("--trials", "65"),
        ("--ticks", "0"),
        ("--ticks", "100001"),
        ("--seed", "0"),
        ("--seed", "not-a-number"),
        ("--trials",),
        ("--unknown",),
    ):
        rejected = subprocess.run(
            [str(arguments.binary.resolve()), *options],
            check=False,
            capture_output=True,
            text=True,
        )
        if rejected.returncode != 2:
            raise RuntimeError(f"invalid options {options!r} were not rejected")

    help_result = subprocess.run(
        [str(arguments.binary.resolve()), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    if help_result.returncode != 0 or not help_result.stdout.startswith("Usage:"):
        raise RuntimeError("Garden evaluator help failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
