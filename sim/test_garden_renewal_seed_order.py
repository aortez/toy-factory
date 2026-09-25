#!/usr/bin/env python3
"""Frozen inventory, read-only traversal views, receipts and CLI boundaries."""
import argparse
import copy
from pathlib import Path
import subprocess
import unittest
from unittest import mock

import garden_renewal_seed_order as trial
from test_garden_renewal_reproduction_access import fixture

BUILD = None


def metadata(tick, count):
    return {"rule": trial.NATIVE, "after": trial.AFTER, "start": trial.start_index(tick, count)}


class SeedOrderTests(unittest.TestCase):
    def test_fixed_budget_and_historical_first(self):
        calls = trial.commands()
        self.assertEqual(len(calls), 16)
        self.assertEqual(len({p for p, _ in calls}), 16)
        self.assertEqual(sum(p.endswith('.gz') for p, _ in calls), 8)
        self.assertEqual(trial.FRAMES, (69120, 245760))
        self.assertEqual(len(trial.historical_files()), 6)
        for index, (path, cmd) in enumerate(calls):
            self.assertIn('/fixed.' if index < 8 else '/rotating.', path)
            self.assertEqual('--seed-order' in cmd, index >= 8)
            self.assertEqual(cmd[cmd.index('--dawn-finish')+1], 'reserve')
            self.assertEqual(cmd[cmd.index('--gap-lineage')+1], '1')

    def test_boundaries_wrap_and_population_changes(self):
        for count in range(9):
            for tick in (0, 69060, 69105, 69120, 69135, 69165):
                self.assertEqual(trial.start_index(tick, count), 0)
            for step in range(1, 65):
                self.assertEqual(trial.start_index(69120+step*60, count), step%count if count else 0)
        for tick, count in ((-1, 7), (True, 7), (69180, 9), (69180, -1)):
            with self.assertRaises(RuntimeError): trial.start_index(tick, count)

    def test_view_is_permutation_without_mutating_evidence(self):
        row = {'tick':69180,'plants':[{'id':i} for i in (12, 1, 3)], 'seed_order':metadata(69180,3)}
        original = copy.deepcopy(row)
        viewed = trial.visit_view(row, 'rotating')
        self.assertEqual([p['id'] for p in viewed['plants']], [1,3,12])
        self.assertEqual(row, original)
        self.assertIsNot(viewed['plants'], row['plants'])
        del row['seed_order']
        self.assertEqual(trial.visit_view(row, 'fixed'), row)

    def test_missing_extra_or_wrong_metadata_rejected(self):
        row = {'tick':69180,'plants':[{'id':1},{'id':2}], 'seed_order':metadata(69180,2)}
        for key in ('rule','after','start'):
            bad=copy.deepcopy(row); bad['seed_order'][key]='bad'
            with self.assertRaises(RuntimeError): trial.visit_view(bad,'rotating')
        with self.assertRaises(RuntimeError): trial.visit_view(row,'fixed')
        del row['seed_order']
        with self.assertRaises(RuntimeError): trial.visit_view(row,'rotating')

    def test_two_buyers_follow_visits_not_array_order(self):
        old,row=fixture(ids=(12,1,3),buyers=(12,1),expired=2,tick=69180)
        row['seed_order']=metadata(69180,3)
        row['seeds'][-2:]=list(reversed(row['seeds'][-2:]))
        row['dark_guard']['events'].reverse()
        original=copy.deepcopy((old,row))
        viewed=trial.visit_view(row,'rotating')
        bank=trial.access.bank_step(old,viewed)
        self.assertEqual(bank['buyers'],[1,12])
        target=trial.access.plant_turn(old['plants'][0],row['plants'][0],row,bank,2,[1])
        self.assertEqual((target['category'],target['bank_at_turn']),('purchase',7))
        self.assertEqual((old,row),original)
        with self.assertRaises(RuntimeError): trial.access.bank_step(old,row)
        row['seeds'][-2:].reverse()  # Reversal of a slice must not mutate the source.
        self.assertEqual((old,row),original)
        row['seeds'][-2:]=list(reversed(row['seeds'][-2:]))
        with self.assertRaises(RuntimeError): trial.access.bank_step(old,trial.visit_view(row,'rotating'))

    def test_prefix_removes_only_metadata(self):
        fixed=[{'type':'world','tick':69105,'hash':'a','plants':[]},
               {'type':'world','tick':69120,'hash':'b','plants':[]}]
        rotated=[{**r,'seed_order':metadata(r['tick'],0)} for r in fixed]
        self.assertEqual(trial.check_prefix(fixed,rotated),2)
        for field in ('hash','plants'):
            bad=copy.deepcopy(rotated);bad[0][field]='changed'
            with self.assertRaises(RuntimeError): trial.check_prefix(fixed,bad)
        with self.assertRaises(RuntimeError): trial.check_prefix(fixed,rotated[:1])

    def test_analysis_only_recovery_does_not_run_native(self):
        with mock.patch.object(trial,'check_capture',side_effect=RuntimeError('stop')), \
                mock.patch.object(trial.experiment,'command_run') as run:
            with self.assertRaises(RuntimeError): trial.finish(Path('/missing-seed-order-fixture'))
            run.assert_not_called()

    def test_native_cli_rejects_malformed_or_out_of_scope_configuration(self):
        if BUILD is None: self.skipTest('requires --build')
        for tool in ('inspect','replay'):
            base=[str(BUILD/('toy-factory-garden-'+tool)),'-','rainfed','adaptive','123','--ticks','15']
            for options in (['--seed-order'],['--seed-order','bad'],['--seed-order','rotating'],
                            ['--seed-order','rotating','--seed-order','rotating'],
                            ['--seed-order','rotating','--dawn-finish','defer']):
                result=subprocess.run([*base,*options],capture_output=True)
                self.assertEqual(result.returncode,2,(tool,options,result.stderr))
                self.assertEqual(result.stdout,b'')


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--build',type=Path)
    args,remaining=parser.parse_known_args()
    BUILD=args.build.resolve() if args.build else None
    unittest.main(argv=[__file__,*remaining])
