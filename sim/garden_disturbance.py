#!/usr/bin/env python3
"""Freeze 64-day paired recurring patch mortality trials, without training or firmware changes."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import shutil
import tempfile
import zlib

import garden_establishment as establishment
import garden_experiments as experiment
import garden_gap_experiment as gap
import garden_leaf_competition as competition
import garden_leaf_experiment as maintenance
from garden_gallery import contact_sheet, rgb565be_to_rgb888, write_png
from garden_resources import require

PROTOCOL = "patch-death-v1"
HORIZON = 245760
MAX_HORIZON = 737280
FIRST = 61440
LATE = 184320
SCHEDULE_SEEDS = (0x70617431, 0x70617432)
ARMS = {"control": None, "schedule-a": SCHEDULE_SEEDS[0], "schedule-b": SCHEDULE_SEEDS[1]}


def mix(value: int) -> int:
    value = ((value ^ (value >> 16)) * 0x7feb352d) & 0xffffffff
    value = ((value ^ (value >> 15)) * 0x846ca68b) & 0xffffffff
    return value ^ (value >> 16)


def schedule(seed: int | None, horizon: int = HORIZON) -> list[dict]:
    if seed is None:
        return []
    require(0 < seed <= 0xffffffff and 0 <= horizon <= MAX_HORIZON, "invalid disturbance schedule")
    result = []
    tick = FIRST
    while tick <= horizon:
        index = len(result)
        center = mix(seed ^ 0x6c6f6361 ^ index) % 30 - 1
        result.append({"protocol": PROTOCOL, "seed": f"{seed:08x}", "index": index, "tick": tick,
                       "first_column": max(0, center-1), "last_column": min(27, center+1)})
        tick += (1024 + mix(seed ^ 0x696e7476 ^ index) % 1025) * 15
    return result


def validate_boundary(before: dict, after: dict, event: dict) -> None:
    expected = schedule(int(event["seed"], 16), MAX_HORIZON)
    require(0 <= event["index"] < len(expected)
            and all(event[k] == v for k, v in expected[event["index"]].items()), "wrong fixed schedule")
    require(before["type"] == after["type"] and before["tick"] == after["tick"] == event["tick"]
            and before["hash"] == event["before_hash"] and after["hash"] == event["after_hash"],
            "invalid disturbance boundary")
    victims = [p for p in before["plants"] if not p["dead"]
               and event["first_column"] <= p["column"] <= event["last_column"]]
    require([p["id"] for p in victims] == event["killed"], "retargeted/missing victim")
    require(after["living"] == before["living"] - len(victims)
            and after["deaths"] == before["deaths"] + len(victims), "wrong death accounting")
    for key in before.keys() - {"hash", "living", "deaths", "plants", "seeds", "sites"}:
        require(before[key] == after[key], "unexpected environmental mutation: " + key)
    require([{k: v for k, v in s.items() if k != "blockers"} for s in before["seeds"]]
            == [{k: v for k, v in s.items() if k != "blockers"} for s in after["seeds"]],
            "seed bank changed during mortality")
    require(len(before["plants"]) == len(after["plants"]), "immediate reclamation")
    for old, new in zip(before["plants"], after["plants"], strict=True):
        if old["id"] not in event["killed"]:
            require(old == new, "survivor altered")
            continue
        if before["type"] == "seed-sites":
            require(new == {**old, "dead": True, "dispersal_columns": 0}, "seed-site victim altered")
        else:
            changes = {"dead": True, "energy": 0, "water": 0, "stress": 8, "flags": 1,
                       "tips": 0, "energy_income": 0, "water_income": 0,
                       "leaf": {**old["leaf"], "remainder": 0}, "active_leaves": new["active_leaves"]}
            require(new == {**old, **changes}, "incorrect ordinary death semantics")
    if before["type"] == "world":
        require(all(sum(p[key] for p in victims) == event[key] for key in ("energy", "water", "nodes")),
                "unreconciled environmental resource loss")
    else:
        require(all(a[1] == b[1] for a, b in zip(after["sites"], before["sites"], strict=True)),
                "soil moisture changed")
        competition.spatial_snapshot(after)
    require(bool(victims) or before == after, "nonempty change on empty hit")


def capture(command: list[str], path: Path, root: Path, kind: str,
            seed: int | None, horizon: int) -> list[dict]:
    boundaries = []
    previous = None
    planned = schedule(seed, horizon)
    with tempfile.TemporaryDirectory(prefix="garden-disturbance-") as temp:
        raw = Path(temp) / "raw.jsonl"
        experiment.command_run(command, raw, root, 300)
        with raw.open() as incoming, path.open("xb") as output:
            with gzip.GzipFile(fileobj=output, filename="", mode="wb", mtime=0) as packed:
                iterator = iter(incoming)
                for line in iterator:
                    row = json.loads(line)
                    if row["type"] in ("bid", "leaf-bid"):
                        require(kind == "world", "bid in seed census")
                        continue
                    if row["type"] == "disturbance":
                        require(len(boundaries) < len(planned)
                                and all(row[k] == v for k, v in planned[len(boundaries)].items()),
                                "wrong/missing/repeated event")
                        after = json.loads(next(iterator))
                        require(previous is not None and after["type"] == kind, "missing event sample")
                        validate_boundary(previous, after, row)
                        boundaries.append({"event": row, "before": previous, "after": after})
                        # Ordinary pre-event row stays in the normalized budget/seed ledger.
                        continue
                    require(row["type"] == kind, "unexpected census record")
                    packed.write(line.encode())
                    previous = row
    require(len(boundaries) == len(planned), "truncated event schedule")
    return boundaries


def analyze(world_path: Path, site_path: Path, boundaries: dict, capacity: int,
            horizon: int = HORIZON, late_cycles: int = 16,
            schedule_seed: int | None = None) -> dict:
    expected = schedule(schedule_seed, horizon)
    require(len(boundaries["world"]) == len(expected) and all(
        all(b["event"][k] == v for k, v in e.items())
        for b, e in zip(boundaries["world"], expected, strict=True)), "missing/wrong planned event")
    require([b["event"] for b in boundaries["world"]] == [b["event"] for b in boundaries["sites"]],
            "world/site interventions differ")
    for kind in ("world", "sites"):
        for b in boundaries[kind]:
            validate_boundary(b["before"], b["after"], b["event"])
    for a, b in zip(boundaries["world"], boundaries["sites"], strict=True):
        require(a["after"]["hash"] == b["after"]["hash"], "post-event hash mismatch")
    world_events = {b["event"]["tick"]: b for b in boundaries["world"]}
    require(len(world_events) == len(boundaries["world"]), "duplicate boundary")
    world, references = competition.world_analysis(world_path, "selective", capacity, horizon,
        horizon-late_cycles*experiment.CYCLE_TICKS, disturbances=world_events)
    site_events = {b["event"]["tick"]: b for b in boundaries["sites"]}
    spatial = {window: Counter() for window in ("whole", "late")}

    def spatial_rows(stream):
        for line in stream:
            row = json.loads(line)
            values = competition.spatial_snapshot(site_events.get(row["tick"], {}).get("after", row))
            if row["tick"]:
                spatial["whole"].update(values)
                if row["tick"] > horizon-late_cycles*experiment.CYCLE_TICKS:
                    spatial["late"].update(values)
            yield line

    with gzip.open(site_path, "rt") as stream:
        seeds = establishment.analyze_stream(spatial_rows(stream), references, late_cycles, capacity)
    lineages = {p["id"]: p for p in world["lineages"]}
    for seed in seeds["seeds"]:
        if seed["outcome"] == "germinated":
            child = lineages[seed["child_id"]]
            require(child["parent"] == seed["parent"] and child["birth_tick"] == seed["end_tick"],
                    "seed/child mismatch")
    require(world["final"]["deaths"] == sum(p["death_tick"] is not None for p in lineages.values()),
            "unreconciled final deaths")
    events = []
    for i, boundary in enumerate(boundaries["world"]):
        event = boundary["event"]
        end = boundaries["world"][i+1]["event"]["tick"] if i+1 < len(boundaries["world"]) else horizon+1
        victims = [lineages[identity] for identity in event["killed"]]
        local = {p["id"] for p in lineages.values() if event["tick"] < p["birth_tick"] < end
                 and any(abs(p["column"]-v["column"]) < 3 for v in victims)}
        events.append({**event, "followup_end_exclusive": end,
                       "local_births_before_next_event": len(local),
                       "local_lifetimes": competition.lifetime_cohort(lineages, min(horizon, end-1),
                                                                      event["tick"], local),
                       "reclamation_delays": [v["reclaimed_tick"]-event["tick"]
                                              if "reclaimed_tick" in v else None for v in victims]})
    cohorts = {"post_establishment": competition.lifetime_cohort(lineages, horizon, FIRST),
               "closing": competition.lifetime_cohort(lineages, horizon, horizon-late_cycles*3840)}
    return {"world": world, "seeds": seeds, "spatial": spatial, "events": events, "cohorts": cohorts}


def summarize(cases: list[dict]) -> dict:
    result = {}
    for arm in ARMS:
        group = [c for c in cases if c["arm"] == arm]
        totals = Counter()
        cohorts = {key: Counter() for key in ("post_establishment", "closing")}
        late_exposure, spatial = Counter(), Counter()
        for case in group:
            data = case["analysis"]
            world = data["world"]
            final = world["final"]
            records = world["lineages"]
            deaths = [p for p in records if p["death_tick"] is not None and p["death_tick"] > FIRST]
            events = data["events"]
            totals.update({"final_living": final["living"], "final_seeds": len(final["seeds"]),
                           "final_nodes": final["nodes"], "final_empty_worlds": int(final["living"] == 0),
                           "final_extinct_worlds": int(final["living"] == 0 and not final["seeds"]),
                           "post_establishment_natural_deaths": sum(not p.get("environmental_death") for p in deaths),
                           "environmental_deaths": sum(len(e["killed"]) for e in events),
                           "events": len(events), "hit_events": sum(bool(e["killed"]) for e in events),
                           "hits_with_local_births": sum(e["local_births_before_next_event"] > 0 for e in events),
                           "hits_with_local_day_survivor": sum(e["local_lifetimes"]["cycle_survivors"] > 0 for e in events),
                           "worlds_recovering_at_least_twice": int(sum(e["local_lifetimes"]["cycle_survivors"] > 0 for e in events) >= 2),
                           "worlds_with_closing_births": int(data["cohorts"]["closing"]["offspring_born"] > 0),
                           "checked_live_steps": world["windows"]["whole"]["budget_checked_live_steps"],
                           "natural_terminal_steps": world["windows"]["whole"]["terminal_steps"],
                           "seed_records": len(data["seeds"]["seeds"]),
                           "checkpoints_verified": data["seeds"]["checkpoints_verified"]})
            for key in cohorts:
                cohorts[key].update(data["cohorts"][key])
            late_exposure.update(world["windows"]["late"])
            spatial.update(data["spatial"]["late"])
        result[arm] = {"worlds": len(group), "totals": totals, "cohorts": cohorts,
                       "late_exposure": late_exposure, "late_spatial": spatial}
    return result


def collect(bundle: Path, build: Path, output: Path, jobs: int) -> None:
    bundle, build, output = bundle.resolve(), build.resolve(), output.resolve()
    manifest = experiment.read_json(bundle / "manifest.json")
    require(manifest.get("status") == "complete" and manifest.get("kind") == "garden-maintenance-competition",
            "wrong input census")
    capacity = manifest["node_capacity"]
    require(capacity in (256, 512), "wrong capacity")
    require(not output.is_relative_to(experiment.ROOT) or output.is_relative_to(experiment.ROOT / "artifacts"),
            "output must be outside source or under artifacts/")
    output.mkdir(parents=True, exist_ok=False)
    for folder in ("input", "bin", "traces", "analyses", "frames"):
        (output / folder).mkdir()
    sources = experiment.source_files()
    experiment.snapshot_sources(output, sources)
    shutil.copy2(bundle / "manifest.json", output / "input/manifest.json")
    selected = [c for c in experiment.read_json(establishment.verified(bundle, manifest, "cases.json"))
                if c["leaf_policy"] == "selective"]
    expected = {(s, seed) for s in experiment.SCENARIOS for seed in experiment.trial_seeds(0x6d617463, 8)}
    require(len(selected) == 16 and {(c["scenario"], c["seed"]) for c in selected} == expected, "incomplete panel")
    for case in selected:
        require(case["growth_policy"] == experiment.NIGHT_POLICY, "wrong policy")
        for suffix in ("world", "sites"):
            name = f"traces/{case['id']}.{suffix}.jsonl.gz"
            shutil.copy2(establishment.verified(bundle, manifest, name), output / f"input/{case['id']}.{suffix}.gz")
    shutil.copy2(establishment.verified(bundle, manifest, "model.tgm"), output / "model.tgm")
    require(experiment.digest(output / "model.tgm") == maintenance.MODEL_SHA, "wrong model")
    experiment.write_json(output / "input/cases.json", selected)
    for tool in ("inspect", "replay"):
        shutil.copy2(build / f"toy-factory-garden-{tool}", output / f"bin/{tool}")
    shutil.copy2(build / "CMakeCache.txt", output / "build-cache.txt")
    frozen = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
    record = {"schema_version": 1, "kind": "garden-patch-disturbance", "protocol": PROTOCOL,
              "node_capacity": capacity, "horizon": HORIZON, "late_start": LATE,
              "schedules": {arm: schedule(seed) for arm, seed in ARMS.items()}, "source_sha256": sources,
              "input_manifest_sha256": experiment.digest(output / "input/manifest.json")}
    experiment.write_json(output / "started.json", record)

    def run_case(item):
        case, arm = item
        seed = ARMS[arm]
        prefix = f"{case['id']}.{arm}"
        base = ["bin/inspect", "model.tgm", case["scenario"], experiment.NIGHT_POLICY, "0x"+case["seed"],
                "--leaf-policy", "selective", "--ticks", str(HORIZON)]
        if seed is not None:
            base += ["--disturbance-seed", hex(seed)]
        boundaries, commands = {}, []
        verified = 0
        for suffix, flag, kind in (("world", "--ecology", "world"), ("sites", "--seed-sites", "seed-sites")):
            path = output / f"traces/{prefix}.{suffix}.gz"
            boundaries[suffix] = capture(base+[flag], path, output, kind, seed, HORIZON)
            commands.append(base+[flag])
            verified += gap.compare_prefix(path, output / f"input/{case['id']}.{suffix}.gz",
                                           FIRST if seed is not None else gap.HORIZON)
        experiment.write_json(output / f"analyses/{prefix}.boundaries.json", boundaries)
        data = analyze(output / f"traces/{prefix}.world.gz", output / f"traces/{prefix}.sites.gz", boundaries,
                       capacity, schedule_seed=seed)
        replay = ["bin/replay", *base[1:]]
        destination = output / f"analyses/{prefix}.replay.json"
        experiment.command_run(replay, destination, output, 300)
        last = experiment.read_json(destination)
        maintenance.check_identity(last, "selective", capacity)
        require(last["hash"] == data["world"]["final"]["hash"] and last["model_crc32"] == "dc5e849d",
                "independent final replay mismatch")
        if seed is not None:
            require(last["disturbance_seed"] == f"{seed:08x}" and last["disturbance_protocol"] == PROTOCOL
                    and last["disturbance_events"] == len(data["events"])
                    and last["environmental_deaths"] == sum(len(e["killed"]) for e in data["events"]),
                    "replay schedule differs")
        experiment.write_json(output / f"analyses/{prefix}.json", data)
        print(f"{capacity}/{prefix} {case['scenario']}/{case['seed']}: "
              f"births after day 16={data['cohorts']['post_establishment']['offspring_born']}, "
              f"final living={last['living']}", flush=True)
        return {**{k: case[k] for k in ("id", "scenario", "seed")}, "arm": arm,
                "commands": commands+[replay], "verified_prefix_samples": verified, "analysis": data}

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        cases = list(pool.map(run_case, ((c, arm) for c in selected for arm in ARMS)))
    experiment.write_json(output / "summary.json", summarize(cases))
    experiment.write_json(output / "cases.json", [{k: v for k, v in c.items() if k != "analysis"} for c in cases])
    frames = []
    for arm, seed in ARMS.items():
        case = next(c for c in cases if c["arm"] == arm and c["scenario"] == "rainfed" and c["seed"] == maintenance.FRAME_SEED)
        points = gap.checkpoints(output / f"traces/{case['id']}.{arm}.world.gz", {FIRST, FIRST+3840, 122880, HORIZON})
        boundaries = experiment.read_json(output / f"analyses/{case['id']}.{arm}.boundaries.json")
        after = {b["event"]["tick"]: b["after"] for b in boundaries["world"]}
        group = []
        for index, tick in enumerate((FIRST, FIRST+3840, 122880, HORIZON)):
            name = f"{arm}-{index}"
            frame = f"frames/{name}.rgb565"
            command = ["bin/replay", "model.tgm", "rainfed", experiment.NIGHT_POLICY, "0x"+maintenance.FRAME_SEED,
                       "--leaf-policy", "selective", "--ticks", str(tick), "--framebuffer", frame]
            if seed is not None:
                command += ["--disturbance-seed", hex(seed)]
            experiment.command_run(command, output / f"frames/{name}.json", output, 300)
            value = experiment.read_json(output / f"frames/{name}.json")
            raw = (output / frame).read_bytes()
            require(value["hash"] == after.get(tick, points[tick])["hash"] and len(raw) == 115200
                    and value["framebuffer_crc32"] == f"{zlib.crc32(raw):08x}", "native frame mismatch")
            write_png(output / f"frames/{name}.png", 240, 240, rgb565be_to_rgb888(raw))
            group.append({"id": name, "tick": tick, "framebuffer": frame, "command": command, "result": value})
        frames.append(group)
    experiment.write_json(output / "frames.json", {"groups": frames, "sheet": contact_sheet(output, frames)})
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
    parser.add_argument("--jobs", type=int, choices=(1, 2, 4), default=2)
    args = parser.parse_args()
    collect(args.bundle, args.build, args.output, args.jobs)


if __name__ == "__main__":
    main()
