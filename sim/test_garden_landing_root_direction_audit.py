#!/usr/bin/env python3
"""First-day balances, flower gates and corruption checks without native execution."""

import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_root_direction_audit as audit

RESULT = audit.ROOT / 'benchmarks/garden-seasons/landing-root-direction-audit-results.json.gz'
RESULT_SHA = '7dafc2ee8ab59bda4d708c9625fa753d4cdb18d92066b737996f769b41f9355e'


class ContractTests(unittest.TestCase):
    def test_physical_comparison_ignores_node_renumbering_and_unused_order(self):
        event = {'tissue': 0, 'action': 1, 'at': [118, 106], 'destination': [118, 99],
                 'allocated': True, 'cost': [6, 4], 'tip': 44, 'order': [2, 1, 0, 3, 4]}
        renamed = event | {'tip': 45, 'order': [2, 3, 4, 1, 0]}
        self.assertEqual(audit.physical_purchase(event), audit.physical_purchase(renamed))
        for change in ({'destination': [115, 100]}, {'allocated': False}, {'cost': [7, 4]}, {'action': 2}):
            self.assertNotEqual(audit.physical_purchase(event), audit.physical_purchase(event | change))
        self.assertIsNone(audit.physical_purchase(None))

    def test_existing_output_rejected_before_reading_bundle(self):
        with tempfile.TemporaryDirectory() as temporary, self.assertRaisesRegex(RuntimeError, 'fresh output'):
            audit.export(Path('/missing'), Path(temporary))


