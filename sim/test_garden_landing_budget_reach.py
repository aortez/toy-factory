#!/usr/bin/env python3
"""Budget reach opt-in, observer parity, clipped support and frozen evidence."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest

import garden_landing_budget_reach as audit
from test_garden_landing_tools import run

BUILD = None
PORTABLE = audit.ROOT / "benchmarks/garden-seasons/landing-budget-reach-results.json.gz"
S = audit.STEP


def fixture():
    result = {"tick": 12 * S, "lineages": [
        {"id": 1, "parent": 0, "birth_tick": 0, "death_tick": None, "column": 14},
        {"id": 2, "parent": 0, "birth_tick": 0, "death_tick": None, "column": 9}],
        "seeds": [
            {"parent": 1, "birth_tick": 0, "end_tick": 10 * S, "column": 7, "species": 0,
             "child_id": None, "outcome": "expired", "lifetime_ecology_ticks": 10},
            {"parent": 1, "birth_tick": 10 * S, "end_tick": None, "column": 21, "species": 0,
             "child_id": None, "outcome": "pending", "lifetime_ecology_ticks": 10}]}
    sites = bytes(0 if c in (0, 19) else 32 for c in range(28)).hex()
    purchases = [{"birth_tick": s["birth_tick"], "parent": 1, "origin": 14, "column": s["column"],
                  "dispersal": 0, "choices": audit.reach.support(14, 0), "sites": sites} for s in result["seeds"]]
    rows = [{"tick": age * S, "seeds": [[1, age, 7, 33 if age < 8 else 32, 12, 80, 2, 64, 0, 0, 2]]}
            for age in (7, 8, 9)]
    rows.append({"tick": 10 * S, "seeds": [[1, 10, 7, 0, 0, 0, 2, 64, 1, 0, -1]]})
    window = {"purchases": purchases, "rows": [{"tick": r["tick"], "checks": [
        v[:4] + v[8:10] + [None if v[8] == 1 else sites] for v in r["seeds"]]} for r in rows]}
    return result, rows, window


class WindowTests(unittest.TestCase):
    def test_carry_in_expiry_end_purchase_and_censored_future_fate(self):
        result, rows, window = fixture()
        original = copy.deepcopy((result, rows, window))
        value = audit.analyze_window(result, rows, window, 6 * S, 10 * S)
        summary = value["summary"]
        self.assertEqual(summary["all"]["mature_checks"], 2)
        self.assertEqual(summary["by_cohort"]["carry_in"]["outcomes"], {"expired": 1})
        self.assertEqual(summary["by_cohort"]["purchased"]["outcomes"], {"pending": 1})
        self.assertEqual(summary["by_cohort"]["purchased"]["no_mature_checks"], 1)
        self.assertEqual(summary["all"]["checks_with"]["reachable_open"], 2)
        self.assertEqual(value["seeds"][0]["open_windows"][19], [2, 8 * S, 9 * S, 2])
        self.assertEqual(value["blocked_seed_ecology_samples_with"],
                         {"global_open": 2, "reachable_open": 2, "alternative_open": 2})
        self.assertEqual((result, rows, window), original)
        clipped = {"purchases": window["purchases"][:1], "rows": window["rows"][:-1]}
        value = audit.analyze_window(result, rows[:-1], clipped, 6 * S, 9 * S)
        self.assertEqual(value["summary"]["all"]["outcomes"], {"pending": 1})

    def test_global_open_is_not_reachable_and_purchase_is_separate(self):
        result, rows, window = fixture()
        # Leave purchase-time alternatives alone; change only the later checks.
        encoded = bytes(0 if c in (0, 1) else 32 for c in range(28)).hex()
        for row in window["rows"][:-1]:
            row["checks"][0][-1] = encoded
        value = audit.analyze_window(result, rows, window, 6 * S, 10 * S)
        summary = value["summary"]["all"]
        self.assertEqual(summary["any_global_open"], 1)
        self.assertEqual(summary["any_reachable_open"], 0)
        self.assertEqual(summary["purchase_alternative_open_actual_blocked"], 2)
        self.assertEqual(summary["always_reachable_spacing_blocked"], 1)

    def test_corrupt_support_samples_order_mask_and_expiry_fail(self):
        for kind in ("missing_purchase", "duplicate_purchase", "origin", "trait", "choices", "actual",
                     "missing_row", "reordered", "duplicate_check", "mask", "global", "expiry"):
            result, rows, window = fixture()
            if kind == "missing_purchase":
                window["purchases"].pop()
            elif kind == "duplicate_purchase":
                window["purchases"].append(window["purchases"][0])
            elif kind in ("origin", "trait", "choices", "actual"):
                p = window["purchases"][0]
                p[{"trait": "dispersal", "actual": "column"}.get(kind, kind)] = [7] * 6 if kind == "choices" else 99
            elif kind == "missing_row":
                window["rows"].pop()
            elif kind == "reordered":
                window["rows"].reverse()
            elif kind == "duplicate_check":
                window["rows"][0]["checks"] *= 2
            elif kind == "mask":
                window["rows"][0]["checks"][0][3] ^= 32
            elif kind == "global":
                window["rows"][0]["checks"][0][-1] = "20" * 28
            else:
                window["rows"][-1]["checks"][0][-1] = "20" * 28
            with self.subTest(kind=kind), self.assertRaises((RuntimeError, ValueError)):
                audit.analyze_window(result, rows, window, 6 * S, 10 * S)


class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        models, _, archive, _ = audit.budget.growth.load_inputs(audit.ROOT / "benchmarks/garden-seasons")
        cls.model_bytes = models[archive["models"]["single-s6d697834-live"]["model"]]

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="budget-reach-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.model = self.root / "model.tgl"
        self.model.write_bytes(self.model_bytes)
        self.cli = BUILD / "toy-factory-garden-landing"

    def native(self, *args, **kwargs):
        raw = run([self.cli, *args], **kwargs)
        return json.loads(raw) if raw else None

    def args(self, mode, ticks):
        return ["budget-replay", self.model, "rainfed-crowded", "0x940cfdc4", "--climate", "seasonal",
                "--shoot-reserve", mode, "--ticks", ticks, "--ledger"]

    def test_plain_reach_only_combined_repeat_pixels_and_partial_horizons(self):
        for mode in ("off", "on"):
            for ticks in (0, 14, 15, 3841, 16 * audit.DAY):
                stem = mode + str(ticks)
                path, children, repeat = (self.root / (stem + suffix) for suffix in
                                         (".jsonl", "-children.jsonl", "-repeat.jsonl"))
                raw, plain_raw = self.root / (stem + ".raw"), self.root / (stem + "-plain.raw")
                args = self.args(mode, ticks)
                result = self.native(*args, "--reach-trace", path, "--recruitment-trace", children)
                plain = self.native(*args, "--framebuffer", plain_raw)
                repeated = self.native(*args, "--reach-trace", repeat, "--framebuffer", raw)
                self.assertEqual({**plain, "framebuffer_crc32": None}, result)
                self.assertEqual(repeated, plain)
                self.assertEqual(raw.read_bytes(), plain_raw.read_bytes())
                self.assertEqual(path.read_bytes(), repeat.read_bytes())
                old = audit.germination.recruitment.analyze_trace(children, result)
                full = audit.reach.analyze_trace(path, result, old)
                self.assertEqual(full["ecology_samples"], ticks // S)
                if ticks == 16 * audit.DAY:
                    self.assertTrue(full["seeds"])
                    with children.open() as stream:
                        rows = [{k: r[k] for k in ("tick", "seeds")} for line in stream if
                                "seeds" in (r := json.loads(line)) and 8 * audit.DAY < r["tick"] <= ticks]
                    window = audit.extract_window(path, full, 8 * audit.DAY, ticks)
                    audit.analyze_window(result, rows, window, 8 * audit.DAY, ticks)
        self.assertEqual(self.model.read_bytes(), self.model_bytes)

    def test_requires_ledger_fresh_path_and_only_supported_modes(self):
        path = self.root / "bad.jsonl"
        args = self.args("on", 0)
        self.native(*args[:-1], "--reach-trace", path, valid=False)
        self.native(*args, "--reach-trace", path, "--reach-trace", path, valid=False)
        self.native("growth-replay", *args[1:6], "--node-limit", "32", "--ticks", 0,
                    "--ledger", "--reach-trace", path, valid=False)
        self.assertFalse(path.exists())
        path.write_bytes(b"keep")
        self.native(*args, "--reach-trace", path, valid=False)
        self.assertEqual(path.read_bytes(), b"keep")
        tool = audit.ROOT / "sim/garden_landing_budget_reach.py"
        out = self.root / "out"
        run([sys.executable, tool, "--out", out, "--jobs", 0], valid=False)
        self.assertFalse(out.exists())
        run([sys.executable, tool, "--verify", out, "--jobs", 1], valid=False)


class PortableTests(unittest.TestCase):
    def test_frozen_panel_windows_and_unchanged_baselines(self):
        self.assertEqual(audit.digest(PORTABLE),
                         "93cba7dfac249a4cca2326e6e163b89856f7d0e1268f3ac0a6eb0e3d7ca637aa")
        audit.verify(PORTABLE)
        with gzip.open(PORTABLE, "rt") as stream:
            value = json.load(stream)
        self.assertEqual(len(value["worlds"]), 6)
        self.assertEqual(value["native_runs"], 36)
        self.assertEqual(value["training_runs"], 0)
        for w in value["worlds"]:
            self.assertEqual(set(w["arms"]), {"eligible", "reserve"})
            for a in w["arms"].values():
                self.assertEqual(a["audit"]["ecology_samples"], 8192)
                self.assertTrue(a["repeat_and_plain_verified"])
        reserved = [w["arms"]["reserve"]["audit"] for w in value["worlds"]]
        self.assertEqual([a["summary"]["all"]["any_reachable_open"] for a in reserved], [3, 4, 1, 0, 10, 0])
        self.assertEqual([a["summary"]["all"]["always_reachable_spacing_blocked"] for a in reserved],
                         [12, 12, 16, 16, 6, 16])
        self.assertEqual([a["blocked_seed_ecology_samples_with"]["reachable_open"] for a in reserved],
                         [93, 173, 0, 0, 494, 0])
        purchases = [s for a in reserved for s in a["seeds"] if s["cohort"] == "purchased"]
        self.assertEqual(len(purchases), 49)
        self.assertEqual(sum(bool(s["opportunities"]["purchase"]["open_columns"]) for s in purchases), 1)
        alternatives = [s for s in purchases if bytes.fromhex(s["purchase"]["sites"])[s["column"]] & 32 and
                        any(not bytes.fromhex(s["purchase"]["sites"])[c] & 32 for c in set(s["purchase"]["choices"]))]
        self.assertEqual(len(alternatives), 9)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path, required=True)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *rest])
