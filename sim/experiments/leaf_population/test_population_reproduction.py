"""Independent ordered-access accounting, fixed scope, and receipt rejection."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import population_reproduction as access


def fixture():
    tick = access.FIRST + access.CADENCE
    final = dict(lineages=[dict(id=i, parent=0, birth_tick=0, death_tick=None) for i in (1, 2)],
                 family_roots=[1, 2], seeds=[dict(parent=1, birth_tick=0, end_tick=None) for _ in range(8)])
    final['seeds'][0]['end_tick'] = tick
    final['seeds'].append(dict(parent=1, birth_tick=tick, end_tick=None))
    first = dict(lineage=1, blockers=0, energy=100, water=100, energy_required=80, water_required=40,
                 immature_flowers=0, spent_flowers=0, ready_flowers=1, flower_index=0,
                 cooldown=0, seed_count=7, stress=0, sun_strength=100, produced=True)
    second = first | dict(lineage=2, blockers=4, seed_count=8, produced=False)
    data = dict(schema='garden-reproduction-access-v1', complete=True,
                first_tick_exclusive=access.FIRST, end_tick=access.END, cadence=access.CADENCE,
                samples=access.SAMPLES, seed_capacity=8, lineage_limit=128, opening_limit=512,
                lineages=[dict(lineage=1, masks={'0': 1, '4': access.SAMPLES - 1}),
                          dict(lineage=2, masks={'4': access.SAMPLES})],
                openings=[dict(tick=tick, visits=[first, second])])
    return data, final


class ReproductionTests(unittest.TestCase):
    def test_fixed_four_call_scope(self):
        calls = access.roster()
        self.assertEqual(len(calls), 4)
        self.assertEqual(len({c['id'] for c in calls}), 4)
        self.assertEqual({(c['policy'], c['mode']) for c in calls},
                         {(p, m) for p in ('original', 'fewest') for m in ('off', 'on')})
        for call in calls:
            self.assertEqual(access.arguments(call), ['--reproduction-panel', '9a903368', 'condition',
                                                     call['policy'], call['mode']])
        self.assertEqual((access.SAMPLES, access.CADENCE), (6656, 60))

    def test_exact_order_distinguishes_lost_opening_from_full_bank(self):
        data, final = fixture()
        result = access.validate_trace(data, final)
        self.assertEqual(result['opening_ticks'], 1)
        self.assertEqual(result['families']['1']['produced'], 1)
        shrub = result['lineages']['2']
        self.assertEqual(shrub['bank_only'], access.SAMPLES)
        self.assertEqual(shrub['bank_only_after_earlier_purchase'], 1)
        self.assertEqual(shrub['sees_open'], 0)
        self.assertEqual(result['bank_only_losses'], [dict(tick=access.FIRST + 60, lineage=2, earlier_buyers=[1])])
        self.assertEqual(access.occupancy(final, access.FIRST), 8)
        self.assertEqual(access.occupancy(final, access.FIRST + 60), 7)
        self.assertEqual(access.occupancy(final, access.FIRST + 120), 8)

    def test_simultaneous_resource_limit_is_not_capacity_only_loss(self):
        data, final = fixture()
        data['openings'][0]['visits'][1].update(energy=10, blockers=132)
        data['lineages'][1]['masks'] = {'4': access.SAMPLES - 1, '132': 1}
        result = access.validate_trace(data, final)
        self.assertEqual(result['lineages']['2']['bank_only_after_earlier_purchase'], 0)
        self.assertEqual(result['lineages']['2']['blockers']['energy'], 1)

    def test_missing_or_duplicate_opening_and_roster_rejected(self):
        data, final = fixture()
        for change in ([], data['openings'] * 2):
            with self.assertRaisesRegex(ValueError, 'coverage'):
                access.validate_trace(data | dict(openings=change), final)
        broken = deepcopy(data)
        broken['openings'][0]['visits'].pop()
        with self.assertRaisesRegex(ValueError, 'missing live'):
            access.validate_trace(broken, final)
        with self.assertRaises(ValueError):
            access.validate_trace(data | dict(lineages=data['lineages'][:1]), final)

    def test_bad_values_order_and_purchase_identity_rejected(self):
        data, final = fixture()
        for fields in (dict(blockers=0), dict(seed_count=7), dict(produced=True),
                       dict(ready_flowers=0), dict(energy=-1), dict(sun_strength=0), dict(lineage=1)):
            broken = deepcopy(data)
            broken['openings'][0]['visits'][1].update(fields)
            with self.assertRaises(ValueError):
                access.validate_trace(broken, final)
        broken = deepcopy(data)
        broken['openings'][0]['visits'].reverse()
        with self.assertRaisesRegex(ValueError, 'occupancy'):
            access.validate_trace(broken, final)
        other = deepcopy(final)
        other['seeds'][-1]['parent'] = 2
        with self.assertRaisesRegex(ValueError, 'purchase receipts'):
            access.validate_trace(data, other)

    def test_histograms_cannot_hide_nonbank_visits_or_missing_living_ticks(self):
        data, final = fixture()
        for masks in ({'4': access.SAMPLES - 1}, {'4': access.SAMPLES - 1, '128': 1},
                      {'4': access.SAMPLES - 1, '6': 1}, {'4': access.SAMPLES - 1, '1024': 1}):
            broken = deepcopy(data)
            broken['lineages'][1]['masks'] = masks
            with self.assertRaises(ValueError):
                access.validate_trace(broken, final)


class PublishedReproductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='published-reproduction-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.out = cls.root / 'evidence'
        cls.archive = access.collect.ROOT / 'benchmarks/garden-seasons/leaf-population-reproduction-results.json.gz'
        assert access.prepare.sha(cls.archive.read_bytes()) == '3258eda497056194975a308f3a8ab79bd8c980afa968cb694b8263033adb226e'
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native calls forbidden')):
            cls.result = access.follow.unpack(cls.archive, cls.out, experiment=access.EXPERIMENT)

    def test_complete_collection_and_resource_timing_mismatch(self):
        self.assertEqual(self.result['calls'], 4)
        original, fewest = (self.result['analyses'][p] for p in ('original', 'fewest'))
        self.assertEqual((original['opening_ticks'], fewest['opening_ticks']), (48, 31))
        self.assertEqual([original['families'][str(f)]['produced'] for f in (1, 2, 3)], [8, 12, 10])
        self.assertEqual([fewest['families'][str(f)]['produced'] for f in (1, 2, 3)], [12, 3, 15])
        shrub = fewest['lineages']['17']
        self.assertEqual((shrub['visits'], shrub['produced'], shrub['bank_only'], shrub['sees_open'],
                          shrub['bank_only_after_earlier_purchase']), (6656, 0, 2142, 8, 16))
        self.assertEqual(shrub['opening_masks'], {'128': 7, '132': 6, '256': 1, '260': 1, '4': 16})
        self.assertEqual(shrub['blockers']['flower'], 0)
        self.assertEqual((original['lineages']['19']['sees_open'], original['lineages']['19']['produced']), (28, 9))

    def test_receipts_expose_actual_thresholds_not_daily_endpoints(self):
        path = self.out / 'runs/9a903368-condition-fewest-on/timeline/reproduction.json'
        trace = json.loads(path.read_bytes())
        rows = [(r['tick'], v) for r in trace['openings'] for v in r['visits'] if v['lineage'] == 17]
        self.assertEqual({(v['energy_required'], v['water_required']) for _, v in rows}, {(208, 184)})
        opened = [(tick / access.score.DAY, v['energy'], v['water'], v['blockers'])
                  for tick, v in rows if v['seed_count'] < 8]
        self.assertEqual(opened, [(152.875, 168, 508, 128), (161.890625, 187, 508, 128),
            (184.875, 172, 508, 128), (191.015625, 44, 503, 128), (191.03125, 50, 508, 128),
            (193.890625, 188, 508, 128), (199.09375, 243, 113, 256), (225.890625, 192, 508, 128)])
        broken = deepcopy(trace)
        broken['openings'][0]['visits'].reverse()
        final = json.loads((path.parent.parent / 'stdout.json').read_bytes())
        with self.assertRaises(ValueError):
            access.validate_trace(broken, final)

    def test_exact_archive_roundtrip_without_simulator(self):
        target = self.root / 'repacked.gz'
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native calls forbidden')):
            access.follow.package(self.out, target, experiment=access.EXPERIMENT)
        self.assertEqual(target.read_bytes(), self.archive.read_bytes())


if __name__ == '__main__':
    unittest.main()
