#!/usr/bin/env python3
"""Offline population, renewal and diversity checks for the frozen day-512 protocol."""

import argparse
from collections import Counter
from functools import cache
import gzip
import json
from pathlib import Path

from garden_descendants import index_records
from garden_experiments import digest
import garden_landing_seed_cursor as previous
from garden_resources import require

ROOT = Path(__file__).resolve().parents[1]
DAY, BASE, STOP = 3840, 384 * 3840, 512 * 3840
BIRTH_STOP = 480 * DAY
WINDOWS = tuple((d * DAY, (d + 32) * DAY) for d in (384, 416, 448))
ARMS = ('fixed', 'cursor')
PHASES = ('anchor', 'middle', 'endpoint', 'repeat', 'plain')
SEEDS = ('3a7e45e6', '366928c6', '275c8982')
PANEL = {s + '-' + layout: dict(seed=s, scenario=layout)
         for s in SEEDS for layout in ('rainfed', 'rainfed-crowded')}
RULE = 'garden-landing-competitive-renewal-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-competitive-renewal-protocol.md'
PROTOCOL_SHA = 'e9ae9a1479547b5f489f9ed06d20322a2c5ede632dbd745154fa490e571b3539'
INPUT = 'benchmarks/garden-seasons/landing-seed-cursor-results.json.gz'
INPUT_SHA = 'cf6ba820eee40259fcaededb7188708517a8b282541ac78ff4b292f68d43af8a'
fingerprint = previous.sweep.fingerprint


