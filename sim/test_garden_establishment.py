#!/usr/bin/env python3
"""Check seed identity/outcome reconciliation, spatial snapshots, and frozen census replay."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import garden_establishment as audit
import garden_experiments as experiment


def run(command, expected=0):
    result = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=120)
    if result.returncode != expected:
        raise RuntimeError(f"{command}: expected {expected}, got {result.returncode}\n{result.stdout}\n{result.stderr}")
    return result.stdout


def rejects(call):
    try:
        call()
    except RuntimeError:
        return
    raise AssertionError("invalid census accepted")


def pack(path, rows):
    with gzip.open(path, "wt") as stream:
        for row in rows:
            stream.write(json.dumps(row)+"\n")


def synthetic(root):
    for outcome in ("expired", "germinated", "pending"):
        end = 3855 if outcome != "pending" else 3840
        rows = []
        for tick in range(0, end+1, 15):
            age = (tick-15)//15
            removed = tick >= (135 if outcome == "germinated" else 3855)
            plants = [dict(id=1, parent=0, column=6, generation=0, species=0,
                           dead=False, dispersal_columns=(1 << 2) | (1 << 10))]
            seeds = []
            if tick >= 15 and not removed:
                seeds.append(dict(parent=1, column=2, generation=1, species=0,
                                  age=age, blockers=2 | (1 if age < 8 else 0)))
            births = int(outcome == "germinated" and removed)
            if births:
                plants.append(dict(id=2, parent=1, column=2, generation=1, species=0,
                                   dead=False, dispersal_columns=1 << 10))
            sites = [[2, 0, 255] for _ in range(28)]
            sites[10] = [0, 100, 255]
            rows.append(dict(type="seed-sites", schema_version=1, tick=tick, hash=f"{tick:08x}",
                             sun_phase=(64+tick//15)%256, sun_strength=255, rain_rate=0,
                             nodes=4+births*4, living=1+births, plants=plants, seeds=seeds, sites=sites,
                             births=births, deaths=0, seeds_created=int(tick>=15),
                             seeds_expired=int(outcome == "expired" and removed)))
        reference = [{**row, "seed_bank": len(row["seeds"]), "plant_slots": len(row["plants"])} for row in rows]
        path = root / "synthetic.gz"
        pack(path, rows)
        result = audit.analyze(path, reference, 1)
        seed = result["seeds"][0]
        assert seed["outcome"] == outcome and seed["birth_tick"] == 15
        assert seed["first_actual_open_tick"] is None
        if outcome != "germinated":
            assert seed["first_any_open_tick"] == 135 and seed["first_reachable_open_tick"] == 135
        assert result["cohorts"]["whole"]["full_followup"] == (outcome != "pending")
        assert result["windows"]["whole"]["bright"]["actual_blocker_hist"][1] == 0
        if outcome == "germinated":
            assert seed["child_id"] == 2 and seed["end_tick"] == 135
        if outcome == "pending":
            longer = copy.deepcopy(rows)
            for row in longer:
                row["seed_lifetime_ecology_ticks"] = 8192
                row["climate"] = {"mode": "winter"}
                for site in row["sites"]:
                    site[0] |= 64
                for item in row["seeds"]:
                    item["blockers"] |= 64
            pack(path, longer)
            extended = audit.analyze(path, reference, 1)
            assert extended["seed_lifetime_ecology_ticks"] == 8192
            assert extended["cohorts"]["whole"]["full_followup"] == 0
            assert len(extended["windows"]["whole"]["bright"]["site_blocker_hist"]) == 128
            longer[-1]["seed_lifetime_ecology_ticks"] = 256
            pack(path, longer)
            rejects(lambda: audit.analyze(path, reference, 1))
        for mutation in ("hash", "age", "duplicate", "dispersal", "outcome", "truncate"):
            bad = copy.deepcopy(rows)
            if mutation == "hash":
                bad[1]["hash"] = "ffffffff"
            elif mutation == "age":
                bad[2]["seeds"][0]["age"] += 1
            elif mutation == "duplicate":
                bad[1]["seeds"].append(copy.deepcopy(bad[1]["seeds"][0]))
            elif mutation == "dispersal":
                bad[1]["plants"][0]["dispersal_columns"] = 1 << 10
            elif mutation == "outcome":
                bad[1]["seeds_created"] += 1
            else:
                bad.pop()
            pack(path, bad)
            rejects(lambda: audit.analyze(path, reference, 1))


def integration(args, root):
    bundle = root / "experiment"
    run([sys.executable, Path(experiment.__file__), "--output", bundle, "--cycles", "2",
         "--trials", "1", "--trace-pairs", "1", "--evaluator", args.evaluator, "--inspector", args.inspector])
    manifest_before = (bundle / "manifest.json").read_bytes()
    output = root / "census"
    command = [sys.executable, Path(audit.__file__), "--bundle", bundle, "--output", output,
               "--late-cycles", "1", "--inspector", args.inspector]
    run(command)
    assert (bundle / "manifest.json").read_bytes() == manifest_before
    result = experiment.read_json(output / "summary.json")
    assert len(result["cases"]) == 4
    assert set(result["aggregate"]) == {"adaptive", "neural-reference"}
    assert sum(d["cohorts"]["whole"]["created"] for d in result["aggregate"].values()) > 0
    run([sys.executable, output / "tools/garden_establishment.py", "--verify", output])
    run(command, 1)
    run([*command[:-1], args.inspector, "--output", root / "bad-window", "--late-cycles", "3"], 1)
    native = [args.inspector, "-", "rainfed", "adaptive", "0x1234", "--seed-sites"]
    for flags in (["--ticks", "1"], ["--root-first", "1"], ["--night-wait", "1"], ["--seed-sites"]):
        run([*native, *flags], 2)
    plain = [json.loads(line) for line in run([args.inspector, "-", "rainfed", "adaptive", "0x1234",
                                              "--ecology", "--ticks", "3840"]).splitlines()]
    sites = [json.loads(line) for line in run([*native, "--ticks", "3840"]).splitlines()]
    assert [r["hash"] for r in plain if r["type"] == "world"] == [r["hash"] for r in sites]
    changed = output / "analyses/01.json"
    changed.write_text("{}")
    run([sys.executable, output / "tools/garden_establishment.py", "--verify", output], 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspector", type=Path, required=True)
    parser.add_argument("--evaluator", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="garden-sites-test-") as temporary:
        root = Path(temporary)
        synthetic(root)
        integration(args, root)
    print("PASS: seed census, follow-up cohorts, opportunity maps, frozen replay, and failure handling")


if __name__ == "__main__":
    main()
