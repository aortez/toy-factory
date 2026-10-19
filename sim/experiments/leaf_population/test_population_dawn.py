"""Matched coverage, per-leaf normalization, and offline evidence reproduction."""

from copy import deepcopy
import json
import subprocess
import unittest
from unittest import mock

import local_results
import population_dawn as dawn

PUBLISHED = dawn.collect.ROOT / 'benchmarks/garden-seasons/leaf-population-dawn.json'


def fixture():
    cases = {}
    for policy, lineage in dawn.LINEAGES.items():
        leaves, condition = (24, 2400) if policy == 'original' else (26, 2548)
        rows = []
        for day in range(dawn.FIRST, dawn.END):
            energy = dict(before=100, income=265, overflow=0, endowment=0, upkeep_due=256,
                          upkeep_paid=256, growth=0, seeds=0, discarded=0, after=100, repair=9)
            water = energy | dict(income=261, repair=5)
            rows.append(dict(day=day, lineage=lineage, first_tick=day * dawn.score.DAY + dawn.score.STEP,
                last_tick=(day + 1) * dawn.score.DAY, samples=256, maintenance=64, born=False, died=False,
                nodes_before=32, nodes_after=32, leaves_before=leaves, leaves_after=leaves,
                condition_before=condition, condition_after=condition, energy=energy, water=water,
                renewals=1, energy_short=0, water_short=0))
        cases[policy] = dict(resources=dict(plant_days=rows), final=dict(family_roots=[2] * lineage,
            lineages=[dict(id=lineage, species=1, birth_tick=64 * dawn.score.DAY, death_tick=None)]))
    return cases


class DawnAccountingTests(unittest.TestCase):
    def test_mean_condition_requires_a_real_leaf_denominator(self):
        self.assertEqual(dawn.mean_condition(2400, 24), 100)
        for condition, leaves in ((0, 0), (0, -1), (-1, 24), (256, 1), (True, 1), (10, True)):
            with self.subTest(condition=condition, leaves=leaves), self.assertRaises(ValueError):
                dawn.mean_condition(condition, leaves)

    def test_normalization_and_flows_not_summed_stocks(self):
        result = dawn.compare_days(fixture())
        self.assertEqual(result['days'], 104)
        self.assertEqual([r['day'] for r in result['focal_days']], [151, 152, 153])
        self.assertEqual(result['comparisons']['endpoint_mean_condition'],
                         dict(original_higher=104, equal=0, fewest_higher=0))
        for case in result['cases'].values():
            self.assertEqual(case['totals']['energy']['before'], 100)
            self.assertEqual(case['totals']['energy']['after'], 100)
            self.assertEqual(case['totals']['energy']['income'], 104 * 265)
            self.assertEqual(case['totals']['renewals'], 104)

    def test_income_and_condition_are_independent_comparisons(self):
        cases = fixture()
        for row in cases['fewest']['resources']['plant_days']:
            row['energy'].update(income=266, overflow=1)
        result = dawn.compare_days(cases)
        self.assertEqual(result['comparisons']['energy_income'], dict(original_higher=0, equal=0, fewest_higher=104))
        self.assertEqual(result['comparisons']['endpoint_mean_condition']['original_higher'], 104)

    def test_missing_duplicate_or_partial_day_rejected(self):
        cases = fixture()
        rows = cases['original']['resources']['plant_days']
        for replacement in (rows[:-1], rows + [rows[-1]], list(reversed(rows))):
            broken = deepcopy(cases)
            broken['original']['resources']['plant_days'] = replacement
            with self.assertRaisesRegex(ValueError, 'coverage'):
                dawn.compare_days(broken)
        for fields in (dict(samples=255), dict(born=True), dict(first_tick=0)):
            broken = deepcopy(cases)
            broken['original']['resources']['plant_days'][0].update(fields)
            with self.assertRaisesRegex(ValueError, 'partial'):
                dawn.compare_days(broken)

    def test_resource_discontinuity_and_wrong_family_rejected(self):
        cases = fixture()
        cases['original']['resources']['plant_days'][1]['energy']['before'] = 99
        with self.assertRaisesRegex(ValueError, 'continuity'):
            dawn.compare_days(cases)
        cases = fixture()
        cases['fewest']['final']['family_roots'][-1] = 1
        with self.assertRaisesRegex(ValueError, 'lineage'):
            dawn.compare_days(cases)


