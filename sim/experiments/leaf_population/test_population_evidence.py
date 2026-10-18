"""Published evidence stays reproducible without native binaries or simulator calls."""

from contextlib import contextmanager
import gzip
import json
from pathlib import Path
import subprocess
import struct
import tempfile
import unittest
import zlib
from unittest import mock

import collect_population as collect
import local_results
import population_evidence as evidence
import population_score as score
import prepare

ARCHIVE = collect.ROOT / 'benchmarks/garden-seasons/leaf-population-results.json.gz'
ARCHIVE_SHA = '3aae48b92ed9787f9dc1601052330cdbf96ed9d72f3d845e0b9932d50112af49'


@local_results.needs('leaf-population-results.json.gz')
class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='garden-population-evidence-test-')
        cls.root = Path(cls.temporary.name) / 'evidence'
        if prepare.sha(ARCHIVE.read_bytes()) != ARCHIVE_SHA:
            raise ValueError('published evidence identity differs')
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native execution forbidden')):
            evidence.unpack(ARCHIVE, cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    @contextmanager
    def changed_json(self, name, mutate):
        path, manifest_path = self.root / name, self.root / 'manifest.json'
        before, manifest_before = path.read_bytes(), manifest_path.read_bytes()
        try:
            value = json.loads(before)
            mutate(value)
            path.write_text(json.dumps(value))
            manifest = json.loads(manifest_before)
            manifest['files'][name] = prepare.sha(path.read_bytes())
            manifest_path.write_text(json.dumps(manifest))
            yield
        finally:
            path.write_bytes(before)
            manifest_path.write_bytes(manifest_before)

    def test_exact_recomputation_without_execution(self):
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native execution forbidden')):
            result = evidence.verify(self.root)
        self.assertEqual(result['calls'], 48)
        self.assertEqual(result['analysis']['initial']['periods']['960']['key'][0], [17, 720])
        self.assertEqual(result['analysis']['s1-g3-c4']['periods']['960']['key'][0], [187, 1440])
        self.assertEqual(result['analysis']['s2-g3-c1']['periods']['960']['key'][0], [19, 240])

    def test_changed_results_rejected_even_after_rehash(self):
        with self.changed_json('result.json', lambda r: r['analysis']['initial'].update(extinct_families=0)):
            with self.assertRaisesRegex(ValueError, 'recomputed results'):
                evidence.verify(self.root)

    def test_missing_condition_or_failed_preflight_rejected(self):
        with self.changed_json('started.json', lambda r: r['plan'].pop()):
            with self.assertRaisesRegex(ValueError, 'protocol'):
                evidence.verify(self.root)
        with self.changed_json('session-tests/process.json', lambda r: r.update(returncode=1)):
            with self.assertRaisesRegex(ValueError, 'preflight'):
                evidence.verify(self.root)

    def test_wrong_command_or_model_rejected(self):
        call = collect.roster()[0]['id']
        with self.changed_json(f'runs/{call}/process.json', lambda r: r['args'].__setitem__(1, 's2-g3-c1')):
            with self.assertRaisesRegex(ValueError, 'arguments'):
                evidence.verify(self.root)
        with self.changed_json('started.json', lambda r: r['models'].update(initial='bad')):
            with self.assertRaisesRegex(ValueError, 'protocol'):
                evidence.verify(self.root)

    def test_corrupt_capture_and_extra_call_rejected(self):
        call = collect.roster()[0]['id']
        name = f'runs/{call}/timeline/tick-0000000000.json'
        with self.changed_json(name, lambda r: r.update(framebuffer_crc32='bad')):
            with self.assertRaisesRegex(ValueError, 'CRC'):
                evidence.verify(self.root)
        extra = self.root / 'runs/unplanned'
        extra.mkdir()
        try:
            with self.assertRaisesRegex(ValueError, 'roster'):
                evidence.verify(self.root)
        finally:
            extra.rmdir()

    def test_archive_roundtrip_and_no_overwrite(self):
        target = Path(self.temporary.name) / 'roundtrip.json.gz'
        evidence.package(self.root, target)
        self.assertEqual(gzip.decompress(target.read_bytes()), gzip.decompress(ARCHIVE.read_bytes()))
        self.assertEqual(target.read_bytes()[9], 255)
        with self.assertRaises(FileExistsError):
            evidence.package(self.root, target)
        with self.assertRaises(ValueError):
            evidence.unpack(ARCHIVE, self.root)

    def test_published_sheets_keep_every_native_pixel(self):
        folder = collect.ROOT / 'benchmarks/garden-seasons/frames/leaf-population'
        self.assertEqual({p.name for p in folder.iterdir()},
                         {f'{seed}-{layout}-sheet.png' for seed in score.SEEDS for layout in score.LAYOUTS})
        for seed in score.SEEDS:
            for layout in score.LAYOUTS:
                expected_rows = []
                for day in score.DAYS:
                    frames = [evidence.rgb565((self.root / 'runs' / f'{m}-{seed}-{layout}-primary' /
                              'timeline' / f'tick-{day * score.DAY:010d}.raw').read_bytes()) for m in score.MODELS]
                    expected_rows += [b'\0' + b''.join(frame[row * 720:(row + 1) * 720] for frame in frames)
                                      for row in range(240)]
                raw = (folder / f'{seed}-{layout}-sheet.png').read_bytes()
                self.assertEqual(raw[:8], b'\x89PNG\r\n\x1a\n')
                offset, compressed = 8, bytearray()
                while offset < len(raw):
                    size, = struct.unpack_from('>I', raw, offset)
                    tag, payload = raw[offset + 4:offset + 8], raw[offset + 8:offset + 8 + size]
                    self.assertEqual(struct.unpack_from('>I', raw, offset + 8 + size)[0], zlib.crc32(tag + payload))
                    if tag == b'IHDR':
                        self.assertEqual(payload, struct.pack('>IIBBBBB', 720, 1440, 8, 2, 0, 0, 0))
                    if tag == b'IDAT':
                        compressed.extend(payload)
                    offset += size + 12
                self.assertEqual(zlib.decompress(compressed), b''.join(expected_rows))

    def test_unsafe_archive_path_refused_before_creation(self):
        target = Path(self.temporary.name) / 'unsafe'
        raw, digest = b'bad', prepare.sha(b'bad')
        bundle = dict(schema='garden-population-evidence-v1', files={'../escape': digest}, blobs={digest: raw.hex()})
        archive = Path(self.temporary.name) / 'unsafe.json.gz'
        archive.write_bytes(gzip.compress(json.dumps(bundle).encode()))
        with self.assertRaisesRegex(ValueError, 'unsafe archive path'):
            evidence.unpack(archive, target)
        self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
