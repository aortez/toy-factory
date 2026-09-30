#!/usr/bin/env python3
"""Fixed multi-seed splits, paired controls, selection isolation and provenance."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_multiseed as multi
from test_garden_gallery import decode_png
from test_garden_landing_tools import run

BUILD = None


class MultiseedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="landing-multiseed-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.inputs = multi.ROOT / "benchmarks/garden-seasons"

    def test_fixed_plan_disjoint_splits_and_budget(self):
        x, seeds = 0x6c766632, []
        for _ in range(4):
            x ^= (x << 13) & 0xffffffff
            x ^= x >> 17
            x ^= (x << 5) & 0xffffffff
            seeds.append(f"{x:08x}")
        self.assertEqual(tuple(seeds), multi.EVALUATION_SEEDS)
        self.assertEqual(multi.TRAIN_SEEDS, (multi.training.TRAIN_SEED, *multi.controls.EVALUATION_SEEDS))
        self.assertFalse(set(seeds) & {*multi.TRAIN_SEEDS, multi.training.REVIEW_SEED,
                                      *multi.controls.signals.previous.SEEDS})
        self.assertEqual(len(multi.training_conditions()), 20)
        self.assertEqual(len({c["id"] for c in multi.training_conditions()}), 20)
        self.assertEqual(len(multi.evaluation_conditions()), 16)
        self.assertEqual(len(multi.slices()), 9)
        self.assertEqual(len(multi.slices()["all"]), 16)
        candidates = len(multi.PROFILES) * len(multi.training.SEARCH_SEEDS) * (
            1 + multi.training.GENERATIONS * multi.training.CHILDREN)
        self.assertEqual(candidates, 42)
        self.assertEqual(candidates * 20 + 6 * 3 * 4 + 14 * 16, 1136)

    def test_explicit_panel_alone_selects_and_default_is_unchanged(self):
        seen = []

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
            seen.append(copy.deepcopy(cases))
            data = json.loads((work / model).read_text())
            preferred = 2 if cases[0]["seed"] == multi.training.REVIEW_SEED else (1 if len(cases) == 20 else 0)
            value = data["generation"] * 10 + int(data["generation"] > 0 and data["child"] == preferred)
            return {"aggregate": {"key": [1, len(cases) * 4, value, value]}, "worlds": {}}

        cases = multi.training_conditions()
        original = copy.deepcopy(cases)
        with patch.object(multi.training, "native", side_effect=native), \
             patch.object(multi.controls, "evaluate", side_effect=evaluate):
            a, _ = multi.controls.search_one(Path("cli"), Path("legacy"), self.root / "multi", 123,
                multi.PROFILES[0], 2, False, train_cases=cases)
            self.assertEqual([g["champion"] for g in a["generations"]], ["g0", "g1-c1", "g2-c1"])
            self.assertEqual(seen.count(cases), 7)
            self.assertEqual(seen.count(multi.training.conditions(multi.training.REVIEW_SEED)), 3)
            b, _ = multi.controls.search_one(Path("cli"), Path("legacy"), self.root / "default", 123,
                multi.PROFILES[0], 1, False)
            c, _ = multi.controls.search_one(Path("cli"), Path("legacy"), self.root / "explicit", 123,
                multi.PROFILES[0], 1, False, train_cases=multi.training.conditions(multi.training.TRAIN_SEED))
        self.assertEqual(b, c)
        self.assertEqual([g["champion"] for g in b["generations"]], ["g0", "g1-c0", "g2-c0"])
        self.assertEqual(cases, original)
        for invalid in ([], [cases[0], cases[0]], multi.training.conditions(multi.training.REVIEW_SEED)):
            with self.assertRaisesRegex(RuntimeError, "training"):
                multi.controls.search_one(Path("cli"), Path("legacy"), self.root / "invalid", 123,
                                         multi.PROFILES[0], 1, False, train_cases=invalid)
        self.assertFalse((self.root / "invalid").exists())

    def test_prior_finalists_are_not_reselected(self):
        archive, old = multi.load_inputs(self.inputs)
        models = multi.evaluation_models(old["searches"], old)
        self.assertEqual(len(models), 14)
        self.assertEqual(len({m["id"] for m in models}), 14)
        for model in models:
            key = model["id"].removeprefix("single-").removeprefix("multi-")
            if key.startswith("initial-"):
                key = f"s{multi.training.SEARCH_SEEDS[0]:08x}-{model['profile']['id']}"
                chosen = old["searches"][key]["candidates"][0]
            else:
                search = old["searches"][key]
                chosen = next(c for c in search["candidates"] if c["id"] == search["generations"][-1]["champion"])
            self.assertEqual(model["champion"], chosen["id"])
            self.assertEqual(model["sha256"], chosen["sha256"])
            self.assertEqual(model["profile"], old["searches"][key]["profile"])
            self.assertEqual(multi.hashlib.sha256(archive[model["model"].removeprefix("single/")]).hexdigest(),
                             model["sha256"])

    def test_paired_controls_reject_rng_bytes_and_incomplete_panel(self):
        archive, old = multi.load_inputs(self.inputs)
        searches = copy.deepcopy(old["searches"])
        for key, search in searches.items():
            for c in search["candidates"]:
                c["train"]["worlds"] = {case["id"]: {} for case in multi.training_conditions()}
                path = self.root / key / c["model"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive[key + "/" + c["model"]])
        with patch.object(multi.controls, "equivalent_evaluation") as equivalent:
            multi.check_controls(searches, self.root, archive, old)
            self.assertEqual(equivalent.call_count, 12)
            for field, message in (("rng_after", "unpaired RNG"), ("sha256", "model changed"), ("panel", "training panel")):
                bad = copy.deepcopy(searches)
                c = bad["s6d697833-fixed"]["candidates"][1]
                if field == "rng_after":
                    c["mutation"][field] += 1
                elif field == "panel":
                    c["train"]["worlds"].pop(next(iter(c["train"]["worlds"])))
                else:
                    c[field] = "bad"
                with self.assertRaisesRegex(RuntimeError, message):
                    multi.check_controls(bad, self.root, archive, old)
            bad = copy.deepcopy(searches)
            bad.pop("s6d697833-live")
            with self.assertRaisesRegex(RuntimeError, "incomplete"):
                multi.check_controls(bad, self.root, archive, old)
            bad_archive = dict(archive)
            bad_archive["s6d697833-fixed/models/g1-c0.tgl"] = b"bad"
            with self.assertRaisesRegex(RuntimeError, "first-generation"):
                multi.check_controls(searches, self.root, bad_archive, old)

    def test_each_gate_requires_all_unique_pairs_and_both_climates(self):
        pairs = [{"kind": kind, "candidate": f"multi-s{s:08x}-{'fixed' if kind == 'breadth-fixed' else 'live'}",
                  "slices": {name: {"comparison": 1, "control": {"key": [1, 64, 10, 100]},
                                    "candidate": {"key": [1, 64, 20, 200]}}
                             for name in ("all", "climate/steady", "climate/seasonal")}}
                 for kind in ("breadth-live", "breadth-fixed", "multi-live-fixed") for s in multi.training.SEARCH_SEEDS]
        self.assertTrue(all(g["consistent_advantage"] for g in multi.support_gates(pairs).values()))
        for field, value in (("comparison", 0), ("comparison", -1), ("candidate", {"key": [1, 63, 30, 300]})):
            bad = copy.deepcopy(pairs)
            bad[1]["slices"]["climate/steady"][field] = value
            gates = multi.support_gates(bad)
            self.assertFalse(gates["breadth-live"]["consistent_advantage"])
            self.assertTrue(gates["breadth-fixed"]["consistent_advantage"])
        with self.assertRaisesRegex(RuntimeError, "incomplete/duplicate"):
            multi.support_gates(pairs[:-1])
        with self.assertRaisesRegex(RuntimeError, "incomplete/duplicate"):
            multi.support_gates(pairs[:-1] + [pairs[-2]])

    def test_retained_searches_scores_models_comparisons_and_gallery(self):
        def load(name):
            return json.loads(gzip.decompress((self.inputs / name).read_bytes()))

        result = load("landing-multiseed-results.json.gz")
        models = {k: bytes.fromhex(v) for k, v in load("landing-multiseed-models.json.gz").items()}
        gallery = load("landing-multiseed-gallery.json.gz")
        summary = json.loads((self.inputs / "landing-multiseed-summary.json").read_text())
        archive, old = multi.load_inputs(self.inputs)
        self.assertEqual(result["rule"], multi.RULE)
        self.assertEqual(result["objective"], multi.training.individual.RULE)
        self.assertEqual(result["profiles"], list(multi.PROFILES))
        self.assertEqual(result["training_conditions"], multi.training_conditions())
        self.assertEqual(result["evaluation_conditions"], multi.evaluation_conditions())
        self.assertEqual(result["models"], multi.evaluation_models(result["searches"], old))
        expected_models = {"initial.tgm"} | {
            key + "/" + c["model"] for key, s in result["searches"].items() for c in s["candidates"]} | {
            m["model"] for m in result["models"] if m["id"].startswith("single-")}
        self.assertEqual(set(models), expected_models)
        self.assertEqual(len(models), 49)
        self.assertEqual(models["initial.tgm"], archive["initial.tgm"])
        for name, data in models.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            if name.startswith("single/"):
                self.assertEqual(data, archive[name.removeprefix("single/")])
        multi.check_controls(result["searches"], self.root, archive, old)
        scored = 0
        cli = BUILD / "toy-factory-garden-landing"

        def verify_evaluation(evaluation, cases, profile, metadata):
            nonlocal scored
            self.assertEqual(set(evaluation["worlds"]), {c["id"] for c in cases})
            for case in cases:
                world = evaluation["worlds"][case["id"]]
                self.assertEqual(world["history"], multi.training.score_world(
                    multi.controls.signals.scoring_view(world["result"], profile), case, metadata))
                scored += 1
            self.assertEqual(evaluation["aggregate"], multi.training.individual.aggregate(
                {k: w["history"] for k, w in evaluation["worlds"].items()}, [c["id"] for c in cases]))

        for key, search in result["searches"].items():
            candidates = {c["id"]: c for c in search["candidates"]}
            self.assertEqual(set(candidates), {"g0"} | {f"g{g}-c{c}" for g in (1, 2) for c in range(3)})
            self.assertEqual([g["generation"] for g in search["generations"]], [0, 1, 2])
            for c in search["candidates"]:
                path = self.root / key / c["model"]
                self.assertEqual(multi.digest(path), c["sha256"])
                self.assertEqual(json.loads(run([cli, "inspect", path]))["model"], c["metadata"])
                if c["mutation"]:
                    target = self.root / (key + "-" + c["id"] + "-repeat.tgl")
                    parent = self.root / key / candidates[c["parent"]]["model"]
                    receipt = json.loads(run([cli, "mutate", parent, target, c["mutation"]["rng_before"], 32, 16]))
                    self.assertEqual(receipt, c["mutation"])
                    self.assertEqual(target.read_bytes(), path.read_bytes())
                verify_evaluation(c["train"], multi.training_conditions(), search["profile"], c["metadata"])
            champion = candidates["g0"]
            for g in search["generations"]:
                if g["generation"]:
                    children = [candidates[f"g{g['generation']}-c{i}"] for i in range(3)]
                    self.assertTrue(all(c["parent"] == champion["id"] for c in children))
                    champion = multi.training.winner(champion, children)
                    self.assertEqual(g["rng_after"], children[-1]["mutation"]["rng_after"])
                else:
                    self.assertEqual(g["rng_after"], search["search_seed"])
                self.assertEqual((g["champion"], g["sha256"], g["training_key"]),
                                 (champion["id"], champion["sha256"], champion["train"]["aggregate"]["key"]))
                verify_evaluation(g["review"], multi.training.conditions(multi.training.REVIEW_SEED),
                                  search["profile"], champion["metadata"])
            self.assertEqual(summary["searches"][key], {
                "search_seed": search["search_seed"], "profile": search["profile"],
                "candidates": [{k: v for k, v in c.items() if k != "train"} |
                               {"training_key": c["train"]["aggregate"]["key"]} for c in search["candidates"]],
                "generations": [{k: v for k, v in g.items() if k != "review"} |
                                {"review_key": g["review"]["aggregate"]["key"],
                                 "review_zero_credit_windows": g["review"]["aggregate"]["zero_world_periods"]}
                                for g in search["generations"]]})
            g = gallery[key]
            multi.training.check_gallery(g, search)
            sheet = summary["galleries"][key]
            self.assertEqual({k: sheet[k] for k in g["sheet"]}, g["sheet"])
            image = self.inputs / sheet["path"]
            self.assertEqual(multi.digest(image), sheet["sha256"])
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
                multi.training.replay.check_result(multi.controls.signals.scoring_view(frame["result"], search["profile"]),
                    frame, frame["day"] * multi.training.DAY, chosen["metadata"], 0, raw)
                if frame["day"] == 192:
                    case = f"{frame['scenario']}-{frame['climate']}-{frame['seed']}"
                    self.assertEqual({**frame["result"], "framebuffer_crc32": None},
                                     search["generations"][i // 4]["review"]["worlds"][case]["result"])
        self.assertEqual(set(gallery), set(result["searches"]))
        self.assertEqual(set(summary["galleries"]), set(gallery))
        self.assertEqual(set(result["evaluations"]), {m["id"] for m in result["models"]})
        for model in result["models"]:
            path = self.root / model["model"]
            self.assertEqual(multi.digest(path), model["sha256"])
            self.assertEqual(json.loads(run([cli, "inspect", path]))["model"], model["metadata"])
            evaluation = result["evaluations"][model["id"]]
            verify_evaluation(evaluation, multi.evaluation_conditions(), model["profile"], model["metadata"])
            self.assertEqual(summary["evaluations"][model["id"]], {
                "aggregate": evaluation["aggregate"], "worlds": {
                    k: {f: w["result"][f] for f in ("world_hash", "run_hash", "living", "descendants", "seed_bank", "births", "deaths")}
                    for k, w in evaluation["worlds"].items()}})
        multi.controls.equivalent_evaluation(result["evaluations"]["initial-live"],
                                            result["evaluations"]["initial-fixed"], *multi.PROFILES)
        self.assertEqual(result["comparisons"], multi.comparisons(result["evaluations"]))
        self.assertEqual(result["support_gates"], multi.support_gates(result["comparisons"]))
        self.assertEqual(summary["comparisons"], [{
            **{k: p[k] for k in ("kind", "control", "candidate")}, "slices": {
                name: {k: v for k, v in value.items() if k not in ("control", "candidate")} |
                      {"control_key": value["control"]["key"], "candidate_key": value["candidate"]["key"]}
                for name, value in p["slices"].items()}} for p in result["comparisons"]])
        for field in ("schema_version", "rule", "objective", "profiles", "training_conditions", "evaluation_conditions",
                      "models", "candidate_evaluations", "scored_worlds", "support_gates"):
            self.assertEqual(summary[field], result[field])
        self.assertEqual(result["candidate_evaluations"], 42)
        self.assertEqual(summary["scored_worlds"], scored)
        self.assertEqual(scored, 1136)
        self.assertEqual(summary["frames"], sum(len(g["frames"]) for g in gallery.values()))
        self.assertEqual(summary["frames"], 72)
        self.assertEqual(summary["protocol_sha256"], multi.digest(multi.ROOT / multi.PROTOCOL))
        self.assertEqual({k: summary["inputs"][k] for k in multi.INPUTS}, multi.INPUTS)
        self.assertTrue(summary["repeat_verified"])
        self.assertTrue(summary["independent_frozen_verification"])
        verification = load(summary["verification"]["receipt"])
        self.assertEqual(verification["status"], "complete")
        self.assertEqual(verification["manifest_sha256"], summary["manifest_sha256"])
        self.assertEqual(len(verification["matched_panel_files"]), summary["verification"]["matched_panel_file_count"])
        self.assertEqual(verification["independent_replay_seconds"], summary["verification"]["independent_replay_seconds"])
        for name, value in (("results.json", result), ("gallery.json", gallery)):
            canonical = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
            self.assertEqual(multi.hashlib.sha256(canonical).hexdigest(), verification["matched_panel_files"][name])
        for name, sha in multi.INPUTS.items():
            self.assertEqual(verification["frozen_inputs_before_replay"]["inputs/" + name], sha)
        self.assertEqual(verification["frozen_inputs_before_replay"]["protocol.md"], summary["protocol_sha256"])
        self.assertEqual(verification["frozen_inputs_before_replay"]["bin/garden-landing"], summary["inputs"]["binary"])
        for name, data in models.items():
            self.assertEqual(multi.hashlib.sha256(data).hexdigest(), verification["matched_panel_files"][name])
        for key in gallery:
            self.assertEqual(summary["galleries"][key]["sha256"],
                             verification["matched_panel_files"][key + "/contact-sheet.png"])

    def test_wrong_input_and_source_change_fail_closed(self):
        output = self.root / "failed"
        with patch.object(multi, "INPUTS", {"landing-controls-results.json.gz": "bad"}):
            with self.assertRaisesRegex(RuntimeError, "wrong frozen input"):
                multi.collect(BUILD, self.inputs, output, 4)
        self.assertFalse(output.exists())
        with patch.object(multi.controls, "snapshot_sources"), \
             patch.object(multi.controls, "source_files", side_effect=[
                 {multi.PROTOCOL: multi.digest(multi.ROOT / multi.PROTOCOL)}, {"changed": "sha"}]), \
             patch.object(multi, "run_panel", return_value={}):
            with self.assertRaisesRegex(RuntimeError, "sources/build changed"):
                multi.collect(BUILD, self.inputs, output, 2)
        self.assertTrue((output / "FAILED.txt").exists())
        self.assertFalse((output / "manifest.json").exists())
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            multi.verify(output)
        with self.assertRaisesRegex(RuntimeError, "fresh"):
            multi.collect(BUILD, self.inputs, output, 2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", required=True, type=Path)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *rest])
