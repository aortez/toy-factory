"""Synthetic and archived scoring checks; never invoke a native simulator."""

import copy
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run_durability as experiment

scoring, DAY = experiment.scoring, experiment.pilot.DAY


def history(entries, days=1376):
    plants, seeds, roots, causes = [], [], [], []
    for identity, parent, birth, death in entries:
        generation = plants[parent - 1]['generation'] + 1 if parent else 0
        plants.append(dict(id=identity, parent=parent, birth_tick=int(birth * DAY),
            death_tick=None if death is None else int(death * DAY), environmental_death=False,
            generation=generation, species=0, column=identity, seeds_created=0, late_seeds_created=0))
        causes.append(4 if death is None else 0)
        roots.append(roots[parent - 1] if parent else identity)
        if parent:
            seeds.append(dict(parent=parent, birth_tick=int((birth - 1) * DAY), end_tick=int(birth * DAY),
                child_id=identity, lifetime_ecology_ticks=8192, generation=generation, species=0,
                column=identity, outcome='germinated'))
            plants[parent - 1]['seeds_created'] += 1
            plants[parent - 1]['late_seeds_created'] += 1
    return dict(complete=True, ledger_start_tick=0, ticks=days * DAY, seed='58d7d6ca', scenario='rainfed',
                candidate_founder=1, lineages=plants, seeds=seeds, family_roots=roots, death_causes=causes)


class PlanTests(unittest.TestCase):
    def test_roster(self):
        calls = experiment.plan()
        self.assertEqual(len(calls), 123)
        self.assertEqual([c['id'] for c in calls], [f'call{i:04d}' for i in range(1, 124)])
        self.assertEqual([sum(c['phase'] == p for c in calls) for p in ('anchor', 'panel', 'confirm')], [3, 96, 24])
        self.assertEqual({c['days'] for c in calls[:3]}, {608})
        self.assertEqual({c['days'] for c in calls[3:]}, {1376})
        self.assertTrue(all(not c['capture'] and c['founder'] == 1 for c in calls[99:]))
        self.assertEqual(experiment.build.TICKS, 5283840)

    def test_exact_archive_early_scores(self):
        self.assertEqual(experiment.preflight_scores()['exact_archived_early_scores'], 96)

    def test_exact_archive_aggregates(self):
        calls = experiment.plan()[3:99]
        values = {c['id']: json.loads(experiment.archived(f"runs/{c['id']}/stdout.json")) for c in calls}
        for name in experiment.MODELS:
            selected = [values[c['id']] for c in calls if c['model'] == name]
            actual = scoring.panel(selected, 192)
            old = experiment.archive()['summary']['analysis']['models'][name]
            self.assertEqual(actual['key'], old['score']['key'])
            self.assertEqual(actual['extinct_families'], old['extinct_families'])
            self.assertEqual(actual['weighted_extinction'], old['weighted_extinction'])
            self.assertEqual(actual['closing_window_families'], old['closing_window_families'])

    def test_missing_roles_rejected(self):
        with self.assertRaisesRegex(ValueError, 'incomplete panel'):
            experiment.analyze({})
        with self.assertRaisesRegex(ValueError, 'scoring roster'):
            scoring.panel([], 960)


