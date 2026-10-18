"""Synthetic score, family-status and bounded-runner checks; no native calls."""

import copy
from fractions import Fraction
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run_generalization as experiment


def history(call):
    count = dict(experiment.pilot.LAYOUTS)[call['layout']]
    return dict(complete=True, ledger_start_tick=0, ticks=608 * experiment.pilot.DAY,
        seed=call['seed'], scenario=call['layout'], candidate_founder=call['founder'],
        family_roots=list(range(1, count + 1)), seeds=[],
        lineages=[dict(id=i, parent=0, birth_tick=0, death_tick=None, environmental_death=False,
                       generation=0, species=0, column=i, seeds_created=0, late_seeds_created=0)
                  for i in range(1, count + 1)])


class PlanTests(unittest.TestCase):
    def test_roster_and_confirmation_mapping(self):
        calls = experiment.plan()
        self.assertEqual(len(calls), 123)
        self.assertEqual([c['id'] for c in calls], [f'call{i:04d}' for i in range(1, 124)])
        self.assertEqual([sum(c['phase'] == phase for c in calls) for phase in ('anchor', 'panel', 'confirm')],
                         [3, 96, 24])
        self.assertEqual(sum(c['capture'] for c in calls), 99)
        lookup = experiment.panel_lookup()
        self.assertEqual(len(lookup), 96)
        for call in calls[99:]:
            self.assertEqual(call['founder'], 1)
            self.assertIn((call['model'], call['seed'], call['layout'], 1), lookup)

    def test_exact_archived_models(self):
        saved = experiment.baseline()
        expected = ('be37b3c3c10356e9b58922893aa875b598517a898dcc2b7bad39edac11f22d75',
                    '8ad9cc95d8b5469b5bdd3159b9d69598da8973b9a79df813dce626f257a7caa1',
                    '70634b853f9d0b1e46d2ca40130d1aeabeaa75bdf91ef10307e072dff6ebb1c7')
        self.assertEqual(tuple(experiment.sha(saved['models'][name]) for name in experiment.MODELS), expected)
        self.assertEqual([len(saved['anchors'][name]['pixels']) for name in experiment.MODELS], [115200] * 3)

    def test_seed_derivation_and_token_boundaries(self):
        seeds = tuple(format(int.from_bytes(hashlib.sha256(
            f'toy-factory/leaf-family-generalization-v1/weather-{i}'.encode()).digest()[:4], 'little'), '08x')
            for i in range(1, 5))
        self.assertEqual(seeds, experiment.SEEDS)
        token = seeds[0].encode()
        self.assertTrue(experiment.previous.seed_occurs(b'"' + token + b'"', (token,)))
        self.assertFalse(experiment.previous.seed_occurs(b'f' + token + b'f', (token,)))


class StatusTests(unittest.TestCase):
    def fixture(self):
        return history(dict(seed='00000001', layout='rainfed', founder=1))

    def test_living_family(self):
        status = experiment.family_status(self.fixture())
        self.assertEqual((status['living'], status['pending'], status['extinct'], status['dormant']),
                         (1, 0, False, False))
        self.assertIsNone(status['extinction_tick'])

    def test_dormant_is_not_extinct(self):
        value = self.fixture()
        value['lineages'][0]['death_tick'] = 100
        value['seeds'] = [dict(parent=1, end_tick=None), dict(parent=2, end_tick=None)]
        status = experiment.family_status(value)
        self.assertEqual((status['living'], status['pending'], status['extinct'], status['dormant']),
                         (0, 1, False, True))
        self.assertIsNone(status['extinction_tick'])

    def test_extinction_waits_for_last_family_seed(self):
        value = self.fixture()
        value['lineages'][0]['death_tick'] = 100
        value['seeds'] = [dict(parent=1, end_tick=200), dict(parent=2, end_tick=None)]
        status = experiment.family_status(value)
        self.assertTrue(status['extinct'])
        self.assertEqual(status['extinction_tick'], 200)

    def test_founder_survival_boundary_and_descendant_ownership(self):
        value = self.fixture()
        value['lineages'][0]['death_tick'] = 16 * experiment.pilot.DAY
        value['lineages'].append(dict(id=4, parent=1, death_tick=None))
        value['family_roots'].append(1)
        status = experiment.family_status(value)
        self.assertEqual(status['founder_survival'], {'1': True, '16': False, '32': False})
        self.assertEqual(status['living'], 1)
        self.assertFalse(status['extinct'])


