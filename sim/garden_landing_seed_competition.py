#!/usr/bin/env python3
"""Audit saved seed queues and single-opening capacity; never run a simulation."""

from __future__ import annotations

import argparse
from functools import cache
import gzip
import json
from pathlib import Path
import sys

import garden_landing_seed_replacement as previous
from garden_experiments import digest
from garden_landing_founders import write_gzip
from garden_landing_root_allocation_audit import fingerprint
from garden_resources import require

ROOT, BASE, STOP, STEP = previous.ROOT, previous.BASE, previous.STOP, previous.STEP
late, window, followup = previous.late, previous.window, previous.followup
RULE = 'garden-landing-seed-competition-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-seed-competition-protocol.md'
PROTOCOL_SHA = 'd321761a612c7528ad1d1bdd213e7450408dedfd4740211e273e9cce5da9719d'
INPUT = 'benchmarks/garden-seasons/landing-seed-replacement-results.json.gz'
INPUT_SHA = 'e856d8877a34747bce4c5ade78e3492acb0f211379ddcb843e4a44a2ec868b4a'
MANIFEST_SHA = '6f5f737dcb8147a488ad0339a553d7f81823db65d5df8a097332112ff15de465'
PHASES = ('control', 'treatment')
KINDS = ('stand', 'adult', 'reach')
SOURCES = tuple(sorted({*previous.SOURCES, 'sim/garden_landing_seed_competition.py'}))


