#!/usr/bin/env python3
"""Founder carry-in, bounded follow-up and paired native-prefix checks."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import garden_founder_independence as founders

DAY, STEP = founders.DAY, founders.STEP


def fixture(plants, extra=()):
    value = founders.fitness.fixture(plants, extra, start=founders.START, end=founders.END)
    value.update(start=founders.START, end=founders.END, stop=founders.STOP)
    return value


class FounderTests(unittest.TestCase):
    def test_fixed_panel(self):
        self.assertEqual(len(founders.MODELS)*len(founders.SEEDS)*len(founders.PATCHES),32)
        self.assertEqual(founders.FRAME_DAYS,(64,80,128))
        self.assertEqual((founders.END-founders.START)//DAY,64)
        self.assertEqual(founders.STOP-founders.END,2*DAY)

    def test_founder_bank_seed_does_not_count_as_descendant_reproduction(self):
        t=fixture([(1,0,0,64*DAY,True),(2,1,64*DAY+60,None,False)])
        f=founders.seed_funnel(t)
        self.assertEqual(f['groups']['founder_carry_in']['confirmed'],1)
        self.assertEqual(f['groups']['founder_carry_in']['qualifying'],0)
        self.assertEqual(f['groups']['new_descendant'],{})

    def test_descendant_bank_seed_is_separate_from_new_purchase(self):
        t=fixture([(1,0,0,None,False),(2,1,10*DAY,None,False),(3,2,64*DAY+60,None,False)])
        f=founders.seed_funnel(t)
        self.assertEqual(f['groups']['descendant_carry_in']['qualifying'],1)
        self.assertEqual(f['groups']['new_descendant'],{})

    def test_further_generation_requires_real_post_split_parent_link(self):
        t=fixture([(1,0,0,None,False),(2,1,10*DAY,None,False),
                   (3,2,70*DAY,None,False),(4,3,75*DAY,None,False)])
        f=founders.seed_funnel(t)
        self.assertEqual(f['groups']['new_descendant']['confirmed'],2)
        self.assertEqual(f['further_generation_links'],[{'parent':3,'child':4,'confirmation_tick':76*DAY}])

    def test_parent_can_die_before_child_confirmation(self):
        t=fixture([(1,0,0,None,False),(2,1,10*DAY,70*DAY,True),(3,2,70*DAY,None,False)])
        self.assertEqual(founders.seed_funnel(t)['groups']['new_descendant']['qualifying'],1)

    def test_exact_first_day_death_fails(self):
        for patch in (False,True):
            t=fixture([(1,0,0,None,False),(2,1,10*DAY,None,False),(3,2,70*DAY,71*DAY,patch)])
            f=founders.seed_funnel(t)['groups']['new_descendant']
            self.assertEqual(f['qualifying'],0)
            self.assertEqual(f['patch_failure' if patch else 'natural_failure'],1)

    def test_future_death_does_not_revoke_confirmation(self):
        t=fixture([(1,0,0,None,False),(2,1,10*DAY,None,False),(3,2,70*DAY,80*DAY,False)])
        before=founders.seed_funnel(t)
        t['lineages'][-1]['death_tick']=None
        self.assertEqual(founders.seed_funnel(t),before)

    def test_post_end_germination_gets_declared_followup(self):
        t=fixture([(1,0,0,None,False),(2,1,10*DAY,None,False),(3,2,128*DAY+60,None,False)])
        self.assertEqual(founders.seed_funnel(t)['groups']['new_descendant']['confirmed'],1)
        t['seeds'][-1]['birth_tick']=128*DAY+STEP
        self.assertEqual(founders.seed_funnel(t)['groups']['new_descendant'],{})

    def test_unresolved_seed_is_not_silently_successful(self):
        t=fixture([(1,0,0,None,False)],[(1,70*DAY)])
        t['seeds'][0].update(outcome='pending',end_tick=None)
        with self.assertRaises(RuntimeError):
            founders.seed_funnel(t)

    def test_seed_only_and_extinction_separate(self):
        t=fixture([(1,0,0,65*DAY,True)],[(1,64*DAY)])
        self.assertEqual(founders.state(t,64*DAY)['classification'],'living')
        t['lineages'][0]['death_tick']=64*DAY
        self.assertEqual(founders.state(t,64*DAY)['classification'],'seed-only')
        self.assertEqual(founders.state(t,66*DAY)['classification'],'extinct')

    def test_projection_at_split_non_mutating(self):
        t=fixture([(1,0,0,None,False),(2,1,70*DAY,None,False)])
        old=copy.deepcopy(t)
        p,s=founders.projection(t,founders.START)
        self.assertEqual([v['id'] for v in p],[1])
        self.assertEqual(s,[])
        self.assertEqual(t,old)

    def test_panel_rejects_missing_or_duplicate_pairs(self):
        with self.assertRaises(RuntimeError):
            founders.summarize([])


def native(build):
    with tempfile.TemporaryDirectory(prefix='founder-exit-test-') as temporary:
        root=Path(temporary)
        model=root/'reference.tgm'
        subprocess.run([build/'toy-factory-garden-water-audit-test',model],check=True,capture_output=True,timeout=30)
        crc=founders.pilot.model_crc(model)
        start,end=16*DAY,18*DAY
        args=[model,'neural','0xb61837dc','0x17c29444',str(start),str(end)]
        def run(suffix,extra):
            value,_=founders.pilot.run_json([build/'toy-factory-garden-persistence-trial',*args,*extra],root/f'{suffix}.json')
            return value
        control=run('control',[])
        ex=run('exit',['--founder-exit',str(start)])
        assert ex==run('repeat',['--founder-exit',str(start)])
        c=next(c for c in control['checkpoints'] if c['tick']==start)
        assert ex['founder_exit']['before_hash']==c['hash']
        for day in (16,18,20):
            r,_=founders.pilot.run_json([build/'toy-factory-garden-replay',model,'rainfed-crowded','neural-no-night-growth',
                '0xb61837dc','--leaf-policy','selective','--disturbance-seed','0x17c29444','--founder-exit',str(start),'--ticks',str(day*DAY)],root/f'replay{day}.json')
            checkpoint=next(c for c in ex['checkpoints'] if c['tick']==day*DAY)
            assert r['hash']==checkpoint['hash'] and r['founder_exit']==ex['founder_exit'] and r['model_crc32']==crc
        for extra in (['--founder-exit','0'],['--founder-exit','1'],['--founder-exit',str(end+STEP)],['--bad',str(start)]):
            p=subprocess.run([build/'toy-factory-garden-persistence-trial',*args,*extra],capture_output=True,timeout=30)
            assert p.returncode==2 and not p.stdout
        print('Native founder exit prefix, deterministic ledgers, independent replay and CLI checks passed')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--build',type=Path)
    args,other=parser.parse_known_args()
    if args.build:
        native(args.build.resolve())
    else:
        unittest.main(argv=[__file__,*other])
