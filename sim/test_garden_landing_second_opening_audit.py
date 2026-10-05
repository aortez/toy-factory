#!/usr/bin/env python3
"""Offline interval accounting, backward agreement and adversarial evidence."""

import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_second_opening_audit as audit

window = audit.window
RESULT = audit.ROOT / 'benchmarks/garden-seasons/landing-second-opening-results.json.gz'


class ContractTests(unittest.TestCase):
    def test_parameterized_accounting_matches_archived_first_window(self):
        prior = window.prior
        saved = prior.inputs()
        key = sorted(saved['panel'])[0]
        with gzip.open(audit.ROOT / 'benchmarks/garden-seasons/landing-disturbance-results.json.gz', 'rt') as stream:
            archived = json.load(stream)
        evidence = archived['evidence'][key]['treatment']
        actual = window.analyze_world(saved['runs']['treatment'][key],
                                      saved['panel'][key] | dict(first_recruits=[]), evidence,
                                      prior.BASE, prior.STOP, 'turnover_probe')
        expected = archived['analysis'][key]['treatment']
        for field in ('plants', 'seed_checks', 'changes', 'disturbance', 'access', 'residence',
                      'natural_deaths', 'incumbent_natural_deaths', 'final'):
            self.assertEqual(actual[field], expected[field], field)
        for group in ('focal', 'recruits'):
            for identity, member in expected[group].items():
                self.assertEqual({k: actual[group][identity][k] for k in member}, member)

    def test_pending_seeds_after_old_horizon_still_require_observation(self):
        tick, stop = audit.BASE + audit.STEP, audit.STOP
        seed = dict(parent=1, birth_tick=audit.BASE, end_tick=None, outcome='pending',
                    child_id=None, column=20, lifetime_ecology_ticks=8192)
        lives = {1: dict(birth_tick=0, death_tick=None, column=3)}
        raw = [1, 1, 20, 1, 100, 100, 1, 4, 0, 0, 28]
        seeds = {(1, audit.BASE): seed}
        self.assertEqual(set(window.check_inventory([[raw, '00' * 28]], [], 1, tick, stop, [1], lives, seeds, False)),
                         set(seeds))
        with self.assertRaisesRegex(RuntimeError, 'inventory'):
            window.check_inventory([], [], 1, tick, stop, [1], lives, seeds, False)
        with self.assertRaisesRegex(RuntimeError, 'bank'):
            window.check_inventory([[raw, '00' * 28]], [], 0, tick, stop, [1], lives, seeds, False)

    def test_fresh_output_refused_before_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('existing', 'dangling'):
                path = Path(tmp) / name
                if name == 'existing':
                    path.mkdir()
                else:
                    path.symlink_to(Path(tmp) / 'missing')
                with patch('sys.argv', ['audit', '--extract-from', '/missing', '--out', str(path)]), \
                     patch.object(audit, 'extract', side_effect=AssertionError('no extraction')):
                    with self.assertRaisesRegex(RuntimeError, 'fresh output'):
                        audit.main()


@unittest.skipUnless(RESULT.exists(), 'portable audit not retained yet')
class CapturedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(RESULT, 'rt') as stream:
            cls.value = json.load(stream)
        cls.saved = audit.inputs()
        cls.key = sorted(cls.saved['panel'])[0]
        cls.saved_run = cls.saved['runs']['treatment'][cls.key]
        cls.world = cls.saved['panel'][cls.key]
        cls.lives, cls.seeds = window.bank.descendants.index_records(
            cls.saved_run['result']['lineages'], cls.saved_run['result']['seeds'], 0, audit.STOP)
        cls.evidence = cls.value['evidence'][cls.key]['treatment']

    def row(self):
        return copy.deepcopy(self.evidence['rows'][0])

    def check(self, row):
        return window.check_row(row, audit.BASE + audit.STEP, audit.STOP, self.saved_run['result'], self.lives, self.seeds)

    def test_full_reanalysis_without_processes(self):
        with patch('subprocess.run', side_effect=AssertionError('no processes')), \
             patch('subprocess.Popen', side_effect=AssertionError('no processes')):
            audit.check_value(self.value)

    def test_missing_resources_and_clock_are_rejected(self):
        row = self.row()
        row[0] += audit.STEP
        with self.assertRaisesRegex(RuntimeError, 'clock'):
            self.check(row)
        row = self.row()
        row[3].pop()
        with self.assertRaisesRegex(RuntimeError, 'coverage'):
            self.check(row)

    def test_incomplete_seeds_wrong_gate_fate_and_bank_are_rejected(self):
        row = self.row()
        row[5].pop()
        with self.assertRaisesRegex(RuntimeError, 'inventory'):
            self.check(row)
        for index, value, message in ((3, 0, 'gate'), (8, 2, 'fate')):
            row = self.row()
            row[5][0][0][index] = value
            with self.assertRaisesRegex(RuntimeError, message):
                self.check(row)
        row = self.row()
        row[7] -= 1
        with self.assertRaisesRegex(RuntimeError, 'bank'):
            self.check(row)

    def test_boundary_discard_and_missing_interval_fail(self):
        changed = copy.deepcopy(self.saved_run)
        changed['result']['second_turnover_probe']['energy'] += 1
        with self.assertRaisesRegex(RuntimeError, 'discard'):
            audit.analyze(changed, self.world, self.evidence)
        damaged = dict(self.evidence, rows=self.evidence['rows'][1:])
        with self.assertRaisesRegex(RuntimeError, 'window'):
            audit.analyze(self.saved_run, self.world, damaged)

    def test_derived_summary_and_boundary_change_fail(self):
        analysis = self.value['analysis'][self.key]['treatment']
        old = analysis['final']['living']
        analysis['final']['living'] += 1
        try:
            with self.assertRaisesRegex(RuntimeError, 'derived audit'):
                audit.check_value(self.value)
        finally:
            analysis['final']['living'] = old
        boundary = self.evidence['boundary']
        boundary[0] += audit.STEP
        try:
            with self.assertRaisesRegex(RuntimeError, 'pre-event evidence'):
                audit.check_value(self.value)
        finally:
            boundary[0] -= audit.STEP

    def test_first_cohort_remains_matched_but_new_numeric_ids_do_not(self):
        for key, world in self.saved['panel'].items():
            comparison = self.value['comparisons'][key]
            self.assertTrue(set(world['first_recruits']) <= set(comparison['matched_incumbents']))
            self.assertNotIn(world['target'], comparison['matched_incumbents'])
            for phase in audit.PHASES:
                result = self.saved['runs'][phase][key]['result']
                born = {p['id'] for p in result['lineages'] if p['birth_tick'] > audit.BASE}
                self.assertFalse(born & set(comparison['matched_incumbents']))


if __name__ == '__main__':
    unittest.main()
