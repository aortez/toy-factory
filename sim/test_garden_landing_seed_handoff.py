#!/usr/bin/env python3
"""Offline handoff accounting, phase boundaries and frozen replay identity checks."""

import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_seed_handoff as audit


class HandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = audit.ROOT / 'benchmarks/garden-seasons/landing-seed-handoff-results.json.gz'
        with gzip.open(path, 'rt') as stream:
            cls.saved = json.load(stream)
        cls.original = audit.capture.audit.load_input()
        cls.result = audit.capture.selected(cls.original)['result']

    def changed_trace(self, kind, change):
        traces = dict(self.saved['traces'])
        rows = audit.records(traces[kind], kind, self.result)
        change(rows)
        traces[kind] = ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows)
        return traces

    def test_capture_adds_only_windowed_observers(self):
        original_args = audit.capture.selected(self.original)['args']
        before = list(original_args)
        args = audit.capture.arguments(self.original)
        self.assertEqual(args[:len(before)], before)
        self.assertEqual(original_args, before)
        self.assertEqual(args[len(before):], [
            '--adult-trace', 'adult.jsonl', '--adult-start', '1838385', '--adult-stop', '1839360',
            '--stand-trace', 'stand.jsonl', '--stand-start', '1838385', '--stand-stop', '1839360',
            '--stand-dawn'])

    def test_complete_evidence_verifies_without_process_creation(self):
        with patch('subprocess.run', side_effect=AssertionError('offline only')), \
             patch('subprocess.Popen', side_effect=AssertionError('offline only')):
            audit.check_value(self.saved)
        self.assertEqual(self.saved['capture']['native_runs'], 2)
        self.assertEqual(self.saved['capture']['training_runs'], 0)

    def test_all_checks_have_simultaneous_capacity_blockers(self):
        result = audit.analyze(self.saved['traces'], self.result)
        self.assertEqual(result['ecology_samples'], 66)
        self.assertEqual(result['seed_samples'], 527)
        self.assertEqual(result['waiting_checks'], 63)
        self.assertEqual(result['waiting_masks'], {'92': 13, '28': 39, '24': 11})
        self.assertEqual(result['waiting_blockers'], dict(dormancy=0, moisture=0, light=52,
                         plant_capacity=63, node_capacity=63, spacing=0, cold=13))
        self.assertEqual(result['waiting_usable_checks'], 0)

    def test_dead_body_is_retained_until_same_step_refill(self):
        result = self.saved['analysis']
        self.assertEqual(result['reclamation'], dict(tick=1839345, lineages=[35], nodes=32))
        self.assertEqual(result['delay_ecology_steps'], 63)
        event = result['refill']
        self.assertEqual(event['tick'], result['reclamation']['tick'])
        self.assertEqual(len(event['stored_before']), 7)
        self.assertEqual(event['stored_after'], event['stored_before'] + [36])
        self.assertNotIn(35, event['stored_before'])
        self.assertEqual(event['older'][3:10], [0, 231, 158, 7, 222, 2, 36])
        self.assertEqual(event['focal'][3:10], [40, 219, 158, 8, 226, 0, 0])
        self.assertEqual(event['order'][0], list(audit.OLDER))
        self.assertEqual(event['order'][4], list(audit.FOCAL))
        self.assertEqual(result['older_steps_until_expiry'], 9)

    def test_post_germination_growth_is_not_charged_to_earlier_seed_checks(self):
        result = self.saved['analysis']
        self.assertEqual(result['refill']['focal'][7], 226)
        self.assertEqual(result['after_refill']['focal'][7], 227)
        self.assertIsNone(result['after_refill']['older'])
        self.assertEqual(result['focal_final_outcome'], 'expired')

    def test_missing_dead_slot_is_rejected(self):
        traces = self.changed_trace('stand', lambda rows: rows[3]['plant_order'].remove(35))
        with self.assertRaisesRegex(RuntimeError, 'stored slots/nodes differ'):
            audit.analyze(traces, self.result)

    def test_death_cannot_reclaim_slot_in_same_step(self):
        traces = self.changed_trace('stand', lambda rows: rows[2]['plant_order'].remove(35))
        with self.assertRaisesRegex(RuntimeError, 'premature plant reclamation'):
            audit.analyze(traces, self.result)

    def test_invented_reclamation_of_living_plant_is_rejected(self):
        traces = self.changed_trace('stand', lambda rows: rows[3]['plant_order'].remove(26))
        with self.assertRaisesRegex(RuntimeError, 'living plant missing'):
            audit.analyze(traces, self.result)

    def test_seed_node_count_must_match_body_inventory(self):
        def change(rows):
            rows[1]['seeds'][0][7] = 255  # Still sets NODE_CAPACITY; exact inventory is 254.
        with self.assertRaisesRegex(RuntimeError, 'stored slots/nodes differ'):
            audit.analyze(self.changed_trace('adult', change), self.result)

    def test_spacing_checks_include_the_earlier_seedling(self):
        def change(rows):
            refill = next(row for row in rows[1:-1] if row['tick'] == 1839345)
            focal = next(raw for raw in refill['seeds'] if raw[0] == 35)
            focal[3] &= ~32
        with self.assertRaisesRegex(RuntimeError, 'spacing differs'):
            audit.analyze(self.changed_trace('adult', change), self.result)

    def test_seed_visit_order_cannot_be_rearranged(self):
        def change(rows):
            seeds = rows[1]['seeds']
            seeds[2], seeds[3] = seeds[3], seeds[2]
        with self.assertRaisesRegex(RuntimeError, 'seed visit order'):
            audit.analyze(self.changed_trace('adult', change), self.result)

    def test_trace_clock_requires_both_boundary_samples(self):
        for index in (1, -2):
            with self.subTest(index=index):
                traces = self.changed_trace('stand', lambda rows: rows.pop(index))
                with self.assertRaisesRegex(RuntimeError, 'coverage'):
                    audit.analyze(traces, self.result)

    def test_living_morphology_matches_resource_observer(self):
        def change(rows):
            rows[1]['bodies'][0]['nodes'] -= 1
        with self.assertRaisesRegex(RuntimeError, 'living morphology differs'):
            audit.analyze(self.changed_trace('stand', change), self.result)

    def test_changed_call_receipt_is_rejected(self):
        saved = copy.deepcopy(self.saved)
        saved['capture']['runs']['repeat']['args'] += ['--reach-trace', 'unbounded.jsonl']
        with self.assertRaisesRegex(RuntimeError, 'capture receipt changed'):
            audit.check_value(saved)

    def test_changed_raw_trace_bytes_are_rejected(self):
        saved = copy.deepcopy(self.saved)
        saved['traces']['adult'] += '\n'
        with self.assertRaisesRegex(RuntimeError, 'trace bytes/repeat differ'):
            audit.check_value(saved)

    def test_changed_derived_result_is_rejected(self):
        saved = copy.deepcopy(self.saved)
        saved['analysis']['waiting_usable_checks'] = 1
        with self.assertRaisesRegex(RuntimeError, 'analysis differs'):
            audit.check_value(saved)

    def test_non_overwriting_deterministic_export(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = (Path(directory) / name for name in ('a.gz', 'b.gz'))
            audit.write_gzip(a, self.saved)
            audit.write_gzip(b, self.saved)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            with self.assertRaises(FileExistsError):
                audit.write_gzip(a, self.saved)


if __name__ == '__main__':
    unittest.main()
