#!/usr/bin/env python3
"""Audit one saved seed-placement decision and family renewal without simulation."""

from __future__ import annotations

import argparse
from collections import Counter
from functools import cache
import gzip
import json
from pathlib import Path
import sys

import garden_landing_winter_light as previous
import garden_landing_late_dispersal as late
from garden_experiments import digest
from garden_landing_energy_audit import archived_sources
from garden_landing_founders import write_gzip
from garden_landing_root_allocation_audit import fingerprint
from garden_resources import require

ROOT, STEP, STOP = previous.ROOT, previous.STEP, previous.STOP
SIDES = previous.SIDES
RULE = 'garden-landing-placement-information-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-placement-information-protocol.md'
PROTOCOL_SHA = '1b8a6a6d648334a0eafb1ad7a8468c98c6b185ddd3888d5cb3bdeb17367dc482'
INPUT = 'benchmarks/garden-seasons/landing-winter-light-results.json.gz'
INPUTS = {INPUT: '4dec6112f5f1c875ed40cfa8515d1581de27c7422311077b7c36cfb49d9d61c6',
          **previous.capture.INPUTS}
MANIFEST_SHA = previous.capture.NATIVE_FILES['manifest.json']
PARENT, CHILD, PURCHASE, BIRTH = 20, 29, 652260, 652380
KINDS = ('stand', 'adult', 'reach')
BLOCKERS = ('dormant', 'moisture', 'light', 'plant_capacity', 'node_capacity', 'spacing', 'cold')
IMPLEMENTATION = {
    'src/garden_agent.h': '12d007b5ba76e7d8fa80420024a395b96c45cd08369b9ef044d843269ae31f29',
    'src/garden_world.c': 'a5e54ce7636bbd3e7c1e2fc148264ded8ae29136078f37dac412090e7edfbfc8',
    'src/garden_world.h': 'ab0ce75d4fe2e0e919ccea3124e84df475b99ed6e7cd2e308c3410869e780a23',
    'src/garden_dispersal.h': 'bfa6f9466fa1483f22695546a6182cc569e55922942e4983fa9238d1c794039f',
    'src/garden_late_dispersal.h': '437d1589eb047f5e4a9abe0db8743dcb2cef2913958c5de098c90deb128a866a',
    'sim/garden_landing_placement.c': '0e783fe309a5ed72a4184ee4e223622d396f7bbe4580e7af417f90d8b5affd97',
    'sim/garden_landing_placement.h': '7852902f303377b1202c9386254d162e4fc43c35797da8379250b583b5c1085a',
    'sim/garden_landing_run.c': '0539c08fb3d30b2ef98c06acfe0874a030abc1d298bd5e2f6ccf3355e336c736',
    'sim/garden_landing_reach.c': 'e9b2306adf4642a5020a283b3d9fbcad4bb3d8aa32738fc2c4cbad6d44e2cd66',
    'sim/garden_landing_plant_trace.c': 'aaf0c371d99a5c3be2216468020a4a5eb103e28338a9f5c2bd7e5f41ad27cdbe',
}
SOURCES = ('sim/garden_landing_placement_information.py', 'sim/garden_landing_late_dispersal.py',
           'sim/garden_landing_reach.py', 'sim/garden_landing_dispersal_timing.py',
           'sim/garden_landing_population.py', 'sim/garden_landing_adults.py',
           'sim/garden_landing_founders.py', 'sim/garden_landing_root_allocation_audit.py',
           'sim/garden_experiments.py', 'sim/garden_resources.py', 'sim/garden_landing_energy_audit.py',
           'sim/garden_landing_winter_light.py', 'sim/garden_landing_winter_light_capture.py')


def provenance():
    require(digest(ROOT / PROTOCOL) == PROTOCOL_SHA and
            all(digest(ROOT / p) == sha for p, sha in INPUTS.items()), 'placement information inputs changed')
    # The implementation belongs to the captured executable, not to a future
    # working tree. inputs() checks these identities against its pinned archive.
    return dict(rule=RULE, inputs=INPUTS, implementation=IMPLEMENTATION, protocol_sha256=PROTOCOL_SHA,
                raw_manifest_sha256=MANIFEST_SHA, native_runs=0, training_runs=0,
                subject=dict(parent=PARENT, child=CHILD, purchase=PURCHASE, birth=BIRTH))


