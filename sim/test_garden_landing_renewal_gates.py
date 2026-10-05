#!/usr/bin/env python3
"""Offline seed gates, ordered purchases, compact evidence and window boundaries."""

import copy
import gzip
import json
import lzma
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_renewal_gates as audit

S = audit.STEP


def life(i=1, column=5, birth=0, death=None, parent=0):
    return dict(id=i, parent=parent, generation=int(parent != 0), column=column,
                birth_tick=birth, death_tick=death)


def seed(birth=0, end=150, outcome='expired', parent=1, column=7, child=None, lifetime=10):
    return dict(parent=parent, birth_tick=birth, end_tick=end, outcome=outcome,
                column=column, child_id=child, lifetime_ecology_ticks=lifetime, species=0)


def row(result, tick, attempts, *, order=None, funded=(), flowers=None, light=100):
    """Small synthetic receipts; no native executable and no audit decision helpers."""
    live = [p['id'] for p in result['lineages'] if p['birth_tick'] <= tick and
            (p['death_tick'] is None or p['death_tick'] > tick)]
    order = live if order is None else order
    phase = (64 + tick // S) % 256
    sun = audit.population.dawn.previous.audit.strength(phase, light)
    bank = sum(s['birth_tick'] < tick < (s['end_tick'] or result['tick'] + S) for s in result['seeds'])
    bought = {s['parent'] for s in result['seeds'] if s['birth_tick'] == tick}
    visits, resources = [], []
    for i in order:
        produced = i in bought
        ready, immature, spent = (flowers or {}).get(i, (1, 0, 0))
        water = 100 if produced or i in funded else 0
        blockers = (2 if tick % 60 else 0) | (4 if bank == 8 else 0) | (8 if i not in live else 0)
        blockers |= (32 if sun <= 24 else 0) | (256 if water < 40 else 0) | (512 if ready == 0 else 0)
        v = dict(id=i, blockers=blockers, energy=100, water=water, energy_required=80, water_required=40,
                 immature=immature, spent=spent, ready=ready, flower=0 if ready else 65535,
                 cooldown=0, bank=bank, stress=0, sun=sun, produced=produced)
        visits.append([v[k] for k in audit.FIELDS])
        if i in live:
            resources.append([i, 100, water, 100 - 48 * produced, water - 24 * produced,
                              ready + immature + spent, 4])
        bank += produced
    return [tick, [phase, sun], light < 65, bank, order, attempts, visits, resources,
            dict(cold=light < 65, light_percent=light)]


def fixture():
    result = dict(tick=180, lineages=[life()], seeds=[seed(), seed(180, None, 'pending', column=0)])
    rows = []
    for tick in range(105, 195, S):
        attempts = ([[1, tick // S, 7, 33 if tick == 105 else 32, 12, 80, 1, 4, 0, 0, 10]]
                    if tick < 150 else [[1, 10, 7, 0, 0, 0, 1, 4, 1, 0, -1]] if tick == 150 else [])
        rows.append(row(result, tick, attempts))
    return result, rows


class AccountingTests(unittest.TestCase):
    def test_raw_season_name_and_numeric_enum_are_equivalent(self):
        stand = dict(tick=120, climate=dict(cold=False, season='spring'), plant_order=[],
                     reproduction=[], bodies=[])
        adult = dict(tick=120, cold=False, season=0, plants=[], sun=[72, 200], bank=0, seeds=[])
        self.assertEqual(audit.packed_row(stand, adult)[2], False)
        adult['season'] = 1
        with self.assertRaises(RuntimeError):
            audit.packed_row(stand, adult)

    def test_boundaries_expiry_supply_and_purchase_on_final_tick(self):
        result, rows = fixture()
        original = copy.deepcopy((result, rows))
        with patch('subprocess.Popen', side_effect=AssertionError('native process forbidden')):
            value = audit.period(result, rows, 90, 180)
        s = value['seed_window']['summary']
        self.assertEqual((s['dormant_checks'], s['mature_checks'], s['expiry_samples']), (1, 2, 1))
        self.assertEqual(s['cohorts']['carry_in']['outcomes_at_window_end'], {'expired': 1})
        self.assertEqual(s['cohorts']['purchased']['outcomes_at_window_end'], {'pending': 1})
        self.assertEqual(value['seed_window']['seeds'][1]['samples'], 0)
        self.assertEqual(value['bank_post_step'], {'0': 2, '1': 4})
        self.assertEqual(value['exposure']['samples_no_seed_at_checks'], 2)
        r = value['reproduction']
        self.assertEqual(r['daylight_payment']['masks'], {'0': 1, '256': 1})
        self.assertEqual(r['access'], {'other_gates': 1, 'purchased': 1})
        self.assertEqual((result, rows), original)

    def test_nested_window_does_not_count_a_future_expiry(self):
        result, rows = fixture()
        value = audit.period(result, rows[:3], 90, 135)
        self.assertEqual(value['seed_window']['summary']['cohorts']['carry_in']['outcomes_at_window_end'],
                         {'pending': 1})
        self.assertEqual(value['seed_window']['summary']['expiry_samples'], 0)

    def test_cold_cannot_claim_an_open_site(self):
        result = dict(tick=120, lineages=[life()], seeds=[seed(end=None, outcome='pending')])
        values = [[1, 8, 7, 96, 12, 80, 1, 4, 0, 0, 0]]
        rows = [row(result, 120, values, light=64)]
        value = audit.period(result, rows, 105, 120)
        self.assertEqual(value['seed_window']['summary']['blocker_checks']['cold'], 1)
        for field, bad in ((3, 32), (10, 1)):
            corrupted = copy.deepcopy(rows)
            corrupted[0][5][0][field] = bad
            with self.assertRaises(RuntimeError):
                audit.period(result, corrupted, 105, 120)

    def test_capacity_and_spacing_are_overlapping_not_exclusive(self):
        result = dict(tick=120, lineages=[life()], seeds=[seed(end=None, outcome='pending')])
        rows = [row(result, 120, [[1, 8, 7, 56, 12, 80, 8, 253, 0, 0, 0]])]
        value = audit.period(result, rows, 105, 120)['seed_window']['summary']
        self.assertEqual(value['mature_checks'], 1)
        self.assertEqual(value['blocker_checks']['plant_capacity'], 1)
        self.assertEqual(value['blocker_checks']['node_capacity'], 1)
        self.assertEqual(value['blocker_checks']['spacing'], 1)
        self.assertFalse(any(value['sole_blocker_checks'].values()))

    def test_sequential_germination_adds_a_spacing_witness(self):
        result = dict(tick=120, lineages=[life(), life(2, 20, 120, parent=1)], seeds=[
            seed(end=120, outcome='germinated', column=20, child=2),
            seed(birth=15, end=None, outcome='pending', column=21)])
        attempts = [[1, 8, 20, 0, 12, 80, 1, 4, 2, 2, 10],
                    [1, 7, 21, 33, 12, 80, 2, 8, 0, 0, 7]]
        rows = [row(result, 120, attempts)]
        value = audit.period(result, rows, 105, 120)
        self.assertEqual(len(value['seed_window']['germinations']), 1)
        # A newborn witness applies even before the second seed matures.
        rows[0][5][1][3] = 1
        with self.assertRaises(RuntimeError):
            audit.period(result, rows, 105, 120)

    def test_expired_seed_releases_bank_before_purchases(self):
        result, rows = fixture()
        result['seeds'][1]['birth_tick'] = 120
        result['seeds'][0].update(end_tick=120, lifetime_ecology_ticks=8)
        one = row(result, 120, [[1, 8, 7, 0, 0, 0, 1, 4, 1, 0, -1]])
        value = audit.period(result, [one], 105, 120)
        self.assertEqual(one[6][0][audit.FIELDS.index('bank')], 0)
        self.assertEqual(value['bank_post_step'], {'1': 1})
        self.assertEqual(value['reproduction']['access'], {'purchased': 1})

    def test_bank_at_entry_versus_earlier_buyers(self):
        self.assertEqual(audit.bank_access(4, 8), 'full_at_entry')
        self.assertEqual(audit.bank_access(4, 7), 'earlier_buyers_fill')
        self.assertEqual(audit.bank_access(260, 8), 'other_gates')
        result = dict(tick=600, lineages=[life(), life(2, 20)], seeds=[
            seed(birth=t, end=None, outcome='pending', lifetime=8192) for t in range(0, 420, 60)] +
            [seed(600, None, 'pending', lifetime=8192)])
        attempts = [[1, (600 - s['birth_tick']) // S, 7, 32, 12, 80, 2, 8, 0, 0, 10]
                    for s in result['seeds'][:-1]]
        values = row(result, 600, attempts, funded=(1, 2))
        value = audit.period(result, [values], 585, 600)
        self.assertEqual(value['reproduction']['access'], {'purchased': 1, 'earlier_buyers_fill': 1})
        self.assertEqual(value['reproduction']['daylight_payment']['sole_blockers']['bank'], 1)
        corrupted = copy.deepcopy(values)
        corrupted[6].reverse()
        with self.assertRaises(RuntimeError):
            audit.period(result, [corrupted], 585, 600)

    def test_absent_immature_spent_and_ready_flowers(self):
        for state, flower_counts in (('absent', (0, 0, 0)), ('immature_without_ready', (0, 1, 1)),
                                    ('spent_only', (0, 0, 1)), ('ready', (1, 1, 1))):
            result, rows = fixture()
            values = row(result, 120, rows[1][5], flowers={1: flower_counts})
            value = audit.period(result, [values], 105, 120)['reproduction']
            self.assertEqual(value['flowers'], {state: 1})
            self.assertEqual(value['daylight_payment']['blockers']['flower'], int(state != 'ready'))

    def test_dead_visits_validate_but_do_not_enter_opportunity_denominator(self):
        result = dict(tick=120, lineages=[life(death=105)], seeds=[seed(end=None, outcome='pending')])
        values = row(result, 120, [[1, 8, 7, 32, 12, 80, 1, 4, 0, 0, 10]], order=[1])
        value = audit.period(result, [values], 105, 120)
        self.assertEqual(value['reproduction']['daylight_payment']['visits'], 0)
        self.assertEqual(value['seed_window']['summary']['spacing_without_living_witness'], 1)

    def test_night_and_off_cadence_are_not_explanatory_opportunities(self):
        for tick in (105, 960):
            result = dict(tick=tick, lineages=[life()], seeds=[])
            values = row(result, tick, [])
            value = audit.period(result, [values], tick - S, tick)
            self.assertEqual(value['exposure']['all_visits'], 1)
            self.assertEqual(value['exposure']['living_visits'], 1)
            self.assertEqual(value['reproduction']['daylight_payment']['visits'], 0)

    def test_corrupt_receipts_fail(self):
        mutations = {
            'missing row': lambda r: r.pop(),
            'extra row': lambda r: r.append(copy.deepcopy(r[-1])),
            'clock': lambda r: r[0].__setitem__(0, 120),
            'inventory': lambda r: r[0][5].clear(),
            'visit mask': lambda r: r[1][6][0].__setitem__(1, 0),
            'visit bank': lambda r: r[1][6][0].__setitem__(11, 8),
            'visit bounds': lambda r: r[1][6][0].__setitem__(9, 256),
            'sun': lambda r: r[1][1].__setitem__(1, 0),
            'cold': lambda r: r[1].__setitem__(2, True),
            'flower count': lambda r: r[1][7][0].__setitem__(5, 2),
            'ready index': lambda r: r[1][6][0].__setitem__(9, 65535),
            'resource debit': lambda r: r[-1][7][0].__setitem__(3, 100),
            'closing bank': lambda r: r[-1].__setitem__(3, 0),
            'boolean mask': lambda r: r[1][6][0].__setitem__(1, True),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                result, rows = fixture()
                mutate(rows)
                with self.assertRaises(RuntimeError):
                    audit.period(result, rows, 90, 180)

    def test_no_clobber_or_unsupported_job_count(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with patch('subprocess.Popen', side_effect=AssertionError('native process forbidden')):
                for out, jobs in ((path, 1), (path / 'new', 0), (path / 'new', 5)):
                    with self.assertRaises(RuntimeError):
                        audit.collect(path, out, jobs)
            file = path / 'result.gz'
            audit.write_gzip(file, {'a': 1})
            with self.assertRaises(FileExistsError):
                audit.write_gzip(file, {'a': 2})
            with gzip.open(file, 'rt') as stream:
                self.assertEqual(json.load(stream), {'a': 1})

    def test_excerpt_cannot_hide_extra_out_of_window_rows(self):
        result, rows = fixture()
        item = dict(id='one')
        capture = dict(runs={'one': dict(result=result, traces=dict(stand={}, adult={}))})
        excerpt = dict(id='one', traces=dict(stand={}, adult={}), rows=rows)
        with patch.multiple(audit, START=90, STOP=180, LATE=120):
            audit.analyze(item, excerpt, capture)
            for tick in (90, 195):
                bad = copy.deepcopy(excerpt)
                extra = copy.deepcopy(rows[0])
                extra[0] = tick
                bad['rows'].append(extra)
                with self.assertRaises(RuntimeError):
                    audit.analyze(item, bad, capture)

    def test_rotating_visit_order_is_checked_at_the_actual_payment(self):
        tick = audit.population.order.AT + 60
        result = dict(tick=tick, lineages=[life(), life(2, 20)], seeds=[], seed_order_probe={})
        values = row(result, tick, [], order=[2, 1])
        values[4] = [1, 2]  # Slot order differs from the rotated visit order.
        audit.period(result, [values], tick - S, tick)
        values[6].reverse()
        with self.assertRaises(RuntimeError):
            audit.period(result, [values], tick - S, tick)


class FrozenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = audit.ROOT / 'benchmarks/garden-seasons'
        with gzip.open(cls.root / 'landing-renewal-gates-results.json.gz', 'rt') as stream:
            cls.value = json.load(stream)

    def test_frozen_panel_identity_and_lossless_excerpt(self):
        value = self.value
        self.assertEqual(audit.digest(self.root / 'landing-renewal-gates-results.json.gz'),
                         '20d269d868b2cc1135e93d4b0f4ebe37ef667e3316d92e280d1d7488b38bd255')
        self.assertEqual(audit.digest(self.root / 'landing-renewal-gates-windows.jsonl.xz'),
                         'd7ff641241c1cc0f242e68628648a04ce82e1ffe5046f0a4221a2485b7c61026')
        self.assertEqual(value['protocol_sha256'], audit.PROTOCOL_SHA)
        self.assertEqual((value['native_runs'], value['training_runs']), (0, 0))
        self.assertEqual(len(value['worlds']), 32)
        self.assertEqual(len({w['id'] for w in value['worlds']}), 32)
        # A complete representative world is re-derived in the regular unit
        # suite. The command-line verifier covers all 32, optionally from raw.
        with patch('subprocess.Popen', side_effect=AssertionError('native process forbidden')):
            capture, panel = audit.source()
            self.assertEqual([w['id'] for w in value['worlds']], [p['id'] for p in panel])
            with lzma.open(self.root / 'landing-renewal-gates-windows.jsonl.xz', 'rt') as stream:
                self.assertEqual(json.loads(next(stream)), audit.header())
                excerpt = json.loads(next(stream))
            self.assertEqual(audit.analyze(panel[0], excerpt, capture), value['worlds'][0])

    def test_all_settings_preserved_with_exact_historical_births(self):
        for label, expected in (('post', [108, 61, 36, 18]), ('late32', [6, 4, 0, 0])):
            births = [sum(len(w['windows'][label]['seed_window']['germinations'])
                          for w in self.value['worlds'] if w['arm'] == arm) for arm in audit.previous.ARMS]
            self.assertEqual(births, expected)
        self.assertEqual(sum(w['windows']['post']['exposure']['all_visits'] for w in self.value['worlds']),
                         4633854)

    def test_cap_bank_supply_and_universal_living_nonparent_spacing(self):
        for w in self.value['worlds']:
            if w['arm'] not in ('cap', 'cap-wick'):
                continue
            x = w['windows']['late32']
            s = x['seed_window']['summary']
            self.assertEqual(s['cohorts']['purchased']['seeds'], 8)
            self.assertEqual(s['expiry_samples'], 8)
            self.assertEqual(s['blocker_checks']['spacing'], s['mature_checks'])
            self.assertEqual(s['spacing_with_living_witness'], s['mature_checks'])
            self.assertEqual(s['other_spacing_checks'], s['mature_checks'])
            self.assertEqual(s['parent_spacing_checks'], 0)
            self.assertEqual(s['spacing_without_living_witness'], 0)
            self.assertEqual(x['reproduction']['daylight_payment']['blockers']['water'], 0)
            self.assertGreaterEqual(x['bank_post_step']['8'], 8188)
            if w['arm'] == 'cap':
                self.assertEqual(s['blocker_checks']['plant_capacity'], 0)
                self.assertEqual(s['blocker_checks']['node_capacity'], 0)
                self.assertGreater(s['open_elsewhere_checks'], 0)
            else:
                self.assertEqual(s['blocker_checks']['moisture'], 0)

    def test_actual_pool_saturation_counterexamples_are_preserved(self):
        both = [w for w in self.value['worlds'] if w['arm'] == 'cap-wick']
        for w in both:
            s = w['windows']['late32']['seed_window']['summary']
            expected = 0 if w['guard'] != 'candidate' or w['allocator'] != 'candidate' else (
                30808 if w['order'] == 'fixed' else 65472)
            self.assertEqual(s['blocker_checks']['plant_capacity'], expected)
            self.assertEqual(s['blocker_checks']['node_capacity'], expected)
        self.assertEqual(sum(w['windows']['late32']['seed_window']['summary']['open_elsewhere_checks'] > 0
                             for w in both), 5)

    def test_bank_only_is_not_conflated_with_energy_or_flower_shortfall(self):
        for w in self.value['worlds']:
            for x in w['windows'].values():
                r = x['reproduction']
                masks = r['daylight_payment']['masks']
                self.assertEqual(r['daylight_payment']['visits'], sum(masks.values()))
                self.assertEqual(r['daylight_payment']['sole_blockers']['bank'], masks.get('4', 0))
                self.assertEqual(masks.get('4', 0), r['access'].get('full_at_entry', 0) +
                                 r['access'].get('earlier_buyers_fill', 0))
                self.assertEqual(r['access'].get('purchased', 0), masks.get('0', 0))
                for i, key in enumerate(audit.BLOCKERS):
                    self.assertEqual(r['daylight_payment']['blockers'][key],
                                     sum(n for m, n in masks.items() if int(m) & (1 << i)))


if __name__ == '__main__':
    unittest.main()
