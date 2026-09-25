#!/usr/bin/env python3
"""Read-only first-day water audit of the frozen seed-reserve panel.

Root-cell moisture is post-step, not pre-uptake availability. Action counters
are deltas (last_action persists when the affordability gate skips decisions).
Terminal clearing is never treated as a resource debit or measured zero income.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path

import garden_seed_reserve as trial
from garden_resources import WATER_COST, budget, require

DAY, START, END = trial.turnover.DAY, trial.turnover.START, trial.turnover.END
BASELINE_SHA = "a4696431b029146d12f241161a7eb53a36b85d71a2efb1351df63ba30a429654"


def cells(plant):
    """Deduplicate roots without counting one soil cell's water twice."""
    result = {}
    require(len(plant["root_cells"]) == plant["roots"], "root count mismatch")
    for x, y, depth, water in plant["root_cells"]:
        require(0 <= x < 28 and 0 <= y < 11 and depth > 0 and 0 <= water <= 255,
                "invalid root cell")
        require((x, y) not in result or result[x, y] == water, "inconsistent shared moisture")
        result[x, y] = water
    return result


def outcome(record, end):
    boundary = record["birth_tick"] + DAY
    death = record["death_tick"]
    if death is not None and death <= min(boundary, end):
        if record.get("environmental_death"):
            return "patch"
        return {2: "energy", 4: "water", 6: "both"}[record["death_flags"] & 6]
    return "survived" if boundary <= end else "censored"


def point(row, plant, previous):
    values = budget(previous, plant, row["tick"])
    old_agent = {} if previous is None else previous["agent"]
    actions = {name: plant["agent"][name] - old_agent.get(name, 0)
               for name in ("decisions", "root_extend", "shoot_extend", "finish", "wait")}
    require(all(v >= 0 for v in actions.values()) and
            sum(actions[n] for n in ("root_extend", "shoot_extend", "finish", "wait")) ==
            actions["decisions"] <= 1, "invalid action deltas")
    require(actions["root_extend"] + actions["shoot_extend"] == values["extensions"],
            "extension tissue mismatch")
    cost = WATER_COST[plant["species"]]
    # Seed production happens later. A paid extension may fail geometrically;
    # action counts are therefore not the number of successfully appended roots.
    pre_growth = ((24 if previous is None else previous["water"]) + values["water_income"] -
                  values["water_overflow"] - values["water_upkeep"] - values.get("water_renewal", 0))
    require(pre_growth >= cost or actions["decisions"] == 0,
            "decision below water affordability threshold")
    roots = cells(plant)
    overlaps = []
    for other in row["plants"]:
        if other["id"] == plant["id"]:
            break  # This order is the native uptake order, not lineage sorting.
        if other["dead"]:
            continue
        shared = roots.keys() & cells(other).keys()
        if shared:
            overlaps.append({"id": other["id"], "cells": sorted(shared)})
    return {"tick": row["tick"], "hash": row["hash"], "phase": row["sun_phase"],
        "rain_rate": row["rain_rate"], "soil_total": row["soil"]["water"],
        "plant": plant, "budget": values, "actions": actions,
        "pre_growth_water": pre_growth, "water_below_growth_cost": pre_growth < cost,
        "unique_root_cells": len(roots), "root_post_water": sum(roots.values()),
        "deepest_root_row": max((y for x, y in roots), default=-1),
        "earlier_live_root_overlap": overlaps}


