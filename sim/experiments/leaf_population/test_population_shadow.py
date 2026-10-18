"""Independent leaf inference, coverage, accounting and safe shadow evidence."""

from copy import deepcopy
from collections import Counter
import gzip
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
import subprocess
import zlib

import population_shadow as shadow


def flat_model(renew=1):
    payload = struct.pack('<4sHHBBBB', b'LFN1', 1, 1, 0, 0, 0, 0)
    payload += bytes(32 + 88) + struct.pack('<2i', 0, renew) + bytes(16)
    return struct.pack('<4sHHII', b'TLF1', 1, 16, len(payload), zlib.crc32(payload)) + payload


def fixture():
    row = dict(tick=208 * 3840 + 15, lineage=2, parent=0, node=3, plant=1,
               inputs=[200, 0, 9, 5, 1, -1, 2, 1, 1, 9, 5], memory=[-1] * 8, actions=[1, 1, 1])
    data = dict(schema='garden-population-shadow-v1', complete=True, ticks=shadow.STOP,
                first_tick=208 * 3840, end_tick=224 * 3840, founder=2,
                applied_model='initial', models=list(shadow.score.MODELS), rows=[row])
    resources = dict(plant_days=[dict(lineage=2, day=208, observations=1, proposals=1,
                                     renewals=1, restored=55)])
    final = dict(family_roots=[1, 2, 3], lineages=[dict(parent=0, birth_tick=0, death_tick=None)] * 3)
    models = {m: flat_model() for m in shadow.score.MODELS}
    return data, resources, final, models


class ShadowTests(unittest.TestCase):
    def test_fixed_protocol(self):
        self.assertEqual((shadow.FIRST_DAY, shadow.END_DAY, shadow.STOP), (208, 224, 256 * 3840))
        self.assertEqual((shadow.WORKERS, shadow.CALL_SECONDS, shadow.BUDGET_SECONDS), (2, 180, 900))
        self.assertEqual(len(shadow.trace.roster()), 6)
        self.assertEqual({shadow.arguments(c)[5] for c in shadow.trace.roster()}, {'--shadow', '--trace'})

    def test_signed_division_clipping_relu_shifts_and_ties(self):
        self.assertEqual([shadow.divide(v, 3) for v in (-4, -2, 2, 4)], [-1, 0, 0, 1])
        inputs = [0] * 11
        inputs[5] = -1
        weights = [0] * 88
        weights[5] = 1
        model = (0, 0, [127] + [0] * 7, weights, [126, 0], [0] * 8 + [1] + [0] * 7)
        self.assertEqual(shadow.infer(model, inputs), (1, 1))
        inputs[5] = -10000
        self.assertEqual(shadow.infer(model, inputs), (0, -126))
        inputs[5] = 10000
        self.assertEqual(shadow.infer(model, inputs), (1, 1))
        shifted = (1, 1, model[2], model[3], [0, 0], model[5])
        self.assertEqual(shadow.infer(shifted, [0] * 11), (1, 31))
        self.assertEqual(shadow.infer(shadow.decode(flat_model(0)), inputs), (0, 0))
        self.assertEqual(shadow.infer(shadow.decode(flat_model(-1)), inputs), (0, -1))

    def test_decode_crc_length_and_bias(self):
        good = flat_model()
        shadow.decode(good)
        bad = bytearray(good)
        bad[-1] ^= 1
        for raw in (good[:-1], good + b'x', bytes(bad), flat_model(1000001)):
            with self.assertRaises(ValueError):
                shadow.decode(raw)

    def test_complete_daily_inference_and_accounting(self):
        args = fixture()
        shadow.validate_shadow(*args)
        mutations = (lambda d: d['rows'].clear(),
                     lambda d: d['rows'].append(deepcopy(d['rows'][0])),
                     lambda d: d['rows'][0].update(actions=[0, 1, 1]),
                     lambda d: d['rows'][0].update(lineage=1),
                     lambda d: d['rows'][0].update(tick=208 * 3840),
                     lambda d: d['rows'][0]['memory'].__setitem__(0, 128),
                     lambda d: d['rows'][0]['inputs'].__setitem__(2, 8),
                     lambda d: d['rows'][0]['inputs'].__setitem__(0, 255))
        for mutate in mutations:
            data = deepcopy(args[0])
            mutate(data)
            with self.assertRaises(ValueError):
                shadow.validate_shadow(data, *args[1:])

    def test_proposals_are_not_accepted_repairs(self):
        data, resources, final, models = fixture()
        data['rows'][0]['inputs'][2] = 8
        resources['plant_days'][0].update(renewals=0, restored=0)
        shadow.validate_shadow(data, resources, final, models)
        result = shadow.summarize(data)['founder']['all']
        self.assertEqual(result['proposals'], [1, 1, 1])
        self.assertEqual(result['immediately_affordable'], [0, 0, 0])
        self.assertEqual(shadow.summarize(data)['descendants']['all']['observations'], 0)

    def test_unsafe_archive_is_rejected_before_writes(self):
        with tempfile.TemporaryDirectory(prefix='shadow-unsafe-') as temporary:
            root = Path(temporary)
            source, target = root / 'bad.gz', root / 'output'
            for name, digest in (('../escape', shadow.prepare.sha(b'x')), ('safe', '0' * 64)):
                source.write_bytes(gzip.compress(json.dumps(dict(schema=shadow.ARCHIVE_SCHEMA,
                    files={name: digest}, blobs={digest: b'x'.hex()})).encode()))
                with self.assertRaises((ValueError, RuntimeError)):
                    shadow.unpack(source, target)
                self.assertFalse(target.exists())


class PublishedShadowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='published-shadow-test-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.out = cls.root / 'evidence'
        cls.archive = shadow.collect.ROOT / 'benchmarks/garden-seasons/leaf-population-shadow-results.json.gz'
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native calls forbidden')):
            cls.result = shadow.unpack(cls.archive, cls.out)

    def test_exact_archive_roundtrip_and_no_overwrite(self):
        packed = self.root / 'repacked.gz'
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native calls forbidden')):
            shadow.package(self.out, packed)
        self.assertEqual(self.archive.read_bytes(), packed.read_bytes())
        with self.assertRaises(ValueError):
            shadow.unpack(self.archive, self.out)
        with self.assertRaises(FileExistsError):
            shadow.package(self.out, packed)
        self.assertEqual(self.result['calls'], 6)

    def test_published_decisions_explanation_and_tamper_rejection(self):
        folder = self.out / 'runs/s1-g3-c4-on'
        data = json.loads((folder / 'timeline/shadow.json').read_bytes())
        resources = json.loads((folder / 'timeline/trace.json').read_bytes())
        final = json.loads((folder / 'stdout.json').read_bytes())
        _, models, _ = shadow.inputs()
        model = shadow.decode(models['s1-g3-c4'])
        control = shadow.decode(models['initial'])
        probe = [0, 0, 256, 512, 21, 0, 0, 4, 3, 9, 5]
        for network, threshold in ((control, 131), (model, 143)):
            choices = [light for light in range(256)
                       if shadow.infer(network, probe[:1] + [light] + probe[2:])[0]]
            self.assertEqual(min(choices), threshold)
        for energy, threshold in ((168, 190), (256, 188)):
            probe[1], probe[2] = 255, energy
            choices = [condition for condition in range(256)
                       if shadow.infer(model, [condition] + probe[1:])[0]]
            self.assertEqual(max(choices), threshold)
        rejected = [r for r in data['rows'] if r['lineage'] == 2 and r['actions'][:2] == [1, 0]]
        reasons = Counter()
        for row in rejected:
            _, h, scores = shadow.network(model, row['inputs'])
            self.assertEqual(scores, [0, 1 - h[0] - h[1]])
            reasons['both' if h[0] and h[1] else 'light' if h[0] else 'condition-energy'] += 1
            self.assertTrue(shadow.eligible(row))
        self.assertEqual(reasons, {'both': 14, 'light': 26, 'condition-energy': 60})
        self.assertEqual(sum(r['tick'] > 220 * 3840 for r in rejected), 3)
        self.assertEqual(self.result['analyses']['s1-g3-c4']['founder']['all']['proposals'], [175, 75, 57])
        changed = deepcopy(data)
        changed['rows'][0]['actions'][0] ^= 1
        with self.assertRaisesRegex(ValueError, 'independent inference'):
            shadow.validate_shadow(changed, resources, final, models)
        changed = deepcopy(data)
        changed['rows'].pop()
        with self.assertRaisesRegex(ValueError, 'daily observations'):
            shadow.validate_shadow(changed, resources, final, models)


if __name__ == '__main__':
    unittest.main()
