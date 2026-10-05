#!/usr/bin/env python3
"""Reconstruct saved soil updates exactly, without executing native simulations."""

from __future__ import annotations

import argparse
from collections import Counter
from functools import cache
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tarfile

import garden_landing_drydown as previous
from garden_experiments import digest, source_files
from garden_resources import require

ROOT, STEP = previous.ROOT, previous.STEP
START, END, ARMS = previous.START, previous.END, previous.ARMS
RULE = 'garden-landing-soil-audit-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-soil-audit-protocol.md'
INPUT = 'benchmarks/garden-seasons/landing-drydown-results.json.gz'
INPUT_SHA = '2107de1ed88bef2ef66d8b168f4fd8d3338329b02c8dc8aff5b919aa487a6a29'
MANIFEST_SHA = 'affb9fd1765e438bbfa4d7a73017a750654c4ccf5475c629d5c52f09aee48ee9'
SOURCES = ('src/garden_world.c', 'src/garden_world.h', 'src/garden_climate.c',
           'src/garden_climate.h', 'sim/garden_evaluation.c', 'sim/garden_landing_cli.c',
           'sim/garden_landing_run.c')
STAGES = ('opening', 'rain', 'vertical', 'lateral', 'evaporation')
FIELDS = ('opening', 'rain', 'vertical_in', 'vertical_out', 'lateral_in', 'lateral_out',
          'evaporation', 'collected', 'closing')
RADII = (0, 1, 2, 4)
COLUMNS, ROWS, CELLS = 28, 11, 308


def text_sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


