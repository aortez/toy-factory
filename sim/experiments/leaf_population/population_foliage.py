#!/usr/bin/env python3
"""Matched, unchanged day-152 light/condition traces for two focal shrubs."""

from collections import Counter
import json
import zlib

import population_budget as budget

access, follow = budget.access, budget.follow
fallback, collect, prepare, score = budget.fallback, budget.collect, budget.prepare, budget.score
BASELINE, BASELINE_SHA = budget.BASELINE, budget.BASELINE_SHA
PROTOCOL = collect.ROOT / 'benchmarks/garden-seasons/leaf-population-foliage-protocol.md'
ARCHIVE_SCHEMA = 'garden-population-foliage-evidence-v1'
FIRST, END = 152 * score.DAY, 153 * score.DAY
DAWN, OPENING = FIRST + 3 * score.DAY // 4, FIRST + 7 * score.DAY // 8
TICKS = list(range(FIRST + 15, END + 1, 15))
FIELDS = ['node', 'x', 'y', 'column', 'row', 'light', 'condition']
ENERGY = ('before', 'income', 'overflow', 'upkeep_due', 'upkeep_paid', 'growth', 'seeds', 'after')
TARGETS = dict(original=(19, 24), fewest=(17, 26))
roster = access.roster
inputs = budget.inputs


def arguments(call):
    return ['--foliage-panel', fallback.SEED, 'condition', call['policy'], call['mode']]


def energy_total(rows):
    result = {k: rows[0]['energy'][k] if k == 'before' else rows[-1]['energy'][k] if k == 'after'
              else sum(r['energy'][k] for r in rows) for k in ENERGY}
    return result | dict(repair=sum(r['renewal_energy'] for r in rows), endowment=0, discarded=0)


