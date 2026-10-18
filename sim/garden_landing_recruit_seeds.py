#!/usr/bin/env python3
"""Audit every day-384-to-512 recruit and seed from saved ledgers; never replay."""

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path

import garden_landing_competitive_renewal as previous
from garden_experiments import digest
from garden_landing_founders import write_gzip
from garden_resources import require

ROOT, DAY, BASE, STOP = previous.ROOT, previous.DAY, previous.BASE, previous.STOP
STEP, DORMANCY, CAPACITY, SPACING = 15, 8, 8, 3
RULE = 'garden-landing-recruit-seeds-v1'
INPUT = 'benchmarks/garden-seasons/landing-competitive-renewal-results.json.gz'
INPUT_SHA = '099d2550d8037b3148b9c135a53b3fe3d5e971151234fa540ad8dbc6231073dc'
# These are the captured rules inspected for stage order, stable seed-bank
# compaction and immutable base columns, not a requirement on today's C files.
IMPLEMENTATION = {
    'src/garden_world.c': '92ed89937463a848bba684d7b333b8177a3f82ea9beba43b463704db1a0b96b7',
    'src/garden_world.h': 'f148562fe1aea1321b9a7dd3b12ab92c917a674d82588f5b89cc9b0770df4f4a',
    'sim/garden_landing_ledger.c': '14ca6dc91bdd97a42b74af73476d4c627ca3c0c3cc4fbdf3455faa5612cccd56',
}


