#!/usr/bin/env python3
"""Two frozen replays with a 66-step passive seed/plant handoff window."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import subprocess

import garden_landing_recruit_seeds as audit
from garden_experiments import digest, write_json
from garden_landing_competitive_renewal_capture import safe_artifact, frame_bytes
from garden_resources import require

ROOT, STOP, STEP = audit.ROOT, audit.STOP, audit.STEP
RULE = 'garden-landing-seed-handoff-capture-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-seed-handoff-protocol.md'
PROTOCOL_SHA = '3b840bf0a18061a537de342446b657ef9f8df6a81a89768c7c342bb0aaaf9134'
ORIGIN_MANIFEST = '4402ad5be09ed19542d303a83015e81e376cd1b9a7efd40350eea11ac319e205'
CASE, ARM = '366928c6-rainfed-crowded', 'cursor'
FIRST, LAST = 1838385, 1839360
LABELS, KINDS = ('trace', 'repeat'), ('adult', 'stand')
FROZEN = ('bin/garden-landing', 'model.tgl', 'CMakeCache.txt', 'source.tar.gz')


def selected(value):
    return value['runs']['endpoint'][ARM][CASE]


def arguments(value):
    args = list(selected(value)['args'])
    for kind in KINDS:
        args += [f'--{kind}-trace', kind + '.jsonl', f'--{kind}-start', str(FIRST),
                 f'--{kind}-stop', str(LAST)]
    return args + ['--stand-dawn']


def read_trace(path, kind, result):
    with path.open() as stream:
        rows = [json.loads(line) for line in stream]
    header = dict(schema='landing-adult-resources-v1', start=FIRST, stop=LAST)
    footer = dict(complete=True, tick=STOP)
    if kind == 'stand':
        header.update(schema='landing-dawn-stand-trace-v1', node_limit=32, budget_mode=2)
        footer['run_hash'] = result['run_hash']
    require(kind in KINDS and rows[0] == header and rows[-1] == footer and
            [r['tick'] for r in rows[1:-1]] == list(range(FIRST, LAST + STEP, STEP)),
            'incomplete or changed bounded trace')
    return rows


def authenticate(origin, value):
    require(digest(origin / 'manifest.json') == ORIGIN_MANIFEST, 'origin manifest changed')
    manifest = json.loads((origin / 'manifest.json').read_text())['artifacts']
    frozen = {name: manifest[name] for name in FROZEN}
    require(frozen['bin/garden-landing'] == value['build']['binary'] and
            frozen['model.tgl'] == value['model_sha256'] and
            frozen['CMakeCache.txt'] == value['build']['cache'], 'wrong frozen build/model')
    for name, sha in frozen.items():
        require(digest(safe_artifact(origin, name)) == sha, 'frozen input changed: ' + name)
    return frozen


def call(origin, out, value, label):
    dest = out / label
    (dest / 'frames').mkdir(parents=True)
    shutil.copy2(origin / 'model.tgl', dest / 'model.tgl')
    args = arguments(value)
    write_json(dest / 'started.json', dict(args=args))
    print(f'{label}: replaying frozen history; only ticks {FIRST}..{LAST} are logged', flush=True)
    process = subprocess.run([str(origin / 'bin/garden-landing'), *args], cwd=dest,
                             capture_output=True, text=True, timeout=900)
    write_json(dest / 'process.json', dict(returncode=process.returncode, stderr=process.stderr,
                                         stdout=process.stdout))
    require(process.returncode == 0 and not process.stderr, 'replay failed; outputs preserved')
    result = json.loads(process.stdout)
    write_json(dest / 'result.json', result)
    require(result == selected(value)['result'], 'observer changed endpoint or lifetime ledgers')
    frame = dest / 'frames/end.raw'
    frame_bytes(frame, result)
    require(digest(frame) == selected(value)['frame']['sha256'], 'observer changed endpoint pixels')
    traces = {}
    for kind in KINDS:
        path = dest / (kind + '.jsonl')
        read_trace(path, kind, result)
        traces[kind] = dict(path=str(path.relative_to(out)), sha256=digest(path))
    run = dict(args=args, result=result, traces=traces,
               frame=dict(path=str(frame.relative_to(out)), sha256=digest(frame)))
    write_json(dest / 'run.json', run)
    print(f'{label}: endpoint, ledgers and pixels match; both 66-step traces complete', flush=True)
    return label, run


def collect(origin, out):
    value = audit.load_input()
    require(not out.exists() and out.is_relative_to(ROOT / 'artifacts'), 'fresh artifact bundle required')
    require(digest(ROOT / PROTOCOL) == PROTOCOL_SHA, 'handoff protocol changed')
    require(shutil.disk_usage(out.parent).free >= 64 * 1024 ** 2, 'need 64 MiB free')
    frozen = authenticate(origin, value)
    out.mkdir()
    shutil.copy2(ROOT / PROTOCOL, out / 'protocol.md')
    shutil.copy2(Path(__file__), out / 'collector.py')
    receipt = dict(rule=RULE, input_sha256=audit.INPUT_SHA, input_receipt_sha256=value['receipt_sha256'],
                   protocol_sha256=PROTOCOL_SHA, collector_sha256=digest(out / 'collector.py'),
                   origin_manifest_sha256=ORIGIN_MANIFEST, frozen=frozen, case=CASE, arm=ARM,
                   first=FIRST, last=LAST, native_runs=2, training_runs=0)
    write_json(out / 'started.json', receipt)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(call, origin, out, value, label) for label in LABELS]
            receipt['runs'] = dict(task.result() for task in futures)
        require(all(receipt['runs']['trace']['traces'][k]['sha256'] ==
                    receipt['runs']['repeat']['traces'][k]['sha256'] for k in KINDS), 'trace repeat differs')
        require(authenticate(origin, value) == frozen and digest(ROOT / PROTOCOL) == PROTOCOL_SHA and
                digest(Path(__file__)) == receipt['collector_sha256'], 'collection inputs changed')
        write_json(out / 'capture.json', receipt)
        write_json(out / 'manifest.json', dict(rule=RULE, artifacts={str(p.relative_to(out)): digest(p)
                   for p in sorted(out.rglob('*')) if p.is_file()}))
        print('Two replays complete; traces match byte for byte. No rules or build changed.', flush=True)
    except Exception as error:
        write_json(out / 'failure.json', dict(error=str(error), automatic_retry=False))
        raise
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', type=Path, default=ROOT / 'artifacts/garden-landing-competitive-renewal-v1')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    collect(args.origin.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
