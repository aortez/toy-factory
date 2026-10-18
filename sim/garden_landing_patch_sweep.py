#!/usr/bin/env python3
"""Fixed local-dieback pilot with frozen controls, exact repeats and offline verification."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from functools import cache
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zlib

import garden_landing_seed_replacement as previous
from garden_descendants import index_records
from garden_experiments import compress, digest, snapshot_sources, source_files, write_json
from garden_gallery import contact_sheet
from garden_landing_energy_audit import archived_sources
from garden_landing_founders import write_gzip
from garden_landing_root_allocation_audit import fingerprint
from garden_landing_training import native
from garden_resources import require

ROOT, DAY, STEP = previous.ROOT, previous.DAY, previous.STEP
BASE, STOP = 192 * DAY, 320 * DAY
followup, window, late = previous.followup, previous.window, previous.late
RULE = 'garden-landing-patch-sweep-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-patch-sweep-protocol.md'
PROTOCOL_SHA = '08a5267e5778b53c27a3d3f938aae22f9a6f7bfcbf4b9d8b147100a70f786544'
INPUT = 'benchmarks/garden-seasons/landing-seed-replacement-results.json.gz'
INPUT_SHA = 'e856d8877a34747bce4c5ade78e3492acb0f211379ddcb843e4a44a2ec868b4a'
BASELINE = 'benchmarks/garden-seasons/landing-followup-results.json.gz'
BASELINE_SHA = 'b13ce089efa12b431f48a35499be93e7cf7af83a636006b2898b283762e12336'
PHASES = ('baseline', 'control', 'treatment', 'repeat', 'plain')
KINDS = ('stand', 'adult', 'reach')
SOURCES = tuple(sorted({*previous.SOURCES, 'sim/garden_landing_patch_sweep.py'}))
RUNTIME_DELTA = {'sim/garden_landing_cli.c', 'sim/garden_landing_ledger.c', 'sim/garden_landing_ledger.h',
                 'sim/garden_landing_patch_sweep.c', 'sim/garden_landing_patch_sweep.h',
                 'sim/garden_landing_patch_sweep_test.c', 'sim/garden_landing_root_allocation.h'}


@cache
def inputs():
    require(digest(ROOT / PROTOCOL) == PROTOCOL_SHA and digest(ROOT / INPUT) == INPUT_SHA and
            digest(ROOT / BASELINE) == BASELINE_SHA, 'sweep protocol/inputs changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream:
        saved = json.load(stream)
    previous.verify_capture(saved)
    with gzip.open(ROOT / BASELINE, 'rt') as stream:
        baseline = json.load(stream)
    followup.check_value(baseline)
    require(saved['model_sha256'] == baseline['model_sha256'], 'model changed')
    return saved, baseline


def schedule(stop=STOP):
    return [dict(tick=(192 + 8 * j) * DAY, first=4 * (j % 7), last=4 * (j % 7) + 3)
            for j in range(15) if (192 + 8 * j) * DAY <= stop]


def tagged(base):
    h = 2166136261
    for b in b'GPS1' + b''.join(n.to_bytes(4, 'little') for n in (int(base, 16), 192, 8, 4, 15)):
        h = ((h ^ b) * 16777619) & 0xffffffff
    return f'{h:08x}'


def arguments(key, phase):
    saved, old = inputs()
    require(key in saved['panel'] and phase in PHASES, 'unknown sweep call')
    args = list(old['runs']['extension'][key]['args'])
    if phase == 'baseline':
        return args
    i = args.index('--direction-trace')
    del args[i:i + 2]
    for flag in ('--ticks', '--stand-stop', '--adult-stop'):
        args[args.index(flag) + 1] = str(STOP)
    for flag in ('--stand-start', '--adult-start'):
        args[args.index(flag) + 1] = str(BASE)
    if phase == 'plain':
        for flag in ('--stand-trace', '--stand-start', '--stand-stop', '--adult-trace',
                     '--adult-start', '--adult-stop', '--reach-trace'):
            i = args.index(flag)
            del args[i:i + 2]
        args.remove('--stand-dawn')
    if phase in ('treatment', 'repeat', 'plain'):
        args += ['--patch-sweep', 'on']
    return args


def prefix(result, cutoff):
    plants, seeds = followup.prefix_ledgers(result, cutoff)
    for p in plants:
        if p['death_tick'] is None or p['environmental_death'] and p['death_tick'] >= cutoff:
            p.update(death_tick=None, environmental_death=False)
    return plants, seeds


def events(result):
    value = result.get('patch_sweep_probe')
    if value is None:
        return {}
    require(set(value) == {'version', 'first_day', 'period_days', 'width', 'scheduled_events', 'events'} and
            {k: value[k] for k in value if k != 'events'} == dict(version=1, first_day=192, period_days=8,
                                                               width=4, scheduled_events=15), 'wrong sweep rule')
    require([{k: e[k] for k in ('tick', 'first', 'last')} for e in value['events']] == schedule(result['tick']),
            'missing/reordered sweep event')
    lives = {p['id']: p for p in result['lineages']}
    seen = set()
    for event in value['events']:
        require(set(event) == {'tick', 'first', 'last', 'victims', 'before_world_hash', 'after_world_hash',
                               'before_run_hash', 'after_run_hash'}, 'wrong event schema')
        tick = event['tick']
        expected = {i for i, p in lives.items() if p['birth_tick'] <= tick and event['first'] <= p['column'] <= event['last'] and
                    (p['death_tick'] is None or p['death_tick'] > tick or p['environmental_death'] and p['death_tick'] == tick)}
        ids = [v['lineage'] for v in event['victims']]
        require(len(ids) == len(set(ids)) <= 8 and set(ids) == expected and not seen.intersection(ids),
                'event is not the complete living spatial patch')
        seen.update(ids)
        for v in event['victims']:
            p = lives[v['lineage']]
            require(set(v) == {'lineage', 'age', 'nodes', 'energy', 'water'} and p['environmental_death'] and
                    # Offspring germinate before grow_plants in the same step;
                    # their stored age is already one at the recorded birth.
                    p['death_tick'] == tick and v['age'] == (tick - p['birth_tick']) // STEP + (p['parent'] != 0) and
                    0 < v['nodes'] <= 32 and 0 <= v['energy'] <= 256 and 0 <= v['water'] <= 512,
                    'wrong imposed-death receipt')
        for kind in ('world', 'run'):
            require((event[f'before_{kind}_hash'] == event[f'after_{kind}_hash']) == (not ids),
                    'empty/nonempty event state differs')
    require(seen == {i for i, p in lives.items() if p['environmental_death']}, 'unreceipted imposed death')
    return {e['tick']: e for e in value['events']}


def check_result(result, key, phase):
    saved, baseline = inputs()
    old = baseline['runs']['extension'][key]['result']
    if phase == 'baseline':
        require(result == old, 'unforced archived day-288 baseline differs')
        return
    active = phase in ('treatment', 'repeat', 'plain')
    require(set(result) == set(old) | ({'patch_sweep_probe', 'placement_run_hash'} if active else set()) and
            result['tick'] == STOP, 'wrong sweep schema/horizon')
    for name in ('schema_version', 'run_version', 'rules', 'scenario', 'seed', 'model', 'gardener', 'irrigation',
                 'seed_lifetime_ecology_ticks', 'ledger_start_tick', 'warmup_samples',
                 *(k for k in old if k.endswith('_probe'))):
        require(result[name] == old[name], 'unrelated setting changed: ' + name)
    require(result['kind'] == ('landing-patch-sweep-replay' if active else old['kind']) and
            (not active or result['run_hash'] == tagged(result['placement_run_hash'])) and
            result['climate'] == followup.previous.climate(int(result['seed'], 16), STOP), 'wrong identity/climate')
    lives, seeds = index_records(result['lineages'], result['seeds'], 0, STOP)
    require(result['births'] == sum(p['parent'] != 0 for p in lives.values()) and
            result['deaths'] == sum(p['death_tick'] is not None for p in lives.values()) and
            result['living'] == len(lives) - result['deaths'] and
            result['seed_bank'] == sum(s['outcome'] == 'pending' for s in seeds.values()) and
            not any('removal_tick' in p for p in lives.values()), 'ledger totals differ')
    if active:
        events(result)
        require(prefix(result, BASE) == prefix(old, BASE), 'pre-onset ledgers differ')
    else:
        require(not any(p['environmental_death'] for p in lives.values()) and
                prefix(result, 288 * DAY) == (old['lineages'], old['seeds']), 'unforced history changed')


def survival(life, days, stop=None):
    stop = STOP if stop is None else stop
    due = life['birth_tick'] + days * DAY
    if life['death_tick'] is not None and life['death_tick'] <= min(due, stop):
        return 'imposed-death' if life['environmental_death'] else 'natural-death'
    return 'confirmed' if due <= stop else 'censored'


def summary(result):
    lives, seeds = index_records(result['lineages'], result['seeds'], 0, STOP)
    cohort = sorted((p for p in lives.values() if p['birth_tick'] > BASE), key=lambda p: (p['birth_tick'], p['id']))
    depths, established_depths, pairs = {}, {}, []
    for p in cohort:
        depths[p['id']] = 1 + depths.get(p['parent'], 0)
        if survival(p, 16) == 'confirmed':
            established_depths[p['id']] = 1 + established_depths.get(p['parent'], 0)
            if p['parent'] in established_depths:
                pairs.append([p['parent'], p['id']])
    return dict(cohort=[dict(life=p, survival={str(d): survival(p, d) for d in (1, 16, 32)}) for p in cohort],
                qualifying_pairs=pairs, reproducing_parents=sorted({p for p, c in pairs}),
                deepest_born_chain=max(depths.values(), default=0),
                deepest_16_day_chain=max(established_depths.values(), default=0),
                survival={str(d): dict(Counter(survival(p, d) for p in cohort)) for d in (1, 16, 32)},
                species=sorted({p['species'] for p in lives.values() if p['death_tick'] is None}),
                natural_deaths=[p for p in lives.values() if p['death_tick'] is not None and
                                p['death_tick'] > BASE and not p['environmental_death']],
                purchases=sum(s['birth_tick'] > BASE for s in seeds.values()),
                seed_fates=dict(Counter(s['outcome'] for s in seeds.values() if s['birth_tick'] > BASE)),
                final={k: result[k] for k in ('living', 'plant_slots', 'nodes', 'seed_bank')})


def account(paths, result):
    lives, seeds = index_records(result['lineages'], result['seeds'], 0, STOP)
    imposed = events(result)
    receipts, streams = {}, {}
    for kind in KINDS:
        receipts[kind] = dict(prefix_sha256=hashlib.sha256(), boundary=None)
        def rows(k=kind):
            for raw, data in followup.trace_rows(paths[k], k, STEP if k == 'reach' else BASE, STOP, result):
                if raw['tick'] <= BASE:
                    receipts[k]['prefix_sha256'].update(data)
                if raw['tick'] == BASE:
                    receipts[k]['boundary'] = fingerprint(raw)
                if raw['tick'] >= BASE:
                    yield raw
        streams[kind] = rows()
    try:
        return account_rows(streams, receipts, result, lives, seeds, imposed)
    finally:
        for stream in streams.values():
            stream.close()


def account_rows(streams, receipts, result, lives, seeds, imposed):
    previous_stores, totals, changes, daily, causes = {}, {}, [], [], {}
    last_slots = None
    for stand, adult, reach in zip(*streams.values(), strict=True):
        tick = stand['tick']
        climate, phase, sun = window.previous.sun_at(int(result['seed'], 16), tick)
        require(adult['tick'] == reach['tick'] == tick and stand['climate'] == climate and
                adult['sun'] == [phase, sun] and adult['cold'] == climate['cold'] and
                adult['season'] == climate['day'] // 4 and stand['seed_lifetime_ecology_ticks'] == 8192,
                'trace clocks/climate differ')
        require(all(p['id'] in lives and p['birth'] == lives[p['id']]['birth_tick'] for p in adult['plants']) and
                all(b['id'] in lives and b['species'] == lives[b['id']]['species'] for b in stand['bodies']) and
                all(set(v) == set(window.bank.FIELDS) for v in stand['reproduction']), 'trace plant identity differs')
        current_event = imposed.get(tick, dict(victims=[]))
        victims = {v['lineage']: v for v in current_event['victims']}
        observed = {i: dict(p, death_tick=None) if i in victims else p for i, p in lives.items()}
        checks = []
        for raw, check in zip(adult['seeds'], reach['checks'], strict=True):
            require(check[:4] == raw[:4] and check[4:6] == raw[8:10], 'seed observers disagree')
            checks.append([raw, check[6]])
        row = [tick, stand['plant_order'], [[v[k] for k in window.bank.FIELDS] for v in stand['reproduction']],
               [[p['id'], window.resources.pack(p)] for p in adult['plants']],
               [[b['id'], b['nodes'], b['roots'], b['flowers']] for b in stand['bodies']], checks,
               reach['purchases'], adult['bank']]
        window.check_row(row, tick, STOP, result, observed, seeds)
        for p in reach['purchases']:
            late.purchase_check(p, row[1], observed, seeds[p['parent'], tick], True)
        if last_slots is not None:
            change = window.prior.slot_change(last_slots, row[1], tick, lives)
            if change['removed'] or change['born']:
                changes.append(change)
        last_slots = row[1]
        bought = {p['parent'] for p in reach['purchases']}
        plants = {p['id']: p for p in adult['plants']}
        for identity, p in plants.items():
            transfers = window.adults.transfers(dict(p, tick=tick), observed[identity], previous_stores.get(identity))
            if tick == BASE:
                total = dict(samples=0, maintenance=0, shortfalls=0, **window.adults.budget())
                for j, name in enumerate(('energy', 'water')):
                    total[name].update(initial=p['stages'][-1][j], final=p['stages'][-1][j])
                totals[str(identity)] = total
            else:
                first = str(identity) not in totals
                total = totals.setdefault(str(identity), dict(samples=0, maintenance=0, shortfalls=0, **window.adults.budget()))
                window.adults.accumulate({k: total[k] for k in ('energy', 'water')}, transfers, first)
                for name, cost in (('energy', 48), ('water', 24)):
                    require(transfers[name]['reproduction'] == cost * (identity in bought), 'purchase debit differs')
                total['samples'] += 1
                if tick % 60 == 0 and tick != lives[identity]['birth_tick']:
                    total['maintenance'] += 1
                    total['shortfalls'] += bool(p['stages'][1][3] & 6)
                if observed[identity]['death_tick'] == tick:
                    causes[str(identity)] = {2: 'energy', 4: 'water', 6: 'combined'}[p['stages'][1][3] & 6]
            previous_stores[identity] = p['stages'][-1]
        for identity, victim in victims.items():
            final = plants[identity]['stages'][-1]
            require([victim['energy'], victim['water'], victim['nodes']] == [final[0], final[1], final[4]],
                    'imposed discard/body does not match pre-death observation')
            for name in ('energy', 'water'):
                totals[str(identity)][name]['discarded'] += victim[name]
                totals[str(identity)][name]['final'] = 0
            previous_stores.pop(identity)
        if tick % DAY == 0:
            daily.append(dict(tick=tick, stored=row[1], living=[b[0] for b in row[4] if b[0] not in victims], bank=adult['bank']))
    receipts = {k: dict(prefix_sha256=r['prefix_sha256'].hexdigest(), boundary=r['boundary']) for k, r in receipts.items()}
    require(set(causes) == {str(p['id']) for p in summary(result)['natural_deaths']}, 'natural cause coverage differs')
    for identity, life in lives.items():
        count = window.bank.samples(max(BASE + STEP, life['birth_tick']), min(STOP, life['death_tick'] or STOP))
        require(totals.get(str(identity), {}).get('samples', 0) == count, 'incomplete resource exposure')
    for name, cost in (('energy', 48), ('water', 24)):
        require(sum(t[name]['reproduction'] for t in totals.values()) == cost * summary(result)['purchases'], 'total fees differ')
        for total in totals.values():
            b = total[name]
            require(b['initial'] + b['income'] == sum(v for k, v in b.items() if k not in ('initial', 'income')),
                    'terminal resource account does not balance')
    value = dict(receipts=receipts, resources=totals, slot_changes=changes, daily=daily, natural_causes=causes)
    check_accounting(value, result)
    return value


def check_accounting(value, result):
    """Check portable ledger/conservation identities; raw verification replays every observed row."""
    lives, seeds = index_records(result['lineages'], result['seeds'], 0, STOP)
    victims = {v['lineage']: v for e in events(result).values() for v in e['victims']}
    expected = {str(i) for i, p in lives.items() if p['death_tick'] is None or p['death_tick'] >= BASE}
    require(set(value) == {'receipts', 'resources', 'slot_changes', 'daily', 'natural_causes'} and
            set(value['resources']) == expected and set(value['receipts']) == set(KINDS), 'missing portable accounts')
    for receipt in value['receipts'].values():
        require(set(receipt) == {'prefix_sha256', 'boundary'} and all(isinstance(v, str) and len(v) == 64 and
                len(bytes.fromhex(v)) == 32 for v in receipt.values()), 'invalid trace receipt')
    for identity, total in value['resources'].items():
        life = lives[int(identity)]
        stop = min(STOP, life['death_tick'] or STOP)
        start = max(BASE + STEP, life['birth_tick'])
        count = window.bank.samples(start, stop)
        maintenance = max(0, stop // 60 - max(BASE, life['birth_tick']) // 60)
        require(set(total) == {'samples', 'maintenance', 'shortfalls', 'energy', 'water'} and
                total['samples'] == count and total['maintenance'] == maintenance and
                type(total['shortfalls']) is int and 0 <= total['shortfalls'] <= maintenance,
                'resource exposure differs')
        purchases = sum(s['parent'] == int(identity) and s['birth_tick'] > BASE for s in seeds.values())
        for name, cost, cap in (('energy', 48, 256), ('water', 24, 512)):
            b = total[name]
            require(set(b) == set(window.adults.budget()[name]) and all(type(v) is int and v >= 0 for v in b.values()) and
                    b['initial'] <= cap and b['final'] <= cap and b['reproduction'] == cost * purchases and
                    b['initial'] + b['income'] == sum(v for k, v in b.items() if k not in ('initial', 'income')) and
                    (life['death_tick'] is None or b['final'] == 0), 'portable budget differs')
            if int(identity) in victims:
                require(b['discarded'] == victims[int(identity)][name], 'imposed discard differs')
            elif life['death_tick'] is None:
                require(b['discarded'] == 0, 'discard on surviving plant')
    require(set(value['natural_causes']) == {str(p['id']) for p in summary(result)['natural_deaths']} and
            set(value['natural_causes'].values()) <= {'energy', 'water', 'combined'}, 'cause census differs')
    require([d['tick'] for d in value['daily']] == list(range(BASE, STOP + DAY, DAY)), 'daily census gaps')
    slots = value['daily'][0]['stored']
    changes = iter(value['slot_changes'])
    next_change, last_tick = next(changes, None), BASE
    for day in value['daily']:
        tick = day['tick']
        while next_change is not None and next_change['tick'] <= tick:
            change_tick = next_change['tick']
            require(last_tick < change_tick <= STOP and change_tick % STEP == 0, 'slot change clock differs')
            after = [i for i in slots if i not in next_change['removed']] + next_change['born']
            require(window.prior.slot_change(slots, after, change_tick, lives) == next_change, 'slot transition differs')
            slots, last_tick, next_change = after, change_tick, next(changes, None)
        living = {i for i, p in lives.items() if p['birth_tick'] <= tick and (p['death_tick'] is None or p['death_tick'] > tick)}
        require(set(day) == {'tick', 'stored', 'living', 'bank'} and day['stored'] == slots and
                len(slots) == len(set(slots)) <= 8 and set(slots) <= set(lives) and living <= set(slots) and
                len(day['living']) == len(living) and set(day['living']) == living and
                all(lives[i]['birth_tick'] <= tick for i in slots) and day['bank'] == sum(
                    s['birth_tick'] <= tick < (s['end_tick'] or STOP + STEP) for s in seeds.values()), 'daily census differs')
    require(next_change is None and len(slots) == result['plant_slots'], 'final slot census differs')


def verdict(runs):
    improvements, regressions = [], []
    for key in inputs()[0]['panel']:
        control, treatment = (runs[p][key]['summary'] for p in ('control', 'treatment'))
        if len(treatment['qualifying_pairs']) > len(control['qualifying_pairs']):
            improvements.append(key)
        if control['final']['living'] and not treatment['final']['living']:
            regressions.append(key)
    return dict(improvements=improvements, empty_regressions=regressions,
                useful=len(improvements) >= 3 and not regressions)


def check_capture(value):
    saved, baseline = inputs()
    require(value['rule'] == RULE and value['protocol_sha256'] == PROTOCOL_SHA and
            value['input_sha256'] == INPUT_SHA and value['baseline_sha256'] == BASELINE_SHA and
            value['panel'] == saved['panel'] and value['model_sha256'] == saved['model_sha256'] and
            value['native_runs'] == 25 and value['training_runs'] == 0 and set(value['runs']) == set(PHASES) and
            value['analysis_sources'] == {p: digest(ROOT / p) for p in SOURCES}, 'capture provenance differs')
    require(set(value['builds']) == set(previous.capture.BUILDS) and
            all(v['settings'] == saved['builds'][a]['settings'] for a, v in value['builds'].items()), 'build settings differ')
    for phase in PHASES:
        require(set(value['runs'][phase]) == set(saved['panel']), 'missing sweep world')
        for key, run in value['runs'][phase].items():
            check_result(run['result'], key, phase)
            kinds = followup.KINDS if phase == 'baseline' else () if phase == 'plain' else KINDS
            require(run['args'] == arguments(key, phase) and run['directory'] == phase + '/' + key and
                    set(run['traces']) == set(kinds) and run['frame']['path'] == run['directory'] + '/' +
                    run['args'][run['args'].index('--framebuffer') + 1] and all(
                        v['path'] == run['directory'] + '/' + run['args'][run['args'].index('--' + k + '-trace') + 1] + '.gz'
                        for k, v in run['traces'].items()), 'wrong call/trace identity')
            if phase == 'baseline':
                late.same_run(run, baseline['runs']['extension'][key], followup.KINDS)
                continue
            require(run['summary'] == summary(run['result']), 'cohort summary differs')
            if phase != 'plain':
                check_accounting(run['accounting'], run['result'])
            if phase in ('treatment', 'repeat'):
                require(run['accounting']['receipts'] == value['runs']['control'][key]['accounting']['receipts'],
                        'pre-event observations changed')
            if phase in ('repeat', 'plain'):
                late.same_run(run, value['runs']['treatment'][key], () if phase == 'plain' else KINDS)
                require(phase == 'plain' or run['accounting'] == value['runs']['treatment'][key]['accounting'],
                        'repeat accounting differs')
    require(value['verdict'] == verdict(value['runs']) and value['receipt_sha256'] ==
            fingerprint({k: v for k, v in value.items() if k != 'receipt_sha256'}), 'verdict/receipt differs')


def collect(out, model, jobs):
    require(not out.exists() and not out.is_symlink() and 1 <= jobs <= 4 and
            shutil.disk_usage(out.parent).free >= 12 * 1024 ** 3, 'fresh output, 12 GiB free and 1..4 jobs required')
    saved, baseline = inputs()
    require(digest(model) == saved['model_sha256'], 'wrong frozen model')
    sources = source_files()
    runtime = {p: h for p, h in sources.items() if p.startswith(('src/', 'sim/')) and p.endswith(('.c', '.h'))}
    old = {p: h for p, h in saved['source_sha256'].items() if p.startswith(('src/', 'sim/')) and p.endswith(('.c', '.h'))}
    require({p for p in runtime.keys() | old.keys() if runtime.get(p) != old.get(p)} <= RUNTIME_DELTA,
            'unrelated runtime changed')
    out.mkdir(parents=True)
    (out / 'bin').mkdir()
    snapshot_sources(out, sources)
    shutil.copy2(ROOT / PROTOCOL, out / 'protocol.md')
    shutil.copy2(model, out / 'model.tgl')
    value = dict(rule=RULE, protocol_sha256=PROTOCOL_SHA, input_sha256=INPUT_SHA, baseline_sha256=BASELINE_SHA,
                 panel=saved['panel'], model_sha256=saved['model_sha256'], native_runs=25, training_runs=0,
                 source_sha256=sources, analysis_sources={p: sources[p] for p in SOURCES}, builds={}, runs={})
    for arm, build in previous.capture.BUILDS.items():
        binary, config = ROOT / build / 'toy-factory-garden-landing', ROOT / build / 'CMakeCache.txt'
        settings = late.settings_at(config, arm)
        require(settings == saved['builds'][arm]['settings'], 'changed experimental build')
        value['builds'][arm] = dict(binary=digest(binary), cache=digest(config), settings=settings)
        shutil.copy2(binary, out / ('bin/' + arm))
        shutil.copy2(config, out / (arm + '-CMakeCache.txt'))
    write_json(out / 'started.json', value)

    def call(key, phase):
        args, directory = arguments(key, phase), out / phase / key
        directory.mkdir(parents=True)
        (directory / 'frames').mkdir()
        shutil.copy2(out / 'model.tgl', directory / 'model.tgl')
        result = native(out / ('bin/' + saved['panel'][key]['arm']), directory, *args)
        write_json(directory / 'result.json', result)
        check_result(result, key, phase)
        run = dict(args=args, directory=str(directory.relative_to(out)), result=result, traces={})
        kinds = followup.KINDS if phase == 'baseline' else () if phase == 'plain' else KINDS
        paths = {}
        for kind in kinds:
            name = args[args.index('--' + kind + '-trace') + 1]
            path = directory / (name + '.gz')
            compress(directory / name, path)
            paths[kind] = path
            run['traces'][kind] = dict(path=str(path.relative_to(out)), sha256=digest(path))
        frame = directory / args[args.index('--framebuffer') + 1]
        require(len(frame.read_bytes()) == 115200 and f'{zlib.crc32(frame.read_bytes()):08x}' == result['framebuffer_crc32'],
                'frame/renderer mismatch')
        run['frame'] = dict(path=str(frame.relative_to(out)), sha256=digest(frame))
        if phase == 'baseline':
            late.same_run(run, baseline['runs']['extension'][key], followup.KINDS)
        else:
            run['summary'] = summary(result)
            if phase != 'plain':
                run['accounting'] = account(paths, result)
            if phase in ('treatment', 'repeat'):
                require(run['accounting']['receipts'] == value['runs']['control'][key]['accounting']['receipts'],
                        'changed pre-event prefix')
            if phase in ('repeat', 'plain'):
                late.same_run(run, value['runs']['treatment'][key], () if phase == 'plain' else KINDS)
                require(phase == 'plain' or run['accounting'] == value['runs']['treatment'][key]['accounting'], 'repeat accounting differs')
        write_json(directory / 'run.json', run)
        print(phase + ': ' + key + ' verified', flush=True)
        return key, run

    for phase in PHASES:
        # Do not queue another batch until every current run has verified. On a
        # failure, retain any already-running peer's evidence but launch no more.
        value['runs'][phase] = {}
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            keys = sorted(saved['panel'])
            for start in range(0, len(keys), jobs):
                tasks = [pool.submit(call, key, phase) for key in keys[start:start + jobs]]
                value['runs'][phase].update(t.result() for t in tasks)
        write_json(out / (phase + '.json'), value['runs'][phase])
    groups = [[dict(id=p + '/' + key, framebuffer=value['runs'][p][key]['frame']['path'])
               for p in ('control', 'treatment')] for key in sorted(saved['panel'])]
    value['gallery'] = contact_sheet(out, groups)
    value['gallery']['sha256'] = digest(out / 'contact-sheet.png')
    value['verdict'] = verdict(value['runs'])
    require(all(digest(ROOT / p) == sources[p] for p in (*runtime, *SOURCES, PROTOCOL)), 'sources changed during capture')
    require(all(digest(out / ('bin/' + a)) == b['binary'] and digest(out / (a + '-CMakeCache.txt')) == b['cache']
                for a, b in value['builds'].items()), 'captured executables/configs changed')
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
            digest(root / 'model.tgl') == value['model_sha256'], 'raw provenance differs')
    for path, sha in manifest['artifacts'].items():
        followup.artifact(root, dict(path=path, sha256=sha))
    require(digest(root / 'protocol.md') == PROTOCOL_SHA and
            all(digest(root / ('bin/' + a)) == b['binary'] and digest(root / (a + '-CMakeCache.txt')) == b['cache']
                for a, b in value['builds'].items()), 'raw protocol/builds differ')
    for phase in PHASES:
        for run in value['runs'][phase].values():
            frame = followup.artifact(root, run['frame']).read_bytes()
            require(len(frame) == 115200 and f'{zlib.crc32(frame):08x}' == run['result']['framebuffer_crc32'],
                    'raw frame/renderer mismatch')
            for trace in run['traces'].values():
                followup.artifact(root, trace)
    for phase in ('control', 'treatment', 'repeat'):
        for key, run in value['runs'][phase].items():
            paths = {k: followup.artifact(root, v) for k, v in run['traces'].items()}
            require(account(paths, run['result']) == run['accounting'], 'raw resource/seed accounts differ')
            print('offline verified: ' + phase + '/' + key, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--collect', type=Path)
    mode.add_argument('--verify', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--model', type=Path, default=ROOT / 'artifacts/garden-landing-seed-replacement-v1/model.tgl')
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    require(bool(args.out) == bool(args.collect) and not (args.bundle and args.collect), 'invalid output/mode')
    if args.collect:
        require(not args.out.exists() and not args.out.is_symlink() and not args.collect.is_symlink(), 'fresh output required')
        value = collect(args.collect.resolve(), args.model.resolve(), args.jobs)
        write_gzip(args.out, value)
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
