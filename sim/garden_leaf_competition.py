#!/usr/bin/env python3
"""Audit maintained-adult/offspring competition without changing frozen worlds."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import shutil
import tempfile

import garden_establishment as establishment
import garden_experiments as experiment
import garden_leaf_experiment as maintenance
from garden_node_audit import ownership
from garden_resources import budget, require

RELAXATIONS = {"none": 0, "nodes": 16, "plant_slots": 8, "spacing": 32,
               "all_space_limits": 56, "light": 4, "moisture": 2}


def lifetime_cohort(records: dict[int, dict], end: int, start: int = -1,
                    selected_ids: set[int] | None = None) -> dict:
    def survives(record):
        boundary = record["birth_tick"] + experiment.CYCLE_TICKS
        return boundary <= end and (record["death_tick"] is None or record["death_tick"] > boundary)

    children = {record["parent"] for record in records.values() if record["parent"] and survives(record)}
    selected = [r for r in records.values() if r["parent"] and start < r["birth_tick"] <= end
                and (selected_ids is None or r["id"] in selected_ids)]
    eligible = [r for r in selected if r["birth_tick"] + experiment.CYCLE_TICKS <= end]
    recent = [r for r in selected if r["birth_tick"] + experiment.CYCLE_TICKS > end]
    return {"offspring_born": len(selected), "eligible_offspring": len(eligible),
            "cycle_survivors": sum(survives(r) for r in eligible),
            "cycle_survivors_with_surviving_child": sum(survives(r) and r["id"] in children for r in eligible),
            "recent_alive": sum(r["death_tick"] is None or r["death_tick"] > end for r in recent),
            "recent_dead": sum(r["death_tick"] is not None and r["death_tick"] <= end for r in recent)}


def spatial_snapshot(row: dict) -> Counter:
    masks = [site[0] for site in row["sites"]]
    require(len(masks) == 28 and all(0 <= mask < 64 and not mask & 1 for mask in masks),
            "invalid spatial blocker masks")
    # Check the geometry interpretation against the simulator's query, not instead of it.
    live_coverage = []
    for column, mask in enumerate(masks):
        covered = any(abs(p["column"] - column) < 3 for p in row["plants"])
        require(bool(mask & 32) == covered, "spacing interpretation disagrees with native query")
        live_coverage.append(any(not p["dead"] and abs(p["column"] - column) < 3 for p in row["plants"]))
    return Counter({"samples": 1, "all_columns_spacing_blocked": int(all(m & 32 for m in masks)),
                    "all_columns_live_spacing_blocked": int(all(live_coverage)),
                    "physically_open_columns": sum(not (m & 6) for m in masks),
                    **{"any_open_relax_" + name: int(any(not (mask & ~bits) for mask in masks))
                       for name, bits in RELAXATIONS.items()}})


def world_analysis(path: Path, mode: str, capacity: int, horizon: int, late_start: int,
                   removal: dict | None = None,
                   disturbances: dict[int, dict] | None = None,
                   growth_policy: str | None = None, *, seed_capacity: int = 8,
                   seed_reserve: str | None = None,
                   root_bootstrap_after: int | None = None) -> tuple[dict, list[dict]]:
    require(removal is None or not disturbances, "cannot mix export and death boundaries")
    disturbances = disturbances or {}
    seen_disturbances = set()
    records = {}
    prior = {}
    previous = None
    references = []
    windows = {name: Counter() for name in ("whole", "late")}
    last_tick = -15
    late_origin = None
    removal_seen = False
    with gzip.open(path, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            require(row["type"] == "world", "non-world record in world census")
            maintenance.check_identity(row, mode, capacity, growth_policy=growth_policy,
                                       seed_capacity=seed_capacity, seed_reserve=seed_reserve,
                                       root_bootstrap_after=root_bootstrap_after)
            require(len(row["seeds"]) <= seed_capacity, "seed bank overflow")
            tick = row["tick"]
            require(tick == last_tick + 15 and tick <= horizon, "missing world checkpoint")
            require(row["sun_phase"] == (64 + tick // 15) % 256, "wrong sun phase")
            values = ownership(row, capacity)
            plants = {p["id"]: p for p in row["plants"]}
            born = died = produced = 0
            step_budget = Counter()
            for identity, plant in plants.items():
                old = prior.get(identity)
                if old is None:
                    require(identity not in records and not plant["dead"], "reused or dead newborn")
                    require(bool(plant["parent"]) == (tick != 0), "unexpected founder/newborn")
                    records[identity] = {key: plant[key] for key in ("id", "parent", "species", "generation", "column")}
                    records[identity].update(birth_tick=tick, death_tick=None, death_flags=None,
                                             seeds_created=0, late_seeds_created=0)
                    born += tick != 0
                record = records[identity]
                require(all(record[k] == plant[k] for k in ("parent", "species", "generation", "column")),
                        "lineage identity changed")
                if old is not None:
                    require(not old["dead"] or plant["dead"], "dead plant revived")
                if plant["dead"] and record["death_tick"] is None:
                    require(plant["flags"] & 6, "unrecorded environmental death")
                    record.update(death_tick=tick, death_flags=plant["flags"])
                    died += 1
                if tick and not plant["dead"]:
                    step_budget.update(budget(old, plant, tick))
                    step_budget["checked_live_steps"] += 1
                    seeded = plant["reproduction_cooldown"] == 16
                    produced += seeded
                    record["seeds_created"] += seeded
                    record["late_seeds_created"] += seeded and tick > late_start
            for identity in prior.keys() - plants.keys():
                if (removal is not None and identity == removal["id"]
                        and previous["tick"] == removal["tick"]):
                    require(not removal_seen and not prior[identity]["dead"], "invalid external removal")
                    # An observed lifetime ends here, but this is not a biological death.
                    records[identity].update(death_tick=removal["tick"], removal_tick=removal["tick"])
                    removal_seen = True
                else:
                    require(prior[identity]["dead"], "living plant disappeared")
                    records[identity]["reclaimed_tick"] = tick
            if previous is not None:
                require(born == row["births"] - previous["births"], "unreconciled births")
                require(died == row["deaths"] - previous["deaths"], "unreconciled deaths")
                require(produced == row["seeds_created"] - previous["seeds_created"], "seed-production disagreement")
            else:
                require(row["births"] == row["deaths"] == row["seeds_created"] == 0, "bad initial counters")
            # Budgets/seed births belong to the completed ordinary ecology step. Then
            # account for the environmental loss and carry post-event state forward.
            reference_row = row
            environmental = 0
            if tick in disturbances:
                boundary = disturbances[tick]
                require(boundary["before"] == row, "death boundary does not match ordinary step")
                row = boundary["after"]
                event = boundary["event"]
                environmental = len(event["killed"])
                for identity in event["killed"]:
                    require(identity in plants and not plants[identity]["dead"]
                            and records[identity]["death_tick"] is None, "invalid environmental victim")
                    records[identity].update(death_tick=tick, death_flags=1, environmental_death=True)
                plants = {p["id"]: p for p in row["plants"]}
                values = ownership(row, capacity)
                values.update(environmental_deaths=environmental,
                              environmental_energy_lost=event["energy"],
                              environmental_water_lost=event["water"])
                seen_disturbances.add(tick)
            live = [p for p in plants.values() if not p["dead"]]
            values.update({"samples": 1, "bank_full": int(len(row["seeds"]) == seed_capacity),
                           "bank_nonempty": int(bool(row["seeds"])), "bank_slots": len(row["seeds"]),
                           "plant_samples": len(live), "energy": sum(p["energy"] for p in live),
                           "water": sum(p["water"] for p in live),
                           "stressed_plants": sum(p["stress"] > 0 for p in live),
                           "below_bare_seed_energy": sum(p["energy"] < 48 for p in live),
                           "below_bare_seed_water": sum(p["water"] < 24 for p in live),
                           "unspent_flower_nodes": sum(p["flowers"] - p["spent_flowers"] for p in live),
                           "births": born, "deaths": died + environmental, "natural_deaths": died,
                           "seeds_created": produced,
                           "terminal_steps": died,
                           "seeds_expired": row["seeds_expired"] - (previous["seeds_expired"] if previous else 0)})
            values.update({"budget_" + key: value for key, value in step_budget.items()})
            if tick:
                windows["whole"].update(values)
                if tick > late_start:
                    windows["late"].update(values)
            if tick == late_start:
                late_origin = row
            references.append({**{name: reference_row[name] for name in ("tick", "hash", "sun_phase", "sun_strength", "rain_rate",
                              "nodes", "living", "births", "deaths", "seeds_created", "seeds_expired")},
                               "seed_bank": len(reference_row["seeds"]), "plant_slots": len(reference_row["plants"])})
            previous, prior, last_tick = row, plants, tick
    require(last_tick == horizon and late_origin is not None, "truncated world census")
    require(removal is None or removal_seen, "external removal was not observed")
    require(seen_disturbances == disturbances.keys(), "unobserved disturbance boundary")
    persistent = [p["id"] for p in previous["plants"] if not p["dead"]
                  and records[p["id"]]["birth_tick"] + experiment.CYCLE_TICKS <= late_start]
    result = {"windows": windows, "lineages": list(records.values()), "final": previous,
              "late_origin": late_origin, "persistent_mature_lineages": persistent,
              "lifetimes": {"whole": lifetime_cohort(records, horizon),
                            "late_born": lifetime_cohort(records, horizon, late_start)}}
    return result, references


def analyze(world_path: Path, site_path: Path, case: dict, capacity: int, horizon: int, late_cycles: int,
            removal: dict | None = None) -> dict:
    start = horizon - late_cycles * experiment.CYCLE_TICKS
    require(horizon % 15 == 0 and 0 <= start < horizon, "invalid late window")
    world, references = world_analysis(world_path, case["leaf_policy"], capacity, horizon, start, removal)
    final = world["final"]
    if removal is None:
        for row_name, trial_name in (("hash", "hash"), ("nodes", "nodes"), ("living", "living"),
                                      ("births", "germinations"), ("deaths", "deaths"),
                                      ("seeds_created", "seeds_created"), ("seeds_expired", "seeds_expired")):
            require(final[row_name] == case["trial"][trial_name], "frozen evaluator mismatch: " + row_name)
        for key in ("offspring_born", "eligible_offspring", "cycle_survivors", "cycle_survivors_with_surviving_child"):
            require(world["lifetimes"]["whole"][key] == case["trial"]["lifetimes"][key], "lifetime disagreement: " + key)
    spatial = {window: {phase: Counter() for phase in ("bright", "twilight", "night")}
               for window in ("whole", "late")}

    def sites_with_spatial_counters(stream):
        for line in stream:
            row = json.loads(line)
            values = spatial_snapshot(row)
            if row["tick"]:
                phase = "night" if row["sun_phase"] >= 128 else ("bright" if row["sun_strength"] >= 128 else "twilight")
                spatial["whole"][phase].update(values)
                if row["tick"] > start:
                    spatial["late"][phase].update(values)
            yield line

    with gzip.open(site_path, "rt") as stream:
        seeds = establishment.analyze_stream(sites_with_spatial_counters(stream), references, late_cycles, capacity)
    lineages = {p["id"]: p for p in world["lineages"]}
    for seed in seeds["seeds"]:
        if seed["outcome"] == "germinated":
            child = lineages[seed["child_id"]]
            require(child["parent"] == seed["parent"] and child["birth_tick"] == seed["end_tick"],
                    "seed/child lineage mismatch")
    return {"world": world, "seeds": seeds, "spatial": spatial}


def capture(command: list[str], destination: Path, output: Path, worlds: bool) -> None:
    with tempfile.TemporaryDirectory(prefix="garden-competition-") as temp:
        raw = Path(temp) / "census.jsonl"
        experiment.command_run(command, raw, output, 180)
        with raw.open("rb") as source, destination.open("xb") as target:
            with gzip.GzipFile(fileobj=target, filename="", mode="wb", mtime=0) as packed:
                for line in source:
                    kind = json.loads(line)["type"]
                    require(kind in (("world", "bid", "leaf-bid") if worlds else ("seed-sites",)),
                            "unexpected inspector record")
                    if not worlds or kind == "world":
                        packed.write(line)


def aggregate(cases: list[dict]) -> dict:
    result = {}
    for mode in maintenance.MODES:
        group = [case for case in cases if case["leaf_policy"] == mode]
        if not group:
            continue
        worlds = {window: Counter() for window in ("whole", "late")}
        spatial = {window: {phase: Counter() for phase in ("bright", "twilight", "night")}
                   for window in ("whole", "late")}
        lifetimes = {window: Counter() for window in ("whole", "late_born")}
        for case in group:
            data = case["analysis"]
            for window in worlds:
                worlds[window].update(data["world"]["windows"][window])
                for phase in spatial[window]:
                    spatial[window][phase].update(data["spatial"][window][phase])
            for window in lifetimes:
                lifetimes[window].update(data["world"]["lifetimes"][window])
        seed_group = establishment.aggregate([{"policy": mode, "analysis": c["analysis"]["seeds"]} for c in group])[mode]
        result[mode] = {"worlds": len(group), "world_windows": worlds, "spatial": spatial,
                        "lifetimes": lifetimes, "seeds": seed_group,
                        "final_living": sum(c["analysis"]["world"]["final"]["living"] for c in group),
                        "persistent_mature_lineages": sum(len(c["analysis"]["world"]["persistent_mature_lineages"]) for c in group),
                        "zero_late_birth_worlds": sum(c["analysis"]["world"]["windows"]["late"]["births"] == 0 for c in group)}
    return result


def collect(bundle: Path, output: Path, jobs: int) -> None:
    bundle, output = bundle.resolve(), output.resolve()
    manifest = experiment.read_json(bundle / "manifest.json")
    require(manifest.get("status") == "complete" and manifest.get("environment") == maintenance.ENVIRONMENT,
            "not a complete maintenance bundle")
    capacity = manifest["node_capacity"]
    require(capacity in (256, 512), "invalid capacity")
    require(not output.is_relative_to(experiment.ROOT) or output.is_relative_to(experiment.ROOT / "artifacts"),
            "output must be outside source or under artifacts/")
    output.mkdir(parents=True, exist_ok=False)
    for folder in ("input", "bin", "traces", "analyses"):
        (output / folder).mkdir()
    sources = experiment.source_files()
    experiment.snapshot_sources(output, sources)
    shutil.copy2(bundle / "manifest.json", output / "input/manifest.json")
    for original, target in (("cases.json", "input/cases.json"), ("model.tgm", "model.tgm"), ("bin/inspect", "bin/inspect")):
        shutil.copy2(establishment.verified(bundle, manifest, original), output / target)
        require(experiment.digest(output / target) == manifest["artifacts"][original], "input changed while copying")
    require(experiment.digest(output / "model.tgm") == maintenance.MODEL_SHA, "wrong frozen model")
    frozen = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
    selected = [c for c in experiment.read_json(output / "input/cases.json") if c["growth_policy"] == experiment.NIGHT_POLICY]
    keys = {(c["leaf_policy"], c["scenario"], c["seed"]) for c in selected}
    expected = {(mode, scenario, seed) for mode in maintenance.MODES for scenario in experiment.SCENARIOS
                for seed in experiment.trial_seeds(0x6d617463, 8)}
    require(len(selected) == len(keys) and keys == expected, "incomplete/mismatched veto panel")
    record = {"schema_version": 1, "kind": "garden-maintenance-competition", "node_capacity": capacity,
              "environment": maintenance.ENVIRONMENT, "input_manifest_sha256": experiment.digest(output / "input/manifest.json"),
              "source_sha256": sources, "horizon": maintenance.TICKS, "late_cycles": 8}
    experiment.write_json(output / "started.json", record)

    def run_case(index_case):
        index, case = index_case
        case_id = f"{index:02d}"
        base = ["bin/inspect", "model.tgm", case["scenario"], experiment.NIGHT_POLICY, "0x" + case["seed"],
                "--leaf-policy", case["leaf_policy"], "--ticks", str(maintenance.TICKS)]
        world_path = output / f"traces/{case_id}.world.jsonl.gz"
        site_path = output / f"traces/{case_id}.sites.jsonl.gz"
        capture(base + ["--ecology"], world_path, output, True)
        capture(base + ["--seed-sites"], site_path, output, False)
        analysis = analyze(world_path, site_path, case, capacity, maintenance.TICKS, 8)
        experiment.write_json(output / f"analyses/{case_id}.json", analysis)
        print(f"{capacity}/{case_id} {case['leaf_policy']}/{case['scenario']}/{case['seed']}: "
              f"{analysis['seeds']['checkpoints_verified']} hashes and {len(analysis['seeds']['seeds'])} seeds reconciled", flush=True)
        return {**case, "id": case_id, "commands": [base + ["--ecology"], base + ["--seed-sites"]], "analysis": analysis}

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        cases = list(pool.map(run_case, enumerate(sorted(selected, key=lambda c: (maintenance.MODES.index(c["leaf_policy"]), c["scenario"], c["seed"])), 1)))
    experiment.write_json(output / "summary.json", aggregate(cases))
    experiment.write_json(output / "cases.json", [{key: value for key, value in case.items() if key != "analysis"} for case in cases])
    require(experiment.source_files() == sources, "source changed during competition census")
    require(all(experiment.digest(output / name) == sha for name, sha in frozen.items()), "frozen input changed")
    record.update(status="complete", artifacts={str(p.relative_to(output)): experiment.digest(p)
                                                for p in output.rglob("*") if p.is_file()})
    experiment.write_json(output / "manifest.json", record)
    print(f"Complete: {output}; manifest sha256={experiment.digest(output / 'manifest.json')}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, choices=(1, 2, 4), default=2)
    args = parser.parse_args()
    collect(args.bundle, args.output, args.jobs)


if __name__ == "__main__":
    main()
