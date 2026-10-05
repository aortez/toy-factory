#!/usr/bin/env python3
"""Offline opening clocks, fixed-trait uncertainty and ordered-access receipts."""

import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_opening_opportunities as audit

RESULT = audit.ROOT / 'benchmarks/garden-seasons/landing-opening-opportunities-results.json.gz'


def visit(identity, count, mask):
    row = dict.fromkeys(audit.bank.FIELDS, 0)
    row.update(id=identity, bank=count, blockers=mask, produced=mask == 0)
    return [row[k] for k in audit.bank.FIELDS]


class ContractTests(unittest.TestCase):
    def test_energy_plus_bank_is_not_an_order_loss(self):
        rows = [visit(10, 7, 128), visit(11, 7, 0), visit(12, 8, 132), visit(13, 8, 4)]
        access = audit.ordered_access(rows)
        self.assertEqual([r['access'] for r in access.values()],
                         ['ineligible', 'purchased', 'ineligible', 'earlier_buyers_fill'])
        self.assertEqual(access[13]['earlier_buyers'], [11])
        self.assertEqual(access[13]['bank_at_entry'], 7)
        self.assertEqual(audit.ordered_access([visit(13, 8, 4)])[13]['access'], 'full_at_entry')

    def test_sequential_bank_cannot_drop_or_buy_when_full(self):
        for rows in ([visit(10, 7, 0), visit(11, 7, 0)], [visit(10, 8, 0)],
                     [visit(10, 8, 4), visit(10, 8, 4)], []):
            with self.subTest(rows=rows), self.assertRaises(RuntimeError):
                audit.ordered_access(rows)

    def test_reflection_aliases_and_gate_layers_are_separate(self):
        sites = bytearray([32] * 28)
        sites[3], sites[4], sites[5], sites[6] = 8, 16, 4, 0
        cols = audit.columns(sites, 0, 0)
        self.assertEqual(cols['choices'], [c for c in range(3, 10) for _ in range(2)])
        self.assertEqual(cols['spacing'], [3, 4, 5, 6])
        self.assertEqual(cols['space'], [5, 6])
        self.assertEqual(cols['opened'], [6])

    def test_fixed_trait_bounds_do_not_choose_a_trait_each_tick(self):
        # Each fixed trait works once, at different steps. Neither works twice.
        maps = []
        for column in (1, 11):
            sites = bytearray([32] * 28)
            sites[column] = 0
            maps.append(sites)
        profiles = {str(t): audit.counters() for t in (-2, 2)}
        for sites in maps:
            for trait, profile in profiles.items():
                profile['space_ticks'] += bool(audit.columns(sites, 0, int(trait))['space'])
        self.assertEqual(audit.bounds(profiles)['space_ticks'], [1, 1])
        self.assertEqual(sum(any(audit.columns(s, 0, t)['space'] for t in (-2, 2)) for s in maps), 2)

    def test_fresh_output_refused_before_loading(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('existing', 'dangling'):
                path = Path(tmp) / name
                if name == 'existing':
                    path.mkdir()
                else:
                    path.symlink_to(Path(tmp) / 'missing')
                with patch('sys.argv', ['audit', '--out', str(path)]), \
                     patch.object(audit, 'export', side_effect=AssertionError('no extraction')):
                    with self.assertRaisesRegex(RuntimeError, 'fresh output'):
                        audit.main()


class CapturedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch('subprocess.run', side_effect=AssertionError('no processes')), \
             patch('subprocess.Popen', side_effect=AssertionError('no processes')):
            cls.saved, cls.capture = audit.inputs()
            if RESULT.exists():
                with gzip.open(RESULT, 'rt') as stream:
                    cls.value = json.load(stream)
            else:
                cls.value = audit.export()
        cls.keys = sorted(cls.capture['panel'])

    def arm(self, index=4, phase='treatment'):
        key = self.keys[index]
        material = self.value['material'][key]
        return material['evidence'][phase], material['traits'], self.capture['panel'][key], \
            self.capture['runs'][phase][key], material['interval'], phase

    def sites(self, row):
        _, _, _, run, _, _ = self.arm()
        lives = {p['id']: p for p in run['result']['lineages']}
        return audit.site_map(row, lives, run['result'])

    def test_full_reanalysis_without_processes(self):
        with patch('subprocess.run', side_effect=AssertionError('no processes')), \
             patch('subprocess.Popen', side_effect=AssertionError('no processes')):
            audit.check_value(self.value)

    def test_five_exact_windows_all_twelve_parents_and_closing_exclusion(self):
        self.assertEqual(len(self.keys), 5)
        self.assertEqual([len(self.arm(i)[0]['rows']) for i in range(5)], [157, 157, 164, 161, 425])
        self.assertEqual(sum(len(m['traits']) for m in self.value['material'].values()), 12)
        for key, material in self.value['material'].items():
            start, stop = material['interval']
            for phase in audit.PHASES:
                evidence = material['evidence'][phase]
                self.assertEqual(evidence['before'][0], start - audit.STEP)
                self.assertEqual(evidence['rows'][-1][0], stop - audit.STEP)
                self.assertEqual(evidence['closing'][0], stop)
                self.assertTrue(all(len(r[1]) == (7 if phase == 'treatment' else 8) for r in evidence['rows']))
                for p in self.value['analysis'][key][phase]['parents'].values():
                    self.assertEqual(p['ecology_visits'], (stop - start) // audit.STEP)
                    self.assertTrue(all(r['tick'] < stop for r in p['opportunity_visits']))

    def test_missing_reordered_and_inclusive_closing_rows_rejected(self):
        evidence, *rest = self.arm()
        variants = [evidence['rows'][1:], list(reversed(evidence['rows'])),
                    evidence['rows'] + [evidence['closing']]]
        for rows in variants:
            with self.assertRaisesRegex(RuntimeError, 'clock or boundary'):
                audit.analyze_arm(dict(evidence, rows=rows), *rest)
        changed = copy.deepcopy(evidence)
        changed['before'][0] += audit.STEP
        with self.assertRaisesRegex(RuntimeError, 'clock or boundary'):
            audit.analyze_arm(changed, *rest)

    def test_unknown_traits_remain_bounded_including_zero_producers(self):
        traits = [t for m in self.value['material'].values() for t in m['traits'].values()]
        self.assertEqual(sum(t['status'] == 'bounded' for t in traits), 7)
        self.assertEqual(sum(t['status'] == 'recorded' for t in traits), 5)
        for t in traits:
            if t['status'] == 'bounded':
                self.assertEqual(t['allowed'], list(audit.TRAITS))
                self.assertEqual(t['witnesses'], [])
            else:
                self.assertEqual(len(t['allowed']), 1)
                self.assertEqual({w['purchase']['dispersal'] for w in t['witnesses']}, set(t['allowed']))
        for index, identity in ((2, '34'), (4, '31')):
            t = self.value['material'][self.keys[index]]['traits'][identity]
            self.assertEqual({w['phase'] for w in t['witnesses']}, {'control'})
            self.assertEqual(t['allowed'], [-1])

    def test_identity_mismatch_and_inconsistent_trait_witness_rejected(self):
        key = self.keys[4]
        pair = self.saved['evidence'][key]
        runs = {phase: copy.deepcopy(self.capture['runs'][phase][key]) for phase in audit.PHASES}
        next(p for p in runs['treatment']['result']['lineages'] if p['id'] == 31)['column'] += 1
        with self.assertRaisesRegex(RuntimeError, 'pre-event trait identity'):
            audit.trait_evidence(pair, runs, [31])
        changed = copy.deepcopy(self.value['material'])
        info = changed[key]['traits']['31']
        info['witnesses'].append(copy.deepcopy(info['witnesses'][0]))
        info['witnesses'][-1]['purchase']['dispersal'] = 0
        with self.assertRaisesRegex(RuntimeError, 'trait evidence'):
            audit.analyze(changed, self.capture)
        changed = copy.deepcopy(self.value['material'])
        changed[self.keys[0]]['traits']['30']['allowed'] = [0]
        with self.assertRaisesRegex(RuntimeError, 'trait evidence'):
            audit.analyze(changed, self.capture)

    def test_site_map_requires_compatible_phases_and_checks(self):
        evidence, *_ = self.arm()
        row = copy.deepcopy(evidence['rows'][0])
        self.sites(row)
        row[3][0][1][0][3][0] += 1
        with self.assertRaisesRegex(RuntimeError, 'changed site phase'):
            self.sites(row)
        row = copy.deepcopy(evidence['rows'][0])
        row[5][0][1] = '00' * 28
        with self.assertRaisesRegex(RuntimeError, 'incompatible site maps'):
            self.sites(row)
        row = copy.deepcopy(evidence['rows'][0])
        for raw, _ in row[5]:
            raw[7] -= 1
        with self.assertRaisesRegex(RuntimeError, 'census differs'):
            self.sites(row)
        row = copy.deepcopy(evidence['rows'][0])
        raw = next(raw for raw, observed in row[5] if observed is not None)
        raw[4] = 0 if raw[4] >= 12 else 12
        with self.assertRaisesRegex(RuntimeError, 'light/moisture differs'):
            self.sites(row)
        with self.assertRaisesRegex(RuntimeError, 'birth or stored corpse'):
            self.sites(copy.deepcopy(evidence['closing']))

    def test_capacity_map_and_post_purchase_phase_are_checked(self):
        evidence, *_ = self.arm()
        row = copy.deepcopy(evidence['rows'][0])
        for check in row[5]:
            if check[1] is not None:
                check[1] = bytes(x ^ 8 for x in bytes.fromhex(check[1])).hex()
        with self.assertRaisesRegex(RuntimeError, 'capacity/spacing/climate'):
            self.sites(row)
        row = copy.deepcopy(next(r for r in evidence['rows'] if r[6]))
        row[6][0]['sites'] = '00' * 28
        with self.assertRaisesRegex(RuntimeError, 'post-purchase site phase'):
            self.sites(row)

    def test_joint_opportunities_are_full_at_entry_not_order_losses(self):
        analyses = [arms['treatment'] for arms in self.value['analysis'].values()]
        plants = [p for a in analyses for p in a['parents'].values()]
        self.assertEqual(sum(p['daylight_cadence'] for p in plants), 149)
        self.assertEqual(sum(p['ecology_visits'] for p in plants), 2446)
        for metric, expected in (('space_eligible', [49, 49]), ('open_eligible', [35, 35]),
                                 ('space_full_at_entry', [49, 49]), ('open_full_at_entry', [35, 35]),
                                 ('space_earlier_buyers_fill', [0, 0]), ('space_purchased', [0, 0])):
            self.assertEqual([sum(p['bounds'][metric][i] for p in plants) for i in (0, 1)], expected, metric)
        w5 = analyses[4]['parents']
        self.assertEqual(w5['30']['bounds']['open_eligible'], [17, 17])
        self.assertEqual(w5['31']['bounds']['open_eligible'], [18, 18])
        for a in self.value['analysis'].values():
            for p in a['control']['parents'].values():
                self.assertEqual(p['bounds']['space_ticks'], [0, 0])

    def test_selected_evidence_counts_and_receipt_tampering_rejected(self):
        changed = dict(self.value, material=copy.deepcopy(self.value['material']))
        changed['material'][self.keys[0]]['evidence']['treatment']['closing'][0] += audit.STEP
        with self.assertRaisesRegex(RuntimeError, 'selected evidence'):
            audit.check_value(changed)
        changed = dict(self.value, analysis=copy.deepcopy(self.value['analysis']))
        changed['analysis'][self.keys[4]]['treatment']['parents']['31']['bounds']['open_eligible'][0] += 1
        with self.assertRaisesRegex(RuntimeError, 'derived opportunity'):
            audit.check_value(changed)
        with self.assertRaisesRegex(RuntimeError, 'opportunity receipt'):
            audit.check_value(dict(self.value, receipt_sha256='0' * 64))


if __name__ == '__main__':
    unittest.main()
