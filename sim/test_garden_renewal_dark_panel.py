#!/usr/bin/env python3
"""Offline-only scope, patch boundaries, lineage/exposure and frame regressions."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zlib

import garden_renewal_dark_panel as audit


def boundary_fixture(guarded=True):
    event = audit.disturbance.schedule(int(audit.CONDITIONS["patch"],16))[0]
    tick = event["tick"]
    plant = {"id":1,"parent":0,"species":"flower","generation":0,"column":event["first_column"],
        "genome":[0]*8,"dead":False,"energy":128,"water":32,"nodes":4,"roots":2,"leaves":1,
        "active_leaves":1,"root_cells":[[0,0],[0,1]],"flowers":0,"spent_flowers":0,
        "vigor":0,"stress":0,"flags":0,"tips":3,"energy_income":0,"water_income":0,
        "reproduction_cooldown":0,"agent":dict.fromkeys(("decisions","extend","finish","wait"),0),
        "leaf":{"conditions":[255],"remainder":0,"renewals":0,"observations":0,"proposals":0,"restored":0,"worn":0}}
    rows = []
    for t in range(0,tick+1,15):
        p = copy.deepcopy(plant)
        p["energy_income"] = p["water_income"] = int(t > 0 and t % 60 == 0)
        phase = (64+t//15)%256
        row = {"type":"world","tick":t,"hash":f"{t:08x}","plants":[p],"nodes":4,"node_capacity":512,
            "living":1,"births":0,"deaths":0,"seeds":[],"seeds_created":0,"seeds_expired":0,"max_generation":0,
            "sun_phase":phase,"sun_strength":audit.guard.reference.prior.sun_strength(phase),
            "rain_rate":0,"rain_deposited":0,"rain_runoff":0,"moisture":10,
            "weather_seed":audit.SEEDS[0],"focal_policy":audit.settings()["routing"],
            "leaf_policy":"selective","leaf_environment":"leaf-maintenance-v1"}
        if guarded:
            row["dark_guard"] = {"rule":audit.guard.GUARD,"overflow":False,"events":[],"evaluated":[0,0,0],"denied":[0,0,0]}
        rows.append(row)
    before = rows[-1]
    after = copy.deepcopy(before)
    after.update(hash="deadbeef",living=0,deaths=1)
    after["plants"][0].update(dead=True,energy=0,water=0,stress=8,flags=1,tips=0,
                              energy_income=0,water_income=0,active_leaves=0)
    event = {**event,"type":"disturbance","killed":[1],"energy":128,"water":32,"nodes":4,
             "before_hash":before["hash"],"after_hash":after["hash"]}
    final = copy.deepcopy(after)
    final.update(tick=tick+15,hash="00000000",sun_phase=(64+(tick+15)//15)%256)
    final["sun_strength"] = audit.guard.reference.prior.sun_strength(final["sun_phase"])
    return rows+[event,after,final],tick+15


class PanelTests(unittest.TestCase):
    def test_fixed_scope_and_commands(self):
        settings = audit.settings()
        self.assertEqual((len(audit.CASES),audit.STOP,audit.LATE),(16,245760,184320))
        self.assertEqual(settings["budget"]["native_calls"],128)
        commands = audit.commands()
        self.assertEqual(len(commands),128)
        self.assertEqual(len({n for n,_ in commands}),128)
        self.assertEqual(sum(n.endswith("gz") for n,_ in commands),32)
        self.assertEqual(sum("--framebuffer" in c for _,c in commands),96)
        self.assertEqual(sum("--disturbance-seed" in c for _,c in commands),64)
        for name,c in commands:
            self.assertEqual(c[c.index("--focal-founder")+1],"5")
            self.assertEqual(c[c.index("--focal-model")+1],"models/r2-w.tgm")
            self.assertEqual(c[1],"models/r2-n.tgm")
            self.assertFalse(any("train" in v or "mutate" in v for v in c))
            if name.endswith("gz"):
                self.assertEqual(int(c[c.index("--ticks")+1]),audit.STOP)
            else:
                self.assertIn(int(c[c.index("--ticks")+1]),audit.FRAME_TICKS)

    def test_split_preserves_ordinary_rows_and_boundary(self):
        rows,stop = boundary_fixture()
        original = copy.deepcopy(rows)
        ordinary,boundaries = audit.split_rows(rows,audit.CONDITIONS["patch"],stop)
        self.assertEqual(rows,original)
        self.assertEqual(len(boundaries),1)
        self.assertEqual(len(ordinary),stop//15+1)
        b = boundaries[audit.disturbance.FIRST]
        self.assertEqual(b["before"],ordinary[-2])
        self.assertEqual(b["after"],rows[-2])

    def test_corrupt_or_missing_patch_boundary_rejected(self):
        original,stop = boundary_fixture()
        for defect in ("missing_event","missing_after","wrong_time","seed","victim","resource","survivor","metadata","duplicate"):
            rows = copy.deepcopy(original)
            if defect == "missing_event": rows=rows[:-3]+rows[-1:]
            elif defect == "missing_after": rows.pop(-2)
            elif defect == "wrong_time": rows[-3]["tick"]+=15
            elif defect == "seed": rows[-3]["seed"]="12345678"
            elif defect == "victim": rows[-3]["killed"]=[]
            elif defect == "resource": rows[-3]["energy"]+=1
            elif defect == "survivor": rows[-2]["plants"][0]["nodes"]+=1
            elif defect == "metadata": rows[-2]["dark_guard"]["denied"][0]=1
            else: rows[-1:-1]=copy.deepcopy(rows[-4:-1])
            with self.subTest(defect=defect),self.assertRaises((RuntimeError,KeyError)):
                audit.split_rows(rows,audit.CONDITIONS["patch"],stop)
        with self.assertRaises(RuntimeError): audit.split_rows(original,None,stop)

    def test_accounting_carries_post_patch_state_and_preserves_default(self):
        rows,stop = boundary_fixture()
        ordinary,boundaries = audit.split_rows(rows,audit.CONDITIONS["patch"],stop)
        result,counters = audit.guard.accounting_rows(ordinary,"guard",stop=stop,boundaries=boundaries,retain_events=False)
        self.assertEqual(result,ordinary)
        self.assertEqual(counters["evaluated"],{})
        self.assertEqual(counters["events"],[])
        bad = copy.deepcopy(boundaries)
        bad[audit.disturbance.FIRST]["before"]["hash"]="bad"
        with self.assertRaises(RuntimeError): audit.guard.accounting_rows(ordinary,"guard",stop=stop,boundaries=bad)
        with self.assertRaises(RuntimeError): audit.guard.accounting_rows(ordinary,"invalid",stop=stop)
        with self.assertRaises(RuntimeError): audit.guard.accounting_rows(ordinary,"guard",stop=stop-15,boundaries=boundaries)
        with self.assertRaises(RuntimeError): audit.guard.accounting_rows(ordinary,"guard",stop=stop,boundaries={stop+15:boundaries[audit.disturbance.FIRST]})

    def test_tip_deaths_not_double_counted_and_post_event_exposure(self):
        rows,stop = boundary_fixture()
        ordinary,boundaries = audit.split_rows(rows,audit.CONDITIONS["patch"],stop)
        result = audit.startup.tips.analyze_stream(map(json.dumps,ordinary),stop,audit.disturbance.FIRST,512,disturbances=boundaries)
        self.assertEqual(result["totals"]["death_tips"],3)
        self.assertEqual(result["totals"]["terminated_tips"],0)
        self.assertEqual(result["totals"]["final_tips"],0)
        self.assertEqual(result["windows"]["late"]["living_steps"],0)
        self.assertEqual(result["windows"]["whole"]["living_steps"],audit.disturbance.FIRST//15)
        self.assertEqual(result["lineages"][0]["death_tick"],audit.disturbance.FIRST)
        self.assertFalse(result["lineages"][0]["alive_at_end"])
        end_rows=ordinary[:-1]
        final = audit.startup.tips.analyze_stream(map(json.dumps,end_rows),stop-15,0,512,disturbances=boundaries)
        self.assertEqual(final["totals"]["final_tips"],0)
        with self.assertRaises(RuntimeError):
            audit.startup.tips.analyze_stream(map(json.dumps,ordinary),stop,0,512,disturbances={stop+15:boundaries[audit.disturbance.FIRST]})

    def test_live_resource_leaf_and_tip_auditors_agree_across_patch(self):
        rows,stop = boundary_fixture()
        ordinary,boundaries = audit.split_rows(rows,audit.CONDITIONS["patch"],stop)
        with tempfile.TemporaryDirectory(prefix="dark-panel-test-") as temp:
            path=Path(temp)/"worlds.gz"
            audit.guard.write_accounting(path,ordinary)
            world,_=audit.competition.world_analysis(path,"selective",512,stop,audit.disturbance.FIRST,disturbances=boundaries)
        records={p["id"]:p for p in world["lineages"]}
        result=audit.supplementary(ordinary,boundaries,records,audit.CASES[0],stop,audit.disturbance.FIRST)
        self.assertEqual(world["windows"]["whole"]["natural_deaths"],0)
        self.assertEqual(world["windows"]["whole"]["environmental_deaths"],1)
        self.assertEqual(result["exposure"]["whole"]["living_steps"],audit.disturbance.FIRST//15)
        self.assertEqual(result["exposure"]["late"]["living_steps"],0)
        self.assertEqual(result["daily"][-1]["living"],0)

    def test_censoring_does_not_turn_recent_child_into_a_survivor(self):
        records={1:{"id":1,"parent":0,"birth_tick":0,"death_tick":None},
                 2:{"id":2,"parent":1,"birth_tick":15,"death_tick":3855,"environmental_death":True},
                 3:{"id":3,"parent":1,"birth_tick":30,"death_tick":None},
                 4:{"id":4,"parent":3,"birth_tick":60,"death_tick":None}}
        result=audit.competition.lifetime_cohort(records,3855)
        self.assertEqual((result["eligible_offspring"],result["cycle_survivors"],result["recent_alive"]),(1,0,2))
        self.assertEqual(result["cycle_survivors_with_surviving_child"],0)

    def test_seed_only_population_is_not_extinct_or_a_living_species(self):
        rows,_=boundary_fixture(False)
        row=copy.deepcopy(rows[-2])
        row["seeds"]=[{"parent":1}]
        records={1:{"founder":1,"species":"flower"}}
        p=audit.population(row,records)
        self.assertFalse(p["extinct"])
        self.assertEqual(p["living_species"],0)
        self.assertEqual(p["extant_species"],["flower"])
        row["seeds"]=[]
        self.assertTrue(audit.population(row,records)["extinct"])

    def test_frame_identity_crc_and_patch_death_count(self):
        rows,_=boundary_fixture()
        sample=rows[-2]
        case=audit.Case(audit.SEEDS[0],"patch","guard")
        raw=bytes(audit.gallery.FRAME_BYTES)
        value={k:sample[k] for k in ("tick","hash","living","nodes","births","deaths","sun_phase","sun_strength",
             "rain_rate","rain_deposited","rain_runoff","moisture","focal_policy")}
        value.update(schema_version=1,scenario="rainfed-crowded",seed=case.seed,policy=audit.experiment.NIGHT_POLICY,
            model_crc32=audit.settings()["models"]["r2-n"],node_capacity=512,seed_dispersal="wide-v1",water_uptake="headroom-v1",
            leaf_policy="selective",leaf_environment="leaf-maintenance-v1",plant_slots=1,seed_bank=0,descendants=0,
            disturbance_protocol=audit.disturbance.PROTOCOL,disturbance_seed=case.patch,disturbance_events=1,environmental_deaths=1,
            dark_guard_rule=audit.guard.GUARD,framebuffer_crc32=f"{zlib.crc32(raw):08x}")
        event=rows[-3]
        audit.check_frame(value,sample,case,sample["tick"],raw,[event])
        for key in ("hash","model_crc32","seed","dark_guard_rule","environmental_deaths","framebuffer_crc32"):
            wrong={**value,key:"wrong"}
            with self.subTest(key=key),self.assertRaises(RuntimeError): audit.check_frame(wrong,sample,case,sample["tick"],raw,[event])
        with self.assertRaises(RuntimeError): audit.check_frame(value,sample,case,sample["tick"],raw[:-1],[event])
        with self.assertRaises(RuntimeError): audit.check_frame(value,sample,audit.CASES[0],sample["tick"],raw,[event])

    def test_prefix_ends_before_same_tick_patch_not_after_it(self):
        rows,stop=boundary_fixture()
        with patch.object(audit.startup,"read_trace",return_value=iter(rows)):
            result=list(audit.prefix(Path("unused"),stop-15))
        self.assertEqual(result[-1],rows[-4])
        self.assertEqual(result[-1]["living"],1)
        with patch.object(audit.startup,"read_trace",return_value=iter(rows[:-4])),self.assertRaises(RuntimeError):
            list(audit.prefix(Path("unused"),stop-15))

    def test_existing_bundle_inputs_include_binaries_and_complete_controls(self):
        copies=audit.copies()
        for arm in audit.guard.CASES:
            self.assertEqual(copies[f"bin/{arm}-inspect"],f"bin/{arm}-inspect")
            self.assertEqual(copies[f"bin/{arm}-replay"],f"bin/{arm}-replay")
            self.assertEqual(copies[f"input/{arm}.jsonl.gz"],f"traces/{arm}.jsonl.gz")
        self.assertEqual(copies["input/native-source.tar.gz"],"source.tar.gz")

    def test_aggregate_keeps_conditions_and_paired_directions_separate(self):
        cases={}
        fields=("births","natural_deaths","environmental_deaths","seeds_created","seeds_expired",
                "descendant_seeds","seed_producing_descendant_parents")
        for case in audit.CASES:
            n=10 if case.patch else 1
            if case.arm=="guard":
                n+=(-1 if case.seed==audit.SEEDS[0] else 2)
            final=dict.fromkeys(("living","living_founders","living_descendants","living_species","living_families"),n)
            final["extinct"]=n==0
            window={**dict.fromkeys(fields,n),"cohort":{"eligible_offspring":n,"cycle_survivors":n},
                    "exposure":{"living_steps":n}}
            cases[case.name]={"summary":{"final":final,"windows":{"whole":window,"late":window}}}
        result=audit.aggregate(cases)
        self.assertEqual(result["no-patch"]["arms"]["control"]["final"]["living"],4)
        self.assertEqual(result["patch"]["arms"]["control"]["final"]["living"],40)
        self.assertEqual(result["no-patch"]["arms"]["guard"]["final"]["extinct"],1)
        for condition in audit.CONDITIONS:
            for i,pair in enumerate(result[condition]["pairs"]):
                expected=-1 if i==0 else 2
                self.assertEqual(pair["seed"],audit.SEEDS[i])
                self.assertEqual(pair["final_delta"]["living"],expected)
                self.assertEqual(pair["window_delta"]["late"]["births"],expected)
                self.assertEqual(pair["closing_cohort_delta"]["cycle_survivors"],expected)

    def test_gallery_includes_every_declared_case_and_day_once(self):
        frames=[]
        cases={}
        for case in audit.CASES:
            cases[case.name]={"summary":{"final":{"living":1},"windows":{"late":{"births":0,"descendant_seeds":0}}}}
            frames.extend({"id":f"{case.name}.{t}","case":case.name,"tick":t} for t in audit.FRAME_TICKS)
        markdown=audit.gallery_markdown({"cases":cases,"frames":frames})
        for frame in frames:
            self.assertEqual(markdown.count(f"(renewal-dark-panel-frames/{frame['id']}.png)"),1)
        self.assertEqual(markdown.count("(renewal-dark-panel-frames/"),48)


if __name__=="__main__":
    unittest.main()
