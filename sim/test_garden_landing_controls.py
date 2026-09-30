#!/usr/bin/env python3
"""Paired budgets, training-only selection, explicit profiles and failure guards."""

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

import garden_landing_controls as controls
from test_garden_gallery import decode_png
from test_garden_landing_tools import run

BUILD = None


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="landing-controls-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cli = BUILD / "toy-factory-garden-landing"
        self.inputs = controls.ROOT / "benchmarks/garden-seasons"

    def native(self, *args):
        return json.loads(run([self.cli, *args]))

    def test_fixed_plan_and_fresh_evaluation_seed_derivation(self):
        x, seeds = 0x6c766631, []
        for _ in range(4):
            x ^= (x << 13) & 0xffffffff
            x ^= x >> 17
            x ^= (x << 5) & 0xffffffff
            seeds.append(f"{x:08x}")
        self.assertEqual(seeds, list(controls.EVALUATION_SEEDS))
        self.assertFalse(set(seeds) & {controls.training.TRAIN_SEED, controls.training.REVIEW_SEED,
                                      *controls.signals.previous.SEEDS})
        self.assertEqual(controls.PROFILES[1], {"id": "fixed", "occupancy": "occupied", "resources": "low"})
        self.assertEqual(len(controls.training.SEARCH_SEEDS) * len(controls.PROFILES) *
                         (1 + controls.training.GENERATIONS * controls.training.CHILDREN), 42)
        self.assertEqual(len(controls.evaluation_conditions()), 16)
        self.assertEqual(len(controls.slices()), 9)
        self.assertEqual(len(set(controls.slices()["all"])), 16)

    def test_initial_profiles_match_plain_and_bad_identity_fails(self):
        models, old = controls.load_inputs(self.inputs)
        initial = self.root / "initial.tgm"
        initial.write_bytes(models["initial.tgm"])
        target = self.root / "initial.tgl"
        metadata = self.native("import", initial, target, "--mode", "current")["model"]
        cases = controls.training.conditions(controls.training.TRAIN_SEED)
        reference = old["searches"]["s6d697833-current"]["candidates"][0]["train"]
        for profile in controls.PROFILES:
            value = controls.evaluate(self.cli, self.root, target, cases, profile, 2, metadata)
            controls.equivalent_evaluation(value, reference, profile)
            self.assertEqual(value, controls.evaluate(self.cli, self.root, target, cases, profile, 1, metadata))
            bad = copy.deepcopy(value)
            next(iter(bad["worlds"].values()))["result"]["world_hash"] = "bad"
            with self.assertRaisesRegex(RuntimeError, "biological trajectory"):
                controls.equivalent_evaluation(bad, reference, profile)
            bad = copy.deepcopy(value)
            next(iter(bad["worlds"].values()))["result"]["signal_probe"]["resources"] = "mid"
            with self.assertRaisesRegex(RuntimeError, "signal intervention"):
                controls.equivalent_evaluation(bad, reference, profile)
        with self.assertRaisesRegex(RuntimeError, "worker count/profile"):
            controls.evaluate(self.cli, self.root, target, cases, controls.PROFILES[0], 0, metadata)
        self.assertEqual(target.read_bytes(), models["s6d697833-current/models/g0.tgl"])

    def test_nonzero_fixed_probe_pixels_and_headless_repeat(self):
        archive, _ = controls.load_inputs(self.inputs)
        target = self.root / "nonzero.tgl"
        data = archive["s6d697833-current/models/g1-c0.tgl"]
        target.write_bytes(data)
        for profile in controls.PROFILES:
            case = controls.training.conditions(controls.training.TRAIN_SEED)[1]
            raw = self.root / (profile["id"] + ".raw")
            captured = controls.signals.run_world(self.cli, self.root, target, case, profile, raw, 2 * 3840)
            headless = controls.signals.run_world(self.cli, self.root, target, case, profile, ticks=2 * 3840)
            self.assertEqual({**captured, "framebuffer_crc32": None}, headless)
            controls.training.replay.check_result(controls.signals.scoring_view(captured, profile), case,
                                                  2 * 3840, captured["model"], 0, raw.read_bytes())
        self.assertEqual(target.read_bytes(), data)

    def test_selection_ignores_review_and_capture(self):
        def native(binary, work, action, *args):
            if action == "import":
                _, target, _, mode = args
                data, extra = {"generation": 0, "child": 0}, {}
            else:
                source, target, rng, base, extension = args
                parent = json.loads((work / source).read_text())
                data = {"generation": parent["generation"] + 1, "child": int(target[-5])}
                extra = {"rng_before": rng, "rng_after": rng + 1,
                         "legacy_mutations": base, "landing_mutations": extension}
            (work / target).write_text(json.dumps(data))
            return {**extra, "model": {"mode": "current", "legacy_payload_crc32": "01b9d94a",
                    "omit_dead_only": False, "common_nonzero_weights": 0, "candidate_nonzero_weights": 0}}

        def evaluate(binary, work, model, cases, profile, jobs, metadata):
            data = json.loads((work / model).read_text())
            preferred = 1 if cases[0]["seed"] == controls.training.TRAIN_SEED else 2
            value = data["generation"] * 10 + int(data["generation"] > 0 and data["child"] == preferred)
            return {"aggregate": {"key": [1, 4, value, value]}, "worlds": {}}

        with patch.object(controls.training, "native", side_effect=native), \
             patch.object(controls, "evaluate", side_effect=evaluate), \
             patch.object(controls, "capture", return_value=[]) as capture, \
             patch.object(controls.training, "check_gallery"), \
             patch.object(controls, "contact_sheet", return_value={}):
            a, gallery = controls.search_one(Path("cli"), Path("legacy"), self.root / "a", 123,
                                             controls.PROFILES[1], 2, True)
            b, absent = controls.search_one(Path("cli"), Path("legacy"), self.root / "b", 123,
                                            controls.PROFILES[1], 1, False)
        self.assertEqual(a, b)
        self.assertIsNone(absent)
        self.assertEqual(capture.call_count, 3)
        self.assertEqual([g["champion"] for g in a["generations"]], ["g0", "g1-c1", "g2-c1"])
        self.assertEqual([c["parent"] for c in a["candidates"]],
                         [None, "g0", "g0", "g0", "g1-c1", "g1-c1", "g1-c1"])

    def test_gate_requires_all_replicates_and_climates_without_tier_loss(self):
        pairs = [{"kind": "paired-training", "candidate": f"s{s:08x}-live",
                  "slices": {name: {"comparison": 1, "control": {"key": [4, 256, 10, 100]},
                                    "candidate": {"key": [4, 256, 20, 200]}}
                             for name in ("all", "climate/steady", "climate/seasonal")}}
                 for s in controls.training.SEARCH_SEEDS]
        self.assertTrue(controls.support_gate(pairs)["consistent_live_advantage"])
        for field, value in (("comparison", 0), ("comparison", -1), ("candidate", {"key": [4, 255, 30, 300]})):
            bad = copy.deepcopy(pairs)
            bad[1]["slices"]["climate/steady"][field] = value
            self.assertFalse(controls.support_gate(bad)["consistent_live_advantage"])
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            controls.support_gate(pairs[:-1])

    def test_original_live_control_and_paired_mutations_are_enforced(self):
        archived, old = controls.load_inputs(self.inputs)
        searches = {}
        for seed in controls.training.SEARCH_SEEDS:
            for profile in controls.PROFILES:
                key = f"s{seed:08x}-{profile['id']}"
                value = copy.deepcopy(old["searches"][f"s{seed:08x}-current"])
                value.pop("mode")
                value["profile"] = profile
                for evaluation in ([c["train"] for c in value["candidates"]] +
                                   [g["review"] for g in value["generations"]]):
                    for world in evaluation["worlds"].values():
                        world["result"].update(kind="landing-signal-replay", signal_probe={
                            "version": 1, "occupancy": profile["occupancy"], "resources": profile["resources"]})
                for candidate in value["candidates"]:
                    path = self.root / key / candidate["model"]
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(archived[f"s{seed:08x}-current/{candidate['model']}"])
                searches[key] = value
        controls.check_controls(searches, self.root, archived, old)
        bad = copy.deepcopy(searches)
        bad["s6d697833-fixed"]["candidates"][1]["mutation"]["rng_after"] += 1
        with self.assertRaisesRegex(RuntimeError, "unpaired RNG"):
            controls.check_controls(bad, self.root, archived, old)
        bad = copy.deepcopy(searches)
        bad["s6d697833-live"]["generations"][-1]["champion"] = "g0"
        with self.assertRaisesRegex(RuntimeError, "champion changed"):
            controls.check_controls(bad, self.root, archived, old)
        bad = copy.deepcopy(searches)
        bad["s6d697833-fixed"]["candidates"][1]["sha256"] = "bad"
        with self.assertRaisesRegex(RuntimeError, "models differ"):
            controls.check_controls(bad, self.root, archived, old)

    def test_bad_input_and_source_change_do_not_create_complete_bundle(self):
        output = self.root / "failed"
        with patch.object(controls, "INPUTS", {"landing-training-summary.json": "bad"}):
            with self.assertRaisesRegex(RuntimeError, "wrong frozen input"):
                controls.collect(BUILD, self.inputs, output, 4)
        self.assertFalse(output.exists())
        with patch.object(controls, "snapshot_sources"), \
             patch.object(controls, "source_files", side_effect=[
                 {controls.PROTOCOL: controls.digest(controls.ROOT / controls.PROTOCOL)}, {"changed": "sha"}]), \
             patch.object(controls, "run_panel", return_value={}):
            with self.assertRaisesRegex(RuntimeError, "sources/build changed"):
                controls.collect(BUILD, self.inputs, output, 2)
        self.assertTrue((output / "FAILED.txt").exists())
        self.assertFalse((output / "manifest.json").exists())
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            controls.verify(output)
        with self.assertRaisesRegex(RuntimeError, "fresh"):
            controls.collect(BUILD, self.inputs, output, 2)

    def test_retained_search_selection_all_scores_models_and_gallery_pixels(self):
        def load(name):
            return json.loads(gzip.decompress((self.inputs / name).read_bytes()))

        result = load("landing-controls-results.json.gz")
        models = {k: bytes.fromhex(v) for k, v in load("landing-controls-models.json.gz").items()}
        gallery = load("landing-controls-gallery.json.gz")
        summary = json.loads((self.inputs / "landing-controls-summary.json").read_text())
        archived, old = controls.load_inputs(self.inputs)
        self.assertEqual(result["rule"], controls.RULE)
        self.assertEqual(result["objective"], controls.training.individual.RULE)
        self.assertEqual(result["profiles"], list(controls.PROFILES))
        self.assertEqual(result["evaluation_conditions"], controls.evaluation_conditions())
        identities = {f"s{s:08x}-{p['id']}" for s in controls.training.SEARCH_SEEDS for p in controls.PROFILES}
        self.assertEqual(set(result["searches"]), identities)
        self.assertEqual(set(gallery), identities)
        self.assertEqual(set(summary["galleries"]), identities)
        self.assertEqual(set(result["evaluations"]), identities | {"initial-live", "initial-fixed"})
        self.assertEqual(set(models), {"initial.tgm"} | {
            key + "/" + c["model"] for key, search in result["searches"].items() for c in search["candidates"]})
        self.assertEqual(models["initial.tgm"], archived["initial.tgm"])
        for name, data in models.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        controls.check_controls(result["searches"], self.root, archived, old)
        scored = 0

        def verify_evaluation(evaluation, cases, profile, metadata):
            nonlocal scored
            self.assertEqual(set(evaluation["worlds"]), {c["id"] for c in cases})
            for case in cases:
                world = evaluation["worlds"][case["id"]]
                self.assertEqual(world["history"], controls.training.score_world(
                    controls.signals.scoring_view(world["result"], profile), case, metadata))
                scored += 1
            self.assertEqual(evaluation["aggregate"], controls.training.individual.aggregate(
                {k: w["history"] for k, w in evaluation["worlds"].items()}, [c["id"] for c in cases]))

        for key, search in result["searches"].items():
            candidates = {c["id"]: c for c in search["candidates"]}
            self.assertEqual(set(candidates), {"g0"} | {f"g{g}-c{c}" for g in (1, 2) for c in range(3)})
            self.assertEqual([g["generation"] for g in search["generations"]], [0, 1, 2])
            for c in search["candidates"]:
                data = models[key + "/" + c["model"]]
                self.assertEqual(hashlib.sha256(data).hexdigest(), c["sha256"])
                self.assertEqual(self.native("inspect", self.root / key / c["model"])["model"], c["metadata"])
                verify_evaluation(c["train"], controls.training.conditions(controls.training.TRAIN_SEED),
                                  search["profile"], c["metadata"])
            champion = candidates["g0"]
            for g in search["generations"]:
                if g["generation"]:
                    children = [candidates[f"g{g['generation']}-c{i}"] for i in range(3)]
                    self.assertTrue(all(c["parent"] == champion["id"] for c in children))
                    champion = controls.training.winner(champion, children)
                self.assertEqual((g["champion"], g["sha256"], g["training_key"]),
                                 (champion["id"], champion["sha256"], champion["train"]["aggregate"]["key"]))
                verify_evaluation(g["review"], controls.training.conditions(controls.training.REVIEW_SEED),
                                  search["profile"], champion["metadata"])
            compact = summary["searches"][key]
            self.assertEqual(compact, {
                "search_seed": search["search_seed"], "profile": search["profile"],
                "candidates": [{k: v for k, v in c.items() if k != "train"} |
                               {"training_key": c["train"]["aggregate"]["key"]} for c in search["candidates"]],
                "generations": [{k: v for k, v in g.items() if k != "review"} |
                                {"review_key": g["review"]["aggregate"]["key"],
                                 "review_zero_credit_windows": g["review"]["aggregate"]["zero_world_periods"]}
                                for g in search["generations"]]})
            g = gallery[key]
            controls.training.check_gallery(g, search)
            sheet = summary["galleries"][key]
            self.assertEqual({k: sheet[k] for k in g["sheet"]}, g["sheet"])
            self.assertEqual(sheet["rows"], [[f["id"] for f in g["frames"][i:i + 2]] for i in range(0, 12, 2)])
            image = self.inputs / sheet["path"]
            self.assertEqual(controls.digest(image), sheet["sha256"])
            width, height, rgb = decode_png(image)
            self.assertEqual((width, height, sheet["gap"]), (504, 1496, 8))
            for i, frame in enumerate(g["frames"]):
                self.assertEqual(frame["profile"], search["profile"])
                chosen = candidates[search["generations"][i // 4]["champion"]]
                x, y = 8 + (i % 2) * 248, 8 + (i // 2) * 248
                tile = b"".join(rgb[((y + row) * width + x) * 3:((y + row) * width + x + 240) * 3]
                                for row in range(240))
                raw = bytearray(240 * 240 * 2)
                for pixel in range(240 * 240):
                    r, green, b = tile[pixel * 3:pixel * 3 + 3]
                    struct.pack_into(">H", raw, pixel * 2, ((r >> 3) << 11) | ((green >> 2) << 5) | (b >> 3))
                controls.training.replay.check_result(controls.signals.scoring_view(frame["result"], search["profile"]),
                    frame, frame["day"] * controls.training.DAY, chosen["metadata"], 0, raw)
                if frame["day"] == 192:
                    case = f"{frame['scenario']}-{frame['climate']}-{frame['seed']}"
                    self.assertEqual({**frame["result"], "framebuffer_crc32": None},
                                     search["generations"][i // 4]["review"]["worlds"][case]["result"])
        self.assertEqual(len(result["models"]), 8)
        for model in result["models"]:
            key = (f"s{controls.training.SEARCH_SEEDS[0]:08x}-{model['profile']['id']}"
                   if model["id"].startswith("initial-") else model["id"])
            search = result["searches"][key]
            selected = "g0" if model["id"].startswith("initial-") else search["generations"][-1]["champion"]
            candidate = next(c for c in search["candidates"] if c["id"] == selected)
            self.assertEqual(model, {"id": model["id"], "profile": search["profile"], "champion": selected,
                                    "model": key + "/" + candidate["model"], "sha256": candidate["sha256"],
                                    "metadata": candidate["metadata"]})
            evaluation = result["evaluations"][model["id"]]
            verify_evaluation(evaluation, controls.evaluation_conditions(), model["profile"], model["metadata"])
            self.assertEqual(summary["evaluations"][model["id"]], {
                "aggregate": evaluation["aggregate"], "worlds": {
                    k: {f: w["result"][f] for f in ("world_hash", "run_hash", "living", "descendants", "seed_bank", "births", "deaths")}
                    for k, w in evaluation["worlds"].items()}})
        controls.equivalent_evaluation(result["evaluations"]["initial-live"],
                                      result["evaluations"]["initial-fixed"], *controls.PROFILES)
        self.assertEqual(result["comparisons"], controls.comparisons(result["evaluations"]))
        self.assertEqual(result["support_gate"], controls.support_gate(result["comparisons"]))
        for field in ("schema_version", "rule", "objective", "profiles", "evaluation_conditions", "models",
                      "candidate_evaluations", "comparisons", "support_gate"):
            self.assertEqual(summary[field], result[field])
        self.assertEqual(result["candidate_evaluations"], 42)
        self.assertEqual(summary["scored_worlds"], scored)
        self.assertEqual(scored, 368)
        self.assertEqual(summary["frames"], sum(len(g["frames"]) for g in gallery.values()))
        self.assertEqual(summary["frames"], 72)
        self.assertEqual(summary["protocol_sha256"], controls.digest(controls.ROOT / controls.PROTOCOL))
        self.assertEqual({k: summary["inputs"][k] for k in controls.INPUTS}, controls.INPUTS)
        self.assertTrue(summary["repeat_verified"])
        self.assertTrue(summary["independent_frozen_verification"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", required=True, type=Path)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *rest])
