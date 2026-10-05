#!/usr/bin/env python3
"""Two frozen, passive winter-light replays; no rebuilds or parameter search."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import cache
import gzip
import json
from pathlib import Path
import shutil
import sys
import tarfile

import garden_landing_late_dispersal as historical
from garden_experiments import compress, digest, write_json
from garden_landing_energy_audit import archived_sources
from garden_resources import require

ROOT = historical.ROOT
RULE = 'garden-landing-winter-light-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-winter-light-protocol.md'
PROTOCOL_SHA = '5bf5f7514bd372af33bd36edf5e55e9dbdbc413ff3734f4692f4fd472e4b5a19'
INPUTS = {
    'benchmarks/garden-seasons/landing-energy-history-results.json.gz':
        'ad05d00dce06ffdfbf5208586dfa03aed07277f0ec2f9ef77f83d78e842540a8',
    'benchmarks/garden-seasons/landing-late-dispersal-results.json.gz':
        '390669aba064732072c82e2170ad1d6f7872612710bc1c6501ad3351c8ad3b62',
}
SPANS = [[974400, 976305], [978240, 979230]]
ARMS = {'control': 'cap', 'candidate': 'wide-cap'}
KINDS = ('stand', 'adult', 'direction', 'reach', 'uptake')
NATIVE_FILES = {
    'manifest.json': '4a94df9dcc4f53c980e3631b58dc3fd853c3f03a68678d335127ab09f7a83001',
    'capture.json': '7f57efe6826bf893b419c7b74def96ba58fe4df9ba244256ed85177b0073c966',
    'source.tar.gz': '6af22304b0907ad8a97ac8c6a7f8d02cf6cede26ea3584309387fa8858a66e11',
    'model.tgl': 'f2dc989380339614dc512f64f11f2bf03f7079c465c4c9bd18895044ec3e1567',
    'bin/cap': '63c4cd859bc7c179374703cc7d2292fc31fa58c977947a17cb0fbbb96e0e9058',
    'bin/wide-cap': '3012729e6ff4209706140b49746df5099620a963d972e5187cfca8a74883d1c2',
    'cap-CMakeCache.txt': '402f85aadd7b58758fe8f593156224a86b6ee7ef16c15d11b9153d878e9e5a57',
    'wide-cap-CMakeCache.txt': '8b122290d5aba7ef6c409690da37a86b1613f9e487d025f56625a34fcd1b5356',
}
SOURCES = ('sim/garden_landing_winter_light_capture.py', 'sim/garden_experiments.py',
           'sim/garden_landing_late_dispersal.py', 'sim/garden_landing_training.py',
           'sim/garden_landing_evaluate.py', 'sim/garden_landing_energy_audit.py',
           'sim/garden_resources.py', PROTOCOL)


def provenance():
    require(digest(ROOT / PROTOCOL) == PROTOCOL_SHA and
            all(digest(ROOT / p) == sha for p, sha in INPUTS.items()), 'frozen winter-light inputs changed')
    return dict(rule=RULE, inputs=INPUTS, protocol_sha256=PROTOCOL_SHA, native_files=NATIVE_FILES,
                full_replays=2, training_runs=0, windows=SPANS)


@cache
def originals():
    provenance()
    with gzip.open(ROOT / list(INPUTS)[1], 'rt') as stream: value = json.load(stream)
    require(value['raw_manifest_sha256'] == NATIVE_FILES['manifest.json'], 'wrong original manifest')
    capture = value['capture']
    return capture, {side: capture['runs']['f7ee4528-fixed-candidate-candidate-' + arm + '-trace']
                     for side, arm in ARMS.items()}


def arguments(original):
    args = list(original['args'])
    require(args.count('--uptake-window') == 1, 'unexpected original observation windows')
    at = args.index('--uptake-window')
    require(args[at + 1] == '626520:660480', 'wrong original observation window')
    return args[:at] + [v for a, b in SPANS for v in ('--uptake-window', f'{a}:{b}')] + args[at + 2:]


def check_run(run, original, side):
    args = arguments(original)
    require(run['args'] == args and run['result'] == original['result'] and
            set(run['traces']) == set(KINDS), 'observer changed arguments/result')
    for kind, item in run['traces'].items():
        require(item['path'] == side + '/' + args[args.index('--' + kind + '-trace') + 1] + '.gz',
                'wrong trace location')
        if kind != 'uptake':
            require(item['sha256'] == original['traces'][kind]['sha256'], 'observer changed ordinary trace')
    require(run['frame'] == dict(path=side + '/' + args[args.index('--framebuffer') + 1],
                                sha256=original['frame']['sha256']), 'observer changed pixels')


def check_capture(value):
    require(value['provenance'] == provenance() and type(value['provenance']['full_replays']) is int and
            type(value['provenance']['training_runs']) is int and set(value['runs']) == set(ARMS),
            'wrong winter-light capture provenance')
    require(value['source_sha256'] == {p: digest(ROOT / p) for p in SOURCES}, 'capture source changed')
    _, runs = originals()
    for side in ARMS: check_run(value['runs'][side], runs[side], side)


def check_native(bundle):
    require(all(digest(bundle / p) == sha for p, sha in NATIVE_FILES.items()), 'archived native input changed')
    capture = json.loads((bundle / 'capture.json').read_text())
    require(capture == originals()[0] and archived_sources(bundle / 'source.tar.gz') == capture['source_sha256'],
            'native source/capture archive differs')
    for arm in ARMS.values():
        require(historical.settings_at(bundle / (arm + '-CMakeCache.txt'), arm) ==
                capture['builds'][arm]['settings'], 'archived settings differ')


def collect(bundle, out):
    require(not out.exists() and not out.is_symlink() and
            (out.is_relative_to(ROOT / 'artifacts') or not out.is_relative_to(ROOT)), 'fresh capture output required')
    meta, (_, old) = provenance(), originals()
    check_native(bundle)
    sources = {p: digest(ROOT / p) for p in SOURCES}
    out.mkdir(parents=True)
    for name in NATIVE_FILES:
        dest = out / 'native' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundle / name, dest)
    with tarfile.open(out / 'capture-source.tar.gz', 'w:gz') as archive:
        for name in sources: archive.add(ROOT / name, arcname=name, recursive=False)
    write_json(out / 'plan.json', dict(provenance=meta, source_sha256=sources))

    def run(side):
        directory = out / side
        directory.mkdir()
        (directory / 'frames').mkdir()
        shutil.copy2(out / 'native/model.tgl', directory / 'model.tgl')
        args = arguments(old[side])
        print(side + ': starting archived passive replay', flush=True)
        result = historical.population.order.training.native(out / ('native/bin/' + ARMS[side]), directory, *args)
        write_json(directory / 'result.json', result)
        require(result == old[side]['result'], 'observer changed native result')
        traces = {}
        for kind in KINDS:
            name = args[args.index('--' + kind + '-trace') + 1]
            target = directory / (name + '.gz')
            compress(directory / name, target)
            traces[kind] = dict(path=side + '/' + name + '.gz', sha256=digest(target))
        frame = args[args.index('--framebuffer') + 1]
        value = dict(args=args, result=result, traces=traces,
                     frame=dict(path=side + '/' + frame, sha256=digest(directory / frame)))
        write_json(directory / 'run.json', value)
        check_run(value, old[side], side)
        print(side + ': exact historical result, ordinary traces and pixels', flush=True)
        return value

    with ThreadPoolExecutor(max_workers=2) as pool:
        runs = dict(zip(ARMS, pool.map(run, ARMS), strict=True))
    value = dict(provenance=meta, source_sha256=sources, runs=runs)
    check_capture(value)
    require(archived_sources(out / 'capture-source.tar.gz') == sources, 'capture source archive changed')
    check_native(out / 'native')
    write_json(out / 'capture.json', value)
    write_json(out / 'manifest.json', dict(rule=RULE, status='complete', artifacts={
        str(p.relative_to(out)): digest(p) for p in sorted(out.rglob('*')) if p.is_file()}))
    return value


def verify_bundle(bundle):
    manifest = json.loads((bundle / 'manifest.json').read_text())
    require(manifest['rule'] == RULE and manifest['status'] == 'complete' and
            not (bundle / 'FAILED.txt').exists(), 'incomplete winter-light capture')
    require(set(manifest['artifacts']) == {str(p.relative_to(bundle)) for p in bundle.rglob('*')
            if p.is_file() and p != bundle / 'manifest.json'}, 'raw inventory changed')
    for name, sha in manifest['artifacts'].items():
        p = (bundle / name).resolve()
        require(p.is_relative_to(bundle.resolve()) and digest(p) == sha, 'raw artifact changed or escaped bundle')
    value = json.loads((bundle / 'capture.json').read_text())
    check_capture(value)
    check_native(bundle / 'native')
    require(archived_sources(bundle / 'capture-source.tar.gz') == value['source_sha256'] and
            json.loads((bundle / 'plan.json').read_text()) == {k: value[k] for k in ('provenance', 'source_sha256')},
            'capture plan/source differs')
    for side, run in value['runs'].items():
        require(json.loads((bundle / side / 'run.json').read_text()) == run and
                json.loads((bundle / side / 'result.json').read_text()) == run['result'] and
                digest(bundle / side / 'model.tgl') == NATIVE_FILES['model.tgl'], 'raw run/model differs')
        for item in (run['frame'], *run['traces'].values()):
            require(digest(bundle / item['path']) == item['sha256'], 'raw run receipt differs')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', type=Path, default=ROOT / 'artifacts/garden-landing-late-dispersal-v1')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--out', type=Path)
    mode.add_argument('--verify', type=Path)
    args = parser.parse_args()
    if args.verify:
        verify_bundle(args.verify.resolve())
        print('Verified passive replay bundle; no native calls.')
    else:
        require(not args.out.exists() and not args.out.is_symlink(), 'fresh capture output required')
        out = args.out.resolve()
        try: collect(args.native.resolve(), out)
        except Exception as error:
            if out.is_dir():
                with (out / 'FAILED.txt').open('x') as stream: stream.write(str(error) + '\n')
            raise
        print('Completed exactly two passive winter-light replays.')


if __name__ == '__main__':
    try: main()
    except (RuntimeError, ValueError, KeyError, OSError, TypeError) as error:
        print('winter-light capture failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
