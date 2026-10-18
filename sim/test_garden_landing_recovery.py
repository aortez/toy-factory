#!/usr/bin/env python3
"""All-plant observer parity, export boundaries and independent receipt checks."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_recovery as screen
from test_garden_landing_tools import run

BUILD = None
D, S = screen.DAY, screen.STEP


class RecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        saved, models = screen.load_inputs()
        cls.model_bytes = models[saved["models"]["single-s6d697834-live"]["model"]]

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="landing-recovery-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.model = self.root / "model.tgl"
        self.model.write_bytes(self.model_bytes)
        self.cli = BUILD / "toy-factory-garden-landing"

    def native(self, *args, **kwargs):
        raw = run([self.cli, *args], **kwargs)
        return json.loads(raw) if raw else None

    def args(self, stop=8 * D, target=None):
        args = ("placement-replay" if target is None else "vacancy-replay", self.model,
                "rainfed-crowded", "0x940cfdc4", "--climate", "seasonal", "--ticks", stop,
                "--ledger", "--shoot-reserve", "on", "--seed-placement", "spacing")
        return args if target is None else (*args, "--vacancy-at", 3 * D, "--vacancy-lineage", target)

    def sample(self, stem="a", start=S, end=8 * D, target=None):
        paths = [self.root / (stem + "-" + k + ".jsonl") for k in ("stand", "adult")]
        options = tuple(v for kind, path in zip(("stand", "adult"), paths, strict=True)
                        for v in ("--" + kind + "-trace", path, "--" + kind + "-start", start, "--" + kind + "-stop", end))
        frame = self.root / (stem + ".raw")
        result = self.native(*self.args(stop=max(8 * D, end), target=target), *options, "--framebuffer", frame)
        rows = [screen.adults.read_trace(p) for p in paths]
        audit = screen.analyze(*rows, result)
        return result, rows, paths, frame, audit

    def test_repeated_all_plants_and_plain_pixels(self):
        result, rows, paths, frame, audit = self.sample(start=55 * D, end=60 * D)
        repeat, again, copied, pixels, checked = self.sample("repeat", start=55 * D, end=60 * D)
        plain = self.root / "plain.raw"
        self.assertEqual(result, self.native(*self.args(stop=60 * D), "--framebuffer", plain))
        self.assertEqual((result, rows, audit), (repeat, again, checked))
        self.assertEqual([p.read_bytes() for p in paths], [p.read_bytes() for p in copied])
        self.assertEqual(frame.read_bytes(), pixels.read_bytes())
        self.assertEqual(frame.read_bytes(), plain.read_bytes())
        self.assertTrue(any(p["parent"] for p in audit["plants"]))
        self.assertTrue(any(p["death_shortage"] for p in audit["resources"]["plants"]))
        self.assertTrue(any(p["purchases"] for p in audit["plants"]))
        self.assertEqual(self.model.read_bytes(), self.model_bytes)

    def test_crossing_export_inventory_and_clipped_window(self):
        baseline = self.native(*self.args(stop=3 * D))
        target = min(p["id"] for p in baseline["lineages"] if p["death_tick"] is None and p["birth_tick"] + D < 3 * D)
        result, rows, _, _, audit = self.sample(start=3 * D - S, end=3 * D + 2 * S, target=target)
        for trace in rows:
            key = "bodies" if "bodies" in trace[1] else "plants"
            self.assertEqual([target in {p["id"] for p in r[key]} for r in trace[1:-1]], [True, True, False, False])
        removed = next(p for p in audit["resources"]["plants"] if p["id"] == target)
        self.assertIsNone(removed["death_tick"])
        self.assertIsNone(removed["death_shortage"])
        self.assertEqual(removed["last_tick"], 3 * D)
        clipped, clips, _, _, _ = self.sample("clipped", start=3 * D + S, end=3 * D + 2 * S, target=target)
        self.assertEqual(result, clipped)
        for full, partial in zip(rows, clips, strict=True):
            self.assertEqual(full[3:-1], partial[1:-1])

    def test_corrupt_inventory_gates_bank_budget_and_resource_fail(self):
        result, rows, _, _, _ = self.sample(end=D)
        for fault in ("clock", "body", "visit", "mask", "bank", "debit", "flower", "budget", "footer", "resource"):
            stand, resources = copy.deepcopy(rows)
            if fault == "clock":
                stand[1]["tick"] += S
            elif fault == "body":
                stand[1]["bodies"].pop()
            elif fault == "visit":
                stand[1]["reproduction"].append(stand[1]["reproduction"][0])
            elif fault == "mask":
                stand[1]["reproduction"][0]["blockers"] ^= 128
            elif fault == "bank":
                stand[1]["reproduction"][0]["bank"] += 1
            elif fault == "debit":
                stand[1]["reproduction"][0]["energy"] -= 1
            elif fault == "flower":
                stand[1]["reproduction"][0]["immature"] += 1
            elif fault == "budget":
                b = next(r["bids"][0] for r in stand[1:-1] if r["bids"])
                b["budget"]["required"] += 1
            elif fault == "footer":
                stand[-1]["run_hash"] = "00000000"
            else:
                resources[1]["plants"][0]["stages"][3][0] += 1
            with self.subTest(fault=fault), self.assertRaises((RuntimeError, ValueError)):
                screen.analyze(stand, resources, result)

    def test_flags_bounds_and_no_clobber(self):
        path = self.root / "safe.jsonl"
        options = ("--stand-trace", path, "--stand-start", S, "--stand-stop", 60)
        for start, end in ((0, 60), (S, 14), (16, 60), (S, 61), (S, 75), (-S, 60)):
            self.native(*self.args(stop=60), "--stand-trace", path, "--stand-start", start, "--stand-stop", end, valid=False)
            self.assertFalse(path.exists())
        for args in ((*self.args(stop=60), *options, "--stand-start", S),
                     (*self.args(stop=60), *options, "--placement-trace", self.root / "place.jsonl"),
                     (*tuple(a for a in self.args(stop=60) if a != "--ledger"), *options),
                     (*self.args(stop=60), "--stand-start", S, "--stand-stop", 60)):
            self.native(*args, valid=False)
            self.assertFalse(path.exists())
        self.native("budget-replay", self.model, "rainfed-crowded", "1", "--ticks", 60,
                    "--ledger", "--shoot-reserve", "on", *options, valid=False)
        self.assertFalse(path.exists())
        path.write_bytes(b"preserve")
        self.native(*self.args(stop=60), *options, valid=False)
        self.assertEqual(path.read_bytes(), b"preserve")
        with self.assertRaises(RuntimeError):
            screen.collect(BUILD, self.root, 1)

    def test_legacy_founder_rows_match_frozen_prefix(self):
        with gzip.open(screen.ROOT / "benchmarks/garden-seasons/landing-founders-results.json.gz", "rt") as stream:
            archive = json.load(stream)
        w = next(w for w in archive["worlds"] if w["model"] == "single-s6d697834-live" and w["case"]["climate"] == "seasonal")
        path = self.root / "legacy.jsonl"
        result = self.native("growth-replay", self.model, "rainfed-crowded", "0x940cfdc4", "--climate", "seasonal",
                            "--ticks", D, "--node-limit", "32", "--ledger", "--founder-trace", path,
                            "--founder-start", S, "--founder-stop", D)
        rows = screen.adults.read_trace(path)
        self.assertEqual(rows[0], {**w["arms"]["32"]["trace"][0], "stop": D})
        self.assertEqual(rows[1:-1], w["arms"]["32"]["trace"][1:D // S + 1])
        self.assertEqual(rows[-1], {"complete": True, "tick": D, "run_hash": result["run_hash"]})
        # The portable archive also pins the original native byte stream,
        # including field order/whitespace, not just parsed JSON values.
        old = w["arms"]["32"]
        full = self.root / "legacy-full.jsonl"
        value = self.native("growth-replay", self.model, "rainfed-crowded", "0x940cfdc4", "--climate", "seasonal",
                            "--ticks", old["result"]["tick"], "--node-limit", "32", "--ledger", "--founder-trace", full,
                            "--founder-start", old["trace"][0]["start"], "--founder-stop", old["trace"][0]["stop"])
        self.assertEqual(screen.digest(full), old["trace_sha256"])
        self.assertEqual(value, {**old["result"], "framebuffer_crc32": None})


class FrozenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = screen.ROOT / "benchmarks/garden-seasons/landing-recovery-gates-results.json.gz"
        if screen.digest(path) != "3fabe95f2d3fa20c6a4d1b97074e15d98d3095f13ba038c02fdc3884044df223":
            raise AssertionError("frozen recovery evidence changed")
        with gzip.open(path, "rt") as stream:
            cls.value = json.load(stream)

    def test_portable_panel_is_checked_without_simulation(self):
        with patch.object(screen.training, "native", side_effect=AssertionError("ran simulation")):
            screen.check_value(self.value)
        self.assertEqual(sum(a["audit"]["samples"] for w in self.value["worlds"] for a in w["arms"].values()), 184320)
        self.assertEqual(sum(a["audit"]["resources"]["plant_samples"] for w in self.value["worlds"]
                             for a in w["arms"].values()), 885063)

    def test_all_five_flower_early_but_cannot_access_bank(self):
        plants = []
        for w in self.value["worlds"]:
            selected = [p for p in w["arms"]["vacancy"]["audit"]["plants"] if p["id"] in w["cohorts"]["early_vacancy"]]
            self.assertEqual([p["id"] for p in selected], screen.FOCAL[w["model"]])
            plants.extend(selected)
        self.assertEqual([p["only_blocker_checks"]["bank"] for p in plants], [752, 564, 861, 461, 756])
        self.assertEqual(sum(sum(p["ready_window_masks"].values()) for p in plants), 5223)
        for p in plants:
            self.assertEqual(p["max_ready"], 1)
            self.assertEqual(p["first_ready"], p["first_flower"])
            self.assertLess(p["first_ready"], p["birth_tick"] + D)
            self.assertTrue(all(int(m) & 4 for m in p["ready_window_masks"]))
            self.assertEqual(p["purchases"], [])
            self.assertEqual(p["last_body"]["nodes"], 32)
            self.assertEqual(p["last_body"]["flowers"], 1)
            self.assertNotIn("stem", p["budget_denied"])

    def test_water_deaths_include_late_exception_and_terminal_discard(self):
        control, focal = [], []
        for w in self.value["worlds"]:
            for arm, cohort, selected in (("control", "old_control", control), ("vacancy", "early_vacancy", focal)):
                a = w["arms"][arm]["audit"]
                selected.extend(p for p in a["resources"]["plants"] if p["id"] in w["cohorts"][cohort])
                for p in a["plants"]:
                    if p["id"] not in w["cohorts"][cohort]:
                        continue
                    self.assertEqual([r["plant"]["stages"][1][3] & 6 for r in p["last_maintenance"]], [4] * 8)
                    last = p["last_maintenance"][-1]["plant"]
                    self.assertEqual(last["uptake"][1], [0, 0, 0, 2, 0, 0])
                    self.assertEqual(last["uptake"][0][3:5], [4, 4])
                    self.assertGreater(last["uptake"][0][-1], 0)
        self.assertEqual((len(control), len(focal)), (31, 5))
        self.assertTrue(all(p["death_shortage"] == "water" for p in control + focal))
        self.assertEqual(sum(199 * D < p["death_tick"] < 201 * D for p in control), 30)
        late = [p for p in control if p["death_tick"] > 201 * D]
        self.assertEqual([(p["id"], p["death_tick"]) for p in late], [(24, 828840)])
        self.assertEqual(late[0]["days"]["200"]["max_stress"], 2)
        self.assertEqual(late[0]["days"]["200"]["resources"]["water"]["final"], 512)

    def test_corrupt_cohort_accounting_and_parity_are_rejected(self):
        for fault in ("cohort", "gate", "resources", "parity"):
            bad = copy.deepcopy(self.value)
            a = bad["worlds"][1]["arms"]["vacancy"]
            if fault == "cohort":
                bad["worlds"][1]["cohorts"]["early_vacancy"] = []
            elif fault == "gate":
                a["audit"]["plants"][0]["blocker_checks"]["bank"] += 1
            elif fault == "resources":
                a["audit"]["resources"]["plants"][0]["resources"]["water"]["initial"] += 1
            else:
                a["frame_sha256"] = "0" * 64
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                screen.check_value(bad)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path, required=True)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *rest])
