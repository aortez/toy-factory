#!/usr/bin/env python3
"""Offline diagnosis of the cursor comparison's extra adult death; never replay."""

import argparse
import gzip
import json
from pathlib import Path

import garden_landing_seed_cursor as capture
from garden_resources import require

ROOT, BASE, STOP, STEP, DAY = capture.ROOT, capture.BASE, capture.STOP, capture.STEP, capture.DAY
INPUT = 'benchmarks/garden-seasons/landing-seed-cursor-results.json.gz'
INPUT_SHA = 'cf6ba820eee40259fcaededb7188708517a8b282541ac78ff4b292f68d43af8a'
RULE = 'garden-landing-cursor-energy-v1'
CASE, FOCAL = '366928c6-rainfed', 37
ARMS, KINDS = ('fixed', 'cursor'), ('stand', 'adult')
window = capture.window


def load_input():
    # This exact capture already passed complete panel/repeat verification.
    # Historical C source identities belong to that build, not the working tree.
    require(capture.sweep.digest(ROOT / INPUT) == INPUT_SHA, 'cursor capture changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream:
        return json.load(stream)


def selected(value, arm):
    return value['runs'][arm][CASE]


def focal_life(value, arm):
    return next(p for p in selected(value, arm)['result']['lineages'] if p['id'] == FOCAL)


def extract(bundle, value, arm):
    run = selected(value, arm)
    receipts, streams = {k: {} for k in KINDS}, {}
    for kind in KINDS:
        meta = run['traces'][kind]
        path = bundle / meta['path']
        require(capture.sweep.digest(path) == meta['sha256'], 'compressed trace changed')
        streams[kind] = capture.scan(path, kind, run['result'], receipts[kind])
    rows, changes, old_shape = [], [], None
    try:
        for stand, adult in zip(*streams.values(), strict=True):
            tick = adult['tick']
            climate, phase, strength = window.previous.sun_at(int(run['result']['seed'], 16), tick)
            require(stand['tick'] == tick and stand['climate'] == climate and
                    adult['sun'] == [phase, strength] and adult['cold'] == climate['cold'] and
                    adult['season'] == climate['day'] // 4, 'observer climate/clock differs')
            plants = {p['id']: p for p in adult['plants']}
            shape = [[b['id'], b['nodes'], b['roots'], plants[b['id']]['active_leaves']]
                     for b in stand['bodies']]
            if shape != old_shape:
                changes.append([tick, shape])
                old_shape = shape
            if FOCAL in plants:
                p = plants[FOCAL]
                require(p['birth'] == focal_life(value, arm)['birth_tick'], 'wrong adult birth')
                rows.append([tick, window.resources.pack(p)])
    finally:
        for stream in streams.values():
            stream.close()
    require(receipts == {k: run['receipts'][k] for k in KINDS}, 'restored trace changed')
    return dict(rows=rows, population_changes=changes)


def history(rows, life, expected):
    require([r[0] for r in rows] == list(range(BASE, (life['death_tick'] or STOP) + STEP, STEP)),
            'incomplete focal history')
    samples, before, roots = {}, None, None
    for tick, packed in rows:
        plant = window.resources.unpack(packed, life, tick)
        transfer = window.adults.transfers(plant, life, before)
        phase = (64 + tick // STEP) % 256
        payment = window.population.payment(plant, transfer, roots if roots is not None else plant['roots'],
                                            tick, phase)
        samples[tick] = dict(plant=plant, transfer=transfer, payment=payment)
        before, roots = plant['stages'][-1], plant['roots']
    require(budget_between(samples, BASE, life['death_tick'] or STOP) == expected['budget'],
            'full focal budget differs from original capture')
    shortfalls = [r['payment'] for t, r in samples.items() if t > BASE and r['payment'] and
                  any(r['payment'][resource]['unpaid'] for resource in ('energy', 'water'))]
    require(shortfalls == expected['shortfalls'], 'shortfall history differs from capture')
    return samples


def budget_between(samples, start, stop):
    """Open-left, closed-right interval; never silently compare unequal exposures."""
    ticks = list(range(start + STEP, stop + STEP, STEP))
    require(start < stop and start % STEP == stop % STEP == 0 and all(t in samples for t in ticks),
            'incomplete budget interval')
    total = window.adults.budget()
    for index, tick in enumerate(ticks):
        window.adults.accumulate(total, samples[tick]['transfer'], index == 0)
    return total


def event(samples, tick):
    climate, phase, strength = window.previous.sun_at(int(CASE[:8], 16), tick)
    return dict(tick=tick, day=tick / DAY, phase=phase, strength=strength,
                light_percent=climate['light_percent'],
                arms={a: dict(energy=samples[a][tick]['plant']['stages'][-1][0],
                             water=samples[a][tick]['plant']['stages'][-1][1],
                             stress=samples[a][tick]['plant']['stages'][-1][2],
                             income=samples[a][tick]['transfer']['energy']['income']) for a in ARMS})


def summarize(histories, value):
    samples = {a: history(histories[a]['rows'], focal_life(value, a),
                          selected(value, a)['audit']['plants'][str(FOCAL)]) for a in ARMS}
    end = focal_life(value, 'cursor')['death_tick']
    require(end is not None and focal_life(value, 'fixed')['death_tick'] is None, 'wrong paired death')
    first = next(t for t in samples['cursor'] if samples['cursor'][t]['transfer']['energy']['income'] !=
                 samples['fixed'][t]['transfer']['energy']['income'])
    purchases = [t for t, r in samples['cursor'].items() if t > BASE and r['transfer']['energy']['reproduction']]
    require(len(purchases) == 1, 'expected one focal seed purchase')
    bought = purchases[0]
    refilled = next(t for t, r in samples['cursor'].items() if t > bought and
                    r['plant']['stages'][0][0] == 256)
    last_full = max(t for t, r in samples['cursor'].items() if r['plant']['stages'][0][0] == 256)
    require(samples['fixed'][last_full]['plant']['stages'][-1] ==
            samples['cursor'][last_full]['plant']['stages'][-1], 'unmatched terminal-window starting state')
    final_day = end // DAY * DAY
    final_loss = next(t for t in samples['cursor'] if t > final_day and
                      samples['cursor'][t]['transfer']['energy']['income'] !=
                      samples['fixed'][t]['transfer']['energy']['income'])
    next_income = next(t for t, r in samples['fixed'].items() if t > end and r['transfer']['energy']['income'])
    daily = []
    for start in range(BASE, STOP, DAY):
        stop = min(start + DAY, end)
        if start >= stop:
            break
        daily.append(dict(start=start, stop=stop, complete_day=stop == start + DAY,
                          budgets={a: budget_between(samples[a], start, stop) for a in ARMS}))
    # Counts describe bodies, not positions or individual ray occluders.
    for arm in ARMS:
        changes = histories[arm]['population_changes']
        require(changes and changes[0][0] == BASE and all(BASE <= t <= STOP and t % STEP == 0
                for t, _ in changes) and all(a[0] < b[0] for a, b in zip(changes, changes[1:])),
                'invalid morphology timeline')
        for tick, shape in changes:
            require(len({s[0] for s in shape}) == len(shape), 'duplicate body')
            lives = selected(value, arm)['result']['lineages']
            require({s[0] for s in shape} == {p['id'] for p in lives if p['birth_tick'] <= tick and
                    (p['death_tick'] is None or p['death_tick'] > tick)}, 'body census differs')
            for i, nodes, roots, leaves in shape:
                require(0 <= roots <= nodes <= 32 and 0 <= leaves <= nodes - roots, 'invalid body')
                if i <= 38:
                    require((nodes, roots, leaves) == (32, 17 if i in (32, 38) else 16, 8),
                            'pre-existing living canopy counts changed')
    common = {a: budget_between(samples[a], BASE, end) for a in ARMS}
    critical = {a: budget_between(samples[a], last_full, end) for a in ARMS}
    return dict(common_end=end, common_budget=common, daily=daily,
                first_income_difference=event(samples, first),
                purchase=event(samples, bought), refill=event(samples, refilled),
                refill_steps=(refilled - bought) // STEP,
                last_full=event(samples, last_full), critical_budget=critical,
                final_day_first_loss=event(samples, final_loss), death=event(samples, end),
                fixed_next_income_tick=next_income,
                shortfalls=selected(value, 'cursor')['audit']['plants'][str(FOCAL)]['shortfalls'],
                preexisting_growth_energy={a: {str(p['id']): selected(value, a)['audit']['plants'][str(p['id'])]
                    ['budget']['energy']['growth'] for p in selected(value, a)['result']['lineages']
                    if p['birth_tick'] <= BASE and (p['death_tick'] is None or p['death_tick'] > BASE)} for a in ARMS},
                new_neighbors={a: [p for p in selected(value, a)['result']['lineages']
                                   if BASE < p['birth_tick'] <= end] for a in ARMS})


def make_value(histories, value):
    return dict(rule=RULE, input_sha256=INPUT_SHA, case=CASE, focal=FOCAL,
                native_runs=0, training_runs=0,
                traces={a: {k: selected(value, a)['traces'][k] for k in KINDS} for a in ARMS},
                histories=histories, analysis=summarize(histories, value))


def check_value(saved):
    require(saved == make_value(saved['histories'], load_input()), 'energy diagnosis differs')


def verify_bundle(bundle, saved):
    value = load_input()
    require(saved == make_value({a: extract(bundle, value, a) for a in ARMS}, value),
            'raw traces do not reproduce diagnosis')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--out', type=Path)
    mode.add_argument('--verify', type=Path)
    parser.add_argument('--bundle', type=Path)
    args = parser.parse_args()
    if args.verify:
        with gzip.open(args.verify, 'rt') as stream:
            saved = json.load(stream)
        check_value(saved)
        if args.bundle:
            verify_bundle(args.bundle, saved)
    else:
        require(args.bundle is not None, '--out needs the saved --bundle; no simulator will run')
        value = load_input()
        saved = make_value({a: extract(args.bundle, value, a) for a in ARMS}, value)
        capture.sweep.write_gzip(args.out, saved)
    print(json.dumps({k: saved['analysis'][k] for k in
                      ('common_end', 'first_income_difference', 'refill_steps', 'critical_budget')}, indent=2))


if __name__ == '__main__':
    main()
