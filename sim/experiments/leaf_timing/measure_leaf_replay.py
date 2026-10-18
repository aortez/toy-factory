#!/usr/bin/env python3
"""Bounded fixed-model throughput diagnostic; no training or ecological changes."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shlex
import struct
import subprocess
import sys
import time
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = ROOT / 'artifacts/garden-leaf-replay-tools-v6'
sys.path.insert(0, str(HERE.parent / 'leaf_replay'))
sys.path.insert(0, str(ROOT / 'sim'))
import build_leaf_replay as build
from garden_descendants import index_records

DAY = 3840
PREFIX_DAYS, FULL_DAYS = 16, 608
FIXTURES = (
    dict(name='wait-normal', action=0, scenario='rainfed', founder=1),
    dict(name='renew-crowded', action=1, scenario='rainfed-crowded', founder=5),
)
SEED, RESIDENT = '3c308d3b', 'selective'
MAX_CALLS = 8


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write('\n')


def model(action):
    require(type(action) is int and action in (0, 1), 'fixed action required')
    payload = struct.pack('<4sHHBBBB', b'LFN1', 1, 1, 0, 0, 0, 0)
    payload += bytes(8 * 4 + 88)
    payload += struct.pack('<2i', int(action == 0), int(action == 1)) + bytes(16)
    return struct.pack('<4sHHII', b'TLF1', 1, 16, len(payload), zlib.crc32(payload)) + payload


def verify_base():
    record = json.loads((BASE / 'build.json').read_text())
    require(record['source_sha256'] == build.pins(), 'live replay sources differ')
    require(record['module_sha256'] == build.inventory(BASE / 'modules'), 'archived modules differ')
    require(record['staged_sha256'] == build.inventory(BASE / 'source'), 'archived core differs')
    require(all(build.origin.digest(BASE / 'native' / name) == digest
                for name, digest in record['binary_sha256'].items()), 'reference binary differs')
    require(build.origin.digest(BASE / 'model.tgl') == record['growth_model_sha256'], 'growth file differs')
    build.origin.verify(build.PREPARED)
    return record


def check_result(value, fixture, days, growth_sha):
    require(value['schema'] == 'garden-leaf-family-replay-v1' and value['complete'] is True
            and value['controller_assignment'] == 'founder-family' and value['objective'] is None,
            'incomplete or wrong replay')
    require(value['seed'] == SEED and value['scenario'] == fixture['scenario']
            and value['ticks'] == days * DAY and value['candidate_founder'] == fixture['founder']
            and value['resident_policy'] == RESIDENT and value['gardener'] is False
            and value['climate'] == 'seasonal' and value['framebuffer_crc32'] is None,
            'timing condition differs')
    require(value['growth_model_sha256'] == growth_sha and
            value['leaf_model_hex'] == model(fixture['action']).hex(), 'model identity differs')
    founders = 3 if fixture['scenario'] == 'rainfed' else 5
    data = bytes.fromhex(value['state_hex'])
    require(data[:8] == b'TFR1' + bytes((fixture['founder'], 3, founders, 0)), 'family state tag differs')
    count, = struct.unpack_from('<I', data, 8)
    require(count == len(value['lineages']) == len(value['family_roots']) and
            data[12:12 + count] == bytes(value['family_roots']) and
            len(data) == 12 + count + 5293, 'family state size or ancestry differs')
    require(data[12 + count:16 + count] == b'TLR1' and
            data[16 + count:188 + count] == model(fixture['action']), 'nested controller differs')
    require(type(value['ledger_start_tick']) is int and value['ledger_start_tick'] == 0,
            'history must start at reset')
    records, _ = index_records(value['lineages'], value['seeds'], 0, days * DAY)
    require(set(records) == set(range(1, count + 1)), 'lineage identities differ')
    roots = {}
    for identity in range(1, count + 1):
        parent = records[identity]['parent']
        require(type(parent) is int and 0 <= parent < identity and
                ((identity <= founders) == (parent == 0)), 'invalid family ownership')
        roots[identity] = roots[parent] if parent else identity
        require(value['family_roots'][identity - 1] == roots[identity], 'incorrect family inheritance')
    return value


def plan():
    return [dict(label=prefix + '-' + fixture['name'], fixture=fixture,
                 build=flavor, days=days, timeout_seconds=timeout)
            for prefix, flavor, days, timeout in (
                ('reference-prefix', 'reference', PREFIX_DAYS, 90),
                ('optimized-prefix', 'optimized', PREFIX_DAYS, 90),
                ('optimized-full', 'optimized', FULL_DAYS, 300),
                ('parallel-full', 'optimized', FULL_DAYS, 300))
            for fixture in FIXTURES]


def check_flags(commands):
    require(commands, 'empty compiler command list')
    for command in commands:
        flags = shlex.split(command['command'])
        # Some frozen support targets already request -O2. Repeating the same
        # flag is harmless; a different optimization level is not equivalent.
        require({f for f in flags if f.startswith('-O')} == {'-O2'} and '-UNDEBUG' in flags and
                not any(f.startswith('-DNDEBUG') for f in flags) and
                '-fsanitize=undefined' in flags and '-fno-sanitize-recover=undefined' in flags,
                'optimization or safety flags differ')


def run_one(out, call, baseline):
    folder = out / call['label']
    folder.mkdir()
    binary = (BASE if call['build'] == 'reference' else out) / 'native/leaf-family-replay'
    fixture = call['fixture']
    args = [str(binary), str(BASE / 'model.tgl'), str(out / (fixture['name'] + '.tlf')),
            SEED, fixture['scenario'], str(call['days'] * DAY), str(fixture['founder']), RESIDENT]
    save(folder / 'started.json', dict(call=call, args=args, automatic_retry=False,
         binary_sha256=build.origin.digest(binary)))
    start = time.perf_counter()
    try:
        child = subprocess.run(args, capture_output=True, timeout=call['timeout_seconds'])
        elapsed = time.perf_counter() - start
        stdout, stderr = child.stdout, child.stderr
        code, timed_out = child.returncode, False
    except subprocess.TimeoutExpired as error:
        elapsed = time.perf_counter() - start
        stdout, stderr = error.stdout or b'', error.stderr or b''
        code, timed_out = None, True
    (folder / 'stdout.json').write_bytes(stdout)
    (folder / 'stderr.txt').write_bytes(stderr)
    receipt = dict(elapsed_seconds=elapsed, returncode=code, timed_out=timed_out,
                   stdout_sha256=sha(stdout), stdout_bytes=len(stdout), stderr_sha256=sha(stderr),
                   stderr_bytes=len(stderr))
    save(folder / 'process.json', receipt)
    require(not timed_out and code == 0 and not stderr and len(stdout) <= 8 * 1024 * 1024,
            'replay failed: ' + call['label'])
    value = check_result(json.loads(stdout), fixture, call['days'], baseline['growth_model_sha256'])
    receipt['logic_ticks_per_second'] = call['days'] * DAY / elapsed
    receipt['logical_realtime_multiplier'] = call['days'] * DAY / 60 / elapsed
    receipt['lineages'] = len(value['lineages'])
    receipt['seeds'] = len(value['seeds'])
    save(folder / 'checked.json', receipt)
    print(f"{call['label']}: {elapsed:.3f}s, {receipt['logic_ticks_per_second']:.0f} ticks/s", flush=True)
    return receipt


def build_optimized(out, baseline):
    env = os.environ | {'PYTHONPATH': os.pathsep.join(map(str, (ROOT / 'sim', ROOT / 'scripts/container'))),
                        'PYTHONDONTWRITEBYTECODE': '1'}
    commands = (
        ['cmake', '-S', BASE / 'modules/leaf_replay', '-B', out / 'native', '-G', 'Ninja',
         '-DTOY_FACTORY_LEAF_CORE=' + str(BASE / 'source'), '-DCMAKE_C_FLAGS=-O2',
         '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON'],
        ['cmake', '--build', out / 'native', '--parallel', '2'],
        ['ctest', '--test-dir', out / 'native', '--output-on-failure'],
    )
    for index, args in enumerate(commands):
        print(f'Optimized build/check {index + 1}/3', flush=True)
        child = subprocess.run(list(map(str, args)), capture_output=True, text=True, env=env, timeout=180)
        save(out / f'build-{index}.json', dict(args=list(map(str, args)), returncode=child.returncode,
                                            stdout=child.stdout, stderr=child.stderr))
        require(child.returncode == 0, child.stdout[-12000:] + child.stderr[-12000:])
        if index == 2:
            require('100% tests passed, 0 tests failed out of 23' in child.stdout, 'suite matrix differs')
    commands = json.loads((out / 'native/compile_commands.json').read_text())
    check_flags(commands)
    require(verify_base() == baseline, 'reference changed during optimized build')
    save(out / 'build.json', dict(reference_sha256=build.origin.digest(BASE / 'build.json'),
         unchanged_core_sha256=baseline['staged_sha256'], unchanged_modules_sha256=baseline['module_sha256'],
         compile_commands_sha256=build.origin.digest(out / 'native/compile_commands.json'),
         optimized_binary_sha256=build.origin.digest(out / 'native/leaf-family-replay'),
         optimization='-O2', assertions=True, undefined_behavior_sanitizer=True, suites_passed=23))


def main(out):
    require(out.parent == ROOT / 'artifacts' and not out.exists() and not out.is_symlink(),
            'fresh direct artifacts child required')
    baseline = verify_base()
    calls = plan()
    require(len(calls) == MAX_CALLS, 'unexpected timing call count')
    out.mkdir()
    scope = dict(schema='garden-leaf-timing-v1', fixed_models=True, training_runs=0,
                 maximum_timing_calls=MAX_CALLS, calls=calls, automatic_retry=False,
                 seed=SEED, resident=RESIDENT, logic_ticks_per_day=DAY,
                 logical_ticks_per_realtime_second=60, peak_concurrent_replays=2,
                 resident_is_timing_fixture_only=True, source_sha256=sha(Path(__file__).read_bytes()),
                 scoring=None, reference_sha256=build.origin.digest(BASE / 'build.json'),
                 host_logical_cpus=os.cpu_count(), available_cpus=len(os.sched_getaffinity(0)),
                 load_average_start=os.getloadavg())
    save(out / 'started.json', scope)
    (out / 'measure_leaf_replay.py').write_bytes(Path(__file__).read_bytes())
    try:
        for fixture in FIXTURES:
            with (out / (fixture['name'] + '.tlf')).open('xb') as stream:
                stream.write(model(fixture['action']))
        build_optimized(out, baseline)
        records = {}
        for call in calls[:4]:
            records[call['label']] = run_one(out, call, baseline)
        for fixture in FIXTURES:
            name = fixture['name']
            require(records['reference-prefix-' + name]['stdout_sha256'] ==
                    records['optimized-prefix-' + name]['stdout_sha256'], 'optimization changes exact output')
        for call in calls[4:6]:
            records[call['label']] = run_one(out, call, baseline)
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=2) as pool:
            # Both already-started bounded calls may finish after a failure.
            futures = [(call, pool.submit(run_one, out, call, baseline)) for call in calls[6:]]
            for call, future in futures:
                records[call['label']] = future.result()
        parallel_elapsed = time.perf_counter() - start
        for fixture in FIXTURES:
            name = fixture['name']
            require(records['optimized-full-' + name]['stdout_sha256'] ==
                    records['parallel-full-' + name]['stdout_sha256'], 'concurrency changes exact output')
        require(verify_base() == baseline and sha(Path(__file__).read_bytes()) == scope['source_sha256'],
                'timing inputs changed')
        save(out / 'result.json', dict(scope=scope, calls=records, parallel_pair_seconds=parallel_elapsed,
             load_average_end=os.getloadavg(), exact_prefix_parity=True, exact_parallel_parity=True,
             training_runs=0, fitness=None))
        print('Timing complete; exact output parity passed; no training or policy selection.', flush=True)
    except BaseException as error:
        save(out / 'failure.json', dict(error=str(error), automatic_retry=False, training_runs=0))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    main(parser.parse_args().out.absolute())
