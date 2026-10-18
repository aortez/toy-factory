#!/usr/bin/env python3
"""One frozen 123-call fixed-policy weather comparison; no search or retries."""

import argparse
from datetime import datetime
from fractions import Fraction
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'leaf_wear_pilot'))
import run_learning as previous

pilot, batches = previous.pilot, previous.wear.batches
ROOT = pilot.ROOT
require, read, save, digest, sha = pilot.require, pilot.read, pilot.save, pilot.digest, pilot.sha
PROTOCOL = ROOT / 'benchmarks/garden-seasons/leaf-family-generalization-protocol.md'
ARCHIVE = ROOT / 'benchmarks/garden-seasons/leaf-family-wear-pilot-results.json.gz'
ARCHIVE_SHA = 'baace2fd65ce2f725cbbe2d022b1ec96bcea119bee44e9fcf82f806b4b0ebb50'
MODELS = ('initial', 's1-g3-c4', 's2-g3-c1')
SEEDS = ('58d7d6ca', '9a903368', '6b9c1a3e', '59818bc3')
ANCHOR = ('98a89374', 'rainfed-crowded', 4)
MAX_CALLS, MAX_SECONDS, MAX_BYTES, MIN_FREE = 123, 2700, 256 * 1024**2, 2 * 1024**3
SCHEMA = 'garden-leaf-family-generalization-v1'
TEST_COUNT = 14


@lru_cache(maxsize=1)
def baseline():
    require(digest(ARCHIVE) == ARCHIVE_SHA, 'closed pilot archive changed')
    bundle = json.loads(gzip.decompress(ARCHIVE.read_bytes()))

    def blob(name):
        identity = bundle['files'][name]
        raw = bytes.fromhex(bundle['blobs'][identity])
        require(sha(raw) == identity, 'closed pilot blob differs')
        return raw

    scope, result = (json.loads(blob(name)) for name in ('started.json', 'result.json'))
    require(result['finals'] == list(MODELS[1:]), 'archived finalists differ')
    anchors = {}
    for logical, name in zip(('wear', 'search1', 'search2'), MODELS):
        matches = []
        for ref in result['evaluations'][f'validation-{logical}-{name}']['calls']:
            raw = blob(f'runs/{ref}/stdout.json')
            value = json.loads(raw)
            if (value['seed'], value['scenario'], value['candidate_founder']) == ANCHOR:
                matches.append(dict(ref=ref, stdout=raw, pixels=blob(f'runs/{ref}/frame.raw')))
        require(len(matches) == 1, 'archived reference is ambiguous')
        anchors[name] = matches[0]
    return dict(identities=scope['identities'], growth=blob('growth.tgl'), anchors=anchors,
                models={name: blob(f'models/{name}.tlf') for name in MODELS})


def label(seed, layout, founder):
    return f'{seed}-{layout}-f{founder}'


def plan():
    result = []
    phases = [('anchor', [(name, *ANCHOR) for name in MODELS], True),
              ('panel', [(name, *role) for role in pilot.roles(SEEDS) for name in MODELS], True),
              ('confirm', [(name, seed, layout, 1) for seed in SEEDS
                           for layout, _ in pilot.LAYOUTS for name in MODELS], False)]
    for phase, entries, capture in phases:
        for name, seed, layout, founder in entries:
            result.append(dict(id=f'call{len(result) + 1:04d}', phase=phase, model=name,
                model_sha256=sha(baseline()['models'][name]), seed=seed, layout=layout,
                founder=founder, days=608, capture=capture))
    return result


