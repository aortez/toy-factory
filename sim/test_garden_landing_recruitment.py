#!/usr/bin/env python3
"""Trace identity, full accounting, corruption and CLI safety regression checks."""

import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import garden_landing_recruitment as trace
from test_garden_landing_tools import run

BUILD = None


class RecruitmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel, cls.archive, cls.audit = trace.load_inputs(trace.ROOT / "benchmarks/garden-seasons")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="landing-recruitment-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cli = BUILD / "toy-factory-garden-landing"
        self.m = next(m for m in self.panel["models"] if m["id"] == "multi-s6d697834-live")
        self.model = self.root / "model.tgl"
        self.model.write_bytes(self.archive[self.m["model"]])

    def native(self, *args, **kwargs):
        value = run([self.cli, *args], **kwargs)
        return json.loads(value) if value else None

    def sample(self, ticks=16 * trace.DAY, name="sample"):
        args = [self.model, "rainfed", "0x5aa2b327", "--ticks", ticks, "--climate", "steady", "--ledger"]
        path = self.root / (name + ".jsonl")
        result = self.native("replay", *args, "--recruitment-trace", path)
        return args, path, result, trace.analyze_trace(path, result)

    def test_selection_is_fixed_and_all_models_are_frozen(self):
        plan = trace.select(self.audit)
        self.assertEqual(len(plan), 12)
        expected = ["rainfed-crowded-steady-7d3b7bde", "rainfed-steady-5aa2b327", "rainfed-crowded-steady-5aa2b327"]
        for i, case in enumerate(expected):
            self.assertEqual([r["case"]["id"] for r in plan[4*i:4*i+4]],
                             [case, case, "rainfed-crowded-seasonal-940cfdc4", "rainfed-crowded-seasonal-940cfdc4"])

    def test_plain_repeat_and_partial_tick_boundaries(self):
        for ticks in (0, 14, 15, 3839, 3840, 3841, 16 * trace.DAY):
            args, path, result, analysis = self.sample(ticks, str(ticks))
            self.assertEqual(self.native("replay", *args), result)
            _, repeated, repeat_result, repeat_analysis = self.sample(ticks, "repeat-" + str(ticks))
            self.assertEqual(repeated.read_bytes(), path.read_bytes())
            self.assertEqual((repeat_result, repeat_analysis), (result, analysis))
            self.assertEqual(analysis["ecology_samples"], ticks // trace.STEP)
        self.assertGreater(analysis["first_day_samples"], 0)
        self.assertGreater(analysis["seed_checks"], 0)
        self.assertEqual(self.model.read_bytes(), self.archive[self.m["model"]])

    def test_missing_duplicate_corrupt_checks_and_budgets_fail(self):
        _, path, result, analysis = self.sample()
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        seed_index = next(i for i, r in enumerate(rows) if r.get("seeds"))
        plant_index = next(i for i, r in enumerate(rows) if any(p["uptake"] for p in r.get("plants", [])))
        cases = [rows[:-1], rows[:2] + rows[3:], rows + [rows[-1]]]
        for kind in ("duplicate", "mask", "income", "stage", "plant"):
            bad = copy.deepcopy(rows)
            if kind == "duplicate":
                bad[seed_index]["seeds"].append(bad[seed_index]["seeds"][0])
            elif kind == "mask":
                bad[seed_index]["seeds"][0][3] = 128
            elif kind == "plant":
                bad[plant_index]["plants"] = []
            else:
                p = next(p for p in bad[plant_index]["plants"] if p["uptake"])
                if kind == "income":
                    p["uptake"][0][1] += 1
                else:
                    p["stages"][0] = None
            cases.append(bad)
        for i, bad in enumerate(cases):
            output = self.root / ("bad-" + str(i) + ".jsonl")
            output.write_text("".join(json.dumps(r) + "\n" for r in bad))
            with self.assertRaises((RuntimeError, StopIteration, TypeError)):
                trace.analyze_trace(output, result)
        self.assertEqual(trace.analyze_trace(path, result), analysis)

    def test_expiry_is_not_a_resource_sample_and_pending_is_censored(self):
        _, _, result, analysis = self.sample(48 * trace.DAY)
        expired = [s for s in analysis["seeds"] if s["outcome"] == "expired"]
        pending = [s for s in analysis["seeds"] if s["outcome"] == "pending"]
        self.assertTrue(expired)
        self.assertTrue(pending)
        for s in expired:
            self.assertEqual(s["samples"], 8192)
            self.assertEqual(sum(s["masks"].values()), 8191)
            self.assertEqual(sum(s["mature_masks"].values()), 8184)
        for s in pending:
            self.assertEqual(sum(s["masks"].values()), s["samples"])
            self.assertLess(result["tick"], s["birth_tick"] + 8192 * trace.STEP)
        for p in analysis["plants"]:
            for r in p["resources"].values():
                self.assertEqual(r["initial"] + r["income"],
                                 sum(r[k] for k in ("overflow", "upkeep", "growth", "reproduction", "discarded", "final")))

    def test_cli_no_clobber_required_ledger_and_exclusive_trace_mode(self):
        args = [self.model, "rainfed", "0x1234", "--ticks", 0, "--climate", "steady"]
        path = self.root / "trace.jsonl"
        for command in (["replay", *args, "--recruitment-trace", path],
                        ["replay", *args, "--ledger", "--recruitment-trace", path, "--recruitment-trace", path],
                        ["trace-replay", *args, "--ledger", "--recruitment-trace", path],
                        ["probe-replay", *args, "--ledger", "--recruitment-trace", path]):
            self.native(*command, valid=False)
            self.assertFalse(path.exists())
        path.write_bytes(b"keep me")
        self.native("replay", *args, "--ledger", "--recruitment-trace", path, valid=False)
        self.assertEqual(path.read_bytes(), b"keep me")

    def test_retained_panel_reconciles_every_budget_and_report_count(self):
        directory = trace.ROOT / "benchmarks/garden-seasons"
        full = json.loads(gzip.decompress((directory / "landing-recruitment-trace-results.json.gz").read_bytes()))
        summary = json.loads((directory / "landing-recruitment-trace-summary.json").read_text())
        self.assertEqual(full["plan"], trace.select(self.audit))
        self.assertEqual(full["rule"], trace.RULE)
        self.assertEqual(full["inputs"], trace.INPUTS)
        canonical = (json.dumps(full, sort_keys=True, indent=2) + "\n").encode()
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), summary["results_sha256"])
        self.assertEqual(trace.digest(trace.ROOT / trace.PROTOCOL), summary["protocol_sha256"])
        self.assertEqual(summary["manifest_sha256"],
                         "ba22339088f42a8d0708128e776a274346c8eeb84e9fda2d8551512240e47278")
        self.assertIs(summary["repeat_verified"], True)
        self.assertIs(summary["independent_frozen_verification"], True)
        totals = dict.fromkeys(("ecology_samples", "seed_samples", "seed_checks", "first_day_samples"), 0)
        steady_seeds, seasonal_seeds, children = [], [], []
        for w, brief in zip(full["worlds"], summary["worlds"], strict=True):
            self.assertEqual(brief["id"], w["id"])
            self.assertEqual(brief["trace_sha256"], w["trace_sha256"])
            self.assertEqual(brief["audit"], {k: v for k, v in w["audit"].items() if k not in ("plants", "seeds")})
            trace.check_history(w["result"], self.panel["evaluations"][w["model"]]["worlds"][w["case"]["id"]],
                                w["case"], full["models"][w["model"]]["metadata"])
            for k in totals:
                totals[k] += w["audit"][k]
            a = w["audit"]
            self.assertEqual(a["seed_checks"], sum(sum(s["masks"].values()) for s in a["seeds"]))
            self.assertEqual(a["seed_samples"], sum(s["samples"] for s in a["seeds"]))
            self.assertEqual(a["first_day_samples"], sum(len(p["rows"]) for p in a["plants"]))
            for p in a["plants"]:
                again = copy.deepcopy(p)
                trace.analyze_child(again, trace.STOP)
                self.assertEqual(again, p)
            late_seeds = [s for s in a["seeds"] if s["outcome"] == "expired" and
                          62 * trace.DAY < s["end_tick"] <= 190 * trace.DAY]
            late_children = [p for p in a["plants"] if 62 * trace.DAY < p["birth_tick"] <= 190 * trace.DAY]
            self.assertEqual(a["summary"], {"all_seeds": trace.seed_summary(a["seeds"]),
                "late_expired": trace.seed_summary(late_seeds), "all_children": trace.child_summary(a["plants"]),
                "late_children": trace.child_summary(late_children)})
            (steady_seeds if w["case"]["climate"] == "steady" else seasonal_seeds).extend(late_seeds)
            children.extend(late_children)
        self.assertEqual(tuple(totals.values()), (589824, 4592849, 4592410, 40175))
        self.assertEqual((len(steady_seeds), len(seasonal_seeds)), (192, 151))
        self.assertTrue(all(all(int(m) & 32 for m in s["mature_masks"]) for s in steady_seeds))
        self.assertTrue(all(s["open_elsewhere_checks"] > 0 for s in steady_seeds + seasonal_seeds))
        self.assertEqual(trace.child_summary(children)["outcomes"], {"confirmed": 55, "died": 72})
        self.assertEqual(trace.child_summary(children)["death_shortages"], {"energy": 22, "energy+water": 7, "water": 43})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path, required=True)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *rest])
