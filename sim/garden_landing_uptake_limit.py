#!/usr/bin/env python3
"""Frozen late uptake cap experiment, paired with the saved wicking panel."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from functools import cache
import gzip
import hashlib
import json
from multiprocessing import get_context
from pathlib import Path
import shutil
import sys
import zlib

import garden_landing_wicking as previous
from garden_experiments import compress, digest, snapshot_sources, source_files, write_json
from garden_gallery import contact_sheet
from garden_landing_energy_audit import archived_sources
from garden_resources import require

ROOT, STEP, STOP, AFTER = previous.ROOT, previous.STEP, previous.STOP, previous.AFTER
START, END, KINDS = previous.START, previous.END, previous.KINDS
population = previous.population
RULE = 'garden-landing-uptake-limit-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-uptake-limit-protocol.md'
INPUT = 'benchmarks/garden-seasons/landing-wicking-results.json.gz'
INPUT_SHA = 'db7f43ee7ca46cbdfff73338b0de1896a91beda5a54132e72bafa4986e04be36'
ENVIRONMENT = dict(version=1, after=AFTER, capacity=512)
ARMS = ('off', 'on', 'cap', 'cap-wick')
CANDIDATES = {'cap': 'off', 'cap-wick': 'on'}
BUILD_DIRS = dict(zip(ARMS, ('build-host', 'build-host-wicking', 'build-host-uptake-limit',
                           'build-host-uptake-limit-wicking'), strict=True))
FLAGS = ('TOY_FACTORY_GARDEN_SOIL_WICKING', 'TOY_FACTORY_GARDEN_LATE_UPTAKE_LIMIT')


@cache
def inputs():
    require(digest(ROOT / INPUT) == INPUT_SHA, 'uptake-limit input changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream: value = json.load(stream)
    previous.check_value(value)
    return value


def name(pair, arm, label='trace'):
    return previous.name_for(pair['case'], pair['allocator'], arm, label)


def saved_run(pair, arm):
    return inputs()['capture']['runs'][name(pair, CANDIDATES.get(arm, arm))]


def calls():
    return [(p, a, label) for p in inputs()['pairs'] for a in ARMS
            for label in (('trace', 'repeat') if a in CANDIDATES else ('trace',))]


def check_result(result, pair, arm):
    value = dict(result)
    require(value.pop('uptake_limit_probe', None) == (ENVIRONMENT if arm in CANDIDATES else None),
            'wrong uptake cap identity')
    previous.check_result(value, pair['case'], pair['allocator'], CANDIDATES.get(arm, arm))


def check_settings(settings, arm):
    enabled = {FLAGS[0]: arm in ('on', 'cap-wick'), FLAGS[1]: arm in CANDIDATES}
    require(all(settings.get(k) == ('ON' if v else 'OFF') for k, v in enabled.items()) and
            all(v == 'OFF' for k, v in settings.items() if k.startswith('TOY_FACTORY_GARDEN_') and k not in FLAGS) and
            all(settings.get('TOY_FACTORY_SIMULATOR_' + k) == 'ON' for k in ('SANITIZERS', 'PROFILING')),
            'wrong isolated uptake-limit build')


def settings_at(path, arm):
    settings = dict(line.split(':BOOL=', 1) for line in path.read_text().splitlines()
                    if line.startswith('TOY_FACTORY_') and ':BOOL=' in line)
    check_settings(settings, arm)
    return settings


def check_capture(value):
    require(value['rule'] == RULE and value['input_sha256'] == INPUT_SHA and value['full_replays'] == 48 and
            value['training_runs'] == 0 and value['environment'] == ENVIRONMENT and
            value['protocol_sha256'] == digest(ROOT / PROTOCOL) and
            value['model_sha256'] == previous.MODEL_SHA and
            value['source_sha256'].get(PROTOCOL) == value['protocol_sha256'] and
            value['source_sha256'].get(INPUT) == INPUT_SHA, 'wrong uptake-limit provenance')
    require(set(value['builds']) == set(ARMS), 'wrong four-arm build panel')
    reference = value['builds']['off']['settings']
    for arm in ARMS:
        settings = value['builds'][arm]['settings']
        check_settings(settings, arm)
        require({k: v for k, v in settings.items() if k not in FLAGS} ==
                {k: v for k, v in reference.items() if k not in FLAGS}, 'unrelated build setting changed')
    require(set(value['runs']) == {name(p, a, label) for p, a, label in calls()}, 'wrong trial panel')
    for pair, arm, label in calls():
        key = name(pair, arm, label)
        run, saved = value['runs'][key], saved_run(pair, arm)
        check_result(run['result'], pair, arm)
        require(run['args'] == saved['args'] and set(run['traces']) == set(KINDS), 'trial arguments changed')
        for kind in KINDS:
            file = run['args'][run['args'].index('--' + kind + '-trace') + 1]
            require(run['traces'][kind]['path'] == key + '/' + file + '.gz', 'wrong trace location')
        require(run['frame']['path'] == key + '/' + run['args'][run['args'].index('--framebuffer') + 1],
                'wrong pixel location')
        if arm not in CANDIDATES: previous.same_run(run, saved)
        if label == 'repeat': previous.same_run(run, value['runs'][name(pair, arm)])


def collect(out, jobs):
    require(not out.exists() and not out.is_symlink() and
            (out.is_relative_to(ROOT / 'artifacts') or not out.is_relative_to(ROOT)), 'fresh uptake-limit output required')
    inputs()
    sources = source_files()
    out.mkdir(parents=True)
    (out / 'bin').mkdir()
    value = dict(rule=RULE, input_sha256=INPUT_SHA, full_replays=48, training_runs=0, environment=ENVIRONMENT,
                 protocol_sha256=digest(ROOT / PROTOCOL), model_sha256=previous.MODEL_SHA,
                 source_sha256=sources, builds={}, runs={})
    for arm, build in BUILD_DIRS.items():
        binary, settings = ROOT / build / 'toy-factory-garden-landing', ROOT / build / 'CMakeCache.txt'
        value['builds'][arm] = dict(binary=digest(binary), cache=digest(settings), settings=settings_at(settings, arm))
        shutil.copy2(binary, out / ('bin/' + arm))
        shutil.copy2(settings, out / (arm + '-CMakeCache.txt'))
    snapshot_sources(out, sources)
    shutil.copy2(ROOT / PROTOCOL, out / 'protocol.md')
    model = population.load_model()[1]
    require(hashlib.sha256(model).hexdigest() == previous.MODEL_SHA, 'wrong model bytes')
    with (out / 'model.tgl').open('xb') as stream: stream.write(model)

    def capture(call):
        pair, arm, label = call
        key, args = name(pair, arm, label), saved_run(pair, arm)['args']
        directory = out / key
        directory.mkdir()
        (directory / 'frames').mkdir()
        shutil.copy2(out / 'model.tgl', directory / 'model.tgl')
        result = population.order.training.native(out / ('bin/' + arm), directory, *args)
        check_result(result, pair, arm)
        write_json(directory / 'result.json', result)
        traces = {}
        for kind in KINDS:
            file = args[args.index('--' + kind + '-trace') + 1]
            target = directory / (file + '.gz')
            compress(directory / file, target)
            traces[kind] = dict(path=key + '/' + file + '.gz', sha256=digest(target))
        frame = args[args.index('--framebuffer') + 1]
        raw = (directory / frame).read_bytes()
        require(len(raw) == 115200 and f'{zlib.crc32(raw):08x}' == result['framebuffer_crc32'], 'wrong pixels')
        run = dict(args=args, result=result, traces=traces,
                   frame=dict(path=key + '/' + frame, sha256=digest(directory / frame)))
        if arm not in CANDIDATES: previous.same_run(run, saved_run(pair, arm))
        write_json(directory / 'run.json', run)
        print(key + ': captured', flush=True)
        return key, run

    with ThreadPoolExecutor(max_workers=jobs) as pool: value['runs'] = dict(pool.map(capture, calls()))
    check_capture(value)
    value['gallery'] = contact_sheet(out, [[dict(id=name(p, a), framebuffer=value['runs'][name(p, a)]['frame']['path'])
                                           for a in ARMS] for p in inputs()['pairs']])
    value['gallery']['sha256'] = digest(out / 'contact-sheet.png')
    require(source_files() == sources and all(
            digest(ROOT / d / 'toy-factory-garden-landing') == value['builds'][a]['binary'] and
            digest(ROOT / d / 'CMakeCache.txt') == value['builds'][a]['cache'] for a, d in BUILD_DIRS.items()),
            'source/build changed during uptake-limit capture')
    write_json(out / 'capture.json', value)
    write_json(out / 'manifest.json', dict(rule=RULE, artifacts={str(p.relative_to(out)): digest(p)
                                          for p in sorted(out.rglob('*')) if p.is_file()}))
    return value


def load_bundle(directory):
    manifest = json.loads((directory / 'manifest.json').read_text())
    require(manifest['rule'] == RULE, 'wrong raw experiment')
    for name_, sha in manifest['artifacts'].items():
        path = (directory / name_).resolve()
        require(path.is_relative_to(directory) and digest(path) == sha, 'raw artifact changed: ' + name_)
    value = json.loads((directory / 'capture.json').read_text())
    check_capture(value)
    require(archived_sources(directory / 'source.tar.gz') == value['source_sha256'] and
            digest(directory / 'protocol.md') == value['protocol_sha256'] and
            digest(directory / 'model.tgl') == previous.MODEL_SHA and
            digest(directory / 'contact-sheet.png') == value['gallery']['sha256'], 'frozen provenance changed')
    for arm in ARMS:
        require(digest(directory / ('bin/' + arm)) == value['builds'][arm]['binary'] and
                digest(directory / (arm + '-CMakeCache.txt')) == value['builds'][arm]['cache'] and
                settings_at(directory / (arm + '-CMakeCache.txt'), arm) == value['builds'][arm]['settings'],
                'frozen build changed')
    for key, run in value['runs'].items():
        for item in (run['frame'], *run['traces'].values()):
            require(manifest['artifacts'].get(item['path']) == item['sha256'], 'run/manifest mismatch')
        require(json.loads((directory / key / 'run.json').read_text()) == run and
                json.loads((directory / key / 'result.json').read_text()) == run['result'] and
                digest(directory / key / 'model.tgl') == previous.MODEL_SHA, 'raw call identity changed')
    return value


def shared_prefix(directory, left, right):
    """Compare complete traces; preserve run-length encoded living-body occupancy."""
    out, occupancy = {}, [[], []]
    for kind in KINDS:
        readers = [previous.uptake.observation_rows(directory / r['traces'][kind]['path'], [[START, END]], r['result'])
                   if kind == 'uptake' else
                   previous.allocation.previous.direction_rows(directory / r['traces'][kind]['path'], r['result'], False)
                   if kind == 'direction' else
                   population.trace_rows(directory / r['traces'][kind]['path'], kind, r['result']) for r in (left, right)]
        hashes, count, first = [hashlib.sha256(), hashlib.sha256()], 0, None
        try:
            for a, b in zip(*readers, strict=True):
                require(a['tick'] == b['tick'], 'unequal clocks')
                if a != b and first is None: first = a['tick']
                if a['tick'] <= AFTER:
                    require(a == b, 'uptake cap changed shared history')
                    count += 1
                    for h, row in zip(hashes, (a, b), strict=True):
                        h.update(json.dumps(row, sort_keys=True, separators=(',', ':')).encode() + b'\n')
                if kind == 'stand':
                    for rows, row in zip(occupancy, (a, b), strict=True):
                        shape = [sum(p['nodes'] for p in row['bodies']), len(row['bodies'])]
                        if not rows or rows[-1][1:] != shape: rows.append([row['tick'], *shape])
        finally:
            for reader in readers: reader.close()
        out[kind] = dict(samples=count, sha256=[h.hexdigest() for h in hashes], first_difference=first)
    return out, occupancy


def occupancy_accounts(rows, result):
    require(rows and rows[0][0] == STEP and all(len(r) == 3 and all(type(v) is int for v in r) and
            STEP <= r[0] <= STOP and r[0] % STEP == 0 and 0 <= r[1] <= 256 and 0 <= r[2] <= 8
            for r in rows) and all(a[0] < b[0] and a[1:] != b[1:] for a, b in zip(rows, rows[1:])),
            'invalid living-body occupancy')
    out = {}
    for key, start in (('post', AFTER), ('late32', STOP - 32 * population.DAY)):
        totals = dict(samples=0, node_samples=0, plant_samples=0, full_living_slots=0, fewer_than_four_live_node_spaces=0)
        for row, next_tick in zip(rows, [r[0] for r in rows[1:]] + [STOP + STEP], strict=True):
            tick, nodes, plants = row
            count = max(0, (next_tick - max(tick, start + STEP)) // STEP)
            totals['samples'] += count
            totals['node_samples'] += nodes * count
            totals['plant_samples'] += plants * count
            totals['full_living_slots'] += (plants == 8) * count
            totals['fewer_than_four_live_node_spaces'] += (nodes > 252) * count
        require(totals['samples'] == (STOP - start) // STEP, 'incomplete occupancy interval')
        totals['births'] = sum(p['generation'] > 0 and p['birth_tick'] > start for p in result['lineages'])
        out[key] = totals
    return out


def derive(receipt, analysis, result, case, arm):
    identity, common_end = previous.SUBJECTS[case['guard']]
    plant = next(p for p in analysis['plants'] if p['life']['id'] == identity)
    selected = previous.focal_accounts(receipt['selected'], plant['life'], common_end)
    full = selected['lifetime']
    require(full['resources'] == plant['resources'] and full['payments'] == plant['payments'] and
            all(full[r + '_unpaid'] == sum(s[r]['unpaid'] for s in plant['shortages']) for r in ('energy', 'water')),
            'selected/population account differs')
    return dict(soil=previous.soil_account(receipt['soil'], result, arm == 'cap-wick', capped_after=AFTER),
                selected=selected, drought=previous.drought_accounts(analysis), metrics=population.metrics(result, analysis))


def comparison(left, right, case):
    identity, old_end = previous.SUBJECTS[case['guard']]
    lives = [next(p for p in a['result']['lineages'] if p['id'] == identity) for a in (left, right)]
    end = min(old_end, *(p['death_tick'] or STOP for p in lives))
    require(all(p['birth_tick'] == 590640 for p in lives), 'selected birth changed')
    return dict(screen=population.comparison(left['derived']['metrics'], right['derived']['metrics']),
                matching=population.matched_births(left['result'], right['result']),
                matched_selected=[previous.focal_accounts(a['receipt']['selected'], life, end)['fixed']
                                  for a, life in zip((left, right), lives, strict=True)])


def analyze_pair(task):
    directory, capture, index = task
    pair = inputs()['pairs'][index]
    arms, prefixes, occupancy, comparisons = {}, {}, {}, {}
    for arm, control in CANDIDATES.items():
        run = capture['runs'][name(pair, arm)]
        shared, shapes = shared_prefix(directory, capture['runs'][name(pair, control)], run)
        prefixes[arm] = shared
        for key, rows in zip((control, arm), shapes, strict=True):
            occupancy[key] = dict(rows=rows, accounts=occupancy_accounts(rows, capture['runs'][name(pair, key)]['result']))
        analysis = previous.analyze_arm(directory, run, pair['case'], pair['allocator'])
        receipt = previous.extract(directory, run, previous.SUBJECTS[pair['case']['guard']][0])
        arms[arm] = dict(result=run['result'], analysis=analysis, receipt=receipt,
                         derived=derive(receipt, analysis, run['result'], pair['case'], arm))
        comparisons[arm] = comparison(pair['arms'][control], arms[arm], pair['case'])
    comparisons['wicking_with_cap'] = comparison(arms['cap'], arms['cap-wick'], pair['case'])
    print(pair['case']['id'] + '/' + pair['allocator'] + ': reconciled', flush=True)
    return dict(case=pair['case'], allocator=pair['allocator'], arms=arms, prefix=prefixes,
                occupancy=occupancy, comparisons=comparisons)


def check_value(value):
    capture = value['capture']
    check_capture(capture)
    require(len(value['pairs']) == len(inputs()['pairs']), 'wrong analyzed panel')
    for pair, old in zip(value['pairs'], inputs()['pairs'], strict=True):
        require(pair['case'] == old['case'] and pair['allocator'] == old['allocator'] and
                set(pair['arms']) == set(CANDIDATES) and set(pair['prefix']) == set(CANDIDATES) and
                set(pair['occupancy']) == set(ARMS), 'wrong analyzed setting')
        expected = {}
        for arm, control in CANDIDATES.items():
            a = pair['arms'][arm]
            require(a['result'] == capture['runs'][name(pair, arm)]['result'], 'analyzed result differs')
            population.check_analysis(a['analysis'], a['result'])
            require(a['derived'] == derive(a['receipt'], a['analysis'], a['result'], pair['case'], arm),
                    'capped account differs')
            identity = previous.SUBJECTS[pair['case']['guard']][0]
            life, saved = [next(p for p in r['lineages'] if p['id'] == identity)
                           for r in (a['result'], old['arms'][control]['result'])]
            require(all(life[k] == saved[k] for k in ('birth_tick', 'parent', 'generation', 'species', 'column')),
                    'selected ancestry changed')
            require(set(pair['prefix'][arm]) == set(KINDS), 'incomplete prefix check')
            for kind in KINDS:
                p = pair['prefix'][arm][kind]
                require(p['samples'] == ((AFTER - START) // STEP + 1 if kind == 'uptake' else AFTER // STEP) and
                        len(p['sha256']) == 2 and p['sha256'][0] == p['sha256'][1] and
                        (p['first_difference'] is None or p['first_difference'] >= AFTER + STEP), 'invalid shared prefix')
            expected[arm] = comparison(old['arms'][control], a, pair['case'])
        for arm, o in pair['occupancy'].items():
            require(o['accounts'] == occupancy_accounts(o['rows'], capture['runs'][name(pair, arm)]['result']),
                    'occupancy summary differs')
        expected['wicking_with_cap'] = comparison(pair['arms']['cap'], pair['arms']['cap-wick'], pair['case'])
        require(pair['comparisons'] == expected, 'paired results differ')


def analyze(directory, capture, jobs):
    inputs()  # Share immutable pinned inputs with forked readers, not serialized copies.
    tasks = [(directory, capture, i) for i in range(len(inputs()['pairs']))]
    if jobs == 1:
        pairs = list(map(analyze_pair, tasks))
    else:
        with ProcessPoolExecutor(max_workers=jobs, mp_context=get_context('fork')) as pool:
            pairs = list(pool.map(analyze_pair, tasks))
    value = dict(capture=capture, raw_manifest_sha256=digest(directory / 'manifest.json'), pairs=pairs)
    check_value(value)
    return value


def verify(path, bundle=None, jobs=4):
    with gzip.open(path, 'rt') as stream: value = json.load(stream)
    check_value(value)
    if bundle:
        require(digest(bundle / 'manifest.json') == value['raw_manifest_sha256'] and
                load_bundle(bundle) == value['capture'], 'wrong raw source')
        require(analyze(bundle, value['capture'], jobs) == value, 'raw re-extraction differs')
    print('Verified uptake-limit controls, repeats, cell budgets and population accounts (offline).')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'artifacts/garden-landing-uptake-limit-v1')
    parser.add_argument('--jobs', type=int, choices=range(1, 5), default=4)
    parser.add_argument('--analyze', type=Path)
    parser.add_argument('--verify', type=Path)
    parser.add_argument('--bundle', type=Path)
    args = parser.parse_args()
    if args.verify:
        verify(args.verify.resolve(), args.bundle.resolve() if args.bundle else None, args.jobs)
    elif args.analyze:
        require(not args.out.exists() and not args.out.is_symlink() and args.bundle is None, 'fresh analysis output required')
        directory = args.analyze.resolve()
        value = analyze(directory, load_bundle(directory), args.jobs)
        population.order.recovery.founders.write_gzip(args.out, value)
    else:
        require(args.bundle is None, '--bundle requires --verify')
        collect(args.out.resolve(), args.jobs)
        print('Capture complete; use --analyze to reconcile saved receipts offline.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, TypeError, OSError, StopIteration) as error:
        print('uptake-limit experiment failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
