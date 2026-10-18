"""Exact per-leaf uptake, wear timing, and unchanged matched replay evidence."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import population_foliage as foliage


def fixture(policy='original'):
    lineage, count = foliage.TARGETS[policy]
    conditions = [200 + i for i in range(count)]
    stored, remainder = 210, 254
    rows, openings = [], []
    for index, tick in enumerate(foliage.TICKS):
        maintenance = tick % 60 == 0
        before = sum(conditions)
        worn = sum(c > 0 for c in conditions) if maintenance else 0
        conditions = [max(0, c - int(maintenance)) for c in conditions]
        # Global node compaction is harmless; body order and position are not.
        base = 8 if index < 128 else 0
        leaves = [[base + i, 8 + 8 * i, 32, i, 0, 96, c] for i, c in enumerate(conditions)]
        income, next_remainder = divmod(remainder + sum(conditions), 255)
        uptake = min(256, stored + income)
        upkeep = min(uptake, 4 if maintenance else 0)
        renew = int(index % 65 == 64)
        restored = (255 - conditions[0]) * renew
        after_repair = uptake - upkeep - 9 * renew
        seeds = 48 if index == 223 else 0
        rows.append(dict(tick=tick, phase=(tick // 15 + 64) % 256, strength=255,
            selected=base, action=renew, remainder_before=remainder,
            remainder_uptake=next_remainder, remainder_after=next_remainder,
            condition_before=before, condition_after=sum(conditions) + restored,
            worn=worn, restored=restored, renewals=renew, renewal_energy=9 * renew, renewal_water=5 * renew,
            energy=dict(before=stored, income=income, overflow=stored + income - uptake,
                upkeep_due=4 if maintenance else 0, upkeep_paid=upkeep, growth=0, seeds=seeds,
                after=after_repair - seeds,
                points=[stored, uptake, uptake - upkeep, uptake - upkeep, after_repair, after_repair - seeds]),
            leaves=leaves))
        if seeds:
            openings.append(dict(tick=tick, visits=[dict(lineage=lineage, energy=after_repair,
                energy_required=208, blockers=0, produced=True)]))
        if renew:
            conditions[0] = 255
        stored, remainder = after_repair - seeds, next_remainder
    data = dict(schema='garden-foliage-uptake-v1', complete=True, lineage=lineage,
                first_tick_exclusive=foliage.FIRST, end_tick=foliage.END, leaf_limit=32,
                leaf_fields=foliage.FIELDS, rows=rows)
    day = dict(day=152, lineage=lineage, energy=foliage.energy_total(rows), nodes_before=32, nodes_after=32,
        leaves_before=count, leaves_after=count, samples=256, observations=256, condition_endowment=0,
        condition_before=rows[0]['condition_before'], condition_after=rows[-1]['condition_after'],
        **{k: sum(r[k] for r in rows) for k in ('worn', 'restored', 'renewals')})
    return data, dict(openings=openings), dict(plant_days=[day]), policy


class FoliageTests(unittest.TestCase):
    def test_fixed_four_run_scope_and_dawn_window(self):
        self.assertEqual([foliage.arguments(c) for c in foliage.roster()], [
            ['--foliage-panel', '9a903368', 'condition', p, m]
            for p in ('original', 'fewest') for m in ('off', 'on')])
        self.assertEqual((len(foliage.TICKS), foliage.TICKS[0], foliage.TICKS[-1]), (256, 583695, 587520))
        self.assertEqual((foliage.DAWN, foliage.OPENING), (586560, 587040))

    def test_fractional_income_wear_and_compaction(self):
        for policy in foliage.TARGETS:
            data, reproduction, resources, _ = fixture(policy)
            result = foliage.validate_trace(data, reproduction, resources, policy)
            self.assertEqual(result['day']['steps'], 256)
            self.assertEqual(result['dawn']['steps'], 32)
            self.assertEqual(result['day']['renewals'], 3)
            self.assertEqual(result['day']['healthy_at_recorded_light'], 256 * result['leaves'])
            self.assertEqual(result['day']['energy']['seeds'], 48)
            self.assertEqual(len(result['openings']), 1)
            day = result['day']
            self.assertEqual(divmod(day['remainder_before'] + day['condition_weighted_numerator'], 255),
                             (day['energy']['income'], day['remainder_after']))

    def test_missing_duplicate_and_mislabeled_rows_rejected(self):
        for operation in ('missing', 'duplicate', 'timing', 'identity', 'fields'):
            args = fixture()
            data = args[0]
            if operation == 'missing':
                data['rows'].pop()
            elif operation == 'duplicate':
                data['rows'][1] = deepcopy(data['rows'][0])
            elif operation == 'timing':
                data['rows'][0]['tick'] -= 1
            elif operation == 'identity':
                data['lineage'] = 17
            else:
                data['leaf_fields'] = list(reversed(data['leaf_fields']))
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                foliage.validate_trace(*args)

    def test_bad_fields_body_mapping_and_payment_stages_rejected(self):
        for kind in ('light', 'condition', 'coordinate', 'position', 'selection', 'node',
                     'remainder', 'upkeep', 'overflow', 'phase', 'restored', 'action'):
            args = fixture()
            row = args[0]['rows'][7]
            if kind in ('light', 'condition', 'coordinate', 'position', 'node'):
                field = dict(light=5, condition=6, coordinate=3, position=1, node=0)[kind]
                row['leaves'][0][field] += 64 if kind == 'light' else 1
            elif kind == 'selection':
                row['selected'] = 255
            elif kind in ('upkeep', 'overflow'):
                row['energy']['upkeep_paid' if kind == 'upkeep' else kind] += 1
            elif kind == 'action':
                row['action'] = 2
            else:
                row['remainder_before' if kind == 'remainder' else kind] += 1
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                foliage.validate_trace(*args)

    def test_individual_wear_cannot_hide_in_unchanged_totals(self):
        args = fixture()
        row = args[0]['rows'][7]
        row['leaves'][0][6] -= 1
        row['leaves'][1][6] += 1
        with self.assertRaisesRegex(ValueError, 'per-leaf wear'):
            foliage.validate_trace(*args)

    def test_daily_ledger_and_opening_receipts_independent_cross_checks(self):
        args = fixture()
        args[1]['openings'][0]['visits'][0]['energy'] += 1
        with self.assertRaisesRegex(ValueError, 'opening receipt'):
            foliage.validate_trace(*args)
        args = fixture()
        args[2]['plant_days'][0]['energy']['income'] += 1
        with self.assertRaisesRegex(ValueError, 'daily ledger'):
            foliage.validate_trace(*args)

    def test_light_weighted_health_is_not_unweighted_health(self):
        args = fixture()
        row = deepcopy(args[0]['rows'][0])
        row['leaves'] = [[0, 8, 32, 0, 0, 255, 0], [1, 16, 32, 1, 0, 0, 255]]
        result = foliage.summary([row])
        self.assertEqual(result['healthy_at_recorded_light'], 3)
        self.assertEqual(result['mean_condition_fraction'], 0.5)
        self.assertEqual(result['weighted_condition_fraction'], 0)
        row['leaves'][0][5] = 0
        self.assertIsNone(foliage.summary([row])['weighted_condition_fraction'])


class PublishedFoliageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='published-foliage-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.out = cls.root / 'evidence'
        cls.archive = foliage.collect.ROOT / 'benchmarks/garden-seasons/leaf-population-foliage-results.json.gz'
        assert foliage.prepare.sha(cls.archive.read_bytes()) == '7462461ae0057387c2e5d1cb68fb61ab5b6671f3601640ecd1cac32b51ce5cf2'
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native calls forbidden')):
            cls.result = foliage.follow.unpack(cls.archive, cls.out, experiment=foliage.EXPERIMENT)

    def test_daily_health_and_dawn_exposure_are_different(self):
        self.assertEqual(self.result['calls'], 4)
        cases = self.result['analyses']
        for policy, daily, dawn, potential, weighted in (
                ('original', 1462, 159, (2329, 341), (372633, 40397)),
                ('fewest', 1252, 84, (2322, 185), (319103, 21613))):
            result = cases[policy]
            self.assertEqual(result['day']['energy']['income'], daily)
            self.assertEqual(result['dawn']['energy']['income'], dawn)
            self.assertEqual(tuple(result[k]['healthy_at_recorded_light'] for k in ('day', 'dawn')), potential)
            self.assertEqual(tuple(result[k]['condition_weighted_numerator'] for k in ('day', 'dawn')), weighted)
            for label in ('day', 'dawn'):
                s = result[label]
                self.assertEqual(divmod(s['remainder_before'] + s['condition_weighted_numerator'], 255),
                                 (s['energy']['income'], s['remainder_after']))
        a, b = (cases[p]['dawn'] for p in ('original', 'fewest'))
        self.assertGreater(a['mean_condition_fraction'] - b['mean_condition_fraction'], 0.17)
        self.assertLess(abs(a['weighted_condition_fraction'] - b['weighted_condition_fraction']), 0.007)

    def test_exact_dawn_reserve_gap_with_no_repairs(self):
        cases = self.result['analyses']
        for policy, before, visit_energy, after, seeds in (
                ('original', 113, 240, 192, 48), ('fewest', 116, 168, 168, 0)):
            result = cases[policy]
            dawn = result['dawn']
            flux = dawn['energy']
            self.assertEqual((flux['before'], flux['after'], flux['seeds']), (before, after, seeds))
            self.assertEqual(flux['upkeep_paid'], 32)
            self.assertEqual(dawn['renewals'], 0)
            self.assertEqual(flux['repair'], 0)
            self.assertEqual(flux['growth'], 0)
            self.assertEqual(flux['overflow'], 0)
            opening, = [r for r in result['openings'] if r['tick'] == foliage.OPENING]
            self.assertEqual(opening['visit']['energy'], visit_energy)
            self.assertEqual(before + flux['income'] - flux['upkeep_paid'], visit_energy)
            path = self.out / f'runs/9a903368-condition-{policy}-on/timeline/foliage.json'
            data = json.loads(path.read_bytes())
            self.assertEqual(len(data['rows']), 256)
            self.assertTrue(all(r['action'] == 0 for r in data['rows'] if foliage.DAWN < r['tick'] <= foliage.OPENING))

    def test_exact_archive_roundtrip_without_simulator(self):
        target = self.root / 'repacked.gz'
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native calls forbidden')):
            foliage.follow.package(self.out, target, experiment=foliage.EXPERIMENT)
        self.assertEqual(target.read_bytes(), self.archive.read_bytes())


if __name__ == '__main__':
    unittest.main()
