"""Whole-population identity, ancestry, repeatability and capture contracts."""

import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

BINARY = str(Path(sys.argv.pop(1)).resolve())
POLICIES = ('initial', 's1-g3-c4', 's2-g3-c1')


class PopulationTests(unittest.TestCase):
    def run_replay(self, policy='initial', layout='rainfed', ticks=0, selection='all',
                   extra=(), success=True):
        result = subprocess.run([BINARY, policy, '58d7d6ca', layout, str(ticks), selection,
                                 *map(str, extra)], capture_output=True, timeout=30)
        self.assertEqual(result.returncode == 0, success, result.stderr)
        if success:
            self.assertEqual(result.stderr, b'')
            return json.loads(result.stdout)
        self.assertEqual(result.stdout, b'')

    def check_record(self, record):
        self.assertEqual(record['schema'], 'garden-leaf-population-replay-v1')
        self.assertEqual(record['controller_assignment'], 'whole-population')
        self.assertIsNone(record['candidate_founder'])
        self.assertIsNone(record['resident_policy'])
        self.assertIsNone(record['objective'])
        self.assertFalse(record['gardener'])
        self.assertTrue(record['complete'])
        state = bytes.fromhex(record['state_hex'])
        self.assertEqual(state[:6], b'TPR1\x00\x00')
        self.assertEqual(state[7], 0)
        count, = struct.unpack_from('<I', state, 8)
        self.assertEqual(count, len(record['lineages']))
        roots = record['family_roots']
        self.assertEqual(list(state[12:12 + count]), roots)
        self.assertEqual(state[12 + count:16 + count], b'TLR1')
        founders = 3 if record['scenario'] == 'rainfed' else 5
        self.assertEqual(state[6], founders)
        self.assertEqual(roots[:founders], list(range(1, founders + 1)))
        for index, row in enumerate(record['lineages']):
            self.assertEqual(row['id'], index + 1)
            if row['parent']:
                self.assertLess(row['parent'], row['id'])
                self.assertEqual(roots[index], roots[row['parent'] - 1])
            else:
                self.assertLessEqual(row['id'], founders)
        self.assertEqual(len(record['death_causes']), count)

    def test_all_policies_and_layouts_with_descendants(self):
        for policy in POLICIES:
            for layout in ('rainfed', 'rainfed-crowded'):
                with self.subTest(policy=policy, layout=layout):
                    record = self.run_replay(policy, layout, 64 * 3840)
                    self.check_record(record)
                    self.assertTrue(any(row['parent'] for row in record['lineages']))

    def test_repeat_and_render_cadence(self):
        with tempfile.TemporaryDirectory(prefix='garden-population-test-') as folder:
            for policy in POLICIES:
                plain = self.run_replay(policy, ticks=3840)
                for cadence in (0, 15):
                    path = Path(folder) / f'{policy}-{cadence}.raw'
                    captured = self.run_replay(policy, ticks=3840, extra=(path, cadence))
                    self.check_record(captured)
                    raw = path.read_bytes()
                    self.assertEqual(len(raw), 115200)
                    self.assertEqual(captured.pop('framebuffer_crc32'), f'{zlib.crc32(raw):08x}')
                    self.assertEqual(captured, {k: v for k, v in plain.items()
                                               if k != 'framebuffer_crc32'})

    def test_scope_has_distinct_identity_and_numeric_family_stays_valid(self):
        population = self.run_replay()
        family = self.run_replay(selection='1')
        self.assertEqual(family['schema'], 'garden-leaf-family-replay-v1')
        self.assertEqual(family['controller_assignment'], 'founder-family')
        self.assertEqual(family['candidate_founder'], 1)
        self.assertEqual(family['resident_policy'], 'selective')
        self.assertTrue(bytes.fromhex(family['state_hex']).startswith(b'TFR1'))
        self.assertNotEqual(population['state_hex'], family['state_hex'])
        self.assertEqual(population['family_roots'], family['family_roots'])

    def test_invalid_selection_and_capture_failure(self):
        for selection in ('0', '4', 'ALL', 'allx', '-1', ''):
            with self.subTest(selection=selection):
                self.run_replay(selection=selection, success=False)
        with tempfile.TemporaryDirectory(prefix='garden-population-test-') as folder:
            path = Path(folder) / 'existing.raw'
            path.write_bytes(b'keep me')
            self.run_replay(extra=(path,), success=False)
            self.assertEqual(path.read_bytes(), b'keep me')
        self.run_replay(ticks=1376 * 3840 + 1, success=False)
        self.run_replay(extra=('--timeline',), success=False)

    def test_timeline_matches_independent_checkpoints(self):
        with tempfile.TemporaryDirectory(prefix='garden-population-test-') as folder:
            timeline = Path(folder) / 'timeline'
            final = self.run_replay('s1-g3-c4', ticks=33 * 3840,
                                    extra=('--timeline', timeline))
            self.assertEqual(sorted(p.name for p in timeline.iterdir()), sorted(
                f'tick-{day * 3840:010d}.{suffix}'
                for day in (0, 32, 33) for suffix in ('json', 'raw')))
            for day in (0, 32, 33):
                prefix = timeline / f'tick-{day * 3840:010d}'
                record = json.loads(prefix.with_suffix('.json').read_bytes())
                self.check_record(record)
                reference = Path(folder) / f'{day}.raw'
                expected = self.run_replay('s1-g3-c4', ticks=day * 3840, extra=(reference,))
                self.assertEqual(record, expected)
                self.assertEqual(prefix.with_suffix('.raw').read_bytes(), reference.read_bytes())
            self.assertEqual(final, record)
            before = {p.name: p.read_bytes() for p in timeline.iterdir()}
            self.run_replay(extra=('--timeline', timeline), success=False)
            self.assertEqual(before, {p.name: p.read_bytes() for p in timeline.iterdir()})
            alias = Path(folder) / 'alias'
            alias.symlink_to(timeline, target_is_directory=True)
            self.run_replay(extra=('--timeline', alias), success=False)
            self.run_replay(selection='1', extra=('--timeline', Path(folder) / 'family'), success=False)
            self.assertFalse((Path(folder) / 'family').exists())

    def test_trace_parity_and_resource_conservation(self):
        with tempfile.TemporaryDirectory(prefix='garden-trace-test-') as folder:
            for policy in POLICIES:
                plain, traced = (Path(folder) / f'{policy}-{mode}' for mode in ('plain', 'trace'))
                expected = self.run_replay(policy, ticks=2 * 3840 + 14, extra=('--timeline', plain))
                actual = self.run_replay(policy, ticks=2 * 3840 + 14, extra=('--trace', 2, traced))
                self.assertEqual(actual, expected)
                for path in plain.iterdir():
                    self.assertEqual(path.read_bytes(), (traced / path.name).read_bytes())
                trace = json.loads((traced / 'trace.json').read_bytes())
                self.assertTrue(trace['complete'])
                self.assertEqual(trace['founder'], 2)
                self.assertEqual(trace['ecology_steps'], 512)
                self.assertEqual(len(trace['seed_days']), 3)
                for row in trace['plant_days']:
                    self.assertEqual(row['lineage'], 2)
                    self.assertEqual(row['samples'], 256)
                    for key in ('energy', 'water'):
                        f = row[key]
                        self.assertEqual(f['before'] + f['income'] + f['endowment'],
                            sum(f[k] for k in ('after', 'overflow', 'upkeep_paid', 'growth',
                                               'seeds', 'discarded', 'repair')))
                    self.assertEqual(row['condition_before'] + row['condition_endowment'] + row['restored'],
                                     row['condition_after'] + row['worn'])
                for row in trace['seeds']:
                    self.assertEqual(row['parent'], 2)
                    self.assertEqual(row['first_tick'], row['birth_tick'] + 15)
                    checks = row['attempts']
                    self.assertEqual(checks['checks'], sum(checks['masks'].values()))

    def test_shadow_parity_and_complete_window(self):
        with tempfile.TemporaryDirectory(prefix='garden-shadow-test-') as folder:
            plain, shadow = (Path(folder) / mode for mode in ('plain', 'shadow'))
            expected = self.run_replay(ticks=224 * 3840, extra=('--trace', 2, plain))
            actual = self.run_replay(ticks=224 * 3840, extra=('--shadow', 2, shadow))
            self.assertEqual(actual, expected)
            for path in plain.iterdir():
                self.assertEqual(path.read_bytes(), (shadow / path.name).read_bytes())
            data = json.loads((shadow / 'shadow.json').read_bytes())
            self.assertEqual(data['schema'], 'garden-population-shadow-v1')
            self.assertTrue(data['complete'])
            self.assertEqual((data['first_tick'], data['end_tick']), (208 * 3840, 224 * 3840))
            self.assertEqual(data['models'], list(POLICIES))
            self.assertGreater(len(data['rows']), 1000)
            self.assertTrue(all(208 * 3840 < r['tick'] <= 224 * 3840 and
                                actual['family_roots'][r['lineage'] - 1] == 2 for r in data['rows']))
            before = (shadow / 'shadow.json').read_bytes()
            self.run_replay(ticks=224 * 3840, extra=('--shadow', 2, shadow), success=False)
            self.assertEqual(before, (shadow / 'shadow.json').read_bytes())
            missing = Path(folder) / 'missing'
            for ticks in (224 * 3840 - 1, 256 * 3840 + 1):
                self.run_replay(ticks=ticks, extra=('--shadow', 2, missing), success=False)
            self.run_replay(ticks=224 * 3840, selection='1', extra=('--shadow', 2, missing), success=False)
            self.assertFalse(missing.exists())

    def test_gate_rejects_bad_arguments_and_existing_output(self):
        with tempfile.TemporaryDirectory(prefix='gate-cli-test-') as temporary:
            root = Path(temporary)
            kept = root / 'keep.txt'
            kept.write_text('unchanged')
            alias = root / 'alias'
            alias.symlink_to(root, target_is_directory=True)
            for args in (('--gate',), ('--gate', 'none'), ('--gate', 'none', 'on'),
                         ('--gate', 'bogus', 'on', root / 'new'),
                         ('--gate', 'none', 'bogus', root / 'new'),
                         ('--gate', 'none', 'on', root), ('--gate', 'both', 'off', alias)):
                for flag in ('--gate', '--gate-long', '--gate-transfer'):
                    result = subprocess.run([BINARY, flag, *map(str, args[1:])],
                                            capture_output=True, timeout=10)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, b'')
            self.assertEqual(kept.read_text(), 'unchanged')
            self.assertFalse((root / 'new').exists())

    def test_gate_panel_rejects_bad_arguments_and_preserves_output(self):
        with tempfile.TemporaryDirectory(prefix='gate-panel-cli-') as temporary:
            root = Path(temporary)
            kept = root / 'keep.txt'
            kept.write_text('unchanged')
            alias = root / 'alias'
            alias.symlink_to(root, target_is_directory=True)
            valid = ('58d7d6ca', 'both', 'on', root / 'new')
            invalid = [valid[:n] for n in range(4)]
            invalid += [(s, 'both', 'on', root / 'new')
                        for s in ('58D7D6CA', '58d7d6c', '58d7d6caz', '98a89374')]
            invalid += [('58d7d6ca', v, m, p) for v, m, p in
                        (('bogus', 'on', root / 'new'), ('both', 'bogus', root / 'new'),
                         ('none', 'on', root), ('both', 'off', alias))]
            for args in invalid:
                result = subprocess.run([BINARY, '--gate-panel', *map(str, args)],
                                        capture_output=True, timeout=10)
                self.assertNotEqual(result.returncode, 0, args)
                self.assertEqual(result.stdout, b'')
            self.assertEqual(kept.read_text(), 'unchanged')
            self.assertFalse((root / 'new').exists())

    def test_fallback_rejects_invalid_scope_and_output(self):
        with tempfile.TemporaryDirectory(prefix='fallback-cli-') as temporary:
            root = Path(temporary)
            valid = ('9a903368', 'condition', 'fewest', 'on', root / 'new')
            invalid = [valid[:n] for n in range(5)] + [valid + ('extra',)]
            for index, value in ((0, '58d7d6ca'), (0, '9A903368'), (1, 'bad'), (2, 'bad'), (3, 'bad')):
                row = list(valid)
                row[index] = value
                invalid.append(tuple(row))
            kept = root / 'keep.txt'
            kept.write_text('unchanged')
            alias = root / 'alias'
            alias.symlink_to(root, target_is_directory=True)
            invalid += [valid[:-1] + (path,) for path in (root, alias)]
            for args in invalid:
                for flag in ('--fallback-panel', '--reproduction-panel', '--budget-panel', '--foliage-panel', '--canopy-panel'):
                    result = subprocess.run([BINARY, flag, *map(str, args)],
                                            capture_output=True, timeout=10)
                    self.assertNotEqual(result.returncode, 0, args)
                    self.assertEqual(result.stdout, b'')
            for variant in ('none', 'light', 'both'):
                result = subprocess.run([BINARY, '--foliage-panel', '9a903368', variant,
                                         'original', 'on', str(root / 'new')], capture_output=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b'')
                result = subprocess.run([BINARY, '--reproduction-panel', '9a903368', variant,
                                         'original', 'on', str(root / 'new')], capture_output=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b'')
                result = subprocess.run([BINARY, '--budget-panel', '9a903368', variant,
                                         'fewest', 'on', str(root / 'new')], capture_output=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b'')
            result = subprocess.run([BINARY, '--budget-panel', '9a903368', 'condition',
                                     'original', 'on', str(root / 'new')], capture_output=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, b'')
            self.assertFalse((root / 'new').exists())
            self.assertEqual(kept.read_text(), 'unchanged')

    def test_trace_rejects_invalid_scope_and_output(self):
        for extra in (('--trace',), ('--trace', 2), ('--trace', 0, 'unused'),
                      ('--trace', 4, 'unused'), ('--trace', '2x', 'unused'),
                      ('--bogus', 2, 'unused'), ('--shadow',), ('--shadow', 2),
                      ('--shadow', 0, 'unused'), ('--shadow', 4, 'unused')):
            self.run_replay(extra=extra, success=False)
        with tempfile.TemporaryDirectory(prefix='garden-trace-test-') as folder:
            existing = Path(folder) / 'existing'
            existing.mkdir()
            kept = existing / 'trace.json'
            kept.write_text('keep me')
            self.run_replay(extra=('--trace', 2, existing), success=False)
            self.assertEqual(kept.read_text(), 'keep me')
            alias = Path(folder) / 'alias'
            alias.symlink_to(existing, target_is_directory=True)
            self.run_replay(extra=('--trace', 2, alias), success=False)
            new = Path(folder) / 'new'
            self.run_replay(extra=('--trace', 2, new), ticks=256 * 3840 + 1, success=False)
            self.run_replay(extra=('--trace', 2, new), selection='1', success=False)
            self.assertFalse(new.exists())


if __name__ == '__main__':
    unittest.main()
