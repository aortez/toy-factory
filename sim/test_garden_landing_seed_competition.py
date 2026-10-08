#!/usr/bin/env python3
"""Saved queue completeness, exact phase, dormancy and geometric/capacity bounds."""

import copy
import gzip
from itertools import combinations
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_seed_competition as audit

RESULT = audit.ROOT / 'benchmarks/garden-seasons/landing-seed-competition-results.json.gz'


class ContractTests(unittest.TestCase):
    def test_packing_is_exact_for_small_column_sets(self):
        for bits in range(1 << 9):
            columns = [c for c in range(9) if bits & (1 << c)]
            best = max(len(s) for size in range(len(columns) + 1) for s in combinations(columns, size)
                       if all(b - a >= 3 for a, b in zip(s, s[1:])))
            self.assertEqual(len(audit.packing(columns)), best)
        self.assertEqual(audit.packing([24, 17, 19, 18, 24]), [17, 24])
        with self.assertRaises(RuntimeError):
            audit.packing([28])

    def test_capacity_and_dormancy_do_not_disappear_at_an_alternative(self):
        sites = bytearray([32] * 28)
        sites[3], sites[6] = 0, 0
        raw = [31, 6, 3, 1, 100, 100, 7, 224, 0, 0, 2]
        chance = audit.opportunity(raw, sites.hex(), [3, 3, 6, 6], [3])
        self.assertEqual(chance['packing'], [3, 6])
        self.assertEqual(chance['admission_bound'], 1)
        self.assertEqual(chance['alternate_sites'], [6])
        self.assertEqual(chance['purchase_allowed_alternates'], [])
        self.assertFalse(chance['mature'])
        raw[1] = 8
        self.assertTrue(audit.opportunity(raw, sites.hex(), [3, 6], [3, 6])['mature'])
        raw[6] = 8
        sites = bytes(m | 8 for m in sites)
        self.assertEqual(audit.opportunity(raw, sites.hex(), [3, 6], [3, 6])['admission_bound'], 0)
        self.assertEqual(audit.opportunity(raw, sites.hex(), [3, 6], [3, 6])['alternate_sites'], [])
        raw[6], raw[7] = 7, 253
        self.assertEqual(audit.opportunity(raw, sites.hex(), [3, 6], [3, 6])['admission_bound'], 0)
        self.assertIsNone(audit.opportunity(raw, None, [3, 6], [3, 6]))

    def test_original_purchase_filter_is_not_current_geometry(self):
        sites = bytearray([32] * 28)
        purchase = dict(choices=[3, 3, 6, 6], sites=sites.hex())
        self.assertEqual(audit.purchase_allowed(purchase), [3, 6])
        sites[3] = 4  # The purchase filter ignores light but does enforce spacing.
        purchase['sites'] = sites.hex()
        self.assertEqual(audit.purchase_allowed(purchase), [3])

    def test_existing_and_dangling_outputs_refused_before_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            existing, dangling = Path(tmp), Path(tmp) / 'dangling'
            dangling.symlink_to(Path(tmp) / 'missing')
            for path in (existing, dangling):
                with patch('sys.argv', ['audit', '--bundle', '/missing', '--out', str(path)]), \
                     patch.object(audit, 'extract', side_effect=AssertionError('no extraction')):
                    with self.assertRaisesRegex(RuntimeError, 'fresh output'):
                        audit.main()


class CapturedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch('subprocess.run', side_effect=AssertionError('no processes')), \
             patch('subprocess.Popen', side_effect=AssertionError('no processes')):
            cls.capture = audit.inputs()
            with gzip.open(RESULT, 'rt') as stream:
                cls.value = json.load(stream)
        cls.keys = sorted(cls.capture['panel'])

    def arm(self, index=4, phase='treatment'):
        key = self.keys[index]
        return copy.deepcopy(self.value['evidence'][key][phase]), key, phase

    def test_portable_reanalysis_and_deterministic_export_without_processes(self):
        with patch('subprocess.run', side_effect=AssertionError('no processes')), \
             patch('subprocess.Popen', side_effect=AssertionError('no processes')):
            audit.check_value(self.value)
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'copy.json.gz'
                audit.write_gzip(path, audit.build(self.value['evidence']))
                self.assertEqual(path.read_bytes(), RESULT.read_bytes())

    def test_all_ten_histories_and_twelve_followed_plants_per_arm(self):
        self.assertEqual(len(self.value['analysis']), 5)
        for phase in audit.PHASES:
            arms = [self.value['analysis'][k][phase] for k in self.keys]
            self.assertEqual(sum(len(a['cohorts']['focal']) for a in arms), 7)
            self.assertEqual(sum(len(a['cohorts']['first_recruit']) for a in arms), 5)
            self.assertTrue(all(a['admission_bound_range'] == [1, 1] for a in arms))
            self.assertTrue(all(not a['later_births'] and not a['later_deaths'] for a in arms))
            self.assertTrue(all(not p['post_onset']['children'] for a in arms
                                for cohort in a['cohorts'].values() for p in cohort.values()))

    def test_windows_cannot_be_shortened_or_reordered(self):
        for mutate in (lambda rows: rows.pop(0), lambda rows: rows.pop(10),
                       lambda rows: rows.reverse(), lambda rows: rows.pop()):
            evidence, key, phase = self.arm()
            mutate(evidence['rows'])
            with self.assertRaisesRegex(RuntimeError, 'clock or boundary'):
                audit.analyze_arm(evidence, key, phase)

    def test_checks_cannot_be_omitted_duplicated_or_moved_to_another_birth(self):
        for kind in ('missing', 'duplicate', 'birth'):
            evidence, key, phase = self.arm()
            checks = evidence['rows'][1]['checks']
            if kind == 'missing':
                checks.pop()
            elif kind == 'duplicate':
                checks.append(copy.deepcopy(checks[0]))
            else:
                checks[0][0][1] += 1
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                audit.analyze_arm(evidence, key, phase)

    def test_missing_or_invented_support_witness_fails(self):
        for kind in ('missing', 'trait', 'aliases'):
            evidence, key, phase = self.arm()
            if kind == 'missing':
                evidence['witnesses'].pop()
            elif kind == 'trait':
                evidence['witnesses'][0]['purchase']['dispersal'] = 8
            else:
                evidence['witnesses'][0]['purchase']['choices'].pop()
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                audit.analyze_arm(evidence, key, phase)

    def test_recruit_is_checked_before_winner_but_is_still_dormant(self):
        evidence, key, phase = self.arm()
        analysis = audit.analyze_arm(evidence, key, phase)
        closing = str(analysis['interval'][1])
        queue = analysis['snapshots'][closing]
        recruit = next(q for q in queue if q['seed'] == [31, 1109340])
        winner = next(q for q in queue if q['outcome'] == 2)
        self.assertLess(queue.index(recruit), queue.index(winner))
        self.assertEqual((recruit['age'], recruit['blockers']), (6, 1))
        self.assertEqual(recruit['opportunity']['admission_bound'], 1)
        after = next(q for q in analysis['snapshots'][str(int(closing) + audit.STEP)] if q['seed'] == recruit['seed'])
        self.assertEqual(after['opportunity']['admission_bound'], 0)
        self.assertTrue(after['blockers'] & 8 and after['blockers'] & 32)
        closing_row = evidence['rows'][-2]
        closing_row['checks'].reverse()
        with self.assertRaises(RuntimeError):
            audit.analyze_arm(evidence, key, phase)

    def test_off_column_maps_and_post_production_bank_are_checked(self):
        for kind in ('capacity', 'spacing', 'bank'):
            evidence, key, phase = self.arm()
            row = evidence['rows'][1]
            if kind == 'bank':
                row['bank'] -= 1
            else:
                raw, encoded = next(c for c in row['checks'] if c[1] is not None)
                sites = bytearray.fromhex(encoded)
                sites[(raw[2] + 1) % 28] ^= 8 if kind == 'capacity' else 32
                next(c for c in row['checks'] if c[1] is not None)[1] = sites.hex()
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                audit.analyze_arm(evidence, key, phase)

    def test_tampered_results_fail_even_with_rehashed_receipt(self):
        for kind in ('cohort', 'count', 'world', 'source'):
            value = copy.deepcopy(self.value)
            arm = value['analysis'][self.keys[0]]['treatment']
            if kind == 'cohort':
                arm['cohorts']['first_recruit'].clear()
            elif kind == 'count':
                arm['seeds'][0]['mature_alternative_checks'] += 1
            elif kind == 'world':
                value['evidence'].pop(self.keys[0])
            else:
                value['sources']['sim/garden_landing_seed_competition.py'] = '0' * 64
            value['receipt_sha256'] = audit.fingerprint({k: v for k, v in value.items() if k != 'receipt_sha256'})
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                audit.check_value(value)


if __name__ == '__main__':
    unittest.main()
