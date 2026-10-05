#!/usr/bin/env python3
"""Offline cohort, equal-exposure and saved-receipt regression tests."""

import copy
from fractions import Fraction
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_root_allocation_audit as audit

RESULT = audit.ROOT / 'benchmarks/garden-seasons/landing-root-allocation-audit-results.json.gz'
RESULT_SHA = '5dda8d5f5229690437c5250a718e7fb43cf954fd627ce8ea733607cbcad6e16f'


def count(payments, water, energy=0):
    return {'payments': payments, 'energy': {'unpaid': energy, 'shortages': int(energy > 0)},
            'water': {'unpaid': water, 'shortages': int(water > 0)}}


class ContractTests(unittest.TestCase):
    def test_recursive_matching_ignores_renumbering_not_changed_ancestry(self):
        def life(i, parent, birth, column):
            return dict(id=i, parent=parent, birth_tick=birth, column=column, species=0)
        a = {'lineages': [life(1, 0, 0, 3), life(2, 0, 0, 8), life(3, 1, 60, 5), life(4, 3, 120, 9)]}
        b = {'lineages': [life(7, 0, 0, 3), life(8, 0, 0, 8), life(9, 7, 60, 5), life(3, 9, 120, 9)]}
        self.assertEqual(audit.population.matched_births(a, b),
                         {'matched': [[1, 7], [2, 8], [3, 9], [4, 3]], 'control_only': [], 'candidate_only': []})
        b['lineages'][2]['parent'] = 8
        match = audit.population.matched_births(a, b)
        self.assertEqual(match['control_only'], [3, 4])
        self.assertEqual(match['candidate_only'], [3, 9])

    def test_common_end_censors_and_includes_earliest_death(self):
        a = dict(birth_tick=60, death_tick=None)
        self.assertEqual(audit.common_end([a, a], stop=240), 240)
        self.assertEqual(audit.common_end([a, a | {'death_tick': 120}], stop=240), 120)
        with self.assertRaisesRegex(RuntimeError, 'unmatched birth'):
            audit.common_end([a, a | {'birth_tick': 75}], stop=240)

    def test_newborn_payment_excluded_and_terminal_payment_included(self):
        p = {'life': {'birth_tick': 60, 'death_tick': 180}, 'shortages': [
            {'tick': 120, 'water': {'unpaid': 2}, 'energy': {'unpaid': 0}},
            {'tick': 180, 'water': {'unpaid': 3}, 'energy': {'unpaid': 1}}]}
        self.assertEqual(audit.counts(p, 60), count(0, 0))
        self.assertEqual(audit.counts(p, 120), count(1, 2))
        self.assertEqual(audit.subtract(audit.counts(p), audit.counts(p, 120)), count(1, 3, 1))
        with self.assertRaisesRegex(RuntimeError, 'outside lifetime'): audit.counts(p, 195)
        with self.assertRaisesRegex(RuntimeError, 'negative exposure'): audit.subtract(count(0, 0), count(1, 0))

    def test_rate_contributions_include_changed_denominator(self):
        groups = {a: {g: count(0, 0) for g in audit.GROUPS} for a in audit.ARMS}
        groups['control']['matched_common'] = count(100, 10)
        groups['candidate']['matched_common'] = count(100, 12)
        groups['candidate']['unmatched'] = count(100, 0)
        value = audit.decompose(groups)
        # Matched plants regress, but the total rate improves through exposure
        # to a new zero-shortage cohort. Neither observation cancels the other.
        self.assertEqual(value['change']['water'], [-1, 25])
        self.assertEqual(value['contributions']['water']['matched_common'], [-1, 25])
        self.assertEqual(value['rates']['control']['water'], [1, 10])
        self.assertEqual(value['rates']['candidate']['water'], [3, 50])
        self.assertEqual(sum(Fraction(*v) for v in value['contributions']['water'].values()),
                         Fraction(*value['change']['water']))

    def test_zero_exposure_is_unavailable_not_a_pass(self):
        self.assertEqual(audit.rates(count(0, 0)), {'water': None, 'energy': None})
        groups = {a: {g: count(0, 0) for g in audit.GROUPS} for a in audit.ARMS}
        groups['candidate']['unmatched'] = count(10, 0)
        self.assertEqual(audit.decompose(groups)['change'], {'water': None, 'energy': None})

    def test_existing_output_refused_before_loading_evidence(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(audit, 'load_input',
                side_effect=AssertionError('should not read inputs')):
            with self.assertRaisesRegex(RuntimeError, 'fresh output'):
                audit.export(Path('/missing'), Path(directory))


@unittest.skipUnless(RESULT.exists(), 'saved allocation audit not retained yet')
class CapturedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if audit.digest(RESULT) != RESULT_SHA:
            raise RuntimeError('saved allocation audit changed')
        with gzip.open(RESULT, 'rt') as stream:
            cls.value = json.load(stream)

    def pair(self, case, identity):
        return next(p for p in self.value['analysis'][case]['plants'] if p['ids'][0] == identity)

    def test_portable_verification_and_wrong_summary_rejection_never_launch_processes(self):
        with patch('subprocess.run', side_effect=AssertionError('unexpected process')), \
             patch('subprocess.Popen', side_effect=AssertionError('unexpected process')):
            audit.check_value(self.value)
            # Reuse the independently derived analysis to exercise the summary
            # rejection without rescanning half a million receipts a second time.
            bad_analysis = copy.deepcopy(self.value['analysis'])
            bad_analysis[0]['cohorts']['groups']['candidate']['matched_common']['water']['unpaid'] -= 1
            with patch.object(audit, 'analyze', return_value=self.value['analysis']):
                with self.assertRaisesRegex(RuntimeError, 'summary differs'):
                    audit.check_value(self.value | {'analysis': bad_analysis})

    def test_all_pairs_fail_water_screen_despite_focal_rescue(self):
        self.assertEqual(len(self.value['analysis']), 4)
        for e, expected in zip(self.value['analysis'], [(25956, 165, 201), (20354, 178, 193)] * 2, strict=True):
            p, u, v = expected
            groups = e['cohorts']['groups']
            self.assertEqual([groups[a]['matched_common']['payments'] for a in audit.ARMS], [p, p])
            self.assertEqual([groups[a]['matched_common']['water']['unpaid'] for a in audit.ARMS], [u, v])
            self.assertEqual(groups['candidate']['focal_common']['water']['unpaid'], 0)
            self.assertFalse(e['population_screen']['checks']['no_worse_water_rate'])
            self.assertFalse(e['population_screen']['passes_harm_screen'])

    def test_full_lifetime_totals_hide_removed_bills(self):
        for case in (0, 2):
            groups = self.value['analysis'][case]['cohorts']['groups']
            self.assertEqual([groups[a]['matched_tail']['payments'] for a in audit.ARMS], [18, 0])
            self.assertEqual([groups[a]['matched_tail']['water']['unpaid'] for a in audit.ARMS], [36, 0])
            self.assertEqual([sum(groups[a][g]['water']['unpaid'] for g in ('matched_common', 'matched_tail'))
                              for a in audit.ARMS], [201, 201])

    def test_neighbor_loss_is_retained_income_not_extra_construction(self):
        for case, loss in ((0, 6), (1, 7), (2, 6), (3, 7)):
            p = self.pair(case, 11)
            d = p['resource_delta']['water']
            self.assertEqual(d['income'] - d['overflow'], -loss)
            self.assertEqual([d[k] for k in ('growth', 'reproduction', 'final', 'discarded')], [0] * 4)
            self.assertEqual(d['upkeep'], -loss)
            self.assertEqual([p['life'][a]['death_tick'] for a in audit.ARMS], [456420, 456300])
            self.assertEqual(p['first']['water_unpaid']['tick'], 455880)
            self.assertFalse(p['common']['candidate']['alive_at_end'])
            self.assertTrue(p['common']['control']['alive_at_end'])
            self.assertEqual([p['common'][a]['counts']['payments'] for a in audit.ARMS], [883, 883])

    def test_later_matched_failures_include_extra_seed_spending(self):
        for case, i, retained, unpaid, stored in ((0, 16, -16, 23, 17), (1, 17, 1, 16, 7)):
            p = self.pair(case, i)
            d = p['resource_delta']['water']
            self.assertEqual(d['income'] - d['overflow'], retained)
            self.assertEqual([d['growth'], d['reproduction'], d['upkeep'], d['final']],
                             [0, 24, -unpaid, -stored])
            self.assertEqual([p['common'][a]['counts']['water']['unpaid'] for a in audit.ARMS], [0, unpaid])
            self.assertGreater(p['life']['control']['birth_tick'], 576780)

    def test_founders_and_repeats_are_not_independent_treatment_trials(self):
        self.assertEqual(len(self.value['sources']), 16)
        self.assertEqual(len(self.value['receipts']), 47)
        self.assertEqual(sum(len(r) for r in self.value['receipts'].values()), 451036)
        for e in self.value['analysis']:
            self.assertEqual(e['cohorts']['founders']['control'], e['cohorts']['founders']['candidate'])
            self.assertTrue(all(not p['first'] for p in e['plants'] if p['kind'] == 'founder'))
        for i in (0, 1):
            for p, q in zip(self.value['analysis'][i]['plants'], self.value['analysis'][i + 2]['plants'], strict=True):
                if p['end'] <= audit.population.order.AT: self.assertEqual(p, q)

    def test_provenance_sources_and_changed_receipts_rejected(self):
        for key, value in (('new_simulations', True), ('training_runs', 1), ('input_sha256', '0' * 64),
                           ('raw_manifest_sha256', '0' * 64), ('packed_fields', [])):
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, 'provenance/scope'):
                audit.check_value(self.value | {key: value})
        with self.assertRaisesRegex(RuntimeError, 'source coverage'):
            audit.check_value(self.value | {'sources': self.value['sources'][:-1]})
        receipts = dict(self.value['receipts'])
        sha = next(iter(receipts))
        receipts[sha] = receipts[sha][:-1]
        with self.assertRaisesRegex(RuntimeError, 'checksum differs'):
            audit.check_value(self.value | {'receipts': receipts})

    def test_missing_coverage_and_resource_discontinuity_rejected(self):
        entry = audit.load_input()[0]
        p = audit.index(entry, 'candidate')[11]
        end = self.pair(0, 11)['end']
        sha = self.value['references'][0]['arms']['candidate']['11']
        rows = self.value['receipts'][sha]
        with self.assertRaisesRegex(RuntimeError, 'incomplete common history'):
            audit.history(rows[:-1], p, end)
        bad = list(rows)
        bad[1] = copy.deepcopy(rows[1])
        bad[1][1][1][0] += 1
        with self.assertRaisesRegex(RuntimeError, 'inter-step resource discontinuity'):
            audit.history(bad, p, end)
        refs = copy.deepcopy(self.value['references'])
        refs[0]['arms']['control'].pop('11')
        with self.assertRaisesRegex(RuntimeError, 'matched receipt coverage'):
            audit.analyze(audit.load_input(), refs, self.value['receipts'])


if __name__ == '__main__':
    unittest.main()
