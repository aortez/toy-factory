#!/usr/bin/env python3
"""Observer equivalence, independent counterfactuals and trace failure boundaries."""

import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_decisions as trace
from test_garden_landing_tools import run

BUILD = None


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="landing-decisions-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cli = BUILD / "toy-factory-garden-landing"
        self.inputs = trace.ROOT / "benchmarks/garden-seasons"
        self.models, _ = trace.signals.prepare_models(self.cli, self.inputs, self.root / "models")
        self.sequence = 0

    def native(self, *args, **kwargs):
        data = run([self.cli, *args], **kwargs)
        return json.loads(data) if data else None

    def sample(self, model=None, layout="rainfed", ticks=7680, image=False):
        model = model or self.models[0]
        path = self.root / "models" / model["model"]
        stem = str(self.sequence)
        self.sequence += 1
        destination = self.root / (stem + ".jsonl")
        raw = self.root / (stem + ".raw")
        args = [path, layout, "0xa9c30c1f", "--ticks", ticks, "--climate", "seasonal", "--ledger"]
        result = self.native("trace-replay", *args, "--trace", destination,
                             *(["--framebuffer", raw] if image else []))
        rows = [json.loads(line) for line in destination.read_text().splitlines()]
        analysis = trace.analyze_trace(rows, path.read_bytes(), result)
        return model, path, args, result, rows, analysis, destination, raw

    def test_live_trace_plain_repeat_and_captured_pixels_match(self):
        for model in self.models:
            for layout in ("rainfed", "rainfed-crowded"):
                _, path, args, result, rows, analysis, output, raw = self.sample(model, layout, image=True)
                original_model = path.read_bytes()
                control_raw = self.root / ("control-" + str(self.sequence) + ".raw")
                plain = self.native("replay", *args, "--framebuffer", control_raw)
                self.assertEqual(result, plain)
                self.assertEqual(raw.read_bytes(), control_raw.read_bytes())
                repeated = self.sample(model, layout)
                self.assertEqual(repeated[3], {**result, "framebuffer_crc32": None})
                self.assertEqual(output.read_bytes(), repeated[6].read_bytes())
                self.assertEqual(analysis, repeated[5])
                self.assertEqual(path.read_bytes(), original_model)
                self.assertGreater(analysis["queries"]["root"], 0)
                self.assertGreater(analysis["queries"]["stem"], 0)
                self.assertLessEqual(sum(analysis["samples"].values()), 4)
                self.assertEqual(rows[0]["probes"], trace.PROBES)
                for probe in trace.PROBES:
                    self.assertEqual(analysis["counts"]["all"]["root"][probe["id"]]["decision_changed"], 0)
        # Empty and partial-day runs keep the same boundary rules.
        for ticks in (0, 14, 15, 3839, 3840, 3841):
            self.sample(ticks=ticks)

    def test_cli_rejects_implicit_probes_bad_masks_and_existing_outputs(self):
        model = self.root / "models" / self.models[0]["model"]
        args = [model, "rainfed", "0x1234", "--ticks", 0, "--climate", "steady"]
        output = self.root / "invalid.jsonl"
        for command in (["trace-replay", *args], ["replay", *args, "--trace", output],
                        ["probe-replay", *args, "--trace", output],
                        ["trace-replay", *args, "--trace", output, "--trace", output],
                        ["trace-replay", *args, "--trace", output, "--occupancy", "open"],
                        ["trace-replay", *args, "--trace", output, "--resources", "mid"]):
            self.native(*command, valid=False)
            self.assertFalse(output.exists())
        for mode, omit in (("off", False), ("history", False), ("current", True)):
            unsupported = self.root / (mode + ".tgl")
            self.native("reference", unsupported, "--mode", mode, *(["--omit-dead-only"] if omit else []))
            self.native("trace-replay", unsupported, *args[1:], "--trace", output, valid=False)
            self.assertFalse(output.exists())
        output.write_bytes(b"retain me")
        self.native("trace-replay", *args, "--trace", output, valid=False)
        self.assertEqual(output.read_bytes(), b"retain me")

    def test_missing_tampered_and_duplicate_trace_records_fail(self):
        _, path, _, result, rows, _, _, _ = self.sample()
        stem = next(i for i, r in enumerate(rows) if r.get("kind") == "sample" and r["role"] == 1)
        def cases():
            yield rows[:-1]
            bad = copy.deepcopy(rows)
            bad[0]["model"] = "bad"
            yield bad
            bad = copy.deepcopy(rows)
            bad[0]["probes"][0]["fields"] = 15
            yield bad
            bad = copy.deepcopy(rows)
            bad[-1]["run_hash"] = "bad"
            yield bad
            bad = copy.deepcopy(rows)
            bad[-1]["daily_queries"][0][1] += 1
            yield bad
            bad = copy.deepcopy(rows)
            bad[stem]["probes"][1]["priority"] += 1
            yield bad
            bad = copy.deepcopy(rows)
            bad.insert(stem, copy.deepcopy(rows[stem]))
            yield bad
            bad = copy.deepcopy(rows)
            bad[stem]["valid"] = 0
            yield bad
            bad = copy.deepcopy(rows)
            bad[stem]["probes"].pop()
            yield bad
        for bad in cases():
            with self.assertRaises((RuntimeError, KeyError)):
                trace.analyze_trace(bad, path.read_bytes(), result)

    def test_probe_fields_and_metrics_do_not_confuse_ranks_with_actions(self):
        row = {"valid": 3, "packet": [[11, 22, 33, 44, 55, 66, 77, 88]] * 6}
        for probe in trace.PROBES:
            actual = trace.inputs(row, probe)
            for f in range(4):
                expected = (probe["values"][f] if probe["fields"] & (1 << f) else row["packet"][0][f]) - 128
                self.assertEqual(actual["landing_common"][f], expected)
                self.assertEqual(actual["landing_candidates"][0][f], expected)
            self.assertEqual(actual["landing_common"][4:], [0] * 5)
            self.assertTrue(all(v == [0] * 8 for v in actual["landing_candidates"][1:]))
        a = {"decision": {"action": 1, "priority": 2, "count": 3, "order": [0, 1, 2, 255, 255], "memory": [0] * 8},
             "hidden_sum": [0] * 16, "hidden": [0] * 16, "logits": [0] * 3}
        b = copy.deepcopy(a)
        b["decision"]["order"] = [1, 0, 2, 255, 255]
        m = trace.metrics({"flags": [1, 3, 3]}, a, b)
        self.assertEqual((m["action_changed"], m["order_changed"], m["first_available_changed"]), (0, 1, 0))
        b["decision"]["order"] = [2, 0, 1, 255, 255]
        self.assertEqual(trace.metrics({"flags": [1, 3, 3]}, a, b)["first_available_changed"], 1)
        b["decision"]["action"] = 0
        self.assertEqual(trace.metrics({"flags": [1, 3, 3]}, a, b)["order_changed"], 0)
        self.assertEqual(trace.histogram_stats([0] * 256)["minimum"], None)

    def test_collection_fails_closed_on_bad_inputs_or_source_change(self):
        output = self.root / "failed"
        with self.assertRaises(RuntimeError):
            trace.collect(BUILD, self.inputs, output, 0)
        self.assertFalse(output.exists())
        with patch.object(trace, "snapshot_sources"), \
             patch.object(trace, "source_files", side_effect=[
                 {trace.PROTOCOL: trace.digest(trace.ROOT / trace.PROTOCOL)}, {"changed": "sha"}]), \
             patch.object(trace, "run_panel", return_value={"worlds": {}}):
            with self.assertRaisesRegex(RuntimeError, "sources/build changed"):
                trace.collect(BUILD, self.inputs, output, 2)
        self.assertTrue((output / "FAILED.txt").exists())
        self.assertFalse((output / "manifest.json").exists())
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            trace.verify(output)
        with self.assertRaisesRegex(RuntimeError, "fresh"):
            trace.collect(BUILD, self.inputs, output, 2)

    def test_retained_evidence_matches_controls_and_independent_arithmetic(self):
        def archive(name):
            with gzip.open(self.inputs / name, "rt") as stream:
                return json.load(stream)

        result = archive("landing-decisions-results.json.gz")
        raw = archive("landing-decisions-traces.json.gz")
        control = archive("landing-validation-results.json.gz")
        summary = json.loads((self.inputs / "landing-decisions-summary.json").read_text())
        cases = trace.signals.previous.conditions()
        identities = {m["id"] + "--" + c["id"] for m in self.models for c in cases}
        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(result["rule"], trace.RULE)
        self.assertEqual(result["models"], self.models)
        self.assertEqual(result["conditions"], cases)
        self.assertEqual(result["probes"], trace.PROBES)
        self.assertEqual(set(result["worlds"]), identities)
        self.assertEqual(set(raw), identities)
        self.assertEqual(set(summary["worlds"]), identities)
        models = {m["id"]: (self.root / "models" / m["model"]).read_bytes() for m in self.models}
        for identity, world in result["worlds"].items():
            self.assertEqual(identity, world["controller"] + "--" + world["condition"])
            self.assertEqual(hashlib.sha256(raw[identity].encode()).hexdigest(), world["trace_sha256"])
            rows = [json.loads(line) for line in raw[identity].splitlines()]
            analysis = trace.analyze_trace(rows, models[world["controller"]], world["result"])
            self.assertEqual(analysis, world["analysis"])
            expected = control["evaluations"][world["controller"] + "-as-current"]["worlds"][world["condition"]]
            self.assertEqual(world["result"], expected["result"])
            self.assertEqual(summary["worlds"][identity], {
                **{f: world[f] for f in ("controller", "condition", "trace_sha256")},
                "run_hash": world["result"]["run_hash"], "world_hash": world["result"]["world_hash"],
                "analysis": {f: analysis[f] for f in ("queries", "samples", "histograms")}})
        self.assertEqual(trace.summarize(result["worlds"], self.models), result["summary"])
        for field in ("schema_version", "rule", "models", "conditions", "probes", "summary"):
            self.assertEqual(summary[field], result[field])
        totals = {kind: {role: sum(w["analysis"][kind][role] for w in result["worlds"].values())
                         for role in trace.ROLES} for kind in ("queries", "samples")}
        self.assertEqual(summary["primary_worlds"], len(identities))
        self.assertEqual(summary["totals"], totals)
        self.assertEqual(summary["native_probe_results"], sum(totals["samples"].values()) * len(trace.PROBES))
        self.assertEqual(summary["protocol_sha256"], trace.digest(trace.ROOT / trace.PROTOCOL))
        for name, expected in trace.INPUTS.items():
            self.assertEqual(summary["inputs"][name], expected)
            self.assertEqual(trace.digest(self.inputs / name), expected)
        self.assertTrue(summary["repeat_verified"])
        self.assertTrue(summary["independent_frozen_verification"])
        self.assertEqual(summary["manifest_sha256"],
                         "6d3e34ab41575df3f91e555a8334de33d3e26d793bad047716193a5a538dd258")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", required=True, type=Path)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *rest])
