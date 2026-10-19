#!/usr/bin/env python3
"""Fixed eight-run scheduled repair-gate intervention; no search or model promotion."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import gzip
import io
import json
from pathlib import Path
import struct
import time
import zlib

import population_shadow as shadow

collect, prepare, score, trace = shadow.collect, shadow.prepare, shadow.score, shadow.trace
VARIANTS = ('none', 'light', 'condition', 'both')
DAYS = (0, 32, 192, 208, 220, 222, 224, 256)
AFTER, STOP = 208 * score.DAY, 256 * score.DAY
WORKERS, CALL_SECONDS, BUDGET_SECONDS = 2, 180, 900
PROTOCOL = collect.ROOT / 'benchmarks/garden-seasons/leaf-population-gates-protocol.md'
ARCHIVE_SCHEMA = 'garden-population-gates-evidence-v1'


def roster():
    return [dict(id=f'{variant}-{mode}', variant=variant, mode=mode)
            for variant in VARIANTS for mode in ('off', 'on')]


def derive(models, variant):
    """Independent TLF1 byte derivation, never import/execute archived code."""
    score.require(variant in VARIANTS, 'unknown gate variant')
    original, fixed = models['s1-g3-c4'], models['initial']
    shadow.decode(original)
    shadow.decode(fixed)
    payload = bytearray(original[16:])
    for unit in range(2):
        if VARIANTS.index(variant) & (1 << unit):
            for offset, length in ((12 + unit * 4, 4), (44 + unit * 11, 11)):
                payload[offset:offset + length] = fixed[16 + offset:16 + offset + length]
    return struct.pack('<4sHHII', b'TLF1', 1, 16, len(payload), zlib.crc32(payload)) + payload


def underlying(value, variant, models, size, tick, *, seed='58d7d6ca', after_tick=AFTER):
    """Validate intervention identity, then project only for explicit parity checks.

    This projection is not a standalone uniform-run record: keep the full TGR1
    identity whenever publishing or storing an intervention result.
    """
    score.require(after_tick in (0, AFTER), 'invalid gate activation')
    derived = derive(models, variant)
    identity = dict(kind='restore-leaf-gates', variant=variant, founder=2,
                    after_tick=after_tick, leaf_model_hex=derived.hex())
    state = bytes.fromhex(value['state_hex'])
    header = b'TGR1' + bytes((VARIANTS.index(variant), 2, 0, 0)) + struct.pack('<I', after_tick) + derived
    score.require(value['schema'] == 'garden-leaf-gate-replay-v1' and
                  value['controller_assignment'] == 'scheduled-founder-family' and
                  value['intervention'] == identity and state.startswith(header), 'intervention identity differs')
    projected = {k: v for k, v in value.items() if k != 'intervention'}
    projected.update(schema='garden-leaf-population-replay-v1', controller_assignment='whole-population',
                     state_hex=state[len(header):].hex())
    score.validate_record(projected, models['s1-g3-c4'], seed=seed, layout='rainfed',
                          ticks=tick, uniform_bytes=size)
    return projected


def summarize(resources, value):
    families = trace.losses.family_rows(value)
    founder_days = [r for r in resources['plant_days'] if r['lineage'] == 2 and r['day'] >= 208]
    children = [p for p in value['lineages'] if p['parent'] and value['family_roots'][p['id'] - 1] == 2]
    windows = {}
    for first, end in ((208, 220), (220, 224), (224, 256)):
        rows = [r for r in founder_days if first <= r['day'] < end]
        if not rows:
            windows[f'{first}-{end}'] = None
            continue
        windows[f'{first}-{end}'] = dict(first_tick=rows[0]['first_tick'], last_tick=rows[-1]['last_tick'],
            renewals=sum(r['renewals'] for r in rows), energy_short=sum(r['energy_short'] for r in rows),
            water_short=sum(r['water_short'] for r in rows),
            resources={resource: {k: (rows[0][resource][k] if k == 'before' else
                rows[-1][resource][k] if k == 'after' else sum(r[resource][k] for r in rows))
                for k in rows[0][resource]} for resource in ('energy', 'water')})
    cohorts = {}
    for label, selected in (('born_by_switch', [p for p in children if p['birth_tick'] <= AFTER]),
                            ('born_after_switch', [p for p in children if p['birth_tick'] > AFTER])):
        cohorts[label] = dict(born=len(selected), established=sum(trace.losses.established(p, STOP) for p in selected),
            living=sum(p['death_tick'] is None for p in selected),
            young_alive=sum(p['death_tick'] is None and p['birth_tick'] + 32 * score.DAY > STOP for p in selected))
    return dict(families=families, founder_days=founder_days, founder_windows=windows, cohorts=cohorts)


def validate_outputs(out, baseline, models, size):
    analyses, checkpoints, resource_logs = {}, {}, {}
    for call in roster():
        folder = out / 'runs' / call['id']
        variant = call['variant']
        final = json.loads((folder / 'stdout.json').read_bytes())
        expected = {f'tick-{d * score.DAY:010d}.{ext}' for d in DAYS for ext in ('raw', 'json')}
        for day in DAYS:
            prefix = folder / 'timeline' / f'tick-{day * score.DAY:010d}'
            encoded, raw = prefix.with_suffix('.json').read_bytes(), prefix.with_suffix('.raw').read_bytes()
            value = json.loads(encoded)
            projected = underlying(value, variant, models, size, day * score.DAY)
            score.require(len(raw) == 115200 and value['framebuffer_crc32'] == f'{zlib.crc32(raw):08x}',
                          'capture differs')
            score.require(score.history_prefix(final, day * score.DAY) ==
                          score.history_prefix(value, day * score.DAY), 'history prefix differs')
            checkpoints[call['id'], day] = projected, raw
            if call['mode'] == 'on':
                other = out / 'runs' / f'{variant}-off' / 'timeline' / prefix.name
                score.require(encoded == other.with_suffix('.json').read_bytes() and
                              raw == other.with_suffix('.raw').read_bytes(), 'trace changed checkpoint')
            if variant == 'none' and day in trace.DAYS:
                old = f'runs/s1-g3-c4-on/timeline/{prefix.name}'
                score.require(projected == json.loads(prepare.blob(baseline, old + '.json')) and
                              raw == prepare.blob(baseline, old + '.raw'), 'archived control differs')
        score.require(final == value, 'stdout differs from final checkpoint')
        if call['mode'] == 'on':
            expected.add('trace.json')
            resources = json.loads((folder / 'timeline/trace.json').read_bytes())
            trace.validate_trace(resources, final)
            resource_logs[variant] = resources
            analyses[variant] = summarize(resources, final)
        score.require({p.name for p in (folder / 'timeline').iterdir()} == expected, 'output roster differs')
    score.require(resource_logs['none'] == json.loads(prepare.blob(baseline,
                  'runs/s1-g3-c4-on/timeline/trace.json')), 'archived control trace differs')
    for variant in VARIANTS:
        for day in (0, 32, 192, 208):
            score.require(checkpoints[f'{variant}-on', day] == checkpoints['none-on', day],
                          'intervention changed pre-switch trajectory')
        before = lambda d: [r for r in d['plant_days'] if r['day'] < 208]
        score.require(before(resource_logs[variant]) == before(resource_logs['none']) and
                      resource_logs[variant]['seed_days'][:208] == resource_logs['none']['seed_days'][:208],
                      'intervention changed pre-switch trace')
    return analyses


def sources():
    return collect.sources() | {str(PROTOCOL.relative_to(collect.ROOT)): prepare.sha(PROTOCOL.read_bytes())}


def arguments(call):
    return ['--gate', call['variant'], call['mode']]


def run(binary, runtime, out):
    score.require(not out.exists() and not out.is_symlink(), 'fresh output directory required')
    baseline, models, size = shadow.inputs()
    bundle = prepare.load_archive()
    prepare.check(runtime, prepare.expected_files(bundle))
    digest, pinned = prepare.sha(binary.read_bytes()), sources()
    out.mkdir(parents=True)
    collect.save(out / 'started.json', dict(schema='garden-population-gates-collection-v1', plan=roster(),
        workers=WORKERS, call_seconds=CALL_SECONDS, budget_seconds=BUDGET_SECONDS,
        baseline_sha256=shadow.BASELINE_SHA, runtime_archive_sha256=prepare.ARCHIVE_SHA,
        derived_models={v: derive(models, v).hex() for v in VARIANTS},
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
            for variant in VARIANTS:
                futures = [pool.submit(worker, c) for c in roster() if c['variant'] == variant]
                for future in futures:
                    future.result()
        elapsed = time.monotonic() - began
        score.require(elapsed <= BUDGET_SECONDS, 'collection budget exceeded')
        analyses = validate_outputs(out, baseline, models, size)
        prepare.check(runtime, prepare.expected_files(bundle))
        score.require(digest == prepare.sha(binary.read_bytes()) and pinned == sources(),
                      'source or binary changed during collection')
        collect.save(out / 'result.json', dict(complete=True, calls=8, elapsed_seconds=elapsed, analyses=analyses))
        collect.save(out / 'manifest.json', {str(p.relative_to(out)): prepare.sha(p.read_bytes())
                     for p in sorted(out.rglob('*')) if p.is_file()})
        print(json.dumps(dict(complete=True, calls=8, elapsed_seconds=elapsed)), flush=True)
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
    baseline, models, size = shadow.inputs()
    started = json.loads((out / 'started.json').read_bytes())
    score.require(started['schema'] == 'garden-population-gates-collection-v1' and
                  started['plan'] == roster() and started['baseline_sha256'] == shadow.BASELINE_SHA and
                  started['runtime_archive_sha256'] == prepare.ARCHIVE_SHA and
                  started['derived_models'] == {v: derive(models, v).hex() for v in VARIANTS} and
                  (started['workers'], started['call_seconds'], started['budget_seconds']) == (2, 180, 900),
                  'protocol differs')
    for name, sha in started['sources'].items():
        prepare.relative(name)
        score.require(actual['source/' + name] == sha, 'source snapshot differs')
    score.require({p.name for p in (out / 'runs').iterdir()} == {c['id'] for c in roster()}, 'call roster differs')
    for call in roster():
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
    score.require(result['complete'] is True and result['calls'] == 8 and
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
        stream.write(json.dumps(dict(schema=ARCHIVE_SCHEMA, files=files, blobs=blobs),
                                sort_keys=True, separators=(',', ':')).encode())
    collect.write(target, packed.getvalue())


def unpack(archive, target):
    score.require(not target.exists() and not target.is_symlink(), 'fresh unpack directory required')
    bundle = json.loads(gzip.decompress(archive.read_bytes()))
    score.require(bundle['schema'] == ARCHIVE_SCHEMA, 'archive schema differs')
    files = {name: prepare.blob(bundle, name) for name in bundle['files']}
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
