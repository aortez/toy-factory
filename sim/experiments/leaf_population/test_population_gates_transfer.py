"""Second-seed identity, shared-prefix renewal credit, and evidence boundaries."""

from dataclasses import FrozenInstanceError
import gzip
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
import subprocess

import local_results
import population_gates_transfer as transfer

follow, gates = transfer.follow, transfer.gates


@local_results.needs('leaf-population-results.json.gz')
class TransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline, cls.models, cls.size = transfer.inputs()

    def test_fixed_recipe_and_eligible_descendants(self):
        self.assertEqual(transfer.SEED, '59818bc3')
        self.assertEqual((follow.WORKERS, follow.CALL_SECONDS, follow.BUDGET_SECONDS), (2, 180, 900))
        self.assertEqual(len(gates.roster()), 8)
        self.assertEqual(transfer.arguments(dict(variant='both', mode='off')), ['--gate-transfer', 'both', 'off'])
        self.assertNotEqual(transfer.EXPERIMENT.collection_schema, follow.DEFAULT.collection_schema)
        self.assertNotEqual(transfer.EXPERIMENT.archive_schema, follow.DEFAULT.archive_schema)
        with self.assertRaises(FrozenInstanceError):
            transfer.EXPERIMENT.baseline_sha = 'changed'
        original = json.loads(transfer.prepare.blob(self.baseline, transfer.BASE_RUN + '/stdout.json'))
        prefix = transfer.score.history_prefix(original, gates.AFTER)
        living = [p['id'] for p in prefix['lineages'] if prefix['family_roots'][p['id'] - 1] == 2 and
                  p['death_tick'] is None]
        self.assertEqual(living, [7, 18])
        self.assertIsNotNone(prefix['lineages'][1]['death_tick'])

    def test_identity_does_not_accept_the_old_seed(self):
        source = json.loads(transfer.prepare.blob(self.baseline,
                            transfer.BASE_RUN + '/timeline/tick-0000000000.json'))
        derived = gates.derive(self.models, 'both')
        header = b'TGR1' + bytes((3, 2, 0, 0)) + struct.pack('<I', gates.AFTER) + derived
        value = source | dict(schema='garden-leaf-gate-replay-v1', controller_assignment='scheduled-founder-family',
            intervention=dict(kind='restore-leaf-gates', variant='both', founder=2, after_tick=gates.AFTER,
                              leaf_model_hex=derived.hex()), state_hex=header.hex() + source['state_hex'])
        self.assertEqual(gates.underlying(value, 'both', self.models, self.size, 0, seed=transfer.SEED), source)
        with self.assertRaisesRegex(ValueError, 'run conditions differ'):
            gates.underlying(value, 'both', self.models, self.size, 0)

    def test_shared_prefix_and_scoring_boundaries(self):
        day = transfer.score.DAY
        parents = (0, 0, 0, 2, 4, 4, 4, 4, 4, 2)
        births = (0, 0, 0, 100, 200, 209, 576, 576, 576, 220)
        plants = [dict(id=i + 1, parent=p, birth_tick=b * day, death_tick=None)
                  for i, (p, b) in enumerate(zip(parents, births, strict=True))]
        plants[6]['death_tick'] = 608 * day  # Death exactly at age 32 fails establishment.
        plants[8]['birth_tick'] += 15  # Beyond the birth window and insufficient follow-up.
        value = dict(ticks=follow.STOP, scenario='rainfed', lineages=plants, family_roots=[1, 2, 3] + [2] * 7)
        rows = transfer.qualifying_children(value)
        self.assertEqual([p['lineage'] for p in rows], [5, 6, 8])
        self.assertEqual([p['shared_prefix'] for p in rows], [True, False, False])
        self.assertEqual([p['window'] for p in rows], [0, 0, 5])

    def test_unsafe_and_wrong_experiment_archives_rejected_before_writes(self):
        with tempfile.TemporaryDirectory(prefix='gates-transfer-unsafe-') as temporary:
            root = Path(temporary)
            archive, output = root / 'bad.gz', root / 'output'
            for name, digest in (('../escape', transfer.prepare.sha(b'x')), ('safe', '0' * 64)):
                archive.write_bytes(gzip.compress(json.dumps(dict(schema=transfer.ARCHIVE_SCHEMA,
                    files={name: digest}, blobs={digest: b'x'.hex()})).encode()))
                with self.assertRaises(ValueError):
                    follow.unpack(archive, output, experiment=transfer.EXPERIMENT)
                self.assertFalse(output.exists())
            archive.write_bytes(gzip.compress(json.dumps(dict(schema=follow.ARCHIVE_SCHEMA,
                                                              files={}, blobs={})).encode()))
            with self.assertRaisesRegex(ValueError, 'archive schema differs'):
                follow.unpack(archive, output, experiment=transfer.EXPERIMENT)
            self.assertFalse(output.exists())


