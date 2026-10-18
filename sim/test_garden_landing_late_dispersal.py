#!/usr/bin/env python3
"""Late support contracts, native observer parity and portable evidence checks."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_late_dispersal as probe
from garden_landing_reach import support as narrow_support

BUILD = None
RESULT = probe.ROOT / 'benchmarks/garden-seasons/landing-late-dispersal-results.json.gz'


class Contracts(unittest.TestCase):
    def test_support_all_origins_traits_and_aliases(self):
        for origin in range(28):
            for trait in range(-2, 3):
                narrow = probe.support(origin, trait, False)
                broad = probe.support(origin, trait, True)
                self.assertEqual(narrow, narrow_support(origin, trait))
                self.assertEqual(broad[4:10], narrow)
                self.assertEqual(len(broad), 14)
                self.assertTrue(all(0 <= c < 28 for c in broad))
        self.assertEqual(probe.support(0, 0, True), [c for c in range(3, 10) for _ in range(2)])
        for args in ((28, 0, True), (0, 3, False), (True, 0, True), (0, 0, 1)):
            with self.assertRaises(RuntimeError): probe.support(*args)

    def test_build_isolation(self):
        base = {k: 'OFF' for k in ('TOY_FACTORY_GARDEN_WIDE_DISPERSAL', 'TOY_FACTORY_GARDEN_LARGE_POOL')}
        base.update({'TOY_FACTORY_SIMULATOR_' + k: 'ON' for k in ('SANITIZERS', 'PROFILING')})
        for arm in probe.ARMS:
            settings = base | dict(zip(probe.FLAGS, ('ON' if arm.endswith('wick') else 'OFF', 'ON',
                                                    'ON' if arm in probe.CANDIDATES else 'OFF'), strict=True))
            probe.check_settings(settings, arm)
            for key in settings:
                bad = settings | {key: 'OFF' if settings[key] == 'ON' else 'ON'}
                with self.assertRaises(RuntimeError): probe.check_settings(bad, arm)

    def test_result_identity(self):
        pair = {}
        with patch.object(probe.previous, 'check_result') as check:
            probe.check_result({'late_dispersal_probe': probe.ENVIRONMENT}, pair, 'wide-cap')
            check.assert_called_once_with({}, pair, 'cap')
            for result, arm in (({}, 'wide-cap'), ({'late_dispersal_probe': probe.ENVIRONMENT}, 'cap')):
                with self.assertRaises(RuntimeError): probe.check_result(result, pair, arm)

    def fixture(self, tick=probe.AFTER + 60, wide=True, origin=13, column=4):
        lives = {1: dict(id=1, column=origin, birth_tick=0, death_tick=None)}
        seed = dict(parent=1, birth_tick=tick, column=column)
        p = dict(parent=1, column=column, origin=origin, dispersal=0,
                 choices=probe.support(origin, 0, wide and tick > probe.AFTER),
                 sites=probe.spacing_map((origin,)).hex())
        return p, [1], lives, seed

    def test_purchase_before_onset_is_narrow(self):
        p, slots, lives, seed = self.fixture(tick=probe.AFTER, column=6)
        probe.purchase_check(p, slots, lives, seed, True)
        p['choices'] = probe.support(13, 0, True)
        with self.assertRaises(RuntimeError): probe.purchase_check(p, slots, lives, seed, True)

    def test_purchase_clear_and_retained_dead_spacing(self):
        p, slots, lives, seed = self.fixture()
        probe.purchase_check(p, slots, lives, seed, True)
        lives[2] = dict(id=2, column=4, birth_tick=0, death_tick=500)
        with self.assertRaises(RuntimeError): probe.purchase_check(p, [1, 2], lives, seed, True)
        p['sites'] = probe.spacing_map((13, 4)).hex()
        # A blocked landing is invalid if another legal choice was clear.
        with self.assertRaisesRegex(RuntimeError, 'spacing-clear choice'):
            probe.purchase_check(p, [1, 2], lives, seed, True)

    def test_all_blocked_fallback_with_global_space(self):
        p, _, _, seed = self.fixture(column=4)
        lives = {i: dict(id=i, column=c, birth_tick=0, death_tick=None)
                 for i, c in enumerate((13, 4, 8, 17, 21), 1)}
        p['sites'] = probe.spacing_map(tuple(x['column'] for x in lives.values())).hex()
        sites = probe.purchase_check(p, list(lives), lives, seed, True)
        self.assertTrue(any(not m & 32 for m in sites))
        for key, value in (('dispersal', 3), ('origin', 28), ('parent', 2), ('column', 27)):
            with self.assertRaises(RuntimeError): probe.purchase_check(p | {key: value}, list(lives), lives, seed, True)

    def test_cohort_survival_and_censoring(self):
        start = probe.LATE
        parent = dict(id=1, parent=0, generation=0, birth_tick=0, death_tick=None, seeds_created=2)
        lives = [parent, dict(id=2, parent=1, generation=1, birth_tick=start + 15,
                             death_tick=start + 30, seeds_created=0),
                 dict(id=3, parent=1, generation=1, birth_tick=probe.STOP - probe.DAY,
                      death_tick=None, seeds_created=1),
                 dict(id=4, parent=3, generation=2, birth_tick=probe.STOP - 15,
                      death_tick=None, seeds_created=0)]
        r = probe.renewal(dict(lineages=lives, seeds=[dict(birth_tick=start), dict(birth_tick=start + 15)]))['late32']
        self.assertEqual((r['births'], r['purchases'], r['seed_parents'], r['successful_parents']), (3, 1, 1, 0))
        self.assertEqual(r['survival']['1'], dict(died=1, confirmed=1, censored=1))
        self.assertEqual(r['survival']['32'], dict(died=1, censored=2))

    def test_reach_histogram_requires_complete_lifetime(self):
        tick = probe.STOP - 120
        p, slots, lives, seed = self.fixture(tick=tick)
        seed |= dict(end_tick=None, outcome='pending')
        result = dict(seeds=[seed], lineages=list(lives.values()), tick=probe.STOP)
        record = dict(seed=[1, tick], purchase=p, slots=slots, samples=8,
                      mature_sites={k: {p['sites']: 1} for k in probe.PERIODS})
        summary = probe.reach_summary([record], result, True)
        self.assertEqual(summary['late32']['any_reachable_open'], 1)
        for key in probe.PERIODS:
            bad = copy.deepcopy(record)
            bad['mature_sites'][key] = {}
            with self.assertRaisesRegex(RuntimeError, 'missing checks'):
                probe.reach_summary([bad], result, True)

    def test_no_clobber(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(probe, 'inputs', side_effect=AssertionError):
            with self.assertRaisesRegex(RuntimeError, 'fresh late-dispersal output'):
                probe.collect(Path(tmp), 1)
            link = Path(tmp) / 'link'; link.symlink_to(Path(tmp) / 'missing')
            # Direct API rejects a dangling link too, before native calls.
            with self.assertRaises(RuntimeError): probe.collect(link, 1)

    def test_reach_framing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'reach.gz'
            rows = [{'schema': 'landing-reach-trace-v1'}, dict(tick=15, purchases=[], checks=[]),
                    dict(complete=True, tick=15)]
            for candidate, valid in ((rows, True), (rows[:-1], False), (rows + [{}], False),
                                     ([rows[0], rows[1] | {'tick': 30}, rows[2]], False)):
                with gzip.open(path, 'wt') as stream:
                    stream.write('\n'.join(json.dumps(row) for row in candidate) + '\n')
                if valid: self.assertEqual(list(probe.reach_rows(path, 15)), [rows[1]])
                else:
                    with self.assertRaises((RuntimeError, StopIteration)): list(probe.reach_rows(path, 15))


class NativeTests(unittest.TestCase):
    def test_zephyr_and_conflicting_builds_rejected(self):
        if BUILD is None: self.skipTest('supply --build for compiler checks')
        for defines in (['-D__ZEPHYR__=1', '-DTOY_FACTORY_GARDEN_LATE_UPTAKE_LIMIT=1'], [],
                        ['-DTOY_FACTORY_GARDEN_LATE_UPTAKE_LIMIT=1', '-DTOY_FACTORY_GARDEN_WIDE_DISPERSAL=1']):
            result = subprocess.run(['cc', '-x', 'c', '-fsyntax-only', '-I', str(probe.ROOT / 'src'), *defines, '-'],
                input='#include "garden_late_dispersal.h"\n', capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('error:', result.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            for index, flags in enumerate(([], ['LATE_UPTAKE_LIMIT', 'WIDE_DISPERSAL'], ['LATE_UPTAKE_LIMIT', 'LARGE_POOL'])):
                result = subprocess.run(['cmake', '-S', str(probe.ROOT / 'sim'), '-B', str(Path(tmp) / str(index)),
                    '-DTOY_FACTORY_GARDEN_LATE_DISPERSAL=ON',
                    *['-DTOY_FACTORY_GARDEN_' + flag + '=ON' for flag in flags]],
                    capture_output=True, text=True, timeout=30)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('CMake Error', result.stderr)

    def test_short_observer_parity_and_metadata(self):
        if BUILD is None: self.skipTest('supply --build for native integration')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'model.tgl').write_bytes(probe.population.load_model()[1])
            base = [str(BUILD / 'toy-factory-garden-landing'), 'placement-replay', 'model.tgl',
                    'rainfed-crowded', '0xf7ee4528', '--ticks', '3840', '--climate', 'seasonal',
                    '--ledger', '--shoot-reserve', 'on', '--seed-placement', 'spacing']
            plain = json.loads(subprocess.check_output(base, cwd=root, text=True))
            observed = json.loads(subprocess.check_output(base + ['--reach-trace', 'reach.jsonl'], cwd=root, text=True))
            self.assertEqual(plain, observed)
            settings = (BUILD / 'CMakeCache.txt').read_text()
            wide = 'TOY_FACTORY_GARDEN_LATE_DISPERSAL:BOOL=ON' in settings
            self.assertEqual(plain.get('late_dispersal_probe'), probe.ENVIRONMENT if wide else None)
            rows = [json.loads(line) for line in (root / 'reach.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows), 258)
            for row in rows[1:-1]:
                for p in row['purchases']:
                    self.assertEqual(p['choices'], probe.support(p['origin'], p['dispersal'], False))


@unittest.skipUnless(RESULT.exists(), 'late-dispersal evidence not exported yet')
class SavedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(RESULT, 'rt') as stream: cls.value = json.load(stream)

    def test_offline_reconciliation(self):
        with patch('subprocess.Popen', side_effect=AssertionError('verification must be offline')):
            probe.check_value(self.value)

    def test_reject_summary_and_evidence_corruption(self):
        pair = self.value['pairs'][0]
        arm = pair['arms']['wide-cap']
        old = arm['reach_summary']['late32']['blocked']
        try:
            arm['reach_summary']['late32']['blocked'] += 1
            with self.assertRaises(RuntimeError): probe.check_value(self.value)
        finally: arm['reach_summary']['late32']['blocked'] = old
        record = copy.deepcopy(arm['reach'][0])
        record['purchase']['choices'][0] = 255
        with self.assertRaises(RuntimeError):
            probe.reach_summary([record, *arm['reach'][1:]], arm['result'], True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve() if args.build else None
    unittest.main(argv=[__file__, *rest])
