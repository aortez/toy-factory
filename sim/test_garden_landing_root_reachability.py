#!/usr/bin/env python3
"""Root geometry boundaries, saved construction, and offline provenance."""

import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_root_reachability as audit

RESULT = audit.ROOT / 'benchmarks/garden-seasons/landing-root-reachability-results.json.gz'


class GeometryTests(unittest.TestCase):
    def test_species_stature_limits(self):
        self.assertEqual([[audit.maximum_depth(s, t) for t in range(-2, 3)] for s in range(3)],
                         [[12, 11, 10, 9, 8], [11, 10, 9, 8, 7], [9, 8, 7, 6, 5]])
        for args in ((3, 0), (0, -3), (True, 0)):
            with self.assertRaises(RuntimeError): audit.maximum_depth(*args)

    def test_segments_are_not_eight_pixel_soil_rows(self):
        self.assertEqual([audit.deepest_row(d) for d in (1, 2, 8, 9, 10, 11, 12)], [0, 1, 5, 6, 7, 8, 8])
        # The deepest ordinary genome ends at y=215, one pixel short of row nine.
        self.assertEqual(149 + 6 * (12 - 1), 215)
        self.assertEqual(audit.direction.root_cell(12, 215) // 28, 8)
        self.assertEqual(audit.direction.root_cell(12, 216) // 28, 9)

    def test_initial_roots_and_world_edges(self):
        self.assertEqual([r['at'] for r in audit.initial_roots(0)], [[9, 149], [15, 149]])
        self.assertEqual([r['at'] for r in audit.initial_roots(27)], [[225, 149], [231, 149]])
        for col in (-1, 28, False):
            with self.assertRaises(RuntimeError): audit.initial_roots(col)
        for x in (9, 231):
            reached = audit.envelope(x, 149, 1, 12)
            self.assertTrue(all(8 <= at[0] <= 231 and 144 <= at[1] <= 231 for _, _, at in reached.values()))
            self.assertEqual(max(c // 28 for c in reached), 8)

    def test_depth_limit_is_terminal_and_never_implies_upward_paths(self):
        reached = audit.envelope(12, 149, 1, 1)
        self.assertEqual(reached, {0: (0, (), (12, 149))})
        self.assertIsNone(audit.row_path(12, 149, 1, 1, 1))
        reached = audit.envelope(12, 193, 9, 10)
        self.assertTrue(all(at[1] >= 193 for _, _, at in reached.values()))

    def test_minimum_path_and_witness_reconstruction(self):
        path = audit.row_path(100, 149, 1, 10, 7)
        self.assertEqual(path['nodes'], 9)
        x, y = 100, 149
        for c in path['path']:
            dx, dy = audit.STEPS[c]; x += dx; y += dy
        self.assertEqual([x, y], path['at'])
        self.assertEqual(audit.direction.root_cell(x, y), path['cell'])
        self.assertIsNone(audit.row_path(100, 149, 1, 9, 7))

    def test_vertical_formula_matches_endpoint_enumeration(self):
        for limit in range(1, 17):
            for x in (9, 120, 231):
                self.assertEqual(max(c // 28 for c in audit.envelope(x, 149, 1, limit)), audit.deepest_row(limit))

    def test_bad_origins_and_rows_rejected(self):
        for args in ((7, 149, 1, 10), (12, 232, 1, 10), (12, 149, 11, 10), (12, 149, 0, 10)):
            with self.assertRaises(RuntimeError): audit.envelope(*args)
        with self.assertRaises(RuntimeError): audit.row_path(12, 149, 1, 10, 11)

    def test_no_clobber_or_dangling_symlink_before_loading(self):
        with tempfile.TemporaryDirectory() as name, patch.object(audit, 'implementation_from', side_effect=AssertionError):
            path = Path(name)
            with self.assertRaisesRegex(RuntimeError, 'fresh root audit'):
                audit.export(path, path, path)
            link = path / 'link'; link.symlink_to(path / 'missing')
            with self.assertRaisesRegex(RuntimeError, 'fresh root audit'):
                audit.export(path, path, link)

    def test_full_trace_clock_and_footer_are_checked_outside_selected_window(self):
        header = {'schema': 'landing-directions-v1', 'start': 15, 'stop': 45}
        footer = {'complete': True, 'tick': 45, 'run_hash': '12345678'}
        for fault in (None, 'before', 'after', 'footer'):
            records = [header, {'tick': 15, 'bids': []}, {'tick': 30, 'bids': []},
                       {'tick': 45, 'bids': []}, footer]
            if fault == 'before': records[1] = {'tick': 0, 'bids': []}
            if fault == 'after': records[3] = {'tick': 60, 'bids': []}
            if fault == 'footer': records[-1] = {'complete': False}
            with tempfile.TemporaryDirectory() as name, patch.object(audit, 'START', 30):
                path = Path(name) / 'trace.gz'
                with gzip.open(path, 'wt') as stream:
                    for record in records: stream.write(json.dumps(record, separators=(',', ':')) + '\n')
                if fault:
                    with self.assertRaises(RuntimeError):
                        list(audit.selected_rows(path, 'direction', {'tick': 45, 'run_hash': '12345678'}, 30))
                else:
                    self.assertEqual(list(audit.selected_rows(path, 'direction',
                                     {'tick': 45, 'run_hash': '12345678'}, 30)), [records[2]])


@unittest.skipUnless(RESULT.exists(), 'root reachability audit not exported')
class SavedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(RESULT, 'rt') as stream: cls.value = json.load(stream)

    def test_portable_verification_never_runs_processes(self):
        with patch('subprocess.Popen', side_effect=AssertionError('audit must be offline')):
            audit.check_value(self.value)

    def test_all_cases_and_duplicate_order_histories(self):
        self.assertEqual(len(self.value['analysis']), 4)
        for i in range(2):
            left, right = self.value['analysis'][i], self.value['analysis'][i+2]
            for arm in audit.ARMS:
                # Lifetime seed counts can differ outside this root window.
                self.assertEqual({k: v for k, v in left['arms'][arm].items() if k != 'life'},
                                 {k: v for k, v in right['arms'][arm].items() if k != 'life'})
        for case in self.value['analysis']:
            self.assertEqual(set(case['arms']), {'control', 'candidate'})
            for arm in case['arms'].values():
                self.assertEqual(len(arm['roots']), arm['final_body']['roots'])
                self.assertLessEqual(arm['actual_deepest_row'], arm['optimistic_deepest_row'])
                self.assertTrue(all(v['below_any_species_limit'] <= v['below_selected_limit'] <= v['below_actual']
                                    for v in arm['reservoirs']))

    def test_historical_source_tampering_rejected(self):
        value = copy.deepcopy(self.value['implementation'])
        value['files']['src/garden_agent_neural.c'] += '\n'
        with self.assertRaises(RuntimeError): audit.check_implementation(value)

    def test_missing_or_changed_root_observation_rejected(self):
        subject = audit.inputs()[0][0]
        drying = audit.inputs()[1]['cases'][0]['arms']['control']
        original = self.value['receipts'][0]['arms']['control']
        for kind in ('missing', 'body', 'direction', 'limit'):
            rows = copy.deepcopy(original)
            if kind == 'missing': rows.pop()
            elif kind == 'body': rows[-1]['body']['roots'] += 1
            else:
                row = next(r for r in rows if any(b['tissue'] == 1 for b in r['bids']))
                i = next(i for i, b in enumerate(row['bids']) if b['tissue'] == 1)
                if kind == 'direction': row['directions'][i]['at'][0] += 1
                else: row['bids'][i]['maximum_depth'] += 1
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                audit.analyze_arm(subject, 'control', rows, drying)

    def test_changed_derived_reach_rejected(self):
        value = copy.deepcopy(self.value)
        value['analysis'][0]['arms']['control']['optimistic_deepest_row'] += 1
        with self.assertRaisesRegex(RuntimeError, 'analysis differs'): audit.check_value(value)

    def test_depth_not_money_stops_the_deepest_root(self):
        for case in self.value['analysis']:
            limit = 9 if case['case']['guard'] == 'control' else 10
            for arm in case['arms'].values():
                self.assertEqual(arm['maximum_depth'], limit)
                self.assertEqual(arm['actual_deepest_row'], arm['optimistic_deepest_row'])
                self.assertEqual(arm['deeper_opportunities'], [])
                stops = [e for e in arm['events'] if e['kind'] == 'finish']
                self.assertEqual(len(stops), 1)
                stop = stops[0]
                self.assertEqual(stop['reason'], 'maximum_depth')
                self.assertLess(stop['nodes_before'], 32)
                self.assertTrue(all(store > cost for store, cost in zip(stop['stores'], stop['cost'], strict=True)))
                self.assertEqual(arm['final_body']['nodes'], 32)
                active = [r for r in arm['roots'] if r['active']]
                self.assertEqual([r['depth'] for r in active], [6])

    def test_global_bottom_two_rows_remain_outside_every_ordinary_genome(self):
        self.assertEqual(max(audit.deepest_row(audit.maximum_depth(s, t))
                             for s in range(3) for t in range(-2, 3)), 8)
        for case in self.value['analysis']:
            for arm in case['arms'].values():
                first, last = arm['reservoirs']
                self.assertEqual(first['below_selected_limit'], last['below_selected_limit'])
                self.assertGreater(last['below_any_species_limit'] * 2, last['total'])
                self.assertEqual(last['below_any_species_limit'], sum(last['rows'][9:]))

    def test_replayed_closed_tip_cannot_extend_again(self):
        value = self.value['receipts'][0]['arms']['control']
        row = next(r for r in value if any(b['tissue'] == 1 for b in r['bids']))
        i = next(i for i, b in enumerate(row['bids']) if b['tissue'] == 1)
        bid, observation = row['bids'][i], row['directions'][i]
        roots = [{'at': observation['at'], 'depth': bid['depth'], 'active': False, 'parent': None}]
        with self.assertRaisesRegex(RuntimeError, 'absent or closed'):
            audit.advance_roots(roots, bid, observation, row['tick'])


if __name__ == '__main__':
    unittest.main()
