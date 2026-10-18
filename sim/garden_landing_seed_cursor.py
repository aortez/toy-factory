#!/usr/bin/env python3
"""Purchase-driven seed priority: frozen six-pair comparison, never training."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from functools import cache
import argparse
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import zlib

import garden_landing_patch_followup as previous
from garden_resources import require

sweep, window = previous.sweep, previous.sweep.window
ROOT, DAY, STEP = previous.ROOT, previous.DAY, previous.STEP
BASE, BIRTH_STOP, STOP = 320 * DAY, 352 * DAY, 384 * DAY
RULE = 'garden-landing-seed-cursor-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-seed-cursor-protocol.md'
PROTOCOL_SHA = '2f7bf234855e366065a453ee713ef01a032637fee66165f01d9fe1afe5ccc2ae'
INPUT = 'benchmarks/garden-seasons/landing-patch-followup-results.json.gz'
INPUT_SHA = '467a2fefbb238689999fd97f0f6de78b2c7558bb3b1e4833e19d90ae76a57083'
ORIGIN_MANIFEST = 'fad8f7bfd1f59e3a70830d8c03d640c40b91065d3ddfef1f001f82b5e9bbc38e'
PHASES = ('anchor-cursor', 'anchor-fixed', 'fixed', 'cursor', 'repeat', 'plain')
SOURCES = tuple(sorted({*previous.SOURCES, 'sim/garden_landing_seed_cursor.py',
                        'sim/test_garden_landing_seed_cursor.py'}))
RUNTIME_DELTA = {'src/garden_agent.h', 'src/garden_world.c', 'sim/garden_landing_growth.h',
                 'sim/garden_landing_growth.c', 'sim/garden_landing_run_internal.h',
                 'sim/garden_landing_run.c', 'sim/garden_landing_cli.c',
                 'sim/garden_landing_seed_cursor_test.c'}


@cache
def prior():
    require(sweep.digest(ROOT / INPUT) == INPUT_SHA and sweep.digest(ROOT / PROTOCOL) == PROTOCOL_SHA,
            'cursor input/protocol changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream:
        value = json.load(stream)
    previous.check_capture(value)
    return value


def horizon(phase):
    return BASE if phase == 'anchor-cursor' else BIRTH_STOP if phase == 'anchor-fixed' else STOP


def active(phase):
    return phase not in ('anchor-fixed', 'fixed')


def arguments(key, phase):
    require(phase in PHASES and key in previous.confirm.panel(), 'unknown cursor call')
    args = previous.arguments(key, 'plain' if phase == 'plain' else 'treatment')
    for flag in ('--ticks', '--stand-stop', '--adult-stop'):
        if flag in args:
            args[args.index(flag) + 1] = str(horizon(phase))
    for flag in ('--stand-start', '--adult-start'):
        if flag in args:
            args[args.index(flag) + 1] = str(BASE)
    if active(phase):
        args += ['--seed-cursor-after', str(BASE)]
    return args


def tagged(base, after=BASE, last=0):
    h = 2166136261
    for b in b'GSC1' + b''.join(n.to_bytes(4, 'little') for n in (int(base, 16), after, last)):
        h = ((h ^ b) * 16777619) & 0xffffffff
    return f'{h:08x}'


def anchor_identity(original):
    """Only the explicitly added run identity differs before activation."""
    expected = copy.deepcopy(original)
    expected['seed_cursor_probe'] = dict(version=1, after=BASE, last_buyer=0)
    expected['placement_run_hash'] = tagged(original['placement_run_hash'])
    expected['run_hash'] = sweep.tagged(expected['placement_run_hash'])
    for event in expected['patch_sweep_probe']['events']:
        for field in ('before_run_hash', 'after_run_hash'):
            event[field] = tagged(event[field])
    return expected


def check_result(result, key, phase):
    anchor = prior()['runs']['anchor-treatment'][key]['result']
    if phase == 'anchor-cursor':
        require(result == anchor_identity(anchor), 'day-320 cursor anchor changed')
        return
    if phase == 'anchor-fixed':
        require(result == prior()['runs']['treatment'][key]['result'], 'day-352 fixed anchor changed')
        return
    reference = anchor_identity(anchor) if active(phase) else anchor
    require(set(result) == set(reference) and result['tick'] == STOP, 'wrong result schema/horizon')
    for field in ('schema_version', 'kind', 'run_version', 'rules', 'scenario', 'seed', 'model',
                  'gardener', 'irrigation', 'seed_lifetime_ecology_ticks', 'ledger_start_tick',
                  'warmup_samples', *(k for k in anchor if k.endswith('_probe'))):
        require(result[field] == reference[field], 'changed setting/history: ' + field)
    if active(phase):
        probe = result['seed_cursor_probe']
        require(set(probe) == {'version', 'after', 'last_buyer'} and probe['version'] == 1 and
                probe['after'] == BASE and type(probe['last_buyer']) is int and
                0 <= probe['last_buyer'] <= max(p['id'] for p in result['lineages']), 'wrong cursor identity')
    lives, seeds = sweep.index_records(result['lineages'], result['seeds'], 0, STOP)
    require(sweep.prefix(result, BASE) == (anchor['lineages'], anchor['seeds']), 'day-320 ledger prefix changed')
    require(result['births'] == sum(p['parent'] != 0 for p in lives.values()) and
            result['deaths'] == sum(p['death_tick'] is not None for p in lives.values()) and
            result['living'] == len(lives) - result['deaths'] and
            result['seed_bank'] == sum(s['outcome'] == 'pending' for s in seeds.values()) and
            0 <= result['living'] <= result['plant_slots'] <= 8 and 0 <= result['nodes'] <= 256 and
            0 <= result['seed_bank'] <= 8 and
            result['run_hash'] == sweep.tagged(result['placement_run_hash']) and
            result['climate'] == sweep.followup.previous.climate(int(result['seed'], 16), STOP),
            'ledger/capacity/identity differs')
    sweep.events(result)


def scan(path, kind, result, receipt, trace_start=BASE):
    """Authenticate restored bytes while decoding only the comparison window."""
    start, stop = STEP if kind == 'reach' else trace_start, result['tick']
    schemas = dict(stand='landing-dawn-stand-trace-v1', adult='landing-adult-resources-v1',
                   reach='landing-reach-trace-v1')
    header = dict(schema=schemas[kind])
    if kind != 'reach':
        header.update(start=start, stop=stop)
    if kind == 'stand':
        header.update(node_limit=32, budget_mode=2)
    footer = dict(complete=True, tick=stop)
    if kind == 'stand':
        footer['run_hash'] = result['run_hash']
    whole, prefix, segment, restored = (hashlib.sha256() for _ in range(4))
    size, boundary = 0, None
    with gzip.open(path, 'rb') as stream:
        def line():
            nonlocal size
            raw = stream.readline()
            require(raw.endswith(b'\n'), 'truncated trace line')
            restored.update(raw)
            size += len(raw)
            return raw
        require(json.loads(line()) == header, 'wrong trace header')
        for tick in range(start, stop + STEP, STEP):
            raw = line()
            whole.update(raw)
            if tick <= BASE:
                prefix.update(raw)
            if BASE <= tick <= BIRTH_STOP:
                segment.update(raw)
            if tick < BASE:
                continue
            row = json.loads(raw)
            require(type(row.get('tick')) is int and row['tick'] == tick, 'trace clock differs')
            if tick == BASE:
                boundary = sweep.fingerprint(row)
            yield row
        require(json.loads(line()) == footer and not stream.read(), 'wrong footer/trailing trace')
    receipt.update(rows_sha256=whole.hexdigest(), prefix_sha256=prefix.hexdigest(),
                   segment_sha256=segment.hexdigest(), boundary_sha256=boundary,
                   raw_sha256=restored.hexdigest(), raw_bytes=size)


def extract(paths, result, trace_start=BASE):
    receipts = {k: {} for k in sweep.KINDS}
    streams = {k: scan(paths[k], k, result, receipts[k], trace_start) for k in sweep.KINDS}
    lives = {p['id']: p for p in result['lineages']}
    evidence = []
    try:
        for stand, adult, reach in zip(*streams.values(), strict=True):
            tick = stand['tick']
            climate, phase, strength = window.previous.sun_at(int(result['seed'], 16), tick)
            require(adult['tick'] == reach['tick'] == tick and stand['climate'] == climate and
                    adult['sun'] == [phase, strength] and adult['cold'] == climate['cold'] and
                    adult['season'] == climate['day'] // 4 and stand['seed_lifetime_ecology_ticks'] == 8192,
                    'observer clocks/climate differ')
            require(all(p['id'] in lives and p['birth'] == lives[p['id']]['birth_tick'] for p in adult['plants']) and
                    all(b['id'] in lives and b['species'] == lives[b['id']]['species'] for b in stand['bodies']) and
                    all(set(v) == set(window.bank.FIELDS) for v in stand['reproduction']), 'observer identities differ')
            checks = []
            for raw, check in zip(adult['seeds'], reach['checks'], strict=True):
                require(len(check) == 7 and check[:4] == raw[:4] and check[4:6] == raw[8:10],
                        'adult/reach checks disagree')
                checks.append([raw, check[6]])
            evidence.append([tick, stand['plant_order'], [[v[k] for k in window.bank.FIELDS]
                             for v in stand['reproduction']],
                             [[p['id'], window.resources.pack(p)] for p in adult['plants']],
                             [[b['id'], b['nodes'], b['roots'], b['flowers']] for b in stand['bodies']],
                             checks, reach['purchases'], adult['bank']])
    finally:
        for stream in streams.values():
            stream.close()
    require(all(receipts.values()), 'incomplete trace receipts')
    return evidence, receipts


def visit_order(tick, slots, visits, lives, enabled, last):
    require(len(slots) == len(set(slots)) <= 8 and all(i in lives for i in slots), 'invalid stored order')
    expected = list(slots)
    if enabled and tick > BASE and tick % 60 == 0:
        living = [i for i in slots if lives[i]['death_tick'] is None or lives[i]['death_tick'] > tick]
        following = [i for i in living if i > last]
        if living:
            start = slots.index(min(following or living))
            expected = slots[start:] + slots[:start]
    require([v[0] for v in visits] == expected, 'purchase cursor traversal differs')
    if enabled and tick > BASE and tick % 60 == 0:
        for visit in visits:
            if visit[-1]:
                last = visit[0]
    return last


def analyze(evidence, result, enabled):
    stop = result['tick']
    require([r[0] for r in evidence] == list(range(BASE, stop + STEP, STEP)), 'incomplete observation window')
    lives, seeds = sweep.index_records(result['lineages'], result['seeds'], 0, stop)
    last, before, old_slots = 0, {}, None
    totals, occupancy, changes, cursor_events, seed_counts = {}, Counter(), [], [], Counter()
    visits_for_bank = []
    for row in evidence:
        tick, slots, visits, packed, bodies, checks, purchases, bank = row
        prior_buyer = last
        last = visit_order(tick, slots, visits, lives, enabled, last)
        living = {i for i, p in lives.items() if p['birth_tick'] <= tick and
                  (p['death_tick'] is None or p['death_tick'] > tick)}
        plants, shapes = dict(packed), {b[0]: b[1:] for b in bodies}
        require(living <= set(slots) and all(lives[i]['birth_tick'] <= tick for i in slots) and
                len(plants) == len(packed) and len(shapes) == len(bodies) and set(shapes) == living and
                set(plants) == living | {i for i, p in lives.items() if p['death_tick'] == tick},
                'resource/body census differs')
        climate, phase, strength = window.previous.sun_at(int(result['seed'], 16), tick)
        require(all(len(v) == len(window.bank.FIELDS) and v[window.bank.FIELDS.index('sun')] == strength
                    for v in visits), 'wrong visit sunlight')
        inventory = window.check_inventory(checks, purchases, bank, tick, stop, slots, lives, seeds, climate['cold'])
        for purchase in purchases:
            sweep.late.purchase_check(purchase, slots, lives, seeds[purchase['parent'], tick], True)
        if old_slots is not None and slots != old_slots:
            changes.append(window.prior.slot_change(old_slots, slots, tick, lives))
        old_slots = slots
        indexed = {v[0]: dict(zip(window.bank.FIELDS, v, strict=True)) for v in visits}
        for i, packed_plant in plants.items():
            plant = window.resources.unpack(packed_plant, lives[i], tick)
            prior_stage = before[i][0][-1] if i in before else None
            if i in shapes:
                transfer, _ = window.previous.check_focal_sample(indexed[i], shapes[i], packed_plant,
                                                                 lives[i], tick, prior_stage)
            else:
                transfer = window.adults.transfers(plant, lives[i], prior_stage)
                require(not indexed[i]['produced'], 'dead plant purchased seed')
            if tick == BASE:
                continue
            record = totals.setdefault(str(i), dict(samples=0, budget=window.adults.budget(),
                                                    payments=0, shortfalls=[], max_stress=0))
            window.adults.accumulate(record['budget'], transfer, record['samples'] == 0)
            record['samples'] += 1
            record['max_stress'] = max(record['max_stress'], *(s[2] for s in packed_plant[0] if s is not None))
            pay = window.population.payment(plant, transfer, before[i][2] if i in before else None, tick, phase)
            if pay:
                record['payments'] += 1
                if any(pay[r]['unpaid'] for r in ('energy', 'water')):
                    record['shortfalls'].append(pay)
        before = plants
        if tick == BASE:
            continue
        occupancy[f'{len(living)}/{len(slots)}'] += 1
        visits_for_bank.append([tick, visits])
        seed_counts.update(inventory.keys())
        if purchases:
            buyers = [v[0] for v in visits if v[-1]]
            require(buyers == [p['parent'] for p in purchases], 'purchase observer order differs')
            cursor_events.append(dict(tick=tick, before=prior_buyer, buyers=buyers, after=last))
    require(last == (result['seed_cursor_probe']['last_buyer'] if enabled else 0), 'final cursor differs')
    for i, life in lives.items():
        samples = window.bank.samples(max(BASE + STEP, life['birth_tick']), min(stop, life['death_tick'] or stop))
        record = totals.get(str(i))
        require((record['samples'] if record else 0) == samples, 'missing plant history')
        if record:
            bought = sum(s['parent'] == i and s['birth_tick'] > BASE for s in seeds.values())
            require(record['budget']['energy']['reproduction'] == 48 * bought and
                    record['budget']['water']['reproduction'] == 24 * bought, 'purchase costs differ')
    for key, seed in seeds.items():
        samples = window.bank.samples(max(BASE + STEP, seed['birth_tick'] + STEP), min(stop, seed['end_tick'] or stop))
        require(seed_counts[key] == samples, 'missing sequential seed admission')
    access = window.bank.analyze_visits(visits_for_bank, result, BASE + STEP, stop) if stop > BASE else None
    return dict(cursor_events=cursor_events, last_buyer=last, plants=totals,
                resource_exposure=window.prior.exposure(list(totals.values())),
                occupancy=dict(occupancy), changes=changes, access=access)


def outcomes(result):
    lives, stop = result['lineages'], result['tick']
    born = [p for p in lives if BASE < p['birth_tick'] <= BIRTH_STOP]
    cohort = [dict(life=p, survival={str(d): sweep.survival(p, d, stop) for d in (16, 32)}) for p in born]
    survivors = {str(d): [r['life']['id'] for r in cohort if r['survival'][str(d)] == 'confirmed'] for d in (16, 32)}
    new = [p for p in lives if p['birth_tick'] > BASE]
    seeds = [s for s in result['seeds'] if s['birth_tick'] > BASE]
    deaths = [p for p in lives if p['death_tick'] is not None and p['death_tick'] > BASE]
    return dict(cohort=cohort, survivors=survivors,
                established_parents={str(d): sorted({p['parent'] for p in born if p['id'] in survivors[str(d)]})
                                     for d in (16, 32)},
                established_pairs={str(d): [[p['parent'], p['id']] for p in born if p['id'] in survivors[str(d)]]
                                   for d in (16, 32)},
                new_births=new, late_births=[p for p in new if p['birth_tick'] > BIRTH_STOP],
                deaths=deaths, old_deaths=[p['id'] for p in deaths if p['birth_tick'] <= BASE],
                young_deaths=[p['id'] for p in deaths if p['death_tick'] - p['birth_tick'] < 16 * DAY],
                purchases=len(seeds), buying_parents=sorted({s['parent'] for s in seeds}),
                seed_fates=dict(Counter(s['outcome'] for s in seeds)),
                species=dict(Counter(str(p['species']) for p in lives if p['death_tick'] is None)),
                endpoint={k: result[k] for k in ('living', 'plant_slots', 'nodes', 'seed_bank')})


def check_audit_summary(audit, result, enabled):
    """Portable arithmetic checks; full traversal/resource proof needs the bundle."""
    stop = result['tick']
    lives, seeds = sweep.index_records(result['lineages'], result['seeds'], 0, stop)
    require(set(audit) == {'cursor_events', 'last_buyer', 'plants', 'resource_exposure',
                           'occupancy', 'changes', 'access'}, 'wrong audit fields')
    require(sum(audit['occupancy'].values()) == (stop - BASE) // STEP and
            all(type(n) is int and n > 0 and 0 <= int(k.split('/')[0]) <= int(k.split('/')[1]) <= 8
                for k, n in audit['occupancy'].items()), 'wrong occupancy exposure')
    expected_plants = {str(i) for i, p in lives.items() if window.bank.samples(
        max(BASE + STEP, p['birth_tick']), min(stop, p['death_tick'] or stop)) > 0}
    require(set(audit['plants']) == expected_plants, 'missing audited plant')
    for i, record in audit['plants'].items():
        life = lives[int(i)]
        require(record['samples'] == window.bank.samples(max(BASE + STEP, life['birth_tick']),
                    min(stop, life['death_tick'] or stop)) and
                0 <= len(record['shortfalls']) <= record['payments'] <= record['samples'] and
                0 <= record['max_stress'] <= 8, 'wrong resource exposure')
        purchases = sum(s['parent'] == int(i) and s['birth_tick'] > BASE for s in seeds.values())
        for resource, cost in (('energy', 48), ('water', 24)):
            b = record['budget'][resource]
            require(set(b) == set(window.adults.FIELDS) and all(type(n) is int and n >= 0 for n in b.values()) and
                    b['initial'] + b['income'] == sum(b[k] for k in b if k not in ('initial', 'income')) and
                    b['reproduction'] == cost * purchases, 'wrong budget/fees')
    require(audit['resource_exposure'] == window.prior.exposure(list(audit['plants'].values())), 'wrong total exposure')
    last, seen = 0, []
    for event in audit['cursor_events']:
        tick, buyers = event['tick'], event['buyers']
        require(set(event) == {'tick', 'before', 'buyers', 'after'} and type(tick) is int and
                BASE < tick <= stop and tick % 60 == 0 and buyers and len(buyers) == len(set(buyers)) and
                set(buyers) == {s['parent'] for s in seeds.values() if s['birth_tick'] == tick} and
                (not seen or tick > seen[-1][1]) and event['before'] == last,
                'wrong purchase/cursor event')
        last = buyers[-1] if enabled else 0
        require(event['after'] == last, 'wrong cursor advancement')
        seen.extend((i, tick) for i in buyers)
    require(set(seen) == {k for k, s in seeds.items() if s['birth_tick'] > BASE} and
            audit['last_buyer'] == last == (result['seed_cursor_probe']['last_buyer'] if enabled else 0),
            'missing purchase/final cursor')
    if stop == BASE:
        require(audit['access'] is None, 'bank tail on anchor')
    else:
        require(audit['access']['bank']['purchases'] == len(seen) and
                audit['access']['bank']['final'] == result['seed_bank'], 'bank summary differs')


def decision(runs):
    pairs = {}
    for key in previous.confirm.panel():
        a, b = (outcomes(runs[p][key]['result']) for p in ('fixed', 'cursor'))
        pairs[key] = dict(delta={str(d): len(b['survivors'][str(d)]) - len(a['survivors'][str(d)]) for d in (16, 32)},
                          extra_old_deaths=sorted(set(b['old_deaths']) - set(a['old_deaths'])),
                          lost_species=sorted(set(a['species']) - set(b['species'])),
                          extra_empty=b['endpoint']['living'] == 0 < a['endpoint']['living'])
    improved = sum(p['delta']['16'] > 0 for p in pairs.values())
    passed = improved >= 2 and all(p['delta']['16'] >= 0 and not p['extra_old_deaths'] and
                                  not p['lost_species'] and not p['extra_empty'] for p in pairs.values())
    return dict(pairs=pairs, improved_pairs=improved, passes_diagnostic=passed, qualifies_environment=False)


def check_run(run, key, phase, runs, reference):
    require(run['args'] == arguments(key, phase) and run['directory'] == phase + '/' + key and
            set(run) == {'args', 'directory', 'result', 'traces', 'receipts', 'frame', 'outcomes', 'audit'}, 'wrong run fields')
    check_result(run['result'], key, phase)
    require(run['outcomes'] == outcomes(run['result']) and
            run['frame']['path'] == run['directory'] + '/frames/end.raw', 'wrong outcome/frame')
    kinds = () if phase == 'plain' else sweep.KINDS
    require(set(run['traces']) == set(run['receipts']) == set(kinds) and
            (run['audit'] is None) == (phase == 'plain'), 'wrong observer coverage')
    if phase != 'plain':
        check_audit_summary(run['audit'], run['result'], active(phase))
    for kind in kinds:
        meta, receipt = run['traces'][kind], run['receipts'][kind]
        require(set(meta) == {'path', 'sha256', 'raw_sha256', 'raw_bytes'} and
                meta['path'] == run['directory'] + '/' + kind + '.jsonl.gz' and
                all(meta[k] == receipt[k] for k in ('raw_sha256', 'raw_bytes')), 'trace receipt differs')
        require(receipt['boundary_sha256'] == reference[key][kind]['boundary_sha256'] and
                (kind != 'reach' or receipt['prefix_sha256'] == reference[key][kind]['prefix_sha256']),
                'day-320 observations changed')
        if phase in ('anchor-fixed', 'fixed'):
            require(receipt['segment_sha256'] == reference[key][kind]['segment_sha256'], 'fixed day-352 prefix changed')
    if phase == 'anchor-cursor':
        require(run['frame']['sha256'] == prior()['runs']['anchor-treatment'][key]['frame']['sha256'], 'anchor pixels changed')
    if phase == 'anchor-fixed':
        require(run['frame']['sha256'] == prior()['runs']['treatment'][key]['frame']['sha256'], 'fixed pixels changed')
    if phase in ('repeat', 'plain'):
        other = runs['cursor'][key]
        sweep.late.same_run(run, other, kinds)
        require(phase == 'plain' or (run['receipts'], run['audit']) == (other['receipts'], other['audit']),
                'repeat audit differs')


def origin_inputs(origin):
    require(sweep.digest(origin / 'manifest.json') == ORIGIN_MANIFEST, 'origin manifest changed')
    manifest = json.loads((origin / 'manifest.json').read_text())['artifacts']
    require(sweep.digest(origin / 'model.tgl') == prior()['model_sha256'] == manifest['model.tgl'], 'model changed')
    reference = {}
    for key in previous.confirm.panel():
        old = prior()['runs']['treatment'][key]
        reference[key] = {}
        for kind, meta in old['traces'].items():
            require(manifest[meta['path']] == meta['sha256'], 'origin trace manifest differs')
            path = sweep.followup.artifact(origin, meta)
            receipt = {}
            for _ in scan(path, kind, old['result'], receipt, sweep.BASE):
                pass
            require(all(receipt[k] == meta[k] for k in ('raw_sha256', 'raw_bytes')) and
                    all(receipt[k] == old['receipts'][kind][k] for k in ('prefix_sha256', 'boundary_sha256')),
                    'origin trace bytes changed')
            reference[key][kind] = receipt
    return reference


def call(out, value, key, phase):
    name, args = phase + '/' + key, arguments(key, phase)
    directory = out / name
    (directory / 'frames').mkdir(parents=True)
    shutil.copy2(out / 'model.tgl', directory / 'model.tgl')
    previous.write_receipt(directory / 'started.json', dict(args=args, phase=phase, key=key))
    result = sweep.native(out / 'bin/garden-landing', directory, *args)
    previous.write_receipt(directory / 'result.json', result)
    check_result(result, key, phase)
    run = dict(args=args, directory=name, result=result, traces={}, receipts={}, outcomes=outcomes(result), audit=None)
    raw_paths = []
    for kind in (() if phase == 'plain' else sweep.KINDS):
        raw = directory / (kind + '.jsonl')
        packed = raw.with_suffix('.jsonl.gz')
        metadata = previous.compressed_trace(raw, packed)
        run['traces'][kind] = dict(path=str(packed.relative_to(out)), sha256=sweep.digest(packed), **metadata)
        raw_paths.append(raw)
    if phase != 'plain':
        evidence, run['receipts'] = extract({k: out / v['path'] for k, v in run['traces'].items()}, result)
        run['audit'] = analyze(evidence, result, active(phase))
    frame = directory / 'frames/end.raw'
    data = frame.read_bytes()
    require(len(data) == 115200 and f'{zlib.crc32(data):08x}' == result['framebuffer_crc32'], 'frame CRC differs')
    run['frame'] = dict(path=str(frame.relative_to(out)), sha256=sweep.digest(frame))
    check_run(run, key, phase, value['runs'], value['reference'])
    previous.write_receipt(directory / 'run.json', run)
    # Remove only these freshly generated, verified duplicates after the durable
    # receipt. Compressed bytes and restoration identities remain in the bundle.
    for raw in raw_paths:
        require(not raw.is_symlink() and sweep.digest(raw) == run['traces'][raw.stem]['raw_sha256'],
                'raw trace changed before compaction')
        with raw.with_suffix('.jsonl.gz').open('rb') as stream:
            os.fsync(stream.fileno())
        raw.unlink()
    print('verified: ' + name, flush=True)
    return key, run


def groups(value):
    return [[dict(id=p + '/' + k, framebuffer=value['runs'][p][k]['frame']['path'])
             for p in ('fixed', 'cursor')] for k in previous.confirm.panel()]


def check_capture(value):
    old = prior()
    require(value['rule'] == RULE and value['protocol_sha256'] == PROTOCOL_SHA and value['input_sha256'] == INPUT_SHA and
            value['origin_manifest_sha256'] == ORIGIN_MANIFEST and value['native_runs'] == 36 and value['training_runs'] == 0 and
            value['panel'] == previous.confirm.panel() and value['model_sha256'] == old['model_sha256'] and
            value['build']['settings'] == old['build']['settings'] and
            value['analysis_sources'] == {p: sweep.digest(ROOT / p) for p in SOURCES}, 'wrong cursor provenance')
    sources, original = previous.confirm.runtime(value['source_sha256']), previous.confirm.runtime(old['source_sha256'])
    require({p for p in sources.keys() | original.keys() if sources.get(p) != original.get(p)} == RUNTIME_DELTA and
            value['source_sha256'][PROTOCOL] == PROTOCOL_SHA and value['source_sha256'][INPUT] == INPUT_SHA and
            all(value['source_sha256'][p] == sha for p, sha in value['analysis_sources'].items()), 'unrelated source change')
    require(set(value['runs']) == set(PHASES) and set(value['reference']) == set(previous.confirm.panel()), 'missing phase/reference')
    for phase in PHASES:
        require(set(value['runs'][phase]) == set(previous.confirm.panel()), 'missing paired case')
        for key, run in value['runs'][phase].items():
            check_run(run, key, phase, value['runs'], value['reference'])
    require(value['decision'] == decision(value['runs']) and
            value['gallery']['rows'] == [[f['id'] for f in row] for row in groups(value)] and
            (value['gallery']['width'], value['gallery']['height'], value['gallery']['gap']) == (504, 1496, 8) and
            value['receipt_sha256'] == sweep.fingerprint({k: v for k, v in value.items() if k != 'receipt_sha256'}),
            'decision/gallery/receipt differs')


def collect(out, output, origin, build, jobs):
    previous.confirm.fresh(out, output)
    require(1 <= jobs <= 2 and shutil.disk_usage(out.parent).free >= 4 * 1024 ** 3, 'need 4 GiB free and 1..2 jobs')
    old, reference = prior(), origin_inputs(origin)
    sources = sweep.source_files()
    original, current = previous.confirm.runtime(old['source_sha256']), previous.confirm.runtime(sources)
    require({p for p in original.keys() | current.keys() if original.get(p) != current.get(p)} == RUNTIME_DELTA,
            'unrelated runtime changes')
    settings = sweep.late.settings_at(build / 'CMakeCache.txt', previous.confirm.ARM)
    require(settings == old['build']['settings'], 'build options changed')
    out.mkdir(parents=True)
    (out / 'bin').mkdir()
    sweep.snapshot_sources(out, sources)
    shutil.copy2(ROOT / PROTOCOL, out / 'protocol.md')
    for src, dest in ((origin / 'model.tgl', 'model.tgl'), (build / 'toy-factory-garden-landing', 'bin/garden-landing'),
                      (build / 'CMakeCache.txt', 'CMakeCache.txt')):
        shutil.copy2(src, out / dest)
    value = dict(rule=RULE, protocol_sha256=PROTOCOL_SHA, input_sha256=INPUT_SHA, origin_manifest_sha256=ORIGIN_MANIFEST,
                 native_runs=36, training_runs=0, panel=previous.confirm.panel(), source_sha256=sources,
                 analysis_sources={p: sources[p] for p in SOURCES}, model_sha256=old['model_sha256'],
                 reference=reference, build=dict(binary=sweep.digest(out / 'bin/garden-landing'),
                     cache=sweep.digest(out / 'CMakeCache.txt'), settings=settings), runs={})
    previous.write_receipt(out / 'started.json', value)
    try:
        for phase in PHASES:
            value['runs'][phase] = {}
            keys = list(previous.confirm.panel())
            with ThreadPoolExecutor(max_workers=jobs) as pool:
                for start in range(0, len(keys), jobs):
                    require(shutil.disk_usage(out).free >= 3 * 1024 ** 3, 'low disk space; evidence retained')
                    tasks = [pool.submit(call, out, value, k, phase) for k in keys[start:start + jobs]]
                    value['runs'][phase].update(task.result() for task in tasks)
            previous.write_receipt(out / (phase + '.json'), value['runs'][phase])
        value['decision'] = decision(value['runs'])
        value['gallery'] = sweep.contact_sheet(out, groups(value))
        value['gallery']['sha256'] = sweep.digest(out / 'contact-sheet.png')
        require(all(sweep.digest(ROOT / p) == sources[p] for p in (*current, *SOURCES, PROTOCOL)),
                'sources changed during experiment')
        require(sweep.digest(out / 'bin/garden-landing') == value['build']['binary'] and
                sweep.digest(out / 'CMakeCache.txt') == value['build']['cache'] and
                sweep.digest(out / 'model.tgl') == value['model_sha256'], 'captured inputs changed')
        value['receipt_sha256'] = sweep.fingerprint(value)
        check_capture(value)
        previous.write_receipt(out / 'capture.json', value)
        previous.write_receipt(out / 'manifest.json', dict(rule=RULE, artifacts={str(p.relative_to(out)): sweep.digest(p)
                              for p in sorted(out.rglob('*')) if p.is_file()}))
        sweep.write_gzip(output, value)
    except Exception as error:
        previous.write_receipt(out / 'failure.json', dict(error=str(error), automatic_retry=False))
        raise
    return value


def verify_bundle(root, value, origin):
    check_capture(value)
    require(origin_inputs(origin) == value['reference'], 'historical comparison reference changed')
    manifest = json.loads((root / 'manifest.json').read_text())
    require(manifest['rule'] == RULE and json.loads((root / 'capture.json').read_text()) == value and
            set(manifest['artifacts']) == {str(p.relative_to(root)) for p in root.rglob('*')
                                         if p.is_file() and p != root / 'manifest.json'} and
            sweep.archived_sources(root / 'source.tar.gz') == value['source_sha256'], 'bundle inventory/snapshot differs')
    for name, sha in manifest['artifacts'].items():
        sweep.followup.artifact(root, dict(path=name, sha256=sha))
    for name, sha in (('protocol.md', PROTOCOL_SHA), ('bin/garden-landing', value['build']['binary']),
                      ('CMakeCache.txt', value['build']['cache']), ('model.tgl', value['model_sha256'])):
        require(sweep.digest(root / name) == sha, 'bundle input differs')
    for phase in PHASES:
        for key, run in value['runs'][phase].items():
            directory = root / run['directory']
            require(json.loads((directory / 'run.json').read_text()) == run and
                    json.loads((directory / 'result.json').read_text()) == run['result'] and
                    sweep.digest(directory / 'model.tgl') == value['model_sha256'], 'run receipt/model differs')
            data = sweep.followup.artifact(root, run['frame']).read_bytes()
            require(len(data) == 115200 and f'{zlib.crc32(data):08x}' == run['result']['framebuffer_crc32'], 'frame differs')
            if phase != 'plain':
                evidence, receipts = extract({k: sweep.followup.artifact(root, v) for k, v in run['traces'].items()}, run['result'])
                require(receipts == run['receipts'] and analyze(evidence, run['result'], active(phase)) == run['audit'],
                        'restored trace/analysis differs')
            print('offline verified: ' + phase + '/' + key, flush=True)
    require(sweep.digest(root / 'contact-sheet.png') == value['gallery']['sha256'], 'gallery differs')
    with tempfile.TemporaryDirectory(prefix='seed-cursor-gallery-') as tmp:
        frames = groups(value)
        for row in frames:
            for frame in row:
                frame['framebuffer'] = str(root / frame['framebuffer'])
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
    parser.add_argument('--origin', type=Path, default=ROOT / 'artifacts/garden-landing-patch-followup-v1')
    parser.add_argument('--build', type=Path, default=ROOT / 'build-host-seed-cursor')
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    require(bool(args.collect) == bool(args.out) and not (args.collect and args.bundle), 'invalid output/mode')
    if args.collect:
        collect(args.collect.resolve(), args.out.resolve(), args.origin.resolve(), args.build.resolve(), args.jobs)
    else:
        with gzip.open(args.verify, 'rt') as stream:
            value = json.load(stream)
        check_capture(value)
        if args.bundle:
            verify_bundle(args.bundle.resolve(), value, args.origin.resolve())
    print('seed-cursor comparison verified')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, TypeError, OSError, StopIteration) as error:
        sys.exit(str(error))
