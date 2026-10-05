#!/usr/bin/env python3
"""Offline purchase-time crowding and bounded dispersal reach; no simulation."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
from concurrent.futures import ProcessPoolExecutor
from functools import cache
import gzip
import json
import lzma
from multiprocessing import get_context
from pathlib import Path
import sys

import garden_landing_renewal_gates as previous
from garden_landing_reach import support
from garden_experiments import digest
from garden_landing_founders import write_gzip
from garden_resources import require

ROOT, STEP, START, LATE, STOP = previous.ROOT, previous.STEP, previous.START, previous.LATE, previous.STOP
RULE = 'garden-landing-dispersal-timing-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-dispersal-timing-protocol.md'
PROTOCOL_SHA = 'b2a4fc11a673028fae591949cd9af67956cdfef040c7ea95cfed937f74537738'
INPUT = 'benchmarks/garden-seasons/landing-renewal-gates-results.json.gz'
INPUT_SHA = '20d269d868b2cc1135e93d4b0f4ebe37ef667e3316d92e280d1d7488b38bd255'
WINDOWS = 'benchmarks/garden-seasons/landing-renewal-gates-windows.jsonl.xz'
WINDOWS_SHA = 'd7ff641241c1cc0f242e68628648a04ce82e1ffe5046f0a4221a2485b7c61026'
IMPLEMENTATION = {
    'src/garden_world.c': 'b36599e86559972c7352b3e7fc801889ed4254e5b9c0abb2ebd5dba65436b70b',
    'src/garden_world.h': 'ab0ce75d4fe2e0e919ccea3124e84df475b99ed6e7cd2e308c3410869e780a23',
    'src/garden_dispersal.h': 'a9de8f4b97f3264c70ecf3ae45482d714ab81593bb207123ac797a6cf33f0286',
    'sim/garden_landing_placement.c': '03846dddeac3dae03324f60dcbfb100d7d0a29dd10bd3912e96a6c4f77ea35df',
    'sim/garden_landing_run.c': '0539c08fb3d30b2ef98c06acfe0874a030abc1d298bd5e2f6ccf3355e336c736',
    'sim/garden_landing_plant_trace.c': 'aaf0c371d99a5c3be2216468020a4a5eb103e28338a9f5c2bd7e5f41ad27cdbe',
}
PERIODS = {'post': START, 'late32': LATE}
TRAITS = tuple(range(-2, 3))
REACH_CLASSES = ('no_global_open', 'definitely_unreachable', 'definitely_reachable', 'unresolved')


def provenance():
    inputs = {INPUT: INPUT_SHA, WINDOWS: WINDOWS_SHA, previous.INPUT: previous.INPUT_SHA}
    require(digest(ROOT / PROTOCOL) == PROTOCOL_SHA and
            all(digest(ROOT / p) == sha for p, sha in inputs.items()), 'frozen input/protocol changed')
    return dict(rule=RULE, inputs=inputs, protocol_sha256=PROTOCOL_SHA,
                implementation=IMPLEMENTATION, native_runs=0, training_runs=0)


@cache
def inputs():
    provenance()
    capture, panel = previous.source()
    require(all(capture['source_sha256'].get(p) == sha for p, sha in IMPLEMENTATION.items()),
            'unreviewed implementation')
    for arm, build in capture['builds'].items():
        previous.previous.check_settings(build['settings'], arm)
    for item in panel:
        run = capture['runs'][item['id']]
        require(run['result']['placement_probe'] == dict(enabled=True, version=1) and
                run['args'][run['args'].index('--seed-placement') + 1] == 'spacing' and
                run['result']['gardener'] is False, 'unsupported placement/gardener')
    with gzip.open(ROOT / INPUT, 'rt') as stream:
        prior = json.load(stream)
    require([w['id'] for w in prior['worlds']] == [p['id'] for p in panel] and
            prior['windows_sha256'] == WINDOWS_SHA, 'wrong prior panel')
    return capture, panel, {w['id']: w for w in prior['worlds']}


def free_columns(slots, lives):
    require(len(slots) == len(set(slots)) <= 8 and all(i in lives for i in slots), 'invalid slot census')
    return [c for c in range(28) if all(abs(c - lives[i]['column']) >= 3 for i in slots)]


def witnesses(column, slots, lives):
    return sorted(i for i in slots if abs(column - lives[i]['column']) < 3)


def landing_traits(result):
    """Retrospective candidates, not an observed genotype or an online input."""
    lives = {p['id']: p for p in result['lineages']}
    by_parent = defaultdict(set)
    for s in result['seeds']:
        by_parent[s['parent']].add(s['column'])
    candidates = {i: [t for t in TRAITS if columns <= set(support(lives[i]['column'], t))]
                  for i, columns in by_parent.items()}
    require(all(candidates.values()), 'recorded landings contradict every legal trait')
    return candidates


def constrained_traits(result, records):
    lives = {p['id']: p for p in result['lineages']}
    landing = landing_traits(result)
    policy = {i: list(ts) for i, ts in landing.items()}
    for r in records:
        if r['purchase'] is None:
            continue
        s = next(s for s in result['seeds'] if [s['parent'], s['birth_tick']] == r['seed'])
        i = s['parent']
        clear = set(free_columns(r['purchase']['slots'], lives))
        if s['column'] not in clear:
            policy[i] = [t for t in policy[i] if not clear.intersection(support(lives[i]['column'], t))]
    require(all(policy.values()), 'landings contradict the enabled spacing-placement rule')
    return {'landing_only': landing, 'with_policy': policy}


def intersection_bounds(clear, supports, column, mask, opened):
    """Bound unknown open-site coordinates using the observed actual-site result."""
    clear = set(clear)
    supports = [set(s) for s in supports]
    require(supports and all(column in s for s in supports) and type(opened) is int and
            0 <= opened <= len(clear) and type(mask) is int and 0 <= mask < 128 and
            bool(mask & 32) == (column not in clear), 'invalid reach cardinalities/spacing')
    known = {column} if mask == 0 else set()
    possible = clear - {column}
    remaining = opened - len(known)
    require(0 <= remaining <= len(possible) and known <= clear, 'actual site contradicts open count')
    lo = min(len(known & s) + max(0, remaining - len(possible - s)) for s in supports)
    hi = max(len(known & s) + min(remaining, len(possible & s)) for s in supports)
    category = ('no_global_open' if opened == 0 else 'definitely_unreachable' if hi == 0 else
                'definitely_reachable' if lo > 0 else 'unresolved')
    return dict(minimum=lo, maximum=hi, category=category)


def add_run(runs, tick, blocked):
    if runs and runs[-1][1] == tick - STEP and runs[-1][2] == blocked:
        runs[-1][1] = tick
    else:
        runs.append([tick, tick, blocked])


def extract(result, rows, periods=PERIODS):
    start, stop = min(periods.values()), result['tick']
    require(len(rows) == (stop - start) // STEP, 'wrong excerpt length')
    lives = {p['id']: p for p in result['lineages']}
    ledger = {(s['parent'], s['birth_tick']): s for s in result['seeds']}
    require(len(ledger) == len(result['seeds']) and len(lives) == len(result['lineages']), 'duplicate ledger')
    selected = {k: s for k, s in ledger.items() if s['birth_tick'] <= stop and
                (s['end_tick'] is None or s['end_tick'] > start)}
    records = {k: dict(seed=list(k), purchase=None, spacing_runs=[], first_mature=None,
                      samples=0, expiry_samples=0, contexts={label: Counter() for label in periods}) for k in selected}
    for tick, row in zip(range(start + STEP, stop + STEP, STEP), rows, strict=True):
        require(len(row) == len(previous.ROW_FIELDS) and type(row[0]) is int and row[0] == tick,
                'wrong row clock/layout')
        slots, attempts, visits = row[4], row[5], row[6]
        free_columns(slots, lives)  # Validate the whole stored population, not only live bodies.
        living = {i for i, p in lives.items() if p['birth_tick'] <= tick and
                  (p['death_tick'] is None or p['death_tick'] > tick)}
        require(living <= set(slots) and all(lives[i]['birth_tick'] <= tick for i in slots), 'invalid population census')
        before = [i for i in slots if lives[i]['birth_tick'] < tick]
        seen = set()
        for a in attempts:
            require(len(a) == 11 and all(type(v) is int for v in a), 'invalid seed receipt')
            parent, age, col, mask, moisture, light, plants, nodes, outcome, child, opened = a
            key = parent, tick - age * STEP
            require(key in selected and key not in seen, 'unknown/duplicate seed check')
            seen.add(key)
            s, r = selected[key], records[key]
            expected = 0 if s['end_tick'] != tick else {'expired': 1, 'germinated': 2}[s['outcome']]
            require(s['column'] == col and age > 0 and len(before) == plants and outcome == expected and
                    child == (s['child_id'] if outcome == 2 else 0), 'seed identity/fate/slots differ')
            r['samples'] += 1
            if outcome == 1:
                require(age == s['lifetime_ecology_ticks'] and mask == moisture == light == 0 and opened == -1,
                        'expiry is not a germination check')
                r['expiry_samples'] += 1
                continue
            blocked = witnesses(col, before, lives)
            require(age < s['lifetime_ecology_ticks'] and bool(mask & 32) == bool(blocked) and
                    bool(mask & 1) == (age < 8) and (mask == 0) == (outcome == 2), 'seed spacing/maturity differs')
            add_run(r['spacing_runs'], tick, blocked)
            if age >= 8:
                if r['first_mature'] is None:
                    r['first_mature'] = [tick, blocked]
                for label, left in periods.items():
                    if tick > left:
                        r['contexts'][label][(tuple(sorted(before)), mask, opened)] += 1
            if outcome == 2:
                require(child in lives and lives[child]['birth_tick'] == tick and child not in before,
                        'wrong newborn identity')
                before.append(child)
        require(before == slots and seen == {k for k, s in selected.items() if s['birth_tick'] < tick <=
                    (s['end_tick'] or stop)}, 'incomplete seed/newborn inventory')
        purchased = [v[0] for v in visits if v[-1]]
        require(len(purchased) == len(set(purchased)) and set(purchased) ==
                {s['parent'] for s in selected.values() if s['birth_tick'] == tick}, 'purchase census differs')
        for parent in purchased:
            require(parent in living, 'dead/unborn purchaser')
            records[parent, tick]['purchase'] = dict(slots=list(slots),
                blockers=witnesses(selected[parent, tick]['column'], slots, lives))
    for key, r in records.items():
        s = selected[key]
        require(r['samples'] == (min(s['end_tick'] or stop, stop) - max(s['birth_tick'], start)) // STEP and
                (r['purchase'] is not None) == (s['birth_tick'] > start), 'incomplete seed history')
        r['contexts'] = {label: [[list(slots), mask, opened, n] for (slots, mask, opened), n in sorted(hist.items())]
                         for label, hist in r['contexts'].items()}
    return list(records.values())


def timing(s, r, lives, start, stop):
    first = max(s['birth_tick'], start) + STEP
    last = min(s['end_tick'] or stop, stop) - STEP * (s['outcome'] == 'expired' and s['end_tick'] <= stop)
    cursor = first
    for a, b, blocked in r['spacing_runs']:
        require(type(a) is int and type(b) is int and a == cursor and b >= a and b <= last and
                (b - a) % STEP == 0 and blocked == sorted(set(blocked)) and
                all(i in lives and lives[i]['birth_tick'] <= a and abs(lives[i]['column'] - s['column']) < 3
                    for i in blocked), 'invalid spacing-witness run')
        cursor = b + STEP
    require(cursor == last + STEP and r['samples'] == max(0, (min(s['end_tick'] or stop, stop) -
                max(s['birth_tick'], start)) // STEP) and
            r['expiry_samples'] == int(s['outcome'] == 'expired' and start < s['end_tick'] <= stop),
            'incomplete spacing-witness coverage')
    mature = max(first, s['birth_tick'] + 8 * STEP)
    expected_mature = next(([mature, ids] for a, b, ids in r['spacing_runs'] if a <= mature <= b), None)
    require(r['first_mature'] == expected_mature, 'first mature check differs')
    first_blocked = next((a for a, _, ids in r['spacing_runs'] if ids), None)
    first_clear = next((a for a, _, ids in r['spacing_runs'] if not ids), None)
    purchase = r['purchase']
    require((purchase is not None) == (s['birth_tick'] > start), 'wrong purchase-window boundary')
    if purchase is None:
        category = 'purchase_precedes_excerpt'
    else:
        require(purchase['blockers'] == witnesses(s['column'], purchase['slots'], lives), 'purchase witnesses differ')
        category = ('blocked_at_purchase' if purchase['blockers'] else
                    'clear_then_blocked' if first_blocked is not None else
                    'clear_through_observation' if r['spacing_runs'] else 'no_followup')
    newcomers = []
    if category == 'clear_then_blocked':
        ids = next(ids for a, _, ids in r['spacing_runs'] if a == first_blocked)
        require(all(i not in purchase['slots'] and s['birth_tick'] < lives[i]['birth_tick'] <= first_blocked
                    for i in ids), 'initially-clear site blocked without a newcomer')
        newcomers = [dict(id=i, birth_tick=lives[i]['birth_tick'], sibling=lives[i]['parent'] == s['parent']) for i in ids]
    return dict(category=category, first_blocked=first_blocked, first_clear=first_clear, newcomers=newcomers)


def analyze(result, records, prior, periods=PERIODS):
    start, stop = min(periods.values()), result['tick']
    lives = {p['id']: p for p in result['lineages']}
    ledger = {(s['parent'], s['birth_tick']): s for s in result['seeds']}
    selected = {k: s for k, s in ledger.items() if s['birth_tick'] <= stop and
                (s['end_tick'] is None or s['end_tick'] > start)}
    require([r['seed'] for r in records] == [list(k) for k in selected], 'missing/reordered/duplicate seed evidence')
    traits = constrained_traits(result, records)
    old_seeds = {label: {(s['parent'], s['birth_tick']): s for s in prior['windows'][label]['seed_window']['seeds']}
                 for label in periods}
    reports = []
    for r in records:
        s = selected[tuple(r['seed'])]
        require(set(r) == {'seed', 'purchase', 'spacing_runs', 'first_mature', 'samples', 'expiry_samples', 'contexts'}
                and set(r['contexts']) == set(periods), 'wrong seed evidence fields')
        t = timing(s, r, lives, start, stop)
        supports = {label: [support(lives[s['parent']]['column'], v) for v in by_parent[s['parent']]]
                    for label, by_parent in traits.items()}
        purchase = None
        if r['purchase'] is not None:
            slots = r['purchase']['slots']
            require(all(lives[i]['birth_tick'] <= s['birth_tick'] for i in slots) and s['parent'] in slots and
                    {i for i, p in lives.items() if p['birth_tick'] <= s['birth_tick'] and
                        (p['death_tick'] is None or p['death_tick'] > s['birth_tick'])} <= set(slots),
                    'purchase population differs')
            clear = set(free_columns(slots, lives))
            purchase = dict(spacing_clear=sorted(clear), reach={})
            for label, choices in supports.items():
                counts = [len(clear & set(cs)) for cs in choices]
                purchase['reach'][label] = dict(minimum=min(counts), maximum=max(counts))
        windows = {}
        for label in periods:
            old = old_seeds[label].get(tuple(r['seed']))
            mask_hist, opened_hist = Counter(), Counter()
            reach = {name: Counter() for name in traits}
            for slots, mask, opened, n in r['contexts'][label]:
                require(type(n) is int and n > 0 and not mask & 1 and old is not None, 'invalid mature context')
                clear = free_columns(slots, lives)
                mask_hist[str(mask)] += n
                opened_hist[str(opened)] += n
                for name, choices in supports.items():
                    bounds = intersection_bounds(clear, choices, s['column'], mask, opened)
                    reach[name][bounds['category']] += n
            require(dict(mask_hist) == (old['mature_masks'] if old else {}) and
                    sum(n for opened, n in opened_hist.items() if int(opened)) ==
                    ((old['open_elsewhere_checks'] + sum(g['seed'] == r['seed']
                        for g in prior['windows'][label]['seed_window']['germinations'])) if old else 0),
                    'mature masks/open-site counts differ from frozen audit')
            windows[label] = dict(checks=sum(mask_hist.values()),
                global_open_checks=sum(n for k, n in opened_hist.items() if int(k)),
                reach={name: {c: counts[c] for c in REACH_CLASSES} for name, counts in reach.items()})
        reports.append(dict(seed=r['seed'], column=s['column'], outcome=s['outcome'],
                            timing=t, purchase=purchase, windows=windows))
    summaries = {}
    for label, left in periods.items():
        cohort = [r for r in reports if tuple(r['seed']) in old_seeds[label]]
        purchases = [r for r in reports if r['seed'][1] > left]
        require(len(cohort) == len(old_seeds[label]), 'incomplete period seed cohort')
        old_summary = prior['windows'][label]['seed_window']['summary']
        total = sum(r['windows'][label]['checks'] for r in cohort)
        require(total == old_summary['mature_checks'] and len(purchases) == old_summary['cohorts']['purchased']['seeds'],
                'period coverage differs')
        summaries[label] = dict(purchases=len(purchases),
            purchase_timing=dict(Counter(r['timing']['category'] for r in purchases)),
            purchase_outcomes=dict(Counter(r['outcome'] for r in purchases)),
            purchase_global_spacing_closed=sum(not r['purchase']['spacing_clear'] for r in purchases),
            purchase_blocked_with_space_elsewhere=sum(r['timing']['category'] == 'blocked_at_purchase' and
                bool(r['purchase']['spacing_clear']) for r in purchases),
            trait_ambiguity={name: sum(len(ts[r['seed'][0]]) > 1 for r in purchases) for name, ts in traits.items()},
            check_cohort_seeds=len(cohort), check_cohort_timing=dict(Counter(r['timing']['category'] for r in cohort)),
            mature_checks=total, mature_by_purchase_timing=dict(sum_counters(
                Counter({r['timing']['category']: r['windows'][label]['checks']}) for r in cohort)),
            reach={name: dict(sum_counters(r['windows'][label]['reach'][name] for r in cohort)) for name in traits})
    return dict(parents=[dict(id=i, origin=lives[i]['column'], **{name: ts[i] for name, ts in traits.items()})
                        for i in sorted(traits['landing_only'])], seeds=reports, summary=summaries)


def sum_counters(values):
    out = Counter()
    for v in values:
        out.update(v)
    return out


def process(item, excerpt, run, prior):
    require(excerpt['id'] == item['id'] and excerpt['traces'] ==
            {k: run['traces'][k] for k in ('stand', 'adult')}, 'wrong excerpt provenance')
    records = extract(run['result'], excerpt['rows'])
    derived = analyze(run['result'], records, prior)
    print(item['id'] + ': purchase timing and reach bounds reconciled', flush=True)
    return dict(**item, evidence=records, analysis=derived)


def calculate(jobs=4):
    require(type(jobs) is int and 1 <= jobs <= 4, 'use 1..4 reader jobs')
    capture, panel, prior = inputs()
    worlds, pending = [], deque()
    with lzma.open(ROOT / WINDOWS, 'rt') as stream, ProcessPoolExecutor(
            max_workers=jobs, mp_context=get_context('fork')) as pool:
        require(json.loads(next(stream)) == previous.header(), 'wrong window header')
        for item in panel:
            excerpt = json.loads(next(stream))
            pending.append(pool.submit(process, item, excerpt, capture['runs'][item['id']], prior[item['id']]))
            if len(pending) >= jobs:
                worlds.append(pending.popleft().result())
        require(not stream.read(), 'trailing excerpt worlds')
        worlds.extend(f.result() for f in pending)
    return dict(**provenance(), worlds=worlds)


def check_value(value):
    capture, panel, prior = inputs()
    require({k: v for k, v in value.items() if k != 'worlds'} == provenance() and
            len(value['worlds']) == len(panel), 'wrong dispersal-timing provenance/panel')
    for w, item in zip(value['worlds'], panel, strict=True):
        require({k: v for k, v in w.items() if k not in ('evidence', 'analysis')} == item, 'world identity differs')
        require(w['analysis'] == analyze(capture['runs'][item['id']]['result'], w['evidence'], prior[item['id']]),
                'saved dispersal-timing analysis differs')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--out', type=Path, help='fresh portable .json.gz output')
    action.add_argument('--verify', type=Path)
    parser.add_argument('--reextract', action='store_true', help='also re-read the pinned window excerpt')
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args(argv)
    require(not args.reextract or args.verify is not None, 're-extraction is a verification option')
    if args.out is not None:
        require(not args.out.exists() and not args.out.is_symlink(), 'fresh output required')
        value = calculate(args.jobs)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        write_gzip(args.out, value)
    else:
        with gzip.open(args.verify, 'rt') as stream:
            value = json.load(stream)
        check_value(value)
        if args.reextract:
            require(calculate(args.jobs) == value, 'independent window re-extraction differs')
        print('Verified purchase timing and bounded reach without simulation.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, IndexError, StopIteration) as error:
        print('dispersal-timing audit failed: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
