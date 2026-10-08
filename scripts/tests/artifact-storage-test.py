#!/usr/bin/env python3
"""No real artifact data is removed by these compaction and recovery tests."""

import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('storage', Path(__file__).parents[1] / 'artifact_storage.py')
storage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(storage)


class StorageTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'artifacts'
        self.bundle = self.root / 'garden-landing-old-v1'
        self.bundle.mkdir(parents=True)
        self.raw = self.bundle / 'trace.jsonl'
        self.packed = self.bundle / 'trace.jsonl.gz'
        self.data = b'{"tick": 15}\n' * 200
        self.raw.write_bytes(self.data)
        self.packed.write_bytes(gzip.compress(self.data, mtime=0))
        self.manifest = self.bundle / 'manifest.json'
        storage.durable_json(self.manifest, dict(artifacts={p.name: storage.digest(p) for p in (self.raw, self.packed)}))
        self.index = self.root / 'compaction.json'
        storage.durable_json(self.index, storage.plan(self.root, storage.KEEP))

    def test_apply_resume_and_byte_identical_restore(self):
        before = self.packed.read_bytes(), self.manifest.read_bytes()
        self.assertEqual(storage.apply(self.index)['removed'], 1)
        self.assertFalse(self.raw.exists())
        self.assertEqual(storage.apply(self.index)['already_absent'], 1)
        self.assertEqual(storage.restore(self.index, bundle=self.bundle.name)['restored'], 1)
        self.assertEqual(self.raw.read_bytes(), self.data)
        self.assertEqual(storage.restore(self.index, selected='garden-landing-old-v1/trace.jsonl')['restored'], 0)
        self.assertEqual((self.packed.read_bytes(), self.manifest.read_bytes()), before)

    def test_mismatch_never_deletes_raw(self):
        for path in (self.raw, self.packed, self.manifest):
            before = path.read_bytes()
            path.write_bytes(before + b'changed')
            with self.subTest(path=path), self.assertRaises((ValueError, OSError)):
                storage.apply(self.index)
            self.assertTrue(self.raw.exists())
            path.write_bytes(before)

    def test_matching_compressed_hash_is_not_enough(self):
        self.packed.write_bytes(gzip.compress(b'not the original', mtime=0))
        manifest = json.loads(self.manifest.read_text())
        manifest['artifacts'][self.packed.name] = storage.digest(self.packed)
        self.manifest.write_text(json.dumps(manifest))
        self.index.write_text(json.dumps(storage.plan(self.root, storage.KEEP)))
        with self.assertRaisesRegex(ValueError, 'decompressed bytes'):
            storage.apply(self.index)
        self.assertEqual(self.raw.read_bytes(), self.data)

    def test_changed_file_between_verification_and_unlink(self):
        original = storage.sync_directory
        def changed(path):
            if path == self.index.parent:
                self.raw.write_bytes(b'concurrent edit')
            original(path)
        with patch.object(storage, 'sync_directory', side_effect=changed), self.assertRaisesRegex(ValueError, 'changed'):
            storage.apply(self.index)
        self.assertEqual(self.raw.read_bytes(), b'concurrent edit')

    def test_restore_never_overwrites_different_file(self):
        storage.apply(self.index)
        self.raw.write_bytes(b'new data')
        with self.assertRaisesRegex(ValueError, 'raw file changed'):
            storage.restore(self.index, bundle=self.bundle.name)
        self.assertEqual(self.raw.read_bytes(), b'new data')

    def test_concurrently_created_raw_file_is_not_removed(self):
        self.raw.unlink()
        original = storage.digest
        def appeared(path):
            result = original(path)
            if path == self.packed:
                self.raw.write_bytes(self.data)
            return result
        with patch.object(storage, 'digest', side_effect=appeared), self.assertRaisesRegex(ValueError, 'appeared'):
            storage.apply(self.index)
        self.assertEqual(self.raw.read_bytes(), self.data)

    def test_symlinks_traversal_protection_and_uncovered_files(self):
        self.raw.unlink()
        self.raw.symlink_to(self.packed)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            storage.apply(self.index)
        self.raw.unlink()
        self.raw.write_bytes(self.data)
        for relative in ('../outside.jsonl', '/outside.jsonl'):
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                storage.safe_path(self.root, relative)
        self.assertEqual(storage.plan(self.root, [self.bundle.name])['files'], [])
        value = json.loads(self.index.read_text())
        value['keep'].append(self.bundle.name)
        self.index.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'protected'):
            storage.apply(self.index)
        self.manifest.unlink()
        self.assertEqual(storage.plan(self.root, [])['files'], [])


if __name__ == '__main__':
    unittest.main()
