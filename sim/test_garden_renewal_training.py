#!/usr/bin/env python3
"""Opt-in scoring and real pilot orchestration with controlled native boundaries."""
import copy
from dataclasses import FrozenInstanceError
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_renewal_training as study

mixed, pilot, DAY = study.mixed, study.pilot, study.pilot.DAY


def fixture(name):
    founder, parent = (1, 0, 0, None, False), (2, 1, DAY, None, False)
    if name == "sterile":
        plants = [founder, parent, (3, 2, 3*DAY, None, False)]
    elif name == "steady":
        plants = [founder, parent, *[(i+3, 2, (62+32*i)*DAY, None, False) for i in range(4)]]
    elif name == "late-burst":
        plants = [founder, parent, *[(i+3, 2, 158*DAY+15*i, None, False) for i in range(20)]]
    elif name == "extinct":
        plants = [(1, 0, 0, 189*DAY, False)]
    elif name == "unconfirmed":
        plants = [founder, parent, (3, 2, 70*DAY, 71*DAY, False)]
    else:
        raise ValueError(name)
    f = pilot.fitness.fixture(plants, start=pilot.START, end=pilot.END)
    f.update(start=pilot.START, end=pilot.END, stop=pilot.STOP)
    return f


def world(name):
    value = fixture(name)
    return study.Objective("renewal").annotate(value, {"evaluation": value["evaluation"]})


def panel(name, seeds=study.STUDY.development):
    w = world(name)
    return {k: copy.deepcopy(w) for k, *_ in mixed.conditions(seeds)}


class ObjectiveTests(unittest.TestCase):
    def test_fixed_budget_and_new_review_split(self):
        s = study.settings()
        self.assertEqual(study.STUDY.development, mixed.COVERAGE.development)
        self.assertEqual(len(mixed.conditions(study.REVIEW)), 8)
        previous = {*mixed.DEVELOPMENT, *mixed.REVIEW, *mixed.COVERAGE.development,
                    *mixed.COVERAGE.review, *pilot.DEVELOPMENT, *pilot.REVIEW, *mixed.validation.SEEDS}
        self.assertTrue(set(study.REVIEW).isdisjoint(previous))
        self.assertEqual(sum(v for k, v in s["budget"].items() if k != "native_processes"), 868)
        self.assertEqual((mixed.GENERATIONS, mixed.OFFSPRING, mixed.MUTATIONS, mixed.RNG), (3, 3, 32, 0x6D697833))

    def test_native_budget_rejects_extra_calls_and_interventions(self):
        timing = {"arms": {arm: [{"command": [f"bin/{name}"]}
            for name, count in (("garden-persistence-trial", 352), ("garden-replay", 64), ("garden-model-mutate", 18))
            for _ in range(count)] for arm in study.ARMS}}
        study.check_budget(timing)
        bad = copy.deepcopy(timing)
        bad["arms"]["v2"].pop()
        with self.assertRaises(RuntimeError):
            study.check_budget(bad)
        timing["arms"]["v2"][0]["command"].append("--founder-exit")
        with self.assertRaises(RuntimeError):
            study.check_budget(timing)

    def test_unknown_and_mutated_objectives_rejected(self):
        with self.assertRaises(RuntimeError):
            study.Objective("mystery")
        with self.assertRaises(FrozenInstanceError):
            study.Objective("renewal").name = "v2"

    def test_default_and_explicit_v2_keep_existing_score(self):
        worlds = panel("steady")
        expected = mixed.aggregate(worlds, study.STUDY.development)
        self.assertEqual(mixed.selection_aggregate(worlds, study.STUDY.development), expected)
        self.assertEqual(study.Objective("v2").aggregate(worlds, study.STUDY.development), expected)
        self.assertEqual(mixed.study_for_rule(mixed.RULE), mixed.MIXED)

    def test_annotation_is_non_mutating_and_uses_tested_history(self):
        t = fixture("steady")
        old = copy.deepcopy(t)
        ordinary = {"evaluation": t["evaluation"]}
        result = study.Objective("renewal").annotate(t, ordinary)
        self.assertEqual(t, old)
        self.assertEqual(set(ordinary), {"evaluation"})
        self.assertEqual(result["renewal_history"], study.rolling.history(t["lineages"], t["seeds"], pilot.START, pilot.STOP))

    def test_reject_interventions_changed_horizon_and_primary_score(self):
        for failure in ("founder_exit", "gap_protocol", "root_bootstrap_rule", "stop", "start", "primary"):
            t = fixture("steady")
            ordinary = {"evaluation": copy.deepcopy(t["evaluation"])}
            if failure in ("stop", "start"):
                t[failure] -= 15
            elif failure == "primary":
                ordinary["evaluation"]["key"][1] += 15
            else:
                t[failure] = {}
            with self.subTest(failure=failure), self.assertRaises(RuntimeError):
                study.Objective("renewal").annotate(t, ordinary)

    def test_missing_extra_and_incomplete_panels_fail(self):
        for failure in ("missing", "extra", "legacy", "followup", "contract"):
            w = panel("steady")
            first = next(iter(w))
            if failure == "missing":
                w.pop(first)
            elif failure == "extra":
                w["wrong.world"] = w[first]
            elif failure == "legacy":
                w[first]["evaluation"].update(status="needs-followup", key=None)
            elif failure == "followup":
                w[first]["renewal_history"]["blocks"][0]["followup_deadline"] -= 15
            else:
                w[first]["renewal_history"]["credit_age_ticks"] += 15
            with self.subTest(failure=failure), self.assertRaises(RuntimeError):
                study.Objective("renewal").aggregate(w, study.STUDY.development)

    def test_different_objectives_choose_different_behaviors(self):
        steady, burst = panel("steady"), panel("late-burst")
        for arm, expected in (("v2", "burst"), ("renewal", "steady")):
            obj = study.Objective(arm)
            parent = {"id": "steady", "aggregate": obj.aggregate(steady, study.STUDY.development)}
            child = {"id": "burst", "aggregate": obj.aggregate(burst, study.STUDY.development)}
            self.assertEqual(pilot.select(parent, [child])["id"], expected)

    def test_unchanged_ties_and_first_equal_better_child(self):
        obj = study.Objective("renewal")
        a = {"id": "parent", "aggregate": obj.aggregate(panel("sterile"), study.STUDY.development)}
        b = {"id": "first", "aggregate": obj.aggregate(panel("steady"), study.STUDY.development)}
        c = {"id": "second", "aggregate": copy.deepcopy(b["aggregate"])}
        self.assertIs(pilot.select(a, [copy.deepcopy(a)]), a)
        self.assertIs(pilot.select(a, [b, c]), b)

    def test_cross_objective_comparison_is_rejected(self):
        p = panel("steady")
        a, b = (study.Objective(arm).aggregate(p, study.STUDY.development) for arm in study.ARMS)
        with self.assertRaises(RuntimeError):
            pilot.fitness.compare(a, b)

    def test_survival_precedes_productivity_without_zero_gap_gate(self):
        obj = study.Objective("renewal")
        living, failed = panel("sterile"), panel("late-burst")
        failed[next(iter(failed))] = world("extinct")
        a, b = (obj.aggregate(p, study.STUDY.development) for p in (living, failed))
        self.assertEqual(a["key"], [1, 64, 0, 0])
        self.assertGreater(b["key"][-1], a["key"][-1])
        self.assertGreater(pilot.fitness.compare(a, b), 0)
        self.assertEqual(obj.aggregate(panel("unconfirmed"), study.STUDY.development)["key"][-1], 0)

    def test_diagnostics_use_matched_pairs_and_do_not_modify_inputs(self):
        a, b = panel("sterile", study.REVIEW), panel("steady", study.REVIEW)
        old = copy.deepcopy((a, b))
        result = study.comparison(a, b, study.REVIEW)
        self.assertEqual((a, b), old)
        for view in ("v2", "renewal"):
            self.assertEqual(result[view]["overall"]["paired_counts"], {"wins": 8, "ties": 0, "losses": 0})
            for seed, group in result[view]["leave_one_world_seed_out"].items():
                self.assertEqual(len(group["pairs"]), 6)
                self.assertTrue(all(not p["condition"].endswith(seed) for p in group["pairs"]))


