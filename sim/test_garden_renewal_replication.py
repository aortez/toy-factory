#!/usr/bin/env python3
"""Replica isolation, explicit schedule routing and unchanged pilot defaults."""
import copy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_renewal_replication as run
import test_garden_renewal_training as fixtures

mixed, previous, pilot = run.mixed, run.previous, run.pilot


def panel(study, *, review=False, label="steady"):
    seeds = study.review if review else study.development
    patches = dict(study.review_patches if review else study.development_patches)
    return {key: copy.deepcopy(fixtures.world(label)) for key, *_ in mixed.conditions(seeds, patches)}


class ProfileTests(unittest.TestCase):
    def test_fixed_fresh_disjoint_seeds_schedules_and_budget(self):
        settings = run.settings()
        self.assertEqual(settings["budget"]["native_processes"], 1736)
        self.assertEqual(sum(v for k, v in settings["budget"].items() if k != "native_processes"), 1736)
        self.assertEqual(settings["concurrent_replicas"], 2)
        self.assertEqual(len(set(s.rng for s in run.STUDIES)), 2)
        for s in run.STUDIES:
            self.assertEqual(len(mixed.conditions(s.development, dict(s.development_patches))), 16)
            self.assertEqual(len(mixed.conditions(s.review, dict(s.review_patches))), 8)
            self.assertTrue(set(s.development).isdisjoint(s.review))
            self.assertNotIn(s.rng, (mixed.RNG, 0))
            self.assertTrue(set(dict(s.development_patches).values()).isdisjoint(dict(s.review_patches).values()))
        self.assertTrue(set((*run.TRAIN, *run.REVIEW)).isdisjoint((*previous.STUDY.development, *previous.REVIEW)))

    def test_old_record_stays_exact_and_new_profile_is_immutable(self):
        s = mixed.MIXED
        self.assertEqual(s.record(), {"name": s.name, "rule": s.rule, "protocol": s.protocol,
            "development": list(s.development), "review": list(s.review), "patches": dict(mixed.PATCHES),
            "generations": 3, "offspring": 3, "mutations": 32, "rng": mixed.RNG})
        with self.assertRaises(FrozenInstanceError):
            run.STUDIES[0].rng = 1
        record = run.STUDIES[0].record()
        record["patches"].clear()
        record["review_patches"].clear()
        self.assertEqual(len(run.STUDIES[0].development_patches), 2)
        self.assertEqual(len(run.STUDIES[0].review_patches), 2)

    def test_invalid_or_mutable_profiles_are_rejected(self):
        s = run.STUDIES[0]
        changes = [{"rng": 0}, {"rng": True}, {"rng": 2**32}, {"development": list(s.development)},
                   {"review": s.development}, {"review": ("invalid",)}, {"review": (run.REVIEW[0],)*2},
                   {"review_patches": list(s.review_patches)}, {"review_patches": ()},
                   {"review_patches": (s.review_patches[0],)*2},
                   {"review_patches": (("../bad", "00000001"),)},
                   {"review_patches": (("a", "00000001"), ("b", "00000001"))}]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                replace(s, **change)

    def test_custom_aggregation_requires_exact_role_conditions(self):
        s = run.STUDIES[0]
        p = panel(s)
        for arm in run.ARMS:
            obj = previous.Objective(arm)
            result = obj.aggregate(p, s.development, patches=dict(s.development_patches))
            self.assertEqual(result, mixed.selection_aggregate(p, s.development, obj, patches=dict(s.development_patches)))
            for seeds, patches in ((s.development, mixed.PATCHES), (s.review, dict(s.review_patches))):
                with self.assertRaises(RuntimeError):
                    obj.aggregate(p, seeds, patches=patches)

    def test_matched_review_omissions_and_diagnostics_are_non_mutating(self):
        s = run.STUDIES[0]
        a, b = panel(s, review=True, label="sterile"), panel(s, review=True)
        before = copy.deepcopy((a, b))
        result = run.comparisons(a, b, s, review=True)
        self.assertEqual((a, b), before)
        for view in run.ARMS:
            self.assertEqual(set(result[view]["schedules"]), {"review-1", "review-2"})
            self.assertEqual(result[view]["overall"]["paired_counts"], {"wins": 8, "ties": 0, "losses": 0})
            for seed, group in result[view]["leave_one_world_seed_out"].items():
                self.assertEqual(len(group["pairs"]), 6)
                self.assertTrue(all(not p["condition"].endswith(seed) for p in group["pairs"]))
        with self.assertRaises(RuntimeError):
            run.comparisons(a, b, s)


