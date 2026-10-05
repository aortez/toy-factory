#!/usr/bin/env python3
"""Offline overlap of dispersal reach, eligibility and bank access during openings."""

from __future__ import annotations

import argparse
from collections import Counter
from functools import cache
import gzip
import json
from pathlib import Path
import sys

import garden_landing_second_opening_audit as previous
import garden_landing_late_dispersal as late
from garden_experiments import digest
from garden_landing_founders import write_gzip
from garden_landing_root_allocation_audit import fingerprint
from garden_resources import require

ROOT, BASE, STOP, STEP = previous.ROOT, previous.BASE, previous.STOP, previous.STEP
bank, window = previous.window.bank, previous.window
RULE = 'garden-landing-opening-opportunities-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-opening-opportunities-protocol.md'
PROTOCOL_SHA = 'b877336aa89cd6fb9495eef18a35e979d95338b65f46818cb203566d79ded7b9'
INPUT = 'benchmarks/garden-seasons/landing-second-opening-results.json.gz'
INPUT_SHA = 'bf54ecec747fcd8e87501d068dce76c98696529651e3950d5cf8fdb7856b5d26'
PHASES = previous.PHASES
TRAITS = (-2, -1, 0, 1, 2)
BLOCKERS = ('cooldown', 'cadence', 'bank', 'dead', 'stress', 'light', 'generation', 'energy', 'water', 'flower')
SPATIAL = 8 | 16 | 32  # Global plant/node capacity and three-column spacing.
IMPLEMENTATION = {
    'src/garden_world.c': '2947410c3622032e7267ebe03aa359a9b035d1847da0f693496838e710087621',
    'src/garden_world.h': 'f148562fe1aea1321b9a7dd3b12ab92c917a674d82588f5b89cc9b0770df4f4a',
    'src/garden_reproduction_audit.h': '1e57b3cab9071cc2aa8b5e54fe9d8dc46fe4216cc555d3e444ce66c439ca15fb',
    'src/garden_dispersal.h': 'bfa6f9466fa1483f22695546a6182cc569e55922942e4983fa9238d1c794039f',
    'src/garden_late_dispersal.h': '437d1589eb047f5e4a9abe0db8743dcb2cef2913958c5de098c90deb128a866a',
    'sim/garden_landing_reach.c': 'e9b2306adf4642a5020a283b3d9fbcad4bb3d8aa32738fc2c4cbad6d44e2cd66',
    'sim/garden_landing_plant_trace.c': 'aaf0c371d99a5c3be2216468020a4a5eb103e28338a9f5c2bd7e5f41ad27cdbe',
    'sim/garden_landing_placement.c': '0e783fe309a5ed72a4184ee4e223622d396f7bbe4580e7af417f90d8b5affd97',
}
SOURCES = tuple(sorted({*previous.SOURCES, 'sim/garden_landing_opening_opportunities.py',
                        'sim/garden_landing_late_dispersal.py', 'sim/garden_landing_reach.py'}))