class ScoreTests(unittest.TestCase):
    def test_late_window_boundaries_and_no_mutation(self):
        value = history([(1, 0, 0, None), (2, 1, 900, None), (3, 2, 960, None),
                         (4, 2, 961, None), (5, 2, 1024, None), (6, 2, 1344, None), (7, 2, 1345, None)])
        before = copy.deepcopy(value)
        result = scoring.score(value, 1, 960)
        self.assertEqual(result['renewal_children'], [2, 0, 0, 0, 0, 1])
        self.assertEqual(Fraction(*result['key'][0]), Fraction(1, 4))
        self.assertEqual(value, before)

    def test_window_cap(self):
        value = history([(1, 0, 0, None), (2, 1, 900, None), (3, 2, 961, None),
                         (4, 2, 970, None), (5, 2, 980, None)])
        result = scoring.score(value, 1, 960)
        self.assertEqual(result['renewal_children'], [3, 0, 0, 0, 0, 0])
        self.assertEqual(Fraction(*result['key'][0]), Fraction(1, 6))

    def test_survival_is_strict_at_32_days(self):
        value = history([(1, 0, 0, None), (2, 1, 900, None), (3, 2, 970, 1002)])
        self.assertEqual(scoring.score(value, 1, 960)['key'][0], [0, 1])
        value['lineages'][2]['death_tick'] += 15
        self.assertEqual(scoring.score(value, 1, 960)['key'][0], [1, 12])
        value['lineages'][1]['death_tick'] = 931 * DAY
        with self.assertRaisesRegex(RuntimeError, 'living parent'):
            scoring.score(value, 1, 960)  # Seed purchase cannot happen after the parent's death.

    def test_unestablished_parent_no_credit(self):
        value = history([(1, 0, 0, None), (2, 1, 950, 981), (3, 2, 970, None)])
        self.assertEqual(scoring.score(value, 1, 960)['key'][0], [0, 1])

    def test_first_generation_and_exact_occupancy(self):
        value = history([(1, 0, 0, None), (2, 1, 940, None), (3, 2, 1344, None)])
        result = scoring.score(value, 1, 960)
        self.assertEqual(result['established_descendant_ticks'], 372 * DAY + 1)
        self.assertEqual(result['key'][0], [1, 12])
        value = history([(1, 0, 0, None), (2, 1, 1000, None)])
        self.assertEqual(scoring.score(value, 1, 960)['key'][0], [0, 1])
        self.assertGreater(Fraction(*scoring.score(value, 1, 960)['key'][1]), 0)

    def test_prefix_includes_cutoff_censors_future_and_counts(self):
        value = history([(1, 0, 0, 608), (2, 1, 610, None)])
        value['seeds'][0]['birth_tick'] = 607 * DAY
        prefix = scoring.prefix(value, 608)
        self.assertEqual(len(prefix['lineages']), 1)
        self.assertEqual(prefix['death_causes'], [0])
        self.assertEqual(prefix['seeds'][0]['outcome'], 'pending')
        self.assertIsNone(prefix['seeds'][0]['child_id'])
        self.assertEqual(prefix['lineages'][0]['seeds_created'], 1)
        self.assertTrue(experiment.previous.family_status(prefix)['dormant'])
        value['lineages'][0]['death_tick'] += 15
        prefix = scoring.prefix(value, 608)
        self.assertIsNone(prefix['lineages'][0]['death_tick'])
        self.assertEqual(prefix['death_causes'], [4])
        self.assertNotIn('state_hex', prefix)

    def test_boundary_birth_preserved(self):
        value = history([(1, 0, 0, None), (2, 1, 608, None)])
        prefix = scoring.prefix(value, 608)
        self.assertEqual(len(prefix['lineages']), 2)
        self.assertEqual(prefix['seeds'][0]['outcome'], 'germinated')
        self.assertEqual(prefix['family_roots'], [1, 1])

    def test_family_isolation(self):
        value = history([(1, 0, 0, None), (2, 0, 0, None), (3, 2, 900, None), (4, 3, 1000, None)])
        self.assertEqual(scoring.score(value, 1, 960)['key'], [[0, 1], [0, 1]])
        self.assertEqual(scoring.score(value, 2, 960)['key'][0], [1, 12])

    def test_invalid_horizon_roots_and_capacity(self):
        value = history([(1, 0, 0, None)])
        for start in (-1, True, 608, 1376):
            with self.assertRaises(ValueError):
                scoring.score(value, 1, start)
        with self.assertRaises(ValueError):
            scoring.score(value | dict(ticks=value['ticks'] - 15), 1, 960)
        with self.assertRaises(ValueError):
            scoring.score(value | dict(family_roots=[2]), 1, 960)
        crowded = history([(i, 0, 0, None) for i in range(1, 10)])
        with self.assertRaises(ValueError):
            scoring.score(crowded, 1, 960)


class RunnerTests(unittest.TestCase):
    def test_failed_batch_stops(self):
        submitted = []
        def execute(call):
            raise ValueError('failed call')
        with self.assertRaises(ValueError):
            experiment.previous.batches([dict(id=i) for i in range(8)], submitted.append,
                                         execute, lambda c, v: None)
        self.assertEqual(submitted, [dict(id=0), dict(id=1)])

    def test_invalid_batch_stops(self):
        submitted = []
        def validate(call, value):
            raise ValueError('invalid output')
        with self.assertRaises(ValueError):
            experiment.previous.batches([dict(id=i) for i in range(8)], submitted.append,
                                         lambda c: c, validate)
        self.assertEqual(submitted, [dict(id=0), dict(id=1)])

    def test_validation_precedes_next_batch(self):
        events = []
        experiment.previous.batches([dict(id=i) for i in range(4)], lambda c: events.append('submit'),
                                     lambda c: c, lambda c, v: events.append('check'))
        self.assertEqual(events, ['submit', 'submit', 'check', 'check'] * 2)

    def test_limits(self):
        with tempfile.TemporaryDirectory(prefix='leaf-durability-limits-') as temporary:
            limits = experiment.Limits(Path(temporary), clock=lambda: 1.0)
            limits.count = 123
            with self.assertRaises(ValueError):
                limits.submit()
            limits.count, limits.first = 0, -5399.0
            with self.assertRaises(ValueError):
                limits.submit()
            limits.first = None
            with patch.object(limits, 'size', return_value=experiment.MAX_BYTES):
                with self.assertRaises(ValueError):
                    limits.submit()
            with patch.object(experiment.shutil, 'disk_usage') as disk:
                disk.return_value.free = 0
                with self.assertRaises(ValueError):
                    limits.submit()


if __name__ == '__main__':
    unittest.main()