def summarize(record, history, end):
    require(history and history[0]["tick"] == record["birth_tick"], "missing birth")
    stop = min(record["birth_tick"] + DAY, end)
    death = record["death_tick"]
    if death is not None and death <= stop:
        stop = death if record.get("environmental_death") else death - 15
    require(history[-1]["tick"] == stop and
            len(history) == (stop - record["birth_tick"]) // 15 + 1,
            "incomplete first-day follow-up")
    totals = Counter()
    for p in history:
        totals.update(p["budget"])
        totals.update({"action_" + k: v for k, v in p["actions"].items()})
    water_parts = ("water_upkeep", "water_growth", "water_seeds", "water_renewal", "water_overflow")
    require(24 + totals["water_income"] - sum(totals[k] for k in water_parts) ==
            history[-1]["plant"]["water"], "first-day water balance mismatch")
    expanded = [p for p in history if p["deepest_root_row"] > 0]
    shortages = [p for p in history if p["tick"] % 60 == 0 and p["plant"]["flags"] & 4]
    cost = WATER_COST[record["species"]]
    first_root = next((p for p in history if p["actions"]["root_extend"]), None)
    before_root = [p for p in history if first_root is None or p["tick"] < first_root["tick"]]
    return {"lineage": record, "outcome": outcome(record, end), "live_samples": len(history),
        "age_followed_ticks": stop - record["birth_tick"], "budget": dict(totals),
        "water_root_extension": cost * totals["action_root_extend"],
        "water_shoot_extension": cost * totals["action_shoot_extend"],
        "water_finish": cost * totals["action_finish"],
        "birth": history[0], "last_alive": history[-1],
        "first_root_extension": first_root, "first_deeper_root": expanded[0] if expanded else None,
        "first_water_shortage": shortages[0] if shortages else None,
        "before_first_root_water_income": sum(p["budget"]["water_income"] for p in before_root),
        "before_first_root_shoot_extensions": sum(p["actions"]["shoot_extend"] for p in before_root),
        "no_income_samples": sum(p["budget"]["water_income"] == 0 for p in history[1:]),
        "below_water_growth_cost_samples": sum(p["water_below_growth_cost"] for p in history),
        "post_root_cells_dry_samples": sum(p["root_post_water"] == 0 for p in history),
        "earlier_overlap_samples": sum(bool(p["earlier_live_root_overlap"]) for p in history),
        "rain_samples": sum(p["rain_rate"] > 0 for p in history),
        "terminal_step_budget": None}


