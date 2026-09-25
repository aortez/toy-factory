#!/usr/bin/env python3
"""Exercise the maintenance CLI, report, trace and replay contract in a short run."""
import argparse
import gzip
import json
from pathlib import Path
import subprocess
import tempfile

from garden_experiments import report_trials, trial_seeds
from garden_leaf_experiment import MODES, audit_trace, check_identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    args = parser.parse_args()
    build = args.build.resolve()
    seed = trial_seeds(0x6d617463, 1)[0]
    ticks = 15360
    for mode in MODES:
        command = [str(build / "toy-factory-garden-eval"), "--rainfed", "--trials", "1",
                   "--seed", "0x6d617463", "--ticks", str(ticks), "--leaf-policy", mode]
        report = json.loads(subprocess.check_output(command, text=True, timeout=60))
        capacity = report["node_capacity"]
        check_identity(report, mode, capacity)
        trials = report_trials(report)
        renewals = sum(t["leaf"]["renewals"] for t in trials.values())
        assert renewals == 0 if mode == "none" else renewals > 0
        result = json.loads(subprocess.check_output([
            str(build / "toy-factory-garden-replay"), "-", "rainfed", "adaptive", "0x" + seed,
            "--ticks", str(ticks), "--leaf-policy", mode], text=True, timeout=60))
        check_identity(result, mode, capacity)
        assert result["hash"] == trials[("rainfed", "adaptive", seed)]["hash"]
        with tempfile.TemporaryDirectory(prefix="leaf-smoke-") as temp:
            trace = subprocess.check_output([
                str(build / "toy-factory-garden-inspect"), "-", "rainfed", "adaptive", "0x" + seed,
                "--ticks", str(ticks), "--ecology", "--leaf-policy", mode], timeout=60)
            path = Path(temp) / "trace.jsonl.gz"
            with gzip.open(path, "wb") as stream:
                stream.write(trace)
            audit = audit_trace(path, mode, capacity, ticks)
            assert audit["hashes"][ticks] == result["hash"]
            assert audit["totals"]["checked_live_steps"] > 0
        rejected = subprocess.run(command[:-1] + ["invalid"], capture_output=True, timeout=60)
        assert rejected.returncode != 0
    print("Maintenance report/replay/trace smoke passed")


if __name__ == "__main__":
    main()
