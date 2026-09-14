#!/usr/bin/env python3
"""Frozen, late-activation wet-root bootstrap A/B; never training or firmware."""
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

import garden_seedling_water as water
from garden_resources import ENERGY_COST, WATER_COST, require
from garden_gallery import contact_sheet, rgb565be_to_rgb888, write_png

trial, experiment = water.trial, water.trial.experiment
DAY, START, END = water.DAY, water.START, water.END
RULE = "wet-root-bootstrap-v1"


def expected_override(bid, plant):
    """Independent reference for a bounded bid change, not a simulation."""
    o = bid["root_bootstrap"]
    require(o["rule"] == RULE and o["after"] == START and bid["action"] == bid["original_action"],
            "unknown rule or changed action")
    order, priority = list(o["original_order"]), bid["original_priority"]
    eligible = (plant["generation"] > 0 and 1 <= o["age"] <= 256 and
        bid["tick"] - (o["age"] - 1) * 15 > START and o["roots"] == 2 and
        bid["tissue"] == 1 and bid["depth"] == 1 and 144 <= bid["y"] < 152 and
        bid["original_action"] == 1 and bid["water"] >= WATER_COST[plant["species"]] and
        bid["energy"] >= ENERGY_COST[plant["species"]] - (plant["vigor"] > 0))
    if eligible:
        require(sorted(order) == list(range(len(bid["candidates"]))), "invalid base permutation")
        candidates = [i for i in order if bid["candidates"][i]["flags"] & 2 and
            bid["candidates"][i]["y"] >= 152 and
            bid["candidates"][i]["moisture"] >= WATER_COST[plant["species"]] and
            bid["candidates"][i]["moisture"] > o["tip_moisture"]]
        if candidates:
            index = max(candidates, key=lambda i: bid["candidates"][i]["moisture"])
            order.remove(index)
            order.insert(0, index)
            priority = 32767
    require(order == o["order"] and priority == bid["priority"], "native override disagrees with reference")
    return order != o["original_order"] or priority != bid["original_priority"]


