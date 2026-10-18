#!/usr/bin/env python3
"""Offline crowding timing, reflected reach and conservative missing-data bounds."""

import copy
import gzip
from itertools import combinations
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_dispersal_timing as audit

S = audit.STEP


def life(i, col, birth=0, parent=0, death=None):
    return dict(id=i, column=col, birth_tick=birth, parent=parent, death_tick=death, generation=int(parent != 0))


def seed(parent=1, birth=120, col=10, end=None, outcome='pending', child=None, lifetime=8192):
    return dict(parent=parent, birth_tick=birth, column=col, end_tick=end, outcome=outcome,
                child_id=child, lifetime_ecology_ticks=lifetime, species=0)


def make_rows(result, start):
    """Synthetic exact slot history. Dry soil keeps unblocked seeds waiting."""
    rows = []
    plants = {p['id']: p for p in result['lineages']}
    for tick in range(start + S, result['tick'] + S, S):
        # These fixtures intentionally retain dead bodies through the horizon.
        slots = [p['id'] for p in result['lineages'] if p['birth_tick'] <= tick]
        before = [i for i in slots if plants[i]['birth_tick'] < tick]
        attempts = []
        for s in result['seeds']:
            if not s['birth_tick'] < tick <= (s['end_tick'] or result['tick']):
                continue
            age = (tick - s['birth_tick']) // S
            outcome = {'expired': 1, 'germinated': 2}[s['outcome']] if s['end_tick'] == tick else 0
            blocked = any(abs(plants[i]['column'] - s['column']) < 3 for i in before)
            mask = (1 if age < 8 else 0) | (32 if blocked else 0) | (0 if outcome else 2)
            attempts.append([s['parent'], age, s['column'], 0 if outcome == 1 else mask,
                             12 if outcome == 2 else 0, 0 if outcome == 1 else 80,
                             len(before), 4 * len(before), outcome, s['child_id'] if outcome == 2 else 0,
                             -1 if outcome == 1 else 1 if outcome == 2 else 0])
            if outcome == 2:
                before.append(s['child_id'])
        purchased = {s['parent'] for s in result['seeds'] if s['birth_tick'] == tick}
        visits = [[i] + [0] * 13 + [i in purchased] for i in slots]
        rows.append([tick, [0, 0], False, 0, slots, attempts, visits, [], {}])
    return rows


def fixture():
    result = dict(tick=270, lineages=[life(1, 5), life(2, 12), life(3, 0)], seeds=[seed()])
    return result, make_rows(result, 105), {'post': 105, 'late': 180}


def prior(result, rows, periods):
    return dict(windows={label: dict(seed_window=audit.previous.germination.seed_window(
        result, [dict(tick=r[0], seeds=r[5]) for r in rows if r[0] > start], start, result['tick']))
        for label, start in periods.items()})


