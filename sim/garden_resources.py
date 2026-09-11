#!/usr/bin/env python3
"""Check and summarize ecology/decision traces without changing a Garden world."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
from typing import TextIO


CYCLE_TICKS = 3840
ENERGY_CAP = 256
WATER_CAP = 512
ENERGY_COST = {"flower": 9, "shrub": 8, "ground-cover": 7}
WATER_COST = {"flower": 5, "shrub": 5, "ground-cover": 4}
TOTAL_KEYS = (
    "energy_income", "water_income", "energy_overflow", "water_overflow",
    "energy_upkeep", "water_upkeep", "energy_growth", "water_growth",
    "energy_seeds", "water_seeds", "extensions", "finishes", "waits",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def budget(previous: dict | None, plant: dict, tick: int) -> dict:
    """Reconcile live-step stores using existing telemetry; do not invent death income.

    These constants mirror hash-v5 mechanics, not a second simulation. A mismatch
    fails analysis. mark_plant_dead clears stores AND income; terminal steps must
    remain explicitly unaccounted, rather than interpreting that clear as upkeep.
    """
    newborn = previous is None
    require(not plant["dead"], "cannot reconstruct cleared terminal-step income")
    energy = 64 if newborn else previous["energy"]
    water = 24 if newborn else previous["water"]
    old_agent = {} if newborn else previous["agent"]
    values = {key: 0 for key in TOTAL_KEYS}
    for name in ("energy", "water"):
        income = plant[f"{name}_income"]
        require(income < 255, "saturated income telemetry cannot support exact accounting")
        values[f"{name}_income"] = income
    values["energy_overflow"] = max(0, energy + values["energy_income"] - ENERGY_CAP)
    values["water_overflow"] = max(0, water + values["water_income"] - WATER_CAP)
    energy = min(ENERGY_CAP, energy + values["energy_income"])
    water = min(WATER_CAP, water + values["water_income"])
    if not newborn and tick % 60 == 0:
        # Maintenance precedes germination/growth and charges the old body.
        values["energy_upkeep"] = min(energy, (previous["nodes"] + 7) // 8)
        values["water_upkeep"] = min(water, (previous["nodes"] - previous["roots"] + 7) // 8)
    for output, counter in (("extensions", "extend"), ("finishes", "finish"), ("waits", "wait")):
        values[output] = plant["agent"][counter] - old_agent.get(counter, 0)
    require(all(value >= 0 for value in values.values()), "negative resource/counter delta")
    require(values["extensions"] + values["finishes"] + values["waits"] <= 1,
            "more than one committed action in an ecology step")
    paid_actions = values["extensions"] + values["finishes"]
    values["energy_growth"] = paid_actions * (ENERGY_COST[plant["species"]] - (plant["vigor"] > 0))
    values["water_growth"] = paid_actions * WATER_COST[plant["species"]]
    # A creation sets 16; the next step always decrements it. This is not the
    # offspring counter, which increments when a seed eventually germinates.
    if plant["reproduction_cooldown"] == 16:
        values["energy_seeds"] = 48
        values["water_seeds"] = 24
    expected_energy = energy - values["energy_upkeep"] - values["energy_growth"] - values["energy_seeds"]
    expected_water = water - values["water_upkeep"] - values["water_growth"] - values["water_seeds"]
    require((expected_energy, expected_water) == (plant["energy"], plant["water"]),
            f"budget mismatch at tick {tick}, lineage {plant['id']}: "
            f"expected {(expected_energy, expected_water)}, got {(plant['energy'], plant['water'])}")
    return values


def checkpoint(world: dict, plant: dict) -> dict:
    return {"tick": world["tick"], "sun_phase": world["sun_phase"], **{
        key: plant[key] for key in (
            "energy", "water", "nodes", "roots", "active_leaves", "stress", "flags", "tips",
        )
    }}


def analyze(path: Path) -> dict:
    with (gzip.open(path, "rt") if path.suffix == ".gz" else path.open()) as stream:
        return analyze_stream(stream, str(path))


def analyze_stream(stream: TextIO, trace_name: str) -> dict:
    previous = {}
    lineages = {}
    pending_bids = {}
    checkpoints = {}
    previous_tick = None
    checked_steps = 0
    checked_winners = 0
    terminal_steps = 0
    changed_bids = 0
    probe_bids = 0
    suppressed_bids = 0
    first_changed_bid_tick = None
    changed_lineages = set()
    for line in stream:
        world = json.loads(line)
        if world["type"] == "bid":
            if "probe" in world:
                require(world["probe"] == "no-night-growth-v1", "unknown policy probe")
                require(world["sun_phase"] == (64 + world["tick"] // 15) % 256,
                        "invalid probe sun phase")
                action = world["probe_original_action"]
                require(action in (0, 1, 2), "invalid pre-probe action")
                expected = 0 if world["sun_phase"] >= 128 else action
                require(world["action"] == expected, "night-growth probe changed unexpected action")
                probe_bids += 1
                suppressed_bids += world["action"] != action
            if (world["priority"] != world.get("original_priority", world["priority"]) or
                    world["action"] != world.get("original_action", world["action"])):
                changed_bids += 1
                changed_lineages.add(world["id"])
                if first_changed_bid_tick is None:
                    first_changed_bid_tick = world["tick"]
            pending_bids.setdefault((world["tick"], world["id"]), []).append(world)
            continue
        require(world["type"] == "world", "unknown trace record")
        tick = world["tick"]
        require((previous_tick is None and tick == 0) or tick == previous_tick + 15,
                "trace must include every ecology sample, starting at reset")
        require(world["sun_phase"] == (64 + tick // 15) % 256, "unexpected sun phase")
        previous_tick = tick
        if tick % CYCLE_TICKS == 0:
            checkpoints[str(tick // CYCLE_TICKS)] = world["hash"]
        current = {plant["id"]: plant for plant in world["plants"]}
        require(len(current) == len(world["plants"]), "duplicate lineage in world")
        for id, plant in current.items():
            old = previous.get(id)
            if id not in lineages:
                require(tick == 0 or plant["parent"] > 0, "unexpected late founder")
                lineages[id] = {
                    "id": id, "parent": plant["parent"], "species": plant["species"],
                    "generation": plant["generation"], "birth_tick": tick,
                    "death_tick": None, "last_living": None,
                    "checkpoints": {"birth": checkpoint(world, plant)},
                    "first_cycle": {key: 0 for key in TOTAL_KEYS},
                    "first_cycle_night": {key: 0 for key in TOTAL_KEYS},
                }
            record = lineages[id]
            bids = pending_bids.pop((tick, id), [])
            old_decisions = 0 if old is None else old["agent"]["decisions"]
            decision_delta = plant["agent"]["decisions"] - old_decisions
            require(decision_delta == (1 if bids else 0), "bid/committed-decision disagreement")
            if bids:
                winner = max(bids, key=lambda bid: bid["priority"])
                require(all(bid["energy"] == winner["energy"] and bid["water"] == winner["water"]
                            for bid in bids), "bids did not observe the same stores")
                require(all(winner[key] == plant["agent"][f"last_{key}"]
                            for key in ("priority", "action", "tissue", "x", "y")),
                        "recorded bids do not explain committed winner")
                checked_winners += 1
            if plant["dead"]:
                if record["death_tick"] is None:
                    record["death_tick"] = tick
                    record["checkpoints"]["death"] = checkpoint(world, plant)
                    terminal_steps += 1
                continue
            require(record["death_tick"] is None, "dead lineage revived")
            record["last_living"] = checkpoint(world, plant)
            marks = record["checkpoints"]
            for name, condition in (
                ("first_water_shortage", plant["flags"] & 4),
                ("first_energy_shortage", plant["flags"] & 2),
                ("first_root_growth", plant["agent"]["root_extend"] > 0),
                ("first_sunset", world["sun_phase"] == 128),
                ("first_dawn", world["sun_phase"] == 0),
                ("cycle_boundary", tick == record["birth_tick"] + CYCLE_TICKS),
            ):
                if condition and name not in marks:
                    marks[name] = checkpoint(world, plant)
            if tick == 0:
                continue
            values = budget(old, plant, tick)
            checked_steps += 1
            if tick - record["birth_tick"] <= CYCLE_TICKS:
                for key, value in values.items():
                    record["first_cycle"][key] += value
                    if world["sun_phase"] >= 128:
                        record["first_cycle_night"][key] += value
        require(not pending_bids, "bids without a corresponding live world entry")
        previous = current
    require(previous_tick is not None, "empty trace")
    require(not pending_bids, "truncated trace ends with an uncommitted bid")
    result = {
        "trace": trace_name, "end_tick": previous_tick,
        "checked_live_steps": checked_steps, "checked_winners": checked_winners,
        "terminal_steps_not_reconstructed": terminal_steps,
        "changed_bids": changed_bids, "first_changed_bid_tick": first_changed_bid_tick,
        "changed_lineages": sorted(changed_lineages),
        "cycle_hashes": checkpoints, "lineages": list(lineages.values()),
    }
    if probe_bids:
        result["probe"] = {"name": "no-night-growth-v1", "bids": probe_bids,
                           "suppressed_bids": suppressed_bids}
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--lineage", type=int)
    parser.add_argument("--reference", type=Path, help="saved evaluator artifact directory")
    parser.add_argument("--scenario")
    parser.add_argument("--policy")
    parser.add_argument("--seed")
    args = parser.parse_args()
    if args.reference and not all((args.scenario, args.policy, args.seed)):
        parser.error("--reference requires --scenario, --policy, and --seed (eight hex digits)")
    result = analyze(args.trace)
    if args.reference:
        require(result["changed_bids"] == 0, "counterfactual trace cannot be checked as an unchanged replay")
        checked = 0
        for path in sorted(args.reference.glob("cycles-*.json")):
            report = json.loads(path.read_text())
            scenario = next(s for s in report["scenarios"] if s["name"] == args.scenario)
            policy = next(p for p in scenario["policies"] if p["name"] == args.policy)
            trial = next(t for t in policy["trials"] if t["seed"] == args.seed)
            cycle = str(report["tick_count"] // CYCLE_TICKS)
            require(result["cycle_hashes"].get(cycle) == trial["hash"], f"replay hash mismatch at cycle {cycle}")
            checked += 1
        require(checked > 0, "no reference reports found")
        result["reference_hashes_checked"] = checked
    if args.lineage is not None:
        result["lineages"] = [v for v in result["lineages"] if v["id"] == args.lineage]
        require(bool(result["lineages"]), "lineage not present in trace")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
