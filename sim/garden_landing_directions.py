#!/usr/bin/env python3
"""Observe legal construction alternatives in four frozen worlds, without policy changes."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from functools import cache
import gzip
import json
from pathlib import Path
import shutil
import sys

import garden_landing_uptake as uptake
from garden_experiments import compress, digest, snapshot_sources, source_files, write_json
from garden_landing_energy_audit import archived_sources
from garden_resources import require

population, previous = uptake.population, uptake.previous
ROOT, STEP, STOP = uptake.ROOT, uptake.STEP, uptake.STOP
RULE = 'garden-landing-directions-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-directions-protocol.md'
INPUT = 'benchmarks/garden-seasons/landing-uptake-results.json.gz'
INPUT_SHA = 'ec0b4901a23a3cb449fc77b5eba79e982a94ca9bf837aa0ad9b1d909d3dd9f74'
INPUTS = {INPUT: INPUT_SHA, **uptake.INPUTS}
STEPS = (((-5, -5), (-3, -6), (0, -7), (3, -6), (5, -5)), ((-4, 5), (0, 6), (4, 5)))


@cache
def inputs():
    require(all(digest(ROOT / name) == sha for name, sha in INPUTS.items()), 'direction inputs changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream:
        value = json.load(stream)
    uptake.check_value(value)
    return previous.cases()


def root_cell(x, y):
    require(8 <= x <= 231 and 144 <= y <= 231, 'root endpoint outside soil')
    return ((y - 144) // 8) * 28 + (x - 8) // 8


def own_cells(direction):
    data = bytes.fromhex(direction['root_cells'])
    require(len(data) == 39 and data[-1] < 16, 'wrong root bitmap or padding')
    return {i for i in range(308) if data[i // 8] & (1 << (i % 8))}


def check_direction(bid, direction):
    require(set(direction) == {'id', 'tip', 'at', 'order', 'candidates', 'root_cells'} and
            (bid['id'], bid['tip']) == (direction['id'], direction['tip']), 'bid/direction identity differs')
    candidates, order = direction['candidates'], direction['order']
    steps = STEPS[bid['tissue']]
    require(len(candidates) == len(steps) and len(direction['at']) == 2 and
            all(type(v) is int for v in direction['at']), 'wrong candidates/tip')
    x, y = direction['at']
    root = bid['tissue'] == 1
    require(8 <= x <= 231 and (144 if root else 32) <= y <= (231 if root else 144), 'tip outside habitat')
    cells = own_cells(direction)
    require(0 < len(cells) <= bid['roots'], 'root coverage count differs')
    if root:
        require(root_cell(x, y) in cells, 'root tip absent from coverage')
    for c, step in zip(candidates, steps, strict=True):
        require(isinstance(c, list) and len(c) == 8 and all(type(v) is int for v in c) and
                tuple(c[:2]) == step and all(0 <= v <= 255 for v in c[2:]), 'malformed canonical candidate')
        dx, dy, cx, cy, light, moisture, clearance, flags = c
        inside = 8 <= x + dx <= 231 and (144 if root else 32) <= y + dy <= (231 if root else 144)
        require(flags <= 15 and bool(flags & 1) == inside, 'candidate bounds differ')
        if not inside:
            require(c[2:] == [0] * 6, 'out-of-bounds candidate has fields')
        else:
            require([cx, cy] == [x + dx, y + dy] and bool(flags & 2) == (clearance >= 9) and
                    bool(flags & 12) == (clearance < 9) and
                    (light == 0 if root else moisture == 0 and light >= 24), 'candidate semantics differ')
    available = [j for j, c in enumerate(candidates) if c[7] & 2]
    require(len(available) == bid['available'] and
            (sorted(order) == list(range(len(steps))) if bid['action'] == 1 else order == []), 'ranking/availability differs')
    chosen = next((j for j in order if j in available), None)
    expected = None if chosen is None else [*candidates[chosen][2:4], candidates[chosen][5]]
    require(expected == bid['water_gate']['destination'], 'selected endpoint differs from historical trace')
    return chosen, available, cells


def water_allowed(bid, candidate):
    if not bid['water_gate']['active']:
        return True
    gate = bid['water_gate']
    wet = bid['tissue'] == 1 and candidate[5] >= gate['cost'] and candidate[5] > gate['tip_moisture']
    reserve = gate['upkeep'] * (1 if wet else 4)
    return bid['water'] >= gate['cost'] + reserve


def assess(event, life, arm):
    bids, directions = event['bids'], event['directions']
    require(type(event['tick']) is int and STEP <= event['tick'] <= STOP and event['tick'] % STEP == 0 and
            life['birth_tick'] <= event['tick'] < (life['death_tick'] or STOP + STEP) and
            event['sun'][0] == (64 + event['tick'] // STEP) % 256 and 24 <= event['sun'][1] <= 255,
            'construction outside lifetime/clock')
    require(event['id'] == life['id'] and event['resource']['id'] == life['id'] and
            event['body']['id'] == life['id'] and all(b['id'] == life['id'] for b in bids), 'event identity differs')
    population.check_growth({'tick': event['tick']}, {'sun': event['sun'], 'plants': [event['resource']]},
                            life, bids, event['body'], None, arm)
    require(len(bids) == len(directions), 'missing bid direction')
    checked = [check_direction(b, d) for b, d in zip(bids, directions, strict=True)]
    require(len({d['root_cells'] for d in directions}) == 1, 'own coverage changes between same-plant bids')
    winner = population.dawn.winner(bids, dawn=True)
    index = next(j for j, b in enumerate(bids) if b['tip'] == winner['tip'])
    b, d = bids[index], directions[index]
    require(winner['eligible'] and b['action'] != 0, 'unpaid event in construction panel')
    chosen, available, cells = checked[index]
    result = {'tip': b['tip'], 'tissue': b['tissue'], 'action': b['action'], 'chosen': chosen,
              'legal': len(available), 'nodes_before': b['nodes'],
              'out_of_bounds': sum(not c[7] & 1 for c in d['candidates']),
              'blocked_own': sum(bool(c[7] & 4) for c in d['candidates']),
              'blocked_foreign': sum(bool(c[7] & 8) for c in d['candidates']),
              'cost': [event['resource']['stages'][2][j] - event['resource']['stages'][3][j] for j in (0, 1)]}
    if b['action'] != 1 or chosen is None:
        result['closure'] = ('maximum_depth' if b['depth'] >= b['maximum_depth'] else
                             'blocked' if not available else 'policy_finish')
        return result
    require(water_allowed(b, d['candidates'][chosen]), 'chosen water gate differs')
    eligible = [j for j in available if water_allowed(b, d['candidates'][j])]
    c = d['candidates'][chosen]
    root = b['tissue'] == 1
    resource = 5 if root else 4
    quantum = (lambda n: min(n, (3, 3, 2)[life['species']])) if root else (lambda n: n // 64)
    result.update({'same_price_alternatives': len(eligible) - 1,
                   'selected_resource': c[resource], 'selected_quantum': quantum(c[resource]),
                   'better_resource': [j for j in eligible if d['candidates'][j][resource] > c[resource]],
                   'better_quantum': [j for j in eligible if quantum(d['candidates'][j][resource]) > quantum(c[resource])],
                   'legal_but_water_denied': len(available) - len(eligible),
                   'fallback_rank': d['order'].index(chosen)})
    if root:
        result['new_cell'] = root_cell(c[2], c[3]) not in cells
        result['new_cell_alternatives'] = [j for j in eligible if root_cell(*d['candidates'][j][2:4]) not in cells]
        result['new_cell_not_drier'] = [j for j in result['new_cell_alternatives'] if d['candidates'][j][5] >= c[5]]
    else:
        result['leaf'] = (b['depth'] + 1) % (2 if life['species'] == 0 else 1) == 0
    return result


def rollup(events, lives):
    groups = defaultdict(Counter)
    for e in events:
        a, life = e['assessment'], lives[e['id']]
        for key in ('all', 'founders' if life['generation'] == 0 else 'offspring', 'plant-' + str(e['id'])):
            g = groups[key + ('/root' if a['tissue'] else '/shoot')]
            g['paid'] += 1
            g['energy_cost'] += a['cost'][0]
            g['water_cost'] += a['cost'][1]
            for k in ('legal', 'out_of_bounds', 'blocked_own', 'blocked_foreign'):
                g[k] += a[k]
            if 'closure' in a:
                g['closure_' + a['closure']] += 1
                continue
            g['allocations'] += 1
            g['multiple_legal'] += a['legal'] > 1
            g['better_resource'] += bool(a['better_resource'])
            g['better_quantum'] += bool(a['better_quantum'])
            g['fallback'] += a['fallback_rank'] > 0
            g['legal_but_water_denied'] += a['legal_but_water_denied']
            g['night_allocations'] += e['sun'][0] >= 128
            g['unproductive_sky_allocations'] += e['sun'][1] < 64
            if a['tissue']:
                g['new_cell'] += a['new_cell']
                g['reuse_with_new_option'] += not a['new_cell'] and bool(a['new_cell_alternatives'])
                g['reuse_with_new_not_drier'] += not a['new_cell'] and bool(a['new_cell_not_drier'])
            else:
                g['leaf_allocations'] += a['leaf']
                g['better_leaf_quantum'] += a['leaf'] and bool(a['better_quantum'])
    return {k: dict(v) for k, v in sorted(groups.items())}


def check_analysis(analysis, saved, arm):
    lives = {p['id']: p for p in saved['result']['lineages']}
    events = analysis['events']
    require([(e['tick'], e['id']) for e in events] == sorted({(e['tick'], e['id']) for e in events}), 'reordered/duplicate event')
    for e in events:
        require(e['assessment'] == assess(e, lives[e['id']], arm), 'direction assessment differs')
    for p in saved['analysis']['plants']:
        selected = [e for e in events if e['id'] == p['life']['id']]
        for j, r in enumerate(('energy', 'water')):
            require(sum(e['assessment']['cost'][j] for e in selected) == p['resources'][r]['growth'], 'paid construction coverage differs')
        expected, prior = [], 4
        for change in p['body_changes']:
            n = change['body']['nodes']
            require(prior <= n <= prior + 1, 'unexpected historical allocation size')
            if n > prior:
                expected.append(change['tick'])
            prior = n
        require([e['tick'] for e in selected if 'closure' not in e['assessment']] == expected, 'allocation history coverage differs')
    require(analysis['summary'] == rollup(events, lives), 'direction summary differs')


def direction_rows(path, result):
    with gzip.open(path, 'rt') as stream:
        require(json.loads(next(stream)) == {'schema': 'landing-directions-v1', 'start': STEP, 'stop': STOP}, 'wrong direction header')
        for tick in range(STEP, STOP + STEP, STEP):
            row = json.loads(next(stream))
            require(set(row) == {'tick', 'bids'} and row['tick'] == tick, 'missing/reordered direction row')
            yield row
        require(json.loads(next(stream)) == {'complete': True, 'tick': STOP, 'run_hash': result['run_hash']} and not stream.read(), 'incomplete direction trace')


def analyze_raw(directory, saved, arm, run):
    events, counts = [], Counter()
    lives = {p['id']: p for p in saved['result']['lineages']}
    streams = [population.trace_rows(directory / run['traces'][k]['path'], k, saved['result']) for k in ('stand', 'adult')]
    stream = direction_rows(directory / run['traces']['direction']['path'], saved['result'])
    for stand, adult, row in zip(*streams, stream, strict=True):
        require(stand['tick'] == adult['tick'] == row['tick'] and len(stand['bids']) == len(row['bids']), 'direction stream/bid coverage differs')
        counts['frames'] += 1
        grouped, dd = defaultdict(list), defaultdict(list)
        for b, d in zip(stand['bids'], row['bids'], strict=True):
            check_direction(b, d)
            grouped[b['id']].append(b)
            dd[b['id']].append(d)
            counts['bids'] += 1
            counts['candidates'] += len(d['candidates'])
        bodies = {b['id']: b for b in stand['bodies']}
        for p in sorted(adult['plants'], key=lambda p: p['id']):
            if p['stages'][2][0] == p['stages'][3][0]:
                continue
            i = p['id']
            e = {'tick': row['tick'], 'id': i, 'sun': adult['sun'], 'bids': grouped[i], 'directions': dd[i],
                 'resource': p, 'body': bodies[i]}
            e['assessment'] = assess(e, lives[i], arm)
            events.append(e)
    analysis = {'counts': dict(counts), 'events': events, 'summary': rollup(events, lives)}
    check_analysis(analysis, saved, arm)
    return analysis


def arguments(case, arm, label):
    return population.arguments(case, arm, 'trace') + (['--direction-trace', 'direction.jsonl'] if label == 'on' else [])


def check_value(value):
    require(value['rule'] == RULE and value['inputs'] == INPUTS and value['full_replays'] == 8 and
            value['training_runs'] == 0 and value['protocol_sha256'] == digest(ROOT / PROTOCOL) and
            value['source_sha256'].get(PROTOCOL) == value['protocol_sha256'] and
            all(value['source_sha256'].get(k) == v for k, v in INPUTS.items()), 'wrong direction provenance')
    require(value['settings'] == previous.load_input()['settings'] and
            [e['case'] for e in value['cases']] == [e['case'] for e in inputs()], 'wrong direction panel/configuration')
    for entry, prior in zip(value['cases'], inputs(), strict=True):
        require(set(entry['arms']) == set(population.ARMS), 'missing direction arm')
        for arm, a in entry['arms'].items():
            saved = prior['arms'][arm]
            require(set(a['runs']) == {'on', 'off'}, 'missing observer ablation')
            for label, run in a['runs'].items():
                h = saved['runs']['trace']
                require(run['args'] == arguments(entry['case'], arm, label) and run['result'] == h['result'] and
                        run['frame']['sha256'] == h['frame']['sha256'] and
                        all(run['traces'][k]['sha256'] == h['traces'][k]['sha256'] for k in ('stand', 'adult')), 'direction observer changed history')
            require(a['analysis']['counts']['frames'] == STOP // STEP, 'incomplete direction coverage')
            check_analysis(a['analysis'], saved, arm)


def collect(build, out, jobs):
    panel = inputs()
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
    value = {'rule': RULE, 'inputs': INPUTS, 'full_replays': 8, 'training_runs': 0,
             'protocol_sha256': digest(ROOT / PROTOCOL), 'source_sha256': sources, 'settings': settings,
             'build': {'binary': digest(frozen), 'cache': digest(cache_path)}, 'cases': []}
    def capture(call):
        entry, arm, label = call
        case = entry['case']
        name = case['id'] + '-' + arm + '-' + label
        directory = out / name
        directory.mkdir()
        (directory / 'frames').mkdir()
        with (directory / 'model.tgl').open('xb') as stream:
            stream.write(population.load_model()[1])
        args = arguments(case, arm, label)
        result = population.order.training.native(frozen, directory, *args)
        write_json(directory / 'result.json', result)
        traces = {}
        for kind in ('stand', 'adult', *(['direction'] if label == 'on' else [])):
            file = args[args.index('--' + kind + '-trace') + 1]
            target = directory / (file + '.gz')
            compress(directory / file, target)
            traces[kind] = {'path': name + '/' + target.name, 'sha256': digest(target)}
        frame = args[args.index('--framebuffer') + 1]
        run = {'args': args, 'result': result, 'traces': traces,
               'frame': {'path': name + '/' + frame, 'sha256': digest(directory / frame)}}
        h = entry['arms'][arm]['runs']['trace']
        require(result == h['result'] and run['frame']['sha256'] == h['frame']['sha256'] and
                all(traces[k]['sha256'] == h['traces'][k]['sha256'] for k in ('stand', 'adult')), 'historical neutrality failed: ' + name)
        print(name + ': historical results, traces and pixels match', flush=True)
        return run
    calls = [(e, a, label) for e in panel for a in population.ARMS for label in ('on', 'off')]
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        captured = list(pool.map(capture, calls))
    it = iter(captured)
    for entry in panel:
        arms = {}
        for arm in population.ARMS:
            runs = {label: next(it) for label in ('on', 'off')}
            analysis = analyze_raw(out, entry['arms'][arm], arm, runs['on'])
            arms[arm] = {'runs': runs, 'analysis': analysis}
            print(entry['case']['id'] + '/' + arm + ': all directions verified', flush=True)
        value['cases'].append({'case': entry['case'], 'arms': arms})
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
        require(manifest['rule'] == RULE, 'wrong direction bundle')
        for name, sha in manifest['artifacts'].items():
            p = (directory / name).resolve()
            require(p.is_relative_to(directory) and digest(p) == sha, 'direction artifact changed')
        path = directory / 'results.json.gz'
    with gzip.open(path, 'rt') as stream:
        value = json.load(stream)
    check_value(value)
    if directory:
        require(archived_sources(directory / 'source.tar.gz') == value['source_sha256'] and
                digest(directory / 'protocol.md') == value['protocol_sha256'] and
                digest(directory / 'bin/garden-landing') == value['build']['binary'] and
                digest(directory / 'CMakeCache.txt') == value['build']['cache'], 'frozen direction source/build differs')
        for entry, saved in zip(value['cases'], inputs(), strict=True):
            for arm, a in entry['arms'].items():
                for run in a['runs'].values():
                    for item in (run['frame'], *run['traces'].values()):
                        require(manifest['artifacts'].get(item['path']) == item['sha256'], 'direction run/manifest differs')
                    raw = (directory / run['traces']['adult']['path']).parent / 'result.json'
                    require(json.loads(raw.read_text()) == run['result'], 'raw direction result differs')
                require(analyze_raw(directory, saved['arms'][arm], arm, a['runs']['on']) == a['analysis'], 'raw direction analysis differs')
                print(entry['case']['id'] + '/' + arm + ': raw directions verified', flush=True)
    print('Verified passive directions, historical neutrality and complete construction receipts.')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=ROOT / 'build-host')
    parser.add_argument('--out', type=Path, default=ROOT / 'artifacts/garden-landing-directions-v1')
    parser.add_argument('--jobs', type=int, choices=range(1, 5), default=2)
    parser.add_argument('--verify', type=Path)
    args = parser.parse_args()
    if args.verify:
        verify(args.verify.resolve())
    else:
        collect(args.build.resolve(), args.out.resolve(), args.jobs)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, TypeError, OSError, StopIteration) as error:
        print('direction diagnostic failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
