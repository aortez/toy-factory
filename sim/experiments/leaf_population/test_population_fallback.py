"""Placement identity, frozen recipe, independent blocker rule, and adapter guards."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import population_fallback as fallback


class FallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle, cls.models, cls.size = fallback.inputs()

    def test_fixed_roster(self):
        calls = fallback.roster()
        self.assertEqual(len(calls), 16)
        self.assertEqual(len({c['id'] for c in calls}), 16)
        self.assertEqual({c['seed'] for c in calls}, {'9a903368'})
        self.assertEqual(fallback.follow.DAYS, (0, 32, 192, 208, 220, 222, 224, 256, 384, 512, 608))
        for c in calls:
            self.assertEqual(fallback.arguments(c), ['--fallback-panel', c['seed'], c['variant'], c['policy'], c['mode']])

    def record(self, variant='both'):
        return json.loads(fallback.prepare.blob(self.bundle, f'runs/9a903368-{variant}-on/stdout.json'))

    def wrapped(self):
        old = self.record()
        return old | dict(schema='garden-blocker-fallback-replay-v1',
            controller_assignment='family-repair-and-placement',
            placement_intervention=fallback.IDENTITY.copy(),
            state_hex=fallback.HEADER.hex() + old['state_hex'])

    def test_explicit_identity_projection(self):
        value = self.wrapped()
        projected = fallback.gate_record(value)
        self.assertEqual(projected, self.record())
        fallback.gates.underlying(projected, 'both', self.models, self.size,
                                 fallback.follow.STOP, seed=fallback.SEED, after_tick=0)
        self.assertIn('placement_intervention', value)

    def test_identity_mutations_rejected(self):
        original = self.wrapped()
        changes = [dict(schema='garden-leaf-gate-replay-v1'),
                   dict(controller_assignment='whole-population'),
                   dict(state_hex=original['state_hex'][24:])]
        changes += [dict(placement_intervention=fallback.IDENTITY | {key: value}) for key, value in
                    (('kind', 'other'), ('version', 2), ('founder', 1), ('after_tick', 15), ('tie_break', 'first'))]
        for change in changes:
            with self.assertRaises(ValueError):
                fallback.gate_record(original | change)
        for offset in range(12):
            state = bytearray.fromhex(original['state_hex'])
            state[offset] ^= 1
            with self.assertRaises(ValueError):
                fallback.gate_record(original | dict(state_hex=state.hex()))

    def test_actual_all_blocked_purchase_has_independent_expected_choice(self):
        raw = fallback.prepare.blob(self.bundle, 'runs/9a903368-both-on/timeline/purchases.json')
        value, final = json.loads(raw), self.record()
        fallback.purchase.validate_trace(value, final)
        # Both-repair's retained purchase chose column 6; the new rule chooses
        # column 20. This fixture checks the rule, not an unrun future outcome.
        with self.assertRaisesRegex(ValueError, 'destination'):
            fallback.purchase.validate_trace(value, final, fewest=True)
        changed, history = deepcopy(value), deepcopy(final)
        row = next(r for r in changed['purchases'] if r['parent'] == 2)
        self.assertEqual((row['ordinary'], row['selected']), (4, 4))
        row['selected'] = 5
        seed = next(s for s in history['seeds'] if s['parent'] == 2 and s['birth_tick'] == row['tick'])
        seed['column'] = 20
        fallback.purchase.validate_trace(changed, history, fewest=True)
        with self.assertRaises(ValueError):
            fallback.purchase.validate_trace(changed, history)

    def test_fallback_is_family_scoped_and_keeps_clear_sites(self):
        from test_population_purchases import fixture
        for blocked in (False, True):
            value, final = fixture(blocked)
            self.assertEqual(fallback.purchase.validate_trace(value, final),
                             fallback.purchase.validate_trace(value, final, fewest=True))
        value = json.loads(fallback.prepare.blob(self.bundle, 'runs/9a903368-both-on/timeline/purchases.json'))
        final = self.record()
        # If the focal family were not selected, its original draw remains valid.
        final['family_roots'] = [1] * len(final['family_roots'])
        fallback.purchase.validate_trace(value, final, fewest=True)

    def test_adapters_keep_original_wrappers_and_reject_drift(self):
        folder = fallback.collect.ROOT / 'sim/research_player'
        with mock.patch.object(sys, 'path', [str(folder), *sys.path]):
            spec = importlib.util.spec_from_file_location('fallback_stage', folder / 'stage_fallback.py')
            stage = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(stage)
        files = fallback.prepare.expected_files(fallback.prepare.load_archive())
        for name, adapt, old, new in (
                ('source/sim/garden_landing_run.c', stage.landing, 'step_with_leaf', 'step_with_placement'),
                ('modules/leaf_replay/garden_leaf_replay.c', stage.replay, 'step', 'step_with_fallback')):
            source = files[name].decode()
            adapted = adapt(source)
            self.assertIn('static int ' + old + '(', adapted)
            self.assertIn('static int ' + new + '(', adapted)
            self.assertIn(', NULL);\n}', adapted)
            for wrong in ('', source + source, adapted):
                with self.assertRaises(ValueError):
                    adapt(wrong)


class PublishedFallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='published-fallback-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.out = cls.root / 'evidence'
        cls.archive = fallback.collect.ROOT / 'benchmarks/garden-seasons/leaf-population-fallback-results.json.gz'
        assert fallback.prepare.sha(cls.archive.read_bytes()) == '61381e2a5d72106e54212c78715718b1aef289bb91375518db204e6dfe5418ce'
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('no native calls')):
            cls.result = fallback.follow.unpack(cls.archive, cls.out, experiment=fallback.EXPERIMENT)

    def test_all_arms_and_unchanged_control(self):
        self.assertEqual(self.result['calls'], 16)
        expected = {'none': (0, 0, 0, 0), 'light': (8, 4, 4, 5),
                    'condition': (4, 0, 2, 0), 'both': (0, 6, 0, 3)}
        for v, numbers in expected.items():
            arms = self.result['analyses'][v]
            summaries = [arms[p]['summary'] for p in ('original', 'fewest')]
            credits = [sum(min(2, n) for n in s['renewal']['2']['renewal_children']) for s in summaries]
            living = [s['families'][1]['living'] for s in summaries]
            self.assertEqual(tuple(credits + living), numbers)
        for day in fallback.follow.DAYS:
            name = f'tick-{day * fallback.score.DAY:010d}'
            paths = [self.out / 'runs' / f'9a903368-none-{p}-on/timeline' / name for p in ('original', 'fewest')]
            self.assertEqual(json.loads(paths[0].with_suffix('.json').read_bytes()),
                             fallback.gate_record(json.loads(paths[1].with_suffix('.json').read_bytes())))
            self.assertEqual(paths[0].with_suffix('.raw').read_bytes(), paths[1].with_suffix('.raw').read_bytes())

    def test_seed_handoffs_and_competitors(self):
        a = self.result['analyses']
        original, fewest = [a['both'][p]['purchases']['focal'][0] for p in ('original', 'fewest')]
        self.assertEqual((original['observation']['selected'], fewest['observation']['selected']), (4, 5))
        self.assertEqual(original['retrospective_seed_outcome']['outcome'], 'expired')
        self.assertEqual(fewest['retrospective_seed_outcome']['end_tick'], 218355)
        old, new = [a['condition'][p]['purchases']['focal'][0]['retrospective_seed_outcome']
                    for p in ('original', 'fewest')]
        self.assertEqual((old['column'], new['column']), (15, 14))
        self.assertEqual(old['end_tick'], new['end_tick'])
        self.assertEqual(a['condition']['fewest']['summary']['families'][1]['extinction_tick'], 891720)
        self.assertEqual([f['living'] for f in a['light']['fewest']['summary']['families']], [2, 5, 1])

    def test_exact_archive_roundtrip_without_simulator(self):
        target = self.root / 'repacked.gz'
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('no native calls')):
            fallback.follow.package(self.out, target, experiment=fallback.EXPERIMENT)
        self.assertEqual(target.read_bytes(), self.archive.read_bytes())


if __name__ == '__main__':
    unittest.main()
