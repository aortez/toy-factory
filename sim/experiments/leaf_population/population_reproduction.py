#!/usr/bin/env python3
"""Four fixed read-only replays of ordered access to seed-bank openings."""

from collections import Counter
import json
import zlib

import population_fallback as fallback
import population_fallback_loss as loss

collect, prepare, score, follow = fallback.collect, fallback.prepare, fallback.score, fallback.follow
BASELINE, BASELINE_SHA = loss.ARCHIVE, loss.ARCHIVE_SHA
PROTOCOL = collect.ROOT / 'benchmarks/garden-seasons/leaf-population-reproduction-protocol.md'
ARCHIVE_SCHEMA = 'garden-population-reproduction-evidence-v1'
FIRST, END, CADENCE = 128 * score.DAY, 232 * score.DAY, 60
SAMPLES = (END - FIRST) // CADENCE
BLOCKERS = ('cooldown', 'cadence', 'bank', 'dead', 'stress', 'light', 'generation', 'energy', 'water', 'flower')
BANK, DEAD = 4, 8


def roster():
    return [dict(id=f'{fallback.SEED}-condition-{policy}-{mode}', policy=policy, mode=mode)
            for policy in ('original', 'fewest') for mode in ('off', 'on')]


def arguments(call):
    return ['--reproduction-panel', fallback.SEED, 'condition', call['policy'], call['mode']]


def inputs():
    baseline = fallback.purchase.early.archive(BASELINE, BASELINE_SHA, fallback.ARCHIVE_SCHEMA)
    _, models, size = collect.archive_inputs()
    return baseline, models, size


def occupancy(final, tick):
    # Seeds expire or germinate before reproduction; same-tick new purchases
    # have not happened yet. This is not end-of-tick occupancy.
    return sum(s['birth_tick'] < tick and (s['end_tick'] is None or s['end_tick'] > tick)
               for s in final['seeds'])


def masks_summary(masks):
    return dict(visits=sum(masks.values()), produced=masks.get('0', 0),
                bank_only=masks.get(str(BANK), 0),
                blockers={name: sum(v for k, v in masks.items() if int(k) & (1 << i))
                          for i, name in enumerate(BLOCKERS)})


def validate_trace(data, final):
    score.require(data['schema'] == 'garden-reproduction-access-v1' and data['complete'] is True and
                  (data['first_tick_exclusive'], data['end_tick'], data['cadence'], data['samples'],
                   data['seed_capacity'], data['lineage_limit'], data['opening_limit']) ==
                  (FIRST, END, CADENCE, SAMPLES, 8, 128, 512), 'reproduction identity/coverage differs')
    plants = {p['id']: p for p in final['lineages']}
    cadence = range(FIRST + CADENCE, END + 1, CADENCE)
    rows = data['lineages']
    score.require(0 < len(rows) <= 128 and len({r['lineage'] for r in rows}) == len(rows),
                  'duplicate or excessive lineage counters')
    histograms, summaries = {}, {}
    for row in rows:
        lineage, masks = row['lineage'], row['masks']
        score.require(lineage in plants and bool(masks) and
                      all(str(int(k)) == k and score.integer(int(k), 0, 1023) and not int(k) & 2 and
                          score.integer(v, 1, SAMPLES) for k, v in masks.items()), 'invalid reproduction histogram')
        p = plants[lineage]
        alive = sum(p['birth_tick'] <= t and (p['death_tick'] is None or p['death_tick'] > t) for t in cadence)
        score.require(sum(v for k, v in masks.items() if not int(k) & DEAD) == alive and
                      sum(masks.values()) <= SAMPLES, 'living visit coverage differs')
        histograms[lineage] = masks
        summaries[str(lineage)] = dict(founder=final['family_roots'][lineage - 1],
                                       **masks_summary(masks), opening_visits=0, sees_open=0,
                                       bank_only_after_earlier_purchase=0, opening_masks={})
    expected_living = {p['id'] for p in plants.values() if any(
        p['birth_tick'] <= t and (p['death_tick'] is None or p['death_tick'] > t) for t in cadence)}
    score.require(expected_living <= histograms.keys(), 'missing living lineage')
    expected_openings = {t for t in cadence if occupancy(final, t) < 8}
    receipts = data['openings']
    ticks = [r['tick'] for r in receipts]
    score.require(len(ticks) <= 512 and ticks == sorted(expected_openings), 'opening coverage/order differs')
    actual_buys, observed = Counter(), {lineage: Counter() for lineage in histograms}
    losses = []
    generations = {}
    for p in final['lineages']:
        generations[p['id']] = 0 if not p['parent'] else generations[p['parent']] + 1
    for receipt in receipts:
        tick, visits = receipt['tick'], receipt['visits']
        score.require(0 < len(visits) <= 8 and len({v['lineage'] for v in visits}) == len(visits),
                      'invalid ordered visit roster')
        alive = {p['id'] for p in plants.values() if p['birth_tick'] <= tick and
                 (p['death_tick'] is None or p['death_tick'] > tick)}
        score.require(alive <= {v['lineage'] for v in visits}, 'missing live opening visit')
        bank, winners = occupancy(final, tick), []
        for visit in visits:
            lineage = visit['lineage']
            score.require(lineage in histograms and visit['seed_count'] == bank, 'ordered occupancy differs')
            p = plants[lineage]
            score.require(p['birth_tick'] <= tick, 'visit before birth')
            for key in ('energy', 'water', 'energy_required', 'water_required', 'immature_flowers',
                        'spent_flowers', 'ready_flowers', 'flower_index'):
                score.require(score.integer(visit[key], 0, 65535), 'invalid receipt resource/flower value')
            for key in ('cooldown', 'stress', 'sun_strength'):
                score.require(score.integer(visit[key], 0, 255), 'invalid receipt small value')
            flower = visit['flower_index'] == 65535
            score.require(flower == (visit['ready_flowers'] == 0) and
                          (flower or visit['flower_index'] < 256) and
                          sum(visit[k] for k in ('immature_flowers', 'spent_flowers', 'ready_flowers')) <= 256,
                          'flower receipt differs')
            checks = (visit['cooldown'] != 0, False, bank >= 8,
                      p['death_tick'] is not None and p['death_tick'] <= tick,
                      visit['stress'] != 0, visit['sun_strength'] <= 24,
                      generations[lineage] == 65535, visit['energy'] < visit['energy_required'],
                      visit['water'] < visit['water_required'], flower)
            mask = sum(1 << i for i, blocked in enumerate(checks) if blocked)
            score.require(visit['blockers'] == mask and visit['produced'] is (mask == 0),
                          'receipt eligibility differs')
            observed[lineage][str(mask)] += 1
            summary = summaries[str(lineage)]
            summary['opening_visits'] += 1
            summary['sees_open'] += bank < 8
            if mask == BANK:
                score.require(bool(winners), 'bank-only loss without earlier purchase')
                summary['bank_only_after_earlier_purchase'] += 1
                losses.append(dict(tick=tick, lineage=lineage, earlier_buyers=winners.copy()))
            if visit['produced']:
                actual_buys[tick, lineage] += 1
                winners.append(lineage)
                bank += 1
        end_bank = sum(s['birth_tick'] <= tick and (s['end_tick'] is None or s['end_tick'] > tick)
                       for s in final['seeds'])
        score.require(bank == end_bank, 'end-of-reproduction inventory differs')
    expected_buys = Counter((s['birth_tick'], s['parent']) for s in final['seeds'] if FIRST < s['birth_tick'] <= END)
    score.require(actual_buys == expected_buys, 'purchase receipts differ from seed ledger')
    for lineage, masks in histograms.items():
        opened = observed[lineage]
        score.require(all(v <= masks.get(k, 0) for k, v in opened.items()) and
                      all(int(k) & BANK or v == opened.get(k, 0) for k, v in masks.items()) and
                      masks.get('0', 0) == sum(v for (t, p), v in expected_buys.items() if p == lineage),
                      'opening histogram differs from totals')
        summaries[str(lineage)]['opening_masks'] = dict(opened)
    families = {}
    for founder in (1, 2, 3):
        selected = [s for s in summaries.values() if s['founder'] == founder]
        families[str(founder)] = {key: sum(s[key] for s in selected) for key in
            ('visits', 'produced', 'bank_only', 'opening_visits', 'sees_open', 'bank_only_after_earlier_purchase')}
    return dict(opening_ticks=len(ticks), samples=SAMPLES, families=families, lineages=summaries,
                bank_only_losses=losses)


