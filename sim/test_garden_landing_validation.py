#!/usr/bin/env python3
"""Fixed finalists, canonical input ablation, panel boundaries and failure checks."""

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

import garden_landing_validation as validation
from garden_experiments import trial_seeds
from test_garden_gallery import decode_png
from test_garden_landing_neural import decode

BUILD = None


class LandingValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="landing-validation-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.inputs = validation.ROOT / "benchmarks/garden-seasons"
        self.cli = BUILD / "toy-factory-garden-landing"

    def test_fixed_plan_has_every_finalist_and_only_removes_inputs(self):
        plan, cases = validation.variant_plan(), validation.conditions()
        self.assertEqual(len(plan), 19)
        self.assertEqual(len({m["id"] for m in plan}), 19)
        self.assertEqual(len(cases), 16)
        self.assertEqual(len({c["id"] for c in cases}), 16)
        self.assertEqual(trial_seeds(0x6c616e64, 4), list(validation.SEEDS))
        self.assertFalse(set(validation.SEEDS) & {validation.training.TRAIN_SEED, validation.training.REVIEW_SEED})
        self.assertEqual(sum(m["trained_mode"] == m["mode"] for m in plan), 10)
        for model in plan:
            self.assertLessEqual(validation.training.MODES.index(model["mode"]),
                                 validation.training.MODES.index(model["trained_mode"]))
        slices = validation.slices()
        self.assertEqual(len(slices), 9)
        for field in ("seed", "scenario", "climate"):
            ids = [i for k, v in slices.items() if k.startswith(field + "/") for i in v]
            self.assertEqual(sorted(ids), sorted(slices["all"]))

    def test_pinned_finalists_and_derived_bytes_repeat(self):
        first = validation.prepare_models(self.cli, self.inputs, self.root / "first")
        second = validation.prepare_models(self.cli, self.inputs, self.root / "second")
        self.assertEqual(first, second)
        archive = validation.load_inputs(self.inputs)
        for item in first:
            data = (self.root / "first" / item["model"]).read_bytes()
            decode(data)
            self.assertEqual(data, (self.root / "second" / item["model"]).read_bytes())
            self.assertEqual(item["sha256"], validation.digest(self.root / "first" / item["model"]))
            if item["id"] != validation.BASELINE:
                old = archive[item["source"]]
                self.assertEqual(data[:12], old[:12])
                self.assertEqual(data[16:1237], old[16:1237])
                self.assertEqual(data[1238:], old[1238:])
                self.assertEqual(data[1237], validation.training.MODES.index(item["mode"]))
        with self.assertRaises(FileExistsError):
            validation.prepare_models(self.cli, self.inputs, self.root / "first")

    def test_bad_inputs_rejected_before_output(self):
        for jobs in (0, 9):
            with self.assertRaises(RuntimeError):
                validation.collect(BUILD, self.inputs, self.root / "out", jobs)
        with patch.object(validation, "INPUTS", {"landing-training-summary.json": "bad"}):
            with self.assertRaisesRegex(RuntimeError, "wrong frozen pilot input"):
                validation.collect(BUILD, self.inputs, self.root / "out", 2)
        self.assertFalse((self.root / "out").exists())
        (self.root / "out").mkdir()
        with self.assertRaisesRegex(RuntimeError, "fresh"):
            validation.collect(BUILD, self.inputs, self.root / "out", 2)

    def test_full_gallery_is_prespecified_not_score_selected(self):
        models = [{**m, "model": f"models/{m['id']}.tgl"} for m in validation.variant_plan()]
        frames = validation.frame_plan(models)
        self.assertEqual(len(frames), 76)
        self.assertEqual(len({f["id"] for f in frames}), 76)
        self.assertEqual({f["seed"] for f in frames}, {validation.SEEDS[0]})
        self.assertEqual({f["climate"] for f in frames}, {"seasonal"})
        for model in models:
            self.assertEqual([(f["scenario"], f["day"]) for f in frames if f["variant"] == model["id"]],
                             [("rainfed", 16), ("rainfed", 192), ("rainfed-crowded", 16), ("rainfed-crowded", 192)])

    def test_pairs_are_same_weight_ablations_or_explicit_training_controls(self):
        # Reuse saved histories as synthetic identical outcomes in every arm.
        saved = json.loads(gzip.decompress((self.inputs / "landing-training-histories.json.gz").read_bytes()))
        worlds = next(iter(saved["searches"].values()))["generations"][-1]["review"]["worlds"]
        history = next(iter(worlds.values()))["history"]
        evaluations = {m["id"]: {"worlds": {c["id"]: {"history": history}
                       for c in validation.conditions()}} for m in validation.variant_plan()}
        pairs = validation.comparisons(evaluations)
        self.assertEqual(len(pairs), 24)  # 9 baseline + 6 training-arm + 9 ablation.
        ablations = [p for p in pairs if p["kind"] == "input-ablation"]
        self.assertEqual(len(ablations), 9)
        for pair in pairs:
            if pair["kind"] == "input-ablation":
                self.assertEqual(pair["control"].split("-as-")[0], pair["candidate"].split("-as-")[0])
            for subset in pair["slices"].values():
                self.assertEqual(subset["comparison"], 0)
                self.assertEqual(subset["paired_counts"], {"wins": 0, "ties": len(subset["pairs"]), "losses": 0})
        broken = copy.deepcopy(evaluations)
        del broken[validation.BASELINE]["worlds"][validation.conditions()[0]["id"]]
        with self.assertRaises((KeyError, RuntimeError)):
            validation.comparisons(broken)

    def test_source_change_and_failed_bundle_cannot_complete(self):
        output = self.root / "failed"
        with patch.object(validation, "snapshot_sources"), \
             patch.object(validation, "source_files", side_effect=[
                 {validation.PROTOCOL: validation.digest(validation.ROOT / validation.PROTOCOL)}, {"changed": "sha"}]), \
             patch.object(validation, "run_panel", return_value={"models": []}) as run:
            with self.assertRaisesRegex(RuntimeError, "sources changed"):
                validation.collect(BUILD, self.inputs, output, 2)
            self.assertEqual(run.call_count, 2)
        self.assertTrue((output / "FAILED.txt").exists())
        self.assertFalse((output / "manifest.json").exists())
        with patch.object(validation, "run_panel") as run:
            with self.assertRaisesRegex(RuntimeError, "incomplete"):
                validation.verify(output)
            run.assert_not_called()

    def test_reference_evaluation_has_complete_cases_and_worker_independence(self):
        meta = validation.training.native(self.cli, self.root, "reference", "reference.tgl", "--mode", "off")["model"]
        model = {"model": "reference.tgl", "metadata": meta}
        # Old development conditions, not new finalist results during unit tests.
        with patch.object(validation, "conditions", return_value=validation.training.conditions("a9c30c1f")):
            a = validation.evaluate(self.cli, self.root, model, 1)
            b = validation.evaluate(self.cli, self.root, model, 2)
        self.assertEqual(a, b)
        self.assertEqual(a["aggregate"]["world_count"], 4)
        for world in a["worlds"].values():
            self.assertEqual(world["result"]["rules"], 0)
            self.assertEqual(len(world["history"]["blocks"]), 4)

    def test_retained_panel_models_scores_and_every_gallery_tile(self):
        def load(name):
            return json.loads(gzip.decompress((self.inputs / name).read_bytes()))

        result = load("landing-validation-results.json.gz")
        archive = load("landing-validation-models.json.gz")
        gallery = load("landing-validation-gallery.json.gz")
        summary = json.loads((self.inputs / "landing-validation-summary.json").read_text())
        source = validation.load_inputs(self.inputs)
        self.assertEqual(result["rule"], validation.RULE)
        self.assertEqual(result["objective"], validation.training.individual.RULE)
        self.assertEqual(result["conditions"], validation.conditions())
        self.assertEqual([{k: m[k] for k in validation.variant_plan()[0]} for m in result["models"]],
                         validation.variant_plan())
        self.assertEqual(set(result["evaluations"]), {m["id"] for m in result["models"]})
        self.assertEqual(set(archive), {m["model"] for m in result["models"]} | {"initial.tgm"})
        self.assertEqual(bytes.fromhex(archive["initial.tgm"]), source["initial.tgm"])
        self.assertEqual(summary["model_variants"], 19)
        self.assertEqual(summary["distinct_model_files"], 18)
        self.assertEqual(summary["primary_worlds"], 304)
        self.assertEqual(summary["frames"], 76)
        self.assertEqual(summary["conditions"], result["conditions"])
        self.assertEqual(len(summary["models"]), len(result["models"]))
        fields = ("key", "world_count", "terminal_tier_counts", "zero_world_periods",
                  "zero_minimum_worlds", "sorted_world_minima", "period_sums")
        for model, retained in zip(result["models"], summary["models"], strict=True):
            self.assertEqual({k: retained[k] for k in model}, model)
            data = bytes.fromhex(archive[model["model"]])
            decode(data)
            self.assertEqual(hashlib.sha256(data).hexdigest(), model["sha256"])
            if model["id"] != validation.BASELINE:
                self.assertEqual(data, validation.ablated_bytes(source[model["source"]], model["mode"]))
            path = self.root / (model["id"] + ".tgl")
            path.write_bytes(data)
            self.assertEqual(validation.training.native(self.cli, self.root, "inspect", path)["model"],
                             model["metadata"])
            evaluated = result["evaluations"][model["id"]]
            self.assertEqual(set(evaluated["worlds"]), {c["id"] for c in validation.conditions()})
            self.assertEqual(set(retained["worlds"]), set(evaluated["worlds"]))
            for case in validation.conditions():
                world = evaluated["worlds"][case["id"]]
                self.assertEqual(world["history"], validation.training.score_world(world["result"], case, model["metadata"]))
                expected = {k: world["result"][k] for k in
                            ("world_hash", "run_hash", "living", "descendants", "seed_bank", "births", "deaths")}
                expected.update(evaluated["aggregate"]["worlds"][case["id"]])
                self.assertEqual(retained["worlds"][case["id"]], expected)
            aggregate = validation.training.individual.aggregate(
                {k: w["history"] for k, w in evaluated["worlds"].items()}, list(evaluated["worlds"]))
            self.assertEqual(evaluated["aggregate"], aggregate)
            self.assertEqual(retained["aggregate"], {k: aggregate[k] for k in fields})
        self.assertEqual(result["comparisons"], validation.comparisons(result["evaluations"]))
        self.assertEqual(len(summary["comparisons"]), len(result["comparisons"]))
        for pair, compact in zip(result["comparisons"], summary["comparisons"], strict=True):
            for key in ("kind", "control", "candidate"):
                self.assertEqual(pair[key], compact[key])
            self.assertEqual(set(compact["slices"]), set(validation.slices()))
            for name, subset in compact["slices"].items():
                for key in ("comparison", "paired_counts", "minimum_delta"):
                    self.assertEqual(subset[key], pair["slices"][name][key])
                for side in ("control", "candidate"):
                    self.assertEqual(subset[side], {k: pair["slices"][name][side][k] for k in fields})

        # Identical canonical models are not independent variants or new evidence.
        self.assertEqual(result["evaluations"]["s6d697835-off-as-off"],
                         result["evaluations"]["s6d697835-history-as-off"])
        plan = validation.frame_plan(result["models"])
        self.assertEqual([{k: f[k] for k in plan[0]} for f in gallery["frames"]], plan)
        self.assertEqual(set(summary["galleries"]), {m["controller"] for m in result["models"]})
        models = {m["id"]: m for m in result["models"]}
        for controller, sheet in summary["galleries"].items():
            selected = [f for f in gallery["frames"] if f["controller"] == controller]
            self.assertEqual(sheet["rows"], [[f["id"] for f in selected[i:i + 2]] for i in range(0, len(selected), 2)])
            path = self.inputs / sheet["path"]
            self.assertEqual(validation.digest(path), sheet["sha256"])
            width, height, rgb = decode_png(path)
            self.assertEqual((width, height), (sheet["width"], sheet["height"]))
            self.assertEqual((width, height, sheet["gap"]), (504, 8 + len(sheet["rows"]) * 248, 8))
            for index, frame in enumerate(selected):
                x = 8 + (index % 2) * 248
                y = 8 + (index // 2) * 248
                tile = b"".join(rgb[((y + row) * width + x) * 3:((y + row) * width + x + 240) * 3]
                                for row in range(240))
                raw = bytearray(240 * 240 * 2)
                for pixel in range(240 * 240):
                    r, g, b = tile[pixel * 3:pixel * 3 + 3]
                    struct.pack_into(">H", raw, pixel * 2, ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3))
                validation.training.replay.check_result(frame["result"], frame, frame["day"] * 3840,
                                                        models[frame["variant"]]["metadata"], 0, raw)
                if frame["day"] == 192:
                    case_id = f"{frame['scenario']}-{frame['climate']}-{frame['seed']}"
                    self.assertEqual({**frame["result"], "framebuffer_crc32": None},
                                     result["evaluations"][frame["variant"]]["worlds"][case_id]["result"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", required=True, type=Path)
    args, remaining = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *remaining])
