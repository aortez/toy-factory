#!/usr/bin/env python3
"""Audit saved seed-production gates and water refills without running worlds."""

from __future__ import annotations

import argparse
from collections import Counter
from functools import cache
import gzip
import json
from pathlib import Path
import sys

import garden_landing_root_allocation_audit as previous
from garden_experiments import digest
from garden_resources import require

ROOT, STEP, STOP = previous.ROOT, previous.STEP, previous.STOP
ARMS, LABELS = previous.ARMS, previous.LABELS
population, adults = previous.population, previous.adults
RULE = 'garden-landing-seed-spending-audit-v1'
INPUT = 'benchmarks/garden-seasons/landing-root-allocation-audit-results.json.gz'
INPUT_SHA = '5dda8d5f5229690437c5250a718e7fb43cf954fd627ce8ea733607cbcad6e16f'
INPUTS = {INPUT: INPUT_SHA, previous.INPUT: previous.INPUT_SHA}
PROTOCOL = 'benchmarks/garden-seasons/landing-seed-spending-audit-protocol.md'
START = 590640
SUBJECTS = {'control': (16, 639480), 'candidate': (17, 644700)}
BLOCKERS = ('cooldown', 'cadence', 'bank', 'dead', 'stress', 'light', 'generation', 'energy', 'water', 'flower')
VISIT_FIELDS = {'id', 'blockers', 'energy', 'water', 'energy_required', 'water_required', 'immature',
                'spent', 'ready', 'flower', 'cooldown', 'bank', 'stress', 'sun', 'produced'}


