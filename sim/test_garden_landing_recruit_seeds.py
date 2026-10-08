#!/usr/bin/env python3
"""Seed-age boundaries, within-step ordering and complete offline cohort evidence."""

import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_recruit_seeds as audit


def plant(identity, column, birth=0, death=None):
    return dict(id=identity, column=column, birth_tick=birth, death_tick=death)


def seed(birth=15, end=255, outcome='expired', column=24, parent=1, child=None):
    return dict(parent=parent, birth_tick=birth, end_tick=end, child_id=child,
                column=column, outcome=outcome, lifetime_ecology_ticks=16)


def population(count=8):
    return [plant(i + 1, i * 3) for i in range(count)]


class TimingTests(unittest.TestCase):
    def test_dormancy_inclusive_and_expiry_exclusive(self):
        s = seed()
        self.assertEqual(audit.mature_window(s, 300), (135, 240))
        result = audit.seed_history(0, [s], population(), 300)
        self.assertEqual(result['counts']['mature_checks'], 8)
        self.assertEqual(result['counts']['capacity_excluded'], 8)
        self.assertEqual(result['counts']['unresolved'], 0)

    def test_expiry_tick_vacancy_is_too_late(self):
        plants = population()
        plants[-1]['death_tick'] = 255
        result = audit.seed_history(0, [seed()], plants, 300)
        self.assertEqual(result['counts']['headcount_room'], 0)
        self.assertEqual(result['observed_last_check_tick'], 240)

    def test_germination_check_is_included(self):
        s = seed(end=135, outcome='germinated', child=8)
        result = audit.seed_history(0, [s], population(7) + [plant(8, 24, 135)], 300)
        self.assertEqual(result['counts']['mature_checks'], 1)
        self.assertEqual(result['counts']['headcount_room'], 1)
        self.assertEqual(result['other_germinations'], [])

    def test_pending_endpoint_is_included_not_an_expiry(self):
        s = seed(end=None, outcome='pending')
        result = audit.seed_history(0, [s], population(), 150)
        self.assertEqual(result['counts']['mature_checks'], 2)
        self.assertTrue(result['censored'])
        self.assertEqual(result['expiry_tick'], 255)

    def test_pending_seed_can_still_be_dormant(self):
        result = audit.seed_history(0, [seed(end=None, outcome='pending')], population(), 120)
        self.assertEqual(result['intervals'], [])
        self.assertEqual(result['counts']['mature_checks'], 0)
        self.assertTrue(result['censored'])

    def test_maintenance_death_precedes_check_but_does_not_prove_stored_slot(self):
        plants = population()
        plants[-1]['death_tick'] = 135
        result = audit.seed_history(0, [seed()], plants, 300)
        self.assertEqual(result['counts']['headcount_room'], 8)
        self.assertEqual(result['counts']['unresolved'], 8)
        self.assertEqual(result['intervals'][0]['state']['before_checks_living'], 7)
        # The ledger proves only a living lower bound, not dead-tissue reclamation.
        self.assertNotIn('eligible', result)
        self.assertNotIn('stored_plants', result['intervals'][0]['state'])

    def test_earlier_germination_consumes_living_room_in_same_step(self):
        winner = seed(birth=30, end=150, outcome='germinated', child=8)
        focal = seed(birth=30, end=None, outcome='pending', parent=2)
        result = audit.seed_history(1, [winner, focal], population(7) + [plant(8, 24, 150)], 150)
        self.assertEqual(result['counts']['precheck_room'], 1)
        self.assertEqual(result['counts']['headcount_room'], 0)
        self.assertEqual(result['counts']['capacity_excluded'], 1)
        self.assertEqual(result['intervals'][0]['state']['living_spacing_blockers'], [8])
        self.assertTrue(result['other_germinations'][0]['checked_earlier'])
        self.assertTrue(result['other_germinations'][0]['same_column'])

    def test_later_germination_does_not_retroactively_block_check(self):
        focal = seed(birth=30, end=None, outcome='pending', parent=2)
        winner = seed(birth=30, end=150, outcome='germinated', child=8)
        result = audit.seed_history(0, [focal, winner], population(7) + [plant(8, 24, 150)], 150)
        self.assertEqual(result['counts']['headcount_room'], 1)
        self.assertEqual(result['counts']['unresolved'], 1)
        self.assertFalse(result['other_germinations'][0]['checked_earlier'])

    def test_spacing_strict_boundary_and_overlapping_blockers(self):
        close = audit.seed_history(0, [seed(column=20)], population(7), 300)
        clear = audit.seed_history(0, [seed(column=21)], population(7), 300)
        both = audit.seed_history(0, [seed(column=20)], population(), 300)
        self.assertEqual(close['counts']['spacing_excluded'], 8)
        self.assertEqual(close['counts']['unresolved'], 0)
        self.assertEqual(clear['counts']['spacing_excluded'], 0)
        self.assertEqual(clear['counts']['unresolved'], 8)
        self.assertEqual(both['counts']['capacity_excluded'], 8)
        self.assertEqual(both['counts']['spacing_excluded'], 8)
        self.assertEqual(both['counts']['mature_checks'], 8)

    def test_parent_death_does_not_end_seed_history(self):
        plants = population(7)
        plants[0]['death_tick'] = 150
        result = audit.seed_history(0, [seed()], plants, 300)
        self.assertEqual(result['counts']['mature_checks'], 8)
        self.assertEqual(result['intervals'][-1]['last'], 240)
        self.assertEqual(result['intervals'][-1]['state']['living_at_turn'], 6)


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch('subprocess.run', side_effect=AssertionError('offline only')), \
             patch('subprocess.Popen', side_effect=AssertionError('offline only')):
            cls.value = audit.load_input()
            cls.derived = audit.make_value(cls.value)

    def test_complete_panel_and_censored_late_cohort(self):
        self.assertEqual(self.derived['panel'], audit.previous.PANEL)
        self.assertEqual(set(self.derived['worlds']), {'fixed', 'cursor'})
        expected = {'fixed': (3, 0, 3), 'cursor': (5, 3, 4)}
        for arm, (births, buyers, late) in expected.items():
            rows = self.derived['summary'][arm]
            self.assertEqual(set(self.derived['worlds'][arm]), set(audit.previous.PANEL))
            self.assertEqual(rows['primary']['recruits'], births)
            self.assertEqual(rows['primary']['buyers'], buyers)
            self.assertEqual(rows['late']['age_32'], {'censored': late})
            self.assertEqual(rows['late']['no_purchase'], late)
            self.assertEqual(rows['primary']['children'] + rows['late']['children'], 0)
        self.assertEqual(self.derived['summary']['cursor']['primary']['seed_fates'],
                         dict(expired=4, germinated=0, pending=1))

    def test_each_seed_counts_and_intervals_are_retained(self):
        rows = {key: [s for p in world['recruits'] for s in p['purchases']]
                for key, world in self.derived['worlds']['cursor'].items()}
        s1 = rows['3a7e45e6-rainfed']
        s2 = rows['366928c6-rainfed-crowded']
        self.assertEqual([s['counts']['headcount_room'] for s in s1], [0, 528])
        self.assertEqual([s['counts']['unresolved'] for s in s1], [0, 0])
        self.assertEqual(s1[1]['intervals'][-1]['state']['living_spacing_blockers'], [42])
        self.assertEqual([s['counts']['headcount_room'] for s in s2], [0, 63, 0])
        self.assertEqual([s['counts']['unresolved'] for s in s2], [0, 63, 0])
        self.assertEqual(s2[1]['counts']['precheck_room'], 64)
        winner = s2[1]['other_germinations'][0]
        self.assertEqual((winner['seed']['parent'], winner['child'], winner['seed']['column']), (31, 36, 15))
        self.assertTrue(winner['checked_earlier'] and winner['same_column'])
        self.assertTrue(s2[2]['censored'])
        self.assertEqual(s2[2]['counts']['mature_checks'], 5841)

    def test_published_evidence_recomputes_without_processes(self):
        path = audit.ROOT / 'benchmarks/garden-seasons/landing-recruit-seeds-results.json.gz'
        with gzip.open(path, 'rt') as stream:
            saved = json.load(stream)
        with patch('subprocess.run', side_effect=AssertionError('offline only')), \
             patch('subprocess.Popen', side_effect=AssertionError('offline only')):
            audit.check_value(saved)
        self.assertEqual(saved, self.derived)

    def test_changed_pending_status_is_rejected(self):
        changed = copy.deepcopy(self.derived)
        changed['summary']['cursor']['primary']['seed_fates']['pending'] = 0
        with self.assertRaisesRegex(RuntimeError, 'differs from frozen ledgers'):
            audit.check_value(changed)

    def test_changed_input_digest_is_rejected(self):
        with patch.object(audit, 'INPUT_SHA', '0' * 64):
            with self.assertRaisesRegex(RuntimeError, 'capture changed'):
                audit.load_input()

    def test_imposed_death_in_new_interval_is_not_misread_as_maintenance(self):
        result = copy.deepcopy(self.value['runs']['endpoint']['cursor']['3a7e45e6-rainfed']['result'])
        next(p for p in result['lineages'] if p['id'] == 51)['environmental_death'] = True
        with self.assertRaisesRegex(RuntimeError, 'post-check imposed deaths'):
            audit.analyze_world(result)

    def test_fresh_output_only_and_identical_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = (Path(directory) / name for name in ('a.gz', 'b.gz'))
            audit.write_gzip(a, self.derived)
            audit.write_gzip(b, self.derived)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            with self.assertRaises(FileExistsError):
                audit.write_gzip(a, self.derived)


if __name__ == '__main__':
    unittest.main()
