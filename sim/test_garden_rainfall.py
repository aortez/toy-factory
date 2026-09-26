#!/usr/bin/env python3
"""Check deterministic, policy-independent rain-fed evaluation contracts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

def rain_at(seed: int, tick: int) -> int:
    bits = seed ^ (tick // 128) ^ 0x7261696E
    bits ^= bits >> 16
    bits = (bits * 0x7FEB352D) & 0xFFFFFFFF
    bits ^= bits >> 15
    bits = (bits * 0x846CA68B) & 0xFFFFFFFF
    bits ^= bits >> 16
    start = 8 + bits % 81
    duration = 16 + (bits >> 8) % 17
    return 2 + (bits >> 16) % 3 if start <= tick % 128 < start + duration else 0


def run(binary: Path, seed: int) -> dict:
    result = subprocess.run(
        [str(binary.resolve()), "--rainfed", "--trials", "2", "--ticks", "7680",
         "--seed", str(seed)], check=True, capture_output=True, text=True,
    )
    return json.loads(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    args = parser.parse_args()
    first = run(args.binary, 0x12345678)
    assert first == run(args.binary, 0x12345678)
    assert first != run(args.binary, 0x12345679)
    assert first["environment"] == {"rain_version": 1, "gardener": False, "irrigation": False,
                                    "climate": "steady", "seed_lifetime_ecology_ticks": 8192}
    assert [s["name"] for s in first["scenarios"]] == ["rainfed", "rainfed-crowded"]
    schedules = {}
    for scenario in first["scenarios"]:
        assert scenario["irrigation_pattern"] == "none"
        assert scenario["irrigation_period_ticks"] == 0
        assert scenario["irrigation_water_per_column"] == 0
        for policy in scenario["policies"]:
            for trial in policy["trials"]:
                weather = trial["weather"]
                assert weather["seed"] == trial["seed"]
                seed = int(weather["seed"], 16)
                offered = sum(rain_at(seed, tick) * 28 for tick in range(1, 513))
                assert weather["deposited"] > 0
                assert weather["runoff"] >= 0
                assert weather["deposited"] + weather["runoff"] == offered
                assert offered == schedules.setdefault(seed, offered)
                assert trial["lineages"] == scenario["plants"] + trial["germinations"]
                assert 0 <= trial["living"] <= 8
                assert 0 <= trial["nodes"] <= 256
                assert 0 <= trial["moisture"] <= 28 * 11 * 255
    print("Rain-fed replay, water accounting, and matched weather passed")


if __name__ == "__main__":
    main()
