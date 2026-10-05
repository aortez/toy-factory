#!/usr/bin/env python3
"""Placement mapping, observer parity, receipt validation and frozen evidence."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest

import garden_landing_placement as screen
from test_garden_landing_tools import run

BUILD = None
PORTABLE = screen.ROOT / "benchmarks/garden-seasons/landing-placement-results.json.gz"


class PlacementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        models, _, archive, _ = screen.growth.load_inputs(screen.ROOT / "benchmarks/garden-seasons")
        cls.model_bytes = models[archive["models"]["single-s6d697834-live"]["model"]]

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="landing-placement-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.model = self.root / "model.tgl"
        self.model.write_bytes(self.model_bytes)
        self.cli = BUILD / "toy-factory-garden-landing"

    def native(self, *args, **kwargs):
        raw = run([self.cli, *args], **kwargs)
        return json.loads(raw) if raw else None

    def args(self, arm="spacing", stop=8 * screen.DAY):
        return ("placement-replay", self.model, "rainfed-crowded", "0x940cfdc4", "--climate", "seasonal",
                "--ticks", stop, "--ledger", "--shoot-reserve", "off" if arm == "eligible" else "on",
                "--seed-placement", "spacing" if arm == "spacing" else "off")

    def sample(self, arm="spacing", stem="a", stop=8 * screen.DAY):
        paths = [self.root / (stem + suffix) for suffix in (".jsonl", "-children.jsonl", "-reach.jsonl", ".raw")]
        result = self.native(*self.args(arm, stop), "--placement-trace", paths[0], "--recruitment-trace", paths[1],
                             "--reach-trace", paths[2], "--framebuffer", paths[3])
        child = screen.growth.recruitment.analyze_trace(paths[1], result)
        reach = screen.reach.analyze_trace(paths[2], result, child)
        receipts = screen.read_trace(paths[0], stop, arm == "spacing")
        sites = screen.purchase_sites(reach)
        audit = screen.analyze(result, receipts, sites, arm == "spacing")
        return result, receipts, sites, audit, [p.read_bytes() for p in paths]

    def test_mapping_preserves_aliases_fallback_and_original_clear(self):
        for origin in range(28):
            for trait in range(-2, 3):
                choices = screen.reach.support(origin, trait)
                for blocked_columns in (set(), set(choices), set(choices[1:3])):
                    mask = sum(1 << i for i, c in enumerate(choices) if c in blocked_columns)
                    clear = [i for i, c in enumerate(choices) if c not in blocked_columns]
                    for r in (*range(42), 0xffffffff):
                        p = {"origin": origin, "dispersal": trait, "choices": choices, "random": r, "blocked": mask}
                        self.assertEqual(screen.choose(p, False), r % 6)
                        expected = clear[(r // 6) % len(clear)] if clear and choices[r % 6] in blocked_columns else r % 6
                        self.assertEqual(screen.choose(p, True), expected)
        bad = {"origin": 0, "dispersal": 0, "choices": [5, 5, 6, 6, 7, 7], "random": 0, "blocked": 1}
        with self.assertRaises(RuntimeError):
            screen.choose(bad, True)

    def test_identities_off_controls_repeat_and_pixels(self):
        initial = {a: self.native(*self.args(a, 0)) for a in screen.ARMS}
        self.assertEqual(len({r["run_hash"] for r in initial.values()}), 3)
        normalized = [screen.common_view(r, a) for a, r in initial.items()]
        self.assertTrue(all(r == normalized[0] for r in normalized))
        for arm in screen.ARMS:
            first = self.sample(arm, arm)
            self.assertEqual(first, self.sample(arm, arm + "-repeat"))
            raw = self.root / (arm + "-plain.raw")
            self.assertEqual(first[0], self.native(*self.args(arm), "--framebuffer", raw))
            self.assertEqual(first[-1][-1], raw.read_bytes())
            self.assertGreater(len(first[1]["purchases"]), 0)
            if arm != "spacing":
                old = self.native("budget-replay", *self.args(arm)[1:-2], "--framebuffer", self.root / (arm + "-old.raw"))
                self.assertEqual(screen.common_view(first[0], arm), screen.budget.common_view(old, arm))
                self.assertEqual(raw.read_bytes(), (self.root / (arm + "-old.raw")).read_bytes())
        self.assertEqual(self.model.read_bytes(), self.model_bytes)
        for field in ("version", "enabled"):
            bad = copy.deepcopy(initial["spacing"])
            bad["placement_probe"][field] = 99
            with self.assertRaises(RuntimeError):
                screen.common_view(bad, "spacing")
        for stop in (0, 15, 29):
            sample = self.sample(stem=str(stop), stop=stop)
            self.assertEqual(sample[1]["ecology_samples"], stop // 15)

    def test_corrupt_receipts_fail(self):
        result, receipts, sites, _, _ = self.sample()
        for field in ("parent", "origin", "dispersal", "blocked", "selected", "tick"):
            bad = copy.deepcopy(receipts)
            bad["purchases"][0][field] += 1
            with self.subTest(field=field), self.assertRaises((RuntimeError, KeyError)):
                screen.analyze(result, bad, sites, True)
        for changed in (receipts["purchases"][:-1], receipts["purchases"] + receipts["purchases"][:1]):
            with self.assertRaises(RuntimeError):
                screen.analyze(result, {**receipts, "purchases": changed}, sites, True)
        bad_sites = copy.deepcopy(sites)
        bad_sites[0]["sites"] = "00" * 28
        with self.assertRaises(RuntimeError):
            screen.analyze(result, receipts, bad_sites, True)
        rows = (self.root / "a.jsonl").read_text().splitlines()
        for i, bad in enumerate((rows[:-1], rows[:1] + rows[2:], rows + [rows[-1]], rows[1:])):
            path = self.root / f"bad-{i}.jsonl"
            path.write_text("\n".join(bad) + "\n")
            with self.assertRaises((RuntimeError, StopIteration)):
                screen.read_trace(path, result["tick"], True)

    def test_explicit_options_and_no_clobber(self):
        base = self.args()[:-2]
        path = self.root / "bad.jsonl"
        for extra in ((), ("--seed-placement", "on"), ("--seed-placement", "spacing", "--seed-placement", "off"),
                      ("--seed-placement", "spacing", "--placement-trace", path, "--placement-trace", path),
                      ("--seed-placement", "spacing", "--founder-trace", path)):
            self.native(*base, *extra, valid=False)
        self.assertFalse(path.exists())
        self.native("budget-replay", *self.args()[1:], valid=False)
        self.native(*[x for x in self.args() if x != "--ledger"], "--placement-trace", path, valid=False)
        self.assertFalse(path.exists())
        path.write_bytes(b"preserve")
        self.native(*self.args(), "--placement-trace", path, valid=False)
        self.assertEqual(path.read_bytes(), b"preserve")

    def test_saved_panel(self):
        screen.verify(PORTABLE)
        with gzip.open(PORTABLE, "rt") as stream:
            data = json.load(stream)
        self.assertEqual(len(data["worlds"]), 12)
        self.assertEqual(set(data["comparison"]["comparisons"]), {"eligible", "reserve"})
        self.assertEqual(data["training_runs"], 0)
        for name, sheet in data["sheets"].items():
            path = screen.ROOT / "benchmarks/garden-seasons/frames" / ("landing-placement-" + name + ".png")
            self.assertEqual(screen.digest(path), sheet["sha256"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path, required=True)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *rest])
