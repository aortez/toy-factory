#!/usr/bin/env python3
"""Native arithmetic/ledger/replay parity and deterministic mutation boundaries."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import tempfile

import garden_lineage_persistence as fitness
import garden_training_pilot as pilot


def reject(call):
    try:
        call()
    except (RuntimeError, ValueError, KeyError):
        return
    raise AssertionError("invalid trial accepted")


def check_arithmetic(build):
    check = build / "toy-factory-garden-persistence-check"
    for name, f in fitness.arithmetic_fixtures().items():
        plants, seeds = f["lineages"], f["seeds"]
        pending = sum(s["outcome"] == "pending" for s in seeds)
        text = f"15360 30720 38400 {pending} {len(plants)}\n"
        for p in plants:
            death = 4294967295 if p["death_tick"] is None else p["death_tick"]
            text += f"{p['parent']} {p['birth_tick']} {death}\n"
        result = subprocess.run([check], input=text, text=True, capture_output=True, check=True, timeout=10)
        assert json.loads(result.stdout) == f["evaluation"]["key"], name
    for text in ("0 15 7695 0 0\n", "0 15 7695 0 1\n0 0 0\n"):
        result = subprocess.run([check], input=text, text=True, capture_output=True, check=True, timeout=10)
        assert json.loads(result.stdout) == [-1, 0, 0, 0, 0]
    for text in ("", "0 15 7695 0 0", "0 15 7695 0 0\nextra\n", "0 15 7695 0 4097\n",
                 "0 15 7695 17 0\n", "0 15 7695 0 1\n1 0 4294967295\n",
                 "0 15 7695 0 1\n0 30 15\n", "1 15 7695 0 0\n", "0 15 7696 0 0\n",
                 "0 15 7695 0 1\n0 7696 4294967295\n", "-1 15 7695 0 0\n",
                 "4294967296 15 7695 0 0\n", "0 15 7695 0 0 ignored\n"):
        result = subprocess.run([check], input=text, text=True, capture_output=True, timeout=10)
        assert result.returncode != 0 and not result.stdout, text
    cases = [{"id": str(i), "aggregate": fitness.aggregate({"world": f["evaluation"]})}
             for i, f in enumerate(fitness.arithmetic_fixtures().values())]
    best = pilot.select(cases[0], cases)
    assert best["aggregate"]["key"] == max(c["aggregate"]["key"] for c in cases)
    assert pilot.select(best, [copy.deepcopy(best)]) is best


def check_mutation(build, model, root):
    tool = build / "toy-factory-garden-model-mutate"
    original = model.read_bytes()
    # Golden outputs from the pre-extraction trainer, using its reference model.
    golden = {1: ("7fbb1ead", 867497350), 32: ("7324f33f", 4246583298),
              4096: ("4ab1dbce", 3923761917)}
    assert pilot.model_crc(model) == "d8131120"
    for count in (1, 32, 4096):
        outputs, results = [], []
        for repeat in (0, 1):
            target = root / f"mutant-{count}-{repeat}.tgm"
            result = subprocess.run([tool, model, target, "0", str(count)], check=True,
                                    capture_output=True, text=True, timeout=10)
            outputs.append(target.read_bytes())
            results.append(json.loads(result.stdout))
            assert results[-1]["before"] == pilot.model_crc(model)
            assert results[-1]["after"] == pilot.model_crc(target)
            assert (results[-1]["after"], results[-1]["rng_after"]) == golden[count]
            no_overwrite = subprocess.run([tool, model, target, "0", str(count)], capture_output=True, timeout=10)
            assert no_overwrite.returncode and target.read_bytes() == outputs[-1]
        assert outputs[0] == outputs[1] and results[0] == results[1]
    for seed, count in (("-1", "32"), ("0", "0"), ("0", "4097"), ("4294967296", "32"), ("2x", "32")):
        target = root / "invalid.tgm"
        result = subprocess.run([tool, model, target, seed, count], capture_output=True, timeout=10)
        assert result.returncode == 2 and not target.exists()
    assert model.read_bytes() == original


def check_trial(build, model, root):
    tool = build / "toy-factory-garden-persistence-trial"
    if not tool.exists():
        print("Frozen experimental trial unavailable in this build; pure C scorer/mutator tested")
        return
    start, end, seed = 10 * pilot.DAY, 16 * pilot.DAY, "b61837dc"
    for policy in ("neural", "reserve"):
        value, _ = pilot.run_json([tool, model, policy, "0x" + seed, "0x" + pilot.PATCH, start, end],
                                  root / f"{policy}.json")
        score = pilot.validate_trial(value, seed, pilot.model_crc(model), start, end, policy)
        assert score["final"]["tick"] == 18 * pilot.DAY
        for mutate in (lambda v: v.update(model_crc32="00000000"),
                       lambda v: v["key"].__setitem__(1, v["key"][1] + 15),
                       lambda v: v["checkpoints"].pop(),
                       lambda v: v["lineages"][0].update(seeds_created=999),
                       lambda v: v["checkpoints"][-1].update(living=999)):
            bad = copy.deepcopy(value)
            mutate(bad)
            reject(lambda: pilot.validate_trial(bad, seed, pilot.model_crc(model), start, end, policy))
        for tick in (480, 2880, end, end + 2 * pilot.DAY):
            cmd = [build / "toy-factory-garden-replay", model, "rainfed-crowded",
                   "neural-no-night-growth" if policy == "neural" else "neural-reserve-growth",
                   "0x" + seed, "--leaf-policy", "selective", "--disturbance-seed", int(pilot.PATCH, 16),
                   "--ticks", tick]
            replay, _ = pilot.run_json(cmd, root / f"{policy}.{tick}.replay.json")
            pilot.check_replay(replay, value, seed, pilot.model_crc(model), tick, policy=policy)
    patch = "17c29444"
    value, _ = pilot.run_json([tool, model, "neural", "0x" + seed, "0x" + patch, start, end],
                              root / "second-patch.json")
    pilot.validate_trial(value, seed, pilot.model_crc(model), start, end, patch=patch)
    reject(lambda: pilot.validate_trial(value, seed, pilot.model_crc(model), start, end))
    cmd = [build / "toy-factory-garden-replay", *pilot.replay_command(
        root, model, seed, end + 2 * pilot.DAY, patch=patch)[1:]]
    replay, _ = pilot.run_json(cmd, root / "second-patch.replay.json")
    pilot.check_replay(replay, value, seed, pilot.model_crc(model), end + 2 * pilot.DAY, patch=patch)
    reject(lambda: pilot.check_replay(replay, value, seed, pilot.model_crc(model), end + 2 * pilot.DAY))
    for args in (("0", "15"), ("1", "15"), ("15", "15"), ("0", "729615")):
        result = subprocess.run([tool, model, "neural", "1", "1", *args], capture_output=True, timeout=10)
        if args == ("0", "15"):
            assert result.returncode == 0
        else:
            assert result.returncode == 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    build = parser.parse_args().build.resolve()
    check_arithmetic(build)
    with tempfile.TemporaryDirectory(prefix="garden-persistence-test-") as temp:
        root, model = Path(temp), Path(temp) / "reference.tgm"
        # The existing model-writing test is available in all host configurations.
        subprocess.run([build / "toy-factory-garden-neural-test"], check=True, timeout=30)
        # The evaluator can export the reference model without running experimental training.
        writer = build / "toy-factory-garden-water-audit-test"
        if writer.exists():
            subprocess.run([writer, model], check=True, timeout=30)
        else:
            subprocess.run([build / "toy-factory-garden-train", "--generations", "0", "--ticks", "1",
                            "--trials", "1", "--output", model, "--c-output", root / "reference.c"],
                           check=True, capture_output=True, timeout=30)
        check_mutation(build, model, root)
        check_trial(build, model, root)
    print("18 C/Python fixtures, invalid inputs, mutation repeat and native replay parity passed")


if __name__ == "__main__":
    main()
