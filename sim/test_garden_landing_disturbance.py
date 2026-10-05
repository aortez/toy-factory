#!/usr/bin/env python3
"""Fixed turnover panel, CLI isolation, environmental death and exact repeats."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_disturbance as screen
from test_garden_landing_tools import run

BUILD = None
RESULT = screen.ROOT / 'benchmarks/garden-seasons/landing-disturbance-capture.json.gz'


class ContractTests(unittest.TestCase):
    def test_fixed_targets_come_from_oldest_nonfocal_at_boundary(self):
        saved, panel = screen.inputs()
        self.assertEqual(len(panel), 5)
        self.assertEqual([p['target'] for p in panel.values()], [17, 17, 20, 17, 18])
        self.assertEqual(sum(len(p['focal']) for p in panel.values()), 7)
        for key, world in panel.items():
            eligible = [p for p in saved['runs']['baseline'][key]['result']['lineages']
                        if p['death_tick'] is None and p['id'] not in world['focal']]
            self.assertEqual(min(eligible, key=lambda p: (p['birth_tick'], p['id']))['id'], world['target'])

    def test_twenty_calls_and_untraced_keeps_every_policy_flag(self):
        saved, panel = screen.inputs()
        self.assertEqual(len(screen.PHASES) * len(panel), 20)
        for key in panel:
            self.assertEqual(screen.arguments(key, 'control'), saved['runs']['extension'][key]['args'])
            self.assertEqual(screen.arguments(key, 'treatment'), screen.arguments(key, 'repeat'))
            args = screen.arguments(key, 'plain')
            self.assertNotIn('--reach-trace', args)
            self.assertNotIn('--stand-start', args)
            self.assertNotIn('--stand-dawn', args)
            for flag in ('--root-dawn-reserve', '--seed-order', '--root-allocation-focal', '--root-all-offspring'):
                self.assertEqual(flag in args, flag in screen.arguments(key, 'control'))

    def test_existing_output_refused_before_native_calls(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(screen, 'native', side_effect=AssertionError('no run')):
            with self.assertRaisesRegex(RuntimeError, 'fresh output'):
                screen.collect(Path(tmp), Path('/missing'), 2)


@unittest.skipUnless(BUILD is not None, 'native executable not selected')
class NativeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='landing-turnover-test-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.model = self.root / 'model.tgl'
        self.model.write_bytes(screen.followup.previous.late.population.load_model()[1])
        self.cli = BUILD / 'toy-factory-garden-landing'

    def native(self, *args, **kwargs):
        raw = run([self.cli, *args], **kwargs)
        return json.loads(raw) if raw else None

    def args(self, stop=3 * screen.DAY, target=None, at=3 * screen.DAY):
        args = ['placement-replay', self.model, 'rainfed-crowded', '0x940cfdc4', '--ticks', stop,
                '--climate', 'seasonal', '--ledger', '--shoot-reserve', 'on', '--seed-placement', 'spacing']
        return args if target is None else args + ['--turnover-at', at, '--turnover-lineage', target]

    def target(self, result):
        return min(p['id'] for p in result['lineages'] if p['death_tick'] is None and
                   p['birth_tick'] + screen.DAY < result['tick'])

    def test_post_observation_death_does_not_export_body_or_seed_bank(self):
        before = self.native(*self.args())
        target = self.target(before)
        files = [self.root / (label + '.jsonl') for label in ('control', 'event')]
        for path, identity in zip(files, (None, target), strict=True):
            value = self.native(*self.args(target=identity), '--reach-trace', path)
        self.assertEqual(files[0].read_bytes(), files[1].read_bytes())
        event = value['turnover_probe']
        self.assertEqual(event['before_world_hash'], before['world_hash'])
        self.assertEqual(event['before_run_hash'], before['run_hash'])
        self.assertEqual(value['plant_slots'], before['plant_slots'])
        self.assertEqual(value['nodes'], before['nodes'])
        self.assertEqual(value['seed_bank'], before['seed_bank'])
        self.assertEqual(value['seeds'], before['seeds'])
        self.assertEqual(value['deaths'], before['deaths'] + 1)
        self.assertEqual(value['living'], before['living'] - 1)
        self.assertEqual(value['run_hash'], screen.probe_hash(value['placement_run_hash'], 3 * screen.DAY, target))
        expected = copy.deepcopy(before['lineages'])
        next(p for p in expected if p['id'] == target).update(death_tick=3 * screen.DAY, environmental_death=True)
        self.assertEqual(value['lineages'], expected)

    def test_exact_repeat_and_observer_neutrality(self):
        target = self.target(self.native(*self.args()))
        values, frames, traces = [], [], []
        for label in ('first', 'repeat', 'plain'):
            frame, trace = self.root / (label + '.raw'), self.root / (label + '.jsonl')
            extra = [] if label == 'plain' else ['--reach-trace', trace]
            values.append(self.native(*self.args(stop=5 * screen.DAY, target=target), '--framebuffer', frame, *extra))
            frames.append(frame.read_bytes())
            if extra: traces.append(trace.read_bytes())
        self.assertEqual(values[0], values[1])
        self.assertEqual(values[0], values[2])
        self.assertEqual(frames[0], frames[1])
        self.assertEqual(frames[0], frames[2])
        self.assertEqual(traces[0], traces[1])
        self.assertFalse(any(s['parent'] == target and s['birth_tick'] > 3 * screen.DAY for s in values[0]['seeds']))

    def test_invalid_or_incomplete_event_rejected(self):
        for at, target in ((0, 1), (screen.DAY, 1), (3 * screen.DAY + 1, 1),
                           (4 * screen.DAY, 1), (3 * screen.DAY, 0), (3 * screen.DAY, 4097)):
            with self.subTest(at=at, target=target):
                self.native(*self.args(at=at, target=target), valid=False)
        for tail in (['--turnover-at', 2 * screen.DAY], ['--turnover-lineage', 1],
                     ['--turnover-at', 2 * screen.DAY, '--turnover-at', 2 * screen.DAY, '--turnover-lineage', 1]):
            self.native(*self.args(), *tail, valid=False)
        args = self.args(target=1)
        args.remove('--ledger')
        self.native(*args, valid=False)
        args = self.args(target=1)
        args[0] = 'budget-replay'
        self.native(*args, valid=False)


@unittest.skipUnless(RESULT.exists(), 'capture not retained yet')
class CapturedTests(unittest.TestCase):
    def test_capture_verifies_without_processes(self):
        with gzip.open(RESULT, 'rt') as stream:
            value = json.load(stream)
        with patch('subprocess.run', side_effect=AssertionError('no native')), \
             patch('subprocess.Popen', side_effect=AssertionError('no native')):
            screen.check_capture(value)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve() if args.build else None
    NativeTests.__unittest_skip__ = BUILD is None
    unittest.main(argv=[__file__, *rest])
