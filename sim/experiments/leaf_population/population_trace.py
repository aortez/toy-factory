#!/usr/bin/env python3
"""Six fixed population replays with read-only resource/seed tracing; no interventions."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from datetime import datetime, timezone
import gzip
import io
import json
from pathlib import Path
import tempfile
import time
import zlib

import collect_population as collect
import population_evidence as evidence
import population_losses as losses
import population_score as score
import prepare

STOP = 256 * score.DAY
DAYS = (0, 32, 192, 256)
WORKERS, CALL_SECONDS, BUDGET_SECONDS = 2, 180, 900
BLOCKERS = ('dormancy', 'moisture', 'light', 'plant-capacity', 'node-capacity', 'spacing', 'cold')
PROTOCOL = collect.ROOT / 'benchmarks/garden-seasons/leaf-population-trace-protocol.md'


def roster():
    return [dict(id=f'{model}-{mode}', model=model, mode=mode) for mode in ('off', 'on') for model in score.MODELS]


def inputs():
    score.require(prepare.sha(losses.ARCHIVE.read_bytes()) == losses.ARCHIVE_SHA, 'baseline archive differs')
    _, models, size = collect.archive_inputs()
    # Verify all original results, not just the selected three histories.
    with tempfile.TemporaryDirectory(prefix='population-trace-baseline-') as temporary:
        root = Path(temporary) / 'baseline'
        evidence.unpack(losses.ARCHIVE, root)
        result = {}
        for model in score.MODELS:
            folder = root / 'runs' / f'{model}-58d7d6ca-rainfed-primary'
            result[model] = dict(final=json.loads((folder / 'stdout.json').read_bytes()),
                captures={day: {ext: (folder / 'timeline' / f'tick-{day * score.DAY:010d}.{ext}').read_bytes()
                               for ext in ('raw', 'json')} for day in DAYS[:-1]})
    return models, size, result


def check_histogram(row):
    for field, limit in (('masks', 127), ('no_living_masks', 127), ('open_sites', 27)):
        score.require(all(str(int(k)) == k and score.integer(int(k), 0, limit) and
                          score.integer(v, 1, 8 * 256 * 256) for k, v in row[field].items()),
                      'invalid sparse histogram')
    score.require(row['checks'] == sum(row['masks'].values()) and
                  row['germinated'] == row['masks'].get('0', 0) and
                  all(v <= row['masks'].get(k, 0) for k, v in row['no_living_masks'].items()),
                  'seed checks do not reconcile')
    if row['checks']:
        score.require(0 <= row['light_min'] <= row['light_max'] <= 255 and
                      0 <= row['moisture_min'] <= row['moisture_max'] <= 255, 'invalid seed resource bounds')
    score.require(all(v <= row['checks'] for v in row['open_sites'].values()), 'site count exceeds checks')


def validate_trace(trace, value):
    score.require(trace['schema'] == 'garden-population-trace-v1' and trace['complete'] is True and
                  trace['founder'] == 2 and trace['ticks'] == STOP and trace['ecology_steps'] == STOP // 15 and
                  len(trace['seed_days']) == 256, 'trace identity/coverage differs')
    plants = {p['id']: p for p in value['lineages'] if value['family_roots'][p['id'] - 1] == 2}
    expected = {}
    for lineage, p in plants.items():
        first = p['birth_tick'] or 15
        last = p['death_tick'] or STOP
        for day in range(256):
            start, end = max(first, day * score.DAY + 15), min(last, (day + 1) * score.DAY)
            if start <= end:
                expected[lineage, day] = (start, end, (end - start) // 15 + 1)
    actual, by_plant = {}, {}
    for row in trace['plant_days']:
        key = row['lineage'], row['day']
        score.require(key not in actual, 'duplicate plant/day')
        actual[key] = row['first_tick'], row['last_tick'], row['samples']
        p = plants[row['lineage']]
        score.require(row['born'] == (p['birth_tick'] != 0 and row['first_tick'] == p['birth_tick']) and
                      row['died'] == (row['last_tick'] == p['death_tick']), 'birth/death sample differs')
        for resource in ('energy', 'water'):
            f = row[resource]
            score.require(all(score.integer(v, 0, 256 * 65535) for v in f.values()), 'invalid resource sum')
            score.require(f['before'] + f['income'] + f['endowment'] ==
                          sum(f[k] for k in ('after', 'overflow', 'upkeep_paid', 'growth', 'seeds', 'discarded', 'repair')),
                          'resource conservation differs')
            score.require(f['upkeep_paid'] <= f['upkeep_due'], 'upkeep payment exceeds due')
            previous = by_plant.get((row['lineage'], resource))
            score.require(previous is None or previous == f['before'], 'daily resource discontinuity')
            by_plant[row['lineage'], resource] = f['after']
        score.require(row['energy']['repair'] == row['renewals'] * 9 and
                      row['water']['repair'] == row['renewals'] * 5 and
                      row['renewals'] <= row['proposals'] <= row['observations'] and
                      row['condition_before'] + row['condition_endowment'] + row['restored'] ==
                      row['condition_after'] + row['worn'], 'leaf conservation differs')
    score.require(actual == expected, 'plant/day coverage differs')
    expected_seeds = {(s['parent'], s['birth_tick'], s['column']): s for s in value['seeds']
                      if s['parent'] in plants and s['birth_tick'] < STOP}
    actual_seeds = {}
    for row in trace['seeds']:
        key = row['parent'], row['birth_tick'], row['column']
        score.require(key not in actual_seeds and key in expected_seeds, 'seed identity differs')
        seed = expected_seeds[key]
        actual_seeds[key] = row
        end = seed['end_tick'] or STOP
        expired, germinated = seed['outcome'] == 'expired', seed['outcome'] == 'germinated'
        c = row['attempts']
        check_histogram(c)
        score.require(row['first_tick'] == seed['birth_tick'] + 15 and row['last_tick'] == end and
                      row['generation'] == seed['generation'] and row['species'] == seed['species'] and
                      row['child'] == (seed['child_id'] or 0) and
                      row['outcome'] == {'pending': 0, 'expired': 1, 'germinated': 2}[seed['outcome']] and
                      c['checks'] == (end - seed['birth_tick']) // 15 - int(expired) and
                      c['expired'] == int(expired) and c['germinated'] == int(germinated), 'seed coverage differs')
        # Lifetime ledgers independently bound the no-living subset. A same-tick
        # birth can precede or follow a waiting seed's sequential check, so do
        # not manufacture an exact ordering from end-of-step history alone.
        minimum, maximum = 0, 0
        for tick in range(seed['birth_tick'] + 15, end + (0 if expired else 15), 15):
            prior = any(p['birth_tick'] < tick and (p['death_tick'] is None or p['death_tick'] > tick)
                        for p in plants.values())
            born_now = any(p['birth_tick'] == tick for p in plants.values())
            maximum += not prior
            minimum += not prior and not born_now
        score.require(minimum <= sum(c['no_living_masks'].values()) <= maximum,
                      'no-living subset disagrees with lifetime ledger')
    score.require(actual_seeds.keys() == expected_seeds.keys(), 'missing attempted seed')
    for row in trace['seed_days']:
        check_histogram(row)
    for field in ('checks', 'expired', 'germinated'):
        score.require(sum(s['attempts'][field] for s in trace['seeds']) ==
                      sum(s[field] for s in trace['seed_days']), 'daily seed totals differ')
    for field in ('masks', 'no_living_masks', 'open_sites'):
        a, b = Counter(), Counter()
        for row in trace['seeds']:
            a.update(row['attempts'][field])
        for row in trace['seed_days']:
            b.update(row[field])
        score.require(a == b, 'daily seed histogram differs')


def summarize(trace, value):
    family = losses.family_rows(value)[1]
    deaths = []
    for row in trace['plant_days']:
        if row['died']:
            lineage = row['lineage']
            death = value['lineages'][lineage - 1]['death_tick']
            # Last full calendar year plus the final partial day, not a causal counterfactual.
            start_day = max(0, (death - 1) // score.DAY - 15)
            selected = [r for r in trace['plant_days'] if r['lineage'] == lineage and r['day'] >= start_day]
            deaths.append(dict(lineage=lineage, tick=death, from_day=start_day,
                energy={k: (selected[0]['energy'][k] if k == 'before' else selected[-1]['energy'][k]
                            if k == 'after' else sum(r['energy'][k] for r in selected)) for k in row['energy']},
                energy_short_steps=sum(r['energy_short'] for r in selected),
                water_short_steps=sum(r['water_short'] for r in selected),
                renewals=sum(r['renewals'] for r in selected), final_day=row))
    terminal = {(s['parent'], s['birth_tick'], s['column']) for s in family['seeds_at_last_living_death']}
    seeds = []
    for s in trace['seeds']:
        if (s['parent'], s['birth_tick'], s['column']) not in terminal:
            continue
        c = s['attempts']
        seeds.append(dict(parent=s['parent'], birth_tick=s['birth_tick'], column=s['column'],
            end_tick=s['last_tick'], checks=c['checks'], blockers={name: sum(v for k, v in c['masks'].items()
                if int(k) & (1 << bit)) for bit, name in enumerate(BLOCKERS)},
            no_living_checks=sum(c['no_living_masks'].values()),
            no_living_blockers={name: sum(v for k, v in c['no_living_masks'].items()
                if int(k) & (1 << bit)) for bit, name in enumerate(BLOCKERS)}, open_sites=c['open_sites']))
    return dict(family=family, deaths=deaths, terminal_seeds=seeds)


def validate_outputs(out, baseline, models, size):
    analyses = {}
    for call in roster():
        folder = out / 'runs' / call['id']
        value = json.loads((folder / 'stdout.json').read_bytes())
        for day in DAYS:
            prefix = folder / 'timeline' / f'tick-{day * score.DAY:010d}'
            raw, encoded = prefix.with_suffix('.raw').read_bytes(), prefix.with_suffix('.json').read_bytes()
            record = json.loads(encoded)
            score.validate_record(record, models[call['model']], seed='58d7d6ca', layout='rainfed',
                                  ticks=day * score.DAY, uniform_bytes=size)
            score.require(len(raw) == 115200 and record['framebuffer_crc32'] == f'{zlib.crc32(raw):08x}',
                          'capture differs')
            score.require(score.history_prefix(baseline[call['model']]['final'], day * score.DAY) ==
                          score.history_prefix(record, day * score.DAY), 'original history prefix differs')
            if day != 256:
                old = baseline[call['model']]['captures'][day]
                score.require(raw == old['raw'] and encoded == old['json'], 'original checkpoint differs')
            if call['mode'] == 'on':
                other = out / 'runs' / f"{call['model']}-off" / 'timeline' / prefix.name
                score.require(raw == other.with_suffix('.raw').read_bytes() and
                              encoded == other.with_suffix('.json').read_bytes(), 'trace changed checkpoint')
        score.require(value == record, 'stdout differs from final checkpoint')
        expected = {f'tick-{d * score.DAY:010d}.{ext}' for d in DAYS for ext in ('raw', 'json')}
        if call['mode'] == 'on':
            expected.add('trace.json')
            trace = json.loads((folder / 'timeline/trace.json').read_bytes())
            validate_trace(trace, value)
            analyses[call['model']] = summarize(trace, value)
        score.require({p.name for p in (folder / 'timeline').iterdir()} == expected, 'output roster differs')
    return analyses


def pinned_sources():
    return collect.sources() | {str(PROTOCOL.relative_to(collect.ROOT)): prepare.sha(PROTOCOL.read_bytes())}


def run(binary, runtime, out):
    score.require(not out.exists() and not out.is_symlink(), 'fresh output directory required')
    models, size, baseline = inputs()
    bundle = prepare.load_archive()
    prepare.check(runtime, prepare.expected_files(bundle))
    digest, sources = prepare.sha(binary.read_bytes()), pinned_sources()
    out.mkdir(parents=True)
    collect.save(out / 'started.json', dict(schema='garden-population-trace-collection-v1', plan=roster(),
        workers=WORKERS, call_seconds=CALL_SECONDS, budget_seconds=BUDGET_SECONDS,
        baseline_sha256=losses.ARCHIVE_SHA, runtime_archive_sha256=prepare.ARCHIVE_SHA,
        binary_sha256=digest, sources=sources, started_utc=datetime.now(timezone.utc).isoformat()))
    try:
        for name in sources:
            path = out / 'source' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            collect.write(path, (collect.ROOT / name).read_bytes())
        collect.preflight(binary, out)
        began = time.monotonic()
        (out / 'runs').mkdir()
        def worker(call):
            remaining = BUDGET_SECONDS - (time.monotonic() - began)
            score.require(remaining > 0, 'collection time exhausted')
            folder = out / 'runs' / call['id']
            args = [str(binary), call['model'], '58d7d6ca', 'rainfed', str(STOP), 'all']
            args += ['--trace', '2'] if call['mode'] == 'on' else ['--timeline']
            args += [str(folder / 'timeline')]
            collect.process_call(args, folder, min(remaining, CALL_SECONDS))
            score.require(sum(p.stat().st_size for p in folder.rglob('*') if p.is_file()) <= 24 * 1024**2,
                          'per-run evidence cap exceeded')
            print(f"Completed {call['id']}", flush=True)
        # Three pairs: stop submitting after any failure; at most two active calls.
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            for model in score.MODELS:
                futures = [pool.submit(worker, c) for c in roster() if c['model'] == model]
                for future in futures:
                    future.result()
        elapsed = time.monotonic() - began
        score.require(elapsed <= BUDGET_SECONDS, 'collection budget exceeded')
        analyses = validate_outputs(out, baseline, models, size)
        prepare.check(runtime, prepare.expected_files(bundle))
        score.require(digest == prepare.sha(binary.read_bytes()) and sources == pinned_sources(),
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
    score.require(actual == json.loads((out / 'manifest.json').read_bytes()) and
                  'failure.json' not in actual, 'manifest differs or collection failed')
    started = json.loads((out / 'started.json').read_bytes())
    score.require(started['plan'] == roster() and started['baseline_sha256'] == losses.ARCHIVE_SHA and
                  started['runtime_archive_sha256'] == prepare.ARCHIVE_SHA and
                  (started['workers'], started['call_seconds'], started['budget_seconds']) == (2, 180, 900),
                  'protocol differs')
    for name, sha in started['sources'].items():
        prepare.relative(name)
        score.require(actual['source/' + name] == sha, 'source snapshot differs')
    score.require({p.name for p in (out / 'runs').iterdir()} == {c['id'] for c in roster()}, 'call roster differs')
    for call in roster():
        folder = out / 'runs' / call['id']
        receipt = json.loads((folder / 'process.json').read_bytes())
        expected = [call['model'], '58d7d6ca', 'rainfed', str(STOP), 'all']
        expected += ['--trace', '2'] if call['mode'] == 'on' else ['--timeline']
        score.require(receipt.get('returncode') == 0 and receipt.get('timed_out') is False and
                      0 < receipt['timeout_seconds'] <= CALL_SECONDS and
                      receipt['args'][1:-1] == expected and
                      Path(receipt['args'][-1]).parts[-3:] == ('runs', call['id'], 'timeline') and
                      (folder / 'stderr.txt').read_bytes() == b'', 'invalid process receipt')
    for name, marker in (('session-tests', '100% tests passed, 0 tests failed out of 7'),
                         ('prepare-tests', 'Ran 10 tests')):
        folder = out / name
        receipt = json.loads((folder / 'process.json').read_bytes())
        score.require(receipt.get('returncode') == 0 and receipt.get('timed_out') is False and marker in
                      (folder / 'stdout.json').read_text() + (folder / 'stderr.txt').read_text(), 'preflight failed')
    models, size, baseline = inputs()
    result = json.loads((out / 'result.json').read_bytes())
    score.require(result['complete'] is True and result['calls'] == 6 and
                  0 < result['elapsed_seconds'] <= BUDGET_SECONDS and
                  result['analyses'] == validate_outputs(out, baseline, models, size), 'result differs')
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
        stream.write(json.dumps(dict(schema='garden-population-trace-evidence-v1', files=files, blobs=blobs),
                                sort_keys=True, separators=(',', ':')).encode())
    collect.write(target, packed.getvalue())


def unpack(archive, target):
    score.require(not target.exists() and not target.is_symlink(), 'fresh unpack directory required')
    bundle = json.loads(gzip.decompress(archive.read_bytes()))
    score.require(bundle['schema'] == 'garden-population-trace-evidence-v1', 'archive schema differs')
    files = {}
    for name, digest in bundle['files'].items():
        prepare.relative(name)
        raw = bytes.fromhex(bundle['blobs'][digest])
        score.require(prepare.sha(raw) == digest, 'archive hash differs')
        files[name] = raw
    target.mkdir(parents=True)
    for name, raw in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        collect.write(path, raw)
    return verify(target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('run')
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--runtime', type=Path, default=prepare.DEFAULT)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('verify')
    p.add_argument('directory', type=Path)
    for name in ('pack', 'unpack'):
        p = sub.add_parser(name)
        p.add_argument('source', type=Path)
        p.add_argument('target', type=Path)
    args = parser.parse_args()
    if args.command == 'run':
        run(args.binary.resolve(), args.runtime.resolve(), args.out.absolute())
    elif args.command == 'verify':
        verify(args.directory)
        print('Verified six calls, original histories/checkpoints, trace parity and conservation.')
    elif args.command == 'pack':
        package(args.source, args.target)
    else:
        unpack(args.source, args.target)
