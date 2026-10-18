"""Offline archive and derived-metric corruption checks; no simulator calls."""

import copy
import gzip
import json
import unittest

import collect_generalization as evidence

ARCHIVE = evidence.experiment.ROOT / 'benchmarks/garden-seasons/leaf-family-generalization-results.json.gz'


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = json.loads(gzip.decompress(ARCHIVE.read_bytes()))

    def setUp(self):
        self.bundle = copy.deepcopy(self.original)

    def data(self, name):
        return bytes.fromhex(self.bundle['blobs'][self.bundle['files'][name]])

    def value(self, name):
        return json.loads(self.data(name))

    def replace(self, name, raw):
        old = self.bundle['files'][name]
        identity = evidence.experiment.sha(raw)
        self.bundle['files'][name] = identity
        self.bundle['blobs'][identity] = raw.hex()
        if old not in self.bundle['files'].values():
            del self.bundle['blobs'][old]

    def test_roundtrip_and_published_pixels(self):
        self.assertEqual(evidence.verify(self.bundle, ARCHIVE.parent / 'frames'), self.bundle['summary'])

    def test_hash(self):
        identity = self.bundle['files']['growth.tgl']
        self.bundle['blobs'][identity] += '00'
        with self.assertRaisesRegex(ValueError, 'archive hash differs'):
            evidence.verify(self.bundle)

    def test_path_escape(self):
        self.bundle['files']['../escape'] = next(iter(self.bundle['blobs']))
        with self.assertRaisesRegex(ValueError, 'unsafe evidence path'):
            evidence.verify(self.bundle)

    def test_no_selection_or_training(self):
        name = 'started.json'
        scope = self.value(name)
        scope['selected_model'] = 's2-g3-c1'
        self.replace(name, json.dumps(scope).encode())
        with self.assertRaisesRegex(ValueError, 'scope/plan differs'):
            evidence.verify(self.bundle)

    def test_model_identity(self):
        self.replace('models/initial.tlf', self.data('models/s1-g3-c4.tlf'))
        with self.assertRaisesRegex(ValueError, 'model provenance differs'):
            evidence.verify(self.bundle)

    def test_source_identity(self):
        name = 'source/sim/experiments/leaf_generalization/run_generalization.py'
        self.replace(name, self.data(name) + b'\n')
        with self.assertRaisesRegex(ValueError, 'source snapshot differs'):
            evidence.verify(self.bundle)

    def test_seed_audit_must_precede_runs(self):
        name = 'seed-audit.json'
        audit = self.value(name)
        audit['checked_utc'] = '2099-01-01T00:00:00+00:00'
        self.replace(name, json.dumps(audit).encode())
        with self.assertRaisesRegex(ValueError, 'seed audit was late'):
            evidence.verify(self.bundle)

    def test_submission_deadline(self):
        name = 'runs/call0004/started.json'
        start = self.value(name)
        start['since_first_seconds'] = 2700
        self.replace(name, json.dumps(start).encode())
        with self.assertRaisesRegex(ValueError, 'submission ceiling exceeded'):
            evidence.verify(self.bundle)

    def test_confirmations_are_serial(self):
        name = 'runs/call0101/started.json'
        start = self.value(name)
        start['submitted_utc'] = self.value('runs/call0100/started.json')['submitted_utc']
        self.replace(name, json.dumps(start).encode())
        with self.assertRaisesRegex(ValueError, 'batch/serial ordering differs'):
            evidence.verify(self.bundle)

    def test_pixels_even_with_rehash(self):
        name = 'runs/call0004/frame.raw'
        pixels = bytearray(self.data(name))
        pixels[0] ^= 1
        self.replace(name, bytes(pixels))
        receipt_name = 'runs/call0004/checked.json'
        receipt = self.value(receipt_name)
        receipt['frame_sha256'] = evidence.experiment.sha(pixels)
        self.replace(receipt_name, json.dumps(receipt).encode())
        with self.assertRaises(ValueError):
            evidence.verify(self.bundle)

    def test_derived_extinction_cannot_change(self):
        self.bundle['summary']['analysis']['models']['initial']['extinct_families'] += 1
        with self.assertRaisesRegex(ValueError, 'derived summary differs'):
            evidence.verify(self.bundle)

    def test_failed_attempt_is_not_complete(self):
        self.assertNotIn('failure.json', self.bundle['files'])
        raw = b'{"error":"retained failure"}'
        identity = evidence.experiment.sha(raw)
        self.bundle['files']['failure.json'] = identity
        self.bundle['blobs'][identity] = raw.hex()
        with self.assertRaisesRegex(ValueError, 'failed attempt is not complete'):
            evidence.verify(self.bundle)


if __name__ == '__main__':
    unittest.main()
