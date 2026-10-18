#!/usr/bin/env python3
"""Flower geometry, site constraints, denominators, legacy output and evidence tests."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import garden_season_flower_sites as audit

CC = BASE = FLOWER = None


def purchase(origins=(1, 18), arm="flower"):
    first = origins[0] if arm == "flower" else 13
    columns = audit.placements(first, 0)
    return {"id": 1, "selected": 0, "base": 13, "origin": first, "species": 0, "dispersal": 0,
        "choice": 1, "column": columns[1], "columns": audit.bitset(columns),
        "flowers": [[i, 8 + c * 8 + 4, 80, audit.bitset(audit.placements(c, 0))] for i, c in enumerate(origins)]}


def sites(open_column=None, mask=0):
    result = [[0, 0, 6] for _ in range(28)]
    if open_column is not None:
        result[open_column] = [100, 255, mask]
    return result


class FlowerSitesTests(unittest.TestCase):
    def test_reference_weights_include_modulo_bias_and_edge_multiplicity(self):
        self.assertEqual(sum(audit.WEIGHTS), audit.TOTAL_WEIGHT)
        self.assertEqual(audit.WEIGHTS[1] - audit.WEIGHTS[0], 1)
        self.assertEqual(audit.WEIGHTS[2] - audit.WEIGHTS[4], 1)
        for column in range(28):
            for trait in range(-2, 3):
                values = audit.placements(column, trait)
                self.assertEqual(len(values), 14)
                self.assertTrue(all(0 <= c < 28 for c in values))
        at_edge = audit.placements(0, 0)
        self.assertEqual(at_edge, [v for c in range(3, 10) for v in (c, c)])
        p = purchase((0,))
        measured = audit.evaluate(p, sites(3), "flower")["views"]["all"]
        self.assertEqual(measured["actual_open_weight"], sum(audit.WEIGHTS[:2]))
        self.assertEqual(audit.pixel_column(0), 0)
        self.assertEqual(audit.pixel_column(15), 0)
        self.assertEqual(audit.pixel_column(16), 1)
        self.assertEqual(audit.pixel_column(255), 27)

    def test_four_site_classes_and_global_vs_local_constraints(self):
        p = purchase()
        for column, category in ((4, "actual_reach_open"), (23, "flower_reach_available"),
                                  (16, "open_outside_flower_reach"), (None, "world_closed")):
            result = audit.evaluate(p, sites(column), "flower")
            self.assertEqual(result["views"]["all"]["category"], category)
            self.assertEqual(result["views"]["local"]["category"], category)
        result = audit.evaluate(p, sites(23, 8 | 16 | 64), "flower")
        self.assertEqual(result["views"]["all"]["category"], "world_closed")
        self.assertEqual(result["views"]["local"]["category"], "flower_reach_available")
        self.assertTrue(result["views"]["local"]["better_flower"])
        self.assertTrue(result["views"]["local"]["first_flower_rescuable"])
        self.assertEqual(result["views"]["local"]["best_flowers"], [1])

    def test_ties_same_column_and_base_arm_are_not_flower_choice_gains(self):
        result = audit.evaluate(purchase((1, 1)), sites(4), "flower")
        self.assertEqual((result["flowers"], result["origins"]), (2, 1))
        self.assertEqual(result["views"]["local"]["best_flowers"], [0, 1])
        self.assertFalse(result["views"]["local"]["better_flower"])
        result = audit.evaluate(purchase((0,), "base"), sites(3), "base")
        self.assertEqual(result["views"]["all"]["category"], "flower_reach_available")
        self.assertFalse(result["views"]["all"]["better_flower"])

    def test_masks_check_actual_thresholds_dead_slot_spacing_and_global_limits(self):
        context = {"nodes": 253, "bases": [0, 3, 6, 9, 12, 15, 18, 21], "cold": True}
        grid = [[12, 80, 88 | (32 if c < 24 else 0)] for c in range(28)]
        audit.validate_sites(grid, context)
        for bad in (grid[:-1], [[*s[:2], s[2] | 1] for s in grid], [[0, 0, s[2]] for s in grid]):
            with self.assertRaises(RuntimeError):
                audit.validate_sites(bad, context)
        for key, value in (("nodes", 252), ("cold", False), ("bases", [0])):
            with self.assertRaises(RuntimeError):
                audit.validate_sites(grid, {**context, key: value})

    def test_malformed_support_selection_draw_and_coordinates_are_rejected(self):
        for mutate in (lambda p: p.update(origin=2), lambda p: p.update(columns=0),
                       lambda p: p.update(choice=14), lambda p: p.update(column=27),
                       lambda p: p.update(species=3), lambda p: p.update(selected=1),
                       lambda p: p.update(dispersal=3), lambda p: p["flowers"].clear(),
                       lambda p: p["flowers"][1].__setitem__(0, 0), lambda p: p["flowers"][1].__setitem__(1, 256),
                       lambda p: p["flowers"][1].__setitem__(3, 0)):
            p = purchase()
            mutate(p)
            with self.assertRaises(RuntimeError):
                audit.evaluate(p, sites(4), "flower")
        with self.assertRaises(RuntimeError):
            audit.analysis([])

    def test_closing_is_purchase_time_and_empty_windows_stay_in_summary(self):
        p = purchase()
        event = {"tick": 112 * audit.DAY, "purchase": p, "sites": sites(4),
            "context": {"nodes": 4, "bases": [13], "cold": False},
            "child_outcome": "day_only", "diagnostics": audit.evaluate(p, sites(4), "flower")}
        result = audit.windows([event])
        self.assertEqual(result["whole"]["purchases"], 1)
        self.assertEqual(result["closing"]["purchases"], 0)
        self.assertEqual(sum(result["closing"]["views"]["all"]["classes"].values()), 0)
        event["tick"] += 15
        self.assertEqual(audit.windows([event])["closing"]["purchases"], 1)

    def test_native_observer_legacy_output_metadata_and_repeatability(self):
        if BASE is None or FLOWER is None:
            self.skipTest("paired diagnostic builds not supplied")
        for build, arm in ((BASE, "base"), (FLOWER, "flower")):
            command = [build / "toy-factory-garden-production-audit", "rainfed", "baseline", "123", "guard", "7680"]
            old = subprocess.check_output(list(map(str, command)), timeout=30)
            command.append("--flower-sites")
            raw = subprocess.check_output(list(map(str, command)), timeout=30)
            self.assertEqual(raw, subprocess.check_output(list(map(str, command)), timeout=30))
            rows = [json.loads(line) for line in raw.splitlines()]
            self.assertEqual(rows[0]["site_phase"], "post-light-refresh")
            self.assertEqual(rows[0].get("seed_origin"), "flower-v1" if arm == "flower" else None)
            self.assertTrue(any(r["purchases"] for r in rows[1:]))
            for row in rows[1:]:
                for p in row["purchases"]:
                    audit.evaluate(p, row["sites"], arm)
                row.pop("purchases")
                row.pop("sites")
            rows[0]["version"] = 1
            for key in ("flower_audit", "site_phase", "flower_fields", "site_fields"):
                rows[0].pop(key)
            normalized = "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows).encode()
            self.assertEqual(normalized, old)

    def test_host_only_header_guard(self):
        if CC is None:
            self.skipTest("compiler not supplied")
        run = subprocess.run([CC, "-std=c11", "-Werror", "-fsyntax-only", "-I", str(audit.ROOT / "src"),
            "-D__ZEPHYR__=1", "-xc", "-"], input='#include "garden_flower_audit.h"\n',
            text=True, capture_output=True, timeout=30)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("restricted to host", run.stderr)

    def test_portable_evidence_recomputes_without_simulation(self):
        folder = audit.ROOT / "benchmarks/garden-seasons"
        path = folder / "flower-sites-purchases.json.gz"
        if not path.exists():
            self.skipTest("observation not collected yet")
        with patch("subprocess.Popen", side_effect=AssertionError("portable check ran native code")):
            report = json.loads(gzip.decompress(path.read_bytes()))
            prior = audit.load_input()
            audit.validate_report(report, prior)
            self.assertEqual(audit.compact(report), json.loads((folder / "flower-sites-summary.json").read_text()))
            self.assertEqual(sum(len(c["events"]) for c in report["cases"]), 3576)
            for mutate in (lambda c: c["events"].pop(), lambda c: c["events"][0]["sites"].pop(),
                           lambda c: c["events"][0].update(child_outcome="unknown"),
                           lambda c: c["events"][0].update(tick=0),
                           lambda c: c["events"][0]["purchase"].update(selected=65535)):
                bad = copy.deepcopy(report["cases"][0])
                mutate(bad)
                with self.assertRaises(RuntimeError):
                    audit.validate_case(bad, prior["cases"][0], "base")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cc")
    parser.add_argument("--base", type=Path)
    parser.add_argument("--flower", type=Path)
    args, rest = parser.parse_known_args()
    CC, BASE, FLOWER = args.cc, args.base, args.flower
    unittest.main(argv=[__file__, *rest])
