#!/usr/bin/env python3
"""Two frozen replays with passive, windowed light observations; never training."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess

import garden_landing_cursor_energy as energy
from garden_resources import require

ROOT, STOP, STEP = energy.ROOT, energy.STOP, energy.STEP
RULE = 'garden-landing-cursor-shade-capture-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-cursor-shade-protocol.md'
ORIGIN_MANIFEST = '245c2f70f8876d4aa9f30e6734215c423fd0a362655444ebda193930bd9de5dd'
WINDOWS = [[1263045, 1267200], [1463640, 1470015]]
ARMS = energy.ARMS
capture = energy.capture
digest, write = capture.sweep.digest, capture.previous.write_receipt


def arguments(value, arm):
    args = list(energy.selected(value, arm)['args'])
    for flag in ('--adult-trace', '--adult-start', '--adult-stop', '--reach-trace'):
        offset = args.index(flag)
        del args[offset:offset + 2]
    for flag, tick in (('--stand-start', WINDOWS[0][0]), ('--stand-stop', WINDOWS[-1][1])):
        args[args.index(flag) + 1] = str(tick)
    args += ['--uptake-trace', 'uptake.jsonl']
    for first, last in WINDOWS:
        args += ['--uptake-window', f'{first}:{last}']
    return args


def uptake_rows(path, result):
    with gzip.open(path, 'rt') as stream:
        require(json.loads(next(stream)) == dict(schema='landing-uptake-v1', stop=STOP, windows=WINDOWS),
                'wrong uptake header')
        for first, last in WINDOWS:
            for tick in range(first, last + STEP, STEP):
                row = json.loads(next(stream))
                require(type(row.get('tick')) is int and row['tick'] == tick, 'missing/reordered uptake sample')
                yield row
        require(json.loads(next(stream)) == dict(complete=True, tick=STOP, run_hash=result['run_hash']) and
                not stream.read(), 'wrong uptake footer/trailing bytes')


def stand_rows(path, result, start, stop):
    with gzip.open(path, 'rt') as stream:
        require(json.loads(next(stream)) == dict(schema='landing-dawn-stand-trace-v1', node_limit=32,
                start=start, stop=stop, budget_mode=2), 'wrong stand header')
        for tick in range(start, stop + STEP, STEP):
            row = json.loads(next(stream))
            require(type(row.get('tick')) is int and row['tick'] == tick, 'wrong stand clock')
            yield row
        require(json.loads(next(stream)) == dict(complete=True, tick=STOP, run_hash=result['run_hash']) and
                not stream.read(), 'wrong stand footer/trailing bytes')


def compare_stand(origin, out, value, arm):
    prior = energy.selected(value, arm)
    meta = prior['traces']['stand']
    path = origin / meta['path']
    require(digest(path) == meta['sha256'], 'original stand trace changed')
    old = stand_rows(path, prior['result'], energy.BASE, STOP)
    new = stand_rows(out / arm / 'stand.jsonl.gz', prior['result'], WINDOWS[0][0], WINDOWS[-1][1])
    count = 0
    for row in old:
        if WINDOWS[0][0] <= row['tick'] <= WINDOWS[-1][1]:
            require(row == next(new), 'passive observer changed a stand row')
            count += 1
    require(next(new, None) is None, 'unconsumed stand rows')
    return count


def call(origin, out, value, arm):
    dest = out / arm
    (dest / 'frames').mkdir(parents=True)
    shutil.copy2(out / 'model.tgl', dest / 'model.tgl')
    args = arguments(value, arm)
    write(dest / 'started.json', dict(args=args))
    process = subprocess.run([str(out / 'bin/garden-landing'), *args], cwd=dest,
                             capture_output=True, text=True, timeout=600)
    write(dest / 'process.json', dict(returncode=process.returncode, stderr=process.stderr,
                                    stdout=process.stdout))
    require(process.returncode == 0, 'native replay failed; outputs preserved')
    result = json.loads(process.stdout)
    write(dest / 'result.json', result)
    prior = energy.selected(value, arm)
    require(result == prior['result'], 'passive observer changed endpoint or ledger')
    frame = dest / 'frames/end.raw'
    require(digest(frame) == prior['frame']['sha256'], 'passive observer changed pixels')
    traces = {}
    for kind in ('stand', 'uptake'):
        raw = dest / (kind + '.jsonl')
        packed = raw.with_suffix('.jsonl.gz')
        meta = capture.previous.compressed_trace(raw, packed)
        traces[kind] = dict(path=str(packed.relative_to(out)), sha256=digest(packed), **meta)
    count = sum(1 for _ in uptake_rows(out / traces['uptake']['path'], result))
    stand_count = compare_stand(origin, out, value, arm)
    run = dict(args=args, result=result, frame=dict(path=str(frame.relative_to(out)), sha256=digest(frame)),
               traces=traces, uptake_samples=count, matching_stand_samples=stand_count)
    write(dest / 'run.json', run)
    # Only verified duplicates created by this call; compressed bytes are durable.
    for kind, meta in traces.items():
        raw, packed = dest / (kind + '.jsonl'), out / meta['path']
        require(not raw.is_symlink() and digest(raw) == meta['raw_sha256'], 'raw duplicate changed')
        with packed.open('rb') as stream:
            os.fsync(stream.fileno())
        raw.unlink()
    print(f'{arm}: endpoint, pixels and {stand_count} stand rows match; {count} uptake samples', flush=True)
    return arm, run


def collect(origin, out):
    value = energy.load_input()
    require(not out.exists() and out.is_relative_to(ROOT / 'artifacts'), 'fresh artifact bundle required')
    require(shutil.disk_usage(out.parent).free >= 2 * 1024 ** 3, 'need 2 GiB free')
    require(digest(origin / 'manifest.json') == ORIGIN_MANIFEST, 'original manifest changed')
    original = json.loads((origin / 'manifest.json').read_text())['artifacts']
    frozen = ('bin/garden-landing', 'model.tgl', 'CMakeCache.txt', 'source.tar.gz')
    for name in frozen:
        require(digest(origin / name) == original[name], 'frozen input changed: ' + name)
    out.mkdir()
    (out / 'bin').mkdir()
    for name in frozen:
        shutil.copy2(origin / name, out / name)
    shutil.copy2(ROOT / PROTOCOL, out / 'protocol.md')
    shutil.copy2(Path(__file__), out / 'collector.py')
    receipt = dict(rule=RULE, input_sha256=energy.INPUT_SHA, origin_manifest_sha256=ORIGIN_MANIFEST,
                   windows=WINDOWS, protocol_sha256=digest(out / 'protocol.md'),
                   collector_sha256=digest(out / 'collector.py'),
                   frozen={name: original[name] for name in frozen}, native_runs=2, training_runs=0)
    write(out / 'started.json', receipt)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(call, origin, out, value, arm) for arm in ARMS]
        receipt['runs'] = dict(future.result() for future in futures)
    require(digest(ROOT / PROTOCOL) == receipt['protocol_sha256'] and
            digest(Path(__file__)) == receipt['collector_sha256'], 'collection instructions changed')
    write(out / 'capture.json', receipt)
    files = {str(p.relative_to(out)): digest(p) for p in sorted(out.rglob('*')) if p.is_file()}
    write(out / 'manifest.json', dict(rule=RULE, artifacts=files))
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', type=Path, default=ROOT / 'artifacts/garden-landing-seed-cursor-v1')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    collect(args.origin.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
