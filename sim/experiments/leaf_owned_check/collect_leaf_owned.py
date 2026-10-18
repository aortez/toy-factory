#!/usr/bin/env python3
"""Retain and verify a completed comparison without executing native code."""

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

import compare_leaf_owned as panel

sys.path.insert(0, str(panel.HERE.parent / 'leaf_timing'))
from measure_leaf_replay import check_flags

SCHEMA = 'garden-leaf-owned-evidence-v1'
PARITY = ('exact_prefix_parity', 'exact_full_parity', 'exact_pixels', 'exact_capture_parallel_parity')
SOURCES = ('sim/experiments/leaf_owned_check/compare_leaf_owned.py',
           'sim/experiments/leaf_objective/family_fitness.py')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify(bundle):
    """Recheck identities and equality from retained bytes, not success flags.

    Hashes bind the retained data to its receipts; they are provenance, not
    adversarial authentication. The repository's prefix reference is required,
    but local build/replay artifact directories are not.
    """
    require = panel.require
    require(bundle['schema'] == SCHEMA, 'wrong evidence schema')
    result = bundle['result']
    scope = result['scope']
    require(scope['schema'] == 'garden-leaf-owned-comparison-v1' and scope['calls'] == panel.calls()
            and scope['maximum_native_calls'] == 11 and scope['maximum_parallel_processes'] == 2
            and scope['automatic_retry'] is False and scope['training_runs'] == 0 and scope['fitness'] is None,
            'comparison scope differs')
    require(result['training_runs'] == 0 and result['fitness'] is None and
            all(result[k] is True for k in PARITY), 'incomplete comparison')
    require(set(bundle['runs']) == set(result['receipts']) == {c['label'] for c in scope['calls']},
            'missing or extra calls')
    require(set(bundle['source_text']) == set(scope['source_sha256']) == set(SOURCES) and
            all(sha(text.encode()) == scope['source_sha256'][path]
                for path, text in bundle['source_text'].items()), 'recorded source bytes differ')
    identities = scope['identities']
    build_meta = {}
    for name, expected_suites in (('new', 25), ('reference', 23)):
        build = bundle['builds'][name]
        raw = build['build_json'].encode()
        require(sha(raw) == identities[name + '_build_sha256'], 'build receipt hash differs')
        meta = json.loads(raw)
        build_meta[name] = meta
        tests = build['tests']
        require(tests['returncode'] == 0 and
                f'100% tests passed, 0 tests failed out of {expected_suites}' in tests['stdout'],
                'incomplete build tests')
        binary = meta['binary_sha256']['leaf-family-owned'] if name == 'new' else meta['optimized_binary_sha256']
        require(binary == identities['owned_binary_sha256' if name == 'new' else 'reference_binary_sha256'],
                'build executable differs')
        check_flags(json.loads(build['compile_commands_json']))
        if name == 'reference':
            require(sha(build['compile_commands_json'].encode()) == meta['compile_commands_sha256'],
                    'reference compiler receipt differs')
    require(build_meta['new']['growth_model_sha256'] == identities['growth_model_sha256'] and
            build_meta['new']['staged_sha256'] == build_meta['reference']['unchanged_core_sha256'],
            'core or growth model differs')
    reference = panel.read(panel.ROOT / 'benchmarks/garden-seasons/leaf-family-throughput.json')
    parsed = {}
    for call in scope['calls']:
        label = call['label']
        row = bundle['runs'][label]
        started, process, checked = row['started'], row['process'], result['receipts'][label]
        binary_sha = identities['owned_binary_sha256' if call['binary'] == 'owned' else 'reference_binary_sha256']
        require(started['call'] == call and started['binary_sha256'] == binary_sha, 'call identity differs')
        args = started['args']
        binary_name = 'leaf-family-owned' if call['binary'] == 'owned' else 'leaf-family-replay'
        root = Path(args[1]).parent
        case = call['case']
        expected_tail = [case['seed'], case['scenario'], str(call['days'] * panel.DAY),
                         str(case['founder']), panel.RESIDENT]
        if call['capture']:
            expected_tail.append(str(root / label / 'frame.raw'))
        require(Path(args[0]).name == binary_name and Path(args[1]).name == 'growth.tgl' and
                args[2] == str(root / (case['model'] + '.tlf')) and args[3:] == expected_tail,
                'command arguments differ')
        stdout, stderr = row['stdout'].encode(), row['stderr'].encode()
        require(process['returncode'] == 0 and process['timed_out'] is False and not stderr and
                process['stdout_sha256'] == sha(stdout) and process['stderr_sha256'] == sha(stderr) and
                process['stdout_bytes'] == len(stdout) and process['stderr_bytes'] == 0 and
                all(checked.get(k) == v for k, v in process.items()), 'process receipt differs')
        elapsed = process['elapsed_seconds']
        require(type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed > 0, 'invalid timing')
        frame_sha = checked['framebuffer_sha256']
        pixels = bytes.fromhex(bundle['frames'][frame_sha]) if call['capture'] else None
        require((pixels is not None and sha(pixels) == frame_sha) or
                (pixels is None and frame_sha is None), 'frame receipt differs')
        value = panel.check_output(json.loads(stdout), call, identities['growth_model_sha256'], pixels)
        require(checked['lineages'] == len(value['lineages']) and checked['seeds'] == len(value['seeds']) and
                checked['logic_ticks_per_second'] == value['ticks'] / elapsed, 'derived receipt differs')
        if call['days'] == 16:
            require(row['stdout'] == reference['prefix_stdout'][case['name']], 'archived prefix differs')
        parsed[label] = value
    expected_frames = {result['receipts'][c['label']]['framebuffer_sha256'] for c in scope['calls'] if c['capture']}
    require(set(bundle['frames']) == expected_frames, 'unreferenced or missing frames')
    for case in panel.CASES:
        owned, reference, plain = (phase + '-' + case['name'] for phase in ('owned', 'reference', 'parallel'))
        require(bundle['runs'][owned]['stdout'] == bundle['runs'][reference]['stdout'], 'full output differs')
        require(result['receipts'][owned]['framebuffer_sha256'] == result['receipts'][reference]['framebuffer_sha256'],
                'full pixels differ')
        require(parsed[owned] | {'framebuffer_crc32': None} == parsed[plain], 'capture/concurrency parity differs')
    return bundle


