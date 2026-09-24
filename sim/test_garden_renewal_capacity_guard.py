#!/usr/bin/env python3
"""Scope, receipt accounting, native parity and isolation of the capacity guard."""
import argparse
import copy
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

import garden_renewal_capacity_guard as audit
import test_garden_renewal_dark_guard as fixtures

BUILD = None


def rows_at(ticks=(15,), *, before=64, after=65, ordinary_denied=False):
    rows = [{"type":"world","tick":0,"plants":[],"dark_guard":{"events":[]},
             "night_capacity":{"rule":audit.NATIVE,"evaluated":0,"denied":0,"events":[]}}]
    evaluated,denied = 0,0
    for tick in range(15,max(ticks)+1,15):
        events,receipts = [],[]
        if tick in ticks:
            e = fixtures.event(tick,id=7,nodes_before=before,nodes_after=after,energy=256,water=512,energy_cost=8)
            e["denied"] = ordinary_denied
            events = [e]
            if not ordinary_denied and after > before:
                refusal = after > 64
                evaluated += 1
                denied += refusal
                receipts = [{"expense":0,"budget":audit.expected_budget(after),"denied":refusal}]
        rows.append({"type":"world","tick":tick,"plants":[{"id":7,"dead":False,"nodes":min(after,64)}],
                     "dark_guard":{"events":events},"night_capacity":{"rule":audit.NATIVE,
                     "evaluated":evaluated,"denied":denied,"events":receipts}})
    return rows


