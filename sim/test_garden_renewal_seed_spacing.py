#!/usr/bin/env python3
"""Spacing receipts, shared-audit defaults, root ordering and native boundaries."""
import argparse
import copy
from pathlib import Path
import subprocess
import unittest
from unittest import mock

import garden_renewal_seed_spacing as trial

BUILD = None
CC = None


def metadata(tick):
    return {"rule": trial.NATIVE, "after": trial.AFTER, "minimum": 2 if tick > trial.AFTER else 3}


class SeedSpacingTests(unittest.TestCase):
    def test_fixed_inventory(self):
        calls = trial.commands()
        self.assertEqual(len(calls), 20)
        self.assertEqual(len({p for p, _ in calls}), 20)
        self.assertEqual(sum(p.endswith(".gz") for p, _ in calls), 8)
        self.assertEqual(trial.FRAMES, (69120, 72960, 245760))
        for index, (path, command) in enumerate(calls):
            self.assertIn("/control." if index < 10 else "/two.", path)
            self.assertEqual("--seed-spacing" in command, index >= 10)
            self.assertEqual(command[command.index("--seed-order")+1], "rotating")
            self.assertEqual(command[command.index("--dawn-finish")+1], "reserve")

    def test_spacing_metadata_and_boundary(self):
        for tick in (0, 69119, 69120, 69121, 69135, 245760):
            self.assertEqual(trial.minimum({"tick": tick}, "control"), 3)
            row = {"tick": tick, "seed_spacing": metadata(tick)}
            self.assertEqual(trial.minimum(row, "two"), 2 if tick > 69120 else 3)
            with self.assertRaises(RuntimeError): trial.minimum(row, "control")
            for field in ("rule", "after", "minimum"):
                bad = copy.deepcopy(row)
                bad["seed_spacing"][field] = "wrong"
                with self.assertRaises(RuntimeError): trial.minimum(bad, "two")
            with self.assertRaises(RuntimeError): trial.minimum({"tick": tick}, "two")
        with self.assertRaises(RuntimeError): trial.minimum({"tick": -1}, "control")

    def test_prefix_strips_only_spacing(self):
        control = [{"type": "world", "tick": t, "hash": "same"} for t in (69105, 69120)]
        candidate = [{**r, "seed_spacing": metadata(r["tick"])} for r in control]
        original = copy.deepcopy(candidate)
        self.assertEqual(trial.check_prefix(control, candidate), 2)
        self.assertEqual(candidate, original)
        for key in ("hash", "seed_order"):
            bad = copy.deepcopy(candidate)
            bad[0][key] = "changed"
            with self.assertRaises(RuntimeError): trial.check_prefix(control, bad)
        with self.assertRaises(RuntimeError): trial.check_prefix(control, candidate[:1])

    def test_spatial_geometry_requires_explicit_override(self):
        plants = [{"id": i, "column": c, "dead": False} for i, c in enumerate((0, 4, 8, 13, 18, 23, 27))]
        row = {"plants": plants, "sites": [[32 if any(abs(c-p["column"]) < 2 for p in plants) else 0, 255, 255]
                                         for c in range(28)]}
        before = copy.deepcopy(row)
        result = trial.gap.panel.competition.spatial_snapshot(row, minimum_spacing=2)
        self.assertEqual(result["all_columns_spacing_blocked"], 0)
        self.assertEqual(sum(not s[0] & 32 for s in row["sites"]), 9)
        self.assertEqual(row, before)
        with self.assertRaises(RuntimeError): trial.gap.panel.competition.spatial_snapshot(row)
        for invalid in (1, 4, True, "2"):
            with self.assertRaises(RuntimeError):
                trial.gap.panel.competition.spatial_snapshot(row, minimum_spacing=invalid)
        record = {"birth_tick": 0}
        seed = {"column": 2, "blockers": 0}
        world = {"tick": 120, "plants": plants, "nodes": 28}
        self.assertEqual(trial.gap.ledger.snapshot(world, seed, record, minimum_spacing=2)["spacing_occupants"], [])
        with self.assertRaises(RuntimeError): trial.gap.ledger.snapshot(world, seed, record)

    def test_root_exposure_preserves_original_order_and_uses_old_roots(self):
        a = {"id": 1, "dead": False, "root_cells": [[4, 0, 1, 20], [6, 0, 2, 20]]}
        b = {"id": 2, "dead": False, "root_cells": [[4, 0, 1, 20], [5, 0, 1, 20]]}
        previous = {"plants": [a, b]}
        current = copy.deepcopy(previous)
        current["plants"][1]["root_cells"][0][3] = 0
        current["plants"][1]["root_cells"].append([6, 0, 2, 0])
        before = copy.deepcopy((previous, current))
        result = trial.root_exposure(previous, current, 2)
        self.assertEqual(result, {"uptake_steps": 1, "array_rank_1": 1, "shared_root_steps": 1,
                                 "shared_cell_samples": 1, "shared_dry_poststep_samples": 1,
                                 "earlier_competitor_samples": 1})
        self.assertEqual((previous, current), before)
        self.assertEqual(trial.root_exposure(previous, current, 3), {"uptake_steps": 0})
        previous["plants"].reverse()
        self.assertEqual(trial.root_exposure(previous, current, 2)["earlier_competitor_samples"], 0)
        previous["plants"][1]["dead"] = True
        self.assertEqual(trial.root_exposure(previous, current, 2)["shared_cell_samples"], 0)

    def test_seed_ledger_keeps_birth_order_separate_from_purchase_order(self):
        records = {i: {"id": i, "parent": 0 if i < 3 else i-2, "generation": int(i > 2),
                      "species": "flower", "column": {1: 0, 2: 27, 3: 4, 4: 8}[i],
                      "birth_tick": 0 if i < 3 else 135, "seeds_created": int(i < 3),
                      "late_seeds_created": 0} for i in range(1, 5)}
        rows = []
        for tick in range(0, 136, 15):
            ids = (1, 2, 3, 4) if tick == 135 else (1, 2)
            plants = [{**records[i], "dead": False, "reproduction_cooldown": 16 if tick == 15 else 0} for i in ids]
            # Purchases visit parent 2 then 1; the seed loop creates IDs 3 then 4.
            if tick == 135:
                plants[2]["parent"], plants[2]["column"] = 2, 8
                plants[3]["parent"], plants[3]["column"] = 1, 4
            seeds = [{"parent": p, "generation": 1, "column": 8 if p == 2 else 4,
                      "blockers": 1} for p in (2, 1)] if 15 <= tick < 135 else []
            rows.append({"type": "world", "tick": tick, "plants": plants, "seeds": seeds,
                         "nodes": 4*len(ids), "births": 2 if tick == 135 else 0,
                         "seeds_created": 2 if tick else 0, "seeds_expired": 0})
        records[3].update(parent=2, column=8)
        records[4].update(parent=1, column=4)
        original = copy.deepcopy(rows)
        ledger = trial.gap.ledger.seed_ledger(rows, {}, records, end=135,
                    reproduction_order=lambda r: list(reversed(r["plants"])))
        self.assertEqual([(s["parent"], s["child_id"]) for s in ledger["seeds"]], [(2, 3), (1, 4)])
        self.assertEqual(rows, original)
        with self.assertRaises(RuntimeError): trial.gap.ledger.seed_ledger(rows, {}, records, end=135)
        with self.assertRaises(RuntimeError):
            trial.gap.ledger.seed_ledger(rows, {}, records, end=135, reproduction_order=lambda r: r["plants"][:1])

    def test_analysis_recovery_never_invokes_native(self):
        with mock.patch.object(trial, "check_capture", side_effect=RuntimeError("stop")), \
                mock.patch.object(trial.experiment, "command_run") as run:
            with self.assertRaises(RuntimeError): trial.finish(Path("/missing-spacing-fixture"))
            run.assert_not_called()

    def test_historical_comparison_normalizes_only_witness_set_order(self):
        a = {"parent": 1, "birth_tick": 10, "first_mature": {"blockers": 32,
             "spacing_occupants": [{"id": 6, "dead": False}, {"id": 5, "dead": False}]},
             "last_snapshot": None}
        b = copy.deepcopy(a)
        b["first_mature"]["spacing_occupants"].reverse()
        original = copy.deepcopy((a, b))
        self.assertEqual(trial.canonical_seed(a), trial.canonical_seed(b))
        self.assertEqual((a, b), original)
        b["first_mature"]["spacing_occupants"][0]["dead"] = True
        self.assertNotEqual(trial.canonical_seed(a), trial.canonical_seed(b))
        b = copy.deepcopy(a)
        b["first_mature"]["blockers"] = 34
        self.assertNotEqual(trial.canonical_seed(a), trial.canonical_seed(b))

    def test_native_cli_rejects_malformed_or_out_of_scope(self):
        if BUILD is None: self.skipTest("requires --build")
        for tool in ("inspect", "replay"):
            base = [str(BUILD/("toy-factory-garden-"+tool)), "-", "rainfed", "adaptive", "123", "--ticks", "15"]
            for options in (["--seed-spacing"], ["--seed-spacing", "bad"], ["--seed-spacing", "3"],
                            ["--seed-spacing", "2"], ["--seed-spacing", "2", "--seed-spacing", "2"],
                            ["--seed-spacing", "2", "--seed-order", "rotating"]):
                result = subprocess.run([*base, *options], capture_output=True)
                self.assertEqual(result.returncode, 2, (tool, options, result.stderr))
                self.assertEqual(result.stdout, b"")

    def test_header_excludes_firmware_and_missing_dependencies(self):
        if CC is None: self.skipTest("requires --cc")
        header = b'#include "garden_seed_spacing.h"\n'
        options = ["-DTOY_FACTORY_GARDEN_SEED_SPACING=1", "-DTOY_FACTORY_GARDEN_SEED_ORDER=1"]
        for flags, valid in ((options, True), ([], False), (options[:1], False), (options+["-D__ZEPHYR__"], False)):
            result = subprocess.run([CC, "-x", "c", "-fsyntax-only", "-I", str(trial.experiment.ROOT/"src"),
                                     *flags, "-"], input=header, capture_output=True)
            self.assertEqual(result.returncode == 0, valid, result.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    parser.add_argument("--cc")
    args, remaining = parser.parse_known_args()
    BUILD = args.build.resolve() if args.build else None
    CC = args.cc
    unittest.main(argv=[__file__, *remaining])
