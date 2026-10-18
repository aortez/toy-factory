#!/usr/bin/env python3
"""Offline readiness, seed-bank allocation and germination of late replacements."""

from __future__ import annotations

import argparse
from collections import Counter
from functools import cache
import gzip
import json
from pathlib import Path
import sys

import garden_landing_followup as followup
import garden_landing_bank_access as bank
import garden_landing_adults as adults
import garden_landing_root_allocation_audit as resources
import garden_landing_seed_spending_audit as spending
from garden_experiments import digest
from garden_landing_energy_audit import archived_sources
from garden_landing_founders import write_gzip
from garden_landing_root_allocation_audit import fingerprint
from garden_resources import require

ROOT, STEP, DAY, BASE, STOP = followup.ROOT, followup.STEP, followup.DAY, followup.BASE, followup.STOP
START = BASE + STEP
RULE = 'garden-landing-reproductive-access-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-reproductive-access-protocol.md'
PROTOCOL_SHA = 'e7aff6d00dd604d649703b5d78563b859b72ef95728ab190f4b9c69f4f2504f4'
INPUT = 'benchmarks/garden-seasons/landing-followup-results.json.gz'
INPUT_SHA = 'b13ce089efa12b431f48a35499be93e7cf7af83a636006b2898b283762e12336'
MANIFEST_SHA = '4b544d137a9ec8f2da3afdfb4b23ee3a300422fb871e10a267527b2f7fcbb1df'
KINDS = ('stand', 'adult', 'reach')
RUNTIME = ('src/garden_world.c', 'src/garden_world.h', 'src/garden_reproduction_audit.h',
           'sim/garden_landing_plant_trace.c', 'sim/garden_landing_recruitment.c', 'sim/garden_landing_reach.c')
SOURCES = ('sim/garden_landing_reproductive_access.py', 'sim/garden_landing_followup.py',
           'sim/garden_landing_bank_access.py', 'sim/garden_landing_adults.py',
           'sim/garden_landing_root_allocation_audit.py', 'sim/garden_landing_seed_spending_audit.py',
           'sim/garden_landing_recovery.py', 'sim/garden_descendants.py',
           'sim/garden_landing_vacancy_sequence.py', 'sim/garden_landing_soil_audit.py',
           'sim/garden_landing_founders.py', 'sim/garden_experiments.py', 'sim/garden_resources.py',
           'sim/garden_landing_population.py', 'sim/garden_landing_order.py',
           'sim/garden_landing_dawn.py', 'sim/garden_landing_dawn_audit.py',
           'sim/garden_landing_light_audit.py', 'sim/garden_landing_energy_audit.py')
BLOCKERS = ('dormant', 'moisture', 'light', 'plant_capacity', 'node_capacity', 'spacing', 'cold')


