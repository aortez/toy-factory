#!/usr/bin/env python3
"""Synthetic boundaries for saved seed lifetimes and conservative spacing evidence."""
from collections import Counter
import copy
from unittest import mock
import unittest

import garden_renewal_rescued_seeds as audit


def record(identity=1,column=0,birth=0,parent=0):
    return {"id":identity,"column":column,"birth_tick":birth,"parent":parent,"genome":[0]*8,
            "species":"shrub","generation":0,"seeds_created":int(identity == 1),"late_seeds_created":0}


def fixture(end=180,*,outcome="pending",birth=0,finish=None):
    seed = {"parent":1,"generation":1,"column":3,"birth_tick":birth,"outcome":outcome,
            "end_tick":finish,"child_id":None if outcome != "germinated" else 3}
    last = end if finish is None else finish-15
    mature = max(0,(last-birth)//15-7)
    seed.update(mature_snapshots=mature,mature_blockers=Counter({"32":mature}) if mature else Counter())
    records = {1:record(),2:record(2,4)}
    worlds = []
    for tick in range(0,end+1,15):
        seeds = []
        if tick >= birth and (finish is None or tick < finish):
            seeds = [{k:seed[k] for k in audit.ledger.SIGNATURE}]
            seeds[0]["blockers"] = 32|int(tick-birth < 120)
        worlds.append({"type":"world","tick":tick,"nodes":8,"seeds":seeds,
                       "plants":[{"id":1,"column":0,"dead":False},{"id":2,"column":4,"dead":False}]})
    return worlds,[seed],records


class RescuedSeedTests(unittest.TestCase):
    def test_fixed_scope_and_zero_native_calls(self):
        self.assertEqual([(c.name,c.target_id,c.first_tick) for c in audit.CASES],
                         [("0d983a80.no-patch",7,37605),("58e36558.patch",12,134940)])
        self.assertEqual(audit.parent.ARMS,("control","capacity"))
        self.assertEqual((audit.STOP,audit.LATE),(245760,184320))

    def test_reflected_support_not_uniform_probability(self):
        self.assertEqual(audit.dispersal_support(0,0),list(range(3,10)))
        self.assertEqual(audit.dispersal_support(27,0),list(range(18,25)))
        self.assertEqual(audit.dispersal_support(7,0),[0,1,2,3,4,10,11,12,13,14,15,16])
        for column in range(28):
            for trait in range(-2,3):
                support = audit.dispersal_support(column,trait)
                self.assertTrue(all(0 <= c < 28 for c in support))
                self.assertEqual(sorted(27-c for c in support),audit.dispersal_support(27-column,trait))
        for args in ((-1,0),(28,0),(0,3),(0,-3),(True,0)):
            with self.assertRaises(RuntimeError): audit.dispersal_support(*args)

    def test_dead_founder_still_proves_spacing(self):
        worlds,seeds,records = fixture()
        row = worlds[-1]
        row["plants"][1]["dead"] = True
        point = audit.spacing_witness(row,row["seeds"][0],seeds[0],records)
        self.assertEqual(point["stable_spacing_occupants"],
                         [{"id":2,"column":4,"dead":True,"founder":True,"self":False}])
        stats = audit.empty_stats()
        audit.observe(stats,point)
        self.assertEqual((stats["stable_spacing"],stats["dead_spacing"],stats["founder_spacing"]),(1,1,1))

    def test_same_step_newborn_does_not_prove_prior_spacing(self):
        worlds,seeds,records = fixture()
        row = worlds[-1]
        records[2].update(birth_tick=row["tick"],parent=9)
        point = audit.spacing_witness(row,row["seeds"][0],seeds[0],records)
        self.assertEqual(point["stable_spacing_occupants"],[])
        stats = audit.empty_stats()
        audit.observe(stats,point)
        self.assertEqual((stats["stable_spacing"],stats["newborn_spacing_only"]),(0,1))

    def test_full_post_step_capacity_with_newborn_is_not_stable_full(self):
        worlds,seeds,records = fixture()
        row = worlds[-1]
        row["seeds"][0].update(column=9,blockers=40)
        seeds[0]["column"] = 9
        row["plants"] = [{"id":i+1,"column":i*3,"dead":False} for i in range(8)]
        records = {p["id"]:record(p["id"],p["column"]) for p in row["plants"]}
        records[4]["birth_tick"] = row["tick"]
        point = audit.spacing_witness(row,row["seeds"][0],seeds[0],records)
        self.assertEqual((point["stable_plant_slots"],point["stable_spacing_occupants"]),(7,[]))
        records[4]["birth_tick"] = 0
        point = audit.spacing_witness(row,row["seeds"][0],seeds[0],records)
        self.assertEqual(point["stable_plant_slots"],8)
        self.assertEqual([p["id"] for p in point["stable_spacing_occupants"]],[4])

    def test_invalid_geometry_dormancy_and_lineage_fail(self):
        for defect in ("mask","birth","column","dormant"):
            worlds,seeds,records = fixture()
            row = worlds[-1]
            if defect == "mask": row["seeds"][0]["blockers"] = 0
            elif defect == "birth": records[2]["birth_tick"] = 195
            elif defect == "column": records[2]["column"] = 20
            else: row = worlds[1]
            with self.subTest(defect=defect),self.assertRaises(RuntimeError):
                audit.spacing_witness(row,row["seeds"][0],seeds[0],records)

    def test_whole_refusal_late_windows_and_no_input_mutation(self):
        worlds,seeds,records = fixture()
        before = copy.deepcopy((worlds,seeds,records))
        with mock.patch.object(audit,"LATE",150):
            selected,support = audit.focused_observations(worlds,seeds,records,1,135,180)
        self.assertEqual((worlds,seeds,records),before)
        s = selected[0]
        self.assertEqual([s["observations"][w]["samples"] for w in audit.WINDOWS],[5,4,2])
        self.assertEqual(s["pending_age"],12)
        self.assertEqual(s["witnesses"]["2"]["samples"],5)
        self.assertEqual(s["first_mature_witness"]["tick"],120)
        self.assertEqual(s["last_mature_witness"]["tick"],180)
        self.assertEqual(support,list(range(3,10)))

    def test_expiry_removes_before_check_and_pending_is_not_failed(self):
        for end,outcome,finish,count in ((3825,"pending",None,248),(3840,"expired",3840,248),
                                          (120,"germinated",120,0)):
            worlds,seeds,records = fixture(end,outcome=outcome,finish=finish)
            selected,_ = audit.focused_observations(worlds,seeds,records,1,0,end)
            self.assertEqual(selected[0]["observations"]["whole"]["samples"],count)
            summary = audit.focused_summary(selected)
            self.assertEqual(summary[outcome],1)
            self.assertEqual(summary["germinated"],int(outcome == "germinated"))

    def test_wrong_outcome_timing_duplicate_or_missing_observations_fail(self):
        for defect in ("expiry","old_pending","early_germination","truncated","counter","mask_count","duplicate","support"):
            worlds,seeds,records = fixture()
            if defect == "expiry": seeds[0].update(outcome="expired",end_tick=180)
            elif defect == "old_pending": seeds[0]["birth_tick"] = -3840
            elif defect == "early_germination": seeds[0].update(outcome="germinated",end_tick=105,child_id=3)
            elif defect == "truncated": worlds.pop()
            elif defect == "counter": seeds[0]["mature_snapshots"] += 1
            elif defect == "mask_count": seeds[0]["mature_blockers"] = Counter({"34":5})
            elif defect == "duplicate": seeds.append(copy.deepcopy(seeds[0]))
            else: seeds[0]["column"] = 27
            with self.subTest(defect=defect),self.assertRaises(RuntimeError):
                audit.focused_observations(worlds,seeds,records,1,0,180)

    def test_empty_control_has_no_observed_success_or_failure_rate(self):
        worlds,seeds,records = fixture()
        for row in worlds: row["seeds"] = []
        selected,_ = audit.focused_observations(worlds,[],records,1,135,180)
        summary = audit.focused_summary(selected)
        self.assertEqual(summary["purchases"],0)
        self.assertIsNone(summary["observations"]["whole"]["all_mature_stably_spacing_blocked"])
        self.assertEqual(summary["observations"]["whole"]["no_observed_blockers"],0)

    def test_blocker_overlap_not_independent_attempts(self):
        worlds,seeds,records = fixture()
        row = worlds[-1]
        row["seeds"][0]["blockers"] = 38
        point = audit.spacing_witness(row,row["seeds"][0],seeds[0],records)
        stats = audit.empty_stats()
        audit.observe(stats,point)
        merged = audit.merge_stats([stats,stats])
        self.assertEqual(merged["samples"],2)
        self.assertEqual(merged["observed_blockers"],
                         {"dormant":0,"moisture":2,"light":2,"plant_capacity":0,"node_capacity":0,"spacing":2})
        self.assertEqual(merged["stable_structural_blocker"],2)

    def test_spacing_boundary_and_self_witness(self):
        worlds,seeds,records = fixture()
        row = worlds[-1]
        row["plants"] = row["plants"][:1]
        row["seeds"][0]["blockers"] = 0
        point = audit.spacing_witness(row,row["seeds"][0],seeds[0],records)
        self.assertEqual(point["stable_spacing_occupants"],[])
        row["seeds"][0].update(column=2,blockers=32)
        point = audit.spacing_witness(row,row["seeds"][0],{**seeds[0],"column":2},records)
        self.assertTrue(point["stable_spacing_occupants"][0]["self"])

    def test_complete_ledger_integrates_with_focused_audit(self):
        worlds,_,records = fixture(3900,birth=60,outcome="expired",finish=3900)
        for row in worlds:
            age = (row["tick"]-60)//15
            row.update(births=0,seeds_created=int(age >= 0),seeds_expired=int(age >= 256))
            for p in row["plants"]:
                p.update(parent=0,reproduction_cooldown=max(0,16-age) if p["id"] == 1 and age >= 0 else 0,
                         species="shrub")
        full = audit.ledger.seed_ledger(worlds,{},records,3900)
        selected,_ = audit.focused_observations(worlds,full["seeds"],records,1,135,3900)
        self.assertEqual(audit.outcome_summary(full["seeds"])["expired"],1)
        self.assertEqual(selected[0]["observations"]["whole"]["stable_spacing"],248)

    def test_ordered_duplicates_retain_native_fifo(self):
        first = {"parent":1,"birth_tick":0,"generation":1,"column":3}
        second = {**first,"birth_tick":240}
        child = {"id":3,"parent":1,"generation":1,"column":3}
        carry,removed,added = audit.ledger.transition([first,second],[second],[child],600)
        self.assertEqual((carry,removed,added),([second],[(first,"germinated",3)],[]))


if __name__ == "__main__":
    unittest.main()
