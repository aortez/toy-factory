#!/usr/bin/env python3
"""Transport ordering, conservation, boundaries and offline evidence checks."""

import copy
import gzip
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_wicking as probe

RESULT = probe.ROOT / 'benchmarks/garden-seasons/landing-wicking-results.json.gz'


class WickingTests(unittest.TestCase):
    def test_onset_cadence_and_gradient(self):
        grid = [0] * 308
        grid[28] = 255
        for tick in range(probe.AFTER - 60, probe.AFTER + 60):
            self.assertEqual(probe.wick(grid, tick, True), (grid, [0] * 10))
        actual, moved = probe.wick(grid, probe.AFTER + 60, True)
        self.assertEqual((actual[0], actual[28], sum(moved)), (1, 254, 1))
        self.assertEqual(probe.wick(grid, probe.AFTER + 60, False), (grid, [0] * 10))
        for lower, expected in ((0, 0), (1, 0), (2, 1)):
            grid[28] = lower
            self.assertEqual(probe.wick(grid, probe.AFTER + 60, True)[0][0], expected)

    def test_no_same_pass_multirow_ascent(self):
        grid = [0] * 308
        grid[280] = 200
        actual, moved = probe.wick(grid, probe.AFTER + 60, True)
        self.assertEqual([actual[i] for i in (224, 252, 280)], [0, 1, 199])
        self.assertEqual(moved, [0] * 9 + [1])
        self.assertEqual(grid[280], 200)

    def test_byte_bounds_conservation_and_determinism(self):
        rng = random.Random(123)
        for grid in ([0] * 308, [255] * 308, *[[rng.randrange(256) for _ in range(308)] for _ in range(100)]):
            actual, moved = probe.wick(grid, probe.AFTER + 60, True)
            self.assertEqual(sum(actual), sum(grid))
            self.assertTrue(all(0 <= v <= 255 for v in actual))
            self.assertLessEqual(sum(moved), 280)
            self.assertEqual((actual, moved), probe.wick(grid, probe.AFTER + 60, True))
        for grid, tick, enabled in (([0] * 307, 0, True), ([256] * 308, 0, True),
                                    ([True] * 308, 0, True), ([0] * 308, -1, True), ([0] * 308, 60, 1)):
            with self.assertRaises(RuntimeError): probe.wick(grid, tick, enabled)

    def test_lateral_then_wicking_then_surface_evaporation(self):
        grid = [0] * 308
        grid[280] = 16
        with patch.object(probe, 'SEED', 0):
            actual, flows = probe.transition(grid, 626640, True)
            ordinary, _ = probe.transition(grid, 626640, False)
            self.assertEqual([actual[i] for i in (252, 253, 280, 281)], [1, 1, 13, 1])
            self.assertEqual([ordinary[i] for i in (252, 253, 280, 281)], [0, 0, 14, 2])
            self.assertEqual(sum(flows['upward']), 2)
            grid = [0] * 308
            grid[28:56] = [2] * 28
            actual, flows = probe.transition(grid, 626640, True)
            self.assertEqual(actual[:28], [0] * 28)
            # Ordinary downward flow leaves one unit: insufficient to wick.
            self.assertEqual(sum(flows['upward']), 0)
            grid[28:56] = [8] * 28
            actual, flows = probe.transition(grid, 626640, True)
            self.assertEqual(actual[:28], [0] * 28)
            self.assertEqual(flows['evaporation'], 28)

    def test_germination_is_a_post_uptake_withdrawal(self):
        grid = [0] * 308
        grid[3] = 25
        lives = [dict(parent=1, birth_tick=60, column=3), dict(parent=0, birth_tick=60, column=3)]
        self.assertEqual(probe.after_births(grid, 60, lives)[3], 13)
        self.assertEqual(probe.after_births(grid, 45, lives), grid)
        grid[3] = 11
        with self.assertRaises(RuntimeError): probe.after_births(grid, 60, lives)

    def test_synthetic_window_reconstructs_birth_and_every_cell(self):
        grid = [0] * 308
        grid[0], grid[280] = 20, 16
        lives = [dict(parent=1, birth_tick=626640, column=0)]
        rows = []
        with patch.object(probe, 'START', 626640), patch.object(probe, 'END', 626655), patch.object(probe, 'SEED', 0):
            for tick in (626640, 626655):
                before = grid.copy()
                grid[280] -= 1
                after = grid.copy()
                grid = probe.after_births(after, tick, lives)
                rows.append(dict(tick=tick, before=bytes(before).hex(), after=bytes(after).hex(),
                                 roots=[[1, 1, 0, 0, 10, 1, before[280], 1, after[280], 10, 11]],
                                 plants=[[1, [10, 1, 0, 0, 0, 0]]], end_total=sum(grid)))
                grid, _ = probe.transition(grid, tick + 15, True)
            result = probe.soil_account(rows, {'lineages': lives}, True)
            self.assertEqual((result['germination'], result['uptake'], result['cell_transitions']), (12, 2, 308))
            for key in ('before', 'after'):
                bad = copy.deepcopy(rows)
                bad[-1][key] = 'ff' + bad[-1][key][2:]
                with self.assertRaises(RuntimeError): probe.soil_account(bad, {'lineages': lives}, True)

    def test_only_observation_arguments_are_added(self):
        saved = dict(args=['placement-replay', '--ticks', '983040'])
        self.assertEqual(probe.arguments(saved), saved['args'] +
                         ['--uptake-trace', 'uptake.jsonl', '--uptake-window', '626520:660480'])
        with self.assertRaises(RuntimeError): probe.arguments(dict(args=['--uptake-window', '1:2']))

    def test_settings_reject_mixed_ecology(self):
        settings = dict(TOY_FACTORY_GARDEN_SOIL_WICKING='ON', TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE='OFF',
                        TOY_FACTORY_SIMULATOR_SANITIZERS='ON', TOY_FACTORY_SIMULATOR_PROFILING='ON')
        probe.check_settings(settings, 'on')
        with self.assertRaises(RuntimeError): probe.check_settings(settings, 'off')
        settings['TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE'] = 'ON'
        with self.assertRaises(RuntimeError): probe.check_settings(settings, 'on')

    def test_fresh_output_is_checked_before_inputs_or_processes(self):
        with tempfile.TemporaryDirectory() as name, patch.object(probe, 'inputs', side_effect=AssertionError):
            path = Path(name)
            with self.assertRaisesRegex(RuntimeError, 'fresh wicking output'):
                probe.collect(path, path, path, 1)
            link = path / 'link'; link.symlink_to(path / 'missing')
            with self.assertRaisesRegex(RuntimeError, 'fresh wicking output'):
                probe.collect(path, path, link, 1)


