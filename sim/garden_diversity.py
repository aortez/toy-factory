#!/usr/bin/env python3
"""Host-only 192-day recurring-disturbance population and diversity audit."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import shutil
import zlib

import garden_disturbance as disturbance
import garden_establishment as establishment
import garden_experiments as experiment
import garden_leaf_competition as competition
import garden_leaf_experiment as maintenance
from garden_gallery import contact_sheet, rgb565be_to_rgb888, write_png
from garden_node_audit import ownership
from garden_resources import require

DAY = experiment.CYCLE_TICKS
HORIZON = 192 * DAY
CHECKPOINTS = (64 * DAY, 128 * DAY, HORIZON)
SCHEDULE_BASE = 0x6c6f6e67
SCHEDULES = {"control": None, **{f"fresh-{i}": int(seed, 16)
    for i, seed in enumerate(experiment.trial_seeds(SCHEDULE_BASE, 4), 1)}}
SPECIES = ("flower", "shrub", "ground-cover")


def population(row: dict, records: dict[int, dict]) -> dict:
    live = [p for p in row["plants"] if not p["dead"]]
    families = Counter(records[p["id"]]["founder"] for p in live)
    species = Counter(p["species"] for p in live)
    bank_families, bank_species = set(), set()
    for seed in row["seeds"]:
        require(seed["parent"] in records, "unknown seed parent")
        parent = records[seed["parent"]]
        require(seed["generation"] == parent["generation"] + 1, "seed generation mismatch")
        # Species is inherited unchanged by create_seed(); traits, not species, mutate.
        bank_families.add(parent["founder"])
        bank_species.add(parent["species"])
    n = len(live)
    require(n == row["living"], "wrong population size")
    return {"tick": row["tick"], "hash": row["hash"], "living": n, "seeds": len(row["seeds"]),
            "births": row["births"], "deaths": row["deaths"], "nodes": row["nodes"],
            "max_generation": row["max_generation"],
            "species": {s: species[s] for s in SPECIES},
            "families": {str(k): families[k] for k in sorted(families)},
            "living_species": len(species), "living_families": len(families),
            "extant_species": sorted(set(species) | bank_species),
            "extant_families": sorted(set(families) | bank_families),
            "effective_families": n*n/sum(c*c for c in families.values()) if n else 0,
            "largest_family_fraction": max(families.values())/n if n else 0,
            "living_genotypes": len({(p["species"], tuple(p["genome"])) for p in live}),
            "extinct": n == 0 and not row["seeds"]}


def analyze(path: Path, boundaries: list[dict], capacity: int, horizon: int,
            schedule_seed: int | None, drainage: str | None = None,
            growth_policy: str | None = None) -> dict:
    require(horizon % DAY == 0 and disturbance.FIRST <= horizon <= HORIZON, "invalid audit horizon")
    expected = disturbance.schedule(schedule_seed, horizon)
    require(len(boundaries) == len(expected) and all(
        all(b["event"][k] == v for k, v in e.items())
        for b, e in zip(boundaries, expected, strict=True)), "incomplete/wrong disturbance schedule")
    for b in boundaries:
        disturbance.validate_boundary(b["before"], b["after"], b["event"])
    events = {b["event"]["tick"]: b for b in boundaries}
    require(len(events) == len(boundaries), "duplicate disturbance boundary")
    records, prior, daily, checkpoints = {}, {}, {}, {}
    previous = None
    establishment_snapshot = None
    seen_events = set()
    observed_rows = 0
    immutable = ("parent", "species", "generation", "column", "genome")
    with gzip.open(path, "rt") as source:
        for line in source:
            row = json.loads(line)
            require(row["type"] == "world", "non-world population row")
            maintenance.check_identity(row, "selective", capacity, drainage, growth_policy)
            ownership(row, capacity)
            tick = row["tick"]
            require(tick % 15 == 0 and tick <= horizon and
                    (tick > previous["tick"] if previous else tick == 0), "invalid census tick order")
            require(row["sun_phase"] == (64 + tick//15) % 256, "wrong sun phase")
            plants = {p["id"]: p for p in row["plants"]}
            born = died = 0
            for identity, plant in plants.items():
                old = prior.get(identity)
                if old is None:
                    require(identity not in records and not plant["dead"], "missing birth/reused identity")
                    parent = plant["parent"]
                    require(bool(parent) == (tick != 0), "unexpected founder/offspring")
                    require(plant["age_ecology_ticks"] == (1 if parent else 0), "missed birth boundary")
                    if parent:
                        require(parent in records and parent < identity, "unknown/noncausal parent")
                        require(plant["species"] == records[parent]["species"] and
                                plant["generation"] == records[parent]["generation"] + 1, "invalid inheritance")
                    else:
                        require(plant["generation"] == 0, "invalid founder generation")
                    records[identity] = {"id": identity, **{k: plant[k] for k in immutable},
                        "founder": records[parent]["founder"] if parent else identity,
                        "birth_tick": tick, "initial_age": plant["age_ecology_ticks"],
                        "death_tick": None, "death_flags": None}
                    born += tick != 0
                record = records[identity]
                require(all(record[k] == plant[k] for k in immutable), "lineage identity/traits changed")
                require(old is None or not old["dead"] or plant["dead"], "dead plant revived")
                expected_age = record["initial_age"] + (tick-record["birth_tick"])//15
                if not plant["dead"]:
                    require(plant["age_ecology_ticks"] == expected_age, "live age drift/wrap")
                elif record["death_tick"] is None:
                    require(plant["flags"] & 6, "missing environmental death")
                    require(plant["age_ecology_ticks"] == expected_age-1, "missed natural death boundary")
                    record.update(death_tick=tick, death_flags=plant["flags"])
                    died += 1
            for identity in prior.keys() - plants.keys():
                require(prior[identity]["dead"], "living plant disappeared")
            if previous:
                require(born == row["births"]-previous["births"] and died == row["deaths"]-previous["deaths"],
                        "unreconciled birth/death counters")
                require(all(row[k] >= previous[k] for k in ("seeds_created", "seeds_expired", "max_generation")),
                        "counter regression")
            else:
                require(row["births"] == row["deaths"] == row["seeds_created"] == row["seeds_expired"] == 0,
                        "bad initial counters")
            if tick == disturbance.FIRST:
                establishment_snapshot = population(row, records)
            if tick in events:
                boundary = events[tick]
                require(boundary["before"] == row, "event does not match census")
                for identity in boundary["event"]["killed"]:
                    require(records[identity]["death_tick"] is None, "duplicate environmental death")
                    records[identity].update(death_tick=tick, death_flags=1, environmental_death=True)
                row = boundary["after"]
                plants = {p["id"]: p for p in row["plants"]}
                seen_events.add(tick)
            if tick % DAY == 0:
                daily[tick] = population(row, records)
            if tick in CHECKPOINTS or tick == horizon:
                checkpoints[tick] = row
            previous, prior = row, plants
            observed_rows += 1
    require(previous is not None and previous["tick"] == horizon, "truncated population census")
    require(seen_events == events.keys(), "missing event sample")
    require(set(daily) == set(range(0, horizon+1, DAY)) and establishment_snapshot is not None,
            "missing daily/establishment sample")
    require(previous["deaths"] == sum(p["death_tick"] is not None for p in records.values()),
            "unreconciled final mortality")
    for earlier, later in zip(list(daily.values()), list(daily.values())[1:]):
        require(set(later["extant_families"]) <= set(earlier["extant_families"]), "extinct family reappeared")
        require(set(later["extant_species"]) <= set(earlier["extant_species"]), "extinct species reappeared")
    milestones = {}
    for tick, row in checkpoints.items():
        start = max(disturbance.FIRST, tick-32*DAY)
        deceased = [p for p in records.values() if p["death_tick"] is not None and start < p["death_tick"] <= tick]
        milestones[str(tick)] = {"population": daily[tick],
            "post_establishment": competition.lifetime_cohort(records, tick, disturbance.FIRST),
            "closing": competition.lifetime_cohort(records, tick, start),
            "closing_start": start,
            "closing_natural_deaths": sum(not p.get("environmental_death") for p in deceased),
            "closing_environmental_deaths": sum(bool(p.get("environmental_death")) for p in deceased)}
    return {"observed_rows": observed_rows, "establishment": establishment_snapshot,
            "daily": list(daily.values()), "milestones": milestones, "final": previous,
            "lineages": list(records.values()), "events": [b["event"] for b in boundaries],
            "first_observed_extinction_tick": next((d["tick"] for d in daily.values() if d["extinct"]), None)}


def compare_sparse_prefix(current: Path, frozen: Path, end: int) -> int:
    count, last = 0, None
    with gzip.open(current, "rt") as left, gzip.open(frozen, "rt") as right:
        other = json.loads(next(right))
        for line in left:
            row = json.loads(line)
            if row["tick"] > end:
                break
            while other["tick"] < row["tick"]:
                other = json.loads(next(right))
            require(row == other, "frozen population-prefix mismatch")
            count += 1
            last = row["tick"]
    require(last == end, "missing comparison endpoint")
    return count


def distribution(values: list) -> dict:
    require(bool(values), "empty distribution")
    values = sorted(values)
    n = len(values)
    return {"min": values[0], "median": (values[(n-1)//2]+values[n//2])/2,
            "mean": sum(values)/n, "max": values[-1], "values": values}


def summarize(cases: list[dict]) -> dict:
    summary = {}
    for arm in SCHEDULES:
        group = [c["analysis"] for c in cases if c["arm"] == arm]
        require(len(group) == 16, "incomplete matched arm")
        stages = {}
        for tick in CHECKPOINTS:
            values = [a["milestones"][str(tick)] for a in group]
            totals, post, closing = Counter(), Counter(), Counter()
            for a, value in zip(group, values, strict=True):
                p = value["population"]
                post.update(value["post_establishment"])
                closing.update(value["closing"])
                totals.update({"living": p["living"], "seeds": p["seeds"], "extinct_worlds": int(p["extinct"]),
                    "worlds_with_closing_births": int(value["closing"]["offspring_born"] > 0),
                    "worlds_with_closing_day_survivors": int(value["closing"]["cycle_survivors"] > 0),
                    "worlds_with_closing_durable_parents": int(value["closing"]["cycle_survivors_with_surviving_child"] > 0),
                    "single_extant_family_worlds": int(len(p["extant_families"]) == 1),
                    "single_extant_species_worlds": int(len(p["extant_species"]) == 1),
                    "worlds_losing_established_family": int(len(p["extant_families"]) < len(a["establishment"]["extant_families"])),
                    "worlds_losing_established_species": int(len(p["extant_species"]) < len(a["establishment"]["extant_species"])),
                    "closing_natural_deaths": value["closing_natural_deaths"],
                    "closing_environmental_deaths": value["closing_environmental_deaths"]})
            stages[str(tick//DAY)] = {"totals": totals, "post_establishment": post, "closing": closing,
                "distributions": {key: distribution([v["population"][key] for v in values]) for key in
                    ("living", "living_species", "living_families", "effective_families", "largest_family_fraction", "living_genotypes")},
                "extant_family_distribution": distribution([len(v["population"]["extant_families"]) for v in values]),
                "extant_species_distribution": distribution([len(v["population"]["extant_species"]) for v in values])}
        summary[arm] = {"worlds": len(group), "milestones": stages,
                       "observed_rows": sum(a["observed_rows"] for a in group),
                       "events": sum(len(a["events"]) for a in group),
                       "hits": sum(bool(e["killed"]) for a in group for e in a["events"])}
    return summary


def collect(bundle: Path, build: Path, output: Path, jobs: int) -> None:
    bundle, build, output = bundle.resolve(), build.resolve(), output.resolve()
    manifest = experiment.read_json(bundle / "manifest.json")
    require(manifest.get("status") == "complete" and manifest.get("kind") == "garden-patch-disturbance",
            "wrong frozen 64-day panel")
    capacity = manifest["node_capacity"]
    require(capacity in (256, 512), "wrong capacity")
    require(not output.is_relative_to(experiment.ROOT) or output.is_relative_to(experiment.ROOT / "artifacts"),
            "output must be outside source or under artifacts/")
    selected = [c for c in experiment.read_json(establishment.verified(bundle, manifest, "cases.json")) if c["arm"] == "control"]
    expected = {(s, seed) for s in experiment.SCENARIOS for seed in experiment.trial_seeds(0x6d617463, 8)}
    require(len(selected) == 16 and {(c["scenario"], c["seed"]) for c in selected} == expected, "incomplete panel")
    output.mkdir(parents=True, exist_ok=False)
    for folder in ("input", "bin", "traces", "analyses", "frames"):
        (output / folder).mkdir()
    sources = experiment.source_files()
    experiment.snapshot_sources(output, sources)
    shutil.copy2(bundle / "manifest.json", output / "input/manifest.json")
    for case in selected:
        name = f"traces/{case['id']}.control.world.gz"
        shutil.copy2(establishment.verified(bundle, manifest, name), output / f"input/{case['id']}.world.gz")
    shutil.copy2(establishment.verified(bundle, manifest, "model.tgm"), output / "model.tgm")
    require(experiment.digest(output / "model.tgm") == maintenance.MODEL_SHA, "wrong model")
    experiment.write_json(output / "input/cases.json", selected)
    for tool in ("inspect", "replay"):
        shutil.copy2(build / f"toy-factory-garden-{tool}", output / f"bin/{tool}")
    shutil.copy2(build / "CMakeCache.txt", output / "build-cache.txt")
    frozen = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
    record = {"schema_version": 1, "kind": "garden-disturbance-longevity", "protocol": disturbance.PROTOCOL,
              "node_capacity": capacity, "horizon": HORIZON, "checkpoint_ticks": list(CHECKPOINTS),
              "schedule_seed_base": f"{SCHEDULE_BASE:08x}", "schedule_seed_derivation": "evaluation-trial-seed-v1",
              "schedules": {arm: disturbance.schedule(seed, HORIZON) for arm, seed in SCHEDULES.items()},
              "source_sha256": sources, "input_manifest_sha256": experiment.digest(output / "input/manifest.json")}
    experiment.write_json(output / "started.json", record)

    def run_case(item):
        case, arm = item
        seed = SCHEDULES[arm]
        prefix = f"{case['id']}.{arm}"
        common = ["model.tgm", case["scenario"], experiment.NIGHT_POLICY, "0x"+case["seed"], "--leaf-policy", "selective"]
        if seed is not None:
            common += ["--disturbance-seed", hex(seed)]
        command = ["bin/inspect", *common, "--population", "--ticks", str(HORIZON)]
        path = output / f"traces/{prefix}.world.gz"
        boundaries = disturbance.capture(command, path, output, "world", seed, HORIZON)
        verified = compare_sparse_prefix(path, output / f"input/{case['id']}.world.gz",
                                         disturbance.HORIZON if seed is None else disturbance.FIRST)
        experiment.write_json(output / f"analyses/{prefix}.boundaries.json", boundaries)
        data = analyze(path, boundaries, capacity, HORIZON, seed)
        commands = [command]
        for tick in CHECKPOINTS:
            replay = ["bin/replay", *common, "--ticks", str(tick)]
            destination = output / f"analyses/{prefix}.{tick}.replay.json"
            experiment.command_run(replay, destination, output, 300)
            last = experiment.read_json(destination)
            maintenance.check_identity(last, "selective", capacity)
            observed = data["milestones"][str(tick)]["population"]
            require(last["model_crc32"] == "dc5e849d" and all(last[k] == observed[k] for k in
                    ("hash", "tick", "living", "births", "deaths", "nodes")), "independent replay mismatch")
            require(last["seed_bank"] == observed["seeds"], "replay seed bank differs")
            if seed is not None:
                due = [b["event"] for b in boundaries if b["event"]["tick"] <= tick]
                require(last["disturbance_protocol"] == disturbance.PROTOCOL and last["disturbance_seed"] == f"{seed:08x}"
                        and last["disturbance_events"] == len(due)
                        and last["environmental_deaths"] == sum(len(e["killed"]) for e in due), "replay schedule mismatch")
            commands.append(replay)
        experiment.write_json(output / f"analyses/{prefix}.json", data)
        final = data["milestones"][str(HORIZON)]
        print(f"{capacity}/{prefix}: closing births={final['closing']['offspring_born']}, "
              f"families={len(final['population']['extant_families'])}, living={final['population']['living']}", flush=True)
        return {**{k: case[k] for k in ("id", "scenario", "seed")}, "arm": arm,
                "commands": commands, "verified_prefix_rows": verified, "analysis": data}

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        cases = list(pool.map(run_case, ((c, arm) for c in selected for arm in SCHEDULES)))
    experiment.write_json(output / "summary.json", summarize(cases))
    experiment.write_json(output / "cases.json", [{k: v for k, v in c.items() if k != "analysis"} for c in cases])
    groups = []
    for arm, seed in SCHEDULES.items():
        case = next(c for c in cases if c["arm"] == arm and c["scenario"] == "rainfed" and c["seed"] == maintenance.FRAME_SEED)
        days = {d["tick"]: d for d in case["analysis"]["daily"]}
        group = []
        for tick in (disturbance.FIRST, *CHECKPOINTS):
            name = f"{arm}-{tick//DAY}"
            frame = f"frames/{name}.rgb565"
            command = ["bin/replay", "model.tgm", "rainfed", experiment.NIGHT_POLICY, "0x"+maintenance.FRAME_SEED,
                       "--leaf-policy", "selective", "--ticks", str(tick), "--framebuffer", frame]
            if seed is not None:
                command += ["--disturbance-seed", hex(seed)]
            experiment.command_run(command, output / f"frames/{name}.json", output, 300)
            value = experiment.read_json(output / f"frames/{name}.json")
            raw = (output / frame).read_bytes()
            require(value["hash"] == days[tick]["hash"] and len(raw) == 115200
                    and value["framebuffer_crc32"] == f"{zlib.crc32(raw):08x}", "native frame mismatch")
            write_png(output / f"frames/{name}.png", 240, 240, rgb565be_to_rgb888(raw))
            group.append({"id": name, "tick": tick, "framebuffer": frame, "command": command, "result": value})
        groups.append(group)
    experiment.write_json(output / "frames.json", {"groups": groups, "sheet": contact_sheet(output, groups)})
    require(experiment.source_files() == sources, "source changed during collection")
    require(all(experiment.digest(output / name) == sha for name, sha in frozen.items()), "frozen input changed")
    record.update(status="complete", artifacts={str(p.relative_to(output)): experiment.digest(p)
                                               for p in output.rglob("*") if p.is_file()})
    experiment.write_json(output / "manifest.json", record)
    print(f"Complete: {output}; manifest sha256={experiment.digest(output / 'manifest.json')}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, choices=(1, 2, 4), default=4)
    args = parser.parse_args()
    collect(args.bundle, args.build, args.output, args.jobs)


if __name__ == "__main__":
    main()
