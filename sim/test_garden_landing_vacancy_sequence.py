#!/usr/bin/env python3
"""Stage timing, observed opportunities, censoring and saved-panel integrity."""

from contextlib import contextmanager
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_vacancy_sequence as audit

RESULT = audit.ROOT / 'benchmarks/garden-seasons/landing-vacancy-sequence-results.json.gz'


@contextmanager
def small_clock():
    with patch.object(audit, 'START', 15), patch.object(audit, 'STOP', 300), \
         patch.object(audit.expand, '__defaults__', (15, 300)), \
         patch.dict(audit.late.PERIODS, {'post': 15, 'late32': 150}, clear=True):
        yield


def life(i, column, birth=0, death=None, parent=0):
    return dict(id=i, column=column, birth_tick=birth, death_tick=death, parent=parent,
                generation=int(bool(parent)), species=0, seeds_created=0)


def fixture(release=45, column=3, pending=False):
    lives = [life(1, 3, death=30), life(2, 9)]
    if not pending: lives.append(life(3, column, birth=135, parent=2))
    seed = dict(parent=2, birth_tick=15, end_tick=None if pending else 135, child_id=None if pending else 3,
                column=column, generation=1, species=0, lifetime_ecology_ticks=8192,
                outcome='pending' if pending else 'germinated')
    states = [[15, [1, 2]], [release, [2]]]
    if not pending:
        if release == 135: states[-1][1].append(3)
        else: states.append([135, [2, 3]])
    result = dict(lineages=lives, seeds=[seed], plant_slots=1 if pending else 2, tick=300, seed='f7ee4528')
    purchase = dict(choices=[2, 14, 3, 15, 4, 16] if column != 0 else [0, 18, 1, 17, 2, 16])
    count = 19 if pending else 8
    world = dict(run=dict(result=result), reach=[dict(seed=[2, 15], purchase=purchase, samples=count)])
    rows = dict(states=states, observations=[], full_checks=count, full_purchases=1)
    ids = {p['id']: p for p in lives}
    for tick in range(30, 301, 15):
        checks = []
        if pending or tick <= 135:
            slots = [2] if tick >= release else [1, 2]
            opened = audit.clear(slots, ids)
            mask = (int(tick < 135) | (32 if not opened & (1 << column) else 0))
            if pending:
                mask |= 4
                opened &= ~(1 << column)
            checks = [[0, mask, opened]]
        audit.append_span(rows['observations'], tick, checks)
    return world, rows


