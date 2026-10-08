#!/usr/bin/env python3
"""Waiting policy CLI, full visit-order oracle and frozen evidence regression tests."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_seed_wait as screen
import garden_landing_bank_access as bank
import garden_landing_order as historical
from test_garden_landing_tools import run

BUILD = None
D = screen.DAY
SAVED = screen.ROOT / 'benchmarks/garden-seasons/landing-seed-wait-results.json.gz'


class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        saved, models, _, _ = historical.load_inputs()
        cls.model_bytes = models[saved['models']['single-s6d697834-live']['model']]

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='seed-wait-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.model = self.root / 'model.tgl'
        self.model.write_bytes(self.model_bytes)

    def args(self, ticks, enabled=True):
        return ['placement-replay', self.model, 'rainfed-crowded', '0x940cfdc4', '--climate', 'seasonal',
                '--ticks', ticks, '--ledger', '--shoot-reserve', 'on', '--seed-placement', 'spacing',
                '--seed-cursor-after', D, *(['--seed-wait-after', 3 * D] if enabled else [])]

    def native(self, args, valid=True):
        raw = run([BUILD / 'toy-factory-garden-landing', *args], valid=valid)
        return json.loads(raw) if raw else None

    def test_onset_is_exactly_neutral_except_declared_identity(self):
        plain = self.native(self.args(3 * D, False))
        wait = self.native(self.args(3 * D))
        screen.check_wait_probe(wait, plain, 3 * D)
        expected = copy.deepcopy(plain)
        expected['seed_wait_probe'] = wait['seed_wait_probe']
        expected['run_hash'] = screen.tagged(plain['run_hash'], wait['seed_wait_probe']['entries'], 3 * D)
        self.assertEqual(wait, expected)

    def test_order_oracle_paid_ledger_and_observer_neutrality(self):
        path = self.root / 'stand.jsonl'
        frame = self.root / 'observed.raw'
        first, last = 3 * D + 15, 8 * D
        observed = self.native(self.args(last) + ['--stand-trace', path, '--stand-start', first,
                               '--stand-stop', last, '--stand-dawn', '--framebuffer', frame])
        other_frame = self.root / 'plain.raw'
        plain = self.native(self.args(last) + ['--framebuffer', other_frame])
        self.assertEqual(observed, plain)
        self.assertEqual(frame.read_bytes(), other_frame.read_bytes())
        screen.check_wait_probe(observed, {}, 3 * D)
        with path.open() as stream:
            rows = [json.loads(line) for line in stream][1:-1]
        self.assertEqual([r['tick'] for r in rows], list(range(first, last + 15, 15)))
        lives = {p['id']: p for p in observed['lineages']}
        visits = []
        for row in rows:
            tick, ids = row['tick'], row['plant_order']
            if tick % 60 == 0:
                def key(i):
                    purchases = [s['birth_tick'] for s in observed['seeds']
                                 if s['parent'] == i and s['birth_tick'] < tick]
                    return (purchases[-1] if purchases else lives[i]['birth_tick']), i
                ids = sorted(ids, key=key)
            self.assertEqual([v['id'] for v in row['reproduction']], ids)
            visits.append([tick, [[v[k] for k in bank.FIELDS] for v in row['reproduction']]])
        audit = bank.analyze_visits(visits, observed, first, last)
        self.assertEqual(audit['bank']['purchases'], sum(first <= s['birth_tick'] <= last for s in observed['seeds']))
        repeat_frame = self.root / 'repeat.raw'
        self.assertEqual(self.native(self.args(last) + ['--framebuffer', repeat_frame]), observed)
        self.assertEqual(repeat_frame.read_bytes(), frame.read_bytes())

    def test_invalid_combinations_do_not_create_files(self):
        path = self.root / 'never-created.raw'
        args = self.args(60, False) + ['--framebuffer', path]
        for value in (0, 61, -1, D, 2 * D + 1, 1966081, '1x'):
            self.native(args + ['--seed-wait-after', value], valid=False)
            self.assertFalse(path.exists())
        for extra in (['--seed-wait-after', 4 * D], ['--seed-order', 'rotating', '--seed-order-after', 60],
                      ['--seed-replace-after', 60]):
            self.native(args + ['--seed-wait-after', 3 * D] + extra, valid=False)
            self.assertFalse(path.exists())
        no_cursor = args[:args.index('--seed-cursor-after')] + args[args.index('--seed-cursor-after') + 2:]
        self.native(no_cursor + ['--seed-wait-after', 3 * D], valid=False)
        self.assertFalse(path.exists())


class OfflineTests(unittest.TestCase):
    def test_shared_success_criteria_do_not_reward_purchases_alone(self):
        old = screen.original()['outcomes']['cursor']
        result = screen.decision({'cursor': old, 'wait': old})
        self.assertFalse(result['waiting_renewal_advantage'])
        self.assertEqual(result['arms']['wait']['renewing'], [])
        self.assertEqual(len(result['arms']['wait']['viable']), 6)

    def test_waiting_timestamp_is_latest_purchase_not_age_or_slot(self):
        result = dict(lineages=[dict(id=2, birth_tick=15, death_tick=None),
                               dict(id=9, birth_tick=45, death_tick=None)],
                      seeds=[dict(parent=2, birth_tick=60), dict(parent=2, birth_tick=120)])
        screen.check_entries([[2, 120], [9, 45]], result, 150, 2)
        for entries in ([[2, 60], [9, 45]], [[2, 120], [9, 0]], [[9, 45], [2, 120]], [[2, 120]]):
            with self.assertRaises(RuntimeError):
                screen.check_entries(entries, result, 150, 2)

    @unittest.skipUnless(SAVED.exists(), 'panel capture not collected yet')
    def test_frozen_capture_verifies_without_processes(self):
        with gzip.open(SAVED, 'rt') as stream:
            value = json.load(stream)
        with patch('subprocess.run', side_effect=AssertionError('offline only')), \
             patch('subprocess.Popen', side_effect=AssertionError('offline only')):
            screen.check_capture(value)

    @unittest.skipUnless(SAVED.exists(), 'panel capture not collected yet')
    def test_tampered_state_and_partial_panel_are_rejected(self):
        with gzip.open(SAVED, 'rt') as stream:
            value = json.load(stream)
        key = next(iter(screen.PANEL))
        broken = copy.deepcopy(value)
        broken['runs']['endpoint']['wait'][key]['result']['seed_wait_probe']['entries'][0][1] += 15
        with self.assertRaisesRegex(RuntimeError, 'purchase clock differs'):
            screen.check_capture(broken)
        broken = copy.deepcopy(value)
        del broken['runs']['repeat']['cursor'][key]
        with self.assertRaisesRegex(RuntimeError, 'missing panel member'):
            screen.check_capture(broken)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path, required=True)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *rest])