class CapacityGuardTests(unittest.TestCase):
    def test_fixed_worlds_calls_and_images(self):
        calls = audit.commands()
        self.assertEqual(len(calls),64)
        self.assertEqual(len({name for name,_ in calls}),64)
        self.assertEqual(sum(name.endswith('.gz') for name,_ in calls),16)
        self.assertEqual(sum('--framebuffer' in c for _,c in calls),48)
        self.assertEqual(audit.FRAMES,(46080,153600,245760))
        self.assertEqual([(c.name,c.first_tick,c.target_id) for c in audit.CASES],
            [('0d983a80.no-patch',37605,7),('58e36558.patch',134940,12),
             ('beda710e.patch',138765,15),('abf7af73.patch',None,None)])
        self.assertTrue(all('--purchase-veto' not in c for _,c in calls))
        self.assertTrue(all(c[c.index('--focal-founder')+1] == '5' for _,c in calls))

    def test_allowed_and_refused_receipts_leave_original_guard_unchanged(self):
        for before in (63,64):
            rows = rows_at(before=before,after=before+1)
            original = copy.deepcopy(rows)
            vetoes,summary = audit.audit_capacity(rows,'capacity',15)
            self.assertEqual(vetoes,{(15,7)} if before == 64 else set())
            self.assertEqual(summary['evaluated'],1)
            self.assertEqual(summary['denied'],int(before == 64))
            self.assertEqual(rows,original)
            self.assertFalse(rows[-1]['dark_guard']['events'][0]['denied'])

    def test_no_add_and_ordinary_denied_are_not_rechecked(self):
        for kwargs in ({'before':64,'after':64},{'ordinary_denied':True}):
            vetoes,summary = audit.audit_capacity(rows_at(**kwargs),'capacity',15)
            self.assertFalse(vetoes)
            self.assertEqual((summary['evaluated'],summary['denied']),(0,0))

    def test_refusal_streaks_count_ecology_steps_not_independent_plants(self):
        rows = rows_at((15,30,60,75,90))
        vetoes,summary = audit.audit_capacity(rows,'capacity',90)
        self.assertEqual(len(vetoes),5)
        self.assertEqual(len(summary['plants']),1)
        p = summary['plants'][0]
        self.assertEqual((p['attempts'],p['longest_streak']),(5,3))
        self.assertEqual((p['first']['tick'],p['last']['tick']),(15,90))

    def test_corrupt_missing_duplicate_or_wrong_budget_receipts_fail(self):
        for defect in ('missing','duplicate','index','decision','budget','counter','rule','body','invalid'):
            rows = copy.deepcopy(rows_at())
            m = rows[-1]['night_capacity']
            if defect == 'missing': m['events'] = []
            elif defect == 'duplicate': m['events'] *= 2
            elif defect == 'index': m['events'][0]['expense'] = 1
            elif defect == 'decision': m['events'][0]['denied'] = False
            elif defect == 'budget': m['events'][0]['budget']['payments'] = 36
            elif defect == 'counter': m['evaluated'] = 2
            elif defect == 'rule': m['rule'] = 'other'
            elif defect == 'body': rows[-1]['plants'][0]['nodes'] = 65
            else: rows[-1]['dark_guard']['events'][0]['invalid'] = True
            with self.subTest(defect=defect), self.assertRaises(RuntimeError):
                audit.audit_capacity(rows,'capacity',15)

    def test_truncation_and_control_metadata_fail(self):
        rows = rows_at()
        with self.assertRaises(RuntimeError): audit.audit_capacity(rows,'capacity',30)
        with self.assertRaises(RuntimeError): audit.audit_capacity(rows+rows[-1:],'capacity',15)
        with self.assertRaises(RuntimeError): audit.audit_capacity(rows,'control',15)
        cleaned = [audit.without_capacity(r) for r in rows]
        self.assertEqual(audit.audit_capacity(cleaned,'control',15)[0],set())

    def test_negative_control_must_match_every_raw_record(self):
        case = audit.CASES[-1]
        left = [{'type':'world','tick':0,'hash':'a'},{'type':'world','tick':15,'hash':'b'}]
        right = [{**r,'night_capacity':{}} for r in left]
        self.assertTrue(audit.check_prefix(left,right,case)['negative_control_identical'])
        with self.assertRaises(RuntimeError): audit.check_prefix(left,right[:-1],case)
        with self.assertRaises(RuntimeError): audit.check_prefix([],[],case)
        right[-1]['hash'] = 'different'
        with self.assertRaises(RuntimeError): audit.check_prefix(left,right,case)

    def test_first_refusal_costs_and_same_step_seed_accounting(self):
        case = audit.Case('seed','patch',15,7)
        event = fixtures.event(15,id=7,nodes_before=64,nodes_after=65,energy=256,water=512,energy_cost=8)
        p = {'id':7,'nodes':65,'energy':248,'water':507,'reproduction_cooldown':0,
             'agent':{'extend':61,'decisions':70}}
        q = {**p,'nodes':64,'energy':256,'water':512,'agent':{'extend':60,'decisions':69}}
        before = {'type':'world','tick':0}
        left = {'type':'world','tick':15,'plants':[p],'dark_guard':{'events':[event]}}
        right = {**left,'plants':[q],'night_capacity':{'events':[{'expense':0,'denied':True}]}}
        self.assertEqual(audit.check_prefix([before,left],[before,right],case)['tick'],15)
        q.update(energy=208,water=488,reproduction_cooldown=16)
        self.assertEqual(audit.check_prefix([before,left],[before,right],case)['tick'],15)
        q['energy'] += 1
        with self.assertRaises(RuntimeError): audit.check_prefix([before,left],[before,right],case)

    def test_later_useful_actions_include_same_step_seed_but_not_earlier_actions(self):
        def point(tick,**costs):
            return {'state':{'tick':tick},'budget':{'extensions':0,'finishes':0,'waits':0,
                    'energy_renewal':0,'energy_seeds':0,**costs}}
        history = [point(15,extensions=1),point(30,energy_seeds=48),point(45,finishes=1),
                   point(60,energy_renewal=9),{'state':{'tick':75},'budget':None}]
        result = audit.activity(history,30)
        self.assertEqual(result['counts'],{'extend':0,'finish':1,'wait':0,'renewal':1,'seeds':1})
        self.assertEqual(result['last_activity']['tick'],60)

    def test_host_only_header_and_forbidden_combinations(self):
        cc = shutil.which('cc')
        if not cc:
            self.skipTest('C compiler unavailable')
        flags = ['NIGHT_CAPACITY','DARK_GUARD','LEAF_MAINTENANCE','LARGE_POOL','COMBINED_EXPERIMENT',
                 'WIDE_DISPERSAL','WATER_HEADROOM']
        variants = [([],None),(['__ZEPHYR__'],False),(['TOY_FACTORY_GARDEN_PURCHASE_VETO'],False)]
        for extra,expected in variants:
            command = [cc,'-x','c','-std=c11','-fsyntax-only','-I',str(audit.experiment.ROOT/'src')]
            command += ['-DTOY_FACTORY_GARDEN_'+name+'=1' for name in flags]
            command += ['-D'+name+'=1' for name in extra]
            result = subprocess.run([*command,'-'],input='#include "garden_world.h"\n',text=True,capture_output=True)
            self.assertEqual(result.returncode == 0,expected is None,result.stderr)
        command = [cc,'-x','c','-fsyntax-only','-I',str(audit.experiment.ROOT/'src'),
                   '-DTOY_FACTORY_GARDEN_NIGHT_CAPACITY=1','-']
        result = subprocess.run(command,input='#include "garden_world.h"\n',text=True,capture_output=True)
        self.assertNotEqual(result.returncode,0)
        helper = audit.experiment.ROOT/'scripts/container/host-garden-defaults.sh'
        defaults = subprocess.check_output(
            ['bash','-eu','-c','source "$1"; printf "%s\\n" "${garden_default_cmake_options[@]}"',
             'garden-defaults',str(helper)],text=True).splitlines()
        self.assertIn('-DTOY_FACTORY_GARDEN_NIGHT_CAPACITY=OFF',defaults)
        for name in ('host-build.sh','host-player-build.sh','host-profile-build.sh'):
            wrapper = (audit.experiment.ROOT/'scripts/container'/name).read_text()
            self.assertIn('source "$app_dir/scripts/container/host-garden-defaults.sh"',wrapper)
            self.assertIn('"${garden_default_cmake_options[@]}"',wrapper)

    def test_native_reference_all_512_bodies(self):
        if BUILD is None:
            self.skipTest('native capacity build not supplied')
        lines = subprocess.check_output([str(BUILD/'toy-factory-garden-night-capacity-test'),'--reference'],text=True).splitlines()
        self.assertEqual(len(lines),512)
        keys = ('energy','stress','peak_stress','upkeep','dark_steps','payments','first_shortage_step','death_step','supported')
        for node,line in enumerate(lines,1):
            values = list(map(int,line.split()))
            self.assertEqual(values[0],node)
            self.assertEqual(dict(zip(keys,values[1:],strict=True)),audit.expected_budget(node))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build',type=Path)
    args,rest = parser.parse_known_args()
    BUILD = args.build.resolve() if args.build else None
    unittest.main(argv=[sys.argv[0],*rest])
