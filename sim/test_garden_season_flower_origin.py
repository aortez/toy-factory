#!/usr/bin/env python3
"""Isolated origin, exact prefix, inherited gates and portable evidence checks."""

import argparse
import copy
import gzip
import itertools
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import garden_season_flower_origin as trial

CC = BASE = FLOWER = None


def prefix():
    seed = {"parent": 1, "generation": 1, "species": "flower", "column": 4, "age": 0, "blockers": 1}
    before = {"tick": 60, "hash": "12345678", "plants": [{"id": 1, "dead": False}],
              "nodes": 4, "seeds": [seed], "seeds_created": 1}
    after = copy.deepcopy(before)
    after.update(hash="87654321", seed_origin=trial.ORIGIN)
    after["seeds"][0].update(column=12, blockers=37)
    return before, after


class OriginTests(unittest.TestCase):
    def test_first_difference_is_only_new_seed_placement(self):
        a, b = prefix()
        event = trial.first_difference(a, b, [], [], [], [])
        self.assertEqual(event["seeds"], [{"parent": 1, "base_column": 4, "flower_column": 12}])
        for mutate in (lambda w: w.update(nodes=5), lambda w: w.update(tick=75),
                       lambda w: w.update(hash=a["hash"]), lambda w: w.pop("seed_origin"),
                       lambda w: w.update(seed_origin="base"), lambda w: w.update(seeds_created=2),
                       lambda w: w["seeds"].clear(), lambda w: w["seeds"][0].update(age=1),
                       lambda w: w["seeds"][0].update(parent=2), lambda w: w["seeds"][0].update(column=28),
                       lambda w: w["seeds"][0].update(column=4), lambda w: w["plants"][0].update(dead=True)):
            changed = copy.deepcopy(b)
            mutate(changed)
            with self.assertRaises(RuntimeError):
                trial.first_difference(a, changed, [], [], [], [])
        for old_bids, new_bids, old_deaths, new_deaths in (([1], [], [], []), ([], [], [], [1])):
            with self.assertRaises(RuntimeError):
                trial.first_difference(a, b, old_bids, new_bids, old_deaths, new_deaths)
        for w in (a, b):
            w["seeds"][0]["age"] = 1
        with self.assertRaises(RuntimeError):
            trial.first_difference(a, b, [], [], [], [])

    def test_old_seed_cannot_change_or_have_rewritten_blockers(self):
        a, b = prefix()
        old = {"parent": 2, "generation": 1, "species": "flower", "column": 20, "age": 8, "blockers": 32}
        for w in (a, b):
            w["seeds"].insert(0, copy.deepcopy(old))
        self.assertEqual(len(trial.first_difference(a, b, [], [], [], [])["seeds"]), 1)
        b["seeds"][0]["blockers"] = 0
        with self.assertRaises(RuntimeError):
            trial.first_difference(a, b, [], [], [], [])

    def test_shared_incumbents_not_reused_descendant_ids(self):
        p = {"id": 1, "parent": 0, "birth_tick": 0, "death_tick": 120, "species": "flower"}
        arms = {a: {"outcome": {"history": {"plants": [
            {**p, "death_tick": death}, {**p, "id": 2, "birth_tick": 75, "parent": parent}]}}}
                for a, death, parent in (("base", 120, 1), ("flower", 90, 999))}
        a, b = prefix()
        result = trial.incumbent_pairs(arms, trial.first_difference(a, b, [], [], [], []))
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["earlier"])
        self.assertEqual((result[0]["base_death"], result[0]["flower_death"]), (120, 90))
        with self.assertRaises(RuntimeError):
            trial.analysis([])

    def test_host_guard_and_isolation(self):
        if CC is None:
            self.skipTest("compiler not supplied")
        for device, wide, incompatible in itertools.product((False, True), (False, True),
                (None, "SEASONAL_SEED_BANK", "WATER_HEADROOM", "COMBINED_EXPERIMENT")):
            flags = ["-DTOY_FACTORY_GARDEN_FLOWER_DISPERSAL=1"]
            if device:
                flags.append("-D__ZEPHYR__=1")
            if wide:
                flags.append("-DTOY_FACTORY_GARDEN_WIDE_DISPERSAL=1")
            if incompatible:
                flags.append("-DTOY_FACTORY_GARDEN_" + incompatible + "=1")
            run = subprocess.run([CC, "-std=c11", "-Werror", "-fsyntax-only", "-I", str(trial.ROOT / "src"),
                *flags, "-xc", "-"], input='#include "garden_world.h"\n', text=True, capture_output=True, timeout=30)
            self.assertEqual(run.returncode == 0, not device and incompatible is None, run.stderr)
        for incompatible in ("SEASONAL_SEED_BANK", "WATER_HEADROOM", "COMBINED_EXPERIMENT"):
            with tempfile.TemporaryDirectory() as tmp:
                run = subprocess.run(["cmake", "-S", str(trial.ROOT / "sim"), "-B", tmp,
                    "-DTOY_FACTORY_GARDEN_FLOWER_DISPERSAL=ON", "-DTOY_FACTORY_GARDEN_" + incompatible + "=ON"],
                    text=True, capture_output=True, timeout=30)
                self.assertNotEqual(run.returncode, 0)
                self.assertIn("Flower dispersal is an isolated", run.stderr)

    def test_native_pair_metadata_sizes_and_repeatability(self):
        if BASE is None or FLOWER is None:
            self.skipTest("paired builds not supplied")
        self.assertEqual(trial.capacity.sizes(BASE), trial.capacity.sizes(FLOWER))
        rows = []
        for build, arm in ((BASE, "base"), (FLOWER, "flower")):
            args = [build / "toy-factory-garden-inspect", "-", "rainfed", "baseline", "123", "--ticks", "7680",
                    "--climate", "seasonal", "--death-audit", "--seedling-reserve", "all"]
            raw = subprocess.check_output(list(map(str, args)), timeout=30)
            self.assertEqual(raw, subprocess.check_output(list(map(str, args)), timeout=30))
            worlds = [json.loads(line) for line in raw.splitlines()]
            worlds = [w for w in worlds if w["type"] == "world"]
            self.assertTrue(all(w.get("seed_origin") == (trial.ORIGIN if arm == "flower" else None) for w in worlds))
            rows.append(worlds)
            replay = [build / "toy-factory-garden-replay", "-", "rainfed", "baseline", "123", "--ticks", "7680",
                      "--climate", "seasonal", "--seedling-reserve", "all"]
            end = json.loads(subprocess.check_output(list(map(str, replay)), timeout=30))
            self.assertEqual(end["hash"], worlds[-1]["hash"])
            self.assertEqual(end.get("seed_origin"), trial.ORIGIN if arm == "flower" else None)
        changed = [(a, b) for a, b in zip(*rows) if a["hash"] != b["hash"]]
        self.assertTrue(changed)
        trial.first_difference(*changed[0], [], [], [], [])

    def test_portable_evidence_recomputes_without_native_calls(self):
        folder = trial.ROOT / "benchmarks/garden-seasons"
        path = folder / "flower-origin-histories.json.gz"
        if not path.exists():
            self.skipTest("screen not collected yet")
        with patch("subprocess.Popen", side_effect=AssertionError("portable check ran native code")):
            report = json.loads(gzip.decompress(path.read_bytes()))
            prior = trial.diagnosis.load_input()
            trial.validate_report(report, prior)
            self.assertEqual(trial.compact(report), json.loads((folder / "flower-origin-summary.json").read_text()))
            for field in ("traces", "exact_prefix_worlds", "incumbents", "frames"):
                bad = copy.deepcopy(report["cases"][0])
                bad[field] = {} if field == "traces" else 0 if field == "exact_prefix_worlds" else []
                with self.assertRaises((RuntimeError, KeyError)):
                    trial.validate_case(bad, prior["cases"][0])
            self.assertEqual(len(report["cases"]), 32)
            self.assertEqual(set(report["analysis"]["groups"]), set(trial.ARMS))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cc")
    parser.add_argument("--base", type=Path)
    parser.add_argument("--flower", type=Path)
    args, rest = parser.parse_known_args()
    CC, BASE, FLOWER = args.cc, args.base, args.flower
    unittest.main(argv=[__file__, *rest])
