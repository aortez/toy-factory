"""Archive preparation fails closed and never repairs or overwrites old files."""

import copy
from pathlib import Path
import tempfile
import unittest

import prepare


class PreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = prepare.load_archive()
        cls.files = prepare.expected_files(cls.bundle)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='research-prepare-test-')
        self.addCleanup(self.temporary.cleanup)
        self.out = Path(self.temporary.name) / 'runtime'

    def test_roundtrip_and_idempotent_reuse(self):
        prepare.prepare(self.out, self.bundle)
        prepare.prepare(self.out, self.bundle)
        prepare.check(self.out, self.files)
        self.assertFalse(any('binaries' in name for name in self.files))
        self.assertEqual(sum(name.endswith('.raw') for name in self.files), 6)

    def test_archive_identity_checked_before_parsing(self):
        path = Path(self.temporary.name) / 'bad.gz'
        path.write_bytes(b'not an archive')
        with self.assertRaisesRegex(ValueError, 'archive identity'):
            prepare.load_archive(path)

    def test_unsafe_names(self):
        for name in ('/absolute', '../escape', 'a/../b', 'a//b', '.', '', 'a\\b'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'unsafe'):
                prepare.relative(name)

    def test_unsafe_archive_entry_rejected(self):
        bundle = self.bundle | dict(files=self.bundle['files'] | {'runtime/source/../escape': 'x'})
        with self.assertRaisesRegex(ValueError, 'unsafe'):
            prepare.expected_files(bundle)

    def test_blob_hash_checked(self):
        bundle = copy.deepcopy(self.bundle)
        identity = bundle['files']['models/initial.tlf']
        bundle['blobs'][identity] += '00'
        with self.assertRaisesRegex(ValueError, 'blob differs'):
            prepare.expected_files(bundle)

    def test_partial_tree_is_retained_and_refused(self):
        self.out.mkdir()
        (self.out / 'sentinel').write_bytes(b'keep')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            prepare.prepare(self.out, self.bundle)
        self.assertEqual((self.out / 'sentinel').read_bytes(), b'keep')

    def test_changed_model_is_not_silently_repaired(self):
        prepare.prepare(self.out, self.bundle)
        path = self.out / 'models/initial.tlf'
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'file differs'):
            prepare.prepare(self.out, self.bundle)
        self.assertEqual(path.read_bytes(), b'changed')

    def test_changed_source_and_manifest_rejected(self):
        prepare.prepare(self.out, self.bundle)
        altered = dict(self.files)
        name = 'source/src/garden_world.c'
        altered[name] += b'\n'
        (self.out / name).write_bytes(altered[name])
        import json
        (self.out / 'manifest.json').write_text(json.dumps(prepare.manifest(altered)))
        with self.assertRaisesRegex(ValueError, 'manifest differs'):
            prepare.check(self.out, self.files)

    def test_symlink_root_refused(self):
        target = Path(self.temporary.name) / 'elsewhere'
        target.mkdir()
        self.out.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'real directory'):
            prepare.prepare(self.out, self.bundle)
        self.assertEqual(list(target.iterdir()), [])

    def test_symlink_entry_refused(self):
        prepare.prepare(self.out, self.bundle)
        (self.out / 'alias').symlink_to(self.out / 'model.tgl')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            prepare.check(self.out, self.files)


if __name__ == '__main__':
    unittest.main()
