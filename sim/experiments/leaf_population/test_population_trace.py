"""Bounded trace roster, complete accounting and safe archive inputs."""

from copy import deepcopy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import subprocess

import population_trace as trace


def checks():
    return dict(checks=0, expired=0, germinated=0, light_min=0, light_max=0,
                moisture_min=0, moisture_max=0, masks={}, no_living_masks={}, open_sites={})


def fixture():
    state = dict(lineages=[dict(id=i, birth_tick=0, death_tick=None) for i in range(1, 4)],
                 family_roots=[1, 2, 3], seeds=[])
    flux = {k: 0 for k in ('before', 'after', 'income', 'overflow', 'endowment', 'upkeep_due',
                           'upkeep_paid', 'growth', 'seeds', 'discarded', 'repair')}
    rows = [dict(day=d, lineage=2, first_tick=d * 3840 + 15, last_tick=(d + 1) * 3840,
                 samples=256, born=False, died=False, energy=dict(flux), water=dict(flux),
                 renewals=0, proposals=0, observations=0, condition_before=0, condition_after=0,
                 condition_endowment=0, restored=0, worn=0) for d in range(256)]
    data = dict(schema='garden-population-trace-v1', complete=True, founder=2,
                ticks=trace.STOP, ecology_steps=65536, plant_days=rows,
                seeds=[], seed_days=[checks() for _ in range(256)])
    return data, state


class TraceTests(unittest.TestCase):
    def test_roster_and_budget(self):
        self.assertEqual(len(trace.roster()), 6)
        self.assertEqual({(r['model'], r['mode']) for r in trace.roster()},
                         {(m, s) for m in trace.score.MODELS for s in ('on', 'off')})
        self.assertEqual((trace.WORKERS, trace.CALL_SECONDS, trace.BUDGET_SECONDS), (2, 180, 900))

    def test_masks_separate_expiry_from_success_and_overlap(self):
        c = checks() | dict(checks=3, expired=1, germinated=1,
            masks={'0': 1, '36': 2}, no_living_masks={'36': 1}, open_sites={'7': 2})
        trace.check_histogram(c)
        for mutation in (dict(germinated=2), dict(checks=4), dict(no_living_masks={'36': 3}),
                         dict(open_sites={'28': 1}), dict(masks={'128': 3})):
            with self.assertRaises(ValueError):
                trace.check_histogram(c | mutation)

    def test_complete_daily_coverage_and_conservation(self):
        data, state = fixture()
        trace.validate_trace(data, state)
        mutations = (lambda d: d['plant_days'].pop(),
                     lambda d: d['plant_days'].append(deepcopy(d['plant_days'][0])),
                     lambda d: d['plant_days'][0]['energy'].update(income=1),
                     lambda d: d['plant_days'][1]['energy'].update(before=1, after=1),
                     lambda d: d['plant_days'][0].update(restored=1),
                     lambda d: d.update(complete=False))
        for mutate in mutations:
            changed = deepcopy(data)
            mutate(changed)
            with self.assertRaises(ValueError):
                trace.validate_trace(changed, state)

    def test_unsafe_or_corrupt_archive_never_creates_destination(self):
        with tempfile.TemporaryDirectory(prefix='trace-archive-test-') as temporary:
            root = Path(temporary)
            source, target = root / 'bad.gz', root / 'output'
            for name, digest in (('../escape', trace.prepare.sha(b'x')), ('safe', '0' * 64)):
                source.write_bytes(gzip.compress(json.dumps(dict(schema='garden-population-trace-evidence-v1',
                    files={name: digest}, blobs={digest: b'x'.hex()})).encode()))
                with self.assertRaises((ValueError, RuntimeError)):
                    trace.unpack(source, target)
                self.assertFalse(target.exists())


class PublishedTraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='published-trace-test-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.out = cls.root / 'evidence'
        cls.archive = trace.collect.ROOT / 'benchmarks/garden-seasons/leaf-population-trace-results.json.gz'
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native calls forbidden')):
            cls.result = trace.unpack(cls.archive, cls.out)

    def test_exact_archive_roundtrip_and_no_overwrite(self):
        packed = self.root / 'repacked.gz'
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native calls forbidden')):
            trace.package(self.out, packed)
        self.assertEqual(self.archive.read_bytes(), packed.read_bytes())
        with self.assertRaises(ValueError):
            trace.unpack(self.archive, self.out)
        with self.assertRaises(FileExistsError):
            trace.package(self.out, packed)
        self.assertEqual(self.result['calls'], 6)
        self.assertEqual(self.result['analyses']['s1-g3-c4']['family']['extinction_tick'], 864720)

    def test_published_terminal_seeds_and_rejected_counter_changes(self):
        folder = self.out / 'runs/s1-g3-c4-on'
        state = json.loads((folder / 'stdout.json').read_bytes())
        data = json.loads((folder / 'timeline/trace.json').read_bytes())
        for s in self.result['analyses']['s1-g3-c4']['terminal_seeds']:
            self.assertEqual(s['checks'], 8191)
            self.assertEqual(s['blockers']['spacing'], 8191)
        changed = deepcopy(data)
        changed['seeds'][-1]['attempts']['no_living_masks'] = {}
        with self.assertRaisesRegex(ValueError, 'no-living subset'):
            trace.validate_trace(changed, state)
        changed = deepcopy(data)
        changed['plant_days'][0]['energy']['repair'] += 9
        with self.assertRaisesRegex(ValueError, 'resource conservation'):
            trace.validate_trace(changed, state)


if __name__ == '__main__':
    unittest.main()
