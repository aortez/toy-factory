#!/usr/bin/env python3
"""Saved energy histories, checkpoint boundaries and independent store arithmetic."""

import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_energy_history as audit

RESULT = audit.ROOT / 'benchmarks/garden-seasons/landing-energy-history-results.json.gz'


def row(tick, energy, phase=0, cold=False):
    return dict(tick=tick, sun=[phase, 100], season=0, cold=cold,
                plant=[[[energy, 100, 0, 0, 32]] * 5, None, 16, 8])


def step(tick, before, income=0, due=0, growth=0, seed=0):
    e = audit.replay_energy(before, income, due, growth, seed)
    resources = audit.adults.budget()
    resources['energy'].update(initial=before, income=income, overflow=e['overflow'],
                               upkeep=due - e['unpaid'], growth=growth, reproduction=seed, final=e['final'])
    payment = dict(energy=dict(due=due, paid=due - e['unpaid'], unpaid=e['unpaid']),
                   water=dict(due=0, paid=0, unpaid=0)) if due else None
    return dict(tick=tick, resources=resources, payment=payment)


class ContractTests(unittest.TestCase):
    def test_cap_precedes_maintenance_growth_and_reproduction(self):
        self.assertEqual(audit.replay_energy(256, 5, 4, 8, 48),
                         dict(uptake=256, maintenance=252, growth=244, final=196, overflow=5, unpaid=0))
        self.assertEqual(audit.replay_energy(0, 3, 4, 0, 0)['unpaid'], 1)
        # Later costs do not create headroom for income that already overflowed.
        self.assertEqual(audit.replay_energy(250, 10, 4, 0, 0)['final'], 252)

    def test_invalid_store_and_unfunded_spending_rejected(self):
        for args in ((257, 0, 0, 0, 0), (-1, 0, 0, 0, 0), (True, 0, 0, 0, 0),
                     (0, -1, 0, 0, 0), (0, 0, 0, 0, 1), (5, 0, 4, 2, 0)):
            with self.subTest(args=args), self.assertRaises(RuntimeError): audit.replay_energy(*args)

    def test_last_shared_full_is_strictly_before_deficit_and_recovery_is_first(self):
        rows = {a: [row(t, e) for t, e in ((15, 256), (30, 252), (45, 256),
                                          (60, 256), (75, 255), (90, 256), (105, 256))]
                for a in audit.SIDES}
        self.assertEqual(audit.shared_full(rows, 60), 2)
        self.assertEqual(audit.shared_full(rows, 60, later=True), 5)
        rows['candidate'][2]['plant'][0][-1][0] = 255
        self.assertEqual(audit.shared_full(rows, 60), 0)

    def test_no_shared_full_remains_explicit_and_unequal_coverage_rejected(self):
        rows = dict(control=[row(15, 256)], candidate=[row(15, 255)])
        self.assertIsNone(audit.shared_full(rows, 30))
        self.assertIsNone(audit.shared_full(rows, 0, later=True))
        with self.assertRaises(ValueError): audit.shared_full(rows | {'candidate': []}, 30)

    def test_post_step_anchor_excludes_anchor_transfers_and_keeps_next_bill(self):
        steps = [step(15, 250, 10), step(60, 256, 4, 4), step(120, 252, 0, 4)]
        window = audit.window(steps, 0, 2)
        self.assertEqual(window['resources']['energy'], dict(initial=256, income=4, overflow=4,
                         upkeep=8, growth=0, reproduction=0, discarded=0, final=248))
        self.assertEqual(window['payments'], 2)
        self.assertEqual(window['due']['energy'], 8)
        self.assertEqual(audit.window(steps, 0, 0)['resources']['energy']['final'], 256)
        self.assertEqual(audit.window(steps, 0, 0)['payments'], 0)
        self.assertEqual(audit.window(steps, None, 2)['resources']['energy']['initial'], 250)
        self.assertEqual(audit.window(steps, None, 2)['resources']['energy']['overflow'], 8)

    def test_invalid_window_and_discontinuous_stores_rejected(self):
        steps = [step(15, 250, 10), step(60, 255, 4, 4)]
        for start, end in ((-1, 0), (1, 0), (0, 2)):
            with self.assertRaisesRegex(RuntimeError, 'history window'): audit.window(steps, start, end)
        with self.assertRaisesRegex(RuntimeError, 'budget discontinuity'): audit.window(steps, 0, 1)

    def test_gross_income_difference_at_full_store_is_not_a_retained_difference(self):
        rows = {a: [row(15, 256), row(60, 252)] for a in audit.SIDES}
        steps = {a: [step(15, 256), step(60, 256, income, 4)]
                 for a, income in zip(audit.SIDES, (8, 4), strict=True)}
        diff = audit.differences(rows, steps, 0, 1)
        self.assertEqual(diff, dict(energy_income=dict(tick=60, control=8, candidate=4)))

    def test_phase_and_cold_boundaries_partition_all_transfers(self):
        values = [row(15, 256, 63), row(30, 256, 63), row(45, 256, 64), row(60, 252, 65, True)]
        rows = {a: values for a in audit.SIDES}
        ss = [step(15, 256), step(30, 256, 3), step(45, 256, 5), step(60, 256, 0, 4)]
        steps = {a: ss for a in audit.SIDES}
        blocks = audit.phase_blocks(rows, steps, 0, 3)
        self.assertEqual([(b['first'], b['through'], b['phase_quarter'], b['cold']) for b in blocks],
                         [(30, 30, 0, False), (45, 45, 1, False), (60, 60, 1, True)])
        for k in ('income', 'overflow', 'upkeep', 'growth', 'reproduction'):
            self.assertEqual(sum(b['arms']['control']['resources']['energy'][k] for b in blocks),
                             audit.window(ss, 0, 3)['resources']['energy'][k])
        self.assertEqual(sum(sum(r[-1] for r in b['post_step_bodies']['control']) for b in blocks), 3)

    def test_raw_hash_and_path_escape_fail_closed(self):
        bundle = Path('/tmp/energy-history-test')
        source = {a: {'trace': dict(path=a + '/adult.jsonl.gz', sha256='1' * 64)} for a in audit.SIDES}
        manifest = json.dumps(dict(artifacts={s['trace']['path']: s['trace']['sha256'] for s in source.values()}))
        with patch.object(audit, 'digest', return_value='0' * 64):
            with self.assertRaisesRegex(RuntimeError, 'raw manifest'): audit.check_raw(bundle, source)
        with patch.object(Path, 'read_text', return_value=manifest), \
             patch.object(audit, 'digest', side_effect=lambda p: audit.MANIFEST_SHA if p.name == 'manifest.json' else '0' * 64):
            with self.assertRaisesRegex(RuntimeError, 'adult trace'): audit.check_raw(bundle, source)
        source['control']['trace']['path'] = '../escape.gz'
        with patch.object(Path, 'read_text', return_value=manifest), \
             patch.object(audit, 'digest', return_value=audit.MANIFEST_SHA):
            with self.assertRaisesRegex(RuntimeError, 'escaped bundle'): audit.check_raw(bundle, source)

    def test_existing_output_and_dangling_symlink_refused_before_inputs(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(audit, 'inputs',
                side_effect=AssertionError('must not load inputs')):
            target = Path(directory) / 'link.gz'
            target.symlink_to(Path(directory) / 'missing.gz')
            for out in (Path(directory), target):
                with self.assertRaisesRegex(RuntimeError, 'fresh output'): audit.export(Path('/missing'), out)


@unittest.skipUnless(RESULT.exists(), 'selected history not yet retained')
class CapturedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(RESULT, 'rt') as stream: cls.value = json.load(stream)
        with patch('subprocess.Popen', side_effect=AssertionError('unexpected process')):
            cls.source = audit.inputs()
        cls.analysis, cls.rows = cls.value['analysis'], cls.value['rows']

    def test_portable_verification_without_process_launches(self):
        with patch('subprocess.Popen', side_effect=AssertionError('unexpected process')), \
             patch('subprocess.run', side_effect=AssertionError('unexpected process')):
            audit.check_value(self.value)

    def test_complete_lifetimes_and_exact_episode_reconcile(self):
        for side in audit.SIDES:
            self.assertEqual(len(self.rows[side]), 26161)
            self.assertEqual(self.analysis['history'][side]['resources'], self.source[side]['plant']['resources'])
        events = [p for p in self.analysis['history']['candidate']['shortages'] if p['energy']['unpaid']]
        self.assertEqual([(e['tick'], e['energy']['unpaid']) for e in events],
                         [(978420, 4), (978480, 4), (978540, 1)])

    def test_no_new_spending_since_shared_full_anchor(self):
        self.assertEqual(self.analysis['checkpoint'], 972045)
        self.assertEqual(self.analysis['episode_purchases'], {a: [] for a in audit.SIDES})
        self.assertEqual([self.analysis['last_prior_purchase'][a]['tick'] for a in audit.SIDES], [967260, 963480])
        for check in self.analysis['checkpoints']:
            for side in audit.SIDES:
                e = check['arms'][side]['resources']['energy']
                self.assertEqual([e[k] for k in ('initial', 'growth', 'reproduction')], [256, 0, 0])
            self.assertEqual(check['arms']['control']['resources']['water'],
                             check['arms']['candidate']['resources']['water'])

    def test_first_difference_is_actual_income_not_a_changed_cost_or_leaf_count(self):
        d = self.analysis['first_difference']
        self.assertEqual(d['energy_income'], dict(tick=974805, control=2, candidate=1))
        self.assertEqual(d['energy_retained'], d['energy_income'])
        self.assertEqual(d['energy_store'], dict(tick=974805, control=80, candidate=79))
        self.assertTrue({'nodes', 'roots', 'active_leaves', 'energy_growth', 'energy_due', 'energy_reproduction'}.isdisjoint(d))
        for block in self.analysis['phase_blocks']:
            self.assertEqual(block['post_step_bodies']['control'], block['post_step_bodies']['candidate'])
            self.assertTrue(all(r[:3] == [32, 16, 8] for r in block['post_step_bodies']['control']))

    def test_first_winter_morning_and_deficit_budget(self):
        block = next(b for b in self.analysis['phase_blocks'] if b['first'] == 974400)
        self.assertEqual([block['arms'][a]['resources']['energy']['income'] for a in audit.SIDES], [189, 77])
        self.assertEqual([block['arms'][a]['due']['energy'] for a in audit.SIDES], [64, 64])
        self.assertEqual((block['season'], block['cold']), (3, True))
        check = next(c for c in self.analysis['checkpoints'] if c['through'] == 978540)
        self.assertEqual([check['arms'][a]['resources']['energy']['final'] for a in audit.SIDES], [87, 0])
        self.assertEqual([check['arms'][a]['unpaid']['energy'] for a in audit.SIDES], [0, 9])
        self.assertEqual(check['delta']['energy']['income'] - check['delta']['energy']['overflow'], -96)

    def test_recovery_does_not_erase_missed_payments(self):
        c = self.analysis['checkpoints'][-1]
        self.assertEqual((c['label'], c['through']), ('shared_full_recovery', 979230))
        self.assertEqual([c['arms'][a]['resources']['energy']['final'] for a in audit.SIDES], [256, 256])
        self.assertEqual([c['arms'][a]['unpaid']['energy'] for a in audit.SIDES], [0, 9])
        self.assertEqual(c['delta']['energy']['income'] - c['delta']['energy']['overflow'], -9)

    def test_missing_reordered_and_discontinuous_records_rejected(self):
        rows = self.rows['control']
        with self.assertRaisesRegex(RuntimeError, 'incomplete selected history'):
            audit.validate_history(rows[:-1], self.source['control'])
        for field in ('tick', 'continuity', 'body', 'overflow'):
            bad = list(rows)
            bad[1] = copy.deepcopy(rows[1])
            if field == 'tick': bad[1]['tick'] += audit.STEP
            elif field == 'continuity': bad[1]['plant'][1][0][0] += 1
            elif field == 'body': bad[1]['plant'][2] += 1
            else: bad[1]['plant'][1][0][2] += 1
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                audit.validate_history(bad, self.source['control'])

    def test_seed_debit_cannot_be_reassigned_to_growth(self):
        rows = self.rows['control']
        n = next(n for n, r in enumerate(rows) if r['plant'][0][3][0] != r['plant'][0][4][0])
        bad = list(rows)
        bad[n] = copy.deepcopy(rows[n])
        # Preserve step-level balance but move 48 units from reproduction to
        # construction; the independent seed ledger must reject this fiction.
        bad[n]['plant'][0][3][0] -= 48
        with self.assertRaisesRegex(RuntimeError, 'seed ledger/debit'):
            audit.validate_history(bad, self.source['control'])

    def test_changed_environment_provenance_sources_receipts_and_summaries_rejected(self):
        for key, v in (('native_runs', True), ('training_runs', 1), ('raw_manifest_sha256', '0' * 64)):
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, 'provenance'):
                audit.check_value(self.value | {'provenance': self.value['provenance'] | {key: v}})
        with self.assertRaisesRegex(RuntimeError, 'source coverage'): audit.check_value(self.value | {'sources': {}})
        with self.assertRaisesRegex(RuntimeError, 'source differs'): audit.check_value(self.value | {'source_sha256': {}})
        with self.assertRaisesRegex(RuntimeError, 'checksum'):
            audit.check_value(self.value | {'receipt_sha256': dict(control='0' * 64, candidate='0' * 64)})
        rows = {**self.rows, 'candidate': list(self.rows['candidate'])}
        rows['candidate'][1] = copy.deepcopy(rows['candidate'][1])
        rows['candidate'][1]['sun'][1] -= 1
        with self.assertRaisesRegex(RuntimeError, 'unequal paired environment'): audit.analyze(rows, self.source)
        with patch.object(audit, 'analyze', return_value=self.analysis):
            with self.assertRaisesRegex(RuntimeError, 'analysis differs'):
                audit.check_value(self.value | {'analysis': self.analysis | {'checkpoint': 972030}})


if __name__ == '__main__':
    unittest.main()