def seed_audit():
    derived = tuple(format(int.from_bytes(hashlib.sha256(
        f'toy-factory/leaf-family-generalization-v1/weather-{i}'.encode()).digest()[:4], 'little'), '08x')
        for i in range(1, 5))
    require(derived == SEEDS and not set(SEEDS).intersection(pilot.TRAIN + pilot.REVIEW +
            pilot.VALIDATE + previous.VALIDATE), 'weather derivation/split differs')
    try:
        listing = subprocess.run(['rg', '--files', 'benchmarks', 'docs', 'sim', '-g', '*.json',
            '-g', '*.json.gz', '-g', '*.md', '-g', '*.py'], cwd=ROOT,
            capture_output=True, text=True, check=True)
        names = listing.stdout.splitlines()
    except FileNotFoundError:
        listing = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z',
            '--', 'benchmarks', 'docs', 'sim'], cwd=ROOT, capture_output=True, text=True, check=True)
        names = [name for name in listing.stdout.split('\0') if name.endswith(('.json', '.json.gz', '.md', '.py'))]
    tokens = tuple(token.encode() for seed in SEEDS for token in (seed, seed.upper(), str(int(seed, 16))))
    files, matches = {}, []
    for name in sorted(set(names)):
        if name.startswith(('sim/experiments/leaf_generalization/', 'sim/experiments/leaf_generalization_report/',
                            'benchmarks/garden-seasons/leaf-family-generalization')):
            continue
        raw = (ROOT / name).read_bytes()
        files[name] = sha(raw)
        if previous.seed_occurs(gzip.decompress(raw) if name.endswith('.gz') else raw, tokens):
            matches.append(name)
    return dict(seeds=list(SEEDS), checked_utc=pilot.utc(), files=files, matches=matches)


class Limits(pilot.Limits):
    def submit(self):
        now = self.clock()
        require(self.count < MAX_CALLS, '123-call ceiling reached')
        require(self.first is None or now - self.first < MAX_SECONDS, '45-minute submission deadline reached')
        require(self.size() < MAX_BYTES, 'run folder reached 256 MiB')
        require(shutil.disk_usage(self.root).free >= MIN_FREE, 'less than 2 GiB free')
        if self.first is None:
            self.first, self.first_utc = now, pilot.utc()
        self.count += 1
        return self.count, now - self.first


def family_status(value):
    founder = value['candidate_founder']
    members = [p for p in value['lineages'] if value['family_roots'][p['id'] - 1] == founder]
    seeds = [s for s in value['seeds'] if value['family_roots'][s['parent'] - 1] == founder]
    living = sum(p['death_tick'] is None for p in members)
    pending = sum(s['end_tick'] is None for s in seeds)
    extinct = living == pending == 0
    death = members[0]['death_tick']
    return dict(living=living, pending=pending, extinct=extinct, dormant=living == 0 and pending > 0,
        extinction_tick=max([p['death_tick'] for p in members] + [s['end_tick'] for s in seeds]) if extinct else None,
        founder_death_tick=death, founder_survival={str(day): death is None or death > day * pilot.DAY
                                                  for day in (1, 16, 32)})


def rational(value):
    return [value.numerator, value.denominator]


def analyze(values):
    calls = [c for c in plan() if c['phase'] == 'panel']
    require(set(values) == {c['id'] for c in calls}, 'incomplete panel roster')
    models = {}
    for name in MODELS:
        selected = [values[c['id']] for c in calls if c['model'] == name]
        score = pilot.score_values(selected, SEEDS)
        details = {label(v['seed'], v['scenario'], v['candidate_founder']): family_status(v) for v in selected}
        conditions, weighted_extinct = {}, Fraction(0)
        for seed in SEEDS:
            for layout, count in pilot.LAYOUTS:
                matches = {v['candidate_founder']: pilot.score_family(v | {'tick': v['ticks']},
                    v['candidate_founder'], start_day=192, window_count=6)
                    for v in selected if (v['seed'], v['scenario']) == (seed, layout)}
                key = seed + '-' + layout
                conditions[key] = pilot.controls.rational_key(pilot.aggregate({key: matches},
                    expected_roles={key: tuple(range(1, count + 1))}))
                weighted_extinct += Fraction(sum(details[label(seed, layout, f)]['extinct']
                    for f in range(1, count + 1)), count * len(SEEDS) * len(pilot.LAYOUTS))
        counts = [row['score']['renewal_children'] for row in score['matches']]
        models[name] = dict(score=score, conditions=conditions, details=details,
            founder_survival={str(day): sum(d['founder_survival'][str(day)] for d in details.values())
                              for day in (1, 16, 32)},
            living_families=sum(d['living'] > 0 for d in details.values()),
            dormant_families=sum(d['dormant'] for d in details.values()),
            extinct_families=sum(d['extinct'] for d in details.values()),
            weighted_extinction=rational(weighted_extinct),
            closing_window_families=sum(c[-1] > 0 for c in counts),
            every_window_families=sum(all(n > 0 for n in c) for c in counts))
    control, comparisons = models['initial'], {}
    for name in MODELS[1:]:
        candidate = models[name]
        changes = {label(row['seed'], row['layout'], row['founder']):
            Fraction(*row['score']['key'][0]) - Fraction(*old['score']['key'][0])
            for row, old in zip(candidate['score']['matches'], control['score']['matches'])}
        delta = [Fraction(*new) - Fraction(*old) for new, old in zip(candidate['score']['key'], control['score']['key'])]
        comparisons[name] = dict(primary_gain=delta[0] > 0, delta=[rational(d) for d in delta],
            paired_primary={key: sum(test(value) for value in changes.values())
                for key, test in (('improved', lambda v: v > 0), ('tied', lambda v: v == 0),
                                  ('regressed', lambda v: v < 0))},
            new_extinctions=[key for key, d in candidate['details'].items()
                             if d['extinct'] and not control['details'][key]['extinct']],
            avoided_extinctions=[key for key, d in candidate['details'].items()
                                 if not d['extinct'] and control['details'][key]['extinct']])
    return dict(models=models, comparisons=comparisons, selected_model=None)


