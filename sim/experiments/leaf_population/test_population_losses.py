"""Loss classifications, terminal sequences and the complete published family roster."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import collect_population as collect
import population_losses as losses
import population_score as score
from test_population_analysis import history

PUBLISHED = collect.ROOT / 'benchmarks/garden-seasons/leaf-population-losses.json'


def add_seed(value, parent, birth, end=None, outcome='pending'):
    p = value['lineages'][parent - 1]
    value['seeds'].append(dict(parent=parent, birth_tick=birth, end_tick=end, child_id=None,
        lifetime_ecology_ticks=8192, outcome=outcome, species=p['species'], generation=p['generation'] + 1,
        column=p['column']))
    p['seeds_created'] += 1
    p['late_seeds_created'] += 1


class LossTests(unittest.TestCase):
    def test_loss_stages_and_age_boundary(self):
        d = score.DAY
        no_seed = history(deaths={1: 15})
        self.assertEqual(losses.family_rows(no_seed)[0]['loss_path'], 'no-seed-purchases')
        no_child = history(deaths={1: 30})
        add_seed(no_child, 1, 15, 15 + 32 * d, 'expired')
        self.assertEqual(losses.family_rows(no_child)[0]['loss_path'], 'no-offspring')
        child = history([(1, 150, 150 + 32 * d)], deaths={1: 60})
        row = losses.family_rows(child)[0]
        self.assertEqual(row['loss_path'], 'no-established-offspring')
        self.assertIsNone(row['first_established_tick'])
        child['lineages'][-1]['death_tick'] += 15
        row = losses.family_rows(child)[0]
        self.assertEqual(row['loss_path'], 'established-then-lost')
        self.assertEqual(row['first_established_tick'], 150 + 32 * d)

    def test_pending_seeds_prevent_extinction_and_survivors_are_not_losses(self):
        value = history(deaths={1: 30}, end=60)
        add_seed(value, 1, 15)
        rows = losses.family_rows(value)
        self.assertEqual(rows[0]['status'], 'dormant')
        self.assertEqual(rows[0]['last_living_death_tick'], 30)
        self.assertIsNone(rows[0]['extinction_tick'])
        self.assertIsNone(rows[0]['terminal_seed_only_ticks'])
        self.assertIsNone(rows[0]['loss_path'])
        self.assertEqual(rows[1]['status'], 'living')
        self.assertIsNone(rows[1]['last_living_death_tick'])

    def test_terminal_seed_expiry_and_posthumous_germination(self):
        d = score.DAY
        value = history(deaths={1: 45})
        add_seed(value, 1, 15, 15 + 32 * d, 'expired')
        add_seed(value, 1, 30, 30 + 32 * d, 'expired')
        row = losses.family_rows(value)[0]
        self.assertEqual(row['terminal_event'], 'seed-expiry')
        self.assertEqual(len(row['seeds_at_last_living_death']), 2)
        self.assertEqual(row['extinction_tick'], 30 + 32 * d)
        self.assertEqual(row['terminal_seed_only_ticks'], 32 * d - 15)
        # A legitimate posthumous birth is a return from dormancy, not revival after extinction.
        posthumous = history([(1, 150, 300)], deaths={1: 45})
        row = losses.family_rows(posthumous)[0]
        self.assertEqual(row['last_living_death_tick'], 300)
        self.assertEqual(row['terminal_event'], 'last-death')
        self.assertEqual(row['extinction_tick'], 300)

    def test_same_tick_seed_expiry_is_not_positive_dormancy(self):
        t = 15 + 32 * score.DAY
        value = history(deaths={1: t})
        add_seed(value, 1, 15, t, 'expired')
        row = losses.family_rows(value)[0]
        self.assertEqual(row['terminal_event'], 'last-death')
        self.assertEqual(row['terminal_seed_only_ticks'], 0)
        self.assertEqual(row['seeds_at_last_living_death'], [])

    def test_recent_offspring_and_tied_final_deaths(self):
        value = history([(1, 150, None)], end=300)
        row = losses.family_rows(value)[0]
        self.assertEqual(row['offspring'], dict(born=1, established=0, early_deaths=0, young_alive=1))
        value = history([(1, 150, 300)], deaths={1: 300})
        value['death_causes'][3] = 1
        rows = losses.family_rows(value)
        self.assertEqual(len(rows[0]['final_deaths']), 2)
        summary = losses.summarize(rows)
        self.assertEqual(summary['status']['extinct'], 1)
        self.assertEqual(summary['final_death_flags'], dict(energy=1, water=1, combined=0, other=0))

    def test_winter_calendar_does_not_claim_a_cold_or_solar_gate(self):
        value = history(deaths={1: 14 * score.DAY + 15})
        summary = losses.summarize(losses.family_rows(value))
        self.assertEqual(summary['final_winter_energy_deaths'], 1)
        self.assertEqual(summary['final_death_year_days']['14'], 1)
        row = losses.family_rows(value)[0]
        self.assertNotIn('cold', row['final_deaths'][0])
        self.assertNotIn('light', row['final_deaths'][0])

    def test_incomplete_or_misassigned_history_is_rejected(self):
        value = history([(1, 150, None)])
        for mutate in (lambda v: v.update(complete=False), lambda v: v.update(ledger_start_tick=15),
                       lambda v: v['family_roots'].__setitem__(3, 2)):
            changed = deepcopy(value)
            mutate(changed)
            with self.assertRaises(ValueError):
                losses.family_rows(changed)
        with self.assertRaisesRegex(ValueError, '24-world roster'):
            losses.panel({})


class PublishedLossTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('simulator execution forbidden')):
            cls.result = losses.diagnose()

    def test_exact_published_derivation_and_complete_roster(self):
        self.assertEqual(self.result, json.loads(PUBLISHED.read_bytes()))
        self.assertEqual(self.result['native_calls'], 0)
        self.assertEqual(len(self.result['families']), 96)
        self.assertEqual(len(self.result['inputs']), 24)
        self.assertEqual(len({(r['model'], r['seed'], r['layout'], r['founder'])
                              for r in self.result['families']}), 96)
        for model, expected in zip(score.MODELS, (11, 19, 15), strict=True):
            self.assertEqual(self.result['summaries'][model]['status']['extinct'], expected)

    def test_paired_losses_and_species_counts(self):
        first = self.result['contrasts']['s1-g3-c4']
        second = self.result['contrasts']['s2-g3-c1']
        self.assertEqual([len(first[k]) for k in ('additional_losses', 'rescued', 'lost_in_both', 'retained_in_both')],
                         [8, 0, 11, 13])
        self.assertEqual(sum(r['loss_path'] == 'established-then-lost' for r in first['additional_losses']), 6)
        self.assertEqual([len(second[k]) for k in ('additional_losses', 'rescued', 'lost_in_both', 'retained_in_both')],
                         [5, 1, 10, 16])
        for model, lost_shrubs in zip(score.MODELS, (8, 12, 11), strict=True):
            species = self.result['summaries'][model]['species']
            self.assertEqual([species[s]['founders'] for s in losses.SPECIES], [12, 12, 8])
            self.assertEqual(species['shrub']['status']['extinct'], lost_shrubs)

    def test_existing_output_and_modified_archive_rejected(self):
        with tempfile.TemporaryDirectory(prefix='garden-loss-test-') as temporary:
            path = Path(temporary) / 'existing.json'
            path.write_bytes(b'keep me')
            with self.assertRaises(FileExistsError):
                collect.save(path, self.result)
            self.assertEqual(path.read_bytes(), b'keep me')
            with self.assertRaisesRegex(ValueError, 'identity differs'):
                losses.diagnose(path)


if __name__ == '__main__':
    unittest.main()
