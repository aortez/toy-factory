#!/usr/bin/env python3
"""Water-eligible selection, receipts, compatibility and portable evidence."""

import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import garden_landing_arbitration as screen
from test_garden_landing_tools import run
import test_garden_landing_water as water_tests

BUILD = None


class ArbitrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models, cls.archive = screen.load_inputs(screen.ROOT / "benchmarks/garden-seasons")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="landing-arbitration-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.binary = BUILD / "toy-factory-garden-landing"
        self.saved = self.archive["worlds"][0]
        self.meta = self.archive["models"][self.saved["model"]]
        self.model = self.root / "model.tgl"
        self.model.write_bytes(self.models[self.meta["model"]])

    def args(self, mode, ticks=0):
        c = self.saved["case"]
        return ("arbitration-replay", self.model, c["scenario"], "0x" + c["seed"], "--climate", c["climate"],
                "--ticks", ticks, "--ledger", "--water-arbitration", mode)

    def test_identity_and_strict_cli(self):
        results = [screen.training.native(self.binary, self.root, *self.args(m)) for m in screen.ARMS]
        self.assertEqual(screen.common_view(results[0], "veto"), screen.common_view(results[1], "eligible"))
        self.assertNotEqual(results[0]["run_hash"], results[1]["run_hash"])
        for mode, result in zip(screen.ARMS, results):
            for field, value in (("kind", "landing-replay"), ("run_hash", "00000000"), ("rules", 1),
                                 ("water_probe", {"version": 2, "enabled": 1, "arbitration": mode})):
                with self.assertRaises(RuntimeError):
                    screen.common_view({**result, field: value}, mode)
            with self.assertRaises(RuntimeError):
                screen.training.score_world(result, self.saved["case"], self.meta["metadata"])
        base = self.args("eligible")
        for args in (base[:-2], (*base[:-1], "on"), (*base, "--water-arbitration", "veto"),
                     ("replay", *base[1:]), ("water-replay", *base[1:]), (*base, "--water-reserve", "on"),
                     (*base, "--reach-trace", self.root / "reach"), (*base, "--water-trace", "")):
            run([self.binary, *args], valid=False)
        path = self.root / "bids.jsonl"
        run([self.binary, *(v for v in base if v != "--ledger"), "--water-trace", path], valid=False)
        self.assertFalse(path.exists())
        path.write_text("existing\n")
        run([self.binary, *base, "--water-trace", path], valid=False)
        self.assertEqual(path.read_text(), "existing\n")
        for args in (("--verify", self.root, "--jobs", 1), ("--out", self.root / "out", "--jobs", 0)):
            run([sys.executable, screen.ROOT / "sim/garden_landing_arbitration.py", *args], valid=False)
        self.assertFalse((self.root / "out").exists())

    @staticmethod
    def entry():
        stem = water_tests.WaterTests.winner(applied=False, result_action=1, bids=2, denied_bids=1, funded_wet_root_bids=1)
        root = {**stem, "tissue": 1, "priority": -32768, "destination": [144, 5], "reserve": 1,
                "wet_root": True, "allowed": True}
        return {"id": 9, "original": 0, "selected": 1, "fallback": False, "result_action": 1,
                "committed_memory": [2] * 8,
                "bids": [{"tip": i, "x": 15, "y": 140 + 5 * i, "memory": [0] * 8,
                          "next_memory": [i + 1] * 8, "proposal": p} for i, p in enumerate((stem, root))]}

    def test_ranking_ties_wait_fallback_and_memory(self):
        e = self.entry()
        self.assertEqual(screen.check_entry(e, "eligible")["tissue"], 1)
        veto = {**e, "selected": 0, "fallback": True, "result_action": 0, "committed_memory": [1] * 8}
        self.assertTrue(screen.check_entry(veto, "veto")["applied"])
        for priority in (-32768, 32767):
            tie = copy.deepcopy(e)
            for b in tie["bids"]:
                b["proposal"]["priority"] = priority
            screen.check_entry(tie, "eligible")
        # A genuine WAIT is not excluded; its priority can legitimately beat root growth.
        wait = copy.deepcopy(e)
        for b in wait["bids"]:
            b["proposal"]["denied_bids"] = 0
        wait["bids"][0]["proposal"].update(action=0, result_action=0, destination=None, cost=0,
            upkeep=0, reserve=0, allowed=True)
        wait.update(selected=0, result_action=0, committed_memory=[1] * 8)
        self.assertFalse(screen.check_entry(wait, "eligible")["applied"])
        denied = copy.deepcopy(e)
        for b in denied["bids"]:
            b["proposal"].update(water=5, allowed=False, denied_bids=2, funded_wet_root_bids=0)
        denied.update(selected=0, fallback=True, result_action=0, committed_memory=[1] * 8)
        self.assertTrue(screen.check_entry(denied, "eligible")["applied"])
        # Fully eligible equal priorities retain the first encountered proposal.
        equal = copy.deepcopy(e)
        for b in equal["bids"]:
            b["proposal"].update(water=9, allowed=True, denied_bids=0, priority=-32768)
        equal.update(selected=0, committed_memory=[1] * 8)
        self.assertEqual(screen.check_entry(equal, "eligible")["tissue"], 0)

    def test_corrupt_bids_are_rejected(self):
        e = self.entry()
        for kind in ("selection", "fallback", "commit", "memory", "duplicate", "forecast", "count", "tip", "age", "empty"):
            bad = copy.deepcopy(e)
            if kind == "selection": bad["selected"] = 0
            elif kind == "fallback": bad["fallback"] = True
            elif kind == "commit": bad["committed_memory"] = [1] * 8
            elif kind == "memory": bad["bids"][1]["memory"][0] = 1
            elif kind == "duplicate": bad["bids"][1]["tip"] = 0
            elif kind == "forecast": bad["bids"][1]["proposal"]["reserve"] = 4
            elif kind == "count": bad["bids"][1]["proposal"]["denied_bids"] = 0
            elif kind == "tip": bad["bids"][1]["tip"] = 256
            elif kind == "age": bad["bids"][1]["proposal"]["age"] = 257
            else: bad["bids"] = []
            with self.assertRaises(RuntimeError, msg=kind):
                screen.check_entry(bad, "eligible")
        screen.check_entry(e, "eligible")

    def test_native_trace_resources_repeat_and_historical_control(self):
        for mode in screen.ARMS:
            base = self.args(mode, screen.STOP)
            trace, bids = self.root / (mode + ".jsonl"), self.root / (mode + "-bids.jsonl")
            result = screen.training.native(self.binary, self.root, *base, "--recruitment-trace", trace, "--water-trace", bids)
            audit = screen.prior.analyze_trace(trace, result)
            water, arbitration = screen.analyze_trace(bids, result, audit, mode)
            self.assertGreater(arbitration["all"]["decisions"], 0)
            if mode == "veto":
                old = self.saved["arms"]["water"]
                self.assertEqual(screen.common_view(result, mode), screen.previous.common_view(old["result"], True))
                self.assertEqual(audit, old["audit"])
                self.assertEqual(water, old["water_audit"])
            else:
                self.assertEqual(arbitration["all"]["fallback_with_eligible_bid"], 0)
            repeated = self.root / (mode + "-repeat.jsonl")
            self.assertEqual(screen.training.native(self.binary, self.root, *base, "--water-trace", repeated), result)
            self.assertEqual(repeated.read_bytes(), bids.read_bytes())
            self.assertEqual(screen.training.native(self.binary, self.root, *base), result)
            lines = bids.read_text().splitlines()
            sample = next(i for i, s in enumerate(lines[1:-1], 1) if json.loads(s)["plants"])
            path = self.root / "bad.jsonl"
            for kind in ("missing", "duplicate", "debit", "truncated", "trailing"):
                rows = lines.copy()
                if kind == "missing": rows.pop(sample)
                elif kind == "truncated": rows.pop()
                elif kind == "trailing": rows.append("{}")
                else:
                    entry = json.loads(rows[sample])
                    if kind == "duplicate": entry["plants"].append(entry["plants"][0])
                    else:
                        for b in entry["plants"][0]["bids"]: b["proposal"]["water"] += 1
                    rows[sample] = json.dumps(entry)
                path.write_text("\n".join(rows) + "\n")
                with self.assertRaises((RuntimeError, StopIteration)):
                    screen.analyze_trace(path, result, audit, mode)
        self.assertEqual(self.model.read_bytes(), self.models[self.meta["model"]])

    def test_portable_panel(self):
        directory = screen.ROOT / "benchmarks/garden-seasons"
        raw = gzip.decompress((directory / "landing-arbitration-results.json.gz").read_bytes())
        data = json.loads(raw)
        summary = json.loads((directory / "landing-arbitration-summary.json").read_text())
        self.assertEqual(summary["results_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(summary["portable_sha256"], screen.digest(directory / "landing-arbitration-results.json.gz"))
        self.assertEqual(summary["protocol_sha256"], screen.digest(screen.ROOT / screen.PROTOCOL))
        self.assertEqual(summary["manifest_sha256"], "1a858785e3b8a988c84fefaa13d4a2e94c275285ca5bcd1a275510381ca0148e")
        self.assertIs(summary["repeat_verified"], True)
        self.assertIs(summary["independent_frozen_verification"], True)
        self.assertEqual(summary["artifact_hashes_rechecked"], 461)
        for k in ("schema_version", "rule", "objective", "inputs", "plan", "models", "arms", "comparison", "sheets"):
            self.assertEqual(summary[k], data[k])
        self.assertEqual(len(summary["portable_images"]), 26)
        for relative, sha in summary["portable_images"].items():
            self.assertEqual(screen.digest(directory / relative), sha)
        self.assertEqual(data["rule"], screen.RULE)
        self.assertEqual(data["inputs"], screen.INPUTS)
        self.assertEqual(data["plan"], self.archive["plan"])
        self.assertEqual(data["models"], self.archive["models"])
        self.assertEqual(data["arms"], screen.ARMS)
        for w, old in zip(data["worlds"], self.archive["worlds"], strict=True):
            self.assertEqual({k: w[k] for k in ("id", "model", "case")}, {k: old[k] for k in ("id", "model", "case")})
            for arm in screen.ARMS:
                x = w["arms"][arm]
                screen.common_view(x["result"], arm)
                history = screen.training.rolling.history(x["result"]["lineages"], x["result"]["seeds"], 0, screen.STOP)
                self.assertEqual(x["history"], history)
                self.assertEqual(x["metrics"], screen.previous.previous.metrics(x["result"], x["audit"], history))
                for p in x["audit"]["plants"]:
                    checked = copy.deepcopy(p)
                    screen.prior.analyze_child(checked, screen.STOP)
                    self.assertEqual(checked, p)
                self.assertEqual(x["late_children"], [screen.establishment.summarize_child(p, screen.STOP)
                    for p in x["audit"]["plants"] if 62 * screen.DAY < p["birth_tick"] <= 190 * screen.DAY])
                by_tick = {}
                for entry in x["arbitration_audit"]["entries"]:
                    by_tick.setdefault(entry["tick"], []).append({k: v for k, v in entry.items() if k != "tick"})
                path = self.root / "reconstructed.jsonl"
                with path.open("w") as stream:
                    stream.write(json.dumps({"schema": "landing-arbitration-trace-v1", "arbitration": arm}) + "\n")
                    for tick in range(screen.STEP, screen.STOP + 1, screen.STEP):
                        stream.write(json.dumps({"tick": tick, "plants": by_tick.get(tick, [])}) + "\n")
                    stream.write(json.dumps({"complete": True, "tick": screen.STOP}) + "\n")
                self.assertEqual(screen.analyze_trace(path, x["result"], x["audit"], arm), (x["water_audit"], x["arbitration_audit"]))
                if arm == "veto":
                    self.assertEqual(screen.common_view(x["result"], arm), screen.previous.common_view(old["arms"]["water"]["result"], True))
                    for k in ("audit", "water_audit", "history", "trace_sha256"):
                        self.assertEqual(x[k], old["arms"]["water"][k])
                self.assertEqual(screen.digest(directory / "frames" / ("landing-arbitration-" + Path(x["frame"]["png"]).name)), x["frame"]["png_sha256"])
        self.assertEqual(data["comparison"], screen.compare(data["worlds"], self.archive))
        expected_brief = [{**{k: w[k] for k in ("id", "model", "case")}, "arms": {a: {
            **{k: x[k] for k in ("metrics", "trace_sha256", "arbitration_trace_sha256", "frame")},
            "water_audit": {k: x["water_audit"][k] for k in ("all", "late")},
            "arbitration_audit": {k: x["arbitration_audit"][k] for k in ("all", "late")}}
            for a, x in w["arms"].items()}} for w in data["worlds"]]
        self.assertEqual(summary["worlds"], expected_brief)
        for climate in ("all", "steady", "seasonal"):
            for scope in ("all", "late"):
                for arm in screen.ARMS:
                    expected = {k: sum(w["arms"][arm]["arbitration_audit"][scope][k] for w in data["worlds"]
                        if climate == "all" or w["case"]["climate"] == climate)
                        for k in data["worlds"][0]["arms"][arm]["arbitration_audit"][scope]}
                    self.assertEqual(summary["arbitration_totals"][climate][scope][arm], expected)
        for baseline in ("veto", "ordinary"):
            self.assertFalse(data["comparison"]["comparisons"][baseline]["passes_screen"])
        self.assertEqual(summary["arbitration_totals"]["all"]["late"]["eligible"]["switches"], 252)
        for climate, sheet in data["sheets"].items():
            self.assertEqual(screen.digest(directory / "frames" / ("landing-arbitration-" + climate + ".png")), sheet["sha256"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path, required=True)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *rest])
