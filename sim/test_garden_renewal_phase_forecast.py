#!/usr/bin/env python3
"""Fixed shadow math, phase wrapping, assumption breaks and censoring tests."""
import copy
import unittest
from unittest.mock import patch

import garden_renewal_phase_forecast as audit
import test_garden_renewal_seed_forecast as fixtures


def plant(**changes):
    return fixtures.plant(leaves=36, **changes)


def samples(extra=None):
    result = fixtures.purchase_samples(extra)
    for r in result.values():
        r["sun_strength"] = audit.sun_strength(r["sun_phase"])
        for p in r["plants"]:
            p["leaves"] = 36
    return result


class PhaseForecastTests(unittest.TestCase):
    def test_sun_curve_symmetry_and_integer_thresholds(self):
        self.assertEqual([audit.sun_strength(p) for p in (0, 10, 11, 64, 117, 118, 128, 255)],
                         [24, 60, 64, 255, 64, 60, 24, 24])
        self.assertTrue(all(audit.sun_strength(p) == audit.sun_strength(128-p) for p in range(129)))
        self.assertTrue(all(audit.sun_strength(p) == 24 for p in range(128, 256)))
        for bad in (-1, 256, 1.5, "64"):
            with self.assertRaises(RuntimeError): audit.sun_strength(bad)

    def test_horizon_means_next_dawn_then_noon_not_current_day_noon(self):
        self.assertEqual(audit.boundaries(4620),
            {"sunset": 4800, "dawn": 6720, "first_possible_income": 6885, "noon": 7680})
        self.assertEqual(audit.boundaries(3480)["noon"], 7680)  # Morning phase 40.
        for bad in (0, -60, 4621, 4800, 6720, 6000, 4620.0):
            with self.assertRaises(RuntimeError): audit.boundaries(bad)

    def test_invalid_anchor_and_saturated_income_rejected(self):
        valid = [4620, 201, 8, 55, 0]
        for index, bad in ((1, -1), (1, 257), (2, 255), (2, -1), (3, 0), (3, 513), (4, -1), (4, 8)):
            values = valid.copy()
            values[index] = bad
            with self.subTest(index=index, bad=bad), self.assertRaises(RuntimeError): audit.project(*values)

    def test_dark_anchor_is_explicitly_unsupported_not_silent_zero_rate(self):
        p = audit.project(4680, 200, 0, 55, 0)
        self.assertFalse(p["supported"])
        self.assertEqual(p["reason"], "zero-current-light-tier")
        self.assertEqual(p["steps"], {})
        self.assertNotIn("death_tick", p)
        # A zero observation with positive global light is a supported zero-rate hypothesis.
        self.assertTrue(audit.project(4620, 200, 0, 55, 0)["supported"])

    def test_rate_floors_ratio_and_has_no_half_income_multiplier(self):
        p = audit.project(4200, 201, 5, 55, 0)  # phase 88, tier 2
        self.assertEqual(p["anchor_tier"], 2)
        self.assertEqual(p["steps"][4215]["potential_income"], 5)
        self.assertEqual(p["steps"][4620]["potential_income"], 2)
        self.assertEqual(p["steps"][4650]["potential_income"], 0)
        self.assertEqual(p["steps"][7680]["potential_income"], 7)

    def test_exact_two_known_late_purchase_predictions(self):
        shrub = audit.project(4620, 201, 8, 55, 0)
        cover = audit.project(4620, 200, 7, 59, 0)
        self.assertNotIn(4620, shrub["steps"])
        self.assertEqual(shrub["steps"][4800]["energy"], 188)
        self.assertEqual(cover["steps"][4800]["energy"], 183)
        self.assertEqual((shrub["death_tick"], cover["death_tick"]), (6840, 6600))

    def test_cap_before_upkeep_and_dawn_recovery_do_not_imply_death(self):
        p = audit.project(4620, 249, 8, 55, 0)
        self.assertEqual(p["steps"][4635]["overflow"], 1)
        self.assertEqual(p["steps"][4635]["energy"], 256)
        self.assertEqual([p["steps"][t]["energy"] for t in (4800, 6705, 6720, 6780)], [235, 18, 11, 4])
        self.assertEqual(p["steps"][6840]["upkeep_unpaid"], 3)
        self.assertEqual(p["steps"][6840]["stress"], 1)
        self.assertEqual(p["steps"][6900]["stress"], 0)
        self.assertEqual(p["peak_stress"], 1)
        self.assertIsNone(p["death_tick"])
        high = audit.project(3780, 256, 254, 8, 0)  # phase 60, noon-facing tier 3
        self.assertEqual(high["steps"][3840]["energy"], 255)  # cap, then maintenance

    def test_predicted_death_is_absorbing_even_when_potential_income_returns(self):
        p = audit.project(4620, 201, 8, 55, 0)
        for tick, state in p["steps"].items():
            if tick >= 6840:
                self.assertEqual((state["energy"], state["stress"], state["dead"]), (0, 8, True))
            if tick > 6840:
                self.assertEqual(state["credited_income"], 0)
                self.assertEqual(state["upkeep_paid"], 0)
        self.assertGreater(p["steps"][6885]["potential_income"], 0)

    def test_projection_is_cycle_shift_invariant(self):
        a, b = (audit.project(t, 201, 8, 55, 0) for t in (4620, 8460))
        self.assertEqual({t+3840: s for t, s in a["steps"].items()}, b["steps"])
        self.assertEqual(a["death_tick"]+3840, b["death_tick"])

    def test_future_spending_cannot_leak_into_prediction(self):
        before, changed = samples(), samples(extra="growth")
        original = copy.deepcopy((before, changed))
        a = audit.audit_purchase(before, "control", 2, 4620)
        b = audit.audit_purchase(changed, "control", 2, 4620)
        self.assertEqual(a["prediction"], b["prediction"])
        self.assertEqual(a["comparison"]["endpoints"]["sunset"]["prediction"],
                         b["comparison"]["endpoints"]["sunset"]["prediction"])
        self.assertNotEqual(a["actual"]["budget"], b["actual"]["budget"])
        self.assertEqual((before, changed), original)

    def test_optional_spending_excludes_the_break_step_from_valid_prefix(self):
        for kind in ("growth", "renewal", "seed"):
            r = audit.audit_purchase(samples(extra=kind), "control", 2, 4620)
            first = 4680 if kind == "seed" else 4635
            self.assertEqual(r["actual"]["first_assumption_break_tick"], first)
            count = r["comparison"]["errors"]["assumption_valid_prefix"]["energy"]["count"]
            self.assertEqual(count, (first - 4620) // 15 - 1)
            self.assertFalse(r["comparison"]["endpoints"]["sunset"]["assumptions_held"])

    def test_mature_leaf_change_counts_as_body_change_without_new_nodes(self):
        s = samples()
        s[4635]["plants"][0]["active_leaves"] += 1
        r = audit.observe(s, 2, 4620, 4800)
        self.assertEqual(r["assumption_breaks"]["body_change"], {"tick": 4635, "fields": ["active_leaves"]})

    def test_exact_zero_after_fully_paid_upkeep_reduces_stress(self):
        old, p = plant(energy=7, stress=7), plant(energy=0, water=507, stress=6)
        values = audit.startup.resources.budget(old, p, 6840)
        audit.check_stress(old, p, 6840, values)
        p["stress"] = 7
        with self.assertRaisesRegex(RuntimeError, "stress"):
            audit.check_stress(old, p, 6840, values)

    def test_water_shortage_is_flagged_and_not_assumed_energy_stress(self):
        s = {6825: fixtures.row(6825, plant(water=0)),
             6840: fixtures.row(6840, plant(energy=248, water=0, stress=1, flags=4))}
        r = audit.observe(s, 2, 6825, 6840)
        self.assertEqual(r["assumption_breaks"]["water_shortage"], {"tick": 6840})
        self.assertIsNone(r["first_energy_shortage_tick"])
        self.assertEqual(r["peak_stress"], 1)

    def test_missing_census_disappearance_and_wrong_stress_rejected(self):
        for defect in ("missing", "absent", "stress"):
            s = samples()
            if defect == "missing": del s[4650]
            elif defect == "absent": s[4650]["plants"] = []
            else: s[4650]["plants"][0]["stress"] = 1
            with self.subTest(defect=defect), self.assertRaises(RuntimeError): audit.observe(s, 2, 4620, 4800)

    def test_terminal_income_never_reconstructed_even_with_future_horizon(self):
        s = {6825: fixtures.row(6825, plant(energy=0, stress=7, flags=2)),
             6840: fixtures.row(6840, plant(energy=0, water=0, dead=True, stress=8, flags=3))}
        with patch.object(audit.startup.resources, "budget", side_effect=AssertionError("death is not a live budget")):
            r = audit.observe(s, 2, 6825, 6900)
        self.assertEqual(r["outcome"], "dead")
        self.assertEqual(r["death"], {"tick": 6840, "cause": "energy"})
        self.assertEqual(r["checked_live_steps"], 0)
        self.assertEqual(r["budget"], {})
        self.assertEqual(r["terminal_step_not_reconstructed"], 6840)
        s[6840]["plants"][0]["energy_income"] = 1
        with self.assertRaisesRegex(RuntimeError, "uncleared"):
            audit.observe(s, 2, 6825, 6900)

    def test_live_right_censor_is_not_survival_and_death_endpoints_have_no_energy_error(self):
        r = audit.audit_purchase(samples(), "control", 2, 4620)
        self.assertEqual(r["actual"]["outcome"], "right-censored")
        self.assertEqual(r["comparison"]["endpoints"]["noon"]["status"], "trace-censored")
        self.assertNotIn("actual", r["comparison"]["endpoints"]["noon"])
        p = audit.project(4620, 201, 8, 55, 0)
        a = audit.observe(samples(), 2, 4620, 7680)
        a["death"] = {"tick": 6660, "cause": "energy"}
        a["outcome"] = "dead"
        c = audit.compare(p, a, {"projected_sunset": 224})
        self.assertEqual(c["endpoints"]["dawn"]["status"], "observed-dead")
        self.assertNotIn("energy_error", c["endpoints"]["dawn"])

    def test_confusion_counts_every_record_with_explicit_exclusions(self):
        def record(outcome, predicted, cut=None, supported=True):
            return {"prediction": {"supported": supported, "death_tick": predicted},
                    "actual": {"outcome": outcome, "first_assumption_break_tick": cut}}
        records = [record("dead", 10), record("dead", None), record("alive", 10), record("alive", None),
                   record("right-censored", None), record("dead", None, supported=False), record("dead", 10, cut=5)]
        self.assertEqual(audit.confusion(records, clean=False), {"true_death": 2, "missed_death": 1,
            "false_death": 1, "true_survival": 1, "right_censored": 1, "unsupported": 1})
        self.assertEqual(audit.confusion(records, clean=True)["assumption_broken"], 1)
        self.assertEqual(sum(audit.confusion(records, clean=True).values()), 7)

    def test_error_statistics_keep_signed_absolute_and_empty_counts(self):
        a = audit.error_stats([3, -3, 1])
        self.assertEqual(a, {"count": 3, "signed_sum": 1, "absolute_sum": 7, "maximum_absolute": 3})
        self.assertEqual(audit.merge_errors([a, audit.error_stats([])]), a)
        self.assertEqual(audit.merge_errors([]), audit.error_stats([]))

    def test_worst_sample_is_locatable_and_never_crosses_prefix_boundary(self):
        r = audit.audit_purchase(samples(), "control", 2, 4620)
        peak = r["comparison"]["errors"]["assumption_valid_prefix"]["energy"]["worst_sample"]
        self.assertEqual(peak, {"tick": 4635, "error": 1, "predicted": 209, "actual": 208})
        r = audit.audit_purchase(samples(extra="growth"), "control", 2, 4620)
        self.assertIsNone(r["comparison"]["errors"]["assumption_valid_prefix"]["energy"]["worst_sample"])

    def test_old_provenance_must_match_before_any_reanalysis(self):
        with patch.object(audit.experiment, "digest", return_value="changed"), patch.object(audit.prior, "verify") as verify:
            with self.assertRaisesRegex(RuntimeError, "previous audit changed"):
                audit.verify(audit.experiment.ROOT)
            verify.assert_not_called()


if __name__ == "__main__":
    unittest.main()
