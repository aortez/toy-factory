#!/usr/bin/env python3
"""Portable accounting and adversarial evidence tests; never simulate."""

import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_disturbance_audit as audit

RESULT = audit.ROOT / 'benchmarks/garden-seasons/landing-disturbance-results.json.gz'


class ContractTests(unittest.TestCase):
    def test_posthumous_child_and_survival_censoring(self):
        saved = audit.inputs()
        key = next(iter(saved['panel']))
        result = saved['runs']['treatment'][key]['result']
        lives, seeds = audit.bank.descendants.index_records(result['lineages'], result['seeds'], 0, audit.STOP)
        target = saved['panel'][key]['target']
        family = audit.family(target, lives, seeds)
        self.assertFalse(family['alive_at_horizon'])
        self.assertEqual(family['new_seeds'], [])
        self.assertEqual(len(family['children']), 1)
        child = family['children'][0]
        self.assertLess(child['seed']['birth_tick'], audit.BASE)
        self.assertGreater(child['life']['birth_tick'], audit.BASE)
        self.assertEqual(child['survival'], {'1': 'confirmed', '16': 'confirmed', '32': 'censored'})

    def test_temporary_slot_release_is_not_hidden_by_same_step_refill(self):
        lives = {1: dict(birth_tick=0, death_tick=90, column=4),
                 2: dict(birth_tick=105, death_tick=None, column=4),
                 3: dict(birth_tick=0, death_tick=None, column=10)}
        event = audit.slot_change([1, 3], [3, 2], 105, lives)
        self.assertEqual(event['slots_before'], 2)
        self.assertEqual(event['slots_before_germination'], 1)
        self.assertEqual(event['slots_after'], 2)
        self.assertEqual(event['removed'], [1])
        self.assertEqual(event['born'], [2])
        self.assertIn(4, event['newly_clear_columns'])
        lives[1]['death_tick'] = None
        with self.assertRaisesRegex(RuntimeError, 'reclamation/birth'):
            audit.slot_change([1, 3], [3, 2], 105, lives)

    def test_fresh_output_refused_before_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('existing', 'dangling'):
                path = Path(tmp) / name
                if name == 'existing': path.mkdir()
                else: path.symlink_to(Path(tmp) / 'missing')
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
        cls.key = next(iter(cls.saved['panel']))
        cls.result = cls.saved['runs']['treatment'][cls.key]['result']
        cls.lives, cls.seeds = audit.bank.descendants.index_records(cls.result['lineages'], cls.result['seeds'], 0, audit.STOP)
        cls.evidence = cls.value['evidence'][cls.key]['treatment']

    def row(self):
        return copy.deepcopy(self.evidence['rows'][0])

    def check(self, row):
        return audit.check_row(row, audit.START, self.result, self.lives, self.seeds)

    def test_full_portable_reanalysis_with_processes_forbidden(self):
        with patch('subprocess.run', side_effect=AssertionError('no processes')), \
             patch('subprocess.Popen', side_effect=AssertionError('no processes')):
            audit.check_value(self.value)

    def test_clock_and_missing_resources_fail_closed(self):
        row = self.row()
        row[0] += audit.STEP
        with self.assertRaisesRegex(RuntimeError, 'clock'):
            self.check(row)
        row = self.row()
        row[3].pop()
        with self.assertRaisesRegex(RuntimeError, 'coverage'):
            self.check(row)

    def test_incomplete_seed_inventory_and_wrong_simultaneous_gate_rejected(self):
        row = self.row()
        row[5].pop()
        with self.assertRaisesRegex(RuntimeError, 'inventory'):
            self.check(row)
        row = self.row()
        row[5][0][0][3] ^= 2
        with self.assertRaisesRegex(RuntimeError, 'gate'):
            self.check(row)

    def test_seed_fate_and_bank_census_rejected(self):
        row = self.row()
        row[5][0][0][8] = 2
        with self.assertRaisesRegex(RuntimeError, 'fate'):
            self.check(row)
        row = self.row()
        row[7] -= 1
        with self.assertRaisesRegex(RuntimeError, 'bank'):
            self.check(row)

    def test_dead_body_stays_stored_but_never_has_living_budget(self):
        row = self.row()
        target = self.saved['panel'][self.key]['target']
        self.assertIn(target, row[1])
        self.assertNotIn(target, dict(row[3]))
        self.check(row)
        anchor = dict(self.evidence['boundary'][3])
        row[3].append([target, anchor[target]])
        with self.assertRaisesRegex(RuntimeError, 'coverage'):
            self.check(row)

    def test_discontinuity_and_wrong_purchase_debit_rejected(self):
        row = self.row()
        identity, packed = row[3][0]
        life = self.lives[identity]
        before = dict(self.evidence['boundary'][3])[identity][0][-1]
        packed[1][0][0] -= 1
        with self.assertRaisesRegex(RuntimeError, 'discontinuity'):
            audit.adults.transfers(audit.resources.unpack(packed, life, audit.START), life, before)
        row = self.row()
        identity, packed = row[3][0]
        visit = dict(zip(audit.bank.FIELDS, next(v for v in row[2] if v[0] == identity), strict=True))
        visit['produced'] = True
        body = next(b[1:] for b in row[4] if b[0] == identity)
        with self.assertRaisesRegex(RuntimeError, 'debits'):
            audit.previous.check_focal_sample(visit, body, packed, self.lives[identity], audit.START, before)

    def test_all_worlds_remain_visible_and_imposed_death_not_natural(self):
        self.assertEqual(len(self.value['comparisons']), 5)
        for key, comparison in self.value['comparisons'].items():
            self.assertNotIn(self.saved['panel'][key]['target'], comparison['matched_incumbents'])
            control, treatment = (comparison['arms'][p] for p in audit.PHASES)
            self.assertEqual(control['births'], 0)
            self.assertEqual(treatment['births'], 1)
            self.assertEqual(treatment['natural_deaths'], 0)
            self.assertEqual(treatment['focal_children'], 0)
            self.assertEqual(treatment['recruit_children'], 0)
            self.assertEqual(self.saved['runs']['treatment'][key]['result']['deaths'],
                             self.saved['runs']['control'][key]['result']['deaths'] + 1)

    def test_derived_tampering_is_rejected(self):
        old = self.value['comparisons'][self.key]['arms']['treatment']['natural_deaths']
        try:
            self.value['comparisons'][self.key]['arms']['treatment']['natural_deaths'] = old + 1
            with self.assertRaisesRegex(RuntimeError, 'comparison'):
                audit.check_value(self.value)
        finally:
            self.value['comparisons'][self.key]['arms']['treatment']['natural_deaths'] = old


if __name__ == '__main__':
    unittest.main()
