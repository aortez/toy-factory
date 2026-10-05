#!/usr/bin/env python3
"""Offline paired accounting of the frozen single-death experiment."""

from __future__ import annotations

import argparse
from collections import Counter
import copy
from functools import cache
import gzip
import json
from pathlib import Path
import sys

import garden_landing_disturbance as capture
from garden_experiments import digest
from garden_landing_founders import write_gzip
from garden_landing_root_allocation_audit import fingerprint
from garden_resources import require

previous, followup = capture.previous, capture.followup
bank, adults, resources = previous.bank, previous.adults, previous.resources
population = followup.previous.late.population
ROOT, BASE, STOP, STEP, DAY = capture.ROOT, capture.BASE, capture.STOP, capture.STEP, capture.DAY
START = BASE + STEP
RULE = 'garden-landing-disturbance-audit-v1'
INPUT = 'benchmarks/garden-seasons/landing-disturbance-capture.json.gz'
INPUT_SHA = '8677447bbb1609522e48c25a425a17e0dbbb9efa5c133810b1a72a8204750e39'
MANIFEST_SHA = '0726b1cf464c09e0d835aa2e888a10e8e1ff38d959ec5a7b17b7186b1206d712'
PHASES = ('control', 'treatment')
SOURCES = tuple(sorted({*previous.SOURCES, *capture.SOURCES, 'sim/garden_landing_disturbance_audit.py'}))


