#!/usr/bin/env python3
"""Same-observation shadow decisions; six fixed replays, no alternative actions applied."""

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import gzip
import io
import json
from pathlib import Path
import struct
import time
import zlib

import population_trace as trace

collect, prepare, score = trace.collect, trace.prepare, trace.score
FIRST_DAY, END_DAY = 208, 224
STOP = trace.STOP
WORKERS, CALL_SECONDS, BUDGET_SECONDS = 2, 180, 900
BASELINE = collect.ROOT / 'benchmarks/garden-seasons/leaf-population-trace-results.json.gz'
BASELINE_SHA = 'b85e6ac58ee50462a4c025a1c3adb09c496b3f1ac7aa569b27d719737eb40178'
PROTOCOL = collect.ROOT / 'benchmarks/garden-seasons/leaf-population-shadow-protocol.md'
ARCHIVE_SCHEMA = 'garden-population-shadow-evidence-v1'
SCALES = (255, 255, 256, 512, 32, 240, 240, 16, 16, 16, 16)


def divide(value, denominator):
    """C's signed integer division, not Python's negative floor division."""
    return (-1 if value < 0 else 1) * (abs(value) // denominator)


def decode(raw):
    score.require(len(raw) == 172 and struct.unpack_from('<4sHHII', raw) ==
                  (b'TLF1', 1, 16, 156, zlib.crc32(raw[16:])), 'invalid model container')
    p = raw[16:]
    magic, version, features, hs, os, r0, r1 = struct.unpack_from('<4sHHBBBB', p)
    score.require((magic, version, features, r0, r1) == (b'LFN1', 1, 1, 0, 0) and
                  hs <= 15 and os <= 15, 'invalid model header')
    hb, hw = struct.unpack_from('<8i', p, 12), struct.unpack_from('<88b', p, 44)
    ab, aw = struct.unpack_from('<2i', p, 132), struct.unpack_from('<16b', p, 140)
    score.require(all(abs(v) <= 1000000 for v in (*hb, *ab)), 'invalid model bias')
    return hs, os, hb, hw, ab, aw


def network(model, inputs):
    score.require(len(inputs) == 11, 'feature count differs')
    hs, os, hb, hw, ab, aw = model
    features = [divide(max(-s, min(s, v)) * 127, s) for v, s in zip(inputs, SCALES)]
    hidden = [max(0, min(127, divide(hb[u] + sum(hw[u * 11 + i] * f
              for i, f in enumerate(features)), 1 << hs))) for u in range(8)]
    scores = [divide(ab[a] + sum(aw[a * 8 + u] * h for u, h in enumerate(hidden)), 1 << os)
              for a in range(2)]
    return features, hidden, scores


def infer(model, inputs):
    _, _, scores = network(model, inputs)
    return int(scores[1] > scores[0]), scores[1] - scores[0]


def eligible(row):
    condition, _, energy, water, *_ = row['inputs']
    return condition < 255 and energy >= row['inputs'][9] and water >= row['inputs'][10]


def validate_shadow(data, resources, final, models):
    score.require(data['schema'] == 'garden-population-shadow-v1' and data['complete'] is True and
                  data['ticks'] == STOP and data['first_tick'] == FIRST_DAY * score.DAY and
                  data['end_tick'] == END_DAY * score.DAY and data['founder'] == 2 and
                  data['models'] == list(score.MODELS) and data['applied_model'] in score.MODELS,
                  'shadow identity differs')
    applied = score.MODELS.index(data['applied_model'])
    decoded = [decode(models[m]) for m in score.MODELS]
    score.require(len(data['rows']) <= 32768, 'row capacity exceeded')
    by_day = defaultdict(Counter)
    previous, seen = (0, -1), set()
    for row in data['rows']:
        tick, lineage = row['tick'], row['lineage']
        score.require(score.integer(tick, FIRST_DAY * score.DAY + 15, END_DAY * score.DAY) and
                      tick % 15 == 0 and score.integer(lineage, 1, len(final['lineages'])), 'row identity invalid')
        plant = final['lineages'][lineage - 1]
        score.require(final['family_roots'][lineage - 1] == 2 and row['parent'] == plant['parent'] and
                      plant['birth_tick'] <= tick and (plant['death_tick'] is None or tick < plant['death_tick']),
                      'row ancestry/lifetime differs')
        score.require(score.integer(row['plant'], 0, 7) and score.integer(row['node'], 0, 511) and
                      (tick, row['plant']) > previous and (tick, lineage) not in seen,
                      'duplicate or unordered observation')
        previous = tick, row['plant']
        seen.add((tick, lineage))
        limits = ((0, 255), (0, 255), (0, 65535), (0, 65535), (1, 512),
                  (-32768, 32767), (-32768, 32767), (0, 255), (0, 255), (9, 9), (5, 5))
        score.require(len(row['inputs']) == 11 and all(score.integer(v, *bounds)
                      for v, bounds in zip(row['inputs'], limits)) and len(row['memory']) == 8 and
                      all(score.integer(v, -128, 127) for v in row['memory']), 'observation bounds differ')
        expected = [infer(m, row['inputs'])[0] for m in decoded]
        score.require(len(row['actions']) == 3 and all(score.integer(v, 0, 1) for v in row['actions']) and
                      row['actions'] == expected, 'independent inference differs')
        day = (tick - 1) // score.DAY
        counts = by_day[lineage, day]
        counts['observations'] += 1
        counts['proposals'] += expected[applied]
        accepted = expected[applied] and eligible(row)
        counts['renewals'] += int(accepted)
        counts['restored'] += (255 - row['inputs'][0]) if accepted else 0
    expected_days = {(r['lineage'], r['day']): {k: r[k] for k in
                     ('observations', 'proposals', 'renewals', 'restored')}
                     for r in resources['plant_days'] if FIRST_DAY <= r['day'] < END_DAY}
    score.require(set(by_day) <= set(expected_days) and all(
        all(by_day[key][k] == v for k, v in counts.items()) for key, counts in expected_days.items()),
        'daily observations/actions do not reconcile')


def metrics(rows, applied):
    renew = [sum(r['actions'][i] for r in rows) for i in range(3)]
    affordable = [sum(r['actions'][i] and eligible(r) for r in rows) for i in range(3)]
    return dict(observations=len(rows), proposals=renew, immediately_affordable=affordable,
                disagreements_with_applied=[sum(r['actions'][i] != r['actions'][applied] for r in rows)
                                            for i in range(3)],
                patterns=dict(sorted(Counter(''.join(map(str, r['actions'])) for r in rows).items())),
                affordable_patterns=dict(sorted(Counter(''.join(map(str, r['actions']))
                                          for r in rows if eligible(r)).items())))


def summarize(data):
    applied = score.MODELS.index(data['applied_model'])
    return {scope: {window: metrics([r for r in data['rows']
                    if (r['lineage'] == 2) == (scope == 'founder') and first * score.DAY < r['tick'] <= last * score.DAY],
                    applied) for window, first, last in [('all', 208, 224), ('winter', 220, 224),
                    *[(f'day-{day}', day, day + 1) for day in range(208, 224)]]}
            for scope in ('founder', 'descendants')}


def inputs():
    raw = BASELINE.read_bytes()
    score.require(prepare.sha(raw) == BASELINE_SHA, 'prior trace archive differs')
    bundle = json.loads(gzip.decompress(raw))
    score.require(bundle['schema'] == 'garden-population-trace-evidence-v1', 'prior trace schema differs')
    _, models, size = collect.archive_inputs()
    return bundle, models, size


def arguments(call):
    return [call['model'], '58d7d6ca', 'rainfed', str(STOP), 'all',
            '--shadow' if call['mode'] == 'on' else '--trace', '2']


def validate_outputs(out, baseline, models, size):
    results = {}
    for call in trace.roster():
        folder = out / 'runs' / call['id']
        old_prefix = f"runs/{call['model']}-on/"
        final_raw = (folder / 'stdout.json').read_bytes()
        score.require(final_raw == prepare.blob(baseline, old_prefix + 'stdout.json'), 'prior final differs')
        final = json.loads(final_raw)
        score.validate_record(final, models[call['model']], seed='58d7d6ca', layout='rainfed',
                              ticks=STOP, uniform_bytes=size)
        expected = {f'tick-{d * score.DAY:010d}.{ext}' for d in trace.DAYS for ext in ('raw', 'json')}
        expected.add('trace.json')
        for name in expected:
            score.require((folder / 'timeline' / name).read_bytes() ==
                          prepare.blob(baseline, old_prefix + 'timeline/' + name), 'prior checkpoint/trace differs')
        if call['mode'] == 'on':
            expected.add('shadow.json')
            data = json.loads((folder / 'timeline/shadow.json').read_bytes())
            resources = json.loads((folder / 'timeline/trace.json').read_bytes())
            score.require(data['applied_model'] == call['model'], 'applied policy differs')
            validate_shadow(data, resources, final, models)
            results[call['model']] = summarize(data)
        score.require({p.name for p in (folder / 'timeline').iterdir()} == expected, 'output roster differs')
    return results


def sources():
    return collect.sources() | {str(PROTOCOL.relative_to(collect.ROOT)): prepare.sha(PROTOCOL.read_bytes())}


def run(binary, runtime, out):
    score.require(not out.exists() and not out.is_symlink(), 'fresh output directory required')
    baseline, models, size = inputs()
    bundle = prepare.load_archive()
    prepare.check(runtime, prepare.expected_files(bundle))
    digest, pinned = prepare.sha(binary.read_bytes()), sources()
    out.mkdir(parents=True)
    collect.save(out / 'started.json', dict(schema='garden-population-shadow-collection-v1', plan=trace.roster(),
        workers=WORKERS, call_seconds=CALL_SECONDS, budget_seconds=BUDGET_SECONDS,
        baseline_sha256=BASELINE_SHA, runtime_archive_sha256=prepare.ARCHIVE_SHA,
        binary_sha256=digest, sources=pinned, started_utc=datetime.now(timezone.utc).isoformat()))
    try:
        for name in pinned:
            path = out / 'source' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            collect.write(path, (collect.ROOT / name).read_bytes())
        collect.preflight(binary, out)
        began = time.monotonic()
        (out / 'runs').mkdir()
        def worker(call):
            remaining = BUDGET_SECONDS - (time.monotonic() - began)
            score.require(remaining > 0, 'collection budget exhausted')
            folder = out / 'runs' / call['id']
            collect.process_call([str(binary), *arguments(call), str(folder / 'timeline')],
                                 folder, min(remaining, CALL_SECONDS))
            score.require(sum(p.stat().st_size for p in folder.rglob('*') if p.is_file()) <= 24 * 1024**2,
                          'per-run evidence cap exceeded')
            print(f"Completed {call['id']}", flush=True)
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            for model in score.MODELS:
                futures = [pool.submit(worker, c) for c in trace.roster() if c['model'] == model]
                for future in futures:
                    future.result()
        elapsed = time.monotonic() - began
        score.require(elapsed <= BUDGET_SECONDS, 'collection budget exceeded')
        analyses = validate_outputs(out, baseline, models, size)
        prepare.check(runtime, prepare.expected_files(bundle))
        score.require(digest == prepare.sha(binary.read_bytes()) and pinned == sources(),
                      'source or binary changed during collection')
        collect.save(out / 'result.json', dict(complete=True, calls=6, elapsed_seconds=elapsed, analyses=analyses))
        collect.save(out / 'manifest.json', {str(p.relative_to(out)): prepare.sha(p.read_bytes())
                     for p in sorted(out.rglob('*')) if p.is_file()})
        print(json.dumps(dict(complete=True, calls=6, elapsed_seconds=elapsed)), flush=True)
    except BaseException as error:
        collect.save(out / 'failure.json', dict(error=repr(error)))
        raise


def verify(out):
    actual = {}
    for p in out.rglob('*'):
        score.require(not p.is_symlink(), 'symlink in evidence')
        if p.is_file() and p != out / 'manifest.json':
            actual[str(p.relative_to(out))] = prepare.sha(p.read_bytes())
    score.require(actual == json.loads((out / 'manifest.json').read_bytes()) and 'failure.json' not in actual,
                  'manifest differs or collection failed')
    started = json.loads((out / 'started.json').read_bytes())
    score.require(started['schema'] == 'garden-population-shadow-collection-v1' and
                  started['plan'] == trace.roster() and started['baseline_sha256'] == BASELINE_SHA and
                  started['runtime_archive_sha256'] == prepare.ARCHIVE_SHA and
                  (started['workers'], started['call_seconds'], started['budget_seconds']) == (2, 180, 900),
                  'protocol differs')
    for name, sha in started['sources'].items():
        prepare.relative(name)
        score.require(actual['source/' + name] == sha, 'source snapshot differs')
    score.require({p.name for p in (out / 'runs').iterdir()} == {c['id'] for c in trace.roster()}, 'call roster differs')
    for call in trace.roster():
        folder = out / 'runs' / call['id']
        receipt = json.loads((folder / 'process.json').read_bytes())
        score.require(receipt.get('returncode') == 0 and receipt.get('timed_out') is False and
                      0 < receipt['timeout_seconds'] <= CALL_SECONDS and
                      receipt['args'][1:-1] == arguments(call) and
                      Path(receipt['args'][-1]).parts[-3:] == ('runs', call['id'], 'timeline') and
                      (folder / 'stderr.txt').read_bytes() == b'', 'invalid process receipt')
    for name, marker in (('session-tests', '100% tests passed, 0 tests failed out of 7'),
                         ('prepare-tests', 'Ran 10 tests')):
        folder = out / name
        receipt = json.loads((folder / 'process.json').read_bytes())
        score.require(receipt.get('returncode') == 0 and receipt.get('timed_out') is False and marker in
                      (folder / 'stdout.json').read_text() + (folder / 'stderr.txt').read_text(), 'preflight failed')
    result = json.loads((out / 'result.json').read_bytes())
    score.require(result['complete'] is True and result['calls'] == 6 and
                  0 < result['elapsed_seconds'] <= BUDGET_SECONDS and
                  result['analyses'] == validate_outputs(out, *inputs()), 'result differs')
    return result


def package(out, target):
    verify(out)
    files, blobs = {}, {}
    for p in sorted(out.rglob('*')):
        if p.is_file():
            raw = p.read_bytes()
            digest = prepare.sha(raw)
            files[str(p.relative_to(out))], blobs[digest] = digest, raw.hex()
    packed = io.BytesIO()
    with gzip.GzipFile(fileobj=packed, mode='wb', filename='', mtime=0) as stream:
        stream.write(json.dumps(dict(schema=ARCHIVE_SCHEMA, files=files, blobs=blobs),
                                sort_keys=True, separators=(',', ':')).encode())
    collect.write(target, packed.getvalue())


def unpack(archive, target):
    score.require(not target.exists() and not target.is_symlink(), 'fresh unpack directory required')
    bundle = json.loads(gzip.decompress(archive.read_bytes()))
    score.require(bundle['schema'] == ARCHIVE_SCHEMA, 'archive schema differs')
    files = {}
    for name in bundle['files']:
        files[name] = prepare.blob(bundle, name)
    target.mkdir(parents=True)
    for name, raw in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        collect.write(path, raw)
    return verify(target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    r = commands.add_parser('run')
    r.add_argument('--binary', type=Path, required=True)
    r.add_argument('--runtime', type=Path, required=True)
    r.add_argument('--out', type=Path, required=True)
    v = commands.add_parser('verify')
    v.add_argument('out', type=Path)
    p = commands.add_parser('pack')
    p.add_argument('out', type=Path)
    p.add_argument('archive', type=Path)
    u = commands.add_parser('unpack')
    u.add_argument('archive', type=Path)
    u.add_argument('out', type=Path)
    args = parser.parse_args()
    if args.command == 'run':
        run(args.binary.resolve(), args.runtime.resolve(), args.out.resolve())
    elif args.command == 'verify':
        verify(args.out)
    elif args.command == 'pack':
        package(args.out, args.archive)
    else:
        unpack(args.archive, args.out)
