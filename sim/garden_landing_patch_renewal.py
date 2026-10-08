#!/usr/bin/env python3
"""Offline winter budgets and recruitment gates after the fixed dieback schedule."""

from collections import Counter
from functools import cache
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys

import garden_landing_patch_followup as previous
import garden_landing_seed_competition as competition
from garden_experiments import digest
from garden_landing_founders import write_gzip
from garden_landing_root_allocation_audit import fingerprint
from garden_resources import require

ROOT, DAY, STEP, BASE, STOP = previous.ROOT, previous.DAY, previous.STEP, previous.BASE, previous.STOP
window, late = previous.sweep.window, previous.sweep.late
RULE = 'garden-landing-patch-renewal-v1'
INPUT = 'benchmarks/garden-seasons/landing-patch-followup-results.json.gz'
INPUT_SHA = '467a2fefbb238689999fd97f0f6de78b2c7558bb3b1e4833e19d90ae76a57083'
MANIFEST_SHA = 'fad8f7bfd1f59e3a70830d8c03d640c40b91065d3ddfef1f001f82b5e9bbc38e'
# The original receipt remains byte-for-byte immutable. A newer verifier may
# reanalyze it without claiming its own sources were the collection sources.
ORIGINAL_RECEIPT = 'ce518978964d7cb53ee2c5763162b38fd376795e6d53f9d8115c479593d09247'
PHASES = ('control', 'treatment')
FOCAL = ('3a7e45e6-rainfed', 'treatment')
IDENTITIES = (46, 47, 48)
SOURCES = tuple(sorted({*previous.SOURCES, 'sim/garden_landing_seed_competition.py',
                        'sim/garden_landing_patch_renewal.py', 'sim/test_garden_landing_patch_renewal.py'}))
RUNTIME = ('src/garden_world.c', 'src/garden_world.h', 'src/garden_climate.c',
           'sim/garden_landing_recruitment.c', 'sim/garden_landing_reach.c',
           'sim/garden_landing_plant_trace.c')


