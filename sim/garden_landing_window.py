#!/usr/bin/env python3
"""Window-parameterized resource/reproduction accounting for imposed-death studies.

Older frozen auditors are intentionally unchanged: their source hashes are part
of published receipts. This module reuses their horizon-independent validators,
but owns the interval and observation/event ordering explicitly.
"""

from collections import Counter
import copy

import garden_landing_disturbance_audit as prior
from garden_resources import require

previous, followup = prior.previous, prior.followup
bank, adults, resources, population = prior.bank, prior.adults, prior.resources, prior.population
STEP = prior.STEP


def extract_world(paths, run, trace_start, base, stop):
    result = run['result']
    lives, _ = bank.descendants.index_records(result['lineages'], result['seeds'], 0, stop)
    streams = {k: followup.trace_rows(paths[k], k, STEP if k == 'reach' else trace_start, stop, result)
               for k in previous.KINDS}
    tails = [(item for item in stream if item[0]['tick'] >= base) for stream in streams.values()]
    evidence = dict(boundary=None, rows=[])
    try:
        for (stand, _), (adult, _), (reach, _) in zip(*tails, strict=True):
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
            if tick == base:
                evidence['boundary'] = row
            else:
                evidence['rows'].append(row)
    finally:
        for stream in (*tails, *streams.values()):
            stream.close()
    return evidence


def check_inventory(checks, purchases, count, tick, stop, slots, lives, seeds, cold):
    born = {i for i, p in lives.items() if p['birth_tick'] == tick}
    before = [i for i in slots if i not in born]
    records = {}
    for raw, encoded in checks:
        require(type(raw) is list and len(raw) == 11, 'invalid seed check')
        key = raw[0], tick - raw[1] * STEP
        require(key in seeds and key not in records, 'unknown/duplicate seed attempt')
        previous.seed_check(raw, encoded, tick, seeds[key], before, lives, cold)
        records[key] = [tick, raw, encoded, list(before)]
        if raw[8] == 2:
            require(raw[9] in born and raw[9] not in before, 'unexpected germinated child')
            before.append(raw[9])
    require(before == slots and set(records) == {k for k, s in seeds.items()
            if s['birth_tick'] < tick <= (s['end_tick'] or stop)}, 'incomplete seed/child inventory')
    require(count == sum(s['birth_tick'] <= tick < (s['end_tick'] or stop + STEP)
                         for s in seeds.values()), 'post-step bank differs')
    bought = {}
    for p in purchases:
        require(set(p) == {'parent', 'column', 'origin', 'dispersal', 'choices', 'sites'} and
                p['parent'] in lives and p['parent'] not in bought and
                p['origin'] == lives[p['parent']]['column'] and p['column'] in p['choices'] and
                all(type(c) is int and 0 <= c < 28 for c in p['choices']) and
                type(p['sites']) is str and len(p['sites']) == 56 and
                all(v < 128 and not v & 1 for v in bytes.fromhex(p['sites'])), 'invalid purchase record')
        key = p['parent'], tick
        require(key in seeds and seeds[key]['column'] == p['column'], 'purchase landing differs')
        bought[p['parent']] = p
    require(set(bought) == {s['parent'] for s in seeds.values() if s['birth_tick'] == tick},
            'incomplete purchase inventory')
    return records


def check_row(row, tick, stop, result, lives, seeds):
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
    require(all(len(v) == len(bank.FIELDS) and v[bank.FIELDS.index('sun')] == strength for v in visits),
            'wrong visit fields/light')
    inventory = check_inventory(checks, purchases, count, tick, stop, slots, lives, seeds, climate['cold'])
    return plants, shapes, inventory, phase


