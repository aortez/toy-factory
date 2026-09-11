#!/usr/bin/env python3
"""Print a compact comparison from a Garden experiment JSON report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    return parser.parse_args()


def require_integer(container: dict[str, object], name: str) -> int:
    value = container.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RuntimeError(f"{name} is not a nonnegative integer")
    return value


def main() -> int:
    arguments = parse_arguments()
    report = json.loads(arguments.report.read_text())
    if not isinstance(report, dict) or report.get("schema_version") != 2:
        raise RuntimeError("unexpected Garden experiment schema")
    trial_count = require_integer(report, "trial_count")
    tick_count = require_integer(report, "tick_count")
    if trial_count == 0 or tick_count == 0:
        raise RuntimeError("Garden experiment dimensions must be positive")
    scenarios = report.get("scenarios")
    if not isinstance(scenarios, list):
        raise RuntimeError("Garden experiment scenarios are missing")

    print(f"Garden policy evaluation: {trial_count} trials x {tick_count} ticks")
    print(
        f"{'scenario':<11} {'policy':<8} {'avg live':>8} {'avg desc':>8} "
        f"{'final live':>10} {'deaths':>6} {'estab':>5} {'ext':>5} "
        f"{'germ':>5} {'blocked':>7} {'extend R/S':>12} {'wait':>7}"
    )
    for scenario in scenarios:
        if not isinstance(scenario, dict) or not isinstance(scenario.get("name"), str):
            raise RuntimeError("invalid Garden experiment scenario")
        policies = scenario.get("policies")
        if not isinstance(policies, list):
            raise RuntimeError("Garden experiment policies are missing")
        for policy in policies:
            if not isinstance(policy, dict) or not isinstance(policy.get("name"), str):
                raise RuntimeError("invalid Garden experiment policy")
            totals = policy.get("totals")
            if not isinstance(totals, dict):
                raise RuntimeError("Garden experiment totals are missing")
            agent = totals.get("agent")
            final_range = totals.get("final_living_range")
            if (
                not isinstance(agent, dict)
                or not isinstance(final_range, list)
                or len(final_range) != 2
                or any(not isinstance(value, int) for value in final_range)
            ):
                raise RuntimeError("invalid Garden experiment summary")
            living_ticks = require_integer(totals, "living_plant_ticks")
            descendant_ticks = require_integer(totals, "descendant_plant_ticks")
            blockers = totals.get("seed_germination_blockers")
            if not isinstance(blockers, dict):
                raise RuntimeError("Garden seed blocker totals are missing")
            decisions = require_integer(agent, "decisions")
            waits = require_integer(agent, "wait")
            average_living = living_ticks / (trial_count * tick_count)
            average_descendants = descendant_ticks / (trial_count * tick_count)
            wait_percentage = 100.0 * waits / decisions if decisions else 0.0
            print(
                f"{scenario['name']:<11} {policy['name']:<8} {average_living:8.2f} "
                f"{average_descendants:8.2f} "
                f"{final_range[0]:>4}..{final_range[1]:<4} "
                f"{require_integer(totals, 'deaths'):6d} "
                f"{require_integer(totals, 'established_offspring'):5d} "
                f"{require_integer(totals, 'extinctions'):>2d}/{trial_count:<2d} "
                f"{require_integer(totals, 'germinations'):5d} "
                f"{require_integer(blockers, 'blocked'):7d} "
                f"{require_integer(agent, 'root_extend'):5d}/"
                f"{require_integer(agent, 'shoot_extend'):<5d} "
                f"{wait_percentage:6.1f}%"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