@cache
def inputs():
    require(digest(ROOT / PROTOCOL) == PROTOCOL_SHA and digest(ROOT / INPUT) == INPUT_SHA,
            'reproductive access protocol/input changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream:
        value = json.load(stream)
    followup.check_value(value)
    cohort = {key: [r['life']['id'] for r in a['censored_replacements']]
              for key, a in value['analysis'].items()}
    require(len(cohort) == 32 and sum(map(len, cohort.values())) == 7 and all(
        r['survival']['32'] == 'confirmed' for a in value['analysis'].values() for r in a['censored_replacements']),
        'wrong frozen survivor cohort')
    return value, cohort


def provenance():
    value, cohort = inputs()
    return dict(rule=RULE, protocol_sha256=PROTOCOL_SHA, input_sha256=INPUT_SHA,
                raw_manifest_sha256=MANIFEST_SHA, native_runs=0, training_runs=0,
                interval=[START, STOP], boundary_tick=BASE, cohort=cohort,
                implementation={p: value['source_sha256'][p] for p in RUNTIME},
                sources={p: digest(ROOT / p) for p in SOURCES})


def sun_at(seed, tick):
    climate = followup.previous.climate(seed, tick)
    phase = (64 + tick // STEP) % 256
    strength = spending.population.dawn.previous.audit.strength(phase, climate['light_percent'])
    return climate, phase, strength


def visit_order(tick, slots, visits, result):
    require(type(slots) is list and len(slots) == len(set(slots)) <= 8 and
            all(type(i) is int and i > 0 for i in slots), 'invalid stored order')
    rotation = result.get('seed_order_probe')
    after = spending.population.order.AT
    first = (tick - after) // 60 % len(slots) if rotation and slots and tick > after and tick % 60 == 0 else 0
    require([v[0] for v in visits] == slots[first:] + slots[:first], 'reproduction order/coverage changed')


def seed_check(raw, encoded, tick, seed, slots, lives, cold):
    require(type(raw) is list and len(raw) == 11 and all(type(v) is int for v in raw), 'invalid seed check')
    parent, age, column, mask, moisture, light, plants, nodes, outcome, child, opened = raw
    require((parent, tick - age * STEP, column) == (seed['parent'], seed['birth_tick'], seed['column']) and
            age > 0 and 0 <= nodes <= 256 and plants == len(slots) <= 8, 'seed identity/census differs')
    expected = 0 if seed['end_tick'] != tick else {'expired': 1, 'germinated': 2}[seed['outcome']]
    require(outcome == expected and child == (seed['child_id'] if outcome == 2 else 0), 'seed fate differs')
    if outcome == 1:
        require(age == seed['lifetime_ecology_ticks'] and mask == moisture == light == 0 and
                opened == -1 and encoded is None, 'expiry is not an observed open site')
        return
    require(age < seed['lifetime_ecology_ticks'] and 0 <= moisture <= 255 and 0 <= light <= 255 and
            type(encoded) is str and len(encoded) == 56, 'invalid viability/site encoding')
    sites = bytes.fromhex(encoded)
    require(all(v < 128 and not v & 1 for v in sites), 'invalid mature site masks')
    spacing = any(abs(column - lives[i]['column']) < 3 for i in slots)
    bits = (age < 8, moisture < 12, light < 80, plants == 8, nodes + 4 > 256, spacing, cold)
    require(mask == sum(1 << i for i, v in enumerate(bits) if v) and
            sites[column] == (mask & ~1) and opened == sum(v == 0 for v in sites) and
            (mask == 0) == (outcome == 2), 'germination gate mismatch')


def check_focal_sample(visit, body, packed, life, tick, before):
    row = resources.unpack(packed, life, tick)
    transfer = adults.transfers(row, life, before)
    stages = row['stages']
    require(type(body) is list and len(body) == 3 and all(type(v) is int and v >= 0 for v in body) and
            body[:2] == [stages[-1][4], row['roots']] and body[2] <= body[0] <= 32 and
            body[2] == sum(visit[k] for k in ('immature', 'spent', 'ready')) and
            (visit['ready'] == 0) == (visit['flower'] == 65535), 'focal flower/body inventory differs')
    require(stages[3][:3] == [visit['energy'], visit['water'], visit['stress']] and
            [stages[3][j] - stages[4][j] for j in (0, 1)] == [48 * visit['produced'], 24 * visit['produced']],
            'focal pre-seed stores/debits differ')
    return transfer, stages[-1]


def seed_summary(seed, records, lives):
    expected = range(seed['birth_tick'] + STEP, min(seed['end_tick'] or STOP, STOP) + STEP, STEP)
    require([r[0] for r in records] == list(expected), 'incomplete focal seed checks')
    masks, blockers, expiry, dormant = Counter(), Counter(), 0, 0
    for tick, raw, encoded, slots in records:
        cold = followup.previous.climate(0xf7ee4528, tick)['cold']
        seed_check(raw, encoded, tick, seed, slots, lives, cold)
        if raw[8] == 1:
            expiry += 1
        elif raw[1] < 8:
            dormant += 1
        else:
            masks[str(raw[3])] += 1
            for i, name in enumerate(BLOCKERS):
                blockers[name] += bool(raw[3] & (1 << i))
    return dict(seed=seed, checks=len(records), dormant=dormant, expiry_only=expiry,
                mature_masks=dict(masks), mature_blockers=dict(blockers), right_censored=seed['outcome'] == 'pending')


def analyze_world(result, identities, evidence):
    lives, seeds = bank.descendants.index_records(result['lineages'], result['seeds'], 0, STOP)
    rows = evidence['visits']
    require(len(rows) == (STOP - BASE) // STEP, 'incomplete production window')
    expected_focal = {str(i) for i in identities}
    require(set(evidence['plants']) == expected_focal and set(evidence['boundary']) == expected_focal,
            'missing/extra focal resources')
    for tick, slots, visits in rows:
        visit_order(tick, slots, visits, result)
        living = {i for i, p in lives.items() if bank.previous.present(p, tick, living=True)}
        require(living <= set(slots) <= set(lives) and all(lives[i]['birth_tick'] <= tick for i in slots),
                'wrong stored/live inventory')
        _, _, strength = sun_at(int(result['seed'], 16), tick)
        require(all(v[bank.FIELDS.index('sun')] == strength for v in visits), 'wrong reproduction light')
    access = bank.analyze_visits([[tick, visits] for tick, _, visits in rows], result, START, STOP)
    stock = bank.residence(result, START, STOP, [i for i, p in lives.items() if p['birth_tick'] <= BASE and i not in identities], identities)
    require(access.pop('resident_samples') == sorted([s['parent'], s['birth_tick'], s['slot_samples']] for s in stock['seeds']),
            'seed residence and ordered census differ')
    indexed = {p['id']: p for p in access['plants']}
    focal = {}
    for identity in identities:
        text = str(identity)
        require(len(evidence['plants'][text]) == len(rows) and lives[identity]['death_tick'] is None,
                'incomplete survivor samples')
        anchor = evidence['boundary'][text]
        adults.transfers(resources.unpack(anchor, lives[identity], BASE), lives[identity])
        before, total = anchor[0][-1], adults.budget()
        shapes, states, daytime_masks, margins = [], Counter(), Counter(), []
        readiness = Counter(cadence_daylight=0, ready_flower=0, eligible_ignoring_bank=0, purchased=0)
        for n, ((tick, _, visits), sample) in enumerate(zip(rows, evidence['plants'][text], strict=True)):
            visit = dict(zip(bank.FIELDS, next(v for v in visits if v[0] == identity), strict=True))
            packed, body = sample
            transfer, before = check_focal_sample(visit, body, packed, lives[identity], tick, before)
            adults.accumulate(total, transfer, n == 0)
            shape = [*body, packed[3]]  # nodes, roots, flowers, active leaves
            if not shapes or shape != shapes[-1][1]:
                shapes.append([tick, shape])
            state = 'ready' if visit['ready'] else 'no_flower' if body[2] == 0 else 'immature' if visit['immature'] else 'spent'
            states[state] += 1
            if tick % 60 == 0 and visit['sun'] > 24:
                readiness['cadence_daylight'] += 1
                readiness['ready_flower'] += visit['ready'] > 0
                readiness['eligible_ignoring_bank'] += (visit['blockers'] & ~bank.BANK) == 0
                readiness['purchased'] += visit['produced']
                daytime_masks[str(visit['blockers'])] += 1
                margins.append([visit['energy'] - visit['energy_required'], visit['water'] - visit['water_required']])
        expected_purchases = [s['birth_tick'] for s in seeds.values() if s['parent'] == identity and s['birth_tick'] > BASE]
        require(indexed[identity]['purchases'] == expected_purchases and total['energy']['reproduction'] == 48 * len(expected_purchases) and
                total['water']['reproduction'] == 24 * len(expected_purchases), 'focal ledger/debits disagree')
        focal[text] = dict(life=lives[identity], resources=total, morphology=shapes, flower_states=dict(states),
                           readiness=dict(readiness), cadence_daylight_masks=dict(daytime_masks),
                           daylight_margin_ranges=[[min(v[j] for v in margins), max(v[j] for v in margins)] for j in (0, 1)],
                           access=indexed[identity])
    purchased = {(s['parent'], s['birth_tick']): s for s in seeds.values() if s['parent'] in identities and s['birth_tick'] > BASE}
    require(set(evidence['seeds']) == {f'{p}:{t}' for p, t in purchased}, 'missing/extra focal seeds')
    offspring = {}
    for (parent, birth), seed in purchased.items():
        key = f'{parent}:{birth}'
        item = evidence['seeds'][key]
        require(item['purchase']['parent'] == parent and item['purchase']['column'] == seed['column'] and
                seed['column'] in item['purchase']['choices'], 'focal purchase identity differs')
        offspring[key] = seed_summary(seed, item['checks'], lives)
    attempts = sum(bank.samples(max(START, s['birth_tick'] + STEP), min(STOP, s['end_tick'] or STOP)) for s in seeds.values())
    require(evidence['checked_seed_attempts'] == attempts and evidence['checked_purchases'] ==
            sum(s['birth_tick'] > BASE for s in seeds.values()), 'complete seed inventory count differs')
    return dict(access=access, residence=stock, focal=focal, seeds=offspring)


def check_inventory(adult, reach, slots, lives, seeds, cold):
    """Check every resident seed, including sequential germination within a step."""
    tick, seen = adult['tick'], set()
    born = {i for i, p in lives.items() if p['birth_tick'] == tick}
    before = [i for i in slots if i not in born]
    records = {}
    for raw, check in zip(adult['seeds'], reach['checks'], strict=True):
        require(type(check) is list and len(check) == 7 and
                check[:4] == raw[:4] and check[4:6] == raw[8:10], 'adult/reach check differs')
        key = raw[0], tick - raw[1] * STEP
        require(key in seeds and key not in seen, 'unknown/duplicate seed attempt')
        seen.add(key)
        seed_check(raw, check[6], tick, seeds[key], before, lives, cold)
        records[key] = [tick, raw, check[6], list(before)]
        if raw[8] == 2:
            require(raw[9] in born and raw[9] not in before, 'unexpected germinated child')
            before.append(raw[9])
    require(before == slots and seen == {k for k, s in seeds.items()
            if s['birth_tick'] < tick <= (s['end_tick'] or STOP)}, 'incomplete seed/child inventory')
    require(adult['bank'] == sum(s['birth_tick'] <= tick < (s['end_tick'] or STOP + STEP)
                               for s in seeds.values()), 'post-step bank differs')
    purchases = {}
    for p in reach['purchases']:
        require(set(p) == {'parent', 'column', 'origin', 'dispersal', 'choices', 'sites'} and
                p['parent'] in lives and p['parent'] not in purchases and
                p['origin'] == lives[p['parent']]['column'] and p['column'] in p['choices'] and
                all(type(c) is int and 0 <= c < 28 for c in p['choices']) and
                type(p['sites']) is str and len(p['sites']) == 56 and
                all(v < 128 and not v & 1 for v in bytes.fromhex(p['sites'])), 'invalid purchase record')
        key = p['parent'], tick
        require(key in seeds and seeds[key]['column'] == p['column'], 'purchase landing differs')
        purchases[p['parent']] = p
    require(set(purchases) == {s['parent'] for s in seeds.values() if s['birth_tick'] == tick},
            'incomplete purchase inventory')
    return records, purchases


def extract_world(paths, run, identities):
    result = run['result']
    lives, seeds = bank.descendants.index_records(result['lineages'], result['seeds'], 0, STOP)
    evidence = dict(visits=[], plants={str(i): [] for i in identities}, boundary={}, seeds={},
                    checked_seed_attempts=0, checked_purchases=0)
    selected = {k for k, s in seeds.items() if s['parent'] in identities and s['birth_tick'] > BASE}
    streams = {k: followup.trace_rows(paths[k], k, STEP if k == 'reach' else BASE, STOP, result) for k in KINDS}
    tail = (r for r in streams['reach'] if r[0]['tick'] >= BASE)
    try:
        for (stand, _), (adult, _), (reach, _) in zip(streams['stand'], streams['adult'], tail, strict=True):
            tick = stand['tick']
            climate, phase, strength = sun_at(int(result['seed'], 16), tick)
            require(adult['tick'] == reach['tick'] == tick and stand['climate'] == climate and
                    adult['sun'] == [phase, strength] and adult['cold'] == climate['cold'] and
                    adult['season'] == climate['day'] // 4 and stand['seed_lifetime_ecology_ticks'] == 8192,
                    'trace clocks/climate differ')
            slots = stand['plant_order']
            living = {i for i, p in lives.items() if bank.previous.present(p, tick, living=True)}
            bodies = {p['id']: p for p in stand['bodies']}
            plants = {p['id']: p for p in adult['plants']}
            require(len(bodies) == len(stand['bodies']) and set(bodies) == living and
                    len(plants) == len(adult['plants']) and set(plants) ==
                    living | {i for i, p in lives.items() if p['death_tick'] == tick}, 'body/resource coverage differs')
            require(all(p['birth'] == lives[i]['birth_tick'] for i, p in plants.items()) and
                    all(b['species'] == lives[i]['species'] for i, b in bodies.items()), 'body/resource identity differs')
            require(all(set(v) == set(bank.FIELDS) for v in stand['reproduction']), 'production visit fields differ')
            visits = [[v[k] for k in bank.FIELDS] for v in stand['reproduction']]
            visit_order(tick, slots, visits, result)
            checks, purchases = check_inventory(adult, reach, slots, lives, seeds, climate['cold'])
            if tick == BASE:
                evidence['boundary'] = {str(i): resources.pack(plants[i]) for i in identities}
                continue
            evidence['visits'].append([tick, slots, visits])
            for i in identities:
                evidence['plants'][str(i)].append([resources.pack(plants[i]),
                                                  [bodies[i][k] for k in ('nodes', 'roots', 'flowers')]])
            evidence['checked_seed_attempts'] += len(checks)
            evidence['checked_purchases'] += len(purchases)
            for parent, purchase in purchases.items():
                if (parent, tick) in selected:
                    evidence['seeds'][f'{parent}:{tick}'] = dict(purchase=purchase, checks=[])
            for key, record in checks.items():
                if key in selected:
                    evidence['seeds'][f'{key[0]}:{key[1]}']['checks'].append(record)
    finally:
        tail.close()
        for stream in streams.values():
            stream.close()
    return evidence


def check_value(value):
    original, cohort = inputs()
    expected = provenance()
    require(set(value) == {*expected, 'evidence', 'analysis', 'receipt_sha256'} and
            all(value[k] == v for k, v in expected.items()), 'audit provenance differs')
    require(set(value['evidence']) == set(value['analysis']) == set(cohort), 'incomplete audit panel')
    for key, identities in cohort.items():
        run, evidence = original['runs']['extension'][key], value['evidence'][key]
        require(set(evidence) == {'visits', 'plants', 'boundary', 'seeds', 'checked_seed_attempts', 'checked_purchases'},
                'unexpected evidence fields')
        states, cursor = run['receipts']['stand']['states'], 0
        for tick, slots, _ in evidence['visits']:
            while cursor + 1 < len(states) and states[cursor + 1][0] <= tick:
                cursor += 1
            require(slots == states[cursor][1], 'stored order differs from captured receipt')
        require(value['analysis'][key] == analyze_world(run['result'], identities, evidence),
                'derived reproduction audit differs: ' + key)
    require(value['receipt_sha256'] == fingerprint({k: v for k, v in value.items() if k != 'receipt_sha256'}),
            'audit receipt changed')


def extract(bundle):
    original, cohort = inputs()
    expected = provenance()
    require(digest(bundle / 'manifest.json') == MANIFEST_SHA, 'wrong raw manifest')
    manifest = json.loads((bundle / 'manifest.json').read_text())
    require(manifest['rule'] == followup.RULE, 'wrong raw bundle')
    for name in ('source.tar.gz', 'capture.json', 'model.tgl', 'protocol.md'):
        followup.artifact(bundle, dict(path=name, sha256=manifest['artifacts'][name]))
    require(json.loads((bundle / 'capture.json').read_text()) == original and
            archived_sources(bundle / 'source.tar.gz') == original['source_sha256'] and
            digest(bundle / 'model.tgl') == original['model_sha256'] and
            digest(bundle / 'protocol.md') == followup.PROTOCOL_SHA, 'raw provenance changed')
    value = dict(expected, evidence={}, analysis={})
    for key, identities in sorted(cohort.items()):
        run = original['runs']['extension'][key]
        paths = {}
        for kind in KINDS:
            item = run['traces'][kind]
            require(manifest['artifacts'][item['path']] == item['sha256'], 'manifest/trace identity differs')
            paths[kind] = followup.artifact(bundle, item)
        evidence = extract_world(paths, run, identities)
        value['evidence'][key] = evidence
        value['analysis'][key] = analyze_world(run['result'], identities, evidence)
        require(all(digest(paths[k]) == run['traces'][k]['sha256'] for k in KINDS), 'trace changed during extraction')
        print(key + ': reproduction, resources and seed inventory verified', flush=True)
    require(digest(bundle / 'manifest.json') == MANIFEST_SHA and provenance() == expected and
            digest(ROOT / INPUT) == INPUT_SHA and digest(ROOT / PROTOCOL) == PROTOCOL_SHA, 'audit input changed')
    value['receipt_sha256'] = fingerprint(value)
    check_value(value)
    return value


def export(bundle, out):
    require(not out.exists() and not out.is_symlink(), 'fresh output required')
    value = extract(bundle)
    write_gzip(out, value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--out', type=Path, help='fresh portable audit; requires --bundle')
    mode.add_argument('--verify', type=Path, help='verify saved portable evidence without raw traces')
    parser.add_argument('--bundle', type=Path, help='raw follow-up bundle; optional re-extraction with --verify')
    args = parser.parse_args()
    require(not args.out or args.bundle, '--out requires --bundle')
    if args.out:
        export(args.bundle.resolve(), args.out)
    else:
        with gzip.open(args.verify, 'rt') as stream:
            value = json.load(stream)
        check_value(value)
        if args.bundle:
            require(extract(args.bundle.resolve()) == value, 'raw re-extraction differs')
    print('verified ' + RULE + '; zero native/training runs')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, TypeError, OSError, StopIteration) as error:
        print('error: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