class BoundTests(unittest.TestCase):
    def test_all_origins_traits_and_reflection_aliases(self):
        self.assertEqual(audit.support(0, -2), [3, 3, 4, 4, 5, 5])
        self.assertEqual(audit.support(27, -2), [24, 24, 23, 23, 22, 22])
        for origin in range(28):
            for trait in audit.TRAITS:
                expected = []
                for distance in range(5 + trait, 8 + trait):
                    for direction in (-1, 1):
                        landed = origin + direction * distance
                        expected.append(landed if 0 <= landed < 28 else origin - direction * distance)
                self.assertEqual(audit.support(origin, trait), expected)

    def test_landing_ambiguity_and_policy_constraint_are_separate(self):
        result, rows, periods = fixture()
        records = audit.extract(result, rows, periods)
        ts = audit.constrained_traits(result, records)
        self.assertEqual(ts['landing_only'][1], [-2, -1, 0])
        self.assertEqual(ts['with_policy'][1], [0])
        self.assertEqual(result['seeds'][0]['column'], 10)

    def test_trait_is_constant_but_not_inferred_from_child_genome(self):
        result, _, _ = fixture()
        result['seeds'].append(seed(birth=60, col=12, end=90, outcome='expired', lifetime=2))
        self.assertEqual(audit.landing_traits(result)[1], [0])
        result['seeds'].append(seed(birth=0, col=27))
        with self.assertRaises(RuntimeError):
            audit.landing_traits(result)

    def test_contradictory_policy_does_not_silently_select_a_trait(self):
        result, _, periods = fixture()
        result['lineages'].pop()  # Every compatible trait now has at least one clear legal choice.
        records = audit.extract(result, make_rows(result, 105), periods)
        with self.assertRaises(RuntimeError):
            audit.constrained_traits(result, records)

    def test_cardinality_bounds_match_exhaustive_unknown_site_sets(self):
        universe = set(range(6))
        families = [[{0, 1, 2}], [{0, 3, 4}], [{0, 1, 2}, {0, 3, 4}]]
        for bits in range(64):
            clear = {i for i in universe if bits & (1 << i)}
            for actual_open in (False, True):
                if actual_open and 0 not in clear:
                    continue
                mask = 0 if actual_open else 2 if 0 in clear else 32
                for count in range(len(clear) + 1):
                    possible = [set(s) for s in combinations(sorted(clear), count) if (0 in s) == actual_open]
                    if not possible:
                        with self.assertRaises(RuntimeError):
                            audit.intersection_bounds(clear, families[0], 0, mask, count)
                        continue
                    for supports in families:
                        actual = [len(s & r) for s in possible for r in supports]
                        result = audit.intersection_bounds(clear, supports, 0, mask, count)
                        self.assertEqual((result['minimum'], result['maximum']), (min(actual), max(actual)))

    def test_all_four_reach_classes_and_invalid_known_site_counts(self):
        choices = [{0, 1}]
        cases = (({2, 3}, 32, 0, 'no_global_open'), ({2, 3}, 32, 1, 'definitely_unreachable'),
                 ({1, 2}, 32, 2, 'definitely_reachable'), ({1, 2}, 32, 1, 'unresolved'))
        for clear, mask, opened, name in cases:
            self.assertEqual(audit.intersection_bounds(clear, choices, 0, mask, opened)['category'], name)
        for clear, mask, opened in (({0}, 0, 0), ({0}, 2, 1), ({0}, 32, 1), ({1}, 0, 1)):
            with self.assertRaises(RuntimeError):
                audit.intersection_bounds(clear, choices, 0, mask, opened)


