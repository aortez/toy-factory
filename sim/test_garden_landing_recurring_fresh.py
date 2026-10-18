#!/usr/bin/env python3
"""Fresh-panel contracts, prospective metric boundaries and evidence integrity."""

import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_recurring_fresh as screen
import garden_landing_order as historical
from test_garden_landing_tools import run
from test_garden_landing_competitive_renewal import fixture as old_fixture
from test_garden_landing_patch_recurring import event_fixture

BUILD = None
D = screen.DAY
SAVED = screen.ROOT / 'benchmarks/garden-seasons/landing-recurring-fresh-results.json.gz'


def fixture(births=()):
    result = old_fixture(births)
    result['tick'] = screen.STOP
    return result


class NativeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='recurring-fresh-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        saved, models, _, _ = historical.load_inputs()
        self.model = self.root / 'model.tgl'
        self.model.write_bytes(models[saved['models']['single-s6d697834-live']['model']])

    def args(self):
        return ['placement-replay', self.model, 'rainfed-crowded', '0x940cfdc4', '--climate', 'seasonal',
                '--ticks', 3 * D, '--ledger', '--shoot-reserve', 'on', '--seed-placement', 'spacing',
                '--seed-cursor-after', D, '--patch-sweep', 'on']

    def native(self, args, valid=True):
        output = run([BUILD / 'toy-factory-garden-landing', *args], valid=valid)
        return json.loads(output) if output else None

    def test_both_pre_onset_arms_preserve_old_state_and_pixels(self):
        frame = self.root / 'base.raw'
        old = self.native(self.args() + ['--framebuffer', frame])
        for arm in screen.ARMS:
            path = self.root / (arm + '.raw')
            result = self.native(self.args() + ['--patch-renewal', arm, '--framebuffer', path])
            expected = copy.deepcopy(old)
            expected.update(kind='landing-patch-renewal-replay', run_hash=screen.tagged(old['run_hash'], arm == 'recurring'))
            expected[screen.PROBE] = dict(screen.SCHEDULE, enabled=arm == 'recurring', events=[])
            self.assertEqual(result, expected)
            self.assertEqual(frame.read_bytes(), path.read_bytes())
            self.assertEqual(screen.check_events(result, arm), set())
            expected['framebuffer_crc32'] = None
            self.assertEqual(self.native(self.args() + ['--patch-renewal', arm]), expected)

    def test_invalid_combinations_and_old_horizons_preserved(self):
        frame = self.root / 'never.raw'
        args = self.args() + ['--framebuffer', frame]
        for extra in (['--patch-renewal', 'on'], ['--patch-renewal', 'stopped', '--patch-renewal', 'recurring'],
                      ['--patch-renewal', 'recurring', '--patch-recurring', 'on'],
                      ['--patch-renewal', 'stopped', '--patch-recurring-followup', 'on'],
                      ['--patch-renewal', 'recurring', '--seed-wait-after', 2 * D],
                      ['--patch-renewal', 'recurring', '--turnover-at', 2 * D, '--turnover-lineage', 1]):
            self.native(args + extra, valid=False)
            self.assertFalse(frame.exists())
        for flag in ('--patch-sweep', '--seed-cursor-after', '--ledger'):
            invalid = list(args)
            i = invalid.index(flag)
            del invalid[i:i + (1 if flag == '--ledger' else 2)]
            self.native(invalid + ['--patch-renewal', 'recurring'], valid=False)
            self.assertFalse(frame.exists())
        for tick, extra in ((512 * D + 1, []),
                            (544 * D + 1, ['--patch-recurring', 'on', '--patch-recurring-followup', 'on']),
                            (608 * D + 1, ['--patch-renewal', 'stopped'])):
            invalid = list(args)
            invalid[invalid.index('--ticks') + 1] = tick
            self.native(invalid + extra, valid=False)
            self.assertFalse(frame.exists())

    def test_existing_frame_is_not_overwritten(self):
        frame = self.root / 'keep.raw'
        frame.write_bytes(b'keep')
        self.native(self.args() + ['--patch-renewal', 'recurring', '--framebuffer', frame], valid=False)
        self.assertEqual(frame.read_bytes(), b'keep')


