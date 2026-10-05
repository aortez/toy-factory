#!/usr/bin/env python3
"""Vacancy isolation, export accounting, repeats and pre-export parity."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_vacancy as screen
from test_garden_landing_tools import run

BUILD = None
D, S = screen.DAY, screen.STEP


class AccountingTests(unittest.TestCase):
    def test_export_ends_credit_not_ancestry_or_natural_death(self):
        plants = [{"id": i, "parent": p, "birth_tick": b * D, "death_tick": d * D if d else None}
                  for i, p, b, d in ((1, 0, 0, None), (2, 1, 1, None), (3, 2, 3, None),
                                      (4, 3, 8, None), (5, 2, 4, 8))]
        plants[2]["removal_tick"] = 6 * D
        original = copy.deepcopy(plants)
        value = screen.credit(plants, 3 * D, 10 * D)
        rows = {p["id"]: p for p in value["children"]}
        self.assertEqual(rows[3]["last_live_sample"], 6 * D - S)
        self.assertEqual(rows[3]["live_ticks"], 2 * D)
        self.assertEqual(rows[3]["death_lost_ticks"], 0)
        self.assertEqual(rows[3]["removal_lost_ticks"], 4 * D + S)
        self.assertEqual(rows[4]["live_ticks"], D + S)
        self.assertGreater(rows[5]["death_lost_ticks"], 0)
        self.assertEqual(rows[5]["removal_lost_ticks"], 0)
        self.assertEqual(value["available_ticks"], value["ticks"] + value["death_lost_ticks"] + value["removal_lost_ticks"])
        self.assertTrue(screen.alive(plants[2], 6 * D - S))
        self.assertFalse(screen.alive(plants[2], 6 * D))
        self.assertEqual(plants, original)

    def test_age_limit_is_not_export_or_death(self):
        plants = [{"id": i, "parent": i - 1, "birth_tick": (i - 1) * D, "death_tick": None}
                  for i in (1, 2, 3)]
        plants[2]["removal_tick"] = 40 * D
        value = screen.credit(plants, 35 * D, 45 * D)
        self.assertEqual(value["ticks"], 0)
        self.assertEqual(value["removal_lost_ticks"], 0)
        self.assertEqual(value["death_lost_ticks"], 0)

    def test_fixed_panel_targets_and_no_clobber(self):
        saved, _ = screen.load_inputs()
        self.assertEqual(len(screen.prior.panel(saved)), 6)
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(RuntimeError):
                screen.collect(Path(root), Path(root), 1)


class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        saved, models = screen.load_inputs()
        cls.model_bytes = models[saved["models"]["single-s6d697834-live"]["model"]]

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="landing-vacancy-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.model = self.root / "model.tgl"
        self.model.write_bytes(self.model_bytes)
        self.cli = BUILD / "toy-factory-garden-landing"

    def native(self, *args, **kwargs):
        raw = run([self.cli, *args], **kwargs)
        return json.loads(raw) if raw else None

    def args(self, stop=3 * D, target=None, at=3 * D):
        base = ("placement-replay" if target is None else "vacancy-replay", self.model,
                "rainfed-crowded", "0x940cfdc4", "--climate", "seasonal", "--ticks", stop,
                "--ledger", "--shoot-reserve", "on", "--seed-placement", "spacing")
        return base if target is None else (*base, "--vacancy-at", at, "--vacancy-lineage", target)

    def target(self, result):
        return min(p["id"] for p in result["lineages"] if p["death_tick"] is None and p["birth_tick"] + D < result["tick"])

    def traced(self, stem, *args):
        traces = [self.root / (stem + k + ".jsonl") for k in ("children", "reach")]
        raw = self.root / (stem + ".raw")
        result = self.native(*args, "--recruitment-trace", traces[0], "--reach-trace", traces[1], "--framebuffer", raw)
        audit = screen.recruitment.analyze_trace(traces[0], result)
        screen.reach.analyze_trace(traces[1], result, audit)
        return result, traces, raw

    def test_pending_identity_no_observer_changes_and_export_boundary(self):
        before, pretraces, _ = self.traced("before", *self.args())
        target = self.target(before)
        pending = self.native(*self.args(stop=0, target=target))
        old = self.native(*self.args(stop=0))
        self.assertIsNone(pending["vacancy_probe"]["event"])
        self.assertEqual(pending["placement_run_hash"], old["run_hash"])
        self.assertEqual(pending["run_hash"], screen.probe_hash(old["run_hash"], 3 * D, target))
        self.assertNotEqual(pending["run_hash"], self.native(*self.args(stop=0, target=target + 1))["run_hash"])
        after, posttraces, _ = self.traced("after", *self.args(target=target))
        screen.check_boundary(before, after)
        for a, b in zip(pretraces, posttraces, strict=True):
            self.assertEqual(a.read_bytes(), b.read_bytes())
            for p in (a, b):
                screen.compress(p, p.with_suffix(".gz"))
            with patch.object(screen, "AT", 3 * D):
                self.assertEqual(screen.prefix_equal(a.with_suffix(".gz"), b.with_suffix(".gz")), 3 * D // S)
        first, traces, raw = self.traced("later", *self.args(stop=5 * D, target=target))
        again, repeated, pixels = self.traced("repeat", *self.args(stop=5 * D, target=target))
        plain = self.root / "plain.raw"
        self.assertEqual(first, again)
        self.assertEqual(first, self.native(*self.args(stop=5 * D, target=target), "--framebuffer", plain))
        self.assertEqual(raw.read_bytes(), pixels.read_bytes())
        self.assertEqual(raw.read_bytes(), plain.read_bytes())
        self.assertEqual([p.read_bytes() for p in traces], [p.read_bytes() for p in repeated])
        self.assertEqual(first["deaths"], sum(p["death_tick"] is not None for p in first["lineages"]))
        self.assertEqual(first["living"], sum(p["death_tick"] is None and not p.get("removal_tick") for p in first["lineages"]))
        self.assertFalse(any(s["parent"] == target and s["birth_tick"] > 3 * D for s in first["seeds"]))
        self.assertEqual(self.model.read_bytes(), self.model_bytes)

    def test_explicit_flags_age_alignment_missing_target_no_clobber(self):
        args = self.args(target=1)
        for extra in (args[:-4], args[:-2], (*args, "--vacancy-lineage", 2),
                      self.args(target=0), self.args(target=1, at=D), self.args(target=1, at=3 * D + 1),
                      tuple(x for x in args if x != "--ledger"), self.args(target=999)):
            self.native(*extra, valid=False)
        self.native(*self.args(), "--vacancy-at", 3 * D, "--vacancy-lineage", 1, valid=False)
        path = self.root / "existing.jsonl"
        path.write_bytes(b"preserve")
        self.native(*args, "--recruitment-trace", path, valid=False)
        self.assertEqual(path.read_bytes(), b"preserve")


class FrozenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = screen.ROOT / "benchmarks/garden-seasons/landing-vacancy-results.json.gz"
        if screen.digest(path) != "f49fa29abdefbc931bbe57937c90c33c2e51c35c573ce3709c9428cee46c6801":
            raise AssertionError("frozen vacancy result changed")
        with gzip.open(path, "rt") as stream:
            cls.value = json.load(stream)

    def test_portable_evidence_and_all_six_galleries_without_replay(self):
        with patch.object(screen.placement.training, "native", side_effect=AssertionError("ran simulation")):
            screen.check_value(self.value)
        for name, sheet in self.value["sheets"].items():
            path = screen.ROOT / "benchmarks/garden-seasons/frames" / ("landing-vacancy-" + name + ".png")
            self.assertEqual(screen.digest(path), sheet["sha256"])

    def test_early_refills_are_not_reproducing_replacements(self):
        early = [p for w in self.value["worlds"] for p in w["arms"]["vacancy"]["analysis"]["children"]
                 if p["birth_tick"] <= 190 * D]
        self.assertEqual(screen.prior.turnover.cohort(early), {"births": 20, "confirmed": 5, "died": 15,
            "pending": 0, "shortages": {"energy": 9, "water": 6}})
        self.assertTrue(all(p["seeds_created"] == 0 and p["children"] == [] for p in early))
        self.assertEqual([w["arms"]["vacancy"]["analysis"]["periods"][0]["birth_cohort"]["confirmed"]
                          for w in self.value["worlds"]], [0, 1, 1, 1, 1, 1])

    def test_extended_controls_recover_and_final_window_keeps_regressions(self):
        self.assertTrue(all(w["arms"]["control"]["analysis"]["reproducing_replacements"] for w in self.value["worlds"]))
        for arm, births, survivors, pending, fresh in (("control", 92, 64, 1, [0, 1, 0, 1, 2, 0]),
                                                      ("vacancy", 120, 73, 1, [1, 1, 0, 0, 0, 0])):
            a = [w["arms"][arm]["analysis"] for w in self.value["worlds"]]
            self.assertEqual(sum(v["post_export_birth_cohort"]["births"] for v in a), births)
            self.assertEqual(sum(v["post_export_birth_cohort"]["confirmed"] for v in a), survivors)
            self.assertEqual(sum(v["post_export_birth_cohort"]["pending"] for v in a), pending)
            self.assertEqual(sum(len(v["reproducing_replacements"]) for v in a), 27)
            self.assertEqual([len(v["periods"][-1]["confirmations"]) for v in a], fresh)

    def test_missing_export_wrong_census_corrupt_resources_or_pixels_fail(self):
        for fault in ("event", "living", "resources", "pixels"):
            bad = copy.deepcopy(self.value)
            a = bad["worlds"][0]["arms"]["vacancy"]
            if fault == "event":
                a["result"]["vacancy_probe"]["event"] = None
            elif fault == "living":
                a["result"]["living"] += 1
            elif fault == "resources":
                a["audit"]["plants"][0]["resources"]["water"]["initial"] += 1
            else:
                a["frames"]["192"]["framebuffer_crc32"] = "00000000"
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                screen.check_value(bad)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path, required=True)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *rest])