@cache
def inputs():
    require(digest(ROOT / PROTOCOL) == PROTOCOL_SHA and digest(ROOT / INPUT) == INPUT_SHA,
            'opportunity protocol/input changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream:
        saved = json.load(stream)
    previous.check_value(saved)
    capture = previous.inputs()
    require(all(capture['source_sha256'].get(p) == h for p, h in IMPLEMENTATION.items()),
            'unreviewed captured implementation')
    return saved, capture


def provenance():
    saved, capture = inputs()
    return dict(rule=RULE, input_sha256=INPUT_SHA, capture_sha256=previous.INPUT_SHA,
                protocol_sha256=PROTOCOL_SHA, implementation=IMPLEMENTATION,
                panel=capture['panel'], native_runs=0, training_runs=0,
                sources={p: digest(ROOT / p) for p in SOURCES})


def lineage_identity(life):
    return {k: life[k] for k in ('id', 'parent', 'birth_tick', 'column', 'generation', 'species')}


def trait_evidence(pair, runs, identities):
    """Only pre-event identities may borrow immutable-trait witnesses across arms."""
    lives = {phase: {p['id']: p for p in run['result']['lineages']} for phase, run in runs.items()}
    records = {}
    for identity in identities:
        life = lives['control'][identity]
        require(life['birth_tick'] <= BASE and lineage_identity(life) ==
                lineage_identity(lives['treatment'][identity]), 'unmatched pre-event trait identity')
        witnesses = []
        for phase in PHASES:
            seeds = {(s['parent'], s['birth_tick']): s for s in runs[phase]['result']['seeds']}
            for row in (pair[phase]['boundary'], *pair[phase]['rows']):
                for purchase in row[6]:
                    if purchase['parent'] != identity:
                        continue
                    late.purchase_check(purchase, row[1], lives[phase], seeds[identity, row[0]], True)
                    witnesses.append(dict(phase=phase, tick=row[0], purchase=purchase))
        observed = {w['purchase']['dispersal'] for w in witnesses}
        require(len(observed) <= 1, 'conflicting immutable dispersal traits')
        records[str(identity)] = dict(life=lineage_identity(life), status='recorded' if observed else 'bounded',
                                      allowed=sorted(observed) if observed else list(TRAITS), witnesses=witnesses)
    return records


def select(saved, capture):
    worlds = {}
    for key, world in sorted(capture['panel'].items()):
        event = saved['analysis'][key]['treatment']['disturbance']
        require(event['event']['lineage'] == world['target'] and event['reclamation'] is not None and
                event['first_germination'] is not None, 'missing second-opening bounds')
        start, stop = event['reclamation']['tick'], event['first_germination']['birth_tick']
        require(BASE < start < stop <= STOP and start % STEP == stop % STEP == 0, 'invalid opening interval')
        evidence = {}
        for phase in PHASES:
            rows = {r[0]: r for r in (saved['evidence'][key][phase]['boundary'], *saved['evidence'][key][phase]['rows'])}
            evidence[phase] = dict(before=rows[start - STEP], rows=[rows[t] for t in range(start, stop, STEP)],
                                   closing=rows[stop])
        runs = {phase: capture['runs'][phase][key] for phase in PHASES}
        identities = world['focal'] + world['first_recruits']
        worlds[key] = dict(interval=[start, stop], evidence=evidence,
                           traits=trait_evidence(saved['evidence'][key], runs, identities))
    return worlds


def site_map(row, lives, result):
    """Same-step observed mature-seed gates, never a forecast for a new seed."""
    tick, slots, _, packed, bodies, checks, purchases, _ = row
    require(set(slots) == {b[0] for b in bodies} and all(lives[i]['birth_tick'] < tick and
            (lives[i]['death_tick'] is None or lives[i]['death_tick'] > tick) for i in slots),
            'site/production phase has a birth or stored corpse')
    require(all(p[0][1] == p[0][2] == p[0][3] for _, p in packed), 'growth/germination changed site phase')
    maps = {encoded for raw, encoded in checks if encoded is not None}
    require(len(maps) == 1 and all(raw[8] != 2 for raw, _ in checks), 'missing or incompatible site maps')
    encoded = next(iter(maps))
    sites = late.sites_decode(encoded)
    nodes = sum(p[0][1][4] for _, p in packed)
    cold = window.previous.sun_at(int(result['seed'], 16), tick)[0]['cold']
    spacing = late.spacing_map(tuple(lives[i]['column'] for i in slots))
    for column, mask in enumerate(sites):
        expected = (8 if len(slots) == 8 else 0) | (16 if nodes + 4 > 256 else 0) | spacing[column] | (64 if cold else 0)
        require(mask & (SPATIAL | 64) == expected, 'site capacity/spacing/climate differs')
    for raw, observed in checks:
        require(raw[6] == len(slots) and raw[7] == nodes, 'seed/production census differs')
        if observed is not None:
            require(bool(sites[raw[2]] & 2) == (raw[4] < 12) and
                    bool(sites[raw[2]] & 4) == (raw[5] < 80), 'observed site light/moisture differs')
    require(all(p['sites'] == encoded for p in purchases), 'post-purchase site phase differs')
    return sites


def ordered_access(visits):
    require(visits and all(len(v) == len(bank.FIELDS) for v in visits), 'missing/invalid ordered visits')
    entry = visits[0][bank.FIELDS.index('bank')]
    require(type(entry) is int and 0 <= entry <= 8, 'invalid entry bank')
    count, buyers, out = entry, [], {}
    for rank, raw in enumerate(visits):
        v = dict(zip(bank.FIELDS, raw, strict=True))
        require(v['id'] not in out and v['bank'] == count <= 8 and
                bool(v['blockers'] & bank.BANK) == (count == 8) and
                type(v['produced']) is bool and v['produced'] == (v['blockers'] == 0), 'ordered bank differs')
        access = 'ineligible' if v['blockers'] & ~bank.BANK else 'purchased' if v['produced'] else (
            'full_at_entry' if entry == 8 else 'earlier_buyers_fill')
        if access == 'earlier_buyers_fill':
            require(len(buyers) == 8 - entry and buyers, 'unexplained lost opening')
        out[v['id']] = dict(rank=rank, bank_at_entry=entry, earlier_buyers=list(buyers), access=access, visit=v)
        if v['produced']:
            count += 1
            buyers.append(v['id'])
    return out


def columns(sites, origin, trait):
    support = late.support(origin, trait, True)
    unique = sorted(set(support))
    return dict(choices=support, spacing=[c for c in unique if not sites[c] & 32],
                space=[c for c in unique if not sites[c] & SPATIAL], opened=[c for c in unique if sites[c] == 0])


def counters():
    return dict.fromkeys(('spacing_ticks', 'space_ticks', 'open_ticks', 'space_daylight', 'open_daylight',
                         *(f'{kind}_{outcome}' for kind in ('space', 'open') for outcome in bank.OUTCOMES),
                         'space_eligible', 'open_eligible'), 0)


def bounds(profiles):
    """Min/max over each fixed trait's whole-window counts, not per-tick trait switching."""
    require(profiles, 'missing trait profiles')
    return {name: [min(p[name] for p in profiles.values()), max(p[name] for p in profiles.values())]
            for name in counters()}


def analyze_arm(evidence, traits, world, run, interval, phase):
    start, stop = interval
    require(set(evidence) == {'before', 'rows', 'closing'} and evidence['before'][0] == start - STEP and
            evidence['closing'][0] == stop and [r[0] for r in evidence['rows']] == list(range(start, stop, STEP)),
            'missing/reordered opening clock or boundary')
    result = run['result']
    lives, seeds = bank.descendants.index_records(result['lineages'], result['seeds'], 0, STOP)
    if phase == 'treatment':
        release = window.prior.slot_change(evidence['before'][1], evidence['rows'][0][1], start, lives)
        closing = window.prior.slot_change(evidence['rows'][-1][1], evidence['closing'][1], stop, lives)
        require(release['removed'] == [world['target']] and not release['born'] and
                release['slots_before'] == 8 and release['slots_after'] == 7 and
                len(closing['born']) == 1 and not closing['removed'] and closing['slots_after'] == 8,
                'wrong reclamation/refill boundaries')
    else:
        require(evidence['before'][1] == evidence['closing'][1], 'control inventory changed')
    access_check = bank.analyze_visits([[r[0], r[2]] for r in evidence['rows']], result, start, stop - STEP)
    parents = {identity: dict(cohort='focal' if int(identity) in world['focal'] else 'first_recruit',
                              ecology_visits=0, cadence_visits=0, daylight_cadence=0,
                              access=dict.fromkeys(bank.OUTCOMES, 0), daylight_access=dict.fromkeys(bank.OUTCOMES, 0),
                              daylight_blockers=dict.fromkeys(BLOCKERS, 0), daylight_energy_margins=[],
                              daylight_water_margins=[], traits={str(t): counters() for t in info['allowed']},
                              opportunity_visits=[]) for identity, info in traits.items()}
    timeline = []
    for row in evidence['rows']:
        tick = row[0]
        window.check_row(row, tick, STOP, result, lives, seeds)
        require(len(row[1]) == (7 if phase == 'treatment' else 8), 'wrong stored interval census')
        sites, visits = site_map(row, lives, result), ordered_access(row[2])
        timeline.append(dict(tick=tick, sites=sites.hex(), bank_at_entry=next(iter(visits.values()))['bank_at_entry'],
                             buyers=[i for i, v in visits.items() if v['visit']['produced']]))
        for identity, record in parents.items():
            receipt = visits[int(identity)]
            v, category = receipt['visit'], receipt['access']
            daylight = tick % 60 == 0 and v['sun'] > 24
            record['ecology_visits'] += 1
            record['cadence_visits'] += tick % 60 == 0
            record['daylight_cadence'] += daylight
            record['access'][category] += 1
            if daylight:
                record['daylight_access'][category] += 1
                record['daylight_energy_margins'].append(v['energy'] - v['energy_required'])
                record['daylight_water_margins'].append(v['water'] - v['water_required'])
                for j, name in enumerate(BLOCKERS):
                    record['daylight_blockers'][name] += bool(v['blockers'] & (1 << j))
            reached = {}
            for trait, profile in record['traits'].items():
                reached[trait] = cols = columns(sites, lives[int(identity)]['column'], int(trait))
                profile['spacing_ticks'] += bool(cols['spacing'])
                for kind, field in (('space', 'space'), ('open', 'opened')):
                    available = bool(cols[field])
                    profile[kind + '_ticks'] += available
                    if daylight and available:
                        profile[kind + '_daylight'] += 1
                        profile[kind + '_' + category] += 1
                        profile[kind + '_eligible'] += not (v['blockers'] & ~bank.BANK)
            if daylight and any(c['space'] for c in reached.values()):
                record['opportunity_visits'].append(dict(tick=tick, **receipt, reachable=reached))
    indexed = {p['id']: p for p in access_check['plants']}
    for identity, record in parents.items():
        require(record['access'] == indexed[int(identity)]['access'], 'access denominator differs')
        record['bounds'] = bounds(record['traits'])
        for name in ('daylight_energy_margins', 'daylight_water_margins'):
            values = record[name]
            record[name] = [min(values), max(values)] if values else None
    cohorts = {}
    for name in ('focal', 'first_recruit'):
        selected = [p for p in parents.values() if p['cohort'] == name]
        cohorts[name] = dict(plants=len(selected), ecology_visits=sum(p['ecology_visits'] for p in selected),
                            daylight_cadence=sum(p['daylight_cadence'] for p in selected),
                            bounds={metric: [sum(p['bounds'][metric][side] for p in selected) for side in (0, 1)]
                                    for metric in counters()})
    return dict(parents=parents, cohorts=cohorts, timeline=timeline,
                bank_entries=dict(sorted(Counter(str(r['bank_at_entry']) for r in timeline).items())),
                closing=dict(tick=stop, slots=evidence['closing'][1],
                             births=[p for p in lives.values() if p['birth_tick'] == stop],
                             seeds=[s for s in seeds.values() if s['end_tick'] == stop and s['outcome'] == 'germinated']))


def analyze(material, capture):
    require(set(material) == set(capture['panel']), 'wrong opportunity panel')
    out = {}
    for key, item in material.items():
        world = capture['panel'][key]
        require(set(item['traits']) == {str(i) for i in world['focal'] + world['first_recruits']} and
                set(item['evidence']) == set(PHASES), 'missing cohort or paired evidence')
        for identity, info in item['traits'].items():
            seen = {w['purchase']['dispersal'] for w in info['witnesses']}
            require(len(seen) <= 1 and info['allowed'] == (sorted(seen) if seen else list(TRAITS)) and
                    info['status'] == ('recorded' if seen else 'bounded'), 'guessed/conflicting trait evidence')
        out[key] = {phase: analyze_arm(item['evidence'][phase], item['traits'], world,
                                      capture['runs'][phase][key], item['interval'], phase) for phase in PHASES}
    return out


def check_value(value):
    saved, capture = inputs()
    expected = provenance()
    require(set(value) == {*expected, 'material', 'analysis', 'receipt_sha256'} and
            all(value[k] == v for k, v in expected.items()), 'opportunity provenance differs')
    require(value['material'] == select(saved, capture), 'selected evidence/trait witnesses changed')
    require(value['analysis'] == analyze(value['material'], capture), 'derived opportunity analysis differs')
    require(value['receipt_sha256'] == fingerprint({k: v for k, v in value.items() if k != 'receipt_sha256'}),
            'opportunity receipt changed')


def export():
    saved, capture = inputs()
    expected = provenance()
    material = select(saved, capture)
    value = dict(expected, material=material, analysis=analyze(material, capture))
    require(provenance() == expected and digest(ROOT / INPUT) == INPUT_SHA, 'opportunity inputs changed')
    value['receipt_sha256'] = fingerprint(value)
    check_value(value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--out', type=Path)
    mode.add_argument('--verify', type=Path)
    args = parser.parse_args()
    if args.out:
        require(not args.out.exists() and not args.out.is_symlink(), 'fresh output required')
        write_gzip(args.out, export())
    else:
        with gzip.open(args.verify, 'rt') as stream:
            value = json.load(stream)
        check_value(value)
    print('verified ' + RULE)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, TypeError, IndexError, OSError) as error:
        print('error: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