def capture(root, baseline, key, arm):
    seed, side, capacity = key.split(".")
    name = f"{key}.{arm}"
    args = ["model.tgm", "rainfed-crowded", trial.bank.POLICIES[side], "0x" + seed,
        "--leaf-policy", "selective", "--disturbance-seed", str(trial.bank.SCHEDULE)]
    if arm == "on":
        args += ["--root-bootstrap-after", str(START)]
    command = [f"bin/{capacity}-inspect", *args, "--ecology", "--ticks", str(END)]
    bounds, pending, overrides = [], {}, []
    old_bounds = {b["event"]["tick"]: b for b in experiment.read_json(baseline / f"analyses/{key}.on.boundaries.json")}
    counts = Counter()
    previous, last_row, first_override, first_hash_difference = {}, None, None, None
    last, before_override = -15, 0
    planned = trial.bank.recruitment.diversity.disturbance.schedule(trial.bank.SCHEDULE, END)
    world_path = root / f"traces/{name}.world.gz"
    with tempfile.TemporaryDirectory(prefix="garden-root-bootstrap-") as temp:
        raw = Path(temp) / "native.jsonl"
        experiment.command_run(command, raw, root, 300)
        with raw.open() as stream, gzip.open(world_path, "xt") as output, gzip.open(
                baseline / f"traces/{key}.on.world.gz", "rt") as control:
            rows = iter(stream)
            for line in rows:
                row = json.loads(line)
                kind, tick = row["type"], row["tick"]
                if kind == "leaf-bid":
                    continue
                if kind == "bid":
                    require(tick == last + 15 and row["action"] == row["original_action"], "invalid bid step/action")
                    if tick <= START:
                        require(row["priority"] == row["original_priority"] and (arm == "off" or
                            row["root_bootstrap"]["order"] == row["root_bootstrap"]["original_order"]),
                            "probe changed a pre-window bid")
                    else:
                        pending.setdefault(row["id"], []).append(row)
                    continue
                if kind == "disturbance":
                    after = json.loads(next(rows))
                    require(all(row[k] == v for k, v in planned[len(bounds)].items()), "wrong patch schedule")
                    trial.bank.recruitment.diversity.disturbance.validate_boundary(last_row, after, row)
                    if arm == "off" or tick <= START:
                        expected = old_bounds[tick]
                        comparable = lambda r: {k: v for k, v in r.items() if not k.startswith("root_bootstrap_")}
                        require(comparable(after) == expected["after"] and row == expected["event"], "control patch differs")
                    bounds.append({"event": row, "before": last_row, "after": after})
                    previous = {p["id"]: p for p in after["plants"]}
                    continue
                require(kind == "world" and tick == last + 15 and tick <= END, "missing world row")
                trial.bank.competition.maintenance.check_identity(row, "selective", 512,
                    growth_policy=trial.bank.recruitment.policy.RESERVE if side == "reserve" else None,
                    seed_capacity=int(capacity), seed_reserve=trial.RULE,
                    root_bootstrap_after=START if arm == "on" else None)
                old_world = json.loads(next(control))
                current = {p["id"]: p for p in row["plants"]}
                for i, p in current.items():
                    bids = pending.pop(i, [])
                    if tick <= START:
                        continue
                    old = previous.get(i)
                    require(p["agent"]["decisions"] - (old["agent"]["decisions"] if old else 0) == bool(bids),
                            "missing/extra winning decision")
                    if not bids:
                        continue
                    winner = max(bids, key=lambda b: b["priority"])
                    require(all(winner[k] == p["agent"]["last_" + k] for k in
                                ("priority", "action", "tissue", "x", "y")), "wrong committed winner")
                    changed = {}
                    for b in bids:
                        if arm == "on":
                            changed[b["tip_index"]] = expected_override(b, p)
                            counts["audited_bids"] += 1
                            counts["changed_offered_bids"] += changed[b["tip_index"]]
                        else:
                            require(b["priority"] == b["original_priority"], "off probe changed priority")
                    if arm == "on" and changed[winner["tip_index"]]:
                        require(not p["dead"] and p["roots"] == 3 and (old is None or old["roots"] == 2),
                                "override did not append first deeper root")
                        require(i not in {v["id"] for v in overrides}, "repeated lineage override")
                        original_winner = max(bids, key=lambda b: b["original_priority"])
                        event = {"tick": tick, "id": i, "winner": winner, "original_winner": original_winner,
                                 "plant_after": p}
                        overrides.append(event)
                        first_override = first_override or event
                require(not pending, "unconsumed bids")
                comparable = {k: v for k, v in row.items() if not k.startswith("root_bootstrap_")}
                if arm == "off" or first_override is None:
                    require(comparable == old_world, "control/pre-override world differs")
                    before_override += 1
                if row["hash"] != old_world["hash"] and first_hash_difference is None:
                    require(first_override is not None and tick >= first_override["tick"], "early unexplained hash difference")
                    first_hash_difference = tick
                output.write(line)
                last_row, last, previous = row, tick, current
            require(next(control, None) is None and last == END and len(bounds) == len(planned), "incomplete capture")
    experiment.write_json(root / f"analyses/{name}.boundaries.json", bounds)
    world, references = trial.bank.competition.world_analysis(world_path, "selective", 512, END, START,
        disturbances={b["event"]["tick"]: b for b in bounds},
        growth_policy=trial.bank.recruitment.policy.RESERVE if side == "reserve" else None,
        seed_capacity=int(capacity), seed_reserve=trial.RULE, root_bootstrap_after=START if arm == "on" else None)
    with gzip.open(world_path, "rt") as stream:
        seedlings, histories = water.analyze_stream(stream, bounds, world, key, "on",
            root_bootstrap_after=START if arm == "on" else None)
    with gzip.open(root / f"analyses/{name}.seedlings.gz", "xt") as stream:
        json.dump(histories, stream, separators=(",", ":"))
    result = {"key": key, "arm": arm, "command": command, "world": world,
        "lifetimes": trial.turnover.summary_lifetimes(world["lineages"]), "seedlings": seedlings,
        "audit": dict(counts) | {"matched_rows_before_override": before_override,
            "first_override_tick": first_override["tick"] if first_override else None,
            "first_hash_difference_tick": first_hash_difference, "overrides": overrides}}
    if arm == "off":
        old = experiment.read_json(baseline / f"analyses/{key}.on.json")
        require(world == old["world"] and result["lifetimes"] == old["lifetimes"], "fresh control analysis differs")
    else:
        frame = root / f"frames/{key}.on.rgb565"
        frame_command = [f"bin/{capacity}-replay", *args, "--ticks", str(END), "--framebuffer", str(frame)]
        meta_path = root / f"frames/{key}.on.json"
        experiment.command_run(frame_command, meta_path, root, 300)
        meta = experiment.read_json(meta_path)
        require(all(meta[k] == world["final"][k] for k in ("tick", "hash", "living", "nodes", "births", "deaths",
            "sun_phase", "rain_rate", "rain_deposited", "rain_runoff")) and
            meta["model_crc32"] == "dc5e849d" and meta["seed"] == seed and
            meta["policy"] == trial.bank.POLICIES[side] and meta["node_capacity"] == 512 and
            meta.get("seed_capacity", 8) == int(capacity) and meta["seed_reserve_rule"] == trial.RULE,
            "frame replay identity/state differs")
        require(meta["hash"] == world["final"]["hash"] and meta["root_bootstrap_rule"] == RULE and
                meta["root_bootstrap_after"] == START and len(frame.read_bytes()) == 115200 and
                meta["framebuffer_crc32"] == f"{zlib.crc32(frame.read_bytes()):08x}", "native frame mismatch")
        write_png(root / f"frames/{key}.on.png", 240, 240, rgb565be_to_rgb888(frame.read_bytes()))
        result["frame_command"] = frame_command
    experiment.write_json(root / f"analyses/{name}.json", result)
    print(name, "births", seedlings["cohort"]["born"], seedlings["outcomes"],
          "overrides", len(overrides), "final alive", world["final"]["living"], flush=True)
    return result


