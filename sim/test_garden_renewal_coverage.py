#!/usr/bin/env python3
"""Coverage-only design, frozen reuse, routing and exact process budget."""
from concurrent.futures import ThreadPoolExecutor
import copy
from dataclasses import FrozenInstanceError
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_renewal_coverage as run
import test_garden_renewal_training as fixtures


def panel(seeds, label="steady", patches=run.previous.TRAIN_PATCHES):
    return {k:copy.deepcopy(fixtures.world(label)) for k,*_ in run.mixed.conditions(seeds,dict(patches))}


def fake_search():
    return {"candidates":[{"id":n,"parent":None if n == "initial" else "initial",
        "mutation":None if n == "initial" else {"rng_before":100+i}} for i,n in enumerate(run.names())]}


def timing_fixture():
    root = Path("/frozen-coverage")
    result = {"replicas":{r:{"arms":{a:{"search":fake_search()} for a in run.ARMS}} for r in run.REPLICAS}}
    timing = {"command_root":str(root),"replicas":{}}
    for replica in run.REPLICAS:
        arms = {}
        for arm in run.ARMS:
            calls = run.expected_calls(root/run.subpath(replica,arm),fake_search(),run.study(replica,arm),train=arm == "wide")
            arms[arm] = [{"artifact":target,"command":command,"seconds":0,
                **({"repeat_command":[*command[:-1],"/tmp/mixed-garden-frame-test/frame.rgb565"],"repeat_seconds":0}
                   if target.endswith(".png") else {})} for target,command in calls.items()]
        timing["replicas"][replica] = {"arms":arms}
    return result,timing


class DesignTests(unittest.TestCase):
    def test_fixed_budget_split_and_unchanged_streams_schedules_selector(self):
        s = run.settings()
        self.assertEqual(s["budget"]["native_processes"],2084)
        self.assertEqual(sum(s["budget"][k] for k in ("training_trials","repeat_trials","review_trials","frame_replays","mutation_calls")),2084)
        self.assertEqual((run.mixed.GENERATIONS,run.mixed.OFFSPRING,run.mixed.MUTATIONS),(3,3,32))
        self.assertEqual(run.OBJECTIVE.name,"renewal")
        for old in run.previous.STUDIES:
            narrow,wide = (run.study(old.name,a) for a in run.ARMS)
            self.assertEqual(narrow.development,old.development)
            self.assertEqual(wide.development,narrow.development+run.ADDED)
            self.assertEqual((len(narrow.development),len(wide.development),len(wide.review)),(8,16,8))
            for study in (narrow,wide):
                self.assertEqual(study.rng,old.rng)
                self.assertEqual(study.development_patches,old.development_patches)
                self.assertEqual(study.review_patches,old.review_patches)
                self.assertTrue(set(study.review).isdisjoint((*study.development,*old.review)))
        self.assertEqual(run.mixed.MIXED.rng,run.mixed.RNG)

    def test_detached_settings_immutable_profiles_and_unknown_names(self):
        settings = run.settings()
        settings["budget"]["native_processes"] = 0
        settings["replicas"]["r1"]["wide"]["development"].clear()
        self.assertEqual(run.settings()["budget"]["native_processes"],2084)
        self.assertEqual(len(run.study("r1","wide").development),16)
        with self.assertRaises(FrozenInstanceError): run.study("r1","wide").rng = 1
        with self.assertRaises(FrozenInstanceError): run.OBJECTIVE.name = "v2"
        for pair in (("other","wide"),("r1","v2")):
            with self.assertRaises(RuntimeError): run.study(*pair)

    def test_reuse_contains_both_complete_narrow_searches_not_old_reviews(self):
        copied = run.copies()
        self.assertEqual(sum('/search/' in k and k.endswith('.json') and not k.endswith('.mutation.json') for k in copied),320)
        self.assertEqual(sum('/repeat/' in k and k.endswith('.json') and not k.endswith('.mutation.json') for k in copied),320)
        self.assertEqual(sum(k.endswith('.mutation.json') for k in copied),36)
        self.assertTrue(all('/review/' not in k and '/wide/search/' not in k and '/wide/repeat/' not in k for k in copied))
        for replica in run.REPLICAS:
            for folder in ('search','repeat'):
                for n in run.names():
                    dest = str(run.subpath(replica,'narrow')/folder/f'{n}.tgm')
                    self.assertEqual(copied[dest],f'replicas/{replica}/arms/renewal/{folder}/{n}.tgm')

    def test_all_generations_all_review_conditions_have_fixed_frame_order(self):
        arms = {}
        for arm in run.ARMS:
            arms[arm] = {"review":[{"frames":[{"id":f"g{g}.{k}","framebuffer":f"review/g{g}.{k}.rgb565",
                "png":f"review/g{g}.{k}.png","generation":g,"condition":k} for k,*_ in
                run.mixed.conditions(run.REVIEW,dict(run.previous.REVIEW_PATCHES))]} for g in range(4)]}
        rows = run.frame_rows(arms)
        self.assertEqual(len(rows),16)
        self.assertTrue(all(len(row) == 8 for row in rows))
        self.assertEqual([f['arm'] for f in rows[0]],['narrow']*4+['wide']*4)
        self.assertEqual([f['generation'] for f in rows[0]],list(range(4))*2)
        self.assertEqual(len({f['id'] for row in rows for f in row}),128)


