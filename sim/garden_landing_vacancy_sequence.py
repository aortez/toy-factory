#!/usr/bin/env python3
"""Offline death, reclamation and replacement sequences in the saved 32-world panel."""

from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import Counter
from functools import cache
import gzip
import json
from pathlib import Path
import sys

import garden_landing_late_dispersal as late
from garden_experiments import digest
from garden_landing_energy_audit import archived_sources
from garden_landing_founders import write_gzip
from garden_landing_root_allocation_audit import fingerprint
from garden_landing_soil_audit import mix32, weather
from garden_resources import require

ROOT, STEP, STOP, START, DAY = late.ROOT, late.STEP, late.STOP, late.AFTER, late.DAY
RULE = 'garden-landing-vacancy-sequence-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-vacancy-sequence-protocol.md'
PROTOCOL_SHA = 'bd0eecb124ebeeca6150625eebc4711b04af5afd2da45f4ebc49977b16ef9b29'
INPUT = 'benchmarks/garden-seasons/landing-late-dispersal-results.json.gz'
INPUTS = {INPUT: '390669aba064732072c82e2170ad1d6f7872612710bc1c6501ad3351c8ad3b62',
          'benchmarks/garden-seasons/landing-placement-information-results.json.gz':
          'e856950a8dc4d7dfb2d6b8871d306a8cebe60e159d55da00d52c814516951c48'}
MANIFEST_SHA = '4a94df9dcc4f53c980e3631b58dc3fd853c3f03a68678d335127ab09f7a83001'
IMPLEMENTATION = {
    'src/garden_world.c': 'a5e54ce7636bbd3e7c1e2fc148264ded8ae29136078f37dac412090e7edfbfc8',
    'src/garden_world.h': 'ab0ce75d4fe2e0e919ccea3124e84df475b99ed6e7cd2e308c3410869e780a23',
    'src/garden_climate.c': '523517697ca44a1da9bb372b2353736433ec139867858047bde2d4fd19834bb6',
    'src/garden_climate.h': 'faf6608fa9e245b2cfe4e6003b91fe636fbaff15432245308ef0ffac4e87beb1',
    'sim/garden_landing_plant_trace.c': 'aaf0c371d99a5c3be2216468020a4a5eb103e28338a9f5c2bd7e5f41ad27cdbe',
    'sim/garden_landing_reach.c': 'e9b2306adf4642a5020a283b3d9fbcad4bb3d8aa32738fc2c4cbad6d44e2cd66',
}
SOURCES = ('sim/garden_landing_vacancy_sequence.py', 'sim/garden_landing_late_dispersal.py',
           'sim/garden_landing_population.py', 'sim/garden_landing_reach.py',
           'sim/garden_landing_soil_audit.py', 'sim/garden_landing_founders.py',
           'sim/garden_landing_energy_audit.py', 'sim/garden_landing_root_allocation_audit.py',
           'sim/garden_experiments.py', 'sim/garden_resources.py')
SEASONS = ('spring', 'summer', 'autumn', 'winter')
BLOCKERS = ('dormant', 'moisture', 'light', 'plant_capacity', 'node_capacity', 'spacing', 'cold')
KINDS = ('stand', 'reach')
ALL_COLUMNS = (1 << 28) - 1


def provenance():
    require(digest(ROOT / PROTOCOL) == PROTOCOL_SHA and
            all(digest(ROOT / p) == sha for p, sha in INPUTS.items()), 'vacancy inputs/protocol changed')
    return dict(rule=RULE, protocol_sha256=PROTOCOL_SHA, inputs=INPUTS, implementation=IMPLEMENTATION,
                raw_manifest_sha256=MANIFEST_SHA, native_runs=0, training_runs=0,
                interval=[START, STOP], primary_worlds=32)


