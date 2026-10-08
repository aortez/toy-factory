#!/usr/bin/env python3
"""Offline full-life eligibility, cursor ordering and compact evidence regressions."""

import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_nonbuyer as audit


class NonbuyerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(audit.ROOT / 'benchmarks/garden-seasons/landing-nonbuyer-results.json.gz', 'rt') as stream:
            cls.saved = json.load(stream)
        cls.original = audit.capture.origin_capture.audit.load_input()
        cls.result = audit.capture.selected(cls.original)['result']

    def changed_row(self, tick, change):
        excerpt = dict(self.saved['excerpt'])
        excerpt['rows'] = list(excerpt['rows'])
        index = (tick - audit.capture.FIRST) // audit.STEP
        excerpt['rows'][index] = copy.deepcopy(excerpt['rows'][index])
        change(excerpt['rows'][index])
        return excerpt

    def test_frozen_evidence_verifies_without_process_creation(self):
        with patch('subprocess.run', side_effect=AssertionError('offline only')), \
             patch('subprocess.Popen', side_effect=AssertionError('offline only')):
            audit.check_value(self.saved)

    def test_only_windowed_observer_arguments_added(self):
        before = list(audit.capture.selected(self.original)['args'])
        self.assertEqual(audit.capture.arguments(self.original), before + [
            '--stand-trace', 'stand.jsonl', '--stand-start', '1593525',
            '--stand-stop', '1966080', '--stand-dawn'])
        self.assertEqual(audit.capture.selected(self.original)['args'], before)

    def test_whole_life_not_a_sampled_subwindow(self):
        a = self.saved['analysis']
        self.assertEqual(a['samples'], 24838)
        self.assertEqual(a['first_tick'], a['focal']['birth_tick'])
        self.assertEqual(a['last_tick'], 512 * 3840)
        self.assertIsNone(a['focal']['death_tick'])
        self.assertEqual(a['focal_access']['living_visits'], a['samples'])

    def test_flower_matures_before_first_birthday(self):
        a = self.saved['analysis']
        self.assertEqual(a['first_ready_tick'], 1597065)
        self.assertLess(a['first_ready_tick'] - a['first_tick'], 3840)
        self.assertEqual(a['overlapping_blockers']['flower'], 236)
        self.assertEqual(a['body_changes'][-1]['body']['nodes'], 32)
        self.assertEqual(a['body_changes'][-1]['body']['flowers'], 1)
        self.assertEqual(a['focal_growth_bids'], 612)

    def test_eligibility_and_ordered_capacity_are_separate(self):
        a = self.saved['analysis']
        self.assertEqual(a['focal_access']['access'], dict(ineligible=22879,
                         full_at_entry=1946, earlier_buyers_fill=13, purchased=0))
        self.assertEqual(a['opening_masks'], {'898': 1, '900': 1, '4': 13, '128': 9, '132': 2})
        self.assertEqual(len(a['openings']), 26)
        self.assertEqual(a['bank']['purchases'], 25)
        self.assertEqual(a['bank']['post_step_counts'], {'7': 1, '8': 24837})

    def test_nine_open_at_turn_checks_are_energy_only(self):
        a = self.saved['analysis']
        opened = [r for r in a['openings'] if r['focal_visit']['bank'] < 8]
        self.assertEqual(len(opened), a['open_at_focal_turn'])
        self.assertEqual(opened[0]['tick'], a['first_tick'])  # Newborn is not yet fertile.
        self.assertEqual(len(opened[1:]), 9)
        for row in opened[1:]:
            v = row['focal_visit']
            self.assertEqual(v['blockers'], 128)
            self.assertLess(v['energy'], v['energy_required'])
            self.assertEqual(v['energy_required'], 208)
            self.assertEqual(row['last_buyer_before'], 38)
            self.assertEqual(row['order'][:2], [39, 41])

    def test_every_missed_opening_has_an_identified_earlier_buyer(self):
        rows = self.saved['analysis']['focal_access']['missed_openings']
        self.assertEqual(len(rows), 13)
        for row in rows:
            self.assertEqual(row['visit'][1], 4)
            self.assertEqual(row['bank_at_entry'], 7)
            self.assertEqual(len(row['earlier_buyers']), 1)
            self.assertNotEqual(row['earlier_buyers'][0], 41)

    def test_missing_birth_or_endpoint_sample_is_rejected(self):
        for start, stop in ((1, None), (0, -1)):
            with self.subTest(start=start):
                excerpt = dict(self.saved['excerpt'], rows=self.saved['excerpt']['rows'][start:stop])
                with self.assertRaisesRegex(RuntimeError, 'missing visit clock'):
                    audit.analyze(excerpt, self.result)

    def test_cursor_order_must_match_last_successful_buyer(self):
        def change(row):
            row['reproduction'][0], row['reproduction'][1] = row['reproduction'][1], row['reproduction'][0]
        excerpt = self.changed_row(1601040, change)  # Full bank, no purchases to obscure the order check.
        with self.assertRaisesRegex(RuntimeError, 'cursor or stored visit order'):
            audit.analyze(excerpt, self.result)

    def test_energy_blocker_cannot_be_ignored_at_an_opening(self):
        def change(row):
            next(v for v in row['reproduction'] if v[0] == 41)[1] = 0
        with self.assertRaisesRegex(RuntimeError, 'production gates differ'):
            audit.analyze(self.changed_row(1639200, change), self.result)

    def test_bank_is_checked_at_own_turn_not_step_entry(self):
        def change(row):
            next(v for v in row['reproduction'] if v[0] == 41)[11] = 7
        with self.assertRaisesRegex(RuntimeError, 'inventory/bank differs'):
            audit.analyze(self.changed_row(1600980, change), self.result)

    def test_missing_flower_contradicts_body_inventory(self):
        def change(row):
            row['body']['flowers'] = 0
        with self.assertRaisesRegex(RuntimeError, 'flower/body accounting'):
            audit.analyze(self.changed_row(1600980, change), self.result)

    def test_climate_is_checked_independently(self):
        def change(row):
            row['climate']['cold'] += 1
        with self.assertRaisesRegex(RuntimeError, 'climate or sun differs'):
            audit.analyze(self.changed_row(audit.capture.FIRST, change), self.result)

    def test_changed_excerpt_fails_provenance(self):
        excerpt = self.changed_row(audit.capture.FIRST, lambda row: row['bids'].clear())
        with self.assertRaisesRegex(RuntimeError, 'excerpt bytes or repeat differ'):
            audit.make_value(self.saved['capture'], excerpt, self.original)

    def test_changed_call_receipt_fails_provenance(self):
        receipt = copy.deepcopy(self.saved['capture'])
        receipt['runs']['repeat']['args'] += ['--unapproved-rule']
        with self.assertRaisesRegex(RuntimeError, 'capture receipt changed'):
            audit.check_capture(receipt, self.original)

    def test_changed_summary_is_not_accepted(self):
        saved = dict(self.saved, analysis=copy.deepcopy(self.saved['analysis']))
        saved['analysis']['focal_access']['access']['purchased'] = 1
        with self.assertRaisesRegex(RuntimeError, 'analysis differs'):
            audit.check_value(saved)

    def test_lossless_compaction_preserves_all_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'stand.jsonl'
            payload = b'example trace\n' * 100
            path.write_bytes(payload)
            receipt = audit.capture.pack_trace(path)
            self.assertFalse(path.exists())
            self.assertEqual(gzip.decompress(path.with_suffix('.jsonl.gz').read_bytes()), payload)
            self.assertEqual(receipt['bytes'], len(payload))
            path.write_bytes(payload)
            with self.assertRaises(FileExistsError):
                audit.capture.pack_trace(path)
            self.assertEqual(path.read_bytes(), payload)


if __name__ == '__main__':
    unittest.main()