class OrchestrationTests(unittest.TestCase):
    def test_actual_evaluator_routes_and_validates_explicit_schedule(self):
        s = run.STUDIES[0]
        for review in (False, True):
            seeds, patches = (s.review, dict(s.review_patches)) if review else (s.development, dict(s.development_patches))
            calls, checks = [], []
            def native(command, target):
                calls.append(command)
                return {"key": [1, 0, 0, 0, 0]}, 0
            def validate(value, seed, crc, *, patch):
                checks.append((seed, patch))
                return {"evaluation": value}
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with patch.object(pilot, "run_json", side_effect=native), patch.object(pilot, "model_crc", return_value="original"), \
                     patch.object(pilot, "validate_trial", side_effect=validate), patch("builtins.print"):
                    worlds = mixed.evaluate(root, root, "g0", root/"model", seeds, [], patches=patches)
            self.assertEqual(list(worlds), [k for k, *_ in mixed.conditions(seeds, patches)])
            self.assertEqual(checks, [(seed, p) for _, _, seed, p in mixed.conditions(seeds, patches)])
            self.assertEqual([(c[3], c[4]) for c in calls], [("0x"+seed, "0x"+p) for seed, p in checks])

    def test_concurrent_serial_searches_have_private_rng_and_repeated_parent_history(self):
        def evaluate(root, folder, name, model, seeds, timings, *, objective=None, patches=None):
            label = "late-burst" if name == "g1-c1" else "steady" if name == "g1-c2" else "sterile"
            return {k: copy.deepcopy(fixtures.world(label)) for k, *_ in mixed.conditions(seeds, patches)}
        def mutate(command, target):
            before, after = Path(command[1]).read_text(), f"{Path(command[2]).stem}:{command[3]}"
            Path(command[2]).write_text(after)
            return {"before": before, "after": after, "rng_before": command[3], "rng_after": command[3]+1}, 0
        def search(root, s):
            records = {}
            for arm in run.ARMS:
                sub = root/s.name/arm
                (sub/"input").mkdir(parents=True)
                (sub/"input/initial.tgm").write_text("initial")
                obj, callbacks = previous.Objective(arm), []
                a = mixed.search(sub, sub/"search", [], lambda g,c: callbacks.append((g,c)), study=s, objective=obj)
                b = mixed.search(sub, sub/"repeat", [], study=s, objective=obj)
                self.assertEqual(a, b)
                self.assertEqual(a["rng_after"], s.rng+9)
                winner = "g1-c1" if arm == "v2" else "g1-c2"
                self.assertEqual(a["champions"], ["initial", winner, winner, winner])
                self.assertEqual(callbacks, list(enumerate(a["champions"])))
                mixed.check_search(a, study=s, objective=obj)
                with self.assertRaises(RuntimeError):
                    mixed.check_search(a, study=run.STUDIES[1] if s == run.STUDIES[0] else run.STUDIES[0], objective=obj)
                records[arm] = {"search": a, "review": [{"worlds": panel(s, review=True)}]}
            run.check_prefix(records)
            return records
        with tempfile.TemporaryDirectory() as directory, patch.object(mixed, "evaluate", side_effect=evaluate), \
             patch.object(pilot, "run_json", side_effect=mutate), patch.object(pilot, "model_crc", side_effect=lambda p: p.read_text()):
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(search, Path(directory), s) for s in run.STUDIES]
                results = [f.result() for f in futures]
        self.assertNotEqual(results[0]["v2"]["search"]["candidates"][1]["model_sha256"],
                            results[1]["v2"]["search"]["candidates"][1]["model_sha256"])
        self.assertEqual(mixed.MIXED.rng, mixed.RNG)

    def test_common_prefix_checks_reject_divergent_first_generation(self):
        candidate = {"id": "initial", "model_sha256": "sha", "model_crc32": "crc", "mutation": None, "parent": None, "worlds": {}}
        arms = {arm: {"search": {"candidates": [dict(candidate, id=str(i)) for i in range(4)]},
                      "review": [{"worlds": {}}]} for arm in run.ARMS}
        run.check_prefix(arms)
        arms["renewal"]["search"]["candidates"][2]["model_sha256"] = "other"
        with self.assertRaises(RuntimeError):
            run.check_prefix(arms)


if __name__ == "__main__":
    unittest.main()
