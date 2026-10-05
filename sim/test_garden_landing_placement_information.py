#!/usr/bin/env python3
"""Decision information boundaries, aliases, seed checks and actual family outcomes."""

import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_placement_information as audit

RESULT = audit.ROOT / 'benchmarks/garden-seasons/landing-placement-information-results.json.gz'


def life(i, column, parent=0, birth=0, generation=0, purchases=0, death=None):
    return dict(id=i, parent=parent, column=column, birth_tick=birth, death_tick=death,
                generation=generation, species=0, seeds_created=purchases)


def purchase_fixture():
    lives = {i: life(i, c) for i, c in ((20, 3), (26, 12), (27, 8), (28, 20))}
    slots = list(lives)
    free = audit.clear_columns(slots, lives)
    p = dict(parent=20, origin=3, dispersal=0, column=0, choices=audit.late.support(3, 0, True),
             sites=bytes(0 if c in free else 32 for c in range(28)).hex())
    return dict(seed=[20, audit.PURCHASE], purchase=p, slots=slots), lives


def seed(parent=20, birth=15, end=135, child=22, column=0, outcome='germinated', generation=1):
    return dict(parent=parent, birth_tick=birth, end_tick=end, child_id=child, column=column,
                outcome=outcome, generation=generation, species=0, lifetime_ecology_ticks=8192)


def germination_fixture():
    s = seed()
    lives = {20: life(20, 3)}
    sites = bytes(32 if c in range(1, 6) else 0 for c in range(28)).hex()
    rows = []
    for age in range(1, 9):
        mask, outcome, child = (1, 0, 0) if age < 8 else (0, 2, 22)
        raw = [20, age, 0, mask, outcome, child, sites]
        adult = [20, age, 0, mask, 12, 80, 1, 4, outcome, child, 23]
        rows.append([15 + age * 15, raw, adult, [20], False])
    return s, rows, dict(choices=[0, 6, 7, 7, 8, 8]), lives


