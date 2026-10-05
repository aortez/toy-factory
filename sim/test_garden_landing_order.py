#!/usr/bin/env python3
"""Rotation identity, common prefixes, actual traversal and outcome accounting."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_order as screen
from test_garden_landing_tools import run

BUILD = None
D, S = screen.DAY, screen.STEP


class OrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        saved, models, _, _ = screen.load_inputs()
        cls.model_bytes = models[saved["models"]["single-s6d697834-live"]["model"]]

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="landing-order-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.model = self.root / "model.tgl"
        self.model.write_bytes(self.model_bytes)
        self.cli = BUILD / "toy-factory-garden-landing"

    def native(self, *args, **kwargs):
        raw = run([self.cli, *args], **kwargs)
        return json.loads(raw) if raw else None

    def args(self, ticks=8 * D, rotating=False, target=None):
        args = ("placement-replay" if target is None else "vacancy-replay", self.model,
                "rainfed-crowded", "0x940cfdc4", "--climate", "seasonal", "--ticks", ticks,
                "--ledger", "--shoot-reserve", "on", "--seed-placement", "spacing")
        if target is not None:
            args += ("--vacancy-at", 3 * D, "--vacancy-lineage", target)
        if rotating:
            args += ("--seed-order", "rotating", "--seed-order-after", 3 * D)
        return args

    def sample(self, stem, rotating=True, ordered=True):
        paths = [self.root / (stem + "-" + kind + ".jsonl") for kind in ("stand", "adult")]
        options = tuple(v for kind, p in zip(("stand", "adult"), paths, strict=True)
                        for v in ("--" + kind + "-trace", p, "--" + kind + "-start", 3 * D,
                                  "--" + kind + "-stop", 8 * D))
        raw = self.root / (stem + ".raw")
        result = self.native(*self.args(rotating=rotating), *options, "--framebuffer", raw,
                             *(("--stand-order",) if ordered else ()))
        return result, [screen.recovery.adults.read_trace(p) for p in paths], paths, raw

    def test_common_prefix_with_and_without_post_step_export(self):
        initial = self.native(*self.args(ticks=3 * D))
        target = min(p["id"] for p in initial["lineages"] if p["death_tick"] is None and p["birth_tick"] + D < 3 * D)
        for victim in (None, target):
            fixed = self.native(*self.args(ticks=3 * D, target=victim))
            rotated = self.native(*self.args(ticks=3 * D, rotating=True, target=victim))
            screen.check_prefix(fixed, rotated, 3 * D)
            self.assertNotEqual(fixed["run_hash"], rotated["run_hash"])
            self.assertEqual(fixed["world_hash"], rotated["world_hash"])
            bad = copy.deepcopy(rotated)
            bad["seed_order_probe"]["after"] += 60
            with self.assertRaises(RuntimeError):
                screen.check_prefix(fixed, bad, 3 * D)

    def test_actual_order_repeats_budgets_plain_parity_and_pixels(self):
        result, rows, paths, raw = self.sample("trace")
        repeated, again, copies, pixels = self.sample("repeat")
        plain_raw = self.root / "plain.raw"
        self.assertEqual(result, self.native(*self.args(rotating=True), "--framebuffer", plain_raw))
        self.assertEqual((result, rows), (repeated, again))
        self.assertEqual([p.read_bytes() for p in paths], [p.read_bytes() for p in copies])
        self.assertEqual(raw.read_bytes(), pixels.read_bytes())
        self.assertEqual(raw.read_bytes(), plain_raw.read_bytes())
        common, audit = screen.analyze_order(rows[0], result, "rotating", 3 * D)
        checked = screen.recovery.analyze(common, rows[1], result)
        self.assertEqual(checked["samples"], 5 * D // S + 1)
        self.assertTrue(any([v["id"] for v in r["reproduction"]] != r["plant_order"] for r in rows[0][1:-1]))
        self.assertTrue(any(len(p["maintenance"]) > 1 for p in audit["ranks"]))
        self.assertEqual(self.model.read_bytes(), self.model_bytes)

    def test_fixed_trace_projection_preserves_legacy_bytes(self):
        a, rows, _, _ = self.sample("fixed", rotating=False)
        b, old, _, _ = self.sample("legacy", rotating=False, ordered=False)
        self.assertEqual(a, b)
        common, _ = screen.analyze_order(rows[0], a, "fixed", 3 * D)
        self.assertEqual(common, old[0])
        self.assertEqual(rows[1], old[1])

    def test_corrupt_order_inventory_clock_footer_and_gates_fail(self):
        result, rows, _, _ = self.sample("corrupt")
        for fault in ("inventory", "order", "clock", "footer", "gate"):
            bad = copy.deepcopy(rows[0])
            if fault == "inventory":
                bad[1]["plant_order"].append(bad[1]["plant_order"][0])
            elif fault == "order":
                bad[1]["reproduction"].reverse()
            elif fault == "clock":
                bad[2]["tick"] = bad[1]["tick"]
            elif fault == "footer":
                bad[-1]["run_hash"] = "00000000"
            else:
                bad[1]["reproduction"][0]["blockers"] ^= 4
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                screen.analyze_order(bad, result, "rotating", 3 * D)

    def test_cli_validation_precedes_output_creation_and_preserves_existing_files(self):
        path = self.root / "trace.jsonl"
        trace = ("--stand-trace", path, "--stand-start", S, "--stand-stop", 60, "--stand-order")
        options = (("--seed-order", "rotating"), ("--seed-order-after", 60),
                   ("--seed-order", "random", "--seed-order-after", 60),
                   ("--seed-order", "rotating", "--seed-order-after", 0),
                   ("--seed-order", "rotating", "--seed-order-after", 61),
                   ("--seed-order", "rotating", "--seed-order-after", 60, "--seed-order", "rotating"),
                   ("--seed-order", "rotating", "--seed-order-after", 60, "--seed-order-after", 120))
        for extra in options:
            self.native(*self.args(ticks=60), *trace, *extra, valid=False)
            self.assertFalse(path.exists())
        self.native(*self.args(ticks=60), "--stand-order", valid=False)
        self.native(*[v for v in self.args(ticks=60, rotating=True) if v != "--ledger"], *trace, valid=False)
        self.assertFalse(path.exists())
        path.write_bytes(b"preserve")
        self.native(*self.args(ticks=60, rotating=True), *trace, valid=False)
        self.assertEqual(path.read_bytes(), b"preserve")
        with self.assertRaises(RuntimeError):
            screen.collect(BUILD, self.root, 1)


class AnalysisTests(unittest.TestCase):
    def test_frozen_baseline_cohorts_windows_and_censoring(self):
        saved, _, _, _ = screen.load_inputs()
        total = dict(early=0, reproduced=0, late=0, pending=0)
        for w in saved["worlds"]:
            for a in w["arms"].values():
                result = screen.outcomes(a["result"])
                screen.check_historical({"outcomes": result}, a)
                total["early"] += len(result["early_survivors"])
                total["reproduced"] += len(result["reproducing_replacements"])
                total["late"] += len(result["periods"][-1]["confirmations"])
                total["pending"] += result["birth_outcomes"].get("pending", 0)
                self.assertEqual(result["early_seed_parents"], [])
                self.assertEqual(result["early_successful_parents"], [])
        self.assertEqual(total, dict(early=5, reproduced=54, late=6, pending=2))

    def test_more_seed_purchases_alone_do_not_pass_the_screen(self):
        saved, _, _, _ = screen.load_inputs()
        worlds = [{"contexts": {context: {arm: {"audit": {"outcomes": screen.outcomes(a["result"])}}
                    for arm in screen.ARMS} for context, a in w["arms"].items()}} for w in saved["worlds"]]
        b = worlds[0]["contexts"]["vacancy"]["rotating"]["audit"]["outcomes"]
        b["early_seed_parents"] = [999]
        self.assertFalse(screen.summarize(worlds)["passes_screen"])
        b["early_successful_parents"] = [999]
        self.assertTrue(screen.summarize(worlds)["passes_screen"])
        b["reproducing_replacements"] = []
        self.assertFalse(screen.summarize(worlds)["passes_screen"])


class FrozenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = screen.ROOT / "benchmarks/garden-seasons/landing-order-results.json.gz"
        if screen.digest(path) != "65d240d896f7f6aeb014212fed502479b69e135b921f26d4a288e84b41cc4f32":
            raise AssertionError("frozen order result changed")
        with gzip.open(path, "rt") as stream:
            cls.value = json.load(stream)

    def test_portable_evidence_without_replay_and_all_twelve_galleries(self):
        with patch.object(screen.training, "native", side_effect=AssertionError("ran simulation")):
            screen.check_value(self.value)
        hashes = {
            "control--single-s6d697833-live": "716364d875e0467089f5c4574a1c0028d607a40d206be0b6c23b5ea3be4c8f2d",
            "control--multi-s6d697833-live": "8ac1d8e68d04e267228d8cae4336d1c309f87a4c815657c806878bc6e6992c14",
            "control--single-s6d697834-live": "d8437779b23fc193d0df27440edb9443e68ece5a11c21f3a82c0cea040f0513a",
            "control--multi-s6d697834-live": "03692f76ea160eeaafd941e22103f52fbfe35761aff4c1ad50c32ae5c962abe1",
            "control--single-s6d697835-live": "fc30992fda9810dabd0db3e294c7f22518ae45f6582d425f18be3d0822f8952e",
            "control--multi-s6d697835-live": "664567a250dd0eec1bfe35377e3f040499b2b64b17ce4008228eb34978d94a04",
            "vacancy--single-s6d697833-live": "bf9143f1ea00f3baa5802d6e9ca0720ec6c290cbe78dd585463e412c145968c1",
            "vacancy--multi-s6d697833-live": "159e76c136a4f09498aeef64bad8ec5d38a86ad18e4d31198721750caf57e02a",
            "vacancy--single-s6d697834-live": "6ba76dc8ea85d3795e79b8406bbb371d98d5bd984d162ba77c4af2a8173351bf",
            "vacancy--multi-s6d697834-live": "162bd87f3b51926abec510c8c6df93bc11c309ece0ea8ee1f75022da2a3f0840",
            "vacancy--single-s6d697835-live": "a89227ff35552edb98fda70dd1f88939cc020d56ff00f380442d232ca6b8811b",
            "vacancy--multi-s6d697835-live": "098bf3718387400dabd2e049da0a951f9c07cdebb5a923903ec02996d58b23f8",
        }
        for name, sha in hashes.items():
            path = screen.ROOT / "benchmarks/garden-seasons/frames" / ("landing-order-" + name + ".png")
            self.assertEqual(screen.digest(path), sha)

    def test_aggregate_gain_retains_context_regressions_and_censoring(self):
        summary = screen.summarize(self.value["worlds"])
        self.assertTrue(summary["passes_screen"])
        for arm, survivors, deaths, parents, early, closing in (
                ("fixed", 137, 73, 54, 0, 6), ("rotating", 147, 84, 66, 4, 9)):
            self.assertEqual(summary["totals"][arm], {
                "birth_outcomes": {"confirmed": survivors, "died": deaths, "pending": 2},
                "early_survivors": 5, "early_seed_parents": early, "early_successful_parents": early,
                "new_reproducing_parents": parents, "closing_confirmations": closing})
        for context, fixed, rotated in (("control", 4, 2), ("vacancy", 2, 7)):
            for arm, expected in (("fixed", fixed), ("rotating", rotated)):
                self.assertEqual(sum(len(w["contexts"][context][arm]["audit"]["outcomes"]["periods"][-1]["confirmations"])
                                     for w in self.value["worlds"]), expected)
        pair = self.value["worlds"][2]["contexts"]["vacancy"]
        self.assertEqual([len(pair[a]["audit"]["outcomes"]["reproducing_replacements"]) for a in screen.ARMS], [4, 1])
        self.assertEqual([len(pair[a]["audit"]["outcomes"]["early_survivors"]) for a in screen.ARMS], [1, 0])

    def test_equal_time_ranks_do_not_guarantee_opening_access(self):
        audit = self.value["worlds"][1]["contexts"]["control"]["rotating"]["audit"]
        ranks = next(p for p in audit["order"]["ranks"] if p["id"] == 28)
        self.assertEqual(set(ranks["maintenance"]), set(map(str, range(6))))
        self.assertEqual(max(ranks["maintenance"].values()) - min(ranks["maintenance"].values()), 1)
        self.assertEqual(ranks["open_eligible"], {"3": 2, "4": 2})
        self.assertEqual(ranks["purchased"], {})
        parent = next(p for p in audit["outcomes"]["children"] if p["id"] == 28)
        self.assertEqual((parent["seeds_created"], parent["confirmed_children"]), (0, []))

    def test_matched_birth_events_keep_seed_fees_and_survival_tradeoff(self):
        pair = self.value["worlds"][1]["contexts"]["vacancy"]
        seeds = [[s for s in pair[a]["result"]["seeds"] if s["child_id"] == 28] for a in screen.ARMS]
        self.assertEqual(seeds[0], seeds[1])
        parents = [next(p for p in pair[a]["audit"]["outcomes"]["children"] if p["id"] == 28) for a in screen.ARMS]
        self.assertEqual([p["seeds_created"] for p in parents], [0, 2])
        self.assertEqual(parents[1]["child_outcomes"], {"confirmed": 1, "died": 1})
        self.assertEqual(parents[1]["death_tick"] - parents[0]["death_tick"], -420)
        for arm, purchases in (("fixed", 0), ("rotating", 2)):
            budget = next(p for p in pair[arm]["audit"]["gates"]["resources"]["plants"] if p["id"] == 28)
            self.assertEqual(budget["resources"]["energy"]["reproduction"], 48 * purchases)
            self.assertEqual(budget["resources"]["water"]["reproduction"], 24 * purchases)
        for w in self.value["worlds"]:
            for context in screen.previous.ARMS:
                audit = w["contexts"][context]["rotating"]["audit"]
                for i in audit["outcomes"]["early_survivors"]:
                    p = next(p for p in audit["gates"]["plants"] if p["id"] == i)
                    receipt = p["last_maintenance"][-1]
                    self.assertEqual(receipt["tick"], p["death_tick"])
                    self.assertEqual(receipt["plant"]["stages"][1][2:4], [8, 5])
                    self.assertEqual(receipt["plant"]["uptake"][1][3:5], [2, 0])

    def test_corrupt_fingerprint_cohort_call_budget_and_prefix_pixels_fail(self):
        for fault in ("fingerprint", "cohort", "calls", "pixels"):
            bad = copy.deepcopy(self.value)
            w = bad["worlds"][0]
            a = w["contexts"]["control"]["rotating"]
            if fault == "fingerprint":
                a["result"]["seed_order_probe"]["after"] += 60
            elif fault == "cohort":
                a["audit"]["outcomes"]["early_successful_parents"] = [999]
                bad["summary"] = screen.summarize(bad["worlds"])
            elif fault == "calls":
                w["calls"].pop()
            else:
                a["frames"]["158"]["raw_sha256"] = "0" * 64
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                screen.check_value(bad)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path, required=True)
    args, remaining = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *remaining])
