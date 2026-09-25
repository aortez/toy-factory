#!/usr/bin/env python3
"""Check exact death receipts, corruption rejection, and diagnostic transparency."""

from __future__ import annotations

import argparse
import copy
import io
import json
from pathlib import Path
import subprocess

from garden_deaths import analyze_stream


def analyze(rows: list[dict]) -> dict:
    return analyze_stream(io.StringIO("".join(json.dumps(row) + "\n" for row in rows)))


def fixtures() -> list[dict]:
    plant = {"id": 1, "dead": False, "energy": 0, "water": 510, "stress": 7,
             "flags": 0, "nodes": 4, "roots": 2, "energy_income": 0, "water_income": 0,
             "agent": {"decisions": 0}}
    rows = [{"type": "world", "death_audit_version": 1, "tick": tick, "deaths": 0,
             "plants": [copy.deepcopy(plant)]} for tick in (0, 15, 30, 45)]
    death = {"type": "death", "version": 1, "tick": 60, "id": 1, "stress_before": 7,
             "flags": 3,
             "energy": {"before": 0, "income": 0, "overflow": 0, "upkeep_due": 1,
                        "upkeep_paid": 0, "discarded": 0},
             "water": {"before": 510, "income": 6, "overflow": 4, "upkeep_due": 1,
                       "upkeep_paid": 1, "discarded": 511}}
    plant.update(dead=True, energy=0, water=0, stress=8, flags=3)
    rows += [death, {"type": "world", "death_audit_version": 1, "tick": 60, "deaths": 1,
                     "plants": [plant]}]
    return rows


def check_fixtures() -> None:
    result = analyze(fixtures())
    assert result["checked_terminal_steps"] == 1
    assert result["terminal_resources"]["water"]["discarded"] == 511
    # Exact receipts support income above the legacy 8-bit telemetry ceiling.
    rows = fixtures()
    rows[-2]["water"].update(income=300, overflow=298)
    assert analyze(rows)["terminal_resources"]["water"]["income"] == 300
    for fault in ("missing", "duplicate", "identity", "version", "overflow", "paid", "discard",
                  "flags", "stress", "negative", "bool", "counter", "truncated", "metadata"):
        rows = fixtures()
        event = rows[-2]
        if fault == "missing":
            rows.pop(-2)
        elif fault == "duplicate":
            rows.insert(-2, copy.deepcopy(event))
        elif fault == "identity":
            event["id"] += 1
        elif fault == "version":
            event["version"] += 1
        elif fault == "overflow":
            event["water"]["overflow"] += 1
        elif fault == "paid":
            event["water"]["upkeep_paid"] += 1
        elif fault == "discard":
            event["water"]["discarded"] += 1
        elif fault == "flags":
            event["flags"] = 7
        elif fault == "stress":
            event["stress_before"] = 6
        elif fault == "negative":
            event["water"]["income"] = -1
        elif fault == "bool":
            event["water"]["upkeep_paid"] = True
        elif fault == "counter":
            rows[-1]["deaths"] = 2
        elif fault == "truncated":
            rows.pop()
        elif fault == "metadata":
            rows[-1].pop("death_audit_version")
        try:
            analyze(rows)
        except RuntimeError:
            continue
        raise AssertionError(f"accepted corrupt death trace: {fault}")


def check_native(binary: Path) -> None:
    deaths = 0
    for scenario, policy in (("rainfed", "baseline"), ("rainfed-crowded", "adaptive"),
                             ("irrigated", "neural-reference")):
        command = [str(binary.resolve()), "-", scenario, policy, "0x9c530b07",
                   "--ticks", "30720", "--ecology"]
        control = subprocess.run(command, check=True, capture_output=True, text=True).stdout
        audited = subprocess.run(command + ["--death-audit"], check=True,
                                 capture_output=True, text=True).stdout
        rows = [json.loads(line) for line in audited.splitlines()]
        deaths += analyze(rows)["checked_terminal_steps"]
        stripped = []
        for row in rows:
            if row["type"] == "death":
                continue
            row.pop("death_audit_version", None)
            stripped.append(row)
        assert stripped == [json.loads(line) for line in control.splitlines()]
    assert deaths > 0, "native panel never exercised death receipts"
    invalid = subprocess.run([str(binary.resolve()), "-", "rainfed", "baseline", "123",
                              "--death-audit", "--seed-sites"], capture_output=True)
    assert invalid.returncode == 2
    print(f"Death audit verified {deaths} native terminal budgets with identical control traces")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspector", type=Path, required=True)
    args = parser.parse_args()
    check_fixtures()
    check_native(args.inspector)
