#!/usr/bin/env python3
"""Contracts and offline evidence checks for the fixed offspring follow-up."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_recurring_followup as screen
import garden_landing_order as historical
from test_garden_landing_tools import run

BUILD = None
D = screen.DAY
SAVED = screen.ROOT / 'benchmarks/garden-seasons/landing-recurring-followup-results.json.gz'


class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        saved, models, _, _ = historical.load_inputs()
        cls.model_bytes = models[saved['models']['single-s6d697834-live']['model']]

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='recurring-followup-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.model = self.root / 'model.tgl'
        self.model.write_bytes(self.model_bytes)

    def args(self):
        return ['placement-replay', self.model, 'rainfed-crowded', '0x940cfdc4', '--climate', 'seasonal',
                '--ticks', 3 * D, '--ledger', '--shoot-reserve', 'on', '--seed-placement', 'spacing',
                '--seed-cursor-after', D, '--patch-sweep', 'on', '--patch-recurring', 'on']

    def native(self, args, valid=True):
        output = run([BUILD / 'toy-factory-garden-landing', *args], valid=valid)
        return json.loads(output) if output else None

    def test_pre_event_state_pixels_and_existing_identity_preserved(self):
        old_frame, frame = self.root / 'old.raw', self.root / 'new.raw'
        old = self.native(self.args() + ['--framebuffer', old_frame])
        actual = self.native(self.args() + ['--patch-recurring-followup', 'on', '--framebuffer', frame])
        expected = copy.deepcopy(old)
        expected.update(kind='landing-patch-recurring-followup-replay', run_hash=screen.tagged(old['run_hash']))
        expected[screen.PROBE] = dict(screen.SCHEDULE, events=[])
        self.assertEqual(actual, expected)
        self.assertEqual(frame.read_bytes(), old_frame.read_bytes())
        self.assertEqual(screen.check_event(actual), set())
        expected['framebuffer_crc32'] = None
        self.assertEqual(self.native(self.args() + ['--patch-recurring-followup', 'on']), expected)

    def test_invalid_options_and_bounds_do_not_create_outputs(self):
        frame = self.root / 'never.raw'
        base = self.args() + ['--framebuffer', frame]
        for extra in (['--patch-recurring-followup', 'off'],
                      ['--patch-recurring-followup', 'on', '--patch-recurring-followup', 'on'],
                      ['--patch-recurring-followup', 'on', '--seed-wait-after', 2 * D],
                      ['--patch-recurring-followup', 'on', '--turnover-at', 2 * D, '--turnover-lineage', 1]):
            self.native(base + extra, valid=False)
            self.assertFalse(frame.exists())
        for flag in ('--patch-recurring', '--patch-sweep', '--seed-cursor-after', '--ledger'):
            args = list(base)
            i = args.index(flag)
            del args[i:i + (1 if flag == '--ledger' else 2)]
            self.native(args + ['--patch-recurring-followup', 'on'], valid=False)
            self.assertFalse(frame.exists())
        for tick, extra in ((512 * D + 1, []), (544 * D + 1, ['--patch-recurring-followup', 'on'])):
            args = list(base)
            args[args.index('--ticks') + 1] = tick
            self.native(args + extra, valid=False)
            self.assertFalse(frame.exists())

    def test_existing_frame_is_preserved(self):
        frame = self.root / 'keep.raw'
        frame.write_bytes(b'keep this')
        self.native(self.args() + ['--patch-recurring-followup', 'on', '--framebuffer', frame], valid=False)
        self.assertEqual(frame.read_bytes(), b'keep this')


def fixture():
    tick = screen.EVENT
    plants = [dict(id=1, parent=0, birth_tick=0, death_tick=tick, column=20, environmental_death=True),
              dict(id=2, parent=1, birth_tick=tick, death_tick=tick, column=23, environmental_death=True),
              dict(id=3, parent=0, birth_tick=0, death_tick=tick, column=22, environmental_death=False),
              dict(id=4, parent=0, birth_tick=0, death_tick=None, column=24, environmental_death=False)]
    victims = [dict(lineage=p['id'], age=(tick - p['birth_tick']) // 15 + (p['parent'] != 0),
                    nodes=4, energy=200, water=256) for p in plants[:2]]
    event = dict(tick=tick, first=20, last=23, victims=victims, before_world_hash='11111111',
                 after_world_hash='22222222', before_run_hash='33333333', after_run_hash='44444444')
    return dict(tick=tick, lineages=plants, patch_sweep_probe=dict(events=[]),
                patch_recurring_probe=dict(events=[]), **{screen.PROBE: dict(screen.SCHEDULE, events=[event])})


class OfflineTests(unittest.TestCase):
    def test_frozen_six_links_and_eleven_survivors(self):
        cohorts = {k: screen.cohorts(k) for k in screen.PANEL}
        self.assertEqual(sum(len(c['focal_links']) for c in cohorts.values()), 6)
        self.assertEqual(sum(len(c['late_survivors']) for c in cohorts.values()), 11)
        self.assertTrue(all(p['birth_tick'] + 32 * D <= screen.STOP
                            for c in cohorts.values() for p in c['late_survivors']))
        for k in screen.PANEL:
            args = screen.arguments(k, 'endpoint')
            self.assertEqual(args[args.index('--ticks') + 1], str(544 * D))
            self.assertNotIn('--framebuffer', screen.arguments(k, 'plain'))

    def test_schedule_complete_patch_and_same_tick_order(self):
        self.assertEqual(screen.EVENT // D % 16, 12)
        self.assertEqual(screen.check_event(fixture()), {1, 2})
        value = fixture()
        value['tick'] -= 1
        with self.assertRaisesRegex(RuntimeError, 'missing/extra'):
            screen.check_event(value)
        value[screen.PROBE]['events'] = []
        for p in value['lineages']:
            p.update(death_tick=None, environmental_death=False)
        self.assertEqual(screen.check_event(value), set())

    def test_wrong_victims_ages_metadata_and_unreceipted_deaths_rejected(self):
        for defect in ('missing', 'duplicate', 'age', 'flag', 'unreceipted', 'hash', 'same_hash', 'time', 'band'):
            value = fixture()
            event = value[screen.PROBE]['events'][0]
            if defect == 'missing':
                event['victims'].pop()
            elif defect == 'duplicate':
                event['victims'].append(dict(event['victims'][0]))
            elif defect == 'age':
                event['victims'][1]['age'] = 0
            elif defect == 'flag':
                value['lineages'][1]['environmental_death'] = False
            elif defect == 'unreceipted':
                value['lineages'][3].update(death_tick=screen.EVENT, environmental_death=True)
            elif defect == 'hash':
                event['before_run_hash'] = 'garbage'
            elif defect == 'same_hash':
                event['after_world_hash'] = event['before_world_hash']
            elif defect == 'time':
                event['tick'] += 15
            else:
                event['first'] = 19
            with self.subTest(defect=defect), self.assertRaises(RuntimeError):
                screen.check_event(value)

    def test_empty_hit_records_identity_without_deaths(self):
        value = fixture()
        for p in value['lineages'][:2]:
            p.update(column=19, death_tick=None, environmental_death=False)
        event = value[screen.PROBE]['events'][0]
        event['victims'] = []
        event['after_world_hash'] = event['before_world_hash']
        event['after_run_hash'] = event['before_run_hash']
        self.assertEqual(screen.check_event(value), set())

    def test_exact_deadline_death_fails_but_later_death_preserves_establishment(self):
        plant = dict(id=1, parent=2, birth_tick=500 * D, death_tick=532 * D, environmental_death=True)
        self.assertEqual(screen.child_outcome(plant)['age_32'], 'failed')
        self.assertEqual(screen.child_outcome(plant)['death_cause'], 'imposed')
        plant['death_tick'] += 15
        outcome = screen.child_outcome(plant)
        self.assertEqual(outcome['age_32'], 'confirmed')
        self.assertFalse(outcome['alive_at_end'])
        plant.update(birth_tick=530 * D, death_tick=None)
        self.assertEqual(screen.child_outcome(plant)['age_32'], 'censored')
        plant['death_tick'] = 540 * D
        self.assertEqual(screen.child_outcome(plant)['age_32'], 'recent-dead')

    def test_changed_frozen_cohort_rejected(self):
        key = next(iter(screen.PANEL))
        bad = copy.deepcopy(screen.reference(key))
        next(p for p in bad['result']['lineages'] if p['id'] == 55)['death_tick'] = screen.BASE
        with patch.object(screen, 'reference', return_value=bad), self.assertRaisesRegex(RuntimeError, 'cohort differs'):
            screen.cohorts(key)

    @unittest.skipUnless(SAVED.exists(), 'panel not collected yet')
    def test_published_capture_verifies_without_running_native_code(self):
        with gzip.open(SAVED, 'rt') as stream:
            value = json.load(stream)
        with patch('subprocess.run', side_effect=AssertionError('offline only')), \
             patch('subprocess.Popen', side_effect=AssertionError('offline only')):
            screen.check_capture(value)

    @unittest.skipUnless(SAVED.exists(), 'panel not collected yet')
    def test_tampered_results_cohorts_history_and_closed_score_fail(self):
        with gzip.open(SAVED, 'rt') as stream:
            source = json.load(stream)
        key = next(iter(screen.PANEL))
        for defect in ('summary', 'cohort', 'missing', 'score', 'history', 'event'):
            value = copy.deepcopy(source)
            if defect == 'summary':
                value['summary']['focal']['confirmed'] += 1
            elif defect == 'cohort':
                value['cohorts'][key]['focal_links'] = []
            elif defect == 'missing':
                del value['runs']['plain'][key]
            elif defect == 'score':
                value['closed_decision']['recurring_renewal_advantage'] = True
            elif defect == 'history':
                value['runs']['endpoint'][key]['result']['lineages'][0]['column'] += 1
            else:
                value['runs']['endpoint'][key]['result'][screen.PROBE]['events'] = []
            with self.subTest(defect=defect), self.assertRaises(RuntimeError):
                screen.check_capture(value)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path, required=True)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *rest])
