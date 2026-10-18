#!/usr/bin/env python3
"""Prospective fresh-seed recurring/stopped comparison, with fixed day-608 follow-up."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import copy
from functools import cache
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import garden_landing_recurring_followup as previous
from garden_experiments import digest, snapshot_sources, write_json
from garden_gallery import contact_sheet, rgb565be_to_rgb888, write_png
from garden_landing_energy_audit import archived_sources
from garden_landing_founders import write_gzip
from garden_resources import require

prior, files = previous.prior, previous.files
ROOT, DAY, BASE = previous.ROOT, previous.DAY, 384 * previous.DAY
STOP, BIRTH_STOP = 608 * DAY, 576 * DAY
WINDOWS = [(d * DAY, (d + 64) * DAY) for d in (384, 448, 512)]
RULE = 'garden-landing-recurring-fresh-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-recurring-fresh-protocol.md'
PROTOCOL_SHA = '2b380d9fdd192ba8a9415e97775af3efd3f421e2a425cbf4e7507355348f99a9'
INPUT = 'benchmarks/garden-seasons/landing-recurring-followup-results.json.gz'
INPUT_SHA = '634d35468b6c2cc09603dd9c4b0af29e82cd95779446db333a7a2579e7c00884'
ORIGIN_MANIFEST = 'd2441d4e879150a119415dc4d2893134bb66211e5344edf8b300d2e3b353874e'
REFERENCE_BINARY = '7938c4b20054346404ca57ba587c046072ea01a89e919ee08136afb9354d1e97'
SEEDS = ('840f7cda', 'd6033864', 'a9802f60')
PANEL = {s + '-' + layout: dict(seed=s, scenario=layout)
         for s in SEEDS for layout in ('rainfed', 'rainfed-crowded')}
ARMS = ('stopped', 'recurring')
PHASES = ('legacy', 'anchor', 'middle', 'endpoint', 'repeat', 'plain')
PROBE = 'patch_renewal_probe'
SCHEDULE = dict(version=1, first_day=396, period_days=32, width=4, first_patch=1, scheduled_events=7)


@cache
def original():
    require(digest(ROOT / INPUT) == INPUT_SHA, 'source capture changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream:
        value = json.load(stream)
    previous.check_capture(value)
    require(value['build']['binary'] == REFERENCE_BINARY, 'reference binary identity differs')
    return value


def arms(phase):
    require(phase in PHASES, 'unknown phase')
    return ('reference',) if phase == 'legacy' else ARMS


def horizon(phase):
    return BASE if phase in ('legacy', 'anchor') else 512 * DAY if phase == 'middle' else STOP


def template():
    return original()['runs']['anchor']['3a7e45e6-rainfed']


def arguments(key, arm, phase):
    require(key in PANEL and arm in arms(phase), 'unknown native call')
    args = list(template()['args'])
    for flag in ('--patch-recurring', '--patch-recurring-followup'):
        i = args.index(flag)
        del args[i:i + 2]
    args[2], args[3] = PANEL[key]['scenario'], '0x' + PANEL[key]['seed']
    args[args.index('--ticks') + 1] = str(horizon(phase))
    if phase == 'plain':
        i = args.index('--framebuffer')
        del args[i:i + 2]
    return args if phase == 'legacy' else args + ['--patch-renewal', arm]


def tagged(base, enabled):
    h = 2166136261
    for byte in b'GPN1' + b''.join(x.to_bytes(4, 'little') for x in (int(base, 16), 396, 32, 4, 7, 1, int(enabled))):
        h = ((h ^ byte) * 16777619) & 0xffffffff
    return f'{h:08x}'


def schedule(tick, enabled):
    return [dict(tick=(396 + 32 * i) * DAY, first=((i + 1) % 7) * 4, last=((i + 1) % 7) * 4 + 3)
            for i in range(7) if enabled and (396 + 32 * i) * DAY <= tick]


def check_events(result, arm):
    enabled = arm == 'recurring'
    return previous.previous.check_events(result, name=PROBE, metadata=dict(SCHEDULE, enabled=enabled),
                                          expected_events=schedule(result['tick'], enabled))


def check_reference(result, key):
    old = template()['result']
    probes = [k for k in old if k.endswith('_probe') and k not in
              ('seed_cursor_probe', 'patch_sweep_probe', 'patch_recurring_probe', previous.PROBE)]
    for name in ('schema_version', 'run_version', 'rules', 'model', 'gardener', 'irrigation',
                 'seed_lifetime_ecology_ticks', 'ledger_start_tick', 'warmup_samples', *probes):
        require(result[name] == old[name], 'reference setting differs: ' + name)
    require(result['scenario'] == PANEL[key]['scenario'] and result['seed'] == PANEL[key]['seed'] and
            result['kind'] == 'landing-patch-sweep-replay', 'wrong reference world/mode')
    require(set(result) == set(old) - {'patch_recurring_probe', previous.PROBE}, 'reference schema differs')
    prior.check_result(result, key, 'cursor', 'endpoint', stop=BASE, reference=result)


def check_result(value, phase, arm, key, result):
    if phase == 'legacy':
        check_reference(result, key)
        return
    reference = value['runs']['legacy']['reference'][key]['result']
    require(set(result) == set(reference) | {PROBE} and result['tick'] == horizon(phase) and
            result['kind'] == 'landing-patch-renewal-replay' and
            result['patch_sweep_probe'] == reference['patch_sweep_probe'] and
            result['run_hash'] == tagged(prior.previous.sweep.tagged(result['placement_run_hash']), arm == 'recurring'),
            'new mode schema/history/identity differs')
    deaths = check_events(result, arm)
    normalized = copy.deepcopy(result)
    normalized.pop(PROBE)
    normalized['kind'] = reference['kind']
    normalized['run_hash'] = prior.previous.sweep.tagged(result['placement_run_hash'])
    # Only adapt already independently audited new death classifications for
    # the historical fifteen-event checker. The captured history is untouched.
    for p in normalized['lineages']:
        if p['id'] in deaths:
            p['environmental_death'] = False
    prior.check_result(normalized, key, 'cursor', 'endpoint', stop=horizon(phase), reference=reference)
    if phase == 'anchor':
        require(normalized == reference, 'frozen-executable anchor differs')
    if phase in ('endpoint', 'repeat', 'plain'):
        middle = value['runs']['middle'][arm][key]['result']
        require(prior.previous.sweep.prefix(result, middle['tick']) == (middle['lineages'], middle['seeds']) and
                [e for e in result[PROBE]['events'] if e['tick'] <= middle['tick']] == middle[PROBE]['events'],
                'day-512 history differs')


def analyze(result):
    require(result['tick'] == STOP, 'analysis needs day 608')
    plants, seeds = result['lineages'], result['seeds']
    prior.index_records(plants, seeds, 0, STOP)
    spans = [prior.span(p) for p in plants]
    blocks = [prior.exposure(spans, d * DAY, (d + 16) * DAY) for d in range(384, 608, 16)]
    minimum, live = min(b['minimum'] for b in blocks), sum(prior.at(p, STOP) for p in plants)
    viability = dict(blocks=blocks, minimum=minimum, endpoint=live,
        empty_intervals=prior.absent(spans, BASE, STOP),
        passes=minimum > 0 and live >= 4 and all(b['plant_ticks'] >= 4 * b['ticks'] for b in blocks))
    born = [p for p in plants if BASE < p['birth_tick'] <= BIRTH_STOP]
    windows = [dict(start_exclusive=a, stop_inclusive=b,
        **prior.cohort([p for p in born if a < p['birth_tick'] <= b], STOP)) for a, b in WINDOWS]
    depths, pairs = {}, []
    for p in born:
        if prior.age_status(p, 32, STOP) == 'confirmed':
            depths[p['id']] = 1 + depths.get(p['parent'], 0)
            if p['parent'] in depths:
                pairs.append([p['parent'], p['id']])
    renewal = dict(primary=prior.cohort(born, STOP), windows=windows, pairs=pairs,
        deepest_chain=max(depths.values(), default=0), late=prior.cohort([p for p in plants if p['birth_tick'] > BIRTH_STOP], STOP),
        passes=bool(pairs) and all(w['ages']['32']['confirmed'] for w in windows))
    deaths = [p for p in plants if p['death_tick'] is not None and BASE < p['death_tick'] <= STOP]
    require(sum(prior.at(p, BASE) for p in plants) + sum(p['birth_tick'] > BASE for p in plants) - len(deaths) == live,
            'population conservation failed')
    mortality = {cause: dict(ids=[p['id'] for p in deaths if p['environmental_death'] == imposed],
        by_age_32=[p['id'] for p in deaths if p['environmental_death'] == imposed and
                   p['death_tick'] - p['birth_tick'] <= 32 * DAY])
        for cause, imposed in (('imposed', True), ('natural', False))}
    diversity = prior.diversity(plants, seeds, STOP)
    families = prior.ancestry(plants)
    for axis, rows in diversity.items():
        def group(p):
            return p['species'] if axis == 'species' else families[p['id']]
        rows['continuous_retained'] = [g for g in rows['baseline'] if not rows['absence_intervals'][str(g)]]
        rows['no_plants_or_seeds'] = {str(g): prior.absent(
            [prior.span(p) for p in plants if group(p) == g] +
            [prior.seed_span(s) for s in seeds if (s['species'] if axis == 'species' else families[s['parent']]) == g],
            BASE, STOP) for g in rows['baseline']}
    bought = [s for s in seeds if s['birth_tick'] > BASE]
    fates = Counter(s['outcome'] for s in bought)
    return dict(viability=viability, renewal=renewal, mortality=mortality, diversity=diversity,
        purchases=len(bought), distinct_buyers=len({s['parent'] for s in bought}),
        seed_fates={s: fates[s] for s in ('germinated', 'expired', 'pending')})


def decision(outcomes):
    summary = {}
    for arm in ARMS:
        rows = outcomes[arm]
        viable = [k for k in PANEL if rows[k]['viability']['passes']]
        renewing = [k for k in PANEL if rows[k]['renewal']['passes']]
        summary[arm] = dict(viable=viable, renewing=renewing,
            broad_signal=len(viable) == 6 and len(renewing) >= 4 and
            {PANEL[k]['seed'] for k in renewing} == set(SEEDS) and
            {PANEL[k]['scenario'] for k in renewing} == {'rainfed', 'rainfed-crowded'})
    pairs = {}
    for k in PANEL:
        a, b = outcomes['stopped'][k], outcomes['recurring'][k]
        pairs[k] = dict(survivor_delta=len(b['renewal']['primary']['ages']['32']['confirmed']) -
                       len(a['renewal']['primary']['ages']['32']['confirmed']),
            additional_losses={axis: sorted(set(a['diversity'][axis]['continuous_retained']) -
                                           set(b['diversity'][axis]['continuous_retained'])) for axis in ('species', 'family')})
    return dict(arms=summary, pairs=pairs,
        diversity_tradeoff=any(any(p['additional_losses'].values()) for p in pairs.values()),
        recurring_renewal_advantage=summary['recurring']['broad_signal'] and
        len(summary['recurring']['renewing']) > len(summary['stopped']['renewing']))


def sources_now():
    return previous.sources_now() | {p: digest(ROOT / p) for p in (PROTOCOL, INPUT)}


def check_sources(sources):
    old, new = files.runtime(original()['source_sha256']), files.runtime(sources)
    require({p for p in old.keys() | new.keys() if old.get(p) != new.get(p)} == previous.previous.RUNTIME_DELTA,
            'runtime changed outside host CLI/schedule')


def groups(value):
    return [[dict(id=f'{phase}/{a}/{k}', framebuffer=value['runs'][phase][a][k]['frame']['path'])
             for phase in ('middle', 'endpoint') for a in ARMS] for k in PANEL]


def check_capture(value):
    require(value['rule'] == RULE and value['protocol_sha256'] == PROTOCOL_SHA and digest(ROOT / PROTOCOL) == PROTOCOL_SHA and
            value['input_sha256'] == INPUT_SHA and value['origin_manifest_sha256'] == ORIGIN_MANIFEST and
            value['native_runs'] == 66 and value['training_runs'] == 0 and value['panel'] == PANEL and
            value['model_sha256'] == original()['model_sha256'] and value['reference_binary_sha256'] == REFERENCE_BINARY and
            value['build']['settings'] == original()['build']['settings'] and set(value['runs']) == set(PHASES) and
            value['closed_decision'] == original()['closed_decision'], 'wrong fresh-panel scope')
    require(value['source_sha256'][PROTOCOL] == PROTOCOL_SHA and value['source_sha256'][INPUT] == INPUT_SHA,
            'source protocol/input differs')
    check_sources(value['source_sha256'])
    for phase in PHASES:
        require(set(value['runs'][phase]) == set(arms(phase)), 'missing arm')
        for arm in arms(phase):
            require(set(value['runs'][phase][arm]) == set(PANEL), 'missing panel member')
            for key, run in value['runs'][phase][arm].items():
                require(run['args'] == arguments(key, arm, phase) and run['directory'] == f'{phase}/{arm}/{key}',
                        'changed native call')
                check_result(value, phase, arm, key, run['result'])
                require((run['frame'] is None) == (phase == 'plain'), 'wrong capture mode')
                if run['frame'] is not None:
                    require(run['frame']['path'] == run['directory'] + '/frames/end.raw', 'wrong frame path')
                    if phase == 'anchor':
                        require(run['frame']['sha256'] == value['runs']['legacy']['reference'][key]['frame']['sha256'],
                                'anchor pixels differ')
                if phase in ('repeat', 'plain'):
                    previous.check_repeat(run, value['runs']['endpoint'][arm][key], phase)
    outcomes = {a: {k: analyze(value['runs']['endpoint'][a][k]['result']) for k in PANEL} for a in ARMS}
    require(value['outcomes'] == outcomes and value['decision'] == decision(outcomes), 'derived outcomes differ')
    require(value['receipt_sha256'] == prior.fingerprint({k: v for k, v in value.items() if k != 'receipt_sha256'}),
            'capture receipt differs')
    require(value['gallery']['rows'] == [[f'{p}/{a}/{k}' for p in ('middle', 'endpoint') for a in ARMS] for k in PANEL] and
            (value['gallery']['width'], value['gallery']['height'], value['gallery']['gap']) == (1000, 1496, 8),
            'gallery panel differs')


def call(out, value, phase, arm, key):
    directory = f'{phase}/{arm}/{key}'
    dest = out / directory
    (dest / 'frames').mkdir(parents=True)
    shutil.copy2(out / 'model.tgl', dest / 'model.tgl')
    args = arguments(key, arm, phase)
    binary = 'bin/garden-reference' if phase == 'legacy' else 'bin/garden-landing'
    write_json(dest / 'started.json', dict(args=args, binary=binary))
    process = subprocess.run([str(out / binary), *args], cwd=dest,
                             capture_output=True, text=True, timeout=900)
    write_json(dest / 'process.json', dict(returncode=process.returncode, stderr=process.stderr, stdout=process.stdout))
    require(process.returncode == 0 and not process.stderr, 'native call failed; evidence retained')
    result = json.loads(process.stdout)
    write_json(dest / 'result.json', result)
    check_result(value, phase, arm, key, result)
    frame = None
    if phase != 'plain':
        path = dest / 'frames/end.raw'
        raw = files.frame_bytes(path, result)
        frame = dict(path=str(path.relative_to(out)), sha256=digest(path))
        write_png(path.with_suffix('.png'), 240, 240, rgb565be_to_rgb888(raw))
        if phase == 'anchor':
            require(frame['sha256'] == value['runs']['legacy']['reference'][key]['frame']['sha256'], 'anchor pixels differ')
    else:
        require(result['framebuffer_crc32'] is None and not any((dest / 'frames').iterdir()), 'plain run wrote frame')
    run = dict(directory=directory, args=args, result=result, frame=frame)
    if phase in ('repeat', 'plain'):
        previous.check_repeat(run, value['runs']['endpoint'][arm][key], phase)
    write_json(dest / 'run.json', run)
    print(f'{directory}: verified; living={result["living"]}, births={result["births"]}', flush=True)
    return arm, key, run


def collect(out, output, origin, build):
    require(not out.exists() and not output.exists() and not output.is_relative_to(out) and
            out.is_relative_to(ROOT / 'artifacts') and output.is_relative_to(ROOT / 'artifacts'), 'fresh paths required')
    require(digest(ROOT / PROTOCOL) == PROTOCOL_SHA and digest(origin / 'manifest.json') == ORIGIN_MANIFEST and
            digest(origin / 'model.tgl') == original()['model_sha256'] and
            digest(origin / 'bin/garden-landing') == REFERENCE_BINARY, 'frozen protocol/origin differs')
    require(shutil.disk_usage(out.parent).free >= 1024 ** 3, 'need 1 GiB free')
    sources = sources_now()
    check_sources(sources)
    settings = prior.previous.sweep.late.settings_at(build / 'CMakeCache.txt', 'wide-cap')
    require(settings == original()['build']['settings'], 'build settings changed')
    out.mkdir()
    try:
        (out / 'bin').mkdir()
        snapshot_sources(out, sources)
        require(archived_sources(out / 'source.tar.gz') == sources, 'source snapshot differs')
        for path, target in ((origin / 'model.tgl', 'model.tgl'), (build / 'toy-factory-garden-landing', 'bin/garden-landing'),
                             (origin / 'bin/garden-landing', 'bin/garden-reference'),
                             (build / 'CMakeCache.txt', 'CMakeCache.txt'), (ROOT / PROTOCOL, 'protocol.md')):
            shutil.copy2(path, out / target)
        value = dict(rule=RULE, protocol_sha256=PROTOCOL_SHA, input_sha256=INPUT_SHA,
            origin_manifest_sha256=ORIGIN_MANIFEST, model_sha256=original()['model_sha256'], panel=PANEL,
            native_runs=66, training_runs=0, source_sha256=sources, runs={},
            reference_binary_sha256=REFERENCE_BINARY, closed_decision=original()['closed_decision'],
            build=dict(binary=digest(out / 'bin/garden-landing'), cache=digest(out / 'CMakeCache.txt'), settings=settings))
        write_json(out / 'started.json', value)
        for phase in PHASES:
            value['runs'][phase] = {a: {} for a in arms(phase)}
            calls = [(a, k) for k in PANEL for a in arms(phase)]
            with ThreadPoolExecutor(max_workers=2) as pool:
                for offset in range(0, len(calls), 2):
                    tasks = [pool.submit(call, out, value, phase, a, k) for a, k in calls[offset:offset + 2]]
                    for task in tasks:
                        a, k, run = task.result()
                        value['runs'][phase][a][k] = run
            write_json(out / (phase + '.json'), value['runs'][phase])
            print(f'{phase}: all {len(calls)} calls passed; no retries.', flush=True)
        value['outcomes'] = {a: {k: analyze(value['runs']['endpoint'][a][k]['result']) for k in PANEL} for a in ARMS}
        value['decision'] = decision(value['outcomes'])
        value['gallery'] = contact_sheet(out, groups(value))
        value['gallery']['sha256'] = digest(out / 'contact-sheet.png')
        require(sources_now() == sources and digest(out / 'bin/garden-landing') == value['build']['binary'] and
                digest(out / 'bin/garden-reference') == REFERENCE_BINARY and
                digest(out / 'model.tgl') == value['model_sha256'] and
                digest(out / 'CMakeCache.txt') == value['build']['cache'] and
                digest(origin / 'manifest.json') == ORIGIN_MANIFEST and digest(ROOT / INPUT) == INPUT_SHA,
                'collection inputs changed')
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
    for name, sha in (('bin/garden-landing', value['build']['binary']), ('bin/garden-reference', REFERENCE_BINARY),
                      ('model.tgl', value['model_sha256']), ('CMakeCache.txt', value['build']['cache']), ('protocol.md', PROTOCOL_SHA)):
        require(digest(root / name) == sha, 'frozen input differs')
    with tempfile.TemporaryDirectory(prefix='garden-fresh-images-') as temp:
        for phase in PHASES:
            require(json.loads((root / (phase + '.json')).read_text()) == value['runs'][phase], 'phase receipt differs')
            for arm in arms(phase):
                for key, run in value['runs'][phase][arm].items():
                    dest = root / run['directory']
                    process = json.loads((dest / 'process.json').read_text())
                    binary = 'bin/garden-reference' if phase == 'legacy' else 'bin/garden-landing'
                    require(process['returncode'] == 0 and not process['stderr'] and
                            json.loads(process['stdout']) == run['result'] and
                            json.loads((dest / 'started.json').read_text()) == dict(args=run['args'], binary=binary) and
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
    parser.add_argument('--origin', type=Path, default=ROOT / 'artifacts/garden-landing-recurring-followup-v1')
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
        print('Fresh recurring comparison verified offline; no simulator executed.')


if __name__ == '__main__':
    main()
