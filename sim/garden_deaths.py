#!/usr/bin/env python3
"""Reconcile natural-death resource receipts from garden-inspect --death-audit."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
from typing import TextIO


RESOURCE_FIELDS = ("before", "income", "overflow", "upkeep_due", "upkeep_paid", "discarded")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def reconcile_death(previous: dict, plant: dict, event: dict, tick: int) -> None:
    require(event.get("version") == 1 and event["tick"] == tick and event["id"] == plant["id"],
            "death receipt identity/version mismatch")
    require(not previous["dead"] and plant["dead"] and tick % 60 == 0,
            "receipt does not describe a natural maintenance death")
    require(event["stress_before"] == previous["stress"] == 7 and plant["stress"] == 8,
            "terminal stress transition mismatch")
    require(plant["agent"] == previous["agent"], "dead plant committed an action")
    expected_flags = 1
    for name, cap, nodes, shortage in (
        ("energy", 256, previous["nodes"], 2),
        ("water", 512, previous["nodes"] - previous["roots"], 4),
    ):
        resource = event[name]
        require(set(resource) == set(RESOURCE_FIELDS), "unexpected resource receipt fields")
        require(all(type(resource[key]) is int and 0 <= resource[key] <= 65535
                    for key in RESOURCE_FIELDS), "invalid resource receipt value")
        require(resource["before"] == previous[name], "pre-step resource mismatch")
        available = min(cap, resource["before"] + resource["income"])
        due = (nodes + 7) // 8
        require(resource["overflow"] == max(0, resource["before"] + resource["income"] - cap),
                "resource overflow mismatch")
        require(resource["upkeep_due"] == due and resource["upkeep_paid"] == min(available, due),
                "terminal upkeep mismatch")
        require(resource["discarded"] == available - resource["upkeep_paid"],
                "terminal discard mismatch")
        require(plant[name] == 0 and plant[f"{name}_income"] == 0,
                "death did not clear live resource state")
        if available < due:
            expected_flags |= shortage
    require(expected_flags != 1 and event["flags"] == plant["flags"] == expected_flags,
            "terminal shortage flags mismatch")


def analyze_stream(stream: TextIO) -> dict:
    previous = {}
    pending = {}
    previous_tick = None
    previous_deaths = 0
    checked = 0
    totals = {name: {key: 0 for key in RESOURCE_FIELDS} for name in ("energy", "water")}
    for line in stream:
        row = json.loads(line)
        if row["type"] in ("bid", "leaf-bid"):
            continue
        if row["type"] == "death":
            key = (row["tick"], row["id"])
            require(key not in pending, "duplicate death receipt")
            pending[key] = row
            continue
        require(row["type"] == "world" and row.get("death_audit_version") == 1,
                "expected --death-audit world records")
        tick = row["tick"]
        require(tick == (0 if previous_tick is None else previous_tick + 15),
                "missing ecology sample")
        current = {plant["id"]: plant for plant in row["plants"]}
        require(len(current) == len(row["plants"]), "duplicate lineage")
        deaths = 0
        for lineage, plant in current.items():
            old = previous.get(lineage)
            if plant["dead"] and (old is None or not old["dead"]):
                require(old is not None, "death without a previous live sample")
                event = pending.pop((tick, lineage), None)
                require(event is not None, "missing death receipt")
                reconcile_death(old, plant, event, tick)
                for name in totals:
                    for key in RESOURCE_FIELDS:
                        totals[name][key] += event[name][key]
                deaths += 1
            if old is not None and old["dead"]:
                require(plant["dead"], "dead lineage revived")
        require(all(old["dead"] or lineage in current for lineage, old in previous.items()),
                "living lineage disappeared without a death sample")
        require(row["deaths"] - previous_deaths == deaths, "death counter/receipt mismatch")
        require(not pending, "unmatched death receipt")
        checked += deaths
        previous, previous_tick, previous_deaths = current, tick, row["deaths"]
    require(previous_tick is not None and not pending, "empty or truncated death trace")
    return {"schema_version": 1, "end_tick": previous_tick,
            "checked_terminal_steps": checked, "terminal_resources": totals}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    args = parser.parse_args()
    with (gzip.open(args.trace, "rt") if args.trace.suffix == ".gz" else args.trace.open()) as stream:
        print(json.dumps(analyze_stream(stream), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
