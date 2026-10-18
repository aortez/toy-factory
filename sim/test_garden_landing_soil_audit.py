#!/usr/bin/env python3
"""Integer transport stages, archived provenance, and saved-cell reconstruction."""

import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_soil_audit as audit
from test_garden_rainfall import rain_at

RESULT = audit.ROOT / 'benchmarks/garden-seasons/landing-soil-audit-results.json.gz'


class TransportTests(unittest.TestCase):
    def test_transfer_threshold_floor_limit_and_direction(self):
        for source, dest, limit, divisor, expected in ((1, 0, 4, 8, 0), (2, 0, 4, 8, 1),
                (9, 1, 4, 8, 1), (255, 0, 4, 8, 4), (255, 0, 12, 4, 12),
                (255, 254, 12, 4, 0), (255, 255, 12, 4, 0), (0, 20, 12, 4, 0)):
            with self.subTest(source=source, dest=dest):
                self.assertEqual(audit.transfer(source, dest, limit, divisor), expected)
        for invalid in ((-1, 0, 4, 8), (256, 0, 4, 8), (2, 0, 0, 8), (2, 0, 4, 0), (True, 0, 4, 8)):
            with self.assertRaises(RuntimeError): audit.transfer(*invalid)

    def test_downward_flow_is_in_place_not_a_synchronous_stencil(self):
        soil = [0] * audit.CELLS
        soil[0] = 12
        step = audit.transition(soil, 0, 1)
        self.assertEqual([step['grids']['vertical'][i] for i in (0, 28, 56, 84)], [9, 2, 1, 0])
        self.assertEqual(soil[0], 12)
        self.assertEqual(sum(step['grids']['vertical']), 12)

    def test_lateral_pair_parity_and_reverse_direction(self):
        soil = [0] * audit.CELLS
        soil[280] = 17
        even, odd = (audit.transition(soil, 0, tick) for tick in (0, 1))
        self.assertEqual(even['grids']['lateral'][280:283], [15, 2, 0])
        self.assertEqual(odd['grids']['lateral'][280:283], [17, 0, 0])
        soil[280], soil[281] = 0, 2
        step = audit.transition(soil, 0, 0)
        self.assertIn([1, 281, 280, 2, 0, 1], step['flows'])

    def test_no_upward_flow_and_evaporation_only_at_surface_cadence(self):
        soil = [0] * audit.CELLS
        soil[0], soil[28] = 1, 1
        at_bill, between = (audit.transition(soil, 0, tick) for tick in (4, 5))
        self.assertEqual(at_bill['grids']['evaporation'][0], 0)
        self.assertEqual(at_bill['grids']['evaporation'][28], 1)
        self.assertEqual(between['grids']['evaporation'][0], 1)
        soil = [0] * audit.CELLS
        soil[280] = 200
        self.assertEqual(audit.transition(soil, 0, 1)['grids']['vertical'][252], 0)

    def test_weather_matches_existing_unsigned_reference_and_drought_gate(self):
        for seed in (1, 0xf7ee4528, 0xffffffff):
            for tick in (*range(512), 0xffffffff):
                w = audit.weather(seed, tick)
                self.assertEqual(w['ungated_rate'], rain_at(seed, tick))
                self.assertEqual(w['rate'], 0 if w['drought'] else w['ungated_rate'])
        self.assertFalse(audit.weather(0xf7ee4528, 629745 // 15)['drought'])
        self.assertTrue(audit.weather(0xf7ee4528, 629760 // 15)['drought'])
        self.assertTrue(all(audit.weather(0, tick)['rate'] == 0 for tick in range(512)))

    def test_rain_saturation_and_transport_conservation(self):
        tick = next(t for t in range(128) if rain_at(1, t))
        soil = [0] * audit.CELLS
        soil[0:28] = [255] * 28
        step = audit.transition(soil, 1, tick)
        self.assertEqual(step['grids']['rain'], soil)
        self.assertEqual(sum(step['grids']['vertical']), sum(soil))
        self.assertEqual(sum(step['grids']['lateral']), sum(soil))
        self.assertTrue(all(0 <= v <= 255 for g in step['grids'].values() for v in g))
        with self.assertRaises(RuntimeError): audit.transition([0] * 307, 1, 1)

    def test_regions_clip_at_edges_and_balance_removes_internal_circulation(self):
        self.assertEqual(audit.region({0}, 1), {0, 1, 28})
        self.assertEqual(len(audit.region({0}, 2)), 6)
        self.assertEqual(len(audit.region({0}, 4)), 15)
        soil = [0] * audit.CELLS
        soil[280] = 17
        step = audit.transition(soil, 0, 0)
        rows = [{'soil_after': bytes(soil).hex()}, {'soil_after': bytes(step['grids']['evaporation']).hex(), 'roots': []}]
        with patch.object(audit, 'START', 0), patch.object(audit, 'END', 15):
            result = audit.account(rows, [step], 0, {280, 281})
        self.assertEqual(result['regions'][0]['lateral_in'], 0)
        self.assertEqual(result['regions'][0]['lateral_out'], 0)
        self.assertEqual(result['all_soil']['lateral_in'], 2)

    def test_no_clobber_before_loading_or_exporting(self):
        with tempfile.TemporaryDirectory() as name, patch.object(audit, 'implementation_from', side_effect=AssertionError):
            with self.assertRaisesRegex(RuntimeError, 'fresh soil audit'):
                audit.export(Path(name), Path(name))


@unittest.skipUnless(RESULT.exists(), 'soil audit not yet exported')
class SavedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(RESULT, 'rt') as stream: cls.value = json.load(stream)

    def test_portable_verification_never_executes_a_process(self):
        with patch('subprocess.Popen', side_effect=AssertionError('verification is offline')):
            audit.check_value(self.value)

    def test_every_transition_cell_and_paired_terminal_account(self):
        arms = [a for c in self.value['analysis'] for a in c['arms'].values()]
        self.assertEqual(sum(a['transitions'] for a in arms), 1728)
        self.assertEqual(sum(a['cell_transitions'] for a in arms), 532224)
        for case in self.value['analysis']:
            self.assertEqual(case['comparison']['delta']['retained'], -40 if case['case']['guard'] == 'control' else -23)
            for a in case['arms'].values():
                self.assertEqual(len(a['post_anchor']['cells']), 308)
                self.assertEqual([r['radius'] for r in a['post_anchor']['regions']], [0, 1, 2, 4])

    def test_fixed_rotating_duplicate_accounts(self):
        for i in range(2):
            self.assertEqual(self.value['analysis'][i]['arms'], self.value['analysis'][i + 2]['arms'])
            self.assertEqual(self.value['analysis'][i]['comparison'], self.value['analysis'][i + 2]['comparison'])

    def test_equal_rain_and_depth_reservoirs_do_not_hide_local_shortages(self):
        for case in self.value['analysis']:
            daylight = case['case']['guard'] == 'control'
            expected = ((36, 33, 96, 6, 159), (36, 22, 61, 6, 113)) if daylight else (
                        (36, 26, 109, 9, 162), (36, 20, 30, 6, 80))
            for arm, values in zip(audit.ARMS, expected, strict=True):
                a = case['arms'][arm]
                region = a['post_anchor']['regions'][0]
                self.assertEqual(tuple(region[k] for k in ('rain', 'vertical_in', 'lateral_in', 'evaporation', 'collected')), values)
                first, last = a['reservoirs']
                self.assertEqual(first['below_deepest_root'], last['below_deepest_root'])
                self.assertGreater(last['below_deepest_root'] * 100, last['total'] * 89)
                self.assertEqual(first['target_cells'], last['target_cells'])
                self.assertEqual(last['target_cells'], 0)

    def test_changed_historical_source_or_capture_metadata_rejected(self):
        for kind in ('file', 'capture'):
            value = copy.deepcopy(self.value['implementation'])
            if kind == 'file': value['files']['src/garden_world.c'] += '\n'
            else: value['capture'] += '\n'
            with self.subTest(kind=kind), self.assertRaises(RuntimeError): audit.check_implementation(value)

    def test_soil_residual_and_post_uptake_birth_rejected(self):
        original = audit.load_input()['cases'][0]['arms']['control']
        for kind in ('soil', 'birth', 'gardener', 'adult_total'):
            value = copy.deepcopy(original)
            if kind == 'soil':
                row = value['receipt']['uptake'][1]
                soil = bytearray.fromhex(row['soil_before'])
                soil[0] ^= 1
                row['soil_before'] = soil.hex()
            elif kind == 'birth': value['runs']['trace']['result']['lineages'][0]['birth_tick'] = audit.START
            elif kind == 'gardener': value['runs']['trace']['result']['gardener'] = True
            else: value['receipt']['adult'][1]['soil_water'] += 1
            with self.subTest(kind=kind), self.assertRaises(RuntimeError): audit.analyze_arm(value)

    def test_changed_stage_receipt_and_account_rejected(self):
        value = copy.deepcopy(self.value)
        value['analysis'][0]['arms']['control']['evidence'][0]['weather']['rate'] += 1
        with self.assertRaisesRegex(RuntimeError, 'analysis differs'): audit.check_value(value)
        value = copy.deepcopy(self.value)
        value['analysis'][0]['comparison']['delta']['retained'] -= 1
        with self.assertRaisesRegex(RuntimeError, 'analysis differs'): audit.check_value(value)


if __name__ == '__main__':
    unittest.main()
