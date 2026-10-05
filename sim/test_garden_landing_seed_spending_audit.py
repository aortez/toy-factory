#!/usr/bin/env python3
"""Offline production gates, capacity reset boundaries and evidence validation."""

import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_seed_spending_audit as audit

RESULT = audit.ROOT / 'benchmarks/garden-seasons/landing-seed-spending-audit-results.json.gz'
RESULT_SHA = '2a1de1c9c6a2574a6e47d9bd7bb787038a87a4e19a0af4f5e8b6268e3736baef'


def refill_row(pre, post, uptake=None):
    return [[None if uptake is None else [0, uptake, 0, 0, 3], None, None,
             [0, pre, 0, 0, 3], [0, post, 0, 0, 3]], None, 2, 0]


class ContractTests(unittest.TestCase):
    def test_actual_refill_and_pre_purchase_store_are_distinct(self):
        rows = [refill_row(490, 466, 500), refill_row(493, 493, 493), refill_row(510, 510, 512)]
        self.assertEqual(audit.first_refill(rows, 0),
                         {'capacity_tick': audit.START + 30, 'pre_purchase_store_tick': audit.START + 15})
        self.assertEqual(audit.first_refill(rows[:1], 0),
                         {'capacity_tick': None, 'pre_purchase_store_tick': None})

    def test_shared_cap_requires_both_arms_and_excludes_shortage_boundary(self):
        full = refill_row(512, 512, 512)
        low = refill_row(500, 500, 500)
        rows = {'control': [full, full, full], 'candidate': [full, low, full]}
        self.assertEqual(audit.last_shared_cap(rows, audit.START + 30), 0)
        self.assertEqual(audit.last_shared_cap(rows, audit.START + 45), 2)
        self.assertIsNone(audit.last_shared_cap(rows, audit.START))
        with self.assertRaisesRegex(RuntimeError, 'unequal common'):
            audit.last_shared_cap(rows | {'candidate': [full]}, audit.START + 45)

    def test_tail_excludes_anchor_uptake_but_includes_its_maintenance(self):
        before = [100, 512, 0, 0, 8]
        after = [99, 511, 0, 0, 8]
        later = [102, 511, 0, 0, 8]
        rows = [[[before, after, after, after, after], [[90, 20, 10, 0, 0, 0], [500, 20, 8, 0, 0, 0]], 2, 2],
                [[later] * 5, [[99, 3, 0, 0, 0, 0], [511, 0, 0, 0, 0, 0]], 2, 2]]
        life = dict(id=1, parent=0, birth_tick=0, death_tick=None)
        value = audit.tail_budget(rows, life, 0)
        self.assertEqual(value['water'], dict(initial=512, income=0, overflow=0, upkeep=1,
                                             growth=0, reproduction=0, discarded=0, final=511))
        self.assertEqual([value['energy'][k] for k in ('initial', 'income', 'overflow', 'upkeep', 'final')],
                         [100, 3, 0, 1, 102])
        with self.assertRaisesRegex(RuntimeError, 'invalid post-uptake anchor'):
            audit.tail_budget(rows, life, -1)

    def test_simultaneous_blocker_names_and_invalid_masks(self):
        self.assertEqual(audit.blocker_names(4 | 128 | 256), ['bank', 'energy', 'water'])
        self.assertEqual(audit.blocker_names(0), [])
        for mask in (True, -1, 1024):
            with self.assertRaisesRegex(RuntimeError, 'invalid blocker'): audit.blocker_names(mask)

    def test_existing_output_refused_before_reading_inputs(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(audit, 'inputs',
                side_effect=AssertionError('should not load evidence')):
            with self.assertRaisesRegex(RuntimeError, 'fresh output'):
                audit.export(Path('/missing'), Path(directory))


@unittest.skipUnless(RESULT.exists(), 'saved seed spending audit not retained yet')
class CapturedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if audit.digest(RESULT) != RESULT_SHA:
            raise RuntimeError('saved seed spending fixture changed')
        with gzip.open(RESULT, 'rt') as stream:
            cls.value = json.load(stream)

    def test_portable_verification_never_launches_a_process(self):
        with patch('subprocess.run', side_effect=AssertionError('unexpected process')), \
             patch('subprocess.Popen', side_effect=AssertionError('unexpected process')):
            audit.verify(RESULT)

    def test_extra_seed_is_bank_availability_not_control_resource_refusal(self):
        for n, e in enumerate(self.value['analysis']):
            tick = 594660 if n % 2 == 0 else 594780
            p = next(p for p in e['paired_purchases'] if p['tick'] == tick)
            self.assertEqual(p['blockers'], {'control': ['bank'], 'candidate': []})
            for v in p['visits'].values():
                self.assertGreaterEqual(v['energy'], v['energy_required'])
                self.assertGreaterEqual(v['water'], v['water_required'])
            self.assertEqual(p['visits']['control']['bank'], 8)
            self.assertEqual(p['visits']['candidate']['bank'], 7 if n % 2 == 0 else 5)

    def test_every_purchase_refills_and_extra_seeds_expire(self):
        for n, e in enumerate(self.value['analysis']):
            tick = 594660 if n % 2 == 0 else 594780
            extra = next(p for p in e['arms']['candidate']['purchases'] if p['tick'] == tick)
            self.assertEqual(extra['refill']['capacity_tick'], 596520)
            self.assertLess(596520 - tick, audit.population.DAY // 2)
            self.assertEqual(extra['seed']['outcome'], 'expired')
            self.assertIsNone(extra['child'])
            for arm in audit.ARMS:
                for p in e['arms'][arm]['purchases']:
                    self.assertIsNotNone(p['refill']['capacity_tick'])
                    self.assertIsNotNone(p['refill']['pre_purchase_store_tick'])
                    self.assertLess(p['refill']['capacity_tick'], e['last_shared_capacity']['tick'])

    def test_post_capacity_loss_has_no_seed_or_growth_spending(self):
        for n, e in enumerate(self.value['analysis']):
            value = e['last_shared_capacity']
            self.assertEqual(value['tick'], 626580 if n % 2 == 0 else 626520)
            self.assertEqual(value['stage'], 'after_uptake_before_maintenance')
            for a in value['arms'].values():
                self.assertEqual(a['seed_ticks'], [])
                w = a['resources']['water']
                self.assertEqual([w[k] for k in ('initial', 'growth', 'reproduction', 'discarded')], [512, 0, 0, 0])
                self.assertEqual(w['initial'] + w['income'] - w['overflow'], w['upkeep'] + w['final'])
            d = value['delta']['water']
            self.assertEqual(d['income'] - d['overflow'], -40 if n % 2 == 0 else -23)
            self.assertEqual(d['upkeep'], -23 if n % 2 == 0 else -16)
            self.assertEqual(d['final'], -17 if n % 2 == 0 else -7)

    def test_order_changes_later_seed_but_not_terminal_water_accounts(self):
        fixed, rotating = [self.value['analysis'][n] for n in (0, 2)]
        for arm in audit.ARMS:
            self.assertIn(621600, [p['tick'] for p in fixed['arms'][arm]['purchases']])
            self.assertNotIn(621600, [p['tick'] for p in rotating['arms'][arm]['purchases']])
        for n in (0, 1):
            a, b = self.value['analysis'][n], self.value['analysis'][n + 2]
            for arm in audit.ARMS:
                self.assertEqual(a['last_shared_capacity']['arms'][arm]['resources']['water'],
                                 b['last_shared_capacity']['arms'][arm]['resources']['water'])
                self.assertEqual(a['arms'][arm]['first_water_shortage'], b['arms'][arm]['first_water_shortage'])

    def test_observed_child_outcomes_are_not_confused_with_extra_seed(self):
        for n in (0, 2):
            e = self.value['analysis'][n]
            first = e['arms']['candidate']['purchases'][0]
            self.assertEqual(first['seed']['child_id'], 22)
            self.assertEqual(first['child_one_day'], 'confirmed')
            self.assertEqual(e['arms']['control']['purchases'][0]['seed']['outcome'], 'expired')
        for n in (1, 3):
            self.assertTrue(all(self.value['analysis'][n]['arms'][a]['purchases'][0]['child_one_day'] == 'confirmed'
                                for a in audit.ARMS))

    def test_complete_coverage_refusals_and_repeat_sources(self):
        self.assertEqual(len(self.value['sources']), 16)
        self.assertEqual(sum(len(rows) for case in self.value['cases'] for rows in case['arms'].values()), 27448)
        for s, c in zip(audit.inputs(), self.value['cases'], strict=True):
            for arm in audit.ARMS:
                self.assertEqual(len(c['arms'][arm]), (s['end'] - audit.START) // audit.STEP + 1)
                self.assertTrue(any(not v['produced'] and v['blockers'] & 2 for row in c['arms'][arm]
                                    for v in row['reproduction'] if v['id'] == s['id']))
        with self.assertRaisesRegex(RuntimeError, 'panel coverage'):
            audit.analyze(self.value['cases'][:-1])

    def test_corrupt_gates_order_body_climate_and_debit_rejected(self):
        subject = audit.inputs()[0]
        n = (594660 - audit.START) // audit.STEP
        original = self.value['cases'][0]['arms']['control'][n]
        packed = subject['resources']['control'][n]
        result = subject['entry']['arms']['control']['result']
        def target(row): return next(v for v in row['reproduction'] if v['id'] == 16)
        for change in (lambda r: target(r).update(blockers=0), lambda r: r['reproduction'].reverse(),
                       lambda r: r['body'].update(flowers=0), lambda r: r['climate'].update(day=0),
                       lambda r: target(r).update(water=497)):
            row = copy.deepcopy(original)
            change(row)
            with self.assertRaises(RuntimeError): audit.check_visits(row, packed, result, 16)
        bad = copy.deepcopy(packed)
        bad[0][4][1] -= 1
        with self.assertRaisesRegex(RuntimeError, 'seed debit differs'):
            audit.check_visits(original, bad, result, 16)

    def test_missing_reordered_boolean_ticks_rejected(self):
        subject, case = audit.inputs()[0], self.value['cases'][0]
        rows = case['arms']['control']
        for altered in (rows[:-1], list(reversed(rows)), [rows[0] | {'tick': True}, *rows[1:]]):
            with self.assertRaises(RuntimeError):
                audit.analyze_case(subject, case | {'arms': case['arms'] | {'control': altered}})

    def test_wrong_provenance_checksum_and_summary_rejected(self):
        for key, value in (('new_simulations', True), ('training_runs', 1), ('inputs', {})):
            with self.assertRaisesRegex(RuntimeError, 'provenance/scope'):
                audit.check_value(self.value | {key: value})
        with self.assertRaisesRegex(RuntimeError, 'audit sources'):
            audit.check_value(self.value | {'sources': self.value['sources'][:-1]})
        with self.assertRaisesRegex(RuntimeError, 'receipt checksum'):
            audit.check_value(self.value | {'receipts_sha256': '0' * 64})
        summary = copy.deepcopy(self.value['analysis'])
        summary[0]['last_shared_capacity']['arms']['candidate']['resources']['water']['reproduction'] = 24
        with self.assertRaisesRegex(RuntimeError, 'summary differs'):
            audit.check_value(self.value | {'analysis': summary})


if __name__ == '__main__':
    unittest.main()
