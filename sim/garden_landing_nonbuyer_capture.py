#!/usr/bin/env python3
"""Two frozen passive replays of a long-lived non-buyer's complete observed life."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import garden_landing_seed_handoff_capture as origin_capture
from garden_landing_bank_access import FIELDS
from garden_landing_founders import write_gzip
from garden_experiments import digest, write_json
from garden_resources import require

ROOT, STOP, STEP = origin_capture.ROOT, origin_capture.STOP, origin_capture.STEP
RULE = 'garden-landing-nonbuyer-capture-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-nonbuyer-protocol.md'
PROTOCOL_SHA = '3af177622cb218332c75e8713b4fa2b8168423e2902ce74a739835cb93557612'
CASE, ARM, FOCAL = '366928c6-rainfed', 'cursor', 41
FIRST, LAST = 1593525, 1966080
LABELS = ('trace', 'repeat')


def selected(value):
    return value['runs']['endpoint'][ARM][CASE]


def arguments(value):
    return list(selected(value)['args']) + [
        '--stand-trace', 'stand.jsonl', '--stand-start', str(FIRST),
        '--stand-stop', str(LAST), '--stand-dawn']


def unpacked_identity(path):
    sha, size = hashlib.sha256(), 0
    with gzip.open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            sha.update(block)
            size += len(block)
    return dict(sha256=sha.hexdigest(), bytes=size)


def pack_trace(path):
    """Discard only a verified, freshly generated duplicate, never unique evidence."""
    identity = dict(sha256=digest(path), bytes=path.stat().st_size)
    packed = path.with_suffix(path.suffix + '.gz')
    with path.open('rb') as source, packed.open('xb') as dest:
        with gzip.GzipFile(fileobj=dest, mode='wb', filename='', mtime=0) as stream:
            shutil.copyfileobj(source, stream, 1024 * 1024)
    require(unpacked_identity(packed) == identity and digest(path) == identity['sha256'],
            'lossless trace compression failed; both files retained')
    path.unlink()
    return identity | dict(sha256_gzip=digest(packed), bytes_gzip=packed.stat().st_size)


def extract(path, result):
    rows = []
    with gzip.open(path, 'rt') as stream:
        require(json.loads(next(stream)) == dict(schema='landing-dawn-stand-trace-v1',
                start=FIRST, stop=LAST, node_limit=32, budget_mode=2), 'wrong trace header')
        for tick in range(FIRST, LAST + STEP, STEP):
            row = json.loads(next(stream))
            require(set(row) == {'tick', 'seed_lifetime_ecology_ticks', 'climate', 'plant_order',
                    'bids', 'reproduction', 'bodies'} and row['tick'] == tick and
                    row['seed_lifetime_ecology_ticks'] == 8192, 'wrong trace clock or fields')
            require(all(set(v) == set(FIELDS) for v in row['reproduction']), 'wrong visit fields')
            bodies = [p for p in row['bodies'] if p['id'] == FOCAL]
            require(len(bodies) == 1, 'missing focal body')
            rows.append(dict(tick=tick, climate=row['climate'], plant_order=row['plant_order'],
                reproduction=[[v[k] for k in FIELDS] for v in row['reproduction']],
                body=bodies[0], bids=[b for b in row['bids'] if b['id'] == FOCAL]))
        require(json.loads(next(stream)) == dict(complete=True, tick=STOP, run_hash=result['run_hash'])
                and not stream.read(), 'incomplete or trailing trace')
    return dict(fields=list(FIELDS), rows=rows)


def call(origin, out, value, label):
    dest = out / label
    (dest / 'frames').mkdir(parents=True)
    shutil.copy2(origin / 'model.tgl', dest / 'model.tgl')
    args = arguments(value)
    write_json(dest / 'started.json', dict(args=args))
    print(f'{label}: frozen replay; logging complete focal life {FIRST}..{LAST}', flush=True)
    process = subprocess.run([str(origin / 'bin/garden-landing'), *args], cwd=dest,
                             capture_output=True, text=True, timeout=900)
    write_json(dest / 'process.json', dict(returncode=process.returncode,
                                         stderr=process.stderr, stdout=process.stdout))
    require(process.returncode == 0 and not process.stderr, 'replay failed; evidence preserved')
    result = json.loads(process.stdout)
    write_json(dest / 'result.json', result)
    require(result == selected(value)['result'], 'observer changed endpoint or lifetime ledgers')
    frame = dest / 'frames/end.raw'
    origin_capture.frame_bytes(frame, result)
    require(digest(frame) == selected(value)['frame']['sha256'], 'observer changed endpoint pixels')
    trace = pack_trace(dest / 'stand.jsonl')
    trace['path'] = label + '/stand.jsonl.gz'
    excerpt = extract(out / trace['path'], result)
    write_gzip(dest / 'excerpt.json.gz', excerpt)
    run = dict(args=args, result=result, trace=trace,
               excerpt=dict(path=label + '/excerpt.json.gz', sha256=digest(dest / 'excerpt.json.gz')),
               frame=dict(path=label + '/frames/end.raw', sha256=digest(frame)))
    write_json(dest / 'run.json', run)
    print(f'{label}: endpoint matches; {len(excerpt["rows"])} samples, '
          f'{trace["bytes"]} raw bytes packed to {trace["bytes_gzip"]}', flush=True)
    return label, run


def collect(origin, out):
    value = origin_capture.audit.load_input()
    require(not out.exists() and out.is_relative_to(ROOT / 'artifacts'), 'fresh artifact bundle required')
    require(digest(ROOT / PROTOCOL) == PROTOCOL_SHA, 'non-buyer protocol changed')
    require(shutil.disk_usage(out.parent).free >= 2 * 1024 ** 3, 'need 2 GiB temporary free space')
    frozen = origin_capture.authenticate(origin, value)
    out.mkdir()
    shutil.copy2(ROOT / PROTOCOL, out / 'protocol.md')
    shutil.copy2(Path(__file__), out / 'collector.py')
    receipt = dict(rule=RULE, input_sha256=origin_capture.audit.INPUT_SHA,
        input_receipt_sha256=value['receipt_sha256'], protocol_sha256=PROTOCOL_SHA,
        collector_sha256=digest(out / 'collector.py'),
        origin_manifest_sha256=origin_capture.ORIGIN_MANIFEST, frozen=frozen,
        case=CASE, arm=ARM, focal=FOCAL, first=FIRST, last=LAST, native_runs=2, training_runs=0)
    write_json(out / 'started.json', receipt)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(call, origin, out, value, label) for label in LABELS]
            receipt['runs'] = dict(task.result() for task in futures)
        a, b = (receipt['runs'][label] for label in LABELS)
        require({k: v for k, v in a['trace'].items() if k != 'path'} ==
                {k: v for k, v in b['trace'].items() if k != 'path'} and
                a['excerpt']['sha256'] == b['excerpt']['sha256'], 'repeat trace or excerpt differs')
        require(origin_capture.authenticate(origin, value) == frozen and
                digest(ROOT / PROTOCOL) == PROTOCOL_SHA and
                digest(Path(__file__)) == receipt['collector_sha256'], 'collection inputs changed')
        write_json(out / 'capture.json', receipt)
        write_json(out / 'manifest.json', dict(rule=RULE, artifacts={str(p.relative_to(out)): digest(p)
                   for p in sorted(out.rglob('*')) if p.is_file()}))
        print('Two exact passive replays complete; only verified raw duplicates removed.', flush=True)
    except Exception as error:
        write_json(out / 'failure.json', dict(error=str(error), automatic_retry=False))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', type=Path, default=ROOT / 'artifacts/garden-landing-competitive-renewal-v1')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    collect(args.origin.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
