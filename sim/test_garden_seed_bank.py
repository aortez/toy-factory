#!/usr/bin/env python3
"""Capacity identity, native ledgers, malformed inputs and pair-prefix checks."""
import argparse
import copy
import gzip
import json
from pathlib import Path
import subprocess
import tempfile

import garden_seed_bank as bank
from test_garden_seed_attempts import rejects


def write_rows(path, rows):
    with gzip.open(path, "wt") as f:
        for r in rows:
            f.write(json.dumps(r)+"\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True, type=Path)
    build = parser.parse_args().build.resolve()
    for capacity in (8,16):
        row = {"leaf_environment": bank.competition.maintenance.ENVIRONMENT,
               "leaf_policy": "selective", "node_capacity": 512, "seed_capacity": capacity}
        bank.identity(row, capacity, "neural")
        rejects(lambda: bank.identity(row, 24-capacity, "neural"))
        rejects(lambda: bank.competition.maintenance.check_identity(row, "selective", 512, seed_capacity=32))
    with tempfile.TemporaryDirectory(prefix="seed-bank-test-") as temp:
        root = Path(temp)
        x = {"tick": 0, "hash": "a", "seeds": [], "seeds_created": 0, "births": 0, "deaths": 0, "nodes": 0}
        a = {**x, "tick": 15, "hash": "b", "seeds": [{}]*8, "seeds_created": 8}
        b = {**a, "hash": "c", "seed_capacity": 16, "seeds": [{}]*9, "seeds_created": 9}
        write_rows(root/"a.gz", [x,a]); write_rows(root/"b.gz", [{**x,"seed_capacity":16},b])
        assert bank.compare_prefix(root/"a.gz", root/"b.gz")["matched_rows"] == 1
        for bad in ({**b, "seeds": [{}]*8}, {**b,"nodes":4}, {**b,"seeds_created":8}):
            write_rows(root/"b.gz", [{**x,"seed_capacity":16},bad])
            rejects(lambda: bank.compare_prefix(root/"a.gz", root/"b.gz"))
        model = root/"model.tgm"
        subprocess.run([str(build/"toy-factory-garden-water-audit-test"), str(model)], check=True, timeout=60)
        end, start = 18*bank.DAY, 16*bank.DAY
        for side in ("neural", "reserve"):
            args = [str(model), "rainfed-crowded", bank.POLICIES[side], "0xb61837dc",
                    "--leaf-policy", "selective", "--disturbance-seed", str(bank.SCHEDULE)]
            bounds = {}
            for kind, flag in (("world","--ecology"),("sites","--seed-sites")):
                path = root/f"{side}.{kind}.gz"
                bounds[kind] = bank.recruitment.diversity.disturbance.capture(
                    [str(build/"toy-factory-garden-inspect"),*args,flag,"--ticks",str(end)], path,
                    root, "world" if kind == "world" else "seed-sites", bank.SCHEDULE, end)
            with gzip.open(root/f"{side}.world.gz", "rt") as f:
                rows = [json.loads(l) for l in f]
            cap = rows[0].get("seed_capacity",8)
            nodes = rows[0].get("node_capacity",256)
            run = lambda n=cap, bs=bounds, w=root/f"{side}.world.gz": bank.analyze(
                w, root/f"{side}.sites.gz", bs, n, side, end, start, nodes)
            result = run()
            assert result["seeds"]["checkpoints_verified"] == end//15+1
            assert result["world"]["windows"]["late"]["samples"] == 512
            assert result["world"]["windows"]["whole"]["budget_checked_live_steps"] > 0
            rejects(lambda: run(n=24-cap))
            bad = copy.deepcopy(bounds)
            bad["world"][0]["after"]["seed_capacity"] = 24-cap
            rejects(lambda: run(bs=bad))
            for damaged in (rows[:-1], [{**rows[0],"seeds":[{}]*(cap+1)},*rows[1:]]):
                write_rows(root/"bad.gz", damaged)
                rejects(lambda: run(w=root/"bad.gz"))
            replay = json.loads(subprocess.check_output([str(build/"toy-factory-garden-replay"),
                *args,"--ticks",str(end)], text=True, timeout=60))
            assert replay["hash"] == result["world"]["final"]["hash"]
            assert replay.get("seed_capacity",8) == cap
            print(f"Seed bank {cap}, nodes {nodes}, {side}: ledgers and identity validated", flush=True)


if __name__ == "__main__":
    main()
