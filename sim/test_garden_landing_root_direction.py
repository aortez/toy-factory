#!/usr/bin/env python3
"""Root direction eligibility, repeated CLI traces and independent receipt checks."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_root_direction as probe
from test_garden_landing_directions import fixture
from test_garden_landing_tools import run

BUILD = None
RESULT = probe.ROOT / 'benchmarks/garden-seasons/landing-root-direction-results.json.gz'


def bid_fixture():
    b, d = fixture()
    b.update(depth=1, maximum_depth=9, energy=256)
    b['water_gate'].update(allowed=True, reserve=4, wet_root=False)
    for gate in probe.population.GATES:
        if gate not in b: b[gate] = {'allowed': True}
    b['energy_gate']['cost'] = 9
    b['water'] = 9
    d['raw_order'] = list(d['order'])
    d['order'] = [1, 0, 2]
    b['water_gate'].update(destination=[104, 150, 9], wet_root=True, reserve=1)
    return b, d, {'species': 0}


class PolicyTests(unittest.TestCase):
    def test_higher_capped_uptake_and_stable_ties(self):
        b, d, life = bid_fixture()
        self.assertEqual(probe.check_bid(b, d, life, True), {'changed': True, 'before': 0, 'after': 1})
        raw, original = probe.raw_pair(b, d, True)
        self.assertFalse(raw['water_gate']['wet_root'])
        self.assertEqual(raw['water_gate']['reserve'], 4)
        d['candidates'][0][5] = 3
        d['order'] = [0, 1, 2]
        b['water_gate'].update(destination=[100, 149, 3], wet_root=False, reserve=4)
        self.assertFalse(probe.check_bid(b, d, life, True)['changed'])
        d['candidates'][0][5] = 2
        b['water_gate']['destination'][2] = 2
        life['species'] = 2
        self.assertFalse(probe.check_bid(b, d, life, True)['changed'])

    def test_rejected_bid_cannot_be_unlocked_by_wet_root_discount(self):
        b, d, life = bid_fixture()
        b['water'] = 8
        with self.assertRaises(RuntimeError): probe.check_bid(b, d, life, True)
        b, d = probe.raw_pair(b, d, True)
        d['raw_order'] = list(d['order'])
        self.assertFalse(probe.check_bid(b, d, life, True)['changed'])

    def test_other_gates_remain_out_of_scope(self):
        for gate in probe.population.GATES:
            if gate == 'water_gate': continue
            b, d, life = bid_fixture()
            b[gate]['allowed'] = False
            with self.subTest(gate=gate), self.assertRaises(RuntimeError): probe.check_bid(b, d, life, True)
        b, d, life = bid_fixture()
        b['energy'] = 0
        with self.assertRaises(RuntimeError): probe.check_bid(b, d, life, True)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='garden-root-direction-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.case = probe.cases()[0]

    def capture(self, name, arm, stop=3840):
        path = self.root / name
        path.mkdir()
        (path / 'frames').mkdir()
        (path / 'model.tgl').write_bytes(probe.population.load_model()[1])
        args = probe.arguments(self.case, arm, stop=stop)
        result = json.loads(run([BUILD / 'toy-factory-garden-landing', *args], cwd=path))
        traces = {kind: {'path': name + '/' + args[args.index('--' + kind + '-trace') + 1]}
                  for kind in ('stand', 'adult', 'direction')}
        return {'result': result, 'traces': traces, 'args': args}

    def test_full_day_repeat_receipts_and_first_effect(self):
        arms = {}
        for arm in probe.ARMS:
            a, b = [self.capture(arm + '-' + label, arm) for label in probe.LABELS]
            self.assertEqual(a['result'], b['result'])
            for kind in ('stand', 'adult', 'direction'):
                self.assertEqual((self.root / a['traces'][kind]['path']).read_bytes(),
                                 (self.root / b['traces'][kind]['path']).read_bytes())
            probe.common_result(a['result'], self.case, arm)
            analysis = probe.population.analyze_receipts(
                *(self.root / a['traces'][k]['path'] for k in ('stand', 'adult')), a['result'], self.case['guard'])
            probe.population.check_analysis(analysis, a['result'])
            observed = probe.analyze_directions(self.root, a, self.case['guard'], arm == 'candidate')
            arms[arm] = {'runs': {'trace': a}, 'directions': observed, 'result': a['result']}
        self.assertEqual(arms['control']['directions']['counts']['rewritten_bids'], 0)
        self.assertGreater(arms['candidate']['directions']['counts']['changed_purchases'], 0)
        effect = probe.first_effect(self.root, arms)
        probe.check_effect(effect, arms)
        bad = copy.deepcopy(effect)
        bad['matching_prior_samples'] += 1
        with self.assertRaises(RuntimeError): probe.check_effect(bad, arms)
        bad = copy.deepcopy(arms['candidate']['directions'])
        bad['changes'].pop()
        with self.assertRaises(RuntimeError): probe.check_directions(bad, arms['candidate']['result'], self.case['guard'], True)

    def test_trace_disabled_is_observationally_identical(self):
        a = self.capture('trace', 'candidate')
        args = a['args'].copy()
        for flag in ('--direction-trace', '--stand-trace', '--stand-start', '--stand-stop',
                     '--adult-trace', '--adult-start', '--adult-stop'):
            j = args.index(flag)
            del args[j:j + 2]
        args.remove('--stand-dawn')
        path = self.root / 'plain'
        path.mkdir()
        (path / 'frames').mkdir()
        (path / 'model.tgl').write_bytes(probe.population.load_model()[1])
        result = json.loads(run([BUILD / 'toy-factory-garden-landing', *args], cwd=path))
        self.assertEqual(a['result'], result)

    def test_invalid_scope_and_duplicate_flag_rejected(self):
        path = self.root / 'bad'
        path.mkdir()
        (path / 'model.tgl').write_bytes(probe.population.load_model()[1])
        args = probe.arguments(self.case, 'candidate', stop=3840)
        for kind in ('missing_scope', 'duplicate', 'wrong_trace'):
            bad = args.copy()
            if kind == 'missing_scope': bad.remove('--root-all-offspring')
            elif kind == 'duplicate': bad += ['--root-wet-direction']
            else: bad[bad.index('--stand-dawn')] = '--stand-daylight'
            run([BUILD / 'toy-factory-garden-landing', *bad], valid=False, cwd=path)
            self.assertFalse((path / 'direction.jsonl').exists())


@unittest.skipUnless(RESULT.exists(), 'root direction capture not yet available')
class SavedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(RESULT, 'rt') as stream: cls.value = json.load(stream)

    def test_portable_verification_without_process_execution(self):
        with patch('subprocess.Popen', side_effect=AssertionError('offline only')): probe.check_value(self.value)
        bad = copy.deepcopy(self.value)
        bad['cases'][0]['arms']['candidate']['directions']['changes'].pop()
        with self.assertRaises(RuntimeError): probe.check_value(bad)

    def test_frozen_population_tradeoffs_and_retained_water(self):
        expected = [
            (5, 6, 18, 13, 116757, 123215, 318, 63),
            (7, 5, 22, 16, 160945, 131374, 300, 65),
            (7, 5, 20, 16, 136470, 120372, 313, 56),
            (5, 6, 23, 17, 152374, 140683, 320, 67),
        ]
        for e, wanted in zip(self.value['cases'], expected, strict=True):
            a, b = [e['arms'][arm] for arm in probe.ARMS]
            retained = [v['resources']['offspring']['resources']['water']['income'] -
                        v['resources']['offspring']['resources']['water']['overflow'] for v in (a, b)]
            self.assertEqual((a['metrics']['living'], b['metrics']['living'],
                              a['metrics']['seed_parents'], b['metrics']['seed_parents'], *retained,
                              b['directions']['counts']['rewritten_bids'],
                              b['directions']['counts']['changed_purchases']), wanted)
            self.assertFalse(e['comparison']['passes_harm_screen'])
            self.assertEqual(e['birth_matching']['matched'], [[i, i] for i in (1, 2, 3, 4, 5, 6, 9)])

    def test_first_purchase_is_same_tip_and_price_not_new_permission(self):
        for e in self.value['cases']:
            f = e['first_effect']
            self.assertEqual((f['tick'], f['id'], f['matching_prior_samples']), (315, 5, 20))
            p = next(p for p in e['arms']['candidate']['directions']['changes'] if (p['tick'], p['id']) == (315, 5))
            d = next(d for d in p['directions'] if d['tip'] == p['selected']['tip'])
            self.assertEqual((d['at'], d['raw_order'], d['order']), ([199, 149], [1, 2, 0], [2, 1, 0]))
            self.assertEqual(d['candidates'][1][2:6], [199, 155, 0, 0])
            self.assertEqual(d['candidates'][2][2:6], [203, 154, 0, 6])
            self.assertEqual(p['resource']['stages'][2][:2], [212, 100])
            self.assertEqual(p['resource']['stages'][3][:2], [204, 95])

    def test_corrupt_rewrite_identity_and_first_effect_rejected(self):
        e = self.value['cases'][0]
        changed = e['arms']['candidate']['directions']['changes'][0]
        life = next(p for p in e['arms']['candidate']['result']['lineages'] if p['id'] == changed['id'])
        bad = copy.deepcopy(changed)
        bad['purchase_changed'] = not bad['purchase_changed']
        with self.assertRaises(RuntimeError): probe.check_change(bad, life, e['case']['guard'])
        bad = copy.deepcopy(changed)
        d = next(d for d in bad['directions'] if d['tip'] in bad['changed'])
        d['order'] = d['raw_order']
        with self.assertRaises(RuntimeError): probe.check_change(bad, life, e['case']['guard'])
        bad = copy.deepcopy(e['first_effect'])
        p = next(p for p in bad['control']['adult']['plants'] if p['id'] == bad['id'])
        p['stages'][2][1] += 1
        with self.assertRaises(RuntimeError): probe.check_effect(bad, e['arms'])
        bad = dict(e['arms']['candidate']['result'], run_hash='00000000')
        with self.assertRaises(RuntimeError): probe.common_result(bad, e['case'], 'candidate')
        with self.assertRaises(RuntimeError): probe.check_value({**self.value, 'full_replays': 17})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path, required=True)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *rest])
