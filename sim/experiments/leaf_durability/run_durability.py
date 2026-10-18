#!/usr/bin/env python3
"""One bounded duration extension of all 96 frozen weather matches."""

import argparse
from datetime import datetime
from fractions import Fraction
from functools import lru_cache
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import sys

import build_durability as build
import durability_score as scoring

previous, pilot, ROOT = build.previous, build.pilot, build.ROOT
require, read, save, digest, sha = previous.require, previous.read, previous.save, previous.digest, previous.sha
HERE, PROTOCOL = build.HERE, build.PROTOCOL
MODELS, SEEDS, DAYS = previous.MODELS, previous.SEEDS, build.DAYS
ARCHIVE = ROOT / 'benchmarks/garden-seasons/leaf-family-generalization-results.json.gz'
ARCHIVE_SHA = '2b1cc660140437c99ae5e0f8980ef23ecc0f34fde3971c1abf37948e6e832094'
SCHEMA = 'garden-leaf-family-durability-v1'
MAX_CALLS, MAX_SECONDS, MAX_BYTES, MIN_FREE = 123, 5400, 512 * 1024**2, 2 * 1024**3
TEST_COUNT = 17


@lru_cache(maxsize=1)
def archive():
    require(digest(ARCHIVE) == ARCHIVE_SHA, 'weather archive changed')
    return json.loads(gzip.decompress(ARCHIVE.read_bytes()))


def archived(name):
    bundle = archive()
    identity = bundle['files'][name]
    raw = bytes.fromhex(bundle['blobs'][identity])
    require(sha(raw) == identity, 'weather archive blob differs')
    return raw


def plan():
    return [c | dict(days=608 if c['phase'] == 'anchor' else DAYS) for c in previous.plan()]


def early_check(value, call):
    old = json.loads(archived(f"runs/{call['id']}/stdout.json"))
    censored = scoring.prefix(value, 608)
    fields = ('lineages', 'seeds', 'family_roots', 'death_causes')
    require(all(censored[k] == old[k] for k in fields), 'day-608 history prefix differs')
    require(scoring.score(censored, call['founder'], 192) ==
            pilot.score_family(old | dict(tick=old['ticks']), call['founder'],
                               start_day=192, window_count=6).record(), 'early score differs')


def preflight_scores():
    for call in plan()[3:99]:
        value = json.loads(archived(f"runs/{call['id']}/stdout.json"))
        early_check(value, call)
    return dict(exact_archived_early_scores=96, archive_sha256=ARCHIVE_SHA)


class Limits(pilot.Limits):
    def submit(self):
        now = self.clock()
        require(self.count < MAX_CALLS, '123-call ceiling reached')
        require(self.first is None or now - self.first < MAX_SECONDS, '90-minute submission deadline reached')
        require(self.size() < MAX_BYTES, 'run folder reached 512 MiB')
        require(shutil.disk_usage(self.root).free >= MIN_FREE, 'less than 2 GiB free')
        if self.first is None:
            self.first, self.first_utc = now, pilot.utc()
        self.count += 1
        return self.count, now - self.first


def source_pins():
    return previous.source_pins() | {str(p.relative_to(ROOT)): digest(p)
                                    for p in (PROTOCOL, *HERE.glob('*.py'))}


def save_runtime(out):
    root = out / 'runtime'
    root.mkdir()
    for group in ('source', 'modules'):
        shutil.copytree(build.OUT / group, root / group)
    for name in ('build.json', 'build-0.json', 'build-1.json', 'build-2.json'):
        shutil.copy2(build.OUT / name, root / name)
    shutil.copy2(build.OLD / 'build.json', root / 'origin-build.json')
    for name in build.CHANGES:
        target = root / 'before' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(build.OLD / name, target)
    for name, path in build.BINARIES.items():
        target = root / 'binaries' / name
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(build.OUT / 'native' / path, target)


