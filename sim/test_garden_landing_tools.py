#!/usr/bin/env python3
"""File/CLI boundaries, legacy equivalence, nonzero models, and frozen galleries."""

import argparse
import copy
import json
from pathlib import Path
import resource
import signal
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_evaluate as evaluation
from garden_experiments import trial_seeds
from test_garden_gallery import decode_png
from test_garden_landing_neural import crc_repair, decode

BUILD = None


def run(command, valid=True, **kwargs):
    result = subprocess.run([str(v) for v in command], capture_output=True, timeout=120, **kwargs)
    if (result.returncode == 0) != valid:
        raise AssertionError(f"{command}: {result.returncode}\n{result.stderr.decode(errors='replace')}")
    if not valid:
        assert result.stdout == b""
    return result.stdout


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="garden-landing-tools-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.cli = BUILD / "toy-factory-garden-landing"
        self.replayer = BUILD / "toy-factory-garden-replay"

    def native(self, *args, **kwargs):
        return run([self.cli, *args], **kwargs)

    def reference(self, mode="history", name="model", omit=False):
        path = self.root / (name + ".tgl")
        result = json.loads(self.native("reference", path, "--mode", mode,
                                      *(["--omit-dead-only"] if omit else [])))
        return path, result["model"]

    def replay(self, model, scenario="rainfed", climate="seasonal", seed="0x1234", ticks=3840, **kwargs):
        return json.loads(self.native("replay", model, scenario, seed, "--ticks", str(ticks),
                                      "--climate", climate, **kwargs))

    def test_explicit_import_and_inspect(self):
        self.native("--help")
        legacy = self.root / "old.tgm"
        legacy.write_bytes(run([BUILD / "toy-factory-garden-landing-codec-probe", "reference"]))
        for mode in ("off", "current", "history"):
            for omit in (False, True):
                path, metadata = self.reference(mode, mode + str(omit), omit)
                self.assertEqual(json.loads(self.native("inspect", path))["model"], metadata)
                self.assertEqual(metadata["mode"], mode)
                self.assertEqual(metadata["omit_dead_only"], omit)
                self.assertEqual(metadata["common_nonzero_weights"], 0)
                self.assertEqual(metadata["candidate_nonzero_weights"], 0)
                data = path.read_bytes()
                self.assertEqual(data[16:1236], legacy.read_bytes())
                decode(data)
                imported = self.root / (path.stem + "-import.tgl")
                self.native("import", legacy, imported, "--mode", mode,
                            *(["--omit-dead-only"] if omit else []))
                self.assertEqual(imported.read_bytes(), data)
                self.native("reference", path, "--mode", mode, valid=False)
                self.assertEqual(path.read_bytes(), data)
        self.native("inspect", legacy, valid=False)
        self.native("import", path, self.root / "wrong.tgl", "--mode", "history", valid=False)
        self.assertFalse((self.root / "wrong.tgl").exists())

    def test_strict_arguments_and_bad_files(self):
        model, _ = self.reference()
        command = ["replay", model, "rainfed", "123", "--ticks", "0", "--climate", "steady"]
        for value in ("", "0", "-1", "+1", " 1", "4294967296", "1x"):
            invalid = command.copy()
            invalid[3] = value
            self.native(*invalid, valid=False)
        for value in ("", "-1", "1228801", "4294967296", "1x"):
            invalid = command.copy()
            invalid[5] = value
            self.native(*invalid, valid=False)
        for suffix in (["--ticks", "0"], ["--climate", "steady"], ["--mode", "off"],
                       ["--framebuffer", ""], ["--framebuffer"], ["--unknown", "x"]):
            self.native(*command, *suffix, valid=False)
        self.native(*command[:-2], valid=False)
        self.native(*command[:2], "crowded", *command[3:], valid=False)
        for suffix in ([], ["--mode", "bad"], ["--mode", "off", "--mode", "history"],
                       ["--mode", "off", "--omit-dead-only", "--omit-dead-only"]):
            self.native("reference", self.root / "invalid.tgl", *suffix, valid=False)
        self.assertFalse((self.root / "invalid.tgl").exists())
        data = model.read_bytes()
        malformed = [b"", data[:-1], data + b"x", data[:-1] + bytes([data[-1] ^ 1]),
                     crc_repair(data[:1237] + b"\x03" + data[1238:])]
        for broken in malformed:
            path = self.root / "bad.tgl"
            path.write_bytes(broken)
            self.native("inspect", path, valid=False)
            self.native("replay", path, *command[2:], "--framebuffer", self.root / "bad.raw", valid=False)
            self.assertFalse((self.root / "bad.raw").exists())
        self.native("inspect", self.root / "absent", valid=False)
        self.native("inspect", self.root, valid=False)
        self.assertEqual(self.replay(model, seed="0xffffffff", ticks=983040)["tick"], 983040)

    def test_followup_horizon_and_trace_boundaries(self):
        model, _ = self.reference()
        stop = 320 * 3840
        trace = self.root / "adult.jsonl"
        command = ["replay", model, "rainfed", "0xffffffff", "--ticks", str(stop),
                   "--climate", "seasonal", "--ledger", "--adult-trace", trace,
                   "--adult-start", str(stop), "--adult-stop", str(stop)]
        for option, bad in (("--ticks", stop + 1), ("--adult-start", stop + 15),
                            ("--adult-stop", stop + 15), ("--adult-start", stop - 1)):
            invalid = command.copy()
            invalid[invalid.index(option) + 1] = str(bad)
            self.native(*invalid, valid=False)
            self.assertFalse(trace.exists())
        result = json.loads(self.native(*command))
        self.assertEqual(result["tick"], stop)
        rows = [json.loads(line) for line in trace.read_text().splitlines()]
        self.assertEqual(rows[0], dict(schema="landing-adult-resources-v1", start=stop, stop=stop))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1]["tick"], stop)
        self.assertEqual(rows[2], dict(complete=True, tick=stop))
        plain = json.loads(self.native(*command[:command.index("--adult-trace")]))
        self.assertEqual(result, plain)
        # The general evaluator/training contract is deliberately not widened.
        run([BUILD / "toy-factory-garden-eval", "--trials", "1", "--ticks", "983041"], valid=False)

    def test_explicit_ablation_preserves_weights_and_only_removes_inputs(self):
        for mode in ("off", "current", "history"):
            base, _ = self.reference(mode, mode, omit=True)
            source = self.root / (mode + "-mutated.tgl")
            self.native("mutate", base, source, 0x6d697833, 32, 16)
            before = source.read_bytes()
            for target in ("off", "current", "history", "bogus", ""):
                output = self.root / (mode + "-as-" + target + ".tgl")
                allowed = (mode, target) in (("current", "off"), ("history", "off"), ("history", "current"))
                result = self.native("ablate", source, output, target, valid=allowed)
                if not allowed:
                    self.assertFalse(output.exists())
                    continue
                receipt = json.loads(result)
                expected = bytearray(before)
                expected[1237] = ("off", "current", "history").index(target)
                self.assertEqual(output.read_bytes(), crc_repair(bytes(expected)))
                self.assertEqual(receipt["source_mode"], mode)
                self.assertEqual(receipt["model"], json.loads(self.native("inspect", output))["model"])
                self.assertTrue(receipt["model"]["omit_dead_only"])
                decode(output.read_bytes())
                self.native("ablate", source, output, target, valid=False)
                self.assertEqual(output.read_bytes(), crc_repair(bytes(expected)))
                if target == "off":
                    legacy = self.root / (mode + ".tgm")
                    legacy.write_bytes(before[16:1236])
                    imported = self.root / (mode + "-legacy.tgl")
                    self.native("import", legacy, imported, "--mode", "off", "--omit-dead-only")
                    def biological(result):
                        return {k: v for k, v in result.items() if k not in ("model", "run_hash")}
                    self.assertEqual(biological(self.replay(output)), biological(self.replay(imported)))
            self.assertEqual(source.read_bytes(), before)
            for suffix in ([], ["off", "extra"]):
                self.native("ablate", source, self.root / "bad.tgl", *suffix, valid=False)
                self.assertFalse((self.root / "bad.tgl").exists())
            self.native("ablate", source, source, "off", valid=False)
            link = self.root / (mode + "-link.tgl")
            link.symlink_to(source)
            self.native("ablate", source, link, "off", valid=False)
            self.assertEqual(source.read_bytes(), before)
        corrupt = self.root / "corrupt.tgl"
        corrupt.write_bytes(before[:-1])
        self.native("ablate", corrupt, self.root / "bad.tgl", "off", valid=False)
        self.assertFalse((self.root / "bad.tgl").exists())

    def test_write_failures_do_not_clobber(self):
        model, _ = self.reference()
        link = self.root / "link.tgl"
        link.symlink_to(model)
        before = model.read_bytes()
        self.native("reference", link, "--mode", "off", valid=False)
        self.assertEqual(model.read_bytes(), before)
        self.native("reference", self.root / "absent" / "model.tgl", "--mode", "off", valid=False)

        def small_files():
            signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
            resource.setrlimit(resource.RLIMIT_FSIZE, (1024, 1024))

        partial = self.root / "partial.tgl"
        self.native("reference", partial, "--mode", "off", valid=False, preexec_fn=small_files)
        self.assertFalse(partial.exists())
        raw = self.root / "partial.raw"
        command = ["replay", model, "rainfed", "123", "--ticks", "0", "--climate", "steady", "--framebuffer", raw]
        self.native(*command, valid=False, preexec_fn=small_files)
        self.assertFalse(raw.exists())
        raw.write_bytes(b"keep me")
        self.native(*command, valid=False)
        self.assertEqual(raw.read_bytes(), b"keep me")

    def test_zero_extra_legacy_states_and_pixels(self):
        models = [self.reference(mode, mode)[0] for mode in ("off", "current", "history")]
        for scenario in evaluation.SCENARIOS:
            for climate in evaluation.CLIMATES:
                for tick in (0, 15, 3840, 32 * 3840):
                    raw = self.root / "legacy.raw"
                    old = json.loads(run([self.replayer, "-", scenario, "neural-reference", "0x1234",
                                          "--ticks", tick, "--climate", climate, "--framebuffer", raw]))
                    data = raw.read_bytes()
                    raw.unlink()
                    hashes = []
                    for model in models:
                        command = ["replay", model, scenario, "0x1234", "--ticks", str(tick), "--climate", climate]
                        result = json.loads(self.native(*command, "--framebuffer", raw))
                        self.assertEqual(result["world_hash"], old["hash"])
                        self.assertEqual(raw.read_bytes(), data)
                        self.assertEqual({**result, "framebuffer_crc32": None}, json.loads(self.native(*command)))
                        for key in ("living", "descendants", "plant_slots", "nodes", "seed_bank", "births", "deaths",
                                    "rain_deposited", "rain_runoff", "moisture", "climate"):
                            self.assertEqual(result[key], old[key])
                        hashes.append(result["run_hash"])
                        raw.unlink()
                    self.assertEqual(len(set(hashes)), 3)  # Fixed mask is part of run identity.

    def test_saved_nonzero_model_is_used(self):
        path, _ = self.reference()
        file = bytearray(path.read_bytes())
        file[42:45] = bytes(3)  # all shifts zero
        file[48:1236] = bytes(1188)  # weights/biases, preserve legacy metadata
        for offset, value in ((756, 1), (992, 128)):
            struct.pack_into("<i", file, offset, value)
        # Current landing light influences arbitration, recurrent memory, and
        # candidate ranking. Unlike wet-only probes it is active at dry starts.
        file[816] = file[864] = file[1228] = file[1243] = file[1387] = 1
        sensor = self.root / "sensor.tgl"
        sensor.write_bytes(crc_repair(file, nested=True))
        decode(sensor.read_bytes())
        model = json.loads(self.native("inspect", sensor))["model"]
        self.assertEqual((model["common_nonzero_weights"], model["candidate_nonzero_weights"]), (1, 1))
        result = self.replay(sensor)
        self.assertEqual(result, self.replay(sensor))
        self.assertEqual(result["model"], model)
        file[1240:] = bytes(208)
        zero = self.root / "zero.tgl"
        zero.write_bytes(crc_repair(file, nested=True))
        # Compare intermediate states too: private memories disappear at death,
        # so equal late hashes need not imply equal earlier decisions/memories.
        self.assertTrue(any(self.replay(sensor, ticks=t)["world_hash"] !=
                            self.replay(zero, ticks=t)["world_hash"] for t in (15, 120, 600, 3840)))

    def test_lifetimes_match_existing_evaluator(self):
        model, _ = self.reference()
        report = json.loads(run([BUILD / "toy-factory-garden-eval", "--trials", "1", "--ticks", 32 * 3840,
                                 "--seed", "0x1234", "--rainfed", "--climate", "seasonal"]))
        seed = "0x" + trial_seeds(0x1234, 1)[0]
        for scenario in report["scenarios"]:
            old = next(p for p in scenario["policies"] if p["name"] == "neural-reference")["trials"][0]
            result = self.replay(model, scenario["name"], seed=seed, ticks=32 * 3840)
            self.assertEqual(result["descendant_live_ticks"], old["descendant_plant_ticks"])
            for key, value in result["lifetimes"].items():
                if key not in ("offspring_deaths", "founder_deaths"):
                    self.assertEqual(value, old["lifetimes"][key], key)
            self.assertEqual(result["lifetimes"]["offspring_deaths"], old["lifetimes"]["offspring_mortality"]["deaths"])
            self.assertEqual(result["lifetimes"]["founder_deaths"], old["lifetimes"]["founder_mortality"]["deaths"])

    def test_frozen_bundle_and_tampering(self):
        off, _ = self.reference("off", "off")
        history, _ = self.reference("history", "history")
        output = self.root / "bundle"
        collector = evaluation.ROOT / "sim/garden_landing_evaluate.py"
        command = [sys.executable, collector, "--build", BUILD, "--out", output, "--days", "2",
                   "--model", f"off={off}", "--model", f"history={history}", "--seed", "123",
                   "--seed", "456", "--scenario", "rainfed", "--jobs", "2"]
        run(command)
        manifest = json.loads((output / "manifest.json").read_text())
        self.assertTrue(manifest["repeat_verified"])
        self.assertEqual(manifest["settings"]["checkpoints"], [1, 2])
        results = json.loads((output / "results.json").read_text())
        self.assertEqual(len(results["cases"]), 4)
        frames = [f for c in results["cases"] for f in c["frames"]]
        for frame in frames:
            width, height, rgb = decode_png(output / frame["png"])
            self.assertEqual((width, height), (240, 240))
            self.assertEqual(rgb, evaluation.rgb565be_to_rgb888((output / frame["framebuffer"]).read_bytes()))
        run([sys.executable, output / "sim/garden_landing_evaluate.py", "--verify", output])
        for option in (["--days", "32"], ["--build", BUILD], ["--jobs", "2"], ["--seed", "123"]):
            run([sys.executable, collector, "--verify", output, *option], valid=False)
        run(command, valid=False)
        self.assertFalse((output / "FAILED.txt").exists())
        original = (output / frames[0]["framebuffer"]).read_bytes()
        (output / frames[0]["framebuffer"]).write_bytes(b"bad")
        with self.assertRaisesRegex(RuntimeError, "artifact changed"):
            evaluation.verify(output, 30)
        (output / frames[0]["framebuffer"]).write_bytes(original)
        changed = copy.deepcopy(results)
        changed["cases"][0]["frames"][0]["result"]["run_hash"] = "deadbeef"
        (output / "results.json").write_text(json.dumps(changed))
        manifest["artifacts"]["results.json"] = evaluation.digest(output / "results.json")
        (output / "manifest.json").write_text(json.dumps(manifest))
        with self.assertRaisesRegex(RuntimeError, "nonrepeatable"):
            evaluation.verify(output, 30)

    def test_collector_bounds_and_failure_marker(self):
        model, _ = self.reference()
        args = argparse.Namespace(out=self.root / "failed", model=[f"reference={model}"],
            seed=[123], climate=["steady"], scenario=["rainfed"], days=1, checkpoint_day=None,
            build=BUILD, jobs=1, timeout=30)
        with patch.object(evaluation, "capture_case", side_effect=RuntimeError("injected replay failure")):
            with self.assertRaisesRegex(RuntimeError, "injected replay failure"):
                evaluation.collect(args)
        self.assertTrue((args.out / "FAILED.txt").is_file())
        self.assertFalse((args.out / "manifest.json").exists())
        with self.assertRaisesRegex(RuntimeError, "output exists"):
            evaluation.collect(args)
        settings = dict(labels=["a"], seeds=["00000001"], climates=["steady"],
                        scenarios=["rainfed"], days=1, checkpoints=[0, 1])
        evaluation.validate_settings(settings)
        for values in ({"labels": ["../escape"]}, {"labels": ["a", "a"]}, {"seeds": ["00000000"]},
                       {"seeds": ["100000000"]}, {"days": 257}, {"checkpoints": [0]},
                       {"climates": ["unknown"]}, {"checkpoints": [0, 0, 1]}):
            with self.assertRaises(RuntimeError):
                evaluation.validate_settings({**settings, **values})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", required=True, type=Path)
    args, remaining = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[sys.argv[0], *remaining])
