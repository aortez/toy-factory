#!/usr/bin/env python3
"""Bounded confirmation contracts and saved evidence checks; never launch a world."""

import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_patch_confirmation as confirm

RESULT = confirm.ROOT / 'benchmarks/garden-seasons/landing-patch-confirmation-results.json.gz'


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch('subprocess.run', side_effect=AssertionError('no native')):
            cls.saved = confirm.prior()

    def test_predeclared_six_pairs_and_twenty_six_calls(self):
        self.assertEqual(len(confirm.panel()), 6)
        calls = confirm.calls()
        self.assertEqual(len(calls), 26)
        self.assertEqual(len(set(calls)), 26)
        self.assertEqual(calls[:2], [('anchor', 'control'), ('anchor', 'treatment')])
        self.assertEqual([c['scenario'] for c in confirm.panel().values()], list(confirm.LAYOUTS) * 3)
        self.assertEqual({c['seed'] for c in confirm.panel().values()}, set(confirm.SEEDS))
        self.assertNotIn('f7ee4528', confirm.SEEDS)
        self.assertEqual(self.saved['panel'][confirm.REFERENCE]['arm'], 'wide-cap')

    def test_only_seed_layout_and_output_names_change(self):
        for phase in confirm.PHASES:
            for key, case in confirm.panel().items():
                actual = confirm.arguments(key, phase)
                original = confirm.sweep.arguments(confirm.REFERENCE, phase)
                self.assertEqual(actual[2:4], [case['scenario'], '0x' + case['seed']])
                actual[2:4] = original[2:4]
                for flag in ('--framebuffer', *(f'--{k}-trace' for k in confirm.sweep.KINDS)):
                    if flag in actual:
                        i = actual.index(flag)
                        actual[i + 1] = original[original.index(flag) + 1]
                self.assertEqual(actual, original)
                self.assertNotIn('--root-allocation-focal', actual)
                self.assertNotIn('--seed-order', actual)
                self.assertNotIn('--turnover-at', actual)
                self.assertEqual('--patch-sweep' in actual, phase != 'control')
                self.assertEqual('--stand-trace' in actual, phase != 'plain')
        for p in ('control', 'treatment'):
            self.assertEqual(confirm.arguments(p, 'anchor'), self.saved['runs'][p][confirm.REFERENCE]['args'])

    def test_each_layout_must_improve_and_losses_cannot_be_averaged_away(self):
        def item(pairs=0, living=1):
            return dict(summary=dict(qualifying_pairs=[[1, 2]] * pairs),
                        result=dict(living=living, lineages=[dict(birth_tick=0, death_tick=None)] if living else []))
        runs = {p: {k: item(int(p == 'treatment')) for k in confirm.panel()} for p in ('control', 'treatment')}
        self.assertTrue(confirm.verdict(runs)['confirmed'])
        for k, case in confirm.panel().items():
            if case['scenario'] == 'rainfed':
                runs['treatment'][k] = item(0)
        self.assertFalse(confirm.verdict(runs)['confirmed'])
        for k in confirm.panel():
            runs['treatment'][k] = item(1)
        key = next(iter(confirm.panel()))
        runs['control'][key] = item(2)
        self.assertFalse(confirm.verdict(runs)['confirmed'])
        self.assertEqual(confirm.verdict(runs)['pair_regressions'], [key])
        runs['control'][key] = item(0, 0)
        runs['treatment'][key] = item(0, 0)
        self.assertFalse(confirm.verdict(runs)['confirmed'])
        self.assertEqual(confirm.verdict(runs)['empty_treatments'], [key])

    def test_minimum_groups_same_tick_and_includes_onset_deaths(self):
        t = confirm.BASE
        result = dict(living=1, lineages=[dict(birth_tick=0, death_tick=t + 15),
                                        dict(birth_tick=t + 15, death_tick=None)])
        self.assertEqual(confirm.minimum_living(result), 1)
        result['lineages'][1]['birth_tick'] += 15
        self.assertEqual(confirm.minimum_living(result), 0)
        result['lineages'][0]['death_tick'] = t
        self.assertEqual(confirm.minimum_living(result), 0)
        result['living'] = 2
        with self.assertRaisesRegex(RuntimeError, 'chronology'):
            confirm.minimum_living(result)

    def test_real_pilot_results_validate_without_named_selector(self):
        key = confirm.REFERENCE
        case = dict(seed='f7ee4528', scenario='rainfed-crowded')
        with patch.object(confirm, 'panel', return_value={key: case}), \
             patch('subprocess.run', side_effect=AssertionError('no native')):
            for p in ('control', 'treatment'):
                confirm.check_result(self.saved['runs'][p][key]['result'], key, p)
            for change in ('founder', 'climate', 'model', 'event', 'extra-probe'):
                result = copy.deepcopy(self.saved['runs']['treatment'][key]['result'])
                if change == 'founder':
                    result['lineages'][0]['column'] += 1
                elif change == 'climate':
                    result['climate']['year'] += 1
                elif change == 'model':
                    result['model']['payload_crc32'] = '00000000'
                elif change == 'event':
                    result['patch_sweep_probe']['events'][0]['tick'] += 15
                else:
                    result['root_allocation_probe'] = dict(version=1)
                with self.subTest(change=change), self.assertRaises(RuntimeError):
                    confirm.check_result(result, key, 'treatment')

    def test_anchor_receipts_require_old_results_traces_and_accounting(self):
        for phase in ('control', 'treatment'):
            run = copy.deepcopy(self.saved['runs'][phase][confirm.REFERENCE])
            before, after = run['directory'], 'anchor/' + phase
            run['directory'] = after
            for item in (run['frame'], *run['traces'].values()):
                item['path'] = after + item['path'][len(before):]
            confirm.check_run(run, phase, 'anchor')
            run['traces']['stand']['sha256'] = '0' * 64
            with self.assertRaises(RuntimeError):
                confirm.check_run(run, phase, 'anchor')

    def test_existing_or_nested_outputs_rejected_before_inputs_or_native(self):
        for kind in ('directory', 'output', 'dangling', 'nested'):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                out, output = root / 'bundle', root / 'out.json.gz'
                if kind == 'directory':
                    out.mkdir()
                elif kind == 'output':
                    output.touch()
                elif kind == 'dangling':
                    out.symlink_to(root / 'absent', target_is_directory=True)
                else:
                    output = out / 'capture.json.gz'
                with patch.object(confirm, 'prior', side_effect=AssertionError('do not load inputs')), \
                     patch.object(confirm.sweep, 'native', side_effect=AssertionError('no native')), \
                     self.assertRaisesRegex(RuntimeError, 'fresh separate outputs'):
                    confirm.collect(out, output, root / 'origin', 2)


