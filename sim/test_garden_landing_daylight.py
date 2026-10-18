#!/usr/bin/env python3
"""Daylight arithmetic, option order, legacy projection and frozen evidence."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_daylight as screen
from test_garden_landing_tools import run

BUILD = None
RESULTS = "benchmarks/garden-seasons/landing-daylight-results.json.gz"
RESULTS_SHA = "9e2acb8cf141e75307020c0b854c3a76611942cec615c21b95db750c97d7748b"


def with_daylight(step, arm):
    value = copy.deepcopy(step)
    for b in value["bids"]:
        e, phase = b["energy_gate"], step["sun"][0]
        active = arm == "candidate" and e["active"]
        d = {"active": active, "allowed": True, "applies": b["action"] != 0 and 64 <= phase < 128,
             "forecast_allowed": True, "sun_strength": step["sun"][1], "useful_steps": 0,
             "daylight_credit": 0, "projected_sunset": 0}
        if d["applies"]:
            f = screen.audit.diagnostic(phase, step["sun"][1], e["income"])
            d["useful_steps"], d["daylight_credit"] = f["useful_steps"], f["credit"]
            d["projected_sunset"] = min(256, b["energy"] - e["cost"] + f["credit"] - e["daylight_upkeep"])
            d["forecast_allowed"] = b["energy"] - e["cost"] >= e["maintenance"] and d["projected_sunset"] >= e["night_upkeep"]
            d["allowed"] = not active or d["forecast_allowed"]
        b["daylight_gate"] = d
    return value


class ContractTests(unittest.TestCase):
    def test_fixed_calls_differ_only_by_treatment_and_paths(self):
        _, world, _, _ = screen.load_inputs()
        calls = []
        for case in screen.CASES:
            for label in screen.LABELS:
                a, b = [screen.arguments(world, case, arm, label) for arm in screen.ARMS]
                self.assertEqual(b[-1], "--root-daylight-energy")
                old, new = screen.root.stem(case, "candidate", label), screen.root.stem(case, "control", label)
                self.assertEqual([arg.replace(old, new) for arg in b[:-1]], a)
                prior = screen.previous.arguments(world, case, "candidate", label)
                self.assertEqual([arg.replace("--stand-afternoon", "--stand-daylight") for arg in prior], b[:-1])
                calls.extend((a, b))
        self.assertEqual(len(calls), 40)
        self.assertEqual(sum("--stand-daylight" in c for c in calls), 20)
        self.assertEqual(sum("--root-daylight-energy" in c for c in calls), 20)
        self.assertEqual(sum("--root-continuous-energy" in c for c in calls), 40)
        self.assertEqual(len({c[c.index("--framebuffer") + 1] for c in calls}), 40)

    def test_audit_example_birth_scope_and_corruption(self):
        entry = screen.load_inputs()[2]["cases"][3]
        case, a = entry["case"], entry["arms"]["candidate"]["analysis"]
        rows = screen.previous.steps(a)
        original = next(s for s in rows if s["tick"] == 914415)
        for arm in screen.ARMS:
            s = with_daylight(original, arm)
            for b in s["bids"]:
                screen.check_daylight(b, a["focal"]["life"], s["tick"], case, arm, s["sun"])
            chosen = screen.winner(s["bids"], daylight=False)
            b = next(b for b in s["bids"] if b["tip"] == chosen["tip"])
            self.assertEqual(tuple(b["daylight_gate"][k] for k in ("useful_steps", "daylight_credit", "projected_sunset")), (9, 22, 76))
            self.assertEqual(b["daylight_gate"]["allowed"], arm == "control")
            self.assertEqual(screen.strip_daylight([s]), [original])
        for field, v in b["daylight_gate"].items():
            corrupt = copy.deepcopy(b)
            corrupt["daylight_gate"][field] = not v if type(v) is bool else v + 1
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                screen.check_daylight(corrupt, a["focal"]["life"], s["tick"], case, arm, s["sun"])
        birth = with_daylight(rows[0], "candidate")
        for b in birth["bids"]:
            screen.check_daylight(b, a["focal"]["life"], birth["tick"], case, "candidate", birth["sun"])
            self.assertFalse(b["daylight_gate"]["active"])

    def test_all_saved_control_receipts_and_paid_prices(self):
        for entry in screen.load_inputs()[2]["cases"]:
            a, case = entry["arms"]["candidate"]["analysis"], entry["case"]
            life = a["focal"]["life"]
            for original in screen.previous.steps(a):
                s = with_daylight(original, "control")
                row = {"tick": s["tick"], "bids": s["bids"], "climate": s["climate"], "bodies": [s["body"]] if s["body"] else []}
                _, _, _, counts, changes = screen.check_row(row, {"sun": s["sun"], "plants": [s["plant"]]}, {life["id"]: life}, case, "control")
                self.assertFalse(counts or changes)
                self.assertEqual(screen.strip_daylight([s]), [original])


class NativeTests(unittest.TestCase):
    def setUp(self):
        if BUILD is None:
            self.skipTest("pass --build for native integration")
        temporary = tempfile.TemporaryDirectory(prefix="landing-daylight-")
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
                "--root-choice-at", 120, "--root-choice-lineage", 45,
                "--root-energy-reserve", "--root-afternoon-reserve")

    def test_option_order_inactive_pixels_and_legacy_trace(self):
        case = {"tick": 120, "lineage": 45, "order": "fixed"}
        captures = []
        for index, options in enumerate((("--root-continuous-energy",),
                ("--root-continuous-energy", "--root-daylight-energy"),
                ("--root-daylight-energy", "--root-continuous-energy"))):
            arm = "candidate" if index else "control"
            stand, resource, frame = [self.directory / (str(index) + ext) for ext in (".jsonl", "-adult.jsonl", ".raw")]
            result = self.native(*self.args(), *options, "--stand-daylight", "--stand-trace", stand,
                "--stand-start", 15, "--stand-stop", 60, "--adult-trace", resource, "--adult-start", 15,
                "--adult-stop", 60, "--framebuffer", frame)
            rows, resources = [screen.adults.read_trace(p) for p in (stand, resource)]
            lives = {p["id"]: p for p in result["lineages"]}
            for row, r in zip(rows[1:-1], resources[1:-1], strict=True):
                screen.check_row(row, r, lives, case, arm)
            captures.append((screen.continuous_result(result, case, arm), screen.strip_daylight(rows[1:-1]), frame.read_bytes()))
        self.assertEqual(captures[0], captures[1])
        self.assertEqual(captures[1], captures[2])
        stand, frame = self.directory / "old.jsonl", self.directory / "old.raw"
        old = self.native(*self.args(), "--root-continuous-energy", "--stand-afternoon", "--stand-trace", stand,
            "--stand-start", 15, "--stand-stop", 60, "--framebuffer", frame)
        self.assertEqual((old, screen.adults.read_trace(stand)[1:-1], frame.read_bytes()), captures[0])
        plain = self.native(*self.args(), "--root-daylight-energy", "--root-continuous-energy")
        self.assertEqual(screen.continuous_result(plain, case, "candidate")["world_hash"], old["world_hash"])

    def test_invalid_and_duplicate_options_preserve_outputs(self):
        trace = self.directory / "trace.jsonl"
        base = (*self.args(), "--stand-trace", trace, "--stand-start", 15, "--stand-stop", 60)
        for flags in (("--root-daylight-energy", "--stand-daylight"),
                      ("--root-daylight-energy", "--root-continuous-energy", "--stand-afternoon"),
                      ("--root-continuous-energy", "--root-continuous-energy", "--stand-daylight"),
                      ("--root-continuous-energy", "--root-daylight-energy", "--root-daylight-energy", "--stand-daylight"),
                      ("--root-continuous-energy", "--stand-daylight", "--stand-daylight"),
                      ("--root-continuous-energy", "--stand-daylight", "--stand-energy")):
            self.native(*base, *flags, valid=False)
            self.assertFalse(trace.exists())
        trace.write_bytes(b"preserve")
        self.native(*base, "--root-daylight-energy", "--stand-daylight", valid=False)
        self.assertEqual(trace.read_bytes(), b"preserve")


class FrozenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = screen.ROOT / RESULTS
        screen.require(screen.root.digest(path) == RESULTS_SHA, "frozen daylight results changed")
        with gzip.open(path, "rt") as stream:
            cls.value = json.load(stream)

    def test_offline_reanalysis_without_native_calls(self):
        with patch.object(screen.order.training, "native", side_effect=AssertionError("ran simulation")):
            screen.check_value(self.value)

    def test_survival_and_three_unchanged_physical_histories(self):
        for index, entry in enumerate(self.value["cases"]):
            a, b = [entry["arms"][arm] for arm in screen.ARMS]
            self.assertIsNone(b["analysis"]["focal"]["life"]["death_tick"])
            for arm in (a, b):
                self.assertEqual(arm["analysis"]["focal"]["life"]["seeds_created"], 0)
            if index < 3:
                self.assertIsNone(screen.first_effect(entry["case"], entry["arms"]))
                self.assertEqual(screen.strip_daylight(screen.previous.steps(a["analysis"])),
                                 screen.strip_daylight(screen.previous.steps(b["analysis"])))
                self.assertEqual(a["runs"]["trace"]["frame"], b["runs"]["trace"]["frame"])

    def test_rescue_common_prefix_spending_and_remaining_dawn_shortages(self):
        entry = self.value["cases"][3]
        effect = screen.first_effect(entry["case"], entry["arms"])
        self.assertEqual((effect["tick"], effect["phase"], effect["matching_prior_focal_samples"]),
                         (914205, 83, 509))
        self.assertTrue(effect["before"]["eligible"])
        self.assertFalse(effect["after"]["eligible"])
        from garden_landing_energy_audit import window
        for arm, expected in (("control", (916440, 72, 63)), ("candidate", (None, 126, 18))):
            analysis = entry["arms"][arm]["analysis"]
            life, rows = analysis["focal"]["life"], screen.previous.steps(analysis)
            self.assertEqual(life["death_tick"], expected[0])
            before, receipts = None, []
            for row in rows:
                receipts.append(screen.adults.transfers({"tick": row["tick"], **row["plant"]}, life, before)["energy"])
                before = row["plant"]["stages"][-1]
            index = next(i for i, r in enumerate(rows) if r["tick"] == 914205)
            balance = window(rows, receipts, life, index, 914880, after_growth=False)
            self.assertEqual((balance["final"], balance["transfers"]["income"], balance["transfers"]["upkeep"],
                              balance["transfers"]["growth"]), (expected[1], 97, 48, expected[2]))
            if arm == "candidate":
                shortages = [r["tick"] for r in rows if 914880 < r["tick"] <= 917100 and
                             r["tick"] % 60 == 0 and r["plant"]["stages"][1][3] & 2]
                self.assertEqual(shortages, [916800, 916860, 916920, 916980, 917040])
                last = next(r for r in rows if r["tick"] == 914400)
                bid = next(b for b in last["bids"] if b["tip"] == screen.winner(last["bids"], daylight=True)["tip"])
                self.assertEqual((bid["daylight_gate"]["daylight_credit"], bid["daylight_gate"]["projected_sunset"]), (25, 128))
                self.assertEqual(len(analysis["daylight"]["changed_choices"]), 16)

    def test_rescue_population_tradeoffs_and_seed_access(self):
        entry = self.value["cases"][3]
        a, b = [entry["arms"][arm] for arm in screen.ARMS]
        for arm, credit, living, seeds in ((a, 514365, [40, 41, 45, 47, 51, 52], 102),
                                          (b, 573300, [40, 41, 45, 47, 49], 100)):
            outcomes = arm["analysis"]["all_plants"]["outcomes"]
            self.assertEqual(outcomes["periods"][-1]["credit"]["ticks"], credit)
            self.assertEqual(outcomes["living_at_stop"], living)
            self.assertEqual(len(arm["runs"]["trace"]["result"]["seeds"]), seeds)
        visits = [r["visit"] for r in screen.previous.steps(b["analysis"]) if r["visit"]]
        self.assertEqual(sum(v["blockers"] == 4 for v in visits), 320)
        self.assertEqual(visits[-1]["blockers"], 4)
        self.assertEqual(visits[-1]["bank"], 8)
        self.assertFalse(any(v["produced"] for v in visits))

    def test_successful_root_delayed_two_steps_without_lifetime_or_seed_change(self):
        entry = self.value["cases"][4]
        a, b = [entry["arms"][arm] for arm in screen.ARMS]
        effect = screen.first_effect(entry["case"], entry["arms"])
        self.assertEqual((effect["tick"], effect["phase"], effect["matching_prior_focal_samples"]), (910170, 70, 230))
        self.assertEqual([c["tick"] for c in b["analysis"]["daylight"]["changed_choices"]], [910170, 910185])
        for arm, tick, nodes, roots in ((a, 910170, 32, 16), (b, 910200, 31, 15)):
            rows = screen.previous.steps(arm["analysis"])
            paid = next(r for r in rows if r["tick"] >= 910170 and r["plant"]["stages"][2][0] > r["plant"]["stages"][3][0])
            self.assertEqual(paid["tick"], tick)
            bid = next(x for x in paid["bids"] if x["tip"] == screen.winner(paid["bids"], daylight=True)["tip"])
            self.assertEqual((bid["tip"], bid["action"], bid["tissue"], bid["water_gate"]["destination"]),
                             (132, 1, 1, [225, 161, 6]))
            self.assertEqual((rows[-1]["body"]["nodes"], rows[-1]["body"]["roots"]), (nodes, roots))
            self.assertFalse(any(r["tick"] % 60 == 0 and r["plant"]["stages"][1] and
                                 r["plant"]["stages"][1][3] & 2 for r in rows))
        for field in ("lineages", "seeds"):
            self.assertEqual(a["runs"]["trace"]["result"][field], b["runs"]["trace"]["result"][field])
        self.assertEqual(a["analysis"]["all_plants"]["outcomes"], b["analysis"]["all_plants"]["outcomes"])
        self.assertNotEqual(a["runs"]["trace"]["frame"], b["runs"]["trace"]["frame"])

    def test_corrupted_history_forecast_calls_and_identity_rejected(self):
        for fault in ("scope", "gap", "credit", "strength", "resource", "choices", "identity", "call", "repeat"):
            value = copy.deepcopy(self.value)
            a = value["cases"][3]["arms"]["candidate"]
            step = next(s for s in a["analysis"]["followup_steps"] if s["bids"])
            if fault == "scope": step["bids"][0]["daylight_gate"]["active"] = False
            elif fault == "gap": a["analysis"]["followup_steps"].pop()
            elif fault == "credit": step["bids"][0]["daylight_gate"]["daylight_credit"] += 1
            elif fault == "strength": step["bids"][0]["daylight_gate"]["sun_strength"] += 1
            elif fault == "resource": step["plant"]["stages"][2][0] += 1
            elif fault == "choices": a["analysis"]["daylight"]["changed_choices"].append({"tick": 0})
            elif fault == "identity": a["runs"]["trace"]["result"]["root_daylight_energy_probe"]["version"] = 2
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
