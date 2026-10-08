#!/usr/bin/env python3
"""Frozen waiting-time comparison, with offline validation and unchanged renewal metrics."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import copy
from functools import cache
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import garden_landing_recruit_seeds as prior_audit
import garden_landing_competitive_renewal_capture as files
from garden_experiments import digest, snapshot_sources, write_json
from garden_gallery import contact_sheet, rgb565be_to_rgb888, write_png
from garden_landing_energy_audit import archived_sources
from garden_landing_founders import write_gzip
from garden_resources import require

prior = prior_audit.previous
ROOT, DAY, BASE, STOP, PANEL = prior.ROOT, prior.DAY, prior.BASE, prior.STOP, prior.PANEL
RULE = 'garden-landing-seed-wait-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-seed-wait-protocol.md'
PROTOCOL_SHA = '23c3d196054bcb1ecdc7a81d7a53f7968c3417dfcb9497e641b3b595cd8b08e1'
ORIGIN_MANIFEST = '4402ad5be09ed19542d303a83015e81e376cd1b9a7efd40350eea11ac319e205'
ARMS, PHASES = ('cursor', 'wait'), ('anchor', 'endpoint', 'repeat', 'plain')
RUNTIME_DELTA = {'src/garden_agent.h', 'src/garden_world.c', 'sim/garden_landing_growth.h',
    'sim/garden_landing_growth.c', 'sim/garden_landing_run.c', 'sim/garden_landing_run_internal.h',
    'sim/garden_landing_cli.c', 'sim/garden_landing_seed_wait.c', 'sim/garden_landing_seed_wait.h'}


@cache
def original():
    return prior_audit.load_input()


def arguments(key, arm, phase):
    require(key in PANEL and arm in ARMS and phase in PHASES, 'unknown call')
    args = list(original()['runs'][phase]['cursor'][key]['args'])
    return args + (['--seed-wait-after', str(BASE)] if arm == 'wait' else [])


def tagged(base, entries, after=BASE):
    words = [int(base, 16), after, len(entries), *(x for e in entries for x in e)]
    h = 2166136261
    for byte in b'GSW1' + b''.join(x.to_bytes(4, 'little') for x in words):
        h = ((h ^ byte) * 16777619) & 0xffffffff
    return f'{h:08x}'


def check_entries(entries, result, tick, count=None):
    require(type(entries) is list and len(entries) <= 8 and
            all(type(e) is list and len(e) == 2 and all(type(n) is int for n in e) for e in entries),
            'invalid waiting entries')
    ids = [e[0] for e in entries]
    lives = {p['id']: p for p in result['lineages']}
    require(ids == sorted(set(ids)) and all(i in lives and lives[i]['birth_tick'] <= tick for i in ids) and
            {i for i, p in lives.items() if prior.at(p, tick)} <= set(ids) and
            (count is None or len(ids) == count), 'waiting inventory differs')
    for i, stamp in entries:
        p = lives[i]
        purchases = [s['birth_tick'] for s in result['seeds'] if s['parent'] == i and s['birth_tick'] <= tick]
        require(stamp == (purchases[-1] if purchases else p['birth_tick']), 'waiting purchase clock differs')
        require(p['death_tick'] is None or p['death_tick'] > tick - 255 * 15,
                'waiting history retained beyond possible corpse lifetime')


def check_wait_probe(result, reference, after=BASE):
    probe = result['seed_wait_probe']
    require(set(probe) == {'version', 'after', 'entries', 'events'} and
            probe['version'] == 1 and probe['after'] == after, 'wrong waiting policy')
    check_entries(probe['entries'], result, result['tick'], result['plant_slots'])
    old_events = reference.get('patch_sweep_probe', {}).get('events', [])
    require(len(probe['events']) == len(old_events), 'missing sweep waiting receipts')
    expected = copy.deepcopy(old_events)
    for receipt, event in zip(probe['events'], expected, strict=True):
        require(type(receipt) is list and len(receipt) == 2 and receipt[0] == event['tick'],
                'waiting sweep clock differs')
        check_entries(receipt[1], result, event['tick'])
        for field in ('before_run_hash', 'after_run_hash'):
            event[field] = tagged(event[field], receipt[1], after)
    require(result.get('patch_sweep_probe', {}).get('events', []) == expected,
            'sweep world or waiting identity changed')


def check_result(result, key, arm, phase):
    reference = original()['runs'][phase]['cursor'][key]['result']
    if arm == 'cursor':
        require(result == reference, 'cursor control differs from frozen result')
        return
    check_wait_probe(result, reference)
    normalized = copy.deepcopy(result)
    probe = normalized.pop('seed_wait_probe')
    normalized['patch_sweep_probe'] = copy.deepcopy(reference['patch_sweep_probe'])
    if phase == 'anchor':
        require(result['placement_run_hash'] == tagged(reference['placement_run_hash'], probe['entries']) and
                result['run_hash'] == prior.previous.sweep.tagged(result['placement_run_hash']),
                'waiting anchor hash differs')
        normalized['placement_run_hash'] = reference['placement_run_hash']
        normalized['run_hash'] = reference['run_hash']
        require(normalized == reference, 'waiting anchor changed the common history')
    else:
        # Only declared waiting metadata and pre-onset event identity wrappers
        # differ. All original population, ledger, resource-setting and prefix
        # checks still apply; the cursor receipt tracks actual buyers in both arms.
        prior.check_result(normalized, key, 'cursor', phase)


def recruits(result):
    plants = [p for p in result['lineages'] if BASE < p['birth_tick'] <= prior.BIRTH_STOP]
    return [dict(life=p, purchases=[s for s in result['seeds'] if s['parent'] == p['id']],
                 children=[q['id'] for q in result['lineages'] if q['parent'] == p['id']]) for p in plants]


def decision(outcomes):
    result = prior.decision({'fixed': outcomes['cursor'], 'cursor': outcomes['wait']})
    return dict(arms=dict(cursor=result['arms']['fixed'], wait=result['arms']['cursor']),
        pairs=result['pairs'], diversity_tradeoff=result['diversity_tradeoff'],
        waiting_renewal_advantage=result['cursor_renewal_advantage'])


def check_capture(value):
    require(value['rule'] == RULE and value['protocol_sha256'] == PROTOCOL_SHA and
            digest(ROOT / PROTOCOL) == PROTOCOL_SHA and value['input_sha256'] == prior_audit.INPUT_SHA and
            value['model_sha256'] == original()['model_sha256'] and value['panel'] == PANEL and
            value['origin_manifest_sha256'] == ORIGIN_MANIFEST and value['native_runs'] == 48 and
            value['training_runs'] == 0 and value['build']['settings'] == original()['build']['settings'] and
            set(value['runs']) == set(PHASES), 'wrong waiting comparison scope')
    require(value['source_sha256'][PROTOCOL] == PROTOCOL_SHA and
            value['source_sha256'][prior_audit.INPUT] == prior_audit.INPUT_SHA,
            'snapshot protocol/input differs')
    old, new = files.runtime(original()['source_sha256']), files.runtime(value['source_sha256'])
    require({p for p in old.keys() | new.keys() if old.get(p) != new.get(p)} == RUNTIME_DELTA,
            'runtime changes outside the declared ordering hook')
    for phase in PHASES:
        require(set(value['runs'][phase]) == set(ARMS), 'missing comparison arm')
        for arm in ARMS:
            require(set(value['runs'][phase][arm]) == set(PANEL), 'missing panel member')
            for key, run in value['runs'][phase][arm].items():
                require(run['args'] == arguments(key, arm, phase) and
                        run['directory'] == f'{phase}/{arm}/{key}', 'changed native call')
                check_result(run['result'], key, arm, phase)
                require((run['frame'] is None) == (phase == 'plain'), 'wrong framebuffer mode')
                if run['frame'] is not None:
                    require(run['frame']['path'] == run['directory'] + '/frames/end.raw', 'wrong frame path')
                    if arm == 'cursor' or phase == 'anchor':
                        require(run['frame']['sha256'] == original()['runs'][phase]['cursor'][key]['frame']['sha256'],
                                'frozen pixels changed')
                if phase in ('repeat', 'plain'):
                    endpoint = value['runs']['endpoint'][arm][key]
                    expected = dict(endpoint['result'])
                    if phase == 'plain':
                        expected['framebuffer_crc32'] = None
                    require(run['result'] == expected and (phase == 'plain' or
                            run['frame']['sha256'] == endpoint['frame']['sha256']), 'repeat/capture dependence')
    outcomes = {a: {k: prior.analyze(value['runs']['endpoint'][a][k]['result']) for k in PANEL} for a in ARMS}
    require(value['outcomes'] == outcomes and value['decision'] == decision(outcomes) and
            value['recruits'] == {a: {k: recruits(value['runs']['endpoint'][a][k]['result'])
                                      for k in PANEL} for a in ARMS}, 'derived outcomes differ')
    require(value['receipt_sha256'] == prior.fingerprint({k: v for k, v in value.items() if k != 'receipt_sha256'}),
            'capture receipt changed')
    require(value['gallery']['rows'] == [[f'endpoint/{a}/{k}' for a in ARMS] for k in PANEL] and
            (value['gallery']['width'], value['gallery']['height'], value['gallery']['gap']) == (504, 1496, 8),
            'gallery panel differs')


def sources_now():
    return files.sources_now() | {p: digest(ROOT / p) for p in (PROTOCOL, prior_audit.INPUT)}


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
        if arm == 'cursor' or phase == 'anchor':
            require(frame['sha256'] == original()['runs'][phase]['cursor'][key]['frame']['sha256'],
                    'frozen pixels changed')
    else:
        require(result['framebuffer_crc32'] is None and not any((dest / 'frames').iterdir()), 'plain run wrote frame')
    if phase in ('repeat', 'plain'):
        prior_run = value['runs']['endpoint'][arm][key]
        expected = dict(prior_run['result'])
        if phase == 'plain':
            expected['framebuffer_crc32'] = None
        require(result == expected and (phase == 'plain' or frame['sha256'] == prior_run['frame']['sha256']),
                'repeat/capture dependence')
    run = dict(directory=directory, args=args, result=result, frame=frame)
    write_json(dest / 'run.json', run)
    print(f'{directory}: verified; living={result["living"]}, births={result["births"]}', flush=True)
    return arm, key, run


def groups(value):
    return [[dict(id=f'endpoint/{arm}/{key}', framebuffer=value['runs']['endpoint'][arm][key]['frame']['path'])
             for arm in ARMS] for key in PANEL]


def collect(out, output, origin, build):
    require(not out.exists() and not output.exists() and not output.is_relative_to(out) and
            out.is_relative_to(ROOT / 'artifacts') and output.is_relative_to(ROOT / 'artifacts'), 'fresh paths required')
    require(digest(ROOT / PROTOCOL) == PROTOCOL_SHA and digest(origin / 'manifest.json') == ORIGIN_MANIFEST and
            digest(origin / 'model.tgl') == original()['model_sha256'], 'frozen protocol/origin changed')
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
        value = dict(rule=RULE, protocol_sha256=PROTOCOL_SHA, input_sha256=prior_audit.INPUT_SHA,
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
        value['outcomes'] = {a: {k: prior.analyze(value['runs']['endpoint'][a][k]['result']) for k in PANEL} for a in ARMS}
        value['recruits'] = {a: {k: recruits(value['runs']['endpoint'][a][k]['result']) for k in PANEL} for a in ARMS}
        value['decision'] = decision(value['outcomes'])
        value['gallery'] = contact_sheet(out, groups(value))
        value['gallery']['sha256'] = digest(out / 'contact-sheet.png')
        require(sources_now() == sources and digest(out / 'bin/garden-landing') == value['build']['binary'] and
                digest(out / 'model.tgl') == value['model_sha256'] and
                digest(out / 'CMakeCache.txt') == value['build']['cache'], 'collection inputs changed')
        value['receipt_sha256'] = prior.fingerprint(value)
        check_capture(value)
        write_json(out / 'capture.json', value)
        write_gzip(output, value)
        write_json(out / 'manifest.json', dict(rule=RULE, artifacts={str(p.relative_to(out)): digest(p)
                   for p in sorted(out.rglob('*')) if p.is_file()}))
    except Exception as error:
        write_json(out / 'failure.json', dict(error=str(error), automatic_retry=False))
        raise


def verify_bundle(root, value):
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
    for phase in PHASES:
        require(json.loads((root / (phase + '.json')).read_text()) == value['runs'][phase], 'phase receipt differs')
        for arm in ARMS:
            for run in value['runs'][phase][arm].values():
                dest = root / run['directory']
                process = json.loads((dest / 'process.json').read_text())
                require(process['returncode'] == 0 and not process['stderr'] and
                        json.loads(process['stdout']) == run['result'] and
                        json.loads((dest / 'run.json').read_text()) == run and
                        json.loads((dest / 'result.json').read_text()) == run['result'] and
                        digest(dest / 'model.tgl') == value['model_sha256'], 'call receipt differs')
                if run['frame']:
                    path = files.safe_artifact(root, run['frame']['path'])
                    require(digest(path) == run['frame']['sha256'], 'frame hash differs')
                    files.frame_bytes(path, run['result'])
    with tempfile.TemporaryDirectory(prefix='garden-wait-gallery-') as temp:
        frames = groups(value)
        for row in frames:
            for frame in row:
                frame['framebuffer'] = str(root / frame['framebuffer'])
        rendered = contact_sheet(Path(temp), frames)
        rendered['sha256'] = digest(Path(temp) / 'contact-sheet.png')
        require(rendered == value['gallery'] and digest(root / 'contact-sheet.png') == rendered['sha256'],
                'gallery differs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--collect', type=Path)
    mode.add_argument('--verify', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--origin', type=Path, default=ROOT / 'artifacts/garden-landing-competitive-renewal-v1')
    parser.add_argument('--build', type=Path, default=ROOT / 'build-host-seed-wait')
    args = parser.parse_args()
    if args.collect:
        require(args.out is not None, '--collect needs --out')
        collect(args.collect.resolve(), args.out.resolve(), args.origin.resolve(), args.build.resolve())
    else:
        with gzip.open(args.verify, 'rt') as stream:
            value = json.load(stream)
        check_capture(value)
        if args.bundle:
            verify_bundle(args.bundle.resolve(), value)
        print(json.dumps(value['decision'], indent=2))
        print('Waiting-time comparison verified offline; no simulator executed.')


if __name__ == '__main__':
    main()