class ContractTests(unittest.TestCase):
    def test_climate_boundaries_and_cold_are_not_death_commands(self):
        a = audit.climate(0xf7ee4528, 0)
        self.assertEqual((a['year'], a['day'], a['season'], a['cold']), (0, 0, 'spring', False))
        self.assertEqual(audit.climate(0xf7ee4528, 16 * 3840)['year'], 1)
        winter = audit.climate(0xf7ee4528, 14 * 3840)
        self.assertEqual(winter['season'], 'winter')
        self.assertLess(winter['light_percent'], 65)
        self.assertTrue(winter['cold'])
        self.assertTrue(any(audit.climate(0xf7ee4528, d * 3840)['drought'] for d in range(4, 8)))
        with self.assertRaises(RuntimeError): audit.climate(0xf7ee4528, 1)

    def test_dead_occupant_still_excludes_spacing(self):
        lives = {1: life(1, 3, death=30), 2: life(2, 9)}
        self.assertFalse(audit.clear([1, 2], lives) & (1 << 3))
        self.assertTrue(audit.clear([2], lives) & (1 << 3))
        self.assertTrue(audit.clear([1], lives) & 1)
        with self.assertRaises(RuntimeError): audit.clear([1, 1], lives)

    def test_rle_roundtrip_and_missing_redundant_spans(self):
        spans = []
        for t, values in ((30, []), (45, []), (60, [[0, 1, 1]])): audit.append_span(spans, t, values)
        self.assertEqual(spans, [[30, 45, []], [60, 60, [[0, 1, 1]]]])
        self.assertEqual([t for t, _ in audit.expand(spans, 15, 60)], [30, 45, 60])
        for bad in (spans[:1], [[30, 30, []], [45, 60, []]], [[45, 60, []]]):
            with self.assertRaises(RuntimeError): list(audit.expand(bad, 15, 60))

    def test_release_follows_death_and_cannot_lose_a_living_plant(self):
        world, rows = fixture()
        with small_clock():
            _, removed, events = audit.slot_history(world['run']['result'], rows['states'])
            self.assertEqual(removed, {1: 45})
            self.assertEqual(events[0]['gained'], audit.bits(range(1, 6)))
            for death in (None, 45, 60):
                bad = copy.deepcopy(world['run']['result'])
                bad['lineages'][0]['death_tick'] = death
                with self.assertRaises(RuntimeError): audit.slot_history(bad, rows['states'])

    def test_opening_precedes_maturity_and_newborn_closes_multiple_columns_once(self):
        world, rows = fixture()
        with small_clock(): result = audit.analyze_world(world, rows)
        col = result['releases'][0]['columns']['3']
        self.assertEqual(col['first_observed_open']['tick'], 45)
        self.assertEqual(col['first_reachable_mature']['tick'], 135)
        self.assertEqual((col['closed_tick'], col['closed_by']), (135, 3))
        self.assertEqual(col['germinated']['child'], 3)
        self.assertEqual(len(result['replacements']), 1)
        self.assertEqual(result['replacements'][0]['survival'], {'1': 'censored', '32': 'censored'})
        self.assertEqual(result['periods']['post']['dead_stored'], 1)

    def test_same_step_release_and_birth_is_not_lost_in_post_step_census(self):
        world, rows = fixture(release=135)
        with small_clock(): result = audit.analyze_world(world, rows)
        event = result['releases'][0]
        self.assertEqual(event['before_checks'], [2])
        self.assertEqual(event['columns']['3']['first_observed_open']['tick'], 135)
        self.assertEqual(event['columns']['3']['closed_tick'], 135)

    def test_reachable_alternative_does_not_move_an_existing_seed(self):
        world, rows = fixture(column=4, pending=True)
        with small_clock(): result = audit.analyze_world(world, rows)
        c = result['releases'][0]['columns']['3']
        self.assertIsNotNone(c['first_reachable_mature'])
        self.assertEqual(c['first_reachable_mature']['landing'], 4)
        self.assertIsNone(c['germinated'])
        self.assertIsNone(c['closed_tick'])
        self.assertEqual(result['replacements'], [])

    def test_preexisting_opening_is_not_a_new_release_replacement(self):
        world, rows = fixture(column=0)
        with small_clock(): result = audit.analyze_world(world, rows)
        self.assertIn(0, result['initial_spacing_clear'])
        self.assertNotIn('0', result['releases'][0]['columns'])
        self.assertEqual(result['releases'][0]['columns']['1']['closed_by'], 3)
        self.assertEqual(result['replacements'], [])
        self.assertEqual(result['periods']['post']['births'], 1)

    def test_simultaneous_release_and_no_checks_means_unobserved_not_unusable(self):
        lives = [life(1, 3, death=30), life(2, 9, death=30)]
        world = dict(run=dict(result=dict(lineages=lives, seeds=[], plant_slots=0, tick=300, seed='f7ee4528')), reach=[])
        rows = dict(states=[[15, [1, 2]], [45, []]], observations=[[30, 300, []]], full_checks=0, full_purchases=0)
        with small_clock(): result = audit.analyze_world(world, rows)
        self.assertEqual(result['releases'][0]['ids'], [1, 2])
        self.assertEqual(len(result['releases']), 1)
        self.assertEqual(result['periods']['post']['site_observed'], 0)
        self.assertGreater(result['periods']['post']['spacing_clear'], 0)
        self.assertTrue(all(v['first_observed_open'] is None and v['closed_tick'] is None
                            for v in result['releases'][0]['columns'].values()))

    def test_expiry_has_no_site_census_and_pending_stays_censored(self):
        world, rows = fixture(column=4, pending=True)
        s = world['run']['result']['seeds'][0]
        s.update(end_tick=150, outcome='expired', lifetime_ecology_ticks=9)
        world['reach'][0]['samples'] = rows['full_checks'] = 9
        expanded = list(audit.expand(rows['observations'], 15, 300))
        rows['observations'] = []
        for tick, checks in expanded:
            audit.append_span(rows['observations'], tick, [[0, -1, 0]] if tick == 150 else [] if tick > 150 else checks)
        with small_clock(): result = audit.analyze_world(world, rows)
        self.assertEqual(result['periods']['post']['site_observed'], 8)
        self.assertEqual(result['periods']['post']['mature_checks'], 1)
        self.assertEqual(result['replacements'], [])

    def test_missing_duplicate_and_impossible_stage_checks_fail(self):
        world, rows = fixture()
        for change in ('missing', 'duplicate', 'mask', 'open', 'clock', 'slots'):
            bad = copy.deepcopy(rows)
            if change == 'missing': bad['observations'][0][2] = []
            elif change == 'duplicate': bad['observations'][0][2] *= 2
            elif change == 'mask': bad['observations'][0][2][0][1] ^= 32
            elif change == 'open': bad['observations'][0][2][0][2] |= 1 << 3
            elif change == 'clock': bad['observations'][0][0] += 15
            else: bad['states'][1][1].append(99)
            with self.subTest(change=change), small_clock(), self.assertRaises(RuntimeError):
                audit.analyze_world(world, bad)

    def test_existing_outputs_and_broken_symlinks_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(audit, 'source',
                side_effect=AssertionError('must reject before loading evidence')):
            link = Path(folder) / 'link'
            link.symlink_to(Path(folder) / 'missing')
            for path in (Path(folder), link):
                with self.assertRaisesRegex(RuntimeError, 'fresh'): audit.export(Path('/missing'), path)

    def test_bad_manifest_fails_before_source_or_trace_read(self):
        with patch.object(audit, 'digest', return_value='wrong'):
            with self.assertRaisesRegex(RuntimeError, 'manifest'): audit.check_bundle(Path('/missing'), {})

    def test_provenance_pins_captured_runtime_not_future_c_edits(self):
        def digest(path):
            name = str(path.relative_to(audit.ROOT))
            if name in audit.IMPLEMENTATION: raise AssertionError('must not read mutable runtime source')
            return audit.PROTOCOL_SHA if name == audit.PROTOCOL else audit.INPUTS[name]
        with patch.object(audit, 'digest', side_effect=digest):
            self.assertEqual(audit.provenance()['implementation'], audit.IMPLEMENTATION)


