#!/usr/bin/env python3
"""Decompose saved allocation regressions; no simulator or other process calls."""

from __future__ import annotations

import argparse
from fractions import Fraction
from functools import cache
import gzip
import hashlib
import json
from pathlib import Path
import sys

import garden_landing_root_allocation as previous
from garden_experiments import digest
from garden_resources import require

ROOT, STEP, STOP = previous.ROOT, previous.STEP, previous.STOP
ARMS, LABELS = previous.ARMS, previous.LABELS
population, adults = previous.population, previous.population.adults
RESOURCES = ('energy', 'water')
RULE = 'garden-landing-root-allocation-audit-v1'
INPUT = 'benchmarks/garden-seasons/landing-root-allocation-results.json.gz'
INPUT_SHA = '8877c4e6f7f951ec06c546c5fc6f3e0ea0175a250b70e21596e734cd8fa63d76'
MANIFEST_SHA = 'b2aab73b6ed9fadf1e28d1dd32e28911202661ca0ff593cc3c1a3641f4195972'
PROTOCOL = 'benchmarks/garden-seasons/landing-root-allocation-audit-protocol.md'
CASE_IDS = tuple('f7ee4528-' + order + '-' + guard
                 for order in ('fixed', 'rotating') for guard in ARMS)
GROUPS = ('focal_common', 'focal_tail', 'matched_common', 'matched_tail', 'unmatched')
PACKED_FIELDS = ('stages', 'uptake', 'roots', 'active_leaves')


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


@cache
def load_input():
    require(digest(ROOT / INPUT) == INPUT_SHA, 'allocation input changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream:
        value = json.load(stream)
    require(value['rule'] == previous.RULE and value['full_replays'] == 16 and
            value['training_runs'] == 0 and
            tuple(e['case']['id'] for e in value['cases']) == CASE_IDS, 'wrong allocation panel')
    # The pinned file already passed complete allocation verification. Retain
    # only the ledgers and population summaries needed here, not its large bid
    # histories. Recheck the accounting and identities we consume independently.
    entries = []
    for e in value['cases']:
        arms = {}
        for arm in ARMS:
            a = e['arms'][arm]
            require(a['result']['tick'] == STOP and set(a['runs']) == set(LABELS), 'wrong horizon/repeats')
            previous.focal_life(a['result'])
            population.check_analysis(a['analysis'], a['result'])
            require(a['metrics'] == population.metrics(a['result'], a['analysis']), 'input metrics differ')
            x, y = (a['runs'][label] for label in LABELS)
            require(x['result'] == y['result'] == a['result'] and
                    x['traces']['adult']['sha256'] == y['traces']['adult']['sha256'], 'input repeats differ')
            arms[arm] = {k: a[k] for k in ('result', 'analysis', 'metrics', 'runs')}
        matching = population.matched_births(*(arms[a]['result'] for a in ARMS))
        require(matching == e['birth_matching'] and e['comparison'] ==
                population.comparison(*(arms[a]['metrics'] for a in ARMS)), 'input matching/screen differs')
        entries.append({'case': e['case'], 'arms': arms, 'matching': matching,
                        'first_effect': e['first_effect']['tick'], 'screen': e['comparison']})
    return entries


def index(entry, arm):
    return {p['life']['id']: p for p in entry['arms'][arm]['analysis']['plants']}


def common_end(lives, stop=STOP):
    require(len({p['birth_tick'] for p in lives}) == 1, 'unmatched birth times')
    end = min(p['death_tick'] if p['death_tick'] is not None else stop for p in lives)
    require(lives[0]['birth_tick'] <= end <= stop, 'invalid common endpoint')
    return end


def counts(plant, end=None):
    life = plant['life']
    limit = life['death_tick'] if life['death_tick'] is not None else STOP
    end = limit if end is None else end
    require(life['birth_tick'] <= end <= limit, 'count endpoint outside lifetime')
    return {'payments': end // (4 * STEP) - life['birth_tick'] // (4 * STEP), **{
        r: {'unpaid': sum(s[r]['unpaid'] for s in plant['shortages'] if s['tick'] <= end),
            'shortages': sum(s[r]['unpaid'] > 0 for s in plant['shortages'] if s['tick'] <= end)}
        for r in RESOURCES}}


def combine(items):
    return {'payments': sum(p['payments'] for p in items), **{
        r: {k: sum(p[r][k] for p in items) for k in ('unpaid', 'shortages')} for r in RESOURCES}}


