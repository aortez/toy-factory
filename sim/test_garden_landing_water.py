#!/usr/bin/env python3
"""Water probe identities, exact controls, receipts, malformed inputs and gates."""

import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import garden_landing_water as screen
from test_garden_landing_tools import run
import test_garden_landing_range as range_tests

BUILD = None


class WaterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel, cls.archive, cls.old = screen.load_inputs(screen.ROOT / "benchmarks/garden-seasons")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="landing-water-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.binary = BUILD / "toy-factory-garden-landing"
        self.saved = self.old["worlds"][0]
        self.meta = self.old["models"][self.saved["model"]]
        self.model = self.root / "model.tgl"
        self.model.write_bytes(self.archive[self.meta["model"]])

    def args(self, mode, ticks=0):
        c = self.saved["case"]
        return ("water-replay", self.model, c["scenario"], "0x" + c["seed"], "--climate", c["climate"],
                "--ticks", ticks, "--ledger", "--water-reserve", mode)

    def test_explicit_identity_and_ordinary_trainer_rejects_probe(self):
        results = [screen.training.native(self.binary, self.root, *self.args(m)) for m in ("off", "on")]
        self.assertEqual(screen.common_view(results[0], False), screen.common_view(results[1], True))
        self.assertNotEqual(results[0]["run_hash"], results[1]["run_hash"])
        with self.assertRaises(RuntimeError):
            screen.common_view(results[0], True)
        for field, value in (("kind", "landing-replay"), ("run_hash", "00000000"), ("rules", 1),
                             ("water_probe", {"version": 1, "enabled": 0})):
            with self.assertRaises(RuntimeError):
                screen.common_view({**results[0], field: value}, False)
        ordinary = self.saved["result"]
        tagged = {**ordinary, "kind": "landing-water-replay", "base_run_hash": ordinary["run_hash"],
                  "run_hash": screen.water_hash(ordinary["run_hash"], False), "water_probe": {"version": 1, "enabled": False}}
        with self.assertRaises(RuntimeError):
            screen.training.score_world(tagged, self.saved["case"], self.meta["metadata"])

    def test_strict_cli_and_no_clobber(self):
        base = self.args("off")
        for args in (base[:-2], (*base[:-1], "both"), (*base, "--water-reserve", "on"),
                     ("replay", *base[1:]), (*base, "--reach-trace", self.root / "reach.jsonl"),
                     (*base, "--resources", "fixed"), (*base, "--water-trace", "")):
            run([self.binary, *args], valid=False)
        no_ledger = tuple(v for v in base if v != "--ledger")
        path = self.root / "water.jsonl"
        run([self.binary, *no_ledger, "--water-trace", path], valid=False)
        self.assertFalse(path.exists())
        path.write_text("existing\n")
        run([self.binary, *base, "--water-trace", path], valid=False)
        self.assertEqual(path.read_text(), "existing\n")
        for args in (("--verify", self.root, "--jobs", 1), ("--out", self.root / "out", "--jobs", 0)):
            run([sys.executable, screen.ROOT / "sim/garden_landing_water.py", *args], valid=False)
        self.assertFalse((self.root / "out").exists())

    @staticmethod
    def winner(**values):
        return {"id": 9, "age": 1, "water": 8, "nodes": 4, "roots": 2, "species": 0,
                "tissue": 0, "action": 1, "priority": 3, "tip_moisture": 0, "destination": [130, 0],
                "cost": 5, "upkeep": 1, "reserve": 4, "wet_root": False, "allowed": False,
                "applied": True, "result_action": 0, "bids": 4, "denied_bids": 4,
                "funded_wet_root_bids": 0, **values}

    def test_forecast_equality_wetter_root_soil_boundary_and_first_day(self):
        w = self.winner()
        screen.check_winner(w, True)
        screen.check_winner({**w, "applied": False, "result_action": 1}, False)
        screen.check_winner({**w, "water": 9, "allowed": True, "applied": False, "result_action": 1}, True)
        root = self.winner(tissue=1, water=6, destination=[144, 5], reserve=1, wet_root=True,
                           allowed=True, applied=False, result_action=1, denied_bids=3, funded_wet_root_bids=1)
        screen.check_winner(root, True)
        for update in ({"destination": [143, 5]}, {"tip_moisture": 5}, {"water": 5}, {"age": 0},
                       {"age": 257}, {"bids": 0}, {"denied_bids": 4}, {"allowed": 1}):
            with self.assertRaises(RuntimeError):
                screen.check_winner({**root, **update}, True)
        for age in (1, 256):
            screen.check_winner({**root, "age": age}, True)

    def test_full_native_receipts_trace_disabled_repeat_and_rollback(self):
        for mode, enabled in (("off", False), ("on", True)):
            base = self.args(mode, screen.STOP)
            trace, water = self.root / (mode + ".jsonl"), self.root / (mode + "-water.jsonl")
            result = screen.training.native(self.binary, self.root, *base, "--recruitment-trace", trace, "--water-trace", water)
            audit = screen.prior.analyze_trace(trace, result)
            observed = screen.analyze_water_trace(water, result, audit, enabled)
            self.assertGreater(observed["all"]["winners"], 0)
            raw = self.root / (mode + ".rgb565be")
            capture = screen.training.native(self.binary, self.root, *base, "--framebuffer", raw)
            self.assertEqual({**capture, "framebuffer_crc32": None}, result)
            screen.previous.history(screen.common_view(capture, enabled), self.saved["case"], self.meta["metadata"], "narrow", raw.read_bytes())
            repeated = self.root / (mode + "-repeat.jsonl")
            self.assertEqual(screen.training.native(self.binary, self.root, *base, "--water-trace", repeated), result)
            self.assertEqual(repeated.read_bytes(), water.read_bytes())
            if not enabled:
                self.assertEqual(screen.common_view(result, False), self.saved["result"])
                self.assertEqual(audit, self.saved["audit"])
                self.assertEqual(observed["all"]["applied_waits"], 0)
            else:
                self.assertGreater(observed["all"]["applied_waits"], 0)
            lines = water.read_text().splitlines()
            sample = next(i for i, line in enumerate(lines[1:-1], 1) if json.loads(line)["winners"])
            original = json.loads(lines[sample])
            bad = self.root / "bad.jsonl"
            for kind in ("missing", "duplicate", "debit", "founder", "truncated", "trailing"):
                rows = lines.copy()
                entry = copy.deepcopy(original)
                if kind == "missing":
                    rows.pop(sample)
                elif kind == "truncated":
                    rows.pop()
                elif kind == "trailing":
                    rows.append("{}")
                else:
                    if kind == "duplicate":
                        entry["winners"].append(entry["winners"][0])
                    elif kind == "founder":
                        entry["winners"][0]["id"] = result["lineages"][0]["id"]
                    else:
                        entry["winners"][0]["water"] += 1
                    rows[sample] = json.dumps(entry)
                bad.write_text("\n".join(rows) + "\n")
                with self.assertRaises((RuntimeError, StopIteration)):
                    screen.analyze_water_trace(bad, result, audit, enabled)
            self.assertEqual(screen.analyze_water_trace(water, result, audit, enabled), observed)
        self.assertEqual(self.model.read_bytes(), self.archive[self.meta["model"]])

    def test_gates_do_not_reward_raw_births_or_hide_a_climate_loss(self):
        groups, worlds = range_tests.RangeTests.gate_fixture()
        for group in groups.values():
            group["totals"] = dict(zip(screen.ARMS, group["totals"].values(), strict=True))
        worlds[0]["arms"] = dict(zip(screen.ARMS, worlds[0]["arms"].values(), strict=True))
        self.assertFalse(all(screen.gates(groups, worlds).values()))
        groups["seasonal"]["totals"]["water"]["births"] = 100000
        self.assertFalse(all(screen.gates(groups, worlds).values()))
        groups["seasonal"]["totals"]["water"]["late_renewal_confirmations"] += 1
        self.assertTrue(all(screen.gates(groups, worlds).values()))
        groups["steady"]["scores"]["candidate"]["key"] = [1, 5, 99999, 99999]
        self.assertFalse(all(screen.gates(groups, worlds).values()))

    def test_portable_panel_reconciles_all_receipts_scores_budgets_and_images(self):
        directory = screen.ROOT / "benchmarks/garden-seasons"
        raw = gzip.decompress((directory / "landing-water-results.json.gz").read_bytes())
        data = json.loads(raw)
        summary = json.loads((directory / "landing-water-summary.json").read_text())
        self.assertEqual(hashlib.sha256(raw).hexdigest(), summary["results_sha256"])
        self.assertEqual(summary["manifest_sha256"],
                         "83e59e734570ddc56a1aa547424bb90b9441a90514e2659a9152031340063d7e")
        self.assertEqual(screen.digest(screen.ROOT / screen.PROTOCOL), summary["protocol_sha256"])
        self.assertIs(summary["repeat_verified"], True)
        self.assertIs(summary["independent_frozen_verification"], True)
        self.assertEqual(summary["artifact_hashes_rechecked"], 456)
        for field in ("rule", "objective", "inputs", "plan", "models", "arms", "comparison", "sheets"):
            self.assertEqual(data[field], summary[field])
        self.assertEqual(data["plan"], self.old["plan"])
        self.assertEqual(data["models"], self.old["models"])
        self.assertEqual(data["inputs"], screen.INPUTS)
        self.assertEqual(data["rule"], screen.RULE)
        self.assertEqual(data["objective"], screen.training.individual.RULE)
        self.assertEqual(data["arms"], screen.ARMS)
        path = self.root / "reconstructed.jsonl"
        for w, old, brief in zip(data["worlds"], self.old["worlds"], summary["worlds"], strict=True):
            self.assertEqual({k: w[k] for k in ("id", "case", "model")},
                             {k: old[k] for k in ("id", "case", "model")})
            self.assertEqual(screen.common_view(w["initial"]["control"], False),
                             screen.common_view(w["initial"]["water"], True))
            self.assertEqual(screen.common_view(w["arms"]["control"]["result"], False), old["result"])
            self.assertEqual(w["arms"]["control"]["audit"], old["audit"])
            self.assertEqual(w["arms"]["control"]["trace_sha256"], old["trace_sha256"])
            for arm, enabled in screen.ARMS.items():
                x = w["arms"][arm]
                screen.common_view(x["result"], enabled)
                h = screen.training.rolling.history(x["result"]["lineages"], x["result"]["seeds"], 0, screen.STOP)
                self.assertEqual(x["history"], h)
                self.assertEqual(x["metrics"], screen.previous.metrics(x["result"], x["audit"], h))
                self.assertEqual(brief["arms"][arm], {
                    **{k: x[k] for k in ("metrics", "trace_sha256", "water_trace_sha256", "frame")},
                    "water_audit": {k: x["water_audit"][k] for k in ("all", "late")}})
                for p in x["audit"]["plants"]:
                    checked = copy.deepcopy(p)
                    screen.prior.analyze_child(checked, screen.STOP)
                    self.assertEqual(checked, p)
                self.assertEqual(x["late_children"], [screen.establishment.summarize_child(p, screen.STOP)
                    for p in x["audit"]["plants"] if 62 * screen.DAY < p["birth_tick"] <= 190 * screen.DAY])
                by_tick = {}
                for winner in x["water_audit"]["winners"]:
                    by_tick.setdefault(winner["tick"], []).append({k: v for k, v in winner.items() if k != "tick"})
                with path.open("w") as stream:
                    stream.write(json.dumps({"schema": "landing-water-trace-v1", "enabled": enabled}) + "\n")
                    for tick in range(screen.STEP, screen.STOP + 1, screen.STEP):
                        stream.write(json.dumps({"tick": tick, "winners": by_tick.get(tick, [])}) + "\n")
                    stream.write(json.dumps({"complete": True, "tick": screen.STOP}) + "\n")
                self.assertEqual(screen.analyze_water_trace(path, x["result"], x["audit"], enabled), x["water_audit"])
                self.assertEqual(screen.digest(directory / "frames" / ("landing-water-" + Path(x["frame"]["png"]).name)),
                                 x["frame"]["png_sha256"])
        self.assertEqual(data["comparison"], screen.compare(data["worlds"]))
        self.assertFalse(data["comparison"]["passes_screen"])
        self.assertEqual(data["comparison"]["groups"]["all"]["scores"]["paired_counts"],
                         {"wins": 3, "ties": 2, "losses": 7})
        for arm, expected in (("control", (127, 55, 72)), ("water", (135, 60, 75))):
            totals = data["comparison"]["groups"]["all"]["totals"][arm]
            self.assertEqual(tuple(totals[k] for k in ("late_child_births", "late_child_survivors", "late_child_deaths")), expected)
            self.assertEqual(summary["sample_totals"][arm], {k: sum(w["arms"][arm]["audit"][k] for w in data["worlds"])
                for k in ("ecology_samples", "seed_samples", "seed_checks", "first_day_samples")})
        self.assertEqual(len(summary["portable_images"]), 26)
        for relative, sha in summary["portable_images"].items():
            self.assertEqual(screen.digest(directory / relative), sha)
        for climate, sheet in data["sheets"].items():
            self.assertEqual(screen.digest(directory / "frames" / ("landing-water-" + climate + ".png")), sheet["sha256"])
            self.assertEqual(sheet["rows"], [[w["arms"][a]["frame"]["id"] for a in screen.ARMS]
                for w in data["worlds"] if w["case"]["climate"] == climate])
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path, required=True)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *rest])
