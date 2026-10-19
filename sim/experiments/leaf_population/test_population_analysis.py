"""Fast offline checks, including all 288 previously published family scores."""

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest

import collect_population as collector
import population_score as score
import population_evidence as evidence
import prepare


def history(children=(), deaths=None, end=1376 * score.DAY):
    """Small synthetic history: children are (parent, birth_tick, death_tick)."""
    deaths = deaths or {}
    plants = [dict(id=i, parent=0, birth_tick=0, death_tick=deaths.get(i),
                   environmental_death=False, column=i * 4, generation=0, species=i - 1)
              for i in range(1, 4)]
    seeds, roots = [], [1, 2, 3]
    for parent, birth, death in children:
        identity = len(plants) + 1
        traits = {k: plants[parent - 1][k] for k in ('column', 'species', 'generation')}
        traits['generation'] += 1
        plants.append(dict(id=identity, parent=parent, birth_tick=birth, death_tick=death,
                           environmental_death=False, **traits))
        seeds.append(dict(parent=parent, birth_tick=birth - 120, end_tick=birth,
                          child_id=identity, lifetime_ecology_ticks=8192,
                          outcome='germinated', **traits))
        roots.append(roots[parent - 1])
    purchases = Counter(s['parent'] for s in seeds)
    for p in plants:
        p.update(seeds_created=purchases[p['id']], late_seeds_created=purchases[p['id']])
    return dict(complete=True, ledger_start_tick=0, ticks=end, scenario='rainfed',
                family_roots=roots, lineages=plants, seeds=seeds,
                death_causes=[4 if p['death_tick'] is None else 0 for p in plants])


class ScoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = prepare.load_archive()
        cls.plan = json.loads(prepare.blob(cls.bundle, 'started.json'))['plan']
        cls.results = json.loads(prepare.blob(cls.bundle, 'result.json'))['analysis']['periods']

    def test_all_288_archived_family_scores_and_ledgers(self):
        count = 0
        for call in self.plan:
            if call['phase'] != 'panel':
                continue
            value = json.loads(prepare.blob(self.bundle, f"runs/{call['id']}/stdout.json"))
            score.validate_history(value)
            score.event_timeline(value)
            for start in score.PERIODS:
                expected = next(r['score'] for r in self.results[str(start)]['models'][call['model']]['matches']
                                if all(r[k] == call[k] for k in ('seed', 'layout', 'founder')))
                self.assertEqual(score.family_score(value, call['founder'], start), expected)
                count += 1
        self.assertEqual(count, 288)

    def test_window_boundaries_cap_and_death_at_establishment(self):
        d = score.DAY
        value = history([(1, 64 * d, None), (4, 192 * d, 224 * d + 15),
                         (4, 256 * d - 30, None), (4, 256 * d - 15, None),
                         (4, 256 * d, None), (4, 256 * d + 15, 288 * d + 15)])
        score.validate_history(value)
        actual = score.family_score(value, 1, 192)
        self.assertEqual(actual['renewal_children'], [3, 0, 0, 0, 0, 0])
        self.assertEqual(actual['key'][0], [1, 6])
        # Surviving just beyond the 32-day boundary qualifies in the next window.
        value['lineages'][-1]['death_tick'] += 15
        self.assertEqual(score.family_score(value, 1, 192)['renewal_children'], [3, 1, 0, 0, 0, 0])
        # A parent that dies at age 32 cannot receive renewal credit either.
        value['lineages'][3]['death_tick'] = 96 * d
        self.assertEqual(score.family_score(value, 1, 192)['key'][0], [0, 1])

    def test_extinct_families_are_retained_and_empty_intervals_are_exact(self):
        value = history(deaths={1: 15, 2: 30, 3: 45})
        result = score.analyze_world(value)
        self.assertEqual(result['extinction_tick'], 45)
        self.assertEqual(result['empty_living_intervals'],
                         [dict(start_inclusive=45, until_exclusive=value['ticks'] + 1)])
        for period in result['periods'].values():
            self.assertEqual(len(period['families']), 3)
            self.assertEqual(period['key'], [[0, 1], [0, 1]])
        self.assertEqual(result['checkpoints']['1376']['family_status'], ['extinct'] * 3)

    def test_seed_only_is_not_extinction_and_posthumous_child_is_valid(self):
        value = history([(1, 150, None)], deaths={1: 45, 2: 45, 3: 45})
        score.validate_history(value)
        events = score.event_timeline(value)
        at_45 = score.demographic(value, 45, events)
        self.assertEqual((at_45['living'], at_45['pending']), (0, 1))
        self.assertEqual(at_45['family_status'], ['dormant', 'extinct', 'extinct'])
        result = score.analyze_world(value)
        self.assertIsNone(result['extinction_tick'])
        self.assertEqual(result['empty_living_intervals'],
                         [dict(start_inclusive=45, until_exclusive=150)])
        prefix = score.history_prefix(value, 30)
        self.assertEqual(prefix['seeds'][0]['outcome'], 'pending')
        self.assertIsNone(prefix['seeds'][0]['child_id'])
        self.assertEqual(prefix['death_causes'], [4, 4, 4])
        score.validate_history(value | prefix | dict(ticks=30))

    def test_incomplete_or_corrupt_ledgers_rejected(self):
        original = history([(1, 150, None)])
        mutations = [lambda v: v.update(complete=False), lambda v: v.update(ledger_start_tick=15),
            lambda v: v['family_roots'].__setitem__(3, 2),
            lambda v: v['lineages'][0].update(seeds_created=7),
            lambda v: v['seeds'][0].update(child_id=2),
            lambda v: v['seeds'][0].update(end_tick=135),
            lambda v: v['lineages'][0].update(environmental_death=True),
            lambda v: v['death_causes'].__setitem__(0, 0),
            lambda v: v['seeds'].append(deepcopy(v['seeds'][0]))]
        for mutate in mutations:
            value = deepcopy(original)
            mutate(value)
            with self.assertRaises(ValueError):
                score.validate_history(value)
        crowded = history([(1, 150 + i * 15, None) for i in range(6)])
        score.validate_history(crowded)
        with self.assertRaises(ValueError):
            score.event_timeline(crowded)

    def test_equal_world_weight_and_complete_roster(self):
        worlds = {}
        for model in score.MODELS:
            for seed in score.SEEDS:
                for layout in score.LAYOUTS:
                    value = score.analyze_world(history())
                    for period in value['periods'].values():
                        period['key'] = [[1, 1] if layout == 'rainfed' else [0, 1], [0, 1]]
                    worlds[model, seed, layout] = value
        result = score.aggregate(worlds)
        for value in result.values():
            for period in value['periods'].values():
                self.assertEqual(period['key'], [[1, 2], [0, 1]])
        worlds.pop(next(iter(worlds)))
        with self.assertRaises(ValueError):
            score.aggregate(worlds)

    def test_early_losses_and_recent_children_are_distinct(self):
        d = score.DAY
        value = history([(1, 64 * d, 96 * d), (2, 1375 * d, None)])
        row = score.analyze_world(value)['checkpoints']['1376']
        self.assertEqual(row['offspring_born'], 2)
        self.assertEqual(row['died_before_establishment'], 1)
        self.assertEqual(row['young_alive'], 1)
        self.assertEqual(row['established_offspring'], 0)

    def test_canonical_record_identity_and_model_guard(self):
        bundle, models, size = collector.archive_inputs()
        call = next(c for c in self.plan if c['phase'] == 'panel')
        value = json.loads(prepare.blob(bundle, f"runs/{call['id']}/stdout.json"))
        state = bytearray.fromhex(value['state_hex'])
        state[:6] = b'TPR1\0\0'
        value.update(schema='garden-leaf-population-replay-v1', controller_assignment='whole-population',
                     candidate_founder=None, resident_policy=None, state_hex=state.hex())
        validate = lambda v: score.validate_record(v, models[call['model']], seed=call['seed'],
            layout=call['layout'], ticks=call['days'] * score.DAY, uniform_bytes=size)
        validate(value)
        for field, replacement in [('schema', 'wrong'), ('candidate_founder', 1),
            ('gardener', True), ('seed', '00000000'), ('ticks', 0), ('state_hex', '00'),
            ('leaf_model_hex', models['s2-g3-c1'].hex())]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate(value | {field: replacement})