def compact(result):
    return {"key": result["key"], "arm": result["arm"], "lifetimes": result["lifetimes"],
        "windows": result["world"]["windows"],
        "final": {k: result["world"]["final"][k] for k in ("hash", "living", "nodes", "births", "deaths")},
        "first_day_outcomes": result["seedlings"]["outcomes"],
        "first_day_water_failures": result["seedlings"]["water_failures"],
        "closing_deaths": result["seedlings"]["closing_natural_deaths"],
        "audit": {k: v for k, v in result["audit"].items() if k != "overrides"} |
                 {"committed_overrides": len(result["audit"]["overrides"])} }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT / "artifacts/garden-seed-reserve-v3")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    baseline, root = args.baseline.resolve(), args.output.resolve()
    require(experiment.digest(baseline / "manifest.json") == water.BASELINE_SHA, "wrong baseline")
    require(not root.exists() and root.is_relative_to(experiment.ROOT / "artifacts") and
            not root.is_relative_to(baseline), "unsafe/existing output")
    m = experiment.read_json(baseline / "manifest.json")
    root.mkdir(parents=True)
    for name in ("bin", "analyses", "traces", "frames", "input"):
        (root / name).mkdir()
    sources = experiment.source_files()
    experiment.snapshot_sources(root, sources)
    inputs = {}
    for key in trial.KEYS:
        for name in (f"traces/{key}.on.world.gz", f"analyses/{key}.on.json",
                     f"analyses/{key}.on.boundaries.json", f"frames/{key}.on.192.rgb565"):
            p = trial.bank.establishment.verified(baseline, m, name)
            inputs[name] = experiment.digest(p)
    model = trial.bank.establishment.verified(baseline, m, "model.tgm")
    require(experiment.digest(model) == trial.bank.competition.maintenance.MODEL_SHA, "wrong frozen model")
    inputs["model.tgm"] = experiment.digest(model)
    shutil.copy2(model, root / "model.tgm")
    shutil.copy2(experiment.ROOT / "benchmarks/garden-longevity/root-bootstrap-protocol.md", root / "protocol.md")
    for capacity in (8, 16):
        build = experiment.ROOT / f"artifacts/seed-reserve-build-on-{capacity}"
        cache = (build / "CMakeCache.txt").read_text()
        for flag, value in (("WIDE_DISPERSAL", True), ("WATER_HEADROOM", True), ("COMBINED_EXPERIMENT", True),
            ("LARGE_POOL", True), ("LEAF_MAINTENANCE", True), ("BOTTOM_DRAINAGE", False),
            ("LARGE_SEED_BANK", capacity == 16), ("SEED_RESERVE", True)):
            require(f"TOY_FACTORY_GARDEN_{flag}:BOOL={'ON' if value else 'OFF'}" in cache, "wrong native config")
        require("TOY_FACTORY_SIMULATOR_SANITIZERS:BOOL=ON" in cache, "UBSan required")
        shutil.copy2(build / "CMakeCache.txt", root / f"input/{capacity}.cache.txt")
        for tool in ("inspect", "replay", "root-bootstrap-test"):
            shutil.copy2(build / f"toy-factory-garden-{tool}", root / f"bin/{capacity}-{tool}")
        experiment.command_run([f"bin/{capacity}-root-bootstrap-test"], root / f"input/{capacity}.test.txt", root, 60)
    observations = experiment.ROOT / "artifacts/garden-root-bids/manifest.json"
    require(experiment.read_json(observations)["status"] == "complete", "missing completed bid replay")
    started = {"kind": "garden-root-bootstrap", "input_manifest_sha256": water.BASELINE_SHA,
               "observational_manifest_sha256": experiment.digest(observations),
               "source_sha256": sources, "inputs": inputs, "expected_runs": 16}
    experiment.write_json(root / "started.json", started)
    frozen = {str(p.relative_to(root)): experiment.digest(p) for p in root.rglob("*") if p.is_file()}
    try:
        jobs = [(key, arm) for key in trial.KEYS for arm in ("off", "on")]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda job: capture(root, baseline, *job), jobs))
        experiment.write_json(root / "summary.json", {"runs": [compact(r) for r in results]})
        groups = []
        for key in trial.KEYS:
            old = baseline / f"frames/{key}.on.192.rgb565"
            shutil.copy2(old, root / f"frames/{key}.off.rgb565")
            groups.append([{"id": f"{key}.{arm}", "framebuffer": f"frames/{key}.{arm}.rgb565"}
                           for arm in ("off", "on")])
        experiment.write_json(root / "frames.json", contact_sheet(root, groups))
        (root / "contact-sheet.png").rename(root / "contact-192.png")
        for name, digest in inputs.items():
            require(experiment.digest(baseline / name) == digest, "frozen input changed")
        require(experiment.source_files() == sources, "source changed during collection")
        require(all(experiment.digest(root / name) == value for name, value in frozen.items()),
                "frozen source/binary/model input changed")
        experiment.write_json(root / "manifest.json", started | {"status": "complete", "artifacts": {
            str(p.relative_to(root)): experiment.digest(p) for p in root.rglob("*") if p.is_file()}})
    except BaseException as error:
        experiment.write_json(root / "failure.json", {"error": str(error)})
        raise


if __name__ == "__main__":
    main()
