#!/usr/bin/env python3
"""Offline cohort accounting, exact boundaries and frozen-evidence checks."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_renewal_cohorts as audit

DAY,STEP = audit.DAY,audit.STEP


def fixture(plants,extra=(),start=62*DAY,end=94*DAY,species=None):
    value = audit.fitness.fixture(plants,extra,start=start,end=end)
    mapping = species or {}
    indexed = {}
    for p in value["lineages"]:
        p["species"] = mapping.get(p["id"],indexed[p["parent"]]["species"] if p["parent"] else 0)
        indexed[p["id"]] = p
    value.update(start=start,end=end,stop=end+2*DAY)
    return value


def inspect(value,start=62*DAY,end=94*DAY):
    block,_ = audit.rolling.score_block(value["lineages"],value["seeds"],start,end,value["start"],value["stop"])
    return audit.period_audit(value,block,audit.family_ids(value["lineages"]))


class AccountingTests(unittest.TestCase):
    def test_fresh_and_carry_count_timing_and_natural_loss_reconcile(self):
        f = fixture([(1,0,0,None,False),(2,1,DAY,None,False),(3,2,50*DAY,None,False),
                     (4,2,70*DAY,73*DAY,False),(5,2,80*DAY,81*DAY,False)])
        before = copy.deepcopy(f)
        result = inspect(f)
        fresh,carry = result["groups"]["fresh"],result["groups"]["carry_in"]
        self.assertEqual(f,before)
        self.assertEqual(fresh["count"],1)
        self.assertEqual(fresh["available_ticks"],23*DAY+STEP)
        self.assertEqual(fresh["live_ticks"],2*DAY)
        self.assertEqual(fresh["natural_loss_ticks"],21*DAY+STEP)
        self.assertEqual(fresh["timing_removed_ticks"],9*DAY-STEP)
        self.assertEqual(carry["count"],1)
        self.assertEqual(carry["live_ticks"],21*DAY-STEP)
        self.assertEqual(carry["natural_loss_ticks"],0)
        self.assertEqual(result["confirmation_cohort"]["confirmation_cohort"],{"confirmed":1,"natural-failure":1})
        self.assertEqual(result["purchase_funnels"]["all"]["natural_failure"],1)
        self.assertEqual(result["purchase_funnels"]["established-descendant"]["purchases"],2)

    def test_confirmation_at_start_is_carry_and_at_end_counts_one_sample(self):
        f = fixture([(1,0,0,None,False),(2,1,DAY,None,False),
                     (3,2,61*DAY,None,False),(4,2,93*DAY,None,False)])
        r = inspect(f)
        self.assertEqual(r["groups"]["carry_in"]["live_ticks"],32*DAY-STEP)
        self.assertEqual(r["groups"]["fresh"]["live_ticks"],STEP)
        self.assertEqual(r["groups"]["fresh"]["timing_removed_ticks"],32*DAY-STEP)

    def test_death_at_confirmation_is_early_failure_not_credit_loss(self):
        for death,expected in ((71*DAY,0),(71*DAY+STEP,STEP)):
            f = fixture([(1,0,0,None,False),(2,1,DAY,None,False),(3,2,70*DAY,death,True)])
            r = inspect(f)
            self.assertEqual(r["groups"]["fresh"]["live_ticks"],expected)
            self.assertEqual(r["groups"]["fresh"]["count"],bool(expected))
            if expected:
                self.assertEqual(r["groups"]["fresh"]["patch_loss_ticks"],23*DAY)
            else:
                self.assertEqual(r["purchase_funnels"]["all"]["patch_censored"],1)
                self.assertEqual(r["groups"]["fresh"]["patch_loss_ticks"],0)

    def test_already_dead_young_carry_child_has_zero_live_but_explicit_loss(self):
        f = fixture([(1,0,0,None,False),(2,1,DAY,None,False),(3,2,50*DAY,55*DAY,True)])
        r = inspect(f)["groups"]["carry_in"]
        self.assertEqual((r["count"],r["positive_count"],r["live_ticks"]),(1,0,0))
        self.assertEqual(r["patch_loss_ticks"],r["available_ticks"])

    def test_unconfirmed_parent_does_not_qualify_surviving_child(self):
        f = fixture([(1,0,0,None,False),(2,1,62*DAY,63*DAY,False),
                     (3,2,63*DAY-STEP,None,False)])
        r = inspect(f)
        self.assertEqual(r["all_credit"]["live_ticks"],0)
        self.assertEqual(r["purchase_funnels"]["unconfirmed-descendant"]["confirmed"],1)
        self.assertEqual(r["purchase_funnels"]["all"]["qualifying"],0)

    def test_earlier_followup_projects_future_lifetimes_and_seed_counters(self):
        values = [fixture([(1,0,0,None,False),(2,1,DAY,None,False),(3,2,70*DAY,death,False)],
                          start=audit.pilot.START,end=audit.pilot.END) for death in (97*DAY,None)]
        self.assertEqual(inspect(values[0]),inspect(values[1]))
        r = inspect(values[0])
        self.assertIsNone(r["credit_children"][0]["death_tick"])

    def test_species_partitions_remain_separate_from_founder_families(self):
        f = fixture([(1,0,0,None,False),(2,0,0,None,False),(3,1,DAY,None,False),
                     (4,2,DAY,None,False),(5,3,70*DAY,None,False),(6,4,72*DAY,None,False)])
        r = inspect(f)
        self.assertEqual(r["by_species"]["flower"]["count"],2)
        self.assertEqual({p["founder_family"] for p in r["credit_children"]},{1,2})
        self.assertEqual(audit.add_groups(r["by_species"].values()),r["all_credit"])

    def test_invalid_credit_or_unexplained_loss_is_rejected(self):
        good = {"available_ticks":30,"live_ticks":15,"death_lost_ticks":15,
                "death_tick":90,"environmental_death":False}
        audit.credit_group([good],60)
        for changes in ({"live_ticks":16},{"available_ticks":90},{"death_tick":None},{"death_lost_ticks":0}):
            with self.subTest(changes=changes),self.assertRaises(RuntimeError): audit.credit_group([{**good,**changes}],60)


class TimelineTests(unittest.TestCase):
    def test_pending_seed_can_recover_a_living_species_loss(self):
        f = fixture([(1,0,0,DAY,True),(2,1,DAY+60,None,False)],start=4*DAY,end=8*DAY)
        families = audit.family_ids(f["lineages"])
        result = audit.species_turnover(f,families)["flower"]
        self.assertEqual(result["living_absences"],[{"loss_tick":DAY,"pending_seeds_at_loss":1,
            "last_deaths":[{"id":1,"cause":"patch"}],"recovery_tick":DAY+60}])
        self.assertEqual(result["terminal_living"],1)
        self.assertEqual(audit.census(f,DAY,families)["pending_by_species"],{"flower":1})

    def test_same_tick_replacement_is_not_a_false_species_absence(self):
        f = fixture([(1,0,0,DAY,False),(2,1,DAY,None,False)],start=4*DAY,end=8*DAY)
        self.assertEqual(audit.species_turnover(f,audit.family_ids(f["lineages"]))["flower"]["living_absences"],[])

    def test_unrecovered_loss_keeps_natural_cause_and_horizon_limit(self):
        f = fixture([(1,0,0,DAY,False),(2,0,0,None,False)],start=4*DAY,end=8*DAY,species={2:1})
        result = audit.species_turnover(f,audit.family_ids(f["lineages"]))
        loss = result["flower"]["living_absences"][0]
        self.assertEqual((loss["loss_tick"],loss["pending_seeds_at_loss"],loss["recovery_tick"]),(DAY,0,None))
        self.assertEqual(loss["last_deaths"],[{"id":1,"cause":"natural"}])
        self.assertEqual(result["ground-cover"]["living_absences"],[])
        self.assertEqual(result["shrub"]["terminal_living"],1)

    def test_full_audit_is_nonmutating_and_has_exact_daily_endpoints(self):
        f = fixture([(1,0,0,None,False),(2,1,DAY,None,False),
                     *[(3+i,2,(62+32*i)*DAY,None,False) for i in range(4)]],start=audit.pilot.START,end=audit.pilot.END)
        families = audit.family_ids(f["lineages"])
        end = audit.census(f,f["stop"],families)
        annotated = {"renewal_history":audit.rolling.history(f["lineages"],f["seeds"],f["start"],f["stop"]),
                     "terminal_species":end["species"],"terminal_families":end["families"],"final":{"living":end["living"]}}
        before = copy.deepcopy(f)
        with patch.object(audit.pilot,"run_json",side_effect=AssertionError("native execution")), \
             patch.object(audit.experiment,"command_run",side_effect=AssertionError("native execution")):
            result = audit.audit_trial(f,annotated)
        self.assertEqual(f,before)
        self.assertEqual(len(result["daily"]),193)
        self.assertEqual(result["daily"][-1],end)
        self.assertEqual([p["days"] for p in result["periods"]],[list(p) for p in audit.rolling.PERIODS])
        annotated["final"]["living"] -= 1
        with self.assertRaises(RuntimeError): audit.audit_trial(f,annotated)


class PairTests(unittest.TestCase):
    def test_minimum_switch_is_not_a_same_period_credit_change(self):
        result = audit.minimum_bridge([10,30,40,50],[25,20,35,60])
        self.assertEqual(result["minimum_delta"],10)
        self.assertEqual(result["at_control_minimum"]["same_period_delta"],15)
        self.assertEqual(result["at_control_minimum"]["candidate_switch_penalty"],5)
        self.assertEqual(result["at_candidate_minimum"]["same_period_delta"],-10)
        self.assertEqual(result["at_candidate_minimum"]["control_switch_penalty"],20)

    def test_minimum_ties_are_retained_and_witness_uses_earliest(self):
        r = audit.minimum_bridge([10,10,20,20],[20,10,10,20])
        self.assertEqual(r["control_minimum_periods"],[[62,94],[94,126]])
        self.assertEqual(r["candidate_minimum_periods"],[[94,126],[126,158]])
        self.assertEqual(r["at_control_minimum"]["period"],[62,94])
        self.assertEqual(r["minimum_delta"],0)
        with self.assertRaises(RuntimeError): audit.minimum_bridge([10],[10])

    def test_paired_accounting_separates_count_timing_and_deaths(self):
        a = {"count":2,"positive_count":2,"available_ticks":90,"live_ticks":60,
             "timing_removed_ticks":30,"natural_loss_ticks":0,"patch_loss_ticks":30}
        b = {"count":1,"positive_count":1,"available_ticks":60,"live_ticks":45,
             "timing_removed_ticks":0,"natural_loss_ticks":15,"patch_loss_ticks":0}
        r = audit.delta_group(a,b,60)
        self.assertEqual((r["live_ticks"],r["count_width_ticks"],r["timing_removed_ticks"],r["natural_loss_ticks"],r["patch_loss_ticks"]),
                         (-15,-60,-30,15,-30))

    def test_examples_are_score_selected_lexical_and_do_not_drop_other_cases(self):
        comparisons = {f"{r}-w-vs-n":{v:{"overall":{"pairs":[{"condition":k,f:d} for k,d in
                        (("z",15),("b",-30),("a",-30))]}} for v,f in (("renewal","minimum_delta"),("v2","renewal_delta"))}
                       for r in ("r1","r2")}
        before = copy.deepcopy(comparisons)
        examples = audit.select_examples(comparisons)
        self.assertEqual(comparisons,before)
        self.assertEqual([e["condition"] for e in examples],["z","a","a"]*2)
        self.assertEqual(len(examples),6)


class BundleTests(unittest.TestCase):
    def test_fixed_copy_plan_includes_every_rr_control_but_no_executables(self):
        self.assertEqual(len(audit.copies()),41)
        self.assertEqual(sum(p.startswith("ledgers/") for p in audit.copies()),40)
        self.assertTrue(all("/rr/" in p for p in audit.copies() if p.startswith("ledgers/")))
        self.assertFalse(any("bin/" in p or p.endswith(".tgm") for p in audit.copies()))
        self.assertEqual(audit.settings()["native_calls"],0)

    def test_offline_collection_repeat_verify_and_export_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base,out = root/"baseline",root/"artifacts/audit"
            base.mkdir(); out.parent.mkdir()
            protocol = root/audit.PROTOCOL
            protocol.parent.mkdir(parents=True); protocol.write_text("test protocol\n")
            audit.experiment.write_json(base/"results.json",{"frozen":True})
            audit.experiment.write_json(base/"manifest.json",{"artifacts":{"results.json":audit.experiment.digest(base/"results.json")}})
            sources = {audit.PROTOCOL:audit.experiment.digest(protocol)}
            with patch.object(audit,"BASELINE_SHA",audit.experiment.digest(base/"manifest.json")), \
                 patch.object(audit,"copies",return_value={"input/return-results.json":"results.json"}), \
                 patch.object(audit.previous,"verify"),patch.object(audit.experiment,"ROOT",root), \
                 patch.object(audit.experiment,"source_files",return_value=sources),patch.object(audit.experiment,"snapshot_sources"), \
                 patch.object(audit,"analyze",return_value={"complete":"synthetic-audit"}), \
                 patch.object(audit.pilot,"run_json",side_effect=AssertionError("native execution")), \
                 patch.object(audit.experiment,"command_run",side_effect=AssertionError("native execution")),patch("builtins.print"):
                audit.collect(base,out)
                audit.verify(out)
                target = root/"portable.json"
                audit.export(out,target); audit.export(out,target,True)
                target.write_text("{}")
                with self.assertRaises(RuntimeError): audit.export(out,target,True)
                (out/"input/return-results.json").write_text("{}")
                with self.assertRaises(RuntimeError): audit.check_inputs(out)
                with self.assertRaises(RuntimeError): audit.verify(out)
                with self.assertRaises(RuntimeError): audit.collect(base,out)


if __name__ == "__main__":
    unittest.main()
