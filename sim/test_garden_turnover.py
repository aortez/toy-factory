#!/usr/bin/env python3
"""Follow-up censoring, ancestry, terminal clearing and trace integrity tests."""
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest

import garden_turnover as audit


class TurnoverTests(unittest.TestCase):
    def test_age_boundary_and_censoring(self):
        day, end = audit.DAY, audit.END
        rows = [{"id":1,"parent":9,"birth_tick":end-2*day,"death_tick":end-day},
                {"id":2,"parent":9,"birth_tick":end-2*day,"death_tick":None},
                {"id":3,"parent":9,"birth_tick":end-day+15,"death_tick":None},
                {"id":4,"parent":9,"birth_tick":end-2*day,"death_tick":end-day-15,
                 "environmental_death":True}]
        r = audit.survival(rows,audit.START,end)["ages"]["1"]
        self.assertEqual(r,{"eligible":3,"survived":1,"survived_ids":[2],"recent":1,
                            "natural_deaths":1,"patch_deaths":1})
        # Death exactly at the threshold is not a survivor; the last young plant
        # stays out of both numerator and denominator even if its outcome is known.
        with self.assertRaises(RuntimeError):
            audit.survival(rows,end,end)

    def test_common_cohort(self):
        rows = [{"id":i,"parent":1,"birth_tick":d*audit.DAY,"death_tick":None}
                for i,d in enumerate((160,161,176,177,191))]
        r = audit.survival(rows,audit.START,audit.END-16*audit.DAY)
        self.assertEqual(r["born"],2)
        self.assertTrue(all(v["eligible"]==2 and v["survived"]==2 for v in r["ages"].values()))

    def test_durable_can_be_posthumous(self):
        d=audit.DAY
        rows=[{"id":1,"parent":0,"birth_tick":0,"death_tick":None,"generation":0},
              {"id":2,"parent":1,"birth_tick":161*d,"death_tick":163*d,"generation":1},
              {"id":3,"parent":2,"birth_tick":163*d+15,"death_tick":None,"generation":2}]
        result=audit.summary_lifetimes(rows)
        self.assertEqual(result["durable_closing"],[{"id":2,"children":[3],
            "qualification_tick":164*d+15,"alive_when_qualified":False,"alive_at_end":False}])
        rows[2]["generation"]=1
        with self.assertRaises(RuntimeError): audit.summary_lifetimes(rows)
        with self.assertRaises(RuntimeError): audit.summary_lifetimes([rows[0],rows[0]])

    @staticmethod
    def trace():
        p={"id":1,"parent":0,"species":"shrub","generation":0,"column":0,"dead":False,
           "energy":0,"water":32,"stress":0,"flags":0,"nodes":4,"roots":2,"tips":2,
           "leaves":1,"active_leaves":1,"energy_income":0,"water_income":0,
           "reproduction_cooldown":0,"vigor":0,"genome":[0]*8,"root_cells":[],
           "leaf":{"conditions":[255],"renewals":0},"agent":{"extend":0,"finish":0,"wait":0}}
        rows=[]
        for tick in range(0,481,15):
            if tick and tick%60==0:
                p["water"]-=1;p["stress"]+=1;p["flags"]=2
            if tick==480:
                p.update(dead=True,energy=0,water=0,flags=3)
            rows.append({"type":"world","tick":tick,"hash":f"{tick:08x}","sun_phase":64+tick//15,
                "leaf_environment":"leaf-maintenance-v1","leaf_policy":"selective",
                "growth_policy":audit.bank.recruitment.policy.RESERVE,"node_capacity":512,"plants":[copy.deepcopy(p)]})
        ref={"lineages":[{"id":1,"parent":0,"species":"shrub","generation":0,"column":0,
            "birth_tick":0,"death_tick":480,"death_flags":3,"seeds_created":0}]}
        return rows,ref

    def test_trace_and_terminal_step(self):
        rows,ref=self.trace()
        with tempfile.TemporaryDirectory(prefix="garden-turnover-test-") as temp:
            path=Path(temp)/"world.gz"
            def run(values=rows, reference=ref):
                with gzip.open(path,"wt") as f:
                    for r in values:f.write(json.dumps(r)+"\n")
                return audit.resource_trace(path,{"world":[]},reference,8,start=0,end=480)
            result=run()
            self.assertEqual(result["checked_live_steps"],31)
            death=result["closing_natural_deaths"][0]
            self.assertEqual(death["last_alive"]["tick"],465)
            self.assertEqual(death["last_day_budget"]["energy_upkeep"],0)
            self.assertEqual(death["last_day_budget"]["water_upkeep"],7)
            self.assertIsNone(death["last_sunset"])
            for field,value in (("energy",5),("stress",7)):
                bad=copy.deepcopy(rows);bad[-1]["plants"][0][field]=value
                with self.assertRaises(RuntimeError):run(bad)
            bad=copy.deepcopy(rows);bad[2]["plants"][0]["water"]=31
            with self.assertRaises(RuntimeError):run(bad)
            for bad in (rows[:-1],rows[:1]+rows[2:],rows[:2]+[rows[1]]+rows[2:]):
                with self.assertRaises(RuntimeError):run(bad)
            bad=copy.deepcopy(rows);bad[1]["seed_capacity"]=16
            with self.assertRaises(RuntimeError):run(bad)
            bad=copy.deepcopy(ref);bad["lineages"][0]["death_tick"]=465
            with self.assertRaises(RuntimeError):run(reference=bad)

    def test_budget_window_open_boundary(self):
        hist=[{"point":{"tick":15},"budget":{"energy_seeds":48}},
              {"point":{"tick":30},"budget":{"energy_upkeep":2}}]
        self.assertEqual(audit.sum_budgets(hist,15),{"energy_upkeep":2})


if __name__ == "__main__":
    unittest.main()