@cache
def source():
    provenance()
    with gzip.open(ROOT / INPUT, 'rt') as stream: value = json.load(stream)
    capture = value['capture']
    require(value['raw_manifest_sha256'] == MANIFEST_SHA and capture['rule'] == late.RULE and
            capture['full_replays'] == 48 and capture['training_runs'] == 0 and
            all(capture['source_sha256'].get(p) == sha for p, sha in IMPLEMENTATION.items()),
            'wrong captured implementation/panel')
    panel = {}
    for pair in value['pairs']:
        for arm in late.ARMS:
            key = late.name(pair, arm)
            run = capture['runs'][key]
            old = pair['arms'][arm]
            require(run['result'] == old['result'] and run['result']['tick'] == STOP and
                    run['result']['seed'] == 'f7ee4528' and run['result']['ledger_start_tick'] == 0 and
                    not run['result']['gardener'] and not run['result']['irrigation'], 'wrong world scope')
            late.check_settings(capture['builds'][arm]['settings'], arm)
            panel[key] = dict(arm=arm, order=pair['case']['world']['order'], guard=pair['case']['guard'],
                              allocator=pair['allocator'], run=run, reach=old['reach'])
    require(len(panel) == 32 and {tuple(w[k] for k in ('arm', 'order', 'guard', 'allocator'))
            for w in panel.values()} == {(a, o, g, r) for a in late.ARMS for o in ('fixed', 'rotating')
            for g in ('control', 'candidate') for r in ('control', 'candidate')}, 'incomplete primary panel')
    return capture, panel


