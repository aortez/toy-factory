#!/usr/bin/env python3
"""Explicit probe identities, packet controls, fixed panel and failure boundaries."""

import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_signals as signals
from test_garden_gallery import decode_png
from test_garden_landing_neural import decode
from test_garden_landing_tools import run

BUILD = None


class SignalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="landing-signals-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.inputs = signals.ROOT / "benchmarks/garden-seasons"
        self.cli = BUILD / "toy-factory-garden-landing"

    def native(self, *args, **kwargs):
        raw = run([self.cli, *args], **kwargs)
        return json.loads(raw) if raw else None

    def reference(self, mode="current", omit=False):
        path = self.root / f"reference-{mode}-{omit}.tgl"
        self.native("reference", path, "--mode", mode, *(["--omit-dead-only"] if omit else []))
        return path

    def command(self, model, occupancy="live", resources="live", ticks=0):
        return ["probe-replay", model, "rainfed", "0x1234", "--ticks", ticks,
                "--climate", "seasonal", "--ledger", "--occupancy", occupancy, "--resources", resources]

    def test_explicit_config_and_independent_identity_oracle(self):
        path = self.reference()
        data = path.read_bytes()
        plain = self.native("replay", path, "rainfed", "0x1234", "--ticks", 0, "--climate", "seasonal", "--ledger")
        hashes = []
        for o, occupancy in enumerate(("live", "neutral", "occupied", "open")):
            for r, resources in enumerate(("live", "mid", "low", "high")):
                result = self.native(*self.command(path, occupancy, resources))
                self.assertEqual(result["model"], plain["model"])
                self.assertEqual(result["world_hash"], plain["world_hash"])
                self.assertEqual(result["kind"], "landing-signal-replay")
                self.assertEqual(result["signal_probe"], {"version": 1, "occupancy": occupancy, "resources": resources})
                h = 2166136261
                for byte in b"GSP1" + struct.pack("<I", int(plain["run_hash"], 16)) + bytes((1, o, r, 0)):
                    h = ((h ^ byte) * 16777619) & 0xffffffff
                self.assertEqual(result["run_hash"], f"{h:08x}")
                hashes.append(h)
        self.assertEqual(len(set(hashes)), 16)
        self.assertEqual(path.read_bytes(), data)

    def test_strict_cli_and_unsupported_masks_have_no_output_files(self):
        model = self.reference()
        raw = self.root / "frame.raw"
        command = self.command(model)
        for invalid in (command[:-2], command[:-4], [*command, "--resources", "low"],
                        [*command, "--occupancy", "open"], self.command(model, "unknown"),
                        self.command(model, resources="unknown"),
                        self.command(model, ticks=512 * 3840 + 1)):
            self.native(*invalid, "--framebuffer", raw, valid=False)
            self.assertFalse(raw.exists())
        self.native("replay", *command[1:], valid=False)
        for mode, omit in (("off", False), ("history", False), ("current", True)):
            unsupported = self.reference(mode, omit)
            before = unsupported.read_bytes()
            self.native(*self.command(unsupported), "--framebuffer", raw, valid=False)
            self.assertFalse(raw.exists())
            self.assertEqual(unsupported.read_bytes(), before)
        corrupted = self.root / "corrupt.tgl"
        corrupted.write_bytes(model.read_bytes()[:-1])
        self.native(*self.command(corrupted), "--framebuffer", raw, valid=False)
        self.assertFalse(raw.exists())
        raw.write_bytes(b"retain existing file")
        self.native(*command, "--framebuffer", raw, valid=False)
        self.assertEqual(raw.read_bytes(), b"retain existing file")

    def test_nonzero_live_neutral_replays_and_captures_match_plain(self):
        models, _ = signals.prepare_models(self.cli, self.inputs, self.root / "models-root")
        for model in models:
            original = self.root / "models-root" / model["model"]
            before = original.read_bytes()
            off = self.root / (model["id"] + "-off.tgl")
            self.native("ablate", original, off, "off")
            for probe in (signals.PROBES[0], signals.PROBES[3]):
                control = original if probe["id"] == "live" else off
                for case in signals.training.conditions("a9c30c1f"):
                    if case["climate"] != "seasonal":
                        continue
                    raw = self.root / "probe.raw"
                    actual = signals.run_world(self.cli, self.root, original, case, probe, raw, 4 * 3840)
                    pixels = raw.read_bytes()
                    raw.unlink()
                    expected = signals.training.run_world(self.cli, self.root, control, case, 4 * 3840, raw)
                    self.assertEqual(pixels, raw.read_bytes())
                    raw.unlink()
                    self.assertEqual(signals.training.biological(signals.scoring_view(actual, probe)),
                                     signals.training.biological(expected))
                    repeated = signals.run_world(self.cli, self.root, original, case, probe, ticks=4 * 3840)
                    self.assertEqual(repeated, {**actual, "framebuffer_crc32": None})
            self.assertEqual(original.read_bytes(), before)

    def test_fixed_plan_and_unchanged_models(self):
        a, _ = signals.prepare_models(self.cli, self.inputs, self.root / "a")
        b, _ = signals.prepare_models(self.cli, self.inputs, self.root / "b")
        self.assertEqual(a, b)
        self.assertEqual(len(a), 3)
        self.assertEqual(len(signals.PROBES), 10)
        self.assertEqual(len({(p["occupancy"], p["resources"]) for p in signals.PROBES}), 10)
        self.assertEqual([m["champion"] for m in a], ["g1-c0", "g1-c2", "g1-c1"])
        self.assertEqual(len(a) * len(signals.PROBES) * len(signals.previous.conditions()), 480)
        frames = signals.frame_plan(a)
        self.assertEqual(len(frames), 60)
        self.assertEqual(len({f["id"] for f in frames}), 60)
        self.assertEqual({f["day"] for f in frames}, {192})
        self.assertEqual({f["seed"] for f in frames}, {signals.previous.SEEDS[0]})
        self.assertEqual({f["climate"] for f in frames}, {"seasonal"})
        for model in a:
            self.assertEqual((self.root / "a" / model["model"]).read_bytes(), (self.root / "b" / model["model"]).read_bytes())
        with self.assertRaises(FileExistsError):
            signals.prepare_models(self.cli, self.inputs, self.root / "a")

    def test_score_bridge_and_frozen_controls_fail_closed(self):
        _, old = signals.load_inputs(self.inputs)
        model = signals.model_plan()[0]
        metadata = next(m["metadata"] for m in old["models"] if m["id"] == model["id"] + "-as-current")
        for probe, mode in ((signals.PROBES[0], "current"), (signals.PROBES[3], "off")):
            value = copy.deepcopy(old["evaluations"][model["id"] + "-as-" + mode])
            for key, world in value["worlds"].items():
                world["result"].update(kind="landing-signal-replay", model=metadata,
                    signal_probe={"version": 1, "occupancy": probe["occupancy"], "resources": probe["resources"]})
                case = next(c for c in signals.previous.conditions() if c["id"] == key)
                self.assertEqual(world["history"], signals.training.score_world(
                    signals.scoring_view(world["result"], probe), case, metadata))
            signals.check_control(value, model, probe, old)
            first = next(iter(value["worlds"].values()))["result"]
            first["world_hash"] = "bad"
            with self.assertRaises(RuntimeError):
                signals.check_control(value, model, probe, old)
            first["signal_probe"]["version"] = 2
            with self.assertRaises(RuntimeError):
                signals.scoring_view(first, probe)

    def test_pair_direction_and_complete_slices(self):
        _, old = signals.load_inputs(self.inputs)
        models = signals.model_plan()
        evaluation = old["evaluations"][models[0]["id"] + "-as-current"]
        worlds = {m["id"] + "--" + p["id"]: evaluation for m in models for p in signals.PROBES}
        comparisons = signals.comparisons(worlds, models)
        self.assertEqual(len(comparisons), 27)
        for comparison in comparisons:
            self.assertTrue(comparison["control"].endswith("--live"))
            self.assertFalse(comparison["candidate"].endswith("--live"))
            self.assertEqual(set(comparison["slices"]), set(signals.previous.slices()))
            for subset in comparison["slices"].values():
                self.assertEqual(subset["comparison"], 0)
                self.assertEqual(subset["paired_counts"], {"wins": 0, "ties": len(subset["pairs"]), "losses": 0})

    def test_bad_input_source_change_and_failed_bundle(self):
        output = self.root / "failed"
        with patch.object(signals, "INPUTS", {"landing-training-summary.json": "bad"}):
            with self.assertRaisesRegex(RuntimeError, "wrong frozen signal input"):
                signals.collect(BUILD, self.inputs, output, 4)
        self.assertFalse(output.exists())
        with patch.object(signals, "snapshot_sources"), \
             patch.object(signals, "source_files", side_effect=[
                 {signals.PROTOCOL: signals.digest(signals.ROOT / signals.PROTOCOL)}, {"changed": "sha"}]), \
             patch.object(signals, "run_panel", return_value={"models": []}) as panel:
            with self.assertRaisesRegex(RuntimeError, "sources changed"):
                signals.collect(BUILD, self.inputs, output, 4)
            self.assertEqual(panel.call_count, 2)
        self.assertTrue((output / "FAILED.txt").exists())
        self.assertFalse((output / "manifest.json").exists())
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            signals.verify(output)
        with self.assertRaisesRegex(RuntimeError, "fresh"):
            signals.collect(BUILD, self.inputs, output, 4)

    def test_retained_models_all_scores_controls_and_every_gallery_tile(self):
        def load(name):
            return json.loads(gzip.decompress((self.inputs / name).read_bytes()))

        result = load("landing-signals-results.json.gz")
        archive = load("landing-signals-models.json.gz")
        gallery = load("landing-signals-gallery.json.gz")
        summary = json.loads((self.inputs / "landing-signals-summary.json").read_text())
        source, old = signals.load_inputs(self.inputs)
        self.assertEqual(result["rule"], signals.RULE)
        self.assertEqual(result["objective"], signals.training.individual.RULE)
        self.assertEqual(result["probes"], signals.PROBES)
        self.assertEqual(result["conditions"], signals.previous.conditions())
        plan = signals.model_plan()
        self.assertEqual([{k: m[k] for k in plan[0]} for m in result["models"]], plan)
        identities = [m["id"] + "--" + p["id"] for m in result["models"] for p in signals.PROBES]
        self.assertEqual(set(result["evaluations"]), set(identities))
        self.assertEqual(set(archive), {m["model"] for m in result["models"]})
        for field in ("rule", "objective", "models", "probes", "conditions"):
            self.assertEqual(summary[field], result[field])
        self.assertEqual([summary[k] for k in ("controllers", "probe_variants", "primary_worlds", "frames")],
                         [3, 30, 480, 60])
        self.assertEqual(summary["protocol_sha256"], signals.digest(signals.ROOT / signals.PROTOCOL))
        self.assertEqual({k: summary["inputs"][k] for k in signals.INPUTS}, signals.INPUTS)
        self.assertTrue(summary["repeat_verified"])
        self.assertTrue(summary["independent_frozen_verification"])
        self.assertEqual([v["id"] for v in summary["variants"]], identities)
        retained = {v["id"]: v for v in summary["variants"]}
        fields = ("key", "world_count", "terminal_tier_counts", "zero_world_periods",
                  "zero_minimum_worlds", "sorted_world_minima", "period_sums")
        for model in result["models"]:
            data = bytes.fromhex(archive[model["model"]])
            self.assertEqual(data, source[model["source"]])
            self.assertEqual(hashlib.sha256(data).hexdigest(), model["sha256"])
            decode(data)
            path = self.root / (model["id"] + ".tgl")
            path.write_bytes(data)
            self.assertEqual(self.native("inspect", path)["model"], model["metadata"])
            for probe in signals.PROBES:
                identity = model["id"] + "--" + probe["id"]
                evaluation = result["evaluations"][identity]
                compact = retained[identity]
                self.assertEqual(compact["controller"], model["id"])
                self.assertEqual(compact["probe"], probe)
                self.assertEqual(set(evaluation["worlds"]), {c["id"] for c in result["conditions"]})
                self.assertEqual(set(compact["worlds"]), set(evaluation["worlds"]))
                for case in result["conditions"]:
                    world = evaluation["worlds"][case["id"]]
                    self.assertEqual(world["history"], signals.training.score_world(
                        signals.scoring_view(world["result"], probe), case, model["metadata"]))
                    expected = {k: world["result"][k] for k in
                                ("world_hash", "run_hash", "living", "descendants", "seed_bank", "births", "deaths")}
                    expected.update(evaluation["aggregate"]["worlds"][case["id"]])
                    self.assertEqual(compact["worlds"][case["id"]], expected)
                aggregate = signals.training.individual.aggregate(
                    {k: w["history"] for k, w in evaluation["worlds"].items()},
                    [c["id"] for c in result["conditions"]])
                self.assertEqual(evaluation["aggregate"], aggregate)
                self.assertEqual(compact["aggregate"], {k: aggregate[k] for k in fields})
                signals.check_control(evaluation, model, probe, old)
        self.assertEqual(result["comparisons"], signals.comparisons(result["evaluations"], result["models"]))
        self.assertEqual(len(summary["comparisons"]), 27)
        for pair, compact in zip(result["comparisons"], summary["comparisons"], strict=True):
            for key in ("control", "candidate"):
                self.assertEqual(pair[key], compact[key])
            self.assertEqual(set(compact["slices"]), set(signals.previous.slices()))
            for name, subset in compact["slices"].items():
                for key in ("comparison", "paired_counts", "minimum_delta"):
                    self.assertEqual(subset[key], pair["slices"][name][key])
                for side in ("control", "candidate"):
                    self.assertEqual(subset[side], {k: pair["slices"][name][side][k] for k in fields})

        frames = signals.frame_plan(result["models"])
        self.assertEqual([{k: f[k] for k in frames[0]} for f in gallery["frames"]], frames)
        self.assertEqual(set(summary["galleries"]),
                         {m["id"] + f"-part-{part}" for m in result["models"] for part in (1, 2)})
        self.assertEqual(set(summary["galleries"]), set(gallery["sheets"]))
        models = {m["id"]: m for m in result["models"]}
        for name, sheet in summary["galleries"].items():
            controller, part = name.rsplit("-part-", 1)
            offset = (int(part) - 1) * 10
            selected = [f for f in gallery["frames"] if f["controller"] == controller][offset:offset + 10]
            self.assertEqual({k: sheet[k] for k in ("gap", "height", "width", "rows")},
                             gallery["sheets"][name]["metadata"])
            self.assertEqual(sheet["rows"], [[f["id"] for f in selected[i:i + 2]] for i in range(0, 10, 2)])
            path = self.inputs / sheet["path"]
            self.assertEqual(signals.digest(path), sheet["sha256"])
            width, height, rgb = decode_png(path)
            self.assertEqual((width, height, sheet["gap"]), (504, 1248, 8))
            for index, frame in enumerate(selected):
                x, y = 8 + (index % 2) * 248, 8 + (index // 2) * 248
                tile = b"".join(rgb[((y + row) * width + x) * 3:((y + row) * width + x + 240) * 3]
                                for row in range(240))
                raw = bytearray(240 * 240 * 2)
                for pixel in range(240 * 240):
                    r, g, b = tile[pixel * 3:pixel * 3 + 3]
                    struct.pack_into(">H", raw, pixel * 2, ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3))
                signals.training.replay.check_result(signals.scoring_view(frame["result"], frame["probe"]),
                    frame, signals.training.STOP, models[frame["controller"]]["metadata"], 0, raw)
                case_id = f"{frame['scenario']}-{frame['climate']}-{frame['seed']}"
                self.assertEqual({**frame["result"], "framebuffer_crc32": None},
                                 result["evaluations"][frame["variant"]]["worlds"][case_id]["result"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", required=True, type=Path)
    args, remaining = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *remaining])
