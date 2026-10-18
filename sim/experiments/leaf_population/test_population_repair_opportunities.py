"""Exact neural gates, selector timing, and immutable offline opportunity evidence."""

from functools import lru_cache
import json
from math import gcd
import struct
import subprocess
import unittest
from unittest import mock
import zlib

import population_repair_opportunities as repair

PUBLISHED = repair.collect.ROOT / 'benchmarks/garden-seasons/leaf-population-repair-opportunities.json'


@lru_cache
def raw_model():
    _, models, _ = repair.collect.archive_inputs()
    return repair.gates.derive(models, 'condition')


def fixture(light=96, initial_condition=100, accepted=True):
    """Attribution-only fixture with a stable body and changing global slots."""
    conditions, rows = [initial_condition] * 24, []
    model = repair.decision_model(raw_model())
    for index, tick in enumerate(repair.foliage.TICKS):
        conditions = [max(0, c - int(tick % 60 == 0)) for c in conditions]
        ordinal = (tick // 15 + 19) % 24
        base = 8 if index < 128 else 0
        action = repair.evaluate(model, conditions[ordinal], light, 24)['action']
        renewed = int(accepted and action == 1)
        rows.append(dict(tick=tick, phase=(tick // 15 + 64) % 256, selected=base + ordinal,
            action=action, renewals=renewed, restored=(255 - conditions[ordinal]) * renewed,
            energy=dict(points=[256, 256, 256, 256, 256, 256]),
            leaves=[[base + i, 8 + 8 * i, 32 + 8 * (i % 14), i, i % 14, light, c]
                    for i, c in enumerate(conditions)]))
        if renewed:
            conditions[ordinal] = 255
    return dict(lineage=19, rows=rows)


class RepairOpportunityTests(unittest.TestCase):
    def test_exact_quantized_thresholds_and_tie_to_wait(self):
        model = repair.decision_model(raw_model())
        for count in (24, 26):
            self.assertEqual(repair.thresholds(model, count), dict(light_minimum=145, condition_maximum=192))
            for condition, light, expected in ((192, 145, 1), (193, 145, 0), (192, 144, 0), (0, 64, 0)):
                result = repair.evaluate(model, condition, light, count)
                self.assertEqual(result['action'], expected)
            self.assertEqual(repair.evaluate(model, 192, 144, count)['scores'], [0, 0])

    def test_unobserved_inputs_are_proven_irrelevant_not_assumed_zero(self):
        model = repair.decision_model(raw_model())
        for condition, light in ((0, 24), (192, 145), (193, 145), (100, 255)):
            expected = repair.evaluate(model, condition, light, 26)['scores']
            for water, dx, dy, energy, upkeep in ((0, -240, 240, 0, 0), (512, 240, -240, 256, 16)):
                _, _, actual = repair.shadow.network(model,
                    [condition, light, energy, water, 26, dx, dy, upkeep, upkeep, 9, 5])
                self.assertEqual(actual, expected)
        for offset in (44 + 3, 44 + 11 + 2, 140 + 8 + 2):
            changed = bytearray(raw_model())
            changed[16 + offset] = 1
            struct.pack_into('<I', changed, 12, zlib.crc32(changed[16:]))
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                repair.decision_model(bytes(changed))

    def test_compaction_preserves_body_order_and_count_conservation(self):
        result = repair.attribute(fixture(180), raw_model())
        self.assertEqual(result['day']['selected'], 256)
        self.assertEqual(result['day']['samples'], 6144)
        self.assertEqual({l['day']['selected'] for l in result['leaves']}, {10, 11})
        self.assertEqual(result['day']['renewal_rejected'], 0)
        for k in repair.COUNTS:
            self.assertEqual(result['day'][k], sum(l['day'][k] for l in result['leaves']))
            self.assertEqual(result['day'][k], sum(h['day'][k] for h in result['heights'].values()))
            for h in result['heights'].values():
                self.assertEqual(h['day'][k], sum(p[k] for p in h['periods'].values()))

    def test_rejected_renewal_is_not_a_controller_wait(self):
        result = repair.attribute(fixture(180, accepted=False), raw_model())
        self.assertEqual(result['day']['selected_would_renew'], 256)
        self.assertEqual(result['day']['renewals'], 0)
        self.assertEqual(result['day']['renewal_rejected'], 256)
        self.assertTrue(all(l['outcome'] == 'requested_but_not_accepted' for l in result['leaves']))

    def test_selection_action_and_body_corruption_are_rejected(self):
        for change in ('selection', 'action', 'position', 'order', 'missing', 'phase', 'condition'):
            data = fixture()
            row = data['rows'][7]
            if change == 'selection':
                row['selected'] = row['leaves'][(row['selected'] - 8 + 1) % 24][0]
            elif change == 'action':
                row['action'] = 1
            elif change == 'position':
                row['leaves'][0][1] += 1
            elif change == 'order':
                row['leaves'].reverse()
            elif change == 'missing':
                data['rows'].pop()
            elif change == 'phase':
                row['phase'] += 1
            else:
                row['leaves'][0][6] = -1
            with self.subTest(change=change), self.assertRaises(ValueError):
                repair.attribute(data, raw_model())

    def test_bright_but_unselected_window_differs_from_never_bright(self):
        data = fixture(initial_condition=0)
        row = next(r for r in data['rows'] if r['selected'] != r['leaves'][0][0])
        row['leaves'][0][5] = 145
        result = repair.attribute(data, raw_model())
        self.assertEqual(result['leaves'][0]['outcome'], 'joint_gate_windows_not_selected')
        self.assertEqual(result['leaves'][0]['day']['would_renew'], 1)
        self.assertEqual(result['leaves'][1]['outcome'], 'never_reaches_light_gate')
        self.assertEqual(result['leaves'][1]['day']['productive'], 256)

    def test_last_sample_renewal_is_not_zero_condition_all_day(self):
        data = fixture(initial_condition=0)
        row = data['rows'][-1]
        ordinal = row['selected'] - row['leaves'][0][0]
        row['leaves'][ordinal][5] = 145
        row.update(action=1, renewals=1, restored=255)
        leaf = repair.attribute(data, raw_model())['leaves'][ordinal]
        self.assertFalse(leaf['zero_all_day'])
        self.assertEqual((leaf['first_condition'], leaf['final_condition']), (0, 255))

    def test_windows_preserve_chronology_and_reject_duplicate_ticks(self):
        ticks = [repair.foliage.FIRST + t for t in (15, 30, 75, 90)]
        self.assertEqual(repair.windows(ticks), [
            dict(first_tick=ticks[0], last_tick=ticks[1], steps=2),
            dict(first_tick=ticks[2], last_tick=ticks[3], steps=2)])
        for bad in (ticks[::-1], [ticks[0], ticks[0]], [ticks[0] + 1], [repair.foliage.FIRST]):
            with self.subTest(ticks=bad), self.assertRaises(ValueError):
                repair.windows(bad)
        self.assertEqual(repair.PERIODS, (('before_dawn', 583680, 586560),
            ('dawn', 586560, 587040), ('after_opening', 587040, 587520)))

    def test_selection_phase_does_not_repeat_every_day(self):
        for lineage, count, days in ((19, 24, 3), (17, 26, 13)):
            self.assertEqual(count // gcd(count, 256), days)
            start = repair.foliage.FIRST // 15
            for phase in range(256):
                first = (start + phase + lineage) % count
                self.assertEqual((start + phase + 256 * days + lineage) % count, first)
                self.assertNotEqual((start + phase + 256 + lineage) % count, first)


class PublishedRepairOpportunityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native calls forbidden')):
            cls.result = repair.diagnose()

    def test_exact_published_derivation(self):
        self.assertEqual(self.result, json.loads(PUBLISHED.read_bytes()))
        self.assertEqual(self.result['native_calls'], 0)
        self.assertEqual(len(self.result['inputs']), 4)
        self.assertEqual(self.result['model_sha256'], repair.MODEL_SHA)
        self.assertEqual(sum(c['day']['selected'] for c in self.result['cases'].values()), 512)
        self.assertEqual(sum(c['day']['samples'] for c in self.result['cases'].values()), 12800)

    def test_all_relocated_lower_visits_fail_only_the_light_gate(self):
        a, b = (self.result['cases'][p] for p in ('original', 'fewest'))
        self.assertEqual((a['day']['renewals'], b['day']['renewals']), (15, 9))
        self.assertEqual((a['heights']['lower']['day']['renewals'], b['heights']['lower']['day']['renewals']), (9, 0))
        lower = b['heights']['lower']
        self.assertEqual(lower['day']['selected'], 146)
        self.assertEqual(lower['day']['wait_light_only'], 146)
        self.assertEqual(lower['day']['selected_productive'], 23)
        self.assertEqual(lower['outcomes'], dict(never_reaches_light_gate=9, joint_gate_windows_not_selected=6))
        self.assertEqual(len(lower['zero_all_day']), 11)
        for c in (a, b):
            self.assertEqual(c['day']['renewal_rejected'], 0)
            self.assertEqual(c['day']['selected_energy_shortages'], 0)

    def test_short_windows_missed_before_and_after_the_opening(self):
        c = self.result['cases']['fewest']
        lower = c['heights']['lower']
        self.assertEqual([lower['periods'][p]['unselected_would_renew']
                          for p, _, _ in repair.PERIODS], [8, 0, 28])
        self.assertEqual([l['ordinal'] for l in c['leaves'] if l['row'] >= 7 and
                          l['outcome'] == 'joint_gate_windows_not_selected'], [0, 1, 3, 5, 8, 19])
        l = c['leaves'][3]
        self.assertEqual(l['joint_gate_windows'], [dict(first_tick=587250, last_tick=587385, steps=10)])
        selected = [r for r in c['decisions'] if r['ordinal'] == 3 and r['tick'] > repair.foliage.OPENING]
        self.assertEqual([(r['tick'], r['phase'], r['light']) for r in selected], [(587130, 38, 118), (587520, 64, 107)])
        self.assertEqual((l['first_condition'], l['final_condition']), (124, 60))

    def test_no_dawn_gate_opportunity_and_zero_condition_is_repairable(self):
        for c in self.result['cases'].values():
            self.assertEqual(sum(h['periods']['dawn']['light_pass'] for h in c['heights'].values()), 0)
        a = self.result['cases']['original']
        renewed_zero = [r for r in a['decisions'] if r['condition'] == 0 and r['renewed']]
        self.assertEqual([(r['ordinal'], r['tick'], r['light'], r['restored']) for r in renewed_zero],
                         [(14, 587445, 154, 255)])


if __name__ == '__main__':
    unittest.main()