@cache
def climate(seed, tick):
    require(type(tick) is int and tick >= 0 and tick % STEP == 0, 'invalid climate tick')
    ecology = tick // STEP
    w = weather(seed, ecology)
    phase, year = ecology % 4096, ecology // 4096
    light = 100
    if phase >= 2560:
        ramp = phase - 2560 if phase <= 3584 else 2 * (4096 - phase)
        minimum = 38 + mix32(seed ^ (year * 0x9e3779b9) ^ 0x77696e31) % 21
        light -= (100 - minimum) * ramp // 1024
    return dict(version=1, mode='seasonal', year=year, day=w['day'], season=SEASONS[w['day'] // 4],
                light_percent=light, drought=w['drought'], cold=light < 65)


def bits(columns):
    return sum(1 << c for c in set(columns))


def clear(slots, lives):
    require(len(slots) == len(set(slots)) <= 8 and all(i in lives for i in slots), 'invalid slot census')
    return bits(c for c, m in enumerate(late.spacing_map(tuple(lives[i]['column'] for i in slots))) if not m)


def append_span(spans, tick, values):
    if spans and spans[-1][1] + STEP == tick and spans[-1][2] == values:
        spans[-1][1] = tick
    else:
        spans.append([tick, tick, values])


def expand(spans, start=START, stop=STOP):
    expected, previous = start + STEP, None
    for row in spans:
        require(type(row) is list and len(row) == 3, 'invalid observation span')
        first, last, values = row
        require(type(first) is int and type(last) is int and first == expected and
                first <= last <= stop and last % STEP == 0 and type(values) is list and
                values != previous, 'incomplete/redundant observation spans')
        for tick in range(first, last + STEP, STEP): yield tick, values
        expected, previous = last + STEP, values
    require(expected == stop + STEP, 'incomplete observation horizon')


def slot_history(result, states):
    """Validate complete identity transitions; death is not reclamation."""
    lives = {p['id']: p for p in result['lineages']}
    require(len(lives) == len(result['lineages']) and states and states[0][0] == STEP,
            'invalid slot history/ledger')
    prior = sorted(i for i, p in lives.items() if p['birth_tick'] == 0)
    seen, removed, releases, last_tick = set(prior), {}, [], 0
    for tick, slots in states:
        require(type(tick) is int and last_tick < tick <= STOP and tick % STEP == 0 and
                type(slots) is list, 'invalid slot transition clock')
        clear(slots, lives)
        born = {i for i, p in lives.items() if p['birth_tick'] == tick}
        lost, added = set(prior) - set(slots), set(slots) - set(prior)
        living = {i for i, p in lives.items() if p['birth_tick'] <= tick and
                  (p['death_tick'] is None or p['death_tick'] > tick)}
        require(added == born and not added & seen and living <= set(slots) and
                all(lives[i]['birth_tick'] <= tick for i in slots), 'slot birth/live inventory differs')
        before_checks = [i for i in slots if i not in born]
        require(before_checks == [i for i in prior if i not in lost] and
                all(lives[i]['death_tick'] is not None and lives[i]['death_tick'] < tick for i in lost),
                'slot disappearance before death or compaction order changed')
        if lost:
            require(not lost & set(removed), 'repeated reclamation')
            removed.update({i: tick for i in lost})
            releases.append(dict(tick=tick, ids=sorted(lost), before=prior, before_checks=before_checks,
                                 gained=clear(before_checks, lives) & ~clear(prior, lives)))
        seen |= added
        prior, last_tick = slots, tick
    require(seen == set(lives) and len(prior) == result['plant_slots'] and
            len(lives) - len(removed) == len(prior), 'incomplete slot history')
    return lives, removed, releases


def check_bundle(bundle, capture):
    require(digest(bundle / 'manifest.json') == MANIFEST_SHA, 'wrong raw manifest')
    manifest = json.loads((bundle / 'manifest.json').read_text())['artifacts']
    require(digest(bundle / 'capture.json') == manifest['capture.json'] and
            json.loads((bundle / 'capture.json').read_text()) == capture and
            digest(bundle / 'source.tar.gz') == manifest['source.tar.gz'] and
            archived_sources(bundle / 'source.tar.gz') == capture['source_sha256'], 'raw source archive differs')
    return manifest


def extract_world(bundle, manifest, world):
    run, wide = world['run'], world['arm'] in late.CANDIDATES
    result = run['result']
    ledger = {(s['parent'], s['birth_tick']): (n, s) for n, s in enumerate(result['seeds'])}
    lives = {p['id']: p for p in result['lineages']}
    require(len(ledger) == len(result['seeds']), 'duplicate seeds')
    newborn = {}
    for p in lives.values(): newborn.setdefault(p['birth_tick'], set()).add(p['id'])
    paths = {}
    for kind in KINDS:
        item = run['traces'][kind]
        path = (bundle / item['path']).resolve()
        require(path.is_relative_to(bundle.resolve()) and
                manifest.get(item['path']) == digest(path) == item['sha256'], 'raw trace changed/escaped')
        paths[kind] = path
    records, active, states, observations = {}, set(), [], []
    readers = (late.population.trace_rows(paths['stand'], 'stand', result), late.reach_rows(paths['reach']))
    try:
        for stand, reach in zip(*readers, strict=True):
            tick = stand['tick']
            require(tick == reach['tick'] and stand['climate'] == climate(int(result['seed'], 16), tick),
                    'trace climate/clock differs')
            slots = stand['plant_order']
            clear(slots, lives)
            require({p['id'] for p in stand['bodies']} == {i for i, p in lives.items()
                    if p['birth_tick'] <= tick and (p['death_tick'] is None or p['death_tick'] > tick)},
                    'live body ledger differs')
            if not states or states[-1][1] != slots: states.append([tick, slots])
            current = [i for i in slots if i not in newborn.get(tick, set())]
            seen, ended, packed = set(), set(), []
            for row in reach['checks']:
                require(len(row) == 7 and all(type(x) is int for x in row[:6]), 'invalid reach check')
                parent, age, column, mask, outcome, child, encoded = row
                key = parent, tick - age * STEP
                require(key in active and key not in seen, 'unknown/duplicate seed check')
                seen.add(key)
                index, seed = ledger[key]
                record = records[key]
                expected = 0 if tick != seed['end_tick'] else {'expired': 1, 'germinated': 2}[seed['outcome']]
                require(age == record['samples'] + 1 and column == seed['column'] and
                        outcome == expected and child == (seed['child_id'] if outcome == 2 else 0),
                        'seed age/fate differs')
                record['samples'] += 1
                if outcome: ended.add(key)
                if outcome == 1:
                    require(encoded is None and mask == 0 and age == seed['lifetime_ecology_ticks'],
                            'invalid expiry record')
                    packed.append([index, -1, 0])
                    continue
                sites, spacing, _ = late.decode_map(encoded)
                require((mask & ~1) == sites[column] and bool(mask & 1) == (age < 8) and
                        ((mask == 0) == (outcome == 2)) and
                        spacing == late.spacing_map(tuple(lives[i]['column'] for i in current)),
                        'sequential check gates/spacing differ')
                if age >= 8:
                    for period, start in late.PERIODS.items():
                        if tick > start: record['mature_sites'][period][encoded] += 1
                packed.append([index, mask, bits(c for c, m in enumerate(sites) if m == 0)])
                if outcome == 2: current.append(child)
            require(seen == active and current == slots, 'incomplete sequential seed inventory')
            active -= ended
            bought = set()
            for p in reach['purchases']:
                key = p['parent'], tick
                require(key in ledger and key not in records, 'unknown/duplicate purchase')
                late.purchase_check(p, slots, lives, ledger[key][1], wide)
                records[key] = dict(seed=list(key), purchase=p, slots=slots, samples=0,
                                    mature_sites={k: Counter() for k in late.PERIODS})
                bought.add(key)
            require(bought == {k for k in ledger if k[1] == tick}, 'purchase ledger differs')
            active |= bought
            if tick > START: append_span(observations, tick, packed)
    finally:
        for reader in readers: reader.close()
    for r in records.values(): r['mature_sites'] = {k: dict(v) for k, v in r['mature_sites'].items()}
    require([records[k] for k in ledger] == world['reach'], 'full reach inventory/histograms differ')
    require(all(digest(paths[k]) == run['traces'][k]['sha256'] for k in KINDS), 'trace changed during read')
    slot_history(result, states)
    return dict(states=states, observations=observations, full_checks=sum(r['samples'] for r in records.values()),
                full_purchases=len(records))


def new_counts():
    return dict(samples=0, full_stored=0, full_living=0, dead_stored=0, spacing_clear=0,
                spacing_and_slot=0, site_observed=0, global_open=0, reachable_mature_open=0,
                mature_checks=0, mature_blockers={b: 0 for b in BLOCKERS})


def analyze_world(world, rows):
    result = world['run']['result']
    lives, removed, releases = slot_history(result, rows['states'])
    require(rows['full_purchases'] == len(result['seeds']) and
            rows['full_checks'] == sum(r['samples'] for r in world['reach']), 'full inventory counts differ')
    times = [r[0] for r in rows['states']]
    def slots_at(tick): return rows['states'][bisect_right(times, tick) - 1][1]
    seeds = result['seeds']
    records = {tuple(r['seed']): r for r in world['reach']}
    supports = [bits(records[(s['parent'], s['birth_tick'])]['purchase']['choices']) for s in seeds]
    seed_births, plant_births = {}, {}
    for n, s in enumerate(seeds): seed_births.setdefault(s['birth_tick'], set()).add(n)
    for p in lives.values(): plant_births.setdefault(p['birth_tick'], set()).add(p['id'])
    active = {n for n, s in enumerate(seeds) if s['birth_tick'] <= START and (s['end_tick'] or STOP + STEP) > START}
    release_events = []
    for r in releases:
        if r['tick'] > START:
            release_events.append(r | {'columns': {str(c): dict(first_observed_open=None, first_reachable_mature=None,
                germinated=None, closed_tick=None, closed_by=None) for c in range(28) if r['gained'] & (1 << c)}})
    at_release = {r['tick']: r for r in release_events}
    pending_columns = {}
    periods = {k: new_counts() for k in late.PERIODS}
    strata = {}
    for tick, checks in expand(rows['observations']):
        post = slots_at(tick)
        newborn = plant_births.get(tick, set())
        slots = [i for i in post if i not in newborn]
        weather_now = climate(int(result['seed'], 16), tick)
        counts = new_counts()
        counts.update(samples=1, full_stored=int(len(slots) == 8),
                      full_living=int(sum(lives[i]['death_tick'] is None or lives[i]['death_tick'] > tick
                                          for i in slots) == 8),
                      dead_stored=int(any(lives[i]['death_tick'] is not None and lives[i]['death_tick'] <= tick
                                          for i in slots)), spacing_clear=int(bool(clear(slots, lives))),
                      spacing_and_slot=int(len(slots) < 8 and bool(clear(slots, lives))))
        if tick in at_release:
            for col, state in at_release[tick]['columns'].items():
                require(int(col) not in pending_columns, 'new release overlaps an unclosed vacancy')
                pending_columns[int(col)] = state
        seen, ended = set(), set()
        for item in checks:
            require(type(item) is list and len(item) == 3 and all(type(v) is int for v in item), 'invalid packed check')
            index, mask, opened = item
            require(index in active and index not in seen and 0 <= opened <= ALL_COLUMNS, 'unknown packed seed/open bits')
            seen.add(index)
            s = seeds[index]
            age = (tick - s['birth_tick']) // STEP
            outcome = s['outcome'] if s['end_tick'] == tick else 'pending'
            if outcome != 'pending': ended.add(index)
            if outcome == 'expired':
                require(mask == -1 and opened == 0 and age == s['lifetime_ecology_ticks'], 'invalid packed expiry')
                continue
            free = clear(slots, lives)
            require(0 <= mask < 128 and bool(mask & 1) == (age < 8) and
                    bool(mask & 8) == (len(slots) == 8) and bool(mask & 32) == (not free & (1 << s['column'])) and
                    bool(mask & 64) == weather_now['cold'] and not opened & ~free and
                    (not mask & (8 | 16 | 64) or opened == 0) and
                    bool(opened & (1 << s['column'])) == (mask & ~1 == 0) and
                    (mask == 0) == (outcome == 'germinated'), 'packed stage gates differ')
            counts['site_observed'] = 1
            counts['global_open'] |= int(bool(opened))
            if age >= 8:
                counts['mature_checks'] += 1
                counts['reachable_mature_open'] |= int(bool(opened & supports[index]))
                for n, b in enumerate(BLOCKERS): counts['mature_blockers'][b] += bool(mask & (1 << n))
            receipt = dict(tick=tick, seed_index=index, age=age, landing=s['column'], opened=opened)
            for c, state in pending_columns.items():
                if opened & (1 << c):
                    if state['first_observed_open'] is None: state['first_observed_open'] = receipt
                    if age >= 8 and supports[index] & (1 << c) and state['first_reachable_mature'] is None:
                        state['first_reachable_mature'] = receipt
                if outcome == 'germinated' and c == s['column']:
                    state['germinated'] = receipt | {'child': s['child_id']}
            if outcome == 'germinated':
                slots.append(s['child_id'])
                for c in list(pending_columns):
                    if abs(c - s['column']) < 3:
                        state = pending_columns.pop(c)
                        state.update(closed_tick=tick, closed_by=s['child_id'])
        require(seen == active and slots == post, 'packed bank/slot inventory differs')
        active -= ended
        active |= seed_births.get(tick, set())
        key = f"{weather_now['season']}/drought={int(weather_now['drought'])}/cold={int(weather_now['cold'])}"
        targets = [periods[k] for k, start in late.PERIODS.items() if tick > start]
        targets.append(strata.setdefault(key, new_counts()))
        for target in targets:
            for k, count in counts.items():
                if k == 'mature_blockers':
                    for b, n in count.items(): target[k][b] += n
                else: target[k] += count
    deaths = []
    for p in lives.values():
        died = p['death_tick']
        if died is not None and (died > START or removed.get(p['id'], STOP + STEP) > START):
            released = removed.get(p['id'])
            deaths.append(dict(id=p['id'], birth=p['birth_tick'], death=died, release=released,
                delay_ticks=None if released is None else released - died,
                climate=climate(int(result['seed'], 16), died), carried_dead=died <= START))
    replacements = sorted({v['germinated']['child'] for r in release_events for v in r['columns'].values()
                           if v['germinated'] is not None})
    for label, start in late.PERIODS.items():
        periods[label].update(deaths=sum(p['death_tick'] is not None and start < p['death_tick'] <= STOP
                                        for p in lives.values()),
            releases=sum(t > start for t in removed.values()),
            births=sum(p['birth_tick'] > start for p in lives.values()),
            purchases=sum(s['birth_tick'] > start for s in seeds))
    return dict(periods=periods, strata=strata, deaths=deaths, releases=release_events,
        replacements=[dict(life=lives[i], seed=next(s for s in seeds if s['child_id'] == i),
                           survival={str(d): late.population.survival(lives[i], STOP, d) for d in (1, 32)})
                      for i in replacements],
        initial_spacing_clear=[c for c in range(28) if clear(slots_at(START), lives) & (1 << c)])


def analyze(rows, panel):
    require(set(rows) == set(panel), 'incomplete vacancy panel')
    return {key: analyze_world(world, rows[key]) for key, world in panel.items()}


def check_value(value):
    require(value['provenance'] == provenance() and type(value['provenance']['native_runs']) is int and
            type(value['provenance']['training_runs']) is int, 'wrong vacancy provenance')
    _, panel = source()
    require(value['sources'] == {i: {k: w['run']['traces'][k] for k in KINDS} for i, w in panel.items()} and
            value['source_sha256'] == {p: digest(ROOT / p) for p in SOURCES}, 'vacancy sources differ')
    require(set(value['receipt_sha256']) == set(panel) and
            all(value['receipt_sha256'][k] == fingerprint(r) for k, r in value['rows'].items()), 'vacancy receipts differ')
    require(value['analysis'] == analyze(value['rows'], panel), 'vacancy analysis differs')


def export(bundle, out):
    require(not out.exists() and not out.is_symlink(), 'fresh vacancy output required')
    capture, panel = source()
    manifest = check_bundle(bundle, capture)
    rows, analysis = {}, {}
    for key, world in panel.items():
        rows[key] = extract_world(bundle, manifest, world)
        analysis[key] = analyze_world(world, rows[key])
        print(key + ': complete inventory and vacancy sequences reconciled', flush=True)
    value = dict(provenance=provenance(), sources={i: {k: w['run']['traces'][k] for k in KINDS} for i, w in panel.items()},
                 source_sha256={p: digest(ROOT / p) for p in SOURCES}, rows=rows,
                 receipt_sha256={k: fingerprint(r) for k, r in rows.items()}, analysis=analysis)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_gzip(out, value)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--out', type=Path)
    mode.add_argument('--verify', type=Path)
    args = parser.parse_args(argv)
    if args.verify:
        with gzip.open(args.verify, 'rt') as stream: value = json.load(stream)
        check_value(value)
        if args.bundle:
            capture, panel = source()
            manifest = check_bundle(args.bundle, capture)
            for key, world in panel.items():
                require(extract_world(args.bundle, manifest, world) == value['rows'][key], 'raw re-extraction differs')
                print(key + ': raw re-extraction verified', flush=True)
        print('Verified vacancy sequences offline; no simulations.')
    else:
        export(args.bundle or ROOT / 'artifacts/garden-landing-late-dispersal-v1', args.out)


if __name__ == '__main__':
    try: main()
    except (RuntimeError, ValueError, KeyError, TypeError, OSError, IndexError, StopIteration) as error:
        print('vacancy sequence audit failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