def validate_outputs(out, baseline, models, size):
    analyses = {}
    for call in roster():
        folder = out / 'runs' / call['id']
        old = 'runs/' + call['id']
        final_bytes = (folder / 'stdout.json').read_bytes()
        score.require(final_bytes == prepare.blob(baseline, old + '/stdout.json'), 'baseline final differs')
        final = json.loads(final_bytes)
        expected = {f'tick-{d * score.DAY:010d}.{ext}' for d in follow.DAYS for ext in ('raw', 'json')}
        for day in follow.DAYS:
            name = f'tick-{day * score.DAY:010d}'
            path = folder / 'timeline' / name
            encoded, raw = path.with_suffix('.json').read_bytes(), path.with_suffix('.raw').read_bytes()
            value = json.loads(encoded)
            projected = fallback.gate_record(value) if call['policy'] == 'fewest' else value
            fallback.gates.underlying(projected, 'condition', models, size, day * score.DAY,
                                      seed=fallback.SEED, after_tick=0)
            score.require(len(raw) == 115200 and value['framebuffer_crc32'] == f'{zlib.crc32(raw):08x}' and
                          encoded == prepare.blob(baseline, old + '/timeline/' + name + '.json') and
                          raw == prepare.blob(baseline, old + '/timeline/' + name + '.raw'), 'baseline checkpoint differs')
            score.require(score.history_prefix(final, day * score.DAY) == score.history_prefix(value, day * score.DAY),
                          'history prefix differs')
            if call['mode'] == 'on':
                other = out / 'runs' / (call['id'][:-2] + 'off') / 'timeline' / name
                score.require(encoded == other.with_suffix('.json').read_bytes() and
                              raw == other.with_suffix('.raw').read_bytes(), 'logging changed checkpoint')
        score.require(final == value, 'stdout differs from endpoint')
        if call['mode'] == 'on':
            expected.update(('trace.json', 'purchases.json', 'reproduction.json'))
            for name in ('trace.json', 'purchases.json'):
                score.require((folder / 'timeline' / name).read_bytes() ==
                              prepare.blob(baseline, old + '/timeline/' + name), 'baseline trace differs')
            analyses[call['policy']] = validate_trace(json.loads((folder / 'timeline/reproduction.json').read_bytes()), final)
        score.require({p.name for p in (folder / 'timeline').iterdir()} == expected, 'output roster differs')
    return analyses


EXPERIMENT = follow.Experiment('garden-population-reproduction-collection-v1', ARCHIVE_SCHEMA,
                              BASELINE_SHA, PROTOCOL, inputs, arguments, validate_outputs, roster)


if __name__ == '__main__':
    follow.main(__doc__, experiment=EXPERIMENT)
