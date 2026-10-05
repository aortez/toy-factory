#!/usr/bin/env python3
"""Growth projection replay, identity, accounting and CLI safety checks."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest

import garden_landing_growth as screen
from test_garden_landing_tools import run

BUILD = None


class GrowthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        models, _, archive, _ = screen.load_inputs(screen.ROOT / "benchmarks/garden-seasons")
        cls.model_bytes = models[archive["models"]["single-s6d697834-live"]["model"]]

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="landing-growth-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.model = self.root / "model.tgl"
        self.model.write_bytes(self.model_bytes)
        self.cli = BUILD / "toy-factory-garden-landing"

    def native(self, *args, **kwargs):
        data = run([self.cli, *args], **kwargs)
        return json.loads(data) if data else None

    def args(self, ticks=8 * screen.DAY):
        return (self.model, "rainfed-crowded", "0x940cfdc4", "--ticks", ticks,
                "--climate", "seasonal", "--ledger")

    def test_off_exact_control_and_separate_identity(self):
        for ticks in (0, 15, 29, 8 * screen.DAY):
            old = self.native("arbitration-replay", *self.args(ticks), "--water-arbitration", "eligible")
            off = self.native("growth-replay", *self.args(ticks), "--node-limit", "off")
            self.assertEqual(screen.common_view(off, "off"), screen.arbitration.common_view(old, "eligible"))
            self.assertNotEqual(off["run_hash"], old["run_hash"])
        cap = self.native("growth-replay", *self.args(0), "--node-limit", "32")
        off = self.native("growth-replay", *self.args(0), "--node-limit", "off")
        self.assertNotEqual(cap["run_hash"], off["run_hash"])
        self.assertEqual(screen.common_view(cap, "32"), screen.common_view(off, "off"))
        for key in ("version", "node_limit", "water_arbitration"):
            bad = copy.deepcopy(cap)
            bad["growth_probe"][key] = 99
            with self.assertRaises(RuntimeError):
                screen.common_view(bad, "32")
        with self.assertRaises(RuntimeError):
            screen.common_view({**cap, "run_hash": "00000000"}, "32")

    def test_cap_traces_pixels_repeat_and_budgets(self):
        args = ("growth-replay", *self.args(), "--node-limit", "32")
        path, first_day = self.root / "adult.jsonl", self.root / "recruitment.jsonl"
        raw = self.root / "traced.raw"
        traced = self.native(*args, "--adult-trace", path, "--adult-start", 15, "--adult-stop", 8 * screen.DAY,
                             "--recruitment-trace", first_day, "--framebuffer", raw)
        plain_raw = self.root / "plain.raw"
        self.assertEqual(self.native(*args, "--framebuffer", plain_raw), traced)
        self.assertEqual(raw.read_bytes(), plain_raw.read_bytes())
        repeat = self.root / "repeat.jsonl"
        self.assertEqual(self.native(*args, "--adult-trace", repeat, "--adult-start", 15,
                                     "--adult-stop", 8 * screen.DAY), {**traced, "framebuffer_crc32": None})
        self.assertEqual(path.read_bytes(), repeat.read_bytes())
        rows = screen.adults.read_trace(path)
        counts = [s[4] for row in rows[1:-1] for p in row["plants"] for s in p["stages"] if s is not None]
        self.assertEqual(max(counts), 32)
        self.assertTrue(screen.adults.analyze(rows, traced)["plants"])
        self.assertEqual(len(screen.recruitment.analyze_trace(first_day, traced)["plants"]), traced["births"])
        self.assertEqual(self.model.read_bytes(), self.model_bytes)

    def test_cli_rejects_implicit_or_mixed_modes_and_preserves_files(self):
        args = ("growth-replay", *self.args(15))
        for suffix in ((), ("--node-limit", "31"), ("--node-limit", "33"), ("--node-limit", "0"),
                       ("--node-limit", "32", "--node-limit", "32"),
                       ("--node-limit", "32", "--water-arbitration", "eligible"),
                       ("--node-limit", "32", "--water-trace", self.root / "bids.jsonl"),
                       ("--node-limit", "32", "--reach-trace", self.root / "reach.jsonl")):
            self.native(*args, *suffix, valid=False)
        for command in ("replay", "arbitration-replay", "water-replay", "probe-replay", "trace-replay"):
            self.native(command, *self.args(15), "--node-limit", "32", valid=False)
        path = self.root / "keep.jsonl"
        path.write_bytes(b"preserve")
        self.native(*args, "--node-limit", "32", "--adult-trace", path,
                    "--adult-start", 15, "--adult-stop", 15, valid=False)
        self.assertEqual(path.read_bytes(), b"preserve")
        self.assertFalse((self.root / "bids.jsonl").exists())
        self.assertFalse((self.root / "reach.jsonl").exists())

    def test_portable_panel_and_retained_gallery(self):
        path = screen.ROOT / "benchmarks/garden-seasons/landing-growth-results.json.gz"
        screen.verify(path)
        value = json.loads(gzip.decompress(path.read_bytes()))
        self.assertFalse(value["comparison"]["passes_screen"])
        groups = value["comparison"]["comparisons"]["eligible"]["groups"]
        self.assertEqual(groups["seasonal"]["scores"]["paired_counts"], {"wins": 6, "ties": 0, "losses": 0})
        self.assertEqual([groups["seasonal"]["totals"][a]["late_child_survivors"] for a in ("control", "water")], [61, 107])
        self.assertEqual(groups["steady"]["totals"]["water"]["total_ticks"], 0)
        focus = next(w for w in value["worlds"] if w["id"] == screen.adults.CASE)
        gaps = {a: [(g["first_tick"], g["end_exclusive"]) for g in d["focus"]["gaps"]] for a, d in focus["arms"].items()}
        self.assertIn((486960, 494790), gaps["off"])
        self.assertNotIn((486960, 494790), gaps["32"])
        for name, sheet in value["sheets"].items():
            image = screen.ROOT / "benchmarks/garden-seasons/frames" / ("landing-growth-" + name + ".png")
            self.assertEqual(screen.digest(image), sheet["sha256"])

    def test_comparison_rejects_missing_world_and_retains_failures(self):
        _, old, archive, _ = screen.load_inputs(screen.ROOT / "benchmarks/garden-seasons")
        value = json.loads(gzip.decompress((screen.ROOT / "benchmarks/garden-seasons/landing-growth-results.json.gz").read_bytes()))
        with self.assertRaises(RuntimeError):
            screen.compare(value["worlds"][:-1], old, archive)
        changed = copy.deepcopy(value["worlds"])
        changed[0]["arms"]["32"]["metrics"]["first_empty_tick"] = 15
        compared = screen.compare(changed, old, archive)
        self.assertTrue(all(not c["gates"]["no_earlier_or_new_empty_world"] for c in compared["comparisons"].values()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path, required=True)
    args, remaining = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *remaining])
