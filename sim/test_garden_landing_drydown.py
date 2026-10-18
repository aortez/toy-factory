#!/usr/bin/env python3
"""Ordered cell accounting, exact observer neutrality and portable evidence."""

import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_drydown as probe
from test_garden_landing_uptake import life, scene

RESULT = probe.ROOT / 'benchmarks/garden-seasons/landing-drydown-results.json.gz'


class CellTests(unittest.TestCase):
    def test_dryness_order_and_overflow_remain_separate(self):
        soil = [0] * 308
        soil[0] = 4
        roots = [[1, 1, 0, 0, 0, 3, 4, 3, 1, 511, 512],
                 [2, 1, 0, 0, 0, 3, 1, 1, 0, 512, 512],
                 [3, 2, 1, 0, 0, 3, 0, 0, 0, 10, 10],
                 [4, 2, 1, 1, 0, 3, 0, 0, 0, 10, 10]]
        row = scene(roots=roots, soil=soil)
        observed = probe.uptake.attribute(row, {}, {1: life(1), 2: life(2)}, partial=True)
        self.assertEqual(probe.root_water(row, 1), {0: [6, 4, 0, 2, 2, 0, 3]})
        self.assertEqual(probe.root_water(row, 2), {0: [3, 0, 0, 3, 0, 3, 0], 1: [3, 0, 3, 0, 0, 0, 0]})
        for i in (1, 2):
            parts = probe.root_water(row, i)
            self.assertEqual([sum(v[j] for v in parts.values()) for j in range(7)], observed[i]['water'])

    def test_soil_balance_keeps_signed_between_step_changes(self):
        a, b = [0] * 308, [0] * 308
        a[0], a[1], b[0], b[1] = 4, 5, 6, 3
        rows = [scene(roots=[[1, 1, 0, 0, 0, 3, 4, 3, 1, 0, 3]], soil=a),
                scene(roots=[[1, 1, 0, 0, 0, 3, 6, 3, 3, 3, 6]], soil=b)]
        cells = probe.soil_budget(rows)
        self.assertEqual(len(cells), 308)
        self.assertEqual([cells[0][k] for k in ('opening', 'between_step_net', 'closing')], [4, 5, 3])
        self.assertEqual(cells[0]['consumed'], {'1': 6})
        self.assertEqual(cells[0]['root_visits'], {'1': 2})
        self.assertEqual([cells[1][k] for k in ('between_step_net', 'between_step_positive', 'between_step_negative')], [-2, 0, 2])

    def test_zero_intake_still_records_consumer_presence(self):
        row = scene(roots=[[1, 1, 0, 0, 0, 3, 0, 0, 0, 3, 3]])
        cell = probe.soil_budget([row])[0]
        self.assertEqual(cell['consumed'], {'1': 0})
        self.assertEqual(cell['root_visits'], {'1': 1})

    def test_bad_soil_balance_and_empty_window_rejected(self):
        bad = scene()
        bad['soil_after'] = '01' + bad['soil_after'][2:]
        for rows in ([], [bad]):
            with self.assertRaises(RuntimeError): probe.soil_budget(rows)

    def test_cell_union_does_not_drop_an_unshared_footprint(self):
        def cell(i, taken, overflow):
            return {'cell': i, **dict.fromkeys(probe.uptake.WATER, 0), 'taken': taken, 'overflow': overflow}
        arms = {'control': {'analysis': {'target_cells': [cell(0, 9, 3), cell(1, 4, 0)]}},
                'candidate': {'analysis': {'target_cells': [cell(0, 8, 1), cell(2, 1, 0)]}}}
        self.assertEqual([(v['cell'], v['retained_delta']) for v in probe.compare(arms)], [(0, 1), (1, -4), (2, 1)])

    def test_only_passive_arguments_added(self):
        old = {'args': ['placement-replay', '--ticks', '983040']}
        before = copy.deepcopy(old)
        self.assertEqual(probe.arguments(old), old['args'] +
                         ['--uptake-trace', 'uptake.jsonl', '--uptake-window', '626520:629760'])
        self.assertEqual(old, before)
        with self.assertRaisesRegex(RuntimeError, 'already observed'):
            probe.arguments({'args': ['--uptake-trace', 'old.jsonl']})

    def test_existing_output_rejected_before_inputs_or_native(self):
        with tempfile.TemporaryDirectory() as name, patch.object(probe, 'inputs', side_effect=AssertionError):
            with self.assertRaisesRegex(RuntimeError, 'fresh drying output'):
                probe.collect(Path(name), Path(name), 1)


