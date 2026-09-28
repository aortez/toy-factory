#!/usr/bin/env python3
"""Native/reference agreement, honest variation denominators and portable shadow evidence."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import subprocess
import unittest

import garden_landing_shadow as shadow

BUILD = None
c = shadow.contract


def example(arm="flower", root=False):
    terrain = c.terrain(list(range(28)), [90 + i * 3 for i in range(28)], [(0, False), (10, True)])
    history = c.sample(c.reset(terrain), 1, terrain)
    xs = [31, 33, 36, 39, 41]
    bid = {"tip": 1, "kind": int(root), "x": 36, "base_x": 36, "dispersal": 0,
           "action": 1, "priority": 123, "candidates": [[x, 3] for x in xs[:3 if root else 5]]}
    packet = c.packet(history, 36, xs, 3, 0, stem=not root, origin_rule=arm)
    packet["values"] = [list(row) for row in packet["values"]]
    bid["packet"] = packet
    return history, bid


class ShadowTests(unittest.TestCase):
    def test_packet_and_corruption(self):
        for arm in shadow.ARMS:
            for root in (False, True):
                history, bid = example(arm, root)
                shadow.check_packet(history, bid, arm)
                broken = copy.deepcopy(bid)
                broken["packet"]["values"][0][0] ^= 1
                with self.assertRaises(RuntimeError):
                    shadow.check_packet(history, broken, arm)
                broken = copy.deepcopy(bid)
                broken["candidates"][0][1] = 2
                with self.assertRaises(RuntimeError):
                    shadow.check_packet(history, broken, arm)

    def test_clock_and_history_errors(self):
        history, _ = example()
        row = {"tick": 1, "samples": 1, "water": list(history.current.water),
               "light": list(history.current.light), "occupied": list(history.current.occupied),
               "traces": [list(r) for r in history.traces]}
        initial = c.reset(history.current)
        self.assertEqual(shadow.decode_cache(row, initial), history)
        for field, value in (("tick", 2), ("samples", 0), ("occupied", [4] * 28), ("traces", [[0] * 28] * 4)):
            bad = copy.deepcopy(row)
            bad[field] = value
            with self.assertRaises((RuntimeError, ValueError)):
                shadow.decode_cache(bad, initial)
        with self.assertRaises(ValueError):
            shadow.decode_cache(row, history)

    def test_invalid_zeros_never_create_variation(self):
        _, bid = example()
        bid["packet"]["valid"] = 3
        bid["packet"]["values"][2:] = [[0] * 8 for _ in range(4)]
        bid["candidates"][1:] = [[0, 0] for _ in range(4)]
        stats = shadow.new_stats()
        shadow.add_bid(stats, bid, "flower")
        self.assertEqual((stats["sources"], stats["choices"], stats["variable"], stats["in_bounds_variable"]), (2, 0, 0, 0))

    def test_unavailable_reading_is_not_a_choice(self):
        _, bid = example()
        bid["candidates"][1:] = [[x, 5] for x, _ in bid["candidates"][1:]]
        stats = shadow.new_stats()
        shadow.add_bid(stats, bid, "flower")
        self.assertEqual(stats["choices"], 0)
        self.assertEqual(stats["variable"], 0)
        self.assertEqual(stats["in_bounds_variable"], 1)

    def test_base_control_and_root_masking(self):
        stats = shadow.new_stats()
        for root in (False, True):
            _, bid = example("base", root)
            shadow.add_bid(stats, bid, "base")
        self.assertEqual((stats["queries"], stats["roots"], stats["stems"], stats["sources"]), (2, 1, 1, 6))
        self.assertEqual(stats["variable"], 0)
        self.assertEqual(stats["max_origins"], 1)
        self.assertTrue(all(sum(hist) == 6 for hist in stats["hist"]))
        self.assertEqual(shadow.merge_stats([stats, stats])["queries"], 4)

    def test_native_short_replay_and_modes(self):
        exe = None if BUILD is None else BUILD / "toy-factory-garden-landing-audit"
        if exe is None or not exe.is_file():
            self.skipTest("This ecology build has no landing observer")
        spec = {"scenario": "rainfed-crowded", "policy": "adaptive", "seed": "ed52188c"}
        cmd = [str(exe), spec["scenario"], spec["policy"], "0xed52188c", "3840"]
        raw = subprocess.check_output(cmd, timeout=30)
        self.assertEqual(raw, subprocess.check_output(cmd, timeout=30))
        rows = [json.loads(line) for line in raw.splitlines()]
        meta = rows.pop(0)
        self.assertEqual(meta, shadow.header(spec, meta["origin"], 3840, meta["dispersal"]))
        self.assertEqual(len(rows), 257)
        previous = None
        queries = 0
        for i, row in enumerate(rows):
            self.assertEqual(row["tick"], i * 15)
            previous = shadow.decode_cache(row["cache"], previous)
            self.assertEqual(previous.tick, i)
            for bid in row["bids"]:
                shadow.check_packet(previous, bid, meta["origin"], meta["dispersal"])
                queries += 1
        self.assertGreater(queries, 100)
        for mode in ("plain", "sample", "observe"):
            summary = json.loads(subprocess.check_output([*cmd, "--bench", mode], timeout=30))
            self.assertEqual((summary["hash"], summary["created"]), (rows[-1]["hash"], rows[-1]["created"]))
            self.assertEqual(summary["queries"], queries if mode == "observe" else 0)
            self.assertGreater(summary["cpu_us"], 0)
        for suffix in (["--bench", "capture"], ["--bad", "plain"]):
            result = subprocess.run([*cmd, *suffix], capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 2)

    def test_portable_evidence_when_present(self):
        folder = shadow.ROOT / "benchmarks/garden-seasons"
        evidence = folder / "landing-shadow-histories.json.gz"
        if not evidence.is_file():
            self.skipTest("No frozen shadow evidence collected yet")
        report = json.loads(gzip.decompress(evidence.read_bytes()))
        shadow.validate_report(report)
        self.assertEqual(shadow.compact(report), json.loads((folder / "landing-shadow-summary.json").read_text()))
        bad = copy.deepcopy(report["cases"][0])
        bad["days"][0]["stats"]["hist"][0][0] += 1
        with self.assertRaises(RuntimeError):
            shadow.validate_case(bad)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    args, rest = parser.parse_known_args()
    BUILD = args.build
    unittest.main(argv=[__file__, *rest])
