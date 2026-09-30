#!/usr/bin/env python3
"""Isolated range identities, unchanged scores, censoring and screen safeguards."""

import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import garden_landing_range as screen
from test_garden_landing_tools import run

BUILD = None


class RangeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel, cls.archive, cls.previous = screen.reach.load_inputs(screen.ROOT / "benchmarks/garden-seasons")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="landing-range-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_fixed_twelve_cases_and_unchanged_ordinary_scores(self):
        self.assertEqual(len(self.previous["plan"]), 12)
        for w in self.previous["worlds"]:
            h = screen.training.score_world(w["result"], w["case"], self.previous["models"][w["model"]]["metadata"])
            self.assertEqual(h, screen.training.rolling.history(w["result"]["lineages"], w["result"]["seeds"], 0, screen.STOP))
            screen.metrics(w["result"], w["audit"], h)

    def test_cache_contract_rejects_other_changes_and_missing_flags(self):
        base = {"TOY_FACTORY_GARDEN_WIDE_DISPERSAL": "OFF", "TOY_FACTORY_GARDEN_FLOWER_DISPERSAL": "OFF",
                "TOY_FACTORY_SIMULATOR_SANITIZERS": "ON", "CMAKE_C_FLAGS": "", "CMAKE_C_COMPILER": "/cc",
                "CMAKE_HOME_DIRECTORY": "/src/sim", "CMAKE_BUILD_TYPE": "RelWithDebInfo"}
        pair = {"narrow": base, "wide": {**base, screen.WIDE: "ON"}}
        paths = {a: self.root / (a + ".txt") for a in pair}

        def write(values):
            for arm, p in paths.items():
                p.write_text("".join(k + ":STRING=" + v + "\n" for k, v in values[arm].items()))

        write(pair)
        self.assertEqual(screen.check_builds(paths)["ecology"]["wide"][screen.WIDE], "ON")
        for key, value in ((screen.WIDE, "OFF"), ("TOY_FACTORY_GARDEN_FLOWER_DISPERSAL", "ON"),
                           ("TOY_FACTORY_SIMULATOR_SANITIZERS", "OFF"), ("CMAKE_C_COMPILER", "/other"),
                           ("CMAKE_C_FLAGS", "-ffast-math"), ("TOY_FACTORY_GARDEN_UNKNOWN", "ON")):
            bad = copy.deepcopy(pair)
            bad["wide"][key] = value
            write(bad)
            with self.assertRaises(RuntimeError):
                screen.check_builds(paths)
        bad = copy.deepcopy(pair)
        del bad["wide"]["TOY_FACTORY_GARDEN_FLOWER_DISPERSAL"]
        write(bad)
        with self.assertRaises(RuntimeError):
            screen.check_builds(paths)

    def test_empty_world_simultaneous_events_and_pending_censoring(self):
        result = {"tick": 90, "lineages": [{"birth_tick": 0, "death_tick": 30}],
                  "seeds": [{"birth_tick": 15, "end_tick": None}]}
        self.assertIsNone(screen.first_empty(result))
        result["seeds"][0]["end_tick"] = 60
        self.assertEqual(screen.first_empty(result), 60)
        result["lineages"].append({"birth_tick": 60, "death_tick": None})
        self.assertIsNone(screen.first_empty(result))
        result["lineages"][1]["death_tick"] = 75
        self.assertEqual(screen.first_empty(result), 75)
        result["tick"] = 70
        self.assertIsNone(screen.first_empty(result))

    @staticmethod
    def gate_fixture():
        groups = {c: {"scores": {"control": {"key": [1, 6, 5, 10]}, "candidate": {"key": [1, 6, 5, 10]},
                                  "comparison": 0},
                      "totals": {a: {"late_child_survivors": 5, "late_renewal_confirmations": 3} for a in screen.ARMS}}
                  for c in ("steady", "seasonal")}
        worlds = [{"arms": {a: {"metrics": {"first_empty_tick": None}} for a in screen.ARMS}}]
        return groups, worlds

    def test_gates_do_not_reward_raw_births_or_hide_a_climate_loss(self):
        groups, worlds = self.gate_fixture()
        self.assertFalse(all(screen.gates(groups, worlds).values()))
        groups["seasonal"]["totals"]["wide"]["births"] = 10000
        self.assertFalse(all(screen.gates(groups, worlds).values()))
        groups["seasonal"]["totals"]["wide"]["late_renewal_confirmations"] += 1
        self.assertTrue(all(screen.gates(groups, worlds).values()))
        for kind in ("key", "survivors", "empty", "earlier"):
            g, w = copy.deepcopy(groups), copy.deepcopy(worlds)
            if kind == "key":
                g["steady"]["scores"]["candidate"]["key"] = [1, 5, 999, 9999]
            elif kind == "survivors":
                g["steady"]["totals"]["wide"]["late_child_survivors"] = 4
            else:
                w[0]["arms"]["wide"]["metrics"]["first_empty_tick"] = 30
                if kind == "earlier":
                    w[0]["arms"]["narrow"]["metrics"]["first_empty_tick"] = 45
            self.assertFalse(all(screen.gates(g, w).values()))

    def test_explicit_native_arm_identity_and_untraced_capture_equivalence(self):
        cache = screen.cache_values(BUILD / "CMakeCache.txt")
        arm = "wide" if cache[screen.WIDE] == "ON" else "narrow"
        w = self.previous["worlds"][0]
        meta = self.previous["models"][w["model"]]
        model = self.root / "model.tgl"
        model.write_bytes(self.archive[meta["model"]])
        binary = BUILD / "toy-factory-garden-landing"
        base = ["replay", model, w["case"]["scenario"], "0x" + w["case"]["seed"], "--climate", w["case"]["climate"], "--ledger"]
        initial = screen.training.native(binary, self.root, *base, "--ticks", 0)
        self.assertEqual(initial["rules"], screen.ARMS[arm])
        trace = self.root / "trace.jsonl"
        result = screen.training.native(binary, self.root, *base, "--ticks", screen.STOP, "--recruitment-trace", trace)
        capture = screen.training.native(binary, self.root, *base, "--ticks", screen.STOP, "--framebuffer", "frame.rgb565be")
        self.assertEqual({**capture, "framebuffer_crc32": None}, result)
        raw = (self.root / "frame.rgb565be").read_bytes()
        score = screen.history(capture, w["case"], meta["metadata"], arm, raw)
        audit = screen.prior.analyze_trace(trace, result)
        screen.metrics(result, audit, score)
        if arm == "narrow":
            self.assertEqual(result, w["result"])
            self.assertEqual(audit, w["audit"])
        with self.assertRaises(RuntimeError):
            screen.history(capture, w["case"], meta["metadata"], "narrow" if arm == "wide" else "wide", raw)
        self.assertEqual(model.read_bytes(), self.archive[meta["model"]])

    def test_cli_verification_disallows_overrides_and_collection_needs_both_builds(self):
        tool, out = screen.ROOT / "sim/garden_landing_range.py", self.root / "out"
        for args in (("--out", out, "--narrow-build", BUILD), ("--verify", out, "--jobs", 2),
                     ("--out", out, "--narrow-build", BUILD, "--wide-build", BUILD, "--jobs", 0)):
            run([sys.executable, tool, *args], valid=False)
            self.assertFalse(out.exists())

    def test_portable_evidence_recomputes_scores_budgets_gates_and_images(self):
        directory = screen.ROOT / "benchmarks/garden-seasons"
        data = json.loads(gzip.decompress((directory / "landing-range-results.json.gz").read_bytes()))
        summary = json.loads((directory / "landing-range-summary.json").read_text())
        canonical = (json.dumps(data, sort_keys=True, indent=2) + "\n").encode()
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), summary["results_sha256"])
        self.assertEqual(screen.digest(screen.ROOT / screen.PROTOCOL), summary["protocol_sha256"])
        self.assertEqual(summary["manifest_sha256"],
                         "f15e65d6655575d5f40253458f75010a41e24bab0fcd218e6cc9c4ec8befd109")
        self.assertIs(summary["repeat_verified"], True)
        self.assertIs(summary["independent_frozen_verification"], True)
        self.assertEqual(summary["artifact_hashes_rechecked"], 405)
        self.assertEqual(data["plan"], self.previous["plan"])
        self.assertEqual(data["inputs"], screen.INPUTS)
        self.assertEqual(data["rule"], screen.RULE)
        self.assertEqual(data["arms"], screen.ARMS)
        self.assertEqual(data["objective"], screen.training.individual.RULE)
        self.assertEqual(data["models"], self.previous["models"])
        for w, old, brief in zip(data["worlds"], self.previous["worlds"], summary["worlds"], strict=True):
            self.assertEqual(w["id"], old["id"])
            self.assertEqual(w["arms"]["narrow"]["result"], old["result"])
            self.assertEqual(w["arms"]["narrow"]["audit"], old["audit"])
            self.assertEqual(w["arms"]["narrow"]["trace_sha256"], old["trace_sha256"])
            self.assertEqual(brief, {**{k: w[k] for k in ("id", "model", "case")}, "arms": {
                a: {k: x[k] for k in ("metrics", "trace_sha256", "frame")} for a, x in w["arms"].items()}})
            views = [{k: v for k, v in w["initial"][a].items() if k not in ("rules", "run_hash")} for a in screen.ARMS]
            self.assertEqual(views[0], views[1])
            self.assertNotEqual(w["initial"]["narrow"]["run_hash"], w["initial"]["wide"]["run_hash"])
            for arm, x in w["arms"].items():
                self.assertEqual(x["result"]["rules"], screen.ARMS[arm])
                self.assertEqual(x["result"]["model"], data["models"][w["model"]]["metadata"])
                h = screen.training.rolling.history(x["result"]["lineages"], x["result"]["seeds"], 0, screen.STOP)
                self.assertEqual(h, x["history"])
                self.assertEqual(screen.metrics(x["result"], x["audit"], h), x["metrics"])
                for p in x["audit"]["plants"]:
                    again = copy.deepcopy(p)
                    screen.prior.analyze_child(again, screen.STOP)
                    self.assertEqual(again, p)
                late = [p for p in x["audit"]["plants"] if 62 * screen.DAY < p["birth_tick"] <= 190 * screen.DAY]
                self.assertEqual(x["audit"]["summary"]["late_children"], screen.prior.child_summary(late))
                image = directory / "frames" / ("landing-range-" + Path(x["frame"]["png"]).name)
                self.assertEqual(screen.digest(image), x["frame"]["png_sha256"])
        self.assertEqual(data["comparison"], screen.compare(data["worlds"]))
        self.assertEqual(summary["comparison"], data["comparison"])
        self.assertFalse(data["comparison"]["passes_screen"])
        overall = data["comparison"]["groups"]["all"]
        self.assertEqual(overall["scores"]["paired_counts"], {"wins": 5, "ties": 0, "losses": 7})
        for arm, expected in (("narrow", (127, 55, 72)), ("wide", (268, 60, 208))):
            self.assertEqual(tuple(overall["totals"][arm][k] for k in
                ("late_child_births", "late_child_survivors", "late_child_deaths")), expected)
        self.assertEqual(summary["sheets"], data["sheets"])
        self.assertEqual(len(summary["portable_images"]), 26)
        for path, sha in summary["portable_images"].items():
            self.assertEqual(screen.digest(directory / path), sha)
        for climate, sheet in data["sheets"].items():
            self.assertEqual(screen.digest(directory / "frames" / ("landing-range-" + climate + ".png")), sheet["sha256"])
            self.assertEqual(sheet["rows"], [[w["arms"][a]["frame"]["id"] for a in screen.ARMS]
                             for w in data["worlds"] if w["case"]["climate"] == climate])
        for arm in screen.ARMS:
            self.assertEqual(summary["sample_totals"][arm], {k: sum(w["arms"][arm]["audit"][k] for w in data["worlds"])
                             for k in ("ecology_samples", "seed_samples", "seed_checks", "first_day_samples")})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path, required=True)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *rest])
