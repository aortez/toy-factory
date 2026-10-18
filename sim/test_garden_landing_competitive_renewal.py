#!/usr/bin/env python3
"""Prospective metric boundaries, ledger validation and offline evidence checks."""

import copy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_competitive_renewal as audit
import garden_landing_competitive_renewal_capture as capture

D = audit.DAY
RESULT = audit.ROOT / 'benchmarks/garden-seasons/landing-competitive-renewal-results.json.gz'


def fixture(births=()):
    plants = [dict(id=i, parent=0, birth_tick=0, death_tick=None, species=i % 2,
                   column=i * 3, generation=0, environmental_death=False,
                   seeds_created=0, late_seeds_created=0) for i in range(1, 5)]
    seeds = []
    for parent_id, day, died in births:
        parent = plants[parent_id - 1]
        birth = int(day * D)
        child = dict(id=len(plants) + 1, parent=parent_id, birth_tick=birth,
                     death_tick=int(died * D) if died is not None else None,
                     species=parent['species'], column=len(plants) * 3,
                     generation=parent['generation'] + 1, environmental_death=False,
                     seeds_created=0, late_seeds_created=0)
        seeds.append(dict(parent=parent_id, birth_tick=birth - 480, end_tick=birth,
                          child_id=child['id'], species=child['species'], generation=child['generation'],
                          column=child['column'], outcome='germinated', lifetime_ecology_ticks=8192))
        plants.append(child)
        parent['seeds_created'] += 1
        parent['late_seeds_created'] += 1
    return dict(tick=audit.STOP, lineages=plants, seeds=seeds)


