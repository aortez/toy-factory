#!/usr/bin/env python3
"""Fixed day-608 follow-up of the four scheduled gate interventions."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import io
import json
from pathlib import Path
import time
from typing import Callable
import zlib

import population_gates as gates

collect, prepare, score, trace = gates.collect, gates.prepare, gates.score, gates.trace
VARIANTS = gates.VARIANTS
DAYS = gates.DAYS + (384, 512, 608)
STOP = 608 * score.DAY
WORKERS, CALL_SECONDS, BUDGET_SECONDS = 2, 180, 900
BASELINE = collect.ROOT / 'benchmarks/garden-seasons/leaf-population-gates-results.json.gz'
BASELINE_SHA = 'a73a6f20cf420348fe1684ef73ea0ea081e872586c91287a4c7940064d9147a1'
PROTOCOL = collect.ROOT / 'benchmarks/garden-seasons/leaf-population-gates-long-protocol.md'
ARCHIVE_SCHEMA = 'garden-population-gates-long-evidence-v1'


@dataclass(frozen=True)
class Experiment:
    """Trusted in-tree recipe; archive data can never supply executable hooks."""
    collection_schema: str
    archive_schema: str
    baseline_sha: str
    protocol: Path
    inputs: Callable
    arguments: Callable
    validate_outputs: Callable
    roster: Callable = gates.roster


def inputs():
    raw = BASELINE.read_bytes()
    score.require(prepare.sha(raw) == BASELINE_SHA, 'short gate archive differs')
    baseline = json.loads(gzip.decompress(raw))
    score.require(baseline['schema'] == gates.ARCHIVE_SCHEMA, 'short gate schema differs')
    _, models, size = collect.archive_inputs()
    return baseline, models, size


def cohort(plants, stop):
    reached = sum(trace.losses.established(p, stop) for p in plants)
    early = sum(p['death_tick'] is not None and
                p['death_tick'] <= p['birth_tick'] + 32 * score.DAY for p in plants)
    young = sum(p['death_tick'] is None and p['birth_tick'] + 32 * score.DAY > stop for p in plants)
    score.require(len(plants) == reached + early + young, 'cohort outcomes do not reconcile')
    return dict(born=len(plants), established=reached, early_deaths=early, young_alive=young,
                living=sum(p['death_tick'] is None for p in plants), lineages=[p['id'] for p in plants])


def summarize(value, *, after_tick=gates.AFTER):
    score.validate_history(value)
    score.require(value['ticks'] == STOP, 'day-608 endpoint required')
    plants = value['lineages']
    children = [p for p, root in zip(plants, value['family_roots'], strict=True) if root == 2 and p['parent']]
    new = [p for p in children if p['birth_tick'] > after_tick]
    born_by_switch = [p for p in children if p['birth_tick'] <= after_tick]
    generations = {}
    for p in plants:
        generations[p['id']] = 0 if not p['parent'] else generations[p['parent']] + 1
    return dict(families=trace.losses.family_rows(value),
        renewal={str(f): score.family_score(value, f, 192) for f in range(1, 4)},
        cohorts=dict(born_by_switch=cohort(born_by_switch, STOP), born_after_switch=cohort(new, STOP),
                     new_nonfounder_children=cohort([p for p in new if plants[p['parent'] - 1]['parent']], STOP)),
        shrub_lineages=[dict(p, generation=generations[p['id']], established=trace.losses.established(p, STOP))
                        for p, root in zip(plants, value['family_roots'], strict=True) if root == 2],
        checkpoints={str(day): next(r for r in reversed(score.event_timeline(value))
                                   if r['tick'] <= day * score.DAY) for day in (208, 256, 384, 512, 608)})


def validate_outputs(out, baseline, models, size):
    analyses = {}
    for call in gates.roster():
        folder = out / 'runs' / call['id']
        final = json.loads((folder / 'stdout.json').read_bytes())
        expected = {f'tick-{d * score.DAY:010d}.{ext}' for d in DAYS for ext in ('raw', 'json')}
        for day in DAYS:
            name = f'tick-{day * score.DAY:010d}'
            prefix = folder / 'timeline' / name
            encoded, raw = prefix.with_suffix('.json').read_bytes(), prefix.with_suffix('.raw').read_bytes()
            value = json.loads(encoded)
            gates.underlying(value, call['variant'], models, size, day * score.DAY)
            score.require(len(raw) == 115200 and value['framebuffer_crc32'] == f'{zlib.crc32(raw):08x}',
                          'capture differs')
            score.require(score.history_prefix(final, day * score.DAY) == score.history_prefix(value, day * score.DAY),
                          'history prefix differs')
            if call['mode'] == 'on':
                other = out / 'runs' / f"{call['variant']}-off" / 'timeline' / name
                score.require(encoded == other.with_suffix('.json').read_bytes() and
                              raw == other.with_suffix('.raw').read_bytes(), 'trace changed checkpoint')
            if day in gates.DAYS:
                old = f"runs/{call['id']}/timeline/{name}"
                score.require(encoded == prepare.blob(baseline, old + '.json') and
                              raw == prepare.blob(baseline, old + '.raw'), 'short gate checkpoint differs')
        score.require(final == value, 'stdout differs from endpoint')
        if call['mode'] == 'on':
            expected.add('trace.json')
            resources = (folder / 'timeline/trace.json').read_bytes()
            score.require(resources == prepare.blob(baseline, f"runs/{call['id']}/timeline/trace.json"),
                          'frozen trace differs')
            anchor = json.loads((folder / 'timeline' / f'tick-{gates.STOP:010d}.json').read_bytes())
            trace.validate_trace(json.loads(resources), anchor)
            analyses[call['variant']] = summarize(final)
        score.require({p.name for p in (folder / 'timeline').iterdir()} == expected, 'output roster differs')
    return analyses


def sources(experiment=None):
    protocol = (experiment or DEFAULT).protocol
    return collect.sources() | {str(protocol.relative_to(collect.ROOT)): prepare.sha(protocol.read_bytes())}


def arguments(call):
    return ['--gate-long', call['variant'], call['mode']]


DEFAULT = Experiment('garden-population-gates-long-collection-v1', ARCHIVE_SCHEMA,
                     BASELINE_SHA, PROTOCOL, inputs, arguments, validate_outputs)


def run(binary, runtime, out, *, experiment=DEFAULT):
    score.require(not out.exists() and not out.is_symlink(), 'fresh output directory required')
    baseline, models, size = experiment.inputs()
    plan = experiment.roster()
    bundle = prepare.load_archive()
    prepare.check(runtime, prepare.expected_files(bundle))
    digest, pinned = prepare.sha(binary.read_bytes()), sources(experiment)
    out.mkdir(parents=True)
    collect.save(out / 'started.json', dict(schema=experiment.collection_schema, plan=plan,
        workers=WORKERS, call_seconds=CALL_SECONDS, budget_seconds=BUDGET_SECONDS,
        baseline_sha256=experiment.baseline_sha, runtime_archive_sha256=prepare.ARCHIVE_SHA,
        derived_models={v: gates.derive(models, v).hex() for v in VARIANTS},
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
            collect.process_call([str(binary), *experiment.arguments(call), str(folder / 'timeline')],
                                 folder, min(remaining, CALL_SECONDS))
            score.require(sum(p.stat().st_size for p in folder.rglob('*') if p.is_file()) <= 24 * 1024**2,
                          'per-run evidence cap exceeded')
            print(f"Completed {call['id']}", flush=True)
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            for offset in range(0, len(plan), WORKERS):
                futures = [pool.submit(worker, c) for c in plan[offset:offset + WORKERS]]
                for future in futures:
                    future.result()
        elapsed = time.monotonic() - began
        score.require(elapsed <= BUDGET_SECONDS, 'collection budget exceeded')
        analyses = experiment.validate_outputs(out, baseline, models, size)
        prepare.check(runtime, prepare.expected_files(bundle))
        score.require(digest == prepare.sha(binary.read_bytes()) and pinned == sources(experiment),
                      'source or binary changed during collection')
        collect.save(out / 'result.json', dict(complete=True, calls=len(plan), elapsed_seconds=elapsed, analyses=analyses))
        collect.save(out / 'manifest.json', {str(p.relative_to(out)): prepare.sha(p.read_bytes())
                     for p in sorted(out.rglob('*')) if p.is_file()})
        print(json.dumps(dict(complete=True, calls=len(plan), elapsed_seconds=elapsed)), flush=True)
    except BaseException as error:
        collect.save(out / 'failure.json', dict(error=repr(error)))
        raise


def verify(out, *, experiment=DEFAULT):
    plan = experiment.roster()
    actual = {}
    for p in out.rglob('*'):
        score.require(not p.is_symlink(), 'symlink in evidence')
        if p.is_file() and p != out / 'manifest.json':
            actual[str(p.relative_to(out))] = prepare.sha(p.read_bytes())
    score.require(actual == json.loads((out / 'manifest.json').read_bytes()) and 'failure.json' not in actual,
                  'manifest differs or collection failed')
    baseline, models, size = experiment.inputs()
    started = json.loads((out / 'started.json').read_bytes())
    score.require(started['schema'] == experiment.collection_schema and
                  started['plan'] == plan and started['baseline_sha256'] == experiment.baseline_sha and
                  started['runtime_archive_sha256'] == prepare.ARCHIVE_SHA and
                  started['derived_models'] == {v: gates.derive(models, v).hex() for v in VARIANTS} and
                  (started['workers'], started['call_seconds'], started['budget_seconds']) == (2, 180, 900),
                  'protocol differs')
    for name, digest in started['sources'].items():
        prepare.relative(name)
        score.require(actual['source/' + name] == digest, 'source snapshot differs')
    score.require({p.name for p in (out / 'runs').iterdir()} == {c['id'] for c in plan}, 'call roster differs')
    for call in plan:
        folder = out / 'runs' / call['id']
        receipt = json.loads((folder / 'process.json').read_bytes())
        score.require(receipt.get('returncode') == 0 and receipt.get('timed_out') is False and
                      0 < receipt['timeout_seconds'] <= CALL_SECONDS and
                      receipt['args'][1:-1] == experiment.arguments(call) and
                      Path(receipt['args'][-1]).parts[-3:] == ('runs', call['id'], 'timeline') and
                      (folder / 'stderr.txt').read_bytes() == b'', 'invalid process receipt')
        score.require(sum(p.stat().st_size for p in folder.rglob('*') if p.is_file()) <= 24 * 1024**2,
                      'per-run evidence cap exceeded')
    for name, marker in (('session-tests', '100% tests passed, 0 tests failed out of 7'),
                         ('prepare-tests', 'Ran 10 tests')):
        folder = out / name
        receipt = json.loads((folder / 'process.json').read_bytes())
        score.require(receipt.get('returncode') == 0 and receipt.get('timed_out') is False and marker in
                      (folder / 'stdout.json').read_text() + (folder / 'stderr.txt').read_text(), 'preflight failed')
    result = json.loads((out / 'result.json').read_bytes())
    score.require(result['complete'] is True and result['calls'] == len(plan) and
                  0 < result['elapsed_seconds'] <= BUDGET_SECONDS and
                  result['analyses'] == experiment.validate_outputs(out, baseline, models, size), 'result differs')
    return result


def package(out, target, *, experiment=DEFAULT):
    verify(out, experiment=experiment)
    files, blobs = {}, {}
    for p in sorted(out.rglob('*')):
        if p.is_file():
            raw = p.read_bytes()
            digest = prepare.sha(raw)
            files[str(p.relative_to(out))], blobs[digest] = digest, raw.hex()
    packed = io.BytesIO()
    with gzip.GzipFile(fileobj=packed, mode='wb', filename='', mtime=0) as stream:
        stream.write(json.dumps(dict(schema=experiment.archive_schema, files=files, blobs=blobs),
                                sort_keys=True, separators=(',', ':')).encode())
    collect.write(target, packed.getvalue())


def unpack(archive, target, *, experiment=DEFAULT):
    score.require(not target.exists() and not target.is_symlink(), 'fresh unpack directory required')
    bundle = json.loads(gzip.decompress(archive.read_bytes()))
    score.require(bundle['schema'] == experiment.archive_schema, 'archive schema differs')
    files = {name: prepare.blob(bundle, name) for name in bundle['files']}
    target.mkdir(parents=True)
    for name, raw in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        collect.write(path, raw)
    return verify(target, experiment=experiment)


def main(description=__doc__, *, experiment=DEFAULT):
    parser = argparse.ArgumentParser(description=description)
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
        run(args.binary.resolve(), args.runtime.resolve(), args.out.resolve(), experiment=experiment)
    elif args.command == 'verify':
        verify(args.out, experiment=experiment)
    elif args.command == 'pack':
        package(args.out, args.archive, experiment=experiment)
    else:
        unpack(args.archive, args.out, experiment=experiment)


if __name__ == '__main__':
    main()
