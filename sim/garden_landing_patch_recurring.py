#!/usr/bin/env python3
"""Frozen recurring-winter comparison and offline population/event verification."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import copy
from functools import cache
import gzip
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import garden_landing_seed_wait as waiting
from garden_experiments import digest, snapshot_sources, write_json
from garden_gallery import contact_sheet, rgb565be_to_rgb888, write_png
from garden_landing_energy_audit import archived_sources
from garden_landing_founders import write_gzip
from garden_resources import require

prior, files = waiting.prior, waiting.files
ROOT, DAY, BASE, STOP, PANEL = prior.ROOT, prior.DAY, prior.BASE, prior.STOP, prior.PANEL
RULE = 'garden-landing-patch-recurring-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-patch-recurring-protocol.md'
PROTOCOL_SHA = 'be1b1fe9f6d422d806b64455afeed0eed0785459c0cec21c4ae7b0548b62292d'
INPUT = 'benchmarks/garden-seasons/landing-seed-wait-results.json.gz'
INPUT_SHA = '05989040f933de126a5d4a1fba6c484608059c26da6642872cc9607d864b6dbb'
ORIGIN_MANIFEST = 'c31d824c205850a9e8c6cf22535ffeb56bf24b9ca5dffeb1d71621f87c140d95'
ARMS, PHASES = ('stopped', 'recurring'), ('anchor', 'endpoint', 'repeat', 'plain')
RUNTIME_DELTA = {'sim/garden_landing_cli.c', 'sim/garden_landing_patch_sweep.c',
                 'sim/garden_landing_patch_sweep.h'}
SCHEDULE = dict(version=1, first_day=396, period_days=32, width=4, first_patch=1, scheduled_events=4)


@cache
def original():
    require(digest(ROOT / INPUT) == INPUT_SHA, 'source capture changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream:
        value = json.load(stream)
    waiting.check_capture(value)
    return value


def arguments(key, arm, phase):
    require(key in PANEL and arm in ARMS and phase in PHASES, 'unknown call')
    args = list(original()['runs'][phase]['cursor'][key]['args'])
    return args + (['--patch-recurring', 'on'] if arm == 'recurring' else [])


def tagged(base):
    words = [int(base, 16), 396, 32, 4, 4, 1]
    h = 2166136261
    for byte in b'GPR1' + b''.join(x.to_bytes(4, 'little') for x in words):
        h = ((h ^ byte) * 16777619) & 0xffffffff
    return f'{h:08x}'


def schedule(tick):
    return [dict(tick=d * DAY, first=4 * (i + 1), last=4 * (i + 1) + 3)
            for i, d in enumerate((396, 428, 460, 492)) if d * DAY <= tick]


def check_events(result, *, name='patch_recurring_probe', metadata=None, expected_events=None):
    # Later fixed panels reuse the same spatial/death audit, supplying their
    # explicit schedule. Historical callers retain the four-event contract.
    metadata = SCHEDULE if metadata is None else metadata
    expected_events = schedule(result['tick']) if expected_events is None else expected_events
    probe = result[name]
    require(set(probe) == set(metadata) | {'events'} and
            {k: probe[k] for k in metadata} == metadata and type(probe['events']) is list,
            'recurring schedule differs')
    require([{k: e[k] for k in ('tick', 'first', 'last')} for e in probe['events']] == expected_events,
            'missing/reordered recurring event')
    lives = {p['id']: p for p in result['lineages']}
    old_ids = {v['lineage'] for e in result['patch_sweep_probe']['events'] for v in e['victims']}
    seen = set()
    for event in probe['events']:
        require(set(event) == {'tick', 'first', 'last', 'victims', 'before_world_hash', 'after_world_hash',
                               'before_run_hash', 'after_run_hash'}, 'wrong event schema')
        tick = event['tick']
        expected = {i for i, p in lives.items() if p['birth_tick'] <= tick and
                    event['first'] <= p['column'] <= event['last'] and
                    (p['death_tick'] is None or p['death_tick'] > tick or
                     p['environmental_death'] and p['death_tick'] == tick)}
        ids = [v['lineage'] for v in event['victims']]
        require(len(ids) == len(set(ids)) <= 8 and set(ids) == expected and
                not (seen | old_ids).intersection(ids), 'incomplete/repeated spatial victims')
        seen.update(ids)
        for v in event['victims']:
            p = lives[v['lineage']]
            require(set(v) == {'lineage', 'age', 'nodes', 'energy', 'water'} and p['environmental_death'] and
                    p['death_tick'] == tick and v['age'] == (tick - p['birth_tick']) // 15 + (p['parent'] != 0) and
                    0 < v['nodes'] <= 32 and 0 <= v['energy'] <= 256 and 0 <= v['water'] <= 512,
                    'wrong recurring victim receipt')
        for kind in ('world', 'run'):
            before, after = (event[f'{side}_{kind}_hash'] for side in ('before', 'after'))
            require(all(type(h) is str and re.fullmatch('[0-9a-f]{8}', h) for h in (before, after)) and
                    ((before == after) == (not ids)), 'empty/nonempty event identity differs')
    require(seen | old_ids == {i for i, p in lives.items() if p['environmental_death']},
            'unreceipted imposed death')
    return seen


def check_result(result, key, arm, phase):
    reference = original()['runs'][phase]['cursor'][key]['result']
    if arm == 'stopped':
        require(result == reference, 'stopped control differs from saved cursor')
        return
    require(set(result) == set(reference) | {'patch_recurring_probe'} and
            result['kind'] == 'landing-patch-recurring-replay' and
            result['patch_sweep_probe'] == reference['patch_sweep_probe'] and
            result['run_hash'] == tagged(prior.previous.sweep.tagged(result['placement_run_hash'])),
            'recurring schema/history/identity differs')
    new_deaths = check_events(result)
    normalized = copy.deepcopy(result)
    normalized.pop('patch_recurring_probe')
    normalized['kind'] = reference['kind']
    normalized['run_hash'] = prior.previous.sweep.tagged(result['placement_run_hash'])
    # The historical checker knows only the fifteen old imposed deaths. After
    # fully reconciling the new receipts, hide ONLY their classification from
    # that legacy check; retain real lifetimes/census and original captured data.
    for p in normalized['lineages']:
        if p['id'] in new_deaths:
            p['environmental_death'] = False
    prior.check_result(normalized, key, 'cursor', phase)
    if phase == 'anchor':
        require(normalized == reference, 'recurring anchor changed common history')


def analyze(result):
    value = prior.analyze(result)
    deaths = [p for p in result['lineages'] if p['death_tick'] is not None and BASE < p['death_tick'] <= STOP]
    value['mortality'] = {cause: dict(ids=[p['id'] for p in deaths if p['environmental_death'] == imposed],
        by_age_32=[p['id'] for p in deaths if p['environmental_death'] == imposed and
                   p['death_tick'] - p['birth_tick'] <= 32 * DAY])
        for cause, imposed in (('imposed', True), ('natural', False))}
    return value


def decision(outcomes):
    value = prior.decision({'fixed': outcomes['stopped'], 'cursor': outcomes['recurring']})
    return dict(arms=dict(stopped=value['arms']['fixed'], recurring=value['arms']['cursor']),
        pairs=value['pairs'], diversity_tradeoff=value['diversity_tradeoff'],
        recurring_renewal_advantage=value['cursor_renewal_advantage'])


def check_capture(value):
    require(value['rule'] == RULE and value['protocol_sha256'] == PROTOCOL_SHA and
            digest(ROOT / PROTOCOL) == PROTOCOL_SHA and value['input_sha256'] == INPUT_SHA and
            value['origin_manifest_sha256'] == ORIGIN_MANIFEST and value['native_runs'] == 48 and
            value['training_runs'] == 0 and value['panel'] == PANEL and
            value['model_sha256'] == original()['model_sha256'] and
            value['build']['settings'] == original()['build']['settings'] and
            set(value['runs']) == set(PHASES), 'wrong comparison scope')
    require(value['source_sha256'][PROTOCOL] == PROTOCOL_SHA and value['source_sha256'][INPUT] == INPUT_SHA,
            'source protocol/input differs')
    old, new = files.runtime(original()['source_sha256']), files.runtime(value['source_sha256'])
    require({p for p in old.keys() | new.keys() if old.get(p) != new.get(p)} == RUNTIME_DELTA,
            'runtime changed outside the fixed host schedule')
    for phase in PHASES:
        require(set(value['runs'][phase]) == set(ARMS), 'missing arm')
        for arm in ARMS:
            require(set(value['runs'][phase][arm]) == set(PANEL), 'missing panel member')
            for key, run in value['runs'][phase][arm].items():
                require(run['args'] == arguments(key, arm, phase) and run['directory'] == f'{phase}/{arm}/{key}',
                        'changed native call')
                check_result(run['result'], key, arm, phase)
                require((run['frame'] is None) == (phase == 'plain'), 'wrong capture mode')
                if run['frame'] is not None:
                    require(run['frame']['path'] == run['directory'] + '/frames/end.raw', 'wrong frame path')
                    if arm == 'stopped' or phase == 'anchor':
                        require(run['frame']['sha256'] == original()['runs'][phase]['cursor'][key]['frame']['sha256'],
                                'frozen pixels differ')
                if phase in ('repeat', 'plain'):
                    endpoint = value['runs']['endpoint'][arm][key]
                    expected = dict(endpoint['result'])
                    if phase == 'plain':
                        expected['framebuffer_crc32'] = None
                    require(run['result'] == expected and (phase == 'plain' or
                            run['frame']['sha256'] == endpoint['frame']['sha256']), 'repeat/capture dependence')
    outcomes = {a: {k: analyze(value['runs']['endpoint'][a][k]['result']) for k in PANEL} for a in ARMS}
    require(value['outcomes'] == outcomes and value['decision'] == decision(outcomes) and
            value['recruits'] == {a: {k: waiting.recruits(value['runs']['endpoint'][a][k]['result'])
                                      for k in PANEL} for a in ARMS}, 'derived outcomes differ')
    require(value['receipt_sha256'] == prior.fingerprint({k: v for k, v in value.items() if k != 'receipt_sha256'}),
            'capture receipt differs')
    require(value['gallery']['rows'] == [[f'endpoint/{a}/{k}' for a in ARMS] for k in PANEL] and
            (value['gallery']['width'], value['gallery']['height'], value['gallery']['gap']) == (504, 1496, 8),
            'gallery panel differs')


def sources_now():
    return files.sources_now() | {p: digest(ROOT / p) for p in (PROTOCOL, INPUT)}


def call(out, value, phase, arm, key):
    directory = f'{phase}/{arm}/{key}'
    dest = out / directory
    (dest / 'frames').mkdir(parents=True)
    shutil.copy2(out / 'model.tgl', dest / 'model.tgl')
    args = arguments(key, arm, phase)
    write_json(dest / 'started.json', dict(args=args))
    process = subprocess.run([str(out / 'bin/garden-landing'), *args], cwd=dest,
                             capture_output=True, text=True, timeout=900)
    write_json(dest / 'process.json', dict(returncode=process.returncode, stderr=process.stderr, stdout=process.stdout))
    require(process.returncode == 0 and not process.stderr, 'native call failed; evidence retained')
    result = json.loads(process.stdout)
    write_json(dest / 'result.json', result)
    check_result(result, key, arm, phase)
    frame = None
    if phase != 'plain':
        path = dest / 'frames/end.raw'
        raw = files.frame_bytes(path, result)
        frame = dict(path=str(path.relative_to(out)), sha256=digest(path))
        write_png(path.with_suffix('.png'), 240, 240, rgb565be_to_rgb888(raw))
        if arm == 'stopped' or phase == 'anchor':
            require(frame['sha256'] == original()['runs'][phase]['cursor'][key]['frame']['sha256'], 'frozen pixels differ')
    else:
        require(result['framebuffer_crc32'] is None and not any((dest / 'frames').iterdir()), 'plain run wrote frame')
    if phase in ('repeat', 'plain'):
        endpoint = value['runs']['endpoint'][arm][key]
        expected = dict(endpoint['result'])
        if phase == 'plain':
            expected['framebuffer_crc32'] = None
        require(result == expected and (phase == 'plain' or frame['sha256'] == endpoint['frame']['sha256']),
                'repeat/capture dependence')
    run = dict(directory=directory, args=args, result=result, frame=frame)
    write_json(dest / 'run.json', run)
    print(f'{directory}: verified; living={result["living"]}, births={result["births"]}', flush=True)
    return arm, key, run


def groups(value):
    return [[dict(id=f'endpoint/{a}/{k}', framebuffer=value['runs']['endpoint'][a][k]['frame']['path'])
             for a in ARMS] for k in PANEL]


def collect(out, output, origin, build):
    require(not out.exists() and not output.exists() and not output.is_relative_to(out) and
            out.is_relative_to(ROOT / 'artifacts') and output.is_relative_to(ROOT / 'artifacts'), 'fresh paths required')
    require(digest(ROOT / PROTOCOL) == PROTOCOL_SHA and digest(origin / 'manifest.json') == ORIGIN_MANIFEST and
            digest(origin / 'model.tgl') == original()['model_sha256'], 'frozen protocol/origin differs')
    require(shutil.disk_usage(out.parent).free >= 1024 ** 3, 'need 1 GiB free')
    sources = sources_now()
    settings = prior.previous.sweep.late.settings_at(build / 'CMakeCache.txt', 'wide-cap')
    require(settings == original()['build']['settings'], 'build settings changed')
    old, new = files.runtime(original()['source_sha256']), files.runtime(sources)
    require({p for p in old.keys() | new.keys() if old.get(p) != new.get(p)} == RUNTIME_DELTA, 'unscoped runtime delta')
    out.mkdir()
    try:
        (out / 'bin').mkdir()
        snapshot_sources(out, sources)
        require(archived_sources(out / 'source.tar.gz') == sources, 'source snapshot differs')
        for path, target in ((origin / 'model.tgl', 'model.tgl'), (build / 'toy-factory-garden-landing', 'bin/garden-landing'),
                             (build / 'CMakeCache.txt', 'CMakeCache.txt'), (ROOT / PROTOCOL, 'protocol.md')):
            shutil.copy2(path, out / target)
        value = dict(rule=RULE, protocol_sha256=PROTOCOL_SHA, input_sha256=INPUT_SHA,
            origin_manifest_sha256=ORIGIN_MANIFEST, model_sha256=original()['model_sha256'], panel=PANEL,
            native_runs=48, training_runs=0, source_sha256=sources, runs={},
            build=dict(binary=digest(out / 'bin/garden-landing'), cache=digest(out / 'CMakeCache.txt'), settings=settings))
        write_json(out / 'started.json', value)
        for phase in PHASES:
            value['runs'][phase] = {a: {} for a in ARMS}
            calls = [(a, k) for k in PANEL for a in ARMS]
            with ThreadPoolExecutor(max_workers=2) as pool:
                for offset in range(0, len(calls), 2):
                    tasks = [pool.submit(call, out, value, phase, a, k) for a, k in calls[offset:offset + 2]]
                    for task in tasks:
                        a, k, run = task.result()
                        value['runs'][phase][a][k] = run
            write_json(out / (phase + '.json'), value['runs'][phase])
            print(f'{phase}: all twelve calls passed; no retries.', flush=True)
        value['outcomes'] = {a: {k: analyze(value['runs']['endpoint'][a][k]['result']) for k in PANEL} for a in ARMS}
        value['recruits'] = {a: {k: waiting.recruits(value['runs']['endpoint'][a][k]['result']) for k in PANEL} for a in ARMS}
        value['decision'] = decision(value['outcomes'])
        value['gallery'] = contact_sheet(out, groups(value))
        value['gallery']['sha256'] = digest(out / 'contact-sheet.png')
        require(sources_now() == sources and digest(out / 'bin/garden-landing') == value['build']['binary'] and
                digest(out / 'model.tgl') == value['model_sha256'] and
                digest(out / 'CMakeCache.txt') == value['build']['cache'], 'collection inputs changed')
        value['receipt_sha256'] = prior.fingerprint(value)
        check_capture(value)
        write_json(out / 'capture.json', value)
        write_json(out / 'manifest.json', dict(rule=RULE, artifacts={str(p.relative_to(out)): digest(p)
                   for p in sorted(out.rglob('*')) if p.is_file()}))
        verify_bundle(out, value)
        write_gzip(output, value)
    except Exception as error:
        write_json(out / 'failure.json', dict(error=str(error), automatic_retry=False))
        raise


def verify_bundle(root, value):
    root = root.resolve()
    check_capture(value)
    manifest = json.loads((root / 'manifest.json').read_text())
    require(manifest['rule'] == RULE and set(manifest['artifacts']) ==
            {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p != root / 'manifest.json'},
            'bundle inventory differs')
    for name, sha in manifest['artifacts'].items():
        require(digest(files.safe_artifact(root, name)) == sha, 'artifact changed: ' + name)
    require(json.loads((root / 'capture.json').read_text()) == value and
            archived_sources(root / 'source.tar.gz') == value['source_sha256'], 'capture/source archive differs')
    for name, sha in (('bin/garden-landing', value['build']['binary']), ('model.tgl', value['model_sha256']),
                      ('CMakeCache.txt', value['build']['cache']), ('protocol.md', PROTOCOL_SHA)):
        require(digest(root / name) == sha, 'frozen input differs')
    with tempfile.TemporaryDirectory(prefix='garden-recurring-images-') as temp:
        for phase in PHASES:
            require(json.loads((root / (phase + '.json')).read_text()) == value['runs'][phase], 'phase receipt differs')
            for arm in ARMS:
                for key, run in value['runs'][phase][arm].items():
                    dest = root / run['directory']
                    process = json.loads((dest / 'process.json').read_text())
                    require(process['returncode'] == 0 and not process['stderr'] and
                            json.loads(process['stdout']) == run['result'] and
                            json.loads((dest / 'started.json').read_text()) == dict(args=run['args']) and
                            json.loads((dest / 'run.json').read_text()) == run and
                            json.loads((dest / 'result.json').read_text()) == run['result'] and
                            digest(dest / 'model.tgl') == value['model_sha256'], 'call receipt differs')
                    if run['frame']:
                        path = files.safe_artifact(root, run['frame']['path'])
                        require(digest(path) == run['frame']['sha256'], 'frame hash differs')
                        raw = files.frame_bytes(path, run['result'])
                        png = Path(temp) / f'{phase}-{arm}-{key}.png'
                        write_png(png, 240, 240, rgb565be_to_rgb888(raw))
                        require(digest(png) == digest(path.with_suffix('.png')), 'PNG differs from raw frame')
                    else:
                        require(not any((dest / 'frames').iterdir()), 'plain run has frame artifacts')
        frames = groups(value)
        for row in frames:
            for frame in row:
                frame['framebuffer'] = str(root / frame['framebuffer'])
        rendered = contact_sheet(Path(temp), frames)
        rendered['sha256'] = digest(Path(temp) / 'contact-sheet.png')
        require(rendered == value['gallery'] and digest(root / 'contact-sheet.png') == rendered['sha256'], 'gallery differs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--collect', type=Path)
    mode.add_argument('--verify', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--origin', type=Path, default=ROOT / 'artifacts/garden-landing-seed-wait-v1')
    parser.add_argument('--build', type=Path, default=ROOT / 'build-host-patch-recurring')
    args = parser.parse_args()
    if args.collect:
        require(args.out is not None, '--collect needs --out')
        collect(args.collect.resolve(), args.out.resolve(), args.origin.resolve(), args.build.resolve())
    else:
        with gzip.open(args.verify, 'rt') as stream:
            value = json.load(stream)
        check_capture(value)
        if args.bundle:
            verify_bundle(args.bundle, value)
        print(json.dumps(value['decision'], indent=2))
        print('Recurring-winter comparison verified offline; no simulator executed.')


if __name__ == '__main__':
    main()
