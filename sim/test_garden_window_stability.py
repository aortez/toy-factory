#!/usr/bin/env python3
"""Projection, fixed deadlines and independent window arithmetic; no native trials."""
import copy
import unittest

import garden_window_stability as windows

fitness, DAY, STEP = windows.fitness, windows.DAY, windows.STEP


class ProjectionTests(unittest.TestCase):
    def score(self, f, start=4 * DAY, end=8 * DAY, source_start=4 * DAY, source_stop=10 * DAY):
        return windows.score_window(f["lineages"], f["seeds"], start, end, source_start, source_stop)

    def test_all_eighteen_arithmetic_fixtures_and_primary_identity(self):
        fixtures = fitness.arithmetic_fixtures()
        self.assertEqual(len(fixtures), 18)
        for name, f in fixtures.items():
            before = copy.deepcopy(f)
            with self.subTest(name=name):
                value = self.score(f)
                self.assertEqual(value["evaluation"], f["evaluation"])
                self.assertEqual(value["evaluation"]["key"], windows.direct_key(f["lineages"], f["seeds"], 4 * DAY, 8 * DAY))
                self.assertEqual(f, before)

    def future_fixture(self, death):
        return fitness.fixture([(1, 0, 0, None, False), (2, 1, DAY, None, False),
                                (3, 2, 5 * DAY, death, death is not None),
                                (4, 2, 9 * DAY, None, False)], extra=[(2, 7 * DAY + DAY // 2)])

    def test_earlier_deadline_hides_future_death_birth_purchase_and_seed_resolution(self):
        f = self.future_fixture(9 * DAY)
        original = copy.deepcopy(f)
        plants, seeds = fitness.project(f["lineages"], f["seeds"], 2 * DAY, 8 * DAY, 4 * DAY, 10 * DAY)
        self.assertEqual([p["id"] for p in plants], [1, 2, 3])
        self.assertIsNone(plants[2]["death_tick"])
        self.assertFalse(plants[2]["environmental_death"])
        pending = [s for s in seeds if s["outcome"] == "pending"]
        self.assertEqual(len(pending), 1)
        self.assertIsNone(pending[0]["end_tick"])
        self.assertIsNone(pending[0]["child_id"])
        parent = next(p for p in plants if p["id"] == 2)
        self.assertEqual(parent["seeds_created"], 2)
        self.assertEqual(parent["late_seeds_created"], 2)
        a = self.score(f, 2 * DAY, 6 * DAY)
        b = self.score(self.future_fixture(None), 2 * DAY, 6 * DAY)
        self.assertEqual(a, b)
        self.assertEqual(a["evaluation"]["key"][1], STEP)
        self.assertEqual(f, original)

    def test_corrupt_original_counter_is_rejected_before_recount(self):
        f = self.future_fixture(None)
        f["lineages"][1]["late_seeds_created"] += 1
        with self.assertRaises(RuntimeError):
            self.score(f, 2 * DAY, 6 * DAY)

    def test_earlier_seed_only_endpoint_cannot_use_later_recovery(self):
        f = fitness.fixture([(1, 0, 0, 8 * DAY, False), (2, 1, 8 * DAY + 90, None, False)])
        # At day eight the founder is dead and its seed is still pending; by day
        # ten the child is established. Each window must use its own deadline.
        early = self.score(f, 2 * DAY, 6 * DAY)
        primary = self.score(f)
        self.assertEqual(early["evaluation"]["key"][0], 0)
        self.assertEqual(early["evaluation"]["terminal"]["classification"], "seed-only-unconfirmed")
        self.assertEqual(primary["evaluation"]["key"][0], 1)

    def test_deadline_death_and_expiry_are_included(self):
        f = fitness.fixture([(1, 0, 0, 8 * DAY, False)], extra=[(1, 7 * DAY)])
        value = self.score(f, 2 * DAY, 6 * DAY)
        self.assertEqual(value["evaluation"]["key"], [-1, 0, 0, 0, 0])

    def test_confirmation_start_excluded_end_included_and_death_boundary(self):
        for death, credited in ((6 * DAY, 0), (6 * DAY + STEP, STEP), (None, STEP)):
            f = fitness.fixture([(1, 0, 0, None, False), (2, 1, DAY, None, False),
                                 (3, 2, 5 * DAY, death, False)])
            with self.subTest(death=death):
                self.assertEqual(self.score(f, 2 * DAY, 6 * DAY)["evaluation"]["key"][1], credited)
                self.assertEqual(self.score(f, 6 * DAY, 8 * DAY)["evaluation"]["key"][1], 0)

    def test_unavailable_followup_and_unaligned_or_reversed_window_rejected(self):
        f = self.future_fixture(None)
        for start, end in ((8 * DAY, 9 * DAY), (2 * DAY + 1, 6 * DAY), (6 * DAY, 2 * DAY)):
            with self.subTest(start=start, end=end), self.assertRaises(RuntimeError):
                self.score(f, start, end)


class TransitionTests(unittest.TestCase):
    def test_entering_leaving_retained_contributions_reconcile(self):
        f = fitness.fixture([(1, 0, 0, None, False), (2, 1, DAY, None, False),
                             (3, 2, 2 * DAY, None, False),
                             (4, 2, 4 * DAY, 6 * DAY + STEP, False),
                             (5, 2, 6 * DAY, None, False)])
        score = lambda start, end: windows.score_window(f["lineages"], f["seeds"], start, end, 4 * DAY, 10 * DAY)
        a, b = score(2 * DAY, 6 * DAY), score(4 * DAY, 8 * DAY)
        c = windows.contributions(a, b)
        self.assertEqual([p["id"] for p in c["children"]["leaving"]], [3])
        self.assertEqual([p["id"] for p in c["children"]["retained"]], [4])
        self.assertEqual([p["id"] for p in c["children"]["entering"]], [5])
        self.assertEqual(c["ticks"]["retained"], 0)
        self.assertEqual(sum(c["ticks"].values()), b["evaluation"]["key"][1] - a["evaluation"]["key"][1])
        b["evaluation"]["key"][1] += STEP
        with self.assertRaises(RuntimeError):
            windows.contributions(a, b)

    def test_same_world_window_has_zero_changes(self):
        f = fitness.arithmetic_fixtures()["steady-offspring"]
        value = windows.score_window(f["lineages"], f["seeds"], 4 * DAY, 8 * DAY, 4 * DAY, 10 * DAY)
        c = windows.contributions(value, copy.deepcopy(value))
        self.assertEqual(c["renewal_delta"], 0)
        self.assertEqual(c["ticks"], {"entering": 0, "leaving": 0, "retained": 0})

    def test_fixed_windows_stability_tracks_signs_and_ties_without_reranking(self):
        signs = [-1, 1, 0, 1, -1]
        cases = [{"days": list(days), "comparisons": {name: {"overall": {"comparison": sign}}
                                                        for name in windows.PAIRS}}
                 for days, sign in zip(windows.WINDOWS, signs, strict=True)]
        result = windows.stability(cases)
        for r in result.values():
            self.assertEqual(r, {"signs": signs, "primary": -1, "adjacent_changes": 4,
                                 "opposite_to_primary": 2, "ties": 1})
        with self.assertRaises(RuntimeError):
            windows.stability(cases[:-1])
        with self.assertRaises(RuntimeError):
            windows.stability(list(reversed(cases)))

    def test_protocol_clocks_and_model_budget(self):
        self.assertEqual(windows.WINDOWS[-1], (158, 190))
        self.assertTrue(all(end - start == 32 and end + 2 <= 192 for start, end in windows.WINDOWS))
        self.assertEqual(len(windows.MODELS) * len(windows.mixed.conditions(windows.SEEDS)) * len(windows.WINDOWS), 160)
        self.assertEqual(len(windows.PAIRS), 5)


if __name__ == "__main__":
    unittest.main()
