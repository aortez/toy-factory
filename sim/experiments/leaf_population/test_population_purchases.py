"""Fixed diagnostic scope, independent spacing checks, and adapter containment."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import local_results
import population_purchases as purchase


def fixture(blocked=False):
    positions = (13, 7, 20) if blocked else (13,)
    plants = [dict(id=i, parent=0, age_ecology_ticks=30 * 256, column=c, species=1,
                   dead=False, energy=100, water=100, stress=0, nodes=1,
                   last_energy_income=1, last_water_income=1) for i, c in enumerate(positions, 1)]
    columns = purchase.columns(13, 0)
    clear = sum(1 << c for c in range(28) if all(abs(c - p) >= 3 for p in positions))
    row = dict(tick=purchase.FIRST, parent=1, random=1, origin=13, dispersal=0,
               blocked_choices=63 if blocked else 0, ordinary=1, selected=1, clear=clear,
               legal=clear & sum(1 << c for c in columns), node_count=len(plants), seed_count=0,
               columns=columns + [0] * 8, site_blockers=[0 if clear & (1 << c) else 32 for c in range(28)],
               plants=plants)
    trace = dict(schema='garden-purchase-trace-v1', first_tick=purchase.FIRST,
                 end_tick_exclusive=purchase.END, limit=256, purchases=[row])
    final = dict(family_roots=[2] * len(plants), lineages=[dict(id=p['id'], parent=0, column=p['column'],
                 species=1, birth_tick=0, death_tick=None) for p in plants],
                 seeds=[dict(parent=1, birth_tick=purchase.FIRST, column=18)])
    return trace, final


class PurchaseTests(unittest.TestCase):
    def test_fixed_roster(self):
        self.assertEqual(len(purchase.roster()), 8)
        self.assertEqual({c['seed'] for c in purchase.roster()}, {'9a903368'})
        self.assertEqual((purchase.FIRST, purchase.END), (115200, 134400))
        for c in purchase.roster():
            self.assertEqual(purchase.arguments(c), ['--purchase-panel', '9a903368', c['variant'], c['mode']])

    def test_spacing_and_forwarded_choice(self):
        for blocked in (False, True):
            trace, final = fixture(blocked)
            result = purchase.validate_trace(trace, final)
            self.assertEqual(result['focal_all_blocked'], int(blocked))
            self.assertEqual(result['total_purchases'], 1)
            self.assertEqual(result['focal'][0]['retrospective_seed_outcome'], final['seeds'][0])
        self.assertEqual(purchase.columns(0, -2), [3, 3, 4, 4, 5, 5])

    def test_mutations_rejected(self):
        trace, final = fixture(True)
        changes = [dict(tick=purchase.END), dict(tick=purchase.FIRST + 1), dict(parent=0),
                   dict(clear=0), dict(legal=1), dict(blocked_choices=0), dict(ordinary=2),
                   dict(selected=2), dict(columns=[0] * 14), dict(random=True),
                   dict(site_blockers=[0] * 28), dict(node_count=0)]
        for change in changes:
            with self.subTest(change=change):
                edited = deepcopy(trace)
                edited['purchases'][0].update(change)
                with self.assertRaises(ValueError):
                    purchase.validate_trace(edited, final)
        for field, value in (('water', 23), ('energy', 47), ('dead', True), ('column', 12)):
            edited = deepcopy(trace)
            edited['purchases'][0]['plants'][0][field] = value
            with self.assertRaises(ValueError):
                purchase.validate_trace(edited, final)

    def test_complete_window_and_no_duplicate_purchases(self):
        trace, final = fixture()
        for rows in ([], trace['purchases'] * 2, trace['purchases'] * 257):
            with self.assertRaises(ValueError):
                purchase.validate_trace(trace | dict(purchases=rows), final)
        with self.assertRaisesRegex(ValueError, 'identity'):
            purchase.validate_trace(trace | dict(first_tick=purchase.FIRST + 15), final)

    def test_reserved_capacity_is_not_an_extra_destination(self):
        trace, final = fixture()
        result = purchase.validate_trace(trace, final)
        self.assertNotIn(0, [r['column'] for r in result['focal'][0]['alternatives']])
        for columns in (trace['purchases'][0]['columns'][:6],
                        trace['purchases'][0]['columns'][:6] + [1] * 8):
            edited = deepcopy(trace)
            edited['purchases'][0]['columns'] = columns
            with self.assertRaisesRegex(ValueError, 'reachable'):
                purchase.validate_trace(edited, final)

    def test_adapter_changes_only_one_binding_and_rejects_drift(self):
        folder = purchase.collect.ROOT / 'sim/research_player'
        spec = importlib.util.spec_from_file_location('purchase_stage', folder / 'stage_purchase_observer.py')
        stage = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(stage)
        # Use authenticated archive data, not a possibly absent build directory.
        files = purchase.prepare.expected_files(purchase.prepare.load_archive())
        source = files['source/sim/garden_landing_run.c'].decode()
        result = stage.adapt(source)
        self.assertEqual(result.count('policy.place_seed = research_purchase_decide;'), 1)
        self.assertNotIn('policy.place_seed = toy_factory_garden_placement_decide;', result)
        self.assertIn('policy.seed_replacement_after = placement->replace_after;', result)
        for wrong in ('', source + source, result):
            with self.assertRaises(ValueError):
                stage.adapt(wrong)


@local_results.needs('leaf-population-purchases-results.json.gz')
class PublishedPurchaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='published-purchases-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.out = cls.root / 'evidence'
        cls.archive = purchase.collect.ROOT / 'benchmarks/garden-seasons/leaf-population-purchases-results.json.gz'
        assert purchase.prepare.sha(cls.archive.read_bytes()) == '2d94fda91c831ac484c906588d0c9db5f0400ee031093c7a2aff9ba532b2f24d'
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('no native calls')):
            cls.result = purchase.follow.unpack(cls.archive, cls.out, experiment=purchase.EXPERIMENT)

    def test_exact_archive_roundtrip_without_simulator(self):
        target = self.root / 'repacked.gz'
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('no native calls')):
            purchase.follow.package(self.out, target, experiment=purchase.EXPERIMENT)
        self.assertEqual(target.read_bytes(), self.archive.read_bytes())
        with self.assertRaises(FileExistsError):
            purchase.follow.package(self.out, target, experiment=purchase.EXPERIMENT)

    def test_complete_trace_and_observable_obstacles(self):
        a = self.result['analyses']
        self.assertEqual(self.result['calls'], 8)
        self.assertEqual([a[v]['total_purchases'] for v in purchase.gates.VARIANTS], [10, 9, 8, 7])
        self.assertEqual([a[v]['focal_purchases'] for v in purchase.gates.VARIANTS], [3, 2, 2, 1])
        self.assertEqual(sum(a[v]['focal_all_blocked'] for v in a), 7)
        row = a['both']['focal'][0]
        self.assertEqual(row['observation']['selected'], 4)
        self.assertEqual(row['observation']['columns'][:6], [8, 18, 7, 19, 6, 20])
        self.assertEqual(row['alternatives'], [dict(column=c, blockers=b) for c, b in
            ((6, [1, 13]), (7, [13]), (8, [13, 14]), (18, [11, 12]), (19, [11, 12]), (20, [11]))])
        blockers = [p for p in row['observation']['plants'] if p['id'] in (1, 11, 13)]
        self.assertTrue(all(p['energy'] == 252 and p['stress'] == 0 for p in blockers))
        self.assertEqual(row['retrospective_seed_outcome']['outcome'], 'expired')

    def test_parser_recovery_preserves_original_failure_and_native_inputs(self):
        record = json.loads((self.out / 'recovery.json').read_bytes())
        self.assertEqual(record['native_calls_added'], 0)
        self.assertEqual(record['error'], "ValueError('reachable columns differ')")
        started = json.loads((self.out / 'started.json').read_bytes())
        for name in started['sources']:
            if name.endswith(('.c', '.h', '.txt')):
                self.assertEqual(record['original_files']['source/' + name],
                                 started['sources'][name])
        self.assertTrue(self.result['validation_recovered_offline'])

    def test_modified_recovery_receipt_is_rejected(self):
        from population_purchases_recovery import validate_recovery
        path = self.out / 'recovery.json'
        saved = path.read_bytes()
        try:
            changed = json.loads(saved)
            changed['native_calls_added'] = 1
            path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, 'recovery identity'):
                validate_recovery(self.out)
        finally:
            path.write_bytes(saved)


if __name__ == '__main__':
    unittest.main()
