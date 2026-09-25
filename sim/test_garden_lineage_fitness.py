#!/usr/bin/env python3
"""Candidate fitness semantics and counterexamples, not native policy demonstrations."""
import copy
import unittest

import garden_lineage_fitness as fitness

DAY = fitness.DAY


class FitnessTests(unittest.TestCase):
    def setUp(self):
        self.fixtures = fitness.arithmetic_fixtures()

    def score(self, name):
        return self.fixtures[name]["evaluation"]

    def rerun(self, name, start=4 * DAY, end=8 * DAY):
        f = self.fixtures[name]
        for p in f["lineages"]:
            p["seeds_created"] = sum(s["parent"] == p["id"] for s in f["seeds"])
            p["late_seeds_created"] = sum(s["parent"] == p["id"] and s["birth_tick"] > start for s in f["seeds"])
        return fitness.world(f["lineages"], f["seeds"], start, end)

    def test_founder_longevity_and_seed_counts_are_not_direct_rewards(self):
        for name in ("founder-only", "sterile-seed-producer", "late-seed-burst"):
            self.assertEqual(self.score(name)["key"], [0, 0, 0, 0])
        self.assertEqual(fitness.compare(self.score("founder-only"), self.score("late-seed-burst")), 0)

    def test_sterile_descendant_has_persistence_but_no_new_renewal(self):
        self.assertEqual(self.score("old-sterile-descendant")["key"], [1, 0, 0, 4 * DAY])

    def test_productive_lineage_beats_sterile_persistence(self):
        result = self.score("productive-lineage")
        self.assertEqual(result["key"], [1, 1, 2, 3 * DAY + 30])
        self.assertEqual(result["renewing_parent_ids"], [2])
        self.assertGreater(fitness.compare(result, self.score("old-sterile-descendant")), 0)

    def test_later_parent_death_does_not_revoke_reproduction(self):
        result = self.score("productive-parent-later-dies")
        self.assertEqual(result["key"][:3], self.score("productive-lineage")["key"][:3])
        self.assertEqual(result["key"][3], 2 * DAY + 30)

    def test_parent_dead_at_child_confirmation_still_counts(self):
        f = self.fixtures["productive-lineage"]
        f["lineages"][1]["death_tick"] = 6 * DAY + 60
        result = self.rerun("productive-lineage")
        self.assertEqual(result["renewing_parent_ids"], [2])
        self.assertEqual(result["establishment_events"][1]["parent_state_at_confirmation"], "natural-dead")

    def test_founder_is_not_a_renewing_descendant_parent(self):
        f = self.fixtures["productive-lineage"]
        f["lineages"] = f["lineages"][:2]
        f["seeds"] = f["seeds"][:1]
        result = self.rerun("productive-lineage")
        self.assertEqual(result["key"][1:3], [0, 1])

    def test_young_failed_parent_does_not_erase_independent_child(self):
        f = self.fixtures["productive-lineage"]
        # The purchase for child 3 precedes parent 2's death at its own day boundary.
        f["lineages"][1]["death_tick"] = 6 * DAY
        result = self.rerun("productive-lineage")
        self.assertEqual(result["key"][:3], [1, 0, 1])
        self.assertFalse(result["establishment_events"][0]["parent_established"])

    def test_child_death_and_patch_at_confirmation(self):
        for patch, status in ((False, "natural-failure"), (True, "patch-censored")):
            f = self.fixtures["productive-lineage"]
            f["lineages"][2].update(death_tick=7 * DAY, environmental_death=patch)
            result = self.rerun("productive-lineage")
            self.assertEqual(result["key"][1:3], [0, 1])
            self.assertEqual(result["diagnostics"]["confirmation_cohort_outcomes"][status], 1)

    def test_child_later_patch_keeps_event_but_stops_occupancy(self):
        f = self.fixtures["productive-lineage"]
        f["lineages"][2].update(death_tick=7 * DAY + 15, environmental_death=True)
        result = self.rerun("productive-lineage")
        self.assertEqual(result["key"][1:3], [1, 2])
        child = next(p for p in result["occupancy"] if p["id"] == 3)
        self.assertEqual(child["live_ticks"], 15)

    def test_extinct_history_loses_to_surviving_founder(self):
        result = self.score("extinct-reproductive-burst")
        self.assertEqual(result["key"][:3], [-1, 1, 2])
        self.assertTrue(result["terminal"]["observed_extinct"])
        self.assertLess(fitness.compare(result, self.score("founder-only")), 0)

    def test_live_founder_cannot_preserve_descendant_terminal_tier(self):
        result = self.score("descendants-lost-founder-remains")
        self.assertEqual(result["key"][:3], [0, 1, 2])
        self.assertLess(fitness.compare(result, self.score("old-sterile-descendant")), 0)

    def test_seed_only_is_unresolved_not_extinct_or_healthy(self):
        result = self.score("seed-only-ending")
        self.assertEqual(result["status"], "needs-followup")
        self.assertIsNone(result["key"])
        self.assertFalse(result["terminal"]["observed_extinct"])
        with self.assertRaises(RuntimeError): fitness.compare(result, self.score("founder-only"))

    def test_seed_only_case_cannot_be_dropped_from_batch(self):
        batch = fitness.aggregate({"good": self.score("productive-lineage"), "pending": self.score("seed-only-ending")})
        self.assertIsNone(batch["key"])
        self.assertEqual(batch["unresolved"], ["pending"])

    def test_endpoint_is_explicitly_one_sample_sensitive(self):
        alive, dead = self.score("old-sterile-descendant"), self.score("endpoint-descendant-death")
        self.assertEqual(alive["key"][3] - dead["key"][3], 15)
        self.assertEqual((alive["key"][0], dead["key"][0]), (1, 0))

    def test_confirmation_event_window_not_seed_creation_cohort(self):
        f = self.fixtures["old-sterile-descendant"]
        f["lineages"][1]["birth_tick"] = 3 * DAY + DAY // 2
        f["seeds"][0].update(birth_tick=3 * DAY + DAY // 2 - 120, end_tick=3 * DAY + DAY // 2)
        result = self.rerun("old-sterile-descendant")
        self.assertEqual(result["diagnostics"]["closing_purchases"], 0)
        self.assertEqual(result["key"][2], 1)

    def test_confirmation_at_start_excluded_at_end_included(self):
        self.assertEqual(self.rerun("productive-lineage", start=7 * DAY)["key"][1:3], [0, 0])
        self.assertEqual(self.rerun("productive-lineage", end=7 * DAY)["key"][1:3], [1, 2])

    def test_newborn_not_yet_confirmed_has_no_occupancy_credit(self):
        f = self.fixtures["old-sterile-descendant"]
        f["lineages"][1]["birth_tick"] = 8 * DAY - 120
        f["seeds"][0].update(birth_tick=8 * DAY - 240, end_tick=8 * DAY - 120)
        result = self.rerun("old-sterile-descendant")
        self.assertEqual(result["key"], [0, 0, 0, 0])
        self.assertEqual(result["terminal"]["young_descendants"], [2])

    def test_each_renewing_parent_counts_once_not_per_child(self):
        result = self.score("brief-established-offspring")
        self.assertEqual(result["key"][1:3], [1, 4])
        self.assertEqual(result["renewing_parent_ids"], [2])

    def test_more_brief_establishments_can_beat_longer_occupancy(self):
        brief, steady = self.score("brief-established-offspring"), self.score("steady-offspring")
        self.assertLess(brief["key"][3], steady["key"][3])
        self.assertGreater(fitness.compare(brief, steady), 0)

    def test_generation_numbers_size_stores_and_order_do_not_reward(self):
        f = self.fixtures["productive-lineage"]
        for p in f["lineages"]:
            p.update(generation=1000, nodes=999, energy=999, water=999, actions=999)
        for s in f["seeds"]:
            s["generation"] = 1000
        f["lineages"].reverse()
        f["seeds"].reverse()
        self.assertEqual(self.rerun("productive-lineage")["key"], f["evaluation"]["key"])

    def test_no_mutation_or_duplicate_identity(self):
        f = self.fixtures["productive-lineage"]
        before = copy.deepcopy(f)
        fitness.world(f["lineages"], f["seeds"], 4 * DAY, 8 * DAY)
        self.assertEqual(f, before)
        with self.assertRaises(RuntimeError):
            fitness.world(f["lineages"] + [f["lineages"][0]], f["seeds"], 4 * DAY, 8 * DAY)

    def test_aggregate_weakest_terminal_tier_precedes_good_worlds(self):
        risky = fitness.aggregate({"a": self.score("productive-lineage"), "b": self.score("extinct-reproductive-burst")})
        safe = fitness.aggregate({"a": self.score("founder-only"), "b": self.score("founder-only")})
        self.assertLess(fitness.compare(risky, safe), 0)
        self.assertEqual(safe["key"], [0, 0, 0, 0, 0])

    def test_mismatched_empty_suites_and_windows_rejected(self):
        a = self.score("founder-only")
        with self.assertRaises(RuntimeError): fitness.aggregate({})
        with self.assertRaises(RuntimeError): fitness.paired({"a": a}, {"b": a})
        with self.assertRaises(RuntimeError): fitness.paired({"a": a}, {"a": self.rerun("founder-only", start=5 * DAY)})
        with self.assertRaises(RuntimeError): fitness.world([], [], 0, 0)

    def test_exact_ties_and_synthetic_labels(self):
        a = self.score("productive-lineage")
        self.assertEqual(fitness.compare(a, copy.deepcopy(a)), 0)
        self.assertEqual(fitness.paired({"a": a}, {"a": a})["comparison"], 0)
        for f in self.fixtures.values():
            self.assertEqual(f["kind"], "synthetic-arithmetic-not-native")


if __name__ == "__main__":
    unittest.main()