def family(identity, lives, seeds, base, stop):
    life = lives[identity]
    children = [p for p in lives.values() if p['parent'] == identity and p['birth_tick'] > base]
    grandchildren = [p for p in lives.values() if p['parent'] in {c['id'] for c in children}]
    return dict(life=life, survival={str(d): population.survival(life, stop, d) for d in (1, 16, 32)},
                alive_at_horizon=life['death_tick'] is None,
                new_seeds=[s for s in seeds.values() if s['parent'] == identity and s['birth_tick'] > base],
                inherited_seeds=[s for s in seeds.values() if s['parent'] == identity and s['birth_tick'] <= base and
                                 (s['end_tick'] is None or s['end_tick'] > base)],
                children=[dict(life=p, seed=next(s for s in seeds.values() if s['child_id'] == p['id']),
                               survival={str(d): population.survival(p, stop, d) for d in (1, 16, 32)},
                               seeds_created=p['seeds_created']) for p in children],
                grandchildren=[p['id'] for p in grandchildren],
                established_grandchildren=[p['id'] for p in grandchildren
                                           if population.survival(p, stop, 1) == 'confirmed'])


def analyze_world(run, world, evidence, base, stop, event_key):
    result = run['result']
    start = base + STEP
    lives, seeds = bank.descendants.index_records(result['lineages'], result['seeds'], 0, stop)
    require(set(evidence) == {'boundary', 'rows'} and type(evidence['rows']) is list and
            len(evidence['rows']) == (stop - base) // STEP, 'incomplete evidence window')
    event = result.get(event_key)
    observed = copy.deepcopy(lives)
    if event:
        require(event['tick'] == base, 'event is not at the observation boundary')
        observed[event['lineage']]['death_tick'] = None
    anchor, _, _, _ = check_row(evidence['boundary'], base, stop, result, observed, seeds)
    for i, packed in anchor.items():
        adults.transfers(resources.unpack(packed, observed[i], base), observed[i])
    if event:
        stage = anchor[event['lineage']][0][-1]
        require([event['energy'], event['water'], event['nodes']] == [stage[0], stage[1], stage[4]],
                'event discard does not match boundary stores/body')
    last, before_plants = evidence['boundary'][1], anchor
    totals, seed_checks, changes = {}, {}, []
    states, occupancy = [[base, last]], Counter()
    for tick, row in zip(range(start, stop + STEP, STEP), evidence['rows'], strict=True):
        plants, shapes, inventory, phase = check_row(row, tick, stop, result, lives, seeds)
        slots, visits = row[1], {v[0]: dict(zip(bank.FIELDS, v, strict=True)) for v in row[2]}
        if slots != last:
            changes.append(prior.slot_change(last, slots, tick, lives))
            states.append([tick, slots])
        occupancy[f'{len(shapes)}/{len(slots)}'] += 1
        for i, packed in plants.items():
            life, before = lives[i], before_plants[i][0][-1] if i in before_plants else None
            plant = resources.unpack(packed, life, tick)
            if i in shapes:
                transfer, _ = previous.check_focal_sample(visits[i], shapes[i], packed, life, tick, before)
            else:
                transfer = adults.transfers(plant, life, before)
                require(not visits[i]['produced'], 'dead plant purchased a seed')
            pay = population.payment(plant, transfer, before_plants[i][2] if i in before_plants else None, tick, phase)
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
        last, before_plants = slots, plants
    require(states == run['receipts']['stand']['states'] and dict(occupancy) == run['receipts']['stand']['occupancy'] and
            len(last) == result['plant_slots'], 'stored chronology differs from capture')
    for key, seed in seeds.items():
        count = bank.samples(max(start, seed['birth_tick'] + STEP), min(stop, seed['end_tick'] or stop))
        require(seed_checks.get(f'{key[0]}:{key[1]}', {}).get('checks', 0) == count, 'incomplete seed checks')
    for i, life in lives.items():
        count = bank.samples(max(start, life['birth_tick']), min(stop, life['death_tick'] or stop))
        record = totals.get(str(i))
        require((record['samples'] if record else 0) == count, 'incomplete plant resource history')
        if record:
            purchases = sum(s['parent'] == i and s['birth_tick'] > base for s in seeds.values())
            require(record['budget']['energy']['reproduction'] == 48 * purchases and
                    record['budget']['water']['reproduction'] == 24 * purchases, 'purchase costs differ')
    access = bank.analyze_visits([[r[0], r[2]] for r in evidence['rows']], result, start, stop)
    focal_ids = world['focal']
    incumbents = [i for i, p in lives.items() if p['birth_tick'] <= base and i not in focal_ids]
    stock = bank.residence(result, start, stop, incumbents, focal_ids)
    require(access.pop('resident_samples') == sorted([s['parent'], s['birth_tick'], s['slot_samples']] for s in stock['seeds']),
            'bank residence differs from visit census')
    parents = {p['id']: p for p in access['plants']}

    def describe(identity):
        return family(identity, lives, seeds, base, stop) | dict(resources=totals.get(str(identity)), access=parents.get(identity))

    recruits = {str(i): describe(i) | dict(seed=next(s for s in seeds.values() if s['child_id'] == i),
                parent_cohort='focal' if p['parent'] in focal_ids else
                'first_recruit' if p['parent'] in world['first_recruits'] else
                'imposed_death' if lives[p['parent']]['environmental_death'] else
                'incumbent' if lives[p['parent']]['birth_tick'] <= base else 'new_recruit')
                for i, p in lives.items() if p['birth_tick'] > base}
    disturbance = None
    if event:
        released = [c for c in changes if event['lineage'] in c['removed']]
        require(len(released) <= 1, 'duplicate reclamation')
        release = released[0] if released else None
        births = sorted((r['life'] for r in recruits.values()), key=lambda p: (p['birth_tick'], p['id']))
        first = births[0] if births else None
        same_column = [p for p in births if p['column'] == event['column']]
        disturbance = dict(event=event, reclamation=release,
                           decomposition_ticks=release['tick'] - base if release else None,
                           first_germination=first, first_exact_column_refill=same_column[0] if same_column else None,
                           new_clear_column_births=[p['id'] for p in births if release and
                               p['column'] in release['newly_clear_columns'] and p['birth_tick'] >= release['tick']],
                           delay_reclamation_to_germination=first['birth_tick'] - release['tick'] if release and first else None)
    natural = [p for p in lives.values() if p['death_tick'] is not None and p['death_tick'] > base and
               not p['environmental_death']]
    return dict(focal={str(i): describe(i) for i in focal_ids},
                first_recruits={str(i): describe(i) for i in world['first_recruits']},
                recruits=recruits, plants=totals, seed_checks=seed_checks, changes=changes,
                disturbance=disturbance, access=access, residence=stock, natural_deaths=natural,
                incumbent_natural_deaths=[p['id'] for p in natural if p['birth_tick'] <= base],
                final=dict(living=result['living'], stored=result['plant_slots'], nodes=result['nodes'], seeds=result['seed_bank']))


def compare(arms, world):
    control, treatment = (arms[a] for a in ('control', 'treatment'))
    excluded = {str(world['target']), *control['recruits'], *treatment['recruits']}
    common = sorted((set(control['plants']) & set(treatment['plants'])) - excluded, key=int)
    return dict(matched_incumbents=[int(i) for i in common], arms={phase: dict(
        births=len(a['recruits']), natural_deaths=len(a['natural_deaths']),
        cohorts={name: dict(new_seeds=sum(len(p['new_seeds']) for p in a[name].values()),
                           children=sum(len(p['children']) for p in a[name].values()),
                           established_children=sum(c['survival']['1'] == 'confirmed'
                                                    for p in a[name].values() for c in p['children']),
                           established_grandchildren=sum(len(p['established_grandchildren']) for p in a[name].values()))
                 for name in ('focal', 'first_recruits', 'recruits')},
        final=a['final'], resources=prior.exposure(list(a['plants'].values())),
        matched_resources=prior.exposure([a['plants'][i] for i in common]),
        per_matched_plant={i: prior.exposure([a['plants'][i]]) for i in common}) for phase, a in arms.items()})