@cache
def inputs():
    require(digest(ROOT / INPUT) == INPUT_SHA, 'disturbance capture changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream:
        value = json.load(stream)
    capture.check_capture(value)
    return value


def provenance():
    value = inputs()
    return dict(rule=RULE, input_sha256=INPUT_SHA, protocol_sha256=capture.PROTOCOL_SHA,
                raw_manifest_sha256=MANIFEST_SHA, native_runs=0, training_runs=0,
                interval=[START, STOP], boundary_tick=BASE, panel=value['panel'],
                sources={p: digest(ROOT / p) for p in SOURCES})


def extract_world(paths, run):
    """Retain every post-event visit, budget, body and seed check, not selected successes."""
    result = run['result']
    lives, _ = bank.descendants.index_records(result['lineages'], result['seeds'], 0, STOP)
    streams = {k: followup.trace_rows(paths[k], k, STEP if k == 'reach' else BASE, STOP, result)
               for k in previous.KINDS}
    tail = (r for r in streams['reach'] if r[0]['tick'] >= BASE)
    evidence = dict(boundary=None, rows=[])
    try:
        for (stand, _), (adult, _), (reach, _) in zip(streams['stand'], streams['adult'], tail, strict=True):
            tick = stand['tick']
            climate, phase, strength = previous.sun_at(int(result['seed'], 16), tick)
            require(adult['tick'] == reach['tick'] == tick and stand['climate'] == climate and
                    adult['sun'] == [phase, strength] and adult['cold'] == climate['cold'] and
                    adult['season'] == climate['day'] // 4 and stand['seed_lifetime_ecology_ticks'] == 8192,
                    'trace clocks/climate differ')
            require(all(p['id'] in lives and p['birth'] == lives[p['id']]['birth_tick'] for p in adult['plants']) and
                    all(b['id'] in lives and b['species'] == lives[b['id']]['species'] for b in stand['bodies']),
                    'plant identity differs')
            require(all(set(v) == set(bank.FIELDS) for v in stand['reproduction']), 'unexpected visit fields')
            checks = []
            for raw, check in zip(adult['seeds'], reach['checks'], strict=True):
                require(len(check) == 7 and check[:4] == raw[:4] and check[4:6] == raw[8:10],
                        'adult/reach check differs')
                checks.append([raw, check[6]])
            row = [tick, stand['plant_order'], [[v[k] for k in bank.FIELDS] for v in stand['reproduction']],
                   [[p['id'], resources.pack(p)] for p in adult['plants']],
                   [[b['id'], b['nodes'], b['roots'], b['flowers']] for b in stand['bodies']],
                   checks, reach['purchases'], adult['bank']]
            if tick == BASE:
                evidence['boundary'] = row
            else:
                evidence['rows'].append(row)
    finally:
        tail.close()
        for stream in streams.values():
            stream.close()
    return evidence


def check_row(row, tick, result, lives, seeds):
    require(type(row) is list and len(row) == 8 and type(row[0]) is int and row[0] == tick,
            'missing/reordered evidence clock')
    _, slots, visits, packed, bodies, checks, purchases, count = row
    previous.visit_order(tick, slots, visits, result)
    living = {i for i, p in lives.items() if bank.previous.present(p, tick, living=True)}
    require(living <= set(slots) <= set(lives) and all(lives[i]['birth_tick'] <= tick for i in slots),
            'wrong stored inventory')
    require(all(type(p) is list and len(p) == 2 for p in packed) and
            all(type(b) is list and len(b) == 4 for b in bodies), 'invalid plant encoding')
    plants, shapes = dict(packed), {b[0]: b[1:] for b in bodies}
    require(len(plants) == len(packed) and len(shapes) == len(bodies) and set(shapes) == living and
            set(plants) == living | {i for i, p in lives.items() if p['death_tick'] == tick},
            'incomplete resource/body coverage')
    climate, phase, strength = previous.sun_at(int(result['seed'], 16), tick)
    require(all(v[bank.FIELDS.index('sun')] == strength for v in visits), 'wrong visit light')
    adult = dict(tick=tick, bank=count, seeds=[c[0] for c in checks])
    reach = dict(purchases=purchases, checks=[c[0][:4] + c[0][8:10] + [c[1]] for c in checks])
    inventory, bought = previous.check_inventory(adult, reach, slots, lives, seeds, climate['cold'])
    return plants, shapes, inventory, bought, phase


def slot_change(before, after, tick, lives):
    """Observe reclamation before germination, even if a slot refills in this step."""
    born = {i for i, p in lives.items() if p['birth_tick'] == tick}
    lost = set(before) - set(after)
    require(set(after) - set(before) == born and
            all(lives[i]['death_tick'] is not None and lives[i]['death_tick'] < tick for i in lost) and
            [i for i in after if i not in born] == [i for i in before if i not in lost],
            'invalid slot reclamation/birth')
    precheck = [i for i in before if i not in lost]
    opened = followup.previous.clear(precheck, lives) & ~followup.previous.clear(before, lives)
    return dict(tick=tick, removed=sorted(lost), born=sorted(born), slots_before=len(before),
                slots_before_germination=len(precheck), slots_after=len(after),
                newly_clear_columns=[c for c in range(28) if opened & (1 << c)])


def family(identity, lives, seeds):
    life = lives[identity]
    purchases = [s for s in seeds.values() if s['parent'] == identity and s['birth_tick'] > BASE]
    children = [p for p in lives.values() if p['parent'] == identity and p['birth_tick'] > BASE]
    grandchildren = [p for p in lives.values() if p['parent'] in {c['id'] for c in children}]
    return dict(life=life, survival={str(d): population.survival(life, STOP, d) for d in (1, 16, 32)},
                alive_at_horizon=life['death_tick'] is None, new_seeds=purchases,
                children=[dict(life=p, seed=next(s for s in seeds.values() if s['child_id'] == p['id']),
                               survival={str(d): population.survival(p, STOP, d) for d in (1, 16, 32)},
                               seeds_created=p['seeds_created']) for p in children],
                grandchildren=[p['id'] for p in grandchildren],
                established_grandchildren=[p['id'] for p in grandchildren
                                           if population.survival(p, STOP, 1) == 'confirmed'])


def analyze_world(run, world, evidence):
    result = run['result']
    lives, seeds = bank.descendants.index_records(result['lineages'], result['seeds'], 0, STOP)
    require(set(evidence) == {'boundary', 'rows'} and type(evidence['rows']) is list and
            len(evidence['rows']) == (STOP - BASE) // STEP, 'incomplete evidence window')
    event = result.get('turnover_probe')
    observed = copy.deepcopy(lives)
    if event:
        observed[event['lineage']]['death_tick'] = None  # BASE observation precedes the imposed death.
    anchor, _, _, _, _ = check_row(evidence['boundary'], BASE, result, observed, seeds)
    for i, packed in anchor.items():
        adults.transfers(resources.unpack(packed, observed[i], BASE), observed[i])
    if event:
        stage = anchor[event['lineage']][0][-1]
        require([event['energy'], event['water'], event['nodes']] == [stage[0], stage[1], stage[4]],
                'event discard does not match boundary stores/body')
    last, prior = evidence['boundary'][1], anchor
    totals, seed_checks, changes = {}, {}, []
    states, occupancy = [[BASE, last]], Counter()
    for tick, row in zip(range(START, STOP + STEP, STEP), evidence['rows'], strict=True):
        plants, shapes, inventory, bought, phase = check_row(row, tick, result, lives, seeds)
        slots, visits = row[1], {v[0]: dict(zip(bank.FIELDS, v, strict=True)) for v in row[2]}
        if slots != last:
            changes.append(slot_change(last, slots, tick, lives))
            states.append([tick, slots])
        occupancy[f'{len(shapes)}/{len(slots)}'] += 1
        for i, packed in plants.items():
            life, before = lives[i], prior[i][0][-1] if i in prior else None
            plant = resources.unpack(packed, life, tick)
            if i in shapes:
                transfer, _ = previous.check_focal_sample(visits[i], shapes[i], packed, life, tick, before)
            else:
                transfer = adults.transfers(plant, life, before)
                require(not visits[i]['produced'], 'dead plant purchased a seed')
            pay = population.payment(plant, transfer, prior[i][2] if i in prior else None, tick, phase)
            record = totals.setdefault(str(i), dict(samples=0, budget=adults.budget(), payments=0,
                                                     shortfalls=[], max_stress=0, morphology=[],
                                                     flower_states=Counter(), readiness=Counter()))
            adults.accumulate(record['budget'], transfer, record['samples'] == 0)
            record['samples'] += 1
            record['max_stress'] = max(record['max_stress'], *(s[2] for s in packed[0] if s is not None))
            if pay:
                record['payments'] += 1
                if any(pay[r]['unpaid'] for r in ('energy', 'water')):
                    record['shortfalls'].append(pay)
            if i in shapes:
                shape, visit = [*shapes[i], packed[3]], visits[i]
                if not record['morphology'] or shape != record['morphology'][-1][1]:
                    record['morphology'].append([tick, shape])
                state = 'ready' if visit['ready'] else 'no_flower' if shapes[i][2] == 0 else 'immature' if visit['immature'] else 'spent'
                record['flower_states'][state] += 1
                if tick % 60 == 0 and visit['sun'] > 24:
                    for name, amount in (('cadence_daylight', 1), ('ready_flower', visit['ready'] > 0),
                                         ('eligible_ignoring_bank', visit['blockers'] & ~bank.BANK == 0),
                                         ('purchased', visit['produced'])):
                        record['readiness'][name] += amount
        for (parent, birth), (_, raw, _, _) in inventory.items():
            key = f'{parent}:{birth}'
            record = seed_checks.setdefault(key, dict(seed=seeds[parent, birth], checks=0, dormant=0,
                                                      expiry_only=0, mature_masks=Counter(), mature_blockers=Counter()))
            record['checks'] += 1
            if raw[8] == 1:
                record['expiry_only'] += 1
            elif raw[1] < 8:
                record['dormant'] += 1
            else:
                record['mature_masks'][str(raw[3])] += 1
                for j, name in enumerate(previous.BLOCKERS):
                    record['mature_blockers'][name] += bool(raw[3] & (1 << j))
        last, prior = slots, plants
    require(states == run['receipts']['stand']['states'] and dict(occupancy) == run['receipts']['stand']['occupancy'] and
            len(last) == result['plant_slots'], 'stored chronology differs from capture')
    for key, seed in seeds.items():
        count = bank.samples(max(START, seed['birth_tick'] + STEP), min(STOP, seed['end_tick'] or STOP))
        require(seed_checks.get(f'{key[0]}:{key[1]}', {}).get('checks', 0) == count, 'incomplete seed checks')
    for i, life in lives.items():
        count = bank.samples(max(START, life['birth_tick']), min(STOP, life['death_tick'] or STOP))
        record = totals.get(str(i))
        require((record['samples'] if record else 0) == count, 'incomplete plant resource history')
        if record:
            purchases = sum(s['parent'] == i and s['birth_tick'] > BASE for s in seeds.values())
            require(record['budget']['energy']['reproduction'] == 48 * purchases and
                    record['budget']['water']['reproduction'] == 24 * purchases, 'purchase costs differ')
    access = bank.analyze_visits([[r[0], r[2]] for r in evidence['rows']], result, START, STOP)
    incumbents = [i for i, p in lives.items() if p['birth_tick'] <= BASE and i not in world['focal']]
    stock = bank.residence(result, START, STOP, incumbents, world['focal'])
    require(access.pop('resident_samples') == sorted([s['parent'], s['birth_tick'], s['slot_samples']] for s in stock['seeds']),
            'bank residence differs from visit census')
    parents = {p['id']: p for p in access['plants']}
    focal = {str(i): family(i, lives, seeds) | dict(resources=totals[str(i)], access=parents[i])
             for i in world['focal']}
    recruits = {str(i): family(i, lives, seeds) | dict(resources=totals[str(i)], access=parents[i],
                seed=next(s for s in seeds.values() if s['child_id'] == i),
                parent_cohort='focal' if p['parent'] in world['focal'] else
                'imposed_death' if event and p['parent'] == event['lineage'] else
                'incumbent' if lives[p['parent']]['birth_tick'] <= BASE else 'new_recruit')
                for i, p in lives.items() if p['birth_tick'] > BASE}
    disturbance = None
    if event:
        released = [c for c in changes if event['lineage'] in c['removed']]
        require(len(released) <= 1, 'duplicate reclamation')
        release = released[0] if released else None
        births = sorted((r['life'] for r in recruits.values()), key=lambda p: (p['birth_tick'], p['id']))
        first = births[0] if births else None
        same_column = [p for p in births if p['column'] == event['column']]
        released_columns = [p for p in births if release and p['column'] in release['newly_clear_columns'] and
                            p['birth_tick'] >= release['tick']]
        disturbance = dict(event=event, reclamation=release,
                           decomposition_ticks=release['tick'] - BASE if release else None,
                           first_germination=first, first_exact_column_refill=same_column[0] if same_column else None,
                           new_clear_column_births=[p['id'] for p in released_columns],
                           delay_reclamation_to_germination=first['birth_tick'] - release['tick'] if release and first else None)
    natural = [p for p in lives.values() if p['death_tick'] is not None and p['death_tick'] > BASE and
               not p['environmental_death']]
    return dict(focal=focal, recruits=recruits, plants=totals, seed_checks=seed_checks, changes=changes,
                disturbance=disturbance, access=access, residence=stock, natural_deaths=natural,
                incumbent_natural_deaths=[p['id'] for p in natural if p['birth_tick'] <= BASE],
                final=dict(living=result['living'], stored=result['plant_slots'], nodes=result['nodes'], seeds=result['seed_bank']))


def exposure(plants):
    return dict(samples=sum(p['samples'] for p in plants), payments=sum(p['payments'] for p in plants),
                shortfall_payments=sum(len(p['shortfalls']) for p in plants),
                unpaid={r: sum(e[r]['unpaid'] for p in plants for e in p['shortfalls']) for r in ('energy', 'water')})


def compare(arms, world):
    control, treatment = (arms[a] for a in PHASES)
    # Post-event numeric IDs can coincide despite divergent ancestry. Match
    # only the pre-event incumbents, excluding the deliberately killed plant.
    excluded = {str(world['target']), *control['recruits'], *treatment['recruits']}
    common = sorted((set(control['plants']) & set(treatment['plants'])) - excluded, key=int)
    return dict(matched_incumbents=[int(i) for i in common], arms={phase: dict(
        births=len(a['recruits']), natural_deaths=len(a['natural_deaths']),
        focal_new_seeds=sum(len(p['new_seeds']) for p in a['focal'].values()),
        focal_children=sum(len(p['children']) for p in a['focal'].values()),
        recruit_seed_producers=sum(bool(p['new_seeds']) for p in a['recruits'].values()),
        recruit_children=sum(len(p['children']) for p in a['recruits'].values()),
        final=a['final'], resources=exposure(list(a['plants'].values())),
        matched_resources=exposure([a['plants'][i] for i in common]),
        per_matched_plant={i: exposure([a['plants'][i]]) for i in common}) for phase, a in arms.items()})


def check_value(value):
    saved, expected = inputs(), provenance()
    require(set(value) == {*expected, 'evidence', 'analysis', 'comparisons', 'receipt_sha256'} and
            all(value[k] == v for k, v in expected.items()), 'audit provenance differs')
    panel = saved['panel']
    require(set(value['evidence']) == set(value['analysis']) == set(value['comparisons']) == set(panel), 'wrong audit panel')
    for key, world in panel.items():
        require(set(value['evidence'][key]) == set(value['analysis'][key]) == set(PHASES), 'wrong paired phases')
        require(value['evidence'][key]['control']['boundary'] == value['evidence'][key]['treatment']['boundary'],
                'paired pre-event evidence changed')
        for phase in PHASES:
            require(value['analysis'][key][phase] == analyze_world(saved['runs'][phase][key], world, value['evidence'][key][phase]),
                    'derived audit differs: ' + phase + '/' + key)
        require(value['comparisons'][key] == compare(value['analysis'][key], world), 'paired comparison differs')
    require(value['receipt_sha256'] == fingerprint({k: v for k, v in value.items() if k != 'receipt_sha256'}),
            'audit receipt changed')


def extract(bundle):
    saved, expected = inputs(), provenance()
    require(digest(bundle / 'manifest.json') == MANIFEST_SHA, 'wrong raw manifest')
    # Authenticates all 20 results, images, traces, binaries and archived sources;
    # rechecks framing and exact repeats without executing any archived binary.
    capture.verify_bundle(bundle, saved)
    value = dict(expected, evidence={}, analysis={}, comparisons={})
    for key, world in saved['panel'].items():
        value['evidence'][key], value['analysis'][key] = {}, {}
        for phase in PHASES:
            run = saved['runs'][phase][key]
            paths = {k: followup.artifact(bundle, v) for k, v in run['traces'].items()}
            evidence = extract_world(paths, run)
            value['evidence'][key][phase] = evidence
            value['analysis'][key][phase] = analyze_world(run, world, evidence)
            require(all(digest(paths[k]) == run['traces'][k]['sha256'] for k in paths), 'trace changed during extraction')
            print(phase + '/' + key + ': resources, bank, seeds and vacancy response verified', flush=True)
        value['comparisons'][key] = compare(value['analysis'][key], world)
    require(digest(bundle / 'manifest.json') == MANIFEST_SHA and provenance() == expected and
            digest(ROOT / INPUT) == INPUT_SHA, 'audit inputs changed')
    value['receipt_sha256'] = fingerprint(value)
    check_value(value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--extract-from', type=Path)
    mode.add_argument('--verify', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    require(bool(args.out) == bool(args.extract_from), 'extraction requires a fresh --out; verify takes no output')
    if args.extract_from:
        require(not args.out.exists() and not args.out.is_symlink(), 'fresh output required')
        write_gzip(args.out, extract(args.extract_from.resolve()))
    else:
        with gzip.open(args.verify, 'rt') as stream:
            value = json.load(stream)
        check_value(value)
    print('verified ' + RULE)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, TypeError, IndexError, OSError) as error:
        print('error: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