@unittest.skipUnless(RESULT.exists(), 'wicking experiment not yet exported')
class SavedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(RESULT, 'rt') as stream: cls.value = json.load(stream)

    def test_verification_is_offline(self):
        with patch('subprocess.Popen', side_effect=AssertionError('offline verification')):
            probe.check_value(self.value)

    def test_full_panel_and_conserved_soil(self):
        self.assertEqual(len(self.value['capture']['runs']), 24)
        self.assertEqual(len(self.value['pairs']), 8)
        for pair in self.value['pairs']:
            self.assertEqual(pair['comparison']['first_soil_difference'], 626640)
            for arm in probe.ARMS:
                soil = pair['arms'][arm]['derived']['soil']
                self.assertEqual(soil['cell_transitions'], 2264 * 308)
                self.assertEqual(soil['opening'] + soil['rain'] - soil['evaporation'] - soil['uptake'] -
                                 soil['germination'], soil['closing'])
                self.assertEqual(soil['drought_rain'], 0)

    def test_changed_soil_or_shortage_summary_rejected(self):
        pair = self.value['pairs'][0]
        for arm in probe.ARMS:
            a = pair['arms'][arm]
            bad = copy.deepcopy(a['receipt'])
            bad['soil'][10]['before'] = 'ff' + bad['soil'][10]['before'][2:]
            with self.assertRaises(RuntimeError):
                probe.derive(bad, a['analysis'], a['result'], pair['case'], arm)


if __name__ == '__main__': unittest.main()