class MetricsTests(unittest.TestCase):
    def test_discrete_post_step_exposure_matches_brute_force(self):
        spans = [(0, 8), (8, 12), (11, None), (5, 5), (21, None)]
        for start, stop in ((0, 16), (7, 8), (8, 12), (13, 20)):
            values = [sum(b <= t and (d is None or t < d) for b, d in spans)
                      for t in range(start + 1, stop + 1)]
            result = audit.exposure(spans, start, stop)
            self.assertEqual(result['plant_ticks'], sum(values))
            self.assertEqual(result['minimum'], min(values))
            self.assertEqual(result['maximum'], max(values))
            self.assertEqual(sum(r['last'] - r['first'] + 1 for r in audit.segments(spans, start, stop)), stop - start)

    def test_survival_death_boundary_and_censoring(self):
        birth = 480 * D
        p = dict(birth_tick=birth, death_tick=audit.STOP)
        self.assertEqual(audit.age_status(p, 32), 'failed')
        self.assertEqual(audit.age_status(p, 16), 'confirmed')
        p['death_tick'] = None
        self.assertEqual(audit.age_status(p, 32), 'confirmed')
        p['birth_tick'] += 15
        self.assertEqual(audit.age_status(p, 32), 'censored')
        p['death_tick'] = audit.STOP
        self.assertEqual(audit.age_status(p, 32), 'recent-dead')

    def test_empty_cohort_and_stable_occupancy_do_not_pass_renewal(self):
        result = audit.analyze(fixture())
        self.assertTrue(result['viability']['passes'])
        self.assertFalse(result['renewal']['passes'])
        self.assertIsNone(result['renewal']['primary']['ages']['32']['survival_rate'])
        self.assertEqual(result['renewal']['deepest_chain'], 0)

    def test_windows_pairs_and_chain_ignore_inherited_generation(self):
        result = fixture(((1, 385, None), (5, 417, None), (6, 449, None)))
        out = audit.analyze(result)
        self.assertTrue(out['renewal']['passes'])
        self.assertEqual(out['renewal']['pairs'], [[5, 6], [6, 7]])
        self.assertEqual(out['renewal']['carry_in_pairs'], [[1, 5]])
        self.assertEqual(out['renewal']['deepest_chain'], 3)
        self.assertEqual([w['births'] for w in out['renewal']['windows']], [[5], [6], [7]])
        shallow = audit.analyze(fixture(((1, 385, None), (1, 417, None), (1, 449, None))))
        self.assertFalse(shallow['renewal']['passes'])
        self.assertEqual(shallow['renewal']['deepest_chain'], 1)

    def test_exact_window_boundaries_and_late_failures(self):
        result = audit.analyze(fixture(((1, 384, None), (1, 416, None), (1, 448, None),
                                       (1, 480, None), (1, 480.5, 481))))
        self.assertEqual([w['births'] for w in result['renewal']['windows']], [[6], [7], [8]])
        late = result['renewal']['late']['ages']['32']
        self.assertEqual(late['recent-dead'], [9])
        self.assertEqual(late['eligible'], 0)
        self.assertIsNone(late['survival_rate'])

    def test_posthumous_seed_can_make_established_pair(self):
        result = fixture(((1, 385, 420), (5, 425, None)))
        result['seeds'][-1]['birth_tick'] = 419 * D
        out = audit.analyze(result)
        self.assertEqual(out['renewal']['pairs'], [[5, 6]])
        self.assertEqual(out['deaths']['after_age_32'], [5])

    def test_adult_death_not_veto_and_exact_population_floor(self):
        result = fixture(((1, 385, None), (5, 417, None), (6, 449, None)))
        result['lineages'][3]['death_tick'] = 450 * D
        out = audit.analyze(result)
        self.assertTrue(out['viability']['passes'])
        self.assertTrue(out['renewal']['passes'])
        self.assertEqual(out['deaths']['baseline'], [4])
        static = fixture()
        self.assertTrue(audit.analyze(static)['viability']['passes'])
        static['lineages'][3]['death_tick'] = audit.STOP
        self.assertFalse(audit.analyze(static)['viability']['passes'])

    def test_absent_population_with_pending_seed_is_not_extinction(self):
        result = fixture(((1, 410, None),))
        result['seeds'][0]['birth_tick'] = 399 * D
        for p in result['lineages'][:4]:
            p['death_tick'] = 400 * D
        out = audit.analyze(result)
        self.assertEqual(out['viability']['empty_intervals'], [[400 * D, 410 * D - 1]])
        self.assertEqual(out['viability']['no_plants_or_seeds'], [])
        self.assertFalse(out['viability']['passes'])
        species = out['diversity']['species']
        self.assertEqual(species['losses']['1'], [400 * D])
        self.assertEqual(species['recoveries'][0]['children'], [5])

    def test_family_replacement_does_not_require_founder_immortality(self):
        result = fixture(((1, 385, None),))
        result['lineages'][0]['death_tick'] = 400 * D
        out = audit.analyze(result)['diversity']
        self.assertEqual(out['family']['retained'], [1, 2, 3, 4])
        self.assertEqual(out['family']['absence_intervals']['1'], [])
        result['lineages'][2]['death_tick'] = 400 * D
        out = audit.analyze(result)['diversity']
        self.assertNotIn(3, out['family']['retained'])
        self.assertTrue(out['family']['variety_retained'])
        self.assertEqual(out['species']['retained'], [0, 1])

    def test_monoculture_is_not_multi_species_success(self):
        result = fixture()
        for p in result['lineages']:
            p['species'] = 0
        out = audit.analyze(result)['diversity']
        self.assertFalse(out['species']['eligible'])
        self.assertIsNone(out['species']['variety_retained'])
        self.assertTrue(out['family']['variety_retained'])

    def test_panel_coverage_is_not_just_a_birth_total(self):
        base = audit.analyze(fixture())
        outcomes = {arm: {key: copy.deepcopy(base) for key in audit.PANEL} for arm in audit.ARMS}
        self.assertFalse(audit.decision(outcomes)['cursor_renewal_advantage'])
        for key in list(audit.PANEL)[:4]:
            outcomes['cursor'][key]['renewal']['passes'] = True
        self.assertFalse(audit.decision(outcomes)['arms']['cursor']['broad_signal'])
        outcomes['cursor'][list(audit.PANEL)[4]]['renewal']['passes'] = True
        self.assertTrue(audit.decision(outcomes)['cursor_renewal_advantage'])
        outcomes['cursor'][list(audit.PANEL)[0]]['diversity']['family']['retained'].remove(1)
        self.assertTrue(audit.decision(outcomes)['diversity_tradeoff'])
        outcomes['cursor'][list(audit.PANEL)[0]]['viability']['passes'] = False
        self.assertFalse(audit.decision(outcomes)['cursor_renewal_advantage'])