def check_runtime(out, scope):
    root = out / 'runtime'
    require(digest(root / 'origin-build.json') == pilot.controls.TEST_BUILD_SHA and
            digest(root / 'build.json') == scope['identities']['durability_build_sha256'], 'build receipt identity differs')
    old, meta = read(root / 'origin-build.json'), read(root / 'build.json')
    require(meta['schema'] == 'garden-leaf-durability-build-v1' and meta['days'] == DAYS and
            meta['old_build_sha256'] == pilot.controls.TEST_BUILD_SHA and
            meta['changes'] == {k: [list(p) for p in v] for k, v in build.CHANGES.items()} and
            meta['recipe_sha256'] == digest(HERE / 'build_durability.py') and
            meta['protocol_sha256'] == digest(PROTOCOL), 'runtime horizon recipe differs')
    expected = {f'{group}/{name}': h for group, field in
                (('source', 'staged_sha256'), ('modules', 'module_sha256')) for name, h in old[field].items()}
    for name, replacements in build.CHANGES.items():
        path = root / 'before' / name
        require(digest(path) == expected[name], 'original changed source differs')
        raw = path.read_text()
        for before, after in replacements:
            require(raw.count(before) == 1, 'ambiguous runtime delta')
            raw = raw.replace(before, after)
        expected[name] = sha(raw.encode())
    actual = {f'{group}/{name}': h for group in ('source', 'modules')
              for name, h in build.inventory(root / group).items()}
    require(actual == expected == meta['files'], 'unexpected runtime source delta')
    require(set(meta['binary_sha256']) == set(build.TARGETS) and
            meta['binary_sha256']['leaf-family-owned'] == scope['identities']['owned_binary_sha256'],
            'runtime executable binding differs')
    for name, identity in meta['binary_sha256'].items():
        require(digest(root / 'binaries' / name) == identity, 'retained binary differs')
    for index in range(3):
        receipt = read(root / f'build-{index}.json')
        require(receipt['returncode'] == 0, 'runtime build/test failed')
        if index == 2:
            require(receipt['args'][-1] == '^(' + '|'.join(build.TESTS) + ')$' and
                    '100% tests passed, 0 tests failed out of 11' in receipt['stdout'], 'runtime suite roster differs')


def analyze(values):
    calls = plan()[3:99]
    require(set(values) == {c['id'] for c in calls}, 'incomplete panel roster')
    periods = {}
    for start in scoring.PERIODS:
        models = {name: scoring.panel([values[c['id']] for c in calls if c['model'] == name], start)
                  for name in MODELS}
        control, comparisons = models['initial'], {}
        for name in MODELS[1:]:
            candidate = models[name]
            changes = [Fraction(*new['score']['key'][0]) - Fraction(*old['score']['key'][0])
                       for new, old in zip(candidate['matches'], control['matches'], strict=True)]
            comparisons[name] = dict(primary_gain=Fraction(*candidate['key'][0]) > Fraction(*control['key'][0]),
                delta=pilot.controls.rational_key([Fraction(*a) - Fraction(*b)
                                                   for a, b in zip(candidate['key'], control['key'], strict=True)]),
                paired_primary={key: sum(test(v) for v in changes) for key, test in
                    (('improved', lambda v: v > 0), ('tied', lambda v: v == 0), ('regressed', lambda v: v < 0))})
        periods[str(start)] = dict(endpoint=start + 416, models=models, comparisons=comparisons)
    losses = {}
    for name in MODELS:
        early = periods['192']['models'][name]
        late = periods['960']['models'][name]
        losses[name] = [previous.label(new['seed'], new['layout'], new['founder'])
                       for new, old in zip(late['matches'], early['matches'], strict=True)
                       if new['status']['extinct'] and not old['status']['extinct']]
    return dict(periods=periods, new_extinctions_after_608=losses, selected_model=None)


