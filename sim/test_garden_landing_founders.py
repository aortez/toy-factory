#!/usr/bin/env python3
"""Founder observer parity, budgets, windows, failures and frozen panel verification."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest

import garden_landing_founders as trace
from test_garden_landing_tools import run

BUILD = None
PORTABLE = trace.ROOT / "benchmarks/garden-seasons/landing-founders-results.json.gz"


class FounderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        models, _, archive, _ = trace.previous.load_inputs(trace.ROOT / "benchmarks/garden-seasons")
        meta = archive["models"]["single-s6d697834-live"]
        cls.model_bytes = models[meta["model"]]

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="landing-founders-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.model = self.root / "model.tgl"
        self.model.write_bytes(self.model_bytes)
        self.cli = BUILD / "toy-factory-garden-landing"

    def native(self, *args, **kwargs):
        raw = run([self.cli, *args], **kwargs)
        return json.loads(raw) if raw else None

    def sample(self, arm="32", start=15, end=None, stop=None, stem="a"):
        end = 2 * trace.DAY if end is None else end
        stop = end if stop is None else stop
        args = ("growth-replay", self.model, "rainfed-crowded", "0x940cfdc4", "--ticks", stop,
                "--climate", "seasonal", "--node-limit", arm, "--ledger")
        path, early = self.root / (stem + ".jsonl"), self.root / (stem + "-early.jsonl")
        result = self.native(*args, "--founder-trace", path, "--founder-start", start, "--founder-stop", end,
                             "--adult-trace", early, "--adult-start", start, "--adult-stop", end)
        rows, resources = trace.adults.read_trace(path), trace.adults.read_trace(early)
        audit = trace.analyze(rows, result, arm, resources)
        return args, rows, resources, result, audit

    def test_plain_repeat_clipped_window_and_framebuffer_parity(self):
        for arm in trace.ARMS:
            args, rows, resources, result, audit = self.sample(arm, stem=arm)
            self.assertEqual(self.native(*args), result)
            _, again, early, value, checked = self.sample(arm, stem=arm + "-again")
            self.assertEqual((rows, resources, result, audit), (again, early, value, checked))
            _, clipped, _, value, _ = self.sample(arm, start=trace.DAY, end=trace.DAY + 60,
                stop=result["tick"], stem=arm + "-window")
            self.assertEqual(value, result)
            self.assertEqual(clipped[1:-1], [r for r in rows[1:-1] if trace.DAY <= r["tick"] <= trace.DAY + 60])
            plain, observed = self.root / (arm + "-plain.raw"), self.root / (arm + "-observed.raw")
            a = self.native(*args, "--framebuffer", plain)
            b = self.native(*args, "--framebuffer", observed, "--founder-trace", self.root / (arm + "-frame.jsonl"),
                            "--founder-start", 15, "--founder-stop", result["tick"])
            self.assertEqual(a, b)
            self.assertEqual(plain.read_bytes(), observed.read_bytes())
        self.assertEqual(self.model.read_bytes(), self.model_bytes)

    def test_single_sample_non_ecology_horizon_and_early_deaths(self):
        for start, end, stop in ((15, 15, 15), (15, 15, 29), (30, 75, 89)):
            _, rows, _, result, audit = self.sample(start=start, end=end, stop=stop, stem=str(stop))
            self.assertEqual(audit["samples"], (end - start) // trace.STEP + 1)
            self.assertEqual(rows[-1]["run_hash"], result["run_hash"])
        _, _, _, _, off = self.sample("off", stem="deaths")
        self.assertTrue(any(p["living_history_complete"] for p in off["founders"]))
        self.assertTrue(any(p["death_shortage"] for p in off["early_resource_audit"]["plants"]))

    def test_corrupt_receipts_inventory_projection_and_footer_fail(self):
        _, rows, resources, result, _ = self.sample()
        bi = next(i for i, r in enumerate(rows) if any(b["raw_action"] != b["action"] for b in r.get("bids", [])))
        for field in ("gap", "body", "visit", "mask", "projection", "duplicate_bid", "footer", "resource"):
            bad, early = copy.deepcopy(rows), copy.deepcopy(resources)
            if field == "gap":
                bad.pop(2)
            elif field == "body":
                bad[1]["bodies"].append(bad[1]["bodies"][0])
            elif field == "visit":
                bad[1]["reproduction"].pop()
            elif field == "mask":
                bad[1]["reproduction"][0]["blockers"] ^= 128
            elif field == "projection":
                b = next(b for b in bad[bi]["bids"] if b["action"] != b["raw_action"])
                b["action"] = b["raw_action"]
            elif field == "duplicate_bid":
                bad[bi]["bids"].append(bad[bi]["bids"][0])
            elif field == "footer":
                bad[-1]["run_hash"] = "00000000"
            else:
                early[1]["plants"][0]["stages"][3][0] += 1
            with self.subTest(field=field), self.assertRaises((RuntimeError, ValueError)):
                trace.analyze(bad, result, "32", early)

    def test_argument_and_file_safety(self):
        base = ("growth-replay", self.model, "rainfed-crowded", "1", "--ticks", 60,
                "--climate", "steady", "--node-limit", "32")
        path = self.root / "safe.jsonl"
        for start, end in ((0, 60), (15, 14), (16, 60), (15, 61), (15, 75), (-15, 60)):
            self.native(*base, "--ledger", "--founder-trace", path, "--founder-start", start,
                        "--founder-stop", end, valid=False)
            self.assertFalse(path.exists())
        for extra in (("--founder-trace", path), ("--founder-start", 15, "--founder-stop", 60),
                      ("--founder-trace", path, "--founder-start", 15, "--founder-stop", 60, "--founder-start", 15)):
            self.native(*base, "--ledger", *extra, valid=False)
            self.assertFalse(path.exists())
        options = ("--founder-trace", path, "--founder-start", 15, "--founder-stop", 60)
        self.native(*base, *options, valid=False)
        self.assertFalse(path.exists())
        path.write_bytes(b"preserve")
        self.native(*base, "--ledger", *options, valid=False)
        self.assertEqual(path.read_bytes(), b"preserve")
        self.native("replay", self.model, "rainfed", "1", "--ticks", 60, "--climate", "steady",
                    "--ledger", *options, valid=False)
        self.assertEqual(path.read_bytes(), b"preserve")

    def test_portable_panel_and_complete_seasonal_founder_lifetimes(self):
        trace.verify(PORTABLE)
        with gzip.open(PORTABLE, "rt") as stream:
            data = json.load(stream)
        self.assertEqual(len(data["worlds"]), 12)
        seasonal, steady = [], []
        early_deaths = {arm: [] for arm in trace.ARMS}
        for world in data["worlds"]:
            for arm, value in world["arms"].items():
                self.assertEqual(value["audit"]["samples"], 64 * 256)
                self.assertEqual(value["audit"]["early_resource_audit"]["ecology_samples"], 2 * 256)
                early_deaths[arm].extend(p for p in value["audit"]["early_resource_audit"]["plants"]
                    if not p["parent"] and p["death_tick"] is not None and p["death_tick"] <= trace.RESOURCE_END)
                if arm == "32":
                    flowers = [p for p in value["audit"]["founders"] if p["species"] == 0]
                    if world["case"]["climate"] == "seasonal":
                        self.assertEqual(len(flowers), 2)
                        self.assertTrue(all(p["living_history_complete"] for p in flowers))
                        seasonal.extend(flowers)
                    else:
                        steady.extend(flowers)
        self.assertEqual(len(seasonal), 12)
        self.assertEqual(sum(p["living_visits"] for p in seasonal), 171920)
        self.assertEqual(sum(p["flower_only_checks"] for p in seasonal), 763)
        self.assertTrue(all(p["max_flowers"] == 0 and not p["purchases"] for p in seasonal))
        self.assertEqual(sorted(p["last_living_body"]["body"]["maximum_stem_depth"] for p in seasonal),
                         [11] * 11 + [12])
        self.assertEqual(sum(p["projected"].get("stem", 0) for p in seasonal), 170396)
        fertile = [p for p in steady if p["max_flowers"] > 0]
        self.assertEqual(len(steady), 10)
        self.assertEqual(len(fertile), 2)
        self.assertEqual([p["last_living_body"]["body"]["roots"] for p in fertile], [16, 16])
        self.assertEqual(len(early_deaths["off"]), 41)
        self.assertTrue(all(p["death_shortage"] == "energy" for p in early_deaths["off"]))
        self.assertEqual(early_deaths["32"], [])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path, required=True)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *rest])
