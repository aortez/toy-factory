#!/usr/bin/env python3
"""Check climate CLI contracts, deterministic replay, and long-lived seed exports."""

import argparse
import json
from pathlib import Path
import subprocess


def run(command, expected=0):
    result = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=120)
    if result.returncode != expected:
        raise RuntimeError(f"{command}: expected {expected}, got {result.returncode}: {result.stderr}")
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    args = parser.parse_args()
    inspector = args.build / "toy-factory-garden-inspect"
    replay = args.build / "toy-factory-garden-replay"
    hashes = set()
    for mode in ("steady", "winter", "drought", "seasonal"):
        command = [inspector, "-", "rainfed", "adaptive", "123", "--ticks", "122880", "--climate", mode]
        output = run(command)
        assert run(command) == output
        worlds = [row for line in output.splitlines() if (row := json.loads(line))["type"] == "world"]
        assert worlds[-1]["tick"] == 122880
        assert all(row["seed_lifetime_ecology_ticks"] == 8192 for row in worlds)
        assert all(row["climate"]["mode"] == mode for row in worlds)
        assert any(seed["age"] > 256 for row in worlds for seed in row["seeds"])
        assert all(row["rain_rate"] == 0 for row in worlds if row["climate"]["drought"])
        assert any(row["climate"]["cold"] for row in worlds) == (mode in ("winter", "seasonal"))
        assert any(row["climate"]["drought"] for row in worlds) == (mode in ("drought", "seasonal"))
        result = json.loads(run([replay, *command[1:]]))
        for key in ("hash", "tick", "sun_phase", "sun_strength", "rain_rate", "rain_deposited",
                    "rain_runoff", "births", "deaths", "living", "nodes", "climate"):
            assert result[key] == worlds[-1][key], key
        hashes.add(result["hash"])
    assert len(hashes) == 4
    for binary in (inspector, replay):
        base = [binary, "-", "rainfed", "adaptive", "123", "--ticks", "15"]
        for flags in (["--climate"], ["--climate", "invalid"],
                      ["--climate", "winter", "--climate", "drought"]):
            run([*base, *flags], 2)
    print("Seasonal CLI/replay checks passed")


if __name__ == "__main__":
    main()
