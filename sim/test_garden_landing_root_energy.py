#!/usr/bin/env python3
"""Root/energy scope, old-path compatibility and fixed-counterfactual evidence."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_root_energy as screen
from test_garden_landing_tools import run

BUILD = None


class ContractTests(unittest.TestCase):
    def test_fixed_calls_and_identical_root(self):
        _, world, _, _ = screen.load_inputs()
        calls = [screen.arguments(world, case, arm, label) for case in screen.CASES
                 for arm in screen.ARMS for label in screen.LABELS]
        self.assertEqual(len(calls), 40)
        self.assertEqual(sum("--root-choice-at" in c for c in calls), 40)
        self.assertEqual(sum("--root-energy-reserve" in c for c in calls), 20)
        self.assertEqual(sum("--stand-energy" in c for c in calls), 20)
        self.assertEqual(len({c[c.index("--framebuffer") + 1] for c in calls}), 40)
        for case in screen.CASES:
            for arm in screen.ARMS:
                args = screen.arguments(world, case, arm, "prefix")
                self.assertEqual(args[args.index("--ticks") + 1], str(case["tick"]))

    def fixture(self):
        # Phase 120: 8 nodes need 32 overnight energy; the ninth needs 64.
        case = {"tick": 825, "lineage": 1}
        life = {"id": 1, "birth_tick": 825, "generation": 1, "species": 0}
        gate = {"active": True, "allowed": False, "forecast_allowed": False,
                "age": 2, "sun_phase": 120, "maintenance_phase": 0, "income": 0, "vigor": 0,
                "post_nodes": 9, "cost": 9, "maintenance": 2, "daylight_steps": 8,
                "daylight_credit": 0, "daylight_upkeep": 4, "night_upkeep": 64, "projected_sunset": 27}
        bid = {"action": 1, "nodes": 8, "available": 1, "energy": 40, "energy_gate": gate}
        return bid, life, case

    def test_forecast_arithmetic_and_scope(self):
        b, life, case = self.fixture()
        screen.check_energy(b, life, 840, case, "candidate")
        for key in b["energy_gate"]:
            bad = copy.deepcopy(b)
            v = bad["energy_gate"][key]
            bad["energy_gate"][key] = not v if type(v) is bool else v + 1
            # Vigor 0->1 changes the ordinary price, income changes credit.
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                screen.check_energy(bad, life, 840, case, "candidate")
        for arm, other in (("control", case), ("candidate", {**case, "lineage": 2}),
                           ("candidate", {**case, "tick": 810})):
            bad = copy.deepcopy(b)
            bad["energy_gate"].update(active=False, allowed=True)
            screen.check_energy(bad, life, 840, other, arm)

    def test_wait_night_and_age_257(self):
        b, life, case = self.fixture()
        numeric = ("post_nodes", "cost", "maintenance", "daylight_steps", "daylight_credit",
                   "daylight_upkeep", "night_upkeep", "projected_sunset")
        b["energy_gate"].update(dict.fromkeys(numeric, 0))
        b["action"] = 0
        b["energy_gate"].update(allowed=True, forecast_allowed=True)
        screen.check_energy(b, life, 840, case, "candidate")
        b["action"] = 1
        b["energy_gate"].update(age=10, sun_phase=128, allowed=False, forecast_allowed=False)
        screen.check_energy(b, life, 960, case, "candidate")
        b["energy_gate"].update(age=257, sun_phase=119, maintenance_phase=3, active=False, allowed=True,
            post_nodes=9, cost=9, maintenance=2, daylight_steps=9, daylight_upkeep=6,
            night_upkeep=64, projected_sunset=25)
        screen.check_energy(b, life, 4665, case, "candidate")


class NativeTests(unittest.TestCase):
    def setUp(self):
        if BUILD is None:
            self.skipTest("pass --build for native integration")
        temporary = tempfile.TemporaryDirectory(prefix="landing-root-energy-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.model = self.directory / "model.tgl"
        self.model.write_bytes(screen.load_inputs()[3])
        self.cli = BUILD / "toy-factory-garden-landing"

    def native(self, *args, **kwargs):
        result = run([self.cli, *args], **kwargs)
        return json.loads(result) if result else None

    def args(self):
        return ("placement-replay", self.model, "rainfed-crowded", "0x940cfdc4", "--climate", "seasonal",
                "--ticks", 60, "--ledger", "--shoot-reserve", "on", "--seed-placement", "spacing")

    def test_inactive_state_pixels_and_old_trace_unchanged(self):
        case = {"tick": 120, "lineage": 45, "order": "fixed"}
        paths = [self.directory / (s + ".jsonl") for s in ("old", "control", "candidate")]
        results, traces, frames = [], [], []
        for label, path in zip(("old", "control", "candidate"), paths, strict=True):
            frame = self.directory / (label + ".raw")
            result = self.native(*self.args(), "--root-choice-at", 120, "--root-choice-lineage", 45,
                "--stand-trace", path, "--stand-start", 15, "--stand-stop", 60,
                "--stand-choice" if label == "old" else "--stand-energy", "--framebuffer", frame,
                *(("--root-energy-reserve",) if label == "candidate" else ()))
            rows = screen.adults.read_trace(path)
            if label != "old":
                lives = {p["id"]: p for p in result["lineages"]}
                for row in rows[1:-1]:
                    for b in row["bids"]:
                        screen.check_energy(b, lives[b["id"]], row["tick"], case, label)
                rows = [{**rows[0], "schema": "landing-root-choice-stand-trace-v1"},
                        *screen.strip_energy(rows[1:-1]),
                        {**rows[-1], "run_hash": screen.root_result(result, case, label)["run_hash"]}]
                result = screen.root_result(result, case, label)
            results.append(result)
            traces.append(rows)
            frames.append(frame.read_bytes())
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0], results[2])
        self.assertEqual(traces[0], traces[1])
        self.assertEqual(traces[0], traces[2])
        self.assertEqual(frames[0], frames[1])
        self.assertEqual(frames[0], frames[2])

    def test_validation_precedes_file_creation(self):
        path = self.directory / "trace.jsonl"
        trace = ("--stand-trace", path, "--stand-start", 15, "--stand-stop", 60)
        for extra in (("--root-energy-reserve",),
                      ("--root-energy-reserve", "--root-choice-at", 120),
                      ("--root-energy-reserve", "--root-choice-at", 120, "--root-choice-lineage", 45, "--stand-choice"),
                      ("--stand-energy", "--stand-choice"), ("--stand-energy", "--stand-order"),
                      ("--stand-energy", "--stand-energy"),
                      ("--root-energy-reserve", "--root-energy-reserve")):
            self.native(*self.args(), *trace, *extra, valid=False)
            self.assertFalse(path.exists())
        self.native(*self.args(), "--stand-energy", valid=False)
        path.write_bytes(b"preserve")
        self.native(*self.args(), *trace, "--stand-energy", valid=False)
        self.assertEqual(path.read_bytes(), b"preserve")


class FrozenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = screen.ROOT / "benchmarks/garden-seasons/landing-root-energy-results.json.gz"
        if not path.exists():
            raise unittest.SkipTest("prospective capture not completed yet")
        if screen.root.digest(path) != "dca98970b1efbd6552df4796c280fcb0883bc959f226d569531353a760abe778":
            raise AssertionError("frozen root-energy results changed")
        with gzip.open(path, "rt") as stream:
            cls.value = json.load(stream)

    def test_offline_reanalysis(self):
        with patch.object(screen.order.training, "native", side_effect=AssertionError("ran simulation")):
            screen.check_value(self.value)

    def test_partial_rescue_and_unchanged_successful_controls(self):
        for entry, death in zip(self.value["cases"], (None, None, None, 908940, 909000), strict=True):
            case, arms = entry["case"], entry["arms"]
            a, b = (arms[arm]["analysis"]["focal"] for arm in screen.ARMS)
            self.assertEqual(b["life"]["death_tick"], death)
            self.assertEqual(b["life"]["seeds_created"], 0)
            if case["role"] == "harm-check":
                self.assertEqual(screen.strip_energy(a["steps"]), screen.strip_energy(b["steps"]))
                for label in screen.LABELS:
                    self.assertEqual(arms["control"]["runs"][label]["result"],
                        screen.root_result(arms["candidate"]["runs"][label]["result"], case, "candidate"))
            elif death:
                self.assertGreater(death, a["life"]["death_tick"])
                self.assertEqual(b["first_day"]["death_shortage"], "energy")
        rescued = self.value["cases"][2]["arms"]["candidate"]["analysis"]
        self.assertIsNone(rescued["focal"]["first_day"]["first_shortage"])
        self.assertEqual(rescued["followup_steps"][-1]["plant"]["stages"][-1], [256, 495, 0, 0, 32])
        self.assertEqual(len(rescued["all_plants"]["outcomes"]["periods"][-1]["confirmations"]), 1)

    def test_remaining_failures_overestimate_income_at_ninth_node(self):
        for entry, forecast, actual, income in zip(self.value["cases"][3:], (66, 64), (43, 45), (26, 6), strict=True):
            steps = entry["arms"]["candidate"]["analysis"]["focal"]["steps"]
            ninth = next(s for s in steps if s["body"] and s["body"]["nodes"] == 9 and any(b["nodes"] == 8 for b in s["bids"]))
            eligible = [b for b in ninth["bids"] if b["budget"]["allowed"] and b["water_gate"]["allowed"] and b["energy_gate"]["allowed"]]
            winner = max(eligible, key=lambda b: b["priority"])
            self.assertEqual(winner["energy_gate"]["projected_sunset"], forecast)
            self.assertEqual(winner["energy_gate"]["night_upkeep"], 64)
            sunset = next(s for s in steps if s["tick"] > ninth["tick"] and s["sun"][0] == 128)
            self.assertEqual(sunset["plant"]["stages"][-1][0], actual)
            self.assertEqual(sum(s["plant"]["uptake"][0][1] for s in steps if ninth["tick"] < s["tick"] <= sunset["tick"]), income)
            self.assertGreater(winner["energy_gate"]["daylight_credit"], income)

    def test_recovery_provenance_and_incomplete_capture_rejected(self):
        self.assertEqual(self.value["validation_recovery"]["additional_native_calls"], 0)
        bad = copy.deepcopy(self.value)
        bad["validation_recovery"]["additional_native_calls"] = 1
        with self.assertRaises(RuntimeError):
            screen.check_value(bad)
        with tempfile.TemporaryDirectory() as temporary, patch.object(
                screen.order.training, "native", side_effect=AssertionError("ran simulation")):
            path = Path(temporary)
            with self.assertRaises(RuntimeError):
                screen.reanalyse(path / "missing", path / "new", path)
            self.assertFalse((path / "new").exists())

    def test_corrupt_evidence_rejected(self):
        for fault in ("panel", "call", "identity", "prefix", "forecast", "scope", "priority", "budget", "followup", "repeat"):
            value = copy.deepcopy(self.value)
            a = value["cases"][0]["arms"]["candidate"]
            if fault == "panel": value["cases"].pop()
            elif fault == "call": a["calls"].pop()
            elif fault == "identity": a["runs"]["trace"]["result"]["root_energy_probe"]["version"] = 2
            elif fault == "prefix": a["runs"]["prefix"]["result"]["world_hash"] = "00000000"
            elif fault in ("forecast", "scope"):
                bid = next(b for s in a["analysis"]["focal"]["steps"][1:] for b in s["bids"])
                if fault == "forecast": bid["energy_gate"]["night_upkeep"] += 1
                else: bid["energy_gate"]["active"] = False
            elif fault == "priority": a["analysis"]["priority_changes"] = []
            elif fault == "budget": a["analysis"]["focal"]["first_day"]["resources"]["energy"]["growth"] += 1
            elif fault == "followup": a["analysis"]["followup_steps"].append({"tick": 0})
            else: a["runs"]["repeat"]["frame"]["raw_sha256"] = "0" * 64
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                screen.check_value(value)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve() if args.build else None
    unittest.main(argv=[__file__, *rest])
