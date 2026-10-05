#!/usr/bin/env python3
"""Frozen late broader-dispersal panel; capture separately from offline analysis."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from functools import cache, lru_cache
import gzip
import hashlib
import json
from multiprocessing import get_context
from pathlib import Path
import shutil
import sys
import zlib

import garden_landing_uptake_limit as previous
from garden_experiments import compress, digest, snapshot_sources, source_files, write_json
from garden_gallery import contact_sheet
from garden_landing_energy_audit import archived_sources
from garden_landing_founders import write_gzip
from garden_landing_reach import sites_decode
from garden_resources import require

ROOT, STEP, STOP, AFTER = previous.ROOT, previous.STEP, previous.STOP, previous.AFTER
population, historical = previous.population, previous.previous
DAY, LATE = population.DAY, STOP - 32 * population.DAY
RULE = 'garden-landing-late-dispersal-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-late-dispersal-protocol.md'
INPUT = 'benchmarks/garden-seasons/landing-uptake-limit-results.json.gz'
INPUT_SHA = '687f354bbeb04b71dc2c8d81b57bccefba0a1f6e2cfa6677f9dd14d517647768'
ENVIRONMENT = dict(version=1, after=AFTER, minimum=3, distances=7)
ARMS = ('cap', 'cap-wick', 'wide-cap', 'wide-cap-wick')
CANDIDATES = {'wide-cap': 'cap', 'wide-cap-wick': 'cap-wick'}
KINDS = (*previous.KINDS, 'reach')
FLAGS = (*previous.FLAGS, 'TOY_FACTORY_GARDEN_LATE_DISPERSAL')
BUILDS = dict(zip(ARMS, ('build-host-uptake-limit', 'build-host-uptake-limit-wicking',
                       'build-host-late-dispersal', 'build-host-late-dispersal-wicking'), strict=True))
PERIODS = {'post': AFTER, 'late32': LATE}


@cache
def inputs():
    require(digest(ROOT / INPUT) == INPUT_SHA, 'late-dispersal input changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream: value = json.load(stream)
    require(value['capture']['rule'] == previous.RULE and len(value['pairs']) == 8,
            'wrong capped panel')
    for pair in value['pairs']:
        for arm in ('cap', 'cap-wick'):
            a = pair['arms'][arm]
            previous.check_result(a['result'], pair, arm)
            population.check_analysis(a['analysis'], a['result'])
            require(a['derived']['metrics'] == population.metrics(a['result'], a['analysis']),
                    'pinned population summary differs')
    return value


def name(pair, arm, label='trace'):
    return previous.name(pair, arm, label)


def saved_run(pair, arm):
    return inputs()['capture']['runs'][name(pair, CANDIDATES.get(arm, arm))]


def calls():
    return [(p, a, label) for p in inputs()['pairs'] for a in ARMS
            for label in (('trace', 'repeat') if a in CANDIDATES else ('trace',))]


def arguments(pair, arm):
    args = saved_run(pair, arm)['args']
    require('--reach-trace' not in args, 'reach observer already present')
    return args + ['--reach-trace', 'reach.jsonl']


def check_result(result, pair, arm):
    value = dict(result)
    require(value.pop('late_dispersal_probe', None) == (ENVIRONMENT if arm in CANDIDATES else None),
            'wrong late-dispersal identity')
    previous.check_result(value, pair, CANDIDATES.get(arm, arm))


def check_settings(settings, arm):
    enabled = {FLAGS[0]: arm.endswith('wick'), FLAGS[1]: True, FLAGS[2]: arm in CANDIDATES}
    require(all(settings.get(k) == ('ON' if v else 'OFF') for k, v in enabled.items()) and
            all(v == 'OFF' for k, v in settings.items() if k.startswith('TOY_FACTORY_GARDEN_') and k not in FLAGS) and
            all(settings.get('TOY_FACTORY_SIMULATOR_' + k) == 'ON' for k in ('SANITIZERS', 'PROFILING')),
            'wrong isolated late-dispersal build')


def settings_at(path, arm):
    settings = dict(line.split(':BOOL=', 1) for line in path.read_text().splitlines()
                    if line.startswith('TOY_FACTORY_') and ':BOOL=' in line)
    check_settings(settings, arm)
    return settings


def same_run(a, b, kinds=KINDS):
    require(a['result'] == b['result'] and a['frame']['sha256'] == b['frame']['sha256'] and
            all(a['traces'][k]['sha256'] == b['traces'][k]['sha256'] for k in kinds),
            'historical control or exact repeat changed')


def check_capture(value):
    require(value['rule'] == RULE and value['input_sha256'] == INPUT_SHA and value['full_replays'] == 48 and
            value['training_runs'] == 0 and value['environment'] == ENVIRONMENT and
            value['protocol_sha256'] == digest(ROOT / PROTOCOL) and
            value['model_sha256'] == historical.MODEL_SHA and
            value['source_sha256'].get(PROTOCOL) == value['protocol_sha256'] and
            value['source_sha256'].get(INPUT) == INPUT_SHA, 'wrong late-dispersal provenance')
    require(set(value['builds']) == set(ARMS), 'wrong four-build panel')
    reference = value['builds']['cap']['settings']
    for arm in ARMS:
        settings = value['builds'][arm]['settings']
        check_settings(settings, arm)
        require({k: v for k, v in settings.items() if k not in FLAGS} ==
                {k: v for k, v in reference.items() if k not in FLAGS}, 'unrelated build changed')
    require(set(value['runs']) == {name(p, a, label) for p, a, label in calls()}, 'wrong trial panel')
    for pair, arm, label in calls():
        key = name(pair, arm, label)
        run = value['runs'][key]
        check_result(run['result'], pair, arm)
        require(run['args'] == arguments(pair, arm) and set(run['traces']) == set(KINDS), 'trial arguments changed')
        for kind in KINDS:
            file = run['args'][run['args'].index('--' + kind + '-trace') + 1]
            require(run['traces'][kind]['path'] == key + '/' + file + '.gz', 'wrong trace location')
        require(run['frame']['path'] == key + '/' + run['args'][run['args'].index('--framebuffer') + 1],
                'wrong frame location')
        if arm not in CANDIDATES: same_run(run, saved_run(pair, arm), previous.KINDS)
        if label == 'repeat': same_run(run, value['runs'][name(pair, arm)])


def collect(out, jobs):
    require(not out.exists() and not out.is_symlink() and
            (out.is_relative_to(ROOT / 'artifacts') or not out.is_relative_to(ROOT)), 'fresh late-dispersal output required')
    inputs()
    sources = source_files()
    out.mkdir(parents=True)
    (out / 'bin').mkdir()
    value = dict(rule=RULE, input_sha256=INPUT_SHA, full_replays=48, training_runs=0, environment=ENVIRONMENT,
                 protocol_sha256=digest(ROOT / PROTOCOL), model_sha256=historical.MODEL_SHA,
                 source_sha256=sources, builds={}, runs={})
    for arm, build in BUILDS.items():
        binary, settings = ROOT / build / 'toy-factory-garden-landing', ROOT / build / 'CMakeCache.txt'
        value['builds'][arm] = dict(binary=digest(binary), cache=digest(settings), settings=settings_at(settings, arm))
        shutil.copy2(binary, out / ('bin/' + arm))
        shutil.copy2(settings, out / (arm + '-CMakeCache.txt'))
    snapshot_sources(out, sources)
    shutil.copy2(ROOT / PROTOCOL, out / 'protocol.md')
    model = population.load_model()[1]
    require(hashlib.sha256(model).hexdigest() == historical.MODEL_SHA, 'wrong model bytes')
    with (out / 'model.tgl').open('xb') as stream: stream.write(model)

    def capture(call):
        pair, arm, label = call
        key, args = name(pair, arm, label), arguments(pair, arm)
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
        if arm not in CANDIDATES: same_run(run, saved_run(pair, arm), previous.KINDS)
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
            digest(ROOT / d / 'CMakeCache.txt') == value['builds'][a]['cache'] for a, d in BUILDS.items()),
            'source/build changed during capture')
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
            digest(directory / 'model.tgl') == historical.MODEL_SHA and
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
                digest(directory / key / 'model.tgl') == historical.MODEL_SHA, 'raw call identity changed')
    return value


def support(origin, trait, wide):
    require(type(origin) is int and 0 <= origin < 28 and type(trait) is int and -2 <= trait <= 2 and
            type(wide) is bool, 'invalid support inputs')
    result = []
    for distance in range(3 if wide else 5, 10 if wide else 8):
        for direction in (-1, 1):
            column = origin + direction * (distance + trait)
            if not 0 <= column < 28: column = origin - direction * (distance + trait)
            result.append(min(27, max(0, column)))
    return result


@lru_cache(maxsize=4096)
def spacing_map(columns):
    return bytes(32 if any(abs(origin - c) < 3 for origin in columns) else 0 for c in range(28))


@lru_cache(maxsize=8192)
def decode_map(encoded):
    sites = sites_decode(encoded)
    return sites, bytes(m & 32 for m in sites), sum(m == 0 for m in sites)


def reach_rows(path, stop=STOP):
    with gzip.open(path, 'rt') as stream:
        require(json.loads(next(stream)) == {'schema': 'landing-reach-trace-v1'}, 'wrong reach header')
        for tick in range(STEP, stop + STEP, STEP):
            row = json.loads(next(stream))
            require(set(row) == {'tick', 'purchases', 'checks'} and row['tick'] == tick, 'wrong reach clock')
            yield row
        require(json.loads(next(stream)) == {'complete': True, 'tick': stop} and not stream.read(), 'wrong reach footer')


def purchase_check(p, slots, lives, seed, wide):
    parent = lives[seed['parent']]
    tick = seed['birth_tick']
    require(set(p) == {'parent', 'column', 'origin', 'dispersal', 'choices', 'sites'} and
            p['parent'] == seed['parent'] and p['column'] == seed['column'] and
            p['origin'] == parent['column'] and parent['birth_tick'] <= tick and
            (parent['death_tick'] is None or tick < parent['death_tick']) and
            p['choices'] == support(p['origin'], p['dispersal'], wide and tick > AFTER) and
            p['column'] in p['choices'], 'wrong purchase/support')
    require(len(slots) == len(set(slots)) and p['parent'] in slots and
            all(i in lives and lives[i]['birth_tick'] <= tick for i in slots), 'wrong stored census')
    sites, spacing, _ = decode_map(p['sites'])
    require(spacing == spacing_map(tuple(lives[i]['column'] for i in slots)), 'purchase spacing/census disagree')
    require(not sites[p['column']] & 32 or all(sites[c] & 32 for c in p['choices']),
            'blocked purchase despite a spacing-clear choice')
    return sites


def extract_reach(directory, run, wide):
    result = run['result']
    ledger = {(s['parent'], s['birth_tick']): s for s in result['seeds']}
    lives = {p['id']: p for p in result['lineages']}
    require(len(ledger) == len(result['seeds']), 'duplicate seed ledger')
    records, active, traits = {}, set(), {}
    readers = [population.trace_rows(directory / run['traces'][k]['path'], k, result) for k in ('stand', 'adult')]
    readers.append(reach_rows(directory / run['traces']['reach']['path'], result['tick']))
    try:
        for stand, adult, row in zip(*readers, strict=True):
            tick = row['tick']
            require(tick == stand['tick'] == adult['tick'], 'reach/stand clock differs')
            newborns = {p['id'] for p in result['lineages'] if p['birth_tick'] == tick}
            slots = [i for i in stand['plant_order'] if i not in newborns]
            seen, ended = set(), set()
            require(len(row['checks']) == len(adult['seeds']), 'reach check count differs')
            for values, attempt in zip(row['checks'], adult['seeds'], strict=True):
                require(len(values) == 7 and all(type(v) is int for v in values[:6]), 'invalid reach check')
                parent, age, column, mask, outcome, child, encoded = values
                require(values[:4] == attempt[:4] and values[4:6] == attempt[8:10] and
                        len(slots) == attempt[6], 'reach/adult/sequential census differ')
                key = parent, tick - age * STEP
                require(key in active and key not in seen, 'unknown/duplicate seed check')
                seen.add(key)
                record, seed = records[key], ledger[key]
                require(age == record['samples'] + 1 and column == seed['column'] and 0 <= mask < 128,
                        'wrong seed age/site')
                expected = 0 if seed['end_tick'] != tick else {'expired': 1, 'germinated': 2}[seed['outcome']]
                require(outcome == expected and child == (seed['child_id'] if outcome == 2 else 0), 'seed fate differs')
                record['samples'] += 1
                if outcome: ended.add(key)
                if outcome == 1:
                    require(encoded is None and mask == 0 and age == seed['lifetime_ecology_ticks'] and attempt[10] == -1,
                            'expiry is not a germination check')
                    continue
                sites, spacing, opened = decode_map(encoded)
                require(bool(mask & 1) == (age < 8) and (mask & ~1) == sites[column] and
                        ((mask == 0) == (outcome == 2)) and opened == attempt[10],
                        'chosen/full-site gates disagree')
                require(spacing == spacing_map(tuple(lives[i]['column'] for i in slots)), 'sequential spacing map differs')
                if not mask & 1:
                    for period, start in PERIODS.items():
                        if tick > start: record['mature_sites'][period][encoded] += 1
                if outcome == 2: slots.append(child)
            require(seen == active and slots == stand['plant_order'], 'seed/slot inventory incomplete')
            active -= ended
            purchased = set()
            for p in row['purchases']:
                key = p['parent'], tick
                require(key in ledger and key not in records, 'unknown/duplicate purchase')
                purchase_check(p, slots, lives, ledger[key], wide)
                require(traits.setdefault(p['parent'], p['dispersal']) == p['dispersal'], 'parent trait changed')
                records[key] = dict(seed=list(key), purchase=p, slots=slots, samples=0,
                                    mature_sites={k: Counter() for k in PERIODS})
                purchased.add(key)
            require(purchased == {k for k in ledger if k[1] == tick}, 'purchase inventory differs')
            active |= purchased
            require(len(active) == adult['bank'], 'seed bank differs')
    finally:
        for reader in readers: reader.close()
    require(set(records) == set(ledger), 'missing purchases')
    for key, r in records.items():
        seed = ledger[key]
        require(r['samples'] == ((seed['end_tick'] or result['tick']) - seed['birth_tick']) // STEP,
                'seed lifetime gap')
        r['mature_sites'] = {k: dict(sorted(v.items())) for k, v in r['mature_sites'].items()}
    return [records[k] for k in ledger]


def renewal(result):
    out = {}
    for period, start in PERIODS.items():
        cohort = [p for p in result['lineages'] if p['generation'] > 0 and p['birth_tick'] > start]
        seeds = [s for s in result['seeds'] if s['birth_tick'] > start]
        out[period] = dict(births=len(cohort), purchases=len(seeds),
            seed_parents=sum(p['seeds_created'] > 0 for p in cohort),
            successful_parents=sum(any(c['parent'] == p['id'] and population.survival(c, STOP, 1) == 'confirmed'
                                      for c in result['lineages']) for p in cohort),
            survival={str(d): dict(Counter(population.survival(p, STOP, d) for p in cohort)) for d in (1, 32)},
            living=sum(p['death_tick'] is None for p in cohort))
    return out


def reach_summary(records, result, wide):
    ledger = {(s['parent'], s['birth_tick']): s for s in result['seeds']}
    lives = {p['id']: p for p in result['lineages']}
    require([tuple(r['seed']) for r in records] == list(ledger), 'wrong compact seed inventory')
    out = {k: dict(purchases=0, blocked=0, blocked_with_global_spacing=0, mature_checks=0,
                  any_global_open=0, any_reachable_open=0, spacing_checks=0) for k in PERIODS}
    traits = {}
    for r in records:
        seed = ledger[tuple(r['seed'])]
        p = r['purchase']
        sites = purchase_check(p, r['slots'], lives, seed, wide)
        require(traits.setdefault(p['parent'], p['dispersal']) == p['dispersal'], 'parent trait changed')
        require(r['samples'] == ((seed['end_tick'] or result['tick']) - seed['birth_tick']) // STEP and
                set(r['mature_sites']) == set(PERIODS), 'invalid compact seed history')
        for period, start in PERIODS.items():
            s = out[period]
            if seed['birth_tick'] > start:
                s['purchases'] += 1
                blocked = bool(sites[seed['column']] & 32)
                s['blocked'] += blocked
                s['blocked_with_global_spacing'] += blocked and any(not m & 32 for m in sites)
            samples = 0
            for encoded, count in r['mature_sites'][period].items():
                require(type(count) is int and count > 0, 'invalid site count')
                masks = sites_decode(encoded)
                samples += count
                s['mature_checks'] += count
                s['any_global_open'] += count * any(m == 0 for m in masks)
                s['any_reachable_open'] += count * any(masks[c] == 0 for c in p['choices'])
                s['spacing_checks'] += count * bool(masks[seed['column']] & 32)
            end = (seed['end_tick'] or result['tick']) - (STEP if seed['outcome'] == 'expired' else 0)
            first = max(start + STEP, seed['birth_tick'] + 8 * STEP)
            require(samples == max(0, (end - first) // STEP + 1), 'mature-site histogram has missing checks')
        for encoded, count in r['mature_sites']['late32'].items():
            require(count <= r['mature_sites']['post'].get(encoded, 0), 'late histogram not a subset')
    return out


def reach_prefix(directory, left, right):
    hashes, count, first = [hashlib.sha256(), hashlib.sha256()], 0, None
    readers = [reach_rows(directory / r['traces']['reach']['path']) for r in (left, right)]
    try:
        for a, b in zip(*readers, strict=True):
            require(a['tick'] == b['tick'], 'reach clocks differ')
            if a != b and first is None: first = a['tick']
            if a['tick'] <= AFTER:
                require(a == b, 'reach changed before onset')
                count += 1
                for h, row in zip(hashes, (a, b), strict=True):
                    h.update(json.dumps(row, sort_keys=True, separators=(',', ':')).encode() + b'\n')
    finally:
        for reader in readers: reader.close()
    return dict(samples=count, sha256=[h.hexdigest() for h in hashes], first_difference=first)


def analyze_pair(task):
    directory, capture, index = task
    pair = inputs()['pairs'][index]
    arms, prefixes, occupancy, comparisons = {}, {}, {}, {}
    for arm in ARMS:
        run = capture['runs'][name(pair, arm)]
        control = CANDIDATES.get(arm, arm)
        if arm in CANDIDATES:
            analysis = historical.analyze_arm(directory, run, pair['case'], pair['allocator'])
            receipt = historical.extract(directory, run, historical.SUBJECTS[pair['case']['guard']][0])
            a = dict(result=run['result'], analysis=analysis, receipt=receipt,
                     derived=previous.derive(receipt, analysis, run['result'], pair['case'], control))
            narrow = capture['runs'][name(pair, control)]
            prefixes[arm], shapes = previous.shared_prefix(directory, narrow, run)
            prefixes[arm]['reach'] = reach_prefix(directory, narrow, run)
            for key, rows in zip((control, arm), shapes, strict=True):
                occupancy[key] = dict(rows=rows, accounts=previous.occupancy_accounts(rows, capture['runs'][name(pair, key)]['result']))
            comparisons[arm] = population.comparison(arms[control]['metrics'], a['derived']['metrics'])
        else:
            a = pair['arms'][arm]  # Pinned analysis, only after byte-identical raw controls.
        records = extract_reach(directory, run, arm in CANDIDATES)
        arms[arm] = dict(result=run['result'], reach=records,
                         reach_summary=reach_summary(records, run['result'], arm in CANDIDATES),
                         metrics=a['derived']['metrics'], renewal=renewal(run['result']))
        if arm in CANDIDATES: arms[arm]['new_analysis'] = a
    print(pair['case']['id'] + '/' + pair['allocator'] + ': reconciled', flush=True)
    return dict(case=pair['case'], allocator=pair['allocator'], arms=arms, prefix=prefixes,
                occupancy=occupancy, comparisons=comparisons)


def check_value(value):
    capture = value['capture']
    check_capture(capture)
    require(len(value['pairs']) == len(inputs()['pairs']), 'wrong analyzed panel')
    for pair, old in zip(value['pairs'], inputs()['pairs'], strict=True):
        require(pair['case'] == old['case'] and pair['allocator'] == old['allocator'] and
                set(pair['arms']) == set(ARMS) and set(pair['prefix']) == set(CANDIDATES) and
                set(pair['occupancy']) == set(ARMS), 'wrong analyzed setting')
        for arm in ARMS:
            a = pair['arms'][arm]
            require(a['result'] == capture['runs'][name(pair, arm)]['result'] and
                    a['renewal'] == renewal(a['result']) and
                    a['reach_summary'] == reach_summary(a['reach'], a['result'], arm in CANDIDATES),
                    'analyzed result/reach differs')
            if arm in CANDIDATES:
                n = a['new_analysis']
                population.check_analysis(n['analysis'], n['result'])
                require(n['result'] == a['result'] and n['derived'] == previous.derive(n['receipt'], n['analysis'],
                        a['result'], pair['case'], CANDIDATES[arm]) and a['metrics'] == n['derived']['metrics'],
                        'candidate population/resource summary differs')
                require(set(pair['prefix'][arm]) == set(KINDS), 'missing prefix receipt')
                for kind, p in pair['prefix'][arm].items():
                    require(p['samples'] == ((AFTER - previous.START) // STEP + 1 if kind == 'uptake' else AFTER // STEP) and
                            len(p['sha256']) == 2 and p['sha256'][0] == p['sha256'][1] and
                            (p['first_difference'] is None or p['first_difference'] >= AFTER + STEP), 'invalid prefix')
            else:
                require(a['metrics'] == old['arms'][arm]['derived']['metrics'], 'control metrics changed')
            occupancy = pair['occupancy'][arm]
            require(occupancy['accounts'] == previous.occupancy_accounts(occupancy['rows'], a['result']),
                    'occupancy summary differs')
        require(pair['comparisons'] == {arm: population.comparison(pair['arms'][control]['metrics'], pair['arms'][arm]['metrics'])
                                       for arm, control in CANDIDATES.items()}, 'paired harm screen differs')


def analyze(directory, capture, jobs):
    check_capture(capture)
    inputs()
    tasks = [(directory, capture, i) for i in range(8)]
    if jobs == 1: pairs = list(map(analyze_pair, tasks))
    else:
        with ProcessPoolExecutor(max_workers=jobs, mp_context=get_context('fork')) as pool:
            pairs = list(pool.map(analyze_pair, tasks))
    value = dict(capture=capture, raw_manifest_sha256=digest(directory / 'manifest.json'), pairs=pairs)
    check_value(value)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'artifacts/garden-landing-late-dispersal-v1')
    parser.add_argument('--jobs', type=int, choices=range(1, 5), default=4)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--analyze', type=Path)
    mode.add_argument('--verify', type=Path)
    parser.add_argument('--bundle', type=Path)
    args = parser.parse_args(argv)
    require(args.bundle is None or args.verify is not None, '--bundle requires --verify')
    if args.verify:
        with gzip.open(args.verify, 'rt') as stream: value = json.load(stream)
        check_value(value)
        if args.bundle:
            directory = args.bundle.resolve()
            require(digest(directory / 'manifest.json') == value['raw_manifest_sha256'] and
                    load_bundle(directory) == value['capture'], 'wrong raw bundle')
            require(analyze(directory, value['capture'], args.jobs) == value, 'raw re-extraction differs')
        print('Verified late dispersal, renewal and resource accounts (offline).')
    elif args.analyze:
        require(not args.out.exists() and not args.out.is_symlink(), 'fresh analysis output required')
        directory = args.analyze.resolve()
        write_gzip(args.out, analyze(directory, load_bundle(directory), args.jobs))
    else:
        require(not args.out.exists() and not args.out.is_symlink(), 'fresh late-dispersal output required')
        collect(args.out.resolve(), args.jobs)
        print('Capture complete; use --analyze to reconcile saved receipts offline.')


if __name__ == '__main__':
    try: main()
    except (RuntimeError, ValueError, KeyError, TypeError, OSError, StopIteration, IndexError) as error:
        print('late-dispersal experiment failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
