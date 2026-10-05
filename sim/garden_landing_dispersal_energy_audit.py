#!/usr/bin/env python3
"""Audit saved dispersal energy regressions by cohort and equal exposure; offline only."""

from __future__ import annotations

import argparse
from bisect import bisect_left
from collections import defaultdict
from fractions import Fraction
from functools import cache
import gzip
import json
from pathlib import Path
import sys

import garden_landing_late_dispersal as previous
from garden_experiments import digest
from garden_landing_founders import write_gzip
from garden_resources import require

ROOT, STEP, DAY, STOP, AFTER, LATE = (previous.ROOT, previous.STEP, previous.DAY,
                                    previous.STOP, previous.AFTER, previous.LATE)
population = previous.population
RULE = 'garden-landing-dispersal-energy-audit-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-dispersal-energy-audit-protocol.md'
PROTOCOL_SHA = '21a10d1e1d7711fa365a3e6ada8a3f9fea8b234a92da4b987595220263681d23'
INPUT = 'benchmarks/garden-seasons/landing-late-dispersal-results.json.gz'
INPUT_SHA = '390669aba064732072c82e2170ad1d6f7872612710bc1c6501ad3351c8ad3b62'
INPUTS = {INPUT: INPUT_SHA, previous.INPUT: previous.INPUT_SHA}
PERIODS = {'whole': (0, STOP), 'pre': (0, AFTER), 'post': (AFTER, STOP), 'late32': (LATE, STOP)}
RESOURCES = ('energy', 'water')
SIDES = ('control', 'candidate')
COHORTS = ('founder', 'prior_dead', 'incumbent', 'died_by_day1', 'died_day1_to32',
           'confirmed32', 'pending_day1', 'pending_day32')
GROUPS = ('shared_pre', 'incumbent_common', 'incumbent_tail',
          'recruit_common', 'recruit_tail', 'unmatched_recruit')
SOURCES = ('sim/garden_landing_dispersal_energy_audit.py', 'sim/garden_landing_population.py',
           'sim/garden_landing_late_dispersal.py', 'sim/garden_landing_founders.py')


def provenance():
    require(digest(ROOT / PROTOCOL) == PROTOCOL_SHA and
            all(digest(ROOT / path) == sha for path, sha in INPUTS.items()),
            'frozen input/protocol changed')
    return dict(rule=RULE, inputs=INPUTS, protocol_sha256=PROTOCOL_SHA,
                native_runs=0, training_runs=0)


@cache
def inputs():
    provenance()
    with gzip.open(ROOT / INPUT, 'rt') as stream:
        value = json.load(stream)
    previous.check_capture(value['capture'])
    old = previous.inputs()
    require(len(value['pairs']) == len(old['pairs']) == 8, 'incomplete setting panel')
    worlds, pairs = {}, []
    for pair, before in zip(value['pairs'], old['pairs'], strict=True):
        require((pair['case'], pair['allocator']) == (before['case'], before['allocator']),
                'setting identity differs')
        for arm in previous.ARMS:
            a = pair['arms'][arm]
            source = a['new_analysis'] if arm in previous.CANDIDATES else before['arms'][arm]
            name = previous.name(pair, arm)
            run = value['capture']['runs'][name]
            require(a['result'] == source['result'] == run['result'] and a['result']['tick'] == STOP,
                    'population result identity differs')
            population.check_analysis(source['analysis'], a['result'])
            require(a['metrics'] == population.metrics(a['result'], source['analysis']),
                    'original population metrics differ')
            worlds[name] = dict(result=a['result'], analysis=source['analysis'], metrics=a['metrics'],
                                traces=run['traces'], arm=arm)
        for candidate, control in previous.CANDIDATES.items():
            screen = population.comparison(*(pair['arms'][a]['metrics'] for a in (control, candidate)))
            require(screen == pair['comparisons'][candidate], 'original harm screen differs')
            for kind in ('adult', 'stand'):
                prefix = pair['prefix'][candidate][kind]
                require(prefix['samples'] == AFTER // STEP and len(prefix['sha256']) == 2 and
                        prefix['sha256'][0] == prefix['sha256'][1] and
                        (prefix['first_difference'] is None or prefix['first_difference'] > AFTER),
                        'invalid common prefix')
            pairs.append(dict(case=pair['case'], allocator=pair['allocator'], water=control,
                              worlds=dict(zip(SIDES, (previous.name(pair, a) for a in (control, candidate)), strict=True)),
                              original_screen=screen))
    return worlds, pairs