@cache
def inputs():
    require(digest(ROOT / INPUT) == INPUT_SHA, 'follow-up input changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream:
        value = json.load(stream)
    previous.check_capture(value)
    # INPUT_SHA authenticates the captured implementation. Comparing it with
    # a moving worktree would invalidate old observations on every code change.
    return value


def provenance():
    saved = inputs()
    return dict(rule=RULE, input_sha256=INPUT_SHA, manifest_sha256=MANIFEST_SHA,
                interval=[BASE + STEP, STOP], sample_step=STEP,
                focal=dict(case=FOCAL[0], phase=FOCAL[1], identities=list(IDENTITIES)),
                panel=saved['panel'], model_sha256=saved['model_sha256'], native_runs=0, training_runs=0,
                implementation={p: saved['source_sha256'][p] for p in RUNTIME},
                sources={p: digest(ROOT / p) for p in SOURCES})


def selected_rows(path, kind, result, metadata, wanted):
    """Stream gzip, authenticating all restored bytes but decoding only selected rows."""
    start = STEP if kind == 'reach' else previous.sweep.BASE
    schemas = dict(stand='landing-dawn-stand-trace-v1', adult='landing-adult-resources-v1',
                   reach='landing-reach-trace-v1')
    header = dict(schema=schemas[kind])
    if kind != 'reach':
        header.update(start=start, stop=STOP)
    if kind == 'stand':
        header.update(node_limit=32, budget_mode=2)
    footer = dict(complete=True, tick=STOP)
    if kind == 'stand':
        footer['run_hash'] = result['run_hash']
    require(digest(path) == metadata['sha256'], 'compressed trace changed')
    restored, length = hashlib.sha256(), 0
    with gzip.open(path, 'rb') as stream:
        def line():
            nonlocal length
            raw = stream.readline()
            require(raw.endswith(b'\n'), 'truncated trace line')
            restored.update(raw)
            length += len(raw)
            return raw
        require(json.loads(line()) == header, 'wrong trace header')
        for tick in range(start, STOP + STEP, STEP):
            raw = line()
            if wanted(tick):
                row = json.loads(raw)
                require(type(row.get('tick')) is int and row['tick'] == tick, 'trace clock differs')
                yield row
        require(json.loads(line()) == footer and not stream.read(), 'wrong trace footer/trailing bytes')
    require((restored.hexdigest(), length) == (metadata['raw_sha256'], metadata['raw_bytes']) and
            digest(path) == metadata['sha256'], 'restored/compressed trace identity differs')


def resident_seeds(seeds):
    return {k: s for k, s in seeds.items() if s['birth_tick'] <= STOP and
            (s['end_tick'] or STOP) >= BASE and s['birth_tick'] < STOP}


def extract_arm(bundle, run, key, phase, manifest):
    result = run['result']
    lives, seeds = previous.sweep.index_records(result['lineages'], result['seeds'], 0, STOP)
    selected = resident_seeds(seeds)
    purchase_ticks = {s['birth_tick'] for s in selected.values()}
    require(min(purchase_ticks) >= previous.sweep.BASE, 'purchase predates stand archive')
    focal = {i: lives[i] for i in IDENTITIES} if (key, phase) == FOCAL else {}
    first = min((p['birth_tick'] for p in focal.values()), default=STOP + STEP)
    rows, witnesses, plants, slots = {}, {}, {str(i): {} for i in focal}, {}
    for kind in previous.sweep.KINDS:
        meta = run['traces'][kind]
        require(manifest['artifacts'].get(meta['path']) == meta['sha256'], 'trace/manifest differs')
        path = previous.sweep.followup.artifact(bundle, meta)
        wanted = lambda t: t >= BASE or t >= first or (kind != 'adult' and t in purchase_ticks)
        for row in selected_rows(path, kind, result, meta, wanted):
            tick = row['tick']
            tail = rows.setdefault(tick, dict(tick=tick)) if tick >= BASE else None
            if kind == 'stand':
                require(row['climate'] == window.previous.sun_at(int(result['seed'], 16), tick)[0] and
                        row['seed_lifetime_ecology_ticks'] == 8192 and
                        all(set(v) == set(window.bank.FIELDS) for v in row['reproduction']),
                        'stand climate/visit fields differ')
                if tick in purchase_ticks:
                    slots[tick] = row['plant_order']
                visits = [[v[k] for k in window.bank.FIELDS] for v in row['reproduction']]
                if tail is not None:
                    tail.update(slots=row['plant_order'], visits=visits)
                for i, life in focal.items():
                    if life['birth_tick'] <= tick <= (life['death_tick'] or STOP):
                        body = next((b for b in row['bodies'] if b['id'] == i), None)
                        plants[str(i)][tick] = [tick, None,
                            [body[k] for k in ('nodes', 'roots', 'flowers')] if body else None,
                            next(v for v in visits if v[0] == i)]
            elif kind == 'adult':
                climate, sun, strength = window.previous.sun_at(int(result['seed'], 16), tick)
                require(row['sun'] == [sun, strength] and row['cold'] == climate['cold'] and
                        row['season'] == climate['day'] // 4, 'adult climate differs')
                if tail is not None:
                    tail.update(checks=row['seeds'], bank=row['bank'])
                for p in row['plants']:
                    if p['id'] in focal:
                        require(p['birth'] == lives[p['id']]['birth_tick'], 'focal birth differs')
                        plants[str(p['id'])][tick][1] = window.resources.pack(p)
            else:
                for p in row['purchases']:
                    identity = p['parent'], tick
                    if identity in selected:
                        require(identity not in witnesses, 'duplicate purchase witness')
                        witnesses[identity] = [list(identity), slots[tick], p]
                if tail is not None:
                    checks = []
                    for raw, check in zip(tail['checks'], row['checks'], strict=True):
                        require(len(check) == 7 and check[:4] == raw[:4] and check[4:6] == raw[8:10],
                                'seed observers disagree')
                        checks.append([raw, check[6]])
                    tail.update(checks=checks, purchases=row['purchases'])
    require(set(witnesses) == set(selected), 'missing purchase witnesses')
    return dict(rows=[rows[t] for t in sorted(rows)], witnesses=[witnesses[k] for k in sorted(witnesses)],
                focal={i: [p[t] for t in sorted(p)] for i, p in plants.items()})


def extract(bundle):
    saved = inputs()
    require(digest(bundle / 'manifest.json') == MANIFEST_SHA, 'wrong follow-up manifest')
    manifest = json.loads((bundle / 'manifest.json').read_text())
    evidence = {}
    for key in previous.confirm.panel():
        evidence[key] = {}
        for phase in PHASES:
            print(f'Auditing {key} / {phase}', file=sys.stderr, flush=True)
            evidence[key][phase] = extract_arm(bundle, saved['runs'][phase][key], key, phase, manifest)
    require(digest(bundle / 'manifest.json') == MANIFEST_SHA, 'manifest changed during audit')
    return evidence


def check_sites(raw, encoded, slots, lives, cold):
    if encoded is None:
        return
    spacing = late.spacing_map(tuple(lives[i]['column'] for i in slots))
    for c, mask in enumerate(late.sites_decode(encoded)):
        fixed = spacing[c] | (8 if len(slots) == 8 else 0) | (16 if raw[7] + 4 > 256 else 0) | (64 if cold else 0)
        require(mask & (8 | 16 | 32 | 64) == fixed, 'off-column capacity/spacing/cold differs')


def focal_history(rows, life, result):
    start, end = life['birth_tick'], life['death_tick'] or STOP
    require([r[0] for r in rows] == list(range(start, end + STEP, STEP)), 'incomplete focal clock')
    total, days, before, roots = window.adults.budget(), {}, None, None
    morphology, shortfalls, reproduction = [], [], []
    for n, (tick, packed, body, raw_visit) in enumerate(rows):
        plant = window.resources.unpack(packed, life, tick)
        require(len(raw_visit) == len(window.bank.FIELDS) and raw_visit[0] == life['id'], 'wrong focal visit')
        visit = dict(zip(window.bank.FIELDS, raw_visit, strict=True))
        climate, sun, strength = window.previous.sun_at(int(result['seed'], 16), tick)
        require(visit['sun'] == strength, 'wrong focal sunlight')
        if tick == life['death_tick']:
            require(body is None and not visit['produced'], 'dead plant has a live body/purchase')
            transfer = window.adults.transfers(plant, life, before)
        else:
            transfer, _ = window.previous.check_focal_sample(visit, body, packed, life, tick, before)
        window.adults.accumulate(total, transfer, n == 0)
        day = days.setdefault(str(tick // DAY), dict(samples=0, resources=window.adults.budget(),
                                                    shortfalls=Counter(), last=None))
        window.adults.accumulate(day['resources'], transfer, day['samples'] == 0)
        day['samples'] += 1
        day['last'] = [tick, plant['stages'][-1], body, plant['active_leaves']]
        pay = window.population.payment(plant, transfer, roots, tick, sun)
        if pay and any(pay[r]['unpaid'] for r in ('energy', 'water')):
            for name in ('energy', 'water'):
                day['shortfalls'][name] += bool(pay[name]['unpaid'])
            shortfalls.append(dict(pay, stress=plant['stages'][1][2], climate=climate,
                                   pre_maintenance=plant['stages'][0]))
        if body is not None:
            shape = [*body, plant['active_leaves']]
            if not morphology or shape != morphology[-1][1]:
                morphology.append([tick, shape])
        if visit['produced']:
            reproduction.append(tick)
        before, roots = plant['stages'][-1], plant['roots']
    expected = [s['birth_tick'] for s in result['seeds'] if s['parent'] == life['id']]
    require(reproduction == expected and total['energy']['reproduction'] == 48 * len(expected) and
            total['water']['reproduction'] == 24 * len(expected), 'focal purchases/debits differ')
    return dict(life=life, samples=len(rows), resources=total, days=days, shortfalls=shortfalls,
                morphology=morphology, purchases=reproduction,
                terminal=rows[-1] if life['death_tick'] is not None else None)


def analyze_arm(evidence, key, phase):
    result = inputs()['runs'][phase][key]['result']
    lives, seeds = previous.sweep.index_records(result['lineages'], result['seeds'], 0, STOP)
    require(set(evidence) == {'rows', 'witnesses', 'focal'}, 'wrong arm fields')
    rows = evidence['rows']
    require([r['tick'] for r in rows] == list(range(BASE, STOP + STEP, STEP)), 'incomplete/reordered tail clock')
    witnesses = {}
    for identity, slots, purchase in evidence['witnesses']:
        identity = tuple(identity)
        require(identity in seeds and identity not in witnesses, 'unknown/duplicate witness')
        late.purchase_check(purchase, slots, lives, seeds[identity], True)
        witnesses[identity] = purchase
    require(set(witnesses) == set(resident_seeds(seeds)), 'purchase coverage differs')
    counts, masks, occupancy, geometry, bounds, columns = (Counter() for _ in range(6))
    seed_counts = {k: dict(seed=seeds[k], checks=0, mature_masks=Counter(), dormant=0, expiry=0,
                          open_elsewhere=0, reachable_elsewhere=0, purchase_allowed_elsewhere=0)
                   for k in witnesses}
    changes, born, last = [], [], None
    for row in rows:
        require(set(row) == {'tick', 'slots', 'visits', 'checks', 'purchases', 'bank'}, 'wrong tail fields')
        tick, slots, visits = row['tick'], row['slots'], row['visits']
        window.previous.visit_order(tick, slots, visits, result)
        living = {i for i, p in lives.items() if p['birth_tick'] <= tick and
                  (p['death_tick'] is None or p['death_tick'] > tick)}
        require(living <= set(slots) <= set(lives) and all(lives[i]['birth_tick'] <= tick for i in slots),
                'wrong stored/live population')
        if last is not None:
            change = window.prior.slot_change(last, slots, tick, lives)
            if change['removed'] or change['born']:
                changes.append(change)
        last = slots
        climate, _, strength = window.previous.sun_at(int(result['seed'], 16), tick)
        require(all(v[window.bank.FIELDS.index('sun')] == strength for v in visits), 'wrong visit sunlight')
        inventory = window.check_inventory(row['checks'], row['purchases'], row['bank'], tick, STOP,
                                            slots, lives, seeds, climate['cold'])
        check_slots = [i for i in slots if lives[i]['birth_tick'] != tick]
        nodes, open_step, reachable_step = None, False, False
        for identity, (_, raw, encoded, before) in inventory.items():
            require(before == check_slots and (nodes is None or nodes == raw[7]), 'sequential census differs')
            nodes = raw[7]
            check_sites(raw, encoded, before, lives, climate['cold'])
            purchase = witnesses[identity]
            chance = competition.opportunity(raw, encoded, purchase['choices'], competition.purchase_allowed(purchase))
            if raw[8] == 2:
                check_slots.append(raw[9])
                nodes += 4
            if tick == BASE:
                continue
            record = seed_counts[identity]
            record['checks'] += 1
            counts['checks'] += 1
            if encoded is None:
                record['expiry'] += 1
                counts['expiry'] += 1
                continue
            bounds[str(chance['admission_bound'])] += 1
            open_step |= bool(raw[10])
            if raw[1] < 8:
                record['dormant'] += 1
                counts['dormant'] += 1
                continue
            counts['mature'] += 1
            masks[str(raw[3])] += 1
            record['mature_masks'][str(raw[3])] += 1
            for j, name in enumerate(window.previous.BLOCKERS):
                counts[name] += bool(raw[3] & (1 << j))
            for c, mask in enumerate(bytes.fromhex(encoded)):
                if mask == 0:
                    columns[str(c)] += 1
            flags = dict(open_elsewhere=bool(raw[10] and raw[3]),
                         reachable_elsewhere=bool(chance['alternate_sites']),
                         purchase_allowed_elsewhere=bool(chance['purchase_allowed_alternates']))
            reachable_step |= flags['reachable_elsewhere']
            for name, flag in flags.items():
                counts[name] += flag
                record[name] += flag
            if raw[8] == 2:
                born.append(dict(tick=tick, seed=list(identity), raw=raw))
        for purchase in row['purchases']:
            require(witnesses[purchase['parent'], tick] == purchase, 'purchase witness differs')
        if tick == BASE:
            continue
        occupancy[f'{len(living)}/{len(slots)}'] += 1
        clear = [c for c, mask in enumerate(late.spacing_map(tuple(lives[i]['column'] for i in slots))) if not mask]
        geometry[','.join(map(str, clear)) or 'none'] += 1
        counts['steps'] += 1
        counts['open_steps'] += open_step
        counts['reachable_steps'] += reachable_step
    for identity, record in seed_counts.items():
        seed = seeds[identity]
        require(record['checks'] == window.bank.samples(max(BASE + STEP, seed['birth_tick'] + STEP),
                min(STOP, seed['end_tick'] or STOP)), 'incomplete seed exposure')
    access = window.bank.analyze_visits([[r['tick'], r['visits']] for r in rows[1:]], result, BASE + STEP, STOP)
    require(access['bank']['post_step_counts'] == dict(Counter(str(r['bank']) for r in rows[1:])),
            'seed access/post-step census differs')
    require(len(born) == len(result['lineages']) - sum(p['birth_tick'] <= BASE for p in lives.values()) and
            dict(occupancy) == inputs()['runs'][phase][key]['receipts']['stand']['occupancy'],
            'birth/occupancy receipt differs')
    wanted = set(map(str, IDENTITIES)) if (key, phase) == FOCAL else set()
    require(set(evidence['focal']) == wanted, 'missing/extra focal histories')
    return dict(counts=counts, mature_masks=masks, occupancy=occupancy, spacing_clear_steps=geometry,
                admission_bound_checks=bounds, viable_column_mature_checks=columns, births=born,
                slot_changes=changes, seeds=[seed_counts[k] for k in sorted(seed_counts)], access=access,
                focal={i: focal_history(evidence['focal'][i], lives[int(i)], result) for i in sorted(wanted)},
                endpoint=[dict(id=i, column=lives[i]['column']) for i in rows[-1]['slots']])


def build(evidence):
    require(set(evidence) == set(inputs()['panel']) and all(set(p) == set(PHASES) for p in evidence.values()),
            'missing/extra world or arm')
    analysis = {k: {p: analyze_arm(pair[p], k, p) for p in PHASES} for k, pair in evidence.items()}
    value = dict(provenance(), evidence=evidence, analysis=analysis)
    value['receipt_sha256'] = fingerprint(value)
    return value


def rebuild(value):
    current = provenance()
    if value['sources'] != current['sources']:
        require(value['receipt_sha256'] == ORIGINAL_RECEIPT and
                fingerprint({k: v for k, v in value.items() if k != 'receipt_sha256'}) == ORIGINAL_RECEIPT,
                'unknown historical audit identity')
    expected = build(value['evidence'])
    expected['sources'] = value['sources']
    expected['receipt_sha256'] = fingerprint({k: v for k, v in expected.items() if k != 'receipt_sha256'})
    require(value == expected, 'renewal analysis/provenance differs')
    return expected


def check_value(value):
    rebuild(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, help='saved compressed day-352 traces; no simulation')
    parser.add_argument('--out', type=Path, help='fresh portable gzip output')
    parser.add_argument('--verify', type=Path, help='verify portable result; add --bundle to re-extract')
    args = parser.parse_args()
    if args.verify:
        require(args.out is None, '--verify cannot write an output')
        with gzip.open(args.verify, 'rt') as stream:
            value = json.load(stream)
        check_value(value)
        if args.bundle:
            require(value['evidence'] == extract(args.bundle), 'raw/portable evidence differs')
    else:
        require(args.bundle is not None and args.out is not None, '--bundle and --out required')
        require(not args.out.exists() and not args.out.is_symlink(), 'fresh output required')
        value = build(extract(args.bundle))
        write_gzip(args.out, value)
    print(json.dumps(dict(rule=RULE, histories=12, native_runs=0, training_runs=0,
                          receipt_sha256=value['receipt_sha256']), sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, OSError, StopIteration, TypeError) as error:
        sys.exit(str(error))
