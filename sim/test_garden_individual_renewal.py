#!/usr/bin/env python3
"""Individual minima, complete panels and compensation challenges; no native runs."""
import copy
import unittest

import garden_individual_renewal as individual

previous, DAY, STEP = individual.previous, individual.DAY, individual.STEP


class IndividualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inherited = previous.arithmetic_cases()
        cls.challenges = individual.arithmetic_cases({"arithmetic_cases": cls.inherited})

    def h(self, name="steady-replacement"):
        return self.inherited[name]["history"]

    def test_all_ten_inherited_single_world_scores_and_inputs_unchanged(self):
        original = copy.deepcopy(self.inherited)
        self.assertEqual(len(self.inherited), 10)
        for name, case in self.inherited.items():
            score = individual.aggregate({"a": case["history"]}, ["a"])
            self.assertEqual(score["key"], case["aggregate"]["key"], name)
            self.assertEqual(score["pooling_gap_ticks"], 0)
        self.assertEqual(self.inherited, original)

    def test_complementary_slumps_lose_the_pooled_continuity_bonus(self):
        score = self.challenges["complementary"]
        self.assertEqual(score["pooled_key"], [1, 8, 32 * DAY, 128 * DAY])
        self.assertEqual(score["key"], [1, 8, 0, 128 * DAY])
        self.assertEqual(score["pooling_gap_ticks"], 32 * DAY)
        self.assertEqual(score["zero_world_periods"], 4)
        self.assertEqual(score["sorted_world_minima"], [0, 0])

    def test_steady_beats_larger_burst_but_compensation_is_still_possible(self):
        a, b = (individual.aggregate({"a": self.h(n)}, ["a"])["key"] for n in
                ("steady-replacement", "large-single-burst"))
        self.assertGreater(a, b)
        self.assertLess(a[3], b[3])
        strong, balanced = (self.challenges[k] for k in ("compensation", "balanced"))
        self.assertGreater(strong["key"], balanced["key"])
        self.assertEqual(strong["zero_minimum_worlds"], ["b"])
        self.assertEqual(balanced["zero_minimum_worlds"], [])
        self.assertEqual(strong["key"][2], 357120)
        self.assertEqual(balanced["key"][2], 238110)

    def test_extinction_tier_precedes_high_renewal(self):
        strong = self.challenges["threefold_fixture"]["history"]
        failed = individual.aggregate({"a": strong, "b": self.h("seed-only-extinct")}, ["a", "b"])
        sterile = individual.aggregate({"a": self.h("old-sterile"), "b": self.h("old-sterile")}, ["a", "b"])
        self.assertGreater(failed["key"][2], sterile["key"][2])
        self.assertLess(failed["key"], sterile["key"])

    def test_missing_extra_empty_duplicate_panels_rejected(self):
        h = self.h()
        for panel, keys in (({}, []), ({"a": h}, ["a", "b"]), ({"a": h, "b": h}, ["a"]),
                            ({"a": h}, ["a", "a"])):
            with self.assertRaises(RuntimeError):
                individual.aggregate(panel, keys)

    def test_wrong_rule_age_window_order_and_incomplete_followup_rejected(self):
        for change in (lambda w: w.update(rule="other"), lambda w: w.update(credit_age_ticks=DAY),
                       lambda w: w["blocks"].reverse(), lambda w: w["blocks"].pop(),
                       lambda w: w["blocks"][0].update(window_ticks=[0, DAY]),
                       lambda w: w["blocks"][0].update(followup_deadline=192 * DAY),
                       lambda w: w["blocks"][0].update(status="needs-followup")):
            h = copy.deepcopy(self.h())
            change(h)
            with self.assertRaises(RuntimeError):
                individual.aggregate({"a": h}, ["a"])

    def test_bad_numeric_credit_and_combined_total_rejected(self):
        for value in (-STEP, 1, True, 15.0):
            h = copy.deepcopy(self.h())
            h["blocks"][0]["rolling"]["ticks"] = value
            h["combined_ticks"] = sum(b["rolling"]["ticks"] for b in h["blocks"])
            with self.assertRaises(RuntimeError):
                individual.aggregate({"a": h}, ["a"])
        h = copy.deepcopy(self.h())
        h["combined_ticks"] += STEP
        with self.assertRaises(RuntimeError):
            individual.aggregate({"a": h}, ["a"])

    def test_child_ledger_carry_flags_and_old_credit_checked(self):
        for change in (lambda b: b["rolling"]["children"].append(copy.deepcopy(b["rolling"]["children"][0])),
                       lambda b: b["rolling"]["children"][0].update(carry_in=1),
                       lambda b: b["rolling"]["children"][0].update(live_ticks=0),
                       lambda b: b["rolling"].update(carry_in_ticks=STEP),
                       lambda b: b["rolling"].update(death_lost_ticks=STEP),
                       lambda b: b["v2_key"].__setitem__(1, 0)):
            h = copy.deepcopy(self.h())
            change(h["blocks"][0])
            with self.assertRaises(RuntimeError):
                individual.aggregate({"a": h}, ["a"])

    def test_partition_additivity_and_world_order_invariance(self):
        worlds = {"a": self.h("alternating-a"), "b": self.h(), "c": self.h("alternating-b")}
        check = individual.partition_check(worlds, ["a", "b", "c"], [["a", "c"], ["b"]])
        self.assertEqual(check["whole_credit"], [sum(v[i] for v in check["partition_credits"]) for i in range(2)])
        self.assertEqual(individual.aggregate(worlds, ["a", "b", "c"]),
                         individual.aggregate(dict(reversed(list(worlds.items()))), ["c", "b", "a"]))
        for groups in ([["a"], ["a", "c"]], [["a", "b"]], [["a", "b", "c"], []]):
            with self.assertRaises(RuntimeError):
                individual.partition_check(worlds, ["a", "b", "c"], groups)

    def test_all_tied_weak_periods_are_preserved(self):
        score = individual.aggregate({"a": self.h("old-sterile")}, ["a"])
        self.assertEqual(score["worlds"]["a"]["weakest_periods"], [list(p) for p in individual.PERIODS])
        self.assertEqual(score["key"], [1, 4, 0, 0])

    def test_fixed_comparisons_preserve_ties_pairs_and_blocked_omissions(self):
        worlds = {k: self.h() for k, *_ in previous.mixed.conditions(individual.SEEDS)}
        original = copy.deepcopy(worlds)
        result = individual.comparison(worlds, worlds)
        self.assertEqual(result["overall"]["comparison"], 0)
        self.assertEqual(result["overall"]["paired_counts"], {"wins": 0, "losses": 0, "ties": 8})
        for seed, group in result["leave_one_world_seed_out"].items():
            self.assertEqual(len(group["pairs"]), 6)
            self.assertTrue(all(not p["condition"].endswith(seed) for p in group["pairs"]))
        self.assertEqual(worlds, original)
        with self.assertRaises(RuntimeError):
            individual.comparison({k: v for i, (k, v) in enumerate(worlds.items()) if i}, worlds)

    def test_paired_delta_and_pooling_gap_exactly_explain_changed_margin(self):
        control = {"a": self.h(), "b": self.h("old-sterile")}
        candidate = {"a": self.h("alternating-a"), "b": self.h("alternating-b")}
        group = individual.pair_group(control, candidate, ["a", "b"])
        self.assertEqual(group["minimum_delta"], sum(p["minimum_delta"] for p in group["pairs"]))
        self.assertEqual(group["minimum_delta"], group["pooled_minimum_delta"] - group["pooling_gap_delta"])
        self.assertGreater(group["pooled_minimum_delta"], 0)
        self.assertLess(group["minimum_delta"], 0)

    def test_same_direction_schedule_losses_do_not_reverse_when_survival_ties(self):
        items = previous.mixed.conditions(individual.SEEDS)
        control = {k: self.h() for k, *_ in items}
        candidate = {k: self.h("alternating-a" if schedule == "fresh-1" else "alternating-b")
                     for k, schedule, *_ in items}
        result = individual.comparison(control, candidate)
        self.assertTrue(all(g["comparison"] == -1 for g in result["schedules"].values()))
        self.assertEqual(result["overall"]["comparison"], -1)
        reverse = individual.comparison(candidate, control)
        self.assertEqual(reverse["overall"]["comparison"], 1)

    def test_declared_scope_is_unchanged(self):
        self.assertEqual(individual.PERIODS, ((62, 94), (94, 126), (126, 158), (158, 190)))
        self.assertEqual(len(individual.MODELS) * len(previous.mixed.conditions(individual.SEEDS)) * len(individual.PERIODS), 128)
        self.assertEqual(len(individual.PAIRS), 5)


if __name__ == "__main__":
    unittest.main()
