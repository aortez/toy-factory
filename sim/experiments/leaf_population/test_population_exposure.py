"""Spatial joins, phase boundaries, and exact offline attribution."""

from copy import deepcopy
import json
import subprocess
import unittest
from unittest import mock
from xml.etree import ElementTree

import exposure_figure
import population_exposure as exposure
from test_population_foliage import fixture

PUBLISHED = exposure.collect.ROOT / 'benchmarks/garden-seasons/leaf-population-exposure.json'
FIGURE = exposure.collect.ROOT / 'benchmarks/garden-seasons/frames/leaf-population-exposure.svg'


class ExposureTests(unittest.TestCase):
    def test_phase_zero_closes_night_not_the_dawn_window(self):
        self.assertEqual([exposure.phase_end(p) for p in (0, 1, 32, 33, 64, 128, 129, 224, 225, 255)],
                         [256, 32, 32, 64, 64, 128, 160, 224, 256, 256])
        for phase in (-1, 256, True, 1.5):
            with self.subTest(phase=phase), self.assertRaises(ValueError):
                exposure.phase_end(phase)

    def test_phase_cells_and_leaf_totals_conserve_all_samples(self):
        case = exposure.attribute(fixture()[0])
        self.assertEqual(case['day']['samples'], 24 * 256)
        self.assertEqual([p['samples'] for p in case['periods']], [24 * 32] * 8)
        self.assertEqual(case['periods'][0]['first_tick'], exposure.foliage.DAWN + 15)
        self.assertEqual(case['periods'][0]['last_tick'], exposure.foliage.OPENING)
        self.assertEqual(case['periods'][-1]['last_tick'], exposure.foliage.DAWN)
        self.assertGreater(case['periods'][1]['first_tick'], exposure.foliage.OPENING)
        self.assertLess(case['periods'][2]['last_tick'], exposure.foliage.DAWN)
        self.assertLess(case['periods'][3]['last_tick'], exposure.foliage.DAWN)
        self.assertEqual(case['leaves'][0]['node_first'], 8)
        self.assertEqual(case['leaves'][0]['node_last'], 0)
        self.assertEqual(case['day'], exposure.total([leaf['day'] for leaf in case['leaves']]))

    def test_colocated_leaves_are_not_deduplicated(self):
        data = fixture()[0]
        for r in data['rows']:
            r['leaves'][1][1:5] = r['leaves'][0][1:5]
        case = exposure.attribute(data)
        cell, = [c for c in case['cells'] if c['ordinals'] == [0, 1]]
        self.assertEqual(len(case['cells']), 23)
        self.assertEqual(cell['periods'][0]['samples'], 64)
        self.assertEqual(cell['periods'][0]['weighted_numerator'],
                         sum(leaf['periods'][0]['weighted_numerator'] for leaf in case['leaves'][:2]))

    def test_fractional_contributions_are_not_individually_rounded(self):
        values = exposure.metrics([(64, 128, 255), (64, 128, 255)])
        self.assertEqual(values['weighted_numerator'], 256)
        self.assertEqual(values['light_bands'], 2)
        self.assertEqual(values['unshaded_bands'], 6)
        self.assertEqual(values['weighted_numerator'] // 255, 1)
        for samples in ([], [(256, 0, 255)], [(64, -1, 255)], [(64, 100, 63)]):
            with self.subTest(samples=samples), self.assertRaises(ValueError):
                exposure.metrics(samples)

    def test_missing_reordered_or_moving_body_is_rejected(self):
        data = fixture()[0]
        for change in ('missing', 'duplicate', 'phase', 'position', 'order'):
            broken = deepcopy(data)
            if change == 'missing':
                broken['rows'].pop()
            elif change == 'duplicate':
                broken['rows'][1] = deepcopy(broken['rows'][0])
            elif change == 'phase':
                broken['rows'][1]['phase'] = 0
            elif change == 'position':
                broken['rows'][1]['leaves'][0][1] += 1
            else:
                broken['rows'][1]['leaves'].reverse()
            with self.subTest(change=change), self.assertRaises(ValueError):
                exposure.attribute(broken)


class PublishedExposureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native calls forbidden')):
            cls.result = exposure.diagnose()

    def test_exact_published_derivation_and_figure(self):
        self.assertEqual(self.result, json.loads(PUBLISHED.read_bytes()))
        self.assertEqual(self.result['native_calls'], 0)
        self.assertEqual(len(self.result['inputs']), 2)
        svg = exposure_figure.render(self.result)
        self.assertEqual(svg, FIGURE.read_bytes())
        root = ElementTree.fromstring(svg)
        self.assertEqual(root.attrib['viewBox'], '0 0 1040 800')
        self.assertNotIn(b'<script', svg)

    def test_upper_canopy_is_similar_and_lower_canopy_explains_gap(self):
        a, b = (self.result['cases'][p] for p in ('original', 'fewest'))
        self.assertEqual([g['weighted_numerator'] for g in a['dawn_by_height']], [19296, 21101])
        self.assertEqual([g['weighted_numerator'] for g in b['dawn_by_height']], [19797, 1816])
        self.assertEqual([g['light_bands'] for g in a['dawn_by_height']], [118, 223])
        self.assertEqual([g['light_bands'] for g in b['dawn_by_height']], [105, 80])
        self.assertEqual([g['leaves'] for g in a['dawn_by_height']], [7, 17])
        self.assertEqual([g['leaves'] for g in b['dawn_by_height']], [11, 15])
        self.assertEqual(a['dawn_contributing_leaves'], b['dawn_contributing_leaves'])
        self.assertEqual(b['dawn_contributing_leaves'], 11)
        lower = b['dawn_by_height'][1]
        self.assertEqual((lower['dark_leaves'], lower['lit_zero_income_leaves'], lower['contributing_leaves']), (8, 5, 2))
        for case in (a, b):
            self.assertEqual(exposure.total(case['dawn_by_height']),
                             {k: case['periods'][0][k] for k in exposure.ADDITIVE})
            for g in case['dawn_by_height']:
                self.assertEqual(g['dark_leaves'] + g['lit_zero_income_leaves'] + g['contributing_leaves'], g['leaves'])

    def test_phase_advantage_reverses_after_the_opening(self):
        a, b = (self.result['cases'][p] for p in ('original', 'fewest'))
        self.assertEqual([p['light_bands'] for p in a['periods']], [341, 1021, 821, 146, 0, 0, 0, 0])
        self.assertEqual([p['light_bands'] for p in b['periods']], [185, 1056, 901, 180, 0, 0, 0, 0])
        self.assertEqual(sum(p['light_bands'] for p in a['periods']), 2329)
        self.assertEqual(sum(p['light_bands'] for p in b['periods']), 2322)
        self.assertEqual((len(a['dawn_dark_but_later_lit']), len(b['dawn_dark_but_later_lit'])), (6, 10))

    def test_leftmost_original_column_accounts_for_most_dawn_energy(self):
        a = self.result['cases']['original']
        left = [leaf['periods'][0] for leaf in a['leaves'] if leaf['column'] == 0]
        self.assertEqual(len(left), 8)
        self.assertEqual(exposure.total(left)['weighted_numerator'], 30448)
        self.assertGreater(30448 / a['periods'][0]['weighted_numerator'], 0.75)


if __name__ == '__main__':
    unittest.main()
