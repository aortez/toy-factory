#!/usr/bin/env python3
"""Independent focal allocation arithmetic, CLI rejection, neutrality and receipts."""

import argparse
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_root_allocation as probe
from test_garden_landing_tools import run

BUILD = None
RESULT = probe.ROOT / 'benchmarks/garden-seasons/landing-root-allocation-results.json.gz'


def saved_result():
    with gzip.open(RESULT, 'rt') as stream:
        return json.load(stream)


def fixture():
    life = {k: v for k, v in probe.FOCAL.items() if k not in ('version', 'lineage')}
    life.update(id=9, death_tick=None)
    b = dict(id=9, tissue=1, action=1, depth=2, maximum_depth=9, energy=256, water=290,
             raw_priority=3, priority=32765, budget={'allocates': True, 'allowed': True},
             energy_gate={'allowed': True, 'cost': 7, 'income': 1, 'maintenance': 4},
             water_gate={'allowed': True, 'cost': 5, 'upkeep': 4, 'destination': [201, 161, 18]},
             allocation=dict(active=True, eligible=True, prefer=True, water_income=1))
    for g in probe.population.GATES: b.setdefault(g, {'allowed': True})
    return b, life, {'uptake': [[0, 1, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0]]}


class PredicateTests(unittest.TestCase):
    def test_equality_and_high_priorities(self):
        b, life, r = fixture()
        for priority in (-32768, 3, 32765, 32766, 32767):
            self.assertEqual(probe.check_priority(b, life, 406695, r, priority), max(priority, 32765))

    def test_one_unit_bill_violations_zero_income_and_guards(self):
        for fault in ('water', 'energy', 'dry', 'budget', *probe.population.GATES, 'price'):
            b, life, r = fixture()
            if fault == 'water': b['water_gate']['upkeep'] = 3
            elif fault == 'energy': b['energy_gate']['maintenance'] = 5
            elif fault == 'dry': b['water_gate']['destination'][2] = 0
            elif fault == 'price': b['water'] = 4
            else: b[fault]['allowed'] = False
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                probe.check_priority(b, life, 406695, r, 3)
        b, life, r = fixture()
        r['uptake'][1][1] = 0
        b['allocation']['water_income'] = 0
        self.assertEqual(probe.check_priority(b, life, 406695, r, 3), 32765)
        b['energy_gate']['income'] = 0
        b['allocation']['prefer'] = False
        self.assertEqual(probe.check_priority(b, life, 406695, r, 3), 3)

    def test_scope_and_receipt_corruption(self):
        for field in ('id', 'birth_tick', 'parent', 'generation', 'column', 'species'):
            b, life, r = fixture()
            life[field] += 1
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                probe.check_priority(b, life, 406695, r, 3)
        b, life, r = fixture()
        b['allocation']['active'] = False
        b['allocation']['prefer'] = False
        self.assertEqual(probe.check_priority(b, life, life['birth_tick'], r, 32767), 32767)

    def test_stable_traversal_ties_and_terminal_precedence(self):
        b, _, _ = fixture()
        first = b | {'tip': 22, 'raw_priority': 2}
        second = b | {'tip': 23, 'raw_priority': 9}
        self.assertEqual(probe.choices([first, second]), ({'tip': 23, 'eligible': True}, {'tip': 22, 'eligible': True}))
        for priority in (32766, 32767):
            terminal = b | {'tip': 24, 'action': 2, 'priority': priority, 'raw_priority': priority}
            terminal['allocation'] = dict(active=True, eligible=False, prefer=False, water_income=1)
            self.assertEqual(probe.choices([first, second, terminal])[1]['tip'], 24)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='garden-root-allocation-test-')
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

    def test_pre_focal_repeat_identity_and_exact_physical_prefix(self):
        arms = {}
        for arm in probe.ARMS:
            a, b = [self.capture(arm + '-' + label, arm) for label in probe.LABELS]
            self.assertEqual(a['result'], b['result'])
            for k in ('stand', 'adult', 'direction'):
                self.assertEqual((self.root / a['traces'][k]['path']).read_bytes(), (self.root / b['traces'][k]['path']).read_bytes())
            probe.common_result(a['result'], self.case, arm)
            analysis, observed = probe.analyze_run(self.root, a, self.case['guard'], arm == 'candidate')
            probe.population.check_analysis(analysis, a['result'])
            probe.check_allocation(observed, a['result'], self.case['guard'], arm == 'candidate')
            arms[arm] = {'runs': {'trace': a}, 'result': a['result'], 'allocation': observed}
        self.assertIsNone(probe.first_effect(self.root, arms))
        self.assertEqual(probe.common_result(arms['candidate']['result'], self.case, 'candidate'), arms['control']['result'])

    def test_trace_disabled_is_identical(self):
        a = self.capture('trace', 'candidate')
        args = a['args'].copy()
        for flag in ('--direction-trace', '--stand-trace', '--stand-start', '--stand-stop', '--adult-trace', '--adult-start', '--adult-stop'):
            j = args.index(flag)
            del args[j:j + 2]
        args.remove('--stand-dawn')
        path = self.root / 'plain'
        path.mkdir()
        (path / 'frames').mkdir()
        (path / 'model.tgl').write_bytes(probe.population.load_model()[1])
        result = json.loads(run([BUILD / 'toy-factory-garden-landing', *args], cwd=path))
        self.assertEqual(a['result'], result)

    def test_invalid_combinations_fail_before_outputs(self):
        path = self.root / 'bad'
        path.mkdir()
        (path / 'model.tgl').write_bytes(probe.population.load_model()[1])
        args = probe.arguments(self.case, 'candidate', stop=3840)
        for fault in ('scope', 'duplicate', 'wet', 'trace', 'budget', 'guard', 'selector'):
            bad = args.copy()
            if fault == 'scope': bad.remove('--root-all-offspring')
            elif fault == 'duplicate': bad += ['--root-allocation-focal']
            elif fault == 'wet': bad += ['--root-wet-direction']
            elif fault == 'trace': bad[bad.index('--stand-dawn')] = '--stand-daylight'
            elif fault == 'budget': bad[bad.index('--shoot-reserve') + 1] = 'off'
            elif fault == 'guard': bad.remove('--root-daylight-energy')
            else: bad += ['--root-choice-at', '403365', '--root-choice-lineage', '9']
            run([BUILD / 'toy-factory-garden-landing', *bad], valid=False, cwd=path)
            self.assertEqual(sorted(p.name for p in path.iterdir()), ['model.tgl'])

    def test_first_predicted_boost_and_active_observer_neutrality(self):
        # Bounded integration fixture, not a full-horizon experimental call.
        a = self.capture('active', 'candidate', stop=406800)
        analysis, observed = probe.analyze_run(self.root, a, self.case['guard'], True)
        probe.population.check_analysis(analysis, a['result'])
        probe.check_allocation(observed, a['result'], self.case['guard'], True)
        self.assertEqual(observed['first_choice'], {'id': 9, 'tick': 406695})
        args = a['args'].copy()
        for flag in ('--direction-trace', '--stand-trace', '--stand-start', '--stand-stop',
                     '--adult-trace', '--adult-start', '--adult-stop'):
            j = args.index(flag)
            del args[j:j + 2]
        args.remove('--stand-dawn')
        path = self.root / 'active-plain'
        path.mkdir()
        (path / 'frames').mkdir()
        (path / 'model.tgl').write_bytes(probe.population.load_model()[1])
        result = json.loads(run([BUILD / 'toy-factory-garden-landing', *args], cwd=path))
        self.assertEqual(a['result'], result)