@unittest.skipUnless(RESULT.exists(), 'saved first-day audit not promoted yet')
class CapturedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if audit.digest(RESULT) != RESULT_SHA:
            raise RuntimeError('captured first-day fixture changed')
        with gzip.open(RESULT, 'rt') as stream:
            cls.value = json.load(stream)

    def plant(self, arm, identity):
        return next(p for p in self.value['analysis'][arm]['plants'] if p['birth']['id'] == identity)

    def step(self, arm, tick, identity):
        return audit.plant_sample(self.value['rows'][arm][tick // audit.STEP - 1], identity)

    def test_portable_verification_does_not_start_any_process(self):
        with patch('subprocess.run', side_effect=AssertionError('unexpected process')), \
             patch('subprocess.Popen', side_effect=AssertionError('unexpected process')):
            audit.verify(RESULT)

    def test_shared_prefixes_are_one_pair_not_four_independent_trials(self):
        checks = self.value['sources']
        self.assertEqual(len(checks), 16)
        self.assertEqual(len({c['case'] for c in checks}), 4)
        self.assertEqual({c['prefix_sha256'] for c in checks}, set(audit.PREFIX_SHA.values()))
        self.assertEqual([len(self.value['rows'][a]) for a in audit.ARMS], [256, 256])
        for arm in audit.ARMS:
            rows = self.value['rows'][arm]
            self.assertEqual([rows[0][1]['sun'][0], rows[-1][1]['sun'][0]], [65, 64])

    def test_balanced_water_totals_do_not_claim_more_retained_water(self):
        old, wet = [self.value['analysis'][a]['totals']['water'] for a in audit.ARMS]
        self.assertEqual([old['income'], wet['income']], [6615, 6702])
        self.assertEqual([old['overflow'], wet['overflow']], [2945, 3053])
        self.assertEqual([old['retained'], wet['retained']], [3670, 3649])
        self.assertEqual([old['final'], wet['final']], [2286, 2262])
        self.assertEqual(self.value['comparison']['totals']['water'], {
            'initial': 0, 'income': 87, 'overflow': 108, 'retained': -21,
            'upkeep': -1, 'growth': 4, 'reproduction': 0, 'discarded': 0, 'final': -24})
        self.assertEqual([p['resources']['water']['retained'] for p in self.value['comparison']['plants']],
                         [-5, -4, -1, 0, -11])
        for arm in audit.ARMS:
            self.assertEqual(sum(p['payments'] for p in self.value['analysis'][arm]['plants']), 320)
            self.assertEqual(sum(p['unpaid']['water'] for p in self.value['analysis'][arm]['plants']), 0)
            self.assertEqual(sum(p['unpaid']['energy'] for p in self.value['analysis'][arm]['plants']), 9)

    def test_first_redirect_collects_water_before_growth_and_without_overflow(self):
        old, wet = [self.step(a, 330, 5)['resource'] for a in audit.ARMS]
        self.assertEqual([old['uptake'][1], wet['uptake'][1]], [[95, 3, 0, 0, 0, 0], [95, 6, 0, 0, 0, 0]])
        self.assertEqual([old['stages'][-1][:2], wet['stages'][-1][:2]], [[212, 98], [212, 101]])

    def test_earlier_seed_is_flower_timing_not_a_resource_gate_rescue(self):
        old, wet = [self.plant(a, 3) for a in audit.ARMS]
        self.assertEqual([old['first_flower'], wet['first_flower']], [855, 735])
        self.assertEqual([old['seeds'][0]['birth_tick'], wet['seeds'][0]['birth_tick']], [900, 780])
        self.assertEqual([old['seeds'][0]['column'], wet['seeds'][0]['column']], [8, 19])
        self.assertTrue(all(p['seeds'][0]['outcome'] == 'expired' for p in (old, wet)))
        for arm, mask, stores in (('control', 512, [243, 192]), ('candidate', 0, [245, 200])):
            row = self.step(arm, 780, 3)['reproduction']
            self.assertEqual(row['blockers'], mask)
            self.assertEqual([row['energy'], row['water']], stores)
            self.assertEqual([row['energy_required'], row['water_required']], [208, 104])
        for arm in audit.ARMS:
            self.assertEqual(len(self.plant(arm, 3)['seeds']), 3)
            seeds = [s for p in self.value['analysis'][arm]['plants'] for s in p['seeds']]
            self.assertEqual(len(seeds), 7)
            self.assertEqual(sum(s['outcome'] == 'expired' for s in seeds), 6)
            recruited = [s for s in seeds if s['outcome'] == 'germinated']
            self.assertEqual([(s['parent'], s['birth_tick'], s['child_id'], s['end_tick']) for s in recruited],
                             [(4, 3540, 6, 30210)])

    def test_shoot_change_is_in_raw_model_ranking_with_equal_local_candidates(self):
        witness = next(p for p in self.value['comparison']['plants'] if p['id'] == 3)['first']['shoot_purchase']
        self.assertEqual(witness['tick'], 585)
        self.assertEqual([witness[a]['destination'] for a in audit.ARMS], [[115, 100], [118, 99]])
        d = [next(d for d in self.value['rows'][a][38][2]['bids'] if (d['id'], d['tip']) == (3, 44))
             for a in audit.ARMS]
        self.assertEqual(d[0]['candidates'], d[1]['candidates'])
        self.assertEqual(d[1]['raw_order'], d[1]['order'])
        self.assertNotEqual(d[0]['order'], d[1]['raw_order'])
        self.assertTrue(all(not e['rewritten'] for a in audit.ARMS for p in self.value['analysis'][a]['plants']
                            for e in p['purchases'] if e['tissue'] == 0))
        self.assertNotIn('shoot_purchase', self.value['comparison']['plants'][0]['first'])
        self.assertNotIn('shoot_purchase', self.value['comparison']['plants'][4]['first'])

    def test_missing_reordered_and_boolean_tick_rejected(self):
        for alter in (lambda rows: rows.pop(), lambda rows: rows.reverse(),
                      lambda rows: rows[0][0].update(tick=True)):
            rows = copy.deepcopy(self.value['rows']['control'])
            alter(rows)
            with self.assertRaises(RuntimeError):
                audit.validate_prefix(rows)

    def test_changed_income_and_inter_step_balance_rejected(self):
        for tick, column in ((1, 1), (2, 0)):
            rows = copy.deepcopy(self.value['rows']['control'])
            rows[tick - 1][1]['plants'][0]['uptake'][1][column] += 1
            with self.assertRaisesRegex(RuntimeError, 'uptake does not balance|inter-step resource discontinuity'):
                audit.analyze_arm(rows, audit.load_input()['cases'][0]['arms']['control'], False)

    def test_corrupt_reproduction_and_direction_rejected(self):
        rows = copy.deepcopy(self.value['rows']['candidate'])
        rows[51][0]['reproduction'][2]['blockers'] = 512
        with self.assertRaisesRegex(RuntimeError, 'production gates differ'):
            audit.analyze_arm(rows, audit.load_input()['cases'][0]['arms']['candidate'], True)
        rows = copy.deepcopy(self.value['rows']['candidate'])
        direction = next(d for d in rows[38][2]['bids'] if (d['id'], d['tip']) == (3, 44))
        direction['raw_order'] = [1, 2, 3, 4, 0]
        with self.assertRaisesRegex(RuntimeError, 'wrong rewrite'):
            audit.analyze_arm(rows, audit.load_input()['cases'][0]['arms']['candidate'], True)

    def test_provenance_corrupt_prefix_and_false_summary_rejected(self):
        for key, value in (('new_simulations', 1), ('training_runs', True),
                           ('input_sha256', '0' * 64), ('window', [15, 7680])):
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, 'provenance/scope'):
                audit.check_value(self.value | {key: value})
        bad = copy.deepcopy(self.value)
        bad['sources'].pop()
        with self.assertRaisesRegex(RuntimeError, 'source coverage'):
            audit.check_value(bad)
        bad = copy.deepcopy(self.value)
        bad['rows']['control'][0][1]['plants'][0]['uptake'][1][1] += 1
        with self.assertRaisesRegex(RuntimeError, 'receipts changed'):
            audit.check_value(bad)
        bad = copy.deepcopy(self.value)
        bad['comparison']['totals']['water']['retained'] = 21
        with self.assertRaisesRegex(RuntimeError, 'summary differs'):
            audit.check_value(bad)


if __name__ == '__main__':
    unittest.main()