class CollectorTests(unittest.TestCase):
    def test_capture_conversion_and_safe_archive_paths(self):
        raw = b'\xf8\x00\x07\xe0\x00\x1f' * 19200
        self.assertEqual(evidence.rgb565(raw)[:9], b'\xff\0\0\0\xff\0\0\0\xff')
        self.assertTrue(evidence.png(evidence.rgb565(raw)).startswith(b'\x89PNG\r\n\x1a\n'))
        with self.assertRaises(ValueError):
            evidence.rgb565(b'\0')
        for name in ('../escape', '/absolute', 'a/../b', 'a\\b'):
            with self.assertRaises(ValueError):
                prepare.relative(name)

    def test_fixed_plan(self):
        plan = collector.roster()
        self.assertEqual(len(plan), 48)
        self.assertEqual(len({c['id'] for c in plan}), 48)
        self.assertEqual(Counter(c['phase'] for c in plan), dict(primary=24, repeat=24))
        self.assertEqual({c['ticks'] for c in plan}, {5283840})
        self.assertEqual((collector.WORKERS, collector.CALL_SECONDS, collector.COLLECTION_SECONDS),
                         (4, 180, 2700))

    def test_process_success_failure_timeout_and_no_overwrite(self):
        with tempfile.TemporaryDirectory(prefix='garden-collector-test-') as directory:
            root = Path(directory)
            self.assertEqual(collector.process_call([sys.executable, '-c', 'print(42)'], root / 'ok', 3), b'42\n')
            with self.assertRaises(FileExistsError):
                collector.process_call(['never-execute'], root / 'ok', 3)
            with self.assertRaises(ValueError):
                collector.process_call([sys.executable, '-c', 'raise SystemExit(7)'], root / 'fail', 3)
            with self.assertRaises(subprocess.TimeoutExpired):
                collector.process_call([sys.executable, '-c', 'import time;time.sleep(10)'], root / 'timeout', .1)
            receipt = json.loads((root / 'timeout/process.json').read_bytes())
            self.assertTrue(receipt['timed_out'])
            with self.assertRaises(ValueError):
                collector.process_call([sys.executable, '-c', 'import sys;sys.stderr.write("bad")'], root / 'stderr', 3)

    def test_bounded_workers_and_no_new_submissions_after_failure(self):
        lock = threading.Lock()
        active, maximum = 0, 0
        def worker(call):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            time.sleep(.002)
            with lock:
                active -= 1
            return call
        self.assertEqual(set(collector.bounded_phase(list(range(24)), worker)), set(range(24)))
        self.assertLessEqual(maximum, 4)
        seen = []
        def fail(call):
            with lock:
                seen.append(call)
            if call == 0:
                raise ValueError('injected failure')
            time.sleep(.02)
            return call
        with self.assertRaisesRegex(ValueError, 'injected failure'):
            collector.bounded_phase(list(range(24)), fail)
        self.assertLessEqual(len(seen), 4)


if __name__ == '__main__':
    unittest.main()
