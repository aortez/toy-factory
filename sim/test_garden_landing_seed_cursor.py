#!/usr/bin/env python3
"""Cursor CLI, independent order oracle, fixed cohorts and evidence guards."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_seed_cursor as screen
import garden_landing_order as historical
from test_garden_landing_tools import run

BUILD = None
D = screen.DAY


class CursorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        saved, models, _, _ = historical.load_inputs()
        cls.model_bytes = models[saved['models']['single-s6d697834-live']['model']]

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='seed-cursor-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cli = BUILD / 'toy-factory-garden-landing'
        self.model = self.root / 'model.tgl'
        self.model.write_bytes(self.model_bytes)

    def native(self, *args, **kwargs):
        raw = run([self.cli, *args], **kwargs)
        return json.loads(raw) if raw else None

    def args(self, stop, enabled=True):
        return ['placement-replay', self.model, 'rainfed-crowded', '0x940cfdc4',
                '--climate', 'seasonal', '--ticks', stop, '--ledger', '--shoot-reserve', 'on',
                '--seed-placement', 'spacing', *(['--seed-cursor-after', 3 * D] if enabled else [])]

    def test_prefix_and_identity(self):
        a = self.native(*self.args(3 * D, False))
        b = self.native(*self.args(3 * D))
        expected = copy.deepcopy(a)
        expected['seed_cursor_probe'] = dict(version=1, after=3 * D, last_buyer=0)
        expected['run_hash'] = screen.tagged(a['run_hash'], 3 * D)
        self.assertEqual(b, expected)
        self.assertNotEqual(a['run_hash'], b['run_hash'])

    def sample(self, name):
        paths = {k: self.root / (name + '-' + k + '.jsonl') for k in screen.sweep.KINDS}
        args = self.args(8 * D)
        for k, path in paths.items():
            args += ['--' + k + '-trace', path]
            if k != 'reach':
                args += ['--' + k + '-start', 3 * D, '--' + k + '-stop', 8 * D]
        frame = self.root / (name + '.raw')
        result = self.native(*args, '--stand-dawn', '--framebuffer', frame)
        packed = {}
        for k, path in paths.items():
            packed[k] = path.with_suffix('.gz')
            screen.previous.compressed_trace(path, packed[k])
        return result, packed, frame

    def test_repeats_observer_neutrality_and_independent_audit(self):
        result, paths, frame = self.sample('observed')
        other, copies, pixels = self.sample('repeat')
        plain_frame = self.root / 'plain.raw'
        plain = self.native(*self.args(8 * D), '--framebuffer', plain_frame)
        self.assertEqual(result, other)
        self.assertEqual(result, plain)
        self.assertEqual(frame.read_bytes(), pixels.read_bytes())
        self.assertEqual(frame.read_bytes(), plain_frame.read_bytes())
        self.assertEqual([p.read_bytes() for p in paths.values()], [p.read_bytes() for p in copies.values()])
        with patch.object(screen, 'BASE', 3 * D):
            rows, receipts = screen.extract(paths, result, 3 * D)
            audit = screen.analyze(rows, result, True)
            screen.check_audit_summary(audit, result, True)
            self.assertEqual(audit['last_buyer'], result['seed_cursor_probe']['last_buyer'])
            self.assertEqual(sum(audit['occupancy'].values()), 5 * D // screen.STEP)
            self.assertTrue(all(r['raw_bytes'] > 0 for r in receipts.values()))
            broken = copy.deepcopy(audit)
            first = next(iter(broken['plants'].values()))
            first['budget']['energy']['income'] += 1
            with self.assertRaises(RuntimeError):
                screen.check_audit_summary(broken, result, True)
            for fault in ('order', 'bank', 'fee', 'clock', 'missing'):
                bad = copy.deepcopy(rows)
                if fault == 'order':
                    bad[1][2].reverse()
                elif fault == 'bank':
                    bad[1][-1] += 1
                elif fault == 'fee':
                    bad[1][3][0][1][0][-1][0] += 1
                elif fault == 'clock':
                    bad[1][0] += screen.STEP
                else:
                    bad.pop()
                with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                    screen.analyze(bad, result, True)

    def test_invalid_flags_do_not_create_files(self):
        path = self.root / 'trace.jsonl'
        args = self.args(60, False)
        trace = ['--stand-trace', path, '--stand-start', 15, '--stand-stop', 60]
        for suffix in (['--seed-cursor-after', v] for v in (0, 61, -1, 1474561, '1x')):
            self.native(*args, *trace, *suffix, valid=False)
            self.assertFalse(path.exists())
        for suffix in (['--seed-cursor-after', 120], ['--seed-order', 'rotating', '--seed-order-after', 60],
                       ['--seed-replace-after', 60]):
            self.native(*args, *trace, '--seed-cursor-after', 60, *suffix, valid=False)
            self.assertFalse(path.exists())
        no_ledger = [v for v in args if v != '--ledger']
        self.native(*no_ledger, *trace, '--seed-cursor-after', 60, valid=False)
        no_spacing = list(args)
        no_spacing[no_spacing.index('spacing')] = 'off'
        self.native(*no_spacing, *trace, '--seed-cursor-after', 60, valid=False)
        self.assertFalse(path.exists())
        path.write_bytes(b'preserve')
        self.native(*args, *trace, '--seed-cursor-after', 60, valid=False)
        self.assertEqual(path.read_bytes(), b'preserve')


class OracleTests(unittest.TestCase):
    def test_scan_rejects_gap_truncation_and_trailing_bytes(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(screen, 'BASE', 30):
            path = Path(tmp) / 'trace.gz'
            rows = [dict(schema='landing-reach-trace-v1'),
                    *(dict(tick=t, purchases=[], checks=[]) for t in (15, 30, 45, 60)),
                    dict(complete=True, tick=60)]
            def save(values):
                path.write_bytes(gzip.compress(b''.join(json.dumps(r).encode() + b'\n' for r in values), mtime=0))
            save(rows)
            receipt = {}
            self.assertEqual(len(list(screen.scan(path, 'reach', dict(tick=60), receipt))), 3)
            self.assertEqual(receipt['raw_bytes'], len(gzip.decompress(path.read_bytes())))
            for changed in (rows[:-1], rows + [dict(extra=True)], rows[:3] + rows[4:],
                            rows[:-1] + [dict(complete=False, tick=60)]):
                save(changed)
                with self.assertRaises((RuntimeError, ValueError)):
                    list(screen.scan(path, 'reach', dict(tick=60), {}))

    def test_order_persists_and_uses_last_actual_buyer(self):
        lives = {i: dict(death_tick=None) for i in (1, 3, 8)}
        def visits(ids, bought=()):
            return [[i, i in bought] for i in ids]
        after = screen.BASE + 60
        self.assertEqual(screen.visit_order(after, [1, 3, 8], visits([3, 8, 1]), lives, True, 2), 2)
        self.assertEqual(screen.visit_order(after, [1, 3, 8], visits([8, 1, 3], (8, 1)), lives, True, 3), 1)
        self.assertEqual(screen.visit_order(after, [1, 3, 8], visits([1, 3, 8], (1,)), lives, True, 8), 1)
        lives[3]['death_tick'] = after
        self.assertEqual(screen.visit_order(after, [1, 3, 8], visits([8, 1, 3]), lives, True, 1), 1)
        with self.assertRaises(RuntimeError):
            screen.visit_order(after, [1, 3, 8], visits([3, 8, 1]), lives, True, 1)
        self.assertEqual(screen.visit_order(after + 15, [1, 3, 8], visits([1, 3, 8]), lives, True, 8), 8)
        self.assertEqual(screen.visit_order(after, [], [], {}, True, 8), 8)

    def test_horizon_censoring_and_exact_death_boundary(self):
        lives = [dict(id=1, parent=0, birth_tick=0, death_tick=None, species=0, environmental_death=False),
                 dict(id=2, parent=1, birth_tick=screen.BASE + 15, death_tick=None, species=0, environmental_death=False),
                 dict(id=3, parent=1, birth_tick=screen.BIRTH_STOP, death_tick=screen.BIRTH_STOP + 16 * D,
                      species=0, environmental_death=False),
                 dict(id=4, parent=1, birth_tick=screen.BIRTH_STOP + 15, death_tick=None, species=0, environmental_death=False)]
        result = dict(tick=screen.STOP, lineages=lives, seeds=[], living=3, plant_slots=3, nodes=12, seed_bank=0)
        out = screen.outcomes(result)
        self.assertEqual(out['survivors'], {'16': [2], '32': [2]})
        self.assertEqual([p['id'] for p in out['late_births']], [4])
        self.assertEqual(out['established_parents']['16'], [1])

    def test_purchase_fairness_does_not_pass_survival_gate(self):
        result = dict(tick=screen.STOP, lineages=[], seeds=[], living=0, plant_slots=0, nodes=0, seed_bank=0)
        runs = {p: {k: dict(result=copy.deepcopy(result)) for k in screen.previous.confirm.panel()}
                for p in ('fixed', 'cursor')}
        for k in runs['cursor']:
            runs['cursor'][k]['result']['seeds'] = [dict(parent=99, birth_tick=screen.BASE + 60, outcome='pending')]
        self.assertFalse(screen.decision(runs)['passes_diagnostic'])

    def test_protocol_calls_and_old_identity_wrapping(self):
        saved = screen.prior()
        calls = [(phase, key, screen.arguments(key, phase)) for phase in screen.PHASES for key in saved['panel']]
        self.assertEqual(len(calls), 36)
        for phase, key, args in calls:
            self.assertEqual(int(args[args.index('--ticks') + 1]), screen.horizon(phase))
            self.assertEqual('--seed-cursor-after' in args, screen.active(phase))
            self.assertEqual('--stand-trace' in args, phase != 'plain')
        for key in saved['panel']:
            old = saved['runs']['anchor-treatment'][key]['result']
            wrapped = screen.anchor_identity(old)
            screen.check_result(wrapped, key, 'anchor-cursor')
            self.assertEqual(wrapped['world_hash'], old['world_hash'])
            bad = copy.deepcopy(wrapped)
            bad['run_hash'] = old['run_hash']
            with self.assertRaises(RuntimeError):
                screen.check_result(bad, key, 'anchor-cursor')

    def test_existing_bundle_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(screen.sweep, 'native', side_effect=AssertionError('must not run')):
                with self.assertRaises(RuntimeError):
                    screen.collect(root, root / 'capture.gz', root, root, 1)


RESULT = screen.ROOT / 'benchmarks/garden-seasons/landing-seed-cursor-results.json.gz'


@unittest.skipUnless(RESULT.exists(), 'comparison has not been collected')
class CapturedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(RESULT, 'rt') as stream:
            cls.value = json.load(stream)

    def test_portable_receipt_without_native_processes(self):
        with patch('subprocess.run', side_effect=AssertionError('no native')), \
             patch('subprocess.Popen', side_effect=AssertionError('no native')):
            screen.check_capture(self.value)

    def test_rehashed_omissions_history_and_budgets_rejected(self):
        key = next(iter(self.value['panel']))
        for fault in ('missing', 'anchor', 'cursor', 'budget', 'survivor', 'pixels'):
            value = copy.deepcopy(self.value)
            run = value['runs']['cursor'][key]
            if fault == 'missing':
                del value['runs']['plain'][key]
            elif fault == 'anchor':
                value['runs']['anchor-cursor'][key]['result']['world_hash'] = '00000000'
            elif fault == 'cursor':
                run['audit']['last_buyer'] += 1
            elif fault == 'budget':
                next(iter(run['audit']['plants'].values()))['budget']['water']['income'] += 1
            elif fault == 'survivor':
                run['outcomes']['survivors']['16'].append(999)
            else:
                value['runs']['plain'][key]['frame']['sha256'] = '0' * 64
            value['receipt_sha256'] = screen.sweep.fingerprint({k: v for k, v in value.items() if k != 'receipt_sha256'})
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                screen.check_capture(value)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path, required=True)
    args, other = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *other])
