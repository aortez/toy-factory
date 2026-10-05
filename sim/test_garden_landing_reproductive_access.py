#!/usr/bin/env python3
"""Offline reproductive readiness, sequential bank access and seed fate receipts."""

import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_reproductive_access as audit
from test_garden_landing_bank_access import fixture as bank_fixture

RESULT = audit.ROOT / 'benchmarks/garden-seasons/landing-reproductive-access-results.json.gz'
RESULT_SHA = '1db7c619a4acd770e36dccfd108c8d75369c9dbcd3153b98273f51b6024b5f39'


def resource_sample(produced=True):
    life = dict(id=1, parent=0, birth_tick=0, death_tick=None)
    before, maintained = [160, 300, 0, 0, 8], [159, 299, 0, 0, 8]
    after = [159 - 48 * produced, 299 - 24 * produced, 0, 0, 8]
    packed = [[before, maintained, maintained, maintained, after],
              [[160, 0, 0, 0, 0, 0], [300, 0, 0, 0, 0, 0]], 2, 2]
    visit = dict(energy=159, water=299, stress=0, immature=0, spent=0, ready=1, flower=6, produced=produced)
    return visit, [8, 2, 1], packed, life, 60, before


def seed(birth):
    return dict(parent=1, birth_tick=birth, column=1, end_tick=None, child_id=None,
                outcome='pending', lifetime_ecology_ticks=8192)