def subtract(a, b):
    value = {'payments': a['payments'] - b['payments'], **{
        r: {k: a[r][k] - b[r][k] for k in ('unpaid', 'shortages')} for r in RESOURCES}}
    require(value['payments'] >= 0 and all(n >= 0 for r in RESOURCES for n in value[r].values()),
            'negative exposure tail')
    return value


def rational(value):
    return [value.numerator, value.denominator]


def rates(count):
    return {r: rational(Fraction(count[r]['unpaid'], count['payments']))
            if count['payments'] else None for r in RESOURCES}


def decompose(groups):
    """Exact additive rate contributions, not an assignment of causal effects."""
    totals = {a: combine(list(groups[a].values())) for a in ARMS}
    a, b = (totals[arm] for arm in ARMS)
    contributions, change = {}, {}
    for r in RESOURCES:
        if not a['payments'] or not b['payments']:
            contributions[r], change[r] = None, None
            continue
        delta = Fraction(b[r]['unpaid'], b['payments']) - Fraction(a[r]['unpaid'], a['payments'])
        parts = {g: Fraction(groups['candidate'][g][r]['unpaid'], b['payments']) -
                    Fraction(groups['control'][g][r]['unpaid'], a['payments']) for g in GROUPS}
        require(sum(parts.values()) == delta, 'rate contributions do not reconcile')
        contributions[r], change[r] = {g: rational(v) for g, v in parts.items()}, rational(delta)
    return {'totals': totals, 'rates': {a: rates(totals[a]) for a in ARMS},
            'change': change, 'contributions': contributions}


def cohorts(entry):
    plants = {a: index(entry, a) for a in ARMS}
    buckets = {a: {g: [] for g in GROUPS} for a in ARMS}
    pairs, founders = [], {a: [] for a in ARMS}
    for ids in entry['matching']['matched']:
        ps = [plants[a][i] for a, i in zip(ARMS, ids, strict=True)]
        end = common_end([p['life'] for p in ps])
        founder = ps[0]['life']['generation'] == 0
        focal = ids == [previous.FOCAL['lineage']] * 2
        require(all((p['life']['generation'] == 0) == founder for p in ps), 'mixed generation match')
        for arm, p in zip(ARMS, ps, strict=True):
            full, shared = counts(p), counts(p, end)
            if founder:
                founders[arm].append(full)
            else:
                group = 'focal' if focal else 'matched'
                buckets[arm][group + '_common'].append(shared)
                buckets[arm][group + '_tail'].append(subtract(full, shared))
        pairs.append({'ids': ids, 'kind': 'founder' if founder else 'focal' if focal else 'matched',
                      'end': end})
    for arm in ARMS:
        for i in entry['matching'][arm + '_only']:
            require(plants[arm][i]['life']['generation'] > 0, 'unmatched founder')
            buckets[arm]['unmatched'].append(counts(plants[arm][i]))
    groups = {a: {g: combine(xs) for g, xs in buckets[a].items()} for a in ARMS}
    decomposed = decompose(groups)
    for arm in ARMS:
        require(decomposed['totals'][arm] == entry['arms'][arm]['metrics']['resources']['offspring'] and
                combine(founders[arm]) == entry['arms'][arm]['metrics']['resources']['founders'],
                'cohort decomposition differs from population totals')
    return {'pairs': pairs, 'matching': entry['matching'], 'groups': groups,
            'founders': {a: combine(founders[a]) for a in ARMS}, 'decomposition': decomposed}


def pack(plant):
    require(set(plant) == {'id', 'birth', *PACKED_FIELDS}, 'wrong adult plant fields')
    return [plant[k] for k in PACKED_FIELDS]


def unpack(values, life, tick):
    require(type(values) is list and len(values) == len(PACKED_FIELDS), 'wrong packed receipt')
    return dict(zip(PACKED_FIELDS, values, strict=True)) | {'tick': tick, 'id': life['id'], 'birth': life['birth_tick']}


