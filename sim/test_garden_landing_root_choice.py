#!/usr/bin/env python3
"""Root-choice identity, no-op compatibility, CLI safety and frozen evidence."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_root_choice as screen
from test_garden_landing_tools import run

BUILD = None


class ContractTests(unittest.TestCase):
    def test_frozen_call_budget_and_independent_targets(self):
        _, world, _, _ = screen.load_inputs()
        calls = [screen.arguments(world, c, a, label) for c in screen.CASES
                 for a in screen.ARMS for label in screen.LABELS]
        self.assertEqual(len(calls), 40)
        self.assertEqual(sum("--root-choice-at" in c for c in calls), 20)
        self.assertEqual(sum("--stand-choice" in c for c in calls), 20)
        self.assertEqual(len({c[c.index("--framebuffer") + 1] for c in calls}), 40)
        for args in calls:
            self.assertNotIn("--vacancy-at", args)
            self.assertNotIn("--node-limit", args)
            self.assertEqual(args[args.index("--shoot-reserve") + 1], "on")

    def test_water_guard_checks_cost_reserve_destination_and_age(self):
        _, _, saved, _ = screen.load_inputs()
        focal = next(p for p in saved["arms"]["rotating"]["analysis"]["children"] if p["life"]["id"] == 48)
        bid = copy.deepcopy(focal["steps"][0]["bids"][1])
        bid["water_gate"] = {"active": True, "allowed": True, "cost": 5, "upkeep": 1,
            "reserve": 1, "wet_root": True, "tip_moisture": 12, "destination": [220, 153, 15]}
        screen.check_water(bid, focal["life"], focal["life"]["birth_tick"])
        for field, value in (("allowed", False), ("cost", 0), ("reserve", 4), ("active", False),
                             ("destination", None), ("wet_root", False)):
            bad = copy.deepcopy(bid)
            bad["water_gate"][field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                screen.check_water(bad, focal["life"], focal["life"]["birth_tick"])

    def test_invalid_hash_config(self):
        self.assertNotEqual(screen.probe_hash("12345678", 15, 1), screen.probe_hash("12345678", 15, 2))
        for tick, lineage in ((0, 1), (16, 1), (15, 0), (15, True)):
            with self.assertRaises(RuntimeError):
                screen.probe_hash("12345678", tick, lineage)


class NativeTests(unittest.TestCase):
    def setUp(self):
        if BUILD is None:
            self.skipTest("pass --build to run native integration tests")
        temporary = tempfile.TemporaryDirectory(prefix="landing-root-choice-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.model = self.root / "model.tgl"
        self.model.write_bytes(screen.load_inputs()[3])
        self.cli = BUILD / "toy-factory-garden-landing"

    def native(self, *args, **kwargs):
        value = run([self.cli, *args], **kwargs)
        return json.loads(value) if value else None

    def args(self):
        return ("placement-replay", self.model, "rainfed-crowded", "0x940cfdc4", "--climate", "seasonal",
                "--ticks", 60, "--ledger", "--shoot-reserve", "on", "--seed-placement", "spacing")

    def test_noop_fingerprint_trace_compatibility_and_pixels(self):
        case = {"tick": 120, "lineage": 45, "order": "fixed"}
        old_path, new_path = self.root / "old.jsonl", self.root / "new.jsonl"
        old_frame, new_frame = self.root / "old.raw", self.root / "new.raw"
        old = self.native(*self.args(), "--stand-trace", old_path, "--stand-start", 15, "--stand-stop", 60,
                          "--stand-order", "--framebuffer", old_frame)
        new = self.native(*self.args(), "--stand-trace", new_path, "--stand-start", 15, "--stand-stop", 60,
                          "--stand-choice", "--framebuffer", new_frame, "--root-choice-at", 120, "--root-choice-lineage", 45)
        self.assertEqual(old, screen.common_result(new, case, "candidate"))
        self.assertEqual(old_frame.read_bytes(), new_frame.read_bytes())
        rows = screen.adults.read_trace(new_path)
        rows[0]["schema"] = "landing-ordered-stand-trace-v1"
        rows[-1]["run_hash"] = old["run_hash"]
        for row in rows[1:-1]:
            for bid in row["bids"]:
                self.assertEqual(bid.pop("raw_priority"), bid["priority"])
                bid.pop("water_gate")
        self.assertEqual(rows, screen.adults.read_trace(old_path))
        for key in ("run_hash", "world_hash"):
            bad = copy.deepcopy(new)
            bad[key] = "00000000"
            if key == "run_hash":
                with self.assertRaises(RuntimeError):
                    screen.common_result(bad, case, "candidate")
            else:
                self.assertNotEqual(old, screen.common_result(bad, case, "candidate"))

    def test_validation_before_files_and_no_clobber(self):
        path = self.root / "trace.jsonl"
        trace = ("--stand-trace", path, "--stand-start", 15, "--stand-stop", 60, "--stand-choice")
        for extra in (("--root-choice-at", 120), ("--root-choice-lineage", 45),
                      ("--root-choice-at", 121, "--root-choice-lineage", 45),
                      ("--root-choice-at", 0, "--root-choice-lineage", 45),
                      ("--root-choice-at", 120, "--root-choice-lineage", 0),
                      ("--root-choice-at", 120, "--root-choice-lineage", 45, "--root-choice-at", 135),
                      ("--stand-order",), ("--stand-choice",)):
            self.native(*self.args(), *trace, *extra, valid=False)
            self.assertFalse(path.exists())
        self.native(*self.args(), "--stand-choice", valid=False)
        self.native(*[v for v in self.args() if v != "--ledger"], *trace,
                    "--root-choice-at", 120, "--root-choice-lineage", 45, valid=False)
        self.assertFalse(path.exists())
        path.write_bytes(b"preserve")
        self.native(*self.args(), *trace, valid=False)
        self.assertEqual(path.read_bytes(), b"preserve")
        with self.assertRaises(RuntimeError):
            screen.collect(BUILD, self.root, self.root)


class FrozenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = screen.ROOT / "benchmarks/garden-seasons/landing-root-choice-results.json.gz"
        if screen.digest(path) != "d29470fc81efc4c111ead315a159bb8e7caac7fb0e2b75f7b7ec0a40c1861b9f":
            raise AssertionError("frozen root-choice results changed")
        with gzip.open(path, "rt") as stream:
            cls.value = json.load(stream)

    def test_offline_reanalysis_never_simulates(self):
        with patch.object(screen.order.training, "native", side_effect=AssertionError("ran simulation")):
            screen.check_value(self.value)

    def test_extra_water_does_not_rescue_energy_starved_seedlings(self):
        for case, expected in zip(self.value["cases"], (None, None, (180, 14), (180, 26), (720, 6)), strict=True):
            a, b = (case["arms"][arm]["analysis"]["focal"] for arm in screen.ARMS)
            if expected is None:
                self.assertIsNone(a["life"]["death_tick"])
                self.assertIsNone(b["life"]["death_tick"])
                self.assertIsNone(b["first_day"]["first_shortage"])
                self.assertEqual(b["steps"][-1]["body"]["roots"], 16)
            else:
                self.assertEqual(a["life"]["death_tick"] - b["life"]["death_tick"], expected[0])
                self.assertEqual(b["first_day"]["death_shortage"], "energy")
                self.assertEqual(b["first_day"]["resources"]["water"]["discarded"], expected[1])
                self.assertGreater(b["first_day"]["resources"]["water"]["income"],
                                   a["first_day"]["resources"]["water"]["income"])
                self.assertEqual(case["arms"]["control"]["runs"]["trace"]["frame"],
                                 case["arms"]["candidate"]["runs"]["trace"]["frame"])

    def test_corrupt_panel_configuration_prefix_budget_and_history_fail(self):
        for fault in ("panel", "calls", "identity", "prefix", "history", "water", "priority", "birth", "repeat", "window"):
            value = copy.deepcopy(self.value)
            arm = value["cases"][0]["arms"]["candidate"]
            if fault == "panel": value["cases"].pop()
            elif fault == "calls": arm["calls"].pop()
            elif fault == "identity": arm["runs"]["trace"]["result"]["root_choice_probe"]["tick"] += 15
            elif fault == "prefix": arm["runs"]["prefix"]["result"]["world_hash"] = "00000000"
            elif fault == "history": arm["analysis"]["focal"]["steps"].pop()
            elif fault == "water": arm["analysis"]["focal"]["steps"][0]["bids"][0]["water_gate"]["cost"] += 1
            elif fault == "priority": arm["analysis"]["priority_changes"] = []
            elif fault == "birth": arm["analysis"]["focal"]["birth_check"][4] += 1
            elif fault == "repeat": arm["runs"]["repeat"]["frame"]["raw_sha256"] = "0" * 64
            else: arm["analysis"]["all_plants"]["gates"]["start"] += 15
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                screen.check_value(value)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve() if args.build else None
    unittest.main(argv=[__file__, *rest])
