#!/usr/bin/env python3
"""Candidate semantics and failure-mode tests; no native executable is invoked."""
import copy
import unittest

import garden_sustained_renewal as sustained

fitness, DAY, STEP = sustained.fitness, sustained.DAY, sustained.STEP


class CreditTests(unittest.TestCase):
    def fixture(self, child_birth=5 * DAY, child_death=None, parent_death=None, end=40 * DAY):
        return fitness.fixture([(1, 0, 0, None, False), (2, 1, DAY, parent_death, False),
                                (3, 2, child_birth, child_death, False)], start=4 * DAY, end=end)

    def test_all_eighteen_existing_fixtures_preserve_scores_and_inputs(self):
        fixtures = fitness.arithmetic_fixtures()
        self.assertEqual(len(fixtures), 18)
        for name, f in fixtures.items():
            with self.subTest(name=name):
                original = copy.deepcopy(f)
                b, old = sustained.score_block(f["lineages"], f["seeds"], 4 * DAY, 8 * DAY, 4 * DAY, 10 * DAY)
                self.assertEqual(old, f["evaluation"])
                self.assertEqual(b["rolling"]["ticks"], sustained.sampled_credit(f["lineages"], 4 * DAY, 8 * DAY))
                self.assertEqual(f, original)

    def test_confirmation_and_age_cap_have_exactly_32_days_of_credit(self):
        f = self.fixture()
        value = sustained.credit(f["lineages"], 4 * DAY, 40 * DAY)
        self.assertEqual(value["ticks"], 32 * DAY)
        child = value["children"][0]
        self.assertEqual(child["first_sample"], 6 * DAY)
        self.assertEqual(child["last_live_sample"], 38 * DAY - STEP)
        self.assertEqual(sustained.credit(f["lineages"], 38 * DAY - STEP, 38 * DAY)["ticks"], 0)
        self.assertEqual(sustained.credit(f["lineages"], 6 * DAY - STEP, 6 * DAY)["ticks"], STEP)

    def test_start_confirmation_is_carry_in_and_end_confirmation_counts_once(self):
        f = self.fixture()
        a, _ = sustained.score_block(f["lineages"], f["seeds"], 6 * DAY, 8 * DAY, 4 * DAY, 42 * DAY)
        self.assertEqual(a["v2_key"][1], 0)
        self.assertEqual(a["rolling"]["carry_in_ticks"], 2 * DAY)
        b, _ = sustained.score_block(f["lineages"], f["seeds"], 4 * DAY, 6 * DAY, 4 * DAY, 42 * DAY)
        self.assertEqual(b["rolling"]["fresh_ticks"], STEP)

    def test_death_at_confirmation_fails_and_next_sample_death_credits_once(self):
        for death, expected in ((6 * DAY, 0), (6 * DAY + STEP, STEP), (7 * DAY, DAY)):
            f = self.fixture(child_death=death)
            value = sustained.credit(f["lineages"], 4 * DAY, 8 * DAY)
            self.assertEqual(value["ticks"], expected)
            self.assertEqual(value["ticks"] + value["death_lost_ticks"], value["available_ticks"])

    def test_parent_can_die_after_qualifying_without_revoking_child_credit(self):
        alive = self.fixture()
        dead = self.fixture(parent_death=5 * DAY + STEP)
        self.assertEqual(sustained.credit(alive["lineages"], 4 * DAY, 8 * DAY),
                         sustained.credit(dead["lineages"], 4 * DAY, 8 * DAY))

    def test_unconfirmed_parent_cannot_earn_credit_via_surviving_child(self):
        # A seed purchased during the parent's first day, then both a parent
        # confirmation-boundary death and a successfully established child.
        f = self.fixture(child_birth=2 * DAY - STEP, parent_death=2 * DAY)
        self.assertEqual(sustained.credit(f["lineages"], 4 * DAY, 8 * DAY)["ticks"], 0)

    def test_arbitrary_partitions_are_additive_and_shift_changes_only_edge_samples(self):
        f = self.fixture(child_death=37 * DAY + STEP)
        cuts = [4 * DAY, 6 * DAY, 6 * DAY + STEP, 18 * DAY, 37 * DAY, 38 * DAY, 40 * DAY]
        total = sum(sustained.credit(f["lineages"], a, b)["ticks"] for a, b in zip(cuts, cuts[1:]))
        self.assertEqual(total, sustained.credit(f["lineages"], cuts[0], cuts[-1])["ticks"])
        # Confirmation exactly at the old end was counted; advancing a single
        # sample adds one credit, rather than reclassifying the entire cohort.
        for start, end in ((4 * DAY, 6 * DAY), (6 * DAY - STEP, 8 * DAY), (7 * DAY, 38 * DAY)):
            before = sustained.credit(f["lineages"], start, end)["ticks"]
            after = sustained.credit(f["lineages"], start + STEP, end + STEP)["ticks"]
            removed = sustained.credit(f["lineages"], start, start + STEP)["ticks"]
            added = sustained.credit(f["lineages"], end, end + STEP)["ticks"]
            self.assertEqual(after - before, added - removed)

    def test_future_death_birth_and_seed_outcomes_do_not_leak(self):
        a = self.fixture(child_death=9 * DAY, end=10 * DAY)
        b = self.fixture(end=10 * DAY)
        score = lambda f: sustained.score_block(f["lineages"], f["seeds"], 2 * DAY, 6 * DAY, 4 * DAY, 12 * DAY)
        self.assertEqual(score(a), score(b))
        f = fitness.arithmetic_fixtures()["seed-only-recovered"]
        early, _ = sustained.score_block(f["lineages"], f["seeds"], 2 * DAY, 6 * DAY, 4 * DAY, 10 * DAY)
        self.assertEqual(early["v2_key"][0], 0)
        self.assertEqual(early["terminal"]["classification"], "seed-only-unconfirmed")

    def test_invalid_counters_clocks_and_missing_followup_are_rejected(self):
        f = self.fixture()
        f["lineages"][1]["late_seeds_created"] += 1
        with self.assertRaises(RuntimeError):
            sustained.score_block(f["lineages"], f["seeds"], 2 * DAY, 6 * DAY, 4 * DAY, 42 * DAY)
        f = self.fixture()
        for start, end, stop in ((0, 40 * DAY, 42 * DAY), (4 * DAY, 8 * DAY, 9 * DAY),
                                 (6 * DAY, 4 * DAY, 42 * DAY), (4 * DAY + 1, 8 * DAY, 42 * DAY)):
            with self.subTest(start=start, end=end, stop=stop), self.assertRaises(RuntimeError):
                sustained.score_block(f["lineages"], f["seeds"], start, end, 4 * DAY, stop)


class PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = sustained.arithmetic_cases()

    def key(self, name):
        return self.cases[name]["aggregate"]["key"]

    def test_steady_beats_burst_despite_lower_total(self):
        steady, burst = self.key("steady-replacement"), self.key("large-single-burst")
        self.assertGreater(steady, burst)
        self.assertLess(steady[-1], burst[-1])
        self.assertGreater(steady[2], 0)
        self.assertEqual(burst[2], 0)

    def test_sterile_and_founders_cannot_earn_renewal(self):
        self.assertEqual(self.key("old-sterile"), [1, 4, 0, 0])
        self.assertEqual(self.key("founder-only"), [0, 0, 0, 0])
        self.assertEqual(self.key("pre-confirmation-death"), self.key("old-sterile"))

    def test_seed_only_deadline_tiers_and_recovery_do_not_add_main_credit(self):
        for suffix, tier in (("recovered", 1), ("unconfirmed", 0), ("extinct", -1)):
            blocks = self.cases["seed-only-" + suffix]["history"]["blocks"]
            self.assertEqual(blocks[-1]["v2_key"][0], tier)
            self.assertEqual(sum(b["rolling"]["ticks"] for b in blocks), 0)

    def test_exact_panel_contract_rejects_missing_extra_duplicates_or_incomplete(self):
        h = self.cases["steady-replacement"]["history"]
        for panel, expected in (({}, []), ({"a": h}, ["a", "b"]), ({"a": h, "b": h}, ["a"]),
                                 ({"a": h}, ["a", "a"])):
            with self.assertRaises(RuntimeError):
                sustained.aggregate(panel, expected)
        for mutate in (lambda w: w.update(rule="other"), lambda w: w.update(credit_age_ticks=DAY),
                       lambda w: w["blocks"].reverse(), lambda w: w["blocks"].pop(),
                       lambda w: w["blocks"][0].update(status="needs-followup"),
                       lambda w: w["blocks"][0].update(followup_deadline=192 * DAY)):
            broken = copy.deepcopy(h)
            mutate(broken)
            with self.assertRaises(RuntimeError):
                sustained.aggregate({"a": broken}, ["a"])
        with self.assertRaises(RuntimeError):
            sustained.aggregate({"a": h}, ["a"], "unknown")

    def test_minimum_after_world_sum_can_hide_complementary_slumps(self):
        # Full validated synthetic lifetimes, not merely edited score fields.
        a = self.cases["alternating-a"]["history"]
        b = self.cases["alternating-b"]["history"]
        self.assertEqual([p["rolling"]["ticks"] for p in a["blocks"]], [32 * DAY, 0, 32 * DAY, 0])
        self.assertEqual([p["rolling"]["ticks"] for p in b["blocks"]], [0, 32 * DAY, 0, 32 * DAY])
        score = sustained.aggregate({"a": a, "b": b}, ["a", "b"])
        self.assertEqual(score["key"], [1, 8, 32 * DAY, 128 * DAY])
        self.assertEqual(score["minimum_world_period_ticks"], 0)
        self.assertEqual(score["zero_renewal_world_periods"], 4)
        self.assertEqual(len(score["weakest_periods"]), 4)

    def test_primary_and_multi_views_are_explicit_and_terminal_failure_wins_priority(self):
        h = self.cases["steady-replacement"]["history"]
        self.assertEqual(sustained.aggregate({"a": h}, ["a"], "rolling-primary")["key"],
                         [1, 1, h["blocks"][-1]["rolling"]["ticks"]])
        self.assertEqual(sustained.aggregate({"a": h}, ["a"], "v2-primary")["key"], [1, *h["blocks"][-1]["v2_key"]])
        extinct = copy.deepcopy(h)
        extinct["blocks"][-1]["v2_key"][0] = -1
        self.assertLess(sustained.aggregate({"a": extinct}, ["a"])["key"], self.key("founder-only"))

    def test_fixed_comparisons_preserve_pairs_and_block_omissions(self):
        h = self.cases["steady-replacement"]["history"]
        worlds = {k: h for k, *_ in sustained.mixed.conditions(sustained.SEEDS)}
        for view in sustained.VIEWS:
            result = sustained.comparison(worlds, worlds, view)
            self.assertEqual(result["overall"]["paired_counts"], {"wins": 0, "losses": 0, "ties": 8})
            self.assertEqual(result["overall"]["comparison"], 0)
            self.assertEqual(len(result["schedules"]), 2)
            for seed, pair in result["leave_one_world_seed_out"].items():
                self.assertEqual(len(pair["pairs"]), 6)
                self.assertTrue(all(not p["condition"].endswith(seed) for p in pair["pairs"]))

    def test_declared_budget_and_aligned_contiguous_periods(self):
        self.assertEqual(sustained.PERIODS, ((62, 94), (94, 126), (126, 158), (158, 190)))
        self.assertEqual(len(sustained.MODELS) * len(sustained.mixed.conditions(sustained.SEEDS)) * len(sustained.PERIODS), 128)
        self.assertEqual(len(sustained.PAIRS), 5)
        self.assertEqual(len(sustained.VIEWS), 4)


if __name__ == "__main__":
    unittest.main()