@cache
def inputs():
    provenance()
    with gzip.open(ROOT / INPUT, 'rt') as stream: winter = json.load(stream)
    previous.check_value(winter)
    with gzip.open(ROOT / list(previous.capture.INPUTS)[1], 'rt') as stream: saved = json.load(stream)
    capture = saved['capture']
    require(saved['raw_manifest_sha256'] == MANIFEST_SHA and all(capture['source_sha256'].get(p) == sha
            for p, sha in IMPLEMENTATION.items()), 'unreviewed archived implementation')
    pair = next(p for p in saved['pairs'] if p['case']['id'] == 'f7ee4528-fixed-candidate' and
                p['allocator'] == 'candidate')
    worlds = {}
    for side, arm in previous.capture.ARMS.items():
        run = capture['runs']['f7ee4528-fixed-candidate-candidate-' + arm + '-trace']
        require(run['result'] == winter['capture']['runs'][side]['result'] == pair['arms'][arm]['result'] and
                run['result']['placement_probe'] == dict(enabled=True, version=1), 'wrong selected world')
        late.check_settings(capture['builds'][arm]['settings'], arm)
        worlds[side] = dict(run=run, reach=pair['arms'][arm]['reach'])
    child = next(p for p in worlds['candidate']['run']['result']['lineages'] if p['id'] == CHILD)
    require((child['parent'], child['birth_tick'], child['column']) == (PARENT, BIRTH, 0), 'wrong selected child')
    require(next(s for s in worlds['candidate']['run']['result']['seeds'] if s['child_id'] == CHILD) ==
            dict(parent=PARENT, birth_tick=PURCHASE, end_tick=BIRTH, child_id=CHILD, column=0,
                 generation=3, species=0, outcome='germinated', lifetime_ecology_ticks=8192), 'wrong selected seed')
    return worlds


def family(result, root=PARENT):
    lives = {p['id']: p for p in result['lineages']}
    require(len(lives) == len(result['lineages']) and root in lives, 'invalid family census')
    for i, p in lives.items():
        if p['parent']:
            parent = lives.get(p['parent'])
            require(parent is not None and p['parent'] < i and parent['birth_tick'] < p['birth_tick'] and
                    parent['generation'] + 1 == p['generation'], 'invalid family ancestry')
    members = {root}
    for i in sorted(lives):
        if lives[i]['parent'] in members: members.add(i)
    return sorted(members)


def family_records(world):
    members = set(family(world['run']['result']))
    return [r for r in world['reach'] if r['seed'][0] in members]


def clear_columns(slots, lives):
    require(len(slots) == len(set(slots)) <= 8 and all(i in lives for i in slots), 'invalid stored census')
    return [c for c in range(28) if all(abs(c - lives[i]['column']) >= 3 for i in slots)]