class ContractTests(unittest.TestCase):
    def test_protocol_and_sixty_calls_without_native_processes(self):
        with patch('subprocess.run', side_effect=AssertionError('no native')), \
             patch('subprocess.Popen', side_effect=AssertionError('no native')):
            self.assertEqual(audit.digest(audit.ROOT / audit.PROTOCOL), audit.PROTOCOL_SHA)
            calls = [(p, a, k) for p in audit.PHASES for a in audit.ARMS for k in audit.PANEL]
            self.assertEqual(len(calls), 60)
            for phase, arm, key in calls:
                args = audit.arguments(key, arm, phase)
                self.assertEqual(int(args[args.index('--ticks') + 1]), audit.horizon(phase))
                self.assertFalse(any('trace' in arg for arg in args))
                self.assertEqual('--framebuffer' in args, phase != 'plain')
                self.assertEqual('--seed-cursor-after' in args, arm == 'cursor')

    def test_all_saved_anchors_and_population_exposure(self):
        for arm in audit.ARMS:
            for key in audit.PANEL:
                audit.check_result(audit.prior()['runs'][arm][key]['result'], key, arm, 'anchor')

    def test_truncated_reordered_and_inconsistent_ledgers_fail(self):
        key = next(iter(audit.PANEL))
        original = audit.prior()['runs']['cursor'][key]['result']
        for fault in ('plant', 'seed', 'order', 'species', 'cursor', 'exposure', 'history', 'capacity'):
            bad = copy.deepcopy(original)
            if fault == 'plant':
                bad['lineages'].pop()
            elif fault == 'seed':
                bad['seeds'].pop()
            elif fault == 'order':
                bad['lineages'].reverse()
            elif fault == 'species':
                bad['seeds'][0]['species'] = 99
            elif fault == 'cursor':
                bad['seed_cursor_probe']['last_buyer'] += 1
            elif fault == 'exposure':
                bad['descendant_live_ticks'] += 1
            elif fault == 'history':
                bad['lineages'][0]['column'] += 1
            else:
                bad['plant_slots'] = 9
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                audit.check_result(bad, key, 'cursor', 'anchor')

    def test_only_cli_bound_and_help_may_change(self):
        # Exercise the historical transform with a controlled source fixture;
        # today's CLI can legitimately acquire later, separately scoped probes.
        source = copy.deepcopy(audit.prior()['source_sha256'])
        old_text = (b'unchanged logic\n(384U * TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS)\n'
                    b'0..1474560 logic ticks (384 Garden days)\n')
        source['sim/garden_landing_cli.c'] = hashlib.sha256(old_text).hexdigest()
        before = copy.deepcopy(source)
        text = old_text.replace(b'384U', b'512U').replace(b'0..1474560 logic ticks (384 Garden days)',
                                                        b'0..1966080 logic ticks (512 Garden days)')
        source['sim/garden_landing_cli.c'] = hashlib.sha256(text).hexdigest()
        with patch.object(audit, 'prior', return_value={'source_sha256': before}):
            capture.check_runtime(source, text)
            source['src/garden_world.c'] = '0' * 64
            with self.assertRaises(RuntimeError):
                capture.check_runtime(source, text)
            source['src/garden_world.c'] = before['src/garden_world.c']
            changed = text + b'changed logic\n'
            source['sim/garden_landing_cli.c'] = hashlib.sha256(changed).hexdigest()
            with self.assertRaisesRegex(RuntimeError, 'beyond limit/help'):
                capture.check_runtime(source, changed)

    def test_existing_bundle_rejected_before_execution(self):
        with tempfile.TemporaryDirectory(prefix='renewal-no-clobber-') as temp, \
             patch('subprocess.run', side_effect=AssertionError('no native')):
            root = Path(temp)
            with self.assertRaises(RuntimeError):
                capture.collect(root, root / 'out.gz', root, root, 1)


@unittest.skipUnless(RESULT.exists(), 'follow-up has not been collected')
class CapturedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(RESULT, 'rt') as stream:
            cls.value = json.load(stream)

    def test_portable_verification_is_offline(self):
        with patch('subprocess.run', side_effect=AssertionError('no native')), \
             patch('subprocess.Popen', side_effect=AssertionError('no native')):
            audit.check_capture(self.value)

    def test_rehashed_missing_calls_and_changed_outcomes_fail(self):
        key = next(iter(audit.PANEL))
        for fault in ('missing', 'anchor', 'outcome', 'image', 'prefix'):
            bad = copy.deepcopy(self.value)
            if fault == 'missing':
                del bad['runs']['plain']['fixed'][key]
            elif fault == 'anchor':
                bad['runs']['anchor']['cursor'][key]['result']['world_hash'] = '00000000'
            elif fault == 'outcome':
                bad['outcomes']['cursor'][key]['renewal']['passes'] ^= True
            elif fault == 'image':
                bad['runs']['repeat']['cursor'][key]['frame']['sha256'] = '0' * 64
            else:
                bad['runs']['endpoint']['cursor'][key]['result']['lineages'][0]['column'] += 1
            bad['receipt_sha256'] = audit.fingerprint({k: v for k, v in bad.items() if k != 'receipt_sha256'})
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                audit.check_capture(bad)

    def test_new_natural_death_cannot_be_relabelled_as_imposed(self):
        key = '3a7e45e6-rainfed'
        result = copy.deepcopy(self.value['runs']['endpoint']['cursor'][key]['result'])
        plant = next(p for p in result['lineages'] if p['death_tick'] is not None and p['death_tick'] > audit.BASE)
        plant['environmental_death'] = True
        with self.assertRaisesRegex(RuntimeError, 'unreceipted imposed death'):
            audit.check_result(result, key, 'cursor', 'endpoint')


if __name__ == '__main__':
    unittest.main()
