"""Day-608 gate follow-up bounds, cohort censoring and archive safety."""

import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import subprocess

import local_results
import population_gates_long as follow


class FollowupTests(unittest.TestCase):
    @local_results.needs('leaf-population-gates-results.json.gz')
    def test_fixed_plan_and_authenticated_anchor(self):
        self.assertEqual((follow.WORKERS, follow.CALL_SECONDS, follow.BUDGET_SECONDS), (2, 180, 900))
        self.assertEqual(follow.DAYS, (0, 32, 192, 208, 220, 222, 224, 256, 384, 512, 608))
        self.assertEqual(len(follow.gates.roster()), 8)
        baseline, models, size = follow.inputs()
        self.assertEqual(baseline['schema'], follow.gates.ARCHIVE_SCHEMA)
        self.assertEqual(len(models), 3)
        self.assertGreater(size, 0)
        self.assertEqual(follow.arguments(dict(variant='both', mode='off')), ['--gate-long', 'both', 'off'])

    def test_age32_exact_boundaries_and_young_censoring(self):
        day = follow.score.DAY
        plants = [dict(id=1, birth_tick=576 * day, death_tick=None),
                  dict(id=2, birth_tick=576 * day + 15, death_tick=None),
                  dict(id=3, birth_tick=560 * day, death_tick=592 * day),
                  dict(id=4, birth_tick=560 * day, death_tick=592 * day + 15)]
        result = follow.cohort(plants, follow.STOP)
        self.assertEqual(result, dict(born=4, established=2, early_deaths=1, young_alive=1,
                                      living=2, lineages=[1, 2, 3, 4]))
        self.assertEqual(follow.cohort([], follow.STOP)['born'], 0)

    def test_unsafe_archive_rejected_before_writes(self):
        with tempfile.TemporaryDirectory(prefix='gates-long-unsafe-') as temporary:
            root = Path(temporary)
            archive, output = root / 'bad.gz', root / 'output'
            for name, digest in (('../escape', follow.prepare.sha(b'x')), ('safe', '0' * 64)):
                archive.write_bytes(gzip.compress(json.dumps(dict(schema=follow.ARCHIVE_SCHEMA,
                    files={name: digest}, blobs={digest: b'x'.hex()})).encode()))
                with self.assertRaises(ValueError):
                    follow.unpack(archive, output)
                self.assertFalse(output.exists())


@local_results.needs('leaf-population-gates-long-results.json.gz', 'leaf-population-gates-results.json.gz')
class PublishedFollowupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='published-gates-long-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.out = cls.root / 'evidence'
        cls.archive = follow.collect.ROOT / 'benchmarks/garden-seasons/leaf-population-gates-long-results.json.gz'
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native calls forbidden')):
            cls.result = follow.unpack(cls.archive, cls.out)

    def test_exact_offline_roundtrip_and_output_preservation(self):
        packed = self.root / 'repacked.gz'
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native calls forbidden')):
            follow.package(self.out, packed)
        self.assertEqual(packed.read_bytes(), self.archive.read_bytes())
        with self.assertRaises(ValueError):
            follow.unpack(self.archive, self.out)
        with self.assertRaises(FileExistsError):
            follow.package(self.out, packed)

    def test_new_generations_censoring_and_competitor_loss(self):
        a = self.result['analyses']
        self.assertEqual(self.result['calls'], 8)
        self.assertEqual([a[v]['cohorts']['born_after_switch']['born'] for v in follow.VARIANTS], [0, 1, 0, 6])
        self.assertEqual([a[v]['cohorts']['born_after_switch']['established'] for v in follow.VARIANTS],
                         [0, 1, 0, 3])
        self.assertEqual([a[v]['families'][1]['living'] for v in follow.VARIANTS], [0, 2, 0, 6])
        self.assertEqual([a[v]['families'][1]['founder_death_tick'] for v in follow.VARIANTS],
                         [855240, None, 855540, None])
        self.assertEqual(a['both']['cohorts']['born_after_switch']['young_alive'], 2)
        self.assertEqual(a['both']['renewal']['2']['renewal_children'], [0, 0, 0, 0, 0, 2])
        self.assertEqual(a['both']['renewal']['2']['key'][0], [1, 6])
        self.assertEqual(a['light']['renewal']['2']['key'][0], [0, 1])
        self.assertEqual([p['id'] for p in a['both']['shrub_lineages'] if p['generation'] >= 2 and p['established']],
                         [24, 28])
        self.assertEqual(a['both']['families'][2]['extinction_tick'], 2092920)
        self.assertEqual(a['light']['families'][2]['status'], 'living')

    def test_modified_summary_and_short_anchor_are_rejected(self):
        path = self.out / 'result.json'
        saved = path.read_bytes()
        try:
            changed = json.loads(saved)
            changed['analyses']['both']['cohorts']['born_after_switch']['established'] += 1
            path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, 'manifest differs'):
                follow.verify(self.out)
        finally:
            path.write_bytes(saved)
        baseline, models, size = follow.inputs()
        name = 'runs/none-off/timeline/tick-0000000000.raw'
        raw = follow.prepare.blob(baseline, name)
        corrupted = bytes((raw[0] ^ 1,)) + raw[1:]
        digest = follow.prepare.sha(corrupted)
        baseline['files'][name] = digest
        baseline['blobs'][digest] = corrupted.hex()
        with self.assertRaisesRegex(ValueError, 'short gate checkpoint differs'):
            follow.validate_outputs(self.out, baseline, models, size)

    def test_unchanged_day608_matches_original_population_archive(self):
        losses = follow.trace.losses
        raw = losses.ARCHIVE.read_bytes()
        self.assertEqual(follow.prepare.sha(raw), losses.ARCHIVE_SHA)
        original = json.loads(gzip.decompress(raw))
        _, models, size = follow.inputs()
        path = self.out / 'runs/none-off/timeline' / f'tick-{follow.STOP:010d}'
        value = json.loads(path.with_suffix('.json').read_bytes())
        projected = follow.gates.underlying(value, 'none', models, size, follow.STOP)
        name = f'runs/s1-g3-c4-58d7d6ca-rainfed-primary/timeline/tick-{follow.STOP:010d}'
        self.assertEqual(projected, json.loads(follow.prepare.blob(original, name + '.json')))
        self.assertEqual(path.with_suffix('.raw').read_bytes(), follow.prepare.blob(original, name + '.raw'))
        eligibility = {}
        for seed in follow.score.SEEDS:
            name = f'runs/s1-g3-c4-{seed}-rainfed-primary/stdout.json'
            value = json.loads(follow.prepare.blob(original, name))
            cutoff = follow.gates.AFTER
            living = [p['id'] for p in value['lineages'] if value['family_roots'][p['id'] - 1] == 2 and
                      p['birth_tick'] <= cutoff and (p['death_tick'] is None or p['death_tick'] > cutoff)]
            pending = sum(value['family_roots'][s['parent'] - 1] == 2 and s['birth_tick'] <= cutoff and
                          (s['end_tick'] is None or s['end_tick'] > cutoff) for s in value['seeds'])
            eligibility[seed] = (living, pending)
        self.assertEqual(eligibility, {'58d7d6ca': ([2, 14], 2), '9a903368': ([], 0),
                                       '6b9c1a3e': ([], 0), '59818bc3': ([7, 18], 0)})


if __name__ == '__main__':
    unittest.main()