def load_input():
    require(digest(ROOT / INPUT) == INPUT_SHA, 'competitive-renewal capture changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream:
        value = json.load(stream)
    previous.check_capture(value)
    require(all(value['source_sha256'][p] == sha for p, sha in IMPLEMENTATION.items()),
            'unrecognized captured seed-check rules')
    return value


def mature_window(seed, stop):
    """Inclusive check ticks: age eight is mature; expiry precedes the check."""
    first = seed['birth_tick'] + DORMANCY * STEP
    last = stop if seed['end_tick'] is None else seed['end_tick']
    if seed['outcome'] == 'expired':
        last -= STEP
    return first, last


def seed_history(seed_index, seeds, plants, stop):
    seed = seeds[seed_index]
    first, last = mature_window(seed, stop)
    ranks = {s['child_id']: i for i, s in enumerate(seeds) if s['child_id'] is not None}
    rows, refills = [], []
    for tick in range(first, last + 1, STEP):
        # Natural maintenance deaths precede checks. New seedlings appear inside
        # the seed loop, before growth and new purchases. No post-384 sweeps occur.
        before = [p for p in plants if p['birth_tick'] < tick and
                  (p['death_tick'] is None or p['death_tick'] > tick)]
        newborn = [p for p in plants if p['birth_tick'] == tick]
        earlier = [p for p in newborn if ranks[p['id']] < seed_index]
        living = before + earlier
        require(len(living) <= CAPACITY, 'living capacity exceeded at seed visit')
        state = dict(before_checks_living=len(before), living_at_turn=len(living),
                     living_spacing_blockers=sorted(p['id'] for p in living
                         if abs(p['column'] - seed['column']) < SPACING),
                     earlier_children=[p['id'] for p in earlier])
        if rows and rows[-1]['state'] == state:
            rows[-1]['last'] = tick
            rows[-1]['checks'] += 1
        else:
            rows.append(dict(first=tick, last=tick, checks=1, state=state))
        for p in newborn:
            if p['id'] != seed['child_id']:
                winner = seeds[ranks[p['id']]]
                refills.append(dict(tick=tick, child=p['id'], seed=winner,
                                    checked_earlier=ranks[p['id']] < seed_index,
                                    same_column=winner['column'] == seed['column']))
    counts = dict(mature_checks=sum(r['checks'] for r in rows), precheck_room=0,
                  headcount_room=0, capacity_excluded=0, spacing_excluded=0,
                  unresolved=0)
    for row in rows:
        state, n = row['state'], row['checks']
        capacity = state['living_at_turn'] >= CAPACITY
        spacing = bool(state['living_spacing_blockers'])
        counts['precheck_room'] += n * (state['before_checks_living'] < CAPACITY)
        counts['headcount_room'] += n * (not capacity)
        counts['capacity_excluded'] += n * capacity
        counts['spacing_excluded'] += n * spacing
        counts['unresolved'] += n * (not capacity and not spacing)
    return dict(seed=seed, mature_first_tick=first, observed_last_check_tick=last,
                expiry_tick=seed['birth_tick'] + seed['lifetime_ecology_ticks'] * STEP,
                censored=seed['outcome'] == 'pending', counts=counts, intervals=rows,
                other_germinations=refills)


def analyze_world(result):
    require(result['tick'] == STOP, 'audit requires day-512 endpoint')
    plants, seeds = result['lineages'], result['seeds']
    previous.index_records(plants, seeds, 0, STOP)
    require([s['birth_tick'] for s in seeds] == sorted(s['birth_tick'] for s in seeds),
            'nonchronological seed ledger')
    require(all(not p['environmental_death'] or p['death_tick'] <= BASE for p in plants),
            'post-check imposed deaths require a different stage reconstruction')
    require(all(0 <= p['column'] < 28 and (p['death_tick'] is None or
                p['death_tick'] > p['birth_tick']) for p in plants), 'invalid plant position/lifetime')
    recruits = []
    for plant in plants:
        if plant['birth_tick'] <= BASE:
            continue
        purchases = [seed_history(i, seeds, plants, STOP) for i, s in enumerate(seeds)
                     if s['parent'] == plant['id']]
        children = [p['id'] for p in plants if p['parent'] == plant['id']]
        recruits.append(dict(life=plant, cohort='primary' if plant['birth_tick'] <= previous.BIRTH_STOP else 'late',
                             age_32=previous.age_status(plant, 32),
                             observed_living_ticks=(plant['death_tick'] or STOP) - plant['birth_tick'],
                             purchase_status='purchased' if purchases else
                             ('none_before_death' if plant['death_tick'] is not None else 'none_observed'),
                             purchases=purchases, children=children))
    return dict(world_hash=result['world_hash'], run_hash=result['run_hash'], recruits=recruits)


def summarize(worlds):
    summary = {}
    for arm in previous.ARMS:
        summary[arm] = {}
        for cohort in ('primary', 'late'):
            recruits = [p for key in previous.PANEL for p in worlds[arm][key]['recruits']
                        if p['cohort'] == cohort]
            seeds = [s for p in recruits for s in p['purchases']]
            summary[arm][cohort] = dict(
                recruits=len(recruits), buyers=sum(bool(p['purchases']) for p in recruits),
                no_purchase=sum(not p['purchases'] for p in recruits),
                purchase_status=dict(Counter(p['purchase_status'] for p in recruits)),
                age_32=dict(Counter(p['age_32'] for p in recruits)),
                children=sum(len(p['children']) for p in recruits), purchases=len(seeds),
                seed_fates={f: sum(s['seed']['outcome'] == f for s in seeds)
                            for f in ('expired', 'germinated', 'pending')},
                expired_with_headcount_room=sum(s['seed']['outcome'] == 'expired' and
                                               s['counts']['headcount_room'] > 0 for s in seeds),
                expired_with_unresolved_checks=sum(s['seed']['outcome'] == 'expired' and
                                                   s['counts']['unresolved'] > 0 for s in seeds))
    return summary


def make_value(value):
    worlds = {a: {k: analyze_world(value['runs']['endpoint'][a][k]['result']) for k in previous.PANEL}
              for a in previous.ARMS}
    return dict(rule=RULE, input_sha256=INPUT_SHA, input_receipt_sha256=value['receipt_sha256'],
                implementation=IMPLEMENTATION, model_sha256=value['model_sha256'], panel=previous.PANEL,
                native_runs=0, training_runs=0,
                method=dict(start_exclusive=BASE, stop_inclusive=STOP, primary_stop=previous.BIRTH_STOP,
                            sample_step=STEP, dormancy_steps=DORMANCY, plant_capacity=CAPACITY,
                            minimum_spacing=SPACING, stored_dead_slots_reconstructed=False,
                            resource_or_purchase_eligibility_reconstructed=False),
                worlds=worlds, summary=summarize(worlds))


def check_value(saved):
    require(saved == make_value(load_input()), 'recruit seed audit differs from frozen ledgers')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--out', type=Path)
    mode.add_argument('--verify', type=Path)
    args = parser.parse_args()
    if args.verify:
        with gzip.open(args.verify, 'rt') as stream:
            saved = json.load(stream)
        check_value(saved)
    else:
        saved = make_value(load_input())
        write_gzip(args.out, saved)
    print(json.dumps(saved['summary'], indent=2))
    print('Recruit seed audit complete offline; no simulator executed.')


if __name__ == '__main__':
    main()
