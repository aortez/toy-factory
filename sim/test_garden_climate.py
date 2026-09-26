#!/usr/bin/env python3
"""Check climate CLI contracts, deterministic replay, and long-lived seed exports."""

import argparse
import json
from pathlib import Path
import subprocess
import tempfile

import garden_experiments as experiments
import garden_gallery as gallery


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
    evaluator = args.build / "toy-factory-garden-eval"
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
        with tempfile.TemporaryDirectory(prefix="garden-climate-eval-") as temporary:
            timeline = Path(temporary) / "timeline.jsonl"
            eval_command = [evaluator, "--rainfed", "--trials", "1", "--seed", "123",
                            "--ticks", "122880", "--climate", mode]
            evaluated = json.loads(run([*eval_command, "--timeline", timeline]))
            assert json.loads(run(eval_command)) == evaluated
            environment = experiments.requested_environment("narrow-v1", "legacy-v1", False,
                                                           climate=mode)
            assert all(evaluated["environment"][k] == v for k, v in environment.items())
            if "leaf_environment" not in evaluated:
                experiments.validate_report(evaluated, experiments.trial_seeds(123, 1), 122880,
                                            None, environment=environment)
            # Probe actual drought and cold checkpoints, not only spring endpoints.
            samples = [json.loads(line) for line in timeline.read_text().splitlines()]
            assert all(row["climate"]["mode"] == mode for row in samples)
            assert all(row["rain_rate"] == 0 for row in samples if row["climate"]["drought"])
            for policy in ("baseline", "adaptive", "neural-reference"):
                for tick in (5 * 3840, 14 * 3840, 122880):
                    row = next(r for r in samples if r["scenario"] == "rainfed"
                               and r["policy"] == policy and r["tick"] == tick)
                    command = [replay, "-", "rainfed", policy, "0x" + row["seed"],
                               "--ticks", str(tick), "--climate", mode]
                    picture = Path(temporary) / "frame.rgb565be"
                    rendered = json.loads(run([*command, "--framebuffer", picture]))
                    gallery.check_frame(rendered, row, None, picture.read_bytes())
                    picture.unlink()
    assert len(hashes) == 4
    for binary in (inspector, replay):
        base = [binary, "-", "rainfed", "adaptive", "123", "--ticks", "15"]
        for flags in (["--climate"], ["--climate", "invalid"],
                      ["--climate", "winter", "--climate", "drought"]):
            run([*base, *flags], 2)
    base = [evaluator, "--rainfed", "--trials", "1", "--ticks", "60"]
    assert json.loads(run(base)) == json.loads(run([*base, "--climate", "steady"]))
    for flags in (["--climate"], ["--climate", "invalid"],
                  ["--climate", "winter", "--climate", "drought"]):
        run([*base, *flags], 2)
    run([evaluator, "--climate", "winter"], 2)
    run([*base, "--ticks", "983041"], 2)
    print("Seasonal CLI/replay checks passed")


if __name__ == "__main__":
    main()
