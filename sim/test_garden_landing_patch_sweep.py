#!/usr/bin/env python3
"""Fixed sweep selection, cohort boundaries, archived accounting and CLI exclusions."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_patch_sweep as screen
from test_garden_landing_tools import run

BUILD = None
RESULT = screen.ROOT / 'benchmarks/garden-seasons/landing-patch-sweep-results.json.gz'
INTERRUPTION = screen.ROOT / 'benchmarks/garden-seasons/landing-patch-sweep-interruption.json.gz'


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved, cls.baseline = screen.inputs()
        cls.key = sorted(cls.saved['panel'])[0]

    def test_fixed_schedule_and_twenty_five_calls(self):
        self.assertEqual(len(screen.PHASES) * len(self.saved['panel']), 25)
        self.assertEqual(len(screen.schedule()), 15)
        self.assertEqual(screen.schedule()[0], dict(tick=192 * screen.DAY, first=0, last=3))
        self.assertEqual(screen.schedule()[-1], dict(tick=304 * screen.DAY, first=0, last=3))
        self.assertEqual(screen.schedule(screen.BASE - 1), [])
        self.assertEqual([e['first'] for e in screen.schedule()], list(range(0, 28, 4)) * 2 + [0])
        for key in self.saved['panel']:
            self.assertEqual(screen.arguments(key, 'baseline'), self.baseline['runs']['extension'][key]['args'])
            control = screen.arguments(key, 'control')
            self.assertEqual(screen.arguments(key, 'treatment'), control + ['--patch-sweep', 'on'])
            self.assertEqual(screen.arguments(key, 'treatment'), screen.arguments(key, 'repeat'))
            for phase in screen.PHASES:
                args = screen.arguments(key, phase)
                for flag in ('--turnover-at', '--second-turnover-at', '--seed-replace-after'):
                    self.assertNotIn(flag, args)
            plain = screen.arguments(key, 'plain')
            self.assertFalse(any(a.endswith('-trace') for a in plain))
            self.assertNotIn('--stand-dawn', plain)
            self.assertIn('--ledger', plain)

    def test_survival_separates_imposed_natural_and_censored(self):
        p = dict(birth_tick=screen.BASE, death_tick=None, environmental_death=False)
        self.assertEqual(screen.survival(p, 16), 'confirmed')
        p['death_tick'] = screen.BASE + 16 * screen.DAY
        self.assertEqual(screen.survival(p, 16), 'natural-death')
        self.assertEqual(screen.survival(dict(p, environmental_death=True), 16), 'imposed-death')
        p.update(birth_tick=screen.STOP - screen.DAY, death_tick=None)
        self.assertEqual(screen.survival(p, 16), 'censored')
        self.assertEqual(screen.survival(p, 1), 'confirmed')

    def test_true_post_onset_chain_not_inherited_generation(self):
        # A pre-onset parent cannot qualify. A dead parent may qualify if it
        # survived sixteen days; a posthumous child is not discarded.
        lives = {i: dict(id=i, parent=i - 1, birth_tick=t * screen.DAY, death_tick=None,
                         environmental_death=False, species=0, generation=40 + i)
                 for i, t in enumerate((180, 193, 215, 238, 319), 1)}
        lives[2].update(death_tick=210 * screen.DAY, environmental_death=True)
        result = dict(living=4, plant_slots=5, nodes=20, seed_bank=0)
        result.update(lineages=list(lives.values()), seeds=[])
        with patch.object(screen, 'index_records', return_value=(lives, {})):
            found = screen.summary(result)
        self.assertEqual(found['qualifying_pairs'], [[2, 3], [3, 4]])
        self.assertEqual(found['deepest_born_chain'], 4)
        self.assertEqual(found['deepest_16_day_chain'], 3)
        self.assertEqual(found['survival']['16'], {'confirmed': 3, 'censored': 1})

    def test_event_complete_patch_includes_seedling_and_rejects_omission(self):
        lives = [dict(id=i, parent=1 if i == 2 else 0, birth_tick=b, death_tick=d, environmental_death=d is not None, column=c)
                 for i, b, d, c in ((1, 0, screen.BASE, 0), (2, screen.BASE, screen.BASE, 3), (3, 0, None, 4))]
        victims = [dict(lineage=p['id'], age=(screen.BASE - p['birth_tick']) // screen.STEP + (p['parent'] != 0),
                        nodes=4, energy=64, water=24) for p in lives[:2]]
        event = dict(screen.schedule()[0], victims=victims, before_world_hash='00000001',
                     after_world_hash='00000002', before_run_hash='00000003', after_run_hash='00000004')
        result = dict(tick=screen.BASE, lineages=lives, patch_sweep_probe=dict(version=1, first_day=192,
                      period_days=8, width=4, scheduled_events=15, events=[event]))
        self.assertEqual(screen.events(result), {screen.BASE: event})
        for edit in ('omit', 'retime', 'outside', 'wrong-age', 'unreceipted'):
            bad = copy.deepcopy(result)
            e = bad['patch_sweep_probe']['events'][0]
            if edit == 'omit':
                e['victims'].pop()
            elif edit == 'retime':
                e['tick'] += screen.STEP
            elif edit == 'outside':
                bad['lineages'][2]['column'] = 2
            elif edit == 'wrong-age':
                e['victims'][1]['age'] = 0
            else:
                bad['lineages'][2].update(death_tick=screen.BASE - screen.STEP, environmental_death=True)
            with self.subTest(edit=edit), self.assertRaises(RuntimeError):
                screen.events(bad)
        empty = copy.deepcopy(result)
        empty['lineages'] = []
        e = empty['patch_sweep_probe']['events'][0]
        e.update(victims=[], after_world_hash=e['before_world_hash'], after_run_hash=e['before_run_hash'])
        self.assertEqual(len(screen.events(empty)), 1)

    def test_improvement_and_no_empty_endpoint_both_required(self):
        keys = sorted(self.saved['panel'])
        runs = {p: {k: dict(summary=dict(qualifying_pairs=[], final=dict(living=1))) for k in keys}
                for p in ('control', 'treatment')}
        for key in keys[:3]:
            runs['treatment'][key]['summary']['qualifying_pairs'] = [[2, 3]]
        self.assertTrue(screen.verdict(runs)['useful'])
        runs['treatment'][keys[-1]]['summary']['final']['living'] = 0
        self.assertFalse(screen.verdict(runs)['useful'])

    def test_fresh_output_before_native(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(screen, 'native', side_effect=AssertionError('no native')):
            with self.assertRaisesRegex(RuntimeError, 'fresh output'):
                screen.collect(Path(tmp), Path('/missing'), 2)

    def test_archived_unforced_traces_without_new_simulation(self):
        root = screen.ROOT / 'artifacts/garden-landing-followup-v1'
        if not root.exists():
            self.skipTest('archived raw follow-up bundle unavailable')
        run = self.baseline['runs']['extension'][self.key]
        paths = {k: root / m['path'] for k, m in run['traces'].items() if k in screen.KINDS}
        with patch.object(screen, 'BASE', 256 * screen.DAY), patch.object(screen, 'STOP', 288 * screen.DAY), \
             patch('subprocess.run', side_effect=AssertionError('no process')), \
             patch('subprocess.Popen', side_effect=AssertionError('no process')):
            value = screen.account(paths, run['result'])
            for edit in ('exposure', 'budget', 'census'):
                bad = copy.deepcopy(value)
                total = next(iter(bad['resources'].values()))
                if edit == 'exposure':
                    total['maintenance'] += 1
                elif edit == 'budget':
                    total['energy']['income'] += 1
                else:
                    bad['daily'].pop()
                with self.subTest(edit=edit), self.assertRaises(RuntimeError):
                    screen.check_accounting(bad, run['result'])
        self.assertEqual(len(value['daily']), 33)
        self.assertTrue(all(r['boundary'] for r in value['receipts'].values()))


@unittest.skipUnless(RESULT.exists(), 'sweep results not retained yet')
class CapturedTests(unittest.TestCase):
    def test_portable_capture_without_process(self):
        with gzip.open(RESULT, 'rt') as stream:
            value = json.load(stream)
        with patch('subprocess.run', side_effect=AssertionError('no process')), \
             patch('subprocess.Popen', side_effect=AssertionError('no process')):
            screen.check_capture(value)


@unittest.skipUnless(INTERRUPTION.exists(), 'interruption checkpoint unavailable')
class InterruptedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(INTERRUPTION, 'rt') as stream:
            cls.value = json.load(stream)

    def test_preserved_partial_batch_is_not_a_completed_experiment(self):
        v = self.value
        self.assertEqual(v['rule'], 'garden-landing-patch-sweep-interrupted-v1')
        self.assertEqual(v['status'], 'stopped-after-auditor-error')
        self.assertEqual((v['planned_native_calls'], v['completed_native_calls'], v['offline_native_calls']), (25, 12, 0))
        self.assertEqual(v['receipt_sha256'], screen.fingerprint({k: x for k, x in v.items() if k != 'receipt_sha256'}))
        self.assertEqual(v['analysis_sources'], {p: screen.digest(screen.ROOT / p) for p in screen.SOURCES})
        self.assertNotIn('verdict', v)
        keys = sorted(screen.inputs()[0]['panel'])
        self.assertEqual({p: sorted(r) for p, r in v['runs'].items()},
                         dict(baseline=keys, control=keys, treatment=keys[:2]))
        self.assertEqual(v['remaining'], [dict(phase=p, key=k) for p in ('treatment', 'repeat', 'plain')
                                         for k in keys if k not in v['runs'].get(p, {})])
        self.assertFalse(v['correction']['simulation_changes'])
        with patch('subprocess.run', side_effect=AssertionError('no process')), \
             patch('subprocess.Popen', side_effect=AssertionError('no process')):
            for phase, runs in v['runs'].items():
                for key, run in runs.items():
                    self.assertEqual(run['args'], screen.arguments(key, phase))
                    screen.check_result(run['result'], key, phase)
                    if phase == 'baseline':
                        screen.late.same_run(run, screen.inputs()[1]['runs']['extension'][key], screen.followup.KINDS)
                    else:
                        screen.check_accounting(run['accounting'], run['result'])
                        self.assertEqual(run['summary'], screen.summary(run['result']))
                    if phase == 'treatment':
                        self.assertEqual(run['accounting']['receipts'], v['runs']['control'][key]['accounting']['receipts'])

    def test_real_victim_age_requires_the_birth_step_offset(self):
        result = copy.deepcopy(next(iter(self.value['runs']['treatment'].values()))['result'])
        screen.events(result)
        result['patch_sweep_probe']['events'][0]['victims'][0]['age'] -= 1
        with self.assertRaisesRegex(RuntimeError, 'imposed-death receipt'):
            screen.events(result)


@unittest.skipUnless(BUILD is not None, 'native executable not selected')
class NativeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='landing-patch-sweep-test-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.cli = BUILD / 'toy-factory-garden-landing'
        self.model = self.root / 'model.tgl'
        run([self.cli, 'reference', self.model, '--mode', 'history'])

    def args(self):
        return [self.cli, 'placement-replay', self.model, 'rainfed-crowded', '0x940cfdc4',
                '--ticks', 240, '--climate', 'seasonal', '--ledger', '--shoot-reserve', 'on',
                '--seed-placement', 'spacing']

    def test_ambiguous_or_incompatible_options_rejected(self):
        for extra in (['--patch-sweep', v] for v in ('off', '', '1')):
            run([*self.args(), *extra], valid=False)
        args = [*self.args(), '--patch-sweep', 'on']
        for extra in (['--patch-sweep', 'on'], ['--turnover-at', 120, '--turnover-lineage', 1],
                      ['--second-turnover-at', 120, '--second-turnover-lineage', 1], ['--seed-replace-after', 60]):
            run([*args, *extra], valid=False)
        args.remove('--ledger')
        run(args, valid=False)
        args = self.args()
        args[1] = 'replay'
        run([*args, '--patch-sweep', 'on'], valid=False)

    def test_pre_event_parity_and_explicit_identity(self):
        plain = json.loads(run(self.args()))
        sweep = json.loads(run([*self.args(), '--patch-sweep', 'on']))
        self.assertEqual(sweep.pop('placement_run_hash'), plain['run_hash'])
        self.assertEqual(sweep.pop('patch_sweep_probe'), dict(version=1, first_day=192, period_days=8,
                                                           width=4, scheduled_events=15, events=[]))
        self.assertEqual(sweep['run_hash'], screen.tagged(plain['run_hash']))
        self.assertEqual(sweep['kind'], 'landing-patch-sweep-replay')
        sweep.update(run_hash=plain['run_hash'], kind=plain['kind'])
        self.assertEqual(sweep, plain)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path)
    options, rest = parser.parse_known_args()
    BUILD = options.build.resolve() if options.build else None
    NativeTests.__unittest_skip__ = BUILD is None
    unittest.main(argv=[__file__, *rest])