@local_results.needs('leaf-population-dawn.json', 'leaf-population-reproduction-results.json.gz')
class PublishedDawnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native calls forbidden')):
            cls.result = dawn.diagnose()

    def test_exact_derivation_from_two_archives(self):
        self.assertEqual(self.result, json.loads(PUBLISHED.read_bytes()))
        self.assertEqual(self.result['native_calls'], 0)
        self.assertEqual(len(self.result['inputs']), 9)
        self.assertEqual(self.result['matched']['days'], 104)

    def test_full_window_is_not_a_selected_good_day(self):
        matched = self.result['matched']
        self.assertEqual(matched['comparisons'], dict(
            energy_income=dict(original_higher=96, equal=0, fewest_higher=8),
            endpoint_mean_condition=dict(original_higher=95, equal=0, fewest_higher=9),
            renewals=dict(original_higher=63, equal=12, fewest_higher=29)))
        a, b = (matched['cases'][p] for p in ('original', 'fewest'))
        self.assertEqual((a['totals']['energy']['income'], b['totals']['energy']['income']), (131091, 117771))
        self.assertEqual((a['totals']['renewals'], b['totals']['renewals']), (991, 852))
        self.assertEqual((a['totals']['energy']['seeds'], b['totals']['energy']['seeds']), (432, 0))
        self.assertEqual((a['plant']['column'], b['plant']['column']), (0, 7))
        self.assertEqual((a['age_at_focal_ticks'], b['age_at_focal_ticks']), (219105, 333960))

    def test_focal_foliage_and_income_not_just_leaf_count(self):
        day = self.result['matched']['focal_days'][1]
        a, b = day['original'], day['fewest']
        self.assertEqual((a['leaves_before'], b['leaves_before']), (24, 26))
        self.assertEqual((a['condition_before'], b['condition_before']), (3227, 2421))
        self.assertEqual((a['energy']['income'], b['energy']['income']), (1462, 1252))
        self.assertEqual((a['energy']['repair'], b['energy']['repair']), (135, 81))
        self.assertEqual((a['energy']['seeds'], b['energy']['seeds']), (48, 0))
        self.assertGreater(a['mean_condition_before'], b['mean_condition_before'])

    def test_dawn_rows_preserve_different_bank_histories(self):
        rows = self.result['dawn']
        self.assertEqual([r['original']['energy'] for r in rows], [175, 200, 240, 231])
        self.assertEqual([r['fewest']['energy'] for r in rows], [125, 139, 168, 204])
        self.assertEqual([r['original']['seed_count'] for r in rows], [6, 6, 6, 8])
        self.assertEqual([r['fewest']['seed_count'] for r in rows], [8, 8, 7, 8])
        self.assertTrue(rows[2]['original']['produced'])
        self.assertEqual(rows[2]['fewest']['blockers'], 128)

    def test_missing_dawn_receipt_and_mismatched_thresholds_rejected(self):
        reproduction = dict(openings=[dict(tick=r['tick'], visits=[r['original']]) for r in self.result['dawn']])
        steps = dict(rows=[dict(tick=r['tick'], visit=r['fewest'],
            energy=dict(points=[0, 0, 0, 0, r['fewest']['energy']]),
            water=dict(points=[0, 0, 0, 0, r['fewest']['water']]),
            condition_before=r['fewest']['condition_before'], leaves_before=26) for r in self.result['dawn']])
        self.assertEqual(len(dawn.dawn_rows(reproduction, steps)), 4)
        with self.assertRaisesRegex(ValueError, 'missing dawn'):
            dawn.dawn_rows(reproduction, dict(rows=steps['rows'][1:]))
        broken = deepcopy(steps)
        broken['rows'][0]['visit']['energy_required'] += 1
        with self.assertRaisesRegex(ValueError, 'thresholds'):
            dawn.dawn_rows(reproduction, broken)


if __name__ == '__main__':
    unittest.main()
