#!/usr/bin/env python3
"""Follow-up boundaries and offline evidence validation; never launch a research world."""

import copy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_patch_followup as follow

RESULT = follow.ROOT / 'benchmarks/garden-seasons/landing-patch-followup-results.json.gz'


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch('subprocess.run', side_effect=AssertionError('no native')):
            cls.old = follow.prior()

    def test_thirty_six_calls_only_horizon_changes(self):
        calls = [(p, k) for p in follow.PHASES for k in follow.confirm.panel()]
        self.assertEqual(len(calls), 36)
        self.assertEqual(len(set(calls)), 36)
        self.assertEqual(follow.PHASES[:2], ('anchor-control', 'anchor-treatment'))
        for phase, key in calls:
            original = follow.confirm.arguments(key, 'plain' if phase == 'plain' else follow.arm(phase))
            args = follow.arguments(key, phase)
            for flag in ('--ticks', '--stand-stop', '--adult-stop'):
                if flag in args:
                    self.assertEqual(args[args.index(flag) + 1], str(follow.horizon(phase)))
                    args[args.index(flag) + 1] = original[original.index(flag) + 1]
            self.assertEqual(args, original)
        self.assertEqual(follow.sweep.schedule(follow.STOP), follow.sweep.schedule(follow.BASE))
        self.assertEqual(follow.sweep.schedule(follow.STOP)[-1]['tick'], 304 * follow.DAY)

    def test_fixed_cohort_censoring_death_boundary_and_chain(self):
        def life(i, born, parent=0, died=None, imposed=False):
            return dict(id=i, birth_tick=born * follow.DAY, parent=parent,
                        death_tick=None if died is None else died * follow.DAY, environmental_death=imposed)
        plants = [life(1, 192), life(2, 200, 1), life(3, 304, 2), life(4, 320, 3), life(5, 321, 4),
                  life(6, 300, 2, 316), life(7, 300, 2, 307, True)]
        old = follow.cohort(dict(tick=follow.BASE, lineages=plants[:-3] + plants[-2:]), follow.BASE)
        fixed = follow.cohort(dict(tick=follow.STOP, lineages=plants), follow.BASE)
        expanded = follow.cohort(dict(tick=follow.STOP, lineages=plants), follow.STOP)
        self.assertEqual([r['life']['id'] for r in fixed['cohort']], [2, 6, 7, 3, 4])
        self.assertEqual(fixed['survival']['16'], {'confirmed': 3, 'natural-death': 1, 'imposed-death': 1})
        self.assertNotIn('censored', fixed['survival']['32'])
        self.assertEqual(old['survival']['16']['censored'], 1)
        self.assertEqual(fixed['qualifying_pairs'], [[2, 3], [3, 4]])
        self.assertEqual(expanded['qualifying_pairs'], [[2, 3], [3, 4], [4, 5]])
        self.assertEqual(expanded['survival']['32']['censored'], 1)
        self.assertEqual(fixed['deepest_16_day_chain'], 3)

    def test_real_anchors_require_exact_results(self):
        for key in follow.confirm.panel():
            for arm in ('control', 'treatment'):
                result = self.old['runs'][arm][key]['result']
                follow.check_result(result, key, 'anchor-' + arm)
                with self.assertRaisesRegex(RuntimeError, 'day-320'):
                    follow.check_result(dict(result, living=result['living'] + 1), key, 'anchor-' + arm)

    def test_compression_preserves_bytes_and_does_not_delete_before_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw, packed = Path(tmp) / 'stand.jsonl', Path(tmp) / 'stand.jsonl.gz'
            data = b'{"tick":15}\n' * 200
            raw.write_bytes(data)
            receipt = follow.compressed_trace(raw, packed)
            self.assertEqual(raw.read_bytes(), data)
            self.assertEqual(gzip.decompress(packed.read_bytes()), data)
            self.assertEqual(receipt, dict(raw_sha256=hashlib.sha256(data).hexdigest(), raw_bytes=len(data)))
            with self.assertRaises(FileExistsError):
                follow.compressed_trace(raw, packed)

    def test_trace_tail_gaps_footer_and_prefix_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(follow, 'BASE', 30):
            path = Path(tmp) / 'reach.jsonl.gz'
            result = dict(tick=60, lineages=[], seeds=[])
            rows = [dict(schema='landing-reach-trace-v1'),
                    *(dict(tick=t, purchases=[], checks=[]) for t in (15, 30, 45, 60)), dict(complete=True, tick=60)]
            def save(values):
                path.write_bytes(gzip.compress(b''.join(json.dumps(r).encode() + b'\n' for r in values), mtime=0))
            save(rows)
            before = follow.trace_receipt(path, 'reach', result)
            for modified in (rows[:-1], rows + [dict(extra=True)], rows[:3] + rows[4:],
                             rows[:-1] + [dict(complete=False, tick=60)]):
                save(modified)
                with self.assertRaises((RuntimeError, ValueError)):
                    follow.trace_receipt(path, 'reach', result)
            altered = copy.deepcopy(rows)
            altered[1]['checks'].append('changed')
            save(altered)
            self.assertNotEqual(follow.trace_receipt(path, 'reach', result)['prefix_sha256'], before['prefix_sha256'])

    def test_portable_census_and_exposure(self):
        result = dict(tick=follow.STOP, lineages=[dict(id=1, birth_tick=0, death_tick=None)],
                      seeds=[], living=1, plant_slots=1)
        receipt = dict(prefix_sha256='0' * 64, boundary_sha256='1' * 64, purchases=[],
                       occupancy={'1/1': (follow.STOP - follow.BASE) // follow.STEP},
                       daily=[dict(tick=t, living=[1], stored=[1]) for t in range(follow.BASE, follow.STOP + follow.DAY, follow.DAY)])
        follow.check_receipt(receipt, 'stand', result)
        for change in ('missing-day', 'wrong-living', 'wrong-exposure'):
            broken = copy.deepcopy(receipt)
            if change == 'missing-day':
                broken['daily'].pop(2)
            elif change == 'wrong-living':
                broken['daily'][-1]['living'] = []
            else:
                broken['occupancy']['1/1'] -= 1
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                follow.check_receipt(broken, 'stand', result)

    def test_existing_outputs_refused_before_loading_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out, output = root / 'bundle', root / 'capture.json.gz'
            out.mkdir()
            with patch.object(follow, 'prior', side_effect=AssertionError('no input load')), \
                 self.assertRaisesRegex(RuntimeError, 'fresh separate outputs'):
                follow.collect(out, output, root / 'origin', root / 'build', 2)


@unittest.skipUnless(RESULT.exists(), 'follow-up capture not collected yet')
class CapturedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(RESULT, 'rt') as stream:
            cls.value = json.load(stream)

    def test_complete_without_launching_processes(self):
        with patch('subprocess.run', side_effect=AssertionError('no native')), \
             patch('subprocess.Popen', side_effect=AssertionError('no native')):
            follow.check_capture(self.value)

    def test_rehashed_omission_changed_history_and_analysis_are_rejected(self):
        key = next(iter(follow.confirm.panel()))
        for change in ('omit', 'event', 'prefix', 'cohort', 'census'):
            value = copy.deepcopy(self.value)
            run = value['runs']['treatment'][key]
            if change == 'omit':
                del value['runs']['plain'][key]
            elif change == 'event':
                run['result']['patch_sweep_probe']['events'][-1]['tick'] += follow.DAY
            elif change == 'prefix':
                run['receipts']['stand']['prefix_sha256'] = '0' * 64
            elif change == 'cohort':
                run['analysis']['fixed_cohort']['cohort'].pop()
            else:
                run['receipts']['stand']['daily'].pop()
            value['receipt_sha256'] = follow.sweep.fingerprint({k: v for k, v in value.items() if k != 'receipt_sha256'})
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                follow.check_capture(value)


if __name__ == '__main__':
    unittest.main()
