#!/usr/bin/env python3
"""Boundary, provenance, accounting and offline checks for late capped uptake."""

import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_uptake_limit as probe

RESULT = probe.ROOT / 'benchmarks/garden-seasons/landing-uptake-limit-results.json.gz'


class UptakeLimitTests(unittest.TestCase):
    def row(self, tick, stored, taken):
        grid = [0] * 308
        grid[0] = 9
        after = grid.copy()
        after[0] -= taken
        return dict(tick=tick, before=bytes(grid).hex(), after=bytes(after).hex(),
                    roots=[[1, 1, 0, 0, 0, 3, 9, taken, 9 - taken, stored, min(512, stored + taken)]],
                    plants=[[1, [stored, taken, max(0, stored + taken - 512), 0, 0, 0]]],
                    end_total=sum(after))

    def test_onset_and_capacity_before_soil_debit(self):
        for tick, stored, taken in ((probe.AFTER, 512, 3), (probe.AFTER + 15, 512, 0),
                                    (probe.AFTER + 15, 511, 1), (probe.AFTER + 15, 509, 3)):
            with patch.object(probe.previous, 'START', tick), patch.object(probe.previous, 'END', tick):
                row = self.row(tick, stored, taken)
                result = probe.previous.soil_account([row], {'lineages': []}, False, capped_after=probe.AFTER)
                self.assertEqual(result['uptake'], taken)
                self.assertEqual(result['closing'], 9 - taken)
                if tick > probe.AFTER: self.assertEqual(result['overflow'], 0)
        tick = probe.AFTER + 15
        with patch.object(probe.previous, 'START', tick), patch.object(probe.previous, 'END', tick):
            with self.assertRaises(RuntimeError):
                probe.previous.soil_account([self.row(tick, 512, 3)], {'lineages': []}, False, capped_after=probe.AFTER)
            with self.assertRaises(RuntimeError):
                probe.previous.soil_account([self.row(tick, 512, 0)], {'lineages': []}, False)

    def test_next_root_uses_updated_storage_and_shared_soil(self):
        tick = probe.AFTER + 15
        row = self.row(tick, 511, 1)
        row['roots'].append([2, 1, 0, 0, 0, 3, 8, 0, 8, 512, 512])
        row['roots'].append([3, 2, 1, 0, 0, 3, 8, 3, 5, 20, 23])
        row['after'] = '05' + row['after'][2:]
        row['end_total'] = 5
        row['plants'].append([2, [20, 3, 0, 0, 0, 0]])
        with patch.object(probe.previous, 'START', tick), patch.object(probe.previous, 'END', tick):
            result = probe.previous.soil_account([row], {'lineages': []}, True, capped_after=probe.AFTER)
            self.assertEqual((result['uptake'], result['overflow']), (4, 0))
            row['roots'][1][-2] = 511
            with self.assertRaises(RuntimeError):
                probe.previous.soil_account([row], {'lineages': []}, True, capped_after=probe.AFTER)

    def test_four_builds_and_no_unrelated_ecology(self):
        for arm in probe.ARMS:
            settings = dict(TOY_FACTORY_GARDEN_SOIL_WICKING='ON' if arm in ('on', 'cap-wick') else 'OFF',
                            TOY_FACTORY_GARDEN_LATE_UPTAKE_LIMIT='ON' if arm in probe.CANDIDATES else 'OFF',
                            TOY_FACTORY_SIMULATOR_SANITIZERS='ON', TOY_FACTORY_SIMULATOR_PROFILING='ON')
            probe.check_settings(settings, arm)
            settings['TOY_FACTORY_GARDEN_WATER_HEADROOM'] = 'ON'
            with self.assertRaises(RuntimeError): probe.check_settings(settings, arm)

    def test_first_root_storage_matches_the_adult_receipt(self):
        tick = probe.AFTER + 15
        row = self.row(tick, 512, 0)
        row['plants'][0][1][0] = 511
        with patch.object(probe.previous, 'START', tick), patch.object(probe.previous, 'END', tick):
            with self.assertRaises(RuntimeError):
                probe.previous.soil_account([row], {'lineages': []}, False, capped_after=probe.AFTER)

    def test_metadata_cannot_hide_cap(self):
        pair = dict(case={}, allocator='control')
        with patch.object(probe.previous, 'check_result') as checked:
            probe.check_result({'uptake_limit_probe': probe.ENVIRONMENT}, pair, 'cap-wick')
            checked.assert_called_once_with({}, {}, 'control', 'on')
            for result, arm in (({}, 'cap'), ({'uptake_limit_probe': probe.ENVIRONMENT}, 'off')):
                with self.assertRaises(RuntimeError): probe.check_result(result, pair, arm)

    def test_occupancy_windows_and_births(self):
        late = probe.STOP - 32 * probe.population.DAY
        rows = [[15, 20, 5], [probe.AFTER + 15, 255, 8], [late + 15, 0, 0]]
        result = dict(lineages=[dict(generation=1, birth_tick=probe.AFTER),
                               dict(generation=1, birth_tick=late + 15)])
        a = probe.occupancy_accounts(rows, result)
        self.assertEqual(a['post']['births'], 1)
        self.assertEqual(a['late32']['births'], 1)
        self.assertEqual(a['post']['full_living_slots'], (late - probe.AFTER) // 15)
        self.assertEqual(a['post']['fewer_than_four_live_node_spaces'], a['post']['full_living_slots'])
        self.assertEqual(a['late32']['node_samples'], 0)
        for bad in ([], [[16, 4, 1]], [[15, 257, 8]], [[15, 4, 9]], [[15, 4, 1], [30, 4, 1]]):
            with self.assertRaises(RuntimeError): probe.occupancy_accounts(bad, result)

    def test_existing_output_rejected_without_native_call(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(probe, 'inputs', side_effect=AssertionError):
            path = Path(tmp)
            with self.assertRaisesRegex(RuntimeError, 'fresh uptake-limit output'): probe.collect(path, 1)
            link = path / 'dangling'; link.symlink_to(path / 'missing')
            with self.assertRaisesRegex(RuntimeError, 'fresh uptake-limit output'): probe.collect(link, 1)


@unittest.skipUnless(RESULT.exists(), 'uptake-limit experiment not yet exported')
class SavedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(RESULT, 'rt') as stream: cls.value = json.load(stream)

    def test_full_offline_reconciliation(self):
        with patch('subprocess.Popen', side_effect=AssertionError('must remain offline')):
            probe.check_value(self.value)
        self.assertEqual(len(self.value['capture']['runs']), 48)

    def test_no_post_onset_overflow(self):
        for pair in self.value['pairs']:
            for arm in probe.CANDIDATES:
                soil = pair['arms'][arm]['derived']['soil']
                self.assertEqual(soil['cell_transitions'], 2264 * 308)
                self.assertTrue(all(overflow == 0 for tick, _, _, overflow in soil['samples'] if tick > probe.AFTER))
                self.assertEqual(soil['drought_rain'], 0)

    def test_changed_root_and_occupancy_rejected(self):
        pair = self.value['pairs'][0]
        a = pair['arms']['cap']
        bad = copy.deepcopy(a['receipt'])
        bad['soil'][-1]['before'] = 'ff' + bad['soil'][-1]['before'][2:]
        with self.assertRaises(RuntimeError): probe.derive(bad, a['analysis'], a['result'], pair['case'], 'cap')
        saved = pair['occupancy']['cap']['accounts']['post']['node_samples']
        try:
            pair['occupancy']['cap']['accounts']['post']['node_samples'] += 1
            with self.assertRaisesRegex(RuntimeError, 'occupancy summary'): probe.check_value(self.value)
        finally:
            pair['occupancy']['cap']['accounts']['post']['node_samples'] = saved


if __name__ == '__main__': unittest.main()