@local_results.needs('leaf-population-gates-transfer-results.json.gz')
class PublishedTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='published-gates-transfer-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.out = cls.root / 'evidence'
        cls.archive = transfer.collect.ROOT / 'benchmarks/garden-seasons/leaf-population-gates-transfer-results.json.gz'
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native calls forbidden')):
            cls.result = follow.unpack(cls.archive, cls.out, experiment=transfer.EXPERIMENT)

    def test_offline_roundtrip_and_recipe_separation(self):
        packed = self.root / 'repacked.gz'
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native calls forbidden')):
            follow.package(self.out, packed, experiment=transfer.EXPERIMENT)
        self.assertEqual(packed.read_bytes(), self.archive.read_bytes())
        with self.assertRaises(ValueError):
            follow.unpack(self.archive, self.out, experiment=transfer.EXPERIMENT)
        with self.assertRaises(FileExistsError):
            follow.package(self.out, packed, experiment=transfer.EXPERIMENT)
        with self.assertRaisesRegex(ValueError, 'protocol differs'):
            follow.verify(self.out)

    def test_survival_renewal_and_shared_prefix_accounting(self):
        a = self.result['analyses']
        self.assertEqual(self.result['calls'], 8)
        self.assertEqual([a[v]['families'][1]['living'] for v in gates.VARIANTS], [0, 2, 0, 2])
        self.assertEqual([a[v]['families'][1]['extinction_tick'] for v in gates.VARIANTS],
                         [1482000, None, 1482240, None])
        self.assertEqual([a[v]['cohorts']['born_after_switch']['born'] for v in gates.VARIANTS], [1, 2, 1, 1])
        self.assertEqual([a[v]['cohorts']['born_after_switch']['established'] for v in gates.VARIANTS], [1, 2, 1, 1])
        self.assertEqual([a[v]['cohorts']['born_after_switch']['living'] for v in gates.VARIANTS], [0, 0, 0, 1])
        self.assertEqual([a[v]['renewal']['2']['key'][0] for v in gates.VARIANTS],
                         [[1, 6], [1, 4], [1, 6], [1, 6]])
        self.assertEqual([a[v]['renewal']['2']['renewal_children'] for v in gates.VARIANTS],
                         [[1, 1, 0, 0, 0, 0], [2, 1, 0, 0, 0, 0],
                          [1, 1, 0, 0, 0, 0], [1, 0, 0, 0, 1, 0]])
        for v in gates.VARIANTS:
            self.assertEqual([p['lineage'] for p in a[v]['qualifying_children'] if p['shared_prefix']], [18])
            self.assertNotIn(18, a[v]['cohorts']['born_after_switch']['lineages'])
            self.assertEqual(a[v]['families'][2]['extinction_tick'], 399780)
        self.assertEqual([p['id'] for p in a['light']['shrub_lineages'] if p['death_tick'] is None], [7, 18])
        self.assertEqual([p['id'] for p in a['both']['shrub_lineages'] if p['death_tick'] is None], [18, 29])

    def test_changed_summary_and_resource_accounting_are_rejected(self):
        path = self.out / 'result.json'
        saved = path.read_bytes()
        try:
            changed = json.loads(saved)
            changed['analyses']['both']['cohorts']['born_after_switch']['born'] += 1
            path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, 'manifest differs'):
                follow.verify(self.out, experiment=transfer.EXPERIMENT)
        finally:
            path.write_bytes(saved)
        folder = self.out / 'runs/both-on/timeline'
        anchor = json.loads((folder / f'tick-{gates.STOP:010d}.json').read_bytes())
        resources = json.loads((folder / 'trace.json').read_bytes())
        resources['plant_days'][-1]['energy']['income'] += 1
        with self.assertRaisesRegex(ValueError, 'resource conservation'):
            transfer.trace.validate_trace(resources, anchor)


if __name__ == '__main__':
    unittest.main()
