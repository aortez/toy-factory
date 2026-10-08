#!/usr/bin/env python3
"""Recurring schedule contracts, spatial event audits and frozen-panel integrity."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_patch_recurring as screen
import garden_landing_order as historical
from test_garden_landing_tools import run

BUILD = None
D = screen.DAY
SAVED = screen.ROOT / 'benchmarks/garden-seasons/landing-patch-recurring-results.json.gz'


class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        saved, models, _, _ = historical.load_inputs()
        cls.model_bytes = models[saved['models']['single-s6d697834-live']['model']]

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='patch-recurring-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.model = self.root / 'model.tgl'
        self.model.write_bytes(self.model_bytes)

    def args(self):
        return ['placement-replay', self.model, 'rainfed-crowded', '0x940cfdc4', '--climate', 'seasonal',
                '--ticks', 3 * D, '--ledger', '--shoot-reserve', 'on', '--seed-placement', 'spacing',
                '--seed-cursor-after', D, '--patch-sweep', 'on']

    def native(self, args, valid=True):
        output = run([BUILD / 'toy-factory-garden-landing', *args], valid=valid)
        return json.loads(output) if output else None

    def test_pre_onset_world_ledgers_and_pixels_are_unchanged(self):
        control_frame, frame = self.root / 'old.raw', self.root / 'new.raw'
        plain = self.native(self.args() + ['--framebuffer', control_frame])
        treatment = self.native(self.args() + ['--patch-recurring', 'on', '--framebuffer', frame])
        expected = copy.deepcopy(plain)
        expected.update(kind='landing-patch-recurring-replay', run_hash=screen.tagged(plain['run_hash']),
                        patch_recurring_probe=dict(screen.SCHEDULE, events=[]))
        self.assertEqual(treatment, expected)
        self.assertEqual(frame.read_bytes(), control_frame.read_bytes())
        self.assertEqual(screen.check_events(treatment), set())
        expected['framebuffer_crc32'] = None
        self.assertEqual(self.native(self.args() + ['--patch-recurring', 'on']), expected)

    def test_invalid_flags_leave_outputs_uncreated(self):
        frame = self.root / 'never.raw'
        args = self.args() + ['--framebuffer', frame]
        for extra in (['--patch-recurring', 'off'], ['--patch-recurring', 'on', '--patch-recurring', 'on'],
                      ['--patch-recurring', 'on', '--seed-wait-after', 2 * D],
                      ['--patch-recurring', 'on', '--turnover-at', 2 * D, '--turnover-lineage', 1],
                      ['--patch-recurring', 'on', '--seed-replace-after', D]):
            self.native(args + extra, valid=False)
            self.assertFalse(frame.exists())
        for flag in ('--patch-sweep', '--seed-cursor-after', '--ledger'):
            stripped = list(args)
            start = stripped.index(flag)
            del stripped[start:start + (1 if flag == '--ledger' else 2)]
            self.native(stripped + ['--patch-recurring', 'on'], valid=False)
            self.assertFalse(frame.exists())
        late = list(args)
        late[late.index('--seed-cursor-after') + 1] = 396 * D
        self.native(late + ['--patch-recurring', 'on'], valid=False)
        self.assertFalse(frame.exists())

    def test_existing_frame_is_not_overwritten(self):
        frame = self.root / 'existing.raw'
        frame.write_bytes(b'keep this')
        self.native(self.args() + ['--patch-recurring', 'on', '--framebuffer', frame], valid=False)
        self.assertEqual(frame.read_bytes(), b'keep this')


def event_fixture():
    tick = 396 * D
    plants = [dict(id=1, parent=0, birth_tick=0, death_tick=tick, column=4, environmental_death=True),
              dict(id=2, parent=1, birth_tick=tick - 15, death_tick=tick, column=7, environmental_death=True),
              dict(id=3, parent=0, birth_tick=0, death_tick=tick, column=6, environmental_death=False),
              dict(id=4, parent=0, birth_tick=0, death_tick=None, column=8, environmental_death=False)]
    victims = [dict(lineage=p['id'], age=(tick - p['birth_tick']) // 15 + (p['parent'] != 0),
                    nodes=4, energy=200, water=256) for p in plants[:2]]
    event = dict(tick=tick, first=4, last=7, victims=victims, before_world_hash='11111111',
                 after_world_hash='22222222', before_run_hash='33333333', after_run_hash='44444444')
    return dict(tick=tick, lineages=plants, patch_sweep_probe=dict(events=[]),
                patch_recurring_probe=dict(screen.SCHEDULE, events=[event]))


class OfflineTests(unittest.TestCase):
    def test_exact_winter_schedule_and_boundaries(self):
        self.assertEqual(screen.schedule(396 * D - 1), [])
        self.assertEqual(screen.schedule(396 * D), [dict(tick=396 * D, first=4, last=7)])
        self.assertEqual(screen.schedule(screen.STOP), [dict(tick=d * D, first=c, last=c + 3)
                         for d, c in ((396, 4), (428, 8), (460, 12), (492, 16))])
        self.assertTrue(all(e['tick'] // D % 16 == 12 for e in screen.schedule(screen.STOP)))

    def test_all_ages_in_patch_but_not_same_step_natural_deaths(self):
        self.assertEqual(screen.check_events(event_fixture()), {1, 2})

    def test_missing_duplicate_wrong_age_or_unreceipted_victims_fail(self):
        for defect in ('missing', 'duplicate', 'age', 'flag', 'extra', 'same_hash', 'bad_hash', 'event'):
            value = event_fixture()
            event = value['patch_recurring_probe']['events'][0]
            if defect == 'missing':
                event['victims'].pop()
            elif defect == 'duplicate':
                event['victims'].append(dict(event['victims'][0]))
            elif defect == 'age':
                event['victims'][1]['age'] -= 1
            elif defect == 'flag':
                value['lineages'][1]['environmental_death'] = False
            elif defect == 'extra':
                value['lineages'][3].update(death_tick=value['tick'], environmental_death=True)
            elif defect == 'same_hash':
                event['after_world_hash'] = event['before_world_hash']
            elif defect == 'bad_hash':
                event['after_run_hash'] = 'garbage'
            else:
                value['patch_recurring_probe']['events'] = []
            with self.subTest(defect=defect), self.assertRaises(RuntimeError):
                screen.check_events(value)

    def test_empty_events_are_retained_without_mutation(self):
        value = event_fixture()
        event = value['patch_recurring_probe']['events'][0]
        for p in value['lineages'][:2]:
            p.update(column=20, death_tick=None, environmental_death=False)
        event['victims'] = []
        event['after_world_hash'] = event['before_world_hash']
        event['after_run_hash'] = event['before_run_hash']
        self.assertEqual(screen.check_events(value), set())

    def test_mortality_partition_and_unchanged_decision(self):
        source = screen.original()
        results = {k: copy.deepcopy(source['runs']['endpoint']['cursor'][k]['result']) for k in screen.PANEL}
        outcomes = {k: screen.analyze(r) for k, r in results.items()}
        choice = screen.decision({a: outcomes for a in screen.ARMS})
        self.assertEqual(choice['arms']['recurring']['renewing'], [])
        self.assertFalse(choice['recurring_renewal_advantage'])
        key = next(iter(screen.PANEL))
        before = outcomes[key]
        self.assertEqual(before['mortality']['imposed']['ids'], [])
        selected = before['mortality']['natural']['ids'][0]
        next(p for p in results[key]['lineages'] if p['id'] == selected)['environmental_death'] = True
        after = screen.analyze(results[key])
        self.assertEqual(after['mortality']['imposed']['ids'], [selected])
        self.assertNotIn(selected, after['mortality']['natural']['ids'])
        self.assertEqual(after['renewal'], before['renewal'])
        self.assertEqual(after['viability'], before['viability'])

    @unittest.skipUnless(SAVED.exists(), 'panel not collected yet')
    def test_saved_capture_is_verifiable_offline(self):
        with gzip.open(SAVED, 'rt') as stream:
            value = json.load(stream)
        with patch('subprocess.run', side_effect=AssertionError('offline only')), \
             patch('subprocess.Popen', side_effect=AssertionError('offline only')):
            screen.check_capture(value)

    @unittest.skipUnless(SAVED.exists(), 'panel not collected yet')
    def test_changed_schedule_partial_panel_and_promoted_results_fail(self):
        with gzip.open(SAVED, 'rt') as stream:
            value = json.load(stream)
        key = next(iter(screen.PANEL))
        broken = copy.deepcopy(value)
        broken['runs']['endpoint']['recurring'][key]['result']['patch_recurring_probe']['period_days'] = 16
        with self.assertRaisesRegex(RuntimeError, 'schedule differs'):
            screen.check_capture(broken)
        broken = copy.deepcopy(value)
        del broken['runs']['plain']['stopped'][key]
        with self.assertRaisesRegex(RuntimeError, 'missing panel member'):
            screen.check_capture(broken)
        broken = copy.deepcopy(value)
        broken['decision']['recurring_renewal_advantage'] = not broken['decision']['recurring_renewal_advantage']
        with self.assertRaisesRegex(RuntimeError, 'derived outcomes differ'):
            screen.check_capture(broken)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path, required=True)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *rest])
