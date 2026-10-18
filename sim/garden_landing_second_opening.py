#!/usr/bin/env python3
"""Frozen second-opening capture; prior single-event artifacts remain immutable."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import copy
from functools import cache
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zlib

import garden_landing_disturbance as first
from garden_experiments import compress, digest, snapshot_sources, source_files, write_json
from garden_gallery import contact_sheet
from garden_landing_energy_audit import archived_sources
from garden_landing_founders import write_gzip
from garden_landing_root_allocation_audit import fingerprint
from garden_landing_training import native
from garden_resources import require

followup = first.followup
ROOT, FIRST, BASE, STEP, DAY = first.ROOT, first.BASE, first.STOP, first.STEP, first.DAY
STOP = 320 * DAY
RULE = 'garden-landing-second-opening-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-second-opening-protocol.md'
PROTOCOL_SHA = '9c144d03df558ab17bba0dbc2a19ff65284d742531315a5b9f643049a575a9e5'
INPUT = 'benchmarks/garden-seasons/landing-disturbance-capture.json.gz'
INPUT_SHA = '8677447bbb1609522e48c25a425a17e0dbbb9efa5c133810b1a72a8204750e39'
AUDIT = 'benchmarks/garden-seasons/landing-disturbance-results.json.gz'
AUDIT_SHA = '0cd9571fa218c7c511db98572c15a56d3982ea66129b748c4919302c614f66d2'
ORIGINAL_MANIFEST = '0726b1cf464c09e0d835aa2e888a10e8e1ff38d959ec5a7b17b7186b1206d712'
PHASES = ('baseline', 'control', 'treatment', 'repeat', 'plain')
KINDS, BUILDS = first.KINDS, first.BUILDS
SOURCES = tuple(sorted({*first.SOURCES, 'sim/garden_landing_second_opening.py'}))
CHANGED_RUNTIME = first.CHANGED_RUNTIME - {'src/garden_world.c', 'src/garden_world.h'}


@cache
def inputs():
    require(digest(ROOT / PROTOCOL) == PROTOCOL_SHA and digest(ROOT / INPUT) == INPUT_SHA and
            digest(ROOT / AUDIT) == AUDIT_SHA, 'second-opening protocol/input changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream:
        saved = json.load(stream)
    first.check_capture(saved)
    panel = {}
    for key, world in saved['panel'].items():
        result = saved['runs']['treatment'][key]['result']
        target = min((p for p in result['lineages'] if p['death_tick'] is None and p['id'] not in world['focal']),
                     key=lambda p: (p['birth_tick'], p['id']))
        require(target['birth_tick'] + DAY < BASE, 'second target is not established')
        recruits = [p['id'] for p in result['lineages'] if p['birth_tick'] > FIRST]
        require(len(recruits) == 1, 'wrong first-recruit cohort')
        panel[key] = dict(focal=world['focal'], first_target=world['target'], first_recruits=recruits,
                          target=target['id'], column=target['column'], arm=world['arm'])
    require([w['target'] for _, w in sorted(panel.items())] == [20, 19, 26, 19, 19], 'fixed targets changed')
    return saved, panel


def arguments(key, phase):
    saved, panel = inputs()
    require(key in panel and phase in PHASES, 'invalid second-opening call')
    args = list(saved['runs']['treatment'][key]['args'])
    if phase != 'baseline':
        for flag in ('--ticks', '--stand-stop', '--adult-stop'):
            args[args.index(flag) + 1] = str(STOP)
    if phase in ('treatment', 'repeat', 'plain'):
        args += ['--second-turnover-at', str(BASE), '--second-turnover-lineage', str(panel[key]['target'])]
    if phase == 'plain':
        for flag in ('--stand-trace', '--stand-start', '--stand-stop', '--adult-trace', '--adult-start',
                     '--adult-stop', '--direction-trace', '--reach-trace'):
            n = args.index(flag)
            del args[n:n + 2]
        args.remove('--stand-dawn')
    return args


def check_result(result, key, phase):
    saved, panel = inputs()
    old, world = saved['runs']['treatment'][key]['result'], panel[key]
    second = phase in ('treatment', 'repeat', 'plain')
    stop = BASE if phase == 'baseline' else STOP
    require(result['tick'] == stop and set(result) == set(old) | ({'second_turnover_probe'} if second else set()),
            'wrong second-opening schema/horizon')
    if phase == 'baseline':
        require(result == old, 'baseline result differs')
    for name in ('schema_version', 'scenario', 'seed', 'model', 'rules', 'run_version', 'gardener', 'irrigation',
                 'seed_lifetime_ecology_ticks', 'ledger_start_tick', 'warmup_samples',
                 *(k for k in old if k.endswith('_probe'))):
        require(result[name] == old[name], 'unrelated configuration/history changed: ' + name)
    require(result['climate'] == followup.previous.climate(int(result['seed'], 16), stop), 'wrong climate')
    lives, seeds = first.previous.bank.descendants.index_records(result['lineages'], result['seeds'], 0, stop)
    require(result['deaths'] == sum(p['death_tick'] is not None for p in lives.values()) and
            result['living'] == len(lives) - result['deaths'] and
            result['births'] == sum(p['parent'] != 0 for p in lives.values()) and
            result['seed_bank'] == sum(s['outcome'] == 'pending' for s in seeds.values()), 'ledger totals differ')
    expected_ids = {world['first_target']} | ({world['target']} if second else set())
    require({i for i, p in lives.items() if p['environmental_death']} == expected_ids and
            all('removal_tick' not in p for p in lives.values()), 'imposed death classification differs')
    expected_hash = first.probe_hash(result['placement_run_hash'], FIRST, world['first_target'])
    prefix = copy.deepcopy(result)
    if second:
        event = result['second_turnover_probe']
        require(set(event) == set(old['turnover_probe']) and event['version'] == 1 and
                event['tick'] == BASE and event['lineage'] == world['target'] and event['column'] == world['column'] and
                event['before_world_hash'] == old['world_hash'] and event['before_run_hash'] == old['placement_run_hash'] and
                event['before_world_hash'] != event['after_world_hash'] and
                event['before_run_hash'] != event['after_run_hash'] and
                0 < event['nodes'] <= 32 and 0 <= event['energy'] <= 256 and 0 <= event['water'] <= 512 and
                lives[world['target']]['death_tick'] == BASE, 'wrong second event/boundary')
        expected_hash = first.probe_hash(expected_hash, BASE, world['target'])
        next(p for p in prefix['lineages'] if p['id'] == world['target']).update(death_tick=None, environmental_death=False)
    require(result['kind'] == ('landing-turnover-pair-replay' if second else 'landing-turnover-replay') and
            result['run_hash'] == expected_hash, 'wrong chronological event identity')
    require(followup.prefix_ledgers(prefix, BASE) == (old['lineages'], old['seeds']), 'day-288 history changed')


def receipt(path, kind, result):
    prefix, boundary, states, occupancy = hashlib.sha256(), None, [], Counter()
    lives = {p['id']: p for p in result['lineages']}
    for row, raw in followup.trace_rows(path, kind, STEP if kind == 'reach' else FIRST, result['tick'], result):
        tick = row['tick']
        if tick <= BASE:
            prefix.update(raw)
        if tick == BASE:
            boundary = fingerprint(row)
        if kind != 'stand':
            continue
        slots = row['plant_order']
        # Both event observations precede the imposed death at that same tick.
        live = {i for i, p in lives.items() if p['birth_tick'] <= tick and
                (p['death_tick'] is None or p['death_tick'] > tick or
                 (p['environmental_death'] and p['death_tick'] == tick))}
        require(len(slots) == len(set(slots)) <= 8 and live <= set(slots) <= set(lives) and
                {b['id'] for b in row['bodies']} == live and
                row['climate'] == followup.previous.climate(int(result['seed'], 16), tick), 'stand census differs')
        if tick >= BASE and (not states or slots != states[-1][1]):
            states.append([tick, slots])
        if tick > BASE:
            occupancy[f'{len(live)}/{len(slots)}'] += 1
    require(boundary is not None, 'missing day-288 observation')
    return dict(prefix_sha256=prefix.hexdigest(), boundary_sha256=boundary, states=states, occupancy=dict(occupancy))


def check_run(run, key, phase, baseline=None):
    saved, _ = inputs()
    require(run['args'] == arguments(key, phase) and run['directory'] == phase + '/' + key and
            set(run['traces']) == set(run['receipts']) == (set() if phase == 'plain' else set(KINDS)), 'wrong call identity')
    check_result(run['result'], key, phase)
    for kind in run['traces']:
        name = run['args'][run['args'].index('--' + kind + '-trace') + 1]
        require(run['traces'][kind]['path'] == run['directory'] + '/' + name + '.gz', 'wrong trace path')
        if baseline is not None:
            require(all(run['receipts'][kind][field] == baseline['receipts'][kind][field]
                        for field in ('prefix_sha256', 'boundary_sha256')), 'pre-event observations changed')
    name = run['args'][run['args'].index('--framebuffer') + 1]
    require(run['frame']['path'] == run['directory'] + '/' + name, 'wrong frame path')
    if phase == 'baseline':
        followup.previous.late.same_run(run, saved['runs']['treatment'][key], KINDS)


def check_capture(value):
    saved, panel = inputs()
    require(value['rule'] == RULE and value['protocol_sha256'] == PROTOCOL_SHA and
            value['input_sha256'] == INPUT_SHA and value['audit_sha256'] == AUDIT_SHA and
            value['native_runs'] == 25 and value['training_runs'] == 0 and value['panel'] == panel and
            value['model_sha256'] == saved['model_sha256'] and set(value['runs']) == set(PHASES) and
            set(value['builds']) == set(BUILDS), 'wrong capture provenance')
    require(value['analysis_sources'] == {p: digest(ROOT / p) for p in SOURCES}, 'collector implementation changed')
    for arm, build in value['builds'].items():
        require(build['settings'] == saved['builds'][arm]['settings'], 'build settings differ')
    for phase in PHASES:
        require(set(value['runs'][phase]) == set(panel), 'incomplete phase')
        for key, run in value['runs'][phase].items():
            check_run(run, key, phase, value['runs']['baseline'][key])
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
    require(digest(original / 'manifest.json') == ORIGINAL_MANIFEST and
            json.loads((original / 'capture.json').read_text()) == saved and
            digest(original / 'model.tgl') == saved['model_sha256'], 'wrong source bundle')
    sources = source_files()
    runtime = {p: h for p, h in sources.items() if p.startswith(('src/', 'sim/')) and p.endswith(('.c', '.h'))}
    old_runtime = {p: h for p, h in saved['source_sha256'].items()
                   if p.startswith(('src/', 'sim/')) and p.endswith(('.c', '.h'))}
    require({p for p in runtime.keys() | old_runtime.keys() if runtime.get(p) != old_runtime.get(p)} <=
            CHANGED_RUNTIME, 'unrelated runtime changed')
    out.mkdir(parents=True)
    (out / 'bin').mkdir()
    snapshot_sources(out, sources)
    shutil.copy2(ROOT / PROTOCOL, out / 'protocol.md')
    shutil.copy2(original / 'model.tgl', out / 'model.tgl')
    value = dict(rule=RULE, protocol_sha256=PROTOCOL_SHA, input_sha256=INPUT_SHA, audit_sha256=AUDIT_SHA,
                 native_runs=25, training_runs=0, panel=panel, model_sha256=saved['model_sha256'],
                 source_sha256=sources, analysis_sources={p: sources[p] for p in SOURCES}, builds={}, runs={})
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
        check_run(run, key, phase, value['runs'].get('baseline', {}).get(key))
        write_json(directory / 'run.json', run)
        print(phase + '/' + key + ': verified', flush=True)
        return key, run

    for phase in PHASES:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            tasks = [pool.submit(capture, key, phase) for key in sorted(panel)]
            value['runs'][phase] = dict(t.result() for t in tasks)
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
    check_capture(value)
    manifest = json.loads((root / 'manifest.json').read_text())
    require(manifest['rule'] == RULE and json.loads((root / 'capture.json').read_text()) == value and
            archived_sources(root / 'source.tar.gz') == value['source_sha256'] and
            digest(root / 'model.tgl') == value['model_sha256'], 'captured provenance differs')
    for path, sha in manifest['artifacts'].items():
        followup.artifact(root, dict(path=path, sha256=sha))
    for calls in value['runs'].values():
        for run in calls.values():
            for kind, item in run['traces'].items():
                require(receipt(followup.artifact(root, item), kind, run['result']) == run['receipts'][kind],
                        'raw trace receipt differs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--collect', type=Path)
    mode.add_argument('--verify', type=Path)
    parser.add_argument('--original', type=Path, default=ROOT / 'artifacts/garden-landing-disturbance-v1')
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