def source_pins():
    paths = {PROTOCOL, *HERE.glob('*.py')}
    for module in tuple(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if filename:
            path = Path(filename).resolve()
            if path.suffix == '.py' and path.is_relative_to(ROOT):
                paths.add(path)
    return {str(path.relative_to(ROOT)): digest(path) for path in sorted(paths)}


def panel_lookup():
    return {(c['model'], c['seed'], c['layout'], c['founder']): c['id']
            for c in plan() if c['phase'] == 'panel'}


def render_gallery(out):
    lookup = panel_lookup()
    for seed in SEEDS:
        folder = out / 'gallery' / seed
        folder.mkdir()
        groups = [[dict(id=lookup[(name, *role)], framebuffer=f'../../runs/{lookup[(name, *role)]}/frame.raw')
                   for name in MODELS] for role in pilot.roles((seed,))]
        metadata = pilot.controls.contact_sheet(folder, groups)
        save(folder / 'gallery.json', metadata | dict(seed=seed, columns=list(MODELS),
            roles=[list(role) for role in pilot.roles((seed,))], png_sha256=digest(folder / 'contact-sheet.png')))


def check(out):
    require(not (out / 'failure.json').exists(), 'failed attempt is not complete')
    scope = read(out / 'started.json')
    require(scope['schema'] == SCHEMA and scope['maximum_native_calls'] == MAX_CALLS and
            scope['submission_seconds'] == MAX_SECONDS and scope['maximum_bytes'] == MAX_BYTES and
            scope['minimum_free_bytes'] == MIN_FREE and scope['workers'] == 2 and
            scope['timeout_seconds'] == 180 and scope['automatic_retry'] is False and
            scope['training_runs'] == 0 and scope['selected_model'] is None and
            scope['plan'] == plan() and scope['archive_sha256'] == ARCHIVE_SHA, 'scope/plan differs')
    require(digest(ARCHIVE) == ARCHIVE_SHA and scope['identities'] == baseline()['identities'] and
            (out / 'growth.tgl').read_bytes() == baseline()['growth'], 'runtime or W2 differs')
    required = {str(PROTOCOL.relative_to(ROOT))} | {str(p.relative_to(ROOT)) for p in HERE.glob('*.py')}
    require(required <= set(scope['source_sha256']), 'missing protocol/checker source')
    for name, expected in scope['source_sha256'].items():
        path = Path(name)
        require(not path.is_absolute() and '..' not in path.parts, 'unsafe source path')
        require(digest(ROOT / path) == expected == digest(out / 'source' / path), 'source snapshot differs')
    tests = read(out / 'tests.json')
    require(tests['returncode'] == 0 and tests['stdout'] == '' and
            f'Ran {TEST_COUNT} tests' in tests['stderr'] and tests['stderr'].endswith('OK\n'), 'preflight tests failed')
    for name, raw in baseline()['models'].items():
        require((out / 'models' / (name + '.tlf')).read_bytes() == raw and
                read(out / 'models' / (name + '.json')) == dict(name=name, sha256=sha(raw),
                    provenance=dict(kind='frozen-pilot-policy', archive_sha256=ARCHIVE_SHA)), 'model provenance differs')
    audit = read(out / 'seed-audit.json')
    require(audit['seeds'] == list(SEEDS) and audit['matches'] == [] and len(audit['files']) >= 1000 and
            all(not Path(p).is_absolute() and '..' not in Path(p).parts and len(h) == 64
                for p, h in audit['files'].items()), 'fresh seed audit differs')
    require(datetime.fromisoformat(audit['checked_utc']) <=
            datetime.fromisoformat(read(out / 'runs/call0001/started.json')['submitted_utc']), 'seed audit was late')
    require({p.name for p in (out / 'runs').iterdir()} == {c['id'] for c in plan()}, 'call roster differs')
    values, intervals = {}, []
    for expected in plan():
        ref = expected['id']
        call, values[ref] = pilot.load_call(out, ref, scope['identities'])
        require(call == expected, 'call differs from roster')
        start, receipt = (read(out / 'runs' / ref / name) for name in ('started.json', 'process.json'))
        require(0 <= start['since_first_seconds'] < MAX_SECONDS, 'submission ceiling exceeded')
        begin, end = (datetime.fromisoformat(t) for t in (start['submitted_utc'], receipt['finished_utc']))
        require(end > begin, 'invalid process interval')
        intervals.append((begin, end))
    previous_end = None
    groups = [[i] for i in range(3)] + [list(range(i, i + 2)) for i in range(3, 99, 2)] + [[i] for i in range(99, 123)]
    for indices in groups:
        require(previous_end is None or min(intervals[i][0] for i in indices) >= previous_end,
                'batch/serial ordering differs')
        previous_end = max(intervals[i][1] for i in indices)
    for call in plan()[:3]:
        old = baseline()['anchors'][call['model']]
        folder = out / 'runs' / call['id']
        require((folder / 'stdout.json').read_bytes() == old['stdout'] and
                (folder / 'frame.raw').read_bytes() == old['pixels'], 'archived reference differs')
    lookup = panel_lookup()
    for call in plan()[99:]:
        ref = lookup[(call['model'], call['seed'], call['layout'], call['founder'])]
        require(values[ref] | dict(framebuffer_crc32=None) == values[call['id']], 'serial capture parity differs')
    for seed in SEEDS:
        folder = out / 'gallery' / seed
        rows = [[lookup[(name, *role)] for name in MODELS] for role in pilot.roles((seed,))]
        metadata = read(folder / 'gallery.json')
        require(metadata == dict(width=752, height=1992, gap=8, rows=rows, seed=seed, columns=list(MODELS),
            roles=[list(role) for role in pilot.roles((seed,))], png_sha256=digest(folder / 'contact-sheet.png')),
            'gallery binding differs')
        rgb = {ref: pilot.controls.rgb565be_to_rgb888((out / 'runs' / ref / 'frame.raw').read_bytes())
               for row in rows for ref in row}
        require(pilot.control_evidence.png_rgb((folder / 'contact-sheet.png').read_bytes(), 752, 1992) ==
                pilot.control_evidence.expected_sheet(rows, rgb), 'gallery pixels differ')
    first = intervals[0][0]
    return dict(schema=SCHEMA, scope=scope, native_calls=123, panel_matches=96, exact_anchors=3,
        exact_serial_capture_checks=24, elapsed_seconds=(intervals[-1][1] - first).total_seconds(),
        analysis=analyze({c['id']: values[c['id']] for c in plan() if c['phase'] == 'panel'}))


def short(result):
    return dict(native_calls=result['native_calls'], elapsed_seconds=result['elapsed_seconds'],
        models={name: dict(key=data['score']['key'], renewal=data['score']['roles_with_renewal'],
            alive=data['living_families'], dormant=data['dormant_families'], extinct=data['extinct_families'],
            closing=data['closing_window_families'], every=data['every_window_families'])
            for name, data in result['analysis']['models'].items()}, comparisons=result['analysis']['comparisons'])


def main(out):
    require(out.parent == ROOT / 'artifacts' and not out.exists() and not out.is_symlink(), 'fresh output required')
    identities, _ = pilot.controls.verify_inputs()
    require(identities == baseline()['identities'], 'runtime identity differs from pilot')
    audit = seed_audit()
    require(not audit['matches'], 'weather already appears: ' + ', '.join(audit['matches']))
    pins = source_pins()
    scope = dict(schema=SCHEMA, maximum_native_calls=MAX_CALLS, submission_seconds=MAX_SECONDS,
        maximum_bytes=MAX_BYTES, minimum_free_bytes=MIN_FREE, timeout_seconds=180, workers=2,
        automatic_retry=False, training_runs=0, selected_model=None, identities=identities,
        archive_sha256=ARCHIVE_SHA, source_sha256=pins, plan=plan(), created_utc=pilot.utc())
    out.mkdir()
    for name in ('models', 'runs', 'gallery', 'source'):
        (out / name).mkdir()
    save(out / 'started.json', scope)
    save(out / 'seed-audit.json', audit)
    runner = pilot.Pilot(out, identities)
    runner.limits = Limits(out)
    try:
        for name, identity in pins.items():
            target = out / 'source' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
            require(digest(target) == identity, 'source changed while copying')
        tests = subprocess.run([sys.executable, str(HERE / 'test_generalization.py'), '-v'],
                               capture_output=True, text=True, timeout=60)
        save(out / 'tests.json', dict(returncode=tests.returncode, stdout=tests.stdout, stderr=tests.stderr))
        require(tests.returncode == 0 and f'Ran {TEST_COUNT} tests' in tests.stderr, tests.stdout + tests.stderr)
        (out / 'growth.tgl').write_bytes(baseline()['growth'])
        for name, raw in baseline()['models'].items():
            runner.put_model(name, raw, dict(kind='frozen-pilot-policy', archive_sha256=ARCHIVE_SHA))
        print('Preflight passed; starting three archived references, then 96 panel matches and 24 confirmations.', flush=True)

        def anchor(call, value):
            old = baseline()['anchors'][call['model']]
            folder = out / 'runs' / call['id']
            require(value == json.loads(old['stdout']) and (folder / 'stdout.json').read_bytes() == old['stdout'] and
                    (folder / 'frame.raw').read_bytes() == old['pixels'], 'archived reference differs')

        calls = plan()
        batches(calls[:3], runner.submit, runner.execute, anchor, workers=1)
        captured = batches(calls[3:99], runner.submit, runner.execute, lambda call, value: None)
        lookup = panel_lookup()

        def confirmation(call, value):
            ref = lookup[(call['model'], call['seed'], call['layout'], call['founder'])]
            require(captured[ref] | dict(framebuffer_crc32=None) == value, 'serial capture parity differs')

        batches(calls[99:], runner.submit, runner.execute, confirmation, workers=1)
        render_gallery(out)
        require(source_pins() == pins and digest(ARCHIVE) == ARCHIVE_SHA and
                pilot.controls.verify_inputs()[0] == identities and runner.limits.size() < MAX_BYTES,
                'inputs/storage changed')
        result = check(out)
        save(out / 'result.json', result)
        print(json.dumps(short(result)), flush=True)
    except BaseException as error:
        save(out / 'failure.json', dict(error=repr(error), submitted_calls=runner.limits.count,
            failed_utc=pilot.utc(), automatic_retry=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--check', type=Path)
    args = parser.parse_args()
    if args.check:
        require(args.out is None, 'check cannot run research')
        result = check(args.check.resolve())
        require(result == read(args.check / 'result.json'), 'saved result differs')
        print(json.dumps(short(result), indent=2))
    else:
        require(args.out is not None, 'fresh output required')
        main(args.out.resolve())
