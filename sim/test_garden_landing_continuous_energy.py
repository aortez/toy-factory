#!/usr/bin/env python3
"""Continuous energy scope, legacy compatibility and complete lifetime evidence."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_continuous_energy as screen
from test_garden_landing_tools import run

BUILD = None
RESULTS = "benchmarks/garden-seasons/landing-continuous-energy-results.json.gz"
RESULTS_SHA = "143cfbb3a1064cadbe0b46b8c0907684928e7e2dc7e54b0a0502324648c3d1b5"


class ContractTests(unittest.TestCase):
    def test_fixed_budget_and_only_one_configuration_difference(self):
        _, world, _, _ = screen.load_inputs()
        calls = []
        for case in screen.CASES:
            for label in screen.LABELS:
                control = screen.arguments(world, case, "control", label)
                candidate = screen.arguments(world, case, "candidate", label)
                self.assertEqual(candidate[-1], "--root-continuous-energy")
                old, new = screen.root.stem(case, "candidate", label), screen.root.stem(case, "control", label)
                self.assertEqual([a.replace(old, new) for a in candidate[:-1]], control)
                self.assertEqual(candidate[:-1], screen.previous.arguments(world, case, "candidate", label))
                calls.extend((control, candidate))
        self.assertEqual(len(calls), 40)
        self.assertEqual(sum("--root-continuous-energy" in c for c in calls), 20)
        self.assertEqual(sum("--stand-afternoon" in c for c in calls), 20)
        self.assertEqual(len({c[c.index("--framebuffer") + 1] for c in calls}), 40)

    def test_saved_control_receipts_still_validate(self):
        _, _, saved, _ = screen.load_inputs()
        for entry in saved["cases"]:
            analysis, case = entry["arms"]["candidate"]["analysis"], entry["case"]
            life = analysis["focal"]["life"]
            for step in screen.steps(analysis):
                row = {"tick": step["tick"], "bids": step["bids"], "bodies": [step["body"]] if step["body"] else []}
                screen.previous.check_row(row, {"plants": [step["plant"]]}, {life["id"]: life}, case, "candidate", continuous=False)
                self.assertEqual(screen.cutoff_choices(row, case, "control"), [])

    def test_expired_receipts_require_explicit_scope_and_keep_math(self):
        _, _, saved, _ = screen.load_inputs()
        entry = saved["cases"][3]
        case, analysis = entry["case"], entry["arms"]["candidate"]["analysis"]
        step = next(s for s in screen.steps(analysis) if s["tick"] == 910410)
        extended = copy.deepcopy(step)
        for bid in extended["bids"]:
            for name in ("energy_gate", "afternoon_gate"):
                bid[name]["active"] = True
                bid[name]["allowed"] = bid[name]["forecast_allowed"]
            screen.previous.check_afternoon(bid, analysis["focal"]["life"], step["tick"], case, "candidate", continuous=True)
            with self.assertRaises(RuntimeError):
                screen.previous.check_afternoon(bid, analysis["focal"]["life"], step["tick"], case, "candidate")
        self.assertEqual(screen.physical([extended]), screen.physical([step]))
        changes = screen.cutoff_choices(extended, case, "candidate")
        self.assertEqual(len(changes), 1)
        self.assertTrue(changes[0]["before"]["eligible"])
        self.assertFalse(changes[0]["after"]["eligible"])
        life = analysis["focal"]["life"]
        for other in ({**life, "death_tick": step["tick"]}, {**life, "generation": 0},
                      {**life, "id": life["id"] + 1}, {**life, "birth_tick": life["birth_tick"] - screen.STEP}):
            with self.subTest(other=other), self.assertRaises(RuntimeError):
                screen.previous.check_afternoon(extended["bids"][0], other, step["tick"], case, "candidate", continuous=True)
        # A trace that merely changes the active annotation must fail too.
        bad = copy.deepcopy(extended["bids"][0])
        bad["afternoon_gate"]["allowed"] = True
        with self.assertRaises(RuntimeError):
            screen.previous.check_afternoon(bad, analysis["focal"]["life"], step["tick"], case, "candidate", continuous=True)


class NativeTests(unittest.TestCase):
    def setUp(self):
        if BUILD is None:
            self.skipTest("pass --build for native integration")
        temporary = tempfile.TemporaryDirectory(prefix="landing-continuous-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.model = self.directory / "model.tgl"
        self.model.write_bytes(screen.load_inputs()[3])
        self.cli = BUILD / "toy-factory-garden-landing"

    def native(self, *args, **kwargs):
        value = run([self.cli, *args], **kwargs)
        return json.loads(value) if value else None

    def args(self):
        return ("placement-replay", self.model, "rainfed-crowded", "0x940cfdc4", "--climate", "seasonal",
                "--ticks", 60, "--ledger", "--shoot-reserve", "on", "--seed-placement", "spacing",
                "--root-choice-at", 120, "--root-choice-lineage", 45)

    def test_inactive_scope_preserves_world_pixels_and_existing_trace(self):
        case = {"tick": 120, "lineage": 45, "order": "fixed"}
        values = []
        for arm in screen.ARMS:
            path, frame = (self.directory / (arm + ext) for ext in (".jsonl", ".raw"))
            result = self.native(*self.args(), "--root-energy-reserve", "--root-afternoon-reserve",
                "--stand-trace", path, "--stand-start", 15, "--stand-stop", 60,
                "--stand-afternoon", "--framebuffer", frame,
                *(("--root-continuous-energy",) if arm == "candidate" else ()))
            rows = screen.adults.read_trace(path)
            lives = {p["id"]: p for p in result["lineages"]}
            for row in rows[1:-1]:
                for bid in row["bids"]:
                    screen.previous.check_afternoon(bid, lives[bid["id"]], row["tick"], case, "candidate", continuous=arm == "candidate")
            normal = screen.afternoon_result(result, case, arm)
            values.append((normal, [*rows[:-1], {**rows[-1], "run_hash": normal["run_hash"]}], frame.read_bytes()))
        self.assertEqual(values[0], values[1])

    def test_invalid_configuration_does_not_create_or_clobber_outputs(self):
        trace = self.directory / "trace.jsonl"
        base = (*self.args(), "--root-continuous-energy", "--stand-trace", trace, "--stand-start", 15, "--stand-stop", 60)
        for extra in (("--stand-afternoon",), ("--root-energy-reserve", "--stand-afternoon"),
                      ("--root-afternoon-reserve", "--stand-afternoon"),
                      ("--root-energy-reserve", "--root-afternoon-reserve", "--stand-energy"),
                      ("--root-energy-reserve", "--root-afternoon-reserve", "--stand-afternoon", "--root-continuous-energy")):
            self.native(*base, *extra, valid=False)
            self.assertFalse(trace.exists())
        trace.write_bytes(b"preserve")
        self.native(*base, "--root-energy-reserve", "--stand-afternoon", valid=False)
        self.assertEqual(trace.read_bytes(), b"preserve")


class FrozenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = screen.ROOT / RESULTS
        if not path.exists():
            raise unittest.SkipTest("prospective capture not completed yet")
        if screen.root.digest(path) != RESULTS_SHA:
            raise AssertionError("frozen continuous results changed")
        with gzip.open(path, "rt") as stream:
            cls.value = json.load(stream)

    def test_full_lifetime_offline_reanalysis(self):
        with patch.object(screen.order.training, "native", side_effect=AssertionError("ran simulation")):
            screen.check_value(self.value)

    def test_four_survivors_are_physically_unchanged_and_do_not_reproduce(self):
        for index in (0, 1, 2, 4):
            entry = self.value["cases"][index]
            arms, case = entry["arms"], entry["case"]
            self.assertIsNone(screen.first_effect(case, arms))
            a, b = [arms[arm]["analysis"] for arm in screen.ARMS]
            self.assertEqual(screen.physical(screen.steps(a)), screen.physical(screen.steps(b)))
            self.assertIsNone(b["focal"]["life"]["death_tick"])
            self.assertEqual(b["focal"]["life"]["seeds_created"], 0)
            for label in screen.LABELS:
                self.assertEqual(arms["control"]["runs"][label]["result"],
                    screen.afternoon_result(arms["candidate"]["runs"][label]["result"], case, "candidate"))
                self.assertEqual(arms["control"]["runs"][label]["frame"], arms["candidate"]["runs"][label]["frame"])

    def test_cutoff_is_removed_but_failure_moves_to_third_night(self):
        from garden_landing_energy_audit import window
        entry = self.value["cases"][3]
        arms, case = entry["arms"], entry["case"]
        a, b = [arms[arm]["analysis"] for arm in screen.ARMS]
        effect = screen.first_effect(case, arms)
        self.assertEqual((effect["tick"], effect["matching_prior_focal_samples"], effect["phase"]), (910410, 256, 86))
        self.assertEqual((a["focal"]["life"]["death_tick"], b["focal"]["life"]["death_tick"]), (912120, 916440))
        self.assertEqual(b["focal"]["life"]["seeds_created"], 0)
        self.assertEqual(len(b["cutoff_choices"]), 181)
        rows = screen.steps(b)
        before, receipts = None, []
        for step in rows:
            receipts.append(screen.adults.transfers({"tick": step["tick"], **step["plant"]}, b["focal"]["life"], before)["energy"])
            before = step["plant"]["stages"][-1]
        observed = []
        for start, stop in ((911040, 912960), (912960, 914880), (914880, 916440)):
            index = next(i for i, s in enumerate(rows) if s["tick"] == start)
            observed.append(window(rows, receipts, b["focal"]["life"], index, stop, after_growth=False))
        self.assertEqual([(r["initial"], r["transfers"]["income"], r["transfers"]["growth"], r["transfers"]["upkeep"], r["final"])
                          for r in observed], [(128, 0, 0, 128, 0), (0, 260, 81, 107, 72), (72, 0, 0, 72, 0)])
        self.assertEqual([len(r["energy_shortages"]) for r in observed], [0, 6, 8])
        self.assertEqual([r["status"] for r in observed], ["alive", "alive", "dead"])
        # Population differences are only the focal lifetime credit, not renewal.
        left, right = [arms[arm]["runs"]["trace"]["result"] for arm in screen.ARMS]
        self.assertEqual(left["seeds"], right["seeds"])
        self.assertEqual([p for p in left["lineages"] if p["id"] != 49], [p for p in right["lineages"] if p["id"] != 49])
        self.assertEqual(arms["control"]["runs"]["trace"]["frame"], arms["candidate"]["runs"]["trace"]["frame"])
        self.assertEqual([x["all_plants"]["outcomes"]["periods"][-1]["credit"]["ticks"] for x in (a, b)], [510045, 514365])

    def test_last_paid_forecast_error_is_income_not_later_spending(self):
        from garden_landing_energy_audit import paid_event
        a = self.value["cases"][3]["arms"]["candidate"]["analysis"]
        rows, life = screen.steps(a), a["focal"]["life"]
        before, receipts = None, []
        for step in rows:
            receipts.append(screen.adults.transfers({"tick": step["tick"], **step["plant"]}, life, before)["energy"])
            before = step["plant"]["stages"][-1]
        i = next(i for i, s in enumerate(rows) if s["tick"] == 914415)
        choice = screen.previous.winner(rows[i]["bids"], afternoon=True)
        bid = next(b for b in rows[i]["bids"] if b["tip"] == choice["tip"])
        event = paid_event(rows, receipts, life, i, bid)
        self.assertTrue(bid["energy_gate"]["active"] and bid["energy_gate"]["allowed"])
        self.assertTrue(bid["afternoon_gate"]["active"])
        self.assertFalse(bid["afternoon_gate"]["applies"])
        self.assertEqual((bid["nodes"], bid["energy_gate"]["post_nodes"]), (31, 32))
        self.assertEqual((bid["energy_gate"]["daylight_credit"], event["sunset"]["transfers"]["income"]), (75, 18))
        self.assertEqual((bid["energy_gate"]["projected_sunset"], event["sunset"]["final"]), (129, 72))
        self.assertEqual(event["error"]["predicted_minus_actual"], 57)
        self.assertEqual(event["error"]["terms"], {"income": 57, "maintenance": 0, "later_growth": 0,
                         "reproduction": 0, "overflow": 0, "discard": 0, "forecast_cap": 0})

    def test_corrupt_late_history_configuration_counts_and_calls_rejected(self):
        for fault in ("scope", "gap", "margin", "resource", "cutoff", "identity", "call", "repeat"):
            value = copy.deepcopy(self.value)
            a = value["cases"][3]["arms"]["candidate"]
            late_step = next(s for s in a["analysis"]["followup_steps"] if s["bids"])
            if fault == "scope": late_step["bids"][0]["energy_gate"]["active"] = False
            elif fault == "gap": a["analysis"]["followup_steps"].pop()
            elif fault == "margin": late_step["bids"][0]["afternoon_gate"]["margin"] += 1
            elif fault == "resource": late_step["plant"]["stages"][2][0] += 1
            elif fault == "cutoff": a["analysis"]["cutoff_choices"].append({"tick": 0})
            elif fault == "identity": a["runs"]["trace"]["result"]["root_continuous_energy_probe"]["version"] = 2
            elif fault == "call": a["calls"].pop()
            else: a["runs"]["repeat"]["frame"]["raw_sha256"] = "0" * 64
            with self.subTest(fault=fault), self.assertRaises((RuntimeError, KeyError, StopIteration)):
                screen.check_value(value)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve() if args.build else None
    unittest.main(argv=[__file__, *rest])