@cache
def inputs():
    require(all(digest(ROOT / p) == sha for p, sha in INPUTS.items()), 'seed spending input changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream:
        audit = json.load(stream)
    require(audit['rule'] == previous.RULE and audit['input_sha256'] == previous.INPUT_SHA and
            audit['raw_manifest_sha256'] == previous.MANIFEST_SHA, 'wrong allocation audit')
    entries = previous.load_input()
    require([p['case']['id'] for p in audit['analysis']] == [e['case']['id'] for e in entries] ==
            [p['case'] for p in audit['references']], 'wrong common history panel')
    subjects = []
    for entry, analysis, refs in zip(entries, audit['analysis'], audit['references'], strict=True):
        i, end = SUBJECTS[entry['case']['guard']]
        pair = next(p for p in analysis['plants'] if p['ids'] == [i, i])
        require(pair['kind'] == 'matched' and pair['end'] == end and [i, i] in entry['matching']['matched'],
                'wrong selected match')
        resources = {}
        for arm in ARMS:
            plant = previous.index(entry, arm)[i]
            require(plant['life'] == pair['life'][arm] and plant['life']['birth_tick'] == START,
                    'selected identity changed')
            sha = refs['arms'][arm][str(i)]
            rows = audit['receipts'][sha]
            require(previous.fingerprint(rows) == sha and previous.history(rows, plant, end) == pair['common'][arm],
                    'selected resource history changed')
            resources[arm] = rows
        subjects.append({'entry': entry, 'pair': pair, 'id': i, 'end': end, 'resources': resources})
    return subjects


def sources(subjects):
    return [{'case': s['entry']['case']['id'], 'arm': arm, 'label': label,
             **s['entry']['arms'][arm]['runs'][label]['traces']['stand']}
            for s in subjects for arm in ARMS for label in LABELS]


def extract(bundle, subjects):
    require(digest(bundle / 'manifest.json') == previous.MANIFEST_SHA and
            digest(bundle / 'results.json.gz') == previous.INPUT_SHA, 'wrong raw allocation bundle')
    manifest = json.loads((bundle / 'manifest.json').read_text())['artifacts']
    for item in sources(subjects):
        path = (bundle / item['path']).resolve()
        require(path.is_relative_to(bundle.resolve()) and manifest.get(item['path']) == item['sha256'] and
                digest(path) == item['sha256'], 'raw stand source changed')
    cases = []
    for subject in subjects:
        entry, arms = subject['entry'], {}
        for arm in ARMS:
            saved = entry['arms'][arm]
            require(saved['runs']['trace']['traces']['stand']['sha256'] ==
                    saved['runs']['repeat']['traces']['stand']['sha256'], 'stand repeat differs')
            path = bundle / saved['runs']['trace']['traces']['stand']['path']
            rows = []
            for row in population.trace_rows(path, 'stand', saved['result']):
                if START <= row['tick'] <= subject['end']:
                    body = next((b for b in row['bodies'] if b['id'] == subject['id']), None)
                    rows.append({k: row[k] for k in ('tick', 'climate', 'plant_order', 'reproduction')} |
                                {'body': None if body is None else {k: body[k] for k in
                                    ('id', 'species', 'nodes', 'roots', 'flowers')}})
            arms[arm] = rows
            print(entry['case']['id'] + '/' + arm + ': seed visits extracted', flush=True)
        cases.append({'case': entry['case']['id'], 'arms': arms})
    return cases


def blocker_names(mask):
    require(type(mask) is int and 0 <= mask < 1 << len(BLOCKERS), 'invalid blocker mask')
    return [b for n, b in enumerate(BLOCKERS) if mask & (1 << n)]


def check_visits(row, packed, result, identity):
    """Reconcile all visits with the ledger; link target debits to its resource trace."""
    require(set(row) == {'tick', 'climate', 'plant_order', 'reproduction', 'body'}, 'wrong selected stand fields')
    tick, slots = row['tick'], row['plant_order']
    lives = {p['id']: p for p in result['lineages']}
    living = {i for i, p in lives.items() if p['birth_tick'] <= tick and (p['death_tick'] is None or tick < p['death_tick'])}
    first = ((tick - population.order.AT) // 60) % len(slots) if ('seed_order_probe' in result and
             tick > population.order.AT and tick % 60 == 0 and slots) else 0
    require(type(slots) is list and all(type(i) is int for i in slots) and
            len(slots) == len(set(slots)) and len(slots) <= 8 and living <= set(slots) <= set(lives) and
            [v['id'] for v in row['reproduction']] == slots[first:] + slots[:first], 'seed visit order/coverage differs')
    climate = row['climate']
    require(set(climate) == {'version', 'mode', 'year', 'day', 'season', 'light_percent', 'drought', 'cold'} and
            climate['mode'] == 'seasonal' and climate['version'] == 1 and
            all(type(climate[k]) is int for k in ('version', 'year', 'day', 'light_percent')) and
            climate['year'] == tick // (16 * population.DAY) and climate['day'] == tick // population.DAY % 16 and
            climate['season'] == ('spring', 'summer', 'autumn', 'winter')[climate['day'] // 4] and
            type(climate['drought']) is bool and type(climate['cold']) is bool and
            0 <= climate['light_percent'] <= 100,
            'wrong climate clock')
    sun = population.dawn.previous.audit.strength((64 + tick // STEP) % 256, climate['light_percent'])
    bank = sum(s['birth_tick'] < tick < (s['end_tick'] or STOP + STEP) for s in result['seeds'])
    purchases = {s['parent'] for s in result['seeds'] if s['birth_tick'] == tick}
    bought, target = set(), None
    for v in row['reproduction']:
        require(set(v) == VISIT_FIELDS and type(v['produced']) is bool and
                all(type(n) is int and n >= 0 for k, n in v.items() if k != 'produced'), 'invalid production visit')
        i = v['id']
        require(v['energy'] <= 256 and v['water'] <= 512 and v['stress'] <= 8 and v['bank'] == bank <= 8 and
                v['sun'] == sun and (v['flower'] < 256 or v['flower'] == 65535) and
                lives[i]['birth_tick'] <= tick, 'invalid visit ranges/clock')
        blocked = (v['cooldown'] > 0, tick % 60 != 0, bank >= 8, i not in living, v['stress'] > 0, sun <= 24,
                   lives[i]['generation'] == 65535, v['energy'] < v['energy_required'],
                   v['water'] < v['water_required'], v['flower'] == 65535)
        mask = sum(1 << j for j, bit in enumerate(blocked) if bit)
        require(v['blockers'] == mask and v['produced'] == (mask == 0), 'seed blockers/production differ')
        if v['produced']:
            bank += 1
            bought.add(i)
        if i == identity: target = v
    require(bought == purchases and bank == sum(s['birth_tick'] <= tick < (s['end_tick'] or STOP + STEP)
                                               for s in result['seeds']), 'seed ledger/bank differs')
    body, stages = row['body'], packed[0]
    require((body is not None) == (identity in living), 'target body coverage differs')
    if identity in living:
        require(target is not None and set(body) == {'id', 'species', 'nodes', 'roots', 'flowers'} and
                all(type(v) is int and v >= 0 for v in body.values()) and
                body['id'] == identity and body['species'] == lives[identity]['species'] and
                [body['nodes'], body['roots']] == [stages[-1][4], packed[2]] and
                body['flowers'] == sum(target[k] for k in ('immature', 'spent', 'ready')) and
                (target['ready'] == 0) == (target['flower'] == 65535), 'target flower/body inventory differs')
        require(stages[3][:2] == [target['energy'], target['water']] and
                stages[3][2] == target['stress'], 'target pre-seed stores differ')
    produced = bool(target and target['produced'])
    require([stages[3][j] - stages[4][j] for j in (0, 1)] == [48 * produced, 24 * produced],
            'target seed debit differs')
    return target


def first_refill(rows, purchase):
    """Actual refilling, not a hypothetical world with the seed suppressed."""
    before = rows[purchase][0][3][1]
    at_cap = next((n for n in range(purchase + 1, len(rows)) if rows[n][0][0] is not None and
                   rows[n][0][0][1] == 512), None)
    recovered = next((n for n in range(purchase + 1, len(rows)) if rows[n][0][-1][1] >= before), None)
    return {'capacity_tick': None if at_cap is None else START + at_cap * STEP,
            'pre_purchase_store_tick': None if recovered is None else START + recovered * STEP}


def last_shared_cap(rows, before):
    length = len(rows['control'])
    require(length == len(rows['candidate']), 'unequal common histories')
    return next((n for n in reversed(range(length)) if START + n * STEP < before and
                 all(rows[a][n][0][0] is not None and rows[a][n][0][0][1] == 512 for a in ARMS)), None)


def tail_budget(rows, life, anchor):
    """Start immediately after anchor uptake; keep anchor maintenance/spending."""
    require(type(anchor) is int and 0 <= anchor < len(rows) and rows[anchor][1] is not None,
            'invalid post-uptake anchor')
    total = adults.budget()
    for n in range(anchor, len(rows)):
        row = previous.unpack(rows[n], life, START + n * STEP)
        step = adults.transfers(row, life, rows[n - 1][0][-1] if n else None)
        if n == anchor:
            for r in total:
                step[r]['initial'] += step[r]['income'] - step[r]['overflow']
                step[r]['income'] = step[r]['overflow'] = 0
        adults.accumulate(total, step, n == anchor)
    return total


def seed_outcome(seed, result):
    child = next((p for p in result['lineages'] if p['id'] == seed['child_id']), None)
    require((child is not None) == (seed['outcome'] == 'germinated'), 'seed child/outcome differs')
    return {'seed': seed, 'child': child,
            'child_one_day': None if child is None else population.survival(child, STOP, 1)}


def analyze_case(subject, case):
    entry, identity, end = subject['entry'], subject['id'], subject['end']
    require(case['case'] == entry['case']['id'] and set(case['arms']) == set(ARMS), 'wrong seed audit case/arms')
    summaries, visits = {}, {}
    for arm in ARMS:
        result, rows = entry['arms'][arm]['result'], case['arms'][arm]
        resources = subject['resources'][arm]
        require(type(rows) is list and len(rows) == len(resources) == (end - START) // STEP + 1,
                'incomplete seed visit window')
        masks, cadence, bought, climates, visits[arm] = Counter(), Counter(), [], [], []
        for n, (row, packed) in enumerate(zip(rows, resources, strict=True)):
            tick = START + n * STEP
            require(type(row['tick']) is int and row['tick'] == tick, 'missing/reordered seed visit')
            visit = check_visits(row, packed, result, identity)
            visits[arm].append(visit)
            if not climates or climates[-1]['climate'] != row['climate']:
                climates.append({'tick': tick, 'climate': row['climate']})
            if visit:
                masks[str(visit['blockers'])] += 1
                if tick % 60 == 0: cadence[str(visit['blockers'])] += 1
                if visit['produced']:
                    seed = next(s for s in result['seeds'] if s['parent'] == identity and s['birth_tick'] == tick)
                    bought.append({'tick': tick, 'pre_water': packed[0][3][1], 'post_water': packed[0][4][1],
                                   'refill': first_refill(resources, n), **seed_outcome(seed, result)})
        expected_seeds = [s for s in result['seeds'] if s['parent'] == identity and START <= s['birth_tick'] <= end]
        require([p['seed'] for p in bought] == expected_seeds, 'incomplete target purchase history')
        common = subject['pair']['common'][arm]
        require(common['resources']['water']['reproduction'] == 24 * len(bought) and
                common['resources']['energy']['reproduction'] == 48 * len(bought), 'purchase spending total differs')
        shortage = next((s for s in common['shortages'] if s['water']['unpaid']), None)
        last_income = next((START + n * STEP for n in reversed(range(len(resources)))
                            if resources[n][1] and resources[n][1][1][1]), None)
        summaries[arm] = {'masks': dict(masks), 'cadence_masks': dict(cadence), 'purchases': bought,
                          'first_water_shortage': shortage, 'last_water_income': last_income,
                          'climate': climates, 'common': common}
    times = sorted({p['tick'] for s in summaries.values() for p in s['purchases']})
    paired_purchases = [{'tick': tick, 'visits': {a: visits[a][(tick - START) // STEP] for a in ARMS},
                         'blockers': {a: blocker_names(visits[a][(tick - START) // STEP]['blockers'])
                                      if visits[a][(tick - START) // STEP] else ['absent'] for a in ARMS}}
                        for tick in times]
    first_shortage = min((s['first_water_shortage']['tick'] for s in summaries.values()
                          if s['first_water_shortage']), default=None)
    anchor = None if first_shortage is None else last_shared_cap(subject['resources'], first_shortage)
    saturated = None
    if anchor is not None:
        tick = START + anchor * STEP
        arms = {a: {'resources': tail_budget(subject['resources'][a], subject['pair']['life'][a], anchor),
                    'seed_ticks': [p['tick'] for p in summaries[a]['purchases'] if p['tick'] >= tick],
                    'climate': case['arms'][a][anchor]['climate']} for a in ARMS}
        require(all(v['resources']['water']['initial'] == 512 for v in arms.values()), 'anchor is not shared capacity')
        saturated = {'tick': tick, 'stage': 'after_uptake_before_maintenance', 'arms': arms,
                     'delta': {r: {k: arms['candidate']['resources'][r][k] - arms['control']['resources'][r][k]
                                   for k in adults.FIELDS} for r in previous.RESOURCES}}
    return {'case': entry['case'], 'id': identity, 'window': [START, end],
            'arms': summaries, 'paired_purchases': paired_purchases, 'last_shared_capacity': saturated}


def analyze(cases):
    subjects = inputs()
    require(type(cases) is list and len(cases) == len(subjects), 'wrong seed audit panel coverage')
    return [analyze_case(subject, case) for subject, case in zip(subjects, cases, strict=True)]


def check_value(value):
    require(value['rule'] == RULE and value['inputs'] == INPUTS and
            value['raw_manifest_sha256'] == previous.MANIFEST_SHA and
            value['protocol_sha256'] == digest(ROOT / PROTOCOL) and
            type(value['new_simulations']) is int and value['new_simulations'] == 0 and
            type(value['training_runs']) is int and value['training_runs'] == 0, 'wrong seed audit provenance/scope')
    require(value['sources'] == sources(inputs()), 'wrong seed audit sources')
    require(value['receipts_sha256'] == previous.fingerprint(value['cases']), 'seed receipt checksum differs')
    require(value['analysis'] == analyze(value['cases']), 'seed audit summary differs')


def export(bundle, out):
    require(not out.exists(), 'fresh output required')
    subjects = inputs()
    cases = extract(bundle, subjects)
    value = {'rule': RULE, 'inputs': INPUTS, 'raw_manifest_sha256': previous.MANIFEST_SHA,
             'protocol_sha256': digest(ROOT / PROTOCOL), 'new_simulations': 0, 'training_runs': 0,
             'sources': sources(subjects), 'cases': cases, 'receipts_sha256': previous.fingerprint(cases),
             'analysis': analyze(cases)}
    out.parent.mkdir(parents=True, exist_ok=True)
    population.order.recovery.founders.write_gzip(out, value)
    print('Saved complete selected seed gates, refills and post-saturation budgets without simulation.')
    return value


def verify(path, bundle=None):
    with gzip.open(path, 'rt') as stream:
        value = json.load(stream)
    check_value(value)
    if bundle:
        require(value['cases'] == extract(bundle, inputs()), 'raw seed extraction differs')
    print('Verified seed gates, bank order, purchases, actual refills and post-saturation accounting offline.')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--out', type=Path, default=ROOT / 'artifacts/garden-landing-seed-spending-audit-v1.json.gz')
    parser.add_argument('--verify', type=Path)
    args = parser.parse_args()
    if args.verify:
        verify(args.verify.resolve(), args.bundle.resolve() if args.bundle else None)
    else:
        export((args.bundle or ROOT / 'artifacts/garden-landing-root-allocation-v1').resolve(), args.out.resolve())


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, TypeError, OSError, StopIteration) as error:
        print('seed spending audit failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
