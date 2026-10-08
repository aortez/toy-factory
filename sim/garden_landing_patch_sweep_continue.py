#!/usr/bin/env python3
"""Complete only the thirteen approved calls from the pinned interrupted sweep."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import copy
from functools import cache
import gzip
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import zlib

import garden_landing_patch_sweep as screen
from garden_resources import require

ROOT = screen.ROOT
INTERRUPTION = 'benchmarks/garden-seasons/landing-patch-sweep-interruption.json.gz'
INTERRUPTION_SHA = 'de9d7713a9f9391e0bf52eb8a5f6b01f7339b474bee969270a720f28ca32bde0'
PLAN = 'benchmarks/garden-seasons/landing-patch-sweep-continuation.md'
PLAN_SHA = '3342b8d7662e8e91e007e468c4e8cb9c58bc6ac09d1998320b99916520a31596'
SCRIPT = 'sim/garden_landing_patch_sweep_continue.py'
AUDITOR = 'sim/garden_landing_patch_sweep.py'
CAPTURE_SHA = '24fb404ec6f437cbb33f8d53468248834d1414e0a3e76274dc3c88426cab3116'
AUDITOR_SHA = 'c50c90426ae50da32c6d2abd67db3d20ec4f0ad5c9bcb7c4bd833b20e7fc15ec'


@cache
def interrupted():
    require(screen.digest(ROOT / INTERRUPTION) == INTERRUPTION_SHA and screen.digest(ROOT / PLAN) == PLAN_SHA and
            screen.digest(ROOT / AUDITOR) == AUDITOR_SHA, 'continuation inputs changed')
    with gzip.open(ROOT / INTERRUPTION, 'rt') as stream:
        value = json.load(stream)
    saved, baseline = screen.inputs()
    keys = sorted(saved['panel'])
    require(value['rule'] == 'garden-landing-patch-sweep-interrupted-v1' and
            value['status'] == 'stopped-after-auditor-error' and value['planned_native_calls'] == 25 and
            value['completed_native_calls'] == 12 and value['offline_native_calls'] == 0 and
            value['receipt_sha256'] == screen.fingerprint({k: v for k, v in value.items() if k != 'receipt_sha256'}) and
            value['analysis_sources'] == {p: screen.digest(ROOT / p) for p in screen.SOURCES} and
            {p: sorted(r) for p, r in value['runs'].items()} == dict(baseline=keys, control=keys, treatment=keys[:2]),
            'invalid interrupted batch')
    require(value['remaining'] == [dict(phase=p, key=k) for p in ('treatment', 'repeat', 'plain') for k in keys
                                   if k not in value['runs'].get(p, {})], 'remaining calls differ')
    for phase, runs in value['runs'].items():
        for key, run in runs.items():
            require(run['args'] == screen.arguments(key, phase) and run['directory'] == phase + '/' + key,
                    'retained invocation differs')
            screen.check_result(run['result'], key, phase)
            if phase == 'baseline':
                screen.late.same_run(run, baseline['runs']['extension'][key], screen.followup.KINDS)
            else:
                screen.check_accounting(run['accounting'], run['result'])
                require(run['summary'] == screen.summary(run['result']), 'retained summary differs')
            if phase == 'treatment':
                require(run['accounting']['receipts'] == value['runs']['control'][key]['accounting']['receipts'],
                        'retained prefix differs')
    return value


def provenance():
    return dict(interruption_sha256=INTERRUPTION_SHA, plan_sha256=PLAN_SHA,
                runner_sha256=screen.digest(ROOT / SCRIPT), captured_auditor_sha256=CAPTURE_SHA,
                corrected_auditor_sha256=AUDITOR_SHA, retained_calls=12, new_calls=13,
                executed_calls=interrupted()['remaining'])


def authenticate(root, prior):
    """Read only. Authenticate the entire pre-continuation bundle, not just winning rows."""
    started = prior['started']
    require(screen.digest(root / 'interruption-manifest.json') == prior['raw_manifest_sha256'] and
            json.loads((root / 'started.json').read_text()) == started and
            screen.archived_sources(root / 'source.tar.gz') == started['source_sha256'], 'original provenance differs')
    manifest = json.loads((root / 'interruption-manifest.json').read_text())
    for path, sha in manifest['artifacts'].items():
        screen.followup.artifact(root, dict(path=path, sha256=sha))
    require(screen.digest(root / 'model.tgl') == started['model_sha256'] and
            screen.digest(root / 'protocol.md') == screen.PROTOCOL_SHA and
            all(screen.digest(root / ('bin/' + arm)) == info['binary'] and
                screen.digest(root / (arm + '-CMakeCache.txt')) == info['cache']
                for arm, info in started['builds'].items()), 'captured executable/model/config differs')
    with tarfile.open(root / 'source.tar.gz') as archive:
        original = archive.extractfile(AUDITOR).read().decode()
    old = "                    p['death_tick'] == tick and v['age'] == (tick - p['birth_tick']) // STEP and\n"
    new = ("                    # Offspring germinate before grow_plants in the same step;\n"
           "                    # their stored age is already one at the recorded birth.\n"
           "                    p['death_tick'] == tick and v['age'] == (tick - p['birth_tick']) // STEP + (p['parent'] != 0) and\n")
    require(started['analysis_sources'][AUDITOR] == CAPTURE_SHA and original.count(old) == 1 and
            original.replace(old, new) == (ROOT / AUDITOR).read_text(), 'unrecorded auditor change')
    for runs in prior['runs'].values():
        for run in runs.values():
            require(json.loads((root / run['directory'] / 'result.json').read_text()) == run['result'],
                    'retained native output differs')
            frame = screen.followup.artifact(root, run['frame']).read_bytes()
            require(len(frame) == 115200 and f'{zlib.crc32(frame):08x}' == run['result']['framebuffer_crc32'],
                    'retained frame differs')
            for trace in run['traces'].values():
                screen.followup.artifact(root, trace)


def require_fresh(root, output, calls):
    paths = [root / 'continuation', root / 'capture.json', root / 'manifest.json', root / 'contact-sheet.png', output,
             *(root / (p + '.json') for p in ('treatment', 'repeat', 'plain')),
             *(root / c['phase'] / c['key'] for c in calls)]
    require(all(not p.exists() and not p.is_symlink() for p in paths), 'continuation outputs must be absent; no automatic resume')


def call(root, value, key, phase):
    args = screen.arguments(key, phase)
    directory = root / phase / key
    directory.mkdir(parents=True)
    (directory / 'frames').mkdir()
    shutil.copy2(root / 'model.tgl', directory / 'model.tgl')
    result = screen.native(root / ('bin/' + value['panel'][key]['arm']), directory, *args)
    screen.write_json(directory / 'result.json', result)
    screen.check_result(result, key, phase)
    run = dict(args=args, directory=phase + '/' + key, result=result, traces={}, summary=screen.summary(result))
    paths = {}
    for kind in (() if phase == 'plain' else screen.KINDS):
        name = args[args.index('--' + kind + '-trace') + 1]
        path = directory / (name + '.gz')
        screen.compress(directory / name, path)
        paths[kind] = path
        run['traces'][kind] = dict(path=str(path.relative_to(root)), sha256=screen.digest(path))
    frame = directory / args[args.index('--framebuffer') + 1]
    pixels = frame.read_bytes()
    require(len(pixels) == 115200 and f'{zlib.crc32(pixels):08x}' == result['framebuffer_crc32'], 'new frame differs')
    run['frame'] = dict(path=str(frame.relative_to(root)), sha256=screen.digest(frame))
    if phase != 'plain':
        run['accounting'] = screen.account(paths, result)
        require(run['accounting']['receipts'] == value['runs']['control'][key]['accounting']['receipts'], 'new prefix differs')
    if phase in ('repeat', 'plain'):
        screen.late.same_run(run, value['runs']['treatment'][key], () if phase == 'plain' else screen.KINDS)
        require(phase == 'plain' or run['accounting'] == value['runs']['treatment'][key]['accounting'], 'repeat account differs')
    screen.write_json(directory / 'run.json', run)
    print('continued ' + phase + ': ' + key + ' verified', flush=True)
    return key, run


def groups(value):
    return [[dict(id=p + '/' + key, framebuffer=value['runs'][p][key]['frame']['path']) for p in ('control', 'treatment')]
            for key in sorted(value['panel'])]


def check_complete(value):
    prior = interrupted()
    screen.check_capture(value)
    require(value['continuation'] == provenance() and value['source_sha256'] == prior['started']['source_sha256'] and
            value['builds'] == prior['started']['builds'] and value['analysis_sources'] == prior['analysis_sources'],
            'continuation provenance differs')
    for phase, runs in prior['runs'].items():
        for key, run in runs.items():
            require(value['runs'][phase][key] == run, 'a retained call was replaced')
    require(value['gallery']['rows'] == [[f['id'] for f in row] for row in groups(value)] and
            value['gallery']['width'] == 504 and value['gallery']['height'] == 1248 and value['gallery']['gap'] == 8,
            'wrong fixed gallery panel')


def complete(root, output, jobs):
    prior = interrupted()
    require_fresh(root, output, prior['remaining'])
    require(1 <= jobs <= 2 and shutil.disk_usage(root).free >= 8 * 1024 ** 3, '1..2 jobs and 8 GiB free required')
    authenticate(root, prior)
    runtime = {p: h for p, h in prior['started']['source_sha256'].items()
               if p.startswith(('src/', 'sim/')) and p.endswith(('.c', '.h'))}
    require(all(screen.digest(ROOT / p) == sha for p, sha in runtime.items()), 'simulation sources changed')
    value = copy.deepcopy(prior['started'])
    value.update(runs=copy.deepcopy(prior['runs']), analysis_sources=prior['analysis_sources'], continuation=provenance())
    marker = root / 'continuation'
    marker.mkdir()
    for path in (PLAN, SCRIPT, AUDITOR):
        shutil.copy2(ROOT / path, marker / Path(path).name)
    screen.write_json(marker / 'started.json', value['continuation'])
    print('Authenticated twelve retained calls; starting exactly thirteen missing calls', flush=True)
    for phase in ('treatment', 'repeat', 'plain'):
        value['runs'].setdefault(phase, {})
        keys = [c['key'] for c in prior['remaining'] if c['phase'] == phase]
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            for start in range(0, len(keys), jobs):
                tasks = [pool.submit(call, root, value, k, phase) for k in keys[start:start + jobs]]
                value['runs'][phase].update(t.result() for t in tasks)
        screen.write_json(root / (phase + '.json'), value['runs'][phase])
    value['gallery'] = screen.contact_sheet(root, groups(value))
    value['gallery']['sha256'] = screen.digest(root / 'contact-sheet.png')
    value['verdict'] = screen.verdict(value['runs'])
    require(value['continuation'] == provenance() and all(screen.digest(ROOT / p) == sha for p, sha in runtime.items()),
            'sources changed during continuation')
    authenticate(root, prior)
    value['receipt_sha256'] = screen.fingerprint(value)
    check_complete(value)
    screen.write_json(root / 'capture.json', value)
    screen.write_json(root / 'manifest.json', dict(rule=screen.RULE, artifacts={str(p.relative_to(root)): screen.digest(p)
                                              for p in sorted(root.rglob('*')) if p.is_file()}))
    screen.write_gzip(output, value)
    return value


def verify_bundle(root, value):
    check_complete(value)
    authenticate(root, interrupted())
    expected = {PLAN: PLAN_SHA, SCRIPT: value['continuation']['runner_sha256'], AUDITOR: AUDITOR_SHA}
    require(json.loads((root / 'continuation/started.json').read_text()) == value['continuation'] and
            all(screen.digest(root / 'continuation' / Path(p).name) == h for p, h in expected.items()),
            'saved continuation sources differ')
    screen.verify_bundle(root, value)
    require(screen.digest(root / 'contact-sheet.png') == value['gallery']['sha256'], 'gallery pixels changed')
    with tempfile.TemporaryDirectory(prefix='patch-sweep-gallery-verify-') as tmp:
        absolute = groups(value)
        for row in absolute:
            for frame in row:
                frame['framebuffer'] = str(root / frame['framebuffer'])
        metadata = screen.contact_sheet(Path(tmp), absolute)
        metadata['sha256'] = screen.digest(Path(tmp) / 'contact-sheet.png')
        require(metadata == value['gallery'], 'gallery does not reproduce from the fixed endpoint frames')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--continue-bundle', type=Path)
    mode.add_argument('--verify', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    require(bool(args.out) == bool(args.continue_bundle) and not (args.bundle and args.continue_bundle), 'invalid mode/output')
    if args.continue_bundle:
        require(not args.continue_bundle.is_symlink() and not args.out.is_symlink(), 'symlink output not allowed')
        value = complete(args.continue_bundle.resolve(), args.out.resolve(), args.jobs)
    else:
        with gzip.open(args.verify, 'rt') as stream:
            value = json.load(stream)
        check_complete(value)
        if args.bundle:
            verify_bundle(args.bundle.resolve(), value)
    print(json.dumps(value['verdict'], sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, TypeError, OSError, StopIteration) as error:
        sys.exit(str(error))