def history(rows, plant, end):
    life, total, before, roots = plant['life'], adults.budget(), None, 2
    start = max(STEP, life['birth_tick'])
    require(type(rows) is list and len(rows) == (end - start) // STEP + 1, 'incomplete common history')
    payments, shortages = 0, []
    for n, values in enumerate(rows):
        tick = start + n * STEP
        row = unpack(values, life, tick)
        receipt = adults.transfers(row, life, before)
        adults.accumulate(total, receipt, n == 0)
        pay = population.payment(row, receipt, roots, tick, (64 + tick // STEP) % 256)
        if pay:
            payments += 1
            if any(pay[r]['unpaid'] for r in RESOURCES): shortages.append(pay)
        before, roots = row['stages'][-1], row['roots']
    observed = {'payments': payments, **{r: {'unpaid': sum(s[r]['unpaid'] for s in shortages),
                 'shortages': sum(s[r]['unpaid'] > 0 for s in shortages)} for r in RESOURCES}}
    value = {'resources': total, 'samples': len(rows), 'counts': observed,
             'rates': rates(observed), 'shortages': shortages,
             'alive_at_end': life['death_tick'] is None or life['death_tick'] > end}
    check_history(value, plant, end)
    return value


def check_history(value, plant, end):
    require(value['counts'] == counts(plant, end) and
            value['shortages'] == [s for s in plant['shortages'] if s['tick'] <= end],
            'common payments/shortages differ')
    require(all(value['resources'][r]['initial'] == plant['resources'][r]['initial'] for r in RESOURCES),
            'common endowment differs')
    if end == (plant['life']['death_tick'] or STOP):
        require(value['resources'] == plant['resources'], 'common lifetime budget differs')


def features(values, previous_roots, tick):
    stages, uptake, roots, leaves = values
    result = {'body': [stages[-1][4], roots, leaves], 'stress': stages[-1][2]}
    for j, r in enumerate(RESOURCES):
        income, overflow = (uptake[j][1:3] if uptake else (0, 0))
        upkeep = (uptake[j][4] if stages[-1][3] & 1 else stages[0][j] - stages[1][j]) if uptake else 0
        due = ((stages[0][4] - (previous_roots if r == 'water' else 0) + 7) // 8
               if uptake and tick % (4 * STEP) == 0 else 0)
        result.update({r + '_income': income, r + '_overflow': overflow,
                       r + '_retained': income - overflow, r + '_store': stages[-1][j],
                       r + '_growth': stages[2][j] - stages[3][j],
                       r + '_reproduction': stages[3][j] - stages[4][j],
                       r + '_upkeep': upkeep, r + '_unpaid': due - upkeep})
    return result


def differences(rows, birth):
    first, roots = {}, [2, 2]
    for n, values in enumerate(zip(*(rows[a] for a in ARMS), strict=True)):
        tick = max(STEP, birth) + n * STEP
        a, b = [features(v, r, tick) for v, r in zip(values, roots, strict=True)]
        for k in a:
            if k not in first and a[k] != b[k]:
                first[k] = {'tick': tick, 'control': a[k], 'candidate': b[k]}
        roots = [v[2] for v in values]
    return first


def analyze(entries, references, receipts):
    result, cache_history, used = [], {}, set()
    require(len(references) == len(entries), 'wrong receipt case coverage')
    for entry, refs in zip(entries, references, strict=True):
        cohort = cohorts(entry)
        require(refs['case'] == entry['case']['id'] and set(refs['arms']) == set(ARMS), 'wrong receipt case/arms')
        plants = {a: index(entry, a) for a in ARMS}
        for n, arm in enumerate(ARMS):
            require(set(refs['arms'][arm]) == {str(p['ids'][n]) for p in cohort['pairs']}, 'wrong matched receipt coverage')
        pairs = []
        for pair in cohort['pairs']:
            common, rows = {}, {}
            for arm, i in zip(ARMS, pair['ids'], strict=True):
                p = plants[arm][i]
                sha = refs['arms'][arm][str(i)]
                require(sha in receipts, 'missing common receipts')
                used.add(sha)
                rows[arm] = receipts[sha]
                key = (sha, json.dumps(p['life'], sort_keys=True), pair['end'])
                if key not in cache_history:
                    cache_history[key] = history(rows[arm], p, pair['end'])
                common[arm] = cache_history[key]
                # Renumbered matches can share byte-identical receipts. Always
                # cross-check the receiving plant's saved shortage/account data.
                check_history(common[arm], p, pair['end'])
            birth = plants['control'][pair['ids'][0]]['life']['birth_tick']
            delta = {r: {k: common['candidate']['resources'][r][k] - common['control']['resources'][r][k]
                         for k in adults.FIELDS} for r in RESOURCES}
            pairs.append(pair | {'life': {a: plants[a][i]['life'] for a, i in zip(ARMS, pair['ids'], strict=True)},
                                 'common': common, 'resource_delta': delta,
                                 'first': differences(rows, birth)})
        result.append({'case': entry['case'], 'cohorts': cohort, 'plants': pairs,
                       'population_screen': entry['screen']})
    require(used == set(receipts), 'unreferenced receipts')
    return result


def expected_sources(entries):
    return [{'case': e['case']['id'], 'arm': arm, 'label': label,
             **e['arms'][arm]['runs'][label]['traces']['adult']}
            for e in entries for arm in ARMS for label in LABELS]


def extract(bundle, entries):
    require(digest(bundle / 'manifest.json') == MANIFEST_SHA and
            digest(bundle / 'results.json.gz') == INPUT_SHA, 'wrong raw allocation bundle')
    manifest = json.loads((bundle / 'manifest.json').read_text())['artifacts']
    sources = expected_sources(entries)
    for item in sources:
        path = (bundle / item['path']).resolve()
        require(path.is_relative_to(bundle.resolve()) and manifest.get(item['path']) == item['sha256'] and
                digest(path) == item['sha256'], 'raw adult source changed')
    references, receipts = [], {}
    for entry in entries:
        cohort, arms = cohorts(entry), {}
        for n, arm in enumerate(ARMS):
            saved = entry['arms'][arm]
            ends = {p['ids'][n]: p['end'] for p in cohort['pairs']}
            lives = {p['id']: p for p in saved['result']['lineages']}
            packed = {i: [] for i in ends}
            path = bundle / saved['runs']['trace']['traces']['adult']['path']
            for row in population.trace_rows(path, 'adult', saved['result']):
                tick = row['tick']
                require(len({p['id'] for p in row['plants']}) == len(row['plants']), 'duplicate plant receipt')
                require({p['id'] for p in row['plants']} == {i for i, p in lives.items()
                        if max(STEP, p['birth_tick']) <= tick <= (p['death_tick'] or STOP)},
                        'raw population coverage differs')
                for p in row['plants']:
                    i = p['id']
                    require(p['birth'] == lives[i]['birth_tick'], 'raw plant identity differs')
                    if i in ends and tick <= ends[i]: packed[i].append(pack(p))
            arms[arm] = {}
            for i, rows in packed.items():
                sha = fingerprint(rows)
                if sha in receipts: require(receipts[sha] == rows, 'receipt hash collision')
                else: receipts[sha] = rows
                arms[arm][str(i)] = sha
            print(entry['case']['id'] + '/' + arm + ': common histories extracted', flush=True)
        references.append({'case': entry['case']['id'], 'arms': arms})
    return references, receipts


def check_value(value):
    require(value['rule'] == RULE and value['input_sha256'] == INPUT_SHA and
            value['raw_manifest_sha256'] == MANIFEST_SHA and value['protocol_sha256'] == digest(ROOT / PROTOCOL) and
            type(value['new_simulations']) is int and value['new_simulations'] == 0 and
            type(value['training_runs']) is int and value['training_runs'] == 0 and
            value['packed_fields'] == list(PACKED_FIELDS), 'wrong audit provenance/scope')
    entries = load_input()
    require(value['sources'] == expected_sources(entries), 'wrong adult source coverage')
    require(all(fingerprint(rows) == sha for sha, rows in value['receipts'].items()), 'common receipt checksum differs')
    require(value['analysis'] == analyze(entries, value['references'], value['receipts']), 'audit summary differs')


def export(bundle, out):
    require(not out.exists(), 'fresh output required')
    entries = load_input()
    references, receipts = extract(bundle, entries)
    value = {'rule': RULE, 'input_sha256': INPUT_SHA, 'raw_manifest_sha256': MANIFEST_SHA,
             'protocol_sha256': digest(ROOT / PROTOCOL), 'new_simulations': 0, 'training_runs': 0,
             'packed_fields': list(PACKED_FIELDS), 'sources': expected_sources(entries),
             'references': references, 'receipts': receipts,
             'analysis': analyze(entries, references, receipts)}
    out.parent.mkdir(parents=True, exist_ok=True)
    population.order.recovery.founders.write_gzip(out, value)
    print('Saved four complete population decompositions and matched common histories; no simulations.')
    return value


def verify(path, bundle=None):
    with gzip.open(path, 'rt') as stream:
        value = json.load(stream)
    check_value(value)
    if bundle:
        references, receipts = extract(bundle, load_input())
        require(value['references'] == references and value['receipts'] == receipts, 'raw extraction differs')
    print('Verified cohort totals, equal exposure, resource balances and exact rate contributions offline.')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--out', type=Path, default=ROOT / 'artifacts/garden-landing-root-allocation-audit-v1.json.gz')
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
        print('root allocation audit failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
