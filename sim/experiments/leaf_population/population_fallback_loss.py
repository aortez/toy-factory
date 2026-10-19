#!/usr/bin/env python3
"""Offline diagnosis of the condition-only placement regression; zero native calls."""

import argparse
from collections import Counter
import json
from pathlib import Path

import population_fallback as fallback

early = fallback.purchase.early
collect, prepare, score, trace = fallback.collect, fallback.prepare, fallback.score, fallback.panel.trace
ARCHIVE = collect.ROOT / 'benchmarks/garden-seasons/leaf-population-fallback-results.json.gz'
ARCHIVE_SHA = '61381e2a5d72106e54212c78715718b1aef289bb91375518db204e6dfe5418ce'
# The authenticated maintenance profile excludes both 16-seed feature flags.
# These are actual frozen capacities/cadence, not the player's larger buffers.
SEED_CAPACITY, CADENCE = 8, 60
FIRST, END = 63 * score.DAY, 256 * score.DAY
WINDOWS = ((63, 96), (96, 128), (128, 160), (160, 192), (192, 224), (224, 232), (232, 233), (233, 256))
WINTER = ((124, 125), (125, 126), (126, 127), (127, 128))


def seed_key(seed):
    return seed['parent'], seed['birth_tick'], seed['column']


def seed_exposure(record, value):
    """Known living blockers only; dead-slot retention is not reconstructed.

    Strict endpoint inequalities exclude within-step birth/death ambiguity.
    Expiry has no germination check, so its last checked tick is one step earlier.
    """
    seed, = [s for s in value['seeds'] if seed_key(s) == seed_key(record)]
    first = record['first_tick']
    last = record['last_tick'] - (score.STEP if record['outcome'] == 1 else 0)
    score.require(first <= last, 'empty seed check interval')
    blockers = [dict(lineage=p['id'], founder=value['family_roots'][p['id'] - 1],
                     column=p['column'], birth_tick=p['birth_tick'], death_tick=p['death_tick'])
                for p in value['lineages'] if abs(p['column'] - seed['column']) < 3 and
                p['birth_tick'] < first and (p['death_tick'] is None or p['death_tick'] > last)]
    attempts = early.checks_summary([record['attempts']])
    if blockers:
        score.require(attempts['blockers']['spacing'] == attempts['checks'],
                      'persistent living blocker contradicts spacing trace')
    return dict(seed, trace_end_tick=record['last_tick'], trace_censored=record['outcome'] == 0,
                first_check_tick=first, last_check_tick=last, attempts=attempts,
                known_persistent_living_blockers=blockers)


