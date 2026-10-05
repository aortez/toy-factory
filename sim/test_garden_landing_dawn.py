#!/usr/bin/env python3
"""Dawn arithmetic, scope, option ordering, legacy projection and accounting."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_dawn as screen
from test_garden_landing_tools import run

BUILD = None
RESULTS = "benchmarks/garden-seasons/landing-dawn-results.json.gz"
RESULTS_SHA = "6c35b2c53f258d0521d7b773f551158fa75770ece81b0ec4564a0b825d1c6687"


def with_dawn(step, arm):
    value = copy.deepcopy(step)
    for b in value["bids"]:
        b["dawn_gate"] = screen.expected_dawn(b, arm)
    return value


class ContractTests(unittest.TestCase):
    def test_fixed_calls_differ_only_by_treatment_and_paths(self):
        _, world, _, _ = screen.load_inputs()
        calls = []
        for case in screen.CASES:
            for label in screen.LABELS:
                a, b = [screen.arguments(world, case, arm, label) for arm in screen.ARMS]
                self.assertEqual(b[-1], "--root-dawn-reserve")
                old, new = screen.root.stem(case, "candidate", label), screen.root.stem(case, "control", label)
                self.assertEqual([arg.replace(old, new) for arg in b[:-1]], a)
                prior = screen.previous.arguments(world, case, "candidate", label)
                self.assertEqual([arg.replace("--stand-daylight", "--stand-dawn") for arg in prior], b[:-1])
                calls.extend((a, b))
        self.assertEqual(len(calls), 40)
        self.assertEqual(sum("--stand-dawn" in c for c in calls), 20)
        self.assertEqual(sum("--root-dawn-reserve" in c for c in calls), 20)
        self.assertEqual(sum("--root-daylight-energy" in c for c in calls), 40)
        self.assertEqual(len({c[c.index("--framebuffer") + 1] for c in calls}), 40)

    def test_predicted_rejections_and_typed_receipt_corruption(self):
        _, _, saved, _ = screen.load_inputs()
        expected = ([], [], [], [910425, 910980, 914130, 914325, 914400], [910140, 910530])
        for entry, ticks in zip(saved["cases"], expected, strict=True):
            analysis, case = entry["arms"]["candidate"]["analysis"], entry["case"]
            actual = []
            for s in screen.steps(analysis):
                if s["plant"]["stages"][2][0] == s["plant"]["stages"][3][0] or not 64 <= s["sun"][0] < 128:
                    continue
                chosen = screen.winner(s["bids"], dawn=False)
                bid = copy.deepcopy(next(b for b in s["bids"] if b["tip"] == chosen["tip"]))
                bid["dawn_gate"] = screen.expected_dawn(bid, "candidate")
                screen.check_dawn(bid, analysis["focal"]["life"], s["tick"], case, "candidate", s["sun"])
                if not bid["dawn_gate"]["allowed"]:
                    actual.append(s["tick"])
                    for field, value in bid["dawn_gate"].items():
                        corrupt = copy.deepcopy(bid)
                        corrupt["dawn_gate"][field] = not value if type(value) is bool else value + 1
                        with self.subTest(field=field), self.assertRaises(RuntimeError):
                            screen.check_dawn(corrupt, analysis["focal"]["life"], s["tick"], case, "candidate", s["sun"])
                    corrupt = copy.deepcopy(bid)
                    corrupt["dawn_gate"]["active"] = 1
                    with self.assertRaises(RuntimeError):
                        screen.check_dawn(corrupt, analysis["focal"]["life"], s["tick"], case, "candidate", s["sun"])
            self.assertEqual(actual, ticks)

    def test_unavailable_and_nonapplicable_estimates(self):
        entry = screen.load_inputs()[2]["cases"][3]
        row = next(s for s in screen.steps(entry["arms"]["candidate"]["analysis"]) if s["tick"] == 910980)
        b = copy.deepcopy(row["bids"][0])
        b["daylight_gate"]["sun_strength"] = 24
        d = screen.expected_dawn(b, "candidate")
        self.assertTrue(d["active"] and d["applies"])
        self.assertFalse(d["allowed"] or d["estimate_available"])
        self.assertEqual((d["reserve"], d["first_light_phase"], d["payment_phase"]), (0, 0, 0))
        self.assertTrue(screen.expected_dawn(b, "control")["allowed"])
        for phase, action in ((63, 1), (128, 1), (255, 2), (124, 0)):
            b["energy_gate"]["sun_phase"], b["action"] = phase, action
            d = screen.expected_dawn(b, "candidate")
            self.assertTrue(d["allowed"])
            self.assertFalse(d["applies"] or d["estimate_available"] or d["stores_applies"])

    def test_all_saved_control_receipts_paid_prices_and_shortages(self):
        for entry in screen.load_inputs()[2]["cases"]:
            analysis, case = entry["arms"]["candidate"]["analysis"], entry["case"]
            life = analysis["focal"]["life"]
            rows = screen.steps(analysis)
            for original in rows:
                s = with_dawn(original, "control")
                row = {"tick": s["tick"], "bids": s["bids"], "climate": s["climate"], "bodies": [s["body"]] if s["body"] else []}
                *_, counts, changes = screen.check_row(row, {"sun": s["sun"], "plants": [s["plant"]]}, {life["id"]: life}, case, "control")
                self.assertFalse(counts or changes)
                self.assertEqual(screen.strip_dawn([s]), [original])
            events = screen.shortages(rows, life)
            self.assertEqual(len(events), {"rotating-49": 11, "rotating-50": 6}.get(case["id"], 0))
            self.assertEqual(sum(e["energy"]["unpaid"] for e in events), 38 if case["id"] == "rotating-49" else 0)
            self.assertEqual(sum(e["water"]["unpaid"] for e in events), 11 if case["id"] == "rotating-50" else 0)
            if case["id"] == "rotating-49":
                self.assertEqual([e["tick"] for e in events], list(range(913020, 913321, 60)) + list(range(916800, 917041, 60)))
                corrupt = copy.deepcopy(rows)
                s = next(s for s in corrupt if s["tick"] == events[0]["tick"])
                s["plant"]["stages"][1][3] ^= 2
                with self.assertRaises(RuntimeError):
                    screen.shortages(corrupt, life)
            if case["id"] == "rotating-50":
                self.assertEqual([e["tick"] for e in events], list(range(910680, 910981, 60)))


class NativeTests(unittest.TestCase):
    def setUp(self):
        if BUILD is None:
            self.skipTest("pass --build for native integration")
        temporary = tempfile.TemporaryDirectory(prefix="landing-dawn-")
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
                "--root-energy-reserve", "--root-afternoon-reserve", "--root-continuous-energy")

    def test_option_order_inactive_pixels_and_legacy_trace(self):
        case = {"tick": 120, "lineage": 45, "order": "fixed"}
        captures = []
        for index, options in enumerate((("--root-daylight-energy",),
                ("--root-daylight-energy", "--root-dawn-reserve"),
                ("--root-dawn-reserve", "--root-daylight-energy"))):
            arm = "candidate" if index else "control"
            stand, resource, frame = [self.directory / (str(index) + ext) for ext in (".jsonl", "-adult.jsonl", ".raw")]
            result = self.native(*self.args(), *options, "--stand-dawn", "--stand-trace", stand,
                "--stand-start", 15, "--stand-stop", 60, "--adult-trace", resource, "--adult-start", 15,
                "--adult-stop", 60, "--framebuffer", frame)
            rows, resources = [screen.adults.read_trace(p) for p in (stand, resource)]
            self.assertEqual(rows[0]["schema"], screen.SCHEMA)
            lives = {p["id"]: p for p in result["lineages"]}
            for row, r in zip(rows[1:-1], resources[1:-1], strict=True):
                screen.check_row(row, r, lives, case, arm)
            captures.append((screen.daylight_result(result, case, arm), screen.strip_dawn(rows[1:-1]), frame.read_bytes()))
        self.assertEqual(captures[0], captures[1])
        self.assertEqual(captures[1], captures[2])
        stand, frame = self.directory / "old.jsonl", self.directory / "old.raw"
        old = self.native(*self.args(), "--root-daylight-energy", "--stand-daylight", "--stand-trace", stand,
            "--stand-start", 15, "--stand-stop", 60, "--framebuffer", frame)
        self.assertEqual((old, screen.adults.read_trace(stand)[1:-1], frame.read_bytes()), captures[0])
        plain = self.native(*self.args(), "--root-dawn-reserve", "--root-daylight-energy")
        self.assertEqual(screen.daylight_result(plain, case, "candidate")["world_hash"], old["world_hash"])
        for field in ("run_hash", "root_dawn_reserve_probe"):
            bad = copy.deepcopy(plain)
            bad[field] = "00000000" if field == "run_hash" else {"version": True}
            with self.assertRaises(RuntimeError):
                screen.daylight_result(bad, case, "candidate")

    def test_invalid_and_duplicate_options_preserve_outputs(self):
        trace = self.directory / "trace.jsonl"
        base = (*self.args(), "--stand-trace", trace, "--stand-start", 15, "--stand-stop", 60)
        for flags in (("--root-dawn-reserve", "--stand-dawn"),
                      ("--root-dawn-reserve", "--root-daylight-energy", "--stand-daylight"),
                      ("--root-daylight-energy", "--root-dawn-reserve", "--root-dawn-reserve", "--stand-dawn"),
                      ("--root-daylight-energy", "--stand-dawn", "--stand-dawn"),
                      ("--root-daylight-energy", "--stand-dawn", "--stand-daylight"),
                      ("--root-daylight-energy", "--stand-dawn", "--stand-energy")):
            self.native(*base, *flags, valid=False)
            self.assertFalse(trace.exists())
        trace.write_bytes(b"preserve")
        self.native(*base, "--root-dawn-reserve", "--root-daylight-energy", "--stand-dawn", valid=False)
        self.assertEqual(trace.read_bytes(), b"preserve")


class FrozenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = screen.ROOT / RESULTS
        screen.require(screen.root.digest(path) == RESULTS_SHA, "frozen dawn results changed")
        with gzip.open(path, "rt") as stream:
            cls.value = json.load(stream)

    def test_offline_reanalysis_without_native_calls(self):
        with patch.object(screen.order.training, "native", side_effect=AssertionError("ran simulation")):
            screen.check_value(self.value)

    def test_survival_population_and_three_unchanged_histories(self):
        for index, entry in enumerate(self.value["cases"]):
            a, b = [entry["arms"][arm] for arm in screen.ARMS]
            for arm in (a, b):
                self.assertIsNone(arm["analysis"]["focal"]["life"]["death_tick"])
                self.assertEqual(arm["analysis"]["focal"]["life"]["seeds_created"], 0)
                self.assertEqual(screen.steps(arm["analysis"])[-1]["visit"]["blockers"], 4)
            for key in ("lineages", "seeds"):
                self.assertEqual(a["runs"]["trace"]["result"][key], b["runs"]["trace"]["result"][key])
            self.assertEqual(a["analysis"]["all_plants"]["outcomes"], b["analysis"]["all_plants"]["outcomes"])
            self.assertFalse(any(e["energy"]["unpaid"] for e in b["analysis"]["dawn"]["shortages"]))
            if index < 3:
                self.assertIsNone(screen.first_effect(entry["case"], entry["arms"]))
                self.assertEqual(screen.strip_dawn(screen.steps(a["analysis"])), screen.strip_dawn(screen.steps(b["analysis"])))
            self.assertEqual(b["analysis"]["dawn"]["counts"]["unavailable"], 0)

    def test_energy_rescue_and_growth_timing(self):
        entry = self.value["cases"][3]
        a, b = [entry["arms"][arm]["analysis"] for arm in screen.ARMS]
        effect = screen.first_effect(entry["case"], entry["arms"])
        self.assertEqual((effect["tick"], effect["phase"], effect["matching_prior_focal_samples"]), (910425, 87, 257))
        self.assertEqual((len(a["dawn"]["shortages"]), sum(e["energy"]["unpaid"] for e in a["dawn"]["shortages"])), (11, 38))
        self.assertEqual(b["dawn"]["shortages"], [])
        self.assertEqual(len(b["dawn"]["changed_choices"]), 40)
        for analysis, values, flower in ((a, [(128, 25), (0, 25), (126, 27), (0, 27)], 914325),
                                         (b, [(127, 24), (31, 24), (146, 27), (18, 27)], 913875)):
            h = screen.steps(analysis)
            actual = [next(s for s in h if s["tick"] == t)["plant"]["stages"][-1] for t in (911040, 912960, 914880, 916800)]
            self.assertEqual([(x[0], x[4]) for x in actual], values)
            self.assertEqual(next(s["tick"] for s in h if s["body"]["flowers"]), flower)
            self.assertEqual(next(s["tick"] for s in h if s["body"]["nodes"] == 32), 917535)

    def test_survivor_water_costs_and_changed_morphology(self):
        entry = self.value["cases"][4]
        a, b = [entry["arms"][arm]["analysis"] for arm in screen.ARMS]
        effect = screen.first_effect(entry["case"], entry["arms"])
        self.assertEqual((effect["tick"], effect["phase"], effect["matching_prior_focal_samples"]), (910140, 68, 228))
        self.assertEqual([c["tick"] for c in b["dawn"]["changed_choices"]], [910140, 910185, 910545, 910560, 910575])
        for analysis, nodes, roots, count, unpaid, flower in ((a, 31, 15, 6, 11, 910140), (b, 29, 13, 4, 7, 910200)):
            h = screen.steps(analysis)
            self.assertEqual((h[-1]["body"]["nodes"], h[-1]["body"]["roots"], h[-1]["body"]["tips"]), (nodes, roots, []))
            self.assertEqual((len(analysis["dawn"]["shortages"]), sum(e["water"]["unpaid"] for e in analysis["dawn"]["shortages"])), (count, unpaid))
            self.assertEqual(next(s["tick"] for s in h if s["body"]["flowers"]), flower)

    def test_corrupt_saved_evidence_rejected(self):
        for fault in ("budget", "scope", "margin", "shortages", "choices", "prefix", "identity"):
            value = {**self.value, "cases": list(self.value["cases"])}
            value["cases"][3] = copy.deepcopy(value["cases"][3])
            a = value["cases"][3]["arms"]["candidate"]
            row = next(s for s in screen.steps(a["analysis"]) if s["tick"] == 910425)
            if fault == "budget": value["full_replays"] += 1
            elif fault == "scope": row["bids"][0]["dawn_gate"]["active"] = False
            elif fault == "margin": row["bids"][0]["dawn_gate"]["stores_margin"] += 1
            elif fault == "shortages": a["analysis"]["dawn"]["shortages"].append({"tick": 0})
            elif fault == "choices": a["analysis"]["dawn"]["changed_choices"].append({"tick": 0})
            elif fault == "prefix": a["analysis"]["focal"]["steps"][0]["soil_water"] += 1
            elif fault == "identity": a["runs"]["trace"]["result"]["root_dawn_reserve_probe"]["version"] = 2
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                screen.check_value(value)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    options, rest = parser.parse_known_args()
    BUILD = options.build.resolve() if options.build else None
    unittest.main(argv=[__file__, *rest])
