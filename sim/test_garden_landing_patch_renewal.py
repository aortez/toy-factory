#!/usr/bin/env python3
"""Saved winter budgets, complete seed queues, and offline-only audit contracts."""

import copy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_patch_renewal as audit

RESULT = audit.ROOT / 'benchmarks/garden-seasons/landing-patch-renewal-results.json.gz'


class ContractTests(unittest.TestCase):
    def test_existing_and_dangling_outputs_refused_before_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            existing, dangling = Path(tmp), Path(tmp) / 'dangling'
            dangling.symlink_to(Path(tmp) / 'missing')
            for path in (existing, dangling):
                with patch('sys.argv', ['audit', '--bundle', '/missing', '--out', str(path)]), \
                     patch.object(audit, 'extract', side_effect=AssertionError('no extraction')):
                    with self.assertRaisesRegex(RuntimeError, 'fresh output'):
                        audit.main()

    def test_even_unselected_trace_bytes_are_authenticated(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(audit, 'STOP', 30):
            path = Path(tmp) / 'reach.jsonl.gz'
            rows = [dict(schema='landing-reach-trace-v1'), dict(tick=15), dict(tick=30),
                    dict(complete=True, tick=30)]
            raw = b''.join(json.dumps(r).encode() + b'\n' for r in rows)
            path.write_bytes(gzip.compress(raw, mtime=0))
            meta = dict(sha256=audit.digest(path), raw_sha256=hashlib.sha256(raw).hexdigest(), raw_bytes=len(raw))
            self.assertEqual(list(audit.selected_rows(path, 'reach', {}, meta, lambda t: t == 30)), [rows[2]])
            changed = raw.replace(b'15', b'16')
            path.write_bytes(gzip.compress(changed, mtime=0))
            meta['sha256'] = audit.digest(path)
            with self.assertRaisesRegex(RuntimeError, 'identity differs'):
                list(audit.selected_rows(path, 'reach', {}, meta, lambda t: t == 30))

    def test_expiry_is_not_a_viable_site_observation(self):
        self.assertIsNone(audit.competition.opportunity([0] * 11, None, [3], [3]))


class CapturedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch('subprocess.run', side_effect=AssertionError('no processes')), \
             patch('subprocess.Popen', side_effect=AssertionError('no processes')):
            cls.capture = audit.inputs()
            with gzip.open(RESULT, 'rt') as stream:
                cls.value = json.load(stream)

    def focal_arm(self):
        key, phase = audit.FOCAL
        return copy.deepcopy(self.value['evidence'][key][phase]), key, phase

    def test_portable_reanalysis_and_reproducible_gzip_without_processes(self):
        with patch('subprocess.run', side_effect=AssertionError('no processes')), \
             patch('subprocess.Popen', side_effect=AssertionError('no processes')):
            audit.check_value(self.value)
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'copy.json.gz'
                audit.write_gzip(path, audit.rebuild(self.value))
                self.assertEqual(path.read_bytes(), RESULT.read_bytes())

    def test_only_exact_original_receipt_can_use_historical_sources(self):
        value = dict(self.value, sources=dict(self.value['sources']))
        value['sources']['sim/garden_landing_patch_renewal.py'] = '0' * 64
        value['receipt_sha256'] = audit.fingerprint({k: v for k, v in value.items() if k != 'receipt_sha256'})
        with self.assertRaisesRegex(RuntimeError, 'historical audit identity'):
            audit.check_value(value)

    def test_all_twelve_histories_and_exactly_one_birth(self):
        arms = [a for pair in self.value['analysis'].values() for a in pair.values()]
        self.assertEqual(len(arms), 12)
        self.assertTrue(all(a['counts']['steps'] == 8192 for a in arms))
        self.assertEqual(sum(len(a['births']) for a in arms), 1)
        self.assertEqual(sum(a['counts']['expiry'] for a in arms), 96)
        self.assertEqual(sum(a['access']['bank']['purchases'] for a in arms), 97)

    def test_complete_focal_lives_and_energy_not_water_failure(self):
        focal = self.value['analysis'][audit.FOCAL[0]][audit.FOCAL[1]]['focal']
        for identity in ('46', '48'):
            p = focal[identity]
            self.assertTrue(p['shortfalls'])
            self.assertTrue(all(s['energy']['unpaid'] > 0 and s['water']['unpaid'] == 0 for s in p['shortfalls']))
            self.assertEqual(p['resources']['water']['discarded'], 510)
            self.assertEqual(p['resources']['energy']['reproduction'], 0)
            self.assertEqual(p['shortfalls'][-1]['stress'], 8)
            self.assertEqual(p['terminal'][0], p['life']['death_tick'])
        self.assertFalse(focal['47']['shortfalls'])
        self.assertEqual(len(focal['47']['purchases']), 3)

    def test_focal_gaps_and_tampered_death_receipts_fail(self):
        ev, key, phase = self.focal_arm()
        rows = ev['focal']['48']
        life = self.capture['runs'][phase][key]['result']['lineages'][47]
        result = self.capture['runs'][phase][key]['result']
        with self.assertRaisesRegex(RuntimeError, 'focal clock'):
            audit.focal_history(rows[:-1], life, result)
        rows[-1][1][1][1][-1] -= 1  # Terminal water discard must balance.
        with self.assertRaises(RuntimeError):
            audit.focal_history(rows, life, result)

    def test_tail_gaps_and_duplicates_fail(self):
        for duplicate in (False, True):
            ev, key, phase = self.focal_arm()
            if duplicate:
                ev['rows'].insert(10, ev['rows'][10])
            else:
                ev['rows'].pop(10)
            with self.assertRaisesRegex(RuntimeError, 'tail clock'):
                audit.analyze_arm(ev, key, phase)

    def test_seed_inventory_and_off_column_maps_are_checked(self):
        for kind in ('missing', 'off_column', 'bank', 'visit'):
            ev, key, phase = self.focal_arm()
            row = ev['rows'][1]
            if kind == 'missing':
                row['checks'].pop()
            elif kind == 'off_column':
                raw, encoded = row['checks'][0]
                sites = bytearray.fromhex(encoded)
                sites[(raw[2] + 1) % 28] ^= 32
                row['checks'][0][1] = sites.hex()
            elif kind == 'bank':
                row['bank'] -= 1
            else:
                row['visits'].reverse()
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                audit.analyze_arm(ev, key, phase)

    def test_birth_updates_sequential_census(self):
        ev, key, phase = self.focal_arm()
        row = next(r for r in ev['rows'] if any(raw[8] == 2 for raw, _ in r['checks']))
        raw, _ = next(c for c in row['checks'] if c[0][8] == 2)
        self.assertEqual((raw[1], raw[6], raw[7], raw[9]), (8, 5, 160, 48))
        row['slots'].remove(48)
        with self.assertRaises(RuntimeError):
            audit.analyze_arm(ev, key, phase)

    def test_global_room_does_not_imply_a_reachable_landing(self):
        data = self.value['analysis']
        s3 = data['275c8982-rainfed-crowded']['treatment']
        self.assertEqual(s3['spacing_clear_steps'], {'23,24,25,26,27': 8192})
        self.assertEqual(s3['counts']['open_steps'], 2375)
        self.assertEqual(s3['counts']['reachable_elsewhere'], 0)
        s3o = data['275c8982-rainfed']['treatment']
        self.assertEqual(s3o['occupancy'], {'7/7': 8192})
        self.assertEqual(s3o['spacing_clear_steps'], {'none': 8192})

    def test_purchase_witnesses_cannot_be_omitted(self):
        ev, key, phase = self.focal_arm()
        ev['witnesses'].pop()
        with self.assertRaisesRegex(RuntimeError, 'purchase coverage'):
            audit.analyze_arm(ev, key, phase)


if __name__ == '__main__':
    unittest.main()
