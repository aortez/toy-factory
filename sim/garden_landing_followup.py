#!/usr/bin/env python3
"""Frozen day-288 follow-up, gated by exact day-256 replay identities."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
from functools import cache
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zlib

import garden_landing_vacancy_sequence as previous
from garden_descendants import index_records
from garden_experiments import compress, digest, snapshot_sources, source_files, write_json
from garden_gallery import contact_sheet
from garden_landing_energy_audit import archived_sources
from garden_landing_founders import write_gzip
from garden_landing_root_allocation_audit import fingerprint
from garden_resources import require

ROOT, DAY, STEP, BASE = previous.ROOT, previous.DAY, previous.STEP, previous.STOP
STOP = 288 * DAY
RULE = 'garden-landing-followup-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-followup-protocol.md'
PROTOCOL_SHA = 'f0093cf4b36d6b137b1ea51face77d9386ae15cb20befa8eeb9d7a90060d7d9b'
VACANCY = 'benchmarks/garden-seasons/landing-vacancy-sequence-results.json.gz'
VACANCY_SHA = 'f58fe1034af55a12349abfbd717ce69581bb4991824d1ae17ded88be36aff135'
KINDS = ('stand', 'adult', 'direction', 'reach')
PHASES = ('baseline', 'extension', 'repeat')
CLI = 'sim/garden_landing_cli.c'
SOURCES = ('sim/garden_landing_followup.py', 'sim/garden_descendants.py',
           'sim/garden_landing_population.py', 'sim/garden_landing_vacancy_sequence.py',
           'sim/garden_landing_late_dispersal.py', 'sim/garden_landing_founders.py',
           'sim/garden_experiments.py', 'sim/garden_resources.py')
# The captured collector predates only the CLI's pre-resolution symlink check.
# Its analysis is identical; keep the archived receipt instead of rewriting it.
CAPTURE_TOOL_SHA = 'fcc7cc05cf5cd39dc533e45d843220263cdff4b9504a96cc0c8d94404a276485'


@cache
def inputs():
    require(digest(ROOT / PROTOCOL) == PROTOCOL_SHA and digest(ROOT / VACANCY) == VACANCY_SHA,
            'follow-up protocol/input changed')
    original, panel = previous.source()
    with gzip.open(ROOT / VACANCY, 'rt') as stream:
        vacancy = json.load(stream)
    require(set(vacancy['analysis']) == set(panel), 'vacancy panel differs')
    return original, panel, vacancy


def repeated(world):
    return (world['order'], world['guard'], world['allocator']) == ('fixed', 'candidate', 'control')


def calls(phase):
    require(phase in PHASES, 'invalid phase')
    return [(key, w) for key, w in sorted(inputs()[1].items()) if phase != 'repeat' or repeated(w)]


def arguments(world, phase):
    require(phase in PHASES, 'invalid phase')
    original, args, i = world['run']['args'], [], 0
    stop = BASE if phase == 'baseline' else STOP
    while i < len(original):
        token = original[i]
        if token in ('--uptake-trace', '--uptake-window'):
            i += 2
            continue
        if token in ('--ticks', '--stand-stop', '--adult-stop'):
            args += [token, str(stop)]
            i += 2
        elif token in ('--stand-start', '--adult-start'):
            args += [token, str(BASE)]
            i += 2
        else:
            args.append(token)
            i += 1
    return args


def prefix_ledgers(result, cutoff=BASE):
    """Undo future fates/counts without masking immutable historical fields."""
    lives = [copy.deepcopy(p) for p in result['lineages'] if p['birth_tick'] <= cutoff]
    seeds = [copy.deepcopy(s) for s in result['seeds'] if s['birth_tick'] <= cutoff]
    purchases = Counter(s['parent'] for s in seeds)
    for p in lives:
        if p['death_tick'] is not None and p['death_tick'] > cutoff:
            p['death_tick'] = None
        p['seeds_created'] = p['late_seeds_created'] = purchases[p['id']]
    for s in seeds:
        if s['end_tick'] is not None and s['end_tick'] > cutoff:
            s.update(end_tick=None, child_id=None, outcome='pending')
    return lives, seeds


def validate_result(result, world, stop):
    old = world['run']['result']
    require(result['tick'] == stop and set(result) == set(old), 'wrong result horizon/schema')
    for key in ('schema_version', 'kind', 'run_version', 'rules', 'scenario', 'seed', 'model',
                'gardener', 'irrigation', 'seed_lifetime_ecology_ticks', 'ledger_start_tick',
                'warmup_samples', *(k for k in old if k.endswith('_probe'))):
        require(result[key] == old[key], 'changed environment/model/probe: ' + key)
    require(result['climate'] == previous.climate(int(result['seed'], 16), stop), 'wrong climate')
    index_records(result['lineages'], result['seeds'], 0, stop)
    require(len(result['lineages']) <= 4096 and len(result['seeds']) <= 65536 and
            sum(p['parent'] != 0 for p in result['lineages']) == result['births'] and
            sum(p['death_tick'] is not None for p in result['lineages']) == result['deaths'] and
            len(result['lineages']) - result['deaths'] == result['living'] and
            sum(s['outcome'] == 'pending' for s in result['seeds']) == result['seed_bank'],
            'ledger census/capacity differs')
    require(prefix_ledgers(result) == (old['lineages'], old['seeds']), 'day-256 event prefix changed')
    if stop == BASE:
        require(result == old, 'day-256 result changed')


def trace_rows(path, kind, start, stop, result):
    schemas = {'stand': 'landing-dawn-stand-trace-v1', 'adult': 'landing-adult-resources-v1',
               'direction': 'landing-directions-v1', 'reach': 'landing-reach-trace-v1'}
    header = dict(schema=schemas[kind])
    if kind != 'reach':
        header.update(start=start, stop=stop)
    if kind == 'stand':
        header.update(node_limit=32, budget_mode=2)
    footer = dict(complete=True, tick=stop)
    if kind in ('stand', 'direction'):
        footer['run_hash'] = result['run_hash']
    with gzip.open(path, 'rb') as stream:
        require(json.loads(stream.readline()) == header, 'wrong trace header')
        for tick in range(start, stop + STEP, STEP):
            raw = stream.readline()
            row = json.loads(raw)
            require(type(row.get('tick')) is int and row['tick'] == tick, 'trace gap/order changed')
            yield row, raw
        require(json.loads(stream.readline()) == footer and not stream.read(), 'incomplete/trailing trace')


def trace_receipt(path, kind, start, stop, result):
    prefix, boundary = hashlib.sha256(), None
    states, occupancy = [], Counter()
    lives = {p['id']: p for p in result['lineages']} if kind == 'stand' else {}
    for row, raw in trace_rows(path, kind, start, stop, result):
        tick = row['tick']
        if tick <= BASE:
            prefix.update(raw)
        if tick == BASE:
            boundary = fingerprint(row)
        if kind != 'stand':
            continue
        slots = row['plant_order']
        live = {i for i, p in lives.items() if p['birth_tick'] <= tick and
                (p['death_tick'] is None or p['death_tick'] > tick)}
        require(len(slots) == len(set(slots)) <= 8 and live <= set(slots) <= set(lives) and
                {b['id'] for b in row['bodies']} == live and
                row['climate'] == previous.climate(int(result['seed'], 16), tick), 'stand census differs')
        if not states or slots != states[-1][1]:
            states.append([tick, slots])
        if tick > BASE:
            occupancy[f'{len(live)}/{len(slots)}'] += 1
    return dict(prefix_sha256=prefix.hexdigest(), boundary_sha256=boundary,
                states=states, occupancy=dict(occupancy))


def cohort(result, identities):
    lives = {p['id']: p for p in result['lineages']}
    records = []
    for identity in identities:
        p = lives[identity]
        children = [c for c in lives.values() if c['parent'] == identity]
        purchases = [s for s in result['seeds'] if s['parent'] == identity]
        records.append(dict(life=p, survival={str(d): previous.late.population.survival(p, STOP, d)
                                              for d in (1, 16, 32)},
                            children=[c['id'] for c in children],
                            one_day_children=[c['id'] for c in children
                                              if previous.late.population.survival(c, STOP, 1) == 'confirmed'],
                            extension_purchases=sum(s['birth_tick'] > BASE for s in purchases),
                            extension_children=[c['id'] for c in children if c['birth_tick'] > BASE]))
    return records


def analyze(result, world, saved, receipt):
    old = world['run']['result']
    lives = {p['id']: p for p in result['lineages']}
    seeds = {(s['parent'], s['birth_tick']): s for s in result['seeds']}
    late = sorted(p['id'] for p in old['lineages'] if p['parent'] and BASE - 32 * DAY < p['birth_tick'] <= BASE)
    censored = sorted(r['life']['id'] for r in saved['replacements'] if r['survival']['32'] == 'censored')
    states = receipt['states']
    require(states and states[0][0] == BASE, 'missing boundary inventory')
    releases, last, seen, clock = [], states[0][1], set(states[0][1]), BASE
    for tick, slots in states[1:]:
        born = {i for i, p in lives.items() if p['birth_tick'] == tick}
        lost = set(last) - set(slots)
        require(type(tick) is int and clock < tick <= STOP and tick % STEP == 0 and
                len(slots) == len(set(slots)) <= 8 and slots != last and
                set(slots) - set(last) == born and not born & seen and
                all(lives[i]['death_tick'] is not None and lives[i]['death_tick'] < tick for i in lost) and
                [i for i in slots if i not in born] == [i for i in last if i not in lost],
                'invalid slot reclamation/birth')
        if lost:
            releases.append(dict(tick=tick, ids=sorted(lost)))
        seen.update(born)
        last, clock = slots, tick
    require(len(last) == result['plant_slots'] and
            {i for i, p in lives.items() if p['birth_tick'] > BASE} <= seen and
            sum(receipt['occupancy'].values()) == (STOP - BASE) // STEP, 'incomplete occupancy')
    expected, cursor = Counter(), 0
    for tick in range(BASE + STEP, STOP + STEP, STEP):
        if cursor + 1 < len(states) and states[cursor + 1][0] == tick:
            cursor += 1
        slots = states[cursor][1]
        live = {i for i, p in lives.items() if p['birth_tick'] <= tick and
                (p['death_tick'] is None or p['death_tick'] > tick)}
        require(live <= set(slots), 'missing live occupant')
        expected[f'{len(live)}/{len(slots)}'] += 1
    require(dict(expected) == receipt['occupancy'], 'occupancy does not reconcile with lifetimes')
    pending = [seeds[s['parent'], s['birth_tick']] for s in old['seeds'] if s['outcome'] == 'pending']
    return dict(late_births=cohort(result, late), censored_replacements=cohort(result, censored),
                pending_seeds=pending, new_births=[p for p in lives.values() if p['birth_tick'] > BASE],
                new_deaths=[p['id'] for p in lives.values() if p['death_tick'] is not None and p['death_tick'] > BASE],
                new_seeds=[s for s in result['seeds'] if s['birth_tick'] > BASE], releases=releases,
                occupancy=receipt['occupancy'], final=dict(living=result['living'], stored=result['plant_slots'],
                                                          nodes=result['nodes'], seeds=result['seed_bank']),
                ledger_usage=dict(lineages=len(lives), purchases=len(seeds)))


def artifact(root, item):
    relative = Path(item['path'])
    require(not relative.is_absolute() and '..' not in relative.parts, 'unsafe artifact path')
    path = (root / relative).resolve()
    require(path.is_relative_to(root.resolve()) and digest(path) == item['sha256'], 'artifact changed')
    return path


def original_receipt(root, world, kind):
    """Pinned full-file digest authenticates earlier rows; retain the boundary."""
    path = artifact(root, world['run']['traces'][kind])
    prefix, before, last = hashlib.sha256(), None, None
    with gzip.open(path, 'rb') as stream:
        stream.readline()  # Header is covered by the original full-file digest.
        for line in stream:
            if last is not None and kind == 'reach':
                prefix.update(last)
            before, last = last, line
    row, footer = json.loads(before), json.loads(last)
    expected = dict(complete=True, tick=BASE)
    if kind in ('stand', 'direction'):
        expected['run_hash'] = world['run']['result']['run_hash']
    require(row['tick'] == BASE and footer == expected, 'wrong original boundary/footer')
    return dict(boundary_sha256=fingerprint(row), prefix_sha256=prefix.hexdigest())


def check_run(run, world, phase):
    stop = BASE if phase == 'baseline' else STOP
    require(run['args'] == arguments(world, phase) and set(run['traces']) == set(KINDS), 'changed call')
    validate_result(run['result'], world, stop)
    for kind in KINDS:
        filename = run['args'][run['args'].index('--' + kind + '-trace') + 1]
        require(run['traces'][kind]['path'] == run['directory'] + '/' + filename + '.gz', 'wrong trace path')
    filename = run['args'][run['args'].index('--framebuffer') + 1]
    require(run['frame']['path'] == run['directory'] + '/' + filename, 'wrong frame path')
    if phase == 'baseline':
        require(run['frame']['sha256'] == world['run']['frame']['sha256'] and
                run['traces']['reach']['sha256'] == world['run']['traces']['reach']['sha256'],
                'saved pixels/full reach trace changed')


def check_value(value):
    original, panel, vacancy = inputs()
    expected_sources = {p: digest(ROOT / p) for p in SOURCES}
    recorded_sources = value['analysis_sources']
    require(set(recorded_sources) == set(SOURCES) and all(
        recorded_sources[p] == expected_sources[p] for p in SOURCES[1:]) and
        recorded_sources[SOURCES[0]] in (expected_sources[SOURCES[0]], CAPTURE_TOOL_SHA),
        'analysis implementation changed')
    require(value['rule'] == RULE and value['protocol_sha256'] == PROTOCOL_SHA and
            value['input_sha256'] == previous.INPUTS[previous.INPUT] and value['vacancy_sha256'] == VACANCY_SHA and
            value['native_runs'] == 68 and value['training_runs'] == 0 and
            value['model_sha256'] == original['model_sha256'], 'wrong provenance')
    require(set(value['builds']) == set(previous.late.ARMS) and set(value['runs']) == set(PHASES) and
            set(value['reference']) == set(panel), 'incomplete panel/builds')
    for arm, build in value['builds'].items():
        previous.late.check_settings(build['settings'], arm)
        require(build['settings'] == original['builds'][arm]['settings'], 'build options changed')
    for phase in PHASES:
        require(set(value['runs'][phase]) == {key for key, _ in calls(phase)}, 'wrong phase panel')
        for key, world in calls(phase):
            run = value['runs'][phase][key]
            require(run['directory'] == phase + '/' + key, 'wrong run identity')
            check_run(run, world, phase)
            for kind in KINDS:
                receipt, reference = run['receipts'][kind], value['reference'][key][kind]
                require(receipt['boundary_sha256'] == reference['boundary_sha256'], 'day-256 boundary changed')
                if kind == 'reach':
                    require(receipt['prefix_sha256'] == reference['prefix_sha256'], 'reach prefix changed')
            if phase == 'repeat':
                other = value['runs']['extension'][key]
                require(run['result'] == other['result'] and run['receipts'] == other['receipts'] and
                        run['frame']['sha256'] == other['frame']['sha256'] and all(
                            run['traces'][k]['sha256'] == other['traces'][k]['sha256'] for k in KINDS),
                        'exact repeat changed')
    require(set(value['analysis']) == set(panel), 'incomplete analysis')
    for key, world in panel.items():
        run = value['runs']['extension'][key]
        require(run['receipts']['stand']['states'][0] == [BASE, vacancy['rows'][key]['states'][-1][1]],
                'boundary inventory changed')
        require(value['analysis'][key] == analyze(run['result'], world, vacancy['analysis'][key],
                                                run['receipts']['stand']), 'derived outcomes changed')
    require(value['receipt_sha256'] == fingerprint({k: v for k, v in value.items() if k != 'receipt_sha256'}),
            'portable receipt changed')


def collect(out, original_bundle, jobs):
    require(not out.exists() and not out.is_symlink() and
            (out.is_relative_to(ROOT / 'artifacts') or not out.is_relative_to(ROOT)), 'fresh output required')
    require(1 <= jobs <= 4 and shutil.disk_usage(out.parent).free >= 20 * 1024 ** 3, 'need 20 GiB free and 1..4 workers')
    original, panel, vacancy = inputs()
    previous.check_bundle(original_bundle, original)
    sources = source_files()
    changed = [p for p in sources if p.startswith(('src/', 'sim/')) and p.endswith(('.c', '.h')) and
               sources[p] != original['source_sha256'].get(p)]
    require(changed == [CLI], 'unexpected simulation/observer source change: ' + repr(changed))
    out.mkdir(parents=True)
    (out / 'bin').mkdir()
    snapshot_sources(out, sources)
    shutil.copy2(ROOT / PROTOCOL, out / 'protocol.md')
    shutil.copy2(original_bundle / 'model.tgl', out / 'model.tgl')
    require(digest(out / 'model.tgl') == original['model_sha256'], 'wrong model bytes')
    value = dict(rule=RULE, protocol_sha256=PROTOCOL_SHA, input_sha256=previous.INPUTS[previous.INPUT],
                 vacancy_sha256=VACANCY_SHA, native_runs=68, training_runs=0, source_sha256=sources,
                 analysis_sources={p: sources[p] for p in SOURCES}, model_sha256=original['model_sha256'],
                 builds={}, reference={}, runs={}, analysis={})
    for arm, build in previous.late.BUILDS.items():
        binary, settings = ROOT / build / 'toy-factory-garden-landing', ROOT / build / 'CMakeCache.txt'
        value['builds'][arm] = dict(binary=digest(binary), cache=digest(settings),
                                   settings=previous.late.settings_at(settings, arm))
        require(value['builds'][arm]['settings'] == original['builds'][arm]['settings'], 'build options changed')
        shutil.copy2(binary, out / ('bin/' + arm))
        shutil.copy2(settings, out / (arm + '-CMakeCache.txt'))
    for key, world in panel.items():
        value['reference'][key] = {kind: original_receipt(original_bundle, world, kind) for kind in KINDS}
        print(key + ': original boundary verified', flush=True)

    def capture(call, phase):
        key, world = call
        args = arguments(world, phase)
        directory = out / phase / key
        directory.mkdir(parents=True)
        (directory / 'frames').mkdir()
        shutil.copy2(out / 'model.tgl', directory / 'model.tgl')
        result = previous.late.population.order.training.native(out / ('bin/' + world['arm']), directory, *args)
        stop = BASE if phase == 'baseline' else STOP
        validate_result(result, world, stop)
        write_json(directory / 'result.json', result)
        run = dict(directory=str(directory.relative_to(out)), args=args, result=result, traces={}, receipts={})
        for kind in KINDS:
            filename = args[args.index('--' + kind + '-trace') + 1]
            target = directory / (filename + '.gz')
            compress(directory / filename, target)
            run['traces'][kind] = dict(path=str(target.relative_to(out)), sha256=digest(target))
            run['receipts'][kind] = trace_receipt(target, kind, STEP if kind == 'reach' else BASE, stop, result)
            reference = value['reference'][key][kind]
            require(run['receipts'][kind]['boundary_sha256'] == reference['boundary_sha256'] and
                    (kind != 'reach' or run['receipts'][kind]['prefix_sha256'] == reference['prefix_sha256']),
                    'prefix/boundary changed: ' + key + '/' + kind)
        frame = directory / args[args.index('--framebuffer') + 1]
        raw = frame.read_bytes()
        require(len(raw) == 115200 and f'{zlib.crc32(raw):08x}' == result['framebuffer_crc32'], 'invalid pixels')
        run['frame'] = dict(path=str(frame.relative_to(out)), sha256=digest(frame))
        check_run(run, world, phase)
        write_json(directory / 'run.json', run)
        print(phase + '/' + key + ': verified', flush=True)
        return key, run

    # A complete baseline is a prerequisite, never interleave extended runs.
    for phase in PHASES:
        pool = ThreadPoolExecutor(max_workers=jobs)
        try:
            pending = [pool.submit(capture, call, phase) for call in calls(phase)]
            value['runs'][phase] = dict(future.result() for future in as_completed(pending))
        finally:
            # On failure retain in-flight evidence, but do not start queued worlds.
            pool.shutdown(wait=True, cancel_futures=True)
        write_json(out / (phase + '.json'), value['runs'][phase])
        print(phase + ': complete', flush=True)
    for key, world in panel.items():
        run = value['runs']['extension'][key]
        value['analysis'][key] = analyze(run['result'], world, vacancy['analysis'][key], run['receipts']['stand'])
    pairs = sorted({(w['order'], w['guard'], w['allocator']) for w in panel.values()})
    groups = [[dict(id=key, framebuffer=value['runs']['extension'][key]['frame']['path'])
               for arm in previous.late.ARMS for key, w in panel.items()
               if (w['order'], w['guard'], w['allocator']) == pair and w['arm'] == arm] for pair in pairs]
    value['gallery'] = contact_sheet(out, groups)
    value['gallery']['sha256'] = digest(out / 'contact-sheet.png')
    require(source_files() == sources and all(digest(ROOT / d / 'toy-factory-garden-landing') == value['builds'][a]['binary'] and
            digest(ROOT / d / 'CMakeCache.txt') == value['builds'][a]['cache'] for a, d in previous.late.BUILDS.items()),
            'source/build changed during capture')
    value['receipt_sha256'] = fingerprint(value)
    check_value(value)
    write_json(out / 'capture.json', value)
    write_json(out / 'manifest.json', dict(rule=RULE, artifacts={str(p.relative_to(out)): digest(p)
                                          for p in sorted(out.rglob('*')) if p.is_file()}))
    return value


def verify_bundle(root, value):
    manifest = json.loads((root / 'manifest.json').read_text())
    require(manifest['rule'] == RULE, 'wrong raw bundle')
    for path, sha in manifest['artifacts'].items():
        artifact(root, dict(path=path, sha256=sha))
    require(json.loads((root / 'capture.json').read_text()) == value and
            archived_sources(root / 'source.tar.gz') == value['source_sha256'] and
            digest(root / 'model.tgl') == value['model_sha256'] and
            digest(root / 'protocol.md') == PROTOCOL_SHA and
            digest(root / 'contact-sheet.png') == value['gallery']['sha256'], 'frozen provenance differs')
    for arm, build in value['builds'].items():
        require(digest(root / ('bin/' + arm)) == build['binary'] and
                digest(root / (arm + '-CMakeCache.txt')) == build['cache'], 'frozen build changed')
    for phase in PHASES:
        for run in value['runs'][phase].values():
            require(json.loads((root / run['directory'] / 'run.json').read_text()) == run and
                    json.loads((root / run['directory'] / 'result.json').read_text()) == run['result'] and
                    digest(root / run['directory'] / 'model.tgl') == value['model_sha256'], 'run archive differs')
            artifact(root, run['frame'])
            for kind, item in run['traces'].items():
                receipt = trace_receipt(artifact(root, item), kind, STEP if kind == 'reach' else BASE,
                                        BASE if phase == 'baseline' else STOP, run['result'])
                require(receipt == run['receipts'][kind], 'raw extraction differs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--collect', type=Path)
    mode.add_argument('--verify', type=Path)
    mode.add_argument('--export', type=Path, help='existing completed raw bundle; no native calls')
    parser.add_argument('--original', type=Path, default=ROOT / 'artifacts/garden-landing-late-dispersal-v1')
    parser.add_argument('--bundle', type=Path, help='also verify raw evidence offline')
    parser.add_argument('--out', type=Path, help='fresh portable result for collect/export')
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    require(bool(args.out) == bool(args.collect or args.export), '--out required only for collect/export')
    require(not args.bundle or args.verify, '--bundle requires --verify')
    if args.out:
        require(not args.out.exists() and not args.out.is_symlink(), 'fresh portable output required')
    if args.collect:
        require(not args.collect.exists() and not args.collect.is_symlink(), 'fresh output required')
        value = collect(args.collect.resolve(), args.original.resolve(), args.jobs)
    elif args.export:
        value = json.loads((args.export / 'capture.json').read_text())
        check_value(value)
        verify_bundle(args.export.resolve(), value)
    else:
        with gzip.open(args.verify, 'rt') as stream:
            value = json.load(stream)
        check_value(value)
        if args.bundle:
            verify_bundle(args.bundle.resolve(), value)
    if args.out:
        write_gzip(args.out, value)
    print('verified ' + RULE)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, OSError) as error:
        print('error: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
