#!/usr/bin/env python3
"""Uptake neutrality, sparse trace boundaries, quantized shade and ordered soil use."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_uptake as probe
from test_garden_landing_tools import run

BUILD = None
RESULT = probe.ROOT / "benchmarks/garden-seasons/landing-uptake-results.json.gz"


def life(i, death=None):
    return {"id": i, "birth_tick": 0, "death_tick": death}


def scene(sources=(), leaves=(), roots=(), soil=None):
    before = soil or [0] * 308
    after = before.copy()
    for r in roots:
        after[r[4] * 28 + r[3]] = r[8]
    # Tick 3840 is noon, vertical rays.
    return {"tick": 3840, "sun": [64, 255, 0], "sources": list(sources), "roots": list(roots),
            "leaves": list(leaves), "soil_before": bytes(before).hex(), "soil_after": bytes(after).hex(),
            "light": bytes(probe.field(probe.opacity(tuple(tuple(s) for s in sources), 0, "actual"), 255, 0)).hex()}


class AttributionTests(unittest.TestCase):
    def test_rounding_symmetry_edges_and_own_cell_exclusion(self):
        self.assertEqual(probe.rays(8)[28 + 10], (9,))
        self.assertEqual(probe.rays(-8)[28 + 10], (11,))
        self.assertEqual(probe.rays(12)[28], ())
        self.assertEqual(probe.rays(0)[28 + 10], (10,))
        self.assertEqual(probe.rays(0)[10], ())

    def test_shadow_removals_are_overlapping_not_additive_shares(self):
        sources = [[1, 1, 0, 10, 0, 200, 0], [2, 2, 0, 10, 0, 200, 0], [3, 3, 1, 10, 0, 26, 0]]
        row = scene(sources, [[4, 1, 10, 1, 24, 0]])
        values = probe.attribute(row, {}, {i: life(i, 15 if i == 3 else None) for i in (1, 2, 3)}, partial=True)[1]
        self.assertEqual(values['energy'], [0, 3, 0, 0, 0, 0])
        # Removing any one class is insufficient despite a three-unit open-sky gap.
        row = scene([[1, 1, 0, 10, 0, 64, 0]], [[4, 1, 10, 1, 191, 2]])
        self.assertEqual(probe.attribute(row, {}, {1: life(1)}, partial=True)[1]['energy'], [2, 3, 3, 2, 2, 2])

    def test_dead_neighbor_and_cell_saturation(self):
        row = scene([[2, 2, 1, 10, 0, 128, 0]], [[4, 1, 10, 1, 127, 1]])
        t = probe.attribute(row, {}, {1: life(1), 2: life(2, 15)}, partial=True)[1]
        self.assertEqual(t['energy'], [1, 3, 1, 1, 3, 3])
        bad = copy.deepcopy(row)
        bad['sources'][0][2] = 0
        with self.assertRaisesRegex(RuntimeError, 'live/dead'):
            probe.attribute(bad, {}, {1: life(1), 2: life(2, 15)}, partial=True)

    def test_preexisting_dryness_and_same_step_competition_with_overflow(self):
        soil = [0] * 308
        soil[0] = 4
        roots = [[1, 1, 0, 0, 0, 3, 4, 3, 1, 511, 512],
                 [2, 1, 0, 0, 0, 3, 1, 1, 0, 512, 512],
                 [3, 2, 1, 0, 0, 3, 0, 0, 0, 10, 10],
                 [4, 2, 1, 1, 0, 3, 0, 0, 0, 10, 10]]
        row = scene(roots=roots, soil=soil)
        totals = probe.attribute(row, {}, {1: life(1), 2: life(2)}, partial=True)
        self.assertEqual(totals[1]['water'], [6, 4, 0, 2, 2, 0, 3])
        self.assertEqual(totals[2]['water'], [6, 0, 3, 3, 0, 3, 0])
        bad = copy.deepcopy(row)
        bad['roots'][1][6] += 1
        with self.assertRaisesRegex(RuntimeError, 'root transfer'):
            probe.attribute(bad, {}, {1: life(1), 2: life(2)}, partial=True)
        bad = copy.deepcopy(row)
        bad['roots'][0], bad['roots'][1] = bad['roots'][1], bad['roots'][0]
        with self.assertRaises(RuntimeError):
            probe.attribute(bad, {}, {1: life(1), 2: life(2)}, partial=True)

    def test_corrupt_grid_income_and_birth_rejected(self):
        row = scene(leaves=[[4, 1, 10, 1, 255, 3]])
        for changed in ('light', 'income', 'birth'):
            bad, lives = copy.deepcopy(row), {1: life(1)}
            if changed == 'light': bad['light'] = '00' + bad['light'][2:]
            elif changed == 'income': bad['leaves'][0][-1] = 2
            else: lives[1]['birth_tick'] = 3840
            with self.subTest(changed=changed), self.assertRaises(RuntimeError):
                probe.attribute(bad, {}, lives, partial=True)

    def test_empty_uptake_and_birth_endowment_are_not_income(self):
        row = scene()
        self.assertEqual(probe.attribute(row, {1: {'uptake': None}}, {1: life(1)})[1],
                         {'energy': [0] * 6, 'water': [0] * 7})


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='garden-uptake-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.binary = BUILD / 'toy-factory-garden-landing'
        (self.root / 'model.tgl').write_bytes(probe.population.load_model()[1])

    def args(self, directory, extra=()):
        directory.mkdir()
        (directory / 'frames').mkdir()
        (directory / 'model.tgl').write_bytes(probe.population.load_model()[1])
        c = probe.previous.cases()[0]['case']
        return [self.binary, *probe.population.arguments(c, 'candidate', 'trace', stop=120), *extra]

    def test_sparse_observer_on_off_exact_neutrality(self):
        a, b = self.root / 'on', self.root / 'off'
        extra = ['--uptake-trace', 'uptake.jsonl', '--uptake-window', '15:30', '--uptake-window', '90:120']
        x = json.loads(run(self.args(a, extra), cwd=a))
        y = json.loads(run(self.args(b), cwd=b))
        self.assertEqual(x, y)
        for name in ('f7ee4528-fixed-candidate-trace-adult.jsonl', 'f7ee4528-fixed-candidate-trace-stand.jsonl',
                     'frames/f7ee4528-fixed-candidate-trace.raw'):
            self.assertEqual((a / name).read_bytes(), (b / name).read_bytes())
        rows = [json.loads(line) for line in (a / 'uptake.jsonl').read_text().splitlines()]
        self.assertEqual([r['tick'] for r in rows[1:-1]], [15, 30, 90, 105, 120])
        self.assertEqual(rows[-1], {'complete': True, 'tick': 120, 'run_hash': x['run_hash']})
        adults = {r['tick']: r for r in probe.population.adults.read_trace(a / 'f7ee4528-fixed-candidate-trace-adult.jsonl')[1:-1]}
        lives = {p['id']: p for p in x['lineages']}
        for r in rows[1:-1]: probe.attribute(r, {p['id']: p for p in adults[r['tick']]['plants']}, lives)

    def test_bad_ranges_and_missing_pair_do_not_create_trace(self):
        values = ('0:15', '16:30', '15:16', '30:15', '15:', ':15', '15:30:45', '-15:30', '15:99999999999999999999', '15:135')
        for j, text in enumerate(values):
            directory = self.root / str(j)
            args = self.args(directory, ['--uptake-trace', 'uptake.jsonl', '--uptake-window', text])
            run(args, valid=False, cwd=directory)
            self.assertFalse((directory / 'uptake.jsonl').exists())
        for j, extra in enumerate((['--uptake-trace', 'uptake.jsonl'], ['--uptake-window', '15:30'],
            ['--uptake-trace', 'uptake.jsonl', '--uptake-window', '15:30', '--uptake-window', '30:45'])):
            directory = self.root / ('missing' + str(j))
            run(self.args(directory, extra), valid=False, cwd=directory)
            self.assertFalse((directory / 'uptake.jsonl').exists())

    def test_no_clobber(self):
        directory = self.root / 'existing'
        args = self.args(directory, ['--uptake-trace', 'uptake.jsonl', '--uptake-window', '15:120'])
        (directory / 'uptake.jsonl').write_text('keep this')
        run(args, valid=False, cwd=directory)
        self.assertEqual((directory / 'uptake.jsonl').read_text(), 'keep this')

    def test_maximum_window_count_and_one_past(self):
        for count, valid in ((64, True), (65, False)):
            directory = self.root / ('limit' + str(count))
            extra = ['--uptake-trace', 'uptake.jsonl']
            for i in range(count):
                extra += ['--uptake-window', f'{15 * (i + 1)}:{15 * (i + 1)}']
            args = self.args(directory, extra)
            for flag in ('--ticks', '--stand-stop', '--adult-stop'):
                args[args.index(flag) + 1] = '975'
            run(args, valid=valid, cwd=directory)
            if valid:
                rows = (directory / 'uptake.jsonl').read_text().splitlines()
                self.assertEqual(len(rows), 66)
            else:
                self.assertFalse((directory / 'uptake.jsonl').exists())


@unittest.skipUnless(RESULT.exists(), 'uptake capture not yet available')
class SavedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(RESULT, 'rt') as stream:
            cls.value = json.load(stream)

    def test_portable_saved_neutrality_and_accounting(self):
        with patch('subprocess.Popen', side_effect=AssertionError('verification must stay offline')):
            probe.check_value(self.value)

    def test_frozen_panel_and_distinct_failure_modes(self):
        arms = [a for c in self.value['cases'] for a in c['arms'].values()]
        self.assertEqual(sum(a['analysis']['counts']['frames'] for a in arms), 38111)
        self.assertEqual(sum(a['analysis']['counts']['roots'] for a in arms), 2857757)
        self.assertEqual(sum(a['analysis']['counts']['leaves'] for a in arms), 2688825)
        self.assertEqual(sum(len(a['analysis']['shortage_witnesses']) for a in arms), 646)
        self.assertEqual(sum(len(p['segments']) for a in arms for p in a['analysis']['histories']), 150)
        self.assertEqual(sum(len(s['samples']) for a in arms for p in a['analysis']['histories']
                             for s in p['segments']), 70439)
        for a in arms:
            for p in a['summary']:
                for w in p['windows']:
                    self.assertEqual(w['water']['without_earlier_other_gain'], 0)
                    self.assertEqual(w['water']['without_earlier_self_gain'], w['water']['earlier_depletion'])
        candidate = self.value['cases'][0]['arms']['candidate']
        mature = next(p for p in candidate['summary'] if p['id'] == 28)['windows'][0]
        self.assertEqual([mature['energy'][k] for k in probe.ENERGY], [364, 1528, 994, 733, 364, 733])
        for i, tick, energy in ((15, 460260, [0, 9, 1, 3, 0, 3]), (16, 533160, [0, 3, 0, 3, 0, 3])):
            sample = next(s for p in candidate['analysis']['histories'] if p['id'] == i
                          for w in p['segments'] for s in w['samples'] if s[0] == tick)
            self.assertEqual(sample[1], energy)

    def test_changed_selection_witness_or_historical_result_rejected(self):
        for kind in ('missing_sample', 'missing_witness', 'light', 'income', 'historical', 'extra_call'):
            value = copy.deepcopy(self.value)
            a = value['cases'][0]['arms']['candidate']
            if kind == 'missing_sample':
                a['analysis']['histories'][0]['segments'][0]['samples'].pop()
            elif kind == 'missing_witness':
                a['analysis']['shortage_witnesses'].pop()
            elif kind == 'light':
                row = a['analysis']['shortage_witnesses'][0]
                row['light'] = '00' + row['light'][2:]
            elif kind == 'income':
                a['analysis']['histories'][0]['segments'][0]['samples'][0][1][0] += 1
            elif kind == 'historical':
                a['runs']['off']['result']['tick'] -= 1
            else:
                value['full_replays'] += 1
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                probe.check_value(value)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', required=True, type=Path)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *rest])
