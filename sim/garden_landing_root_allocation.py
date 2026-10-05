#!/usr/bin/env python3
"""Frozen focal root allocation comparison; sixteen calls, no adaptive search."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from functools import cache
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zlib

import garden_landing_root_direction as previous
from garden_experiments import compress, digest, snapshot_sources, source_files, write_json
from garden_gallery import contact_sheet
from garden_landing_energy_audit import archived_sources
from garden_resources import require

population, direction = previous.population, previous.direction
ROOT, STEP, STOP = previous.ROOT, previous.STEP, previous.STOP
ARMS, LABELS = previous.ARMS, previous.LABELS
RULE = 'garden-landing-root-allocation-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-root-allocation-protocol.md'
INPUT = 'benchmarks/garden-seasons/landing-root-direction-results.json.gz'
INPUTS = {INPUT: '18f81abb8f76fc0a2fb4bf1e86b6b659984cadc9b2f507382187075a56b9122b',
          'benchmarks/garden-seasons/landing-population-audit-results.json.gz':
          'c40da0fc11e0a9e7cb1480faa0cbaaa328c758ddea8681d7f8981084244cf461', **previous.INPUTS}
FOCAL = dict(version=1, lineage=9, birth_tick=403365, parent=4, generation=1, column=24, species=1)


@cache
def inputs():
    require(all(digest(ROOT / p) == sha for p, sha in INPUTS.items()), 'allocation inputs changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream:
        value = json.load(stream)
    previous.check_value(value)
    return value


def cases():
    return [e['case'] for e in inputs()['cases']]


def historical(case):
    return next(e for e in inputs()['cases'] if e['case'] == case)['arms']['control']['runs']['trace']


def arguments(case, arm, *, stop=STOP):
    require(case in cases() and arm in ARMS, 'wrong allocation call')
    return previous.arguments(case, 'control', stop=stop) + (['--root-allocation-focal'] if arm == 'candidate' else [])


def allocation_hash(base):
    data = b'GLA1' + int(base, 16).to_bytes(4, 'little')
    data += b''.join(v.to_bytes(4, 'little') for v in FOCAL.values())
    h = 2166136261
    for b in data: h = ((h ^ b) * 16777619) & 0xffffffff
    return f'{h:08x}'


def common_result(result, case, arm):
    value = dict(result)
    p = population.order.previous.placement
    h = p.probe_hash(p.budget.probe_hash(value['base_run_hash'], 2), True)
    if case['world']['order'] == 'rotating': h = population.order.order_hash(h, population.order.AT)
    for tag in (b'GLF1', b'GLE1', b'GLN1', b'GLU1', b'GLD1', *([b'GLM1'] if case['guard'] == 'candidate' else [])):
        h = population.wrapped(h, tag)
    if arm == 'candidate':
        require(value.pop('root_allocation_probe', None) == FOCAL and value['run_hash'] == allocation_hash(h),
                'wrong focal allocation identity')
        value['run_hash'] = h
    else:
        require('root_allocation_probe' not in value, 'allocation enabled in control')
    previous.common_result(value, case, 'control')
    return value


def focal_life(result):
    life = next(p for p in result['lineages'] if p['id'] == FOCAL['lineage'])
    require(all(life[k] == FOCAL[k] for k in ('birth_tick', 'parent', 'generation', 'column', 'species')),
            'focal ancestry/site changed')
    return life


def check_priority(b, life, tick, resource, ordinary):
    """Independent arithmetic; population validators check all spending forecasts first."""
    active = (life['id'] == FOCAL['lineage'] and life['birth_tick'] == FOCAL['birth_tick'] and
              tick > life['birth_tick'] and (life['death_tick'] is None or tick < life['death_tick']))
    if life['id'] == FOCAL['lineage'] and life['birth_tick'] == FOCAL['birth_tick']:
        require(all(life[k] == FOCAL[k] for k in ('parent', 'generation', 'column', 'species')),
                'wrong focal identity in bid')
    eligible = (b['tissue'] == 1 and b['action'] == 1 and b['depth'] < b['maximum_depth'] and
                b['budget']['allocates'] and previous.eligible(b))
    income = resource['uptake'][1][1] if resource['uptake'] else 0
    destination = b['water_gate']['destination']
    prefer = bool(active and eligible and destination is not None and destination[2] > 0 and
                  4 * income <= b['water_gate']['upkeep'] and
                  4 * b['energy_gate']['income'] >= b['energy_gate']['maintenance'])
    require(b.get('allocation') == dict(active=active, eligible=eligible, prefer=prefer, water_income=income),
            'allocation predicate differs')
    return max(ordinary, 32765) if prefer else ordinary


def plain_bid(b):
    # Allocation excludes birth; preserve the historical birth-root priority.
    return {k: (b['raw_priority'] if k == 'priority' and b.get('allocation', {}).get('prefer') else v)
            for k, v in b.items() if k != 'allocation'}


def choices(bids):
    if not bids: return None, None
    return (population.dawn.winner([plain_bid(b) for b in bids], dawn=True),
            population.dawn.winner(bids, dawn=True))


def check_frame(frame, life, guard, enabled):
    tick, bids, body, resource = frame['tick'], frame['bids'], frame['body'], frame['resource']
    require(resource['id'] == life['id'] and all(b['id'] == life['id'] for b in bids), 'focal frame identity differs')
    if bids:
        population.check_growth({'tick': tick}, {'sun': frame['sun'], 'plants': [resource]},
                                life, bids, body, None, guard,
                                priority_check=check_priority if enabled else None)
    for b, d in zip(bids, frame['directions'], strict=True): direction.check_direction(b, d)
    before, after = choices(bids)
    require(frame['before'] == before and frame['after'] == after, 'allocation winner differs')
    return before != after


def analyze_allocation(directory, run, guard, enabled):
    lives = {p['id']: p for p in run['result']['lineages']}
    counts = Counter(frames=0, bids=0, boosted_bids=0, changed_choices=0)
    frames, first = [], None
    for s, r, d in previous.streams(directory, run, False):
        require(s['tick'] == r['tick'] == d['tick'], 'allocation stream ticks differ')
        counts['frames'] += 1
        rr = {p['id']: p for p in r['plants']}
        bb, dd = defaultdict(list), defaultdict(list)
        for b, endpoint in zip(s['bids'], d['bids'], strict=True):
            direction.check_direction(b, endpoint)
            life = lives[b['id']]
            if enabled:
                ordinary = b['priority'] if s['tick'] == life['birth_tick'] else b['raw_priority']
                require(check_priority(b, life, s['tick'], rr[b['id']], ordinary) == b['priority'], 'unvalidated boost')
            else: require('allocation' not in b, 'extra control receipt')
            counts['bids'] += 1
            counts['boosted_bids'] += b['priority'] != plain_bid(b)['priority']
            bb[b['id']].append(b)
            dd[b['id']].append(endpoint)
        i = FOCAL['lineage']
        if i in rr:
            before, after = choices(bb[i])
            frame = {'tick': s['tick'], 'sun': r['sun'], 'bids': bb[i], 'directions': dd[i],
                     'resource': rr[i], 'body': next((p for p in s['bodies'] if p['id'] == i), None),
                     'before': before, 'after': after}
            changed = check_frame(frame, lives[i], guard, enabled)
            counts['changed_choices'] += changed
            if changed and first is None: first = {'tick': s['tick'], 'id': i}
            frames.append(frame)
    return {'counts': dict(counts), 'first_choice': first, 'focal_frames': frames}


def focal_account(frames, life, stop, guard, enabled):
    end = min(stop, life['death_tick'] or stop)
    selected = [f for f in frames if f['tick'] <= end]
    require([f['tick'] for f in selected] == list(range(life['birth_tick'], end + STEP, STEP)),
            'incomplete focal exposure')
    resources, payments, shortages, events = population.adults.budget(), 0, [], []
    before = None
    for f in selected:
        check_frame(f, life, guard, enabled)
        r = f['resource']
        receipt = population.adults.transfers({'tick': f['tick'], **r}, life, before['stages'][-1] if before else None)
        population.adults.accumulate(resources, receipt, before is None)
        event = population.payment(r, receipt, before['roots'] if before else None, f['tick'], f['sun'][0])
        if event:
            payments += 1
            if any(event[k]['unpaid'] for k in ('energy', 'water')): shortages.append(event)
        chosen = f['after']
        if chosen and chosen['eligible']:
            b = next(b for b in f['bids'] if b['tip'] == chosen['tip'])
            if b['action'] != 0:
                events.append({'tick': f['tick'], 'tip': b['tip'], 'tissue': b['tissue'],
                               'action': b['action'], 'allocates': b['budget']['allocates']})
        before = r
    return {'end': end, 'samples': len(selected), 'payments': payments, 'resources': resources,
            'shortages': shortages, 'events': events,
            'unpaid': {k: sum(e[k]['unpaid'] for e in shortages) for k in ('energy', 'water')}}


def focal_summary(arm, guard, enabled, stop):
    life = focal_life(arm['result'])
    account = focal_account(arm['allocation']['focal_frames'], life, stop, guard, enabled)
    analysis = next(p for p in arm['analysis']['plants'] if p['life']['id'] == life['id'])
    seeds = [s for s in arm['result']['seeds'] if s['parent'] == life['id'] and s['birth_tick'] <= account['end']]
    children = [p for p in arm['result']['lineages'] if p['parent'] == life['id'] and p['birth_tick'] <= stop]
    flower = analysis['first_flower']
    return {'life': life, 'account': account, 'first_flower': flower if flower is not None and flower <= account['end'] else None,
            'first_seed': min((s['birth_tick'] for s in seeds), default=None), 'seeds': len(seeds),
            'children': {str(p['id']): population.survival(p, stop, 1) for p in children}}


def focal_comparison(arms, guard):
    # Equal exposure includes the earlier endpoint's final maintenance/death sample.
    end = min(focal_life(arms[a]['result'])['death_tick'] or STOP for a in ARMS)
    full = {a: focal_summary(arms[a], guard, a == 'candidate', STOP) for a in ARMS}
    equal = {a: focal_summary(arms[a], guard, a == 'candidate', end) for a in ARMS}
    x, y = full['control'], full['candidate']
    rates = {}
    for r in ('energy', 'water'):
        a, b = x['account'], y['account']
        delta = b['unpaid'][r] * a['payments'] - a['unpaid'][r] * b['payments']
        rates[r] = None if not a['payments'] or not b['payments'] else (delta > 0) - (delta < 0)
    survival = lambda v: v['life']['death_tick'] or STOP
    checks = {'no_earlier_death': survival(y) >= survival(x),
              'no_worse_energy_rate': rates['energy'] is not None and rates['energy'] <= 0,
              'retain_seeds': y['seeds'] >= x['seeds'],
              'retain_successful_offspring': sum(v == 'confirmed' for v in y['children'].values()) >=
                                             sum(v == 'confirmed' for v in x['children'].values())}
    return {'full': full, 'equal_exposure_end': end, 'equal': equal, 'rates': rates, 'checks': checks,
            'improves': rates['water'] == -1 or survival(y) > survival(x), 'passes': all(checks.values())}


def normalized(step):
    s, r, d = step
    return {'stand': s | {'bids': [plain_bid(b) for b in s['bids']]}, 'adult': r, 'direction': d}


def check_effect(effect, arms):
    target = arms['candidate']['allocation']['first_choice']
    require((effect is None) == (target is None), 'missing allocation effect')
    if effect is None: return
    require({k: effect[k] for k in ('tick', 'id')} == target and
            effect['matching_prior_samples'] == effect['tick'] // STEP - 1 and
            len(effect['prefix_sha256']) == 64, 'wrong allocation prefix')
    a, t = effect['control'], effect['candidate']
    b = normalized((t['stand'], t['adult'], t['direction']))
    require(a['stand']['tick'] == b['stand']['tick'] == effect['tick'] and
            a['stand']['climate'] == b['stand']['climate'] and a['adult']['sun'] == b['adult']['sun'] and
            a['stand']['plant_order'] == b['stand']['plant_order'], 'unequal allocation world')
    n = max(j for j, bid in enumerate(a['stand']['bids']) if bid['id'] == effect['id']) + 1
    require(a['stand']['bids'][:n] == b['stand']['bids'][:n] and
            a['direction']['bids'][:n] == b['direction']['bids'][:n], 'unequal pre-action observations')
    ra, rb = [next(p for p in side['adult']['plants'] if p['id'] == effect['id']) for side in (a, t)]
    require(ra['stages'][:3] == rb['stages'][:3] and ra['uptake'] == rb['uptake'], 'unequal pre-action resources')
    ab, bb = [[p for p in side['stand']['bids'] if p['id'] == effect['id']] for side in (a, t)]
    require(population.dawn.winner(ab, dawn=True) != population.dawn.winner(bb, dawn=True), 'unchanged first winner')


def first_effect(directory, arms):
    target = arms['candidate']['allocation']['first_choice']
    prefix = hashlib.sha256()
    readers = [previous.streams(directory, arms[a]['runs']['trace'], False) for a in ARMS]
    try:
        for x, y in zip(*readers, strict=True):
            a, b = normalized(x), normalized(y)
            if target and a['stand']['tick'] == target['tick']:
                effect = dict(target, matching_prior_samples=target['tick'] // STEP - 1,
                              prefix_sha256=prefix.hexdigest(), control=a,
                              candidate=dict(zip(('stand', 'adult', 'direction'), y, strict=True)))
                check_effect(effect, arms)
                return effect
            require(a == b, 'physical prefix changed before focal choice')
            prefix.update(json.dumps(a, sort_keys=True, separators=(',', ':')).encode())
        require(target is None, 'missing first allocation effect')
        return None
    finally:
        for r in readers: r.close()


def check_allocation(a, result, guard, enabled):
    frames = a['focal_frames']
    if result['tick'] >= FOCAL['birth_tick']:
        life = focal_life(result)
        focal_account(frames, life, result['tick'], guard, enabled)
    else: require(not frames, 'focal born early')
    changed = [f for f in frames if f['before'] != f['after']]
    require(a['first_choice'] == ({'tick': changed[0]['tick'], 'id': FOCAL['lineage']} if changed else None) and
            a['counts']['frames'] == result['tick'] // STEP and
            a['counts']['changed_choices'] == len(changed) and
            a['counts']['boosted_bids'] == sum(b['priority'] != plain_bid(b)['priority'] for f in frames for b in f['bids']) and
            (enabled or not changed), 'allocation coverage differs')


def conclusion(entries):
    return {'population_pairs_passing': sum(e['comparison']['passes_harm_screen'] for e in entries),
            'focal_pairs_passing': sum(e['focal']['passes'] for e in entries),
            'focal_pairs_improving': sum(e['focal']['improves'] for e in entries),
            'supports_broader_trial': all(e['comparison']['passes_harm_screen'] and e['focal']['passes'] for e in entries) and
                                     any(e['focal']['improves'] for e in entries)}


def check_value(value):
    require(value['rule'] == RULE and value['inputs'] == INPUTS and value['full_replays'] == 16 and
            value['training_runs'] == 0 and value['protocol_sha256'] == digest(ROOT / PROTOCOL) and
            value['source_sha256'].get(PROTOCOL) == value['protocol_sha256'] and
            all(value['source_sha256'].get(p) == sha for p, sha in INPUTS.items()) and
            value['settings'] == inputs()['settings'] and [e['case'] for e in value['cases']] == cases(), 'wrong allocation provenance/panel')
    for e in value['cases']:
        case = e['case']
        require(set(e['arms']) == set(ARMS), 'missing allocation arm')
        for arm, a in e['arms'].items():
            common_result(a['result'], case, arm)
            require(a['result']['tick'] == STOP and set(a['runs']) == set(LABELS), 'wrong allocation horizon/repeats')
            population.check_analysis(a['analysis'], a['result'])
            check_allocation(a['allocation'], a['result'], case['guard'], arm == 'candidate')
            require(a['metrics'] == population.metrics(a['result'], a['analysis']), 'allocation metrics differ')
            for run in a['runs'].values():
                require(run['args'] == arguments(case, arm) and run['result'] == a['result'], 'wrong repeated allocation call')
            x, y = [a['runs'][k] for k in LABELS]
            require(x['frame']['sha256'] == y['frame']['sha256'] and all(x['traces'][k]['sha256'] == y['traces'][k]['sha256']
                    for k in ('stand', 'adult', 'direction')), 'allocation repeat differs')
            if arm == 'control':
                h = historical(case)
                require(x['result'] == h['result'] and x['frame']['sha256'] == h['frame']['sha256'] and
                        all(x['traces'][k]['sha256'] == h['traces'][k]['sha256'] for k in ('stand', 'adult', 'direction')),
                        'historical allocation control changed')
            focal = focal_account(a['allocation']['focal_frames'], focal_life(a['result']), STOP, case['guard'], arm == 'candidate')
            p = next(p for p in a['analysis']['plants'] if p['life']['id'] == FOCAL['lineage'])
            require(all(focal[k] == p[k] for k in ('resources', 'samples', 'payments', 'shortages')), 'focal/population accounts differ')
        require(e['comparison'] == population.comparison(*(e['arms'][a]['metrics'] for a in ARMS)) and
                e['birth_matching'] == population.matched_births(*(e['arms'][a]['result'] for a in ARMS)) and
                e['focal'] == focal_comparison(e['arms'], case['guard']), 'allocation comparison differs')
        check_effect(e['first_effect'], e['arms'])
    require(value['conclusion'] == conclusion(value['cases']), 'allocation conclusion differs')


def analyze_run(out, run, guard, enabled):
    analysis = population.analyze_receipts(*(out / run['traces'][k]['path'] for k in ('stand', 'adult')),
                                          run['result'], guard, priority_check=check_priority if enabled else None)
    return analysis, analyze_allocation(out, run, guard, enabled)


def collect(build, out, jobs):
    inputs()
    require(not out.exists() and (out.is_relative_to(ROOT / 'artifacts') or not out.is_relative_to(ROOT)), 'fresh allocation output required')
    binary, cache_path = build / 'toy-factory-garden-landing', build / 'CMakeCache.txt'
    settings = population.order.previous.placement.budget.growth.water.check_build(cache_path)
    sources = source_files()
    out.mkdir(parents=True)
    (out / 'bin').mkdir()
    frozen = out / 'bin/garden-landing'
    shutil.copy2(binary, frozen)
    shutil.copy2(cache_path, out / 'CMakeCache.txt')
    shutil.copy2(ROOT / PROTOCOL, out / 'protocol.md')
    snapshot_sources(out, sources)
    value = {'rule': RULE, 'inputs': INPUTS, 'full_replays': 16, 'training_runs': 0,
             'protocol_sha256': digest(ROOT / PROTOCOL), 'source_sha256': sources, 'settings': settings,
             'build': {'binary': digest(frozen), 'cache': digest(cache_path)}, 'cases': []}
    write_json(out / 'capture.json', value)
    def capture(call):
        case, arm, label = call
        name = case['id'] + '-' + arm + '-' + label
        directory = out / name
        directory.mkdir()
        (directory / 'frames').mkdir()
        with (directory / 'model.tgl').open('xb') as stream: stream.write(population.load_model()[1])
        args = arguments(case, arm)
        result = population.order.training.native(frozen, directory, *args)
        common_result(result, case, arm)
        write_json(directory / 'result.json', result)
        traces = {}
        for kind in ('stand', 'adult', 'direction'):
            file = args[args.index('--' + kind + '-trace') + 1]
            target = directory / (file + '.gz')
            compress(directory / file, target)
            traces[kind] = {'path': name + '/' + target.name, 'sha256': digest(target)}
        frame = args[args.index('--framebuffer') + 1]
        raw = (directory / frame).read_bytes()
        require(len(raw) == 115200 and f'{zlib.crc32(raw):08x}' == result['framebuffer_crc32'], 'wrong allocation pixels')
        run = {'args': args, 'result': result, 'traces': traces,
               'frame': {'path': name + '/' + frame, 'sha256': digest(directory / frame)}}
        write_json(directory / 'run.json', run)
        print(name + ': captured', flush=True)
        return run
    calls = [(c, a, label) for c in cases() for a in ARMS for label in LABELS]
    with ThreadPoolExecutor(max_workers=jobs) as pool: captured = list(pool.map(capture, calls))
    it, gallery = iter(captured), []
    for case in cases():
        arms, frames = {}, []
        for arm in ARMS:
            runs = {label: next(it) for label in LABELS}
            run = runs['trace']
            analysis, observed = analyze_run(out, run, case['guard'], arm == 'candidate')
            arms[arm] = {'runs': runs, 'result': run['result'], 'analysis': analysis, 'allocation': observed,
                         'metrics': population.metrics(run['result'], analysis)}
            frames.append({'id': case['id'] + '-' + arm, 'framebuffer': run['frame']['path']})
            print(case['id'] + '/' + arm + ': receipts verified', flush=True)
        value['cases'].append({'case': case, 'arms': arms, 'first_effect': first_effect(out, arms),
                               'comparison': population.comparison(*(arms[a]['metrics'] for a in ARMS)),
                               'birth_matching': population.matched_births(*(arms[a]['result'] for a in ARMS)),
                               'focal': focal_comparison(arms, case['guard'])})
        gallery.append(frames)
    value['conclusion'] = conclusion(value['cases'])
    value['gallery'] = contact_sheet(out, gallery)
    value['gallery']['sha256'] = digest(out / 'contact-sheet.png')
    check_value(value)
    require(source_files() == sources and digest(binary) == value['build']['binary'] and digest(cache_path) == value['build']['cache'],
            'source/build changed during allocation capture')
    population.order.recovery.founders.write_gzip(out / 'results.json.gz', value)
    write_json(out / 'manifest.json', {'rule': RULE, 'artifacts': {
        str(p.relative_to(out)): digest(p) for p in sorted(out.rglob('*')) if p.is_file()}})
    return value


def verify(path):
    directory = path if path.is_dir() else None
    if directory:
        manifest = json.loads((directory / 'manifest.json').read_text())
        require(manifest['rule'] == RULE, 'wrong allocation bundle')
        for name, sha in manifest['artifacts'].items():
            p = (directory / name).resolve()
            require(p.is_relative_to(directory) and digest(p) == sha, 'allocation artifact changed')
        path = directory / 'results.json.gz'
    with gzip.open(path, 'rt') as stream: value = json.load(stream)
    check_value(value)
    if directory:
        require(archived_sources(directory / 'source.tar.gz') == value['source_sha256'] and
                digest(directory / 'protocol.md') == value['protocol_sha256'] and
                digest(directory / 'bin/garden-landing') == value['build']['binary'] and
                digest(directory / 'CMakeCache.txt') == value['build']['cache'] and
                digest(directory / 'contact-sheet.png') == value['gallery']['sha256'], 'allocation frozen provenance differs')
        for entry in value['cases']:
            for arm, a in entry['arms'].items():
                for run in a['runs'].values():
                    for item in (run['frame'], *run['traces'].values()):
                        require(manifest['artifacts'].get(item['path']) == item['sha256'], 'allocation run/manifest differs')
                    raw = (directory / run['traces']['adult']['path']).parent / 'result.json'
                    require(json.loads(raw.read_text()) == run['result'], 'allocation raw result differs')
                analysis, observed = analyze_run(directory, a['runs']['trace'], entry['case']['guard'], arm == 'candidate')
                require(analysis == a['analysis'] and observed == a['allocation'], 'allocation raw analysis differs')
            require(first_effect(directory, entry['arms']) == entry['first_effect'], 'allocation raw prefix differs')
            print(entry['case']['id'] + ': raw verified', flush=True)
    print('Verified focal allocation comparison, exact controls/repeats and complete receipts.')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=ROOT / 'build-host')
    parser.add_argument('--out', type=Path, default=ROOT / 'artifacts/garden-landing-root-allocation-v1')
    parser.add_argument('--jobs', type=int, choices=range(1, 5), default=2)
    parser.add_argument('--verify', type=Path)
    args = parser.parse_args()
    if args.verify: verify(args.verify.resolve())
    else: collect(args.build.resolve(), args.out.resolve(), args.jobs)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, TypeError, OSError, StopIteration) as error:
        print('root allocation comparison failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
