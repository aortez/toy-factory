#!/usr/bin/env python3
"""Portable adult-death diagnosis, interval accounting and corruption checks."""

import copy
import gzip
import json
import unittest
from unittest.mock import patch

import garden_landing_cursor_energy as audit


class EnergyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(audit.ROOT / 'benchmarks/garden-seasons/landing-cursor-energy-results.json.gz', 'rt') as stream:
            cls.saved = json.load(stream)

    def test_portable_reanalysis_without_native_execution(self):
        with patch('subprocess.run', side_effect=AssertionError('no native runs')), \
             patch('subprocess.Popen', side_effect=AssertionError('no native runs')):
            audit.check_value(self.saved)

    def test_same_horizon_explains_shortfall(self):
        result = self.saved['analysis']
        a, b = (result['critical_budget'][arm]['energy'] for arm in audit.ARMS)
        self.assertEqual((a['initial'], b['initial']), (252, 252))
        self.assertEqual((a['income'], b['income']), (172, 142))
        self.assertEqual((a['upkeep'], b['upkeep']), (424, 394))
        self.assertEqual(sum(p['energy']['unpaid'] for p in result['shortfalls']), 30)
        self.assertTrue(all(p['water']['unpaid'] == 0 for p in result['shortfalls']))
        self.assertEqual(result['fixed_next_income_tick'], result['common_end'] + audit.STEP)
        self.assertEqual(result['refill_steps'], 5)
        self.assertEqual(result['daily'][-1]['stop'], result['common_end'])
        self.assertFalse(result['daily'][-1]['complete_day'])

    def test_reject_missing_or_reordered_samples(self):
        value = audit.load_input()
        rows = self.saved['histories']['cursor']['rows']
        for bad in (rows[:-1], rows[1:], [rows[1], rows[0], *rows[2:]]):
            with self.subTest(length=len(bad)), self.assertRaises(RuntimeError):
                audit.history(bad, audit.focal_life(value, 'cursor'),
                              audit.selected(value, 'cursor')['audit']['plants']['37'])

    def test_reject_changed_transfers_and_summary(self):
        for fault in ('income', 'discard', 'summary', 'identity'):
            bad = copy.deepcopy(self.saved)
            if fault == 'income':
                bad['histories']['cursor']['rows'][1][1][1][0][1] += 1
            elif fault == 'discard':
                bad['histories']['cursor']['rows'][-1][1][1][1][-1] -= 1
            elif fault == 'summary':
                bad['analysis']['critical_budget']['cursor']['energy']['income'] += 1
            else:
                bad['input_sha256'] = '0' * 64
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                audit.check_value(bad)

    def test_budget_intervals_exclude_start_include_end(self):
        samples = {}
        for t in (15, 30, 45):
            transfer = audit.window.adults.budget()
            for resource in transfer.values():
                resource.update(initial=t // 15 - 1, income=1, final=t // 15)
            samples[t] = dict(transfer=transfer)
        self.assertEqual(audit.budget_between(samples, 15, 45)['energy']['income'], 2)
        self.assertEqual(audit.budget_between(samples, 15, 45)['energy']['initial'], 1)
        for bounds in ((0, 60), (15, 15), (16, 45)):
            with self.subTest(bounds=bounds), self.assertRaises(RuntimeError):
                audit.budget_between(samples, *bounds)


if __name__ == '__main__':
    unittest.main()