@cache
def prior():
    # Exact already-audited capture, not a recursive comparison against today's C.
    require(digest(ROOT / INPUT) == INPUT_SHA, 'historical cursor capture changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream:
        value = json.load(stream)
    require(value['panel'] == PANEL, 'historical panel differs')
    return value


def horizon(phase):
    require(phase in PHASES, 'unknown phase')
    return {'anchor': BASE, 'middle': 448 * DAY}.get(phase, STOP)


def arguments(key, arm, phase):
    require(key in PANEL and arm in ARMS, 'unknown world/arm')
    args = list(prior()['runs'][arm][key]['args'])
    for flag in ('--stand-trace', '--stand-start', '--stand-stop', '--adult-trace',
                 '--adult-start', '--adult-stop', '--reach-trace'):
        offset = args.index(flag)
        del args[offset:offset + 2]
    args.remove('--stand-dawn')
    args[args.index('--ticks') + 1] = str(horizon(phase))
    if phase == 'plain':
        offset = args.index('--framebuffer')
        del args[offset:offset + 2]
    return args


def at(record, tick):
    return record['birth_tick'] <= tick and (record['death_tick'] is None or record['death_tick'] > tick)


def segments(spans, start, stop):
    """Exact post-step counts on discrete ticks (start, stop]; intervals are inclusive."""
    require(start < stop, 'empty exposure interval')
    changes = Counter({start + 1: 0, stop + 1: 0})
    for birth, death in spans:
        first, last = max(start + 1, birth), min(stop, death - 1 if death is not None else stop)
        if first <= last:
            changes[first] += 1
            changes[last + 1] -= 1
    points, count, rows = sorted(changes), 0, []
    for first, next_tick in zip(points, points[1:]):
        count += changes[first]
        require(count >= 0, 'negative presence count')
        if rows and rows[-1]['count'] == count:
            rows[-1]['last'] = next_tick - 1
        else:
            rows.append(dict(first=first, last=next_tick - 1, count=count))
    return rows


def absent(spans, start=BASE, stop=STOP):
    return [[r['first'], r['last']] for r in segments(spans, start, stop) if r['count'] == 0]


def exposure(spans, start, stop):
    rows = segments(spans, start, stop)
    total = sum((r['last'] - r['first'] + 1) * r['count'] for r in rows)
    return dict(start_exclusive=start, stop_inclusive=stop, plant_ticks=total,
                ticks=stop - start, mean=total / (stop - start),
                minimum=min(r['count'] for r in rows), maximum=max(r['count'] for r in rows))


def span(p):
    return p['birth_tick'], p['death_tick']


def seed_span(s):
    return s['birth_tick'], s['end_tick']


def age_status(p, days, stop=STOP):
    due = p['birth_tick'] + days * DAY
    dead = p['death_tick'] is not None and p['death_tick'] <= min(due, stop)
    return ('failed' if dead else 'confirmed') if due <= stop else ('recent-dead' if dead else 'censored')


def cohort(plants, stop=STOP):
    ages = {}
    for days in (16, 32):
        statuses = {name: [p['id'] for p in plants if age_status(p, days, stop) == name]
                    for name in ('confirmed', 'failed', 'recent-dead', 'censored')}
        eligible = len(statuses['confirmed']) + len(statuses['failed'])
        ages[str(days)] = dict(eligible=eligible, **statuses,
                              survival_rate=len(statuses['confirmed']) / eligible if eligible else None)
    return dict(births=[p['id'] for p in plants], ages=ages)


def ancestry(plants):
    families = {}
    for p in plants:
        require(p['parent'] == 0 or p['parent'] in families, 'missing/nonchronological ancestor')
        families[p['id']] = families[p['parent']] if p['parent'] else p['id']
    return families


def diversity(plants, seeds, stop=STOP):
    families = ancestry(plants)
    out = {}
    for axis in ('species', 'family'):
        def group(p):
            return p['species'] if axis == 'species' else families[p['id']]
        records = {p['id']: p for p in plants}
        baseline = sorted({group(p) for p in plants if at(p, BASE)})
        checkpoints = []
        for tick in range(BASE, stop + 1, 16 * DAY):
            counts = Counter(group(p) for p in plants if at(p, tick))
            bank = Counter(s['species'] if axis == 'species' else families[s['parent']]
                           for s in seeds if s['birth_tick'] <= tick and
                           (s['end_tick'] is None or s['end_tick'] > tick))
            checkpoints.append(dict(tick=tick, living={str(k): counts[k] for k in sorted(counts)},
                                    shares={str(k): counts[k] / sum(counts.values()) for k in sorted(counts)},
                                    pending={str(k): bank[k] for k in sorted(bank)}))
        losses = {str(g): [c['tick'] for c in checkpoints[1:] if str(g) not in c['living']] for g in baseline}
        gaps = {str(g): absent([span(p) for p in plants if group(p) == g], BASE, stop) for g in baseline}
        recoveries = []
        for g in baseline:
            for first, last in gaps[str(g)]:
                if last < stop:
                    children = [p['id'] for p in plants if group(p) == g and p['birth_tick'] == last + 1]
                    sources = [[s['parent'], s['birth_tick']] for s in seeds if s['child_id'] in children]
                    require(children and sources and all(records[c]['parent'] for c in children),
                            'unexplained group recovery')
                    recoveries.append(dict(group=g, absent=[first, last], children=children, seeds=sources))
        out[axis] = dict(baseline=baseline, checkpoints=checkpoints, losses=losses,
                         retained=[g for g in baseline if not losses[str(g)]], absence_intervals=gaps,
                         recoveries=recoveries, eligible=len(baseline) >= 2,
                         variety_retained=(all(len(c['living']) >= 2 for c in checkpoints[1:])
                                           if len(baseline) >= 2 else None))
    return out


def analyze(result):
    require(result['tick'] == STOP, 'analysis requires complete day-512 follow-up')
    plants, seeds = result['lineages'], result['seeds']
    index_records(plants, seeds, 0, STOP)
    spans = [span(p) for p in plants]
    blocks = [exposure(spans, d * DAY, (d + 16) * DAY) for d in range(384, 512, 16)]
    minimum = min(b['minimum'] for b in blocks)
    endpoint = sum(at(p, STOP) for p in plants)
    viability = dict(blocks=blocks, minimum=minimum, endpoint=endpoint,
                     empty_intervals=absent(spans),
                     no_plants_or_seeds=absent(spans + [seed_span(s) for s in seeds]),
                     passes=minimum > 0 and endpoint >= 4 and all(b['plant_ticks'] >= 4 * b['ticks'] for b in blocks))
    born = [p for p in plants if BASE < p['birth_tick'] <= BIRTH_STOP]
    windows = [dict(start_exclusive=a, stop_inclusive=b,
                    **cohort([p for p in born if a < p['birth_tick'] <= b])) for a, b in WINDOWS]
    primary, depths, pairs = cohort(born), {}, []
    for p in born:
        if age_status(p, 32) == 'confirmed':
            depths[p['id']] = 1 + depths.get(p['parent'], 0)
            if p['parent'] in depths:
                pairs.append([p['parent'], p['id']])
    by_id = {p['id']: p for p in plants}
    carry_in = [[p['parent'], p['id']] for p in born if by_id[p['parent']]['birth_tick'] <= BASE and
                age_status(p, 32) == age_status(by_id[p['parent']], 32) == 'confirmed']
    renewal = dict(primary=primary, windows=windows, pairs=pairs,
                   parents=sorted({p for p, _ in pairs}), deepest_chain=max(depths.values(), default=0),
                   carry_in_pairs=carry_in, late=cohort([p for p in plants if p['birth_tick'] > BIRTH_STOP]),
                   passes=bool(pairs) and all(w['ages']['32']['confirmed'] for w in windows))
    deaths = [p for p in plants if p['death_tick'] is not None and BASE < p['death_tick'] <= STOP]
    bought = [s for s in seeds if s['birth_tick'] > BASE]
    outcomes = Counter(s['outcome'] for s in bought)
    return dict(viability=viability, renewal=renewal, diversity=diversity(plants, seeds),
                deaths=dict(all=[p['id'] for p in deaths], baseline=[p['id'] for p in deaths if at(p, BASE)],
                            by_age_32=[p['id'] for p in deaths if p['death_tick'] - p['birth_tick'] <= 32 * DAY],
                            after_age_32=[p['id'] for p in deaths if p['death_tick'] - p['birth_tick'] > 32 * DAY]),
                purchases=len(bought), distinct_buyers=len({s['parent'] for s in bought}),
                seed_fates={k: outcomes[k] for k in ('germinated', 'expired', 'pending')})


def check_result(result, key, arm, phase, *, stop=None, reference=None):
    # Later explicitly frozen follow-ups reuse the same ledger/capacity rules;
    # historical callers keep their original horizons and outcome definitions.
    old = prior()['runs'][arm][key]['result'] if reference is None else reference
    stop = horizon(phase) if stop is None else stop
    require(set(result) == set(old) and result['tick'] == stop, 'wrong result schema/horizon')
    for name in ('schema_version', 'kind', 'run_version', 'rules', 'scenario', 'seed', 'model',
                 'gardener', 'irrigation', 'seed_lifetime_ecology_ticks', 'ledger_start_tick',
                 'warmup_samples', *(k for k in old if k.endswith('_probe') and k != 'seed_cursor_probe')):
        require(result[name] == old[name], 'changed historical setting: ' + name)
    plants, seeds = index_records(result['lineages'], result['seeds'], 0, stop)
    previous.sweep.events(result)
    require(list(plants) == list(range(1, len(plants) + 1)) and len(plants) <= 4096 and len(seeds) <= 65536,
            'noncontiguous/overflowed ledger')
    require([s['birth_tick'] for s in seeds.values()] == sorted(s['birth_tick'] for s in seeds.values()),
            'seed purchase order changed')
    for p in plants.values():
        require(type(p['species']) is int and 0 <= p['species'] < 3 and
                type(p['column']) is int and 0 <= p['column'] < 32 and
                type(p['generation']) is int and 0 <= p['generation'] <= 65535 and
                type(p['environmental_death']) is bool, 'invalid plant metadata')
        if p['parent']:
            require(p['parent'] < p['id'] and p['species'] == plants[p['parent']]['species'] and
                    p['generation'] == plants[p['parent']]['generation'] + 1, 'invalid inherited identity')
    require(all(s['species'] == plants[s['parent']]['species'] and s['lifetime_ecology_ticks'] == 8192
                for s in seeds.values()), 'seed species/lifetime changed')
    live = [p for p in plants.values() if at(p, stop)]
    require(result['births'] == sum(p['parent'] != 0 for p in plants.values()) and
            result['deaths'] == len(plants) - len(live) and result['living'] == len(live) and
            result['descendants'] == sum(p['parent'] != 0 for p in live) and
            result['seed_bank'] == sum(s['end_tick'] is None for s in seeds.values()) and
            0 <= result['living'] <= result['plant_slots'] <= 8 and 0 <= result['nodes'] <= 256 and
            0 <= result['seed_bank'] <= 8, 'endpoint census/capacity differs')
    require(exposure([span(p) for p in plants.values()], 0, stop)['maximum'] <= 8 and
            exposure([seed_span(s) for s in seeds.values()], 0, stop)['maximum'] <= 8,
            'historical living/seed capacity exceeded')
    descendants = [span(p) for p in plants.values() if p['parent']]
    require(exposure(descendants, 0, stop)['plant_ticks'] == result['descendant_live_ticks'],
            'descendant exposure differs')
    require(result['run_hash'] == previous.sweep.tagged(result['placement_run_hash']) and
            result['climate'] == previous.sweep.followup.previous.climate(int(result['seed'], 16), stop),
            'run identity/climate differs')
    if arm == 'cursor':
        buyers = [s['parent'] for s in seeds.values() if s['birth_tick'] > 320 * DAY]
        require(result['seed_cursor_probe'] == dict(version=1, after=320 * DAY, last_buyer=buyers[-1] if buyers else 0),
                'cursor does not match last paid buyer')
    require(previous.sweep.prefix(result, BASE) == (old['lineages'], old['seeds']), 'day-384 history changed')
    if phase == 'anchor':
        require(result == old, 'day-384 result changed')


def decision(outcomes):
    summary = {}
    for arm in ARMS:
        rows = outcomes[arm]
        viable = [k for k in PANEL if rows[k]['viability']['passes']]
        renewing = [k for k in PANEL if rows[k]['renewal']['passes']]
        summary[arm] = dict(viable=viable, renewing=renewing,
            broad_signal=len(viable) == 6 and len(renewing) >= 4 and
            {PANEL[k]['seed'] for k in renewing} == set(SEEDS) and
            {PANEL[k]['scenario'] for k in renewing} == {'rainfed', 'rainfed-crowded'},
            variety={axis: dict(eligible=[k for k in PANEL if rows[k]['diversity'][axis]['eligible']],
                                retained=[k for k in PANEL if rows[k]['diversity'][axis]['variety_retained']])
                     for axis in ('species', 'family')})
    pairs = {}
    for key in PANEL:
        a, b = outcomes['fixed'][key], outcomes['cursor'][key]
        pairs[key] = dict(renewal_delta=int(b['renewal']['passes']) - int(a['renewal']['passes']),
                          survivor_delta=len(b['renewal']['primary']['ages']['32']['confirmed']) -
                          len(a['renewal']['primary']['ages']['32']['confirmed']),
                          additional_losses={axis: sorted(set(a['diversity'][axis]['retained']) -
                                                        set(b['diversity'][axis]['retained']))
                                             for axis in ('species', 'family')})
    tradeoff = any(any(p['additional_losses'].values()) for p in pairs.values()) or any(
        len(summary['cursor']['variety'][axis]['retained']) < len(summary['fixed']['variety'][axis]['retained'])
        for axis in ('species', 'family'))
    return dict(arms=summary, pairs=pairs, diversity_tradeoff=tradeoff,
                cursor_renewal_advantage=summary['cursor']['broad_signal'] and
                len(summary['cursor']['renewing']) > len(summary['fixed']['renewing']))


def check_capture(value):
    require(value['rule'] == RULE and value['protocol_sha256'] == PROTOCOL_SHA and
            value['input_sha256'] == INPUT_SHA and value['panel'] == PANEL and
            value['origin_manifest_sha256'] == '245c2f70f8876d4aa9f30e6734215c423fd0a362655444ebda193930bd9de5dd' and
            value['native_runs'] == 60 and value['training_runs'] == 0 and
            value['model_sha256'] == prior()['model_sha256'] and
            value['build']['settings'] == prior()['build']['settings'] and
            set(value['runs']) == set(PHASES), 'wrong capture protocol/coverage')
    for phase in PHASES:
        require(set(value['runs'][phase]) == set(ARMS), 'missing arm')
        for arm in ARMS:
            runs = value['runs'][phase][arm]
            require(set(runs) == set(PANEL), 'missing world')
            for key, run in runs.items():
                require(run['args'] == arguments(key, arm, phase) and
                        run['directory'] == f'{phase}/{arm}/{key}', 'changed call')
                check_result(run['result'], key, arm, phase)
                require((run['frame'] is None) == (phase == 'plain'), 'wrong capture mode')
                if phase == 'plain':
                    require(run['result']['framebuffer_crc32'] is None, 'capture-free run has frame CRC')
                else:
                    require(run['frame']['path'] == run['directory'] + '/frames/end.raw', 'wrong frame path')
                if phase == 'anchor':
                    require(run['frame']['sha256'] == prior()['runs'][arm][key]['frame']['sha256'], 'anchor pixels differ')
                if phase == 'endpoint':
                    middle = value['runs']['middle'][arm][key]['result']
                    require(previous.sweep.prefix(run['result'], middle['tick']) ==
                            (middle['lineages'], middle['seeds']), 'day-448 history changed')
                if phase in ('repeat', 'plain'):
                    endpoint = value['runs']['endpoint'][arm][key]
                    expected = dict(endpoint['result'])
                    if phase == 'plain':
                        expected['framebuffer_crc32'] = None
                    require(run['result'] == expected and (phase == 'plain' or
                            run['frame']['sha256'] == endpoint['frame']['sha256']), 'repeat/capture dependence')
    derived = {a: {k: analyze(value['runs']['endpoint'][a][k]['result']) for k in PANEL} for a in ARMS}
    require(value['outcomes'] == derived and value['decision'] == decision(derived), 'outcomes/decision changed')
    require(value['receipt_sha256'] == fingerprint({k: v for k, v in value.items() if k != 'receipt_sha256'}),
            'capture receipt changed')
    expected_rows = [[f'{phase}/{arm}/{key}' for phase in ('middle', 'endpoint') for arm in ARMS] for key in PANEL]
    require(value['gallery']['rows'] == expected_rows and
            (value['gallery']['width'], value['gallery']['height'], value['gallery']['gap']) == (1000, 1496, 8),
            'gallery panel differs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', required=True, type=Path)
    parser.add_argument('--bundle', type=Path)
    args = parser.parse_args()
    with gzip.open(args.verify, 'rt') as stream:
        value = json.load(stream)
    check_capture(value)
    if args.bundle:
        from garden_landing_competitive_renewal_capture import verify_bundle
        verify_bundle(args.bundle.resolve(), value)
    print(json.dumps(value['decision'], indent=2))
    print('Competitive renewal verified offline; no simulator executed.')


if __name__ == '__main__':
    main()
