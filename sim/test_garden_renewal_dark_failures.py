#!/usr/bin/env python3
"""Offline residual-death attribution, dark boundaries and patch regressions."""
import copy
import unittest
from unittest.mock import patch

import garden_renewal_dark_failures as audit
import test_garden_renewal_dark_panel as panel_fixture
import test_garden_renewal_seed_forecast as seed_fixture


def history(start=4635,end=6870,energy=256,water=512,nodes=55,stress=0,expenses=None):
    p=seed_fixture.plant(energy=energy,water=water,nodes=nodes,stress=stress,leaves=1,tips=0,
                         leaf={"conditions":[255],"renewals":0,"restored":0,"worn":0})
    result=[{"state":audit.point(start,p),"budget":None,"events":[],"terminal":None}]
    for tick in range(start+15,end+1,15):
        old,p=p,copy.deepcopy(p)
        p["reproduction_cooldown"]=max(0,p["reproduction_cooldown"]-1)
        if tick%60==0:
            energy_cost=(p["nodes"]+7)//8
            water_cost=(p["nodes"]-p["roots"]+7)//8
            p["flags"]=(2 if p["energy"]<energy_cost else 0)|(4 if p["water"]<water_cost else 0)
            p["energy"]=max(0,p["energy"]-energy_cost)
            p["water"]=max(0,p["water"]-water_cost)
            p["stress"]=p["stress"]+1 if p["flags"] else max(0,p["stress"]-1)
            if p["stress"]==8:
                p.update(dead=True,energy=0,water=0,flags=p["flags"]|1,tips=0)
        if not p["dead"] and tick in (expenses or {}):
            kind=expenses[tick]
            if kind=="growth":
                p["agent"]["extend"]+=1
                p["nodes"]+=1
                p["energy"]-=8
                p["water"]-=5
            elif kind=="renewal":
                p["leaf"]["renewals"]+=1
                p["energy"]-=9
                p["water"]-=5
            elif kind=="seeds":
                p["reproduction_cooldown"]=16
                p["energy"]-=48
                p["water"]-=24
            else:
                raise AssertionError("bad fixture expense")
        values=None if p["dead"] else audit.startup.resources.budget(old,p,tick)
        result.append({"state":audit.point(tick,p),"budget":values,"events":[],
                       "terminal":"natural" if p["dead"] else None})
        if p["dead"]:
            break
    return result


def record(h):
    return {"id":2,"parent":0,"species":"shrub","generation":0,"birth_tick":h[0]["state"]["tick"],
            "death_tick":h[-1]["state"]["tick"] if h[-1]["terminal"] else None}


