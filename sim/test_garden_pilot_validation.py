#!/usr/bin/env python3
"""Cohort attribution and fixed-panel pairing checks; no new native runs."""
import copy
import unittest

import garden_pilot_validation as validation

fitness, DAY, STEP = validation.fitness, validation.DAY, validation.fitness.STEP


class CohortTests(unittest.TestCase):
    def inspect(self, f):
        return validation.cohorts(f["lineages"], f["seeds"], f["evaluation"])

    def test_all_arithmetic_fixtures_reconcile(self):
        for name, f in fitness.arithmetic_fixtures().items():
            with self.subTest(name=name):
                c = self.inspect(f)
                self.assertEqual(c["live_ticks"], f["evaluation"]["key"][1])
                self.assertEqual(c["available_ticks"] - c["lost_ticks"], c["live_ticks"])

    def test_brief_offspring_have_observed_losses(self):
        f = fitness.arithmetic_fixtures()["brief-established-offspring"]
        c = self.inspect(f)
        self.assertEqual(c["credited_children"], 4)
        self.assertEqual(c["live_ticks"], 60)
        self.assertEqual(c["credited_main_end_states"], {"natural-dead": 4})
        self.assertGreater(c["lost_ticks"], c["live_ticks"])

    def test_exact_confirmation_bins_and_parent_classes(self):
        f = fitness.fixture([(1, 0, 0, None, False), (2, 1, DAY, None, False),
                             (3, 2, 4 * DAY, None, False), (4, 2, 4 * DAY + STEP, None, False),
                             (5, 2, 7 * DAY, None, False)])
        c = self.inspect(f)
        self.assertEqual([b["credited_children"] for b in c["confirmation_bins"]], [1, 1, 0, 1])
        self.assertEqual(c["children"][-1]["live_ticks"], STEP)
        self.assertEqual(c["lost_ticks"], 0)
        founder_child = fitness.fixture([(1, 0, 0, None, False), (2, 1, 5 * DAY, None, False)])
        self.assertEqual(self.inspect(founder_child)["children"][0]["parent_class"], "founder")
        self.assertEqual(self.inspect(founder_child)["credited_children"], 0)

    def test_failed_child_does_not_misclassify_parent(self):
        f = fitness.fixture([(1, 0, 0, None, False), (2, 1, DAY, None, False),
                             (3, 2, 5 * DAY, 6 * DAY, True)])
        c = self.inspect(f)
        self.assertEqual(c["confirmation_cohort"], {"patch-censored": 1})
        self.assertEqual(c["children"][0]["parent_class"], "established-descendant")
        self.assertEqual(c["live_ticks"], 0)

    def test_changed_score_rejected(self):
        f = fitness.arithmetic_fixtures()["steady-offspring"]
        f["evaluation"]["key"][1] += STEP
        with self.assertRaises(RuntimeError):
            self.inspect(f)


class PanelTests(unittest.TestCase):
    def setUp(self):
        score = fitness.arithmetic_fixtures()["steady-offspring"]["evaluation"]
        self.cases = [{"schedule": a, "seed": s, "side": side, "evaluation": copy.deepcopy(score)}
                      for a in validation.PATCHES for s in validation.SEEDS for side in validation.MODELS]

    def test_complete_tied_panel_and_blocked_omissions(self):
        summary = validation.summarize(self.cases)
        self.assertEqual(summary["paired_counts"], {"wins": 0, "losses": 0, "ties": 16})
        self.assertEqual(len(summary["leave_one_world_seed_out"]), 8)
        for leave in summary["leave_one_world_seed_out"].values():
            self.assertEqual(leave["control"]["key"][1], 14)
        for bad in (self.cases[:-1], [*self.cases[:-1], self.cases[0]]):
            with self.assertRaises(RuntimeError):
                validation.summarize(bad)

    def test_first_differing_component_decides_pair(self):
        self.cases[1]["evaluation"]["key"][0] = 0
        self.cases[1]["evaluation"]["key"][1] += 999999
        summary = validation.summarize(self.cases)
        self.assertEqual(summary["paired_counts"]["losses"], 1)
        self.assertEqual(summary["overall"]["comparison"], -1)

    def test_visual_selection_ties_are_lexical(self):
        summary = validation.summarize(list(reversed(self.cases)))
        self.assertTrue(all(s["seed"] == min(validation.SEEDS) for s in summary["selected"]))

    def test_fixed_seeds_and_schedules(self):
        from garden_diversity import SCHEDULES
        self.assertEqual(tuple(validation.experiment.trial_seeds(0x70616972, 8)), validation.SEEDS)
        self.assertTrue(set(validation.SEEDS).isdisjoint((*validation.pilot.DEVELOPMENT, *validation.pilot.REVIEW)))
        self.assertTrue(all(f"{SCHEDULES[a]:08x}" == v for a, v in validation.PATCHES.items()))


if __name__ == "__main__":
    unittest.main()