class AnalysisTests(unittest.TestCase):
    def test_primary_gain_uses_actual_renewal_and_exact_weights(self):
        calls = [c for c in experiment.plan() if c['phase'] == 'panel']
        values = {c['id']: history(c) for c in calls}
        ref = experiment.panel_lookup()[('s1-g3-c4', experiment.SEEDS[0], 'rainfed', 1)]
        value = values[ref]
        day = experiment.pilot.DAY
        for identity, parent, birth, generation in ((4, 1, 200, 1), (5, 4, 240, 2)):
            value['lineages'].append(dict(id=identity, parent=parent, birth_tick=birth * day, death_tick=None,
                environmental_death=False, generation=generation, species=0, column=1,
                seeds_created=0, late_seeds_created=0))
            value['family_roots'].append(1)
            value['seeds'].append(dict(parent=parent, birth_tick=(birth - 1) * day,
                end_tick=birth * day, child_id=identity, lifetime_ecology_ticks=8192,
                generation=generation, species=0, column=1, outcome='germinated'))
            value['lineages'][parent - 1]['seeds_created'] += 1
            value['lineages'][parent - 1]['late_seeds_created'] += 1
        result = experiment.analyze(values)
        candidate = result['models']['s1-g3-c4']
        self.assertEqual(Fraction(*candidate['score']['key'][0]), Fraction(1, 288))
        self.assertEqual(candidate['score']['roles_with_renewal'], 1)
        self.assertEqual(result['comparisons']['s1-g3-c4']['paired_primary'],
                         dict(improved=1, tied=31, regressed=0))
        self.assertTrue(result['comparisons']['s1-g3-c4']['primary_gain'])
        self.assertEqual(result['comparisons']['s1-g3-c4']['new_extinctions'], [])

    def test_condition_weighting_and_paired_extinctions(self):
        calls = [c for c in experiment.plan() if c['phase'] == 'panel']
        values = {c['id']: history(c) for c in calls}
        for layout in ('rainfed', 'rainfed-crowded'):
            ref = experiment.panel_lookup()[('s1-g3-c4', experiment.SEEDS[0], layout, 1)]
            values[ref]['lineages'][0]['death_tick'] = 15
        before = copy.deepcopy(values)
        result = experiment.analyze(values)
        self.assertEqual(values, before)
        candidate = result['models']['s1-g3-c4']
        self.assertEqual(candidate['extinct_families'], 2)
        self.assertEqual(Fraction(*candidate['weighted_extinction']), Fraction(1, 15))
        self.assertEqual(candidate['score']['key'], [[0, 1], [0, 1]])
        self.assertEqual(result['comparisons']['s1-g3-c4']['paired_primary'],
                         dict(improved=0, tied=32, regressed=0))
        self.assertEqual(len(result['comparisons']['s1-g3-c4']['new_extinctions']), 2)
        self.assertFalse(result['comparisons']['s1-g3-c4']['primary_gain'])
        self.assertIsNone(result['selected_model'])

    def test_missing_panel_role_is_not_a_zero(self):
        with self.assertRaisesRegex(ValueError, 'incomplete panel roster'):
            experiment.analyze({})


class RunnerTests(unittest.TestCase):
    def test_failed_batch_stops_submissions(self):
        submitted = []
        def execute(call):
            if call['id'] == 1:
                raise ValueError('failed call')
            return call
        with self.assertRaises(ValueError):
            experiment.batches([dict(id=i) for i in range(8)], submitted.append,
                               execute, lambda call, value: None)
        self.assertEqual(submitted, [dict(id=0), dict(id=1)])

    def test_invalid_batch_stops_submissions(self):
        submitted = []
        def validate(call, value):
            raise ValueError('invalid result')
        with self.assertRaises(ValueError):
            experiment.batches([dict(id=i) for i in range(8)], submitted.append, lambda call: call, validate)
        self.assertEqual(submitted, [dict(id=0), dict(id=1)])

    def test_next_batch_waits_for_validation(self):
        events = []
        experiment.batches([dict(id=i) for i in range(4)], lambda c: events.append(('submit', c)),
                           lambda c: c, lambda c, v: events.append(('check', c)))
        self.assertEqual([kind for kind, _ in events], ['submit', 'submit', 'check', 'check'] * 2)

    def test_all_limits(self):
        with tempfile.TemporaryDirectory(prefix='leaf-generalization-limits-') as temporary:
            limits = experiment.Limits(Path(temporary), clock=lambda: 1.0)
            limits.count = 123
            with self.assertRaises(ValueError):
                limits.submit()
            limits.count, limits.first = 0, -2699.0
            with self.assertRaises(ValueError):
                limits.submit()
            limits.first = None
            with patch.object(limits, 'size', return_value=experiment.MAX_BYTES):
                with self.assertRaises(ValueError):
                    limits.submit()
            with patch.object(experiment.shutil, 'disk_usage') as disk:
                disk.return_value.free = 0
                with self.assertRaises(ValueError):
                    limits.submit()


if __name__ == '__main__':
    unittest.main()