def summary(rows):
    bands = Counter(f[5] // 64 for r in rows for f in r['leaves'])
    potential = sum(b * n for b, n in bands.items())
    weighted = sum((f[5] // 64) * f[6] for r in rows for f in r['leaves'])
    leaves = sum(len(r['leaves']) for r in rows)
    return dict(first_tick=rows[0]['tick'], last_tick=rows[-1]['tick'], steps=len(rows),
        leaf_samples=leaves, light_band_counts={str(b): bands[b] for b in range(4)},
        healthy_at_recorded_light=potential, condition_weighted_numerator=weighted,
        weighted_condition_fraction=weighted / (255 * potential) if potential else None,
        mean_condition_fraction=sum(f[6] for r in rows for f in r['leaves']) / (255 * leaves),
        mean_light_band=potential / leaves, energy=energy_total(rows),
        remainder_before=rows[0]['remainder_before'], remainder_after=rows[-1]['remainder_after'],
        condition_before=rows[0]['condition_before'], condition_after=rows[-1]['condition_after'],
        renewals=sum(r['renewals'] for r in rows))


def validate_trace(data, reproduction, resources, policy):
    lineage, leaf_count = TARGETS[policy]
    score.require(data['schema'] == 'garden-foliage-uptake-v1' and data['complete'] is True and
                  (data['lineage'], data['first_tick_exclusive'], data['end_tick'], data['leaf_limit']) ==
                  (lineage, FIRST, END, 32) and data['leaf_fields'] == FIELDS, 'foliage identity differs')
    rows = data['rows']
    score.require([r['tick'] for r in rows] == TICKS, 'foliage coverage differs')
    observed = {r['tick']: v for r in reproduction['openings'] for v in r['visits']
                if v['lineage'] == lineage and FIRST < r['tick'] <= END}
    prior, after_conditions, positions, joined = None, None, None, []
    for r in rows:
        leaves = r['leaves']
        score.require(len(leaves) == leaf_count and all(len(f) == 7 and
                      all(score.integer(v, 0, 255) for v in f) for f in leaves), 'invalid leaf fields')
        nodes = [f[0] for f in leaves]
        score.require(nodes == sorted(set(nodes)) and r['selected'] in nodes and
                      all(f[3] == max(0, min(27, (f[1] - 8) // 8)) and
                          f[4] == max(0, min(13, (f[2] - 32) // 8)) for f in leaves),
                      'leaf coordinates or selection differ')
        current_positions = [f[1:3] for f in leaves]
        score.require(positions is None or positions == current_positions, 'leaf body changed')
        positions = current_positions
        score.require(score.integer(r['phase'], 0, 255) and r['phase'] == (r['tick'] // 15 + 64) % 256 and
                      score.integer(r['strength'], 0, 255) and score.integer(r['action'], 0, 1) and
                      all(score.integer(r[k], 0, 65535) for k in ('condition_before', 'condition_after',
                          'worn', 'restored', 'renewals', 'renewal_energy', 'renewal_water')),
                      'invalid foliage metadata')
        maintenance = r['tick'] % 60 == 0
        conditions = [f[6] for f in leaves]
        selected = nodes.index(r['selected'])
        score.require(r['renewals'] <= r['action'] and
                      r['restored'] == (255 - conditions[selected]) * r['renewals'] and
                      r['renewal_energy'] == 9 * r['renewals'] and r['renewal_water'] == 5 * r['renewals'] and
                      sum(conditions) + r['worn'] == r['condition_before'] and
                      sum(conditions) + r['restored'] == r['condition_after'] and
                      (maintenance or r['worn'] == 0), 'leaf condition conservation differs')
        if after_conditions is not None:
            expected = [max(0, c - int(maintenance)) for c in after_conditions]
            score.require(conditions == expected and
                          r['worn'] == (sum(c > 0 for c in after_conditions) if maintenance else 0),
                          'per-leaf wear continuity differs')
        after_conditions = conditions.copy()
        if r['renewals']:
            after_conditions[selected] = 255
        score.require(all(score.integer(r[k], 0, 254) for k in
                          ('remainder_before', 'remainder_uptake', 'remainder_after')) and
                      r['remainder_uptake'] == r['remainder_after'], 'fractional stages differ')
        numerator = r['remainder_before'] + sum((f[5] // 64) * f[6] for f in leaves)
        f = r['energy']
        score.require(all(score.integer(f[k], 0, 65535) for k in ENERGY) and len(f['points']) == 6 and
                      all(score.integer(p, 0, 256) for p in f['points']), 'invalid energy fields')
        score.require(divmod(numerator, 255) == (f['income'], r['remainder_uptake']),
                      'exact light-condition income differs')
        before, uptake, paid, germination, growth, reproduction_point = f['points']
        score.require(before == f['before'] and uptake == min(256, before + f['income']) and
                      f['overflow'] == before + f['income'] - uptake and
                      f['upkeep_due'] == (4 if maintenance else 0) and
                      f['upkeep_paid'] == min(uptake, f['upkeep_due']) and paid == uptake - f['upkeep_paid'] and
                      germination == paid and f['growth'] == 0 and
                      growth == germination - r['renewal_energy'] and
                      reproduction_point == growth - f['seeds'] == f['after'] and
                      f['seeds'] in (0, 48), 'energy payment stages differ')
        if prior is not None:
            score.require(f['before'] == prior['energy']['after'] and
                          r['condition_before'] == prior['condition_after'] and
                          r['remainder_before'] == prior['remainder_after'], 'foliage continuity differs')
        if r['tick'] in observed:
            v = observed[r['tick']]
            score.require(growth == v['energy'] and f['seeds'] == 48 * int(v['produced']) and
                          bool(v['blockers'] & 128) == (growth < v['energy_required']), 'opening receipt differs')
            joined.append(dict(tick=r['tick'], visit=v, energy=f))
        else:
            score.require(f['seeds'] == 0, 'unreceipted purchase')
        prior = r
    day, = [r for r in resources['plant_days'] if r['lineage'] == lineage and r['day'] == 152]
    score.require(energy_total(rows) == day['energy'] and
                  day['nodes_before'] == day['nodes_after'] == 32 and
                  day['leaves_before'] == day['leaves_after'] == leaf_count and
                  day['condition_endowment'] == 0 and day['samples'] == day['observations'] == 256 and
                  all(sum(r[k] for r in rows) == day[k] for k in ('renewals', 'worn', 'restored')) and
                  rows[0]['condition_before'] == day['condition_before'] and
                  rows[-1]['condition_after'] == day['condition_after'], 'daily ledger differs')
    return dict(lineage=lineage, leaves=leaf_count, day=summary(rows),
                dawn=summary([r for r in rows if DAWN < r['tick'] <= OPENING]), openings=joined)


def validate_outputs(out, baseline, models, size, *, extra_names=()):
    analyses, traces = {}, {}
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
            projected = fallback.gate_record(value) if call['policy'] == 'fewest' else value
            fallback.gates.underlying(projected, 'condition', models, size,
                                      day * score.DAY, seed=fallback.SEED, after_tick=0)
            score.require(encoded == prepare.blob(baseline, old + '/timeline/' + name + '.json') and
                          raw == prepare.blob(baseline, old + '/timeline/' + name + '.raw') and
                          len(raw) == 115200 and value['framebuffer_crc32'] == f'{zlib.crc32(raw):08x}',
                          'baseline checkpoint differs')
            score.require(score.history_prefix(final, day * score.DAY) == score.history_prefix(value, day * score.DAY),
                          'history prefix differs')
            if call['mode'] == 'on':
                other = out / 'runs' / (call['id'][:-2] + 'off') / 'timeline' / name
                score.require(encoded == other.with_suffix('.json').read_bytes() and
                              raw == other.with_suffix('.raw').read_bytes(), 'logging changed checkpoint')
        score.require(final == value, 'stdout differs from endpoint')
        if call['mode'] == 'on':
            old_traces = {}
            for name in ('trace.json', 'purchases.json', 'reproduction.json'):
                raw = (folder / 'timeline' / name).read_bytes()
                score.require(raw == prepare.blob(baseline, old + '/timeline/' + name), 'baseline diagnostic differs')
                old_traces[name] = json.loads(raw)
            data = json.loads((folder / 'timeline/foliage.json').read_bytes())
            traces[call['policy']] = data
            analyses[call['policy']] = validate_trace(data, old_traces['reproduction.json'],
                                                     old_traces['trace.json'], call['policy'])
            expected.update(('trace.json', 'purchases.json', 'reproduction.json', 'foliage.json'))
            expected.update(extra_names)
        score.require({p.name for p in (folder / 'timeline').iterdir()} == expected, 'output roster differs')
    score.require([(r['tick'], r['phase'], r['strength']) for r in traces['original']['rows']] ==
                  [(r['tick'], r['phase'], r['strength']) for r in traces['fewest']['rows']], 'matched sunlight differs')
    return analyses


EXPERIMENT = follow.Experiment('garden-population-foliage-collection-v1', ARCHIVE_SCHEMA,
                              BASELINE_SHA, PROTOCOL, inputs, arguments, validate_outputs, roster)


if __name__ == '__main__':
    follow.main(__doc__, experiment=EXPERIMENT)
