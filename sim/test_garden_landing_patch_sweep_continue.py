#!/usr/bin/env python3
"""Pinned partial-batch preservation and explicit continuation guards; no new simulation."""

import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_patch_sweep_continue as resume

RESULT = resume.ROOT / 'benchmarks/garden-seasons/landing-patch-sweep-results.json.gz'


class ContinuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch('subprocess.run', side_effect=AssertionError('no native')), \
             patch('subprocess.Popen', side_effect=AssertionError('no native')):
            cls.prior = resume.interrupted()

    def test_only_thirteen_missing_calls_in_original_order(self):
        calls = resume.provenance()['executed_calls']
        keys = sorted(self.prior['started']['panel'])
        self.assertEqual(calls, [dict(phase=p, key=k) for p, ks in
                         (('treatment', keys[2:]), ('repeat', keys), ('plain', keys)) for k in ks])
        self.assertEqual(len(calls), 13)
        self.assertEqual(len({(c['phase'], c['key']) for c in calls}), 13)
        self.assertFalse(any(c['key'] in self.prior['runs'].get(c['phase'], {}) for c in calls))

    def test_existing_marker_run_or_output_rejected_before_native(self):
        calls = self.prior['remaining']
        with tempfile.TemporaryDirectory() as tmp:
            root, output = Path(tmp), Path(tmp) / 'out.json.gz'
            resume.require_fresh(root, output, calls)
            path = root / calls[0]['phase'] / calls[0]['key']
            path.mkdir(parents=True)
            with patch.object(resume.screen, 'native', side_effect=AssertionError('no native')):
                with self.assertRaisesRegex(RuntimeError, 'no automatic resume'):
                    resume.complete(root, output, 2)
        for name in ('continuation', 'out.json.gz', 'capture.json', 'manifest.json', 'treatment.json'):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / name).touch()
                with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, 'outputs must be absent'):
                    resume.require_fresh(root, root / 'out.json.gz', calls)

    def test_dangling_run_symlink_is_not_a_fresh_target(self):
        calls = self.prior['remaining']
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / calls[0]['phase'] / calls[0]['key']
            path.parent.mkdir()
            path.symlink_to(root / 'missing', target_is_directory=True)
            with self.assertRaises(RuntimeError):
                resume.require_fresh(root, root / 'out.json.gz', calls)

    def test_twelve_saved_calls_are_never_relabelled_or_replaced(self):
        value = copy.deepcopy(self.prior['started'])
        value.update(continuation=resume.provenance(), analysis_sources=self.prior['analysis_sources'],
                     runs=copy.deepcopy(self.prior['runs']))
        for key in value['panel']:
            value['runs']['treatment'].setdefault(key, copy.deepcopy(value['runs']['control'][key]))
        value['gallery'] = dict(rows=[[f['id'] for f in row] for row in resume.groups(value)], width=504, height=1248, gap=8)
        # Only test the continuation checks here; the complete-capture validator
        # must reject this incomplete batch independently.
        with patch.object(resume.screen, 'check_capture'):
            resume.check_complete(value)
            key = sorted(value['panel'])[0]
            value['runs']['control'][key]['result']['living'] -= 1
            with self.assertRaisesRegex(RuntimeError, 'retained call was replaced'):
                resume.check_complete(value)
        with self.assertRaises(RuntimeError):
            resume.screen.check_capture(self.prior['started'])


@unittest.skipUnless(RESULT.exists(), 'complete capture not retained yet')
class CapturedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(RESULT, 'rt') as stream:
            cls.value = json.load(stream)

    def test_complete_capture_and_continuation_without_process(self):
        with patch('subprocess.run', side_effect=AssertionError('no native')), \
             patch('subprocess.Popen', side_effect=AssertionError('no native')):
            resume.check_complete(self.value)

    def test_rehashed_omission_or_changed_panel_still_rejected(self):
        for mutation in ('drop-call', 'change-frame-order', 'change-runner', 'change-event'):
            value = copy.deepcopy(self.value)
            key = sorted(value['panel'])[-1]
            if mutation == 'drop-call':
                del value['runs']['plain'][key]
            elif mutation == 'change-frame-order':
                value['gallery']['rows'].reverse()
            elif mutation == 'change-runner':
                value['continuation']['runner_sha256'] = '0' * 64
            else:
                value['runs']['treatment'][key]['result']['patch_sweep_probe']['events'][0]['first'] += 1
            value['receipt_sha256'] = resume.screen.fingerprint({k: v for k, v in value.items() if k != 'receipt_sha256'})
            with self.subTest(mutation=mutation), self.assertRaises(RuntimeError):
                resume.check_complete(value)


if __name__ == '__main__':
    unittest.main()
