"""Offline early-life accounting, narrow seed handoffs, and interpretation boundaries."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import population_gates_early as early

PUBLISHED = early.collect.ROOT / 'benchmarks/garden-seasons/leaf-population-gates-early.json'


class EarlyAccountingTests(unittest.TestCase):
    def test_stocks_are_not_summed_and_discontinuity_is_rejected(self):
        def row(day, before, after, income):
            flow = dict(before=before, after=after, income=income, upkeep_due=5, upkeep_paid=5,
                        endowment=0, overflow=0, growth=0, seeds=0, discarded=0, repair=0)
            return dict(day=day, lineage=2, first_tick=day * 3840 + 15, last_tick=(day + 1) * 3840,
                        samples=256, renewals=0, energy_short=0, water_short=0,
                        leaves_before=1, leaves_after=1, condition_before=100, condition_after=90,
                        energy=flow, water=dict(flow))
        resources = dict(plant_days=[row(0, 10, 14, 9), row(1, 14, 11, 2)])
        result = early.plant_window(resources, 2, 0, 2)
        self.assertEqual(result['energy']['before'], 10)
        self.assertEqual(result['energy']['after'], 11)
        self.assertEqual(result['energy']['income'], 11)
        self.assertEqual(result['energy']['upkeep_paid'], 10)
        self.assertEqual(result['samples'], 512)
        self.assertIsNone(early.plant_window(resources, 2, 2, 3))
        with self.assertRaisesRegex(ValueError, 'invalid resource window'):
            early.plant_window(resources, 2, 0, 257)
        changed = deepcopy(resources)
        changed['plant_days'][1]['energy']['before'] += 1
        with self.assertRaisesRegex(ValueError, 'resource continuity differs'):
            early.plant_window(changed, 2, 0, 2)
        changed = deepcopy(resources)
        changed['plant_days'][0]['energy']['income'] += 1
        with self.assertRaisesRegex(ValueError, 'resource conservation differs'):
            early.plant_window(changed, 2, 0, 2)

    def test_blockers_overlap_and_open_sites_are_column_marginals(self):
        row = dict(checks=4, expired=1, germinated=1, light_min=0, light_max=255,
                   moisture_min=0, moisture_max=100, masks={'32': 1, '34': 2, '0': 1},
                   no_living_masks={'32': 1}, open_sites={'7': 3, '19': 2})
        result = early.checks_summary([row])
        self.assertEqual(result['checks'], 4)  # Expiry is not a successful check.
        self.assertEqual(result['blockers']['spacing'], 3)
        self.assertEqual(result['blockers']['moisture'], 2)
        self.assertEqual(result['spacing_only'], 1)
        self.assertEqual(result['no_living_spacing_only'], 1)
        self.assertEqual(result['open_sites'], {'7': 3, '19': 2})
        self.assertGreater(sum(result['open_sites'].values()), result['checks'])
        row['no_living_masks']['32'] = 2
        with self.assertRaisesRegex(ValueError, 'seed checks do not reconcile'):
            early.checks_summary([row])

    def test_changed_archive_is_rejected_before_parsing(self):
        with tempfile.TemporaryDirectory(prefix='early-evidence-') as temporary:
            path = Path(temporary) / 'bad.gz'
            path.write_bytes(b'not the published archive')
            with self.assertRaisesRegex(ValueError, 'archive identity differs'):
                early.archive(path, early.ARCHIVE_SHA, early.panel.ARCHIVE_SCHEMA)


class PublishedEarlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native calls forbidden')):
            cls.result = early.diagnose()

    def test_exact_published_derivation_and_coverage(self):
        self.assertEqual(self.result, json.loads(PUBLISHED.read_bytes()))
        self.assertEqual(self.result['native_calls'], 0)
        self.assertEqual(len(self.result['inputs']), 36)
        self.assertEqual(set(self.result['cases']), set(early.SEEDS))
        self.assertTrue(all(set(cases) == set(early.panel.gates.VARIANTS)
                            for cases in self.result['cases'].values()))
        self.assertEqual((self.result['early_stop_day'], self.result['trace_stop_day'],
                          self.result['outcome_stop_day']), (64, 256, 608))

    def test_founder_budget_does_not_rank_like_family_survival(self):
        cases = self.result['cases']['9a903368']
        budgets = [cases[v]['founder_budget_through_day64'] for v in early.panel.gates.VARIANTS]
        self.assertEqual([b['renewals'] for b in budgets], [313, 295, 356, 384])
        self.assertEqual([b['energy_short'] for b in budgets], [13, 17, 15, 12])
        self.assertEqual([b['water_short'] for b in budgets], [0, 0, 0, 0])
        self.assertEqual([b['energy']['overflow'] for b in budgets], [32481, 27024, 29701, 31283])
        self.assertEqual([cases[v]['family_at_day608']['living'] for v in early.panel.gates.VARIANTS], [0, 4, 2, 0])

    def test_posthumous_handoffs_are_young_at_day64_but_later_establish(self):
        cases = self.result['cases']['9a903368']
        for variant, child, column, margin in (('light', 15, 19, 120), ('condition', 16, 15, 240)):
            family = cases[variant]['family_at_day64']
            self.assertEqual((family['living'], family['offspring']['established'],
                              family['offspring']['young_alive']), (1, 0, 1))
            returned, = cases[variant]['seed_only_returns_through_day64']
            self.assertEqual((returned['child_id'], returned['column']), (child, column))
            self.assertLess(returned['parent_death_tick'], returned['end_tick'])
            self.assertEqual(returned['remaining_ticks_at_germination'], margin)
            self.assertTrue(returned['child_established_by_608'])
            self.assertEqual(returned['attempts']['masks']['0'], 1)
            self.assertEqual(returned['attempts']['no_living_masks']['0'], 1)
        self.assertEqual(cases['both']['family_at_day64']['status'], 'dormant')
        self.assertEqual(cases['none']['seed_only_returns_through_day64'], [])

    def test_combined_terminal_seed_has_persistent_spacing_and_open_alternatives(self):
        case = self.result['cases']['9a903368']['both']
        terminal = next(s for s in case['early_seed_fates'] if s['birth_tick'] == 34 * early.score.DAY)
        self.assertEqual((terminal['column'], terminal['outcome'], terminal['end_tick']),
                         (6, 'expired', 66 * early.score.DAY))
        a = terminal['attempts']
        self.assertEqual((a['checks'], a['blockers']['spacing'], a['spacing_only']), (8191, 8191, 519))
        self.assertEqual((a['no_living_checks'], a['no_living_spacing_only']), (832, 275))
        window = case['seed_check_windows']['64-66']
        self.assertEqual((window['checks'], window['no_living_checks'], window['spacing_only']), (511, 511, 158))
        self.assertEqual(window['open_sites']['7'], 139)
        self.assertEqual(window['blockers']['plant-capacity'], 0)
        self.assertEqual(window['blockers']['node-capacity'], 0)
        bundle = early.archive(early.ARCHIVE, early.ARCHIVE_SHA, early.panel.ARCHIVE_SCHEMA)
        value = json.loads(early.prepare.blob(bundle, 'runs/9a903368-both-on/stdout.json'))
        flower = value['lineages'][0]
        self.assertEqual((flower['species'], flower['column'], flower['birth_tick']), (0, 4, 0))
        self.assertIsNone(flower['death_tick'])
        # Frozen narrow dispersal is origin +/- (5 + trait + [0,2]);
        # all trait values are covered, so no unrecorded genome is guessed.
        origin = value['lineages'][terminal['parent'] - 1]['column']
        self.assertEqual(origin, 13)
        living_at_purchase = [p for p in value['lineages'] if p['birth_tick'] < terminal['birth_tick'] and
                              (p['death_tick'] is None or p['death_tick'] > terminal['birth_tick'])]
        for trait in range(-2, 3):
            for distance in range(5 + trait, 8 + trait):
                for column in (origin - distance, origin + distance):
                    self.assertTrue(0 <= column < 28)  # No edge reflection in this case.
                    self.assertTrue(any(abs(p['column'] - column) < 3 for p in living_at_purchase))
        # The two successful handoff seeds were also spacing-blocked when bought.
        for variant, child in (('light', 15), ('condition', 16)):
            world = json.loads(early.prepare.blob(bundle, f'runs/9a903368-{variant}-on/stdout.json'))
            seed = next(s for s in world['seeds'] if s['child_id'] == child)
            self.assertTrue(any(p['birth_tick'] < seed['birth_tick'] and
                                (p['death_tick'] is None or p['death_tick'] > seed['birth_tick']) and
                                abs(p['column'] - seed['column']) < 3 for p in world['lineages']))

    def test_second_case_preserves_late_prefix_and_separates_founder_from_child(self):
        cases = self.result['cases']['59818bc3']
        children = [next(p for p in cases[v]['early_plants'] if p['id'] == 7)
                    for v in early.panel.gates.VARIANTS]
        self.assertEqual([p['death_tick'] / 3840 for p in children],
                         [318.671875, 14.78125, 190.796875, 14.8125])
        self.assertEqual([p['windows']['0-12']['leaves_after'] for p in children], [13, 14, 13, 14])
        self.assertEqual([p['windows']['0-12']['energy']['income'] for p in children], [7742, 7110, 7949, 7227])
        self.assertEqual([cases[v]['family_at_day608']['living'] for v in early.panel.gates.VARIANTS], [0, 0, 0, 0])
        self.assertTrue(all(v['early_prefix_matches_unchanged'] for v in self.result['late_comparison'].values()))
        self.assertEqual([self.result['late_comparison'][v]['family_at_day608']['living']
                          for v in early.panel.gates.VARIANTS], [0, 2, 0, 2])


if __name__ == '__main__':
    unittest.main()