@cache
def load_input():
    require(digest(ROOT / INPUT) == INPUT_SHA, 'drying input changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream: value = json.load(stream)
    previous.check_value(value)
    return value


def check_implementation(implementation):
    require(set(implementation) == {'capture', 'files'} and set(implementation['files']) == set(SOURCES) and
            text_sha(implementation['capture']) == previous.NATIVE_FILES['capture.json'],
            'native implementation provenance changed')
    capture = json.loads(implementation['capture'])
    require(capture['build'] == {'binary': previous.NATIVE_FILES['bin/garden-landing'],
                                'cache': previous.NATIVE_FILES['CMakeCache.txt']} and
            capture['settings']['TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE'] == 'OFF', 'unsupported native build')
    require(all(text_sha(body) == capture['source_sha256'][name]
                for name, body in implementation['files'].items()), 'historical implementation text changed')


def implementation_from(bundle):
    require(digest(bundle / 'manifest.json') == MANIFEST_SHA, 'wrong drying bundle')
    native = bundle / 'native'
    previous.check_native(native)
    files = {}
    with tarfile.open(native / 'source.tar.gz', 'r:gz') as archive:
        for name in SOURCES:
            with archive.extractfile(name) as stream: files[name] = stream.read().decode('utf-8')
    value = {'capture': (native / 'capture.json').read_text(), 'files': files}
    check_implementation(value)
    return value


def mix32(bits):
    bits &= 0xffffffff
    bits ^= bits >> 16
    bits = bits * 0x7feb352d & 0xffffffff
    bits ^= bits >> 15
    bits = bits * 0x846ca68b & 0xffffffff
    return bits ^ (bits >> 16)


def weather(seed, tick):
    """tick is the ecology count, not a logic tick; all products wrap to u32."""
    require(type(seed) is int and 0 <= seed <= 0xffffffff and
            type(tick) is int and 0 <= tick <= 0xffffffff, 'invalid weather clock/seed')
    year, day = tick // 4096, tick // 256 % 16
    dry = mix32(seed ^ (year * 0x9e3779b9) ^ 0x64727931)
    start, duration = 4 + dry % 2, 2 + (dry >> 8) % (7 - (4 + dry % 2))
    drought = start <= day < start + duration
    bits = mix32(seed ^ (tick // 128) ^ 0x7261696e)
    rain_start, rain_length = 8 + bits % 81, 16 + (bits >> 8) % 17
    ungated = 2 + (bits >> 16) % 3 if seed and rain_start <= tick % 128 < rain_start + rain_length else 0
    return {'ecology_tick': tick, 'year': year, 'day': day, 'drought': drought,
            'ungated_rate': ungated, 'rate': 0 if drought else ungated}


def transfer(source, destination, limit, divisor):
    require(all(type(v) is int for v in (source, destination, limit, divisor)) and
            0 <= source <= 255 and 0 <= destination <= 255 and 0 < limit <= 255 and divisor > 0,
            'invalid water transfer')
    if destination == 255 or source <= destination + 1:
        return 0
    return min(max(1, (source - destination) // divisor), limit, 255 - destination)


def transition(opening, seed, tick):
    require(len(opening) == CELLS and all(type(v) is int and 0 <= v <= 255 for v in opening),
            'invalid soil grid')
    grid, grids, flows = list(opening), {'opening': list(opening)}, []
    w = weather(seed, tick)
    for cell in range(COLUMNS): grid[cell] = min(255, grid[cell] + w['rate'])
    grids['rain'] = grid.copy()

    def move(axis, source, destination, limit, divisor):
        a, b = grid[source], grid[destination]
        amount = transfer(a, b, limit, divisor)
        # All attempted edges, including blocked gradients, retain stage-local water.
        flows.append([axis, source, destination, a, b, amount])
        grid[source] -= amount
        grid[destination] += amount

    for row in range(ROWS - 1):
        for col in range(COLUMNS):
            move(0, row * COLUMNS + col, (row + 1) * COLUMNS + col, 12, 4)
    grids['vertical'] = grid.copy()
    for row in range(ROWS):
        for col in range(tick & 1, COLUMNS - 1, 2):
            a, b = row * COLUMNS + col, row * COLUMNS + col + 1
            source, dest = (a, b) if grid[a] >= grid[b] else (b, a)
            move(1, source, dest, 4, 8)
    grids['lateral'] = grid.copy()
    if tick % 4 == 0:
        for cell in range(COLUMNS): grid[cell] = max(0, grid[cell] - 1)
    grids['evaporation'] = grid.copy()
    require(sum(grids['rain']) == sum(grids['vertical']) == sum(grids['lateral']),
            'transport did not conserve water')
    return {'weather': w, 'grids': grids, 'flows': flows}


def decode(text):
    values = list(bytes.fromhex(text))
    require(len(values) == CELLS, 'wrong recorded soil size')
    return values


def footprint(row, identity):
    return {r[4] * COLUMNS + r[3] for r in row['roots'] if r[1] == identity}


def region(cells, radius):
    require(bool(cells) and radius in RADII, 'invalid soil region')
    return {i for i in range(CELLS) if min(abs(i % COLUMNS - j % COLUMNS) +
            abs(i // COLUMNS - j // COLUMNS) for j in cells) <= radius}


def collected(row):
    cells = [Counter() for _ in range(CELLS)]
    for r in row['roots']: cells[r[4] * COLUMNS + r[3]][str(r[1])] += r[7]
    return cells


def balance(value):
    require(value['opening'] + value['rain'] + value['vertical_in'] + value['lateral_in'] -
            value['vertical_out'] - value['lateral_out'] - value['evaporation'] - value['collected'] ==
            value['closing'], 'soil account does not close')


def account(rows, reconstructed, start, cells):
    require(START <= start < END and start % STEP == 0, 'invalid soil account start')
    n = (start - START) // STEP
    opening, closing = decode(rows[n]['soil_after']), decode(rows[-1]['soil_after'])
    ledger = [{'cell': i, 'opening': opening[i], 'closing': closing[i], 'consumers': Counter(),
               **dict.fromkeys(FIELDS[1:-1], 0)} for i in range(CELLS)]
    selected = list(zip(rows[n + 1:], reconstructed[n:], strict=True))
    for row, step in selected:
        grids, used = step['grids'], collected(row)
        for i, entry in enumerate(ledger):
            entry['rain'] += grids['rain'][i] - grids['opening'][i]
            entry['evaporation'] += grids['lateral'][i] - grids['evaporation'][i]
            entry['consumers'].update(used[i])
            entry['collected'] += sum(used[i].values())
        for axis, a, b, _, _, amount in step['flows']:
            name = 'vertical' if axis == 0 else 'lateral'
            ledger[a][name + '_out'] += amount
            ledger[b][name + '_in'] += amount
    for entry in ledger:
        balance(entry)
        entry['consumers'] = dict(entry['consumers'])
    regions = []
    for radius in RADII:
        included = region(cells, radius)
        totals = {k: sum(ledger[i][k] for i in included) for k in FIELDS}
        # Remove internal circulation from both sides of a regional boundary.
        for _, step in selected:
            for axis, a, b, _, _, amount in step['flows']:
                if a in included and b in included:
                    name = 'vertical' if axis == 0 else 'lateral'
                    totals[name + '_in'] -= amount
                    totals[name + '_out'] -= amount
        consumers = Counter()
        for i in included: consumers.update(ledger[i]['consumers'])
        balance(totals)
        regions.append({'radius': radius, 'cells': sorted(included), 'consumers': dict(consumers), **totals})
    all_soil = {k: sum(v[k] for v in ledger) for k in FIELDS}
    balance(all_soil)
    require(all_soil['vertical_in'] == all_soil['vertical_out'] and
            all_soil['lateral_in'] == all_soil['lateral_out'], 'whole-world transport imbalance')
    return {'start': start, 'end': END, 'cells': ledger, 'regions': regions, 'all_soil': all_soil}


def analyze_arm(saved):
    rows = saved['receipt']['uptake']
    result = saved['runs']['trace']['result']
    require(result['gardener'] is False and result['irrigation'] is False and result['rules'] == 0 and
            result['climate']['mode'] == 'seasonal' and
            not any(START <= p['birth_tick'] <= END for p in result['lineages']),
            'unsupported intervention or post-uptake germination')
    require([r['tick'] for r in rows] == list(range(START, END + STEP, STEP)), 'missing soil observation')
    identity, anchor = saved['analysis']['id'], saved['analysis']['anchor']
    cells = footprint(rows[0], identity)
    require(all(footprint(r, identity) == cells for r in rows), 'changed target footprint')
    adult = {r['tick']: r for r in saved['receipt']['adult']}
    require(all(adult[r['tick']]['soil_water'] == sum(decode(r['soil_after'])) for r in rows),
            'unaccounted post-uptake soil change')
    reconstructed, evidence = [], []
    for before, after in zip(rows, rows[1:]):
        step = transition(decode(before['soil_after']), int(result['seed'], 16), after['tick'] // STEP)
        require(step['grids']['evaporation'] == decode(after['soil_before']),
                'soil reconstruction differs at ' + str(after['tick']))
        require(adult[after['tick']]['season'] == step['weather']['day'] // 4, 'climate clock differs')
        reconstructed.append(step)
        evidence.append({'tick': after['tick'], 'weather': step['weather'],
                         'grids': {k: bytes(g).hex() for k, g in step['grids'].items()},
                         'boundary': [f for f in step['flows'] if (f[1] in cells) != (f[2] in cells)]})
    full = account(rows, reconstructed, START, cells)
    tail = account(rows, reconstructed, anchor, cells)
    target = tail['regions'][0]
    prior = saved['analysis']['post_anchor_water']
    require(target['collected'] == prior['taken'] and
            all(owner == str(identity) or amount == 0 for owner, amount in target['consumers'].items()),
            'target terminal uptake differs')
    depth = max(i // COLUMNS for i in cells)
    reservoirs = []
    for tick in sorted({anchor, END}):
        row = rows[(tick - START) // STEP]
        grid = decode(row['soil_after'])
        by_depth = [sum(grid[j * COLUMNS:(j + 1) * COLUMNS]) for j in range(ROWS)]
        reservoirs.append({'tick': tick, 'stage': 'after_uptake', 'total': sum(grid), 'by_depth': by_depth,
                           'target_cells': sum(grid[i] for i in cells), 'deepest_root_row': depth,
                           'below_deepest_root': sum(by_depth[depth + 1:])})
    return {'id': identity, 'anchor': anchor, 'transitions': len(evidence), 'cell_transitions': len(evidence) * CELLS,
            'evidence': evidence, 'full': full, 'post_anchor': tail, 'reservoirs': reservoirs,
            'overflow': prior['overflow'], 'retained': prior['taken'] - prior['overflow']}


def edge_key(flow):
    return flow[0], min(flow[1:3]), max(flow[1:3])


def compare(arms):
    a, b = (arms[arm] for arm in ARMS)
    require(a['anchor'] == b['anchor'] and a['post_anchor']['regions'][0]['cells'] ==
            b['post_anchor']['regions'][0]['cells'], 'unmatched soil comparison')
    cells = set(a['post_anchor']['regions'][0]['cells'])
    delta = {k: b['post_anchor']['regions'][0][k] - a['post_anchor']['regions'][0][k] for k in FIELDS}
    balance(delta)
    delta['overflow'] = b['overflow'] - a['overflow']
    delta['retained'] = b['retained'] - a['retained']
    require(delta['retained'] == delta['collected'] - delta['overflow'], 'retained difference does not close')
    edges = {}
    for x, y in zip(a['evidence'], b['evidence'], strict=True):
        require(x['tick'] == y['tick'] and x['weather'] == y['weather'], 'unmatched external weather')
        if x['tick'] <= a['anchor']: continue
        left, right = ({edge_key(f): f for f in r['boundary']} for r in (x, y))
        require(left.keys() == right.keys(), 'boundary edge coverage differs')
        for key in left:
            transfers = [f[5] * (1 if f[2] in cells else -1) for f in (left[key], right[key])]
            edge = edges.setdefault(key, {'axis': key[0], 'cells': list(key[1:]), 'control': 0, 'candidate': 0,
                                          'changed_steps': 0, 'first_difference': None})
            for arm, amount in zip(ARMS, transfers, strict=True): edge[arm] += amount
            if transfers[0] != transfers[1]:
                edge['changed_steps'] += 1
                if edge['first_difference'] is None:
                    edge['first_difference'] = {'tick': x['tick'], 'control': left[key], 'candidate': right[key]}
    for e in edges.values(): e['delta'] = e['candidate'] - e['control']
    require(sum(e['delta'] for e in edges.values()) ==
            delta['vertical_in'] + delta['lateral_in'] - delta['vertical_out'] - delta['lateral_out'],
            'boundary differences do not close')
    return {'delta': delta, 'edges': [edges[k] for k in sorted(edges)]}


def analyze(value):
    out = []
    for case in value['cases']:
        arms = {arm: analyze_arm(case['arms'][arm]) for arm in ARMS}
        out.append({'case': case['case'], 'arms': arms, 'comparison': compare(arms)})
    return out


def check_value(value):
    require(value['rule'] == RULE and value['input_sha256'] == INPUT_SHA and
            value['protocol_sha256'] == digest(ROOT / PROTOCOL) and value['native_calls'] == value['training_runs'] == 0 and
            value['source_sha256'].get(PROTOCOL) == value['protocol_sha256'] and
            value['source_sha256'].get(INPUT) == INPUT_SHA, 'wrong soil audit provenance')
    check_implementation(value['implementation'])
    require(value['analysis'] == analyze(load_input()), 'soil audit analysis differs')


def export(bundle, out):
    require(not out.exists() and (out.is_relative_to(ROOT / 'artifacts') or not out.is_relative_to(ROOT)),
            'fresh soil audit output required')
    implementation = implementation_from(bundle)
    source = source_files()
    value = {'rule': RULE, 'input_sha256': INPUT_SHA, 'protocol_sha256': digest(ROOT / PROTOCOL),
             'native_calls': 0, 'training_runs': 0, 'source_sha256': source, 'implementation': implementation,
             'analysis': analyze(load_input())}
    check_value(value)
    require(source_files() == source, 'soil audit sources changed')
    out.parent.mkdir(parents=True, exist_ok=True)
    previous.population.order.recovery.founders.write_gzip(out, value)
    return value


def verify(path, bundle=None):
    with gzip.open(path, 'rt') as stream: value = json.load(stream)
    check_value(value)
    if bundle is not None:
        previous.verify(bundle)
        require(value['implementation'] == implementation_from(bundle), 'archived implementation differs')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--verify', type=Path)
    args = parser.parse_args()
    if args.verify:
        require(args.out is None, 'verify cannot export')
        verify(args.verify.resolve(), args.bundle.resolve() if args.bundle else None)
    else:
        require(args.out is not None, 'fresh output required')
        export((args.bundle or ROOT / 'artifacts/garden-landing-drydown-v1').resolve(), args.out.resolve())
    print('Verified 1728 soil transitions and their stage/edge accounts; zero native calls.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, StopIteration) as error:
        print('soil audit failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