@cache
def inputs():
    require(digest(ROOT / INPUT) == INPUT_SHA and digest(ROOT / PROTOCOL) == PROTOCOL_SHA,
            'competition input/protocol changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream:
        saved = json.load(stream)
    previous.verify_capture(saved)
    return saved


def provenance():
    saved = inputs()
    return dict(rule=RULE, input_sha256=INPUT_SHA, manifest_sha256=MANIFEST_SHA,
                protocol_sha256=PROTOCOL_SHA, model_sha256=saved['model_sha256'], panel=saved['panel'],
                sources={p: digest(ROOT / p) for p in SOURCES}, native_runs=0, training_runs=0)


def bounds(key, phase):
    # Replacement starts later than this common, independently recorded release.
    prior, _ = previous.opportunities.inputs()
    start = prior['analysis'][key]['treatment']['disturbance']['reclamation']['tick']
    result = inputs()['runs'][phase][key]['result']
    stop = min(p['birth_tick'] for p in result['lineages'] if p['birth_tick'] > BASE)
    require(BASE < start < stop < STOP and start % STEP == stop % STEP == 0, 'wrong opening bounds')
    return start, stop


def identities(seeds, start, stop):
    return {k for k, s in seeds.items() if s['birth_tick'] <= stop + STEP and
            (s['end_tick'] or STOP + STEP) >= start - STEP}


def extract_arm(paths, run, key, phase):
    start, stop = bounds(key, phase)
    _, seeds = previous.index_result(run['result'])
    wanted = identities(seeds, start, stop)
    birth_ticks = {seeds[k]['birth_tick'] for k in wanted}
    require(min(birth_ticks) >= previous.FIRST, 'purchase predates archived stand trace')
    rows, slots, witnesses = {}, {}, {}
    for kind in KINDS:
        for raw, _ in followup.trace_rows(paths[kind], kind, STEP if kind == 'reach' else previous.FIRST,
                                         STOP, run['result']):
            tick = raw['tick']
            if kind == 'stand' and tick in birth_ticks:
                slots[tick] = raw['plant_order']
            if kind == 'reach':
                for purchase in raw['purchases']:
                    identity = purchase['parent'], tick
                    if identity in wanted:
                        require(identity not in witnesses, 'duplicate purchase witness')
                        witnesses[identity] = dict(seed=list(identity), slots=slots[tick], purchase=purchase)
            if not start - STEP <= tick <= stop + STEP:
                continue
            row = rows.setdefault(tick, dict(tick=tick))
            if kind == 'stand':
                row['slots'] = raw['plant_order']
            elif kind == 'adult':
                row.update(checks=raw['seeds'], bank=raw['bank'])
            else:
                checks = []
                for seed, check in zip(row['checks'], raw['checks'], strict=True):
                    require(check[:4] == seed[:4] and check[4:6] == seed[8:10], 'adult/reach checks differ')
                    checks.append([seed, check[6]])
                row.update(checks=checks, purchases=raw['purchases'])
    require(set(witnesses) == wanted, 'missing purchase witnesses')
    return dict(rows=[rows[t] for t in sorted(rows)], witnesses=[witnesses[k] for k in sorted(wanted)])


def extract(bundle):
    saved = inputs()
    require(digest(bundle / 'manifest.json') == MANIFEST_SHA, 'wrong raw manifest')
    manifest = json.loads((bundle / 'manifest.json').read_text())
    evidence = {}
    for key in sorted(saved['panel']):
        evidence[key] = {}
        for phase in PHASES:
            run = saved['runs'][phase][key]
            paths = {}
            for kind in KINDS:
                item = run['traces'][kind]
                require(manifest['artifacts'].get(item['path']) == item['sha256'], 'trace/manifest differs')
                paths[kind] = followup.artifact(bundle, item)
            print(f'Auditing {phase}: {key}', file=sys.stderr, flush=True)
            evidence[key][phase] = extract_arm(paths, run, key, phase)
            require(all(digest(paths[k]) == run['traces'][k]['sha256'] for k in KINDS), 'trace changed during read')
    return evidence


def packing(columns):
    """Earliest-column greedy is exact for equal-width intervals on a line."""
    placed = []
    for column in sorted(set(columns)):
        require(type(column) is int and 0 <= column < 28, 'invalid packing column')
        if not placed or column - placed[-1] >= 3:
            placed.append(column)
    return placed


def purchase_allowed(purchase):
    """The recorded placement rule prefers clear choices, falling back if none exist."""
    sites = late.sites_decode(purchase['sites'])
    support = sorted(set(purchase['choices']))
    return [c for c in support if not sites[c] & 32] or support


def opportunity(raw, encoded, choices, allowed):
    if encoded is None:  # Expiry performs no viability query.
        return None
    sites = late.sites_decode(encoded)
    support = sorted(set(choices))
    clear = [c for c in range(28) if not sites[c] & 32]
    alternate = [c for c in support if c != raw[2] and sites[c] == 0]
    return dict(spacing_clear=clear, packing=packing(clear),
                plant_slots_free=8 - raw[6], seedling_node_slots_free=(256 - raw[7]) // 4,
                admission_bound=min(len(packing(clear)), 8 - raw[6], (256 - raw[7]) // 4),
                reachable_spacing=[c for c in support if not sites[c] & 32],
                alternate_sites=alternate, purchase_allowed_alternates=[c for c in alternate if c in allowed],
                mature=raw[1] >= 8)


def validate_row(row, tick, lives, seeds, result, witnesses):
    require(set(row) == {'tick', 'slots', 'checks', 'bank', 'purchases'} and row['tick'] == tick,
            'invalid row schema/clock')
    slots = row['slots']
    live = {i for i, p in lives.items() if p['birth_tick'] <= tick and
            (p['death_tick'] is None or p['death_tick'] > tick)}
    require(len(slots) == len(set(slots)) <= 8 and live <= set(slots) <= set(lives) and
            all(lives[i]['birth_tick'] <= tick for i in slots), 'stored census differs')
    born = {i for i, p in lives.items() if p['birth_tick'] == tick}
    check_slots = [i for i in slots if i not in born]
    checked, queue, nodes = set(), [], None
    cold = window.previous.sun_at(int(result['seed'], 16), tick)[0]['cold']
    for raw, encoded in row['checks']:
        identity = raw[0], tick - raw[1] * STEP
        require(identity in seeds and identity not in checked and identity in witnesses, 'seed identity differs')
        checked.add(identity)
        seed = seeds[identity]
        gate_seed = dict(seed, outcome='pending', end_tick=None) if seed['outcome'] == 'replaced' else seed
        window.previous.seed_check(raw, encoded, tick, gate_seed, check_slots, lives, cold)
        require(nodes is None or nodes == raw[7], 'sequential node count differs')
        nodes = raw[7]
        if encoded is not None:
            sites = late.sites_decode(encoded)
            spacing = late.spacing_map(tuple(lives[i]['column'] for i in check_slots))
            for c, mask in enumerate(sites):
                expected = spacing[c] | (8 if len(check_slots) == 8 else 0) | (16 if nodes + 4 > 256 else 0)
                require(mask & (8 | 16 | 32 | 64) == expected | (64 if cold else 0),
                        'site capacity/spacing/climate differs')
        purchase = witnesses[identity]['purchase']
        chance = opportunity(raw, encoded, purchase['choices'], purchase_allowed(purchase))
        queue.append(dict(seed=list(identity), age=raw[1], column=raw[2], blockers=raw[3], outcome=raw[8],
                          child=raw[9], plants=raw[6], nodes=nodes, opportunity=chance))
        if raw[8] == 2:
            check_slots.append(raw[9])
            nodes += 4
    expected = {k for k, s in seeds.items() if s['birth_tick'] < tick <= (s['end_tick'] or STOP)}
    require(checked == expected and check_slots == slots, 'incomplete seed admission')
    bought = {}
    for purchase in row['purchases']:
        identity = purchase['parent'], tick
        require(identity in seeds and identity not in bought, 'unexpected/duplicate purchase')
        late.purchase_check(purchase, slots, lives, seeds[identity], True)
        require(witnesses.get(identity) == dict(seed=list(identity), slots=slots, purchase=purchase),
                'purchase witness differs')
        bought[identity] = purchase
    require(set(bought) == {k for k, s in seeds.items() if s['birth_tick'] == tick}, 'purchase coverage differs')
    # A replaced seed WAITs above, then leaves during reproduction. Do not count
    # it as an expiry or remove it before its final recorded germination check.
    active = {k for k, s in seeds.items() if s['birth_tick'] <= tick < (s['end_tick'] or STOP + STEP)}
    require(len(active) == row['bank'] <= 8, 'post-production bank differs')
    return queue


def analyze_arm(evidence, key, phase):
    start, stop = bounds(key, phase)
    run = inputs()['runs'][phase][key]
    result, world = run['result'], inputs()['panel'][key]
    lives, seeds = previous.index_result(result)
    require(set(evidence) == {'rows', 'witnesses'} and
            [r['tick'] for r in evidence['rows']] == list(range(start - STEP, stop + 2 * STEP, STEP)),
            'missing/reordered opening clock or boundary')
    witnesses, traits = {}, {}
    for witness in evidence['witnesses']:
        require(set(witness) == {'seed', 'slots', 'purchase'}, 'wrong witness schema')
        identity = tuple(witness['seed'])
        require(identity in seeds and identity not in witnesses, 'duplicate/unknown witness')
        purchase = witness['purchase']
        late.purchase_check(purchase, witness['slots'], lives, seeds[identity], True)
        trait = purchase['dispersal']
        require(traits.setdefault(identity[0], trait) == trait, 'conflicting immutable dispersal traits')
        witnesses[identity] = witness
    require(list(witnesses) == sorted(identities(seeds, start, stop)), 'incomplete/reordered competing seed cohort')
    rows = evidence['rows']
    prior, _ = previous.opportunities.inputs()
    old_before = next(r for r in prior['evidence'][key]['treatment']['rows'] if r[0] == start - STEP)
    require(rows[0]['slots'] == old_before[1], 'common pre-release inventory differs')
    records = {k: dict(seed=seeds[k], maturity_tick=k[1] + 8 * STEP,
                       purchase_allowed_columns=purchase_allowed(witnesses[k]['purchase']),
                       checks_before_refill=0, mature_before_refill=0, reachable_spacing_checks=0,
                       mature_alternative_checks=0, dormant_alternative_checks=0,
                       purchase_allowed_mature_checks=0, purchase_allowed_dormant_checks=0,
                       mature_alternative_first=None, mature_alternative_last=None,
                       dormant_alternative_first=None, dormant_alternative_last=None)
               for k in sorted(witnesses)}
    snapshots, admission_bounds, changes = {}, [], []
    for index, row in enumerate(rows):
        tick = row['tick']
        queue = validate_row(row, tick, lives, seeds, result, witnesses)
        if index:
            changes.append(window.prior.slot_change(rows[index - 1]['slots'], row['slots'], tick, lives))
        if tick in (start, stop, stop + STEP):
            snapshots[str(tick)] = queue
        if start <= tick <= stop:
            for q in queue:
                chance = q['opportunity']
                if chance is None or q['plants'] == 8:
                    continue  # Expiry has no site query; a previous admission closed the slot.
                admission_bounds.append(chance['admission_bound'])
                record = records[tuple(q['seed'])]
                record['checks_before_refill'] += 1
                record['mature_before_refill'] += chance['mature']
                record['reachable_spacing_checks'] += bool(chance['reachable_spacing'])
                if chance['alternate_sites']:
                    name = 'mature' if chance['mature'] else 'dormant'
                    record[name + '_alternative_checks'] += 1
                    record['purchase_allowed_' + name + '_checks'] += bool(chance['purchase_allowed_alternates'])
                    witness = dict(tick=tick, age=q['age'], columns=chance['alternate_sites'],
                                   purchase_allowed=chance['purchase_allowed_alternates'], blockers=q['blockers'])
                    if record[name + '_alternative_first'] is None:
                        record[name + '_alternative_first'] = witness
                    record[name + '_alternative_last'] = witness
    release = changes[0]
    closing = next(c for c in changes if c['tick'] == stop)
    require(release['removed'] == [world['target']] and not release['born'] and
            release['slots_before'] == 8 and release['slots_after'] == 7 and
            len(closing['born']) == 1 and not closing['removed'] and closing['slots_after'] == 8 and
            all(not c['removed'] and not c['born'] for c in changes if c['tick'] not in (start, stop)),
            'unexpected release/refill events')
    child = lives[closing['born'][0]]
    winner = next(s for s in seeds.values() if s['child_id'] == child['id'])
    geometry = next(q['opportunity'] for q in snapshots[str(start)] if q['opportunity'] is not None)
    cohorts = {}
    for name, ids in (('focal', world['focal']), ('first_recruit', world['first_recruits'])):
        cohorts[name] = {str(i): dict(life=lives[i], competing_seeds=[list(k) for k in records if k[0] == i],
                                    post_onset=run['analysis']['summary']['cohorts'][name][str(i)]) for i in ids}
    return dict(interval=[start, stop], opening_steps=(stop - start) // STEP,
                release=release, initial_capacity=geometry, admission_bound_range=[min(admission_bounds), max(admission_bounds)],
                winner=dict(seed=winner, child=child), snapshots=snapshots, seeds=list(records.values()), cohorts=cohorts,
                mature_alternative_seeds=[list(k) for k, r in records.items() if r['mature_alternative_checks']],
                dormant_alternative_seeds=[list(k) for k, r in records.items() if r['dormant_alternative_checks']],
                later_births=[p for p in lives.values() if p['birth_tick'] > stop],
                later_deaths=[p for p in lives.values() if p['death_tick'] is not None and p['death_tick'] > stop])


def analyze(evidence):
    require(set(evidence) == set(inputs()['panel']), 'missing world')
    result = {}
    for key, pair in evidence.items():
        require(set(pair) == set(PHASES), 'missing arm')
        result[key] = {phase: analyze_arm(pair[phase], key, phase) for phase in PHASES}
    return result


def build(evidence):
    value = dict(provenance(), evidence=evidence, analysis=analyze(evidence))
    value['receipt_sha256'] = fingerprint(value)
    return value


def check_value(value):
    require(value == build(value['evidence']), 'competition analysis/provenance differs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, help='pinned raw replacement bundle; no native execution')
    parser.add_argument('--out', type=Path, help='fresh portable gzip output')
    parser.add_argument('--verify', type=Path, help='verify portable evidence; add --bundle to re-extract it')
    args = parser.parse_args()
    if args.verify:
        require(args.out is None, '--verify cannot write an output')
        with gzip.open(args.verify, 'rt') as stream:
            value = json.load(stream)
        check_value(value)
        if args.bundle:
            require(value['evidence'] == extract(args.bundle), 'raw/portable evidence differs')
    else:
        require(args.bundle is not None and args.out is not None, '--bundle and --out required')
        require(not args.out.exists() and not args.out.is_symlink(), 'fresh output required')
        value = build(extract(args.bundle))
        write_gzip(args.out, value)
    print(json.dumps(dict(rule=RULE, worlds=len(value['analysis']), histories=10, native_runs=0,
                          training_runs=0, receipt_sha256=value['receipt_sha256']), sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, OSError, StopIteration, TypeError) as error:
        sys.exit(str(error))