class ContractTests(unittest.TestCase):
    def test_fixed_cohort_is_seven_survivors_in_five_of_32_worlds(self):
        _, cohort = audit.inputs()
        self.assertEqual(len(cohort), 32)
        self.assertEqual(sum(map(len, cohort.values())), 7)
        self.assertEqual(sum(bool(ids) for ids in cohort.values()), 5)
        self.assertEqual(cohort['f7ee4528-fixed-candidate-control-wide-cap-trace'], [33, 34])
        self.assertEqual((audit.STOP - audit.BASE) // audit.STEP, 8192)

    def test_rotation_uses_stored_inventory_only_on_production_cadence(self):
        after = audit.spending.population.order.AT
        slots = [7, 3, 8]
        for tick, ids in ((after, slots), (after + 15, slots),
                          (after + 60, [3, 8, 7]), (after + 120, [8, 7, 3])):
            audit.visit_order(tick, slots, [[i] for i in ids], {'seed_order_probe': {'after': after}})
        audit.visit_order(after + 60, slots, [[i] for i in slots], {})
        for ids in ([8, 3, 7], [7, 3], [7, 3, 3]):
            with self.assertRaises(RuntimeError):
                audit.visit_order(after, slots, [[i] for i in ids], {})

    def test_full_at_entry_and_earlier_buyer_are_distinct(self):
        for release in (True, False):
            result, rows = bank_fixture(release=release)
            value = audit.bank.analyze_visits(rows, result, rows[0][0], rows[-1][0])
            p = next(p for p in value['plants'] if p['id'] == 2)
            self.assertEqual(p['access']['earlier_buyers_fill'], int(release))
            self.assertEqual(p['access']['full_at_entry'], int(not release))

    def test_seed_costs_and_continuity_reconcile(self):
        for produced in (True, False):
            args = resource_sample(produced)
            transfers, _ = audit.check_focal_sample(*args)
            self.assertEqual(transfers['energy']['reproduction'], 48 * produced)
            self.assertEqual(transfers['water']['reproduction'], 24 * produced)
        for fault in ('cost', 'continuity', 'stores', 'stress', 'flowers', 'ready'):
            args = list(copy.deepcopy(resource_sample()))
            if fault == 'cost': args[2][0][4][1] += 1
            elif fault == 'continuity': args[-1] = [159, 300, 0, 0, 8]
            elif fault == 'stores': args[0]['energy'] += 1
            elif fault == 'stress': args[0]['stress'] = 1
            elif fault == 'flowers': args[1][2] = 0
            else: args[0]['flower'] = 65535
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                audit.check_focal_sample(*args)

    def test_flower_inventory_accepts_immature_spent_and_ready_separately(self):
        for state in ('immature', 'spent', 'ready'):
            args = list(resource_sample(False))
            args[0].update(immature=0, spent=0, ready=0, flower=65535)
            args[0][state] = 1
            if state == 'ready': args[0]['flower'] = 6
            audit.check_focal_sample(*args)

    def test_simultaneous_germination_gates_are_not_exclusive_causes(self):
        s = seed(audit.BASE + 60)
        tick = s['birth_tick'] + 8 * audit.STEP
        raw = [1, 8, 1, 126, 11, 79, 8, 253, 0, 0, 0]
        lives = {i: {'column': i} for i in range(1, 9)}
        audit.seed_check(raw, '7e' * 28, tick, s, list(lives), lives, True)
        for field, change in ((3, 124), (4, 12), (5, 80), (6, 7), (7, 252), (10, 1)):
            bad = list(raw)
            bad[field] = change
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                audit.seed_check(bad, '7e' * 28, tick, s, list(lives), lives, True)

    def test_expiry_is_not_a_successful_open_site_check(self):
        s = seed(audit.BASE)
        s.update(end_tick=audit.STOP, outcome='expired')
        raw = [1, 8192, 1, 0, 0, 0, 1, 8, 1, 0, -1]
        audit.seed_check(raw, None, audit.STOP, s, [1], {1: {'column': 1}}, False)
        for change, encoded in (({10: 0}, None), ({1: 8191}, None), ({}, '00' * 28)):
            bad = list(raw)
            for k, v in change.items(): bad[k] = v
            with self.assertRaises(RuntimeError):
                audit.seed_check(bad, encoded, audit.STOP, s, [1], {1: {'column': 1}}, False)

    def test_pending_seed_is_censored_and_dormancy_is_not_mature_exposure(self):
        s = seed(audit.STOP - 7 * audit.STEP)
        records = [[s['birth_tick'] + age * audit.STEP,
                    [1, age, 1, 33, 100, 100, 1, 8, 0, 0, 0], '20' * 28, [1]] for age in range(1, 8)]
        summary = audit.seed_summary(s, records, {1: {'column': 1}})
        self.assertTrue(summary['right_censored'])
        self.assertEqual((summary['checks'], summary['dormant'], summary['mature_masks']), (7, 7, {}))
        with self.assertRaisesRegex(RuntimeError, 'incomplete focal seed'):
            audit.seed_summary(s, records[:-1], {1: {'column': 1}})

    def test_germination_changes_next_seed_plant_count_and_spacing(self):
        tick = audit.BASE + 120
        s = seed(audit.BASE)
        s.update(column=10, end_tick=tick, child_id=2, outcome='germinated')
        second = seed(audit.BASE + 15)
        second['column'] = 11
        lives = {1: dict(column=1, birth_tick=0), 2: dict(column=10, birth_tick=tick)}
        raw = [[1, 8, 10, 0, 100, 100, 1, 8, 2, 2, 28],
               [1, 7, 11, 33, 100, 100, 2, 12, 0, 0, 0]]
        reach = dict(checks=[[1, 8, 10, 0, 2, 2, '00' * 28],
                             [1, 7, 11, 33, 0, 0, '20' * 28]], purchases=[])
        adult = dict(tick=tick, seeds=raw, bank=1)
        seeds = {(1, audit.BASE): s, (1, audit.BASE + 15): second}
        records, purchases = audit.check_inventory(adult, reach, [1, 2], lives, seeds, False)
        self.assertEqual([r[3] for r in records.values()], [[1], [1, 2]])
        self.assertEqual(purchases, {})
        for fault in ('missing', 'duplicate', 'census', 'reach'):
            a, r = copy.deepcopy(adult), copy.deepcopy(reach)
            if fault == 'missing': a['seeds'].pop(); r['checks'].pop()
            elif fault == 'duplicate': a['seeds'][1] = a['seeds'][0]; r['checks'][1] = r['checks'][0]
            elif fault == 'census': a['seeds'][1][6] = 1
            else: r['checks'][1][3] = 1
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                audit.check_inventory(a, r, [1, 2], lives, seeds, False)

    def test_existing_and_broken_symlink_outputs_refused_before_extraction(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(audit, 'extract', side_effect=AssertionError('no read')):
            root = Path(tmp)
            link = root / 'broken.gz'
            link.symlink_to(root / 'missing.gz')
            for out in (root, link):
                with self.assertRaisesRegex(RuntimeError, 'fresh output'):
                    audit.export(root, out)
            self.assertFalse((root / 'missing.gz').exists())

    def test_runtime_provenance_comes_from_captured_sources_not_future_C(self):
        expected = audit.provenance()
        real_digest = audit.digest

        def changed_C(path):
            return '0' * 64 if str(path).endswith(('.c', '.h')) else real_digest(path)

        with patch.object(audit, 'digest', side_effect=changed_C):
            self.assertEqual(audit.provenance(), expected)


@unittest.skipUnless(RESULT.exists(), 'portable audit not retained yet')
class CapturedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if audit.digest(RESULT) != RESULT_SHA:
            raise RuntimeError('saved reproductive access fixture changed')
        with gzip.open(RESULT, 'rt') as stream:
            cls.value = json.load(stream)

    def test_portable_verification_never_launches_a_process(self):
        with patch('subprocess.run', side_effect=AssertionError('no processes')), \
             patch('subprocess.Popen', side_effect=AssertionError('no processes')):
            audit.check_value(self.value)

    def test_all_seven_have_complete_resources_and_only_two_purchase(self):
        focal = [p for a in self.value['analysis'].values() for p in a['focal'].values()]
        self.assertEqual(len(focal), 7)
        self.assertEqual(sorted(p['readiness']['purchased'] for p in focal), [0, 0, 0, 0, 0, 1, 1])
        for p in focal:
            self.assertEqual(sum(p['flower_states'].values()), 8192)
            self.assertEqual(p['resources']['energy']['reproduction'], p['readiness']['purchased'] * 48)
            self.assertEqual(p['resources']['water']['reproduction'], p['readiness']['purchased'] * 24)
        offspring = [s for a in self.value['analysis'].values() for s in a['seeds'].values()]
        self.assertEqual(len(offspring), 2)
        self.assertTrue(all(s['seed']['outcome'] != 'germinated' for s in offspring))

    def test_focal_banks_and_seed_gates_preserve_overlapping_constraints(self):
        for a in self.value['analysis'].values():
            if not a['focal']:
                continue
            self.assertEqual(a['access']['bank']['post_step_counts'], {'8': 8192})
            for s in a['seeds'].values():
                self.assertTrue(s['right_censored'])
                self.assertEqual(s['checks'], 1540)
                self.assertEqual(s['dormant'], 7)
                self.assertEqual(s['mature_blockers']['plant_capacity'], 1533)
                self.assertEqual(s['mature_blockers']['spacing'], 1533)
                self.assertEqual(s['mature_blockers']['moisture'], 0)

    def test_missing_panel_changed_provenance_and_receipt_fail(self):
        for fault in ('panel', 'cohort', 'sources', 'implementation', 'receipt'):
            value = dict(self.value)
            if fault == 'panel': value['evidence'] = {}
            elif fault == 'receipt': value['receipt_sha256'] = '0' * 64
            else: value[fault] = {}
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                audit.check_value(value)

    def test_mutated_clock_flower_stores_and_order_fail_reanalysis(self):
        key = 'f7ee4528-fixed-candidate-control-wide-cap-trace'
        original, cohort = audit.inputs()
        source = self.value['evidence'][key]
        for fault in ('clock', 'flower', 'stores', 'order', 'missing_seed_checks'):
            evidence = copy.deepcopy(source)
            if fault == 'clock': evidence['visits'][0][0] += audit.STEP
            elif fault == 'flower': evidence['plants']['33'][0][1][2] += 1
            elif fault == 'stores': evidence['boundary']['33'][0][-1][1] -= 1
            elif fault == 'order': evidence['visits'][0][2].reverse()
            else: evidence['checked_seed_attempts'] -= 1
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                audit.analyze_world(original['runs']['extension'][key]['result'], cohort[key], evidence)


if __name__ == '__main__':
    unittest.main()
