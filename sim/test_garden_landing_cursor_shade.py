#!/usr/bin/env python3
"""Same-state shade removal, exact windows and portable replay evidence."""

import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_cursor_shade as audit


def scene(sources, strength=255):
    field = audit.light.field(audit.light.opacity(tuple(tuple(s) for s in sources), 0, 'actual'), strength, 0)
    local = field[38]
    return dict(tick=3840, sun=[64, strength, 0], sources=sources,
                leaves=[[3, 37, 10, 1, local, local // 64]], roots=[],
                soil_before='00' * 308, soil_after='00' * 308, light=bytes(field).hex())


class LightTests(unittest.TestCase):
    def test_ray_rounding_edges_and_own_cell_exclusion(self):
        self.assertEqual(audit.light.rays(8)[38], (9,))
        self.assertEqual(audit.light.rays(-8)[38], (11,))
        self.assertEqual(audit.light.rays(12)[28], ())
        self.assertEqual(audit.light.rays(0)[10], ())

    def test_rebuild_saturated_cell_instead_of_subtracting(self):
        sources = [[1, 32, 0, 10, 0, 140, 0], [2, 39, 0, 10, 0, 200, 0]]
        row = scene(sources)
        lives = {i: dict(birth_tick=0, death_tick=None) for i in (32, 37, 39)}
        self.assertEqual(audit.validate_light(row, lives)[37], 0)
        grid = audit.without_neighbor(sources)
        self.assertEqual(grid[10], 140)
        self.assertEqual(audit.light.field(grid, 255, 0)[38], 115)
        self.assertNotEqual(grid[10], 255 - 200)

    def test_one_light_unit_crosses_integer_income_threshold(self):
        row = scene([[2, 39, 0, 10, 0, 1, 0]], 128)
        lives = {i: dict(birth_tick=0, death_tick=None) for i in (37, 39)}
        self.assertEqual(row['leaves'][0][-2:], [127, 1])
        self.assertEqual(audit.validate_light(row, lives)[37], 1)
        without = audit.light.field(audit.without_neighbor(row['sources']), 128, 0)
        self.assertEqual(without[38] // 64, 2)

    def test_corrupt_grid_leaf_source_and_birth(self):
        original = scene([[2, 39, 0, 10, 0, 64, 0]])
        for fault in ('grid', 'income', 'duplicate', 'birth', 'dead', 'ray'):
            row = copy.deepcopy(original)
            lives = {i: dict(birth_tick=0, death_tick=None) for i in (37, 39)}
            if fault == 'grid':
                row['light'] = '00' + row['light'][2:]
            elif fault == 'income':
                row['leaves'][0][-1] += 1
            elif fault == 'duplicate':
                row['sources'].append(row['sources'][0])
            elif fault == 'birth':
                lives[37]['birth_tick'] = 3840
            elif fault == 'dead':
                row['sources'][0][2] = 1
            else:
                row['sun'][2] = 1
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                audit.validate_light(row, lives)


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = audit.ROOT / 'benchmarks/garden-seasons/landing-cursor-shade-results.json.gz'
        with gzip.open(path, 'rt') as stream:
            cls.saved = json.load(stream)

    def test_portable_reconstruction_without_native_execution(self):
        with patch('subprocess.run', side_effect=AssertionError('offline only')), \
             patch('subprocess.Popen', side_effect=AssertionError('offline only')):
            audit.check_value(self.saved)

    def test_winter_totals_geometry_and_boundary_exclusions(self):
        result = self.saved['analysis']
        winter = result['periods']['winter']
        self.assertEqual((winter['samples'], winter['fixed'], winter['cursor'], winter['without_neighbor']),
                         (424, 172, 142, 172))
        self.assertEqual(winter['residual_absolute'], 0)
        self.assertEqual(winter['leaf_gains'], {'171': 21, '173': 9})
        self.assertEqual(winter['income_gap_steps'], 24)
        self.assertEqual(result['paired_samples'], 703)
        self.assertEqual(result['validated_grids'], 1408)
        self.assertEqual(result['matching_other_sources'], 703)
        self.assertEqual(result['matching_focal_geometry'], 703)
        self.assertEqual(result['mismatches'], [])
        self.assertFalse(result['proves_long_run_rescue'])
        self.assertFalse(result['original_harm_gate_passes'])

    def test_missing_samples_and_tampered_summary_rejected(self):
        for fault in ('missing', 'clock', 'summary', 'receipt'):
            bad = copy.deepcopy(self.saved)
            if fault == 'missing':
                bad['rows']['cursor'].pop()
            elif fault == 'clock':
                bad['rows']['fixed'][0]['tick'] += 15
            elif fault == 'summary':
                bad['analysis']['periods']['winter']['without_neighbor'] += 1
            else:
                bad['capture']['native_runs'] = 3
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                audit.check_value(bad)

    def test_uptake_reader_requires_exact_header_footer_and_clock(self):
        spans = [[15, 30], [60, 60]]
        rows = [dict(schema='landing-uptake-v1', stop=75, windows=spans),
                *[dict(tick=t) for t in (15, 30, 60)], dict(complete=True, tick=75, run_hash='12345678')]
        with tempfile.TemporaryDirectory() as tmp, patch.object(audit.capture, 'STOP', 75), \
             patch.object(audit.capture, 'WINDOWS', spans):
            path = Path(tmp) / 'uptake.gz'
            def save(records):
                path.write_bytes(gzip.compress(b''.join(json.dumps(r).encode() + b'\n' for r in records), mtime=0))
            save(rows)
            self.assertEqual(len(list(audit.capture.uptake_rows(path, dict(run_hash='12345678')))), 3)
            for bad in (rows[:-1], rows[:2] + rows[3:], rows + [dict(extra=1)],
                        rows[:-1] + [dict(complete=True, tick=75, run_hash='00000000')]):
                save(bad)
                with self.assertRaises((RuntimeError, StopIteration)):
                    list(audit.capture.uptake_rows(path, dict(run_hash='12345678')))

    def test_only_observer_arguments_change(self):
        original = audit.energy.load_input()
        for arm in audit.capture.ARMS:
            before = list(audit.energy.selected(original, arm)['args'])
            after = audit.capture.arguments(original, arm)
            observed = {'--adult-trace', '--adult-start', '--adult-stop', '--reach-trace',
                        '--stand-start', '--stand-stop', '--uptake-trace', '--uptake-window'}
            def strip(args):
                out, i = [], 0
                while i < len(args):
                    if args[i] in observed:
                        i += 2
                    else:
                        out.append(args[i])
                        i += 1
                return out
            self.assertEqual(strip(before), strip(after))


if __name__ == '__main__':
    unittest.main()
