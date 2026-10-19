#!/usr/bin/env python3
"""Two unchanged replays with step budgets around eight missed seed openings."""

from collections import Counter
import json
import zlib

import population_reproduction as access

fallback, follow = access.fallback, access.follow
collect, prepare, score = access.collect, access.prepare, access.score
BASELINE = collect.ROOT / 'benchmarks/garden-seasons/leaf-population-reproduction-results.json.gz'
BASELINE_SHA = '3258eda497056194975a308f3a8ab79bd8c980afa968cb694b8263033adb226e'
PROTOCOL = collect.ROOT / 'benchmarks/garden-seasons/leaf-population-budget-protocol.md'
ARCHIVE_SCHEMA = 'garden-population-budget-evidence-v1'
EVENTS = (587040, 621660, 709920, 733500, 733560, 744540, 764520, 867420)
BEFORE, AFTER, LINEAGE = 3840, 960, 17
TICKS = sorted({tick for event in EVENTS for tick in range(event - BEFORE + 15, event + AFTER + 1, 15)})
FLUX = ('before', 'income', 'overflow', 'endowment', 'upkeep_due', 'upkeep_paid', 'growth', 'seeds', 'discarded', 'after', 'repair')


def roster():
    return [dict(id=f'{fallback.SEED}-condition-fewest-{mode}', mode=mode) for mode in ('off', 'on')]


def arguments(call):
    return ['--budget-panel', fallback.SEED, 'condition', 'fewest', call['mode']]


def inputs():
    baseline = fallback.purchase.early.archive(BASELINE, BASELINE_SHA, access.ARCHIVE_SCHEMA)
    _, models, size = collect.archive_inputs()
    return baseline, models, size


def aggregate(rows, resource):
    return {k: (rows[0][resource][k] if k == 'before' else rows[-1][resource][k] if k == 'after'
                else sum(r[resource][k] for r in rows)) for k in FLUX}