class ContractTests(unittest.TestCase):
    def test_signed_support_and_reflection_aliases_all_origins_and_traits(self):
        for wide in (False, True):
            for origin in range(28):
                for trait in range(-2, 3):
                    expected = []
                    for distance in range((3 if wide else 5) + trait, (10 if wide else 8) + trait):
                        for sign in (-1, 1):
                            col = origin + sign * distance
                            if col < 0 or col > 27: col = origin - sign * distance
                            expected.append(min(27, max(0, col)))
                    self.assertEqual(audit.late.support(origin, trait, wide), expected)
        self.assertEqual(audit.late.support(3, 0, True), [0, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12])
        self.assertEqual(audit.late.support(0, -2, True)[:4], [1, 1, 2, 2])

    def test_clear_original_kept_redirect_retains_aliases(self):
        columns = [0, 0, 10, 10, 11, 11]
        self.assertEqual(audit.choose(2, columns, 3), 2)
        self.assertEqual([audit.choose(r, columns, 3) for r in (0, 6, 12, 18)], [2, 3, 4, 5])
        for r in range(48):
            self.assertEqual(audit.choose(r, columns, 3), audit.choose(r + 24, columns, 3))

    def test_all_blocked_falls_back_and_invalid_inputs_fail(self):
        cols = list(range(6))
        self.assertEqual([audit.choose(r, cols, 63) for r in range(12)], cols * 2)
        for random, columns, blocked in ((-1, cols, 0), (True, cols, 0), (2**32, cols, 0),
                                         (0, cols[:5], 0), (0, cols, 64), (0, [0, 0, 1, 2, 3, 4], 1)):
            with self.assertRaises(RuntimeError): audit.choose(random, columns, blocked)

    def test_forced_landing_does_not_invent_random_draw_or_path(self):
        receipt, lives = purchase_fixture()
        out = audit.decision(receipt, lives, True)
        self.assertTrue(out['forced_column'])
        self.assertEqual(out['possible_selected_columns'], [0])
        self.assertEqual(out['compatible_selected_indices'], [0])
        self.assertIsNone(out['random_draw'])
        self.assertEqual(out['compatible_selector_paths'], ['kept_original', 'redirected_blocked'])
        self.assertEqual(out['blocked_choices'], 16382)

    def test_multiple_clear_columns_stay_ambiguous_and_impossible_landing_rejected(self):
        receipt, lives = purchase_fixture()
        receipt['slots'] = [20]
        free = audit.clear_columns([20], lives)
        receipt['purchase']['sites'] = bytes(0 if c in free else 32 for c in range(28)).hex()
        out = audit.decision(receipt, lives, True)
        self.assertFalse(out['forced_column'])
        self.assertEqual(out['possible_selected_columns'], [0, 6, 7, 8, 9, 10, 11, 12])
        receipt['purchase']['column'] = 5
        with self.assertRaisesRegex(RuntimeError, 'impossible'): audit.decision(receipt, lives, True)

    def test_spacing_is_strictly_less_than_three_and_keeps_dead_occupants(self):
        lives = {20: life(20, 3), 21: life(21, 8, death=15)}
        clear = audit.clear_columns([20, 21], lives)
        self.assertIn(0, clear)
        self.assertNotIn(1, clear)
        self.assertNotIn(10, clear)
        self.assertIn(11, clear)
        for slots in ([20, 20], [99]):
            with self.assertRaises(RuntimeError): audit.clear_columns(slots, lives)

    def test_same_site_light_is_not_a_callback_spacing_bit(self):
        receipt, lives = purchase_fixture()
        value = bytes.fromhex(receipt['purchase']['sites'])
        receipt['purchase']['sites'] = (bytes([value[0] | 4]) + value[1:]).hex()
        out = audit.decision(receipt, lives, True)
        self.assertEqual(out['clear_reachable'], [0])
        self.assertEqual(out['possible_selected_columns'], [0])
        self.assertNotIn(0, out['post_step_open'])

    def test_dormancy_first_mature_check_and_thresholds(self):
        s, rows, p, lives = germination_fixture()
        out = audit.summarize_detail(s, rows, p, lives)
        self.assertEqual((out['checks'], out['dormant_checks'], out['mature_checks']), (8, 7, 1))
        for index in (4, 5):
            bad = copy.deepcopy(rows)
            bad[-1][2][index] -= 1
            with self.assertRaisesRegex(RuntimeError, 'site gates'): audit.summarize_detail(s, bad, p, lives)

    def test_missing_reordered_seed_checks_and_newborn_inserted_too_early_fail(self):
        s, rows, p, lives = germination_fixture()
        for bad in (rows[:-1], [rows[1], rows[0], *rows[2:]]):
            with self.assertRaises(RuntimeError): audit.summarize_detail(s, bad, p, lives)
        bad = copy.deepcopy(rows)
        bad[-1][3].append(22)
        with self.assertRaises(RuntimeError):
            audit.summarize_detail(s, bad, p, lives | {22: life(22, 0, 20, 135, 1)})

    def test_expiry_is_not_counted_as_a_mature_site_check(self):
        s, rows, p, lives = germination_fixture()
        s.update(end_tick=60, outcome='expired', child_id=None, lifetime_ecology_ticks=3)
        rows = copy.deepcopy(rows[:3])
        rows[-1][1] = [20, 3, 0, 0, 1, 0, None]
        rows[-1][2] = [20, 3, 0, 0, 0, 0, 1, 4, 1, 0, -1]
        out = audit.summarize_detail(s, rows, p, lives)
        self.assertEqual((out['dormant_checks'], out['expiry_records'], out['mature_checks']), (2, 1, 0))

    def test_family_ancestry_exposure_and_pending_outcomes(self):
        result = dict(lineages=[life(29, 12, 22, 90, 2, 1), life(20, 3, purchases=1),
                               life(22, 0, 20, 30, 1, 1), life(21, 18)],
                      seeds=[seed(end=30), seed(22, 75, 90, 29, 12, generation=2),
                             seed(29, 120, None, None, 20, 'pending', 3)])
        with patch.object(audit, 'STOP', 150):
            out = audit.family_summary(result)
        self.assertEqual(out['descendants']['live_ticks'], 180)
        self.assertEqual(out['relative_generation_depth'], 2)
        self.assertEqual(out['seed_outcomes'], dict(germinated=2, pending=1))
        self.assertEqual(out['descendant_purchases'], 2)
        bad = copy.deepcopy(result)
        bad['seeds'][-1]['outcome'] = 'expired'
        with self.assertRaisesRegex(RuntimeError, 'censoring'): audit.family_summary(bad)
        for parent in (99, 29):
            bad = copy.deepcopy(result)
            bad['lineages'][2]['parent'] = parent
            with self.assertRaisesRegex(RuntimeError, 'ancestry'): audit.family(bad)

    def test_existing_file_and_symlink_refused_before_loading_evidence(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(audit, 'inputs',
                side_effect=AssertionError('must not load evidence')):
            link = Path(directory) / 'link'
            link.symlink_to(Path(directory) / 'missing')
            for target in (Path(directory), link):
                with self.assertRaisesRegex(RuntimeError, 'fresh'):
                    audit.export(Path('/missing'), target)

    def test_raw_manifest_rejected_before_trace_reading(self):
        with patch.object(audit, 'digest', return_value='0' * 64):
            with self.assertRaisesRegex(RuntimeError, 'raw manifest'): audit.check_raw(Path('/missing'), {})

    def test_provenance_pins_captured_implementation_not_future_working_tree(self):
        def digest(path):
            name = str(path.relative_to(audit.ROOT))
            if name in audit.IMPLEMENTATION: raise AssertionError('must not read mutable runtime code')
            return audit.PROTOCOL_SHA if name == audit.PROTOCOL else audit.INPUTS[name]
        with patch.object(audit, 'digest', side_effect=digest):
            self.assertEqual(audit.provenance()['implementation'], audit.IMPLEMENTATION)


@unittest.skipUnless(RESULT.exists(), 'placement information audit not yet retained')
class CapturedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(RESULT, 'rt') as stream: cls.value = json.load(stream)
        cls.worlds = audit.inputs()
        cls.analysis, cls.rows = cls.value['analysis'], cls.value['rows']

    def test_portable_verification_cannot_launch_processes(self):
        with patch('subprocess.Popen', side_effect=AssertionError('unexpected process')), \
             patch('subprocess.run', side_effect=AssertionError('unexpected process')):
            audit.check_value(self.value)

    def test_only_clear_reachable_landing_is_forced_but_global_space_exists(self):
        d = self.analysis['candidate']['decisions'][0]
        self.assertEqual(d['global_spacing_clear'], [0, 15, 16, 17, 23, 24, 25, 26, 27])
        self.assertEqual(d['clear_reachable'], [0])
        self.assertEqual(d['possible_selected_columns'], [0])
        self.assertEqual(d['selector_period'], 14)
        self.assertEqual(d['aliases']['7'], [2, 3])
        self.assertIsNone(d['random_draw'])

    def test_control_did_not_buy_at_the_same_tick(self):
        self.assertEqual(self.analysis['control']['decisions'], [])
        seeds = self.analysis['control']['window_purchases']
        self.assertEqual([(s['birth_tick'], s['column']) for s in seeds], [(652320, 9)])
        self.assertEqual(self.analysis['candidate']['purchase_context']['stand']['plant_order'], [20, 26, 27, 28])

    def test_selected_child_passed_every_non_dormancy_gate(self):
        detail = next(d for d in self.analysis['candidate']['detailed_seeds'] if d['seed']['child_id'] == 29)
        self.assertEqual(detail['masks'], {'0': 1, '1': 7})
        self.assertEqual(detail['checks'], 8)
        rows = next(d['rows'] for d in self.rows['candidate']['details'] if d['seed'] == [20, 652260])
        self.assertEqual(rows[-1][2], [20, 8, 0, 0, 13, 154, 4, 106, 2, 29, 8])
        self.assertNotIn(29, rows[-1][3])
        self.assertIn(29, self.rows['candidate']['context'][-1]['stand']['plant_order'])

    def test_surviving_child_is_real_benefit_not_proven_multigeneration_renewal(self):
        a, b = (self.analysis[s]['family'] for s in audit.SIDES)
        self.assertEqual((a['descendants']['living'], b['descendants']['living']), (0, 1))
        self.assertEqual(b['descendants']['live_ticks'] - a['descendants']['live_ticks'], 330660)
        self.assertEqual((a['parent_purchases'], b['parent_purchases'], b['descendant_purchases']), (21, 15, 9))
        child = next(p for p in b['per_parent'] if p['id'] == 29)
        self.assertEqual(child['seed_outcomes'], dict(expired=5, pending=4))
        self.assertEqual(child['children'], [])
        self.assertEqual((a['relative_generation_depth'], b['relative_generation_depth']), (1, 1))

    def test_child_seeds_always_spacing_blocked_and_almost_always_slot_blocked(self):
        seeds = [s for s in self.analysis['candidate']['detailed_seeds'] if s['seed']['parent'] == 29]
        self.assertEqual(len(seeds), 9)
        self.assertEqual(sum(s['mature_checks'] for s in seeds), 54324)
        self.assertEqual(sum(s['mature_blockers']['spacing'] for s in seeds), 54324)
        self.assertEqual(sum(s['mature_blockers']['plant_capacity'] for s in seeds), 54323)
        self.assertEqual(sum(s['mature_blockers']['node_capacity'] for s in seeds), 0)
        self.assertEqual(sum(s['checks_with']['reachable_open'] for s in seeds), 0)
        self.assertEqual(sum(s['checks_with']['global_open'] for s in seeds), 1)

    def test_full_inventory_coverage_and_detailed_histogram_reconciliation(self):
        self.assertEqual(sum(r['full_reach_checks'] for r in self.rows.values()), 1039250)
        self.assertEqual(sum(r['full_reach_seeds'] for r in self.rows.values()), 174)
        self.assertEqual(sum(len(d['rows']) for d in self.rows['candidate']['details']), 54400)
        self.assertTrue(all(len(r['context']) == 10 for r in self.rows.values()))
        self.assertEqual(self.rows['control']['details'], [])

    def test_tampered_receipts_missing_context_and_changed_family_fail(self):
        for change in ('context', 'family', 'detail', 'mask', 'census'):
            rows = copy.deepcopy(self.rows)
            b = rows['candidate']
            if change == 'context': b['context'].pop()
            elif change == 'family': b['family_reach'].pop()
            elif change == 'detail': b['details'].pop()
            elif change == 'mask': b['details'][0]['rows'][0][2][4] = 0
            else: b['context'][1]['stand']['plant_order'].append(99)
            with self.subTest(change=change), self.assertRaises(RuntimeError): audit.analyze(rows, self.worlds)

    def test_changed_provenance_sources_checksums_and_summary_fail(self):
        for key, value in (('native_runs', True), ('training_runs', 1), ('raw_manifest_sha256', '0' * 64)):
            with self.assertRaises(RuntimeError):
                audit.check_value(self.value | {'provenance': self.value['provenance'] | {key: value}})
        for key in ('sources', 'source_sha256', 'receipt_sha256', 'analysis'):
            with self.subTest(key=key), self.assertRaises(RuntimeError): audit.check_value(self.value | {key: {}})


if __name__ == '__main__': unittest.main()
