"""Offline handoff diagnosis, timing boundaries, and noncausal capacity accounting."""

from copy import deepcopy
import json
import subprocess
import unittest
from unittest import mock

import population_fallback_loss as loss

PUBLISHED = loss.collect.ROOT / 'benchmarks/garden-seasons/leaf-population-fallback-loss.json'


def seed_fixture():
    seed = dict(parent=2, birth_tick=0, column=7, end_tick=45, outcome='expired')
    record = dict(parent=2, birth_tick=0, first_tick=15, last_tick=45, column=7, outcome=1,
                  attempts=dict(checks=2, expired=1, germinated=0, masks={'32': 2},
                                no_living_masks={}, open_sites={}, light_min=0, light_max=100,
                                moisture_min=0, moisture_max=100))
    plant = dict(id=2, column=7, birth_tick=0, death_tick=45)
    value = dict(seeds=[seed], lineages=[plant], family_roots=[1, 2])
    return record, value


class LossAccountingTests(unittest.TestCase):
    def test_frozen_capacity_and_cadence_not_player_buffer_limits(self):
        files = loss.prepare.expected_files(loss.prepare.load_archive())
        header = files['source/src/garden_world.h'].decode()
        guard = files['source/src/garden_maintenance_guard.h'].decode()
        cmake = files['source/maintenance-fixture/CMakeLists.txt'].decode()
        self.assertIn('#define PICOSYSTEM_GARDEN_MAX_SEEDS 8U', header)
        self.assertIn('#define PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR  4U', header)
        self.assertEqual(loss.CADENCE, 4 * loss.score.STEP)
        for flag in ('TOY_FACTORY_GARDEN_LARGE_SEED_BANK', 'TOY_FACTORY_GARDEN_SEASONAL_SEED_BANK'):
            self.assertIn('defined(' + flag + ')', guard)
            self.assertNotIn(flag, cmake)
        self.assertIn('#error "Maintenance transfer excludes unrelated ecology experiments"', guard)

    def test_expiry_is_not_a_seed_check(self):
        record, value = seed_fixture()
        result = loss.seed_exposure(record, value)
        self.assertEqual((result['first_check_tick'], result['last_check_tick']), (15, 30))
        self.assertEqual(result['known_persistent_living_blockers'][0]['lineage'], 2)
        self.assertFalse(result['trace_censored'])
        # A death at expiry still occurs AFTER every actual check. A death at
        # the last check is order-ambiguous and cannot prove a living blocker.
        value['lineages'][0]['death_tick'] = 30
        self.assertEqual(loss.seed_exposure(record, value)['known_persistent_living_blockers'], [])
        value['lineages'][0].update(death_tick=None, birth_tick=15)
        self.assertEqual(loss.seed_exposure(record, value)['known_persistent_living_blockers'], [])

    def test_persistent_blocker_cannot_have_an_open_check(self):
        record, value = seed_fixture()
        record['attempts']['masks'] = {'32': 1, '2': 1}
        with self.assertRaisesRegex(ValueError, 'contradicts spacing'):
            loss.seed_exposure(record, value)
        # Lack of a proven living blocker does not prove the site was clear:
        # a dead occupant can still be retained in a physical slot.
        value['lineages'][0]['death_tick'] = 0
        self.assertEqual(loss.seed_exposure(record, value)['known_persistent_living_blockers'], [])

    def test_censoring_does_not_import_future_failure_into_check_counts(self):
        record, value = seed_fixture()
        record.update(last_tick=30, outcome=0)
        record['attempts']['expired'] = 0
        result = loss.seed_exposure(record, value)
        self.assertTrue(result['trace_censored'])
        self.assertEqual(result['last_check_tick'], 30)
        self.assertEqual(result['end_tick'], 45)
        self.assertEqual(result['attempts']['expired'], 0)

    def test_event_ticks_are_not_sequential_reproduction_observations(self):
        value = dict(ticks=240, family_roots=[1, 2, 3], seeds=[
            dict(parent=1, birth_tick=0, end_tick=120),
            dict(parent=2, birth_tick=120, end_tick=180)])
        result = loss.seed_bank(value, 0, 240)
        self.assertEqual(result['non_event_occupancy'], {'1': 1, '0': 1})
        self.assertEqual(result['event_cadence_ticks'], [120, 180])
        self.assertEqual(result['purchases_by_founder'], {'1': 0, '2': 1, '3': 0})
        self.assertEqual(result['non_event_cadence_samples'], 2)
        for start, end in ((-1, 240), (240, 240), (0, 241)):
            with self.assertRaises(ValueError):
                loss.seed_bank(value, start, end)
        crowded = deepcopy(value)
        crowded['seeds'] = [dict(parent=1, birth_tick=0, end_tick=None)] * 9
        with self.assertRaisesRegex(ValueError, 'capacity'):
            loss.seed_bank(crowded, 0, 240)


class PublishedLossTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native calls forbidden')):
            cls.result = loss.diagnose()

    def test_exact_published_derivation_and_coverage(self):
        self.assertEqual(self.result, json.loads(PUBLISHED.read_bytes()))
        self.assertEqual(self.result['native_calls'], 0)
        self.assertEqual(len(self.result['inputs']), 6)
        self.assertEqual(set(self.result['cases']), {'original', 'fewest'})
        self.assertEqual((self.result['handoff_first_tick'], self.result['trace_stop_tick'],
                          self.result['outcome_stop_tick']), (241920, 983040, 2334720))

    def test_longer_lived_adults_do_not_imply_family_replacement(self):
        cases = self.result['cases']
        first = [{p['id']: p for p in cases[mode]['posthandoff_plants']}
                 for mode in ('original', 'fewest')]
        self.assertEqual([first[0][i]['purchases_through_256'] for i in (16, 17)], [5, 1])
        self.assertEqual([first[1][i]['purchases_through_256'] for i in (16, 17)], [9, 2])
        for i in (16, 17):
            self.assertEqual(first[0][i]['birth_tick'], first[1][i]['birth_tick'])
            self.assertLess(first[0][i]['death_tick'], first[1][i]['death_tick'])
        self.assertEqual(cases['fewest']['seed_summary'], dict(count=11,
            outcomes=dict(expired=9, germinated=2), expired_always_spacing_blocked=8,
            expired_with_persistent_own_blocker=3, expired_with_persistent_other_blocker=5))
        self.assertEqual(cases['original']['seed_summary']['outcomes'], dict(expired=11, germinated=8, censored=2))
        self.assertEqual(first[1][18]['seeds_created'], 0)
        self.assertFalse(first[1][18]['established_by_608'])

    def test_winter_failure_has_energy_debt_without_water_debt(self):
        original = self.result['cases']['original']['edge_child']['windows']['126-127']
        fewest = self.result['cases']['fewest']['edge_child']['windows']['126-127']
        self.assertEqual((original['samples'], fewest['samples']), (256, 252))
        self.assertEqual((original['energy']['income'], fewest['energy']['income']), (217, 99))
        self.assertEqual((original['renewals'], fewest['renewals']), (7, 0))
        self.assertEqual((fewest['energy_short'], fewest['water_short']), (8, 0))
        self.assertEqual(fewest['water']['discarded'], 508)
        self.assertEqual((fewest['condition_before'], fewest['condition_after']), (679, 71))

    def test_capacity_pressure_and_terminal_seed_gap(self):
        original, fewest = (self.result['cases'][p] for p in ('original', 'fewest'))
        bank = fewest['bank_128_232']
        self.assertEqual(bank['capacity'], 8)
        self.assertEqual(bank['non_event_occupancy'], {'8': 6625})
        self.assertEqual(len(bank['event_cadence_ticks']), 31)
        self.assertEqual(bank['purchases_by_founder'], {'1': 12, '2': 3, '3': 15})
        self.assertEqual(original['bank_128_232']['purchases_by_founder']['2'], 12)
        self.assertEqual(fewest['lineage17_128_232'], dict(resource_days=104,
            daily_endpoints_energy_ge_200_water_ge_400=91, stress_free_days=103))
        self.assertEqual(fewest['seedless_terminal_ticks'], 31980)
        terminal = fewest['posthandoff_seeds'][-1]
        self.assertEqual(terminal['end_tick'], 859740)
        self.assertEqual(terminal['attempts']['checks'] - terminal['attempts']['blockers']['spacing'], 90)
        self.assertEqual({k: v for k, v in terminal['attempts']['masks'].items() if not int(k) & 32},
                         {'2': 55, '6': 35})


if __name__ == '__main__':
    unittest.main()