def validate_trace(data, reproduction, resources):
    score.require(data['schema'] == 'garden-reproduction-budget-v1' and data['complete'] is True and
                  (data['lineage'], data['before_ticks'], data['after_ticks'], data['limit']) ==
                  (LINEAGE, BEFORE, AFTER, 2560) and data['events'] == list(EVENTS), 'budget identity differs')
    rows = data['rows']
    score.require([r['tick'] for r in rows] == TICKS and len(rows) == 2244, 'budget coverage differs')
    observed = {r['tick']: v for r in reproduction['openings'] for v in r['visits'] if v['lineage'] == LINEAGE}
    selected = sorted(t for t, v in observed.items() if v['seed_count'] < 8 and v['blockers'] in (128, 256, 384))
    score.require(selected == list(EVENTS), 'event selection differs from archived open visits')
    visit_masks = Counter()
    prior = None
    for r in rows:
        score.require(r['maintenance'] is (r['tick'] % 60 == 0) and
                      all(score.integer(r[k], 0, 65535) for k in ('nodes_before', 'nodes_after',
                      'leaves_before', 'leaves_after', 'condition_before', 'condition_after',
                      'condition_endowment', 'worn', 'restored')) and
                      all(score.integer(r[k], 0, 255) for k in ('stress_before', 'stress_after')),
                      'invalid budget metadata')
        score.require(0 <= r['renewals'] <= r['proposals'] <= r['observations'] <= 1 and
                      0 <= r['leaves_after'] - r['leaves_before'] <= 1 and
                      r['condition_endowment'] == 255 * (r['leaves_after'] - r['leaves_before']) and
                      r['condition_before'] + r['condition_endowment'] + r['restored'] ==
                      r['condition_after'] + r['worn'], 'leaf conservation differs')
        score.require(all(score.integer(r[k], 0, 254) for k in
                      ('remainder_before', 'remainder_uptake', 'remainder_after')) and
                      r['remainder_uptake'] == r['remainder_after'] and r['remainder_discarded'] == 0,
                      'fractional resource stages differ')
        for resource, cost, cap in (('energy', 9, 256), ('water', 5, 512)):
            f = r[resource]
            score.require(all(score.integer(f[k], 0, 65535) for k in FLUX) and len(f['points']) == 6 and
                          all(score.integer(p, 0, cap) for p in f['points']), 'invalid budget flux')
            before, uptake, paid, germination, growth, reproduction_point = f['points']
            score.require(before == f['before'] and uptake == before + f['income'] - f['overflow'] and
                          uptake == min(cap, before + f['income']) and
                          f['upkeep_paid'] == min(uptake, f['upkeep_due']) and paid == uptake - f['upkeep_paid'] and
                          f['endowment'] == f['discarded'] == 0 and germination == paid and
                          growth == germination - f['growth'] - f['repair'] and
                          reproduction_point == growth - f['seeds'] == f['after'] and
                          f['repair'] == cost * r['renewals'] and
                          (r['maintenance'] or f['upkeep_due'] == 0), 'payment stages/conservation differ')
            if prior is not None and r['tick'] == prior['tick'] + 15:
                score.require(f['before'] == prior[resource]['after'], 'resource continuity differs')
        if prior is not None and r['tick'] == prior['tick'] + 15:
            for before, after in (('leaves_before', 'leaves_after'), ('condition_before', 'condition_after'),
                                  ('nodes_before', 'nodes_after'), ('stress_before', 'stress_after'),
                                  ('remainder_before', 'remainder_after')):
                score.require(r[before] == prior[after], 'plant continuity differs')
        v = r['visit']
        score.require((v is not None) == r['maintenance'], 'visit cadence differs')
        if v is not None:
            mask = v['blockers']
            score.require(score.integer(mask, 0, 1023) and not mask & 2 and score.integer(v['seed_count'], 0, 8) and
                          bool(mask & 4) == (v['seed_count'] == 8), 'budget visit mask differs')
            for resource, bit, cost in (('energy', 128, 48), ('water', 256, 24)):
                score.require(score.integer(v[resource + '_required'], 0, 65535) and
                              bool(mask & bit) == (r[resource]['points'][4] < v[resource + '_required']) and
                              r[resource]['seeds'] == (cost if mask == 0 else 0), 'budget eligibility differs')
            visit_masks[str(mask)] += 1
            if r['tick'] in observed:
                old = observed[r['tick']]
                score.require(all(v[k] == old[k] for k in v) and
                              all(r[k]['points'][4] == old[k] for k in ('energy', 'water')),
                              'opening receipt differs')
        prior = r
    totals, = [r['masks'] for r in reproduction['lineages'] if r['lineage'] == LINEAGE]
    score.require(all(v <= totals.get(k, 0) for k, v in visit_masks.items()), 'visit subset exceeds full trace')
    # Exact full calendar days cross-check the independently retained daily trace.
    daily = {r['day']: r for r in resources['plant_days'] if r['lineage'] == LINEAGE}
    checked_days = []
    for day in sorted({(r['tick'] - 1) // score.DAY for r in rows}):
        selected_rows = [r for r in rows if day * score.DAY < r['tick'] <= (day + 1) * score.DAY]
        if len(selected_rows) == 256:
            for resource in ('energy', 'water'):
                score.require(aggregate(selected_rows, resource) == daily[day][resource], 'daily budget differs')
            checked_days.append(day)
    by_tick = {r['tick']: r for r in rows}
    summaries = []
    for tick in EVENTS:
        r = by_tick[tick]
        before = [s for s in rows if tick - BEFORE < s['tick'] <= tick]
        after = [s for s in rows if tick < s['tick'] <= tick + AFTER]
        deficit = {k: max(0, r['visit'][k + '_required'] - r[k]['points'][4]) for k in ('energy', 'water')}
        repaired = {k: r[k]['points'][4] + r[k]['repair'] for k in ('energy', 'water')}
        recovery = next((s for s in after if s['visit'] is not None and not s['visit']['blockers'] & (128 | 256)), None)
        last_cap = {k: next((s['tick'] for s in reversed(before) if s[k]['points'][1] == cap), None)
                    for k, cap in (('energy', 256), ('water', 512))}
        summaries.append(dict(tick=tick, day=tick / score.DAY, deficit=deficit,
            opening=r, preceding_day={k: aggregate(before, k) for k in ('energy', 'water')},
            following_quarter_day={k: aggregate(after, k) for k in ('energy', 'water')},
            immediate_repair_addback=repaired,
            immediate_addback_meets_resource_thresholds=all(repaired[k] >= r['visit'][k + '_required'] for k in repaired),
            last_observed_cap_tick=last_cap,
            repair_since_last_observed_cap={k: sum(s[k]['repair'] for s in before if s['tick'] >= t)
                                           if t is not None else None for k, t in last_cap.items()},
            first_following_resource_funded_visit=recovery))
    return dict(records=len(rows), joined_openings=len(set(TICKS) & observed.keys()),
                complete_calendar_days=checked_days, events=summaries)


def validate_outputs(out, baseline, models, size):
    result = None
    for call in roster():
        folder = out / 'runs' / call['id']
        old = 'runs/' + call['id']
        encoded_final = (folder / 'stdout.json').read_bytes()
        score.require(encoded_final == prepare.blob(baseline, old + '/stdout.json'), 'baseline final differs')
        final = json.loads(encoded_final)
        expected = {f'tick-{d * score.DAY:010d}.{ext}' for d in follow.DAYS for ext in ('raw', 'json')}
        for day in follow.DAYS:
            name = f'tick-{day * score.DAY:010d}'
            path = folder / 'timeline' / name
            encoded, raw = path.with_suffix('.json').read_bytes(), path.with_suffix('.raw').read_bytes()
            value = json.loads(encoded)
            fallback.gates.underlying(fallback.gate_record(value), 'condition', models, size,
                                      day * score.DAY, seed=fallback.SEED, after_tick=0)
            score.require(encoded == prepare.blob(baseline, old + '/timeline/' + name + '.json') and
                          raw == prepare.blob(baseline, old + '/timeline/' + name + '.raw') and
                          len(raw) == 115200 and value['framebuffer_crc32'] == f'{zlib.crc32(raw):08x}', 'baseline checkpoint differs')
            score.require(score.history_prefix(final, day * score.DAY) == score.history_prefix(value, day * score.DAY),
                          'history prefix differs')
            if call['mode'] == 'on':
                other = out / 'runs' / (call['id'][:-2] + 'off') / 'timeline' / name
                score.require(encoded == other.with_suffix('.json').read_bytes() and raw == other.with_suffix('.raw').read_bytes(),
                              'logging changed checkpoint')
        score.require(final == value, 'stdout differs from endpoint')
        if call['mode'] == 'on':
            old_traces = {}
            for name in ('trace.json', 'purchases.json', 'reproduction.json'):
                raw = (folder / 'timeline' / name).read_bytes()
                score.require(raw == prepare.blob(baseline, old + '/timeline/' + name), 'baseline diagnostic differs')
                old_traces[name] = json.loads(raw)
            result = validate_trace(json.loads((folder / 'timeline/budget.json').read_bytes()),
                                    old_traces['reproduction.json'], old_traces['trace.json'])
            expected.update(('trace.json', 'purchases.json', 'reproduction.json', 'budget.json'))
        score.require({p.name for p in (folder / 'timeline').iterdir()} == expected, 'output roster differs')
    return result


EXPERIMENT = follow.Experiment('garden-population-budget-collection-v1', ARCHIVE_SCHEMA,
                              BASELINE_SHA, PROTOCOL, inputs, arguments, validate_outputs, roster)


if __name__ == '__main__':
    follow.main(__doc__, experiment=EXPERIMENT)
