#!/usr/bin/env python3
"""Predeclared six-pair confirmation using the pilot's unchanged W2 executable."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from functools import cache
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import zlib

import garden_landing_patch_sweep as sweep
import garden_landing_patch_sweep_continue as continuation
from garden_resources import require

ROOT, BASE, STOP, DAY = sweep.ROOT, sweep.BASE, sweep.STOP, sweep.DAY
RULE = 'garden-landing-patch-confirmation-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-patch-confirmation-protocol.md'
PROTOCOL_SHA = '1547fb806ce393680909a2f8d6aac21f3a1c9b8b7302c4847081497f6c760304'
INPUT = 'benchmarks/garden-seasons/landing-patch-sweep-results.json.gz'
INPUT_SHA = 'dd5b43c954c9e82b51f1200819bdef6c9287c7e412bdf467964bb95bdd012f64'
ORIGIN_MANIFEST = 'c48725b1cd3419f3cb9f74c8b3ed6c24dffb13a26a54ecba06d3f582e535caaf'
REFERENCE = 'f7ee4528-fixed-candidate-control-wide-cap-trace'
ARM = 'wide-cap'
SEEDS = ('3a7e45e6', '366928c6', '275c8982')
LAYOUTS = ('rainfed', 'rainfed-crowded')
PHASES = ('control', 'treatment', 'repeat', 'plain')
SOURCES = tuple(sorted({*sweep.SOURCES, continuation.SCRIPT,
                        'sim/garden_landing_patch_confirmation.py',
                        'sim/test_garden_landing_patch_confirmation.py'}))


@cache
def prior():
    require(sweep.digest(ROOT / PROTOCOL) == PROTOCOL_SHA and sweep.digest(ROOT / INPUT) == INPUT_SHA,
            'confirmation protocol/input changed')
    require(SEEDS == tuple(hashlib.sha256(f'toy-factory/landing-patch-confirmation-v1/world/{i}'.encode()).hexdigest()[:8]
                           for i in range(1, 4)), 'world seed derivation changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream:
        value = json.load(stream)
    continuation.check_complete(value)
    require(value['panel'][REFERENCE]['arm'] == ARM and
            '--root-allocation-focal' not in value['runs']['control'][REFERENCE]['args'], 'wrong fixed recipe')
    return value


def panel():
    return {seed + '-' + layout: dict(seed=seed, scenario=layout) for seed in SEEDS for layout in LAYOUTS}


def calls():
    return [('anchor', p) for p in ('control', 'treatment')] + [(p, k) for p in PHASES for k in panel()]


def arguments(key, phase):
    if phase == 'anchor':
        require(key in ('control', 'treatment'), 'unknown anchor')
        return list(prior()['runs'][key][REFERENCE]['args'])
    require(key in panel() and phase in PHASES, 'unknown confirmation call')
    args = sweep.arguments(REFERENCE, phase)
    args[2:4] = [panel()[key]['scenario'], '0x' + panel()[key]['seed']]
    for flag, path in (('--framebuffer', 'frames/end.raw'), *(('--' + k + '-trace', k + '.jsonl') for k in sweep.KINDS)):
        if flag in args:
            args[args.index(flag) + 1] = path
    return args


def check_result(result, key, phase):
    old = prior()['runs']['control'][REFERENCE]['result']
    if phase == 'anchor':
        require(result == prior()['runs'][key][REFERENCE]['result'], 'historical anchor differs')
        return
    case = panel()[key]
    active = phase != 'control'
    require(set(result) == set(old) | ({'patch_sweep_probe', 'placement_run_hash'} if active else set()) and
            result['tick'] == STOP and result['scenario'] == case['scenario'] and result['seed'] == case['seed'],
            'wrong confirmation result identity')
    for name in ('schema_version', 'run_version', 'rules', 'model', 'gardener', 'irrigation',
                 'seed_lifetime_ecology_ticks', 'ledger_start_tick', 'warmup_samples',
                 *(k for k in old if k.endswith('_probe'))):
        require(result[name] == old[name], 'fixed setting changed: ' + name)
    require(result['kind'] == ('landing-patch-sweep-replay' if active else old['kind']) and
            (not active or result['run_hash'] == sweep.tagged(result['placement_run_hash'])) and
            result['climate'] == sweep.followup.previous.climate(int(case['seed'], 16), STOP), 'wrong rule/climate')
    lives, seeds = sweep.index_records(result['lineages'], result['seeds'], 0, STOP)
    require(result['births'] == sum(p['parent'] != 0 for p in lives.values()) and
            result['deaths'] == sum(p['death_tick'] is not None for p in lives.values()) and
            result['living'] == len(lives) - result['deaths'] and
            result['seed_bank'] == sum(s['outcome'] == 'pending' for s in seeds.values()) and
            0 <= result['living'] <= result['plant_slots'] <= 8 and 0 <= result['nodes'] <= 256 and
            0 <= result['seed_bank'] <= 8 and not any('removal_tick' in p for p in lives.values()), 'ledger/capacity differs')
    founders = [(p['column'], p['species']) for p in lives.values() if p['parent'] == 0]
    expected = [(4, 0), (13, 1), (22, 2)] if case['scenario'] == 'rainfed' else [(3, 0), (8, 1), (13, 2), (18, 1), (23, 0)]
    require(founders == expected and all(p['birth_tick'] == 0 and p['generation'] == 0
                                       for p in lives.values() if p['parent'] == 0), 'founder layout differs')
    if active:
        sweep.events(result)
    else:
        require(not any(p['environmental_death'] for p in lives.values()), 'imposed death in control')


def minimum_living(result):
    lives = result['lineages']
    count = sum(p['birth_tick'] <= BASE and (p['death_tick'] is None or p['death_tick'] > BASE) for p in lives)
    low, changes = count, Counter()
    for p in lives:
        if p['birth_tick'] > BASE:
            changes[p['birth_tick']] += 1
        if p['death_tick'] is not None and p['death_tick'] > BASE:
            changes[p['death_tick']] -= 1
    for tick, delta in sorted(changes.items()):
        count += delta
        low = min(low, count)
    require(count == result['living'], 'living chronology differs')
    return low


def verdict(runs):
    wins = {layout: [] for layout in LAYOUTS}
    regressions, empty, temporary_empty = [], [], []
    for key, case in panel().items():
        control, treatment = (runs[p][key] for p in ('control', 'treatment'))
        delta = len(treatment['summary']['qualifying_pairs']) - len(control['summary']['qualifying_pairs'])
        if delta > 0:
            wins[case['scenario']].append(case['seed'])
        elif delta < 0:
            regressions.append(key)
        if not treatment['result']['living']:
            empty.append(key)
        if minimum_living(treatment['result']) == 0:
            temporary_empty.append(key)
    return dict(wins_by_layout=wins, pair_regressions=regressions, empty_treatments=empty,
                zero_living_during_window=temporary_empty,
                confirmed=all(len(v) >= 2 for v in wins.values()) and not regressions and not empty)


def runtime(sources):
    return {p: sha for p, sha in sources.items() if p.startswith(('src/', 'sim/')) and p.endswith(('.c', '.h'))}


def groups(value):
    return [[dict(id=p + '/' + key, framebuffer=value['runs'][p][key]['frame']['path'])
             for p in ('control', 'treatment')] for key in panel()]


def check_run(run, key, phase):
    args = arguments(key, phase)
    kinds = () if phase == 'plain' else sweep.KINDS
    directory = phase + '/' + key
    require(set(run) == {'args', 'directory', 'result', 'summary', 'frame', 'traces'} |
            ({'accounting'} if kinds else set()), 'wrong run receipt fields')
    require(run['args'] == args and run['directory'] == directory and set(run['traces']) == set(kinds) and
            run['frame']['path'] == directory + '/' + args[args.index('--framebuffer') + 1] and all(
                run['traces'][k]['path'] == directory + '/' + args[args.index('--' + k + '-trace') + 1] + '.gz'
                for k in kinds), 'wrong call/trace paths')
    check_result(run['result'], key, phase)
    require(run['summary'] == sweep.summary(run['result']), 'cohort summary differs')
    if kinds:
        sweep.check_accounting(run['accounting'], run['result'])
    if phase == 'anchor':
        previous = prior()['runs'][key][REFERENCE]
        sweep.late.same_run(run, previous, sweep.KINDS)
        require(run['accounting'] == previous['accounting'], 'historical anchor accounting differs')


def check_capture(value):
    original = prior()
    require(value['rule'] == RULE and value['protocol_sha256'] == PROTOCOL_SHA and value['input_sha256'] == INPUT_SHA and
            value['origin_manifest_sha256'] == ORIGIN_MANIFEST and value['reference'] == REFERENCE and
            value['panel'] == panel() and value['native_runs'] == 26 and value['training_runs'] == 0 and
            value['model_sha256'] == original['model_sha256'] and value['build'] == original['builds'][ARM] and
            value['analysis_sources'] == {p: sweep.digest(ROOT / p) for p in SOURCES}, 'confirmation provenance differs')
    sources = value['source_sha256']
    require(runtime(sources) == runtime(original['source_sha256']) and sources[INPUT] == INPUT_SHA and
            sources[PROTOCOL] == PROTOCOL_SHA and all(sources[p] == sha for p, sha in value['analysis_sources'].items()),
            'simulation or analysis snapshot differs')
    require(set(value['runs']) == {'anchor', *PHASES}, 'missing confirmation phase')
    for phase in ('anchor', *PHASES):
        require(set(value['runs'][phase]) == (set(('control', 'treatment')) if phase == 'anchor' else set(panel())),
                'missing confirmation case')
        for key, run in value['runs'][phase].items():
            check_run(run, key, phase)
            if phase in ('treatment', 'repeat', 'plain'):
                control = value['runs']['control'][key]
                require(sweep.prefix(run['result'], BASE) == sweep.prefix(control['result'], BASE), 'pre-event ledgers differ')
                if phase != 'plain':
                    require(run['accounting']['receipts'] == control['accounting']['receipts'], 'pre-event observations differ')
            if phase in ('repeat', 'plain'):
                treatment = value['runs']['treatment'][key]
                sweep.late.same_run(run, treatment, () if phase == 'plain' else sweep.KINDS)
                require(phase == 'plain' or run['accounting'] == treatment['accounting'], 'repeat accounting differs')
    require(value['verdict'] == verdict(value['runs']) and value['gallery']['rows'] ==
            [[f['id'] for f in row] for row in groups(value)] and
            (value['gallery']['width'], value['gallery']['height'], value['gallery']['gap']) == (504, 1496, 8) and
            value['receipt_sha256'] == sweep.fingerprint({k: v for k, v in value.items() if k != 'receipt_sha256'}),
            'wrong verdict/gallery/receipt')


def fresh(out, output):
    require(not out.exists() and not out.is_symlink() and not output.exists() and not output.is_symlink() and
            not output.resolve().is_relative_to(out.resolve()), 'fresh separate outputs required; no automatic resume')


def origin_inputs(origin):
    original = prior()
    require(sweep.digest(origin / 'manifest.json') == ORIGIN_MANIFEST, 'origin manifest changed')
    manifest = json.loads((origin / 'manifest.json').read_text())
    for path, sha in (('bin/' + ARM, original['builds'][ARM]['binary']),
                      (ARM + '-CMakeCache.txt', original['builds'][ARM]['cache']), ('model.tgl', original['model_sha256'])):
        require(manifest['artifacts'][path] == sha, 'origin asset not authenticated')
        sweep.followup.artifact(origin, dict(path=path, sha256=sha))


def call(out, value, key, phase):
    args = arguments(key, phase)
    directory = out / phase / key
    directory.mkdir(parents=True)
    (directory / 'frames').mkdir()
    shutil.copy2(out / 'model.tgl', directory / 'model.tgl')
    result = sweep.native(out / 'bin/garden-landing', directory, *args)
    sweep.write_json(directory / 'result.json', result)
    check_result(result, key, phase)
    run = dict(args=args, directory=phase + '/' + key, result=result, summary=sweep.summary(result), traces={})
    paths = {}
    for kind in (() if phase == 'plain' else sweep.KINDS):
        name = args[args.index('--' + kind + '-trace') + 1]
        path = directory / (name + '.gz')
        sweep.compress(directory / name, path)
        paths[kind] = path
        run['traces'][kind] = dict(path=str(path.relative_to(out)), sha256=sweep.digest(path))
    frame = directory / args[args.index('--framebuffer') + 1]
    raw = frame.read_bytes()
    require(len(raw) == 115200 and f'{zlib.crc32(raw):08x}' == result['framebuffer_crc32'], 'frame CRC differs')
    run['frame'] = dict(path=str(frame.relative_to(out)), sha256=sweep.digest(frame))
    if phase != 'plain':
        run['accounting'] = sweep.account(paths, result)
    check_run(run, key, phase)
    if phase in ('treatment', 'repeat', 'plain'):
        control = value['runs']['control'][key]
        require(sweep.prefix(result, BASE) == sweep.prefix(control['result'], BASE), 'new pre-event ledger differs')
        if phase != 'plain':
            require(run['accounting']['receipts'] == control['accounting']['receipts'], 'new prefix observation differs')
    if phase in ('repeat', 'plain'):
        treatment = value['runs']['treatment'][key]
        sweep.late.same_run(run, treatment, () if phase == 'plain' else sweep.KINDS)
        require(phase == 'plain' or run['accounting'] == treatment['accounting'], 'new repeat account differs')
    sweep.write_json(directory / 'run.json', run)
    print('verified: ' + phase + '/' + key, flush=True)
    return key, run


def collect(out, output, origin, jobs):
    fresh(out, output)
    require(1 <= jobs <= 2 and shutil.disk_usage(out.parent).free >= 14 * 1024 ** 3, '1..2 jobs and 14 GiB free required')
    original = prior()
    origin_inputs(origin)
    sources = sweep.source_files()
    require(runtime(sources) == runtime(original['source_sha256']), 'simulation sources changed')
    out.mkdir(parents=True)
    (out / 'bin').mkdir()
    sweep.snapshot_sources(out, sources)
    shutil.copy2(ROOT / PROTOCOL, out / 'protocol.md')
    shutil.copy2(origin / ('bin/' + ARM), out / 'bin/garden-landing')
    shutil.copy2(origin / (ARM + '-CMakeCache.txt'), out / 'CMakeCache.txt')
    shutil.copy2(origin / 'model.tgl', out / 'model.tgl')
    value = dict(rule=RULE, protocol_sha256=PROTOCOL_SHA, input_sha256=INPUT_SHA,
                 origin_manifest_sha256=ORIGIN_MANIFEST, reference=REFERENCE, panel=panel(),
                 native_runs=26, training_runs=0, model_sha256=original['model_sha256'], build=original['builds'][ARM],
                 source_sha256=sources, analysis_sources={p: sources[p] for p in SOURCES}, runs={})
    sweep.write_json(out / 'started.json', value)
    try:
        for phase in ('anchor', *PHASES):
            value['runs'][phase] = {}
            keys = [k for p, k in calls() if p == phase]
            with ThreadPoolExecutor(max_workers=jobs) as pool:
                for start in range(0, len(keys), jobs):
                    require(shutil.disk_usage(out).free >= 4 * 1024 ** 3, 'less than 4 GiB free; stop without deleting evidence')
                    tasks = [pool.submit(call, out, value, k, phase) for k in keys[start:start + jobs]]
                    value['runs'][phase].update(task.result() for task in tasks)
            sweep.write_json(out / (phase + '.json'), value['runs'][phase])
        value['gallery'] = sweep.contact_sheet(out, groups(value))
        value['gallery']['sha256'] = sweep.digest(out / 'contact-sheet.png')
        value['verdict'] = verdict(value['runs'])
        require(all(sweep.digest(ROOT / p) == sources[p] for p in (*runtime(sources), *SOURCES, PROTOCOL)),
                'sources changed during confirmation')
        origin_inputs(origin)
        require(sweep.digest(out / 'bin/garden-landing') == value['build']['binary'] and
                sweep.digest(out / 'CMakeCache.txt') == value['build']['cache'] and
                sweep.digest(out / 'model.tgl') == value['model_sha256'], 'captured inputs changed')
        value['receipt_sha256'] = sweep.fingerprint(value)
        check_capture(value)
        sweep.write_json(out / 'capture.json', value)
        sweep.write_json(out / 'manifest.json', dict(rule=RULE, artifacts={str(p.relative_to(out)): sweep.digest(p)
                                              for p in sorted(out.rglob('*')) if p.is_file()}))
        sweep.write_gzip(output, value)
    except Exception as error:
        sweep.write_json(out / 'failure.json', dict(rule=RULE, error=str(error), automatic_retry=False))
        raise
    return value


def verify_bundle(root, value):
    check_capture(value)
    manifest = json.loads((root / 'manifest.json').read_text())
    require(manifest['rule'] == RULE and json.loads((root / 'capture.json').read_text()) == value and
            sweep.archived_sources(root / 'source.tar.gz') == value['source_sha256'], 'raw snapshot differs')
    require(set(manifest['artifacts']) == {str(p.relative_to(root)) for p in root.rglob('*')
                                         if p.is_file() and p != root / 'manifest.json'}, 'raw inventory differs')
    for path, sha in manifest['artifacts'].items():
        sweep.followup.artifact(root, dict(path=path, sha256=sha))
    require(sweep.digest(root / 'protocol.md') == PROTOCOL_SHA and
            sweep.digest(root / 'bin/garden-landing') == value['build']['binary'] and
            sweep.digest(root / 'CMakeCache.txt') == value['build']['cache'] and
            sweep.digest(root / 'model.tgl') == value['model_sha256'], 'raw inputs differ')
    for phase, key in calls():
        run = value['runs'][phase][key]
        directory = root / run['directory']
        require(json.loads((directory / 'run.json').read_text()) == run and
                json.loads((directory / 'result.json').read_text()) == run['result'], 'raw run receipt differs')
        raw = sweep.followup.artifact(root, run['frame']).read_bytes()
        require(len(raw) == 115200 and f'{zlib.crc32(raw):08x}' == run['result']['framebuffer_crc32'], 'raw frame differs')
        paths = {k: sweep.followup.artifact(root, t) for k, t in run['traces'].items()}
        if paths:
            require(sweep.account(paths, run['result']) == run['accounting'], 'raw accounting differs')
        print('offline verified: ' + phase + '/' + key, flush=True)
    require(sweep.digest(root / 'contact-sheet.png') == value['gallery']['sha256'], 'gallery changed')
    with tempfile.TemporaryDirectory(prefix='patch-confirmation-gallery-') as tmp:
        frames = groups(value)
        for row in frames:
            for f in row:
                f['framebuffer'] = str(root / f['framebuffer'])
        found = sweep.contact_sheet(Path(tmp), frames)
        found['sha256'] = sweep.digest(Path(tmp) / 'contact-sheet.png')
        require(found == value['gallery'], 'gallery does not reproduce')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--collect', type=Path)
    mode.add_argument('--verify', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--origin', type=Path, default=ROOT / 'artifacts/garden-landing-patch-sweep-v1')
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    require(bool(args.collect) == bool(args.out) and not (args.collect and args.bundle), 'invalid output/mode')
    if args.collect:
        fresh(args.collect, args.out)
        value = collect(args.collect.resolve(), args.out.resolve(), args.origin.resolve(), args.jobs)
    else:
        with gzip.open(args.verify, 'rt') as stream:
            value = json.load(stream)
        check_capture(value)
        if args.bundle:
            verify_bundle(args.bundle.resolve(), value)
    print(json.dumps(value['verdict'], sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, TypeError, OSError, StopIteration) as error:
        sys.exit(str(error))