def endpoint(life):
    return life['death_tick'] if life['death_tick'] is not None else STOP


def cohort(life):
    if life['generation'] == 0:
        return 'founder'
    if life['birth_tick'] <= AFTER:
        return 'prior_dead' if endpoint(life) <= AFTER else 'incumbent'
    one, long = (population.survival(life, STOP, days) for days in (1, 32))
    if one == 'died': return 'died_by_day1'
    if one == 'censored': return 'pending_day1'
    return {'died': 'died_day1_to32', 'confirmed': 'confirmed32', 'censored': 'pending_day32'}[long]


def empty():
    return {'payments': 0, **{r: dict(due=0, paid=0, unpaid=0, shortages=0) for r in RESOURCES}}


def combine(items):
    total = empty()
    for item in items:
        total['payments'] += item['payments']
        for r in RESOURCES:
            for k in total[r]: total[r][k] += item[r][k]
    return total


def original_counts(count):
    return {'payments': count['payments'], **{
        r: {k: count[r][k] for k in ('unpaid', 'shortages')} for r in RESOURCES}}


def counts(plant, start=0, end=STOP):
    """Bills in (start,end], with post-step shapes taking effect strictly afterwards."""
    life, shapes = plant['life'], plant['body_changes']
    require(0 <= start <= end <= STOP, 'invalid account window')
    first, last = max(start, life['birth_tick']), min(end, endpoint(life))
    total = empty()
    if last <= first: return total
    total['payments'] = last // 60 - first // 60
    for n, change in enumerate(shapes):
        body = change['body']
        lower = max(first, change['tick'])
        upper = min(last, shapes[n + 1]['tick'] if n + 1 < len(shapes) else last)
        payments = max(0, upper // 60 - lower // 60)
        for r, nodes in (('energy', body['nodes']), ('water', body['nodes'] - body['roots'])):
            total[r]['due'] += payments * ((nodes + 7) // 8)
    for event in plant['shortages']:
        if first < event['tick'] <= last:
            for r in RESOURCES:
                total[r]['unpaid'] += event[r]['unpaid']
                total[r]['shortages'] += event[r]['unpaid'] > 0
    for r in RESOURCES:
        total[r]['paid'] = total[r]['due'] - total[r]['unpaid']
        require(total[r]['paid'] >= 0, 'unpaid exceeds reconstructed demand')
    return total


def check_body(plant):
    life, shapes = plant['life'], plant['body_changes']
    ticks = [s['tick'] for s in shapes]
    require(ticks and ticks == sorted(set(ticks)) and ticks[0] == max(STEP, life['birth_tick']) and
            all(type(t) is int and t % STEP == 0 and t <= endpoint(life) and
                (life['death_tick'] is None or t < life['death_tick']) for t in ticks),
            'incomplete/invalid body history')
    require(all(type(s['body']['nodes']) is int and type(s['body']['roots']) is int and
                0 <= s['body']['roots'] <= s['body']['nodes'] <= 32 for s in shapes), 'invalid body shape')
    for event in plant['shortages']:
        n = bisect_left(ticks, event['tick']) - 1
        require(n >= 0 and [shapes[n]['body'][k] for k in ('nodes', 'roots')] ==
                [event[k] for k in ('nodes', 'roots')], 'pre-maintenance body differs')
    total = counts(plant)
    require(total['payments'] == plant['payments'] and all(
        total[r]['paid'] == plant['resources'][r]['upkeep'] for r in RESOURCES),
        'body demand does not reconcile with paid upkeep and shortages')


def rational(value):
    return [value.numerator, value.denominator]


def rates(count):
    return {r: {base: rational(Fraction(count[r]['unpaid'], denominator)) if denominator else None
                for base, denominator in (('per_payment', count['payments']), ('per_due', count[r]['due']))}
            for r in RESOURCES}


def decompose(groups):
    totals = {a: combine(groups[a].values()) for a in SIDES}
    changes, contributions = {}, {}
    x, y = (totals[a] for a in SIDES)
    for r in RESOURCES:
        if not x['payments'] or not y['payments']:
            changes[r], contributions[r] = None, None
            continue
        delta = Fraction(y[r]['unpaid'], y['payments']) - Fraction(x[r]['unpaid'], x['payments'])
        parts = {g: Fraction(groups['candidate'][g][r]['unpaid'], y['payments']) -
                    Fraction(groups['control'][g][r]['unpaid'], x['payments']) for g in GROUPS}
        require(sum(parts.values()) == delta, 'rate contributions do not sum')
        changes[r], contributions[r] = rational(delta), {k: rational(v) for k, v in parts.items()}
    return dict(totals=totals, rates={a: rates(totals[a]) for a in SIDES},
                change=changes, contributions=contributions)


def events(plant):
    life = plant['life']
    return [dict(event, id=life['id'], cohort=cohort(life), age=event['tick'] - life['birth_tick'],
                 death_step=event['tick'] == life['death_tick'])
            for event in plant['shortages'] if event['tick'] > AFTER and event['energy']['unpaid']]


def event_summary(rows):
    def blank(): return dict(events=0, unpaid=0, water_shortage_events=0, death_events=0)
    total = blank()
    bins = {k: defaultdict(blank) for k in ('cohort', 'phase_quarter', 'age', 'nodes')}
    for e in rows:
        labels = dict(cohort=e['cohort'], phase_quarter=str(e['phase'] // 64), nodes=str(e['nodes']),
                      age='below_day1' if e['age'] < DAY else 'day1_to32' if e['age'] < 32 * DAY else 'at_least_day32')
        for target in (total, *(bins[k][v] for k, v in labels.items())):
            target['events'] += 1
            target['unpaid'] += e['energy']['unpaid']
            target['water_shortage_events'] += e['water']['unpaid'] > 0
            target['death_events'] += e['death_step']
    return dict(total=total, **{k: dict(sorted(v.items())) for k, v in bins.items()})


def analyze_world(world):
    plants = []
    for p in world['analysis']['plants']:
        check_body(p)
        windows = {k: counts(p, *bounds) for k, bounds in PERIODS.items()}
        require(combine(windows[k] for k in ('pre', 'post')) == windows['whole'], 'time partition differs')
        plants.append(dict(life=p['life'], cohort=cohort(p['life']), windows=windows,
                           energy_events=events(p), resources=p['resources']))
    cohorts = {k: {period: combine(p['windows'][period] for p in plants if p['cohort'] == k)
                   for period in PERIODS} for k in COHORTS}
    totals = {kind: {period: combine(p['windows'][period] for p in plants
                                    if (p['cohort'] == 'founder') == (kind == 'founders'))
                     for period in PERIODS} for kind in ('founders', 'offspring')}
    for kind in totals:
        require(original_counts(totals[kind]['whole']) == world['metrics']['resources'][kind],
                'original whole-population account differs')
    return dict(plants=plants, cohorts=cohorts, totals=totals,
                events=event_summary(e for p in plants for e in p['energy_events']))


def analyze_pair(pair, worlds, analyzed):
    source = {a: worlds[pair['worlds'][a]] for a in SIDES}
    plants = {a: {p['life']['id']: p for p in source[a]['analysis']['plants']} for a in SIDES}
    matching = population.matched_births(*(source[a]['result'] for a in SIDES))
    buckets = {a: {g: [] for g in GROUPS} for a in SIDES}
    matched = []
    for ids in matching['matched']:
        ps = [plants[a][i] for a, i in zip(SIDES, ids, strict=True)]
        require(len({p['life']['birth_tick'] for p in ps}) == 1 and
                len({p['life']['generation'] for p in ps}) == 1, 'invalid birth match')
        end = min(endpoint(p['life']) for p in ps)
        born = ps[0]['life']['birth_tick']
        pre = [counts(p, 0, AFTER) for p in ps]
        require(pre[0] == pre[1], 'shared pre-intervention accounts differ')
        if ps[0]['life']['generation'] == 0: continue
        group = 'incumbent' if born <= AFTER else 'recruit'
        common = {a: counts(p, AFTER, max(AFTER, end)) for a, p in zip(SIDES, ps, strict=True)}
        require(len({v['payments'] for v in common.values()}) == 1, 'unequal common exposure')
        for a, p, before in zip(SIDES, ps, pre, strict=True):
            buckets[a]['shared_pre'].append(before)
            buckets[a][group + '_common'].append(common[a])
            buckets[a][group + '_tail'].append(counts(p, max(AFTER, end), STOP))
        matched.append(dict(ids=ids, kind=group, end=end, common=common,
                            rates={a: rates(common[a]) for a in SIDES}))
    for a in SIDES:
        for i in matching[a + '_only']:
            p = plants[a][i]
            require(p['life']['birth_tick'] > AFTER and p['life']['generation'] > 0,
                    'unmatched pre-intervention plant')
            buckets[a]['unmatched_recruit'].append(counts(p))
    groups = {a: {g: combine(items) for g, items in buckets[a].items()} for a in SIDES}
    decomposition = decompose(groups)
    for a in SIDES:
        require(decomposition['totals'][a] == analyzed[pair['worlds'][a]]['totals']['offspring']['whole'],
                'matched partition differs from whole population')
    return pair | dict(matching=matching, matched=matched, groups=groups, decomposition=decomposition)


def analyze(worlds, pairs):
    analyzed = {name: analyze_world(w) for name, w in worlds.items()}
    compared = [analyze_pair(p, worlds, analyzed) for p in pairs]
    pooled = {}
    for water in previous.CANDIDATES.values():
        selected = [p for p in compared if p['water'] == water]
        groups = {a: {g: combine(p['groups'][a][g] for p in selected) for g in GROUPS} for a in SIDES}
        cohorts = {a: {c: {period: combine(analyzed[p['worlds'][a]]['cohorts'][c][period] for p in selected)
                          for period in PERIODS} for c in COHORTS} for a in SIDES}
        pooled[water] = dict(groups=groups, decomposition=decompose(groups), cohorts=cohorts,
                            events={a: event_summary(e for p in selected for plant in
                                analyzed[p['worlds'][a]]['plants'] for e in plant['energy_events']) for a in SIDES})
    return dict(worlds=analyzed, pairs=compared, pooled=pooled)


def check_value(value):
    require(value['provenance'] == provenance() and
            all(type(value['provenance'][k]) is int for k in ('native_runs', 'training_runs')),
            'wrong audit provenance/scope')
    worlds, pairs = inputs()
    require(value['source_sha256'] == {p: digest(ROOT / p) for p in SOURCES},
            'analysis source receipt differs from current verifier')
    require(value['traces'] == {k: w['traces'] for k, w in worlds.items()}, 'wrong original trace coverage')
    require(value['analysis'] == analyze(worlds, pairs), 'audit analysis differs')


def export(out):
    require(not out.exists() and not out.is_symlink(), 'fresh output required')
    worlds, pairs = inputs()
    value = dict(provenance=provenance(), source_sha256={p: digest(ROOT / p) for p in SOURCES},
                 traces={k: w['traces'] for k, w in worlds.items()}, analysis=analyze(worlds, pairs))
    out.parent.mkdir(parents=True, exist_ok=True)
    write_gzip(out, value)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--out', type=Path, default=ROOT / 'artifacts/garden-landing-dispersal-energy-audit-v1.json.gz')
    mode.add_argument('--verify', type=Path)
    args = parser.parse_args(argv)
    if args.verify:
        with gzip.open(args.verify, 'rt') as stream: value = json.load(stream)
        check_value(value)
        print('Verified all sixteen saved energy/cohort/exposure comparisons; no simulations.')
    else:
        export(args.out)
        print('Saved all sixteen energy/cohort/exposure comparisons; no simulations.')


if __name__ == '__main__':
    try: main()
    except (RuntimeError, ValueError, KeyError, TypeError, OSError, IndexError) as error:
        print('dispersal energy audit failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
