#!/usr/bin/env python3
"""Mixed-panel selection and replay-contract tests without a training sweep."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_mixed_training as mixed


def worlds(seeds):
    score = mixed.fitness.arithmetic_fixtures()["steady-offspring"]["evaluation"]
    return {key: {"evaluation": copy.deepcopy(score), "terminal_species": {"flower": 2},
                  "terminal_families": {"1": 2}} for key, *_ in mixed.conditions(seeds)}


class PanelTests(unittest.TestCase):
    def test_split_and_budget(self):
        self.assertEqual(tuple(mixed.experiment.trial_seeds(0x6D697864, 4)), mixed.DEVELOPMENT)
        self.assertEqual(tuple(mixed.experiment.trial_seeds(0x726D7833, 4)), mixed.REVIEW)
        historical = {*mixed.pilot.DEVELOPMENT, *mixed.pilot.REVIEW, *mixed.validation.SEEDS}
        self.assertTrue(set(mixed.DEVELOPMENT).isdisjoint(mixed.REVIEW))
        self.assertTrue(set((*mixed.DEVELOPMENT, *mixed.REVIEW)).isdisjoint(historical))
        self.assertEqual(len(mixed.conditions(mixed.DEVELOPMENT)), 8)
        self.assertEqual(1 + mixed.GENERATIONS * mixed.OFFSPRING, 10)

    def test_missing_extra_and_wrong_schedule_rejected(self):
        good = worlds(mixed.DEVELOPMENT)
        for name in ("missing", "extra", "wrong"):
            bad = copy.deepcopy(good)
            if name != "extra":
                value = bad.pop(next(iter(bad)))
            if name != "missing":
                bad["fresh-3.unknown"] = value if name == "wrong" else next(iter(good.values()))
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                mixed.aggregate(bad, mixed.DEVELOPMENT)

    def test_seed_omission_removes_both_schedules(self):
        a = worlds(mixed.REVIEW)
        result = mixed.comparison(a, a, mixed.REVIEW)
        self.assertEqual(result["overall"]["paired_counts"], {"wins": 0, "ties": 8, "losses": 0})
        for seed, group in result["leave_one_world_seed_out"].items():
            self.assertEqual(len(group["pairs"]), 6)
            self.assertTrue(all(not p["condition"].endswith(seed) for p in group["pairs"]))
        self.assertTrue(all(len(g["pairs"]) == 4 for g in result["schedules"].values()))

    def test_terminal_tier_precedes_renewal_and_diversity(self):
        a, b = worlds(mixed.REVIEW), worlds(mixed.REVIEW)
        first = b[next(iter(b))]
        first["evaluation"]["key"][0] = 0
        first["evaluation"]["key"][1] += 10000000
        first["terminal_species"] = {"flower": 1, "shrub": 1, "ground-cover": 1}
        result = mixed.comparison(a, b, mixed.REVIEW)
        self.assertEqual(result["overall"]["comparison"], -1)

    def test_diversity_is_not_a_tie_breaker(self):
        a, b = worlds(mixed.DEVELOPMENT), worlds(mixed.DEVELOPMENT)
        for w in b.values():
            w["terminal_species"] = {"flower": 1, "shrub": 1, "ground-cover": 1}
        parent = {"id": "parent", "aggregate": mixed.aggregate(a, mixed.DEVELOPMENT)}
        child = {"id": "child", "aggregate": mixed.aggregate(b, mixed.DEVELOPMENT)}
        self.assertIs(mixed.pilot.select(parent, [child]), parent)
        self.assertNotEqual(mixed.diversity(a), mixed.diversity(b))

    def test_equal_better_offspring_keep_first_in_order(self):
        a, b = worlds(mixed.DEVELOPMENT), worlds(mixed.DEVELOPMENT)
        b[next(iter(b))]["evaluation"]["key"][1] += 15
        parent = {"aggregate": mixed.aggregate(a, mixed.DEVELOPMENT)}
        first = {"aggregate": mixed.aggregate(b, mixed.DEVELOPMENT)}
        second = copy.deepcopy(first)
        self.assertIs(mixed.pilot.select(parent, [first, second]), first)


class SearchTests(unittest.TestCase):
    def run_fake(self, study=mixed.MIXED):
        """Keep real orchestration/selection; substitute only expensive native work."""
        a = worlds(study.development)
        def mutate(args, target):
            before = Path(args[1]).read_text()
            after = Path(args[2]).stem
            Path(args[2]).write_text(after)
            return {"before": before, "after": after, "rng_before": args[3], "rng_after": args[3] + 1}, 0

        seen = []
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "input").mkdir()
            (root / "input/initial.tgm").write_text("initial")
            with patch.object(mixed, "evaluate", side_effect=lambda *args, **kwargs: copy.deepcopy(a)), \
                 patch.object(mixed.pilot, "run_json", side_effect=mutate), \
                 patch.object(mixed.pilot, "model_crc", side_effect=lambda p: p.read_text()):
                captured = mixed.search(root, root / "search", [], lambda g, c: seen.append((g, c)), study=study)
                repeated = mixed.search(root, root / "repeat", [], study=study)
        self.assertEqual(captured, repeated)
        self.assertEqual(seen, [(g, "initial") for g in range(4)])
        mixed.check_search(captured, study=study)
        return captured

    def test_capture_callback_and_unchanged_champions(self):
        result = self.run_fake()
        self.assertEqual(result["champions"], ["initial"] * 4)
        self.assertEqual(result["rng_after"], mixed.RNG + 9)

    def test_corrupt_parent_rng_champion_and_budget_rejected(self):
        result = self.run_fake()
        for failure in ("parent", "rng", "champion", "budget", "score"):
            bad = copy.deepcopy(result)
            if failure == "parent":
                bad["candidates"][2]["parent"] = "g1-c1"
            elif failure == "rng":
                bad["candidates"][3]["mutation"]["rng_before"] += 1
            elif failure == "champion":
                bad["champions"][1] = "g1-c1"
            elif failure == "budget":
                bad["candidates"].pop()
            else:
                bad["candidates"][1]["aggregate"]["key"][2] += 15
            with self.subTest(failure=failure), self.assertRaises(RuntimeError):
                mixed.check_search(bad)

    def test_review_diagnostics_cannot_select_a_champion(self):
        result = self.run_fake()
        original = copy.deepcopy(result)
        reviews = [{"worlds": worlds(mixed.REVIEW)} for _ in range(4)]
        for w in reviews[3]["worlds"].values():
            w["evaluation"]["key"][1] += 999999
        self.assertEqual(mixed.diagnostics(result, reviews)[3]["review"]["overall"]["comparison"], 1)
        self.assertEqual(result, original)
        mixed.check_search(result)

    def test_broader_search_keeps_budget_and_requires_all_sixteen_conditions(self):
        result = self.run_fake(mixed.COVERAGE)
        self.assertEqual(len(result["candidates"]), 10)
        self.assertTrue(all(len(c["worlds"]) == 16 for c in result["candidates"]))
        with self.assertRaises(RuntimeError):
            mixed.check_search(result)
        for c in result["candidates"]:
            c["worlds"].pop(next(iter(c["worlds"])))
        with self.assertRaises(RuntimeError):
            mixed.check_search(result, study=mixed.COVERAGE)

    def test_coverage_diagnostics_separate_seed_blocks_and_fixed_reference(self):
        result = self.run_fake(mixed.COVERAGE)
        reviews = [{"worlds": worlds(mixed.COVERAGE.review)} for _ in range(4)]
        narrow = {"worlds": worlds(mixed.COVERAGE.review)}
        for w in narrow["worlds"].values():
            w["evaluation"]["key"][1] += 99999
        before = copy.deepcopy(result)
        d = mixed.coverage_diagnostics(result, reviews, narrow)
        for g in d:
            self.assertEqual(g["versus_narrow_review"]["overall"]["comparison"], -1)
            for name in ("original_training_seeds", "added_training_seeds"):
                self.assertEqual(len(g[name]["overall"]["pairs"]), 8)
            old = {p["condition"] for p in g["original_training_seeds"]["overall"]["pairs"]}
            added = {p["condition"] for p in g["added_training_seeds"]["overall"]["pairs"]}
            self.assertTrue(old.isdisjoint(added))
        self.assertEqual(result, before)


class StudyTests(unittest.TestCase):
    def test_fixed_coverage_split_and_fresh_review(self):
        self.assertEqual(mixed.COVERAGE.development[:4], mixed.DEVELOPMENT)
        self.assertEqual(mixed.COVERAGE.development[4:], tuple(mixed.experiment.trial_seeds(0x636F7664, 4)))
        self.assertEqual(mixed.COVERAGE.review, tuple(mixed.experiment.trial_seeds(0x62727631, 4)))
        previous = {*mixed.DEVELOPMENT, *mixed.REVIEW, *mixed.validation.SEEDS,
                    *mixed.pilot.DEVELOPMENT, *mixed.pilot.REVIEW}
        self.assertTrue(set(mixed.COVERAGE.development[4:]).isdisjoint(previous))
        self.assertTrue(set(mixed.COVERAGE.review).isdisjoint(previous | set(mixed.COVERAGE.development)))
        self.assertEqual(len(set(mixed.COVERAGE.development)), 8)

    def test_profiles_are_immutable_and_old_default_is_preserved(self):
        from dataclasses import FrozenInstanceError
        self.assertEqual(mixed.study_for_rule(mixed.RULE), mixed.MIXED)
        self.assertEqual(mixed.study_for_rule(mixed.COVERAGE.rule), mixed.COVERAGE)
        with self.assertRaises(RuntimeError):
            mixed.study_for_rule("unknown")
        with self.assertRaises(FrozenInstanceError):
            mixed.COVERAGE.name = "changed"
        record = mixed.COVERAGE.record()
        record["development"].clear()
        self.assertEqual(len(mixed.COVERAGE.development), 8)
        self.assertEqual(mixed.MIXED.development, mixed.DEVELOPMENT)
        self.assertEqual(mixed.review_name("narrow"), "narrow")
        self.assertEqual(mixed.review_name(0), "g0")


if __name__ == "__main__":
    unittest.main()
