#!/usr/bin/env python3
"""Passive direction framing/neutrality and conservative endpoint analysis."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_directions as probe
from test_garden_landing_tools import run

BUILD = None
RESULT = probe.ROOT / 'benchmarks/garden-seasons/landing-directions-results.json.gz'


def fixture():
    bitmap = bytearray(39)
    bitmap[1] = 16
    d = {'id': 1, 'tip': 2, 'at': [104, 144], 'order': [0, 1, 2], 'root_cells': bitmap.hex(),
         'candidates': [[dx, dy, 104 + dx, 144 + dy, 0, water, 16, 3]
                        for (dx, dy), water in zip(probe.STEPS[1], [1, 9, 1], strict=True)]}
    b = {'id': 1, 'tip': 2, 'tissue': 1, 'roots': 2, 'available': 3, 'action': 1, 'water': 8,
         'water_gate': {'destination': [100, 149, 1], 'active': True, 'upkeep': 1, 'cost': 5, 'tip_moisture': 1}}
    return b, d


class DirectionTests(unittest.TestCase):
    def test_canonical_ranking_and_root_cells(self):
        b, d = fixture()
        self.assertEqual(probe.check_direction(b, d), (0, [0, 1, 2], {12}))
        self.assertEqual(probe.root_cell(8, 144), 0)
        self.assertEqual(probe.root_cell(231, 231), 307)
        self.assertNotIn(probe.root_cell(100, 149), probe.own_cells(d))
        self.assertIn(probe.root_cell(104, 150), probe.own_cells(d))
        for x, y in ((7, 144), (232, 144), (8, 143), (8, 232)):
            with self.assertRaises(RuntimeError): probe.root_cell(x, y)

    def test_unavailable_first_choice_falls_through_ranking(self):
        b, d = fixture()
        d['candidates'][0][6:] = [4, 5]
        b['available'] = 2
        b['water_gate']['destination'] = [104, 150, 9]
        self.assertEqual(probe.check_direction(b, d)[0], 1)

    def test_first_day_guard_is_not_just_purchase_price(self):
        b, d = fixture()
        self.assertFalse(probe.water_allowed(b, d['candidates'][0]))
        self.assertTrue(probe.water_allowed(b, d['candidates'][1]))
        b['water'] = 5
        self.assertFalse(probe.water_allowed(b, d['candidates'][1]))
        b['water_gate']['active'] = False
        self.assertTrue(probe.water_allowed(b, d['candidates'][0]))

    def test_malformed_endpoint_order_and_bitmap_rejected(self):
        for kind in ('duplicate', 'missing', 'endpoint', 'flags', 'padding', 'empty', 'destination', 'count'):
            b, d = fixture()
            if kind == 'duplicate': d['order'][0] = 1
            elif kind == 'missing': d['candidates'].pop()
            elif kind == 'endpoint': d['candidates'][0][2] += 1
            elif kind == 'flags': d['candidates'][0][7] = 1
            elif kind == 'padding': d['root_cells'] = d['root_cells'][:-2] + 'f0'
            elif kind == 'empty': d['root_cells'] = '00' * 39
            elif kind == 'destination': b['water_gate']['destination'][0] += 1
            else: b['available'] = 2
            with self.subTest(kind=kind), self.assertRaises(RuntimeError): probe.check_direction(b, d)

    def test_nonextend_has_no_selected_endpoint(self):
        b, d = fixture()
        b['action'] = 2
        b['water_gate']['destination'] = None
        d['order'] = []
        self.assertIsNone(probe.check_direction(b, d)[0])


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='garden-directions-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.case = probe.previous.cases()[0]['case']

    def args(self, path, enabled):
        path.mkdir()
        (path / 'frames').mkdir()
        (path / 'model.tgl').write_bytes(probe.population.load_model()[1])
        return [BUILD / 'toy-factory-garden-landing',
                *probe.population.arguments(self.case, 'candidate', 'trace', stop=3840),
                *(['--direction-trace', 'direction.jsonl'] if enabled else [])]

    def test_full_day_on_off_byte_neutrality_and_complete_directions(self):
        a, b = self.root / 'on', self.root / 'off'
        observed = json.loads(run(self.args(a, True), cwd=a))
        plain = json.loads(run(self.args(b, False), cwd=b))
        self.assertEqual(observed, plain)
        prefix = probe.population.stem(self.case, 'candidate', 'trace')
        for name in (prefix + '-stand.jsonl', prefix + '-adult.jsonl', 'frames/' + prefix + '.raw'):
            self.assertEqual((a / name).read_bytes(), (b / name).read_bytes())
        rows = [json.loads(r) for r in (a / 'direction.jsonl').read_text().splitlines()]
        self.assertEqual(rows[0], {'schema': 'landing-directions-v1', 'start': 15, 'stop': 3840})
        self.assertEqual(rows[-1], {'complete': True, 'tick': 3840, 'run_hash': observed['run_hash']})
        self.assertEqual([r['tick'] for r in rows[1:-1]], list(range(15, 3841, 15)))
        stands = list(probe.population.trace_rows(a / (prefix + '-stand.jsonl'), 'stand', observed))
        adults = list(probe.population.trace_rows(a / (prefix + '-adult.jsonl'), 'adult', observed))
        lives = {p['id']: p for p in observed['lineages']}
        assessed = 0
        for row, stand, adult in zip(rows[1:-1], stands, adults, strict=True):
            self.assertEqual(len(row['bids']), len(stand['bids']))
            for bid, direction in zip(stand['bids'], row['bids'], strict=True):
                probe.check_direction(bid, direction)
            for p in adult['plants']:
                if p['stages'][2][0] == p['stages'][3][0]: continue
                e = {'id': p['id'], 'tick': row['tick'], 'sun': adult['sun'], 'resource': p,
                     'body': next(b for b in stand['bodies'] if b['id'] == p['id']),
                     'bids': [b for b in stand['bids'] if b['id'] == p['id']],
                     'directions': [d for d in row['bids'] if d['id'] == p['id']]}
                probe.assess(e, lives[p['id']], 'candidate')
                assessed += 1
        self.assertGreater(assessed, 50)
        saved = {'result': observed, 'analysis': probe.population.analyze(
            a / (prefix + '-stand.jsonl'), a / (prefix + '-adult.jsonl'), observed, self.case, 'candidate')}
        traces = {}
        for kind, name in (('stand', prefix + '-stand.jsonl'), ('adult', prefix + '-adult.jsonl'),
                           ('direction', 'direction.jsonl')):
            probe.compress(a / name, a / (name + '.gz'))
            traces[kind] = {'path': name + '.gz'}
        with patch.object(probe, 'STOP', 3840):
            analysis = probe.analyze_raw(a, saved, 'candidate', {'traces': traces})
        self.assertEqual(len(analysis['events']), assessed)
        broken = copy.deepcopy(analysis)
        broken['events'].pop()
        with self.assertRaises(RuntimeError): probe.check_analysis(broken, saved, 'candidate')

    def test_missing_dawn_or_stand_rejected_before_creating_file(self):
        for kind in ('dawn', 'stand'):
            path = self.root / kind
            args = self.args(path, True)
            if kind == 'dawn': args.remove('--stand-dawn')
            else:
                for flag in ('--stand-trace', '--stand-start', '--stand-stop'):
                    j = args.index(flag)
                    del args[j:j + 2]
            run(args, valid=False, cwd=path)
            self.assertFalse((path / 'direction.jsonl').exists())

    def test_no_clobber(self):
        path = self.root / 'exists'
        args = self.args(path, True)
        (path / 'direction.jsonl').write_text('keep')
        run(args, valid=False, cwd=path)
        self.assertEqual((path / 'direction.jsonl').read_text(), 'keep')


@unittest.skipUnless(RESULT.exists(), 'direction capture not yet available')
class SavedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(RESULT, 'rt') as stream:
            cls.value = json.load(stream)

    def test_complete_offline_saved_check(self):
        with patch('subprocess.Popen', side_effect=AssertionError('offline only')):
            probe.check_value(self.value)
        bad = copy.deepcopy(self.value)
        bad['cases'][0]['arms']['candidate']['analysis']['events'].pop()
        with self.assertRaises(RuntimeError): probe.check_value(bad)

    def test_frozen_coverage_and_endpoint_opportunities(self):
        expected = {
            ('fixed', 'control'): (753, 303, 57, 61, 267, 5),
            ('fixed', 'candidate'): (1180, 476, 106, 114, 390, 8),
            ('rotating', 'control'): (886, 362, 71, 74, 301, 7),
            ('rotating', 'candidate'): (1133, 461, 112, 113, 377, 7),
        }
        totals = dict.fromkeys(('frames', 'bids', 'candidates'), 0)
        for entry in self.value['cases']:
            for arm, data in entry['arms'].items():
                a = data['analysis']
                root, shoot = a['summary']['all/root'], a['summary']['all/shoot']
                key = (entry['case']['order'], arm)
                with self.subTest(world=key):
                    self.assertEqual((len(a['events']), root['allocations'], root['better_quantum'],
                                      root['reuse_with_new_not_drier'], shoot['leaf_allocations'],
                                      shoot['better_leaf_quantum']), expected[key])
                    self.assertEqual(root['fallback'] + shoot['fallback'], 0)
                    self.assertEqual(root.get('closure_policy_finish', 0) +
                                     shoot.get('closure_policy_finish', 0), 0)
                    self.assertEqual(root['legal_but_water_denied'], 2 if arm == 'candidate' else 0)
                for k in totals: totals[k] += a['counts'][k]
        self.assertEqual(totals, {'frames': 262144, 'bids': 2443220, 'candidates': 9670816})

    def test_focal_light_limits_and_wet_root_witness(self):
        for entry in self.value['cases']:
            a = entry['arms']['candidate']['analysis']
            for i, n in ((15, 15), (16, 14), (28, 14)):
                shoot = a['summary'][f'plant-{i}/shoot']
                self.assertEqual((shoot['allocations'], shoot['better_resource'], shoot['better_quantum']),
                                 (n, 0, 0))
            mature = [e for e in a['events'] if e['id'] == 28]
            self.assertEqual((mature[0]['tick'], mature[-1]['tick']), (648405, 649245))
            self.assertEqual([(e['tick'], e['assessment']['closure']) for e in mature
                              if 'closure' in e['assessment']],
                             [(648855, 'maximum_depth'), (649065, 'blocked'), (649245, 'maximum_depth')])
            self.assertEqual((mature[-1]['body']['nodes'], mature[-1]['body']['tips']), (30, []))
            self.assertEqual(a['summary']['plant-9/root']['allocations'], 1)
            self.assertEqual(a['summary']['plant-9/root']['better_quantum'], 0)
            self.assertEqual(a['summary']['plant-9/shoot']['allocations'], 27)
            e = next(e for e in a['events'] if e['id'] == 15 and e['tick'] == 460965)
            assessment = e['assessment']
            d = next(d for d in e['directions'] if d['tip'] == assessment['tip'])
            self.assertEqual(d['at'], [167, 149])
            self.assertEqual(d['order'], [1, 2, 0])
            self.assertEqual(d['candidates'][1][2:6], [167, 155, 0, 0])
            self.assertEqual(d['candidates'][2][2:6], [171, 154, 0, 7])
            self.assertEqual(assessment['cost'], [7, 5])
            self.assertEqual(assessment['selected_quantum'], 0)
            self.assertEqual(assessment['better_quantum'], [2])
            self.assertFalse(assessment['new_cell'])
            self.assertEqual(assessment['new_cell_not_drier'], [2])

    def test_corrupt_construction_receipts_and_extra_calls_rejected(self):
        entry = self.value['cases'][0]
        a = entry['arms']['candidate']['analysis']
        saved = probe.inputs()[0]['arms']['candidate']
        e = next(e for e in a['events'] if e['id'] == 15 and e['tick'] == 460965)
        life = next(p for p in saved['result']['lineages'] if p['id'] == e['id'])
        for kind in ('rank', 'cost', 'endpoint', 'clock'):
            bad = copy.deepcopy(e)
            d = next(d for d in bad['directions'] if d['tip'] == bad['assessment']['tip'])
            if kind == 'rank': d['order'] = [1, 1, 0]
            elif kind == 'cost': bad['resource']['stages'][3][1] += 1
            elif kind == 'endpoint': d['candidates'][1][2] += 1
            else: bad['sun'][0] += 1
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                probe.assess(bad, life, 'candidate')
        with self.assertRaises(RuntimeError):
            probe.check_value({**self.value, 'full_replays': 9})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path, required=True)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *rest])