class TimingTests(unittest.TestCase):
    def test_purchase_and_first_mature_check_are_distinct(self):
        result, rows, periods = fixture()
        saved = copy.deepcopy((result, rows))
        with patch('subprocess.Popen', side_effect=AssertionError('native process forbidden')):
            records = audit.extract(result, rows, periods)
            value = audit.analyze(result, records, prior(result, rows, periods), periods)
        self.assertEqual(records[0]['first_mature'], [240, [2]])
        self.assertEqual(records[0]['spacing_runs'], [[135, 270, [2]]])
        self.assertEqual(value['seeds'][0]['timing']['category'], 'blocked_at_purchase')
        self.assertEqual(value['summary']['post']['purchase_blocked_with_space_elsewhere'], 1)
        self.assertEqual((result, rows), saved)

    def test_retained_dead_occupant_is_not_dropped_from_spacing(self):
        result, _, periods = fixture()
        result['lineages'][1]['death_tick'] = 150
        rows = make_rows(result, 105)
        records = audit.extract(result, rows, periods)
        self.assertEqual(records[0]['spacing_runs'], [[135, 270, [2]]])
        rows[-1][5][0][3] &= ~32
        with self.assertRaises(RuntimeError):
            audit.extract(result, rows, periods)

    def test_later_sibling_and_other_parent_germination(self):
        for sibling in (False, True):
            parent = 1 if sibling else 2
            result = dict(tick=270, lineages=[life(1, 5), life(2, 20), life(3, 12, 180, parent)],
                          seeds=[seed(), seed(parent, 60, 12, 180, 'germinated', 3)])
            rows, periods = make_rows(result, 105), {'post': 105, 'late': 180}
            records = audit.extract(result, rows, periods)
            value = audit.analyze(result, records, prior(result, rows, periods), periods)
            t = value['seeds'][0]['timing']
            self.assertEqual(t['category'], 'clear_then_blocked')
            # Seed 1 was checked before the other seed germinated at tick 180.
            self.assertEqual(t['first_blocked'], 195)
            self.assertEqual(t['newcomers'], [dict(id=3, birth_tick=180, sibling=sibling)])
            germ_row = next(r for r in rows if r[0] == 180)
            germ_row[5].reverse()
            with self.assertRaises(RuntimeError):
                audit.extract(result, rows, periods)

    def test_expiry_is_not_a_spacing_check_and_purchase_at_end_is_unobserved(self):
        result, _, periods = fixture()
        result['seeds'][0].update(end_tick=240, outcome='expired', lifetime_ecology_ticks=8)
        result['seeds'].append(seed(birth=270))
        rows = make_rows(result, 105)
        records = audit.extract(result, rows, periods)
        value = audit.analyze(result, records, prior(result, rows, periods), periods)
        self.assertEqual(records[0]['spacing_runs'], [[135, 225, [2]]])
        self.assertIsNone(records[0]['first_mature'])
        self.assertEqual(records[0]['expiry_samples'], 1)
        self.assertEqual(records[1]['samples'], 0)
        self.assertEqual(value['seeds'][1]['timing']['category'], 'blocked_at_purchase')
        # For a clear last-tick purchase, no follow-up is not a success.
        result['lineages'] = [life(1, 5)]
        rows = make_rows(result, 105)
        records = audit.extract(result, rows, periods)
        value = audit.analyze(result, records, prior(result, rows, periods), periods)
        self.assertEqual(value['seeds'][1]['timing']['category'], 'no_followup')

    def test_carry_in_is_not_treated_as_purchase_observation(self):
        result, rows, _ = fixture()
        periods = {'post': 120, 'late': 180}
        rows = rows[1:]
        records = audit.extract(result, rows, periods)
        value = audit.analyze(result, records, prior(result, rows, periods), periods)
        self.assertIsNone(records[0]['purchase'])
        self.assertEqual(value['seeds'][0]['timing']['category'], 'purchase_precedes_excerpt')

    def test_missing_duplicate_clock_slot_and_spacing_corruption_fail(self):
        faults = {
            'clock': lambda rows: rows[0].__setitem__(0, 135),
            'missing': lambda rows: rows.pop(),
            'duplicate slot': lambda rows: rows[0][4].append(1),
            'missing occupant': lambda rows: rows[1][4].remove(2),
            'missing check': lambda rows: rows[1][5].clear(),
            'duplicate check': lambda rows: rows[1][5].append(copy.deepcopy(rows[1][5][0])),
            'spacing': lambda rows: rows[1][5][0].__setitem__(3, 3),
            'pool count': lambda rows: rows[1][5][0].__setitem__(6, 2),
            'purchase': lambda rows: rows[0][6][0].__setitem__(-1, False),
        }
        for label, mutate in faults.items():
            result, rows, periods = fixture()
            mutate(rows)
            with self.subTest(label=label), self.assertRaises(RuntimeError):
                audit.extract(result, rows, periods)

    def test_compact_evidence_rejects_gaps_and_changed_counts(self):
        result, rows, periods = fixture()
        old = prior(result, rows, periods)
        records = audit.extract(result, rows, periods)
        for fault in ('missing', 'run_gap', 'first_mature', 'count', 'purchase'):
            bad = copy.deepcopy(records)
            if fault == 'missing': bad.clear()
            elif fault == 'run_gap': bad[0]['spacing_runs'][0][0] += S
            elif fault == 'first_mature': bad[0]['first_mature'][0] += S
            elif fault == 'count': bad[0]['contexts']['post'][0][-1] += 1
            else: bad[0]['purchase']['blockers'] = []
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                audit.analyze(result, bad, old, periods)

    def test_cli_does_not_clobber_or_launch_native_code(self):
        with tempfile.TemporaryDirectory() as directory, patch('subprocess.Popen',
                side_effect=AssertionError('native process forbidden')):
            path = Path(directory) / 'keep.gz'
            audit.write_gzip(path, {'keep': True})
            before = path.read_bytes()
            with self.assertRaises(RuntimeError):
                audit.main(['--out', str(path)])
            self.assertEqual(path.read_bytes(), before)
            for jobs in (0, 5, True):
                with self.assertRaises(RuntimeError):
                    audit.calculate(jobs)


class FrozenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = audit.ROOT / 'benchmarks/garden-seasons/landing-dispersal-timing-results.json.gz'
        with gzip.open(cls.path, 'rt') as stream:
            cls.value = json.load(stream)

    def test_all_worlds_rederive_offline_and_match_pinned_identity(self):
        self.assertEqual(audit.digest(self.path), '5873783662a03884d5fb0cca1a6c41b36fcb1a3dba35a458838b40755111aa6a')
        with patch('subprocess.Popen', side_effect=AssertionError('native process forbidden')):
            audit.check_value(self.value)
        self.assertEqual(len(self.value['worlds']), 32)
        self.assertEqual((self.value['native_runs'], self.value['training_runs']), (0, 0))

    def test_all_late_cap_purchases_and_mature_checks_were_already_blocked(self):
        for w in self.value['worlds']:
            if w['arm'] not in ('cap', 'cap-wick'):
                continue
            s = w['analysis']['summary']['late32']
            self.assertEqual(s['purchase_timing'], {'blocked_at_purchase': 8})
            self.assertEqual(s['mature_by_purchase_timing'], {'blocked_at_purchase': s['mature_checks']})
            if w['arm'] == 'cap':
                self.assertEqual(s['purchase_global_spacing_closed'], 0)
                self.assertEqual(s['purchase_blocked_with_space_elsewhere'], 8)
            self.assertNotIn('purchase_precedes_excerpt', s['check_cohort_timing'])

    def test_all_controls_and_late_arriving_blockers_are_retained(self):
        expected = {'off': [177, 29, 50], 'on': [181, 9, 26], 'cap': [177, 13, 12], 'cap-wick': [188, 0, 8]}
        for arm, counts in expected.items():
            rows = [w['analysis']['summary']['post'] for w in self.value['worlds'] if w['arm'] == arm]
            actual = [sum(s['purchase_timing'].get(k, 0) for s in rows)
                      for k in ('blocked_at_purchase', 'clear_then_blocked', 'clear_through_observation')]
            self.assertEqual(actual, counts)

    def test_reachable_late_exception_and_unresolved_bounds_are_not_discarded(self):
        w = next(w for w in self.value['worlds'] if w['id'] == 'f7ee4528-fixed-candidate-control-cap-trace')
        s = next(s for s in w['analysis']['seeds'] if s['seed'] == [17, 898260])
        self.assertEqual(s['column'], 19)
        self.assertEqual(s['outcome'], 'pending')
        self.assertEqual(s['purchase']['spacing_clear'], [0, 27])
        self.assertEqual(s['purchase']['reach']['landing_only'], {'minimum': 0, 'maximum': 0})
        self.assertEqual(s['windows']['late32']['reach']['landing_only']['definitely_reachable'], 931)
        self.assertEqual(s['windows']['late32']['reach']['landing_only']['unresolved'], 375)

    def test_policy_deduction_is_separate_from_direct_landing_bounds(self):
        w = next(w for w in self.value['worlds'] if w['id'] == 'f7ee4528-fixed-control-candidate-cap-wick-trace')
        s = w['analysis']['summary']['late32']
        self.assertEqual(s['reach']['landing_only']['unresolved'], 2407)
        self.assertEqual(s['reach']['with_policy']['unresolved'], 0)
        self.assertEqual(s['reach']['with_policy']['definitely_unreachable'], 19256)
        for w in self.value['worlds']:
            for parent in w['analysis']['parents']:
                self.assertTrue(set(parent['with_policy']) <= set(parent['landing_only']))
            for period in w['analysis']['summary'].values():
                for reach in period['reach'].values():
                    self.assertEqual(sum(reach.values()), period['mature_checks'])

    def test_tampered_provenance_and_panel_fail_before_acceptance(self):
        for key, value in (('protocol_sha256', 'wrong'), ('native_runs', 1),
                           ('worlds', self.value['worlds'][:-1])):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                audit.check_value({**self.value, key: value})


if __name__ == '__main__':
    unittest.main()
