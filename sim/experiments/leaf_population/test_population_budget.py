"""Fixed windows, stage accounting, and conservative repair attribution."""

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import population_budget as budget


def fixture(repair=True):
    rows, openings = [], []
    for tick in budget.TICKS:
        maintenance = tick % 60 == 0
        visit = dict(blockers=128 if tick in budget.EVENTS else 132,
                     seed_count=7 if tick in budget.EVENTS else 8,
                     energy_required=208, water_required=184) if maintenance else None
        row = dict(tick=tick, maintenance=maintenance, nodes_before=32, nodes_after=32,
                   leaves_before=27, leaves_after=27, condition_before=100, condition_after=100,
                   condition_endowment=0, worn=int(repair), restored=int(repair),
                   observations=1, proposals=int(repair), renewals=int(repair),
                   stress_before=0, stress_after=0, remainder_before=0, remainder_uptake=0,
                   remainder_after=0, remainder_discarded=0, visit=visit)
        for name, stored, cost in (('energy', 200, 9), ('water', 400, 5)):
            paid = cost * int(repair)
            flux = dict.fromkeys(budget.FLUX, 0)
            flux.update(before=stored, after=stored, income=paid, repair=paid,
                        points=[stored, stored + paid, stored + paid, stored + paid, stored, stored])
            row[name] = flux
        rows.append(row)
        if tick in budget.EVENTS:
            openings.append(dict(tick=tick, visits=[dict(lineage=17, energy=200, water=400, **visit)]))
    data = dict(schema='garden-reproduction-budget-v1', complete=True, lineage=17,
                before_ticks=budget.BEFORE, after_ticks=budget.AFTER, limit=2560,
                events=list(budget.EVENTS), rows=rows)
    reproduction = dict(openings=openings, lineages=[dict(lineage=17, masks=dict(
        Counter(str(r['visit']['blockers']) for r in rows if r['maintenance'])))])
    daily = []
    for day in sorted({(r['tick'] - 1) // budget.score.DAY for r in rows}):
        selected = [r for r in rows if day * budget.score.DAY < r['tick'] <= (day + 1) * budget.score.DAY]
        if len(selected) == 256:
            # Independent expectations for this constant-reserve synthetic trace.
            values = {}
            for name, stored, cost in (('energy', 200, 9), ('water', 400, 5)):
                values[name] = dict.fromkeys(budget.FLUX, 0)
                values[name].update(before=stored, after=stored, income=256 * cost * int(repair),
                                    repair=256 * cost * int(repair))
            daily.append(dict(day=day, lineage=17, **values))
    return data, reproduction, dict(plant_days=daily)


class BudgetTests(unittest.TestCase):
    def test_two_call_scope_and_deduplicated_windows(self):
        calls = budget.roster()
        self.assertEqual([budget.arguments(c) for c in calls], [
            ['--budget-panel', '9a903368', 'condition', 'fewest', m] for m in ('off', 'on')])
        self.assertEqual(len({c['id'] for c in calls}), 2)
        self.assertEqual((len(budget.TICKS), budget.TICKS[0], budget.TICKS[-1]), (2244, 583215, 868380))
        self.assertEqual(len(set(budget.TICKS)), len(budget.TICKS))
        for event in budget.EVENTS:
            self.assertEqual(sum(event - budget.BEFORE < t <= event for t in budget.TICKS), 256)
            self.assertEqual(sum(event < t <= event + budget.AFTER for t in budget.TICKS), 64)

    def test_stage_balances_and_immediate_payment_point_calculation(self):
        result = budget.validate_trace(*fixture())
        self.assertEqual((result['records'], result['joined_openings']), (2244, 8))
        self.assertTrue(result['complete_calendar_days'])
        for event in result['events']:
            self.assertEqual(event['deficit'], dict(energy=8, water=0))
            self.assertEqual(event['immediate_repair_addback'], dict(energy=209, water=405))
            self.assertTrue(event['immediate_addback_meets_resource_thresholds'])
            self.assertEqual(event['preceding_day']['energy']['repair'], 2304)
            self.assertEqual(event['following_quarter_day']['water']['repair'], 320)
            self.assertEqual(event['last_observed_cap_tick'], dict(energy=None, water=None))
            self.assertIsNone(event['first_following_resource_funded_visit'])
        no_repair = budget.validate_trace(*fixture(repair=False))
        self.assertTrue(all(not e['immediate_addback_meets_resource_thresholds'] for e in no_repair['events']))

    def test_missing_duplicate_and_wrong_event_coverage_rejected(self):
        data, reproduction, resources = fixture()
        for rows in (data['rows'][:-1], data['rows'] + [data['rows'][-1]], data['rows'][1:]):
            with self.assertRaisesRegex(ValueError, 'coverage'):
                budget.validate_trace(data | dict(rows=rows), reproduction, resources)
        broken = deepcopy(reproduction)
        broken['openings'].pop()
        with self.assertRaisesRegex(ValueError, 'event selection'):
            budget.validate_trace(data, broken, resources)

    def test_payment_points_and_flux_cannot_disagree(self):
        for field in ('income', 'overflow', 'repair', 'upkeep_paid', 'growth', 'seeds', 'after'):
            data, reproduction, resources = fixture()
            data['rows'][0]['energy'][field] += 1
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'payment stages'):
                budget.validate_trace(data, reproduction, resources)
        for point in range(6):
            data, reproduction, resources = fixture()
            data['rows'][0]['water']['points'][point] -= 1
            with self.subTest(point=point), self.assertRaisesRegex(ValueError, 'payment stages'):
                budget.validate_trace(data, reproduction, resources)

    def test_continuity_leaf_condition_and_visit_cadence_rejected(self):
        data, reproduction, resources = fixture()
        broken = deepcopy(data)
        row = broken['rows'][1]['energy']
        row['before'] += 1
        row['after'] += 1
        row['points'] = [v + 1 for v in row['points']]
        with self.assertRaisesRegex(ValueError, 'resource continuity'):
            budget.validate_trace(broken, reproduction, resources)
        for fields in (dict(condition_after=101), dict(renewals=2), dict(remainder_after=1),
                       dict(visit={}), dict(maintenance=True)):
            broken = deepcopy(data)
            broken['rows'][0].update(fields)
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                budget.validate_trace(broken, reproduction, resources)

    def test_old_receipts_histogram_and_daily_ledger_cross_checks(self):
        data, reproduction, resources = fixture()
        broken = deepcopy(reproduction)
        broken['openings'][0]['visits'][0]['energy'] -= 1
        with self.assertRaisesRegex(ValueError, 'opening receipt'):
            budget.validate_trace(data, broken, resources)
        broken = deepcopy(reproduction)
        broken['lineages'][0]['masks']['128'] -= 1
        with self.assertRaisesRegex(ValueError, 'visit subset'):
            budget.validate_trace(data, broken, resources)
        broken = deepcopy(resources)
        broken['plant_days'][0]['energy']['repair'] -= 1
        with self.assertRaisesRegex(ValueError, 'daily budget'):
            budget.validate_trace(data, reproduction, broken)

    def test_repair_addback_does_not_remove_other_blockers(self):
        data, reproduction, resources = fixture()
        row = next(r for r in data['rows'] if r['tick'] == budget.EVENTS[0] + 60)
        # A lower threshold makes resources sufficient here, but the bank stays full.
        row['visit'].update(energy_required=190, blockers=4)
        reproduction['lineages'][0]['masks']['4'] = 1
        result = budget.validate_trace(data, reproduction, resources)
        funded = result['events'][0]['first_following_resource_funded_visit']
        self.assertEqual(funded['tick'], budget.EVENTS[0] + 60)
        self.assertEqual(funded['visit']['blockers'], 4)


class PublishedBudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='published-budget-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.out = cls.root / 'evidence'
        cls.archive = budget.collect.ROOT / 'benchmarks/garden-seasons/leaf-population-budget-results.json.gz'
        assert budget.prepare.sha(cls.archive.read_bytes()) == 'ab314a17361fe939525f61c6d340fc45d9a0058f0fb0fdc9c770f432709728ed'
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native calls forbidden')):
            cls.result = budget.follow.unpack(cls.archive, cls.out, experiment=budget.EXPERIMENT)

    def test_complete_trace_and_payment_point_misses(self):
        result = self.result['analyses']
        self.assertEqual(self.result['calls'], 2)
        self.assertEqual((result['records'], result['joined_openings']), (2244, 15))
        self.assertEqual(result['complete_calendar_days'], [152, 161, 184, 193, 225])
        events = result['events']
        self.assertEqual([e['deficit'] for e in events], [dict(energy=e, water=w) for e, w in
            ((40, 0), (21, 0), (36, 0), (164, 0), (158, 0), (20, 0), (0, 71), (16, 0))])
        self.assertEqual([e['opening']['energy']['repair'] for e in events], [0, 0, 0, 9, 0, 0, 9, 0])
        self.assertTrue(all(not e['immediate_addback_meets_resource_thresholds'] for e in events))
        self.assertEqual([e['first_following_resource_funded_visit']['tick'] - e['tick'] for e in events],
                         [120, 60, 60, 480, 420, 60, 180, 60])
        self.assertTrue(all(e['first_following_resource_funded_visit']['visit']['blockers'] == 4 for e in events))

    def test_caps_and_low_income_preclude_simple_repair_attribution(self):
        events = self.result['analyses']['events']
        for i in (0, 1, 2, 5, 7):
            event = events[i]
            self.assertIsNotNone(event['last_observed_cap_tick']['energy'])
            self.assertEqual(event['repair_since_last_observed_cap']['energy'], 0)
            self.assertGreater(event['preceding_day']['energy']['overflow'], 0)
        for i, income in ((3, 196), (4, 223)):
            self.assertEqual(events[i]['preceding_day']['energy']['income'], income)
            self.assertEqual(events[i]['preceding_day']['energy']['upkeep_due'], 256)
            self.assertEqual(events[i]['preceding_day']['energy']['upkeep_paid'], 232)
        self.assertEqual(events[6]['preceding_day']['water']['income'], 101)
        path = self.out / 'runs/9a903368-condition-fewest-on/timeline/budget.json'
        rows = json.loads(path.read_bytes())['rows']
        self.assertEqual({(r['nodes_before'], r['nodes_after'], r['leaves_before'], r['leaves_after'])
                          for r in rows}, {(32, 32, 26, 26)})
        self.assertTrue(all(r[k]['growth'] == r[k]['seeds'] == 0 for r in rows for k in ('energy', 'water')))

    def test_exact_archive_roundtrip_without_simulator(self):
        target = self.root / 'repacked.gz'
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native calls forbidden')):
            budget.follow.package(self.out, target, experiment=budget.EXPERIMENT)
        self.assertEqual(target.read_bytes(), self.archive.read_bytes())


if __name__ == '__main__':
    unittest.main()