class OfflineTests(unittest.TestCase):
    def test_deterministic_panel_and_exact_66_calls(self):
        self.assertEqual(tuple(hashlib.sha256(f'toy-factory:recurring-renewal-v1:seed:{i}'.encode()).hexdigest()[:8]
                               for i in (1, 2, 3)), screen.SEEDS)
        calls = [(p, a, k) for p in screen.PHASES for a in screen.arms(p) for k in screen.PANEL]
        self.assertEqual(len(calls), 66)
        with patch('subprocess.run', side_effect=AssertionError('offline only')):
            for phase, arm, key in calls:
                args = screen.arguments(key, arm, phase)
                self.assertEqual(int(args[args.index('--ticks') + 1]), screen.horizon(phase))
                self.assertEqual('--framebuffer' in args, phase != 'plain')
                self.assertEqual('--patch-renewal' in args, phase != 'legacy')
                self.assertFalse(any('trace' in a for a in args))

    def test_cycle_wrap_and_explicit_disabled_schedule(self):
        events = screen.schedule(screen.STOP, True)
        self.assertEqual([e['tick'] // D for e in events], [396, 428, 460, 492, 524, 556, 588])
        self.assertEqual([e['first'] for e in events], [4, 8, 12, 16, 20, 24, 0])
        self.assertEqual(screen.schedule(screen.STOP, False), [])
        value = event_fixture()
        value[screen.PROBE] = value.pop('patch_recurring_probe')
        value[screen.PROBE].update(screen.SCHEDULE, enabled=True)
        self.assertEqual(screen.check_events(value, 'recurring'), {1, 2})
        with self.assertRaises(RuntimeError):
            screen.check_events(value, 'stopped')
        value[screen.PROBE]['events'][0]['victims'].pop()
        with self.assertRaises(RuntimeError):
            screen.check_events(value, 'recurring')

    def test_new_windows_require_observed_parent_child_survival(self):
        value = screen.analyze(fixture(((1, 400, None), (5, 470, None), (6, 540, None))))
        self.assertTrue(value['viability']['passes'])
        self.assertTrue(value['renewal']['passes'])
        self.assertEqual([w['births'] for w in value['renewal']['windows']], [[5], [6], [7]])
        self.assertEqual(value['renewal']['pairs'], [[5, 6], [6, 7]])
        self.assertEqual(value['renewal']['deepest_chain'], 3)
        self.assertFalse(screen.analyze(fixture(((1, 400, None), (1, 470, None), (1, 540, None))))['renewal']['passes'])
        self.assertFalse(screen.analyze(fixture())['renewal']['passes'])

    def test_exact_window_death_and_late_birth_boundaries(self):
        value = screen.analyze(fixture(((1, 384, None), (1, 448, None), (1, 512, None),
                                       (1, 576, 608), (1, 576.00390625, None))))
        self.assertEqual([w['births'] for w in value['renewal']['windows']], [[6], [7], [8]])
        self.assertEqual(value['renewal']['primary']['ages']['32']['failed'], [8])
        self.assertEqual(value['renewal']['late']['ages']['32']['censored'], [9])

    def test_adult_death_and_posthumous_children_are_not_vetoed(self):
        result = fixture(((1, 400, 440), (5, 450, None), (6, 540, None)))
        result['seeds'][1]['birth_tick'] = 439 * D
        value = screen.analyze(result)
        self.assertTrue(value['renewal']['passes'])
        self.assertEqual(value['mortality']['natural']['ids'], [5])
        self.assertEqual(value['mortality']['natural']['by_age_32'], [])

    def test_living_family_gap_is_distinct_from_extinction(self):
        result = fixture(((4, 550, None),))
        result['seeds'][0]['birth_tick'] = 530 * D
        result['lineages'][3]['death_tick'] = 540 * D
        value = screen.analyze(result)['diversity']['family']
        self.assertEqual(value['absence_intervals']['4'], [[540 * D, 550 * D - 1]])
        self.assertEqual(value['no_plants_or_seeds']['4'], [])
        self.assertNotIn(4, value['continuous_retained'])
        result = fixture()
        result['lineages'][3]['death_tick'] = 540 * D
        self.assertEqual(screen.analyze(result)['diversity']['family']['no_plants_or_seeds']['4'], [[540 * D, screen.STOP]])

    def test_broad_signal_needs_coverage_viability_and_advantage(self):
        base = screen.analyze(fixture())
        outcomes = {a: {k: copy.deepcopy(base) for k in screen.PANEL} for a in screen.ARMS}
        keys = list(screen.PANEL)
        for k in keys[:4]:
            outcomes['recurring'][k]['renewal']['passes'] = True
        self.assertFalse(screen.decision(outcomes)['recurring_renewal_advantage'])
        outcomes['recurring'][keys[4]]['renewal']['passes'] = True
        self.assertTrue(screen.decision(outcomes)['recurring_renewal_advantage'])
        outcomes['recurring'][keys[4]]['diversity']['family']['continuous_retained'].remove(1)
        self.assertTrue(screen.decision(outcomes)['diversity_tradeoff'])
        outcomes['recurring'][keys[5]]['viability']['passes'] = False
        self.assertFalse(screen.decision(outcomes)['recurring_renewal_advantage'])

    @unittest.skipUnless(SAVED.exists(), 'panel not collected yet')
    def test_published_capture_verifies_offline(self):
        with gzip.open(SAVED, 'rt') as stream:
            value = json.load(stream)
        with patch('subprocess.run', side_effect=AssertionError('offline only')), \
             patch('subprocess.Popen', side_effect=AssertionError('offline only')):
            screen.check_capture(value)

    @unittest.skipUnless(SAVED.exists(), 'panel not collected yet')
    def test_tampered_scope_history_and_outcomes_fail(self):
        with gzip.open(SAVED, 'rt') as stream:
            source = json.load(stream)
        key = next(iter(screen.PANEL))
        for defect in ('score', 'closed', 'missing', 'seed', 'event', 'history'):
            value = copy.deepcopy(source)
            if defect == 'score':
                value['decision']['recurring_renewal_advantage'] = not value['decision']['recurring_renewal_advantage']
            elif defect == 'closed':
                value['closed_decision']['recurring_renewal_advantage'] = True
            elif defect == 'missing':
                del value['runs']['plain']['stopped'][key]
            elif defect == 'seed':
                value['panel'][key]['seed'] = '00000001'
            elif defect == 'event':
                value['runs']['endpoint']['recurring'][key]['result'][screen.PROBE]['events'].pop()
            else:
                value['runs']['endpoint']['stopped'][key]['result']['lineages'][0]['column'] += 1
            with self.subTest(defect=defect), self.assertRaises(RuntimeError):
                screen.check_capture(value)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path, required=True)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *rest])
