#!/usr/bin/env python3
"""Check spatial counterfactuals, censored lifetimes, and native census binding."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import subprocess
import tempfile

import garden_leaf_competition as audit
from garden_experiments import report_trials, trial_seeds


def rejects(call):
    try:
        call()
    except RuntimeError:
        return
    raise AssertionError("invalid competition census accepted")


def synthetic():
    def plant(identity, parent, birth, death=None):
        return {"id": identity, "parent": parent, "birth_tick": birth, "death_tick": death}

    records = {p["id"]: p for p in [plant(1, 0, 0), plant(2, 1, 15), plant(3, 2, 3855),
                                   plant(4, 1, 30, 3870), plant(5, 1, 60, 3915),
                                   plant(6, 1, 7680), plant(7, 1, 7695, 7710)]}
    result = audit.lifetime_cohort(records, 11520)
    assert result == {"offspring_born": 6, "eligible_offspring": 5, "cycle_survivors": 4,
                      "cycle_survivors_with_surviving_child": 1, "recent_alive": 0, "recent_dead": 1}
    subset = audit.lifetime_cohort(records, 11520, selected_ids={2})
    assert subset["offspring_born"] == subset["cycle_survivors_with_surviving_child"] == 1
    late = audit.lifetime_cohort(records, 11520, 3855)
    assert late["offspring_born"] == 2 and late["eligible_offspring"] == late["cycle_survivors"] == 1
    recent = audit.lifetime_cohort(records, 7710, 3855)
    assert recent["recent_alive"] == recent["recent_dead"] == 1 and recent["eligible_offspring"] == 0

    def row(columns, global_mask=0, dead=False):
        return {"plants": [{"column": c, "dead": dead} for c in columns],
                "sites": [[global_mask | (32 if any(abs(c-p) < 3 for p in columns) else 0), 100, 200]
                          for c in range(28)]}

    covered = row([1, 4, 8, 12, 17, 22, 26])
    values = audit.spatial_snapshot(covered)
    assert values["all_columns_live_spacing_blocked"] == values["all_columns_spacing_blocked"] == 1
    assert values["any_open_relax_none"] == values["any_open_relax_nodes"] == 0
    assert values["any_open_relax_spacing"] == 1 and values["physically_open_columns"] == 28
    overlap = audit.spatial_snapshot(row([1, 4, 8, 12, 17, 22, 26], 16 | 8))
    assert overlap["any_open_relax_spacing"] == overlap["any_open_relax_nodes"] == 0
    assert overlap["any_open_relax_all_space_limits"] == 1
    shaded = audit.spatial_snapshot(row([1, 4, 8, 12, 17, 22, 26], 16 | 8 | 4))
    assert shaded["any_open_relax_all_space_limits"] == shaded["any_open_relax_light"] == 0
    dead = audit.spatial_snapshot(row([1, 4, 8, 12, 17, 22, 26], dead=True))
    assert dead["all_columns_live_spacing_blocked"] == 0 and dead["all_columns_spacing_blocked"] == 1
    covered["sites"][0][0] = 0
    rejects(lambda: audit.spatial_snapshot(covered))
    covered["sites"].pop()
    rejects(lambda: audit.spatial_snapshot(covered))


def integration(build):
    seed = trial_seeds(0x6d617463, 1)[0]
    horizon = 15360
    for mode in audit.maintenance.MODES:
        report = json.loads(subprocess.check_output([
            str(build / "toy-factory-garden-eval"), "--rainfed", "--trials", "1", "--seed", "0x6d617463",
            "--ticks", str(horizon), "--leaf-policy", mode], text=True, timeout=60))
        trial = report_trials(report)[("rainfed", "adaptive", seed)]
        case = {"leaf_policy": mode, "trial": trial}
        with tempfile.TemporaryDirectory(prefix="competition-test-") as temp:
            root = Path(temp)
            world, sites = root / "world.gz", root / "sites.gz"
            command = [str(build / "toy-factory-garden-inspect"), "-", "rainfed", "adaptive", "0x" + seed,
                       "--ticks", str(horizon), "--leaf-policy", mode]
            audit.capture(command + ["--ecology"], world, root, True)
            audit.capture(command + ["--seed-sites"], sites, root, False)
            capacity = report["node_capacity"]
            data = audit.analyze(world, sites, case, capacity, horizon, 2)
            assert data["seeds"]["checkpoints_verified"] == horizon // 15 + 1
            assert data["world"]["windows"]["late"]["samples"] == 512
            assert data["world"]["windows"]["whole"]["budget_checked_live_steps"] > 0
            assert sum(p["samples"] for p in data["spatial"]["late"].values()) == 512
            assert len(data["seeds"]["seeds"]) == trial["seeds_created"] > 0
            aggregate = audit.aggregate([{**case, "analysis": data}])[mode]
            assert aggregate["worlds"] == 1 and aggregate["final_living"] == trial["living"]
            assert aggregate["seeds"]["cohorts"]["whole"]["created"] == trial["seeds_created"]

            wrong = copy.deepcopy(case)
            wrong["trial"]["hash"] = "wrong"
            rejects(lambda: audit.analyze(world, sites, wrong, capacity, horizon, 2))
            rejects(lambda: audit.analyze(world, sites, {**case, "leaf_policy": "invalid"}, capacity, horizon, 2))
            rejects(lambda: audit.analyze(world, sites, case, 768-capacity, horizon, 2))
            with gzip.open(sites, "rt") as stream:
                rows = [json.loads(line) for line in stream]
            bad_path = root / "bad.gz"

            def pack(values):
                with gzip.open(bad_path, "wt") as stream:
                    for row in values:
                        stream.write(json.dumps(row) + "\n")

            pack(rows[:-1])
            rejects(lambda: audit.analyze(world, bad_path, case, capacity, horizon, 2))
            rows[1]["hash"] = "wrong"
            pack(rows)
            rejects(lambda: audit.analyze(world, bad_path, case, capacity, horizon, 2))
            with gzip.open(world, "rt") as stream:
                worlds = [json.loads(line) for line in stream]
            pack(worlds[:-1])
            rejects(lambda: audit.analyze(bad_path, sites, case, capacity, horizon, 2))
            worlds[1]["seeds_created"] += 1
            pack(worlds)
            rejects(lambda: audit.analyze(bad_path, sites, case, capacity, horizon, 2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path)
    args = parser.parse_args()
    synthetic()
    if args.build:
        integration(args.build.resolve())
    print("Maintenance competition checks passed")


if __name__ == "__main__":
    main()
