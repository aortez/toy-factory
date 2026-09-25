#!/usr/bin/env python3
"""Ordered seed reconstruction and offspring censoring without native execution."""
import copy
import unittest

import garden_renewal_recruitment as audit


def seed(parent=1,birth=0,column=3):
    return {"parent":parent,"birth_tick":birth,"column":column,"generation":1}


def child(identity=10,parent=1,column=3,birth=120,death=None):
    return {"id":identity,"parent":parent,"column":column,"generation":1,
            "birth_tick":birth,"death_tick":death,"species":"flower"}


class RecruitmentTests(unittest.TestCase):
    def test_simultaneous_expiry_germination_creation(self):
        active = [seed(birth=0),seed(2,birth=3000,column=9)]
        new = seed(3,birth=3840,column=15)
        carry,removed,added = audit.transition(active,[new],[child(parent=2,column=9)],3840)
        self.assertEqual(carry,[])
        self.assertEqual([(r[1],r[2]) for r in removed],[("expired",None),("germinated",10)])
        self.assertEqual(added,[new])

    def test_duplicate_seed_uses_earliest_mature_entry(self):
        first,second = seed(birth=0),seed(birth=240)
        carry,removed,added = audit.transition([first,second],[second],[child()],600)
        self.assertEqual(carry,[second])
        self.assertEqual(removed,[(first,"germinated",10)])
        self.assertEqual(added,[])

    def test_dormant_and_expiry_boundaries(self):
        with self.assertRaises(RuntimeError): audit.transition([seed()],[],[child()],105)
        self.assertEqual(audit.transition([seed()],[],[child()],120)[1][0][1],"germinated")
        with self.assertRaises(RuntimeError): audit.transition([seed()],[],[child()],3840)
        self.assertEqual(audit.transition([seed()],[],[],3840)[1][0][1],"expired")
        with self.assertRaises(RuntimeError): audit.transition([seed()],[],[],3855)

    def test_other_parent_same_column_cannot_skip_earlier_mature_seed(self):
        a,b = seed(1),seed(2,birth=240)
        with self.assertRaises(RuntimeError): audit.transition([a,b],[a],[child(parent=2)],600)

    def test_corrupt_order_missing_seed_or_child_fails(self):
        a,b = seed(),seed(2,column=9)
        for observed,born in (([b,a],[]),([a],[]),([],[]),([a,b],[child(parent=3)])):
            with self.subTest(observed=observed),self.assertRaises(RuntimeError):
                audit.transition([a,b],observed,born,600)

    def test_snapshot_dormancy_capacity_spacing_and_dead_occupants(self):
        row = {"tick":120,"plants":[{"id":22,"column":3,"dead":True}],"nodes":50}
        s = {**seed(),"blockers":32}
        value = audit.snapshot(row,s,seed())
        self.assertEqual(value["spacing_occupants"],[{"id":22,"dead":True}])
        for mask in (0,1,8,16,64):
            with self.assertRaises(RuntimeError): audit.snapshot(row,{**s,"blockers":mask},seed())
        row.update(tick=105)
        audit.snapshot(row,{**s,"blockers":33},seed())

    def test_full_day_boundary_and_recent_censoring(self):
        rows = [child(1,birth=120,death=3960),child(2,birth=120,death=3975),
                child(3,birth=120),child(4,birth=3990)]
        records = {p["id"]:p for p in rows}
        group = audit.offspring_group(rows,records,4005)
        self.assertEqual((group["eligible_offspring"],group["cycle_survivors"],group["recent_alive"]),(3,2,1))
        self.assertEqual((group["early_natural_deaths"],group["natural_deaths"]),(1,2))

    def test_death_partition_does_not_match_newborn_ids(self):
        a = child(1,parent=0,birth=0,death=1000)
        b = child(2,birth=1000,death=72000)
        c = child(3,birth=audit.CUTOFF,death=80000)
        c["environmental_death"] = True
        result = audit.death_partition({p["id"]:p for p in (a,b,c)})
        self.assertEqual(result["founders"]["natural_deaths"],1)
        self.assertEqual(result["pre_intervention_offspring"]["natural_deaths"],1)
        self.assertEqual(result["post_intervention_offspring"]["patch_deaths"],1)

    def test_empty_ledger_and_truncation(self):
        row = {"type":"world","tick":0,"plants":[],"seeds":[],"nodes":0,
               "births":0,"seeds_created":0,"seeds_expired":0}
        self.assertEqual(audit.seed_ledger([row],{}, {},0)["seeds"],[])
        with self.assertRaises(RuntimeError): audit.seed_ledger([row],{}, {},15)
        with self.assertRaises(RuntimeError): audit.seed_ledger([row,row],{}, {},0)
        bad = {**row,"seeds_created":1}
        with self.assertRaises(RuntimeError): audit.seed_ledger([bad],{}, {},0)

    def test_patch_preserves_seeds_and_is_not_a_second_step(self):
        row = {"type":"world","tick":0,"plants":[],"seeds":[],"nodes":0,
               "births":0,"seeds_created":0,"seeds_expired":0}
        boundary = {"before":row,"after":copy.deepcopy(row)}
        audit.seed_ledger([row],{0:boundary},{},0)
        boundary["after"]["seeds"] = [seed()]
        with self.assertRaises(RuntimeError): audit.seed_ledger([row],{0:boundary},{},0)


if __name__ == "__main__":
    unittest.main()
