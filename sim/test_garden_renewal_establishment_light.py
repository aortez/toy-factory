#!/usr/bin/env python3
"""Fail-closed tests for saved-trace light and spending inference; no simulation."""
import copy
import hashlib
import unittest

import garden_renewal_establishment_light as audit


def light_fixture(condition=255, light=63, tick=15, carry=0):
    worn = max(0, condition-int(tick % 60 == 0))
    numerator = worn*(light//64)
    income, remainder = divmod(numerator+carry, 255)
    old = {"id": 14, "dead": False, "energy": 64, "water": 24, "nodes": 4, "roots": 2, "leaves": 1,
           "leaf": {"conditions": [condition], "remainder": carry, "observations": 0,
                    "proposals": 0, "renewals": 0}}
    plant = copy.deepcopy(old)
    upkeep = int(tick % 60 == 0)
    plant.update(energy_income=income, water_income=0, energy=64+income-upkeep, water=24-upkeep)
    plant["leaf"].update(conditions=[worn], remainder=remainder, observations=1)
    bid = {"tick": tick, "id": 14, "mature_leaves": 1, "condition": worn, "light": light,
           "energy": plant["energy"], "water": plant["water"], "site_x": 0, "site_y": -6, "action": 0}
    values = {"energy_upkeep": upkeep, "water_upkeep": upkeep, "energy_renewal": 0}
    return old, plant, tick, bid, values


def growth_fixture(action=1, tissue=0):
    before = {"decisions": 0, "extend": 0, "finish": 0, "wait": 0, "shoot_extend": 0, "root_extend": 0}
    bid = {"tick": 15, "id": 14, "priority": 12, "tip_index": 8, "action": action, "tissue": tissue,
           "x": 90, "y": 120, "energy": 64, "water": 24,
           "candidates": [{"light": 24, "flags": 3} for _ in range(5 if tissue == 0 else 3)]}
    agent = {**before, "decisions": 1, ("wait", "extend", "finish")[action]: 1,
             **{"last_"+k: bid[k] for k in ("priority", "action", "tissue", "x", "y")}}
    if action == 1:
        agent["root_extend" if tissue else "shoot_extend"] = 1
    values = {"extensions": int(action == 1), "finishes": int(action == 2), "waits": int(action == 0),
              "energy_growth": 7*bool(action), "water_growth": 5*bool(action)}
    return {"agent": before}, {"id": 14, "agent": agent}, 15, [bid], values


class LightTests(unittest.TestCase):
    def test_light_is_quantized_before_condition_scaling(self):
        for light in (24, 63, 64, 127, 128, 191, 192, 255):
            result = audit.photometry(*light_fixture(light=light))
            self.assertEqual(result["numerator"], 255*(light//64))
            self.assertEqual(result["all_bands_zero_proven"], light < 64)

    def test_zero_integer_income_is_not_zero_light_contribution(self):
        args = light_fixture(condition=1, light=64)
        self.assertEqual(args[1]["energy_income"], 0)
        result = audit.photometry(*args)
        self.assertEqual(result["numerator"], 1)
        self.assertFalse(result["all_bands_zero_proven"])
        args = light_fixture(condition=1, light=64, carry=254)
        self.assertEqual(args[1]["energy_income"], 1)
        self.assertEqual(audit.photometry(*args)["numerator"], 1)

    def test_zero_condition_cannot_prove_darkness(self):
        result = audit.photometry(*light_fixture(condition=0, light=255))
        self.assertEqual(result["numerator"], 0)
        self.assertFalse(result["all_bands_zero_proven"])

    def test_wear_precedes_photosynthesis_and_observation(self):
        args = light_fixture(condition=255, light=192, tick=60)
        self.assertEqual(audit.photometry(*args)["numerator"], 254*3)
        args[3]["condition"] = 255
        with self.assertRaises(RuntimeError): audit.photometry(*args)

    def test_gross_income_not_storage_delta(self):
        args = light_fixture(light=255)
        args[0]["energy"] = args[1]["energy"] = args[3]["energy"] = 256
        self.assertEqual(audit.photometry(*args)["numerator"], 765)

    def test_sampled_leaf_cannot_contradict_whole_plant_numerator(self):
        args = light_fixture(light=24)
        args[3]["light"] = 64
        with self.assertRaises(RuntimeError): audit.photometry(*args)

    def test_one_dark_sample_is_not_a_whole_canopy_measurement(self):
        args = light_fixture(light=24)
        for p in args[:2]:
            p["leaves"] = 2
            p["leaf"]["conditions"] = [255, 255]
        args[3]["mature_leaves"] = 2
        args[1]["energy_income"] = 1
        args[3]["energy"] = 65
        result = audit.photometry(*args)
        self.assertEqual(result["numerator"], 255)
        self.assertFalse(result["all_bands_zero_proven"])
        self.assertEqual(result["sample"]["band"], 0)

    def test_missing_wrong_or_duplicate_observation_counts_rejected(self):
        for defect in ("missing", "identity", "time", "count", "carry"):
            args = list(light_fixture())
            if defect == "missing": args[3] = None
            if defect == "identity": args[3]["id"] = 15
            if defect == "time": args[3]["tick"] = 30
            if defect == "count": args[3]["mature_leaves"] = 2
            if defect == "carry": args[1]["leaf"]["remainder"] = 255
            with self.assertRaises(RuntimeError): audit.photometry(*args)

    def test_newborn_and_dead_steps_are_not_light_measurements(self):
        args = list(light_fixture())
        args[0], args[3] = None, None
        self.assertIsNone(audit.photometry(*args))
        args[1]["energy_income"] = 1
        with self.assertRaises(RuntimeError): audit.photometry(*args)
        args = light_fixture()
        args[1]["dead"] = True
        with self.assertRaises(RuntimeError): audit.photometry(*args)

    def test_selective_repair_gate_distinguishes_proposal_and_acceptance(self):
        args = light_fixture(condition=128, light=128)
        old, plant, _, bid, values = args
        old["energy"], old["water"] = 200, 200
        bid["energy"], bid["water"], bid["action"] = 201, 200, 1
        plant["leaf"]["proposals"] = 1
        result = audit.photometry(*args)
        self.assertEqual((result["sample"]["proposed"], result["sample"]["accepted"]), (1, 0))
        self.assertEqual(result["sample"]["limits"], {"energy": 49, "water": 45})
        plant["leaf"]["renewals"], values["energy_renewal"] = 1, 9
        self.assertEqual(audit.photometry(*args)["sample"]["accepted"], 1)
        bid["action"] = 0
        with self.assertRaises(RuntimeError): audit.photometry(*args)


class GrowthTests(unittest.TestCase):
    def test_paid_growth_uses_actual_tissue_and_available_candidates_only(self):
        for tissue in (0, 1):
            args = growth_fixture(tissue=tissue)
            args[3][0]["candidates"][0] = {"light": 255, "flags": 9}
            result = audit.growth(*args)
            self.assertEqual(result["tissue"], "root" if tissue else "shoot")
            self.assertEqual(result["maximum_available_light"], 24)
            self.assertEqual(result["energy"], 7)
            self.assertEqual(result["chosen_candidate"], "not recorded")

    def test_wait_and_refused_bid_are_not_spending(self):
        self.assertIsNone(audit.growth(*growth_fixture(action=0)))
        args = growth_fixture()
        args[1]["agent"] = args[0]["agent"].copy()
        args[4].update(extensions=0, energy_growth=0, water_growth=0)
        self.assertIsNone(audit.growth(*args))
        args[4]["energy_growth"] = 7
        with self.assertRaises(RuntimeError): audit.growth(*args)

    def test_first_bid_wins_tie_and_wrong_winner_rejected(self):
        args = growth_fixture()
        other = copy.deepcopy(args[3][0])
        other.update(tip_index=9, x=99)
        args[3].append(other)
        self.assertIsNotNone(audit.growth(*args))
        args[3].reverse()
        with self.assertRaises(RuntimeError): audit.growth(*args)


class BoundaryTests(unittest.TestCase):
    def test_cohort_is_complete_not_success_selected(self):
        records = [{"id": i, "birth_tick": audit.AFTER+15, "parent": 2} for i in audit.CHILDREN]
        self.assertEqual(tuple(audit.scope(records)), audit.CHILDREN)
        for changed in (records[1:], records+[records[0]],
                        records+[{"id": 32, "birth_tick": audit.STOP, "parent": 2}]):
            with self.assertRaises(RuntimeError): audit.scope(changed)

    def test_only_exact_build_registration_is_allowed(self):
        old = b"original CMake\n"+audit.REGISTRATION_ANCHOR.encode()+b"\noriginal suffix\n"
        sha = hashlib.sha256(old).hexdigest()
        new = old.replace(audit.REGISTRATION_ANCHOR.encode(),
                          (audit.REGISTRATION+audit.REGISTRATION_ANCHOR).encode())
        audit.check_build_registration(old, new, sha)
        for changed in (old, new+b"\n", b"# changed\n"+new):
            with self.assertRaises(RuntimeError): audit.check_build_registration(old, changed, sha)
        with self.assertRaises(RuntimeError): audit.check_build_registration(old, new, "0"*64)

    def test_matched_leaf_sites_required_and_terminal_not_compared(self):
        def point(tick, x=0, terminal=None):
            return {"state": {"tick": tick, "phase": 64}, "terminal": terminal,
                    "light": {"sample": {"site_x": x, "site_y": -6, "light": 128, "band": 2, "condition": 100}}}
        a, b = [point(15), point(30)], [point(15), point(30, terminal="natural")]
        result = audit.paired_samples(a, b)
        self.assertEqual(result["counts"]["matched_samples"], 1)
        self.assertEqual(result["counts"]["terminal_excluded"], 1)
        b[0]["light"]["sample"]["site_x"] = 1
        with self.assertRaises(RuntimeError): audit.paired_samples(a, b)
        with self.assertRaises(RuntimeError): audit.paired_samples(a, b[:1])

    def test_terminal_debit_is_not_invented(self):
        live = {"state": {"tick": 15, "id": 14, "phase": 65, "dead": False, "energy": 64, "water": 24},
                "budget": {"energy_income": 0}, "terminal": None, "light": None, "maintenance": None}
        dead = {**live, "state": {**live["state"], "tick": 60, "dead": True, "energy": 0, "water": 0},
                "budget": None, "terminal": "natural"}
        origin = {"energy": 64, "water": 24}
        self.assertEqual(audit.summarize([live, dead], origin)["terminal_step_unaccounted"], 60)
        dead["budget"] = {"energy_upkeep": 64, "water_upkeep": 24}
        with self.assertRaises(RuntimeError): audit.summarize([live, dead], origin)


if __name__ == "__main__":
    unittest.main()
