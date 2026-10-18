#!/usr/bin/env python3
"""Capture the frozen five-world single-death diagnostic, then verify offline."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import copy
from functools import cache
import gzip
import json
from pathlib import Path
import shutil
import sys
import zlib

import garden_landing_reproductive_access as previous
from garden_experiments import compress, digest, snapshot_sources, source_files, write_json
from garden_gallery import contact_sheet
from garden_landing_energy_audit import archived_sources
from garden_landing_founders import write_gzip
from garden_landing_root_allocation_audit import fingerprint
from garden_landing_training import native
from garden_resources import require

followup = previous.followup
ROOT, BASE, STOP, STEP, DAY = previous.ROOT, previous.BASE, previous.STOP, previous.STEP, previous.DAY
RULE = 'garden-landing-disturbance-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-disturbance-protocol.md'
PROTOCOL_SHA = 'e193885119bfc3b394074b1a2d2791c612c344d5023efadcb88d68cf7f4fba61'
AUDIT = 'benchmarks/garden-seasons/landing-reproductive-access-results.json.gz'
AUDIT_SHA = '1db7c619a4acd770e36dccfd108c8d75369c9dbcd3153b98273f51b6024b5f39'
PHASES = ('control', 'treatment', 'repeat', 'plain')
KINDS = followup.KINDS
BUILDS = {k: v for k, v in followup.previous.late.BUILDS.items() if k.startswith('wide')}
SOURCES = ('sim/garden_landing_disturbance.py', 'sim/garden_landing_followup.py',
           'sim/garden_landing_reproductive_access.py', 'sim/garden_descendants.py',
           'sim/garden_experiments.py', 'sim/garden_gallery.py', 'sim/garden_resources.py',
           'sim/garden_landing_training.py', 'sim/garden_landing_founders.py',
           'sim/garden_landing_energy_audit.py', 'sim/garden_landing_root_allocation_audit.py')
CHANGED_RUNTIME = {'src/garden_world.c', 'src/garden_world.h', 'sim/garden_landing_cli.c',
                   'sim/garden_landing_ledger.c', 'sim/garden_landing_ledger.h',
                   'sim/garden_landing_turnover.c', 'sim/garden_landing_turnover.h',
                   'sim/garden_landing_turnover_test.c'}


@cache
def inputs():
    require(digest(ROOT / PROTOCOL) == PROTOCOL_SHA and digest(ROOT / AUDIT) == AUDIT_SHA,
            'turnover protocol/input changed')
    saved, cohort = previous.inputs()
    panel = {}
    for key, ids in cohort.items():
        if not ids:
            continue
        old = saved['runs']['baseline'][key]['result']
        target = min((p for p in old['lineages'] if p['death_tick'] is None and p['id'] not in ids),
                     key=lambda p: (p['birth_tick'], p['id']))
        require(target['birth_tick'] + DAY < BASE, 'target is not established')
        panel[key] = dict(focal=ids, target=target['id'], column=target['column'],
                          arm=key.split('-', 4)[4].removesuffix('-trace'))
    require(len(panel) == 5 and sum(len(w['focal']) for w in panel.values()) == 7, 'wrong fixed panel')
    return saved, panel


def arguments(key, phase):
    saved, panel = inputs()
    require(phase in PHASES and key in panel, 'invalid call')
    args = list(saved['runs']['extension'][key]['args'])
    if phase == 'plain':
        flags = ('--stand-trace', '--stand-start', '--stand-stop', '--adult-trace', '--adult-start',
                 '--adult-stop', '--direction-trace', '--reach-trace')
        for flag in flags:
            n = args.index(flag)
            del args[n:n + 2]
        args.remove('--stand-dawn')
    if phase != 'control':
        args += ['--turnover-at', str(BASE), '--turnover-lineage', str(panel[key]['target'])]
    return args


def probe_hash(base, tick, identity):
    value = 2166136261
    raw = b'GLT1' + b''.join(v.to_bytes(4, 'little') for v in (int(base, 16), tick, identity))
    for byte in raw:
        value = ((value ^ byte) * 16777619) & 0xffffffff
    return f'{value:08x}'


def check_result(result, key, phase):
    saved, panel = inputs()
    old, base = saved['runs']['extension'][key]['result'], saved['runs']['baseline'][key]['result']
    w = panel[key]
    require(result['tick'] == STOP and set(result) == set(old) | (
        {'turnover_probe', 'placement_run_hash'} if phase != 'control' else set()), 'wrong result schema')
    if phase == 'control':
        require(result == old, 'control differs from archived result')
    for name in ('scenario', 'seed', 'model', 'rules', 'run_version', 'gardener', 'irrigation',
                 'seed_lifetime_ecology_ticks', 'ledger_start_tick', 'climate',
                 *(k for k in old if k.endswith('_probe'))):
        require(result[name] == old[name], 'unrelated configuration changed: ' + name)
    lives, seeds = previous.bank.descendants.index_records(result['lineages'], result['seeds'], 0, STOP)
    require(result['deaths'] == sum(p['death_tick'] is not None for p in lives.values()) and
            result['living'] == len(lives) - result['deaths'] and
            result['births'] == sum(p['parent'] != 0 for p in lives.values()) and
            result['seed_bank'] == sum(s['outcome'] == 'pending' for s in seeds.values()), 'ledger totals differ')
    prefix = copy.deepcopy(result)
    if phase != 'control':
        event = result['turnover_probe']
        require(set(event) == {'version', 'tick', 'lineage', 'column', 'nodes', 'energy', 'water',
                               'before_world_hash', 'after_world_hash', 'before_run_hash', 'after_run_hash'} and
                event['version'] == 1 and event['tick'] == BASE and event['lineage'] == w['target'] and
                event['column'] == w['column'] and event['before_run_hash'] == base['run_hash'] and
                event['before_world_hash'] == base['world_hash'] and
                0 < event['nodes'] <= 32 and 0 <= event['energy'] <= 256 and 0 <= event['water'] <= 512 and
                event['before_world_hash'] != event['after_world_hash'] and
                event['before_run_hash'] != event['after_run_hash'], 'wrong imposed event/boundary')
        require(result['kind'] == 'landing-turnover-replay' and result['run_hash'] ==
                probe_hash(result['placement_run_hash'], BASE, w['target']), 'wrong turnover identity')
        require([p['id'] for p in lives.values() if p['environmental_death']] == [w['target']] and
                lives[w['target']]['death_tick'] == BASE and
                all('removal_tick' not in p for p in lives.values()), 'death/export classification differs')
        next(p for p in prefix['lineages'] if p['id'] == w['target']).update(death_tick=None, environmental_death=False)
    require(followup.prefix_ledgers(prefix) == (base['lineages'], base['seeds']), 'pre-event ledger history changed')


def check_run(run, key, phase):
    saved, _ = inputs()
    require(run['args'] == arguments(key, phase) and run['directory'] == phase + '/' + key and
            set(run['traces']) == (set() if phase == 'plain' else set(KINDS)), 'call/trace identity differs')
    check_result(run['result'], key, phase)
    if phase == 'plain':
        require(run['receipts'] == {}, 'untraced run has receipts')
    else:
        require(set(run['receipts']) == set(KINDS), 'incomplete receipts')
        for kind in KINDS:
            name = run['args'][run['args'].index('--' + kind + '-trace') + 1]
            require(run['traces'][kind]['path'] == run['directory'] + '/' + name + '.gz', 'wrong trace path')
            r, old = run['receipts'][kind], saved['runs']['extension'][key]['receipts'][kind]
            require(r['boundary_sha256'] == old['boundary_sha256'] and
                    (kind != 'reach' or r['prefix_sha256'] == old['prefix_sha256']), 'pre-event observations changed')
    name = run['args'][run['args'].index('--framebuffer') + 1]
    require(run['frame']['path'] == run['directory'] + '/' + name, 'wrong frame path')
    if phase == 'control':
        followup.previous.late.same_run(run, saved['runs']['extension'][key], KINDS)


def receipt(path, kind, result):
    # The event is after the BASE observation: use the pre-event lifetime only
    # for stand framing/census receipts. Full post-event analysis uses true fates.
    observed = copy.deepcopy(result)
    if 'turnover_probe' in result:
        identity = result['turnover_probe']['lineage']
        next(p for p in observed['lineages'] if p['id'] == identity)['death_tick'] = BASE + STEP
    return followup.trace_receipt(path, kind, STEP if kind == 'reach' else BASE, STOP, observed)


def check_capture(value):
    saved, panel = inputs()
    require(value['rule'] == RULE and value['protocol_sha256'] == PROTOCOL_SHA and
            value['input_sha256'] == previous.INPUT_SHA and value['audit_sha256'] == AUDIT_SHA and
            value['native_runs'] == 20 and value['training_runs'] == 0 and value['panel'] == panel and
            value['model_sha256'] == saved['model_sha256'] and set(value['runs']) == set(PHASES) and
            set(value['builds']) == set(BUILDS), 'wrong capture provenance')
    require(value['analysis_sources'] == {p: digest(ROOT / p) for p in SOURCES}, 'collector implementation changed')
    for arm, build in value['builds'].items():
        require(build['settings'] == saved['builds'][arm]['settings'], 'build settings differ')
    for phase in PHASES:
        require(set(value['runs'][phase]) == set(panel), 'incomplete phase')
        for key, run in value['runs'][phase].items():
            check_run(run, key, phase)
            if phase in ('repeat', 'plain'):
                other = value['runs']['treatment'][key]
                followup.previous.late.same_run(run, other, () if phase == 'plain' else KINDS)
                require(phase == 'plain' or run['receipts'] == other['receipts'], 'repeated receipts differ')
    require(value['receipt_sha256'] == fingerprint({k: v for k, v in value.items() if k != 'receipt_sha256'}),
            'capture receipt changed')


def collect(out, original, jobs):
    require(not out.exists() and not out.is_symlink() and 1 <= jobs <= 4 and
            shutil.disk_usage(out.parent).free >= 10 * 1024 ** 3, 'fresh output, 10 GiB free and 1..4 jobs required')
    saved, panel = inputs()
    require(digest(original / 'manifest.json') == previous.MANIFEST_SHA and
            json.loads((original / 'capture.json').read_text()) == saved and
            digest(original / 'model.tgl') == saved['model_sha256'], 'wrong source bundle')
    sources = source_files()
    runtime = {p: h for p, h in sources.items() if p.startswith(('src/', 'sim/')) and p.endswith(('.c', '.h'))}
    require({p for p, h in runtime.items() if h != saved['source_sha256'].get(p)} <= CHANGED_RUNTIME,
            'unrelated runtime changed')
    out.mkdir(parents=True)
    (out / 'bin').mkdir()
    snapshot_sources(out, sources)
    shutil.copy2(ROOT / PROTOCOL, out / 'protocol.md')
    shutil.copy2(original / 'model.tgl', out / 'model.tgl')
    value = dict(rule=RULE, protocol_sha256=PROTOCOL_SHA, input_sha256=previous.INPUT_SHA,
                 audit_sha256=AUDIT_SHA, native_runs=20, training_runs=0, panel=panel,
                 model_sha256=saved['model_sha256'], source_sha256=sources,
                 analysis_sources={p: sources[p] for p in SOURCES}, builds={}, runs={})
    for arm, build in BUILDS.items():
        binary, settings = ROOT / build / 'toy-factory-garden-landing', ROOT / build / 'CMakeCache.txt'
        options = followup.previous.late.settings_at(settings, arm)
        require(options == saved['builds'][arm]['settings'], 'build options changed')
        value['builds'][arm] = dict(binary=digest(binary), cache=digest(settings), settings=options)
        shutil.copy2(binary, out / ('bin/' + arm))
        shutil.copy2(settings, out / (arm + '-CMakeCache.txt'))
    write_json(out / 'started.json', value)

    def capture(key, phase):
        args, directory = arguments(key, phase), out / phase / key
        directory.mkdir(parents=True)
        (directory / 'frames').mkdir()
        shutil.copy2(out / 'model.tgl', directory / 'model.tgl')
        result = native(out / ('bin/' + panel[key]['arm']), directory, *args)
        write_json(directory / 'result.json', result)
        check_result(result, key, phase)
        run = dict(directory=str(directory.relative_to(out)), args=args, result=result, traces={}, receipts={})
        for kind in (() if phase == 'plain' else KINDS):
            name = args[args.index('--' + kind + '-trace') + 1]
            path = directory / (name + '.gz')
            compress(directory / name, path)
            run['traces'][kind] = dict(path=str(path.relative_to(out)), sha256=digest(path))
            run['receipts'][kind] = receipt(path, kind, result)
        frame = directory / args[args.index('--framebuffer') + 1]
        pixels = frame.read_bytes()
        require(len(pixels) == 115200 and f'{zlib.crc32(pixels):08x}' == result['framebuffer_crc32'], 'frame differs')
        run['frame'] = dict(path=str(frame.relative_to(out)), sha256=digest(frame))
        check_run(run, key, phase)
        write_json(directory / 'run.json', run)
        print(phase + '/' + key + ': verified', flush=True)
        return key, run

    for phase in PHASES:
        pool = ThreadPoolExecutor(max_workers=jobs)
        try:
            tasks = [pool.submit(capture, key, phase) for key in sorted(panel)]
            value['runs'][phase] = dict(t.result() for t in tasks)
        finally:
            pool.shutdown(wait=True, cancel_futures=True)
        write_json(out / (phase + '.json'), value['runs'][phase])
        print(phase + ': complete', flush=True)
    groups = [[dict(id=phase + '/' + key, framebuffer=value['runs'][phase][key]['frame']['path'])
               for phase in ('control', 'treatment')] for key in sorted(panel)]
    value['gallery'] = contact_sheet(out, groups)
    value['gallery']['sha256'] = digest(out / 'contact-sheet.png')
    require(all(digest(ROOT / p) == h for p, h in runtime.items()) and
            all(digest(ROOT / p) == sources[p] for p in (*SOURCES, PROTOCOL)) and
            all(digest(ROOT / d / 'toy-factory-garden-landing') == value['builds'][a]['binary']
                for a, d in BUILDS.items()), 'runtime/collector/build changed during capture')
    value['receipt_sha256'] = fingerprint(value)
    check_capture(value)
    write_json(out / 'capture.json', value)
    write_json(out / 'manifest.json', dict(rule=RULE, artifacts={str(p.relative_to(out)): digest(p)
                                          for p in sorted(out.rglob('*')) if p.is_file()}))
    return value


def verify_bundle(root, value):
    manifest = json.loads((root / 'manifest.json').read_text())
    require(manifest['rule'] == RULE, 'wrong raw bundle')
    for path, sha in manifest['artifacts'].items():
        followup.artifact(root, dict(path=path, sha256=sha))
    require(json.loads((root / 'capture.json').read_text()) == value and
            archived_sources(root / 'source.tar.gz') == value['source_sha256'] and
            digest(root / 'model.tgl') == value['model_sha256'], 'captured provenance differs')
    for phase, calls in value['runs'].items():
        for run in calls.values():
            for kind, item in run['traces'].items():
                require(receipt(followup.artifact(root, item), kind, run['result']) == run['receipts'][kind],
                        'raw trace receipt differs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--collect', type=Path)
    mode.add_argument('--verify', type=Path)
    parser.add_argument('--original', type=Path, default=ROOT / 'artifacts/garden-landing-followup-v1')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    require(bool(args.out) == bool(args.collect) and not (args.bundle and args.collect), 'invalid mode options')
    if args.collect:
        require(not args.collect.exists() and not args.collect.is_symlink() and
                not args.out.exists() and not args.out.is_symlink(), 'fresh outputs required')
        value = collect(args.collect.resolve(), args.original.resolve(), args.jobs)
        write_gzip(args.out, value)
    else:
        with gzip.open(args.verify, 'rt') as stream:
            value = json.load(stream)
        check_capture(value)
        if args.bundle:
            verify_bundle(args.bundle.resolve(), value)
    print('verified ' + RULE)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, TypeError, OSError) as error:
        print('error: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
