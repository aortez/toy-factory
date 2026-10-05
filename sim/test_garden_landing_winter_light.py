#!/usr/bin/env python3
"""Winter-light capture isolation, ray arithmetic and saved income reconciliation."""

import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_winter_light as audit

capture = audit.capture
RESULT = audit.ROOT / 'benchmarks/garden-seasons/landing-winter-light-results.json.gz'


def sample(sources):
    grid = audit.uptake.opacity(tuple(tuple(s) for s in sources), 0, 'actual')
    field = audit.uptake.field(grid, 255, 0)
    return dict(tick=983040, sun=[64, 255, 0], sources=sources, light=bytes(field).hex(),
                leaves=[[s[0], s[1], s[3], s[4], field[s[4] * 28 + s[3]],
                         field[s[4] * 28 + s[3]] // 64] for s in sources if not s[2]])


def life(identity, *, death=None):
    return dict(id=identity, birth_tick=0, death_tick=death, species=0)


class ContractTests(unittest.TestCase):
    def test_arguments_replace_only_old_window(self):
        args = ['x', '--uptake-window', '626520:660480', '--reach-trace', 'r.jsonl']
        changed = capture.arguments(dict(args=args))
        self.assertEqual(changed, ['x', '--uptake-window', '974400:976305', '--uptake-window',
                                  '978240:979230', '--reach-trace', 'r.jsonl'])
        self.assertEqual(args[2], '626520:660480')
        for bad in ([], args + ['--uptake-window', '1:2'], ['--uptake-window', '15:30']):
            with self.assertRaises(RuntimeError): capture.arguments(dict(args=bad))

    def test_signed_ray_rounding_edges_and_no_self_cell(self):
        self.assertEqual(audit.uptake.rays(7)[2 * 28 + 2], (30, 1))
        self.assertEqual(audit.uptake.rays(-7)[2 * 28 + 2], (30, 3))
        self.assertEqual(audit.uptake.rays(12)[5 * 28], ())
        self.assertEqual(audit.uptake.rays(-12)[5 * 28 + 27], ())
        self.assertEqual(audit.uptake.rays(0)[2 * 28 + 2], (30, 2))
        self.assertEqual(audit.uptake.rays(0)[2], ())
        for ray in (-13, 13, True):
            with self.assertRaises(RuntimeError): audit.uptake.rays(ray)

    def test_per_cell_saturation_neighbors_and_floor(self):
        sources = ((0, 1, 0, 0, 0, 200, 66), (1, 2, 0, 0, 0, 200, 66))
        grid = audit.uptake.opacity(sources, 20, 'actual')
        self.assertEqual(grid[:3], (255, 132, 0))
        self.assertEqual(grid[27], 0)  # Left overflow cannot wrap onto the other edge.
        field = audit.uptake.field(grid, 255, 0)
        self.assertEqual(field[28:31], [24, 123, 255])
        self.assertEqual(audit.uptake.field(grid, 24, -12), [24] * 392)

    def test_independent_cell_and_ray_reconstruction_all_directions(self):
        sources = ((0, 1, 0, 0, 0, 200, 66), (1, 2, 1, 0, 0, 200, 66),
                   (2, 3, 0, 12, 5, 38, 12), (3, 4, 0, 27, 10, 26, 8))
        grid = [min(255, sum(s[5] if s[3] == col else s[6] if abs(s[3] - col) == 1 else 0
                            for s in sources if s[4] == row)) for row in range(14) for col in range(28)]
        self.assertEqual(tuple(grid), audit.uptake.opacity(sources, 0, 'actual'))
        for ray in range(-12, 13):
            expected = []
            for row in range(14):
                for col in range(28):
                    total = 0
                    for distance in range(1, row + 1):
                        # Round half away from zero, independently of the Q4 helper.
                        x = ray * distance / 16
                        offset = int(x + 0.5) if x >= 0 else -int(-x + 0.5)
                        source = col - offset
                        if not 0 <= source < 28: break
                        total += grid[(row - distance) * 28 + source]
                    expected.append(max(24, 153 - total))
            self.assertEqual(audit.uptake.field(tuple(grid), 153, ray), expected)

    def test_threshold_removal_gains_are_not_additive(self):
        for strength, shade, gain, joint in ((80, 16, 1, 1), (100, 50, 0, 1)):
            sources = [[0, 21, 0, 5, 0, shade, 0], [1, 22, 0, 5, 0, shade, 0]]
            local = max(24, strength - 2 * shade)
            row = dict(tick=1, sun=[64, strength, 0], sources=sources,
                       leaves=[[2, 20, 5, 1, local, local // 64]])
            out = audit.frozen_income(row)
            self.assertEqual(out['single_owner_gain'], {'21': gain, '22': gain})
            self.assertEqual(out['income']['open'] - out['income']['actual'], joint)
            self.assertNotEqual(sum(out['single_owner_gain'].values()), joint)

    def test_source_identity_and_current_step_death_timing(self):
        row = sample([[0, 20, 0, 2, 2, 26, 8], [1, 21, 1, 2, 1, 26, 8]])
        lives = {20: life(20, death=983040), 21: life(21, death=983025)}
        _, income, counts = audit.validate_light(row, lives)
        self.assertEqual(counts, {20: 1})
        self.assertEqual(income[20], 3)
        for identity, death in ((20, 983025), (21, 983040)):
            with self.assertRaisesRegex(RuntimeError, 'live/dead'):
                audit.validate_light(row, lives | {identity: life(identity, death=death)})
        for bad in ({}, lives | {20: life(20) | {'birth_tick': 983040}}):
            with self.assertRaisesRegex(RuntimeError, 'unknown/unborn'): audit.validate_light(row, bad)

    def test_duplicate_sources_or_leaves_and_wrong_field_rejected(self):
        row = sample([[0, 20, 0, 2, 2, 26, 8]])
        for change in ('source', 'leaf', 'light', 'income', 'species'):
            bad = copy.deepcopy(row)
            if change == 'source': bad['sources'] *= 2
            elif change == 'leaf': bad['leaves'] *= 2
            elif change == 'light': bad['light'] = '18' * 392
            elif change == 'income': bad['leaves'][0][-1] -= 1
            else: bad['sources'][0][5:] = [27, 9]
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                audit.validate_light(bad, {20: life(20)})

    def test_multiset_comparison_keeps_duplicates_gains_and_geometry_mismatch(self):
        a = [[2, 3, 63, 0], [2, 3, 63, 0]]
        b = [[2, 3, 64, 1], [2, 3, 64, 1]]
        pairs = audit.leaf_comparison(a, b)
        self.assertEqual(len(pairs), 2)
        self.assertEqual(sum(p['income_delta'] for p in pairs), 2)
        self.assertIsNone(audit.leaf_comparison(a, b[:1]))
        self.assertIsNone(audit.leaf_comparison(a, [[2, 4, 64, 1]] * 2))

    def test_ray_witness_preserves_clipping_and_unvisited_sources(self):
        row = sample([[0, 20, 0, 2, 2, 26, 8], [1, 21, 0, 2, 1, 200, 66],
                      [2, 22, 0, 2, 1, 200, 66], [3, 23, 0, 2, 0, 26, 8]])
        witness = audit.ray_witness(row, 2, 2)
        self.assertEqual(witness['light'], 24)
        self.assertEqual(witness['cells'][0]['cell_clipped'], 145)
        self.assertEqual(witness['cells'][0]['effective_reduction'], 231)
        self.assertFalse(witness['cells'][1]['visited'])
        self.assertEqual(witness['floor_clipped'], 50)
        self.assertEqual(witness['cells'][1]['sources'][0]['owner'], 23)

    def test_complete_and_ordered_observer_framing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'uptake.gz'
            rows = [dict(schema='landing-uptake-v1', stop=audit.STOP, windows=capture.SPANS),
                    *(dict(tick=t) for t in audit.ticks()),
                    dict(complete=True, tick=audit.STOP, run_hash='test')]
            def check(values):
                with gzip.open(path, 'wt') as stream:
                    stream.write('\n'.join(json.dumps(r) for r in values) + '\n')
                return list(audit.uptake.observation_rows(path, capture.SPANS, dict(run_hash='test')))
            self.assertEqual(len(check(rows)), 195)
            for bad in (rows[:-1], rows + [{}], rows[:1] + rows[2:],
                        rows[:1] + [rows[2], rows[1]] + rows[3:]):
                with self.assertRaises((RuntimeError, StopIteration)): check(bad)

    def test_existing_output_and_dangling_symlink_refused_before_input(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(capture, 'originals',
                side_effect=AssertionError('must not load originals')):
            out = Path(directory) / 'link'
            out.symlink_to(Path(directory) / 'absent')
            for target in (Path(directory), out):
                for method in (capture.collect, audit.export):
                    with self.assertRaisesRegex(RuntimeError, 'fresh'):
                        method(Path('/missing'), target)


@unittest.skipUnless(RESULT.exists(), 'winter-light result not yet retained')
class CapturedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(RESULT, 'rt') as stream: cls.value = json.load(stream)
        cls.rows, cls.analysis = cls.value['rows'], cls.value['analysis']

    def test_portable_offline_verification_cannot_launch_processes(self):
        with patch('subprocess.Popen', side_effect=AssertionError('unexpected process')), \
             patch('subprocess.run', side_effect=AssertionError('unexpected process')):
            audit.check_value(self.value)

    def test_neutrality_arguments_traces_results_and_pixels(self):
        originals = capture.originals()[1]
        for side in audit.SIDES:
            run = self.value['capture']['runs'][side]
            capture.check_run(run, originals[side], side)
            for change in ('args', 'trace', 'result', 'frame', 'path'):
                bad = copy.deepcopy(run)
                if change == 'args': bad['args'] += ['--ticks', '42']
                elif change == 'trace': bad['traces']['adult']['sha256'] = '0' * 64
                elif change == 'result': bad['result']['run_hash'] = 'bad'
                elif change == 'frame': bad['frame']['sha256'] = '0' * 64
                else: bad['traces']['uptake']['path'] = '../escape.gz'
                with self.subTest(side=side, change=change), self.assertRaises(RuntimeError):
                    capture.check_run(bad, originals[side], side)

    def test_all_cells_leaves_and_population_receipts_reconcile(self):
        c = self.analysis['counts']
        self.assertEqual(sum(x['frames'] for x in c.values()), 390)
        self.assertEqual(sum(x['light_cells'] for x in c.values()), 152880)
        self.assertEqual(sum(x['leaves'] for x in c.values()), 20475)
        self.assertEqual(sum(x['adult_receipts'] for x in c.values()), 2340)
        self.assertEqual(self.analysis['comparison']['geometry'],
                         dict(leaf_mismatch_ticks=[], self_shade_mismatch_ticks=[]))

    def test_target_unchanged_and_live_offspring_shade_recovers_every_leaf(self):
        arms = self.analysis['arms']
        self.assertEqual(arms['control']['geometry'], arms['candidate']['geometry'])
        child = next(p for p in arms['candidate']['owners'] if p['life']['id'] == 29)
        self.assertEqual([child['life'][k] for k in ('birth_tick', 'column', 'parent', 'generation')],
                         [652380, 0, 20, 3])
        self.assertEqual((child['observed_live_samples'], child['observed_dead_samples']), (195, 0))
        self.assertTrue(all(p['observed_dead_samples'] == 0 for a in arms.values() for p in a['owners']))
        matches = self.analysis['comparison']['candidate_owner_removal_matches']
        self.assertEqual(matches['29'], dict(compared_samples=195, equal_light_samples=195, equal_income_samples=195))

    def test_all_period_losses_recovered_without_summing_removal_gains(self):
        for n, expected in enumerate(((189, 77, 112), (95, 85, 10), (455, 310, 145))):
            a, b = (self.analysis['arms'][s]['periods'][n] for s in audit.SIDES)
            self.assertEqual((a['income']['actual'], b['income']['actual'], b['single_owner_gain']['29']), expected)
            cells = self.analysis['comparison']['periods'][n]['cells']
            self.assertEqual(sum(c['income_loss'] for c in cells), expected[2])
            self.assertEqual(sum(c['income_gain'] for c in cells), 0)
            self.assertEqual(a['income']['self_only'], b['income']['self_only'])
        morning = self.analysis['arms']['candidate']['periods'][0]
        self.assertNotEqual(sum(morning['single_owner_gain'].values()),
                            morning['income']['open'] - morning['income']['actual'])

    def test_first_income_difference_has_exact_threshold_and_ray_receipt(self):
        first = self.analysis['comparison']['first_income_difference']
        self.assertEqual((first['tick'], first['sun']), (974805, [27, 64, 7]))
        leaf = first['leaves'][0]
        self.assertEqual((leaf['column'], leaf['row'], leaf['control'], leaf['candidate']), (3, 12, [64, 1], [24, 0]))
        ray = first['rays']['candidate'][0]
        self.assertEqual((ray['ray_cell_opacity'], ray['effective_reduction'], ray['floor_clipped']), (42, 40, 2))
        self.assertEqual([s['opacity'] for c in ray['cells'] for s in c['sources']], [8, 26, 8])
        self.assertEqual({s['owner'] for c in ray['cells'] for s in c['sources']}, {29})

    def test_missing_misordered_and_changed_adult_or_light_receipts_fail(self):
        for change in ('missing', 'order', 'count', 'income', 'identity', 'history', 'sun'):
            bad = copy.deepcopy(self.rows['candidate'])
            if change == 'missing': bad['uptake'].pop()
            elif change == 'order': bad['uptake'][:2] = bad['uptake'][1::-1]
            elif change == 'count': bad['adult'][0]['plants'][0]['active_leaves'] += 1
            elif change == 'income': bad['uptake'][30]['leaves'][0][-1] += 1
            elif change == 'identity': bad['uptake'][0]['sources'][0][1] = 999
            elif change == 'history': bad['adult'][1]['plants'][0]['stages'][-1][0] -= 1
            else: bad['uptake'][0]['sun'][1] += 1
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                audit.validate_receipt(bad, 'candidate', self.value['capture']['runs']['candidate']['result'])

    def test_changed_provenance_checksum_or_summary_fails(self):
        for key, value in (('raw_manifest_sha256', '0' * 64), ('source_sha256', {}),
                           ('receipt_sha256', {}), ('analysis', {})):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                audit.check_value(self.value | {key: value})
        bad = copy.deepcopy(self.value['capture'])
        bad['provenance']['full_replays'] = 3
        with self.assertRaises(RuntimeError): capture.check_capture(bad)


if __name__ == '__main__': unittest.main()
