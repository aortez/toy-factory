#!/usr/bin/env python3
"""Capacity isolation, fixed acceptance gates, exact prefix and portable evidence."""

import argparse
import copy
import gzip
import itertools
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import garden_season_seed_bank_capacity as trial
from test_garden_season_reproduction_funnel import plant, seed, world

EIGHT = SIXTEEN = CC = None


class CapacityTests(unittest.TestCase):
    def test_explicit_capacity_and_exact_sixteenth_seed_boundary(self):
        for capacity in (0, 7, 9, 17, True, 16.0):
            with self.assertRaises(RuntimeError):
                trial.population.Audit(True, capacity)
            with self.assertRaises(RuntimeError):
                trial.funnel.SeedLedger(capacity)
        ledger = trial.funnel.SeedLedger(16)
        for tick in range(0, 316, 15):
            parents = [plant(i + 1, column=i) for i in range(8)]
            seeds = ([seed(tick, i + 1, i, 60) for i in range(8)] if tick >= 60 else [])
            if tick >= 300:
                seeds += [seed(tick, i + 1, i, 300) for i in range(8)]
            if tick in (60, 300):
                for p in parents:
                    p["reproduction_cooldown"] = 16
            row = {**world(tick, parents, seeds, len(seeds)), "seed_capacity": 16}
            ledger.accept(row)
            if tick == 0:
                with self.assertRaises(RuntimeError):
                    trial.funnel.SeedLedger().accept(row)
        self.assertEqual(len(ledger.result(315)["seeds"]), 16)
        row = copy.deepcopy(row)
        row["tick"] = 330
        row["seeds"].append(copy.deepcopy(row["seeds"][0]))
        with self.assertRaises(RuntimeError):
            ledger.accept(row)

    def test_prefix_requires_extra_capacity_not_other_changes(self):
        before = {"tick": 60, "plants": [{"id": 1, "parent": 0, "species": "flower", "generation": 0, "dead": False}],
                  "seeds": [{"parent": 1, "age": i} for i in range(8)], "seeds_created": 8,
                  "births": 0, "deaths": 0, "nodes": 4, "seeds_expired": 0}
        after = {**copy.deepcopy(before), "seed_capacity": 16, "seeds_created": 9}
        after["seeds"].append({"parent": 1, "age": 0})
        self.assertEqual(trial.first_difference(before, after, [], [], [], [])["tick"], 60)
        for mutate in (lambda r: r.update(tick=75), lambda r: r.update(seed_capacity=8),
                       lambda r: r["seeds"].pop(), lambda r: r["seeds"][-1].update(age=1),
                       lambda r: r["seeds"][0].update(parent=2), lambda r: r.update(nodes=5),
                       lambda r: r.update(seeds_created=10), lambda r: r["plants"][0].update(id=2)):
            changed = copy.deepcopy(after)
            mutate(changed)
            with self.assertRaises(RuntimeError):
                trial.first_difference(before, changed, [], [], [], [])
        with self.assertRaises(RuntimeError):
            trial.first_difference(before, after, [], ["changed bid"], [], [])

    def test_acceptance_requires_durable_gain_not_just_seed_or_birth_counts(self):
        before = {"closing_durable_parents": 6, "closing_survivors": 55, "closing_eligible": 62,
                  "historical_durable_parents": 285, "multi_living_species_worlds": 0}
        outcome = {"first_empty_tick": None, "history": {"daily": [{"living": 2, "viable_species": ["flower"]}]}}
        cases = [{"arms": {a: {"outcome": copy.deepcopy(outcome)} for a in trial.CAPACITIES}}]
        self.assertFalse(trial.gates(before, {**before, "seeds_created": 99999, "births": 9999}, cases)
                         ["improve_closing_durable_parents"])
        after = {**before, "closing_durable_parents": 7}
        self.assertTrue(all(trial.gates(before, after, cases).values()))
        for key, value in (("closing_survivors", 54), ("closing_eligible", 63),
                           ("historical_durable_parents", 284)):
            self.assertFalse(all(trial.gates(before, {**after, key: value}, cases).values()))
        changed = copy.deepcopy(cases)
        changed[0]["arms"]["sixteen"]["outcome"]["first_empty_tick"] = 15
        self.assertFalse(trial.gates(before, after, changed)["no_new_empty_world"])
        changed[0]["arms"]["sixteen"]["outcome"]["history"]["daily"][0]["viable_species"] = []
        self.assertFalse(trial.gates(before, after, changed)["retain_viable_species_each_world"])
        with self.assertRaises(RuntimeError):
            trial.analysis([])

    def test_post_step_occupancy_and_no_post_divergence_lineage_matching(self):
        counts = trial.occupancy()
        trial.add_occupancy(counts, {"tick": 0, "seeds": [None] * 16}, 16)
        trial.add_occupancy(counts, {"tick": 15, "seeds": [None] * 8}, 16)
        trial.add_occupancy(counts, {"tick": 112 * trial.DAY + 15, "seeds": [None] * 16}, 16)
        self.assertEqual(counts["whole"]["histogram"], {"8": 1, "16": 1})
        self.assertEqual(counts["closing"]["samples"], 1)
        p = {"id": 1, "parent": 0, "birth_tick": 0, "death_tick": 120, "species": "flower"}
        new = {**p, "death_tick": 90}
        # ID 2 is deliberately different in each history after the split.
        arms = {a: {"outcome": {"history": {"plants": [q, {**q, "id": 2, "birth_tick": 75, "parent": parent}]}}}
                for a, q, parent in (("eight", p, 1), ("sixteen", new, 99))}
        difference = {"tick": 60, "eight": {"plants": [{"id": 1, "dead": False}]}}
        result = trial.incumbent_pairs(arms, difference)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["earlier"])

    def test_build_guards_defaults_and_forbidden_combinations(self):
        if CC is None:
            self.skipTest("compiler not supplied")
        for enabled, wide, device, incompatible in itertools.product((False, True), repeat=4):
            flags = []
            if enabled:
                flags.append("-DTOY_FACTORY_GARDEN_SEASONAL_SEED_BANK=1")
            if wide:
                flags.append("-DTOY_FACTORY_GARDEN_WIDE_DISPERSAL=1")
            if device:
                flags.append("-D__ZEPHYR__=1")
            if incompatible:
                flags += ["-DTOY_FACTORY_GARDEN_WATER_HEADROOM=1"]
            expected = (not (device and (enabled or wide or incompatible))
                        and not (incompatible and (enabled or wide)))
            code = '#include "garden_world.h"\n_Static_assert(PICOSYSTEM_GARDEN_MAX_SEEDS == ' + (
                    "16" if enabled else "8") + ', "capacity");\n'
            run = subprocess.run([CC, "-std=c11", "-Werror", "-fsyntax-only", "-I", str(trial.ROOT / "src"),
                *flags, "-xc", "-"], input=code, text=True, capture_output=True, timeout=30)
            self.assertEqual(run.returncode == 0, expected, run.stderr)
        helper = trial.ROOT / "scripts/container/host-garden-defaults.sh"
        defaults = subprocess.check_output(["bash", "-eu", "-c",
            'source "$1"; printf "%s\\n" "${garden_default_cmake_options[@]}"', "defaults", str(helper)], text=True).splitlines()
        options = set(re.findall(r"option\((TOY_FACTORY_GARDEN_\w+)", (trial.ROOT / "sim/CMakeLists.txt").read_text()))
        self.assertEqual(set(defaults), {"-D" + name + "=OFF" for name in options})
        with tempfile.TemporaryDirectory() as tmp:
            run = subprocess.run(["cmake", "-S", str(trial.ROOT / "sim"), "-B", tmp,
                "-DTOY_FACTORY_GARDEN_SEASONAL_SEED_BANK=ON", "-DTOY_FACTORY_GARDEN_COMBINED_EXPERIMENT=ON"],
                text=True, capture_output=True, timeout=30)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn("Seasonal seed bank is isolated", run.stderr)

    def test_native_sizes_metadata_and_prefix(self):
        if EIGHT is None or SIXTEEN is None:
            self.skipTest("paired builds not supplied")
        sizes = [trial.sizes(b) for b in (EIGHT, SIXTEEN)]
        self.assertEqual([s["seed_capacity"] for s in sizes], [8, 16])
        self.assertEqual(sizes[1]["world"] - sizes[0]["world"], 8 * sizes[0]["seed"])
        self.assertEqual(sizes[1]["garden_snapshot"] - sizes[0]["garden_snapshot"], 8 * sizes[0]["snapshot_seed"])
        traces = []
        for build, capacity in ((EIGHT, 8), (SIXTEEN, 16)):
            command = [build / "toy-factory-garden-inspect", "-", "rainfed", "baseline", "123",
                       "--ticks", str(16 * trial.DAY), "--climate", "seasonal", "--death-audit", "--seedling-reserve", "all"]
            raw = subprocess.check_output(list(map(str, command)), timeout=30)
            self.assertEqual(raw, subprocess.check_output(list(map(str, command)), timeout=30))
            rows = [json.loads(line) for line in raw.splitlines()]
            audit, ledger = trial.population.Audit(True, capacity), trial.funnel.SeedLedger(capacity)
            bids, deaths = [], []
            groups = []
            for row in rows:
                if row["type"] == "bid": bids.append(row)
                elif row["type"] == "death": deaths.append(row)
                else:
                    self.assertEqual(row.get("seed_capacity", 8), capacity)
                    audit.accept(row, bids, deaths)
                    ledger.accept(row)
                    groups.append((row, bids, deaths))
                    bids, deaths = [], []
            self.assertEqual(ledger.result(16 * trial.DAY)["worlds"], 4097)
            traces.append(groups)
        changed = False
        for (before, a, b), (after, c, d) in zip(*traces):
            if before != {k: v for k, v in after.items() if k != "seed_capacity"}:
                trial.first_difference(before, after, a, c, b, d)
                changed = True
                break
        self.assertTrue(changed)

    def test_portable_evidence_complete_panel_and_corruption(self):
        folder = trial.ROOT / "benchmarks/garden-seasons"
        path = folder / "seed-bank-capacity-histories.json.gz"
        if not path.exists():
            self.skipTest("capacity screen not collected yet")
        report = json.loads(gzip.decompress(path.read_bytes()))
        prior, _ = trial.inputs()
        trial.validate_report(report, prior)
        self.assertEqual(trial.compact(report), json.loads((folder / "seed-bank-capacity-summary.json").read_text()))
        for cases in (report["cases"][:-1], report["cases"][:-1] + [report["cases"][0]]):
            with self.assertRaises(RuntimeError):
                trial.analysis(cases)
        for mutate in (lambda c: c["arms"]["sixteen"].update(capacity=8),
                       lambda c: c["arms"]["sixteen"]["ledger"]["seeds"].pop(),
                       lambda c: c["arms"]["sixteen"]["occupancy"]["closing"].update(samples=4095),
                       lambda c: c.update(exact_prefix_worlds=0), lambda c: c["incumbents"].pop()):
            c = copy.deepcopy(report["cases"][0])
            mutate(c)
            with self.assertRaises(RuntimeError):
                trial.validate_case(c, prior["cases"][0])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--eight", type=Path)
    parser.add_argument("--sixteen", type=Path)
    parser.add_argument("--cc")
    args, rest = parser.parse_known_args()
    EIGHT = args.eight.resolve() if args.eight else None
    SIXTEEN = args.sixteen.resolve() if args.sixteen else None
    CC = args.cc
    unittest.main(argv=[__file__] + rest)
