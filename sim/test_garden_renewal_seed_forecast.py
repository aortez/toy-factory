#!/usr/bin/env python3
"""Offline forecast timing, purchase reconstruction and censored-budget tests."""
import copy
import unittest
from unittest.mock import patch

import garden_renewal_seed_forecast as audit


def plant(**changes):
    return {"id": 2, "species": "shrub", "energy": 255, "water": 512, "nodes": 55,
            "roots": 18, "active_leaves": 36, "vigor": 0, "dead": False, "stress": 0,
            "flags": 0, "energy_income": 0, "water_income": 0, "spent_flowers": 3,
            "reproduction_cooldown": 0, "agent": {"extend": 0, "finish": 0, "wait": 0},
            "leaf": {"renewals": 0}, **changes}


def row(tick, p, **changes):
    return {"tick": tick, "sun_phase": (64 + tick // 15) % 256, "sun_strength": 67,
            "plants": [p], "seeds_created": 0, "seeds": [], **changes}


def purchase_samples(extra=None):
    before = plant()
    after = plant(energy=201, water=483, energy_income=8, spent_flowers=4, reproduction_cooldown=16)
    samples = {4605: row(4605, before), 4620: row(4620, after, seeds_created=1, seeds=[{"parent": 2}])}
    energy, water = 201, 483
    for tick in range(4635, 4801, 15):
        income = 7 if tick == 4635 else 0
        energy += income - (7 if tick % 60 == 0 else 0)
        water -= 5 if tick % 60 == 0 else 0
        p = plant(energy_income=income, spent_flowers=4,
                  reproduction_cooldown=max(0, 16 - (tick - 4620) // 15))
        if extra == "growth":
            p["agent"]["finish"] = 1
        if extra == "renewal":
            p["leaf"]["renewals"] = 1
        if extra in ("growth", "renewal") and tick == 4635:
            energy -= 8 if extra == "growth" else 9
            water -= 5
        if extra == "seed" and tick >= 4680:
            p["spent_flowers"] = 5
            p["reproduction_cooldown"] = 16 - (tick - 4680) // 15
            if tick == 4680:
                energy -= 48
                water -= 24
        p.update(energy=energy, water=water)
        samples[tick] = row(tick, p)
    return samples


class SeedForecastTests(unittest.TestCase):
    def test_fixed_scope_and_phase_boundaries(self):
        self.assertEqual(audit.CASES, (("control", 2), ("veto", 3)))
        self.assertEqual((audit.PURCHASE, audit.SUNSET, audit.LAST_NIGHT, audit.DAWN, audit.STOP),
                         (4620, 4800, 6705, 6720, 7140))
        night = range(audit.SUNSET + 15, audit.LAST_NIGHT + 1, 15)
        self.assertEqual(len([t for t in night if t % 60 == 0]), 31)
        self.assertNotIn(audit.DAWN, night)

    def test_reference_boundaries_match_frozen_c_fixtures(self):
        for args, sunset, upkeep, allowed in (
            ((240, 0, 48, 124), 186, 6, True), ((239, 0, 48, 124), 185, 6, False),
            ((240, 0, 49, 124), 185, 7, False), ((248, 255, 64, 124), 248, 8, True),
            ((248, 255, 65, 124), 247, 9, False), ((248, 38, 64, 124), 248, 8, True),
            ((248, 36, 64, 124), 246, 8, False), ((248, 30, 64, 124), 237, 8, False),
        ):
            with self.subTest(args=args):
                f = audit.forecast_ledger(*args)
                self.assertEqual((f["projected_sunset"], f["maintenance_cost"], f["allowed"]),
                                 (sunset, upkeep, allowed))

    def test_income_floor_cap_before_upkeep_and_current_step_exclusion(self):
        f = audit.forecast_ledger(249, 8, 55, 116)
        self.assertEqual(f["after_seed"], 201)
        self.assertEqual([s["phase"] for s in f["steps"]], list(range(117, 129)))
        self.assertEqual(f["budget"], {"energy_income": 44, "energy_overflow": 0, "energy_upkeep": 21})
        self.assertEqual([s["phase"] for s in f["steps"] if s["upkeep"]], [120, 124, 128])
        self.assertEqual(f["steps"][-1]["income"], 0)
        odd = audit.forecast_ledger(248, 7, 59, 116)
        self.assertEqual(odd["budget"]["energy_income"], 33)
        capped = audit.forecast_ledger(248, 255, 64, 124)
        self.assertEqual(capped["budget"], {"energy_income": 381, "energy_overflow": 325, "energy_upkeep": 8})
        self.assertEqual(capped["steps"][-1]["projected_energy"], 248)

    def test_invalid_forecast_inputs_and_non_daylight_audit_rejected(self):
        for args in ((257, 8, 55, 116), (-1, 8, 55, 116), (249, 256, 55, 116),
                     (249, 8, 0, 116), (249, 8, 513, 116), (249, 8, 55, 0),
                     (249, 8, 55, 128), (249, 8, 55, 255)):
            with self.subTest(args=args), self.assertRaises(RuntimeError):
                audit.forecast_ledger(*args)

    def test_reconstructs_decision_after_current_cap_and_upkeep(self):
        samples = purchase_samples()
        original = copy.deepcopy(samples)
        d = audit.decision(samples, 2, 4620)
        self.assertEqual((d["energy_before_seed"], d["energy_after_seed"]), (249, 201))
        self.assertEqual(d["current_step_budget"]["energy_overflow"], 7)
        self.assertEqual(d["current_step_budget"]["energy_upkeep"], 7)
        self.assertEqual(d["forecast"]["projected_sunset"], 224)
        self.assertEqual(samples, original)

    def test_purchase_requires_flags_cooldown_debit_and_seed_parent(self):
        for key, value in (("spent_flowers", 3), ("reproduction_cooldown", 15), ("energy", 202), ("dead", True)):
            samples = purchase_samples()
            samples[4620]["plants"][0][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                audit.decision(samples, 2, 4620)
        for key, value in (("seeds_created", 0), ("seeds", [{"parent": 3}]), ("seeds", [])):
            samples = purchase_samples()
            samples[4620][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, "seed bank"):
                audit.decision(samples, 2, 4620)

    def test_daylight_error_has_exact_accounting(self):
        samples = purchase_samples()
        w = audit.window(samples, 2, 4620, 4800, detailed=True)
        c = audit.compare_daylight(audit.decision(samples, 2, 4620), w)
        self.assertEqual(w["checked_live_steps"], 12)
        self.assertEqual(w["end"]["energy"], 187)
        self.assertEqual(c["sunset_overestimate"], 37)
        self.assertEqual(c["error_terms"], {"income_overestimate": 37, "overflow_difference": 0,
                                            "upkeep_difference": 0, "optional_spending": 0})
        self.assertEqual((c["projected_night_margin"], c["actual_night_margin_fixed_body"]), (7, -30))

    def test_optional_spending_is_not_misattributed_to_income(self):
        for kind, cost in (("growth", 8), ("renewal", 9), ("seed", 48)):
            samples = purchase_samples(extra=kind)
            c = audit.compare_daylight(audit.decision(samples, 2, 4620),
                audit.window(samples, 2, 4620, 4800, detailed=True))
            with self.subTest(kind=kind):
                self.assertEqual(c["error_terms"]["income_overestimate"], 37)
                self.assertEqual(c["error_terms"]["optional_spending"], cost)
                self.assertEqual(c["sunset_overestimate"], 37 + cost)

    def test_missing_wrong_phase_and_duplicate_lineage_rejected(self):
        for corruption in ("missing", "phase", "duplicate"):
            samples = purchase_samples()
            if corruption == "missing":
                del samples[4650]
            elif corruption == "phase":
                samples[4650]["sun_phase"] += 1
            else:
                samples[4650]["plants"] *= 2
            with self.subTest(corruption=corruption), self.assertRaises(RuntimeError):
                audit.window(samples, 2, 4620, 4800)

    def test_requested_and_paid_upkeep_are_distinct(self):
        samples = {6825: row(6825, plant(energy=4)),
                   6840: row(6840, plant(energy=0, water=507, stress=1, flags=2))}
        w = audit.window(samples, 2, 6825, 6840)
        self.assertEqual(w["upkeep_required_checked_live"], 7)
        self.assertEqual(w["budget"]["energy_upkeep"], 4)
        self.assertEqual(w["upkeep_unpaid_checked_live"], 3)

    def test_terminal_step_never_reconstructed_or_counted_as_upkeep(self):
        samples = {6825: row(6825, plant(energy=0, stress=7, flags=2)),
                   6840: row(6840, plant(energy=0, water=0, dead=True, stress=8, flags=3)),
                   6855: row(6855, plant(energy=0, water=0, dead=True, stress=8, flags=3))}
        with patch.object(audit.startup.resources, "budget", side_effect=AssertionError("must not reconcile death")):
            w = audit.window(samples, 2, 6825, 6855)
        self.assertEqual(w["terminal_step_not_reconstructed"], 6840)
        self.assertEqual(w["checked_live_steps"], 0)
        self.assertEqual(w["upkeep_required_checked_live"], 0)
        self.assertEqual(w["budget"], {})
        self.assertFalse(w["complete_live_window"])
        samples[6855]["plants"][0]["dead"] = False
        with self.assertRaisesRegex(RuntimeError, "revived"):
            audit.window(samples, 2, 6825, 6855)

    def test_already_dead_window_and_live_disappearance(self):
        samples = {6705: row(6705, plant(dead=True, energy=0)),
                   6720: row(6720, plant(dead=True, energy=0))}
        w = audit.window(samples, 2, 6705, 6720)
        self.assertTrue(w["already_dead_at_start"])
        self.assertIsNone(w["last_live_tick"])
        self.assertIsNone(w["terminal_step_not_reconstructed"])
        self.assertEqual(w["checked_live_steps"], 0)
        samples[6705]["plants"][0]["dead"] = False
        samples[6720]["plants"] = []
        with self.assertRaisesRegex(RuntimeError, "disappeared"):
            audit.window(samples, 2, 6705, 6720)

    def test_wrong_manifest_rejected_before_baseline_analysis(self):
        with patch.object(audit.experiment, "digest", return_value="wrong"), patch.object(audit.prior, "verify") as verify:
            with self.assertRaisesRegex(RuntimeError, "baseline"):
                audit.verify(audit.experiment.ROOT)
            verify.assert_not_called()

    def test_zero_income_gap_excludes_both_productive_boundaries(self):
        samples = {t: {"sun_strength": 63 if 4650 <= t < 6885 else 64}
                   for t in range(4620, 7141, 15)}
        gap = audit.zero_income_interval(samples, [55, 59])
        self.assertEqual((gap["start_inclusive"], gap["end_inclusive"]), (4650, 6870))
        self.assertEqual(gap["previous_possible_income_tick"], 4635)
        self.assertEqual(gap["earliest_possible_income_tick"], 6885)
        self.assertEqual(len(gap["upkeep_ticks"]), 37)
        self.assertEqual(gap["upkeep_ticks"][:3], [4680, 4740, 4800])
        self.assertEqual(gap["upkeep_ticks"][-3:], [6720, 6780, 6840])
        self.assertEqual(gap["fixed_body_lower_bounds"], [
            {"nodes": 55, "upkeep": 7, "required_energy": 259, "minimum_unpaid_from_full_storage": 3},
            {"nodes": 59, "upkeep": 8, "required_energy": 296, "minimum_unpaid_from_full_storage": 40}])
        del samples[4650]
        with self.assertRaisesRegex(RuntimeError, "missing"):
            audit.zero_income_interval(samples, [55])

    def test_zero_income_gap_requires_darkness_and_returning_light(self):
        for strength in (63, 64):
            samples = {t: {"sun_strength": strength} for t in range(4620, 7141, 15)}
            with self.subTest(strength=strength), self.assertRaisesRegex(RuntimeError, "missing"):
                audit.zero_income_interval(samples, [55])


if __name__ == "__main__":
    unittest.main()
