#!/usr/bin/env python3
"""Budget identities, unchanged proposals, replay parity and saved-screen checks."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest

import garden_landing_budget as screen
from test_garden_landing_tools import run

BUILD = None
PORTABLE = screen.ROOT / "benchmarks/garden-seasons/landing-budget-results.json.gz"


class BudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        models, _, archive, _ = screen.growth.load_inputs(screen.ROOT / "benchmarks/garden-seasons")
        cls.model_bytes = models[archive["models"]["single-s6d697834-live"]["model"]]

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="landing-budget-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.model = self.root / "model.tgl"
        self.model.write_bytes(self.model_bytes)
        self.cli = BUILD / "toy-factory-garden-landing"

    def native(self, *args, **kwargs):
        raw = run([self.cli, *args], **kwargs)
        return json.loads(raw) if raw else None

    def args(self, arm="reserve", stop=2 * screen.DAY):
        return ("budget-replay", self.model, "rainfed-crowded", "0x940cfdc4", "--climate", "seasonal",
                "--ticks", stop, "--ledger", "--shoot-reserve", "on" if arm == "reserve" else "off")

    def sample(self, arm="reserve", stem="a", start=15, end=2 * screen.DAY, stop=2 * screen.DAY):
        trace, early, raw = (self.root / (stem + suffix) for suffix in (".jsonl", "-early.jsonl", ".raw"))
        result = self.native(*self.args(arm, stop), "--founder-trace", trace, "--founder-start", start,
            "--founder-stop", end, "--adult-trace", early, "--adult-start", start, "--adult-stop", end,
            "--framebuffer", raw)
        rows, resources = screen.adults.read_trace(trace), screen.adults.read_trace(early)
        audit = screen.founders.analyze(rows, result, "32", resources, budget_mode=screen.MODES[arm])
        return rows, resources, result, audit, raw.read_bytes()

    def test_identities_and_unchanged_initial_state(self):
        states = {arm: self.native(*self.args(arm, 0)) for arm in screen.MODES}
        states.update({arm: self.native("growth-replay", self.model, "rainfed-crowded", "0x940cfdc4",
            "--climate", "seasonal", "--ticks", 0, "--ledger", "--node-limit", arm) for arm in screen.growth.ARMS})
        self.assertEqual(len({s["run_hash"] for s in states.values()}), 4)
        normalized = [screen.common_view(s, arm) for arm, s in states.items()]
        self.assertTrue(all(s == normalized[0] for s in normalized))
        for key in ("version", "node_limit", "shoot_reserve", "water_arbitration"):
            bad = copy.deepcopy(states["reserve"])
            bad["budget_probe"][key] = 99
            with self.assertRaises(RuntimeError):
                screen.common_view(bad, "reserve")
        with self.assertRaises(RuntimeError):
            screen.common_view({**states["eligible"], "run_hash": states["reserve"]["run_hash"]}, "eligible")

    def test_repeat_observer_pixels_window_and_budget_receipts(self):
        for arm in screen.MODES:
            first = self.sample(arm, stem=arm)
            self.assertEqual(first, self.sample(arm, stem=arm + "-repeat"))
            raw = self.root / (arm + "-plain.raw")
            self.assertEqual(first[2], self.native(*self.args(arm), "--framebuffer", raw))
            self.assertEqual(first[-1], raw.read_bytes())
            clipped = self.sample(arm, stem=arm + "-window", start=screen.DAY, end=screen.DAY + 60)
            self.assertEqual(clipped[2], first[2])
            self.assertEqual(clipped[4], first[4])
            self.assertEqual(clipped[0][1:-1], [r for r in first[0][1:-1] if screen.DAY <= r["tick"] <= screen.DAY + 60])
            self.assertTrue(all(b["raw_action"] == b["action"] for r in first[0][1:-1] for b in r["bids"]))
            self.assertTrue(any(not b["budget"]["allowed"] for r in first[0][1:-1] for b in r["bids"]))
            self.assertTrue(all(b["nodes"] <= 32 for r in first[0][1:-1] for b in r["bodies"]))
        self.assertEqual(self.model.read_bytes(), self.model_bytes)
        for stop in (15, 29):
            sample = self.sample(stem=str(stop), end=15, stop=stop)
            self.assertEqual(sample[3]["samples"], 1)

    def test_corrupt_budget_gate_and_body_receipts_fail(self):
        rows, resources, result, _, _ = self.sample()
        i = next(i for i, r in enumerate(rows) if r.get("bids"))
        for field in ("leader", "remaining", "required", "allowed", "allocates", "flower"):
            bad = copy.deepcopy(rows)
            budget = bad[i]["bids"][0]["budget"]
            budget[field] = not budget[field] if type(budget[field]) is bool else budget[field] + 1
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                screen.founders.analyze(bad, result, "32", resources, budget_mode=2)
        bad = copy.deepcopy(rows)
        bad[i]["bids"][0]["action"] = (bad[i]["bids"][0]["action"] + 1) % 3
        with self.assertRaises(RuntimeError):
            screen.founders.analyze(bad, result, "32", resources, budget_mode=2)
        with self.assertRaises(RuntimeError):
            screen.founders.analyze(rows, result, "32", resources, budget_mode=1)

    def test_explicit_options_and_no_clobber(self):
        base = self.args()[:-2]
        for extra in ((), ("--shoot-reserve", "32"), ("--node-limit", "32"),
                      ("--shoot-reserve", "on", "--shoot-reserve", "off"),
                      ("--shoot-reserve", "on", "--node-limit", "32"),
                      ("--shoot-reserve", "on", "--water-arbitration", "eligible"),
                      ("--shoot-reserve", "on", "--reach-trace", self.root / "bad.jsonl",
                       "--reach-trace", self.root / "bad.jsonl")):
            self.native(*base, *extra, valid=False)
        self.assertFalse((self.root / "bad.jsonl").exists())
        self.native("growth-replay", *base[1:], "--shoot-reserve", "on", valid=False)
        keep = self.root / "keep.jsonl"
        keep.write_bytes(b"preserve")
        self.native(*self.args(), "--founder-trace", keep, "--founder-start", 15,
                    "--founder-stop", 2 * screen.DAY, valid=False)
        self.assertEqual(keep.read_bytes(), b"preserve")

    def test_saved_full_panel_and_galleries(self):
        screen.verify(PORTABLE)
        with gzip.open(PORTABLE, "rt") as stream:
            data = json.load(stream)
        self.assertEqual(len(data["worlds"]), 12)
        self.assertEqual(set(data["comparison"]["comparisons"]), {"eligible", "32", "off", "veto", "ordinary"})
        for w in data["worlds"]:
            self.assertEqual(set(w["arms"]), set(screen.ARMS))
            self.assertEqual(screen.common_view(w["arms"]["32"]["result"], "32"),
                             screen.common_view(w["arms"]["eligible"]["result"], "eligible"))
            self.assertEqual(w["arms"]["32"]["frame"]["raw_sha256"], w["arms"]["eligible"]["frame"]["raw_sha256"])
        self.assertFalse(data["comparison"]["passes_screen"])
        self.assertTrue(all(not c["passes_screen"] for c in data["comparison"]["comparisons"].values()))
        reserve = [w["arms"]["reserve"] for w in data["worlds"]]
        flowers = [p for a in reserve for p in a["founder_audit"]["founders"] if p["species"] == 0]
        self.assertEqual(len(flowers), 22)
        self.assertTrue(all(p["max_flowers"] > 0 for p in flowers))
        self.assertFalse(any(not p["parent"] and p["death_tick"] is not None and p["death_tick"] <= 2 * screen.DAY
                            for a in reserve for p in a["founder_audit"]["early_resource_audit"]["plants"]))
        seasonal = [w for w in data["worlds"] if w["case"]["climate"] == "seasonal"]
        self.assertEqual([sum(w["arms"][a]["metrics"]["late_child_survivors"] for w in seasonal)
                          for a in ("eligible", "reserve")], [107, 41])
        self.assertEqual(sum(w["arms"]["reserve"]["metrics"]["zero_periods"] for w in seasonal), 4)
        with self.assertRaises(RuntimeError):
            screen.compare(data["worlds"][:-1], {"worlds": []}, {"worlds": []})
        for name, sheet in data["sheets"].items():
            path = screen.ROOT / "benchmarks/garden-seasons/frames" / ("landing-budget-" + name + ".png")
            self.assertEqual(screen.digest(path), sheet["sha256"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path, required=True)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *rest])
