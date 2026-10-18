#!/usr/bin/env python3
"""Fixed owned/reference equivalence panel; eleven bounded calls, no search."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NEW = ROOT / 'artifacts/garden-leaf-replay-tools-v7'
OLD = ROOT / 'artifacts/garden-leaf-timing-v2'
ARCHIVE = ROOT / 'artifacts/garden-leaf-replay-tools-v6'
sys.path.insert(0, str(HERE.parent / 'leaf_replay'))
sys.path.insert(0, str(HERE.parent / 'leaf_objective'))
import build_leaf_replay as build
from family_fitness import score_family
from test_leaf_replay import model
from test_leaf_owned import light_model

DAY = 3840
CASES = (
    dict(name='wait-normal', model='wait', seed='3c308d3b', scenario='rainfed', founder=1),
    dict(name='renew-crowded', model='renew', seed='3c308d3b', scenario='rainfed-crowded', founder=5),
    dict(name='light-normal', model='light', seed='97806ca5', scenario='rainfed', founder=2),
)
RESIDENT = 'selective'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write('\n')


def models():
    return dict(wait=model(0), renew=model(1), light=light_model())


def calls():
    return [dict(label='prefix-' + case['name'], case=case, days=16, capture=False,
                 binary='owned', timeout_seconds=60) for case in CASES[:2]] + [
        dict(label=phase + '-' + case['name'], case=case, days=608, capture=capture,
             binary=binary, timeout_seconds=timeout)
        for phase, binary, capture, timeout in (
            ('owned', 'owned', True, 180),
            ('reference', 'reference', True, 1200),
            ('parallel', 'owned', False, 180)) for case in CASES]


def verify_inputs():
    current, reference = read(NEW / 'build.json'), read(OLD / 'build.json')
    require(current['source_sha256'] == build.pins(), 'current replay sources differ')
    require(current['module_sha256'] == build.inventory(NEW / 'modules'), 'new module snapshot differs')
    require(current['staged_sha256'] == build.inventory(NEW / 'source') ==
            reference['unchanged_core_sha256'] == build.inventory(ARCHIVE / 'source'), 'core differs')
    require(reference['unchanged_modules_sha256'] == build.inventory(ARCHIVE / 'modules'),
            'pre-refactor module snapshot differs')
    require(all(digest(NEW / 'native' / name) == sha for name, sha in current['binary_sha256'].items()),
            'new binary differs')
    require(digest(OLD / 'native/leaf-family-replay') == reference['optimized_binary_sha256'],
            'pre-refactor executable differs')
    require(digest(OLD / 'native/compile_commands.json') == reference['compile_commands_sha256'],
            'reference compiler flags differ')
    require(digest(NEW / 'model.tgl') == current['growth_model_sha256'] == digest(ARCHIVE / 'model.tgl'),
            'growth model differs')
    require(digest(NEW / 'reference.json') == current['reference_results_sha256'], 'prefix evidence differs')
    for folder, suites in ((NEW, 25), (OLD, 23)):
        receipt = read(folder / 'build-2.json')
        require(receipt['returncode'] == 0 and f'100% tests passed, 0 tests failed out of {suites}'
                in receipt['stdout'], 'build tests incomplete')
    build.origin.verify(build.PREPARED)
    return dict(new_build_sha256=digest(NEW / 'build.json'),
                reference_build_sha256=digest(OLD / 'build.json'),
                growth_model_sha256=current['growth_model_sha256'],
                reference_binary_sha256=reference['optimized_binary_sha256'],
                owned_binary_sha256=current['binary_sha256']['leaf-family-owned'])


def check_output(value, call, growth_sha, pixels=None):
    case = call['case']
    require(value['schema'] == 'garden-leaf-family-replay-v1' and value['complete'] is True and
            value['controller_assignment'] == 'founder-family' and value['objective'] is None,
            'incomplete or wrong replay')
    expected = dict(seed=case['seed'], scenario=case['scenario'], ticks=call['days'] * DAY,
                    candidate_founder=case['founder'], resident_policy=RESIDENT, climate='seasonal',
                    growth_model_sha256=growth_sha, leaf_model_hex=models()[case['model']].hex())
    require(all(value.get(k) == v for k, v in expected.items()) and value['gardener'] is False,
            'condition or model identity differs')
    require(type(value.get('ledger_start_tick')) is int and value['ledger_start_tick'] == 0,
            'incomplete lifetime history')
    if call['capture']:
        require(pixels is not None and len(pixels) == 115200 and
                value['framebuffer_crc32'] == f'{zlib.crc32(pixels):08x}', 'frame differs')
    else:
        require(pixels is None and value['framebuffer_crc32'] is None, 'unexpected frame')
    founders = 3 if case['scenario'] == 'rainfed' else 5
    state = bytes.fromhex(value['state_hex'])
    require(len(state) >= 12, 'truncated family checkpoint')
    count, = struct.unpack_from('<I', state, 8)
    require(state[:8] == b'TFR1' + bytes((case['founder'], 3, founders, 0)) and
            founders <= count <= 4096 and
            len(state) == 12 + count + 5293 and count == len(value['lineages']) == len(value['family_roots']),
            'wrong family checkpoint')
    require(state[12:12 + count] == bytes(value['family_roots']) and
            state[12 + count:16 + count] == b'TLR1' and
            state[16 + count:188 + count] == models()[case['model']], 'checkpoint identity differs')
    roots = {}
    require(all(type(p['id']) is int for p in value['lineages']) and
            [p['id'] for p in value['lineages']] == list(range(1, count + 1)), 'lineage ordering differs')
    for plant in value['lineages']:
        identity, parent = plant['id'], plant['parent']
        require(type(parent) is int and 0 <= parent < identity and
                ((identity <= founders) == (parent == 0)), 'invalid parent')
        roots[identity] = roots[parent] if parent else identity
        require(value['family_roots'][identity - 1] == roots[identity], 'ownership mismatch')
    if call['days'] == 608:
        # Validate the full lifetime/seed ledger and physical capacity using the
        # agreed scorer, but do not rank or select these diagnostic models.
        score_family(value | {'tick': value['ticks']}, case['founder'], start_day=192, window_count=6)
    return value


def execute(root, call, identities):
    folder = root / call['label']
    folder.mkdir()
    binary = NEW / 'native/leaf-family-owned' if call['binary'] == 'owned' else OLD / 'native/leaf-family-replay'
    case = call['case']
    args = list(map(str, (binary, root / 'growth.tgl', root / (case['model'] + '.tlf'),
                         case['seed'], case['scenario'], call['days'] * DAY, case['founder'], RESIDENT)))
    if call['capture']:
        args.append(str(folder / 'frame.raw'))
    save(folder / 'started.json', dict(call=call, args=args, binary_sha256=digest(binary)))
    start = time.perf_counter()
    try:
        child = subprocess.run(args, capture_output=True, timeout=call['timeout_seconds'])
        stdout, stderr, code, timeout = child.stdout, child.stderr, child.returncode, False
    except subprocess.TimeoutExpired as error:
        stdout, stderr, code, timeout = error.stdout or b'', error.stderr or b'', None, True
    elapsed = time.perf_counter() - start
    (folder / 'stdout.json').write_bytes(stdout)
    (folder / 'stderr.txt').write_bytes(stderr)
    receipt = dict(returncode=code, timed_out=timeout, elapsed_seconds=elapsed,
                   stdout_bytes=len(stdout), stderr_bytes=len(stderr), stdout_sha256=digest(folder / 'stdout.json'),
                   stderr_sha256=digest(folder / 'stderr.txt'))
    save(folder / 'process.json', receipt)
    require(code == 0 and not timeout and not stderr and len(stdout) < 8 * 1024 * 1024,
            'failed bounded call: ' + call['label'])
    pixels = (folder / 'frame.raw').read_bytes() if call['capture'] else None
    value = check_output(json.loads(stdout), call, identities['growth_model_sha256'], pixels)
    receipt |= dict(lineages=len(value['lineages']), seeds=len(value['seeds']),
                    logic_ticks_per_second=value['ticks'] / elapsed,
                    framebuffer_sha256=digest(folder / 'frame.raw') if call['capture'] else None)
    save(folder / 'checked.json', receipt)
    print(f"{call['label']}: {elapsed:.3f}s; {receipt['lineages']} lineages, {receipt['seeds']} seed records", flush=True)
    return receipt


def main(out):
    require(out.parent == ROOT / 'artifacts' and not out.exists() and not out.is_symlink(), 'fresh output required')
    require(shutil.disk_usage(ROOT).free >= 2 * 1024**3, 'less than 2 GiB free')
    identities = verify_inputs()
    plan = calls()
    require(len(plan) == 11, 'unexpected diagnostic budget')
    out.mkdir()
    source = {str(p.relative_to(ROOT)): digest(p) for p in (Path(__file__), HERE.parent / 'leaf_objective/family_fitness.py')}
    scope = dict(schema='garden-leaf-owned-comparison-v1', calls=plan, maximum_native_calls=11,
                 maximum_parallel_processes=2, already_submitted_calls_may_finish_after_failure=True,
                 automatic_retry=False, training_runs=0, fitness=None, identities=identities,
                 source_sha256=source, load_average_start=os.getloadavg())
    save(out / 'started.json', scope)
    try:
        shutil.copy2(NEW / 'model.tgl', out / 'growth.tgl')
        for name, data in models().items():
            (out / (name + '.tlf')).write_bytes(data)
        saved_prefixes = read(NEW / 'reference.json')['prefix_stdout']
        records = {}
        for call in plan[:5]:
            records[call['label']] = execute(out, call, identities)
            if call['days'] == 16:
                require((out / call['label'] / 'stdout.json').read_text() == saved_prefixes[call['case']['name']],
                        'archived prefix differs')
        for phase in (plan[5:8], plan[8:]):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [(call, pool.submit(execute, out, call, identities)) for call in phase]
                for call, future in futures:
                    records[call['label']] = future.result()
        for case in CASES:
            name = case['name']
            a, b = (out / (phase + '-' + name) for phase in ('owned', 'reference'))
            require((a / 'stdout.json').read_bytes() == (b / 'stdout.json').read_bytes(), 'full output differs: ' + name)
            require((a / 'frame.raw').read_bytes() == (b / 'frame.raw').read_bytes(), 'full pixels differ: ' + name)
            plain = read(out / ('parallel-' + name) / 'stdout.json')
            require(read(a / 'stdout.json') | {'framebuffer_crc32': None} == plain,
                    'capture/concurrency changes state: ' + name)
        require(verify_inputs() == identities and all(digest(ROOT / p) == sha for p, sha in source.items()),
                'comparison inputs changed')
        save(out / 'result.json', dict(scope=scope, receipts=records, exact_prefix_parity=True,
             exact_full_parity=True, exact_pixels=True, exact_capture_parallel_parity=True,
             load_average_end=os.getloadavg(), training_runs=0, fitness=None))
        print('All eleven bounded calls complete; exact full histories/state/pixels and capture/concurrency parity.', flush=True)
    except BaseException as error:
        save(out / 'failure.json', dict(error=str(error), automatic_retry=False, training_runs=0))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    main(parser.parse_args().out.absolute())