def collect(root):
    panel.require(not (root / 'failure.json').exists(), 'failed attempt cannot be collected as complete')
    result = panel.read(root / 'result.json')
    panel.require(result['scope'] == panel.read(root / 'started.json'), 'scope changed')
    panel.require(set(result['scope']['source_sha256']) == set(SOURCES), 'unexpected source paths')
    source = {path: (panel.ROOT / path).read_text() for path in SOURCES}
    runs, frames = {}, {}
    for call in result['scope']['calls']:
        folder = root / call['label']
        panel.require(panel.read(folder / 'checked.json') == result['receipts'][call['label']],
                      'checked receipt changed')
        runs[call['label']] = dict(started=panel.read(folder / 'started.json'),
            process=panel.read(folder / 'process.json'), stdout=(folder / 'stdout.json').read_text(),
            stderr=(folder / 'stderr.txt').read_text())
        if call['capture']:
            pixels = (folder / 'frame.raw').read_bytes()
            frames[sha(pixels)] = pixels.hex()
    builds = {name: dict(build_json=(folder / 'build.json').read_text(),
                        tests=panel.read(folder / 'build-2.json'),
                        compile_commands_json=(folder / 'native/compile_commands.json').read_text())
              for name, folder in (('new', panel.NEW), ('reference', panel.OLD))}
    return verify(dict(schema=SCHEMA, result=result, runs=runs, frames=frames, builds=builds, source_text=source))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--check', type=Path)
    args = parser.parse_args()
    if args.check is not None:
        panel.require(args.source is None and args.out is None, 'check cannot collect')
        verify(json.loads(gzip.decompress(args.check.read_bytes())))
    else:
        panel.require(args.source is not None and args.out is not None, 'source and fresh output required')
        value = collect(args.source)
        raw = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()
        with args.out.open('xb') as stream:
            stream.write(gzip.compress(raw, mtime=0))
    print('All eleven calls, histories, state bytes, pixel bytes and receipts verify without native execution.')


if __name__ == '__main__':
    main()
