#!/usr/bin/env python3
"""Offline matched-day foliage and dawn budgets; no native execution."""

import argparse
import json
from pathlib import Path

import population_budget as budget

access, fallback = budget.access, budget.fallback
collect, prepare, score = budget.collect, budget.prepare, budget.score
early, trace = fallback.purchase.early, fallback.panel.trace
ARCHIVE = collect.ROOT / 'benchmarks/garden-seasons/leaf-population-budget-results.json.gz'
ARCHIVE_SHA = 'ab314a17361fe939525f61c6d340fc45d9a0058f0fb0fdc9c770f432709728ed'
FIRST, END = 128, 232
FOCAL_DAYS = (151, 152, 153)
FOCAL_TICK = 587040
DAWN_TICKS = tuple(range(FOCAL_TICK - 120, FOCAL_TICK + 61, 60))
LINEAGES = {'original': 19, 'fewest': 17}


def mean_condition(condition, leaves):
    score.require(score.integer(leaves, 1, 256) and score.integer(condition, 0, leaves * 255),
                  'invalid leaf condition denominator')
    return condition / leaves


def daily_rows(resources, lineage):
    rows = [r for r in resources['plant_days'] if r['lineage'] == lineage and FIRST <= r['day'] < END]
    score.require([r['day'] for r in rows] == list(range(FIRST, END)), 'matched-day coverage differs')
    for r in rows:
        score.require(r['first_tick'] == r['day'] * score.DAY + score.STEP and
                      r['last_tick'] == (r['day'] + 1) * score.DAY and r['samples'] == 256 and
                      r['maintenance'] == 64 and not r['born'] and not r['died'], 'partial matched day')
        for endpoint in ('before', 'after'):
            mean_condition(r['condition_' + endpoint], r['leaves_' + endpoint])
    return rows


def compare_days(cases):
    rows = {p: daily_rows(cases[p]['resources'], lineage) for p, lineage in LINEAGES.items()}
    pairs = []
    for original, fewest in zip(rows['original'], rows['fewest'], strict=True):
        pair = dict(day=original['day'])
        for policy, r in (('original', original), ('fewest', fewest)):
            pair[policy] = dict(r, mean_condition_before=mean_condition(r['condition_before'], r['leaves_before']),
                                mean_condition_after=mean_condition(r['condition_after'], r['leaves_after']))
        pairs.append(pair)
    summaries = {}
    for policy, lineage in LINEAGES.items():
        plant, = [p for p in cases[policy]['final']['lineages'] if p['id'] == lineage]
        score.require(cases[policy]['final']['family_roots'][lineage - 1] == 2 and plant['species'] == 1 and
                      plant['birth_tick'] < FIRST * score.DAY and
                      (plant['death_tick'] is None or plant['death_tick'] > END * score.DAY), 'wrong comparison lineage')
        summaries[policy] = dict(plant=plant, age_at_focal_ticks=FOCAL_TICK - plant['birth_tick'],
            node_counts=sorted({r['nodes_' + end] for r in rows[policy] for end in ('before', 'after')}),
            leaf_counts=sorted({r['leaves_' + end] for r in rows[policy] for end in ('before', 'after')}),
            totals=early.plant_window(cases[policy]['resources'], lineage, FIRST, END))
    def wins(extract):
        comparisons = [extract(p['original']) - extract(p['fewest']) for p in pairs]
        return dict(original_higher=sum(v > 0 for v in comparisons), equal=sum(v == 0 for v in comparisons),
                    fewest_higher=sum(v < 0 for v in comparisons))
    return dict(first_day=FIRST, end_day_exclusive=END, days=len(pairs), cases=summaries, daily=pairs,
                comparisons=dict(energy_income=wins(lambda r: r['energy']['income']),
                    endpoint_mean_condition=wins(lambda r: r['mean_condition_after']),
                    renewals=wins(lambda r: r['renewals'])),
                focal_days=[p for p in pairs if p['day'] in FOCAL_DAYS])


