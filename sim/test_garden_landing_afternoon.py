#!/usr/bin/env python3
"""Afternoon eligibility, old-path compatibility and fixed-panel evidence."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_afternoon as screen
from test_garden_landing_tools import run

BUILD = None
RESULTS = "benchmarks/garden-seasons/landing-afternoon-results.json.gz"
RESULTS_SHA = "dea464eae46233bcc2f253ae657a7b4a05e8b2d3c51a8b484f23e04c40602afc"


def gate(bid, arm):
    e = bid["energy_gate"]
    before = max(1, (bid["nodes"] + 7) // 8)
    applies = bid["action"] == 1 and bid["available"] > 0 and 64 <= e["sun_phase"] < 128 and e["maintenance"] > before
    margin = bid["energy"] - e["cost"] - e["daylight_upkeep"] - e["night_upkeep"] if applies else 0
    active = arm == "candidate" and e["active"]
    return {"active": active, "allowed": not active or not applies or margin >= 0,
            "applies": applies, "forecast_allowed": not applies or margin >= 0,
            "maintenance_before": before if applies else 0, "margin": margin}


class ContractTests(unittest.TestCase):
    def test_fixed_budget_control_and_trace_identity(self):
        _, world, _, _ = screen.load_inputs()
        calls = [screen.arguments(world, c, a, label) for c in screen.CASES for a in screen.ARMS for label in screen.LABELS]
        self.assertEqual(len(calls), 40)
        self.assertEqual(sum("--root-energy-reserve" in c for c in calls), 40)
        self.assertEqual(sum("--root-afternoon-reserve" in c for c in calls), 20)
        self.assertEqual(sum("--stand-afternoon" in c for c in calls), 20)
        self.assertFalse(any("--stand-energy" in c for c in calls))
        self.assertEqual(len({c[c.index("--framebuffer") + 1] for c in calls}), 40)

    def test_saved_failure_math_scope_and_mutations(self):
        _, _, saved, _ = screen.load_inputs()
        for entry, margin in zip(saved["cases"][3:], (-47, -25), strict=True):
            case = entry["case"]
            focal = entry["arms"]["candidate"]["analysis"]["focal"]
            step = next(s for s in focal["steps"] if s["body"] and s["body"]["nodes"] == 9 and any(b["nodes"] == 8 for b in s["bids"]))
            bid = max([b for b in step["bids"] if b["budget"]["allowed"] and b["water_gate"]["allowed"] and b["energy_gate"]["allowed"]],
                      key=lambda b: b["priority"])
            for arm in screen.ARMS:
                b = {**bid, "afternoon_gate": gate(bid, arm)}
                screen.check_afternoon(b, focal["life"], step["tick"], case, arm)
                self.assertEqual(b["afternoon_gate"]["margin"], margin)
                self.assertEqual(b["afternoon_gate"]["allowed"], arm == "control")
                for key in b["afternoon_gate"]:
                    bad = copy.deepcopy(b)
                    value = bad["afternoon_gate"][key]
                    bad["afternoon_gate"][key] = not value if type(value) is bool else value + 1
                    with self.subTest(key=key), self.assertRaises(RuntimeError):
                        screen.check_afternoon(bad, focal["life"], step["tick"], case, arm)

    def test_control_focal_receipts_and_combined_winners_match_saved(self):
        _, _, saved, _ = screen.load_inputs()
        for entry in saved["cases"]:
            a, case = entry["arms"]["candidate"]["analysis"], entry["case"]
            life = a["focal"]["life"]
            for original in a["focal"]["steps"] + a["followup_steps"]:
                step = copy.deepcopy(original)
                for bid in step["bids"]:
                    bid["afternoon_gate"] = gate(bid, "control")
                _, counts, changes = screen.check_row({"tick": step["tick"], "bids": step["bids"],
                    "bodies": [step["body"]] if step["body"] else []}, {"plants": [step["plant"]]}, {life["id"]: life}, case, "control")
                self.assertEqual(dict(counts), {})
                self.assertEqual(changes, [])
                self.assertEqual(screen.strip_afternoon([step]), [original])

    def test_arbitration_uses_lower_eligible_bid_and_preserves_ties(self):
        def bid(tip, priority, allowed):
            return {"tip": tip, "priority": priority, "budget": {"allowed": True},
                    "water_gate": {"allowed": True}, "energy_gate": {"allowed": True}, "afternoon_gate": {"allowed": allowed}}
        bids = [bid(1, 9, False), bid(2, 8, True), bid(3, 8, True)]
        self.assertEqual(screen.winner(bids, afternoon=False), {"tip": 1, "eligible": True})
        self.assertEqual(screen.winner(bids, afternoon=True), {"tip": 2, "eligible": True})
        for b in bids:
            b["afternoon_gate"]["allowed"] = False
        self.assertEqual(screen.winner(bids, afternoon=True), {"tip": 1, "eligible": False})


class NativeTests(unittest.TestCase):
    def setUp(self):
        if BUILD is None:
            self.skipTest("pass --build for native integration")
        temporary = tempfile.TemporaryDirectory(prefix="landing-afternoon-")
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

    def test_inactive_config_and_observation_preserve_world_pixels_and_old_trace(self):
        case = {"tick": 120, "lineage": 45, "order": "fixed"}
        results, traces, frames = [], [], []
        for label in ("old", "control", "candidate"):
            path, frame = (self.directory / (label + ext) for ext in (".jsonl", ".raw"))
            result = self.native(*self.args(), "--root-choice-at", 120, "--root-choice-lineage", 45,
                "--root-energy-reserve", "--stand-trace", path, "--stand-start", 15, "--stand-stop", 60,
                "--stand-energy" if label == "old" else "--stand-afternoon", "--framebuffer", frame,
                *(("--root-afternoon-reserve",) if label == "candidate" else ()))
            rows = screen.adults.read_trace(path)
            if label != "old":
                lives = {p["id"]: p for p in result["lineages"]}
                for row in rows[1:-1]:
                    for b in row["bids"]:
                        screen.check_afternoon(b, lives[b["id"]], row["tick"], case, label)
                result = screen.energy_result(result, case, label)
                rows = [{**rows[0], "schema": screen.previous.SCHEMA}, *screen.strip_afternoon(rows[1:-1]),
                        {**rows[-1], "run_hash": result["run_hash"]}]
            results.append(result)
            traces.append(rows)
            frames.append(frame.read_bytes())
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0], results[2])
        self.assertEqual(traces[0], traces[1])
        self.assertEqual(traces[0], traces[2])
        self.assertEqual(frames[0], frames[1])
        self.assertEqual(frames[0], frames[2])

    def test_validation_precedes_output_creation(self):
        trace = self.directory / "trace.jsonl"
        base = (*self.args(), "--root-choice-at", 120, "--root-choice-lineage", 45,
                "--stand-trace", trace, "--stand-start", 15, "--stand-stop", 60)
        for extra in (("--root-afternoon-reserve", "--stand-afternoon"),
                      ("--root-energy-reserve", "--root-afternoon-reserve", "--stand-energy"),
                      ("--root-energy-reserve", "--stand-energy", "--stand-afternoon"),
                      ("--stand-choice", "--stand-afternoon"), ("--stand-order", "--stand-afternoon"),
                      ("--stand-afternoon", "--stand-afternoon"),
                      ("--root-energy-reserve", "--stand-afternoon", "--root-afternoon-reserve", "--root-afternoon-reserve")):
            self.native(*base, *extra, valid=False)
            self.assertFalse(trace.exists())
        self.native(*self.args(), "--stand-afternoon", valid=False)
        self.native(*self.args(), "--root-afternoon-reserve", "--root-energy-reserve", valid=False)
        trace.write_bytes(b"preserve")
        self.native(*base, "--stand-afternoon", valid=False)
        self.assertEqual(trace.read_bytes(), b"preserve")


class FrozenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = screen.ROOT / RESULTS
        if not path.exists():
            raise unittest.SkipTest("prospective capture not completed yet")
        if screen.root.digest(path) != RESULTS_SHA:
            raise AssertionError("frozen afternoon results changed")
        with gzip.open(path, "rt") as stream:
            cls.value = json.load(stream)

    def test_full_panel_offline_reanalysis(self):
        with patch.object(screen.order.training, "native", side_effect=AssertionError("ran simulation")):
            screen.check_value(self.value)

    def test_rescue_delayed_death_and_three_unchanged_checks(self):
        for index, entry in enumerate(self.value["cases"]):
            case, arms = entry["case"], entry["arms"]
            a, b = [arms[arm]["analysis"]["focal"] for arm in screen.ARMS]
            self.assertEqual(b["life"]["seeds_created"], 0)
            self.assertEqual(b["first_day"]["status"], "confirmed")
            self.assertIsNone(b["first_day"]["first_shortage"])
            if index < 3:
                self.assertIsNone(screen.first_effect(case, arms))
                self.assertEqual(screen.strip_afternoon(a["steps"]), screen.strip_afternoon(b["steps"]))
                for label in screen.LABELS:
                    self.assertEqual(arms["control"]["runs"][label]["result"],
                                     screen.energy_result(arms["candidate"]["runs"][label]["result"], case, "candidate"))
            else:
                effect = screen.first_effect(case, arms)
                self.assertEqual(effect["tick"], (906690, 906930)[index - 3])
                self.assertEqual(effect["matching_prior_focal_samples"], (8, 14)[index - 3])
                self.assertTrue(effect["before"]["eligible"])
                self.assertFalse(effect["after"]["eligible"])
                self.assertEqual(b["life"]["death_tick"], 912120 if index == 3 else None)
                first_sunset = next(s for s in b["steps"] if s["sun"][0] == 128)
                first_dawn = next(s for s in b["steps"] if s["sun"][0] == 0)
                self.assertEqual(first_sunset["plant"]["stages"][-1][0], (61, 59)[index - 3])
                self.assertEqual(first_dawn["plant"]["stages"][-1][0], (29, 27)[index - 3])
                self.assertEqual(first_sunset["body"]["nodes"], 8)

    def test_remaining_failure_buys_rejected_increases_after_guard_expiry(self):
        a = self.value["cases"][3]["arms"]["candidate"]["analysis"]
        steps = a["focal"]["steps"] + a["followup_steps"]
        for tick, nodes, age, margin in ((910410, 16, 257, -5), (910680, 24, 275, -24)):
            s = next(s for s in steps if s["tick"] == tick)
            chosen = screen.winner(s["bids"], afternoon=True)
            b = next(b for b in s["bids"] if b["tip"] == chosen["tip"])
            e, extra = b["energy_gate"], b["afternoon_gate"]
            self.assertTrue(chosen["eligible"])
            self.assertEqual((b["nodes"], s["body"]["nodes"], e["age"], extra["margin"]), (nodes, nodes + 1, age, margin))
            self.assertFalse(e["active"] or extra["active"] or extra["forecast_allowed"])
            self.assertTrue(extra["applies"] and extra["allowed"] and e["forecast_allowed"])
            self.assertEqual(s["plant"]["stages"][2][0] - s["plant"]["stages"][3][0], 9)
        sunset = next(s for s in steps if s["tick"] == 911040)
        self.assertEqual(sunset["plant"]["stages"][-1][0], 59)
        self.assertEqual((sunset["body"]["nodes"], a["focal"]["life"]["death_tick"]), (30, 912120))
        before, growth, upkeep, income = sunset["plant"]["stages"][-1], 0, 0, 0
        for s in steps:
            if s["tick"] <= sunset["tick"]:
                continue
            receipt = screen.adults.transfers({"tick": s["tick"], **s["plant"]}, a["focal"]["life"], before)["energy"]
            growth += receipt["growth"]
            upkeep += receipt["upkeep"]
            income += receipt["income"]
            before = s["plant"]["stages"][-1]
        self.assertEqual((growth, upkeep, income, before[0]), (18, 41, 0, 0))

    def test_population_effects_are_not_focal_reproduction(self):
        for index, expected_credit in ((3, 510045), (4, 573150)):
            arms = self.value["cases"][index]["arms"]
            a, b = [arms[arm]["analysis"]["all_plants"]["outcomes"] for arm in screen.ARMS]
            self.assertEqual(a["periods"][-1]["confirmations"], [])
            self.assertEqual(b["periods"][-1]["confirmations"], [49 if index == 3 else 50])
            self.assertEqual(b["periods"][-1]["credit"]["ticks"], expected_credit)
        same = self.value["cases"][3]["arms"]
        self.assertEqual(same["control"]["runs"]["trace"]["result"]["seeds"], same["candidate"]["runs"]["trace"]["result"]["seeds"])
        self.assertEqual(same["control"]["runs"]["trace"]["frame"], same["candidate"]["runs"]["trace"]["frame"])
        changed = self.value["cases"][4]["arms"]
        for arm, seed_counts in (("control", (4, 4)), ("candidate", (5, 2))):
            result = changed[arm]["runs"]["trace"]["result"]
            lives = {p["id"]: p for p in result["lineages"]}
            self.assertEqual((lives[40]["seeds_created"], lives[47]["seeds_created"]), seed_counts)
            self.assertEqual(lives[50]["seeds_created"], 0)

    def test_corrupt_scope_calls_prefix_receipts_and_censoring_rejected(self):
        for fault in ("panel", "call", "prefix", "identity", "scope", "margin", "budget", "followup", "repeat", "choices"):
            value = copy.deepcopy(self.value)
            a = value["cases"][0]["arms"]["candidate"]
            if fault == "panel": value["cases"].pop()
            elif fault == "call": a["calls"].pop()
            elif fault == "prefix": a["runs"]["prefix"]["result"]["world_hash"] = "00000000"
            elif fault == "identity": a["runs"]["trace"]["result"]["root_afternoon_probe"]["version"] = 2
            elif fault in ("scope", "margin"):
                b = next(b["afternoon_gate"] for s in a["analysis"]["focal"]["steps"][1:] for b in s["bids"])
                if fault == "scope": b["active"] = not b["active"]
                else: b["margin"] += 1
            elif fault == "budget": a["analysis"]["focal"]["first_day"]["resources"]["energy"]["growth"] += 1
            elif fault == "followup": a["analysis"]["followup_steps"].append({"tick": 0})
            elif fault == "repeat": a["runs"]["repeat"]["frame"]["raw_sha256"] = "0" * 64
            else: a["analysis"]["afternoon"]["changed_choices"].append({"tick": 0})
            with self.subTest(fault=fault), self.assertRaises((RuntimeError, KeyError, StopIteration)):
                screen.check_value(value)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve() if args.build else None
    unittest.main(argv=[__file__, *rest])