def seed_bank(value, first, end):
    """Inventory on (first,end], separating event ticks from stable cadence ticks.

    A same-tick expiry/germination/purchase can change who sees the open slot.
    Never infer sequential eligibility or visitation order from final ledgers.
    """
    score.require(0 <= first < end <= value['ticks'], 'invalid bank window')
    seeds = value['seeds']
    event_ticks = {tick for s in seeds for tick in (s['birth_tick'], s['end_tick']) if tick is not None}
    occupancy, family_inventory = Counter(), Counter()
    events = []
    for tick in range((first // CADENCE + 1) * CADENCE, end + 1, CADENCE):
        if tick in event_ticks:
            events.append(tick)
            continue
        active = [s for s in seeds if s['birth_tick'] < tick and
                  (s['end_tick'] is None or s['end_tick'] > tick)]
        score.require(len(active) <= SEED_CAPACITY, 'frozen seed capacity exceeded')
        occupancy[str(len(active))] += 1
        roots = Counter(value['family_roots'][s['parent'] - 1] for s in active)
        family_inventory[','.join(str(roots[f]) for f in (1, 2, 3))] += 1
    buys = [s for s in seeds if first < s['birth_tick'] <= end]
    return dict(first_exclusive_tick=first, end_inclusive_tick=end, capacity=SEED_CAPACITY,
                cadence_ticks=CADENCE, non_event_cadence_samples=sum(occupancy.values()),
                non_event_occupancy=dict(occupancy), family_inventory=dict(family_inventory),
                event_cadence_ticks=events,
                purchases_by_founder={str(f): sum(value['family_roots'][s['parent'] - 1] == f for s in buys)
                                      for f in (1, 2, 3)},
                purchases_by_parent=dict(Counter(str(s['parent']) for s in buys)))


def plant_detail(plant, value, resources):
    lineage = plant['id']
    rows = [r for r in resources['plant_days'] if r['lineage'] == lineage]
    score.require(bool(rows), 'missing post-handoff resource coverage')
    buys = [s for s in value['seeds'] if s['parent'] == lineage]
    before_end = [s for s in buys if s['birth_tick'] < END]
    score.require(sum(r['energy']['seeds'] for r in rows) == len(before_end) * 48 and
                  sum(r['water']['seeds'] for r in rows) == len(before_end) * 24,
                  'plant seed costs differ from purchase history')
    return dict(plant, established_by_608=trace.losses.established(plant, value['ticks']),
                shortage_flag=trace.losses.CAUSES[value['death_causes'][lineage - 1]]
                              if plant['death_tick'] is not None else None,
                total_resources_through_256=early.plant_window(resources, lineage, 0, 256),
                windows={f'{a}-{z}': early.plant_window(resources, lineage, a, z) for a, z in WINDOWS},
                purchases_through_256=len(before_end), last_purchase_tick=buys[-1]['birth_tick'] if buys else None,
                children=[s['child_id'] for s in buys if s['child_id'] is not None])


def summarize(value, resources, edge_lineage):
    selected = [p for p in value['lineages'] if value['family_roots'][p['id'] - 1] == 2 and
                FIRST <= p['birth_tick'] < END]
    seeds = [seed_exposure(s, value) for s in resources['seeds'] if FIRST <= s['birth_tick'] < END]
    outcomes = Counter('censored' if s['trace_censored'] else s['outcome'] for s in seeds)
    failed = [s for s in seeds if not s['trace_censored'] and s['outcome'] == 'expired']
    continuous = [s for s in failed if s['attempts']['checks'] == s['attempts']['blockers']['spacing']]
    family = trace.losses.family_rows(value)[1]
    last_seed_end = max((s['end_tick'] for s in value['seeds']
                         if value['family_roots'][s['parent'] - 1] == 2 and s['end_tick'] is not None), default=0)
    quiet_rows = [r for r in resources['plant_days'] if r['lineage'] == 17 and 128 <= r['day'] < 232]
    return dict(family_at_608=family, renewal=fallback.follow.summarize(value, after_tick=0)['renewal']['2'],
        posthandoff_plants=[plant_detail(p, value, resources) for p in selected],
        posthandoff_seeds=seeds,
        seed_summary=dict(count=len(seeds), outcomes=dict(outcomes),
            expired_always_spacing_blocked=len(continuous),
            expired_with_persistent_own_blocker=sum(any(p['founder'] == 2 for p in s['known_persistent_living_blockers'])
                                                  for s in continuous),
            expired_with_persistent_other_blocker=sum(any(p['founder'] != 2 for p in s['known_persistent_living_blockers'])
                                                    for s in continuous)),
        edge_child=dict(lineage=edge_lineage, windows={f'{a}-{z}': early.plant_window(resources, edge_lineage, a, z)
                                                       for a, z in WINTER}),
        bank_128_232=seed_bank(value, 128 * score.DAY, 232 * score.DAY),
        lineage17_128_232=dict(resource_days=len(quiet_rows),
            daily_endpoints_energy_ge_200_water_ge_400=sum(r['energy']['after'] >= 200 and r['water']['after'] >= 400
                                                         for r in quiet_rows),
            stress_free_days=sum(r['stress_max'] == 0 for r in quiet_rows)),
        seedless_terminal_ticks=(family['extinction_tick'] - last_seed_end)
            if family['status'] == 'extinct' and last_seed_end <= family['extinction_tick'] else None)


def diagnose():
    bundle = early.archive(ARCHIVE, ARCHIVE_SHA, fallback.ARCHIVE_SCHEMA)
    _, models, size = collect.archive_inputs()
    inputs, cases = {}, {}
    for policy, edge in (('original', 19), ('fewest', 18)):
        prefix = f'runs/{fallback.SEED}-condition-{policy}-on/'
        records = {}
        for label, name in (('final', 'stdout.json'), ('anchor', f'timeline/tick-{END:010d}.json'),
                            ('resources', 'timeline/trace.json')):
            raw = prepare.blob(bundle, prefix + name)
            inputs[prefix + name] = prepare.sha(raw)
            records[label] = json.loads(raw)
        for label, tick in (('final', fallback.follow.STOP), ('anchor', END)):
            value = records[label]
            projected = fallback.gate_record(value) if policy == 'fewest' else value
            fallback.gates.underlying(projected, 'condition', models, size, tick,
                                      seed=fallback.SEED, after_tick=0)
        score.require(score.history_prefix(records['final'], END) == score.history_prefix(records['anchor'], END),
                      'resource anchor differs from full history')
        trace.validate_trace(records['resources'], records['anchor'])
        cases[policy] = summarize(records['final'], records['resources'], edge)
    return dict(schema='garden-population-fallback-loss-v1', native_calls=0, seed=fallback.SEED,
                variant='condition', evidence_sha256=ARCHIVE_SHA,
                runtime_archive_sha256=prepare.ARCHIVE_SHA, inputs=inputs,
                handoff_first_tick=FIRST, trace_stop_tick=END, outcome_stop_tick=fallback.follow.STOP,
                cases=cases)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--out', type=Path, help='new derived JSON; never overwrite')
    mode.add_argument('--check', type=Path, help='recompute and compare derived JSON')
    args = parser.parse_args()
    result = diagnose()
    if args.check:
        score.require(json.loads(args.check.read_bytes()) == result, 'fallback loss derivation differs')
    else:
        collect.save(args.out, result)
    print('Verified both condition-only trajectories; zero native calls.')