@unittest.skipUnless(RESULT.exists(), 'allocation capture not yet available')
class SavedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.value = saved_result()

    def test_portable_and_corruptions(self):
        with patch('subprocess.Popen', side_effect=AssertionError('offline only')): probe.check_value(self.value)
        for fault in ('coverage', 'priority', 'repeat', 'prefix', 'conclusion'):
            # Decode an independent copy of the same full fixture. Recursive
            # Python deepcopy dominates this test on these large JSON trees.
            bad = saved_result()
            e = bad['cases'][0]
            if fault == 'coverage': e['arms']['candidate']['allocation']['focal_frames'].pop()
            elif fault == 'priority':
                next(f for f in e['arms']['candidate']['allocation']['focal_frames'] if f['bids'])['bids'][0]['priority'] += 1
            elif fault == 'repeat': e['arms']['candidate']['runs']['repeat']['frame']['sha256'] = '0' * 64
            elif fault == 'prefix': e['first_effect']['matching_prior_samples'] += 1
            else: bad['conclusion']['supports_broader_trial'] = not bad['conclusion']['supports_broader_trial']
            with self.subTest(fault=fault), self.assertRaises(RuntimeError): probe.check_value(bad)
            # Do not retain the previous corrupt tree while decoding the next.
            del bad, e

    def test_focal_improvement_does_not_hide_population_harm(self):
        self.assertEqual(self.value['conclusion'], dict(focal_pairs_improving=4, focal_pairs_passing=4,
                                                       population_pairs_passing=0, supports_broader_trial=False))
        for e in self.value['cases']:
            self.assertEqual(e['arms']['candidate']['allocation']['counts']['boosted_bids'], 1)
            self.assertEqual(e['arms']['candidate']['allocation']['counts']['changed_choices'], 1)
            self.assertFalse(e['comparison']['checks']['no_worse_water_rate'])
            for a in probe.ARMS:
                f = e['focal']['full'][a]
                equal = e['focal']['equal'][a]
                p = next(p for p in e['arms'][a]['analysis']['plants'] if p['life']['id'] == 9)
                self.assertEqual((p['last_body']['nodes'], p['last_body']['roots']), (32, 4 if a == 'candidate' else 3))
                self.assertEqual(f['seeds'], 2 if a == 'candidate' else 1)
                self.assertEqual(f['account']['unpaid']['energy'], 0)
                self.assertEqual(equal['account']['payments'], 895)
                if a == 'candidate':
                    self.assertEqual(equal['account']['unpaid']['water'], 0)
                    self.assertEqual(equal['account']['resources']['water']['final'], 22)
                else:
                    self.assertEqual(f['life']['death_tick'], 457020)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path, required=True)
    args, remaining = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *remaining])
