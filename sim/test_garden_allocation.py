#!/usr/bin/env python3
"""Allocation ledger, censoring, provenance and opt-in native CLI guards."""
import argparse
import copy
from pathlib import Path
import subprocess
import sys
import unittest

import garden_allocation as allocation


def fixture():
    spec = allocation.SPECS[0]
    rows = [{"stage": "checkpoint", "tick": spec["birth"] - 15, "plant": None}]
    for tick in range(spec["birth"], spec["end"] + 1, 15):
        age = (tick - spec["birth"]) // 15 + 1
        income = int(tick % 60 == 0 and age > 1)
        p = {"id": spec["lineage"], "parent": 1, "generation": 1, "species": "shrub", "dead": False,
            "age_ecology_ticks": age, "energy": 64, "water": 24, "energy_income": income,
            "water_income": income, "nodes": 4, "roots": 2, "active_leaves": 0, "offspring": 0,
            "flags": 0, "vigor": 0, "reproduction_cooldown": 0, "leaf": {"renewals": 0},
            "agent": {"decisions": age, "extend": 0, "root_extend": 0, "shoot_extend": 0,
                      "finish": 0, "wait": age}}
        rows.append({"stage": "ecology", "tick": tick, "hash": "12345678", "plant": p,
            "sun_phase": (64 + tick // 15) % 256, "manual_actions": 0, "auto_actions": 0,
            "living": 1, "births": 0, "deaths": 0, "new_children": []})
    return spec, rows


class AllocationTests(unittest.TestCase):
    def test_predeclared_cases(self):
        self.assertEqual(len(allocation.SPECS), 6)
        self.assertEqual(len({s["name"] for s in allocation.SPECS}), 6)
        for s in allocation.SPECS:
            self.assertEqual(s["birth"] % 15, 0)
            self.assertEqual(s["end"] - s["birth"], 8 * allocation.DAY)

    def test_dawn_and_censoring(self):
        dawn = 2880
        self.assertEqual(allocation.dawn_tick(dawn), dawn + allocation.DAY)
        self.assertEqual(allocation.dawn_tick(dawn - 15), dawn)
        self.assertEqual(allocation.followup(None, 100, 99), "horizon-censored")
        self.assertEqual(allocation.followup(None, 100, 100), "alive")
        for cause in ("energy", "water", "both", "patch"):
            death = {"tick": 100, "cause": cause}
            self.assertEqual(allocation.followup(death, 99, 101), "alive")
            self.assertEqual(allocation.followup(death, 100, 101),
                             "patch-censored" if cause == "patch" else cause)

    def test_identity_rejects_different_models_environments_and_checkpoints(self):
        spec = allocation.SPECS[0]
        meta = {"type": "identity", "rule": allocation.RULE, "seed": spec["seed"],
            "growth": spec["growth"], "root_after": spec["root_after"], "lineage": spec["lineage"],
            "birth": spec["birth"], "end": spec["end"], "checkpoint_tick": spec["birth"] - 15,
            "checkpoint_hash": "12345678", "reference_crc32": "dc5e849d", "candidate_crc32": "87654321",
            "node_capacity": 512, "seed_capacity": spec["bank"], "patch_seed": "e4d65e6f",
            "seed_reserve_rule": "sunset-seed-reserve-v1", "leaf_policy": "selective",
            "water_uptake": "headroom-v1", "seed_dispersal": "wide-v1", "scenario": "rainfed-crowded",
            "gardener": False, "drainage": False}
        allocation.validate_identity(meta, spec, "12345678", "87654321")
        for key in meta:
            with self.assertRaises(RuntimeError, msg=key):
                allocation.validate_identity(meta | {key: None}, spec, "12345678", "87654321")

    def test_live_ledger_and_wait_is_not_a_score(self):
        spec, rows = fixture()
        result = allocation.analyze_arm(rows, spec)
        self.assertEqual(result["followup"]["day8"], "alive")
        self.assertEqual(result["actions"]["wait"], 2049)
        self.assertEqual(result["peak_active_leaves"], 0)
        self.assertEqual(result["seeds_created"], 0)
        self.assertNotIn("fitness", result)
        self.assertEqual(result["budget"]["water_income"], result["budget"]["water_upkeep"])

    def test_corrupt_ledger_cadence_birth_and_gardener(self):
        spec, fixture_rows = fixture()
        for change in ("water", "missing", "order", "age", "target", "gardener", "truncated"):
            rows = copy.deepcopy(fixture_rows)
            if change == "water": rows[2]["plant"]["water"] += 1
            if change == "missing": rows.pop(2)
            if change == "order": rows[2:4] = reversed(rows[2:4])
            if change == "age": rows[1]["plant"]["age_ecology_ticks"] = 2
            if change == "target": rows[1]["plant"]["id"] += 1
            if change == "gardener": rows[1]["auto_actions"] = 1
            if change == "truncated": rows.pop()
            with self.assertRaises(RuntimeError, msg=change): allocation.analyze_arm(rows, spec)

    def test_death_clearing_not_debited(self):
        spec, rows = fixture()
        index = 4
        tick = rows[index]["tick"]
        for row in rows[index:]:
            row["plant"].update(dead=True, flags=5, water=0, energy=0, water_income=0, energy_income=0)
        result = allocation.analyze_arm(rows, spec)
        self.assertEqual(result["death"]["tick"], tick)
        self.assertIsNone(result["death"]["terminal_step_budget"])
        self.assertEqual(result["last_alive"]["plant"]["water"], 24)
        self.assertEqual(result["live_steps_checked"], index - 1)
        # A seed can germinate after its parent has been reclaimed. The parent's
        # disappearing offspring counter is not a complete child census.
        for row in rows[index + 1:]:
            row["plant"] = None
        rows[-1]["new_children"] = [spec["lineage"] + 1]
        result = allocation.analyze_arm(rows, spec)
        self.assertEqual(result["children_germinated"], 1)
        rows[-2]["new_children"] = rows[-1]["new_children"]
        with self.assertRaises(RuntimeError): allocation.analyze_arm(rows, spec)
        rows[-2]["new_children"] = []
        rows[-1]["plant"] = copy.deepcopy(rows[index]["plant"])
        rows[-1]["plant"]["dead"] = False
        with self.assertRaises(RuntimeError): allocation.analyze_arm(rows, spec)


def cli(build):
    binary = build / "toy-factory-garden-allocation"
    cache = (build / "CMakeCache.txt").read_text()
    if "TOY_FACTORY_GARDEN_SEED_RESERVE:BOOL=ON" not in cache:
        # A stale experimental binary could exist in reused builds; only a fresh
        # seed-reserve build exposes the target. Do not invoke an old executable.
        return
    assert binary.is_file()
    help_result = subprocess.run([binary, "--help"], capture_output=True, text=True, timeout=10)
    assert help_result.returncode == 0 and "Fork one seedling" in help_result.stdout
    valid = ["missing.tgm", "missing.tgm", "0x1234", "reserve", "0", "65", "617805", "648525", "-"]
    for index, value in ((2, "0"), (2, "-1"), (3, "adaptive"), (4, "1"), (4, "614415"),
                         (5, "0"), (6, "617806"), (6, "614400"), (7, "648526"),
                         (7, "4294967296"), (8, "")):
        args = valid.copy()
        args[index] = value
        result = subprocess.run([binary, *args], capture_output=True, timeout=10)
        assert result.returncode == 2, (args, result.stderr)
    result = subprocess.run([binary, *valid], capture_output=True, timeout=10)
    assert result.returncode == 1 and not result.stdout
    print("Native allocation opt-in/CLI/model failure guards passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    args, remaining = parser.parse_known_args()
    program = unittest.main(argv=[__file__, *remaining], exit=False)
    if not program.result.wasSuccessful():
        sys.exit(1)
    if args.build:
        cli(args.build.resolve())