class AnalysisTests(unittest.TestCase):
    def test_twice_the_worlds_does_not_fake_mean_credit_improvement(self):
        a,b = (run.views(panel(s.development),s.development,s.development_patches)
               for s in (run.study('r1','narrow'),run.study('r1','wide')))
        for view in run.scoring.ARMS:
            self.assertEqual(a[view]['mean_credit_ticks'],b[view]['mean_credit_ticks'])
            self.assertEqual(b[view]['aggregate']['key'][2],2*a[view]['aggregate']['key'][2])
            self.assertEqual((a[view]['condition_count'],b[view]['condition_count']),(16,32))
            mean = a[view]['mean_credit_ticks']
            self.assertEqual(Fraction(mean['numerator'],mean['denominator']),Fraction(a[view]['aggregate']['key'][2],16))

    def test_shared_added_subsets_and_paired_review_omissions(self):
        wide = panel(run.study('r1','wide').development)
        before = copy.deepcopy(wide)
        a,b = run.subset(wide,run.previous.TRAIN),run.subset(wide,run.ADDED)
        self.assertEqual(set(a)|set(b),set(wide))
        self.assertTrue(set(a).isdisjoint(b))
        self.assertEqual(wide,before)
        review_a = panel(run.REVIEW,'sterile',run.previous.REVIEW_PATCHES)
        review_b = panel(run.REVIEW,'steady',run.previous.REVIEW_PATCHES)
        result = run.comparisons(review_a,review_b)
        for view in run.scoring.ARMS:
            self.assertEqual(result[view]['overall']['paired_counts'],{'wins':16,'ties':0,'losses':0})
            self.assertEqual(set(result[view]['schedules']),{'review-1','review-2'})
            for seed,g in result[view]['leave_one_world_seed_out'].items():
                self.assertEqual(len(g['pairs']),14)
                self.assertTrue(all(not p['condition'].endswith('.'+seed) for p in g['pairs']))
        with self.assertRaises(RuntimeError): run.comparisons(a,b)


