#!/usr/bin/env python3
"""Bounded second event, unchanged first history, and frozen capture contracts."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_second_opening as screen
from test_garden_landing_tools import run

BUILD = None
RESULT = screen.ROOT / 'benchmarks/garden-seasons/landing-second-opening-capture.json.gz'


class ContractTests(unittest.TestCase):
    def test_fixed_oldest_targets_and_all_first_recruits(self):
        saved, panel = screen.inputs()
        self.assertEqual([w['target'] for _, w in sorted(panel.items())], [20, 19, 26, 19, 19])
        self.assertEqual(sum(len(w['first_recruits']) for w in panel.values()), 5)
        for key, world in panel.items():
            lives = saved['runs']['treatment'][key]['result']['lineages']
            target = min((p for p in lives if p['death_tick'] is None and p['id'] not in world['focal']),
                         key=lambda p: (p['birth_tick'], p['id']))
            self.assertEqual(target['id'], world['target'])

    def test_twenty_five_calls_and_old_baselines(self):
        saved, panel = screen.inputs()
        self.assertEqual(len(screen.PHASES) * len(panel), 25)
        for key in panel:
            self.assertEqual(screen.arguments(key, 'baseline'), saved['runs']['treatment'][key]['args'])
            self.assertEqual(screen.arguments(key, 'treatment'), screen.arguments(key, 'repeat'))
            plain = screen.arguments(key, 'plain')
            self.assertIn('--turnover-at', plain)
            self.assertIn('--second-turnover-at', plain)
            self.assertNotIn('--stand-trace', plain)
            self.assertNotIn('--stand-dawn', plain)
            for flag in ('--root-dawn-reserve', '--seed-order', '--root-allocation-focal', '--root-all-offspring'):
                self.assertEqual(flag in plain, flag in screen.arguments(key, 'control'))

    def test_existing_output_refused_before_native(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(screen, 'native', side_effect=AssertionError('no run')):
            with self.assertRaisesRegex(RuntimeError, 'fresh output'):
                screen.collect(Path(tmp), Path('/missing'), 2)


@unittest.skipUnless(BUILD is not None, 'native executable not selected')
class NativeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='landing-second-opening-test-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.model = self.root / 'model.tgl'
        self.model.write_bytes(screen.followup.previous.late.population.load_model()[1])
        self.cli = BUILD / 'toy-factory-garden-landing'

    def native(self, *args, **kwargs):
        value = run([self.cli, *args], **kwargs)
        return json.loads(value) if value else None

    def args(self, stop=3, first=None, second=None):
        args = ['placement-replay', self.model, 'rainfed-crowded', '0x940cfdc4', '--ticks', stop * screen.DAY,
                '--climate', 'seasonal', '--ledger', '--shoot-reserve', 'on', '--seed-placement', 'spacing']
        if first is not None:
            args += ['--turnover-at', 3 * screen.DAY, '--turnover-lineage', first]
        if second is not None:
            args += ['--second-turnover-at', 4 * screen.DAY, '--second-turnover-lineage', second]
        return args

    def targets(self):
        plain = self.native(*self.args())
        first = min(p['id'] for p in plain['lineages'] if p['death_tick'] is None and
                    p['birth_tick'] + screen.DAY < plain['tick'])
        before = self.native(*self.args(4, first))
        second = min(p['id'] for p in before['lineages'] if p['death_tick'] is None and
                     p['birth_tick'] + screen.DAY < before['tick'])
        return first, second, before

    def test_second_death_is_post_observation_and_not_export(self):
        first, second, before = self.targets()
        traces = [self.root / (label + '.jsonl') for label in ('before', 'second')]
        for path, target in zip(traces, (None, second), strict=True):
            result = self.native(*self.args(4, first, target), '--reach-trace', path)
        self.assertEqual(traces[0].read_bytes(), traces[1].read_bytes())
        event = result['second_turnover_probe']
        self.assertEqual(event['before_world_hash'], before['world_hash'])
        self.assertEqual(event['before_run_hash'], before['placement_run_hash'])
        for field in ('turnover_probe', 'plant_slots', 'nodes', 'seed_bank', 'seeds'):
            self.assertEqual(result[field], before[field])
        expected = copy.deepcopy(before['lineages'])
        next(p for p in expected if p['id'] == second).update(death_tick=4 * screen.DAY, environmental_death=True)
        self.assertEqual(result['lineages'], expected)
        self.assertEqual(result['living'], before['living'] - 1)
        self.assertEqual(result['deaths'], before['deaths'] + 1)
        self.assertEqual(result['kind'], 'landing-turnover-pair-replay')
        expected_hash = screen.first.probe_hash(result['placement_run_hash'], 3 * screen.DAY, first)
        self.assertEqual(result['run_hash'], screen.first.probe_hash(expected_hash, 4 * screen.DAY, second))

    def test_repeat_and_observer_neutrality(self):
        first, second, _ = self.targets()
        values, frames, traces = [], [], []
        for label in ('treatment', 'repeat', 'plain'):
            frame, trace = self.root / (label + '.raw'), self.root / (label + '.jsonl')
            extra = [] if label == 'plain' else ['--reach-trace', trace]
            values.append(self.native(*self.args(6, first, second), '--framebuffer', frame, *extra))
            frames.append(frame.read_bytes())
            if extra:
                traces.append(trace.read_bytes())
        self.assertEqual(values[0], values[1])
        self.assertEqual(values[0], values[2])
        self.assertEqual(frames[0], frames[1])
        self.assertEqual(frames[0], frames[2])
        self.assertEqual(traces[0], traces[1])

    def test_invalid_schedule_rejected_before_trace_creation(self):
        first, second = 1, 2
        tails = [[], ['--second-turnover-at', 4 * screen.DAY], ['--second-turnover-lineage', second]]
        tails += [['--second-turnover-at', tick, '--second-turnover-lineage', identity]
                  for tick, identity in ((0, second), (2 * screen.DAY, second), (3 * screen.DAY, second),
                                         (4 * screen.DAY + 1, second), (7 * screen.DAY, second),
                                         (4 * screen.DAY, first), (4 * screen.DAY, 0), (4 * screen.DAY, 4097))]
        tails += [['--second-turnover-at', 4 * screen.DAY, '--second-turnover-lineage', second,
                   '--second-turnover-' + flag, value] for flag, value in (('at', 5 * screen.DAY), ('lineage', 3))]
        for i, tail in enumerate(tails[1:]):
            path = self.root / f'invalid-{i}.jsonl'
            self.native(*self.args(6, first), *tail, '--reach-trace', path, valid=False)
            self.assertFalse(path.exists())
        for args in (self.args(6, None, second), self.args(6, first, second)):
            if '--ledger' in args:
                args.remove('--ledger')
            self.native(*args, valid=False)
        self.native(*self.args(6, None, second), valid=False)
        for command in ('budget-replay', 'vacancy-replay'):
            args = self.args(6, first, second)
            args[0] = command
            self.native(*args, valid=False)


@unittest.skipUnless(RESULT.exists(), 'capture not retained yet')
class CapturedTests(unittest.TestCase):
    def test_capture_offline_and_mutations_rejected(self):
        with gzip.open(RESULT, 'rt') as stream:
            value = json.load(stream)
        with patch('subprocess.run', side_effect=AssertionError('no native')), \
             patch('subprocess.Popen', side_effect=AssertionError('no native')):
            screen.check_capture(value)
            key = sorted(value['panel'])[0]
            run = value['runs']['treatment'][key]
            for field in ('lineage', 'tick', 'before_run_hash'):
                damaged = copy.deepcopy(run['result'])
                damaged['second_turnover_probe'][field] = 'bad'
                with self.assertRaises(RuntimeError):
                    screen.check_result(damaged, key, 'treatment')
            damaged = copy.deepcopy(run)
            damaged['receipts']['stand']['prefix_sha256'] = 'bad'
            with self.assertRaisesRegex(RuntimeError, 'pre-event'):
                screen.check_run(damaged, key, 'treatment', value['runs']['baseline'][key])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve() if args.build else None
    NativeTests.__unittest_skip__ = BUILD is None
    unittest.main(argv=[__file__, *rest])
