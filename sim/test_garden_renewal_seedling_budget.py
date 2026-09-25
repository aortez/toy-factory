#!/usr/bin/env python3
"""Frozen seedling-cohort coverage, live-budget boundaries and censored nights."""
import copy
import unittest

import garden_renewal_seedling_budget as audit
from test_garden_renewal_seed_forecast import plant
from test_garden_renewal_dark_failures import history as dark_history


def fixture(birth=15, end=None, earn=True):
    end = end if end is not None else birth+3*audit.DAY
    rows, old, death = [], None, None
    for tick in range(0, end+1, 15):
        phase = (64+tick//15)%256
        if tick == birth:
            p = plant(id=10, energy=64, water=24, nodes=4, roots=2, leaves=1,
                      active_leaves=0, tips=1,
                      leaf={"conditions": [255], "renewals": 0, "restored": 0, "worn": 0})
        elif old is not None:
            p = copy.deepcopy(old)
            if not p["dead"]:
                p["energy_income"] = audit.reference.prior.sun_strength(phase)//64 if earn else 0
                p["water_income"] = min(1, 512-p["water"])
                p["energy"] = min(256, p["energy"]+p["energy_income"])
                p["water"] += p["water_income"]
                p["active_leaves"] = 1
                if tick%60 == 0:
                    p["flags"] = (2 if p["energy"] < 1 else 0) | (4 if p["water"] < 1 else 0)
                    p["energy"] = max(0, p["energy"]-1)
                    p["water"] = max(0, p["water"]-1)
                    p["stress"] = p["stress"]+1 if p["flags"] else max(0, p["stress"]-1)
                    if p["stress"] == 8:
                        p.update(dead=True, flags=p["flags"]|1, energy=0, water=0, energy_income=0, water_income=0)
                        death = tick
        else:
            p = None
        rows.append({"type": "world", "tick": tick, "sun_phase": phase,
                     "sun_strength": audit.reference.prior.sun_strength(phase), "plants": [p] if p else []})
        old = p
    record = {"id": 10, "parent": 7, "species": "shrub", "generation": 2,
              "birth_tick": birth, "death_tick": death}
    histories, checked = audit.failures.histories(rows, {}, {10: record}, end)
    return record, histories[10], rows, checked


class SeedlingTests(unittest.TestCase):
    def test_fixed_scope_and_pre_gap_exclusion(self):
        self.assertEqual((audit.STEP, audit.DAY, audit.DAYS), (15, 3840, 3))
        self.assertEqual(audit.COHORT, {"required": (10,), "optional": (10, 11, 12, 13, 14)})
        p = {"id": 10, "parent": 2, "birth_tick": 57360}
        self.assertEqual(audit.scope([{"id": 1, "parent": 0, "birth_tick": 0}, p], "required"), {10: p})
        for rows in ([], [dict(p, id=11)], [dict(p, birth_tick=audit.parent.AT)],
                     [dict(p, birth_tick=audit.parent.STOP)], [p, dict(p, id=11)]):
            with self.assertRaises(RuntimeError): audit.scope(rows, "required")

    def test_live_ledgers_and_three_days_partition_exactly(self):
        p, h, _, checked = fixture()
        result = audit.describe(p, h, {})
        self.assertEqual(checked, 769)
        self.assertEqual(result["checked_live_steps"], 769)
        self.assertEqual([d["observed_steps"] for d in result["days"]], [257, 256, 256])
        self.assertTrue(all(d["complete"] for d in result["days"]))
        self.assertIsNone(result["death"])
        self.assertEqual(result["first_possible_global_income_tick"], 30)
        self.assertEqual(result["first_observed_income_tick"], 30)
        self.assertTrue(all(w["status"] == "exact-survival" for w in result["dark_windows"]))
        self.assertEqual(result["budget"], audit.failures.budget_sum(h))

    def test_death_step_is_retained_but_never_charged_as_resource_spending(self):
        p, h, _, _ = fixture(earn=False)
        result = audit.describe(p, h, {})
        self.assertEqual(p["death_tick"], 4320)
        self.assertEqual(result["last_live"]["tick"], 4305)
        self.assertEqual(result["budget"]["energy_upkeep"], 64)
        self.assertEqual(result["terminal_budget"], "cleared-not-reconstructed")
        self.assertIsNone(result["steps"][-1]["budget"])
        self.assertIsNone(result["steps"][-1]["maintenance"])
        self.assertEqual(result["stress_episodes"][-1]["terminal_tick"], 4320)
        self.assertEqual(result["stress_episodes"][-1]["maintenance_shortages"]["energy"], 8)
        self.assertIsNone(result["first_observed_income_tick"])

    def test_maintenance_uses_old_body_and_distinguishes_unpaid_demand(self):
        old = {"nodes": 8, "roots": 2}
        p = {"tick": 60, "nodes": 9, "roots": 2}
        values = {"energy_upkeep": 0, "water_upkeep": 1}
        self.assertEqual(audit.maintenance(old, p, values),
                         {"energy": {"due": 1, "paid": 0, "unpaid": 1},
                          "water": {"due": 1, "paid": 1, "unpaid": 0}})
        self.assertIsNone(audit.maintenance(None, p, values))
        self.assertIsNone(audit.maintenance(old, dict(p, tick=75), values))
        self.assertIsNone(audit.maintenance(old, p, None))
        with self.assertRaises(RuntimeError):
            audit.maintenance(old, p, dict(values, energy_upkeep=2))

    def test_partial_first_night_and_right_censored_last_night(self):
        p, h, _, _ = fixture(birth=960)
        result = audit.describe(p, h, {})
        self.assertEqual(len(result["dark_windows"]), 4)
        self.assertEqual(result["dark_windows"][0]["anchor"]["tick"], 960)
        self.assertEqual(result["dark_windows"][-1]["status"], "trace-censored")

    def test_missing_duplicate_or_changed_focal_identity_rejected(self):
        p, h, _, _ = fixture()
        for changed in (h[:10]+h[11:], h[:10]+[h[9]]+h[10:]):
            with self.assertRaises(RuntimeError): audit.describe(p, changed, {})
        changed = copy.deepcopy(h)
        changed[4]["state"]["id"] = 11
        with self.assertRaises(RuntimeError): audit.describe(p, changed, {})

    def test_live_and_terminal_accounting_tampering_rejected(self):
        p, h, _, _ = fixture(earn=False)
        for index, defect in ((1, "missing"), (-1, "invented"), (1, "income")):
            changed = copy.deepcopy(h)
            if defect == "missing": changed[index]["budget"] = None
            elif defect == "invented": changed[index]["budget"] = h[1]["budget"]
            else: changed[index]["budget"]["energy_income"] += 1
            with self.assertRaises(RuntimeError): audit.describe(p, changed, {})

    def test_full_census_stress_and_resource_corruption_fail_closed(self):
        p, _, rows, _ = fixture()
        for field in ("energy", "water", "stress"):
            bad = copy.deepcopy(rows)
            bad[4]["plants"][0][field] += 1
            with self.assertRaises(RuntimeError):
                audit.failures.histories(bad, {}, {10: p}, rows[-1]["tick"])

    def test_sticky_flags_are_not_extra_maintenance_events(self):
        h = dark_history(energy=208)
        episodes = audit.stress_episodes(h)
        self.assertEqual(len(episodes), 1)
        self.assertEqual(episodes[0]["maintenance_shortages"]["energy"], 8)
        self.assertIsNone(episodes[0]["recovery_tick"])
        self.assertEqual(episodes[0]["peak_stress"], 8)

    def test_recovery_requires_flags_and_stress_to_clear(self):
        p, h, _, _ = fixture()
        h = copy.deepcopy(h[:5])
        for entry, stress, flags in zip(h, (0, 1, 1, 1, 0), (0, 2, 2, 0, 0), strict=True):
            entry["state"].update(stress=stress, flags=flags)
        episode = audit.stress_episodes(h)[0]
        self.assertEqual(episode["first"]["tick"], 30)
        self.assertEqual(episode["recovery_tick"], 75)

    def test_zero_income_is_not_equated_with_global_darkness(self):
        _, h, _, _ = fixture(earn=False)
        runs = audit.zero_income_runs(h)
        self.assertEqual(len(runs), 1)
        self.assertGreater(runs[0]["possible_global_light_steps"], 0)
        self.assertGreater(runs[0]["active_leaf_steps"], 0)
        self.assertEqual(runs[0]["last_tick"], 4305)

    def test_filter_keeps_capacity_receipt_associated_with_correct_plant(self):
        rows = [{"tick": 15, "plants": [{"id": 10}, {"id": 11}],
                 "dark_guard": {"events": [{"id": 11}, {"id": 10}]},
                 "night_capacity": {"events": [{"expense": 0, "denied": True}, {"expense": 1, "denied": False}]}}]
        original, capacity = copy.deepcopy(rows), {}
        filtered = list(audit.focal_rows(rows, {10: {}}, capacity))
        self.assertEqual(rows, original)
        self.assertEqual(filtered[0]["plants"], [{"id": 10}])
        self.assertEqual(list(capacity), [(15, 10)])
        self.assertFalse(capacity[(15, 10)][0]["denied"])


if __name__ == "__main__":
    unittest.main()