@unittest.skipUnless(RESULT.exists(), 'confirmation capture not collected yet')
class CapturedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(RESULT, 'rt') as stream:
            cls.value = json.load(stream)

    def test_complete_capture_without_native_processes(self):
        with patch('subprocess.run', side_effect=AssertionError('no native')), \
             patch('subprocess.Popen', side_effect=AssertionError('no native')):
            confirm.check_capture(self.value)

    def test_rehashed_missing_case_changed_rule_or_gallery_rejected(self):
        key = next(iter(confirm.panel()))
        for change in ('omit', 'seed', 'event', 'recipe', 'gallery', 'runtime'):
            value = copy.deepcopy(self.value)
            if change == 'omit':
                del value['runs']['plain'][key]
            elif change == 'seed':
                value['panel'][key]['seed'] = 'f7ee4528'
            elif change == 'event':
                value['runs']['treatment'][key]['result']['patch_sweep_probe']['events'][0]['first'] += 1
            elif change == 'recipe':
                value['runs']['control'][key]['args'].append('--root-allocation-focal')
            elif change == 'gallery':
                value['gallery']['rows'].reverse()
            else:
                value['source_sha256']['src/garden_world.c'] = '0' * 64
            value['receipt_sha256'] = confirm.sweep.fingerprint({k: v for k, v in value.items() if k != 'receipt_sha256'})
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                confirm.check_capture(value)


if __name__ == '__main__':
    unittest.main()
