#!/usr/bin/env python3
"""Frozen root-only direction comparison with historical controls and exact repeats."""

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

import garden_landing_directions as direction
from garden_experiments import compress, digest, snapshot_sources, source_files, write_json
from garden_gallery import contact_sheet
from garden_landing_energy_audit import archived_sources
from garden_resources import require

population = direction.population
ROOT, STEP, STOP = direction.ROOT, direction.STEP, direction.STOP
RULE = 'garden-landing-root-direction-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-root-direction-protocol.md'
INPUT = 'benchmarks/garden-seasons/landing-directions-results.json.gz'
INPUT_SHA = 'ceb1b8a5ab527eb42b635d87b795c646a1afbed493b896917897ec7ef55dab63'
INPUTS = {INPUT: INPUT_SHA, **direction.INPUTS}
ARMS, LABELS = ('control', 'candidate'), ('trace', 'repeat')


@cache
def inputs():
    require(all(digest(ROOT / p) == sha for p, sha in INPUTS.items()), 'root direction inputs changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream:
        value = json.load(stream)
    direction.check_value(value)
    return value


def cases():
    return [{'id': e['case']['id'] + '-' + a, 'world': e['case'], 'guard': a}
            for e in inputs()['cases'] for a in ARMS]


def historical(case):
    return next(e for e in inputs()['cases'] if e['case'] == case['world'])['arms'][case['guard']]['runs']['on']


def arguments(case, arm, *, stop=STOP):
    require(case in cases() and arm in ARMS, 'wrong root direction call')
    return (population.arguments(case['world'], case['guard'], 'trace', stop=stop) +
            ['--direction-trace', 'direction.jsonl'] +
            (['--root-wet-direction'] if arm == 'candidate' else []))


def common_result(result, case, arm):
    value = dict(result)
    h = population.order.previous.placement.probe_hash(
        population.order.previous.placement.budget.probe_hash(value['base_run_hash'], 2), True)
    if case['world']['order'] == 'rotating':
        h = population.order.order_hash(h, population.order.AT)
    for tag in (b'GLF1', b'GLE1', b'GLN1', b'GLU1', b'GLD1',
                *([b'GLM1'] if case['guard'] == 'candidate' else [])):
        h = population.wrapped(h, tag)
    if arm == 'candidate':
        require(value.pop('root_wet_direction_probe', None) == {'version': 1} and
                value['run_hash'] == population.wrapped(h, b'GLW1'), 'wrong wet-direction identity')
        value['run_hash'] = h
    else:
        require('root_wet_direction_probe' not in value, 'unexpected wet-direction control')
    population.common_result(value, case['world'], case['guard'])
    return value


def plain_direction(d):
    return {k: v for k, v in d.items() if k != 'raw_order'}


def raw_pair(b, d, enabled):
    if not enabled:
        require('raw_order' not in d, 'extra raw order in historical schema')
        return b, d
    require('raw_order' in d, 'missing original model order')
    raw = plain_direction(d) | {'order': d['raw_order']}
    available = [j for j, c in enumerate(raw['candidates']) if c[7] & 2]
    chosen = next((j for j in raw['order'] if j in available), None)
    gate = dict(b['water_gate'])
    gate['destination'] = None if chosen is None else [*raw['candidates'][chosen][2:4], raw['candidates'][chosen][5]]
    gate['wet_root'] = bool(b['action'] == 1 and b['tissue'] == 1 and chosen is not None and
                            raw['candidates'][chosen][5] >= gate['cost'] and
                            raw['candidates'][chosen][5] > gate['tip_moisture'])
    gate['reserve'] = gate['upkeep'] * (1 if gate['wet_root'] else 4)
    gate['allowed'] = not gate['active'] or b['water'] >= gate['cost'] + gate['reserve']
    return b | {'water_gate': gate}, raw


def eligible(b):
    return (all(b[g]['allowed'] for g in population.GATES) and
            b['energy'] >= b['energy_gate']['cost'] and b['water'] >= b['water_gate']['cost'])


def check_bid(b, d, life, enabled):
    applied = plain_direction(d)
    after, _, _ = direction.check_direction(b, applied)
    raw, original = raw_pair(b, d, enabled)
    before, available, _ = direction.check_direction(raw, original)
    wanted = list(original['order'])
    if enabled and b['tissue'] == 1 and b['action'] == 1 and b['depth'] < b['maximum_depth'] and eligible(raw) and before is not None:
        limit = (3, 3, 2)[life['species']]
        best = before
        for c in original['order']:
            if (c in available and direction.water_allowed(raw, original['candidates'][c]) and
                    min(limit, original['candidates'][c][5]) > min(limit, original['candidates'][best][5])):
                best = c
        if best != before:
            wanted = [best] + [c for c in wanted if c != best]
    require(applied['order'] == wanted and eligible(raw) == eligible(b), 'wrong rewrite or changed eligibility')
    return {'changed': original['order'] != wanted, 'before': before, 'after': after}


def direction_rows(path, result, enabled):
    with (gzip.open(path, 'rt') if path.suffix == '.gz' else path.open()) as stream:
        schema = 'landing-root-directions-v1' if enabled else 'landing-directions-v1'
        require(json.loads(next(stream)) == {'schema': schema, 'start': STEP, 'stop': result['tick']}, 'wrong root direction header')
        for tick in range(STEP, result['tick'] + STEP, STEP):
            row = json.loads(next(stream))
            require(set(row) == {'tick', 'bids'} and row['tick'] == tick, 'missing/reordered direction frame')
            yield row
        require(json.loads(next(stream)) == {'complete': True, 'tick': result['tick'], 'run_hash': result['run_hash']}
                and not stream.read(), 'incomplete/trailing direction stream')


def streams(directory, run, enabled):
    result = run['result']
    readers = [population.trace_rows(directory / run['traces'][k]['path'], k, result) for k in ('stand', 'adult')]
    readers.append(direction_rows(directory / run['traces']['direction']['path'], result, enabled))
    try:
        yield from zip(*readers, strict=True)
    finally:
        for reader in readers: reader.close()


def check_change(e, life, guard):
    require(e['id'] == life['id'] and all(b['id'] == e['id'] for b in e['bids']) and
            life['birth_tick'] <= e['tick'] < (life['death_tick'] or STOP + STEP), 'wrong changed-bid identity')
    population.check_growth({'tick': e['tick']}, {'sun': e['sun'], 'plants': [e['resource']]},
                            life, e['bids'], e['body'], None, guard)
    changed = [b['tip'] for b, d in zip(e['bids'], e['directions'], strict=True) if check_bid(b, d, life, True)['changed']]
    winner = population.dawn.winner(e['bids'], dawn=True)
    require(changed and e['changed'] == changed and e['selected'] == winner and
            e['purchase_changed'] == (winner['eligible'] and winner['tip'] in changed), 'changed receipt differs')
    if e['purchase_changed']:
        require(e['resource']['stages'][2][4] + 1 == e['resource']['stages'][3][4], 'changed root not allocated')


def change_summary(changes, lives):
    groups = defaultdict(Counter)
    for e in changes:
        g = groups['founders' if lives[e['id']]['generation'] == 0 else 'offspring']
        g['rewritten_bids'] += len(e['changed'])
        g['changed_purchases'] += e['purchase_changed']
    return {k: dict(v) for k, v in sorted(groups.items())}


def check_directions(a, result, guard, enabled):
    require(a['counts']['frames'] == result['tick'] // STEP, 'incomplete direction coverage')
    lives = {p['id']: p for p in result['lineages']}
    changes = a['changes']
    require([(e['tick'], e['id']) for e in changes] == sorted({(e['tick'], e['id']) for e in changes}), 'reordered/duplicate changed receipt')
    for e in changes: check_change(e, lives[e['id']], guard)
    require(a['summary'] == change_summary(changes, lives) and
            a['counts']['rewritten_bids'] == sum(len(e['changed']) for e in changes) and
            a['counts']['changed_purchases'] == sum(e['purchase_changed'] for e in changes) and
            (enabled or not changes), 'rewrite coverage differs')
    purchases = [e for e in changes if e['purchase_changed']]
    target = a['first_purchase']
    require((target is None) == (not purchases), 'missing first changed purchase')
    if target:
        require(target['tick'] == min(e['tick'] for e in purchases) and
                any((e['tick'], e['id']) == (target['tick'], target['id']) for e in purchases), 'wrong first purchase')


def analyze_directions(directory, run, guard, enabled):
    lives = {p['id']: p for p in run['result']['lineages']}
    changes, counts, first = [], Counter(frames=0, bids=0, candidates=0, rewritten_bids=0, changed_purchases=0), None
    for stand, adult, row in streams(directory, run, enabled):
        require(stand['tick'] == adult['tick'] == row['tick'], 'stream tick mismatch')
        grouped, dd, rewrites = defaultdict(list), defaultdict(list), defaultdict(list)
        counts['frames'] += 1
        for b, d in zip(stand['bids'], row['bids'], strict=True):
            result = check_bid(b, d, lives[b['id']], enabled)
            grouped[b['id']].append(b)
            dd[b['id']].append(d)
            counts['bids'] += 1
            counts['candidates'] += len(d['candidates'])
            if result['changed']: rewrites[b['id']].append(b['tip'])
        changed_here = []
        for i in stand['plant_order']:
            if i not in rewrites: continue
            winner = population.dawn.winner(grouped[i], dawn=True)
            e = {'tick': row['tick'], 'id': i, 'sun': adult['sun'], 'bids': grouped[i], 'directions': dd[i],
                 'resource': next(p for p in adult['plants'] if p['id'] == i),
                 'body': next(p for p in stand['bodies'] if p['id'] == i), 'changed': rewrites[i],
                 'selected': winner, 'purchase_changed': winner['eligible'] and winner['tip'] in rewrites[i]}
            check_change(e, lives[i], guard)
            counts['rewritten_bids'] += len(rewrites[i])
            counts['changed_purchases'] += e['purchase_changed']
            if first is None and e['purchase_changed']: first = {'tick': row['tick'], 'id': i}
            changed_here.append(e)
        changes.extend(sorted(changed_here, key=lambda e: e['id']))
    value = {'counts': dict(counts), 'changes': changes, 'first_purchase': first, 'summary': change_summary(changes, lives)}
    check_directions(value, run['result'], guard, enabled)
    return value


def normalized_step(step, enabled):
    s, r, d = step
    pairs = [raw_pair(b, direction, enabled) for b, direction in zip(s['bids'], d['bids'], strict=True)]
    return {'stand': s | {'bids': [b for b, _ in pairs]}, 'adult': r,
            'direction': d | {'bids': [v for _, v in pairs]}}


def first_effect(directory, arms):
    target = arms['candidate']['directions']['first_purchase']
    prefix = hashlib.sha256()
    readers = [streams(directory, arms[a]['runs']['trace'], a == 'candidate') for a in ARMS]
    try:
        for control, candidate in zip(*readers, strict=True):
            a, b = normalized_step(control, False), normalized_step(candidate, True)
            if target and a['stand']['tick'] == target['tick']:
                effect = dict(target, matching_prior_samples=target['tick'] // STEP - 1,
                              prefix_sha256=prefix.hexdigest(), control=a,
                              candidate={'stand': candidate[0], 'adult': candidate[1], 'direction': candidate[2]})
                check_effect(effect, arms)
                return effect
            require(a == b, 'physical prefix changed before a different root purchase')
            prefix.update(json.dumps(a, sort_keys=True, separators=(',', ':')).encode())
        require(target is None, 'missing physical effect')
        return None
    finally:
        for reader in readers: reader.close()


def check_effect(effect, arms):
    target = arms['candidate']['directions']['first_purchase']
    require((effect is None) == (target is None), 'wrong first effect')
    if effect is None: return
    require({k: effect[k] for k in ('tick', 'id')} == target and
            effect['matching_prior_samples'] == effect['tick'] // STEP - 1 and
            len(effect['prefix_sha256']) == 64, 'first-effect boundary differs')
    a, t = effect['control'], effect['candidate']
    b = normalized_step((t['stand'], t['adult'], t['direction']), True)
    require(a['stand']['tick'] == b['stand']['tick'] == effect['tick'] and
            a['stand']['climate'] == b['stand']['climate'] and a['adult']['sun'] == b['adult']['sun'] and
            a['stand']['plant_order'] == b['stand']['plant_order'], 'unequal first-effect world')
    # Later plants in this step may already observe the newly placed root.
    n = max(j for j, bid in enumerate(a['stand']['bids']) if bid['id'] == effect['id']) + 1
    require(a['stand']['bids'][:n] == b['stand']['bids'][:n] and
            a['direction']['bids'][:n] == b['direction']['bids'][:n], 'unequal pre-purchase decisions')
    source = next(e for e in arms['candidate']['directions']['changes'] if
                  (e['tick'], e['id']) == (effect['tick'], effect['id']))
    for side in (a, t):
        bids = [v for v in side['stand']['bids'] if v['id'] == effect['id']]
        require(population.dawn.winner(bids, dawn=True) == source['selected'], 'first effect changed winning tip')
        p = next(p for p in side['adult']['plants'] if p['id'] == effect['id'])
        require(p['stages'] == source['resource']['stages'], 'first effect changed reserves/costs')


def resources(analysis):
    result = {}
    for kind in ('founders', 'offspring'):
        plants = [p for p in analysis['plants'] if (p['life']['generation'] == 0) == (kind == 'founders')]
        totals = {r: dict(sum((Counter(p['resources'][r]) for p in plants), Counter())) for r in ('energy', 'water')}
        result[kind] = {'resources': totals,
                        'last_roots': sum(p['last_body']['roots'] for p in plants),
                        'last_shoots': sum(p['last_body']['nodes'] - p['last_body']['roots'] for p in plants)}
    return result


def check_value(value):
    require(value['rule'] == RULE and value['inputs'] == INPUTS and value['full_replays'] == 16 and
            value['training_runs'] == 0 and value['protocol_sha256'] == digest(ROOT / PROTOCOL) and
            value['source_sha256'].get(PROTOCOL) == value['protocol_sha256'] and
            all(value['source_sha256'].get(p) == sha for p, sha in INPUTS.items()) and
            value['settings'] == inputs()['settings'], 'wrong root direction provenance')
    require([e['case'] for e in value['cases']] == cases(), 'wrong root direction panel')
    for entry in value['cases']:
        case = entry['case']
        require(set(entry['arms']) == set(ARMS), 'missing root direction arm')
        for arm, a in entry['arms'].items():
            common_result(a['result'], case, arm)
            require(a['result']['tick'] == STOP and set(a['runs']) == set(LABELS), 'wrong horizon/repeats')
            population.check_analysis(a['analysis'], a['result'])
            check_directions(a['directions'], a['result'], case['guard'], arm == 'candidate')
            require(a['metrics'] == population.metrics(a['result'], a['analysis']) and
                    a['resources'] == resources(a['analysis']), 'root direction metrics differ')
            for run in a['runs'].values():
                require(run['args'] == arguments(case, arm) and run['result'] == a['result'], 'wrong repeated call')
            x, y = [a['runs'][k] for k in LABELS]
            require(x['frame']['sha256'] == y['frame']['sha256'] and all(
                    x['traces'][k]['sha256'] == y['traces'][k]['sha256'] for k in ('stand', 'adult', 'direction')), 'repeat differs')
            if arm == 'control':
                h = historical(case)
                require(x['result'] == h['result'] and x['frame']['sha256'] == h['frame']['sha256'] and
                        all(x['traces'][k]['sha256'] == h['traces'][k]['sha256'] for k in ('stand', 'adult', 'direction')),
                        'historical root direction control changed')
        a, b = [entry['arms'][arm] for arm in ARMS]
        require(entry['comparison'] == population.comparison(a['metrics'], b['metrics']) and
                entry['birth_matching'] == population.matched_births(a['result'], b['result']), 'root comparison differs')
        check_effect(entry['first_effect'], entry['arms'])


def collect(build, out, jobs):
    inputs()
    require(not out.exists() and (out.is_relative_to(ROOT / 'artifacts') or not out.is_relative_to(ROOT)), 'fresh output required')
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
        write_json(directory / 'result.json', result)
        traces = {}
        for kind in ('stand', 'adult', 'direction'):
            file = args[args.index('--' + kind + '-trace') + 1]
            target = directory / (file + '.gz')
            compress(directory / file, target)
            traces[kind] = {'path': name + '/' + target.name, 'sha256': digest(target)}
        frame = args[args.index('--framebuffer') + 1]
        raw = (directory / frame).read_bytes()
        require(len(raw) == 115200 and f'{zlib.crc32(raw):08x}' == result['framebuffer_crc32'], 'wrong final pixels')
        run = {'args': args, 'result': result, 'traces': traces,
               'frame': {'path': name + '/' + frame, 'sha256': digest(directory / frame)}}
        write_json(directory / 'run.json', run)
        print(name + ': captured', flush=True)
        return run
    calls = [(c, a, label) for c in cases() for a in ARMS for label in LABELS]
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        captured = list(pool.map(capture, calls))
    it, gallery = iter(captured), []
    for case in cases():
        arms, frames = {}, []
        for arm in ARMS:
            runs = {label: next(it) for label in LABELS}
            run = runs['trace']
            common_result(run['result'], case, arm)
            analysis = population.analyze_receipts(*(out / run['traces'][k]['path'] for k in ('stand', 'adult')),
                                                    run['result'], case['guard'])
            observed = analyze_directions(out, run, case['guard'], arm == 'candidate')
            arms[arm] = {'runs': runs, 'result': run['result'], 'analysis': analysis, 'directions': observed,
                         'metrics': population.metrics(run['result'], analysis), 'resources': resources(analysis)}
            frames.append({'id': case['id'] + '-' + arm, 'framebuffer': run['frame']['path']})
            print(case['id'] + '/' + arm + ': receipts verified', flush=True)
        entry = {'case': case, 'arms': arms, 'first_effect': first_effect(out, arms),
                 'comparison': population.comparison(*(arms[a]['metrics'] for a in ARMS)),
                 'birth_matching': population.matched_births(*(arms[a]['result'] for a in ARMS))}
        value['cases'].append(entry)
        gallery.append(frames)
    value['gallery'] = contact_sheet(out, gallery)
    value['gallery']['sha256'] = digest(out / 'contact-sheet.png')
    check_value(value)
    require(source_files() == sources and digest(binary) == value['build']['binary'] and digest(cache_path) == value['build']['cache'], 'source/build changed during capture')
    population.order.recovery.founders.write_gzip(out / 'results.json.gz', value)
    write_json(out / 'manifest.json', {'rule': RULE, 'artifacts': {
        str(p.relative_to(out)): digest(p) for p in sorted(out.rglob('*')) if p.is_file()}})
    return value


def verify(path):
    directory = path if path.is_dir() else None
    if directory:
        manifest = json.loads((directory / 'manifest.json').read_text())
        require(manifest['rule'] == RULE, 'wrong root direction bundle')
        for name, sha in manifest['artifacts'].items():
            p = (directory / name).resolve()
            require(p.is_relative_to(directory) and digest(p) == sha, 'root direction artifact changed')
        path = directory / 'results.json.gz'
    with gzip.open(path, 'rt') as stream: value = json.load(stream)
    check_value(value)
    if directory:
        require(archived_sources(directory / 'source.tar.gz') == value['source_sha256'] and
                digest(directory / 'protocol.md') == value['protocol_sha256'] and
                digest(directory / 'bin/garden-landing') == value['build']['binary'] and
                digest(directory / 'CMakeCache.txt') == value['build']['cache'] and
                digest(directory / 'contact-sheet.png') == value['gallery']['sha256'], 'frozen root direction provenance differs')
        for entry in value['cases']:
            case = entry['case']
            for arm, a in entry['arms'].items():
                for run in a['runs'].values():
                    for item in (run['frame'], *run['traces'].values()):
                        require(manifest['artifacts'].get(item['path']) == item['sha256'], 'root run/manifest differs')
                    raw = (directory / run['traces']['adult']['path']).parent / 'result.json'
                    require(json.loads(raw.read_text()) == run['result'], 'raw result differs')
                run = a['runs']['trace']
                require(population.analyze_receipts(*(directory / run['traces'][k]['path'] for k in ('stand', 'adult')),
                        a['result'], case['guard']) == a['analysis'] and
                        analyze_directions(directory, run, case['guard'], arm == 'candidate') == a['directions'], 'raw root analysis differs')
            require(first_effect(directory, entry['arms']) == entry['first_effect'], 'raw first effect differs')
            print(case['id'] + ': raw verified', flush=True)
    print('Verified root-only direction comparison, exact controls/repeats and complete receipts.')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=ROOT / 'build-host')
    parser.add_argument('--out', type=Path, default=ROOT / 'artifacts/garden-landing-root-direction-v1')
    parser.add_argument('--jobs', type=int, choices=range(1, 5), default=2)
    parser.add_argument('--verify', type=Path)
    args = parser.parse_args()
    if args.verify: verify(args.verify.resolve())
    else: collect(args.build.resolve(), args.out.resolve(), args.jobs)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, TypeError, OSError, StopIteration) as error:
        print('root direction comparison failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
