#!/usr/bin/env python3
"""Validate sparse population histories against the full ecology census and replay."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import subprocess
import tempfile

import garden_diversity as audit
from test_garden_leaf_competition import rejects


def synthetic():
    assert list(audit.SCHEDULES.values()) == [None, 0xe4d65e6f, 0x17c29444, 0x42b9cb9c, 0xf1fb8012]
    records = {1: {"founder": 1, "generation": 0, "species": "flower"},
               2: {"founder": 2, "generation": 0, "species": "shrub"},
               3: {"founder": 1, "generation": 1, "species": "flower"}}
    row = {"tick": 0, "hash": "test", "living": 2, "births": 1, "deaths": 1,
           "nodes": 12, "max_generation": 1,
           "plants": [{"id": 1, "species": "flower", "dead": False, "genome": [0]*8},
                      {"id": 2, "species": "shrub", "dead": True, "genome": [0]*8},
                      {"id": 3, "species": "flower", "dead": False, "genome": [1]*8}],
           "seeds": [{"parent": 2, "generation": 1}]}
    result = audit.population(row, records)
    assert result["living_families"] == result["living_species"] == 1
    assert result["extant_families"] == [1, 2] and result["extant_species"] == ["flower", "shrub"]
    assert result["effective_families"] == result["largest_family_fraction"] == 1
    assert result["living_genotypes"] == 2 and not result["extinct"]
    row["plants"][0]["dead"] = row["plants"][2]["dead"] = True
    row["living"] = 0
    result = audit.population(row, records)
    assert not result["extinct"] and result["extant_families"] == [2]
    assert result["effective_families"] == result["largest_family_fraction"] == result["living_genotypes"] == 0
    row["seeds"] = []
    assert audit.population(row, records)["extinct"]
    row["seeds"] = [{"parent": 99, "generation": 1}]
    rejects(lambda: audit.population(row, records))
    assert audit.distribution([1, 3, 2, 4])["median"] == 2.5
    for seed in audit.SCHEDULES.values():
        if seed is None:
            continue
        extended = audit.disturbance.schedule(seed, audit.HORIZON)
        assert [e for e in extended if e["tick"] <= audit.disturbance.HORIZON] == audit.disturbance.schedule(seed)
        assert extended[-1]["tick"] > audit.disturbance.HORIZON


def integration(build):
    horizon = 92160
    base = [str(build / "toy-factory-garden-inspect"), "-", "rainfed", "adaptive", "0x9c530b07",
            "--leaf-policy", "selective"]
    with tempfile.TemporaryDirectory(prefix="garden-diversity-test-") as temp:
        root = Path(temp)
        for seed in (None, 1):
            label = "control" if seed is None else "disturbed"
            common = base + (["--disturbance-seed", hex(seed)] if seed else [])
            boundaries = {}
            for suffix, flag, kind in (("full", "--ecology", "world"), ("sites", "--seed-sites", "seed-sites"),
                                       ("sparse", "--population", "world")):
                boundaries[suffix] = audit.disturbance.capture(common+[flag, "--ticks", str(horizon)],
                    root/f"{label}.{suffix}.gz", root, kind, seed, horizon)
            assert boundaries["full"] == boundaries["sparse"]
            path = root/f"{label}.sparse.gz"
            with gzip.open(path, "rt") as source:
                rows = [json.loads(line) for line in source]
            capacity = rows[0].get("node_capacity", 256)
            data = audit.analyze(path, boundaries["sparse"], capacity, horizon, seed)
            full = audit.disturbance.analyze(root/f"{label}.full.gz", root/f"{label}.sites.gz",
                {"world": boundaries["full"], "sites": boundaries["sites"]}, capacity, horizon, 8, seed)
            assert data["observed_rows"] < horizon//15//10
            assert audit.compare_sparse_prefix(path, root/f"{label}.full.gz", horizon) == len(rows)
            assert data["final"] == full["world"]["final"]
            keys = ("id", "parent", "species", "generation", "column", "birth_tick", "death_tick", "death_flags")
            assert [{k:p[k] for k in keys} for p in data["lineages"]] == [{k:p[k] for k in keys} for p in full["world"]["lineages"]]
            assert data["milestones"][str(horizon)]["closing"] == full["cohorts"]["closing"]
            # The bank's species interpretation must match the native full seed-site query.
            by_id = {p["id"]:p for p in data["lineages"]}
            names = {0: "flower", 1: "shrub", 2: "ground-cover"}
            with gzip.open(root/f"{label}.sites.gz", "rt") as source:
                for line in source:
                    site = json.loads(line)
                    for s in site["seeds"]:
                        assert by_id[s["parent"]]["species"] == names[s["species"]]
            wrong_path = root/"wrong.gz"

            def pack(values):
                with gzip.open(wrong_path, "wt") as output:
                    for r in values:
                        output.write(json.dumps(r)+"\n")

            pack(rows[:-1])
            rejects(lambda: audit.analyze(wrong_path, boundaries["sparse"], capacity, horizon, seed))
            wrong = copy.deepcopy(rows)
            wrong[1]["plants"][0]["age_ecology_ticks"] += 1
            pack(wrong)
            rejects(lambda: audit.analyze(wrong_path, boundaries["sparse"], capacity, horizon, seed))
            wrong = copy.deepcopy(rows)
            first_birth = next(i for i, r in enumerate(wrong) if r["births"] > 0)
            wrong.pop(first_birth)
            pack(wrong)
            rejects(lambda: audit.analyze(wrong_path, boundaries["sparse"], capacity, horizon, seed))
            if seed is not None:
                rejects(lambda: audit.analyze(path, [], capacity, horizon, seed))
                # Last sample exactly on an event, with a complete day boundary.
                first = audit.disturbance.FIRST
                pack([r for r in rows if r["tick"] <= first])
                endpoint = audit.analyze(wrong_path, boundaries["sparse"][:1], capacity, first, seed)
                assert endpoint["final"] == boundaries["sparse"][0]["after"]
        # Verify extended scheduling, live ages and the full 192-day endpoint.
        seed = next(s for s in audit.SCHEDULES.values() if s is not None)
        common = base + ["--disturbance-seed", hex(seed)]
        long_path = root/"long.gz"
        bounds = audit.disturbance.capture(common+["--population", "--ticks", str(audit.HORIZON)],
                                           long_path, root, "world", seed, audit.HORIZON)
        data = audit.analyze(long_path, bounds, capacity, audit.HORIZON, seed)
        assert len(data["daily"]) == 193 and len(data["events"]) > 13
        for tick in audit.CHECKPOINTS:
            command = [str(build / "toy-factory-garden-replay"), *common[1:], "--ticks", str(tick)]
            replay = json.loads(subprocess.check_output(command, text=True, timeout=60))
            assert replay["hash"] == data["milestones"][str(tick)]["population"]["hash"]
        for extra in (["--population"], ["--ecology"], ["--seed-sites"], ["--root-first", "1"],
                      ["--night-wait", "1"], ["--gap-at", "61440"]):
            result = subprocess.run(base+["--population", "--ticks", "61440", *extra], capture_output=True, timeout=60)
            assert result.returncode != 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    args = parser.parse_args()
    synthetic()
    integration(args.build.resolve())
    print("Population census/diversity/long-horizon checks passed")


if __name__ == "__main__":
    main()