def analyze_stream(stream, boundaries, reference, key, gate, start=START, end=END, *, root_bootstrap_after=None):
    require(0 <= start < end <= END and gate in ("off", "on"), "invalid audit window/gate")
    side, capacity = key.split(".")[1:]
    require(side in ("neural", "reserve"), "invalid policy")
    records = {r["id"]: r for r in reference["lineages"]}
    require(len(records) == len(reference["lineages"]), "duplicate lineage")
    selected = {i: r for i, r in records.items() if r["parent"] and start < r["birth_tick"] <= end}
    histories = {i: [] for i in selected}
    events = {b["event"]["tick"]: b for b in boundaries}
    require(len(events) == len(boundaries), "duplicate patch boundary")
    for b in boundaries:
        trial.bank.recruitment.diversity.disturbance.validate_boundary(b["before"], b["after"], b["event"])
    previous, seen_deaths, seen_events, last_tick = {}, set(), set(), -15
    for line in stream:
        row = json.loads(line)
        tick = row["tick"]
        trial.bank.competition.maintenance.check_identity(row, "selective", 512,
            growth_policy=trial.bank.recruitment.policy.RESERVE if side == "reserve" else None,
            seed_capacity=int(capacity), seed_reserve=trial.RULE if gate == "on" else None,
            root_bootstrap_after=root_bootstrap_after)
        require(row["type"] == "world" and tick == last_tick + 15 and tick <= end and
                row["sun_phase"] == (64 + tick // 15) % 256, "missing/reordered world")
        current = {p["id"]: p for p in row["plants"]}
        require(len(current) == len(row["plants"]), "duplicate live ID")
        for i, p in current.items():
            if i not in selected:
                continue
            r = selected[i]
            if tick > min(r["birth_tick"] + DAY, end):
                continue
            require(tick >= r["birth_tick"], "plant precedes recorded birth")
            old = previous.get(i)
            if p["dead"]:
                if old is not None and not old["dead"]:
                    require(not r.get("environmental_death") and tick == r["death_tick"] and
                            p["flags"] == r["death_flags"] and tick % 60 == 0 and
                            old["stress"] == 7 and p["stress"] == 8 and
                            all(p[k] == 0 for k in ("water", "energy", "water_income", "energy_income")),
                            "unexpected terminal clearing")
                    seen_deaths.add(i)
                continue
            require((old is None) == (tick == r["birth_tick"]) and
                    (r["death_tick"] is None or tick <= r["death_tick"]), "inconsistent lifetime")
            histories[i].append(point(row, p, old))
        if tick in events:
            b = events[tick]
            require(row == b["before"], "patch snapshot mismatch")
            seen_events.add(tick)
            for i in b["event"]["killed"]:
                if i in selected and tick <= selected[i]["birth_tick"] + DAY:
                    require(selected[i].get("environmental_death") and
                            selected[i]["death_tick"] == tick, "patch lifetime mismatch")
                    seen_deaths.add(i)
            current = {p["id"]: p for p in b["after"]["plants"]}
        previous, last_tick = current, tick
    require(last_tick == end and seen_events == events.keys(), "incomplete world/boundaries")
    expected_deaths = {i for i, r in selected.items() if r["death_tick"] is not None and
                       r["death_tick"] <= min(r["birth_tick"] + DAY, end)}
    require(seen_deaths == expected_deaths, "first-day death coverage mismatch")
    results = [summarize(r, histories[i], end) for i, r in selected.items()]
    counts = Counter(r["outcome"] for r in results)
    failed = [r for r in results if r["outcome"] in ("water", "both")]
    # Natural adult deaths are retained as a separate count, not silently folded
    # into the seedling diagnosis; this audit does not reconstruct adult budgets.
    deaths = [r for r in records.values() if r["death_tick"] is not None and
              start < r["death_tick"] <= end and not r.get("environmental_death")]
    death_counts = Counter(("seedling" if r["death_tick"] - r["birth_tick"] <= DAY else "adult") +
                          ("_water" if r["death_flags"] & 4 else "_energy") for r in deaths)
    return {"key": key, "gate": gate, "world_rows": end // 15 + 1,
        "cohort": {"birth_start_exclusive": start, "birth_end_inclusive": end,
                   "followup_ticks": DAY, "born": len(results)},
        "outcomes": dict(counts), "closing_natural_deaths": dict(death_counts),
        "water_failures": {"count": len(failed),
            "no_root_extension": sum(not r["budget"]["action_root_extend"] for r in failed),
            "no_deeper_root": sum(r["first_deeper_root"] is None for r in failed),
            "no_earlier_root_overlap": sum(not r["earlier_overlap_samples"] for r in failed)},
        "checked_live_budgets": sum(len(h) for h in histories.values()), "seedlings": results}, histories


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=trial.experiment.ROOT / "artifacts/garden-seed-reserve-v3")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, output = args.baseline.resolve(), args.output.resolve()
    require(trial.experiment.digest(root / "manifest.json") == BASELINE_SHA, "wrong frozen input manifest")
    manifest = trial.experiment.read_json(root / "manifest.json")
    require(manifest["status"] == "complete" and manifest["kind"] == "garden-seed-reserve", "incomplete input")
    require(not output.exists() and not output.is_relative_to(root), "output exists/overlaps frozen input")
    output.mkdir(parents=True)
    sources = trial.experiment.source_files()
    trial.experiment.snapshot_sources(output, sources)
    inputs, results = {}, []
    for key in trial.KEYS:
        for gate in ("off", "on"):
            name = f"{key}.{gate}"
            names = (f"traces/{name}.world.gz", f"analyses/{name}.json", f"analyses/{name}.boundaries.json")
            paths = [trial.bank.establishment.verified(root, manifest, n) for n in names]
            inputs.update({n: manifest["artifacts"][n] for n in names})
            reference = trial.experiment.read_json(paths[1])
            boundaries = trial.experiment.read_json(paths[2])
            with gzip.open(paths[0], "rt") as stream:
                result, histories = analyze_stream(stream, boundaries, reference["world"], key, gate)
            require(result["cohort"]["born"] == reference["lifetimes"]["closing"]["born"], "cohort mismatch")
            trial.experiment.write_json(output / f"{name}.json", result)
            # These are extracted native observations plus derived accounting,
            # not new simulation steps or a Python implementation of the world.
            with gzip.open(output / f"{name}.histories.json.gz", "xt") as stream:
                json.dump(histories, stream, separators=(",", ":"))
            results.append(result)
            print(name, result["outcomes"], result["water_failures"], flush=True)
    trial.experiment.write_json(output / "summary.json", {"input_manifest_sha256": BASELINE_SHA, "runs": results})
    require(sources == trial.experiment.source_files(), "source changed during analysis")
    trial.experiment.write_json(output / "manifest.json", {"kind": "garden-seedling-water", "status": "complete",
        "input_manifest_sha256": BASELINE_SHA, "inputs": inputs, "source_sha256": sources,
        "artifacts": {str(p.relative_to(output)): trial.experiment.digest(p) for p in sorted(output.iterdir()) if p.is_file()}})
    print("Complete:", trial.experiment.digest(output / "manifest.json"), flush=True)


if __name__ == "__main__":
    main()
