#!/usr/bin/env python3
"""Bounded synthetic witnesses for append-only access and reproduction gates."""
import copy
from pathlib import Path
import unittest
from unittest import mock

import garden_renewal_reproduction_access as audit


def fixture(*, ids=(12,), buyers=(), denied=(), prior_bank=8, expired=0, germinated=0,
            tick=60, energy=256, water=512, cooldown=0, old_flowers=7, flowers=7, spent=0):
    old_plants, plants, events = [], [], []
    for identity in ids:
        old = {"id": identity, "dead": False, "energy": energy, "water": water, "energy_income": 0,
               "water_income": 0, "nodes": 61, "roots": 18, "species": "shrub", "vigor": 0,
               "genome": [0]*8, "stress": 0, "generation": 1, "flowers": old_flowers,
               "spent_flowers": spent, "reproduction_cooldown": cooldown,
               "agent": {"extend": 0, "finish": 0, "wait": 0}}
        plant = copy.deepcopy(old)
        due = tick % 60 == 0
        plant.update(energy=energy-8*due, water=water-6*due, flowers=flowers,
                     reproduction_cooldown=max(0,cooldown-1),
                     spent_flowers=0 if (64+tick//15)%256 == 0 else spent)
        if identity in buyers or identity in denied:
            events.append({"id": identity, "kind": "seeds", "energy": plant["energy"],
                           "water": plant["water"], "energy_cost": 48, "water_cost": 24,
                           "nodes_before": 61, "nodes_after": 61, "stress": 0,
                           "denied": identity in denied, "invalid": False})
        if identity in buyers:
            plant["energy"] -= 48
            plant["water"] -= 24
            plant["spent_flowers"] += 1
            plant["reproduction_cooldown"] = 16
        old_plants.append(old)
        plants.append(plant)
    kept = prior_bank-expired-germinated
    previous = {"tick": tick-15, "seeds": [{"parent": 99} for _ in range(prior_bank)],
                "seeds_created": 0, "seeds_expired": 0, "births": 0, "plants": old_plants}
    phase = (64+tick//15)%256
    row = {"tick": tick, "sun_phase": phase, "sun_strength": audit.sun_strength(phase),
           "seeds": [{"parent": 99} for _ in range(kept)]+[{"parent": i} for i in ids if i in buyers],
           "seeds_created": len(buyers), "seeds_expired": expired, "births": germinated, "plants": plants,
           "dark_guard": {"events": events}}
    return previous, row


def focal(previous, row, *, earlier=()):
    bank = audit.bank_step(previous, row)
    index = next(i for i,p in enumerate(row["plants"]) if p["id"] == 12)
    old = next(p for p in previous["plants"] if p["id"] == 12)
    return audit.plant_turn(old, row["plants"][index], row, bank, index, earlier)


class AccessTests(unittest.TestCase):
    def test_scope_windows_and_no_cross_arm_id_matching(self):
        self.assertEqual(audit.ARMS, ("control","defer","reserve"))
        self.assertEqual((audit.NOON,audit.LATE,audit.STOP), (69120,184320,245760))
        self.assertEqual(audit.windows(0), [])
        self.assertEqual(audit.windows(69105), ["whole"])
        self.assertEqual(audit.windows(69120), ["whole","after_noon"])
        self.assertEqual(audit.windows(184320), ["whole","after_noon"])
        self.assertEqual(audit.windows(184335), ["whole","after_noon","late"])

    def test_capped_retention_threshold(self):
        old, row = fixture()
        p = row["plants"][0]
        self.assertEqual(audit.thresholds(p), {"energy":248,"water":264,"energy_upkeep":8,"water_upkeep":6})
        for trait in (-2,0,2):
            small = {**p, "nodes":8, "roots":4, "genome":[0]*6+[trait,0]}
            self.assertEqual(audit.thresholds(small)["energy"], 48+96+trait*16)
        for changes in ({"nodes":0},{"roots":62},{"genome":[0]*6+[3,0]}):
            with self.assertRaises(RuntimeError): audit.thresholds({**p,**changes})

    def test_exact_energy_water_boundaries(self):
        old, row = fixture(prior_bank=7,buyers=(12,),water=270)
        turn = focal(old,row)
        self.assertEqual((turn["energy_before"],turn["water_before"],turn["category"]),(248,264,"purchase"))
        for change, failure in (({"energy":255},"energy"),({"water":269},"water")):
            old,row = fixture(**change)
            turn = focal(old,row)
            self.assertIn(failure,turn["failures"])
            self.assertFalse(turn["eligible_except_bank_guard"])

    def test_full_end_bank_does_not_prove_full_at_loop_entry(self):
        old,row = fixture(ids=(1,12),buyers=(1,),prior_bank=8,expired=1)
        turn = focal(old,row,earlier=(1,))
        self.assertEqual((turn["bank_entry"],turn["bank_at_turn"],turn["bank_final"]),(7,8,8))
        self.assertEqual(turn["category"],"earlier-parent-filled")
        stats=audit.empty_access(); audit.observe(stats,turn)
        self.assertEqual(stats["last_filler"],{"1":1})

    def test_later_purchase_cannot_block_earlier_turn(self):
        old,row = fixture(ids=(12,99),buyers=(99,),prior_bank=7,energy=255)
        # The later buyer needs enough energy; the target remains below threshold.
        old["plants"][1]["energy"] += 1
        row["plants"][1]["energy"] += 1
        row["dark_guard"]["events"][0]["energy"] += 1
        turn=focal(old,row)
        self.assertEqual((turn["bank_entry"],turn["bank_at_turn"],turn["bank_final"]),(7,7,8))
        self.assertEqual(turn["category"],"other-ineligible")

    def test_bank_full_before_any_parent_and_no_mutation(self):
        old,row=fixture()
        original=copy.deepcopy((old,row))
        turn=focal(old,row)
        self.assertEqual(turn["category"],"bank-full-at-entry")
        self.assertTrue(turn["eligible_except_bank_guard"])
        self.assertEqual((old,row),original)

    def test_release_and_ordered_multi_purchase(self):
        old,row=fixture(ids=(1,12),buyers=(1,12),expired=1,germinated=1)
        bank=audit.bank_step(old,row)
        self.assertEqual((bank["entry"],bank["final"],bank["buyers"]),(6,8,[1,12]))
        self.assertEqual(focal(old,row,earlier=(1,))["bank_at_turn"],7)

    def test_bad_inventory_or_order_fails(self):
        for defect in ("append-order","counter","expired","duplicate-event","event-order","tick","sun","duplicate-id"):
            old,row=fixture(ids=(1,12),buyers=(1,12),expired=2)
            if defect=="append-order": row["seeds"][-2:]=list(reversed(row["seeds"][-2:]))
            elif defect=="counter": row["seeds_created"]+=1
            elif defect=="expired": row["seeds_expired"]+=1
            elif defect=="duplicate-event": row["dark_guard"]["events"].append(row["dark_guard"]["events"][0])
            elif defect=="event-order": row["dark_guard"]["events"].reverse()
            elif defect=="tick": row["tick"]+=15
            elif defect=="sun": row["sun_strength"]-=1
            else: row["plants"][1]["id"]=1
            with self.subTest(defect=defect),self.assertRaises(RuntimeError): audit.bank_step(old,row)

    def test_cooldown_decrements_before_eligibility_and_resets_after_purchase(self):
        old,row=fixture(prior_bank=7,buyers=(12,),cooldown=1)
        self.assertEqual(focal(old,row)["cooldown"],0)
        old,row=fixture(prior_bank=7,cooldown=2)
        self.assertEqual(focal(old,row)["failures"],["cooldown"])
        row["plants"][0]["reproduction_cooldown"]=0
        with self.assertRaises(RuntimeError): focal(old,row)

    def test_daily_spent_flower_reset(self):
        old,row=fixture(tick=2880,spent=7)
        turn=focal(old,row)
        self.assertEqual((turn["unspent_flowers"],turn["mature_lower_bound"]),(7,7))
        self.assertEqual(turn["failures"],["dark"])
        row["plants"][0]["spent_flowers"]=7
        with self.assertRaises(RuntimeError): focal(old,row)

    def test_new_flower_maturity_is_unknown_not_eligible(self):
        old,row=fixture(prior_bank=7,old_flowers=0,flowers=1)
        turn=focal(old,row)
        self.assertEqual((turn["maturity"],turn["category"]),("unknown","maturity-unknown"))
        self.assertFalse(turn["eligible_except_bank_guard"])
        old,row=fixture(prior_bank=7,buyers=(12,),old_flowers=0,flowers=1)
        self.assertEqual(focal(old,row)["maturity"],"native-receipt")

    def test_spent_flowers_and_off_cadence(self):
        old,row=fixture(spent=7)
        self.assertEqual(focal(old,row)["failures"],["no-unspent-flower"])
        old,row=fixture(tick=75)
        self.assertEqual(focal(old,row)["category"],"off-cadence")

    def test_dark_guard_distinct_from_bank_and_resources(self):
        old,row=fixture(prior_bank=7,denied=(12,))
        self.assertEqual(focal(old,row)["category"],"dark-guard")
        row["dark_guard"]["events"][0]["denied"]=False
        with self.assertRaises(RuntimeError): focal(old,row)

    def test_stress_generation_and_overlapping_failures(self):
        old,row=fixture(energy=255)
        row["plants"][0].update(stress=7,generation=65535)
        turn=focal(old,row)
        self.assertEqual(turn["failures"],["stress","generation-limit","energy"])
        stats=audit.empty_access();audit.observe(stats,turn)
        self.assertEqual(stats["categories"],{"other-ineligible":1})
        self.assertEqual(stats["eligible_except_bank_guard"],0)
        self.assertEqual(sum(stats["failures"].values()),3)

    def test_receipt_and_resource_corruption_fails(self):
        for defect in ("energy","water","cost","body","invalid","spent","no-event"):
            old,row=fixture(prior_bank=7,buyers=(12,))
            event=row["dark_guard"]["events"][0]
            if defect in ("energy","water"): event[defect]-=1
            elif defect=="cost": event["energy_cost"]-=1
            elif defect=="body": event["nodes_before"]-=1
            elif defect=="invalid": event["invalid"]=True
            elif defect=="spent": row["plants"][0]["spent_flowers"]+=1
            else: row["dark_guard"]["events"]=[]
            with self.subTest(defect=defect),self.assertRaises(RuntimeError): focal(old,row)

    def test_eligible_open_bank_requires_paid_or_denied_receipt(self):
        old,row=fixture(prior_bank=7)
        with self.assertRaises(RuntimeError): focal(old,row)

    def test_no_reconstruction_of_terminal_or_revived_plants(self):
        for which in (0,1):
            old,row=fixture()
            (old,row)[which]["plants"][0]["dead"]=True
            with self.assertRaises(RuntimeError): focal(old,row)

    def test_offline_verify_does_not_call_native(self):
        with mock.patch.object(audit,"check_parent",side_effect=RuntimeError("stop")), \
                mock.patch.object(audit.experiment,"command_run") as native:
            with self.assertRaises(RuntimeError): audit.verify(Path("/missing-access-fixture"))
            native.assert_not_called()


if __name__ == "__main__":
    unittest.main()
