#!/usr/bin/env python3
"""Fixed-clock persistence scoring, projection and synthetic follow-up tests."""
import copy
import unittest

import garden_lineage_persistence as fitness

DAY, STEP = fitness.DAY, fitness.STEP
START, END, STOP = 4 * DAY, 8 * DAY, 10 * DAY


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.fixtures = fitness.arithmetic_fixtures()

    def score(self, name):
        return self.fixtures[name]["evaluation"]

    def rerun(self, name):
        f = self.fixtures[name]
        return fitness.world(f["lineages"], f["seeds"], START, END, STOP)

    def test_long_lived_child_beats_brief_offspring(self):
        steady, brief = self.score("steady-offspring"), self.score("brief-established-offspring")
        self.assertEqual(steady["key"], [1, 7695, 23055, 1, 1])
        self.assertEqual(brief["key"], [1, 60, 15420, 1, 4])
        self.assertGreater(fitness.compare(steady, brief), 0)
        self.assertLess(fitness.v1.compare(steady["main_v1"], brief["main_v1"]), 0)

    def test_many_renewing_parents_cannot_override_live_time(self):
        steady, brief = self.score("steady-offspring"), self.score("brief-multiple-renewing-parents")
        self.assertGreater(brief["components"]["renewing_parents"], steady["components"]["renewing_parents"])
        self.assertGreater(brief["components"]["descendant_live_ticks"], steady["components"]["descendant_live_ticks"])
        self.assertGreater(fitness.compare(steady, brief), 0)

    def test_later_parent_death_preserves_child_time(self):
        a, b = self.score("productive-lineage"), self.score("productive-parent-later-dies")
        self.assertEqual(a["key"][:2], b["key"][:2])
        self.assertLess(b["key"][2], a["key"][2])

    def test_parent_dead_before_confirmation_keeps_renewal(self):
        self.fixtures["productive-lineage"]["lineages"][1]["death_tick"] = 6 * DAY + STEP
        result = self.rerun("productive-lineage")
        self.assertEqual(result["components"]["renewing_child_live_ticks"], DAY + STEP)
        self.assertEqual(result["main_v1"]["establishment_events"][1]["parent_state_at_confirmation"], "natural-dead")

    def test_failed_young_parent_child_gets_only_ordinary_occupancy(self):
        self.fixtures["productive-lineage"]["lineages"][1]["death_tick"] = 6 * DAY
        self.assertEqual(self.rerun("productive-lineage")["key"], [1, 0, DAY + STEP, 0, 1])

    def test_founder_offspring_and_old_sterile_descendants_have_no_renewal_time(self):
        self.assertEqual(self.score("old-sterile-descendant")["key"], [1, 0, 4 * DAY, 0, 0])
        f = fitness.fixture([(1, 0, 0, None, False), (2, 1, 5 * DAY, None, False)])
        self.assertEqual(f["evaluation"]["key"], [1, 0, 2 * DAY + STEP, 0, 1])

    def test_seed_counts_and_founder_longevity_not_direct_rewards(self):
        for name in ("founder-only", "sterile-seed-producer", "late-seed-burst"):
            self.assertEqual(self.score(name)["key"], [0, 0, 0, 0, 0])

    def test_child_death_at_confirmation_natural_and_patch(self):
        for patch, status in ((False, "natural-failure"), (True, "patch-censored")):
            self.fixtures["productive-lineage"]["lineages"][2].update(death_tick=7 * DAY, environmental_death=patch)
            result = self.rerun("productive-lineage")
            self.assertEqual(result["components"]["renewing_child_live_ticks"], 0)
            self.assertEqual(result["main_v1"]["diagnostics"]["confirmation_cohort_outcomes"][status], 1)

    def test_later_patch_keeps_only_observed_child_samples(self):
        self.fixtures["productive-lineage"]["lineages"][2].update(death_tick=7 * DAY + STEP, environmental_death=True)
        result = self.rerun("productive-lineage")
        self.assertEqual(result["components"]["renewing_child_live_ticks"], STEP)
        self.assertEqual(result["components"]["renewing_parents"], 1)

    def test_confirmation_window_start_excluded_end_included(self):
        f = self.fixtures["productive-lineage"]
        excluded = fitness.world(f["lineages"], f["seeds"], 7 * DAY, END, STOP, source_start=START)
        self.assertEqual(excluded["components"]["renewing_child_live_ticks"], 0)
        included = fitness.world(f["lineages"], f["seeds"], START, 7 * DAY, 9 * DAY)
        self.assertEqual(included["components"]["renewing_child_live_ticks"], STEP)

    def test_short_history_is_incomplete_even_when_plants_alive(self):
        f = self.fixtures["productive-lineage"]
        result = fitness.world(f["lineages"], f["seeds"], START, END, END)
        self.assertEqual(result["status"], "needs-followup")
        self.assertIsNone(result["key"])
        with self.assertRaises(RuntimeError): fitness.compare(result, self.score("productive-lineage"))

    def test_incomplete_world_blocks_suite(self):
        f = self.fixtures["founder-only"]
        short = fitness.world(f["lineages"], f["seeds"], START, END, END)
        result = fitness.aggregate({"short": short, "good": self.score("productive-lineage")})
        self.assertIsNone(result["key"])
        self.assertEqual(result["unresolved"], ["short"])

    def test_seed_only_expiry_resolves_to_observed_extinction(self):
        result = self.score("seed-only-ending")
        self.assertEqual(result["main_v1"]["status"], "needs-followup")
        self.assertEqual(result["key"], [-1, 0, 0, 0, 0])
        self.assertEqual(result["terminal"]["classification"], "observed-extinct")
        self.assertEqual(result["pending_seed_followup"][0]["outcome"], "expired")

    def test_seed_only_established_recovery_has_no_retroactive_event_credit(self):
        result = self.score("seed-only-recovered")
        self.assertEqual(result["key"], [1, 0, 0, 0, 0])
        self.assertEqual(result["pending_seed_followup"][0]["child_confirmation"], "confirmed")
        self.assertEqual(result["pending_seed_followup"][0]["child_terminal"], "alive")
        self.assertEqual(result["main_v1"]["establishment_events"], [])

    def test_seed_only_failures_keep_natural_patch_and_later_collapse_distinct(self):
        for name, confirmation, terminal in (("natural-failure", "natural-failure", "natural-dead"),
                                             ("patch-censored", "patch-censored", "patch-dead"),
                                             ("later-collapse", "confirmed", "natural-dead")):
            result = self.score("seed-only-" + name)
            self.assertEqual(result["key"][0], -1)
            self.assertEqual(result["pending_seed_followup"][0]["child_confirmation"], confirmation)
            self.assertEqual(result["pending_seed_followup"][0]["child_terminal"], terminal)

    def test_new_generation_pending_seeds_are_unconfirmed_not_healthy_or_extinct(self):
        result = self.score("seed-only-new-generation-unconfirmed")
        self.assertEqual(result["key"], [0, 0, 0, 0, 0])
        self.assertEqual(result["terminal"]["classification"], "seed-only-unconfirmed")
        self.assertEqual(result["terminal"]["pending_seeds"], 1)
        self.assertEqual(result["pending_seed_followup"][0]["outcome"], "germinated")

    def test_original_pending_seed_cannot_outlive_maximum_lifetime(self):
        f = self.fixtures["seed-only-ending"]
        f["seeds"][0].update(outcome="pending", end_tick=None)
        with self.assertRaises(RuntimeError): self.rerun("seed-only-ending")

    def test_fixed_followup_rejects_extra_or_missing_main_time(self):
        f = self.fixtures["founder-only"]
        for stop in (STOP + STEP, END - STEP):
            with self.assertRaises(RuntimeError): fitness.world(f["lineages"], f["seeds"], START, END, stop)

    def test_last_eligible_germination_has_full_first_day_followup(self):
        f = fitness.fixture([(1, 0, 0, None, False),
                             (2, 1, END + DAY - 2 * STEP, None, False)])
        f["lineages"][0]["death_tick"] = END
        f["seeds"][0]["birth_tick"] = END - STEP
        result = fitness.world(f["lineages"], f["seeds"], START, END, STOP)
        self.assertEqual(result["main_v1"]["status"], "needs-followup")
        self.assertEqual(result["pending_seed_followup"][0]["child_confirmation"], "confirmed")
        self.assertEqual(result["key"], [1, 0, 0, 0, 0])

    def test_followup_endpoint_remains_one_sample_sensitive(self):
        before = self.score("old-sterile-descendant")
        self.fixtures["old-sterile-descendant"]["lineages"][1]["death_tick"] = STOP
        after = self.rerun("old-sterile-descendant")
        self.assertEqual(before["key"][1:], after["key"][1:])
        self.assertEqual((before["key"][0], after["key"][0]), (1, 0))

    def test_followup_death_does_not_change_main_credit(self):
        before = self.score("productive-lineage")
        self.fixtures["productive-lineage"]["lineages"][2].update(death_tick=9 * DAY, environmental_death=True)
        after = self.rerun("productive-lineage")
        self.assertEqual(before["main_v1"], after["main_v1"])
        self.assertEqual(before["components"], after["components"])

    def test_future_birth_and_purchase_excluded_and_seed_outcome_hidden(self):
        f = self.fixtures["seed-only-new-generation-unconfirmed"]
        plants, seeds = fitness.project(f["lineages"], f["seeds"], START, END, START, STOP)
        self.assertEqual([p["id"] for p in plants], [1])
        self.assertEqual(plants[0]["seeds_created"], 1)
        self.assertEqual(len(seeds), 1)
        self.assertEqual(seeds[0]["outcome"], "pending")
        self.assertIsNone(seeds[0]["child_id"])
        self.assertIsNone(seeds[0]["end_tick"])

    def test_bad_original_counter_rejected_before_projection_recounts(self):
        self.fixtures["productive-lineage"]["lineages"][0]["seeds_created"] += 1
        with self.assertRaises(RuntimeError): self.rerun("productive-lineage")

    def test_input_preserved_and_duplicate_child_identity_rejected(self):
        f = self.fixtures["productive-lineage"]
        before = copy.deepcopy(f)
        self.rerun("productive-lineage")
        self.assertEqual(f, before)
        f["seeds"][1]["child_id"] = 2
        with self.assertRaises(RuntimeError): self.rerun("productive-lineage")

    def test_generation_numbers_body_stores_and_order_do_not_change_score(self):
        f = self.fixtures["productive-lineage"]
        for p in f["lineages"]: p.update(generation=999, nodes=999, water=999, energy=999)
        for s in f["seeds"]: s["generation"] = 999
        f["lineages"].reverse()
        f["seeds"].reverse()
        self.assertEqual(self.rerun("productive-lineage"), f["evaluation"])

    def test_weakest_terminal_tier_precedes_renewal(self):
        risky = fitness.aggregate({"a": self.score("productive-lineage"), "b": self.score("seed-only-ending")})
        safe = fitness.aggregate({"a": self.score("founder-only"), "b": self.score("founder-only")})
        self.assertLess(fitness.compare(risky, safe), 0)
        self.assertEqual(safe["key"], [0, 0, 0, 0, 0, 0])

    def test_windows_deadlines_conditions_and_empty_suites(self):
        a = self.score("productive-lineage")
        with self.assertRaises(RuntimeError): fitness.aggregate({})
        with self.assertRaises(RuntimeError): fitness.paired({"a": a}, {"b": a})
        for field, value in (("followup_deadline", STOP + STEP), ("window", {}), ("rule", "other")):
            b = copy.deepcopy(a)
            b[field] = value
            with self.assertRaises(RuntimeError): fitness.compare(a, b)
            with self.assertRaises(RuntimeError): fitness.aggregate({"a": a, "b": b})

    def test_exact_ties_and_original_fixtures_preserved(self):
        a = self.score("productive-lineage")
        self.assertEqual(fitness.compare(a, copy.deepcopy(a)), 0)
        self.assertEqual(fitness.paired({"a": a}, {"a": a})["comparison"], 0)
        for name, old in fitness.v1.arithmetic_fixtures().items():
            self.assertEqual(self.score(name)["main_v1"], old["evaluation"])
        self.assertTrue(all(f["kind"] == "synthetic-arithmetic-not-native" for f in self.fixtures.values()))


if __name__ == "__main__":
    unittest.main()
