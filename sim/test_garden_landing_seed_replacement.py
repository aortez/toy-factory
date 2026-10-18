#!/usr/bin/env python3
"""Replacement identity, new seed fates, offline accounting and CLI boundaries."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_seed_replacement as screen
from test_garden_landing_tools import run

BUILD = None
RESULT = screen.ROOT / 'benchmarks/garden-seasons/landing-seed-replacement-results.json.gz'


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved = screen.inputs()
        cls.key = sorted(cls.saved['panel'])[4]

    def test_fixed_twenty_calls_and_identical_prior_event_settings(self):
        self.assertEqual(len(screen.PHASES) * len(self.saved['panel']), 20)
        for key in self.saved['panel']:
            self.assertEqual(screen.arguments(key, 'control')[:-2], self.saved['runs']['treatment'][key]['args'])
            self.assertEqual(screen.arguments(key, 'treatment'), screen.arguments(key, 'repeat'))
            plain = screen.arguments(key, 'plain')
            self.assertIn('--ledger', plain)
            self.assertIn('--second-turnover-at', plain)
            self.assertIn('--seed-replace-after', plain)
            self.assertNotIn('--replacement-trace', plain)
            self.assertNotIn('--stand-trace', plain)

    def test_archived_results_and_zero_new_first_recruit_children(self):
        for key, world in self.saved['panel'].items():
            result = self.saved['runs']['treatment'][key]['result']
            screen.check_result(result, key, 'control')
            summary = screen.summary(result, world)
            self.assertEqual(len(summary['births']), 1)
            self.assertEqual(summary['established'], {'1': 1, '16': 1, '32': 0})
            self.assertTrue(all(not p['children'] for p in summary['cohorts']['first_recruit'].values()))

    def test_replaced_is_a_separate_fate_with_exact_old_identity(self):
        value = copy.deepcopy(self.saved['runs']['treatment'][self.key]['result'])
        seed = next(s for s in value['seeds'] if s['parent'] == 31 and s['outcome'] == 'expired'
                    and s['birth_tick'] < screen.BASE < s['end_tick'])
        seed.update(outcome='replaced', end_tick=screen.BASE + 60)
        _, seeds = screen.index_result(value)
        self.assertEqual(seeds[seed['parent'], seed['birth_tick']]['outcome'], 'replaced')
        for changes in (dict(end_tick=screen.BASE), dict(child_id=1),
                        dict(end_tick=seed['birth_tick'] + 8192 * screen.STEP), dict(column=28)):
            bad = copy.deepcopy(value)
            next(s for s in bad['seeds'] if s['outcome'] == 'replaced').update(changes)
            with self.subTest(changes=changes), self.assertRaises(RuntimeError):
                screen.index_result(bad)

    def test_survival_boundary_and_censoring(self):
        p = dict(birth_tick=screen.BASE, death_tick=None)
        self.assertEqual(screen.survival(p, 32), 'confirmed')
        self.assertEqual(screen.survival(dict(p, birth_tick=screen.BASE + 15), 32), 'censored')
        self.assertEqual(screen.survival(dict(p, death_tick=screen.BASE + screen.DAY), 1), 'failed')

    def test_fresh_output_rejected_before_native(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(screen, 'native', side_effect=AssertionError('no native')):
            with self.assertRaisesRegex(RuntimeError, 'fresh output'):
                screen.collect(Path(tmp), Path('/missing'), 2)

    def test_first_effect_and_complete_common_prefix(self):
        run = dict(traces={k: dict(path=k) for k in screen.capture.KINDS}, result={})
        treatment = dict(run, analysis=dict(replacements=[dict(tick=screen.BASE + 60)]))

        def rows(path, kind, start, stop, result):
            for tick in (screen.BASE, screen.BASE + 15, screen.BASE + 60, screen.STOP):
                value = 1 if result and tick >= screen.BASE + 60 else 0
                yield dict(tick=tick), f'{tick}:{value}\n'.encode()

        treatment['result'] = dict(treatment=True)
        with patch.object(screen.followup, 'trace_rows', side_effect=rows):
            found = screen.first_effects(Path('/unused'), run, treatment)
            self.assertTrue(all(v['first_tick'] == screen.BASE + 60 for v in found.values()))
            treatment['analysis']['replacements'][0]['tick'] += 60
            with self.assertRaisesRegex(RuntimeError, 'first observed effect'):
                screen.first_effects(Path('/unused'), run, treatment)

    def test_lost_establishment_is_not_hidden_by_a_first_recruit_gain(self):
        baseline = dict(summary=screen.summary(self.saved['runs']['treatment'][self.key]['result'],
                                               self.saved['panel'][self.key]), replacements=[], resources={})
        for p in self.saved['runs']['treatment'][self.key]['result']['lineages']:
            if p['birth_tick'] <= screen.BASE and (p['death_tick'] is None or p['death_tick'] > screen.BASE):
                baseline['resources'][str(p['id'])] = dict(shortfalls=0)
        treatment = copy.deepcopy(baseline)
        child = treatment['summary']['births'][0]
        child['parent'] = 31
        treatment['summary']['cohorts']['first_recruit']['31']['children'] = [
            dict(life=child, survival={'1': 'confirmed', '16': 'confirmed', '32': 'censored'})]
        comparison = screen.compare(baseline, treatment, self.key)
        self.assertEqual(comparison['first_recruit_gains'], [31])
        self.assertEqual(comparison['established_16_delta'], 0)
        self.assertTrue(comparison['established_parent_losses'])
        self.assertFalse(screen.verdict({self.key: comparison})['no_establishment_loss_elsewhere'])

    def test_offline_accounting_on_original_w5_when_raw_bundle_available(self):
        root = screen.ROOT / 'artifacts/garden-landing-second-opening-v1'
        if not root.exists():
            self.skipTest('original raw bundle not available')
        trial = self.saved['runs']['treatment'][self.key]
        paths = {k: root / m['path'] for k, m in trial['traces'].items()}
        paths['replacement'] = Path('/not-read')
        empty = [dict(tick=t, replacements=[]) for t in range(screen.STEP, screen.STOP + screen.STEP, screen.STEP)]
        with patch.object(screen, 'replacement_rows', return_value=iter(empty)), \
             patch('subprocess.run', side_effect=AssertionError('no process')), \
             patch('subprocess.Popen', side_effect=AssertionError('no process')):
            result = screen.analyze_paths(paths, trial['result'], self.key, 'control')
        self.assertEqual(result['replacements'], [])
        self.assertEqual(result['resources']['31']['maintenance'], 2048)
        self.assertEqual(result['resources']['31']['shortfalls'], 0)


@unittest.skipUnless(RESULT.exists(), 'replacement capture not retained yet')
class CapturedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(RESULT, 'rt') as stream:
            cls.value = json.load(stream)
        cls.key = sorted(cls.value['panel'])[4]

    def test_offline_complete_capture_and_no_first_recruit_gain(self):
        with patch('subprocess.run', side_effect=AssertionError('no process')), \
             patch('subprocess.Popen', side_effect=AssertionError('no process')):
            screen.verify_capture(self.value)
        self.assertEqual(self.value['verdict'], dict(first_recruit_gain=False,
            no_establishment_loss_elsewhere=True, no_extra_matched_natural_death=True,
            no_extra_matched_shortfall=True))
        for comparison in self.value['comparisons'].values():
            self.assertEqual(comparison['established_16_delta'], 0)

    def test_four_replacements_do_not_mean_four_extra_purchases(self):
        calls = self.value['runs']['treatment']
        self.assertEqual(sum(len(r['analysis']['replacements']) for r in calls.values()), 4)
        for phase in ('control', 'treatment'):
            runs = self.value['runs'][phase].values()
            self.assertEqual(sum(s['birth_tick'] > screen.BASE for r in runs for s in r['result']['seeds']), 42)
        for comparison in self.value['comparisons'].values():
            for pair in comparison['displaced']:
                self.assertTrue(pair['matched_prefix_seed'])
                self.assertEqual(pair['old']['outcome'], 'replaced')
                self.assertEqual(pair['control']['outcome'], 'expired')

    def test_replacement_cannot_be_relabelled_as_expiration(self):
        value = copy.deepcopy(self.value['runs']['treatment'][self.key]['result'])
        next(s for s in value['seeds'] if s['outcome'] == 'replaced')['outcome'] = 'expired'
        with self.assertRaises(RuntimeError):
            screen.index_result(value)

    def test_omitted_unsuccessful_parent_is_rejected_after_rehash(self):
        value = copy.deepcopy(self.value)
        del value['runs']['treatment'][self.key]['analysis']['summary']['cohorts']['first_recruit']['31']
        value['receipt_sha256'] = screen.fingerprint({k: v for k, v in value.items() if k != 'receipt_sha256'})
        with self.assertRaises(RuntimeError):
            screen.verify_capture(value)

    def test_retimed_effect_is_rejected_after_rehash(self):
        value = copy.deepcopy(self.value)
        for effect in value['first_effects'][self.key].values():
            effect['first_tick'] += 60
        value['receipt_sha256'] = screen.fingerprint({k: v for k, v in value.items() if k != 'receipt_sha256'})
        with self.assertRaisesRegex(RuntimeError, 'first-effect receipt'):
            screen.verify_capture(value)


@unittest.skipUnless(BUILD is not None, 'native executable not selected')
class NativeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='landing-seed-replacement-test-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.cli = BUILD / 'toy-factory-garden-landing'
        self.model = self.root / 'model.tgl'
        run([self.cli, 'reference', self.model, '--mode', 'history'])

    def args(self, stop=240):
        return [self.cli, 'placement-replay', self.model, 'rainfed-crowded', '0x940cfdc4',
                '--ticks', stop, '--climate', 'seasonal', '--ledger', '--shoot-reserve', 'on',
                '--seed-placement', 'spacing']

    def test_reject_invalid_or_ambiguous_replacement_options(self):
        for value in ('0', '-1', '61', '300', '1228801', ''):
            run([*self.args(), '--seed-replace-after', value], valid=False)
        run([*self.args(), '--seed-replace-after', 60, '--seed-replace-after', 60], valid=False)
        missing = self.args()
        missing.remove('--ledger')
        run([*missing, '--seed-replace-after', 60], valid=False)
        run([*missing, '--replacement-trace', self.root / 'bad.jsonl'], valid=False)
        off = self.args()
        off[-1] = 'off'
        run([*off, '--seed-replace-after', 60], valid=False)

    def test_pre_onset_world_equal_but_run_identity_explicit(self):
        control = json.loads(run(self.args()))
        enabled = json.loads(run([*self.args(), '--seed-replace-after', 240]))
        self.assertEqual(control['world_hash'], enabled['world_hash'])
        self.assertEqual(control['seeds'], enabled['seeds'])
        self.assertEqual(control['lineages'], enabled['lineages'])
        self.assertEqual(enabled['run_hash'], screen.tagged(control['run_hash'], 240))
        self.assertEqual(enabled['seed_replacement_probe'], dict(version=1, after=240))

    def test_replacement_observer_is_neutral_and_does_not_overwrite(self):
        path = self.root / 'replacement.jsonl'
        args = [*self.args(3840), '--seed-replace-after', 60]
        plain = json.loads(run(args))
        observed = json.loads(run([*args, '--replacement-trace', path]))
        self.assertEqual(plain, observed)
        data = path.read_bytes()
        rows = [json.loads(line) for line in data.splitlines()]
        self.assertEqual(rows[0], dict(schema='landing-seed-replacement-trace-v1', after=60))
        self.assertEqual([r['tick'] for r in rows[1:-1]], list(range(15, 3841, 15)))
        self.assertEqual(rows[-1], dict(complete=True, tick=3840))
        run([*args, '--replacement-trace', path], valid=False)
        self.assertEqual(path.read_bytes(), data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path)
    options, rest = parser.parse_known_args()
    BUILD = options.build.resolve() if options.build else None
    NativeTests.__unittest_skip__ = BUILD is None
    unittest.main(argv=[__file__, *rest])