def check(out):
    require(not (out / 'failure.json').exists(), 'failed attempt is not complete')
    scope = read(out / 'started.json')
    require(scope['schema'] == SCHEMA and scope['plan'] == plan() and scope['maximum_native_calls'] == MAX_CALLS and
            scope['submission_seconds'] == MAX_SECONDS and scope['maximum_bytes'] == MAX_BYTES and
            scope['minimum_free_bytes'] == MIN_FREE and scope['workers'] == 2 and scope['timeout_seconds'] == 180 and
            scope['automatic_retry'] is False and scope['training_runs'] == 0 and scope['selected_model'] is None and
            scope['weather_archive_sha256'] == ARCHIVE_SHA and scope['model_archive_sha256'] == previous.ARCHIVE_SHA,
            'scope/plan differs')
    require(digest(ARCHIVE) == ARCHIVE_SHA and digest(previous.ARCHIVE) == previous.ARCHIVE_SHA and
            scope['original_identities'] == previous.baseline()['identities'] and
            scope['identities']['growth_model_sha256'] == sha(previous.baseline()['growth']) and
            (out / 'growth.tgl').read_bytes() == previous.baseline()['growth'], 'baseline identities differ')
    required = {str(p.relative_to(ROOT)) for p in (PROTOCOL, *HERE.glob('*.py'))}
    require(required <= set(scope['source_sha256']), 'missing protocol/checker source')
    for name, identity in scope['source_sha256'].items():
        path = Path(name)
        require(not path.is_absolute() and '..' not in path.parts and
                digest(ROOT / path) == identity == digest(out / 'source' / path), 'source snapshot differs')
    check_runtime(out, scope)
    tests = read(out / 'tests.json')
    require(tests['returncode'] == 0 and tests['stdout'] == '' and f'Ran {TEST_COUNT} tests' in tests['stderr'] and
            tests['stderr'].endswith('OK\n'), 'preflight tests failed')
    preflight = read(out / 'score-preflight.json')
    require({k: preflight[k] for k in ('exact_archived_early_scores', 'archive_sha256')} == preflight_scores(),
            'score preflight differs')
    for name, raw in previous.baseline()['models'].items():
        require((out / 'models' / (name + '.tlf')).read_bytes() == raw and
                read(out / 'models' / (name + '.json')) == dict(name=name, sha256=sha(raw),
                  provenance=dict(kind='frozen-pilot-policy', archive_sha256=previous.ARCHIVE_SHA)), 'model provenance differs')
    require({p.name for p in (out / 'runs').iterdir()} == {c['id'] for c in plan()}, 'call roster differs')
    values, intervals = {}, []
    for expected in plan():
        call, value = pilot.load_call(out, expected['id'], scope['identities'])
        require(call == expected, 'call differs from roster')
        values[call['id']] = value
        start, receipt = (read(out / 'runs' / call['id'] / name) for name in ('started.json', 'process.json'))
        require(0 <= start['since_first_seconds'] < MAX_SECONDS, 'submission ceiling exceeded')
        begin, end = (datetime.fromisoformat(t) for t in (start['submitted_utc'], receipt['finished_utc']))
        require(end > begin, 'invalid process interval')
        intervals.append((begin, end))
        if call['phase'] == 'panel':
            early_check(value, call)
    require(datetime.fromisoformat(preflight['checked_utc']) <= intervals[0][0], 'score preflight was late')
    groups = [[i] for i in range(3)] + [list(range(i, i + 2)) for i in range(3, 99, 2)] + [[i] for i in range(99, 123)]
    previous_end = None
    for indices in groups:
        require(previous_end is None or min(intervals[i][0] for i in indices) >= previous_end,
                'batch/serial ordering differs')
        previous_end = max(intervals[i][1] for i in indices)
    for call in plan()[:3]:
        old = previous.baseline()['anchors'][call['model']]
        folder = out / 'runs' / call['id']
        require((folder / 'stdout.json').read_bytes() == old['stdout'] and
                (folder / 'frame.raw').read_bytes() == old['pixels'], 'archived reference differs')
    lookup = previous.panel_lookup()
    for call in plan()[99:]:
        ref = lookup[(call['model'], call['seed'], call['layout'], call['founder'])]
        require(values[ref] | dict(framebuffer_crc32=None) == values[call['id']], 'serial capture parity differs')
    for seed in SEEDS:
        folder = out / 'gallery' / seed
        rows = [[lookup[(name, *role)] for name in MODELS] for role in pilot.roles((seed,))]
        require(read(folder / 'gallery.json') == dict(width=752, height=1992, gap=8, rows=rows, seed=seed,
            columns=list(MODELS), roles=[list(role) for role in pilot.roles((seed,))],
            png_sha256=digest(folder / 'contact-sheet.png')), 'gallery binding differs')
        rgb = {ref: pilot.controls.rgb565be_to_rgb888((out / 'runs' / ref / 'frame.raw').read_bytes())
               for row in rows for ref in row}
        require(pilot.control_evidence.png_rgb((folder / 'contact-sheet.png').read_bytes(), 752, 1992) ==
                pilot.control_evidence.expected_sheet(rows, rgb), 'gallery pixels differ')
    return dict(schema=SCHEMA, scope=scope, native_calls=123, panel_matches=96, exact_anchors=3,
        exact_day608_prefixes=96, exact_serial_capture_checks=24,
        elapsed_seconds=(intervals[-1][1] - intervals[0][0]).total_seconds(),
        analysis=analyze({c['id']: values[c['id']] for c in plan()[3:99]}))


