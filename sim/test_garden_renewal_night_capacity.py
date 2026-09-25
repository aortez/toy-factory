#!/usr/bin/env python3
"""Capacity boundaries, action accounting and censoring without native runs."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_renewal_night_capacity as audit


def plant(nodes=64,extend=60):
    return {"id":1,"nodes":nodes,"dead":False,"agent":{"extend":extend}}


class NightCapacityTests(unittest.TestCase):
    def test_closed_form_all_legal_bodies_and_tier_edges(self):
        for n in range(1,513):
            value = audit.capacity(n)
            self.assertEqual(value["viable_at_cap"],n <= 64)
            self.assertEqual(value["minimum_energy"],((n+7)//8)*30)
        self.assertEqual(audit.capacity(64)["minimum_energy"],240)
        self.assertEqual(audit.capacity(65)["minimum_energy"],270)
        self.assertEqual(audit.capacity(65)["canonical_death_tick"],2940)
        self.assertEqual(audit.classify(63,64),"safe")
        self.assertEqual(audit.classify(64,65),"newly-unsafe")
        self.assertEqual(audit.classify(65,66),"already-unsafe")
        self.assertEqual(audit.capacity(8)["upkeep"],1)
        self.assertEqual(audit.capacity(9)["upkeep"],2)

    def test_invalid_nodes_and_non_positive_growth_fail(self):
        for value in (True,0,-1,513,64.0,"64"):
            with self.assertRaises(RuntimeError): audit.capacity(value)
        for pair in ((64,64),(64,66),(65,64),(0,1),(512,513)):
            with self.assertRaises(RuntimeError): audit.classify(*pair)

    def test_cached_capacity_cannot_be_mutated_by_caller(self):
        value = audit.capacity(65)
        value["viable_at_cap"] = True
        self.assertFalse(audit.capacity(65)["viable_at_cap"])

    def test_canonical_alignment_and_minimum_reserve(self):
        bounds = audit.reference.horizon(audit.ANCHOR)
        self.assertEqual((bounds["dark_steps"],bounds["first_possible_income_tick"]),(149,3045))
        self.assertEqual(bounds["maintenance_ticks"],list(range(840,3001,60)))
        self.assertIsNone(audit.reference.project(795,240,64,0)["death_tick"])
        self.assertIsNotNone(audit.reference.project(795,239,64,0)["death_tick"])
        self.assertIsNotNone(audit.reference.project(795,256,65,0)["death_tick"])

    def test_structural_flag_is_not_remaining_night_or_current_reserve(self):
        # Late night can be safe now while the same body cannot fund a full night.
        value = audit.event_record(2940,1,64,65,paid=True,energy=256,stress=0)
        self.assertEqual(value["classification"],"newly-unsafe")
        self.assertIsNone(value["actual_remaining_dark"]["death_tick"])
        self.assertTrue(audit.capacity(64)["viable_at_cap"])
        self.assertIsNotNone(audit.reference.project(795,0,64,0)["death_tick"])
        self.assertEqual(audit.event_record(60,1,64,65,paid=True,energy=256,stress=0)["classification"],
                         value["classification"])

    def test_only_actual_added_node_and_newborn(self):
        self.assertTrue(audit.added_node(plant(),plant(65,61)))
        self.assertFalse(audit.added_node(plant(),plant()))  # FINISH or no committed action.
        self.assertFalse(audit.added_node(plant(),plant(64,61)))  # Blocked EXTEND.
        self.assertTrue(audit.added_node(None,plant(5,1)))
        self.assertFalse(audit.added_node(None,plant(4,0)))
        for after in (plant(65,60),plant(66,61),plant(63,61),{**plant(),"dead":True}):
            with self.assertRaises(RuntimeError): audit.added_node(plant(),after)

    def test_paid_and_denied_denominators_and_retries(self):
        denied = [audit.event_record(t,1,64,65,paid=False,node=8) for t in (600,615,630)]
        denied += [audit.event_record(645,1,64,65,paid=False,node=9)]
        paid = [audit.event_record(660,1,64,65,paid=True,energy=200,stress=0)]
        original = copy.deepcopy((paid,denied))
        self.assertEqual(audit.event_summary(denied)["classification"]["newly-unsafe"],4)
        self.assertEqual(audit.event_summary(paid)["classification"]["newly-unsafe"],1)
        groups = audit.denied_groups(denied)
        self.assertEqual([g["attempts"] for g in groups],[3,1])
        self.assertEqual(groups[0]["last"]["tick"],630)
        self.assertEqual((paid,denied),original)
        with self.assertRaises(RuntimeError): audit.denied_groups(paid)

    def test_first_anchor_and_pre_anchor_censoring(self):
        for terminal,label in ((None,"trace-censored-before-anchor"),("natural","natural-death-before-anchor"),
                               ("patch","patch-censored-before-anchor")):
            history = [{"state":{"tick":0},"terminal":None},{"state":{"tick":780},"terminal":terminal}]
            self.assertEqual(audit.first_full_night(history,{"tick":600})["status"],label)
        history = [{"state":{"tick":0},"terminal":None},{"state":{"tick":795},"terminal":"patch"}]
        self.assertEqual(audit.first_full_night(history,{"tick":600})["status"],"patch-censored-at-anchor")

    def test_first_anchor_includes_equal_and_skips_incomplete_night(self):
        history = [{"state":{"tick":0},"terminal":None},
                   {"state":{"tick":795,"nodes":65},"terminal":None},
                   {"state":{"tick":4635,"nodes":66},"terminal":None}]
        with patch.object(audit.failures,"audit_window",return_value={"status":"trace-censored"}) as window:
            self.assertEqual(audit.first_full_night(history,{"tick":795})["anchor_tick"],795)
            window.assert_called_with(history,1)
            self.assertEqual(audit.first_full_night(history,{"tick":810})["anchor_tick"],4635)
            window.assert_called_with(history,2)
        with self.assertRaises(RuntimeError): audit.first_full_night(history,{"tick":4650})
        with self.assertRaises(RuntimeError): audit.first_full_night([history[0],history[2]],{"tick":780})

    def test_missing_or_reordered_census_fails(self):
        row = {"type":"world","tick":0,"plants":[plant(4,0)]}
        self.assertEqual(audit.extension_ledger([row],{},False,0),([],[]))
        with self.assertRaises(RuntimeError): audit.extension_ledger([row],{},False,15)
        with self.assertRaises(RuntimeError): audit.extension_ledger([row,row],{},False,15)
        with self.assertRaises(RuntimeError): audit.extension_ledger([row],{},True,0)
        with self.assertRaises(RuntimeError): audit.extension_ledger([{**row,"plants":[plant(65,0)]}],{},False,0)

    def test_guard_receipt_matches_paid_or_denied_growth(self):
        old = {**plant(4,0),"energy":128,"stress":0}
        new = {**plant(5,1),"energy":121,"stress":0}
        receipt = {"kind":"growth","id":1,"node":1,"invalid":False,"energy":128,"water":32,
                   "energy_cost":7,"water_cost":4,"nodes_before":4,"nodes_after":5,"stress":0,
                   "denied":False,"before":audit.panel.guard.native_budget(15,128,4,0),
                   "after":audit.panel.guard.native_budget(15,121,5,0)}
        rows = [{"type":"world","tick":0,"plants":[old],"dark_guard":{"events":[]}},
                {"type":"world","tick":15,"plants":[new],"dark_guard":{"events":[receipt]}}]
        values = {"extensions":1,"finishes":0,"energy_growth":7,"energy_seeds":0}
        with patch.object(audit.startup.resources,"budget",return_value=values):
            paid,denied = audit.extension_ledger(rows,{},True,15)
            self.assertEqual((len(paid),len(denied)),(1,0))
            broken = copy.deepcopy(rows)
            broken[1]["plants"][0]["nodes"] = 4
            with self.assertRaises(RuntimeError): audit.extension_ledger(broken,{},True,15)
            broken = copy.deepcopy(rows)
            broken[1]["dark_guard"]["events"][0]["energy_cost"] = 6
            with self.assertRaises(RuntimeError): audit.extension_ledger(broken,{},True,15)

    def test_death_coverage_retains_unflagged_and_surviving_plants(self):
        def detail(identity,nodes,outcome):
            crossed = nodes > 64
            return {"lineage":{"id":identity,"parent":0,"species":"flower","seeds_created":2},
                    "outcome":outcome,"cause":"energy" if outcome == "natural" else None,
                    "crossing":{"tick":600} if crossed else None,"last_live":{"nodes":nodes},
                    "first_full_night":{"status":"trace-censored"} if crossed else None}
        result = audit.summary([detail(1,65,"natural"),detail(2,64,"natural"),
                                detail(3,65,"alive-at-end"),detail(4,65,"patch")],[],[])
        self.assertEqual(result["crossed_plants"],3)
        self.assertEqual(result["crossed_outcomes"],{"natural":1,"alive-at-end":1,"patch":1})
        self.assertEqual((result["natural_with_crossing"],result["natural_without_crossing"]),(1,1))

    def test_wrong_manifest_and_missing_artifact_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            audit.experiment.write_json(root/"manifest.json",{"artifacts":{"missing":"bad"}})
            with self.assertRaises(RuntimeError): audit.check_frozen(root,"bad")
            with self.assertRaises(RuntimeError): audit.check_frozen(root,audit.experiment.digest(root/"manifest.json"))


if __name__ == "__main__":
    unittest.main()
