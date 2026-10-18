"""Scheduled gate derivation, explicit identity, bounded roster and archive safety."""

from copy import deepcopy
import gzip
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
import subprocess

import population_gates as gates


class GateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline, cls.models, cls.size = gates.shadow.inputs()

    def test_fixed_budget_and_roster(self):
        self.assertEqual(len(gates.roster()), 8)
        self.assertEqual({(r['variant'], r['mode']) for r in gates.roster()},
                         {(v, m) for v in gates.VARIANTS for m in ('off', 'on')})
        self.assertEqual((gates.WORKERS, gates.CALL_SECONDS, gates.BUDGET_SECONDS), (2, 180, 900))
        self.assertEqual(gates.AFTER, 798720)
        self.assertEqual(gates.DAYS, (0, 32, 192, 208, 220, 222, 224, 256))

    def test_derivation_changes_only_selected_units(self):
        original, control = (gates.shadow.decode(self.models[m]) for m in ('s1-g3-c4', 'initial'))
        for mask, variant in enumerate(gates.VARIANTS):
            actual = gates.shadow.decode(gates.derive(self.models, variant))
            self.assertEqual(actual[:2], original[:2])
            self.assertEqual(actual[4:], original[4:])
            for unit in range(8):
                expected = control if mask & (1 << unit) else original
                self.assertEqual(actual[2][unit], expected[2][unit])
                self.assertEqual(actual[3][unit * 11:(unit + 1) * 11], expected[3][unit * 11:(unit + 1) * 11])
        self.assertEqual(gates.derive(self.models, 'none'), self.models['s1-g3-c4'])
        self.assertNotEqual(gates.derive(self.models, 'both'), self.models['initial'])
        both = gates.shadow.decode(gates.derive(self.models, 'both'))
        # Both output-active units restored; retained unused units cannot affect choices.
        self.assertEqual(original[4:], control[4:])
        self.assertEqual(original[5][2:8] + original[5][10:], (0,) * 12)
        for condition in (0, 135, 188, 190, 192, 193, 255):
            for light in (0, 125, 130, 131, 139, 142, 143, 255):
                for energy in (0, 8, 168, 256):
                    inputs = [condition, light, energy, 512, 21, -76, 14, 4, 3, 9, 5]
                    self.assertEqual(gates.shadow.infer(both, inputs), gates.shadow.infer(control, inputs))

    def test_explicit_envelope_and_corruption(self):
        source = json.loads(gates.prepare.blob(self.baseline,
                    'runs/s1-g3-c4-on/timeline/tick-0000000000.json'))
        for mask, variant in enumerate(gates.VARIANTS):
            derived = gates.derive(self.models, variant)
            identity = dict(kind='restore-leaf-gates', variant=variant, founder=2,
                            after_tick=gates.AFTER, leaf_model_hex=derived.hex())
            header = b'TGR1' + bytes((mask, 2, 0, 0)) + struct.pack('<I', gates.AFTER) + derived
            wrapped = source | dict(schema='garden-leaf-gate-replay-v1',
                controller_assignment='scheduled-founder-family', intervention=identity,
                state_hex=header.hex() + source['state_hex'])
            self.assertEqual(gates.underlying(wrapped, variant, self.models, self.size, 0), source)
            for key, value in (('founder', 1), ('after_tick', gates.AFTER + 15), ('leaf_model_hex', '00')):
                bad = deepcopy(wrapped)
                bad['intervention'][key] = value
                with self.assertRaises(ValueError):
                    gates.underlying(bad, variant, self.models, self.size, 0)
            bad = wrapped | dict(state_hex=source['state_hex'])
            with self.assertRaises(ValueError):
                gates.underlying(bad, variant, self.models, self.size, 0)

    def test_unsafe_archive_rejected_before_writes(self):
        with tempfile.TemporaryDirectory(prefix='gates-unsafe-') as temporary:
            root = Path(temporary)
            archive, output = root / 'bad.gz', root / 'output'
            for name, digest in (('../escape', gates.prepare.sha(b'x')), ('safe', '0' * 64)):
                archive.write_bytes(gzip.compress(json.dumps(dict(schema=gates.ARCHIVE_SCHEMA,
                    files={name: digest}, blobs={digest: b'x'.hex()})).encode()))
                with self.assertRaises(ValueError):
                    gates.unpack(archive, output)
                self.assertFalse(output.exists())


class PublishedGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='published-gates-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.out = cls.root / 'evidence'
        cls.archive = gates.collect.ROOT / 'benchmarks/garden-seasons/leaf-population-gates-results.json.gz'
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native calls forbidden')):
            cls.result = gates.unpack(cls.archive, cls.out)

    def test_exact_archive_roundtrip_and_output_preservation(self):
        packed = self.root / 'repacked.gz'
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native calls forbidden')):
            gates.package(self.out, packed)
        self.assertEqual(packed.read_bytes(), self.archive.read_bytes())
        with self.assertRaises(ValueError):
            gates.unpack(self.archive, self.out)
        with self.assertRaises(FileExistsError):
            gates.package(self.out, packed)
        self.assertEqual(self.result['calls'], 8)

    def test_survival_is_not_new_recruitment_and_accounting_is_checked(self):
        a = self.result['analyses']
        self.assertEqual([a[v]['families'][1]['living'] for v in gates.VARIANTS], [0, 1, 0, 2])
        self.assertEqual([a[v]['families'][1]['founder_death_tick'] for v in gates.VARIANTS],
                         [855240, None, 855540, None])
        self.assertEqual([a[v]['founder_windows']['208-220']['renewals'] for v in gates.VARIANTS],
                         [75, 87, 98, 116])
        self.assertEqual([a[v]['founder_windows']['220-224']['energy_short'] for v in gates.VARIANTS],
                         [8, 6, 8, 0])
        self.assertTrue(all(a[v]['cohorts']['born_after_switch']['born'] == 0 for v in gates.VARIANTS))
        folder = self.out / 'runs/both-on'
        final = json.loads((folder / 'stdout.json').read_bytes())
        resources = json.loads((folder / 'timeline/trace.json').read_bytes())
        changed = deepcopy(resources)
        changed['plant_days'][-1]['energy']['income'] += 1
        with self.assertRaisesRegex(ValueError, 'resource conservation'):
            gates.trace.validate_trace(changed, final)
        baseline, models, size = gates.shadow.inputs()
        changed = deepcopy(final)
        changed['intervention']['after_tick'] += 15
        with self.assertRaisesRegex(ValueError, 'intervention identity'):
            gates.underlying(changed, 'both', models, size, gates.STOP)


if __name__ == '__main__':
    unittest.main()