def short(result):
    return dict(native_calls=result['native_calls'], elapsed_seconds=result['elapsed_seconds'],
        periods={start: dict(models={name: {k: data[k] for k in ('key', 'roles_with_renewal', 'living_families',
            'dormant_families', 'extinct_families', 'closing_window_families', 'every_window_families')}
            for name, data in period['models'].items()}, comparisons=period['comparisons'])
            for start, period in result['analysis']['periods'].items()},
        new_extinctions_after_608=result['analysis']['new_extinctions_after_608'])


def main(out):
    require(out.parent == ROOT / 'artifacts' and not out.exists() and not out.is_symlink(), 'fresh output required')
    original, _ = pilot.controls.verify_inputs()
    meta = build.verify()
    identities = dict(owned_binary_sha256=meta['binary_sha256']['leaf-family-owned'],
        growth_model_sha256=original['growth_model_sha256'], durability_build_sha256=digest(build.OUT / 'build.json'))
    score_check = preflight_scores() | dict(checked_utc=pilot.utc())
    pins = source_pins()
    scope = dict(schema=SCHEMA, maximum_native_calls=MAX_CALLS, submission_seconds=MAX_SECONDS,
        maximum_bytes=MAX_BYTES, minimum_free_bytes=MIN_FREE, workers=2, timeout_seconds=180,
        automatic_retry=False, training_runs=0, selected_model=None, identities=identities,
        original_identities=original, weather_archive_sha256=ARCHIVE_SHA,
        model_archive_sha256=previous.ARCHIVE_SHA, source_sha256=pins, plan=plan(), created_utc=pilot.utc())
    out.mkdir()
    for name in ('models', 'runs', 'gallery', 'source'):
        (out / name).mkdir()
    save(out / 'started.json', scope)
    save(out / 'score-preflight.json', score_check)
    runner = pilot.Pilot(out, identities)
    runner.binary, runner.limits = build.OUT / 'native/leaf-family-owned', Limits(out)
    try:
        save_runtime(out)
        for name, identity in pins.items():
            path = out / 'source' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, path)
            require(digest(path) == identity, 'source changed while copying')
        tests = subprocess.run([sys.executable, str(HERE / 'test_durability.py'), '-v'],
                               capture_output=True, text=True, timeout=90)
        save(out / 'tests.json', dict(returncode=tests.returncode, stdout=tests.stdout, stderr=tests.stderr))
        require(tests.returncode == 0 and f'Ran {TEST_COUNT} tests' in tests.stderr, tests.stdout + tests.stderr)
        (out / 'growth.tgl').write_bytes(previous.baseline()['growth'])
        for name, raw in previous.baseline()['models'].items():
            runner.put_model(name, raw, dict(kind='frozen-pilot-policy', archive_sha256=previous.ARCHIVE_SHA))
        print('Preflight passed: 96 exact archived scores; starting 3 anchors, 96 extensions and 24 confirmations.', flush=True)
        def anchor(call, value):
            old = previous.baseline()['anchors'][call['model']]
            folder = out / 'runs' / call['id']
            require((folder / 'stdout.json').read_bytes() == old['stdout'] and
                    (folder / 'frame.raw').read_bytes() == old['pixels'], 'archived reference differs')
        calls = plan()
        previous.batches(calls[:3], runner.submit, runner.execute, anchor, workers=1)
        captured = previous.batches(calls[3:99], runner.submit, runner.execute, lambda c, v: early_check(v, c))
        def confirmation(call, value):
            ref = previous.panel_lookup()[(call['model'], call['seed'], call['layout'], call['founder'])]
            require(captured[ref] | dict(framebuffer_crc32=None) == value, 'serial capture parity differs')
        previous.batches(calls[99:], runner.submit, runner.execute, confirmation, workers=1)
        previous.render_gallery(out)
        require(source_pins() == pins and build.verify() == meta and
                pilot.controls.verify_inputs()[0] == original and runner.limits.size() < MAX_BYTES,
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