def dawn_rows(reproduction, steps):
    original = {r['tick']: v for r in reproduction['openings'] for v in r['visits'] if v['lineage'] == 19}
    fewest = {r['tick']: r for r in steps['rows']}
    result = []
    for tick in DAWN_TICKS:
        score.require(tick in original and tick in fewest, 'missing dawn receipt')
        a, b = original[tick], fewest[tick]
        score.require(b['visit'] is not None and
                      (a['energy_required'], a['water_required']) ==
                      (b['visit']['energy_required'], b['visit']['water_required']), 'dawn thresholds differ')
        result.append(dict(tick=tick, original=a, fewest=dict(b['visit'], energy=b['energy']['points'][4],
            water=b['water']['points'][4], condition_before=b['condition_before'],
            mean_condition_before=mean_condition(b['condition_before'], b['leaves_before']))))
    return result


def diagnose():
    base = early.archive(budget.BASELINE, budget.BASELINE_SHA, access.ARCHIVE_SCHEMA)
    detailed = early.archive(ARCHIVE, ARCHIVE_SHA, budget.ARCHIVE_SCHEMA)
    _, models, size = collect.archive_inputs()
    inputs, cases = {}, {}
    for policy in LINEAGES:
        prefix = f'runs/{fallback.SEED}-condition-{policy}-on/'
        records = {}
        for label, name in (('final', 'stdout.json'), ('anchor', f'timeline/tick-{trace.STOP:010d}.json'),
                            ('resources', 'timeline/trace.json'), ('reproduction', 'timeline/reproduction.json')):
            raw = prepare.blob(base, prefix + name)
            inputs['reproduction/' + prefix + name] = prepare.sha(raw)
            records[label] = json.loads(raw)
            if policy == 'fewest':
                score.require(raw == prepare.blob(detailed, prefix + name), 'budget baseline differs')
        for label, tick in (('final', fallback.follow.STOP), ('anchor', trace.STOP)):
            value = records[label]
            projected = fallback.gate_record(value) if policy == 'fewest' else value
            fallback.gates.underlying(projected, 'condition', models, size, tick,
                                      seed=fallback.SEED, after_tick=0)
        score.require(score.history_prefix(records['final'], trace.STOP) ==
                      score.history_prefix(records['anchor'], trace.STOP), 'daily anchor history differs')
        trace.validate_trace(records['resources'], records['anchor'])
        access.validate_trace(records['reproduction'], records['final'])
        cases[policy] = records
    name = f'runs/{fallback.SEED}-condition-fewest-on/timeline/budget.json'
    raw = prepare.blob(detailed, name)
    inputs['budget/' + name] = prepare.sha(raw)
    steps = json.loads(raw)
    budget.validate_trace(steps, cases['fewest']['reproduction'], cases['fewest']['resources'])
    matched = compare_days(cases)
    # Cross-check the comparison day against its independently validated step ledger.
    for pair in matched['focal_days']:
        selected = [r for r in steps['rows'] if pair['day'] * score.DAY < r['tick'] <= (pair['day'] + 1) * score.DAY]
        if len(selected) == 256:
            score.require(all(budget.aggregate(selected, k) == pair['fewest'][k] for k in ('energy', 'water')),
                          'focal day differs from step budget')
    return dict(schema='garden-population-dawn-v1', native_calls=0, seed=fallback.SEED, variant='condition',
                reproduction_archive_sha256=budget.BASELINE_SHA, budget_archive_sha256=ARCHIVE_SHA,
                runtime_archive_sha256=prepare.ARCHIVE_SHA, inputs=inputs,
                matched=matched, dawn=dawn_rows(cases['original']['reproduction'], steps))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--out', type=Path, help='new derived JSON; never overwrite')
    mode.add_argument('--check', type=Path, help='recompute and compare derived JSON')
    args = parser.parse_args()
    result = diagnose()
    if args.check:
        score.require(json.loads(args.check.read_bytes()) == result, 'dawn derivation differs')
    else:
        collect.save(args.out, result)
    print('Verified 104 matched days and four dawn visits; zero native calls.')
