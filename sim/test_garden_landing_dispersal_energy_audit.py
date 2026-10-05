#!/usr/bin/env python3
"""Offline energy cohort, maintenance-boundary and saved-evidence regression checks."""

import copy
from fractions import Fraction
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_dispersal_energy_audit as audit

RESULT = audit.ROOT / 'benchmarks/garden-seasons/landing-dispersal-energy-audit-results.json.gz'


def life(birth=60, death=180, generation=1, i=1, parent=0, column=3):
    return dict(id=i, parent=parent, column=column, species=0, birth_tick=birth,
                death_tick=death, generation=generation)


def body(tick, nodes, roots):
    return dict(tick=tick, body=dict(nodes=nodes, roots=roots))


def shortage(tick, nodes=8, roots=2, energy=1, water=0):
    e, w = (nodes + 7) // 8, (nodes - roots + 7) // 8
    return dict(tick=tick, phase=(64 + tick // audit.STEP) % 256, nodes=nodes, roots=roots,
                energy=dict(due=e, paid=e - energy, unpaid=energy),
                water=dict(due=w, paid=w - water, unpaid=water))


def plant():
    return dict(life=life(), body_changes=[body(60, 8, 2), body(120, 9, 2)],
                shortages=[shortage(180, nodes=9)], payments=2,
                resources=dict(energy=dict(upkeep=2), water=dict(upkeep=2)))


def count(payments=0, unpaid=0):
    value = audit.empty()
    value['payments'] = payments
    value['energy'] = dict(due=payments, paid=payments - unpaid,
                           unpaid=unpaid, shortages=int(unpaid > 0))
    return value


class ContractTests(unittest.TestCase):
    def test_birth_excluded_death_included_growth_effective_next_payment(self):
        p = plant()
        audit.check_body(p)
        self.assertEqual(audit.counts(p, 0, 60), audit.empty())
        self.assertEqual(audit.counts(p, 60, 120)['energy'],
                         dict(due=1, paid=1, unpaid=0, shortages=0))
        self.assertEqual(audit.counts(p, 120, 180)['energy'],
                         dict(due=2, paid=1, unpaid=1, shortages=1))
        self.assertEqual(audit.counts(p, 180, 240), audit.empty())
        self.assertEqual(audit.counts(p)['payments'], 2)

    def test_off_cadence_birth_and_shapes_partition_without_rounding_drift(self):
        p = plant()
        p['life']['birth_tick'] = 75
        p['body_changes'][0]['tick'] = 75
        p['body_changes'][1]['tick'] = 135
        audit.check_body(p)
        self.assertEqual(audit.combine(audit.counts(p, a, b) for a, b in
                         ((0, 90), (90, 135), (135, 165), (165, 180), (180, 240))), audit.counts(p))

    def test_missing_wrong_and_late_body_history_rejected(self):
        for shapes in ([], [body(120, 8, 2)], [body(60, 8, 2), body(60, 9, 2)],
                       [body(60, 8, 2), body(180, 9, 2)]):
            with self.subTest(shapes=shapes), self.assertRaisesRegex(RuntimeError, 'body history'):
                audit.check_body(plant() | {'body_changes': shapes})
        p = plant()
        p['shortages'][0]['nodes'] = 8
        with self.assertRaisesRegex(RuntimeError, 'pre-maintenance body'): audit.check_body(p)
        p = plant()
        p['resources']['energy']['upkeep'] = 3
        with self.assertRaisesRegex(RuntimeError, 'body demand'): audit.check_body(p)

    def test_invalid_window_and_negative_payment_balance_rejected(self):
        for start, end in ((-1, 0), (120, 60), (0, audit.STOP + 1)):
            with self.assertRaisesRegex(RuntimeError, 'account window'): audit.counts(plant(), start, end)
        p = plant()
        p['shortages'][0]['energy']['unpaid'] = 10
        with self.assertRaisesRegex(RuntimeError, 'exceeds'): audit.counts(p)

    def test_cohort_exact_death_boundaries_and_censoring(self):
        born, day = audit.AFTER + 15, audit.DAY
        cases = [(life(generation=0), 'founder'),
                 (life(birth=audit.AFTER, death=audit.AFTER), 'prior_dead'),
                 (life(birth=audit.AFTER, death=None), 'incumbent'),
                 (life(birth=born, death=born + day), 'died_by_day1'),
                 (life(birth=born, death=born + day + 60), 'died_day1_to32'),
                 (life(birth=born, death=born + 32 * day), 'died_day1_to32'),
                 (life(birth=born, death=born + 32 * day + 60), 'confirmed32'),
                 (life(birth=audit.STOP - day + 15, death=None), 'pending_day1'),
                 (life(birth=audit.STOP - day, death=None), 'pending_day32'),
                 (life(birth=audit.STOP - 32 * day, death=None), 'confirmed32')]
        for p, expected in cases:
            with self.subTest(life=p): self.assertEqual(audit.cohort(p), expected)

    def test_identity_matching_requires_ancestry_not_numeric_id(self):
        a = {'lineages': [life(0, None, 0, 1, 0, 3), life(60, None, 1, 2, 1, 8)]}
        b = {'lineages': [life(0, None, 0, 7, 0, 3), life(60, None, 1, 1, 7, 8)]}
        self.assertEqual(audit.population.matched_births(a, b)['matched'], [[1, 7], [2, 1]])
        b['lineages'][1]['column'] = 9
        self.assertEqual(audit.population.matched_births(a, b)['control_only'], [2])

    def test_rate_decomposition_preserves_changed_denominators(self):
        groups = {a: {g: count() for g in audit.GROUPS} for a in audit.SIDES}
        groups['control']['incumbent_common'] = count(100, 10)
        groups['candidate']['incumbent_common'] = count(100, 12)
        groups['candidate']['unmatched_recruit'] = count(100, 0)
        d = audit.decompose(groups)
        self.assertEqual(d['change']['energy'], [-1, 25])
        self.assertEqual(sum(Fraction(*v) for v in d['contributions']['energy'].values()), Fraction(-1, 25))
        self.assertGreater(Fraction(*audit.rates(groups['candidate']['incumbent_common'])['energy']['per_payment']),
                           Fraction(*audit.rates(groups['control']['incumbent_common'])['energy']['per_payment']))

    def test_no_exposure_has_unavailable_rates(self):
        self.assertEqual(audit.rates(count())['energy'], dict(per_payment=None, per_due=None))
        groups = {a: {g: count() for g in audit.GROUPS} for a in audit.SIDES}
        groups['candidate']['unmatched_recruit'] = count(100)
        self.assertIsNone(audit.decompose(groups)['change']['energy'])

    def test_event_scope_age_phase_and_water_concurrence(self):
        p = plant()
        p['life'] = life(birth=audit.AFTER, death=audit.AFTER + 60)
        p['shortages'] = [shortage(audit.AFTER), shortage(audit.AFTER + 60, water=1)]
        rows = audit.events(p)
        self.assertEqual(len(rows), 1)
        summary = audit.event_summary(rows)
        self.assertEqual(summary['total'], dict(events=1, unpaid=1, water_shortage_events=1, death_events=1))
        self.assertEqual(summary['age']['below_day1'], summary['total'])
        self.assertEqual(sum(b['events'] for b in summary['phase_quarter'].values()), 1)

    def test_clobber_and_dangling_symlink_refused_before_reading_inputs(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(audit, 'inputs',
                side_effect=AssertionError('should not load inputs')):
            target = Path(directory) / 'link.gz'
            target.symlink_to(Path(directory) / 'missing.gz')
            for path in (Path(directory), target):
                with self.assertRaisesRegex(RuntimeError, 'fresh output'): audit.export(path)


@unittest.skipUnless(RESULT.exists(), 'saved energy audit not retained yet')
class CapturedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(RESULT, 'rt') as stream: cls.value = json.load(stream)
        cls.analysis = cls.value['analysis']
        with patch('subprocess.Popen', side_effect=AssertionError('unexpected process')):
            cls.worlds, cls.pairs = audit.inputs()

    def test_complete_portable_verification_with_processes_forbidden(self):
        with patch('subprocess.Popen', side_effect=AssertionError('unexpected process')), \
             patch('subprocess.run', side_effect=AssertionError('unexpected process')):
            audit.check_value(self.value)

    def test_second_export_is_byte_identical_without_processes(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch('subprocess.Popen', side_effect=AssertionError('unexpected process')):
            out = Path(directory) / 'second.gz'
            audit.export(out)
            self.assertEqual(out.read_bytes(), RESULT.read_bytes())

    def test_all_16_screens_retained_including_energy_improvements_and_parent_losses(self):
        pairs = self.analysis['pairs']
        self.assertEqual(len(pairs), 16)
        self.assertEqual(sum(p['original_screen']['unpaid_rate_comparison']['energy'] == 1 for p in pairs), 10)
        self.assertEqual(sum(p['original_screen']['passes_harm_screen'] for p in pairs), 4)
        self.assertEqual(sum(not p['original_screen']['checks']['retain_seed_parents'] for p in pairs), 2)
        self.assertTrue(all(p['original_screen']['unpaid_rate_comparison']['water'] == -1 for p in pairs))

    def test_individual_bill_iteration_independently_matches_body_segments(self):
        # Independent per-payment walk checks the interval arithmetic against
        # every retained body history, not just the saved aggregate result.
        for world in self.worlds.values():
            for p in world['analysis']['plants']:
                n, sums = 0, dict(energy=0, water=0)
                shapes = p['body_changes']
                for tick in range((p['life']['birth_tick'] // 60 + 1) * 60,
                                  audit.endpoint(p['life']) + 1, 60):
                    while n + 1 < len(shapes) and shapes[n + 1]['tick'] < tick: n += 1
                    body = shapes[n]['body']
                    sums['energy'] += (body['nodes'] + 7) // 8
                    sums['water'] += (body['nodes'] - body['roots'] + 7) // 8
                self.assertEqual(sums, {r: audit.counts(p)[r]['due'] for r in audit.RESOURCES})

    def test_cohort_totals_and_horizon_censoring_are_exhaustive(self):
        for w in self.analysis['worlds'].values():
            for period in audit.PERIODS:
                self.assertEqual(audit.combine(c[period] for name, c in w['cohorts'].items() if name != 'founder'),
                                 w['totals']['offspring'][period])
            for p in w['plants']:
                self.assertEqual(p['cohort'], audit.cohort(p['life']))
            self.assertEqual(w['events']['total']['unpaid'], w['totals']['offspring']['post']['energy']['unpaid'])

    def test_shared_history_and_equal_exposure_do_not_imply_equal_shortfalls(self):
        regressed, passing_with_regression = 0, 0
        for p in self.analysis['pairs']:
            self.assertEqual(p['groups']['control']['shared_pre'], p['groups']['candidate']['shared_pre'])
            worse = False
            for match in p['matched']:
                a, b = (match['common'][arm] for arm in audit.SIDES)
                self.assertEqual(a['payments'], b['payments'])
                for r in audit.RESOURCES: self.assertEqual(a[r]['due'], b[r]['due'])
                worse |= b['energy']['unpaid'] > a['energy']['unpaid']
            regressed += worse
            passing_with_regression += worse and p['original_screen']['passes_harm_screen']
        self.assertEqual(regressed, 10)
        self.assertEqual(passing_with_regression, 1)

    def test_most_candidate_shortfalls_are_in_confirmed_32_day_cohort(self):
        for water, unpaid, established in (('cap', 387, 274), ('cap-wick', 319, 199)):
            pooled = self.analysis['pooled'][water]
            self.assertEqual(pooled['events']['candidate']['total']['unpaid'], unpaid)
            self.assertEqual(pooled['cohorts']['candidate']['confirmed32']['post']['energy']['unpaid'], established)
            self.assertGreater(established, unpaid / 2)
            self.assertEqual(pooled['events']['candidate']['total']['water_shortage_events'], 0)

    def test_renumbered_regression_and_clean_incumbent_witness_retained(self):
        selected = [p for p in self.analysis['pairs'] if p['case']['id'] == 'f7ee4528-fixed-candidate'
                    and p['allocator'] == 'candidate']
        cap, wick = selected
        m = next(m for m in cap['matched'] if m['ids'] == [20, 20])
        self.assertEqual([m['common'][a]['energy']['unpaid'] for a in audit.SIDES], [0, 9])
        self.assertEqual(m['end'], audit.STOP)
        n = next(m for m in wick['matched'] if m['ids'] == [28, 29])
        self.assertEqual([n['common'][a]['energy']['unpaid'] for a in audit.SIDES], [0, 34])

    def test_tampered_provenance_trace_sources_and_analysis_rejected(self):
        for key, v in (('native_runs', True), ('training_runs', 1), ('inputs', {}), ('protocol_sha256', '0' * 64)):
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, 'provenance/scope'):
                audit.check_value(self.value | {'provenance': self.value['provenance'] | {key: v}})
        with self.assertRaisesRegex(RuntimeError, 'source receipt'):
            audit.check_value(self.value | {'source_sha256': {}})
        with self.assertRaisesRegex(RuntimeError, 'trace coverage'):
            audit.check_value(self.value | {'traces': {}})
        # Derive once; the independent complete-verification test exercises the
        # full computation, while these focus on rejection of corrupted fields.
        with patch.object(audit, 'analyze', return_value=self.analysis):
            for change in ('count', 'coverage', 'event'):
                bad = copy.deepcopy(self.analysis)
                if change == 'count': bad['pairs'][0]['groups']['control']['shared_pre']['payments'] += 1
                elif change == 'coverage': bad['pairs'].pop()
                else:
                    world = next(w for w in bad['worlds'].values() if w['events']['total']['events'])
                    plant = next(p for p in world['plants'] if p['energy_events'])
                    plant['energy_events'][0]['energy']['unpaid'] += 1
                with self.subTest(change=change), self.assertRaisesRegex(RuntimeError, 'analysis differs'):
                    audit.check_value(self.value | {'analysis': bad})


if __name__ == '__main__':
    unittest.main()
