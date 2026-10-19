"""Fresh seeds, exact threshold models, predeclared criteria and offline sweep checks."""

from contextlib import contextmanager
from fractions import Fraction
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
from xml.etree import ElementTree

import local_results
import population_sweep as sweep
import sweep_evidence as evidence
import sweep_figure

score = sweep.score
ARCHIVE = sweep.collect.ROOT / 'benchmarks/garden-seasons/leaf-population-threshold-sweep-results.json.gz'
ARCHIVE_SHA = 'd42463565e814398d9d80cddaab5a6916937505362da21d53762b5923e36159e'


@lru_cache
def named():
    _, models, _ = sweep.collect.archive_inputs()
    return models


def row(policy, seed, layout, *, late=Fraction(1, 12), extinct=0, retained=(True, True, True)):
    founders = score.LAYOUTS[layout]
    status = ['extinct'] * extinct + ['living'] * (founders - extinct)
    return dict(id=f'{policy}-{seed}-{layout}', policy=policy, seed=seed, layout=layout,
                renewal={start: score.rational(late) for start in ('192', '576', '960')},
                closing_window_families=1, family_status=status, retained_species=list(retained),
                living=8, pending=8, offspring_born=10, established_offspring=8,
                died_before_establishment=2, deaths=12, empty_living_intervals=0,
                extinction_tick=None)


def panel(names, **overrides):
    return [row(p, s, l, **overrides.get(p, {})) for s in sweep.seeds() for l in score.LAYOUTS
            for p in names]


