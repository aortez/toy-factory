#!/usr/bin/env python3
"""Check fixed schedules, pre/post-death ledgers, replay identity and terminal boundaries."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import subprocess
import tempfile

import garden_disturbance as audit
from test_garden_leaf_competition import rejects


def synthetic():
    # A death exactly at a full-day survival boundary is a failure, not a survivor.
    records = {1: {"id": 1, "parent": 0, "birth_tick": 0, "death_tick": None},
               2: {"id": 2, "parent": 1, "birth_tick": 15, "death_tick": 3855,
                   "environmental_death": True},
               3: {"id": 3, "parent": 1, "birth_tick": 30, "death_tick": 30,
                   "environmental_death": True}}
    result = audit.competition.lifetime_cohort(records, 3855)
    assert result["eligible_offspring"] == 1 and result["cycle_survivors"] == 0
    assert result["recent_dead"] == 1
    early = audit.competition.lifetime_cohort(records, 20)
    assert early["offspring_born"] == early["recent_alive"] == 1 and early["recent_dead"] == 0
    assert audit.schedule(None) == [] and audit.schedule(1, audit.FIRST-1) == []
    assert len(audit.schedule(1, audit.FIRST)) == 1
    coverage = set()
    for seed in range(1, 1001):
        events = audit.schedule(seed)
        assert 7 <= len(events) <= 13 and events[0]["tick"] == audit.FIRST
        for a, b in zip(events, events[1:]):
            assert 15360 <= b["tick"]-a["tick"] <= 30720
        for event in events:
            coverage.update(range(event["first_column"], event["last_column"]+1))
    assert coverage == set(range(28))


def integration(build):
    horizon = 92160
    seed = 4  # Fixed long-lived-seed fixture; archived panels retain their original schedules.
    base = [str(build / "toy-factory-garden-inspect"), "-", "rainfed", "adaptive", "0x9c530b07",
            "--leaf-policy", "selective"]
    with tempfile.TemporaryDirectory(prefix="disturbance-test-") as temp:
        root = Path(temp)
        results = {}
        for arm in ("control", "disturbed"):
            commands = base + ["--ticks", str(horizon)]
            if arm == "disturbed":
                commands += ["--disturbance-seed", hex(seed)]
            boundaries = {}
            for suffix, flag, kind in (("world", "--ecology", "world"), ("sites", "--seed-sites", "seed-sites")):
                path = root / f"{arm}.{suffix}.gz"
                boundaries[suffix] = audit.capture(commands+[flag], path, root, kind,
                                                  seed if arm == "disturbed" else None, horizon)
                if arm == "disturbed":
                    audit.gap.compare_prefix(path, root / f"control.{suffix}.gz", audit.FIRST)
            with gzip.open(root / f"{arm}.world.gz", "rt") as stream:
                capacity = json.loads(next(stream)).get("node_capacity", 256)
            data = audit.analyze(root / f"{arm}.world.gz", root / f"{arm}.sites.gz", boundaries,
                                 capacity, horizon, 8, seed if arm == "disturbed" else None)
            replay = json.loads(subprocess.check_output([str(build / "toy-factory-garden-replay"), *commands[1:]],
                                                       text=True, timeout=60))
            assert replay["hash"] == data["world"]["final"]["hash"]
            assert data["seeds"]["checkpoints_verified"] == horizon//15+1
            results[arm] = data
            if arm == "control":
                continue
            assert len(boundaries["world"]) == len(audit.schedule(seed, horizon)) >= 2
            killed = sum(len(b["event"]["killed"]) for b in boundaries["world"])
            assert killed > 0
            windows = data["world"]["windows"]["whole"]
            assert windows["environmental_deaths"] == replay["environmental_deaths"] == killed
            assert windows["terminal_steps"] + killed == replay["deaths"]
            assert sum(p.get("environmental_death", False) for p in data["world"]["lineages"]) == killed
            rejects(lambda: audit.analyze(root / "disturbed.world.gz", root / "disturbed.sites.gz",
                                         {"world": [], "sites": []}, capacity, horizon, 8, seed))
            for field in ("tick", "first_column", "energy", "nodes", "after_hash", "killed"):
                b = copy.deepcopy(next(b for b in boundaries["world"] if b["event"]["killed"]))
                event = b["event"]
                event[field] = [] if field == "killed" else ("wrong" if field == "after_hash" else event[field]+1)
                rejects(lambda: audit.validate_boundary(b["before"], b["after"], event))
            # The endpoint itself is post-event state, even though the normalized row
            # preserves the pre-event ecology step. This must hold for repeated events too.
            for boundary in boundaries["world"]:
                tick = boundary["event"]["tick"]
                clipped = {kind: [b for b in values if b["event"]["tick"] <= tick]
                           for kind, values in boundaries.items()}
                for suffix in ("world", "sites"):
                    with gzip.open(root / f"disturbed.{suffix}.gz", "rt") as source:
                        with gzip.open(root / f"endpoint.{suffix}.gz", "wt") as target:
                            for line in source:
                                if json.loads(line)["tick"] <= tick:
                                    target.write(line)
                endpoint = audit.analyze(root / "endpoint.world.gz", root / "endpoint.sites.gz",
                                         clipped, capacity, tick, 8, seed)
                assert endpoint["world"]["final"] == boundary["after"]
                command = [str(build / "toy-factory-garden-replay"), *base[1:], "--ticks", str(tick),
                           "--disturbance-seed", hex(seed)]
                assert json.loads(subprocess.check_output(command, text=True, timeout=60))["hash"] == boundary["after"]["hash"]
        summary = audit.summarize([{"arm": "control", "analysis": results["control"]},
                                   {"arm": "schedule-a", "analysis": results["disturbed"]}])
        assert summary["control"]["worlds"] == summary["schedule-a"]["worlds"] == 1
        assert summary["schedule-b"]["worlds"] == 0
        for executable in ("inspect", "replay"):
            command = [str(build / f"toy-factory-garden-{executable}"), *base[1:], "--ticks", str(horizon)]
            for arguments in (["--disturbance-seed", "0"], ["--disturbance-seed", "-1"],
                              ["--disturbance-seed", "0x100000000"],
                              ["--disturbance-seed", "1", "--disturbance-seed", "2"],
                              ["--disturbance-seed", "1", "--gap-at", str(audit.FIRST)]):
                assert subprocess.run(command+arguments, capture_output=True, timeout=60).returncode != 0
            assert subprocess.run([str(build / f"toy-factory-garden-{executable}"), *base[1:],
                                   "--ticks", str(audit.MAX_HORIZON+1)], capture_output=True, timeout=60).returncode != 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    args = parser.parse_args()
    synthetic()
    integration(args.build.resolve())
    print("Recurring disturbance ledger/replay checks passed")


if __name__ == "__main__":
    main()
