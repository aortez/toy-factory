#!/usr/bin/env python3
"""Exact dark boundaries, stage accounting, stress and observation exclusions."""
import copy
import unittest
from unittest.mock import patch

import garden_renewal_dark_budget as audit
import test_garden_renewal_seed_forecast as fixtures


def plant(**changes):
    return fixtures.plant(**{"nodes": 55, "roots": 18, "leaves": 36, "energy": 256,
                             "water": 512, **changes})


def row(tick, p):
    return fixtures.row(tick, p, sun_strength=audit.prior.sun_strength((64 + tick // 15) % 256))


def dark_samples(start=4635, end=6870, *, energy=256, stress=0, expenses=None):
    """Small synthetic ledger, with optional post-maintenance expenses."""
    p = plant(energy=energy, stress=stress)
    result = {start: row(start, copy.deepcopy(p))}
    for tick in range(start + 15, end + 1, 15):
        p = copy.deepcopy(p)
        p["reproduction_cooldown"] = max(0, p["reproduction_cooldown"] - 1)
        if tick % 60 == 0:
            energy_due = (p["nodes"] + 7) // 8
            water_due = (p["nodes"] - p["roots"] + 7) // 8
            p["flags"] = (2 if p["energy"] < energy_due else 0) | (4 if p["water"] < water_due else 0)
            p["energy"] = max(0, p["energy"] - energy_due)
            p["water"] = max(0, p["water"] - water_due)
            p["stress"] = p["stress"] + 1 if p["flags"] else max(0, p["stress"] - 1)
            if p["stress"] == 8:
                p.update(dead=True, energy=0, water=0, flags=p["flags"] | 1)
        if not p["dead"] and tick in (expenses or {}):
            kind = expenses[tick]
            if kind == "growth":
                p["agent"]["extend"] += 1
                p["nodes"] += 1
                p["energy"] -= 8
                p["water"] -= 5
            elif kind == "renewal":
                p["leaf"]["renewals"] += 1
                p["energy"] -= 9
                p["water"] -= 5
            elif kind == "seeds":
                p["reproduction_cooldown"] = 16
                p["energy"] -= 48
                p["water"] -= 24
            else:
                raise AssertionError("unknown fixture expense")
        result[tick] = row(tick, p)
        if p["dead"]:
            break
    return result


class DarkBudgetTests(unittest.TestCase):
    def test_every_phase_has_explicit_coverage_and_bounded_horizon(self):
        for phase in range(256):
            tick = ((phase - 64) % 256) * 15
            h = audit.horizon(tick)
            supported = phase >= 117 or phase < 10
            self.assertEqual(h["dark_steps"] > 0, supported)
            self.assertLessEqual(h["dark_steps"], 149)
            self.assertGreaterEqual(audit.prior.sun_strength((64+h["first_possible_income_tick"]//15) % 256), 64)
            self.assertTrue(all(audit.prior.sun_strength((64+t//15) % 256) < 64
                                for t in range(tick+15, h["first_possible_income_tick"], 15)))

    def test_last_productive_anchor_includes_all_37_future_payments(self):
        h = audit.horizon(4635)
        self.assertEqual((h["first_possible_income_tick"], h["last_dark_tick"], h["dark_steps"]), (6885, 6870, 149))
        self.assertEqual(h["maintenance_ticks"], list(range(4680, 6841, 60)))
        self.assertEqual(audit.project(4635, 256, 55, 0)["fixed_body_demand_to_boundary"], 259)

    def test_daylight_and_empty_dawn_horizons_are_unsupported_not_approval(self):
        for tick in (0, 4620, 6870, 6885):
            p = audit.project(tick, 256, 55, 0)
            self.assertFalse(p["supported"])
            self.assertEqual(p["reason"], "next-step-could-earn-income")
            self.assertNotIn("classification", p)
            self.assertEqual(p["steps"], {})

    def test_early_morning_zero_payment_check_is_not_whole_night_survival(self):
        p = audit.project(6840, 0, 512, 7)
        self.assertEqual(p["classification"], "no-maintenance")
        self.assertEqual(p["final"], {"energy": 0, "stress": 7, "dead": False})
        self.assertEqual(list(p["steps"]), [6855, 6870])

    def test_anchor_maintenance_is_not_charged_twice(self):
        p = audit.project(4680, 200, 59, 0)
        self.assertNotIn(4680, p["steps"])
        self.assertEqual(p["boundaries"]["maintenance_ticks"][0], 4740)
        self.assertEqual(p["steps"][4695]["energy"], 200)
        self.assertEqual(p["steps"][4740]["energy"], 192)

    def test_known_shortage_survivor_and_energy_stress_deaths(self):
        survivor = audit.project(4635, 256, 55, 0)
        self.assertEqual(survivor["classification"], "shortage-alive")
        self.assertEqual(survivor["final"], {"energy": 0, "stress": 1, "dead": False})
        self.assertEqual(survivor["first_shortage_tick"], 6840)
        self.assertEqual(survivor["upkeep_unpaid_until_death_or_boundary"], 3)
        self.assertEqual(audit.project(4635, 208, 55, 0)["death_tick"], 6840)
        self.assertEqual(audit.project(4635, 207, 59, 0)["death_tick"], 6600)
        self.assertEqual(audit.project(12360, 200, 59, 0)["death_tick"], 14340)
        self.assertEqual(audit.project(23880, 201, 56, 0)["death_tick"], 26040)

    def test_full_last_payment_recovers_stress_partial_payment_increases_it(self):
        paid = audit.project(6780, 7, 55, 7)
        partial = audit.project(6780, 6, 55, 7)
        self.assertEqual(paid["final"], {"energy": 0, "stress": 6, "dead": False})
        self.assertEqual(paid["classification"], "all-paid")
        self.assertEqual(partial["death_tick"], 6840)
        self.assertEqual(partial["steps"][6840]["upkeep_unpaid"], 1)

    def test_death_absorbs_later_payments_and_state_changes(self):
        p = audit.project(4635, 0, 55, 7)
        self.assertEqual(p["death_tick"], 4680)
        for tick, state in p["steps"].items():
            if tick > 4680:
                self.assertEqual(state, {"energy": 0, "stress": 8, "dead": True,
                                         "upkeep_required": 0, "upkeep_paid": 0, "upkeep_unpaid": 0})

    def test_closed_form_payment_oracle_across_store_body_and_stress_boundaries(self):
        for tick in (4635, 4680, 4800, 6705, 6855):
            payments = audit.horizon(tick)["maintenance_ticks"]
            for energy in (0, 1, 6, 7, 8, 55, 200, 255, 256):
                for nodes in (1, 8, 9, 55, 59, 512):
                    for stress in (0, 1, 7):
                        upkeep = (nodes+7)//8
                        successes = min(len(payments), energy//upkeep)
                        recovered = max(0, stress-successes)
                        failures_to_death = 8-recovered
                        death_index = successes+failures_to_death-1
                        death = payments[death_index] if death_index < len(payments) else None
                        p = audit.project(tick, energy, nodes, stress)
                        self.assertEqual(p["death_tick"], death)
                        self.assertEqual(p["final"]["stress"], min(8, recovered+len(payments)-successes))
                        self.assertEqual(p["final"]["energy"], max(0, energy-upkeep*len(payments)))

    def test_invalid_inputs_including_bool_fail_closed(self):
        for tick in (-15, 1, 4635.0, True):
            with self.assertRaises(RuntimeError): audit.horizon(tick)
        for args in ((-1, 8, 0), (257, 8, 0), (256, 0, 0), (256, 513, 0),
                     (256, 8, -1), (256, 8, 8), (256, 8.0, 0), (True, 8, 0)):
            with self.subTest(args=args), self.assertRaises(RuntimeError): audit.project(4635, *args)

    def test_cycle_shift_and_inputs_are_unchanged(self):
        a, b = (audit.project(t, 200, 59, 0) for t in (4680, 8520))
        self.assertEqual({t+3840: s for t, s in a["steps"].items()}, b["steps"])
        self.assertEqual(a["death_tick"]+3840, b["death_tick"])

    def test_stage_order_renewal_then_seed_uses_intermediate_stores(self):
        old = plant(nodes=8, roots=2)
        p = plant(nodes=8, roots=2, energy=198, water=482, reproduction_cooldown=16, leaf={"renewals": 1})
        values = audit.startup.resources.budget(old, p, 4680)
        stages = audit.spending_stages(old, p, 4680, values)
        self.assertEqual([s["kind"] for s in stages], ["renewal", "seeds"])
        self.assertEqual([s["before"]["energy"] for s in stages], [255, 246])
        self.assertEqual([s["after"]["energy"] for s in stages], [246, 198])
        self.assertEqual([s["after"]["nodes"] for s in stages], [8, 8])

    def test_growth_charges_old_body_now_but_new_body_in_future(self):
        old = plant(nodes=8, roots=2)
        p = plant(nodes=9, roots=2, energy=247, water=506, agent={"extend": 1, "finish": 0, "wait": 0})
        values = audit.startup.resources.budget(old, p, 4680)
        self.assertEqual(values["energy_upkeep"], 1)
        stage, = audit.spending_stages(old, p, 4680, values)
        self.assertEqual((stage["before_budget"]["maintenance_cost"], stage["after_budget"]["maintenance_cost"]), (1, 2))

    def test_seed_after_growth_uses_post_growth_body_and_store(self):
        old = plant(nodes=8, roots=2)
        p = plant(nodes=9, roots=2, energy=199, water=482, reproduction_cooldown=16,
                  agent={"extend": 1, "finish": 0, "wait": 0})
        values = audit.startup.resources.budget(old, p, 4680)
        growth, seed = audit.spending_stages(old, p, 4680, values)
        self.assertEqual(growth["after"], seed["before"])
        self.assertEqual(seed["before"]["nodes"], 9)
        self.assertEqual(seed["before"]["energy"], 247)
        self.assertEqual(seed["after"]["energy"], 199)

    def test_finish_expense_need_not_add_nodes(self):
        old = plant()
        p = plant(energy=248, water=507, agent={"extend": 0, "finish": 1, "wait": 0})
        stage, = audit.spending_stages(old, p, 4635, audit.startup.resources.budget(old, p, 4635))
        self.assertEqual(stage["action"], "finish")
        self.assertEqual(stage["before"]["nodes"], stage["after"]["nodes"])

    def test_newborn_starts_with_four_nodes_and_no_current_maintenance(self):
        p = plant(nodes=5, roots=2, energy=56, water=19, agent={"extend": 1, "finish": 0, "wait": 0})
        values = audit.startup.resources.budget(None, p, 4680)
        stage, = audit.spending_stages(None, p, 4680, values)
        self.assertEqual(stage["before"], {"energy": 64, "water": 24, "nodes": 4, "stress": 0})
        self.assertEqual(values["energy_upkeep"], 0)

    def test_stage_local_fatal_flip_is_separate_from_actual_rollout(self):
        old = plant(energy=256, nodes=59)
        p = plant(energy=200, water=482, nodes=59, reproduction_cooldown=16)
        stage, = audit.spending_stages(old, p, 12360, audit.startup.resources.budget(old, p, 12360))
        self.assertEqual(stage["local_effect"], "becomes-fatal")
        self.assertIsNone(stage["before_budget"]["death_tick"])
        self.assertEqual(stage["after_budget"]["death_tick"], 14340)

    def test_unexplained_body_change_and_bad_pre_stores_are_rejected(self):
        old, p = plant(), plant()
        values = audit.startup.resources.budget(old, p, 4635)
        p["nodes"] += 1
        with self.assertRaisesRegex(RuntimeError, "body change"): audit.spending_stages(old, p, 4635, values)
        p = plant()
        values["energy_renewal"] = 9
        with self.assertRaisesRegex(RuntimeError, "stores"): audit.spending_stages(old, p, 4635, values)

    def test_clean_shortage_survival_checks_every_step_exactly(self):
        r = audit.audit_state(dark_samples(), "control", 2, 4635, "evening")
        self.assertEqual(r["comparison"]["status"], "exact-alive-at-boundary")
        self.assertEqual(r["prediction"]["classification"], "shortage-alive")
        self.assertEqual(r["actual"]["checked_live_steps"], 149)
        self.assertEqual(r["actual"]["peak_stress"], 1)
        self.assertEqual(r["comparison"]["errors"]["valid_prefix"]["energy"]["absolute_sum"], 0)

    def test_clean_death_timing_uses_terminal_state_not_a_fictional_budget(self):
        r = audit.audit_state(dark_samples(energy=208), "control", 2, 4635, "evening")
        self.assertEqual(r["comparison"]["status"], "exact-death")
        self.assertEqual(r["actual"]["death"], {"tick": 6840, "cause": "energy"})
        self.assertEqual(r["actual"]["terminal_step_not_reconstructed"], 6840)
        self.assertEqual(r["actual"]["budget"]["energy_upkeep"], 208)

    def test_later_expenses_break_assumptions_without_changing_prediction(self):
        normal = dark_samples()
        original = copy.deepcopy(normal)
        a = audit.audit_state(normal, "control", 2, 4635, "evening")
        for kind in audit.KINDS:
            changed = dark_samples(expenses={4665: kind})
            b = audit.audit_state(changed, "control", 2, 4635, "evening")
            self.assertEqual(a["prediction"], b["prediction"])
            self.assertEqual(b["actual"]["first_assumption_break_tick"], 4665)
            self.assertEqual(b["comparison"]["status"], "assumption-broken")
            self.assertEqual(b["comparison"]["errors"]["valid_prefix"]["energy"]["count"], 1)
        self.assertEqual(normal, original)

    def test_maturation_and_root_counts_do_not_break_zero_energy_income(self):
        s = dark_samples(end=4650)
        p = s[4650]["plants"][0]
        p.update(active_leaves=37, leaves=37, roots=19)
        r = audit.observe(s, 2, 4635, 4650)
        self.assertEqual(r["assumption_breaks"], {})

    def test_changed_energy_upkeep_breaks_even_if_node_growth_is_not_paid(self):
        s = dark_samples(end=4650)
        s[4650]["plants"][0]["nodes"] = 57
        r = audit.observe(s, 2, 4635, 4650)
        self.assertEqual(r["assumption_breaks"]["energy_upkeep_change"], {"tick": 4650, "nodes": 57})

    def test_water_stress_is_an_explicit_break(self):
        old = plant(energy=20, water=0)
        p = plant(energy=13, water=0, stress=1, flags=4)
        r = audit.observe({6825: row(6825, old), 6840: row(6840, p)}, 2, 6825, 6840)
        self.assertEqual(r["assumption_breaks"], {"water_shortage": {"tick": 6840}})

    def test_old_water_flag_between_maintenance_is_not_a_new_shortage(self):
        p = plant(stress=3, flags=4)
        s = {4800: row(4800, p), 4815: row(4815, copy.deepcopy(p))}
        r = audit.observe(s, 2, 4800, 6870)
        self.assertEqual(r["assumption_breaks"], {})
        self.assertEqual(audit.compare(audit.project(4800, 256, 55, 3), r)["status"], "right-censored")

    def test_missing_duplicate_disappearing_and_inconsistent_records_fail(self):
        for defect in ("missing", "duplicate", "absent", "phase", "stress", "income"):
            s = dark_samples(end=4680)
            if defect == "missing": del s[4650]
            elif defect == "duplicate": s[4650]["plants"] *= 2
            elif defect == "absent": s[4650]["plants"] = []
            elif defect == "phase": s[4650]["sun_phase"] += 1
            elif defect == "stress": s[4650]["plants"][0]["stress"] = 1
            else: s[4650]["plants"][0]["energy_income"] = 1  # Capped, so ledger itself still reconciles.
            with self.subTest(defect=defect), self.assertRaises(RuntimeError): audit.observe(s, 2, 4635, 4680)

    def test_terminal_step_cannot_be_used_as_live_budget(self):
        s = dark_samples(energy=0, stress=7, start=4665, end=4680)
        with patch.object(audit.startup.resources, "budget", side_effect=AssertionError("not a live step")):
            r = audit.observe(s, 2, 4665, 4680)
        self.assertEqual(r["checked_live_steps"], 0)
        self.assertEqual(r["budget"], {})
        self.assertEqual(r["first_energy_shortage_tick"], 4680)
        s[4680]["plants"][0]["energy_income"] = 1
        with self.assertRaisesRegex(RuntimeError, "uncleared"): audit.observe(s, 2, 4665, 4680)

    def test_right_censor_is_not_a_survivor_and_unsupported_does_not_observe(self):
        r = audit.audit_state(dark_samples(end=4680), "control", 2, 4635, "evening")
        self.assertEqual(r["actual"]["outcome"], "right-censored")
        self.assertEqual(r["comparison"]["status"], "right-censored")
        with patch.object(audit, "observe", side_effect=AssertionError("daylight has no exact window")):
            r = audit.audit_state({4620: row(4620, plant())}, "control", 2, 4620, "spending")
        self.assertIsNone(r["actual"])

    def test_first_possible_income_step_is_never_observed_or_credited(self):
        s = dark_samples()
        p = copy.deepcopy(s[6870]["plants"][0])
        p.update(energy=7, energy_income=7)
        s[6885] = row(6885, p)
        r = audit.audit_state(s, "control", 2, 4635, "evening")
        self.assertEqual(r["actual"]["last_live_tick"], 6870)
        self.assertEqual(r["actual"]["last_live_state"], {"energy": 0, "stress": 1})
        self.assertEqual(r["actual"]["budget"]["energy_income"], 0)
        with self.assertRaisesRegex(RuntimeError, "crosses dark boundary"):
            audit.observe(s, 2, 4635, 6885)

    def test_terminal_water_shortage_excludes_energy_only_death_comparison(self):
        old = plant(energy=20, water=0, stress=7, flags=4)
        dead = plant(energy=0, water=0, dead=True, stress=8, flags=5)
        s = {6825: row(6825, old), 6840: row(6840, dead)}
        r = audit.audit_state(s, "control", 2, 6825, "evening")
        self.assertEqual(r["actual"]["death"], {"tick": 6840, "cause": "water"})
        self.assertEqual(r["comparison"]["status"], "assumption-broken")
        self.assertIsNone(r["prediction"]["death_tick"])

    def test_exact_comparison_rejects_wrong_energy_and_death_timing(self):
        s = dark_samples(energy=208)
        a = audit.observe(s, 2, 4635, 6870)
        prediction = audit.project(4635, 208, 55, 0)
        prediction["steps"][4650]["energy"] += 1
        with self.assertRaisesRegex(RuntimeError, "prefix mismatch"): audit.compare(prediction, a)
        prediction = audit.project(4635, 208, 55, 0)
        prediction["death_tick"] -= 60
        with self.assertRaisesRegex(RuntimeError, "death mismatch"): audit.compare(prediction, a)

    def test_short_observation_cannot_be_compared_as_a_full_dark_horizon(self):
        a = audit.observe(dark_samples(end=4680), 2, 4635, 4680)
        with self.assertRaisesRegex(RuntimeError, "matching dark horizon"):
            audit.compare(audit.project(4635, 256, 55, 0), a)

    def test_summary_keeps_panels_censoring_and_expense_units_distinct(self):
        records = [audit.audit_state(dark_samples(energy=e), "control", 2, 4635, "evening") for e in (208, 256)]
        records.append(audit.audit_state(dark_samples(end=4680), "veto", 2, 4635, "evening"))
        r = audit.summarize(records)
        self.assertEqual(r["anchors"], 3)
        self.assertEqual(r["observed_outcomes"], {"dead": 1, "alive": 1, "right-censored": 1})
        self.assertEqual(r["distinct_case_specific_deaths"], 1)
        self.assertEqual(r["expenses"], {})
        self.assertEqual(r["complete_clean_predictions"], {"death": 1, "shortage-alive": 1})

    def test_stale_provenance_fails_before_reanalysis(self):
        with patch.object(audit.experiment, "digest", return_value="changed"), patch.object(audit.prior, "verify") as verify:
            with self.assertRaisesRegex(RuntimeError, "previous audit changed"): audit.verify(audit.experiment.ROOT)
            verify.assert_not_called()


if __name__ == "__main__":
    unittest.main()
