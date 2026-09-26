#!/usr/bin/env python3
"""Synthetic accounting fixtures, not claims of reachable Garden behavior."""
import copy
import unittest

import garden_descendants as audit

DAY = audit.DAY


def plant(identity=1, birth=0, parent=0, death=None, patch=False):
    return {"id": identity, "birth_tick": birth, "parent": parent, "death_tick": death,
            "environmental_death": patch, "column": identity, "generation": identity - 1,
            "seeds_created": 0, "late_seeds_created": 0}


def seed(parent=1, tick=DAY, child=None, finish=None, pending=False):
    return {"parent": parent, "birth_tick": tick, "child_id": child,
            "end_tick": None if pending else finish or tick + DAY,
            "column": child or parent, "generation": parent, "species": 0,
            "reachable_columns": 1 << (child or parent),
            "outcome": "pending" if pending else "germinated" if child else "expired"}


def prepare(plants, seeds, start=0):
    for p in plants:
        p["seeds_created"] = sum(s["parent"] == p["id"] for s in seeds)
        p["late_seeds_created"] = sum(s["parent"] == p["id"] and s["birth_tick"] > start for s in seeds)
    return plants, seeds


def run(plants=None, seeds=None, start=0, end=4 * DAY):
    plants, seeds = prepare(plants or [plant()], seeds or [], start)
    return audit.outcomes(plants, seeds, start, end)


def visit_rows(s, end=4 * DAY):
    rows = []
    for tick in range(s["birth_tick"] + 15, (s["end_tick"] or end) + 1, 15):
        age = (tick - s["birth_tick"]) // 15
        terminal = tick == s["end_tick"]
        outcome = (2 if s["outcome"] == "germinated" else 1) if terminal else 0
        masks = [32] * 28
        masks[2] = 0
        rows.append({"type": "seed-step", "tick": tick, "attempts": [{
            **{k: s[k] for k in ("parent", "column", "generation", "species")},
            "age": age, "outcome": outcome, "child": s["child_id"] if outcome == 2 else 0,
            "blockers": 0 if outcome in (1, 2) else 32 | int(age < 8), "sites": masks}]})
    return rows