class BoundaryTests(unittest.TestCase):
    def test_full_call_budget_and_narrow_has_no_training_calls(self):
        result,timing = timing_fixture()
        run.check_budget(timing,result)
        for replica in run.REPLICAS:
            records = timing['replicas'][replica]['arms']
            self.assertEqual(len(records['narrow']),128)
            self.assertEqual(len(records['wide']),786)
            self.assertTrue(all(r['artifact'].startswith('review/') for r in records['narrow']))

    def test_wrong_counts_commands_and_interventions_are_rejected(self):
        result,timing = timing_fixture()
        for failure in ('missing','extra','duplicate','schedule','model','mutation','intervention','target','repeat','unlogged_repeat','replica'):
            bad = copy.deepcopy(timing)
            rows = bad['replicas']['r1']['arms']['wide']
            if failure == 'missing': rows.pop()
            elif failure == 'extra': rows.append(copy.deepcopy(rows[0]))
            elif failure == 'duplicate': rows[1] = copy.deepcopy(rows[0])
            elif failure == 'schedule': rows[0]['command'][4] = '0x00000001'
            elif failure == 'model': rows[0]['command'][1] = '/other/model.tgm'
            elif failure == 'mutation': next(r for r in rows if r['artifact'].endswith('.mutation.json'))['command'][-1] = '33'
            elif failure == 'intervention': rows[0]['command'].append('--founder-exit')
            elif failure == 'target': rows[0]['artifact'] = 'elsewhere.json'
            elif failure == 'repeat': next(r for r in rows if r['artifact'].endswith('.png'))['repeat_command'][-1] = '/tmp/not-private.rgb565'
            elif failure == 'unlogged_repeat': rows[0]['repeat_command'] = list(rows[0]['command'])
            else: bad['replicas'].pop('r2')
            with self.subTest(failure=failure),self.assertRaises(RuntimeError): run.check_budget(bad,result)

    def test_expected_commands_keep_roles_models_and_followup(self):
        result,timing = timing_fixture()
        for replica in run.REPLICAS:
            for arm in run.ARMS:
                for r in timing['replicas'][replica]['arms'][arm]:
                    c = r['command']
                    if c[0].endswith('garden-model-mutate'):
                        self.assertEqual(c[-1],'32')
                        continue
                    patches = dict(run.previous.REVIEW_PATCHES if r['artifact'].startswith('review/') else run.previous.TRAIN_PATCHES)
                    self.assertIn(f'/arms/{arm}/',c[1])
                    if c[0].endswith('garden-persistence-trial'):
                        self.assertIn(c[4][2:],patches.values())
                        self.assertEqual(c[-2:],[str(run.pilot.START),str(run.pilot.END)])
                    else:
                        self.assertIn(int(c[c.index('--disturbance-seed')+1]),[int(p,16) for p in patches.values()])
                        self.assertEqual(c[c.index('--ticks')+1],str(run.pilot.STOP))

    def test_frozen_control_rejection_happens_before_reanalysis(self):
        baseline = {'replicas':{'r1':{'arms':{'renewal':{'search':{'frozen':True}}}}}}
        result = {'rule':run.RULE,'arms':{'narrow':{'search':{'changed':True}},'wide':{}}}
        with patch.object(run.mixed,'check_results') as checked,self.assertRaises(RuntimeError):
            run.check_replica(Path('/not-used'),result,baseline,'r1')
        checked.assert_not_called()

    def test_contact_sheet_checks_pixels_and_row_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'frame.rgb565').write_bytes(bytes(run.pilot.gallery.FRAME_BYTES))
            rows = [[{'id':'fixed','framebuffer':'frame.rgb565'}]]
            saved = run.pilot.gallery.contact_sheet(root,rows)
            run.check_sheet(root,rows,saved)
            bad = copy.deepcopy(saved)
            bad['rows'] = [['wrong']]
            with self.assertRaises(RuntimeError): run.check_sheet(root,rows,bad)
            (root/'contact-sheet.png').write_bytes(b'changed')
            with self.assertRaises(RuntimeError): run.check_sheet(root,rows,saved)

    def test_existing_output_and_incomplete_manifest_rejected_without_native_calls(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(run.pilot,'run_json') as native:
            root = Path(directory)
            with self.assertRaises(RuntimeError): run.collect(root/'input',root)
            run.experiment.write_json(root/'manifest.json',{'rule':run.RULE,'status':'failed'})
            with self.assertRaises(RuntimeError): run.verify(root)
            native.assert_not_called()


class SearchTests(unittest.TestCase):
    def test_concurrent_coverage_selection_and_capture_disabled_repeats(self):
        def evaluate(root,folder,name,model,seeds,timings,*,objective=None,patches=None):
            return {k:copy.deepcopy(fixtures.world('steady' if name == 'g1-c2' or
                (name == 'g1-c1' and seed in run.previous.TRAIN) else 'sterile'))
                for k,_,seed,_ in run.mixed.conditions(seeds,patches)}
        def mutate(command,target):
            before = Path(command[1]).read_text()
            after = f'{Path(command[2]).stem}:{command[3]}'
            Path(command[2]).write_text(after)
            return {'before':before,'after':after,'rng_before':command[3],'rng_after':command[3]+1},0
        def search_replica(root,replica):
            result = {}
            for arm in run.ARMS:
                s,sub = run.study(replica,arm),root/replica/arm
                (sub/'input').mkdir(parents=True)
                (sub/'input/initial.tgm').write_text('original')
                captured = []
                a = run.mixed.search(sub,sub/'search',[],lambda g,c:captured.append((g,c)),study=s,objective=run.OBJECTIVE)
                b = run.mixed.search(sub,sub/'repeat',[],study=s,objective=run.OBJECTIVE)
                self.assertEqual(a,b)
                winner = 'g1-c1' if arm == 'narrow' else 'g1-c2'
                self.assertEqual(a['champions'],['initial',winner,winner,winner])
                self.assertEqual(captured,list(enumerate(a['champions'])))
                run.mixed.check_search(a,study=s,objective=run.OBJECTIVE)
                result[arm] = a
            for a,b in zip(result['narrow']['candidates'][:4],result['wide']['candidates'][:4]):
                self.assertEqual(a['model_sha256'],b['model_sha256'])
                self.assertEqual(a['worlds'],run.subset(b['worlds'],run.previous.TRAIN))
            return result
        with tempfile.TemporaryDirectory() as directory,patch.object(run.mixed,'evaluate',side_effect=evaluate), \
             patch.object(run.pilot,'run_json',side_effect=mutate),patch.object(run.pilot,'model_crc',side_effect=lambda p:p.read_text()):
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(search_replica,Path(directory),r) for r in run.REPLICAS]
                results = [f.result() for f in futures]
        self.assertNotEqual(results[0]['wide']['candidates'][1]['model_sha256'],results[1]['wide']['candidates'][1]['model_sha256'])

    def test_common_prefix_validates_subset_identity_and_native_bytes(self):
        narrow = [{'id':n,'parent':None,'mutation':None,'model_crc32':n,'model_sha256':n,
                   'worlds':{k:{'value':1} for k,*_ in run.mixed.conditions(run.previous.TRAIN,dict(run.previous.TRAIN_PATCHES))}}
                  for n in run.names()[:4]]
        wide = [{**c,'worlds':{**c['worlds'],**{k:{'value':2} for k,*_ in run.mixed.conditions(run.ADDED,dict(run.previous.TRAIN_PATCHES))}}}
                for c in copy.deepcopy(narrow)]
        arms = {'narrow':{'search':{'candidates':narrow},'review':[{'worlds':{}}]},
                'wide':{'search':{'candidates':wide},'review':[{'worlds':{}}]}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for arm in run.ARMS:
                folder = root/'arms'/arm/'search'
                folder.mkdir(parents=True)
                for c in narrow:
                    for suffix in ('tgm',*[f'{k}.json' for k in c['worlds']]):
                        (folder/f"{c['id']}.{suffix}").write_bytes(b'same')
            run.check_prefix(root,arms)
            for failure in ('metadata','world','native','review'):
                bad = copy.deepcopy(arms)
                if failure == 'metadata': bad['wide']['search']['candidates'][1]['model_sha256'] = 'changed'
                elif failure == 'world': next(iter(bad['wide']['search']['candidates'][0]['worlds'].values()))['value'] = 9
                elif failure == 'native': (root/'arms/wide/search/initial.tgm').write_bytes(b'changed')
                else: bad['wide']['review'][0]['worlds'] = {'changed':True}
                with self.subTest(failure=failure),self.assertRaises(RuntimeError): run.check_prefix(root,bad)
                (root/'arms/wide/search/initial.tgm').write_bytes(b'same')


if __name__ == '__main__':
    unittest.main()
