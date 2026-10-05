#!/usr/bin/env python3
"""Frozen cohorts, prefix recovery, framing, fresh outputs and offline verification."""

import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_followup as followup

RESULT = followup.ROOT / 'benchmarks/garden-seasons/landing-followup-results.json.gz'


def life(identity, birth=0, death=None, parent=0):
    return dict(id=identity, birth_tick=birth, death_tick=death, parent=parent,
                seeds_created=0, late_seeds_created=0)


class FollowupTests(unittest.TestCase):
    def test_panel_and_fixed_repeat_selection(self):
        self.assertEqual([len(followup.calls(p)) for p in followup.PHASES], [32, 32, 4])
        self.assertEqual({w['arm'] for _, w in followup.calls('repeat')}, set(followup.previous.late.ARMS))
        self.assertTrue(all(followup.repeated(w) for _, w in followup.calls('repeat')))
        with self.assertRaises(RuntimeError):
            followup.calls('extra')

    def test_arguments_change_only_horizon_and_observers(self):
        for _, world in followup.calls('baseline'):
            old = world['run']['args']
            for phase in followup.PHASES:
                args = followup.arguments(world, phase)
                self.assertNotIn('--uptake-trace', args)
                self.assertNotIn('--uptake-window', args)
                self.assertEqual(args[args.index('--stand-start') + 1], str(followup.BASE))
                stop = followup.BASE if phase == 'baseline' else followup.STOP
                self.assertEqual(args[args.index('--ticks') + 1], str(stop))
                for flag in ('--root-dawn-reserve', '--root-allocation-focal', '--seed-order'):
                    self.assertEqual(flag in args, flag in old)

    def test_saved_results_validate_without_native_execution(self):
        with patch('subprocess.run', side_effect=AssertionError('no native calls')), \
             patch('subprocess.Popen', side_effect=AssertionError('no native calls')):
            for _, world in followup.calls('baseline'):
                followup.validate_result(world['run']['result'], world, followup.BASE)

    def test_prefix_reverses_future_fates_counts_and_births(self):
        base = followup.BASE
        result = dict(lineages=[life(1, death=base + 15), life(2, base + 15, parent=1)],
                      seeds=[dict(parent=1, birth_tick=base - 15, end_tick=base + 15,
                                  child_id=2, outcome='germinated'),
                             dict(parent=1, birth_tick=base + 15, end_tick=None,
                                  child_id=None, outcome='pending')])
        original = copy.deepcopy(result)
        lives, seeds = followup.prefix_ledgers(result)
        self.assertEqual(len(lives), 1)
        self.assertIsNone(lives[0]['death_tick'])
        self.assertEqual(lives[0]['seeds_created'], 1)
        self.assertEqual(lives[0]['late_seeds_created'], 1)
        self.assertEqual(len(seeds), 1)
        self.assertEqual((seeds[0]['outcome'], seeds[0]['end_tick'], seeds[0]['child_id']), ('pending', None, None))
        self.assertEqual(result, original)

    def test_prefix_keeps_events_exactly_on_old_boundary(self):
        base = followup.BASE
        result = dict(lineages=[life(1, death=base), life(2, birth=base, parent=1)],
                      seeds=[dict(parent=1, birth_tick=15, end_tick=base, child_id=2, outcome='germinated')])
        lives, seeds = followup.prefix_ledgers(result)
        self.assertEqual(lives[0]['death_tick'], base)
        self.assertEqual(lives[1]['birth_tick'], base)
        self.assertEqual(seeds, result['seeds'])

    def test_prior_immutable_history_is_not_masked(self):
        _, world = followup.calls('baseline')[0]
        for field in ('column', 'generation', 'parent'):
            changed = copy.deepcopy(world['run']['result'])
            changed['lineages'][-1][field] += 1
            with self.assertRaises(RuntimeError):
                followup.validate_result(changed, world, followup.BASE)

    def test_survival_death_on_boundary_fails_and_later_death_passes(self):
        base, day = followup.BASE, followup.DAY
        lives = [life(1, base, base + day), life(2, base, base + 32 * day),
                 life(3, base - 15, base + 32 * day), life(4, base + 15)]
        records = followup.cohort(dict(lineages=lives, seeds=[]), [1, 2, 3, 4])
        self.assertEqual(records[0]['survival']['1'], 'died')
        self.assertEqual(records[1]['survival']['32'], 'died')
        self.assertEqual(records[2]['survival']['32'], 'confirmed')
        self.assertEqual(records[3]['survival']['32'], 'censored')

    def test_ever_and_extension_reproduction_are_distinct(self):
        base = followup.BASE
        lives = [life(1), life(2, base - 15, parent=1), life(3, base + 15, parent=1)]
        seeds = [dict(parent=1, birth_tick=base), dict(parent=1, birth_tick=base + 15)]
        record = followup.cohort(dict(lineages=lives, seeds=seeds), [1])[0]
        self.assertEqual(record['children'], [2, 3])
        self.assertEqual(record['extension_children'], [3])
        self.assertEqual(record['extension_purchases'], 1)
        self.assertEqual(record['one_day_children'], [2, 3])

    def write_trace(self, root, rows):
        path = root / 'trace.jsonl.gz'
        with gzip.open(path, 'wt') as stream:
            for row in rows:
                stream.write(json.dumps(row) + '\n')
        return path

    def test_trace_framing_and_boundary(self):
        base = followup.BASE
        rows = [dict(schema='landing-adult-resources-v1', start=base, stop=base + 15),
                dict(tick=base), dict(tick=base + 15), dict(complete=True, tick=base + 15)]
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_trace(Path(tmp), rows)
            receipt = followup.trace_receipt(path, 'adult', base, base + 15, {})
            self.assertEqual(receipt['boundary_sha256'], followup.fingerprint(rows[1]))
            self.assertEqual(len(list(followup.trace_rows(path, 'adult', base, base + 15, {}))), 2)
            for bad in (rows[:-1], rows[:2] + rows[3:], rows + [rows[-1]],
                        [rows[0], rows[2], rows[1], rows[3]]):
                path = self.write_trace(Path(tmp), bad)
                with self.assertRaises((RuntimeError, ValueError)):
                    list(followup.trace_rows(path, 'adult', base, base + 15, {}))

    def test_reach_prefix_excludes_new_steps_and_footer(self):
        rows = [dict(schema='landing-reach-trace-v1'), dict(tick=15), dict(tick=30), dict(tick=45),
                dict(complete=True, tick=45)]
        with tempfile.TemporaryDirectory() as tmp, patch.object(followup, 'BASE', 30):
            path = self.write_trace(Path(tmp), rows)
            first = followup.trace_receipt(path, 'reach', 15, 45, {})
            rows[3]['new'] = True
            path = self.write_trace(Path(tmp), rows)
            self.assertEqual(first, followup.trace_receipt(path, 'reach', 15, 45, {}))
            rows[1]['historical'] = True
            path = self.write_trace(Path(tmp), rows)
            self.assertNotEqual(first['prefix_sha256'], followup.trace_receipt(path, 'reach', 15, 45, {})['prefix_sha256'])

    def test_reclamation_and_same_step_birth_are_separate(self):
        base, stop = followup.BASE, followup.STOP
        old = dict(lineages=[life(1), life(2)], seeds=[])
        lives = [life(1, death=base + 15), life(2), life(3, birth=base + 30, parent=2)]
        result = dict(lineages=lives, seeds=[], plant_slots=2, living=2, nodes=6, seed_bank=0)
        receipt = dict(states=[[base, [1, 2]], [base + 30, [2, 3]]],
                       occupancy={'1/2': 1, '2/2': (stop - base) // 15 - 1})
        a = followup.analyze(result, dict(run=dict(result=old)), dict(replacements=[]), receipt)
        self.assertEqual(a['releases'], [dict(tick=base + 30, ids=[1])])
        self.assertEqual(a['new_births'], [lives[2]])
        result['lineages'][0]['death_tick'] = base + 30
        with self.assertRaises(RuntimeError):
            followup.analyze(result, dict(run=dict(result=old)), dict(replacements=[]), receipt)

    def test_frozen_late_cohort_boundaries_and_pending_seed_followup(self):
        base, stop, day = followup.BASE, followup.STOP, followup.DAY
        lives = [life(1), life(2, base - 32 * day, parent=1), life(3, base - 32 * day + 15, parent=1),
                 life(4, base, parent=1)]
        old_seed = dict(parent=1, birth_tick=base - 15, end_tick=None, child_id=None, outcome='pending')
        new_seed = old_seed | dict(end_tick=base + 15, child_id=5, outcome='germinated')
        newborn = life(5, base + 15, parent=1)
        old = dict(lineages=lives, seeds=[old_seed])
        result = dict(lineages=lives + [newborn], seeds=[new_seed], plant_slots=5, living=5, nodes=15, seed_bank=0)
        receipt = dict(states=[[base, [1, 2, 3, 4]], [base + 15, [1, 2, 3, 4, 5]]],
                       occupancy={'5/5': (stop - base) // 15})
        saved = dict(replacements=[dict(life=lives[-1], survival={'32': 'censored'})])
        result = followup.analyze(result, dict(run=dict(result=old)), saved, receipt)
        self.assertEqual([r['life']['id'] for r in result['late_births']], [3, 4])
        self.assertEqual([r['life']['id'] for r in result['censored_replacements']], [4])
        self.assertEqual(result['pending_seeds'], [new_seed])
        self.assertTrue(all(r['survival']['32'] == 'confirmed' for r in result['late_births']))

    def test_existing_output_and_broken_symlink_refused_before_calls(self):
        with tempfile.TemporaryDirectory() as tmp, patch('subprocess.run', side_effect=AssertionError('no launch')):
            root = Path(tmp)
            with self.assertRaises(RuntimeError):
                followup.collect(root, root, 4)
            link = root / 'dangling'
            link.symlink_to(root / 'missing')
            with self.assertRaises(RuntimeError):
                followup.collect(link, root, 4)

    def test_artifact_paths_cannot_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            for path in ('../outside', '/outside'):
                with self.assertRaises(RuntimeError):
                    followup.artifact(Path(tmp), dict(path=path, sha256='invalid'))

    def test_cli_rejects_broken_symlink_before_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            link = root / 'dangling'
            link.symlink_to(root / 'missing')
            args = ['followup', '--collect', str(link), '--out', str(root / 'new.json.gz')]
            with patch('sys.argv', args), patch.object(followup, 'collect') as collect:
                with self.assertRaises(RuntimeError):
                    followup.main()
                collect.assert_not_called()
            self.assertFalse((root / 'missing').exists())

    @unittest.skipUnless(RESULT.exists(), 'captured panel not yet available')
    def test_portable_reanalysis_and_tampering_without_native(self):
        with gzip.open(RESULT, 'rt') as stream:
            value = json.load(stream)
        with patch('subprocess.run', side_effect=AssertionError('no launch')), \
             patch('subprocess.Popen', side_effect=AssertionError('no launch')):
            followup.check_value(value)
            for section, key in (('analysis', next(iter(value['analysis']))),
                                 ('runs', 'baseline'), ('reference', next(iter(value['reference'])))):
                bad = copy.deepcopy(value)
                del bad[section][key]
                with self.assertRaises((RuntimeError, KeyError)):
                    followup.check_value(bad)
            bad = copy.deepcopy(value)
            bad['protocol_sha256'] = 'wrong'
            with self.assertRaises(RuntimeError):
                followup.check_value(bad)
            bad = copy.deepcopy(value)
            bad['analysis_sources'][followup.SOURCES[0]] = 'unknown implementation'
            with self.assertRaises(RuntimeError):
                followup.check_value(bad)


if __name__ == '__main__':
    unittest.main()
