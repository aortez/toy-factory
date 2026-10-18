"""Ray geometry, source caps, snapshot ablations, and trace corruption guards."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import population_canopy as canopy
from test_population_foliage import fixture as foliage_fixture


def fixture():
    leaves = foliage_fixture()[0]
    rows = []
    for leaf in leaves['rows']:
        if leaf['tick'] not in canopy.TICKS:
            continue
        strength = 24 + leaf['phase'] * 3
        leaf['strength'] = strength
        sources = []
        for f in leaf['leaves']:
            f[5] = strength
            sources.append([19, f[0], f[3], f[4], 38 * f[6] // 255, 12 * f[6] // 255, False])
        ray = 12 - (leaf['phase'] * 24 + 64) // 128
        cells = canopy.field(sources)
        rows.append(dict(tick=leaf['tick'], phase=leaf['phase'], strength=strength, ray=ray, sources=sources,
            light=[canopy.cast(cells, col, r, strength, ray)['light'] for r in range(14) for col in range(28)]))
    return dict(schema='garden-canopy-sources-v1', lineage=19,
        first_tick_exclusive=canopy.foliage.DAWN, end_tick=canopy.foliage.OPENING,
        source_fields=canopy.FIELDS, rows=rows), leaves, 'original'


class CanopyTests(unittest.TestCase):
    def test_fixed_scope(self):
        self.assertEqual([canopy.arguments(c) for c in canopy.roster()], [
            ['--canopy-panel', '9a903368', 'condition', p, m]
            for p in ('original', 'fewest') for m in ('off', 'on')])
        self.assertEqual((len(canopy.TICKS), canopy.TICKS[0], canopy.TICKS[-1]), (32, 586575, 587040))

    def test_signed_rounding_ties(self):
        self.assertEqual([canopy.offset(r, 1) for r in (-12, -8, -7, 0, 7, 8, 12)], [-1, -1, 0, 0, 0, 1, 1])
        self.assertEqual(canopy.offset(-6, 4), -2)

    def test_boundary_is_not_darkness(self):
        cells = canopy.field([[1, 0, 0, 0, 38, 12, False]])
        left = canopy.cast(cells, 0, 13, 100, 12)
        self.assertEqual((left['stop'], left['light'], left['cells']), ('left', 100, []))
        right = canopy.cast(cells, 27, 13, 100, -12)
        self.assertEqual((right['stop'], right['light']), ('right', 100))
        self.assertEqual(canopy.cast(cells, 7, 0, 100, 12)['stop'], 'top')

    def test_ambient_floor_stops_before_geometric_boundary(self):
        cells = canopy.field([[1, 0, 1, 12, 38, 12, True]])
        path = canopy.cast(cells, 2, 13, 50, 12)
        self.assertEqual((path['stop'], path['light']), ('floor', 24))
        self.assertEqual(path['cells'], [[1, 12, 38, 26]])
        self.assertEqual(path['raw'], {1: 38})
        self.assertEqual(canopy.cast(cells, 2, 13, 24, 12)['cells'], [])

    def test_overlapping_sources_caps_and_nonadditive_marginal_gains(self):
        cells = canopy.field([[lineage, i, 5, 0, 38, 12, False]
                              for i, lineage in enumerate([1] * 4 + [2] * 4)])
        self.assertEqual(sum(cells[5].values()), 304)
        actual = canopy.cast(cells, 5, 1, 100, 0)
        self.assertEqual(actual['cells'], [[5, 0, 255, 76]])
        self.assertEqual(actual['raw'], {1: 152, 2: 152})
        self.assertEqual(canopy.cast(cells, 5, 1, 100, 0, keep=lambda k: k == 1)['light'], 24)
        self.assertEqual(canopy.cast(cells, 5, 1, 100, 0, keep=lambda k: k == 2)['light'], 24)
        self.assertEqual(canopy.cast(cells, 5, 1, 100, 0, keep=lambda k: False)['light'], 100)

    def test_complete_grid_and_ordered_body_join(self):
        data, leaves, policy = fixture()
        for row in data['rows']:
            for source in row['sources']:
                source[1] += 8  # Earlier world indices, before reclamation.
        result = canopy.validate_trace(data, leaves, policy)
        self.assertEqual(result['full_grid_cells_checked'], 12544)
        self.assertEqual(result['total']['stops'], {'top': 768})
        self.assertEqual(result['total']['bands'], result['total']['unshaded_bands'])

    def test_reject_changed_metadata_sources_grid_and_focal_light(self):
        for kind in ('missing', 'duplicate', 'identity', 'ray', 'source', 'order', 'dead', 'grid', 'focal'):
            data, leaves, policy = fixture()
            row = data['rows'][0]
            if kind == 'missing':
                data['rows'].pop()
            elif kind == 'duplicate':
                data['rows'][1] = deepcopy(row)
            elif kind == 'identity':
                data['lineage'] = 17
            elif kind == 'ray':
                row['ray'] -= 1
            elif kind == 'source':
                row['sources'][0][4] += 1
            elif kind == 'order':
                row['sources'].reverse()
            elif kind == 'dead':
                row['sources'][0][6] = True
            elif kind == 'grid':
                row['light'][-1] += 1
            else:
                next(r for r in leaves['rows'] if r['tick'] == row['tick'])['leaves'][0][5] += 1
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                canopy.validate_trace(data, leaves, policy)

    def test_staged_adapter_preserves_frozen_text_and_fails_closed(self):
        path = canopy.collect.ROOT / 'sim/research_player/stage_canopy.py'
        spec = importlib.util.spec_from_file_location('canopy_stage', path)
        stage = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(stage)
        text = '\n'.join(('static void update_node_growth_progress(', 'static void wear_leaves(',
                          'static int update_light_observed(', 'static bool world_is_valid('))
        self.assertTrue(stage.adapt(text).startswith(text))
        for bad in ('', text + '\nstatic void wear_leaves('):
            with self.assertRaises(ValueError):
                stage.adapt(bad)


class PublishedCanopyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='published-canopy-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.archive = canopy.collect.ROOT / 'benchmarks/garden-seasons/leaf-population-canopy-results.json.gz'
        assert canopy.prepare.sha(cls.archive.read_bytes()) == 'bffc7454ca81b41470461c493b6a8a2260072fe485aab4dadefffc99e24171e1'
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native calls forbidden')):
            cls.result = canopy.follow.unpack(cls.archive, cls.root / 'evidence', experiment=canopy.EXPERIMENT)

    def test_exact_parity_and_full_grid_reconstruction(self):
        self.assertEqual(self.result['calls'], 4)
        for key, samples, weighted, raw in (
                ('original', 768, 40397, {'19': 24756}),
                ('fewest', 832, 21613, {'1': 9448, '17': 31467})):
            a = self.result['analyses'][key]
            self.assertEqual(a['full_grid_cells_checked'], 12544)
            self.assertEqual(len(a['paths']), samples)
            self.assertEqual(a['total']['weighted'], weighted)
            self.assertEqual(a['total']['raw_opacity_by_lineage'], raw)

    def test_actual_boundary_crossing_not_unvisited_geometry(self):
        a, b = (self.result['analyses'][p] for p in ('original', 'fewest'))
        self.assertEqual(a['total']['stops'], {'floor': 237, 'left': 531})
        self.assertEqual(b['total']['stops'], {'floor': 423, 'left': 8, 'top': 401})
        self.assertEqual(a['columns']['0']['stops'], {'left': 256})
        self.assertEqual(a['columns']['0']['weighted'], 30448)

    def test_worn_lower_canopy_limits_even_unshaded_snapshot(self):
        a, b = (self.result['analyses'][p] for p in ('original', 'fewest'))
        self.assertEqual(a['total']['no_other_weighted'], a['total']['weighted'])
        self.assertEqual(b['total']['no_other_weighted'], 31854)
        lower = b['heights']['lower']
        self.assertEqual(tuple(lower[k] for k in
            ('weighted', 'no_other_weighted', 'no_self_weighted', 'unshaded_weighted')),
            (1816, 3674, 3203, 5693))
        self.assertLess(lower['unshaded_weighted'], a['heights']['lower']['weighted'])
        # A fixed-snapshot accounting change is NOT a replay prediction.
        self.assertEqual((31854 + 36) // 255 + 116 - 32, 209)

    def test_changed_source_rejected_and_archive_roundtrip_offline(self):
        timeline = self.root / 'evidence/runs/9a903368-condition-fewest-on/timeline'
        data = json.loads((timeline / 'canopy.json').read_bytes())
        leaves = json.loads((timeline / 'foliage.json').read_bytes())
        # A single source can be hidden by the ambient floor. Remove the
        # measured external caster across the window to guarantee a light change.
        for row in data['rows']:
            for source in row['sources']:
                if source[0] == 1:
                    source[4:6] = [0, 0]
        with self.assertRaisesRegex(ValueError, 'independent light solve'):
            canopy.validate_trace(data, leaves, 'fewest')
        target = self.root / 'repacked.gz'
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native calls forbidden')):
            canopy.follow.package(self.root / 'evidence', target, experiment=canopy.EXPERIMENT)
        self.assertEqual(target.read_bytes(), self.archive.read_bytes())


if __name__ == '__main__':
    unittest.main()
