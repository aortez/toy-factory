#!/usr/bin/env python3
"""Named export contracts, censoring, interval semantics and native CLI parity."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import garden_renewal_controlled_gap as audit


def boundary(kind="world"):
    parent = {"id":1,"column":3,"dead":False,"parent":0,"generation":0,
              "age_ecology_ticks":3072,"species":"flower","nodes":36,"energy":240,"water":510}
    survivor = {**parent,"id":7,"parent":2,"column":0,"nodes":64,"species":"shrub"}
    before = {"type":kind,"tick":audit.AT,"hash":"5eea8cea","nodes":100,"living":2,
              "plants":[parent,survivor],"seeds":[{"parent":1,"column":4,"generation":1,"blockers":32}],
              "births":1,"deaths":0,"seeds_created":1,"seeds_expired":0}
    if kind == "seed-sites":
        before["sites"] = [[32 if c <= 5 else 0,42,100] for c in range(28)]
    after = copy.deepcopy(before)
    after.update(hash="postgap",nodes=64,living=1,plants=[copy.deepcopy(survivor)])
    after["seeds"][0]["blockers"] = 0
    if kind == "seed-sites":
        after["sites"] = [[32 if c <= 2 else 0,42,128] for c in range(28)]
    event = {"type":"gap","protocol":audit.NATIVE,"tick":audit.AT,"id":1,"column":3,
             "nodes":36,"energy":240,"water":510,"before_hash":"5eea8cea","after_hash":"postgap"}
    return before,after,event


class GapTests(unittest.TestCase):
    def test_fixed_scope_and_native_budget(self):
        self.assertEqual((audit.SEED,audit.TARGET,audit.REMOVED,audit.AT,audit.STOP),("0d983a80",7,1,46080,245760))
        calls = audit.commands()
        self.assertEqual(len(calls),24)
        self.assertEqual(sum(p.endswith(".gz") for p,_ in calls),8)
        self.assertEqual(sum("--framebuffer" in c for _,c in calls),16)
        self.assertEqual(audit.FRAMES,(46080,49920,61440,245760))
        for target,command in calls:
            self.assertEqual("--gap-lineage" in command,"gap." in target)
            self.assertNotIn("--disturbance-seed",command)
            self.assertEqual(command[command.index("--focal-founder")+1],"5")

    def test_named_boundary_preserves_bank_and_survivors(self):
        for kind in ("world","seed-sites"):
            before,after,event = boundary(kind)
            audit.validate_boundary(before,after,event)
            original = copy.deepcopy((before,after,event))
            ordinary,found = audit.split_rows([before,event,after],"gap",kind)
            self.assertEqual(ordinary,[before])
            self.assertEqual(found,{"before":before,"event":event,"after":after})
            self.assertEqual((before,after,event),original)

    def test_wrong_export_identity_cost_or_state_rejected(self):
        for field in ("tick","id","nodes","column","energy","water","protocol","before_hash","after_hash"):
            before,after,event = boundary()
            event[field] = "wrong" if isinstance(event[field],str) else event[field]+1
            with self.subTest(field=field),self.assertRaises(RuntimeError):
                audit.validate_boundary(before,after,event)
        for defect in ("survivor","seed","dead","young","founder","counter","extra"):
            before,after,event = copy.deepcopy(boundary())
            if defect == "survivor": after["plants"][0]["energy"] -= 1
            elif defect == "seed": after["seeds"][0]["parent"] = 7
            elif defect == "dead": before["plants"][0]["dead"] = True
            elif defect == "young": before["plants"][0]["age_ecology_ticks"] = 255
            elif defect == "founder": before["plants"][0]["parent"] = 99
            elif defect == "counter": after["deaths"] = 1
            else: after["unexpected"] = 1
            with self.subTest(defect=defect),self.assertRaises(RuntimeError):
                audit.validate_boundary(before,after,event)

    def test_soil_and_light_boundary_constraints(self):
        for index in (1,2):
            before,after,event = boundary("seed-sites")
            after["sites"][3][index] = 0
            with self.assertRaises(RuntimeError): audit.validate_boundary(before,after,event)

    def test_missing_repeated_or_unscheduled_event_rejected(self):
        before,after,event = boundary()
        for rows,arm in (([before],"gap"),([before,event],"gap"),([event,after],"gap"),
                         ([before,event,after,event,after],"gap"),([before,event,after],"control")):
            with self.assertRaises(RuntimeError): audit.split_rows(rows,arm)

    def test_prefix_requires_exact_ordinary_boundary(self):
        before,after,event = boundary()
        rows = [{"type":"world","tick":0},before]
        self.assertEqual(audit.check_prefix(rows,[*rows,event,after]),2)
        for wrong in (rows[:-1],[rows[0],after],[{**rows[0],"hash":"bad"},before]):
            with self.assertRaises(RuntimeError): audit.check_prefix(rows,wrong)

    def test_censoring_and_parentage(self):
        records = {1:{"id":1,"parent":0,"birth_tick":0,"death_tick":audit.AT,"removal_tick":audit.AT},
                   2:{"id":2,"parent":1,"birth_tick":audit.AT+15,"death_tick":None},
                   3:{"id":3,"parent":2,"birth_tick":audit.STOP-15,"death_tick":None},
                   4:{"id":4,"parent":1,"birth_tick":audit.AT+30,"death_tick":audit.AT+30+3840}}
        result = audit.cohort(records,audit.AT)
        self.assertEqual((result["offspring_born"],result["eligible_offspring"],result["cycle_survivors"],result["recent_alive"]),(3,2,1,1))
        self.assertEqual((result["natural_deaths"],result["alive_at_end"]),(1,2))
        self.assertEqual(result["parents"],{"1":2,"2":1})

    def test_exposure_uses_post_export_intervals_but_not_double_seed_ages(self):
        sites = [{"tick":t,"sites":[[0,42,100] for _ in range(28)],"seeds":[]} for t in (0,15,30,45)]
        sites[1]["sites"][3][0] = 32
        after = copy.deepcopy(sites[1]); after["sites"][3][0] = 0
        sites[2]["seeds"] = [{"parent":7,"column":4,"generation":2,"age":8,"blockers":4}]
        seeds = [{"parent":7,"birth_tick":-90,"column":4,"outcome":"pending"}]
        with mock.patch.object(audit,"AT",15),mock.patch.object(audit,"STOP",45):
            data = audit.site_exposure(sites,{"after":after},seeds)
        self.assertEqual(data["post_export_intervals"],2)
        self.assertEqual(data["footprint_columns"]["3"]["open_steps"],2)
        self.assertEqual(data["footprint_columns"]["3"]["longest_open_streak"],2)
        self.assertEqual(data["target_seed_exposure"]["-90"]["samples"],1)

    def test_native_dead_plants_have_no_dispersal_support(self):
        plant = {"id":1,"parent":0,"generation":0,"column":3,"dead":True,"species":"flower","genome":[0]*8}
        world = {"type":"world","tick":0,"hash":"same","nodes":4,"living":0,"births":0,
                 "deaths":1,"seeds_created":0,"seeds_expired":0,"plants":[plant],"seeds":[]}
        native = {k:v for k,v in plant.items() if k != "genome"}
        native.update(species=0,dispersal_columns=0)
        sites = {**world,"type":"seed-sites","plants":[native],"sites":[[32 if abs(c-3)<3 else 0,42,100] for c in range(28)]}
        with mock.patch.object(audit,"STOP",0):
            self.assertEqual(audit.check_sites([world],[sites],[],{1:plant}),1)
            sites["plants"][0]["dispersal_columns"] = 1
            with self.assertRaises(RuntimeError): audit.check_sites([world],[sites],[],{1:plant})

    def test_logged_age_and_order_must_match_reconstruction(self):
        parent = {"id":1,"parent":0,"generation":0,"column":0,"dead":False,"species":"flower","genome":[0]*8}
        seed = {"parent":1,"generation":1,"column":3,"blockers":1}
        world = {"type":"world","tick":0,"hash":"same","nodes":4,"living":1,"births":0,
                 "deaths":0,"seeds_created":1,"seeds_expired":0,"plants":[parent],"seeds":[seed]}
        native_parent = {**parent,"species":0,"dispersal_columns":sum(1 << c for c in range(3,10))}
        sites = {**world,"type":"seed-sites","plants":[native_parent],
                 "seeds":[{**seed,"age":0,"species":0}],"sites":[[32 if c<3 else 0,42,100] for c in range(28)]}
        record = {**seed,"birth_tick":0,"end_tick":None,"species":"flower"}
        with mock.patch.object(audit,"STOP",0):
            self.assertEqual(audit.check_sites([world],[sites],[record],{1:parent}),1)
            for age in (-1,1,256):
                sites["seeds"][0]["age"] = age
                with self.assertRaises(RuntimeError): audit.check_sites([world],[sites],[record],{1:parent})


def cli_checks(build):
    if "TOY_FACTORY_GARDEN_LEAF_MAINTENANCE:BOOL=ON\n" not in (build/"CMakeCache.txt").read_text():
        return
    with tempfile.TemporaryDirectory(prefix="named-gap-test-") as directory:
        model = Path(directory)/"reference.tgm"
        subprocess.run([str(build/"toy-factory-garden-water-audit-test"),str(model)],check=True,timeout=60)
        base = [str(model),"rainfed-crowded",audit.experiment.NIGHT_POLICY,"123","--leaf-policy","selective",
                "--focal-model",str(model),"--focal-founder","5"]
        def run(tool,args):
            return subprocess.run([str(build/f"toy-factory-garden-{tool}"),*base,*args],capture_output=True,text=True,timeout=30)
        control = run("inspect",["--ecology","--ticks","3855"])
        audit.require(control.returncode == 0,control.stderr)
        rows = [json.loads(s) for s in control.stdout.splitlines()]
        before = next(r for r in rows if r["type"] == "world" and r["tick"] == 3840)
        target = next(p["id"] for p in before["plants"] if not p["dead"] and p["age_ecology_ticks"] >= 256)
        named = ["--gap-at","3840","--gap-lineage",str(target)]
        result = run("inspect",["--ecology","--ticks","3855",*named])
        audit.require(result.returncode == 0,result.stderr)
        values = [json.loads(s) for s in result.stdout.splitlines()]
        event_at = next(i for i,r in enumerate(values) if r["type"] == "gap")
        audit.require(values[:event_at] == rows[:event_at],"native named prefix changed")
        event,after = values[event_at:event_at+2]
        audit.require(event["id"] == target and event["protocol"] == audit.NATIVE and
                      after["plants"] == [p for p in before["plants"] if p["id"] != target],"wrong native named removal")
        for ticks,expected in ((3840,after),(3855,values[-1])):
            replay = run("replay",["--ticks",str(ticks),*named])
            audit.require(replay.returncode == 0,replay.stderr)
            value = json.loads(replay.stdout)
            audit.require(value["hash"] == expected["hash"] and value["gap_protocol"] == audit.NATIVE
                          and value["removed_id"] == target,"named replay/census differs")
        for tool in ("inspect","replay"):
            for options in (["--gap-lineage"],["--gap-lineage","1"],["--gap-at","3840","--gap-lineage","0"],
                            ["--gap-at","3840","--gap-lineage","-1"],["--gap-at","3840","--gap-lineage","4294967296"],
                            [*named,"--gap-lineage",str(target)],["--gap-at","3840","--gap-lineage","999"],
                            ["--gap-at","15","--gap-lineage",str(target)],
                            [*named,"--disturbance-seed","123"],[*named,"--root-bootstrap-after","15"],
                            ["--gap-at","3840"]):
                audit.require(run(tool,["--ticks","3855",*options]).returncode != 0,"invalid named CLI accepted")
    print("Named gap CLI: exact prefix, focal routing, boundary/next-step replay and invalid options passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build",type=Path)
    args = parser.parse_args()
    if args.build:
        cli_checks(args.build.resolve())
    unittest.main(argv=[sys.argv[0]])