@unittest.skipUnless(RESULT.exists(), 'drying capture not yet available')
class SavedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(RESULT, 'rt') as stream: cls.value = json.load(stream)

    def test_portable_verification_stays_offline(self):
        with patch('subprocess.Popen', side_effect=AssertionError('verification must not execute')):
            probe.check_value(self.value)

    def test_complete_panel_and_terminal_income(self):
        self.assertEqual(len(self.value['cases']), 4)
        for case in self.value['cases']:
            expected = [(159, 6), (113, 0)] if case['case']['guard'] == 'control' else [(162, 59), (80, 0)]
            for arm, income in zip(probe.ARMS, expected, strict=True):
                a = case['arms'][arm]['analysis']
                self.assertEqual(a['counts']['frames'], 217)
                self.assertEqual(len(a['soil']), 308)
                self.assertEqual((a['post_anchor_water']['taken'], a['post_anchor_water']['overflow']), income)
            self.assertEqual(sum(c['retained_delta'] for c in case['cells']),
                             -40 if case['case']['guard'] == 'control' else -23)

    def test_changed_historical_result_trace_pixels_or_call_budget_rejected(self):
        for kind in ('result', 'trace', 'pixels', 'arguments', 'repeat', 'calls'):
            value = copy.deepcopy(self.value)
            run = value['cases'][0]['arms']['control']['runs']['repeat']
            if kind == 'result': run['result']['tick'] -= 1
            elif kind == 'trace': run['traces']['adult']['sha256'] = '0' * 64
            elif kind == 'pixels': run['frame']['sha256'] = '0' * 64
            elif kind == 'arguments': run['args'].append('--root-wet-direction')
            elif kind == 'repeat': run['traces']['uptake']['sha256'] = '0' * 64
            else: value['full_replays'] += 1
            with self.subTest(kind=kind), self.assertRaises(RuntimeError): probe.check_value(value)

    def test_identical_root_footprints_exhaust_cells_without_foreign_visitors(self):
        for case in self.value['cases']:
            shapes = []
            for arm in probe.ARMS:
                a = case['arms'][arm]
                self.assertEqual(len(a['analysis']['geometry']), 1)
                identity = a['analysis']['id']
                roots = a['analysis']['geometry'][0]['roots']
                shapes.append([r[3:] for r in roots])
                cells = {r[4] * 28 + r[3] for r in roots}
                self.assertEqual((len(roots), len(cells)), (15, 9) if identity == 16 else (16, 11))
                for row in a['receipt']['uptake']:
                    self.assertFalse(any(r[1] != identity and r[4] * 28 + r[3] in cells for r in row['roots']))
                    self.assertTrue(all(bytes.fromhex(row['soil_after'])[i] == 0 for i in cells))
                    self.assertLessEqual(max(bytes.fromhex(row['soil_before'])[i] for i in cells), 2)
            self.assertEqual(*shapes)

    def test_order_settings_duplicate_observations_not_independent_evidence(self):
        for i in range(2):
            for arm in probe.ARMS:
                a, b = (self.value['cases'][j]['arms'][arm] for j in (i, i + 2))
                self.assertEqual(a['receipt']['uptake'], b['receipt']['uptake'])
                self.assertEqual(a['analysis'], b['analysis'])

    def test_missing_sample_root_or_changed_soil_rejected(self):
        subject = probe.inputs()[0]
        for kind in ('sample', 'adult', 'root', 'soil', 'target_resource'):
            receipt = copy.deepcopy(self.value['cases'][0]['arms']['control']['receipt'])
            if kind == 'sample': receipt['uptake'].pop()
            elif kind == 'adult': receipt['adult'].pop(0)
            elif kind == 'root': receipt['uptake'][0]['roots'].pop()
            elif kind == 'soil':
                r = receipt['uptake'][0]
                b = bytearray.fromhex(r['soil_before'])
                b[0] ^= 1
                r['soil_before'] = b.hex()
            else:
                target = next(p for p in receipt['adult'][1]['plants'] if p['id'] == subject['id'])
                target['stages'][-1][1] -= 1
            with self.subTest(kind=kind), self.assertRaises(RuntimeError): probe.analyze(subject, 'control', receipt)

    def test_changed_summary_or_anchor_rejected(self):
        value = copy.deepcopy(self.value)
        value['cases'][0]['arms']['control']['analysis']['anchor'] += probe.STEP
        with self.assertRaisesRegex(RuntimeError, 'analysis differs'): probe.check_value(value)


if __name__ == '__main__':
    unittest.main()
