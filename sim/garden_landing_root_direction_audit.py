#!/usr/bin/env python3
"""Audit the saved first day of the wet-root A/B; never launch a simulator."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from functools import cache
import gzip
import hashlib
from itertools import islice
import json
from pathlib import Path
import sys

import garden_landing_root_direction as previous
from garden_experiments import digest
from garden_resources import require

ROOT, STEP = previous.ROOT, previous.STEP
population, adults = previous.population, previous.population.adults
DAY = population.DAY
ARMS = previous.ARMS
RULE = 'garden-landing-root-direction-audit-v1'
INPUT = 'benchmarks/garden-seasons/landing-root-direction-results.json.gz'
INPUT_SHA = '18f81abb8f76fc0a2fb4bf1e86b6b659984cadc9b2f507382187075a56b9122b'
MANIFEST_SHA = '814b0af751397b91db4d618ef6606dac466eb30916013ce82827e61ee4924a0e'
PROTOCOL = 'benchmarks/garden-seasons/landing-root-direction-audit-protocol.md'
FIRST_CASE = 'f7ee4528-fixed-control'
PREFIX_SHA = {
    'control': '55674da45e77638a0972aa492b72abf27a31f48e222a00c077a87cefd78caa64',
    'candidate': 'c170a8e98191d2378b3c7862cd715ca2f6380686e765d1dad0a338b4405f5f16',
}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


@cache
def load_input():
    require(digest(ROOT / INPUT) == INPUT_SHA, 'root direction input changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream:
        value = json.load(stream)
    previous.check_value(value)
    require(value['cases'][0]['case']['id'] == FIRST_CASE and all(
        value['settings'][k] == 'OFF' for k in ('TOY_FACTORY_GARDEN_WATER_HEADROOM',
        'TOY_FACTORY_GARDEN_LEAF_MAINTENANCE', 'TOY_FACTORY_GARDEN_SEED_RESERVE')),
        'unsupported captured accounting')
    return value


def birth_identity(life):
    return {k: life[k] for k in ('id', 'parent', 'generation', 'birth_tick', 'column', 'species')}


def validate_prefix(rows):
    require(type(rows) is list and len(rows) == DAY // STEP, 'incomplete first-day prefix')
    for tick, step in zip(range(STEP, DAY + STEP, STEP), rows, strict=True):
        require(type(step) is list and len(step) == 3 and
                all(type(row['tick']) is int and row['tick'] == tick for row in step),
                'missing/reordered first-day sample')


def analyze_arm(rows, saved, enabled):
    validate_prefix(rows)
    result = saved['result']
    lives = {p['id']: p for p in result['lineages'] if p['birth_tick'] <= DAY}
    require(len(lives) == 5 and all(p['birth_tick'] == p['parent'] == p['generation'] == 0 and
            p['death_tick'] > DAY for p in lives.values()), 'not the five living founders')
    plants = {i: {'birth': birth_identity(life), 'resources': adults.budget(), 'payments': 0,
                  'unpaid': {'energy': 0, 'water': 0}, 'purchases': [], 'first_flower': None,
                  'first_overflow': {'energy': None, 'water': None}} for i, life in lives.items()}
    old, shapes, rewrites = {}, {}, []
    for s, r, d in rows:
        tick = s['tick']
        require(r['sun'][0] == (64 + tick // STEP) % 256 and
                s['plant_order'] == list(lives) and
                [p['id'] for p in r['plants']] == list(lives) and
                [b['id'] for b in s['bodies']] == list(lives), 'founder identity/order differs')
        grouped, directions = defaultdict(list), defaultdict(list)
        for b, direction in zip(s['bids'], d['bids'], strict=True):
            require(b['id'] in lives, 'unknown bid identity')
            change = previous.check_bid(b, direction, lives[b['id']], enabled)
            grouped[b['id']].append(b)
            directions[b['id']].append(direction)
            if change['changed']:
                rewrites.append({'tick': tick, 'id': b['id'], 'tip': b['tip']})
        bodies = {b['id']: b for b in s['bodies']}
        for p in r['plants']:
            i = p['id']
            require(p['birth'] == lives[i]['birth_tick'], 'wrong founder birth')
            receipt = adults.transfers({'tick': tick, **p}, lives[i], old.get(i))
            target = plants[i]
            adults.accumulate(target['resources'], receipt, tick == STEP)
            body = bodies[i]
            require((body['nodes'], body['roots'], body['species']) ==
                    (p['stages'][-1][4], p['roots'], lives[i]['species']), 'body/receipt differs')
            prior_roots = shapes[i]['roots'] if i in shapes else 2
            pay = population.payment(p, receipt, prior_roots, tick, r['sun'][0])
            if pay:
                target['payments'] += 1
                for name in target['unpaid']:
                    target['unpaid'][name] += pay[name]['unpaid']
            bids = grouped[i]
            if bids:
                # Both baseline dawn modes are inactive for founders.
                population.check_growth(s, r, lives[i], bids, body, shapes.get(i), 'control')
                winner = population.dawn.winner(bids, dawn=True)
                index = next(j for j, b in enumerate(bids) if b['tip'] == winner['tip'])
                b, direction = bids[index], directions[i][index]
                if winner['eligible'] and b['action'] != 0:
                    checked = previous.check_bid(b, direction, lives[i], enabled)
                    chosen = checked['after']
                    target['purchases'].append({'tick': tick, 'tip': b['tip'], 'tissue': b['tissue'],
                        'action': b['action'], 'at': direction['at'],
                        'destination': direction['candidates'][chosen][2:4] if chosen is not None else None,
                        'allocated': body['nodes'] > b['nodes'], 'rewritten': checked['changed'],
                        'raw_order': direction.get('raw_order', direction['order']), 'order': direction['order'],
                        'cost': [receipt[n]['growth'] for n in ('energy', 'water')]})
            else:
                require(all(receipt[n]['growth'] == 0 for n in ('energy', 'water')) and
                        p['stages'][2] == p['stages'][3], 'unobserved growth')
            if body['flowers'] and target['first_flower'] is None:
                target['first_flower'] = tick
            for name in target['first_overflow']:
                if receipt[name]['overflow'] and target['first_overflow'][name] is None:
                    target['first_overflow'][name] = tick
            old[i], shapes[i] = p['stages'][-1], body
        population.check_visits(s, r, result, lives, set(lives))
    for i, target in plants.items():
        target['last_body'] = shapes[i]
        target['seeds'] = [s for s in result['seeds'] if s['parent'] == i and s['birth_tick'] <= DAY]
        for name, cost in (('energy', 48), ('water', 24)):
            require(target['resources'][name]['reproduction'] == cost * len(target['seeds']),
                    'first-day seed spending differs')
            target['resources'][name]['retained'] = (target['resources'][name]['income'] -
                                                   target['resources'][name]['overflow'])
        target['paid_by_action'] = dict(Counter(('root' if e['tissue'] else 'shoot') +
            ('_allocation' if e['allocated'] else '_closure') for e in target['purchases']))
    totals = {name: {key: sum(p['resources'][name][key] for p in plants.values())
                    for key in next(iter(plants.values()))['resources'][name]} for name in ('energy', 'water')}
    return {'plants': list(plants.values()), 'totals': totals, 'rewrites': rewrites}


def plant_sample(step, identity):
    s, r, _ = step
    return {'tick': s['tick'], 'resource': next(p for p in r['plants'] if p['id'] == identity),
            'body': next(p for p in s['bodies'] if p['id'] == identity),
            'reproduction': next(p for p in s['reproduction'] if p['id'] == identity)}


def physical_purchase(event):
    # Global node indices can shift when another plant allocates a node. A
    # different index or unused fallback ranking alone is not different growth.
    return None if event is None else {k: event[k] for k in
        ('tissue', 'action', 'at', 'destination', 'allocated', 'cost')}


def compare(rows, analysis):
    differences = []
    for a, b in zip(*(analysis[arm]['plants'] for arm in ARMS), strict=True):
        require(a['birth'] == b['birth'], 'unmatched founder')
        i = a['birth']['id']
        first = {}
        accessors = {'water_income': lambda x: x['resource']['uptake'][1][1],
                     'energy_income': lambda x: x['resource']['uptake'][0][1],
                     'stores': lambda x: x['resource']['stages'][-1][:2],
                     'body': lambda x: [x['body'][k] for k in ('nodes', 'roots', 'flowers')],
                     'reproduction': lambda x: x['reproduction']['produced']}
        for left, right in zip(rows['control'], rows['candidate'], strict=True):
            x, y = plant_sample(left, i), plant_sample(right, i)
            for name, get in accessors.items():
                if name not in first and get(x) != get(y):
                    first[name] = {'tick': x['tick'], 'control': get(x), 'candidate': get(y)}
        shoot = [{e['tick']: e for e in p['purchases'] if e['tissue'] == 0} for p in (a, b)]
        for tick in sorted(set(shoot[0]) | set(shoot[1])):
            x, y = shoot[0].get(tick), shoot[1].get(tick)
            if physical_purchase(x) != physical_purchase(y):
                first['shoot_purchase'] = {'tick': tick, 'control': x, 'candidate': y}
                break
        differences.append({'id': i, 'first': first,
            'resources': {r: {k: b['resources'][r][k] - a['resources'][r][k]
                for k in a['resources'][r]} for r in ('energy', 'water')}})
    return {'plants': differences, 'totals': {r: {k: analysis['candidate']['totals'][r][k] -
            analysis['control']['totals'][r][k] for k in analysis['control']['totals'][r]}
            for r in ('energy', 'water')}}


def expected_checksums(value):
    return [{'case': e['case']['id'], 'arm': arm, 'repeat': label,
             'traces': e['arms'][arm]['runs'][label]['traces']}
            for e in value['cases'] for arm in ARMS for label in previous.LABELS]


def extract(bundle):
    """Hash complete input streams, but parse only the inclusive first-day prefix."""
    original = load_input()
    require(digest(bundle / 'manifest.json') == MANIFEST_SHA and
            digest(bundle / 'results.json.gz') == INPUT_SHA, 'wrong raw A/B bundle')
    manifest = json.loads((bundle / 'manifest.json').read_text())['artifacts']
    rows, checks = {}, []
    for entry in expected_checksums(original):
        for item in entry['traces'].values():
            path = (bundle / item['path']).resolve()
            require(path.is_relative_to(bundle.resolve()) and manifest.get(item['path']) == item['sha256'] and
                    digest(path) == item['sha256'], 'raw first-day source changed')
        case = next(e for e in original['cases'] if e['case']['id'] == entry['case'])
        run = case['arms'][entry['arm']]['runs'][entry['repeat']]
        reader = previous.streams(bundle, run, entry['arm'] == 'candidate')
        try:
            prefix = [list(step) for step in islice(reader, DAY // STEP)]
        finally:
            reader.close()
        validate_prefix(prefix)
        if entry['arm'] in rows:
            require(prefix == rows[entry['arm']], 'first days are not identical across baseline worlds/repeats')
        else:
            rows[entry['arm']] = prefix
        checks.append(entry | {'prefix_sha256': fingerprint(prefix)})
    return rows, checks


def check_value(value):
    require(value['rule'] == RULE and value['input_sha256'] == INPUT_SHA and
            value['raw_manifest_sha256'] == MANIFEST_SHA and value['protocol_sha256'] == digest(ROOT / PROTOCOL) and
            value['window'] == [STEP, DAY] and type(value['new_simulations']) is int and
            value['new_simulations'] == 0 and type(value['training_runs']) is int and value['training_runs'] == 0 and
            value['canonical_case'] == FIRST_CASE and set(value['rows']) == set(ARMS), 'wrong first-day provenance/scope')
    original = load_input()
    expected = expected_checksums(original)
    require(all(fingerprint(value['rows'][arm]) == PREFIX_SHA[arm] for arm in ARMS),
            'frozen first-day receipts changed')
    require(value['sources'] == [e | {'prefix_sha256': fingerprint(value['rows'][e['arm']])}
                                 for e in expected], 'wrong prefix/source coverage')
    analysis = {arm: analyze_arm(value['rows'][arm], original['cases'][0]['arms'][arm], arm == 'candidate')
                for arm in ARMS}
    require(value['analysis'] == analysis and value['comparison'] == compare(value['rows'], analysis),
            'first-day accounting/summary differs')


def export(bundle, out):
    require(not out.exists(), 'fresh output required')
    rows, sources = extract(bundle)
    original = load_input()
    analysis = {arm: analyze_arm(rows[arm], original['cases'][0]['arms'][arm], arm == 'candidate') for arm in ARMS}
    value = {'rule': RULE, 'input_sha256': INPUT_SHA, 'raw_manifest_sha256': MANIFEST_SHA,
             'protocol_sha256': digest(ROOT / PROTOCOL), 'window': [STEP, DAY], 'new_simulations': 0,
             'training_runs': 0, 'canonical_case': FIRST_CASE, 'sources': sources, 'rows': rows,
             'analysis': analysis, 'comparison': compare(rows, analysis)}
    check_value(value)
    out.parent.mkdir(parents=True, exist_ok=True)
    population.order.recovery.founders.write_gzip(out, value)
    print('Saved complete first-day receipts: sixteen matching prefixes, two distinct histories, no simulations.')
    return value


def verify(path, bundle=None):
    with gzip.open(path, 'rt') as stream:
        value = json.load(stream)
    check_value(value)
    if bundle:
        rows, sources = extract(bundle)
        require(value['rows'] == rows and value['sources'] == sources, 'raw first-day extraction differs')
    print('Verified first-day resource balances, construction, seed gates and shared prefixes without simulation.')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--out', type=Path, default=ROOT / 'artifacts/garden-landing-root-direction-audit-v1.json.gz')
    parser.add_argument('--verify', type=Path)
    args = parser.parse_args()
    if args.verify:
        verify(args.verify.resolve(), args.bundle.resolve() if args.bundle else None)
    else:
        export((args.bundle or ROOT / 'artifacts/garden-landing-root-direction-v1').resolve(), args.out.resolve())


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, TypeError, OSError, StopIteration) as error:
        print('root direction audit failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
