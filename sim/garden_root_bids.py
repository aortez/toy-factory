#!/usr/bin/env python3
"""Replay frozen worlds unchanged and retain every closing seedling's tip bids."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import time

import garden_seedling_water as water

trial, require = water.trial, water.require
experiment = trial.experiment
# Target, both adverse baseline banks, and the rooted-failure reserve case.
KEYS = ("c7f54e18.reserve.16", "b61837dc.neural.8", "b61837dc.neural.16", "b61837dc.reserve.16")


def bid_group(bids, plant, old, tick):
    decisions = plant["agent"]["decisions"] - (old["agent"]["decisions"] if old else 0)
    require(decisions == bool(bids), "missing or invented decision bids")
    if not bids:
        return None
    require(len({b["tip_index"] for b in bids}) == len(bids), "duplicate tip bid")
    winner = max(bids, key=lambda b: b["priority"])
    require(all(winner[k] == plant["agent"]["last_" + k] for k in
                ("priority", "action", "tissue", "x", "y")), "wrong winning bid")
    for b in bids:
        require(b["tick"] == tick and b["id"] == plant["id"] and
                b["priority"] == b["original_priority"] and b["action"] == b["original_action"],
                "observational replay changed a bid")
    roots = [b for b in bids if b["tissue"] == 1]
    available = [b for b in roots if any(c["flags"] & 2 for c in b["candidates"])]
    wet = [b for b in available if any(c["flags"] & 2 and c["moisture"] >= 5 for c in b["candidates"])]
    extending = [b for b in wet if b["action"] == 1]
    return {"tick": tick, "id": plant["id"], "winner": winner,
        "roots": roots, "wet_available_roots": len(wet),
        "wet_extending_roots": len(extending),
        "wet_roots_energy_vetoed": sum(b.get("probe_original_action") == 1 and
            b["sun_phase"] < 128 and b.get("reserve", {}).get("allowed") is False for b in wet),
        "shoot_beats_wet_root_extension": winner["tissue"] == 0 and winner["action"] == 1 and bool(extending)}


def replay(root, baseline, key):
    seed, side, capacity = key.split(".")
    ref = experiment.read_json(baseline / f"analyses/{key}.on.json")
    bounds = experiment.read_json(baseline / f"analyses/{key}.on.boundaries.json")
    by_tick = {b["event"]["tick"]: b for b in bounds}
    selected = {p["id"]: p for p in ref["world"]["lineages"] if p["parent"] and
                water.START < p["birth_tick"] <= water.END}
    command = [f"bin/on-{capacity}-inspect", "model.tgm", "rainfed-crowded", trial.bank.POLICIES[side],
        "0x" + seed, "--ecology", "--ticks", str(water.END), "--leaf-policy", "selective",
        "--disturbance-seed", str(trial.bank.SCHEDULE)]
    start = time.monotonic()
    groups, pending, previous = {i: [] for i in selected}, {}, {}
    last, checked, event_count, expect_after = -15, 0, 0, None
    with (root / f"{key}.stderr").open("xb") as errors, gzip.open(root / f"{key}.bids.gz", "xt") as output:
        with subprocess.Popen(command, cwd=root, stdout=subprocess.PIPE, stderr=errors, text=True) as process:
            try:
                with gzip.open(baseline / f"traces/{key}.on.world.gz", "rt") as control:
                    for line in process.stdout:
                        row = json.loads(line)
                        kind, tick = row["type"], row["tick"]
                        if kind in ("bid", "leaf-bid"):
                            if kind == "bid" and row["id"] in selected:
                                r = selected[row["id"]]
                                if r["birth_tick"] <= tick <= r["birth_tick"] + water.DAY:
                                    require(tick == last + 15, "bid outside next ecology step")
                                    pending.setdefault(row["id"], []).append(row)
                                    output.write(line)
                            continue
                        if kind == "disturbance":
                            require(expect_after is None and row == by_tick[tick]["event"], "event differs")
                            expect_after = by_tick[tick]["after"]
                            event_count += 1
                            continue
                        require(kind == "world", "unexpected native record")
                        if expect_after is not None:
                            require(row == expect_after, "post-patch replay differs")
                            previous = {p["id"]: p for p in row["plants"]}
                            expect_after = None
                            continue
                        require(tick == last + 15 and row == json.loads(next(control)), "world replay differs")
                        current = {p["id"]: p for p in row["plants"]}
                        for i, p in current.items():
                            if i not in selected or tick > selected[i]["birth_tick"] + water.DAY:
                                continue
                            result = bid_group(pending.pop(i, []), p, previous.get(i), tick)
                            if result is not None:
                                groups[i].append(result)
                        require(not pending, "unconsumed bids")
                        last, previous = tick, current
                        checked += 1
                    require(next(control, None) is None, "replay ended early")
                require(process.wait(timeout=30) == 0, "native inspector failed")
            except BaseException:
                process.kill()
                process.wait()
                raise
    require(last == water.END and event_count == len(bounds) and expect_after is None, "incomplete replay")
    seedlings = []
    for i, r in selected.items():
        values = Counter()
        for g in groups[i]:
            values.update({k: int(g[k]) for k in ("wet_available_roots", "wet_extending_roots",
                "wet_roots_energy_vetoed", "shoot_beats_wet_root_extension")})
        seedlings.append({"lineage": r, "outcome": water.outcome(r, water.END),
            "decisions": len(groups[i]), "counts": dict(values), "groups": groups[i]})
    result = {"key": key, "command": command, "elapsed_seconds": time.monotonic() - start,
        "matched_world_rows": checked, "matched_patch_boundaries": event_count, "seedlings": seedlings}
    experiment.write_json(root / f"{key}.json", result)
    print(key, "matched", checked, "rows;", len(selected), "seedlings;",
          round(result["elapsed_seconds"], 1), "s", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT / "artifacts/garden-seed-reserve-v3")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    baseline, root = args.baseline.resolve(), args.output.resolve()
    require(experiment.digest(baseline / "manifest.json") == water.BASELINE_SHA, "wrong input")
    require(not root.exists() and root.is_relative_to(experiment.ROOT / "artifacts") and
            not root.is_relative_to(baseline), "existing/unsafe output")
    manifest = experiment.read_json(baseline / "manifest.json")
    root.mkdir(parents=True)
    (root / "bin").mkdir()
    sources = experiment.source_files()
    experiment.snapshot_sources(root, sources)
    inputs = {}
    names = ["model.tgm"] + [f"bin/on-{n}-inspect" for n in (8, 16)]
    names += [name for key in KEYS for name in (f"traces/{key}.on.world.gz",
             f"analyses/{key}.on.json", f"analyses/{key}.on.boundaries.json")]
    for name in names:
        p = trial.bank.establishment.verified(baseline, manifest, name)
        inputs[name] = experiment.digest(p)
        if name in ("model.tgm", "bin/on-8-inspect", "bin/on-16-inspect"):
            shutil.copy2(p, root / name)
    started = {"kind": "garden-root-bids", "input_manifest_sha256": water.BASELINE_SHA,
               "source_sha256": sources, "inputs": inputs}
    experiment.write_json(root / "started.json", started)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda key: replay(root, baseline, key), KEYS))
        experiment.write_json(root / "summary.json", {"runs": results})
        require(experiment.source_files() == sources, "source changed during capture")
        experiment.write_json(root / "manifest.json", started | {"status": "complete",
            "artifacts": {str(p.relative_to(root)): experiment.digest(p) for p in root.rglob("*") if p.is_file()}})
    except BaseException as error:
        experiment.write_json(root / "failure.json", {"error": str(error)})
        raise


if __name__ == "__main__":
    main()