class SweepTests(unittest.TestCase):
    def test_seeds_follow_the_fixed_label_rule(self):
        seeds = sweep.seeds()
        self.assertEqual(len(set(seeds)), sweep.SEED_COUNT)
        digest = hashlib.sha256(b'toy-factory/garden-repair-threshold-sweep-v1/weather-01').digest()
        self.assertEqual(seeds[0], f"{int.from_bytes(digest[:4], 'little'):08x}")
        self.assertEqual(seeds[0], '457e75c9')
        self.assertTrue(set(seeds).isdisjoint(score.SEEDS))

    def test_threshold_models_change_only_the_light_bias(self):
        base = sweep.leaf_model.decode(named()['initial'])
        models = sweep.policies(named())
        self.assertEqual(list(models), [f'light-{f:03d}' for f in sweep.FEATURES] + list(sweep.REFERENCES))
        self.assertEqual(models['light-065'], named()['initial'])
        for feature in sweep.FEATURES:
            with self.subTest(feature=feature):
                model = sweep.leaf_model.decode(models[f'light-{feature:03d}'])
                self.assertEqual(model.hidden_bias, (64 * feature,) + base.hidden_bias[1:])
                self.assertEqual((model.hidden_weights, model.action_bias, model.action_weights),
                                 (base.hidden_weights, base.action_bias, base.action_weights))
        with self.assertRaises(ValueError):
            sweep.threshold_model(named()['initial'], 129)
        with self.assertRaises(ValueError):
            sweep.threshold_model(named()['s1-g3-c4'], 65)

    def test_verified_gates_match_the_exact_network(self):
        models = sweep.policies(named())
        self.assertEqual(sweep.verify_model(models['light-065'], 65),
                         dict(feature=65, light_minimum=131, condition_maximum=192))
        self.assertEqual(sweep.verify_model(models['light-071'], 71)['light_minimum'], 143)
        self.assertEqual(sweep.verify_model(models['light-000'], 0)['light_minimum'], 0)
        self.assertEqual(sweep.verify_model(models['light-128'], 128),
                         dict(feature=128, light_minimum=None, condition_maximum=None))
        with self.assertRaises(ValueError):
            sweep.verify_model(models['light-068'], 65)
        for feature in sweep.FEATURES[:-1]:
            minimum = sweep.light_minimum(feature)
            self.assertGreaterEqual(minimum * 127 // 255, feature)
            self.assertTrue(minimum == 0 or (minimum - 1) * 127 // 255 < feature)

    def test_roster_covers_every_policy_seed_and_layout_once(self):
        names = list(sweep.policies(named()))
        plan = sweep.roster(names)
        self.assertEqual(len(plan), 14 * 16 * 2)
        self.assertEqual(len({c['id'] for c in plan}), len(plan))
        self.assertEqual({(c['policy'], c['seed'], c['layout']) for c in plan},
                         {(p, s, l) for p in names for s in sweep.seeds() for l in score.LAYOUTS})

    def test_aggregate_weights_worlds_and_rejects_incomplete_panels(self):
        names = ['light-065', 'light-080', 's1-g3-c4']
        rows = panel(names, **{'light-080': dict(late=Fraction(1, 6), extinct=1,
                                                retained=(True, False, False))})
        result = sweep.aggregate(rows, names)
        self.assertEqual(result['light-065']['late_renewal'], 1 / 12)
        self.assertEqual(result['light-080']['late_renewal'], 1 / 6)
        self.assertEqual(result['light-080']['extinct_families'], 32)
        self.assertEqual(result['light-080']['single_species_gardens'], 32)
        self.assertEqual(result['light-080']['shrub_gardens'], 0)
        self.assertEqual(result['light-065']['founders'], 16 * 8)
        self.assertEqual(result['light-080']['extinct_minus_fixed'], [2.0, 2.0])
        self.assertEqual(result, sweep.aggregate(rows, names))
        with self.assertRaises(ValueError):
            sweep.aggregate(rows[1:], names)
        with self.assertRaises(ValueError):
            sweep.aggregate(rows + rows[:1], names)

    def test_decision_requires_search_renewal_and_fixed_wear_variety(self):
        names = ['light-065', 'light-071', 'light-080', 's1-g3-c4']
        search = dict(late=Fraction(1, 6), extinct=1)
        cases = {
            'both': ({'light-071': dict(late=Fraction(1, 6))}, ['light-071']),
            'too little renewal': ({'light-071': dict(late=Fraction(1, 7))}, []),
            'more family losses': ({'light-071': dict(late=Fraction(1, 6), extinct=1)}, []),
            'single species': ({'light-071': dict(late=Fraction(1, 6),
                                                   retained=(True, False, False))}, []),
        }
        for name, (overrides, both) in cases.items():
            with self.subTest(case=name):
                rows = panel(names, **{'s1-g3-c4': search, **overrides})
                decision = sweep.decide(sweep.aggregate(rows, names))
                self.assertEqual(decision, dict(tradeoff_reproduced=True, both=both))
        rows = panel(names, **{'s1-g3-c4': search})
        rows = [r | dict(empty_living_intervals=1) if r['policy'] == 'light-080' else r for r in rows]
        rows = [r | dict(renewal={k: score.rational(Fraction(1, 6)) for k in r['renewal']})
                if r['policy'] == 'light-080' else r for r in rows]
        self.assertEqual(sweep.decide(sweep.aggregate(rows, names))['both'], [])
        flat = sweep.decide(sweep.aggregate(panel(names), names))
        self.assertFalse(flat['tradeoff_reproduced'])
        self.assertEqual(flat['both'], names[:3])

    def test_figure_is_well_formed_and_states_the_decision(self):
        names = ['light-000', 'light-065', 'light-071', 'light-128', 's1-g3-c4', 's2-g3-c1']
        started = dict(thresholds={p: dict(light_minimum=sweep.light_minimum(int(p[6:])))
                                   for p in names if p.startswith('light-')})
        for overrides, title in (({}, 'Light settings 0, 131, 143, never match'),
                                 ({'s1-g3-c4': dict(late=Fraction(1, 6), extinct=1)},
                                  'No light setting matches')):
            with self.subTest(title=title):
                analysis = sweep.aggregate(panel(names, **overrides), names)
                svg = sweep_figure.render(dict(analysis=analysis, decision=sweep.decide(analysis)),
                                          started)
                root = ElementTree.fromstring(svg)
                self.assertTrue(root.find('{http://www.w3.org/2000/svg}title').text.startswith(title))
                self.assertEqual(svg, sweep_figure.render(
                    dict(analysis=analysis, decision=sweep.decide(analysis)), started))
                dashed = [e for e in root.iter('{http://www.w3.org/2000/svg}path')
                          if e.get('stroke-dasharray') and e.get('stroke-width') == '2']
                self.assertEqual(len(dashed), 2)
        self.assertEqual(sweep_figure.ticks(0, 0.17, 6)[0], [0, 0.05, 0.1, 0.15, 0.2])
        self.assertEqual(sweep_figure.ticks(94, 132, 8)[0], list(range(90, 136, 5)))
        self.assertTrue(sweep_figure.crosses((0, 0, 10, 10), ((-5, 5), (15, 5))))
        self.assertFalse(sweep_figure.crosses((0, 0, 10, 10), ((-5, 12), (15, 12))))


@local_results.needs('leaf-population-results.json.gz', 'leaf-population-threshold-sweep-results.json.gz')
class SweepEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='garden-threshold-sweep-test-')
        cls.root = Path(cls.temporary.name) / 'evidence'
        if sweep.prepare.sha(ARCHIVE.read_bytes()) != ARCHIVE_SHA:
            raise ValueError('published evidence identity differs')
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('native execution forbidden')):
            cls.checked = evidence.unpack(ARCHIVE, cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    @contextmanager
    def changed_json(self, name, mutate):
        path, manifest_path = self.root / name, self.root / 'manifest.json'
        before, manifest_before = path.read_bytes(), manifest_path.read_bytes()
        try:
            value = json.loads(before)
            mutate(value)
            path.write_text(json.dumps(value))
            manifest = json.loads(manifest_before)
            manifest['files'][name] = sweep.prepare.sha(path.read_bytes())
            manifest_path.write_text(json.dumps(manifest))
            yield
        finally:
            path.write_bytes(before)
            manifest_path.write_bytes(manifest_before)

    def test_published_sweep_recomputes_without_execution(self):
        self.assertEqual(self.checked, dict(calls=448, decision=dict(tradeoff_reproduced=True, both=[])))
        analysis = json.loads((self.root / 'result.json').read_bytes())['analysis']
        self.assertEqual({p: analysis[p]['extinct_families'] for p in ('light-048', 'light-065', 's1-g3-c4')},
                         {'light-048': 23, 'light-065': 42, 's1-g3-c4': 72})
        self.assertEqual(analysis['light-065']['renewal']['960'], [1, 72])
        self.assertEqual(analysis['s1-g3-c4']['renewal']['960'], [383, 2880])

    def test_changed_receipts_and_extra_files_rejected(self):
        call = sweep.roster(list(sweep.policies(named())))[0]['id']
        with self.changed_json(f'runs/{call}/process.json', lambda r: r['args'].__setitem__(2, 'deadbeef')):
            with self.assertRaisesRegex(ValueError, 'arguments'):
                evidence.verify(self.root)
        with self.changed_json('started.json', lambda r: r.update(workers=13)):
            with self.assertRaisesRegex(ValueError, 'protocol'):
                evidence.verify(self.root)
        extra = self.root / 'runs' / 'unplanned.json'
        extra.write_text('{}')
        try:
            with self.assertRaisesRegex(ValueError, 'evidence files'):
                evidence.verify(self.root)
        finally:
            extra.unlink()

    def test_unsafe_archive_and_existing_target_refused_before_creation(self):
        target = Path(self.temporary.name) / 'unsafe'
        raw, digest = b'bad', sweep.prepare.sha(b'bad')
        bundle = dict(schema=evidence.EVIDENCE, files={'../escape': digest}, blobs={digest: raw.hex()})
        archive = Path(self.temporary.name) / 'unsafe.json.gz'
        archive.write_bytes(gzip.compress(json.dumps(bundle).encode()))
        with self.assertRaisesRegex(ValueError, 'unsafe archive path'):
            evidence.unpack(archive, target)
        self.assertFalse(target.exists())
        with self.assertRaisesRegex(ValueError, 'fresh unpack'):
            evidence.unpack(ARCHIVE, self.root)


if __name__ == '__main__':
    unittest.main()