def choose(random, columns, blocked):
    require(type(random) is int and 0 <= random <= 0xffffffff and len(columns) in (6, 14) and
            all(type(c) is int and 0 <= c < 28 for c in columns) and type(blocked) is int and
            0 <= blocked < 1 << len(columns), 'invalid placement input')
    require(all(bool(blocked & (1 << i)) == bool(blocked & (1 << j)) for i, c in enumerate(columns)
                for j, other in enumerate(columns) if c == other), 'inconsistent alias spacing')
    clear = [i for i in range(len(columns)) if not blocked & (1 << i)]
    original = random % len(columns)
    return clear[(random // len(columns)) % len(clear)] if clear and blocked & (1 << original) else original


def decision(record, lives, wide):
    p, slots = record['purchase'], record['slots']
    tick = record['seed'][1]
    require(p['choices'] == late.support(p['origin'], p['dispersal'], wide and tick > late.AFTER),
            'wrong placement support')
    free = clear_columns(slots, lives)
    sites = late.sites_decode(p['sites'])
    require(all(bool(sites[c] & 32) == (c not in free) for c in range(28)), 'spacing map differs')
    columns = p['choices']
    blocked = sum(1 << i for i, c in enumerate(columns) if c not in free)
    clear = [i for i, c in enumerate(columns) if c in free]
    # The selector repeats after this many draws. Enumerate residues, not new
    # simulated outcomes or an invented value for the unrecorded random draw.
    period = len(columns) * max(1, len(clear))
    outcomes = [choose(r, columns, blocked) for r in range(period)]
    possible = sorted({columns[i] for i in outcomes})
    require(p['column'] in possible, 'observed landing impossible under placement rule')
    paths = sorted({'kept_original' if selected == r % len(columns) else 'redirected_blocked'
                    for r, selected in enumerate(outcomes) if columns[selected] == p['column']})
    return dict(parent=p['parent'], tick=tick, landing=p['column'], origin=p['origin'], trait=p['dispersal'],
                columns=columns, aliases={str(c): [i for i, col in enumerate(columns) if col == c]
                                         for c in sorted(set(columns))},
                stored=[dict(life=lives[i], dead=lives[i]['death_tick'] is not None and
                             lives[i]['death_tick'] <= tick) for i in slots],
                global_spacing_clear=free, clear_choice_indices=clear,
                clear_reachable=sorted(set(columns) & set(free)), blocked_choices=blocked,
                possible_selected_columns=possible, forced_column=len(possible) == 1,
                compatible_selected_indices=sorted({i for i in outcomes if columns[i] == p['column']}),
                random_draw=None, compatible_selector_paths=paths, selector_period=period,
                post_step_open=[c for c, mask in enumerate(sites) if mask == 0],
                post_step_landing_mask=sites[p['column']])


def check_raw(bundle, worlds):
    require(digest(bundle / 'manifest.json') == MANIFEST_SHA, 'wrong original raw manifest')
    manifest = json.loads((bundle / 'manifest.json').read_text())['artifacts']
    for name in ('capture.json', 'source.tar.gz'):
        require(digest(bundle / name) == previous.capture.NATIVE_FILES[name], 'raw source provenance changed')
    capture = json.loads((bundle / 'capture.json').read_text())
    require(archived_sources(bundle / 'source.tar.gz') == capture['source_sha256'], 'native source archive differs')
    for world in worlds.values():
        for kind in KINDS:
            item = world['run']['traces'][kind]
            path = (bundle / item['path']).resolve()
            require(path.is_relative_to(bundle.resolve()) and manifest.get(item['path']) == item['sha256'] and
                    digest(path) == item['sha256'], 'raw trace changed or escaped bundle')


def detail_keys(result, side):
    return {(s['parent'], s['birth_tick']) for s in result['seeds'] if side == 'candidate' and
            (s['child_id'] == CHILD or s['parent'] == CHILD)}


def extract(bundle, worlds):
    check_raw(bundle, worlds)
    rows = {}
    for side, world in worlds.items():
        run, result = world['run'], world['run']['result']
        # Reuse the whole-population checker, including sequential newborns,
        # dead stored occupants, every seed check and every purchase.
        all_reach = late.extract_reach(bundle, run, side == 'candidate')
        require(all_reach == world['reach'], 'full raw reach extraction differs from pinned history')
        wanted = detail_keys(result, side)
        details = {key: [] for key in wanted}
        context = []
        born = {}
        for p in result['lineages']: born.setdefault(p['birth_tick'], set()).add(p['id'])
        readers = [late.population.trace_rows(bundle / run['traces'][k]['path'], k, result) for k in ('stand', 'adult')]
        readers.append(late.reach_rows(bundle / run['traces']['reach']['path']))
        try:
            for stand, adult, reach in zip(*readers, strict=True):
                tick = reach['tick']
                require(tick == stand['tick'] == adult['tick'], 'excerpt clocks differ')
                slots = [i for i in stand['plant_order'] if i not in born.get(tick, set())]
                for check, receipt in zip(reach['checks'], adult['seeds'], strict=True):
                    key = check[0], tick - check[1] * STEP
                    if key in wanted:
                        details[key].append([tick, check, receipt, list(slots), adult['cold']])
                    if check[4] == 2: slots.append(check[5])
                if PURCHASE - STEP <= tick <= BIRTH:
                    context.append(dict(stand={k: stand[k] for k in ('tick', 'plant_order', 'reproduction', 'bodies')},
                                        adult=adult, reach=reach))
        finally:
            for reader in readers: reader.close()
        rows[side] = dict(family_reach=family_records(world), context=context,
                          details=[dict(seed=list(k), rows=details[k]) for k in sorted(details)],
                          full_reach_seeds=len(all_reach), full_reach_checks=sum(r['samples'] for r in all_reach))
        print(side + ': full reach inventory verified; placement/family receipts extracted', flush=True)
    return rows


def summarize_detail(seed, rows, purchase, lives):
    stop = seed['end_tick'] or STOP
    require(len(rows) == (stop - seed['birth_tick']) // STEP, 'incomplete selected seed checks')
    masks, mature, dormant, expired = Counter(), Counter(), 0, 0
    for n, item in enumerate(rows, 1):
        require(type(item) is list and len(item) == 5, 'invalid detailed seed row')
        tick, raw, receipt, slots, cold = item
        require(type(tick) is int and tick == seed['birth_tick'] + n * STEP and type(cold) is bool and
                type(raw) is list and len(raw) == 7 and late.population.adults.vector(raw[:6], 6, 0xffffffff) and
                type(receipt) is list and len(receipt) == 11 and
                late.population.adults.vector(receipt[:10], 10, 0xffffffff) and
                type(receipt[10]) is int and -1 <= receipt[10] <= 28,
                'invalid detailed seed clock/fields')
        parent, age, column, mask, outcome, child, encoded = raw
        expected = 0 if seed['end_tick'] != tick else {'expired': 1, 'germinated': 2}[seed['outcome']]
        require([parent, age, column] == [seed['parent'], n, seed['column']] and
                raw[:4] == receipt[:4] and raw[4:6] == receipt[8:10] and outcome == expected and
                child == (seed['child_id'] if outcome == 2 else 0) and len(slots) == receipt[6], 'seed check identity/fate differs')
        free = clear_columns(slots, lives)
        require(all(lives[i]['birth_tick'] <= tick for i in slots), 'future stored occupant')
        if outcome == 1:
            require(age == seed['lifetime_ecology_ticks'] and mask == 0 and encoded is None and
                    receipt[4:6] == [0, 0] and receipt[10] == -1, 'expiry is not a site check')
            expired += 1
            continue
        sites = late.sites_decode(encoded)
        calculated = ((age < 8) | ((receipt[4] < 12) << 1) | ((receipt[5] < 80) << 2) |
                      ((receipt[6] >= 8) << 3) | ((receipt[7] + 4 > 256) << 4) |
                      ((column not in free) << 5) | (cold << 6))
        require(age < seed['lifetime_ecology_ticks'] and mask == calculated and
                (mask & ~1) == sites[column] and all(bool(sites[c] & 32) == (c not in free) for c in range(28)) and
                ((mask == 0) == (outcome == 2)) and receipt[10] == sum(s == 0 for s in sites), 'seed site gates differ')
        masks[str(mask)] += 1
        if age < 8: dormant += 1
        else: mature[encoded] += 1
    all_mature = sum(mature.values())
    columns = set(purchase['choices'])
    return dict(seed=seed, checks=len(rows), dormant_checks=dormant, expiry_records=expired,
                mature_checks=all_mature, masks=dict(sorted(masks.items())), mature_sites=dict(sorted(mature.items())),
                checks_with={name: sum(n * predicate(late.sites_decode(s)) for s, n in mature.items())
                    for name, predicate in {
                        'global_open': lambda s: any(m == 0 for m in s),
                        'reachable_open': lambda s: any(s[c] == 0 for c in columns),
                        'global_spacing_clear': lambda s: any(not m & 32 for m in s),
                        'reachable_spacing_clear': lambda s: any(not s[c] & 32 for c in columns)}.items()},
                mature_blockers={b: sum(n * bool(late.sites_decode(s)[seed['column']] & (1 << i))
                                       for s, n in mature.items()) for i, b in enumerate(BLOCKERS)})


def family_summary(result):
    ids = family(result)
    lives = sorted((p for p in result['lineages'] if p['id'] in ids), key=lambda p: p['id'])
    seeds = [s for s in result['seeds'] if s['parent'] in ids]
    require(len({(s['parent'], s['birth_tick']) for s in seeds}) == len(seeds), 'duplicate family seed')
    for p in lives:
        require(p['seeds_created'] == sum(s['parent'] == p['id'] for s in seeds), 'family seed totals differ')
    children = {s['child_id'] for s in seeds if s['outcome'] == 'germinated'}
    require(children == set(ids) - {PARENT}, 'family child ledger differs')
    for s in seeds:
        require(s['outcome'] in ('expired', 'pending', 'germinated') and
                (s['end_tick'] is None) == (s['outcome'] == 'pending') and
                (s['child_id'] is None) == (s['outcome'] != 'germinated'), 'inconsistent seed censoring')
        if s['child_id'] is not None:
            p = next(p for p in lives if p['id'] == s['child_id'])
            require([s['parent'], s['end_tick'], s['column'], s['generation'], s['species']] ==
                    [p['parent'], p['birth_tick'], p['column'], p['generation'], p['species']], 'child seed identity differs')
    descendants = [p for p in lives if p['id'] != PARENT]
    def cohort(ps):
        return dict(ids=[p['id'] for p in ps], births=len(ps), deaths=sum(p['death_tick'] is not None for p in ps),
                    living=sum(p['death_tick'] is None for p in ps),
                    live_ticks=sum((p['death_tick'] or STOP) - p['birth_tick'] for p in ps),
                    live_ticks_since_purchase=sum(max(0, (p['death_tick'] or STOP) - max(p['birth_tick'], PURCHASE))
                                                  for p in ps))
    return dict(lives=lives, seeds=seeds, descendants=cohort(descendants),
                relative_generation_depth=max(p['generation'] for p in lives) - lives[0]['generation'],
                parent_purchases=sum(s['parent'] == PARENT for s in seeds),
                descendant_purchases=sum(s['parent'] != PARENT for s in seeds),
                seed_outcomes=dict(Counter(s['outcome'] for s in seeds)),
                per_parent=[dict(id=p['id'], purchases=p['seeds_created'],
                    seed_outcomes=dict(Counter(s['outcome'] for s in seeds if s['parent'] == p['id'])),
                    children=[c['id'] for c in descendants if c['parent'] == p['id']]) for p in lives])


def validate_context(rows, result):
    require([r['stand']['tick'] for r in rows] == list(range(PURCHASE - STEP, BIRTH + STEP, STEP)),
            'incomplete placement context')
    lives = {p['id']: p for p in result['lineages']}
    for r in rows:
        stand, adult, reach = r['stand'], r['adult'], r['reach']
        tick = stand['tick']
        require(tick == adult['tick'] == reach['tick'], 'context clock differs')
        slots = stand['plant_order']
        clear_columns(slots, lives)
        live = {i for i, p in lives.items() if p['birth_tick'] <= tick and (p['death_tick'] is None or p['death_tick'] > tick)}
        require(live <= set(slots) and {p['id'] for p in stand['bodies']} == live, 'context stored/live census differs')
        newborns = {i for i in live if lives[i]['birth_tick'] == tick}
        current = [i for i in slots if i not in newborns]
        for raw, receipt in zip(reach['checks'], adult['seeds'], strict=True):
            seed = next(s for s in result['seeds'] if [s['parent'], s['birth_tick']] == [raw[0], tick - raw[1] * STEP])
            require(raw[:4] == receipt[:4] and raw[4:6] == receipt[8:10] and len(current) == receipt[6] and
                    (seed['end_tick'] == tick) == bool(raw[4]), 'context sequential seed check differs')
            if raw[4] == 2: current.append(raw[5])
        require(current == slots and {p['parent'] for p in reach['purchases']} ==
                {v['id'] for v in stand['reproduction'] if v['produced']} ==
                {s['parent'] for s in result['seeds'] if s['birth_tick'] == tick}, 'context purchase inventory differs')
    return next(r for r in rows if r['stand']['tick'] == PURCHASE)


def analyze(rows, worlds):
    require(set(rows) == set(SIDES), 'wrong placement arm coverage')
    out = {}
    for side in SIDES:
        world, receipt = worlds[side], rows[side]
        result = world['run']['result']
        lives = {p['id']: p for p in result['lineages']}
        ledger = {(s['parent'], s['birth_tick']): s for s in result['seeds']}
        require(receipt['family_reach'] == family_records(world) and
                receipt['full_reach_seeds'] == len(ledger) and
                receipt['full_reach_checks'] == sum(r['samples'] for r in world['reach']), 'saved family/reach summary differs')
        context = validate_context(receipt['context'], result)
        purchases = {(r['seed'][0], r['seed'][1]): r for r in receipt['family_reach']}
        details = {tuple(r['seed']): r['rows'] for r in receipt['details']}
        require(len(details) == len(receipt['details']) and set(details) == detail_keys(result, side), 'wrong detailed seed panel')
        summaries = []
        for key, records in details.items():
            record = purchases[key]
            summary = summarize_detail(ledger[key], records, record['purchase'], lives)
            require(summary['checks'] == record['samples'] and
                    {s: n for s, n in summary['mature_sites'].items()} == record['mature_sites']['post'],
                    'selected raw checks disagree with pinned mature-site histogram')
            summaries.append(summary)
        decisions = [decision(r, lives, side == 'candidate') for r in receipt['family_reach']
                     if r['seed'][1] == PURCHASE]
        require([r['purchase'] for r in receipt['family_reach'] if r['seed'][1] == PURCHASE] ==
                [p for p in context['reach']['purchases'] if p['parent'] in family(result)], 'purchase context differs')
        out[side] = dict(family=family_summary(result), decisions=decisions, detailed_seeds=summaries,
                         purchase_context=context, window_purchases=[s for s in result['seeds']
                             if s['parent'] == PARENT and PURCHASE - STEP <= s['birth_tick'] <= BIRTH])
    return out


def check_value(value):
    require(value['provenance'] == provenance() and type(value['provenance']['native_runs']) is int and
            type(value['provenance']['training_runs']) is int, 'wrong placement information provenance')
    worlds = inputs()
    require(value['sources'] == {a: {k: worlds[a]['run']['traces'][k] for k in KINDS} for a in SIDES},
            'wrong placement trace sources')
    require(value['source_sha256'] == {p: digest(ROOT / p) for p in SOURCES}, 'analysis source differs')
    require(set(value['receipt_sha256']) == set(SIDES) and set(value['rows']) == set(SIDES) and
            all(value['receipt_sha256'][a] == fingerprint(value['rows'][a]) for a in SIDES), 'placement receipt checksum differs')
    require(value['analysis'] == analyze(value['rows'], worlds), 'placement information analysis differs')


def export(bundle, out):
    require(not out.exists() and not out.is_symlink(), 'fresh placement information output required')
    worlds = inputs()
    rows = extract(bundle, worlds)
    value = dict(provenance=provenance(), sources={a: {k: worlds[a]['run']['traces'][k] for k in KINDS} for a in SIDES},
                 source_sha256={p: digest(ROOT / p) for p in SOURCES}, rows=rows,
                 receipt_sha256={a: fingerprint(rows[a]) for a in SIDES}, analysis=analyze(rows, worlds))
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
        if args.bundle: require(extract(args.bundle, inputs()) == value['rows'], 'raw placement re-extraction differs')
        print('Verified placement information and family renewal offline.')
    else:
        export(args.bundle or ROOT / 'artifacts/garden-landing-late-dispersal-v1', args.out)
        print('Saved placement information audit; no simulations.')


if __name__ == '__main__':
    try: main()
    except (RuntimeError, ValueError, KeyError, TypeError, OSError, IndexError, StopIteration) as error:
        print('placement information audit failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