class SearchTests(unittest.TestCase):
    def test_actual_orchestrator_opt_in_parent_rng_review_and_repeat(self):
        cached = {n: panel(n) for n in ("sterile", "steady", "late-burst")}
        def evaluate(root, folder, name, model, seeds, timings, *, objective=None, patches=mixed.PATCHES):
            label = "late-burst" if name == "g1-c1" else "steady" if name == "g1-c2" else "sterile"
            return copy.deepcopy(cached[label])
        def mutate(args, target):
            before, after = Path(args[1]).read_text(), Path(args[2]).stem
            Path(args[2]).write_text(after)
            return {"before": before, "after": after, "rng_before": args[3], "rng_after": args[3]+1}, 0
        for arm, winner in (("v2", "g1-c1"), ("renewal", "g1-c2")):
            objective = study.Objective(arm)
            reviews = []
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root/"input").mkdir()
                (root/"input/initial.tgm").write_text("initial")
                with patch.object(mixed, "evaluate", side_effect=evaluate), \
                     patch.object(pilot, "run_json", side_effect=mutate), \
                     patch.object(pilot, "model_crc", side_effect=lambda p: p.read_text()):
                    a = mixed.search(root, root/"search", [], lambda g, c: reviews.append((g, c)), study=study.STUDY, objective=objective)
                    b = mixed.search(root, root/"repeat", [], study=study.STUDY, objective=objective)
            self.assertEqual(a, b)
            self.assertEqual(a["champions"], ["initial", winner, winner, winner])
            self.assertEqual(reviews, list(enumerate(a["champions"])))
            self.assertEqual(a["rng_after"], mixed.RNG+9)
            self.assertTrue(all(c["parent"] == winner for c in a["candidates"][4:]))
            mixed.check_search(a, study=study.STUDY, objective=objective)
            bad = copy.deepcopy(a)
            bad["champions"][1] = "g1-c3"
            with self.assertRaises(RuntimeError):
                mixed.check_search(bad, study=study.STUDY, objective=objective)
            if arm == "renewal":
                with self.assertRaises(RuntimeError):
                    mixed.check_search(a, study=study.STUDY)


if __name__ == "__main__":
    unittest.main()
