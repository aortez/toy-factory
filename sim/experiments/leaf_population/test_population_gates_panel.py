"""From-start activation, fixed panel boundaries, and unchanged scoring."""

from copy import deepcopy
import gzip
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest import mock

import population_gates_panel as panel

follow, gates, score = panel.follow, panel.gates, panel.score


class PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline, cls.models, cls.size = panel.inputs()

    def test_fixed_roster_and_bounded_recipe(self):
        plan = panel.roster()
        self.assertEqual(len(plan), 32)
        self.assertEqual(len({c['id'] for c in plan}), 32)
        self.assertEqual((follow.WORKERS, follow.CALL_SECONDS, follow.BUDGET_SECONDS), (2, 180, 900))
        self.assertEqual(follow.DAYS, (0, 32, 192, 208, 220, 222, 224, 256, 384, 512, 608))
        for off, on in zip(plan[::2], plan[1::2], strict=True):
            self.assertEqual((off['seed'], off['variant']), (on['seed'], on['variant']))
            self.assertEqual((off['mode'], on['mode']), ('off', 'on'))
            self.assertEqual(panel.arguments(off), ['--gate-panel', off['seed'], off['variant'], 'off'])
        self.assertEqual(len(follow.DEFAULT.roster()), 8)
        self.assertEqual(len(panel.transfer.EXPERIMENT.roster()), 8)

    def test_identity_requires_zero_activation_and_exact_seed(self):
        for seed in score.SEEDS:
            source = json.loads(panel.prepare.blob(self.baseline,
                                panel.base_run(seed) + '/timeline/tick-0000000000.json'))
            derived = gates.derive(self.models, 'both')
            header = b'TGR1' + bytes((3, 2, 0, 0)) + struct.pack('<I', 0) + derived
            value = source | dict(schema='garden-leaf-gate-replay-v1', controller_assignment='scheduled-founder-family',
                intervention=dict(kind='restore-leaf-gates', variant='both', founder=2, after_tick=0,
                                  leaf_model_hex=derived.hex()), state_hex=header.hex() + source['state_hex'])
            self.assertEqual(gates.underlying(value, 'both', self.models, self.size, 0,
                                             seed=seed, after_tick=0), source)
            with self.assertRaisesRegex(ValueError, 'intervention identity differs'):
                gates.underlying(value, 'both', self.models, self.size, 0, seed=seed)
            with self.assertRaisesRegex(ValueError, 'invalid gate activation'):
                gates.underlying(value, 'both', self.models, self.size, 0, seed=seed, after_tick=1)
            with self.assertRaisesRegex(ValueError, 'run conditions differ'):
                gates.underlying(value, 'both', self.models, self.size, 0, seed='98a89374', after_tick=0)

    def test_summary_caps_per_seed_and_preserves_censoring(self):
        seeds = {}
        for seed in score.SEEDS:
            original = json.loads(panel.prepare.blob(self.baseline, panel.base_run(seed) + '/stdout.json'))
            value = original | score.history_prefix(original, follow.STOP) | dict(ticks=follow.STOP)
            summary = panel.summarize(value)
            self.assertEqual(summary['cohorts']['born_by_switch']['born'], 0)
            self.assertTrue(all(not p['shared_prefix'] for p in summary['qualifying_children']))
            self.assertEqual(summary['cohorts']['born_after_switch']['established'],
                             summary['families'][1]['offspring']['established'])
            seeds[seed] = {v: deepcopy(summary) for v in gates.VARIANTS}
        for seed in score.SEEDS:
            seeds[seed]['both']['renewal']['2']['renewal_children'] = [5, 0, 1, 3, 0, 0]
        result = panel.aggregate(seeds)
        self.assertEqual(result['both']['capped_renewal_credits'], 20)
        self.assertEqual(result['both']['maximum_renewal_credits'], 48)
        self.assertEqual(result['both']['conditions'], 4)
        del seeds[score.SEEDS[0]]
        with self.assertRaisesRegex(ValueError, 'summary roster differs'):
            panel.aggregate(seeds)

    def test_unsafe_and_wrong_recipe_archives_rejected_before_writes(self):
        with tempfile.TemporaryDirectory(prefix='gates-panel-unsafe-') as temporary:
            root = Path(temporary)
            archive, output = root / 'bad.gz', root / 'output'
            for name, digest in (('../escape', panel.prepare.sha(b'x')), ('safe', '0' * 64)):
                archive.write_bytes(gzip.compress(json.dumps(dict(schema=panel.ARCHIVE_SCHEMA,
                    files={name: digest}, blobs={digest: b'x'.hex()})).encode()))
                with self.assertRaises(ValueError):
                    follow.unpack(archive, output, experiment=panel.EXPERIMENT)
                self.assertFalse(output.exists())
            archive.write_bytes(gzip.compress(json.dumps(dict(schema=panel.transfer.ARCHIVE_SCHEMA,
                                                              files={}, blobs={})).encode()))
            with self.assertRaisesRegex(ValueError, 'archive schema differs'):
                follow.unpack(archive, output, experiment=panel.EXPERIMENT)
            self.assertFalse(output.exists())


class PublishedPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='published-gates-panel-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.out = cls.root / 'evidence'
        cls.archive = panel.collect.ROOT / 'benchmarks/garden-seasons/leaf-population-gates-panel-results.json.gz'
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native calls forbidden')):
            cls.result = follow.unpack(cls.archive, cls.out, experiment=panel.EXPERIMENT)

    def test_offline_roundtrip_and_recipe_separation(self):
        packed = self.root / 'repacked.gz'
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native calls forbidden')):
            follow.package(self.out, packed, experiment=panel.EXPERIMENT)
        self.assertEqual(packed.read_bytes(), self.archive.read_bytes())
        with self.assertRaises(ValueError):
            follow.unpack(self.archive, self.out, experiment=panel.EXPERIMENT)
        with self.assertRaises(FileExistsError):
            follow.package(self.out, packed, experiment=panel.EXPERIMENT)
        with self.assertRaisesRegex(ValueError, 'protocol differs'):
            follow.verify(self.out, experiment=panel.transfer.EXPERIMENT)

    def test_outcomes_scoring_and_censored_young_child(self):
        a = self.result['analyses']
        self.assertEqual(self.result['calls'], 32)
        self.assertEqual([a['aggregate'][v]['capped_renewal_credits'] for v in gates.VARIANTS], [2, 16, 10, 4])
        self.assertEqual([a['aggregate'][v]['shrub_status']['living'] for v in gates.VARIANTS], [0, 2, 2, 1])
        self.assertEqual([a['aggregate'][v]['offspring']['established'] for v in gates.VARIANTS], [7, 35, 22, 13])
        expected = {'58d7d6ca': [0, 6, 4, 8], '9a903368': [0, 4, 2, 0],
                    '6b9c1a3e': [0, 0, 0, 0], '59818bc3': [0, 0, 0, 0]}
        for seed, counts in expected.items():
            self.assertEqual([a['seeds'][seed][v]['families'][1]['living'] for v in gates.VARIANTS], counts)
        light = a['seeds']['9a903368']['light']
        self.assertEqual(light['renewal']['2']['renewal_children'], [2, 1, 1, 2, 1, 1])
        self.assertIsNotNone(light['families'][1]['founder_death_tick'])
        self.assertEqual(light['max_shrub_generation'], 6)
        condition = a['seeds']['58d7d6ca']['condition']
        self.assertEqual(condition['cohorts']['born_after_switch']['young_alive'], 1)
        young = next(p for p in condition['shrub_lineages'] if p['id'] == 53)
        self.assertEqual(young['birth_tick'], 577 * score.DAY)
        self.assertFalse(young['established'])
        self.assertNotIn(53, [p['lineage'] for p in condition['qualifying_children']])
        both = a['seeds']['58d7d6ca']['both']
        self.assertEqual(both['checkpoints']['608']['living_species'], [0, 8, 0])
        self.assertEqual(both['renewal']['2']['renewal_children'], [4, 0, 0, 2, 0, 0])

    def test_changed_summary_and_activation_are_rejected(self):
        path = self.out / 'result.json'
        saved = path.read_bytes()
        try:
            changed = json.loads(saved)
            changed['analyses']['aggregate']['both']['capped_renewal_credits'] += 1
            path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, 'manifest differs'):
                follow.verify(self.out, experiment=panel.EXPERIMENT)
        finally:
            path.write_bytes(saved)
        seed = score.SEEDS[0]
        value = json.loads((self.out / 'runs' / f'{seed}-both-on' / 'stdout.json').read_bytes())
        value['intervention']['after_tick'] = gates.AFTER
        _, models, size = panel.inputs()
        with self.assertRaisesRegex(ValueError, 'intervention identity differs'):
            gates.underlying(value, 'both', models, size, follow.STOP, seed=seed, after_tick=0)


if __name__ == '__main__':
    unittest.main()
