#!/usr/bin/env python3
"""Exercise native gap export, replay binding, accounting, and invalid boundaries."""

import argparse
import copy
import json
from pathlib import Path
import subprocess
import tempfile

import garden_gap_experiment as gap
from garden_experiments import report_trials, trial_seeds
from test_garden_leaf_competition import rejects


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    args = parser.parse_args()
    build = args.build.resolve()
    horizon, at = 15360, 7680
    seed = trial_seeds(0x6d617463, 1)[0]
    report = json.loads(subprocess.check_output([
        str(build / "toy-factory-garden-eval"), "--rainfed", "--trials", "1", "--seed", "0x6d617463",
        "--ticks", str(horizon), "--leaf-policy", "selective"], text=True, timeout=60))
    case = {"leaf_policy": "selective", "trial": report_trials(report)[("rainfed", "adaptive", seed)]}
    with tempfile.TemporaryDirectory(prefix="gap-smoke-") as temp:
        root = Path(temp)
        results = {}
        for arm in ("control", "gap"):
            base = [str(build / "toy-factory-garden-inspect"), "-", "rainfed", "adaptive", "0x" + seed,
                    "--ticks", str(horizon), "--leaf-policy", "selective"]
            if arm == "gap":
                base += ["--gap-at", str(at)]
            boundaries = {}
            for suffix, flag, kind in (("world", "--ecology", "world"), ("sites", "--seed-sites", "seed-sites")):
                path = root / f"{arm}.{suffix}.gz"
                boundaries[suffix] = gap.capture(base + [flag], path, root, kind, at if arm == "gap" else None)
                if arm == "gap":
                    assert gap.compare_prefix(path, root / f"control.{suffix}.gz", at) == at // 15 + 1
            event = boundaries["world"]["event"] if arm == "gap" else None
            data = gap.competition.analyze(root / f"{arm}.world.gz", root / f"{arm}.sites.gz", case,
                                           report["node_capacity"], horizon, 2, event)
            if arm == "gap":
                assert event == boundaries["sites"]["event"]
                assert data["seeds"]["checkpoints_verified"] == horizon // 15 + 1
                removed = [p for p in data["world"]["lineages"] if "removal_tick" in p]
                assert len(removed) == 1 and removed[0]["id"] == event["id"] and removed[0]["removal_tick"] == at
                # Gap exports are absent from biological death counts and live-step debits.
                assert data["world"]["windows"]["whole"]["terminal_steps"] == data["world"]["final"]["deaths"]
                rejects(lambda: gap.competition.analyze(root / "gap.world.gz", root / "gap.sites.gz", case,
                                                        report["node_capacity"], horizon, 2))
                for field in ("id", "nodes", "energy", "tick", "after_hash"):
                    wrong = dict(event)
                    wrong[field] = "wrong" if field == "after_hash" else wrong[field] + 1
                    rejects(lambda: gap.validate_boundary(boundaries["world"]["before"], boundaries["world"]["after"], wrong))
                wrong = copy.deepcopy(boundaries["world"]["after"])
                wrong["plants"][0]["water"] += 1
                rejects(lambda: gap.validate_boundary(boundaries["world"]["before"], wrong, event))
                wrong = copy.deepcopy(boundaries["sites"]["after"])
                wrong["sites"][0][1] += 1
                rejects(lambda: gap.validate_boundary(boundaries["sites"]["before"], wrong, event))
                wrong = copy.deepcopy(boundaries["sites"]["after"])
                wrong["seeds"] = []
                assert boundaries["sites"]["before"]["seeds"]
                rejects(lambda: gap.validate_boundary(boundaries["sites"]["before"], wrong, event))
            command = [str(build / "toy-factory-garden-replay"), *base[1:]]
            replay = json.loads(subprocess.check_output(command, text=True, timeout=60))
            assert replay["hash"] == data["world"]["final"]["hash"]
            if arm == "gap":
                assert replay["removed_id"] == event["id"] and replay["gap_protocol"] == gap.PROTOCOL
            results[arm] = {"analysis": data, "boundaries": boundaries}
        for arm, result in results.items():
            later = gap.checkpoints(root / f"{arm}.world.gz", {11520})[11520]
            result["metrics"] = gap.metrics(result["analysis"], event, later, at, horizon)
        summary = gap.summarize([results])
        assert summary["gap"]["worlds"] == 1
        assert summary["gap"]["totals"]["bank_seed_births"] + summary["gap"]["totals"]["new_seed_births"] == summary["gap"]["totals"]["births"]
        for executable in ("inspect", "replay"):
            base = [str(build / f"toy-factory-garden-{executable}"), "-", "rainfed", "adaptive", "0x" + seed,
                    "--ticks", str(horizon), "--leaf-policy", "selective"]
            for arguments in (["--gap-at", "0"], ["--gap-at", "7"], ["--gap-at", str(horizon+15)],
                              ["--gap-at", str(at), "--gap-at", str(at)], ["--gap-at", "15"]):
                result = subprocess.run(base + arguments, capture_output=True, timeout=60)
                assert result.returncode != 0
    print("Gap census/replay/budget tests passed")


if __name__ == "__main__":
    main()
