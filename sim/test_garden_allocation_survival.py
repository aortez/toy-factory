#!/usr/bin/env python3
"""Survival-confirmed objective arithmetic; fixtures are not native ecology."""
import copy
from fractions import Fraction
import unittest

import garden_allocation_survival as survival

original = survival.original
DAY = original.DAY


def evidence(**changes):
    return {"birth": 0, "through": 8 * DAY, "reason": "horizon", "death": None,
            "seed_ticks": [], "shortage_ticks": []} | changes


class SurvivalTests(unittest.TestCase):
    def test_old_scores_are_unchanged(self):
        for fixture in original.arithmetic_fixtures().values():
            e = fixture["evidence"]
            old, new = original.scores(original.features(e)), survival.scores(e)
            self.assertEqual(len(new), 10)
            self.assertEqual({key: new[key] for key in old}, old)

    def test_productive_survivor_beats_wait(self):
        inactive = survival.scores(evidence())
        productive = survival.scores(evidence(seed_ticks=[DAY, 2 * DAY, 3 * DAY, 4 * DAY]))
        for weight in original.WEIGHTS:
            key = f"survival-confirmed-days:{weight}"
            self.assertEqual(productive[key] - inactive[key], weight)

    def test_shortages_cannot_change_survival_credit(self):
        e = evidence(seed_ticks=[DAY, 2 * DAY, 3 * DAY, 4 * DAY])
        stressed = e | {"shortage_ticks": list(range(60, 8 * DAY + 1, 60))}
        self.assertEqual(survival.production(e), survival.production(stressed))
        values = survival.scores(stressed)
        self.assertEqual(values["confirmed-days:1/4"], 2)
        self.assertEqual(values["survival-confirmed-days:1/4"], Fraction(9, 4))

    def test_seed_status_counts_and_distinct_bins(self):
        e = evidence(seed_ticks=[DAY, DAY + 60, 2 * DAY, 8 * DAY - 60])
        p = survival.production(e)
        self.assertEqual(p["status_counts"], {"alive": 3, "horizon-censored": 1})
        self.assertEqual(p["confirmed_seeds"], 3)
        self.assertEqual(p["confirmed_day_bins"], [1, 2])
        self.assertEqual(survival.unpack(p["capped_fraction"]), Fraction(1, 2))

    def test_confirmation_exactly_at_horizon(self):
        p = survival.production(evidence(seed_ticks=[7 * DAY, 7 * DAY + 15]))
        self.assertEqual([e["status"] for e in p["seed_events"]], ["alive", "horizon-censored"])

    def test_death_at_confirmation_fails_but_later_does_not(self):
        for cause in ("energy", "water", "both"):
            for tick, status in ((2 * DAY, "natural-failure"), (2 * DAY + 15, "alive")):
                p = survival.production(evidence(seed_ticks=[DAY], death={"tick": tick, "cause": cause}))
                self.assertEqual(p["seed_events"][0]["status"], status)

    def test_death_after_censoring_is_not_known_confirmation_failure(self):
        e = evidence(through=2 * DAY, seed_ticks=[DAY + 60],
                     death={"tick": 2 * DAY + 15, "cause": "energy"})
        self.assertEqual(survival.production(e)["status_counts"], {"horizon-censored": 1})

    def test_observed_natural_death_precedes_incomplete_followup(self):
        e = evidence(through=2 * DAY, seed_ticks=[DAY + 60],
                     death={"tick": 2 * DAY, "cause": "water"})
        self.assertEqual(survival.production(e)["status_counts"], {"natural-failure": 1})

    def test_patch_censoring_and_shortage_are_separate(self):
        e = evidence(through=2 * DAY, reason="patch", seed_ticks=[DAY + 60],
                     shortage_ticks=[DAY + 120], death={"tick": 2 * DAY + 15, "cause": "patch"})
        self.assertEqual(original.features(e)["seed_status_counts"], {"resource-shortage": 1})
        self.assertEqual(survival.production(e)["status_counts"], {"patch-censored": 1})
        self.assertEqual(survival.scores(e)["survival-confirmed-days:1/4"], 2)

    def test_cap_and_single_bin_burst(self):
        p = survival.production(evidence(seed_ticks=[i * DAY for i in range(1, 8)]))
        self.assertEqual(p["confirmed_seeds"], 7)
        self.assertEqual(survival.unpack(p["capped_fraction"]), 1)
        burst = survival.production(evidence(seed_ticks=[DAY + 15 * i for i in range(8)]))
        self.assertEqual(burst["confirmed_seeds"], 8)
        self.assertEqual(survival.unpack(burst["capped_fraction"]), Fraction(1, 4))

    def test_day_boundary_can_reward_two_close_purchases(self):
        fixtures = survival.arithmetic_fixtures()
        across = fixtures["burst-across-day-boundary"]
        self.assertEqual(across["survival_production"]["confirmed_day_bins"], [1, 2])
        self.assertEqual(survival.unpack(across["scores"]["survival-confirmed-days:1/4"]), Fraction(17, 8))

    def test_late_collapse_tradeoff_persists(self):
        fixtures = survival.arithmetic_fixtures()
        for weight in original.WEIGHTS:
            key = f"survival-confirmed-days:{weight}"
            self.assertGreater(survival.unpack(fixtures["late-collapse"]["scores"][key]),
                               survival.unpack(fixtures["inactive"]["scores"][key]))
        self.assertEqual(fixtures["burst-then-die"]["survival_production"]["confirmed_seeds"], 0)

    def test_lost_survival_budget_and_exact_tie(self):
        window = evidence()
        limits = survival.loss_budget(window)
        for weight in original.WEIGHTS:
            loss = weight * 8
            self.assertEqual(survival.unpack(limits[str(weight)]["4"]), loss)
            self.assertEqual(survival.unpack(limits[str(weight)]["1"]), loss / 4)
        # One confirmed bin buys exactly half a day at weight 1/4 in eight days.
        death_tick = 8 * DAY - DAY // 2 + 15
        for offset, comparison in ((-15, -1), (0, 0), (15, 1)):
            e = evidence(seed_ticks=[DAY], death={"tick": death_tick + offset, "cause": "energy"})
            value = survival.scores(e)["survival-confirmed-days:1/4"]
            self.assertEqual((value > 2) - (value < 2), comparison)

    def test_patch_window_scales_loss_budget(self):
        limits = survival.loss_budget(evidence(through=4 * DAY, reason="patch"))
        self.assertEqual(survival.unpack(limits["1/4"]["4"]), 1)

    def test_shape_resources_actions_and_children_are_not_rewarded(self):
        e = evidence(seed_ticks=[DAY])
        changed = e | {"roots": 99, "shoots": 99, "energy": 512, "water": 512,
                       "children_germinated": 100, "actions": {"seed": 999}, "stress": 100}
        self.assertEqual(survival.scores(e), survival.scores(changed))

    def test_short_window_and_invalid_purchase_rejected(self):
        for e in (evidence(through=DAY - 15), evidence(seed_ticks=[DAY, DAY]),
                  evidence(seed_ticks=[15], death={"tick": 15, "cause": "energy"})):
            with self.assertRaises(RuntimeError): survival.scores(e)

    def test_new_credit_never_below_zero_shortage_credit(self):
        for fixture in survival.arithmetic_fixtures().values():
            self.assertEqual(fixture["kind"], "arithmetic-only-not-native")
            for weight in original.WEIGHTS:
                values = fixture["scores"]
                self.assertGreaterEqual(survival.unpack(values[f"survival-confirmed-days:{weight}"]),
                                        survival.unpack(values[f"confirmed-days:{weight}"]))

    def test_rescore_does_not_mutate_baseline_and_rejects_changed_score(self):
        e = evidence()
        values = {k: original.exact(v) for k, v in original.scores(original.features(e)).items()}
        arm = {"evidence": e, "features": original.features(e), "scores": values}
        baseline = {"cases": [{"spec": {"name": name}, "window": e,
                              "arms": {a: copy.deepcopy(arm) for a in survival.allocation.ARMS}}
                             for name in ("first", "second")],
                    "equal_case_means": {}, "leave_one_case_out": {}}
        before = copy.deepcopy(baseline)
        result = survival.rescore(baseline)
        self.assertEqual(baseline, before)
        self.assertEqual(result["equal_case_means"]["survival-confirmed-days:1/4"]["ranking"],
                         [list(survival.allocation.ARMS)])
        baseline["cases"][0]["arms"]["wait"]["scores"]["survival"] = original.exact(0)
        with self.assertRaises(RuntimeError): survival.rescore(baseline)


if __name__ == "__main__":
    unittest.main()
