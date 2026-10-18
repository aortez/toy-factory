#!/usr/bin/env python3
"""Mutation oracle, complete-ledger scoring bridge, and bounded selection tests."""

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

import garden_landing_training as training
from test_garden_landing_tools import run
from test_garden_landing_neural import crc_repair, decode

BUILD = None


class LandingTrainingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="landing-training-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cli = BUILD / "toy-factory-garden-landing"

    def native(self, *args, **kwargs):
        output = run([self.cli, *args], **kwargs)
        return json.loads(output) if output else None

    def reference(self, mode="history"):
        model = self.root / f"{mode}.tgl"
        meta = self.native("reference", model, "--mode", mode)["model"]
        return model, meta

    def test_mutation_matches_legacy_and_independent_extension_oracle(self):
        source, meta = self.reference()
        initial = source.read_bytes()
        old = self.root / "old.tgm"
        old.write_bytes(initial[16:1236])
        for seed in (0, 1, 0x6d697833, 0xffffffff):
            for count in (1, 16, 4096):
                prefix = f"{seed}-{count}"
                old_result = self.root / (prefix + ".tgm")
                receipt = json.loads(run([BUILD / "toy-factory-garden-model-mutate", old,
                                         old_result, seed, 32]))
                path = self.root / (prefix + ".tgl")
                mutation = self.native("mutate", source, path, seed, 32, count)
                expected = bytearray(initial)
                expected[16:1236] = old_result.read_bytes()
                state = receipt["rng_after"]

                def next_rng():
                    nonlocal state
                    state ^= (state << 13) & 0xffffffff
                    state ^= state >> 17
                    state ^= (state << 5) & 0xffffffff
                    state = state or 0x74726169
                    return state

                for _ in range(count):
                    i = next_rng() % 208
                    delta = next_rng() % 17 - 8
                    if not delta:
                        delta = 1 if next_rng() & 1 else -1
                    value = struct.unpack_from("b", expected, 1240 + i)[0]
                    struct.pack_into("b", expected, 1240 + i, max(-128, min(127, value + delta)))
                self.assertEqual(path.read_bytes(), crc_repair(bytes(expected)))
                self.assertEqual(mutation["rng_after"], state)
                decode(path.read_bytes())
                self.assertEqual(path.read_bytes()[1236:1240], initial[1236:1240])
                repeat = self.root / (prefix + "-repeat.tgl")
                self.assertEqual(self.native("mutate", source, repeat, seed, 32, count), mutation)
                self.assertEqual(repeat.read_bytes(), path.read_bytes())
        self.assertEqual(source.read_bytes(), initial)

    def test_mutation_masks_share_draws_and_fail_without_clobbering(self):
        models = [self.reference(mode)[0] for mode in training.MODES]
        outputs = []
        for model in models:
            path = self.root / (model.stem + "-mutated.tgl")
            receipt = self.native("mutate", model, path, 123, 32, 16)
            data = path.read_bytes()
            outputs.append((data[16:1236], data[1240:], receipt["rng_after"]))
            for a, b in ((0, 0), (-1, 16), (32, 4097), (4097, 1)):
                bad = self.root / "bad.tgl"
                self.native("mutate", model, bad, 1, a, b, valid=False)
                self.assertFalse(bad.exists())
            self.native("mutate", model, path, 123, 32, 16, valid=False)
            self.assertEqual(path.read_bytes(), data)
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[1], outputs[2])

    def test_complete_ledgers_do_not_change_runs_or_captures(self):
        model, meta = self.reference()
        for case in training.conditions("a9c30c1f"):
            args = ["replay", model, case["scenario"], "0x" + case["seed"],
                    "--ticks", training.STOP, "--climate", case["climate"]]
            plain = self.native(*args)
            ledger = self.native(*args, "--ledger")
            extra = ("ledger_start_tick", "lineages", "seeds")
            self.assertEqual(plain, {k: v for k, v in ledger.items() if k not in extra})
            history = training.score_world(ledger, case, meta)
            self.assertEqual(len(history["blocks"]), 4)
            raw = self.root / f"{case['id']}.raw"
            image = self.native(*args, "--ledger", "--framebuffer", raw)
            self.assertEqual({**image, "framebuffer_crc32": None}, ledger)
            for field in ("lineages", "seeds"):
                corrupted = copy.deepcopy(ledger)
                del corrupted[field]
                with self.assertRaises((ValueError, KeyError, RuntimeError)):
                    training.score_world(corrupted, case, meta)
            self.native(*args, "--ledger", "--ledger", valid=False)

    def test_nonzero_model_scores_and_parallel_order(self):
        model, _ = self.reference()
        changed = self.root / "mutated.tgl"
        meta = self.native("mutate", model, changed, 0x6d697833, 32, 16)["model"]
        self.assertGreater(meta["common_nonzero_weights"] + meta["candidate_nonzero_weights"], 0)
        one = training.evaluate(self.cli, self.root, changed, "ed52188c", 1, meta)
        two = training.evaluate(self.cli, self.root, changed, "ed52188c", 2, meta)
        self.assertEqual(one, two)
        self.assertEqual(list(one["worlds"]), [c["id"] for c in training.conditions("ed52188c")])

    def test_selector_is_strict_and_canonical(self):
        def c(name, key):
            return {"id": name, "train": {"aggregate": {"key": key}}}

        initial = c("parent", [0, 0, 100, 500])
        self.assertIs(training.winner(initial, [c("tie", [0, 0, 100, 500])]), initial)
        first, second = c("first", [1, 0, 0, 0]), c("second", [1, 0, 0, 0])
        self.assertIs(training.winner(initial, [first, second]), first)
        self.assertEqual(len(training.SEARCH_SEEDS) * len(training.MODES) *
                         (1 + training.GENERATIONS * training.CHILDREN), 63)
        self.assertNotEqual(training.TRAIN_SEED, training.REVIEW_SEED)

    def test_retained_models_histories_and_summary_agree(self):
        root = training.ROOT / "benchmarks/garden-seasons"
        summary = json.loads((root / "landing-training-summary.json").read_text())
        with gzip.open(root / "landing-training-histories.json.gz", "rt") as f:
            histories = json.load(f)
        with gzip.open(root / "landing-training-models.json.gz", "rt") as f:
            models = {k: bytes.fromhex(v) for k, v in json.load(f).items()}
        self.assertEqual(hashlib.sha256(models["initial.tgm"]).hexdigest(), training.BASE_SHA)
        self.assertEqual(len(models), 64)
        self.assertEqual(summary["candidate_evaluations"], histories["candidate_evaluations"])
        self.assertEqual(set(summary["searches"]), set(histories["searches"]))
        self.assertEqual(summary["rule"], training.RULE)
        for key, search in histories["searches"].items():
            compact = summary["searches"][key]
            self.assertEqual([c["id"] for c in compact["candidates"]],
                             [c["id"] for c in search["candidates"]])
            for c, short in zip(search["candidates"], compact["candidates"], strict=True):
                data = models[key + "/" + c["model"]]
                decode(data)
                self.assertEqual(hashlib.sha256(data).hexdigest(), c["sha256"])
                self.assertEqual(short["sha256"], c["sha256"])
                self.assertEqual(short["parent"], c["parent"])
                self.assertEqual(short["training_key"], c["train"]["aggregate"]["key"])
                self.assertEqual(short["model_crc32"], c["metadata"]["payload_crc32"])
            for g, short in zip(search["generations"], compact["generations"], strict=True):
                for field in ("generation", "champion", "sha256", "rng_after", "training_key"):
                    self.assertEqual(short[field], g[field])
                self.assertEqual(short["review_key"], g["review"]["aggregate"]["key"])
                self.assertEqual(short["review_zero_credit_windows"], g["review"]["aggregate"]["zero_world_periods"])
            final = search["generations"][-1]["review"]
            rescored = {}
            for case in training.conditions(training.REVIEW_SEED):
                w = final["worlds"][case["id"]]
                h = training.score_world(w["result"], case, w["result"]["model"])
                self.assertEqual(h, w["history"])
                rescored[case["id"]] = h
                short = compact["final_review_worlds"][case["id"]]
                for field in ("world_hash", "run_hash", "living", "seed_bank", "births", "deaths"):
                    self.assertEqual(short[field], w["result"][field])
                self.assertEqual(short["credit_ticks"], [b["rolling"]["ticks"] for b in h["blocks"]])
            self.assertEqual(training.individual.aggregate(rescored, list(rescored)), final["aggregate"])

    def test_search_persists_generations_and_ignores_review(self):
        calls = []

        def native(binary, root, action, *args):
            if action == "import":
                _, target, _, mode = args
                data = {"mode": mode, "generation": 0, "child": 0}
                extra = {}
            else:
                source, target, rng, base, extension = args
                data = json.loads((root / source).read_text())
                data = {**data, "generation": data["generation"] + 1, "child": int(target[-5])}
                extra = {"rng_before": rng, "rng_after": rng + 1,
                         "legacy_mutations": base, "landing_mutations": extension}
            (root / target).write_text(json.dumps(data))
            return {**extra, "model": {"mode": data["mode"], "legacy_payload_crc32": "01b9d94a",
                "common_nonzero_weights": 0, "candidate_nonzero_weights": 0, "omit_dead_only": False}}

        def evaluate(binary, root, model, seed, jobs, metadata):
            data = json.loads((root / model).read_text())
            # Training selects c1; review prefers c2. Review must never select.
            value = data["generation"] * 10 + (data["child"] == (1 if seed == training.TRAIN_SEED else 2))
            if data["generation"] == 0:
                value = 0
            calls.append((str(root), model, seed, jobs))
            return {"aggregate": {"key": [1, 4, value, value]},
                    "worlds": {"world": {"result": {"living": value}}}}

        with patch.object(training, "native", side_effect=native), \
             patch.object(training, "evaluate", side_effect=evaluate), \
             patch.object(training, "SEARCH_SEEDS", (1,)), \
             patch.object(training, "capture", return_value=[]), \
             patch.object(training, "contact_sheet", return_value={}):
            a = training.search(Path("binary"), Path("legacy"), self.root / "a", 2, True)
            b = training.search(Path("binary"), Path("legacy"), self.root / "b", 1, False)
        self.assertEqual(a, b)
        for key, search in a["searches"].items():
            self.assertEqual([g["champion"] for g in search["generations"]], ["g0", "g1-c1", "g2-c1"])
            self.assertEqual([c["parent"] for c in search["candidates"]],
                             [None, "g0", "g0", "g0", "g1-c1", "g1-c1", "g1-c1"])
            self.assertTrue((self.root / "a" / key / "generation-2.json").is_file())
        self.assertEqual(len(calls), 2 * 3 * (7 + 3))

    def test_incomplete_gallery_and_bundle_fail_closed(self):
        run = {"candidates": [{"id": "g0", "model": "models/g0.tgl"}],
               "generations": [{"generation": g, "champion": "g0"} for g in range(3)]}
        frames = [{**case, "id": f"g{g}-{case['id']}-day-{day}", "model": "models/g0.tgl", "day": day}
                  for g in range(3) for case in training.conditions(training.REVIEW_SEED)
                  if case["climate"] == "seasonal" for day in (16, 192)]
        training.check_gallery({"frames": frames}, run)
        for bad in (frames[:-1], frames[::-1], frames + [frames[0]],
                    [{**f, "model": "models/not-champion.tgl"} for f in frames]):
            with self.assertRaises(RuntimeError):
                training.check_gallery({"frames": bad}, run)
        (self.root / "FAILED.txt").write_text("interrupted\n")
        with patch.object(training, "search") as search:
            with self.assertRaises(RuntimeError):
                training.verify(self.root)
            search.assert_not_called()

    def test_bad_inputs_and_changed_sources_leave_no_complete_manifest(self):
        model, _ = self.reference()
        output = self.root / "bad-input"
        with self.assertRaises(RuntimeError):
            training.collect(BUILD, model, output, 2)
        self.assertFalse(output.exists())
        with patch.object(training, "BASE_SHA", training.digest(model)), \
             patch.object(training, "snapshot_sources"), \
             patch.object(training, "source_files", side_effect=[{}, {"changed": "sha"}]), \
             patch.object(training, "search", return_value={}) as search:
            with self.assertRaisesRegex(RuntimeError, "sources changed"):
                training.collect(BUILD, model, output, 2)
            self.assertEqual(search.call_count, 2)
        self.assertTrue((output / "FAILED.txt").is_file())
        self.assertFalse((output / "manifest.json").exists())
        with self.assertRaises(RuntimeError):
            training.collect(BUILD, model, output, 2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", required=True, type=Path)
    args, remaining = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *remaining])