class DescendantTests(unittest.TestCase):
    def test_long_seed_viability_and_followup_are_explicit(self):
        pending = {**seed(pending=True), "lifetime_ecology_ticks": 8192}
        result = run(seeds=[pending])
        self.assertEqual(result["all"]["counts"]["pending"], 1)
        self.assertEqual(result["full_potential"]["counts"]["created"], 0)
        expired = {**seed(finish=33 * DAY), "lifetime_ecology_ticks": 8192}
        self.assertEqual(run(seeds=[expired], end=33 * DAY)["all"]["counts"]["expired"], 1)
        for lifetime in (0, True, 65536):
            with self.assertRaises(RuntimeError):
                run(seeds=[{**pending, "lifetime_ecology_ticks": lifetime}])
        with self.assertRaises(RuntimeError):
            run(seeds=[{**seed(), "lifetime_ecology_ticks": 8192}])

    def test_nonproducing_survivor_is_separate_from_productivity(self):
        result = run()
        p = result["parents"][0]
        self.assertEqual(p["category"], "no-closing-purchases")
        self.assertEqual(p["closing_day_confirmation"], "confirmed")
        self.assertEqual(p["closing_live_ticks"], 4 * DAY)
        self.assertEqual(result["all"]["counts"]["created"], 0)

    def test_expiry_is_not_child_death(self):
        result = run(seeds=[seed()])
        self.assertEqual(result["all"]["counts"]["expired"], 1)
        self.assertEqual(result["all"]["counts"]["child_natural_failure"], 0)
        self.assertEqual(result["seeds"][0]["parent_confirmation"], "confirmed")
        self.assertEqual(result["parents"][0]["category"], "purchases-no-observed-established-child")

    def test_pending_is_censored_not_expired(self):
        result = run(seeds=[seed(tick=4 * DAY - 15, pending=True)])
        self.assertEqual(result["all"]["counts"]["pending"], 1)
        self.assertEqual(result["seeds"][0]["parent_confirmation"], "horizon-censored")
        self.assertEqual(result["full_potential"]["counts"]["created"], 0)

    def test_child_death_confirmation_boundary(self):
        birth = DAY + 120
        for offset, expected in ((-15, "natural-failure"), (0, "natural-failure"), (15, "confirmed")):
            result = run([plant(), plant(2, birth, 1, birth + DAY + offset)], [seed(child=2, finish=birth)])
            self.assertEqual(result["seeds"][0]["child_confirmation"], expected)

    def test_horizon_exact_confirmation_and_recent_child(self):
        for birth, expected in ((3 * DAY, "confirmed"), (3 * DAY + 15, "horizon-censored")):
            result = run([plant(), plant(2, birth, 1)], [seed(tick=birth - 120, child=2, finish=birth)])
            self.assertEqual(result["seeds"][0]["child_confirmation"], expected)

    def test_patch_at_confirmation_censors_not_starves(self):
        birth = DAY + 120
        for offset, expected in ((0, "patch-censored"), (15, "confirmed")):
            result = run([plant(), plant(2, birth, 1, birth + DAY + offset, True)],
                         [seed(child=2, finish=birth)])
            self.assertEqual(result["seeds"][0]["child_confirmation"], expected)
            self.assertEqual(result["seeds"][0]["child_final"], "patch-dead")

    def test_success_before_later_death_stays_confirmed(self):
        birth = DAY + 120
        result = run([plant(), plant(2, birth, 1, 3 * DAY)], [seed(child=2, finish=birth)])
        self.assertEqual(result["seeds"][0]["child_confirmation"], "confirmed")
        self.assertEqual(result["seeds"][0]["child_final"], "natural-dead")

    def test_reclaimed_dead_parent_does_not_erase_posthumous_success(self):
        p = plant(death=DAY + 60)
        p["reclaimed_tick"] = DAY + 90
        result = run([p, plant(2, DAY + 120, 1)], [seed(child=2, finish=DAY + 120)])
        e = result["seeds"][0]
        self.assertEqual(e["parent_confirmation"], "natural-failure")
        self.assertEqual(e["child_confirmation"], "confirmed")
        self.assertEqual(e["parent_at_child_confirmation"], "natural-dead")
        self.assertEqual(result["parents"][0]["established_children"], [2])

    def test_same_tick_purchase_then_parent_patch(self):
        result = run([plant(death=DAY, patch=True)], [seed()])
        self.assertEqual(result["seeds"][0]["parent_confirmation"], "patch-censored")
        with self.assertRaises(RuntimeError): run([plant(death=DAY)], [seed()])

    def test_same_tick_newborn_then_patch(self):
        birth = DAY + 120
        result = run([plant(), plant(2, birth, 1, birth, True)], [seed(child=2, finish=birth)])
        self.assertEqual(result["seeds"][0]["child_confirmation"], "patch-censored")
        self.assertEqual(result["parents"][1]["closing_live_ticks"], 0)

    def test_two_generation_establishment_requires_both_days(self):
        b, g = DAY + 120, 2 * DAY + 120
        seeds = [seed(child=2, finish=b), seed(parent=2, tick=2 * DAY, child=3, finish=g)]
        for death, expected in ((None, [3]), (g + DAY, [])):
            result = run([plant(), plant(2, b, 1), plant(3, g, 2, death)], seeds)
            self.assertEqual(result["seeds"][0]["established_grandchildren"], expected)
            self.assertEqual(result["all"]["counts"]["established_with_established_child"], bool(expected))

    def test_failed_child_is_not_durable_even_with_surviving_grandchild(self):
        b, g = DAY + 120, DAY + 360
        seeds = [seed(child=2, finish=b), seed(parent=2, tick=DAY + 240, child=3, finish=g)]
        result = run([plant(), plant(2, b, 1, DAY + 480), plant(3, g, 2)], seeds)
        self.assertEqual(result["seeds"][0]["established_grandchildren"], [])

    def test_creation_time_eligibility_does_not_select_early_success(self):
        for tick, eligible in ((2 * DAY, True), (2 * DAY + 15, False)):
            birth = tick + 120
            result = run([plant(), plant(2, birth, 1)], [seed(tick=tick, child=2, finish=birth)])
            self.assertEqual(result["seeds"][0]["full_potential_followup"], eligible)
            self.assertEqual(result["all"]["counts"]["established"], 1)
            self.assertEqual(result["full_potential"]["counts"]["established"], int(eligible))

    def test_calendar_eligibility_does_not_remove_patch_censoring(self):
        birth = DAY + 120
        result = run([plant(), plant(2, birth, 1, birth + 60, True)], [seed(child=2, finish=birth)])
        self.assertEqual(result["full_potential"]["counts"]["child_patch_censored"], 1)

    def test_creation_cohort_and_birth_cohort_are_distinct(self):
        birth = DAY + 120
        result = run([plant(), plant(2, birth, 1)], [seed(child=2, finish=birth)], start=DAY)
        self.assertEqual(result["all"]["counts"]["created"], 0)
        self.assertEqual(result["birth_cohort_reconciliation"], {
            "all_closing_births": 1, "from_closing_purchases": 0, "from_earlier_purchases": 1})

    def test_ambiguous_or_unmatched_identities_rejected(self):
        b = DAY + 120
        plants, seeds = prepare([plant(), plant(2, b, 1)], [seed(child=2, finish=b)])
        for ps, ss in ((plants + [plants[0]], seeds), (plants, seeds * 2), (plants, []),
                       ([plants[0]], seeds), (plants, [seeds[0] | {"column": 3}]),
                       (plants, [seeds[0] | {"parent": 99}])):
            with self.assertRaises(RuntimeError): audit.outcomes(ps, ss, 0, 4 * DAY)

    def test_purchase_ledgers_and_temporal_validity_rejected(self):
        ps, ss = prepare([plant()], [seed()])
        for changes in ({"seeds_created": 0}, {"late_seeds_created": 0}, {"birth_tick": -15},
                        {"death_tick": 0}, {"environmental_death": True}):
            with self.assertRaises(RuntimeError): audit.outcomes([ps[0] | changes], ss, 0, 4 * DAY)
        for changes in ({"outcome": "lost"}, {"end_tick": DAY + 15}, {"child_id": 2},
                        {"outcome": "pending", "end_tick": None}):
            with self.assertRaises(RuntimeError): audit.outcomes(ps, [ss[0] | changes], 0, 4 * DAY)

    def test_parent_bins_are_diagnostic_not_seed_count(self):
        result = run(seeds=[seed(tick=DAY + 15), seed(tick=DAY + 30)])
        self.assertEqual(result["parents"][0]["purchases"], 2)
        self.assertEqual(result["parents"][0]["confirmed_parent_age_bins"], [1])
        self.assertNotIn("score", result["parents"][0])

    def test_no_input_mutation(self):
        ps, ss = prepare([plant()], [seed()])
        before = copy.deepcopy((ps, ss))
        audit.outcomes(ps, ss, 0, 4 * DAY)
        self.assertEqual((ps, ss), before)

    def test_exact_opportunities_do_not_impute_a_landing(self):
        s = seed()
        c = audit.opportunities(visit_rows(s), [s], 0, 4 * DAY)[1, DAY]
        self.assertEqual(c["visits"], 256)
        self.assertEqual(c["expired"], 1)
        self.assertEqual(c["mature_checks"], 248)
        self.assertEqual(c["anywhere_open_actual_blocked"], 248)
        self.assertEqual(c["reachable_open"], 0)
        self.assertEqual(c["actual_open"], 0)
        s["reachable_columns"] |= 1 << 2
        c = audit.opportunities(visit_rows(s), [s], 0, 4 * DAY)[1, DAY]
        self.assertEqual(c["reachable_open"], 248)
        self.assertEqual(c["actual_open"], 0)

    def test_exact_success_and_no_visit_for_last_tick_purchase(self):
        s = seed(child=2, finish=DAY + 120)
        c = audit.opportunities(visit_rows(s), [s], 0, 4 * DAY)[1, DAY]
        self.assertEqual(c["actual_open"], 1)
        self.assertEqual(c["dormant_checks"], 7)
        late = seed(tick=4 * DAY, pending=True)
        self.assertEqual(audit.opportunities([], [late], 0, 4 * DAY)[1, 4 * DAY]["visits"], 0)

    def test_missing_changed_duplicate_or_unmatched_visit_rejected(self):
        s = seed()
        rows = visit_rows(s)
        for broken in (rows[1:], rows[:-1], rows[:1] + rows, list(reversed(rows))):
            with self.assertRaises(RuntimeError): audit.opportunities(broken, [s], 0, 4 * DAY)
        for change in ({"parent": 99}, {"column": 3}, {"age": 9}, {"outcome": 2, "child": 9}):
            broken = copy.deepcopy(rows)
            broken[0]["attempts"][0].update(change)
            with self.assertRaises(RuntimeError): audit.opportunities(broken, [s], 0, 4 * DAY)

    def test_examples_are_first_sorted_match_or_explicit_absence(self):
        result = run()
        examples = audit.examples([{"key": "z", **result}, {"key": "a", **result}])
        self.assertEqual(examples["nonproducing_survivor"], {"case": "a", "parent": 1})
        self.assertIsNone(examples["producer_with_established_child"])


if __name__ == "__main__":
    unittest.main()
