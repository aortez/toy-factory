#!/usr/bin/env python3
"""Fixed diagnostic selection, live conservation, malformed traces and exports."""

import copy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import garden_season_seedlings as replay


def plant(energy=64, water=24):
    return {"id": 2, "dead": False, "energy": energy, "water": water, "flags": 0,
            "nodes": 4, "roots": 2, "species": "flower", "vigor": 0, "stress": 0,
            "energy_income": 0, "water_income": 0, "active_leaves": 1,
            "root_cells": [[1, 0, 1, 20], [1, 1, 2, 40]], "reproduction_cooldown": 0,
            "agent": {key: 0 for key in ("decisions", "extend", "root_extend", "shoot_extend", "finish", "wait")}}


def live_history():
    previous, result = None, []
    for tick in range(15, 15 + replay.DAY + 1, 15):
        current = plant()
        if previous is not None:
            current.update(energy=min(256, previous["energy"] + 2) - int(tick % 60 == 0),
                           water=min(512, previous["water"] + 1) - int(tick % 60 == 0),
                           energy_income=2, water_income=1)
        row = {"tick": tick, "sun_phase": (64 + tick // 15) % 256, "sun_strength": 80}
        result.append({"tick": tick, "phase": row["sun_phase"], "sun_strength": 80,
                       "plant": current, "terminal": None, "bids": [],
                       **replay.live_point(row, previous, current, [])})
        previous = current
    return result


class SeedlingTests(unittest.TestCase):
    def test_selection_is_fixed_and_does_not_invent_control(self):
        parent = replay.load_input()
        chosen = replay.selection(parent)
        self.assertEqual([(r["case"], r["wide"]["id"], r["control"]["id"] if r["control"] else None)
                          for r in chosen], [("seasonal-rainfed-baseline-a9c30c1f", 35, 34),
                                             ("seasonal-rainfed-crowded-baseline-ed52188d", 41, None),
                                             ("seasonal-rainfed-crowded-adaptive-4f0b9246", 39, 26)])
        self.assertEqual(len(replay.jobs_for(parent, chosen)), 6)
        self.assertEqual(sum(len(j["plants"]) for j in replay.jobs_for(parent, chosen)), 5)
        parent["cases"]["wide"].reverse()
        for c in parent["cases"]["wide"]:
            c["plants"].reverse()
        self.assertEqual(replay.selection(parent), chosen)
        for c in parent["cases"]["wide"]:
            for death in c["deaths"]:
                if death["flags"] == 5:
                    death["flags"] = 7
        with self.assertRaisesRegex(RuntimeError, "category"):
            replay.selection(parent)

    def test_birth_spending_and_bid_store_reconciliation(self):
        current = plant(55, 19)
        current["agent"].update(decisions=1, extend=1, root_extend=1)
        row = {"tick": 15}
        bids = [{"energy": 64, "water": 24}]
        point = replay.live_point(row, None, current, bids)
        self.assertEqual(point["budget"]["energy_growth"], 9)
        self.assertEqual(point["budget"]["water_growth"], 5)
        self.assertEqual(point["upkeep_due"], {"energy": 0, "water": 0})
        self.assertEqual(point["root_post_water"], 60)
        self.assertEqual(point["pre_growth"], {"energy": 64, "water": 24})
        for mutate in (lambda p: p.update(water=18),
                       lambda p: p["agent"].update(root_extend=2),
                       lambda p: p["root_cells"].pop()):
            bad = copy.deepcopy(current)
            mutate(bad)
            with self.assertRaises(RuntimeError):
                replay.live_point(row, None, bad, bids)
        with self.assertRaisesRegex(RuntimeError, "Bid/budget"):
            replay.live_point(row, None, current, [{"energy": 63, "water": 24}])

    def test_first_day_closes_including_overflow_and_upkeep(self):
        history = live_history()
        record = {"id": 2, "birth_tick": 15, "death_tick": None}
        result = replay.describe(record, history)
        self.assertEqual(result["observed_steps"], 257)
        self.assertEqual(result["totals"]["energy_income"], 512)
        self.assertEqual(result["totals"]["energy_upkeep"], 64)
        self.assertGreater(result["totals"]["energy_overflow"], 0)
        self.assertEqual(result["upkeep_due"], {"energy": 64, "water": 64})
        self.assertIsNone(result["checkpoints"]["first_energy_shortage"])
        self.assertIsNotNone(result["checkpoints"]["first_sunset"])
        for mutate in (lambda h: h.pop(), lambda h: h[10]["budget"].update(energy_income=3),
                       lambda h: h[-1]["plant"].update(dead=True)):
            bad = copy.deepcopy(history)
            mutate(bad)
            with self.assertRaises(RuntimeError):
                replay.describe(record, bad)

    def test_trace_rejects_truncation_gaps_unknown_and_misordered_events(self):
        world = {"type": "world", "tick": 0, "death_audit_version": 1, "plants": [],
                 "deaths": 0, "births": 0, "sun_phase": 64}
        variants = [[], [world], [{**world, "tick": 15}], [{**world, "type": "unexpected"}],
                    [{"type": "death", "tick": 60, "id": 1}],
                    [world, {"type": "bid", "tick": 30, "id": 1}],
                    [world, {"type": "bid", "tick": 15, "id": 1, "action": 1, "original_action": 2}]]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trace.gz"
            for rows in variants:
                with gzip.open(path, "wt") as stream:
                    for row in rows:
                        stream.write(json.dumps(row) + "\n")
                with self.assertRaises(RuntimeError):
                    replay.analyze_trace(path, {"plants": {}, "frame_ticks": set()})

    def test_compact_preserves_checkpoints_and_detectable_step_digest(self):
        report = {"cases": [{"plants": [{"steps": [{"tick": 15}], "checkpoints": {"birth": 15}}]}]}
        compact = replay.compact(report)
        self.assertIn("steps", report["cases"][0]["plants"][0])
        self.assertNotIn("steps", compact["cases"][0]["plants"][0])
        self.assertEqual(compact["cases"][0]["plants"][0]["checkpoints"], {"birth": 15})
        report["cases"][0]["plants"][0]["steps"][0]["tick"] = 30
        self.assertNotEqual(replay.compact(report), compact)

    def test_retained_focal_histories_and_images(self):
        evidence = replay.ROOT / "benchmarks/garden-seasons"
        raw = gzip.decompress((evidence / "seedling-resources-histories.json.gz").read_bytes())
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         "32c2c1490cbdc7ef2a427d7519dfc40499a56420adc32578b60735b31aebb2a5")
        report = json.loads(raw)
        self.assertEqual(report["selection"], replay.selection(replay.load_input()))
        self.assertEqual(report["selection"], json.loads((evidence / "seedling-resources-selection.json").read_text()))
        self.assertEqual(replay.compact(report), json.loads((evidence / "seedling-resources-summary.json").read_text()))
        for case in report["cases"]:
            for focal in case["plants"]:
                previous = None
                for point in focal["steps"]:
                    if point["terminal"] is not None:
                        replay.reconcile_death(previous, point["plant"], point["terminal"], point["tick"])
                    else:
                        actual = replay.live_point(point, previous, point["plant"], point["bids"])
                        self.assertEqual(actual, {key: point[key] for key in actual})
                    previous = point["plant"]
                self.assertEqual(replay.describe(focal["record"], focal["steps"]), focal)
            for frame in case["frames"]:
                self.assertEqual(replay.digest(evidence / frame["png"]), frame["png_sha256"])


if __name__ == "__main__":
    unittest.main()