class FailureTests(unittest.TestCase):
    def test_complete_survivor_and_fatal_dark_window_are_exact(self):
        for energy,status in ((256,"exact-survival"),(208,"exact-energy-death")):
            h=history(energy=energy)
            w=audit.audit_window(h,0)
            self.assertEqual(w["status"],status)
            self.assertEqual(w["checked_live_steps"],w["exact_prefix_steps"])
            self.assertEqual(w["maximum_errors"],{"energy":0,"stress":0})
        self.assertEqual(w["actual"]["terminal"]["tick"],6840)
        self.assertEqual(w["actual"]["last_live"]["tick"],6825)

    def test_all_living_dusk_anchors_and_dark_newborns_without_duplicates(self):
        self.assertEqual(len(audit.all_windows(history())),1)
        self.assertEqual(audit.all_windows(history(start=4650))[0]["anchor"]["tick"],4650)
        self.assertEqual(audit.all_windows(history(start=4620))[0]["anchor"]["tick"],4635)
        self.assertFalse(audit.all_windows(history(start=0,end=15)))

    def test_daylight_is_not_implicit_dark_approval(self):
        with self.assertRaises(RuntimeError): audit.audit_window(history(start=6870,end=6885),0)
        with self.assertRaises(RuntimeError): audit.minimum_energy(6870,history()[0]["state"])

    def test_optional_spending_and_upkeep_tier_break_prefix(self):
        for kind in ("growth","renewal","seeds"):
            h=history(nodes=56,expenses={4650:kind})
            w=audit.audit_window(h,0)
            self.assertEqual(w["status"],"assumption-broken")
            self.assertEqual(w["exact_prefix_steps"],0)
            self.assertEqual(w["actual"]["assumption_breaks"]["optional_spending"],4650)
            self.assertEqual("energy_upkeep_change" in w["actual"]["assumption_breaks"],kind=="growth")

    def test_water_death_is_not_claimed_as_an_energy_prediction(self):
        w=audit.audit_window(history(water=0),0)
        self.assertEqual(w["status"],"assumption-broken")
        self.assertEqual(w["actual"]["terminal"]["cause"],"water")
        self.assertIsNone(w["prediction"]["death_tick"])
        self.assertEqual(w["actual"]["assumption_breaks"]["water_shortage"],4680)

    def test_trace_and_patch_censoring_do_not_credit_survival(self):
        short=history(end=4680)
        self.assertEqual(audit.audit_window(short,0)["status"],"trace-censored")
        patch_history=copy.deepcopy(short)
        patch_history[-1]["state"].update(dead=True,energy=0,water=0,stress=8,flags=1)
        patch_history[-1]["terminal"]="patch"
        w=audit.audit_window(patch_history,0)
        self.assertEqual(w["status"],"patch-censored")
        self.assertEqual(w["actual"]["terminal"],{"kind":"patch","tick":4680})
        self.assertEqual(w["actual"]["last_live"]["tick"],4665)

    def test_corrupt_prefix_and_missing_step_are_rejected(self):
        for key in ("energy","stress"):
            h=history()
            h[1]["state"][key]+=1
            with self.subTest(key=key),self.assertRaises(RuntimeError): audit.audit_window(h,0)
        h=history()
        h.pop(1)
        with self.assertRaises(RuntimeError): audit.audit_window(h,0)

    def test_live_dark_income_is_rejected_even_with_broken_assumptions(self):
        h=history(expenses={4650:"seeds"})
        h[1]["budget"]["energy_income"]=1
        with self.assertRaises(RuntimeError): audit.audit_window(h,0)

    def test_minimum_store_and_cap_infeasibility(self):
        p=history()[0]["state"]
        result=audit.minimum_energy(4635,p)
        self.assertEqual(result["minimum_energy_within_cap"],210)
        self.assertIsNone(audit.minimum_energy(4635,{**p,"nodes":65})["minimum_energy_within_cap"])
        self.assertEqual(audit.minimum_energy(6855,p)["minimum_energy_within_cap"],0)

    def test_post_horizon_death_is_not_a_failed_dark_forecast(self):
        h=history(end=7400)
        windows=audit.all_windows(h)
        d=audit.death_record(h,windows,record(h),True)
        self.assertEqual(d["death_tick"],7260)
        self.assertEqual(d["relation"],"after-dark-window")
        self.assertEqual(d["latest_window_status"],"exact-survival")
        self.assertEqual(d["post_dark"]["first_possible_income_tick"],6885)
        self.assertIsNone(d["post_dark"]["first_observed_income_tick"])
        self.assertEqual(d["post_dark"]["live_budget"]["energy_income"],0)
        self.assertEqual(d["last_live"]["stress"],7)
        self.assertTrue(d["post_dark"]["terminal_income_unknown"])

    def test_no_anchor_before_bright_death_and_details_optional(self):
        h=history(start=240,end=400,energy=0,stress=7)
        self.assertFalse(audit.all_windows(h))
        d=audit.death_record(h,[],record(h),False)
        self.assertEqual(d["relation"],"no-prior-dark-anchor")
        self.assertNotIn("lookback",d)

    def test_expense_history_preserves_costs_and_not_counterfactual_credit(self):
        h=history(energy=208,expenses={4650:"seeds"})
        d=audit.death_record(h,audit.all_windows(h),record(h),True)
        self.assertEqual(d["lifetime_live_budget"]["energy_seeds"],48)
        stage=d["lookback"]["purchases"][0]["stages"][0]
        self.assertEqual(stage["before"]["energy"]-stage["after"]["energy"],48)
        self.assertEqual(stage["local_effect"],"already-fatal")
        self.assertNotIn("steps",stage["before_budget"])

    def test_denial_retries_count_one_plant_and_patch_is_not_natural(self):
        h=history(energy=208)
        event={"denied":True,"before":{"death_step":1}}
        for entry in h[:3]: entry["events"]=[copy.deepcopy(event)]
        r=record(h)
        denials=audit.denied_records(h,r,6870)
        summary=audit.summarize(audit.all_windows(h),[],denials)
        self.assertEqual((summary["denials"],summary["already_fatal_plants"]),(3,1))
        self.assertEqual(summary["already_fatal_outcomes"],{"natural-death-before-boundary":3})
        r["environmental_death"]=True
        self.assertTrue(all(d["observed_outcome"]=="patch-before-boundary" for d in audit.denied_records(h,r,6870)))

    def test_history_patch_step_budget_and_carry_forward(self):
        rows,end=panel_fixture.boundary_fixture()
        ordinary,boundaries=audit.panel.split_rows(rows,audit.panel.CONDITIONS["patch"],end)
        records={1:{"birth_tick":0,"death_tick":61440,"environmental_death":True}}
        with patch.object(audit.experiment,"command_run",side_effect=AssertionError("native call forbidden")):
            histories,checked=audit.histories(ordinary,boundaries,records,end)
        self.assertEqual(checked,61440//15)
        self.assertEqual(histories[1][-1]["terminal"],"patch")
        self.assertEqual(histories[1][-1]["state"]["energy"],0)
        self.assertEqual(histories[1][-1]["budget"]["energy_upkeep"],1)
        broken=copy.deepcopy(ordinary)
        broken[1]["plants"][0]["energy"]+=1
        with self.assertRaises(RuntimeError): audit.histories(broken,boundaries,records,end)
        with self.assertRaises(RuntimeError): audit.histories(ordinary[1:],boundaries,records,end)


if __name__=="__main__":
    unittest.main()
