#!/usr/bin/env python3
"""Offline early-life diagnosis of two fixed cases; no native calls or policy changes."""

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path

import population_gates_panel as panel

collect, prepare, score, trace = panel.collect, panel.prepare, panel.score, panel.trace
ARCHIVE = collect.ROOT / 'benchmarks/garden-seasons/leaf-population-gates-panel-results.json.gz'
ARCHIVE_SHA = '2c1e0260aad599c631073d3f796bc2529e97632e1ff6110bd2f2998aff4900fd'
LATE_ARCHIVE = collect.ROOT / 'benchmarks/garden-seasons/leaf-population-gates-transfer-results.json.gz'
LATE_SHA = '4c2a1c1522ec0ad696a9214f8b40941f14e3f698d9f5973aed7883b11d5ee175'
SEEDS = ('9a903368', '59818bc3')
WINDOWS = ((0, 12), (12, 16), (16, 32), (32, 48), (48, 64))


def archive(path, expected, schema):
    raw = path.read_bytes()
    score.require(prepare.sha(raw) == expected, 'evidence archive identity differs')
    bundle = json.loads(gzip.decompress(raw))
    score.require(bundle['schema'] == schema, 'evidence schema differs')
    return bundle


def plant_window(resources, lineage, first, end):
    """Sum fluxes, not stocks; retain actual coverage if birth/death truncates a window."""
    score.require(0 <= first < end <= 256, 'invalid resource window')
    rows = [r for r in resources['plant_days'] if r['lineage'] == lineage and first <= r['day'] < end]
    if not rows:
        return None
    result = dict(first_tick=rows[0]['first_tick'], last_tick=rows[-1]['last_tick'],
                  samples=sum(r['samples'] for r in rows),
                  renewals=sum(r['renewals'] for r in rows),
                  energy_short=sum(r['energy_short'] for r in rows),
                  water_short=sum(r['water_short'] for r in rows),
                  leaves_before=rows[0]['leaves_before'], leaves_after=rows[-1]['leaves_after'],
                  condition_before=rows[0]['condition_before'], condition_after=rows[-1]['condition_after'])
    for resource in ('energy', 'water'):
        for previous, current in zip(rows, rows[1:]):
            score.require(previous['last_tick'] + score.STEP == current['first_tick'] and
                          previous[resource]['after'] == current[resource]['before'], 'resource continuity differs')
        flow = {k: rows[0][resource][k] if k == 'before' else rows[-1][resource][k] if k == 'after'
                else sum(r[resource][k] for r in rows) for k in rows[0][resource]}
        score.require(flow['before'] + flow['income'] + flow['endowment'] ==
                      sum(flow[k] for k in ('after', 'overflow', 'upkeep_paid', 'growth', 'seeds', 'discarded', 'repair')),
                      'window resource conservation differs')
        result[resource] = flow
    return result


def checks_summary(rows):
    """Blocker counts overlap; open_sites maps COLUMN to count, not number of free sites."""
    counters = {field: Counter() for field in ('masks', 'no_living_masks', 'open_sites')}
    for row in rows:
        trace.check_histogram(row)
        for field in counters:
            counters[field].update(row[field])
    result = {k: sum(r[k] for r in rows) for k in ('checks', 'expired', 'germinated')}
    result.update({field: dict(sorted(c.items(), key=lambda item: int(item[0]))) for field, c in counters.items()})
    result['blockers'] = {name: sum(n for mask, n in counters['masks'].items() if int(mask) & (1 << bit))
                          for bit, name in enumerate(trace.BLOCKERS)}
    result['spacing_only'] = counters['masks']['32']
    result['no_living_checks'] = sum(counters['no_living_masks'].values())
    result['no_living_spacing_only'] = counters['no_living_masks']['32']
    return result


def seed_detail(seed, resources, value):
    key = (seed['parent'], seed['birth_tick'], seed['column'])
    matches = [s for s in resources['seeds'] if (s['parent'], s['birth_tick'], s['column']) == key]
    score.require(len(matches) == 1, 'missing or duplicate seed trace')
    recorded = matches[0]
    expiry = seed['birth_tick'] + seed['lifetime_ecology_ticks'] * score.STEP
    score.require(seed['end_tick'] is not None and seed['end_tick'] <= trace.STOP,
                  'early seed outcome not covered by trace')
    child = value['lineages'][seed['child_id'] - 1] if seed['child_id'] else None
    return dict(seed, expiry_tick=expiry,
        parent_death_tick=value['lineages'][seed['parent'] - 1]['death_tick'],
        child_established_by_608=child is not None and trace.losses.established(child, panel.follow.STOP),
        remaining_ticks_at_germination=expiry - child['birth_tick'] if child else None,
        returned_from_seed_only=recorded['attempts']['no_living_masks'].get('0', 0) == 1,
        attempts=checks_summary([recorded['attempts']]))