@unittest.skipUnless(RESULT.exists(), 'vacancy audit has not been retained yet')
class CapturedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(RESULT, 'rt') as stream: cls.value = json.load(stream)
        cls.panel = audit.source()[1]

    def test_portable_reanalysis_cannot_launch_processes(self):
        with patch('subprocess.Popen', side_effect=AssertionError('unexpected process')), \
             patch('subprocess.run', side_effect=AssertionError('unexpected process')):
            audit.check_value(self.value)

    def test_all_primary_worlds_and_no_repeat_pseudoreplicates(self):
        self.assertEqual(len(self.panel), 32)
        self.assertEqual(set(self.value['rows']), set(self.panel))
        self.assertTrue(all(k.endswith('-trace') for k in self.panel))

    def test_full_inventory_and_observation_denominators(self):
        self.assertEqual(sum(r['full_checks'] for r in self.value['rows'].values()), 16640021)
        self.assertEqual(sum(r['full_purchases'] for r in self.value['rows'].values()), 2700)
        self.assertEqual(sum(a['periods']['post']['samples'] for a in self.value['analysis'].values()), 760448)
        self.assertTrue(all(a['periods']['post']['site_observed'] == a['periods']['post']['samples']
                            for a in self.value['analysis'].values()))

    def test_turnover_exists_and_reclamation_is_short(self):
        analyses = self.value['analysis'].values()
        self.assertEqual(sum(a['periods']['post']['deaths'] for a in analyses), 153)
        self.assertEqual(sum(a['periods']['post']['releases'] for a in analyses), 153)
        self.assertEqual(sum(len(a['releases']) for a in analyses), 140)
        delays = [d['delay_ticks'] for a in analyses for d in a['deaths']]
        self.assertEqual((min(delays), max(delays)), (765, 975))
        self.assertTrue(all(a['periods']['post']['deaths'] > 0 for a in analyses))

    def test_late_births_return_only_in_broader_worlds(self):
        for arm, births in (('cap', 0), ('cap-wick', 0), ('wide-cap', 7), ('wide-cap-wick', 4)):
            selected = [self.value['analysis'][k] for k, w in self.panel.items() if w['arm'] == arm]
            self.assertEqual(len(selected), 8)
            self.assertEqual(sum(a['periods']['late32']['births'] for a in selected), births)

    def test_partial_refill_does_not_hide_remaining_clear_columns(self):
        for arm, expected in (('cap', 16), ('cap-wick', 8), ('wide-cap', 2), ('wide-cap-wick', 3)):
            events = [e for key, world in self.panel.items() if world['arm'] == arm
                      for e in self.value['analysis'][key]['releases']]
            remaining = [e for e in events if any(c['closed_tick'] is None for c in e['columns'].values())]
            self.assertEqual(len(remaining), expected)
        broad = [e for key, world in self.panel.items() if world['arm'].startswith('wide-')
                 for e in self.value['analysis'][key]['releases']
                 if any(c['closed_tick'] is None for c in e['columns'].values())]
        self.assertEqual(sum(e['tick'] > audit.STOP - audit.DAY for e in broad), 4)

    def test_seed_at_a_clear_site_can_wait_for_a_slot_elsewhere(self):
        key = 'f7ee4528-fixed-candidate-control-wide-cap-trace'
        result = self.panel[key]['run']['result']
        seed = next(s for s in result['seeds'] if s['child_id'] == 34)
        index = result['seeds'].index(seed)
        counts = {}
        for first, last, checks in self.value['rows'][key]['observations']:
            for i, mask, _ in checks:
                if i == index:
                    first_mature = max(first, seed['birth_tick'] + 8 * audit.STEP)
                    n = max(0, (last - first_mature) // audit.STEP + 1)
                    if n: counts[mask] = counts.get(mask, 0) + n
        self.assertEqual(sum(counts.values()), 3884)
        self.assertEqual(counts[0], 1)
        self.assertEqual(counts[8], 671)
        self.assertTrue(all(mask == 0 or mask & 8 for mask in counts))
        self.assertTrue(all(not mask & (16 | 32) for mask in counts))
        self.assertEqual(seed['end_tick'], 979485)

    def test_changed_identity_hashes_and_provenance_are_rejected(self):
        for field in ('sources', 'source_sha256', 'receipt_sha256'):
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                audit.check_value(self.value | {field: {}})
        for field, value in (('native_runs', True), ('training_runs', 1), ('raw_manifest_sha256', 'wrong')):
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                audit.check_value(self.value | {'provenance': self.value['provenance'] | {field: value}})

    def test_releases_and_replacements_have_ledger_evidence(self):
        for key, a in self.value['analysis'].items():
            lives = {p['id']: p for p in self.panel[key]['run']['result']['lineages']}
            for r in a['releases']:
                self.assertTrue(all(lives[i]['death_tick'] < r['tick'] for i in r['ids']))
                for c, v in r['columns'].items():
                    if v['germinated']:
                        child = lives[v['germinated']['child']]
                        self.assertEqual(child['column'], int(c))
                        self.assertEqual(child['birth_tick'], v['closed_tick'])
            self.assertEqual(len(a['replacements']), len({p['life']['id'] for p in a['replacements']}))


if __name__ == '__main__': unittest.main()
