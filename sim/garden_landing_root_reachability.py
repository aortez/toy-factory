#!/usr/bin/env python3
"""Audit saved root construction and optimistic reach; never run a simulator."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from functools import cache
import gzip
import json
from pathlib import Path
import sys
import tarfile

import garden_landing_soil_audit as soil
from garden_experiments import digest, source_files
from garden_resources import require

ROOT, STEP, ARMS = soil.ROOT, soil.STEP, soil.ARMS
spending = soil.previous.spending
population, allocation = spending.population, spending.previous.previous
direction = allocation.direction
START = spending.START
RULE = 'garden-landing-root-reachability-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-root-reachability-protocol.md'
INPUT = 'benchmarks/garden-seasons/landing-soil-audit-results.json.gz'
INPUT_SHA = 'bd5066879c513a2d4af58773014d70d39da931584b40eafbe4f6d27d07898a55'
INPUTS = {INPUT: INPUT_SHA, soil.INPUT: soil.INPUT_SHA, **spending.INPUTS}
SOURCES = ('src/garden_world.c', 'src/garden_world.h', 'src/garden_agent.c',
           'src/garden_agent.h', 'src/garden_agent_neural.c', 'src/garden_landing.c',
           'sim/garden_landing_growth.c', 'sim/garden_landing_growth.h',
           'sim/garden_landing_neural.c', 'sim/garden_landing_neural.h', 'sim/garden_landing_run.c',
           'sim/garden_landing_plant_trace.c')
STEPS = ((-4, 5), (0, 6), (4, 5))
BASE_DEPTHS = (10, 9, 7)
ENERGY_COSTS, WATER_COSTS = (9, 8, 7), (5, 5, 4)


@cache
def inputs():
    require(all(digest(ROOT / name) == sha for name, sha in INPUTS.items()), 'reachability input changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream: value = json.load(stream)
    soil.check_value(value)
    return soil.previous.inputs(), soil.load_input(), value


def maximum_depth(species, stature):
    require(type(species) is int and 0 <= species < 3 and type(stature) is int and -2 <= stature <= 2,
            'invalid root species or stature')
    return min(16, max(3, BASE_DEPTHS[species] - stature))


def deepest_row(depth):
    require(type(depth) is int and 1 <= depth <= 16, 'invalid maximum depth')
    # Two initial roots start five pixels into the soil at segment depth one.
    return min(10, (5 + 6 * (depth - 1)) // 8)


@cache
def envelope(x, y, depth, limit):
    """Optimistic endpoint reach, no future collisions or spending assumptions."""
    require(all(type(v) is int for v in (x, y, depth, limit)) and
            8 <= x <= 231 and 144 <= y <= 231 and 1 <= depth <= limit <= 16,
            'invalid root envelope origin')
    layer, reached = {(x, y): ()}, {}
    for count in range(limit - depth + 1):
        following = {}
        for (px, py), path in sorted(layer.items()):
            cell = direction.root_cell(px, py)
            reached.setdefault(cell, (count, path, (px, py)))
            if depth + count == limit: continue
            for choice, (dx, dy) in enumerate(STEPS):
                dest = (px + dx, py + dy)
                if 8 <= dest[0] <= 231 and 144 <= dest[1] <= 231:
                    following.setdefault(dest, (*path, choice))
        layer = following
    return reached


def row_path(x, y, depth, limit, row):
    require(type(row) is int and 0 <= row <= 10, 'invalid target soil row')
    choices = [(steps, path, cell, at) for cell, (steps, path, at) in envelope(x, y, depth, limit).items()
               if cell // 28 >= row]
    if not choices: return None
    steps, path, cell, at = min(choices)
    return {'nodes': steps, 'path': list(path), 'cell': cell, 'at': list(at)}


def check_implementation(value):
    _, _, prior = inputs()
    require(value['capture'] == prior['implementation']['capture'] and set(value['files']) == set(SOURCES),
            'wrong root implementation provenance')
    capture = json.loads(value['capture'])
    require(all(soil.text_sha(body) == capture['source_sha256'][name]
                for name, body in value['files'].items()), 'historical root implementation changed')


def implementation_from(native):
    soil.previous.check_native(native)
    files = {}
    with tarfile.open(native / 'source.tar.gz', 'r:gz') as archive:
        for name in SOURCES:
            with archive.extractfile(name) as stream: files[name] = stream.read().decode('utf-8')
    value = {'capture': (native / 'capture.json').read_text(), 'files': files}
    check_implementation(value)
    return value


def sources(subjects):
    return [{'case': s['entry']['case']['id'], 'arm': arm, 'label': label, 'kind': kind,
             **s['entry']['arms'][arm]['runs'][label]['traces'][kind]}
            for s in subjects for arm in ARMS for label in spending.LABELS for kind in ('stand', 'direction')]


def selected_rows(path, kind, result, end):
    """Hash-pinned traces: validate full framing, parse only the frozen window."""
    stop = result['tick']
    header = ({'schema': population.dawn.SCHEMA, 'node_limit': 32, 'budget_mode': 2} if kind == 'stand'
              else {'schema': 'landing-directions-v1'}) | {'start': STEP, 'stop': stop}
    with gzip.open(path, 'rt') as stream:
        require(json.loads(next(stream)) == header, 'wrong reachability trace header')
        for tick in range(STEP, stop + STEP, STEP):
            line = next(stream)
            require(line.startswith('{"tick":' + str(tick) + ','), 'missing or reordered trace clock')
            if START <= tick <= end: yield json.loads(line)
        require(json.loads(next(stream)) == {'complete': True, 'tick': stop, 'run_hash': result['run_hash']} and
                not stream.read(), 'incomplete reachability trace')


def extract(bundle):
    subjects, _, _ = inputs()
    require(digest(bundle / 'manifest.json') == spending.previous.MANIFEST_SHA and
            digest(bundle / 'results.json.gz') == spending.previous.INPUT_SHA, 'wrong allocation bundle')
    artifacts = json.loads((bundle / 'manifest.json').read_text())['artifacts']
    receipts = sources(subjects)
    for item in receipts:
        path = (bundle / item['path']).resolve()
        require(path.is_relative_to(bundle.resolve()) and artifacts.get(item['path']) == item['sha256'] and
                digest(path) == item['sha256'], 'raw root trace changed')

    def one(task):
        subject, arm = task
        saved = subject['entry']['arms'][arm]
        for kind in ('stand', 'direction'):
            require(saved['runs']['trace']['traces'][kind]['sha256'] ==
                    saved['runs']['repeat']['traces'][kind]['sha256'], 'root trace repeat differs')
        run, end = saved['runs']['trace'], subject['drying_anchor']['tick']
        streams = [selected_rows(bundle / run['traces'][k]['path'], k, saved['result'], end)
                   for k in ('stand', 'direction')]
        rows = []
        for stand, dd in zip(*streams, strict=True):
            require(stand['tick'] == dd['tick'] and len(stand['bids']) == len(dd['bids']) and
                    all((b['id'], b['tip']) == (d['id'], d['tip']) for b, d in
                        zip(stand['bids'], dd['bids'], strict=True)), 'stand/direction coverage differs')
            identity = subject['id']
            bodies = [b for b in stand['bodies'] if b['id'] == identity]
            require(len(bodies) == 1, 'missing selected living body')
            rows.append({'tick': stand['tick'], 'body': bodies[0],
                         'bids': [b for b in stand['bids'] if b['id'] == identity],
                         'directions': [d for d in dd['bids'] if d['id'] == identity]})
        print(subject['entry']['case']['id'] + '/' + arm + ': saved root history extracted', flush=True)
        return rows

    tasks = [(s, a) for s in subjects for a in ARMS]
    with ThreadPoolExecutor(max_workers=2) as workers: rows = list(workers.map(one, tasks))
    return [{'case': s['entry']['case']['id'], 'arms': dict(zip(ARMS, rows[2*i:2*i+2], strict=True))}
            for i, s in enumerate(subjects)]


def initial_roots(column):
    require(type(column) is int and 0 <= column < 28, 'invalid birth column')
    center = 8 + column * 8 + 4
    return [{'at': [center - 3, 149], 'depth': 1, 'active': True, 'parent': None},
            {'at': [center + 3, 149], 'depth': 1, 'active': True, 'parent': None}]


def advance_roots(roots, bid, observation, tick):
    selected = [i for i, r in enumerate(roots) if r['at'] == observation['at'] and r['depth'] == bid['depth']]
    require(len(selected) == 1 and roots[selected[0]]['active'], 'selected root absent or closed')
    parent = selected[0]
    chosen, _, _ = direction.check_direction(bid, observation)
    if bid['action'] == 0: return None
    roots[parent]['active'] = False
    event = {'tick': tick, 'parent': parent, 'depth': bid['depth'], 'at': observation['at'],
             'nodes_before': bid['nodes'], 'stores': [bid['energy'], bid['water']],
             'cost': [bid['energy_gate']['cost'], bid['water_gate']['cost']], 'budget': bid['budget']}
    if bid['action'] == 1 and chosen is not None:
        require(bid['depth'] < bid['maximum_depth'], 'root exceeds controller depth limit')
        at = observation['candidates'][chosen][2:4]
        require(all((r['at'][0] - at[0])**2 + (r['at'][1] - at[1])**2 >= 9 for r in roots),
                'new endpoint collides with own roots')
        roots.append({'at': at, 'depth': bid['depth'] + 1, 'active': True, 'parent': parent})
        event.update(kind='extend', destination=at, choice=chosen)
    else:
        event.update(kind='finish', reason='maximum_depth' if bid['depth'] >= bid['maximum_depth'] else
                     'blocked' if not bid['available'] else 'policy_finish')
    return event


def analyze_arm(subject, arm, rows, drying):
    identity, anchor = subject['id'], subject['drying_anchor']['tick']
    life = spending.previous.index(subject['entry'], arm)[identity]['life']
    require(life['birth_tick'] == START and [r['tick'] for r in rows] == list(range(START, anchor + STEP, STEP)),
            'incomplete root history')
    roots, events, limits, vigor, counts, previous_body = initial_roots(life['column']), [], set(), set(), Counter(), None
    for n, row in enumerate(rows):
        require(set(row) == {'tick', 'bids', 'directions', 'body'}, 'wrong saved root row')
        tick, bids, dd, body = row['tick'], row['bids'], row['directions'], row['body']
        packed = subject['resources'][arm][n]
        resource = spending.previous.unpack(packed, life, tick)
        require(body['id'] == identity and body['species'] == life['species'] and
                body['nodes'] == resource['stages'][-1][4] and body['roots'] == resource['roots'] and
                all(b['id'] == identity for b in bids) and len(bids) == len(dd), 'body/bid/resource identity differs')
        cells = {direction.root_cell(*r['at']) for r in roots}
        for b, d in zip(bids, dd, strict=True):
            _, _, actual_cells = direction.check_direction(b, d)
            require(actual_cells == cells, 'reconstructed root coverage differs before growth')
            if b['tissue'] != 1: continue
            limits.add(b['maximum_depth']); vigor.add(b['energy_gate']['vigor'])
            require(any(r['at'] == d['at'] and r['depth'] == b['depth'] and r['active'] for r in roots),
                    'observed root tip absent from reconstruction')
            counts['root_bids'] += 1
            counts[('wait', 'extend', 'finish')[b['action']] + '_bids'] += 1
            for gate in population.GATES: counts[gate + '_denied'] += not b[gate]['allowed']
        if bids:
            sun_phase = (64 + tick // STEP) % 256
            # All forecast validators use the recorded seasonal strength on every bid.
            sun = [sun_phase, bids[0]['daylight_gate']['sun_strength']]
            population.check_growth({'tick': tick}, {'sun': sun, 'plants': [resource]}, life, bids, body,
                                    previous_body, subject['entry']['case']['guard'],
                                    priority_check=allocation.check_priority if arm == 'candidate' else None)
            winner = population.dawn.winner(bids, dawn=True)
            idx = next(i for i, b in enumerate(bids) if b['tip'] == winner['tip'])
            if winner['eligible'] and bids[idx]['tissue'] == 1:
                event = advance_roots(roots, bids[idx], dd[idx], tick)
                if event: events.append(event)
        else:
            require(resource['stages'][2] == resource['stages'][3], 'unobserved construction expense')
        require(len(roots) == body['roots'] and Counter(r['depth'] for r in roots if r['active']) ==
                Counter(t[2] for t in body['tips'] if t[1] == 1), 'reconstructed root body/tips differ')
        previous_body = body
    require(len(limits) == len(vigor) == 1, 'root limits or vigor changed')
    limit, v = next(iter(limits)), next(iter(vigor))
    stature = BASE_DEPTHS[life['species']] - limit
    require(maximum_depth(life['species'], stature) == limit, 'recorded depth outside species/genome limits')
    root_cells = Counter(direction.root_cell(*r['at']) for r in roots)
    for observation in drying['receipt']['uptake']:
        expected = Counter(r[4]*28 + r[3] for r in observation['roots'] if r[1] == identity)
        require(root_cells == expected, 'root endpoints differ from later uptake counts')
    actual_row = max(c // 28 for c in root_cells)
    reachable = {}
    for r in initial_roots(life['column']):
        for cell, witness in envelope(*r['at'], 1, limit).items():
            if cell not in reachable or witness < reachable[cell]: reachable[cell] = witness
    possible_row = max(c // 28 for c in reachable)
    require(possible_row == deepest_row(limit), 'envelope disagrees with vertical bound')
    reservoirs = []
    for tick in (anchor, soil.END):
        obs = next(r for r in drying['receipt']['uptake'] if r['tick'] == tick)
        grid = soil.decode(obs['soil_after'])
        reservoirs.append({'tick': tick, 'rows': [sum(grid[28*y:28*(y+1)]) for y in range(11)],
                           'total': sum(grid), 'below_actual': sum(grid[28*(actual_row+1):]),
                           'below_selected_limit': sum(grid[28*(possible_row+1):]),
                           'below_any_species_limit': sum(grid[28*(deepest_row(max(BASE_DEPTHS)+2)+1):]),
                           'within_optimistic_endpoint_envelope': sum(grid[c] for c in reachable),
                           'deeper_within_envelope': sum(grid[c] for c in reachable if c // 28 > actual_row)})
    opportunities = []
    for row in rows:
        for b, d in zip(row['bids'], row['directions'], strict=True):
            if b['tissue'] != 1: continue
            witness = row_path(*d['at'], b['depth'], limit, actual_row + 1) if actual_row < 10 else None
            if witness is None: continue
            count = witness['nodes']
            first = d['candidates'][witness['path'][0]]
            cost = [count * (ENERGY_COSTS[life['species']] - int(v > 0)), count * WATER_COSTS[life['species']]]
            opportunities.append({'tick': row['tick'], 'tip': b['tip'], 'path': witness,
                                  'construction_cost': cost, 'stores': [b['energy'], b['water']],
                                  'stores_cover_construction_only': b['energy'] >= cost[0] and b['water'] >= cost[1],
                                  'reserved_nodes_after': b['nodes'] + count + b['budget']['remaining'],
                                  'fits_reserved_body_budget': b['nodes'] + count + b['budget']['remaining'] <= 32,
                                  'first_endpoint_available': bool(first[7] & 2),
                                  'first_water_allowed': direction.water_allowed(b, first),
                                  'recorded_gates': {g: b[g]['allowed'] for g in population.GATES}})
    return {'life': life, 'samples': len(rows), 'maximum_depth': limit, 'inferred_stature': stature,
            'vigor': v, 'actual_deepest_row': actual_row, 'optimistic_deepest_row': possible_row,
            'counts': dict(counts), 'events': events, 'roots': roots, 'final_body': rows[-1]['body'],
            'reservoirs': reservoirs, 'deeper_opportunities': opportunities,
            'optimistic_cells': [{'cell': c, 'nodes_from_initial_root': w[0], 'path': list(w[1]), 'at': list(w[2])}
                                 for c, w in sorted(reachable.items())]}


def analyze(receipts):
    subjects, drying, _ = inputs()
    require(len(receipts) == len(subjects), 'wrong root case count')
    result = []
    for s, saved, dry in zip(subjects, receipts, drying['cases'], strict=True):
        require(saved['case'] == dry['case']['id'] == s['entry']['case']['id'] and set(saved['arms']) == set(ARMS),
                'wrong root case or arms')
        result.append({'case': s['entry']['case'], 'arms': {a: analyze_arm(s, a, saved['arms'][a], dry['arms'][a])
                                                         for a in ARMS}})
    return result


def check_value(value):
    subjects, _, _ = inputs()
    require(value['rule'] == RULE and value['inputs'] == INPUTS and value['raw_manifest_sha256'] ==
            spending.previous.MANIFEST_SHA and value['protocol_sha256'] == digest(ROOT / PROTOCOL) and
            value['source_sha256'].get(PROTOCOL) == value['protocol_sha256'] and
            all(value['source_sha256'].get(p) == sha for p, sha in INPUTS.items()) and
            value['native_calls'] == value['training_runs'] == 0 and value['traces'] == sources(subjects),
            'wrong root reachability provenance')
    check_implementation(value['implementation'])
    require(value['analysis'] == analyze(value['receipts']), 'root reachability analysis differs')


def export(bundle, native, out):
    require(not out.exists() and not out.is_symlink() and
            (out.is_relative_to(ROOT / 'artifacts') or not out.is_relative_to(ROOT)), 'fresh root audit output required')
    implementation = implementation_from(native)
    src = source_files()
    receipts = extract(bundle)
    value = {'rule': RULE, 'inputs': INPUTS, 'raw_manifest_sha256': spending.previous.MANIFEST_SHA,
             'protocol_sha256': digest(ROOT / PROTOCOL), 'source_sha256': src,
             'native_calls': 0, 'training_runs': 0, 'implementation': implementation,
             'traces': sources(inputs()[0]), 'receipts': receipts, 'analysis': analyze(receipts)}
    check_value(value)
    require(source_files() == src, 'root audit sources changed')
    out.parent.mkdir(parents=True, exist_ok=True)
    population.order.recovery.founders.write_gzip(out, value)
    return value


def verify(path, bundle=None):
    with gzip.open(path, 'rt') as stream: value = json.load(stream)
    check_value(value)
    if bundle is not None: require(extract(bundle) == value['receipts'], 'raw root observations differ')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--native', type=Path)
    parser.add_argument('--verify', type=Path)
    args = parser.parse_args()
    if args.verify:
        require(args.out is None and args.native is None, 'verify cannot export')
        verify(args.verify.resolve(), args.bundle.resolve() if args.bundle else None)
    else:
        require(args.out is not None, 'fresh output required')
        export((args.bundle or ROOT / 'artifacts/garden-landing-root-allocation-v1').resolve(),
               (args.native or ROOT / 'artifacts/garden-landing-drydown-v1/native').resolve(), args.out.resolve())
    print('Verified saved root construction and reachability bounds; zero native calls.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, StopIteration) as error:
        print('root reachability audit failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