def summarize(value, resources):
    early = value | score.history_prefix(value, 64 * score.DAY) | dict(ticks=64 * score.DAY)
    early_family = trace.losses.family_rows(early)[1]
    plants = [p for p, root in zip(value['lineages'], value['family_roots'], strict=True)
              if root == 2 and p['birth_tick'] <= 64 * score.DAY]
    seeds = [seed_detail(s, resources, value) for s in value['seeds']
             if value['family_roots'][s['parent'] - 1] == 2 and s['birth_tick'] <= 64 * score.DAY]
    return dict(family_at_day64=early_family, family_at_day608=trace.losses.family_rows(value)[1],
        early_plants=[dict(p, death_flag=trace.losses.CAUSES[value['death_causes'][p['id'] - 1]]
                           if p['death_tick'] is not None else None,
                           established_by_day608=trace.losses.established(p, panel.follow.STOP),
                           windows={f'{first}-{end}': plant_window(resources, p['id'], first, end)
                                    for first, end in WINDOWS}) for p in plants],
        founder_budget_through_day64=plant_window(resources, 2, 0, 64),
        early_seed_fates=seeds,
        seed_only_returns_through_day64=[s for s in seeds if s['returned_from_seed_only'] and
                                        s['end_tick'] <= 64 * score.DAY],
        seed_check_windows={f'{first}-{end}': checks_summary(resources['seed_days'][first:end])
                            for first, end in ((0, 16), (16, 32), (32, 48), (48, 64), (64, 66))})


def record(bundle, run, seed, variant, after_tick, models, size, digests, label):
    data = {}
    for key, relative in (('final', 'stdout.json'), ('anchor', f'timeline/tick-{trace.STOP:010d}.json'),
                          ('resources', 'timeline/trace.json')):
        name = f'runs/{run}/{relative}'
        raw = prepare.blob(bundle, name)
        digests[f'{label}/{name}'] = prepare.sha(raw)
        data[key] = json.loads(raw)
    for key, tick in (('final', panel.follow.STOP), ('anchor', trace.STOP)):
        panel.gates.underlying(data[key], variant, models, size, tick, seed=seed, after_tick=after_tick)
    score.require(score.history_prefix(data['final'], trace.STOP) ==
                  score.history_prefix(data['anchor'], trace.STOP), 'trace anchor history differs')
    trace.validate_trace(data['resources'], data['anchor'])
    return data['final'], data['resources']


def diagnose():
    bundle = archive(ARCHIVE, ARCHIVE_SHA, panel.ARCHIVE_SCHEMA)
    late = archive(LATE_ARCHIVE, LATE_SHA, panel.transfer.ARCHIVE_SCHEMA)
    _, models, size = collect.archive_inputs()
    results, digests, cached = {}, {}, {}
    for seed in SEEDS:
        results[seed] = {}
        for variant in panel.gates.VARIANTS:
            value, resources = record(bundle, f'{seed}-{variant}-on', seed, variant, 0,
                                       models, size, digests, 'from-start')
            cached[seed, variant] = value, resources
            results[seed][variant] = summarize(value, resources)
    secondary = {}
    seed = SEEDS[1]
    original, original_trace = cached[seed, 'none']
    for variant in panel.gates.VARIANTS:
        value, resources = record(late, f'{variant}-on', seed, variant, panel.gates.AFTER,
                                   models, size, digests, 'late')
        score.require(score.history_prefix(value, 64 * score.DAY) == score.history_prefix(original, 64 * score.DAY) and
                      [r for r in resources['plant_days'] if r['day'] < 64] ==
                      [r for r in original_trace['plant_days'] if r['day'] < 64] and
                      resources['seed_days'][:64] == original_trace['seed_days'][:64], 'late early prefix differs')
        secondary[variant] = dict(early_prefix_matches_unchanged=True,
                                  family_at_day608=trace.losses.family_rows(value)[1])
    return dict(schema='garden-population-gates-early-v1', native_calls=0, trace_stop_day=256,
        early_stop_day=64, outcome_stop_day=608, evidence_sha256=ARCHIVE_SHA, late_evidence_sha256=LATE_SHA,
        inputs=digests, cases=results, late_comparison=secondary)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--out', type=Path, help='new derived JSON; never overwrite existing output')
    mode.add_argument('--check', type=Path, help='recompute and compare the existing derived JSON')
    args = parser.parse_args()
    result = diagnose()
    if args.check:
        score.require(result == json.loads(args.check.read_bytes()), 'derived early-life analysis differs')
    else:
        collect.save(args.out, result)
    print('Verified eight from-start cases and four late-rescue references; zero native calls.')
