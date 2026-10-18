#!/usr/bin/env python3
"""Reconstruct recorded light and isolate one neighbor's same-state shadow."""

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

import garden_landing_cursor_shade_capture as capture
import garden_landing_uptake as light
from garden_resources import require

energy = capture.energy
ROOT, STEP, STOP = capture.ROOT, capture.STEP, capture.STOP
RULE = 'garden-landing-cursor-shade-v1'
MANIFEST_SHA = 'b713cd3f8804e61132bf0cdd4dcca3ae6703b9d1b66d37354b8755d72c5dda0d'
CAPTURE_SHA = '099e9969e196a5a542b1740f712965e107882059e02c04f4123f3db684335253'
ENERGY_INPUT = 'benchmarks/garden-seasons/landing-cursor-energy-results.json.gz'
ENERGY_SHA = '60d9d2d2a581cd1fd10183935eb21d1c549c077dbb8f9bf3ebbc0676b324664c'
FOCAL, NEIGHBOR = 37, 39
CRITICAL_START, CRITICAL_STOP = 1463640, 1470000


def inputs():
    require(capture.digest(ROOT / ENERGY_INPUT) == ENERGY_SHA, 'energy diagnosis changed')
    with gzip.open(ROOT / ENERGY_INPUT, 'rt') as stream:
        diagnosis = json.load(stream)
    return energy.load_input(), diagnosis


def without_neighbor(sources, neighbor=NEIGHBOR):
    # Rebuild from sources: subtracting from a saturated cell loses information.
    kept = tuple(tuple(s) for s in sources if s[1] != neighbor)
    return light.opacity(kept, 0, 'actual')


def validate_light(row, lives):
    require(set(row) == {'tick', 'sun', 'sources', 'roots', 'leaves', 'soil_before', 'soil_after', 'light'},
            'wrong uptake fields')
    tick = row['tick']
    require(type(tick) is int and tick > 0 and tick % STEP == 0 and
            type(row['sun']) is list and len(row['sun']) == 3 and
            all(type(v) is int for v in row['sun']), 'invalid uptake clock')
    phase, strength, ray = row['sun']
    require(phase == (64 + tick // STEP) % 256 and 24 <= strength <= 255 and
            ray == 12 - ((phase if phase <= 128 else 256 - phase) * 24 + 64) // 128,
            'invalid sun/ray')

    def alive(i):
        require(i in lives and lives[i]['birth_tick'] < tick, 'unknown or newborn absorber')
        return lives[i]['death_tick'] is None or lives[i]['death_tick'] >= tick

    sources = tuple(tuple(s) for s in row['sources'])
    require(len(sources) <= 256 and all(light.vector(list(s), 7, 0xffffffff) and
            s[0] < 256 and s[2] in (0, 1) and s[3] < 28 and s[4] < 14 and
            s[5] <= 255 and s[6] <= 255 for s in sources), 'invalid shade source')
    require([s[0] for s in sources] == sorted({s[0] for s in sources}), 'duplicate/unordered shade source')
    for source in sources:
        require(bool(source[2]) != alive(source[1]), 'wrong live/dead source')
    field = light.field(light.opacity(sources, 0, 'actual'), strength, ray)
    require(bytes(field).hex() == row['light'], 'light field reconstruction differs')
    require(len(row['leaves']) <= 256, 'too many leaves')
    seen, totals = set(), Counter()
    for leaf in row['leaves']:
        require(light.vector(leaf, 6, 0xffffffff), 'invalid leaf vector')
        node, owner, column, canopy_row, local, income = leaf
        require(node < 256 and node not in seen and alive(owner) and column < 28 and canopy_row < 14,
                'invalid leaf identity')
        seen.add(node)
        require(local == field[canopy_row * 28 + column] and income == local // 64,
                'leaf light/income differs')
        totals[owner] += income
    return totals


def analyze(rows, original, diagnosis):
    ticks = [t for first, last in capture.WINDOWS for t in range(first, last + STEP, STEP)]
    require(set(rows) == set(capture.ARMS) and all([r['tick'] for r in rows[a]] == ticks
            for a in capture.ARMS), 'missing/reordered window samples')
    lives = {a: {p['id']: p for p in energy.selected(original, a)['result']['lineages']}
             for a in capture.ARMS}
    resources = {a: {t: packed for t, packed in diagnosis['histories'][a]['rows']} for a in capture.ARMS}
    periods = {name: dict(samples=0, fixed=0, cursor=0, without_neighbor=0, residual_absolute=0,
                         income_gap_steps=0, leaf_gains={}, changed=[]) for name in ('establishment', 'winter')}
    source_matches = geometry_matches = matched = 0
    mismatches = []
    focal_coordinates = set()
    for fixed, cursor in zip(rows['fixed'], rows['cursor'], strict=True):
        tick = fixed['tick']
        totals = {}
        for arm, row in zip(capture.ARMS, (fixed, cursor), strict=True):
            _, phase, strength = energy.window.previous.sun_at(int(energy.CASE[:8], 16), tick)
            require(row['sun'][:2] == [phase, strength], 'weather differs from original history')
            totals[arm] = validate_light(row, lives[arm])
            focal_leaves = [l for l in row['leaves'] if l[1] == FOCAL]
            if tick in resources[arm]:
                p = energy.window.resources.unpack(resources[arm][tick], lives[arm][FOCAL], tick)
                require(totals[arm][FOCAL] == p['uptake'][0][1] and len(focal_leaves) == 8,
                        'focal leaf total/count differs from original resource history')
            else:
                require(not focal_leaves and tick > lives[arm][FOCAL]['death_tick'],
                        'unexpected missing focal adult')
        if tick > CRITICAL_STOP:
            continue  # The post-death sample is validated, never counted as a paired canopy.
        matched += 1
        fixed_leaves = [l for l in fixed['leaves'] if l[1] == FOCAL]
        cursor_leaves = [l for l in cursor['leaves'] if l[1] == FOCAL]
        same_geometry = [l[:4] for l in fixed_leaves] == [l[:4] for l in cursor_leaves]
        same_sources = fixed['sources'] == [s for s in cursor['sources'] if s[1] != NEIGHBOR]
        geometry_matches += same_geometry
        source_matches += same_sources
        if not same_geometry or not same_sources:
            mismatches.append(dict(tick=tick, geometry=same_geometry, other_sources=same_sources))
        field = light.field(without_neighbor(cursor['sources']), cursor['sun'][1], cursor['sun'][2])
        removed = sum(field[l[3] * 28 + l[2]] // 64 for l in cursor_leaves)
        if tick == CRITICAL_START:
            continue  # Left-open resource interval starts after the full-energy boundary.
        name = 'establishment' if tick <= capture.WINDOWS[0][1] else 'winter'
        period = periods[name]
        period['samples'] += 1
        period['fixed'] += totals['fixed'][FOCAL]
        period['cursor'] += totals['cursor'][FOCAL]
        period['without_neighbor'] += removed
        period['residual_absolute'] += abs(removed - totals['fixed'][FOCAL])
        period['income_gap_steps'] += totals['fixed'][FOCAL] != totals['cursor'][FOCAL]
        changes = []
        for leaf in cursor_leaves:
            node, _, column, canopy_row, actual_light, actual_income = leaf
            focal_coordinates.add((node, column, canopy_row))
            changed_light = field[canopy_row * 28 + column]
            changed_income = changed_light // 64
            require(changed_light >= actual_light and changed_income >= actual_income, 'removing shade lost light')
            if changed_income != actual_income:
                changes.append([node, column, canopy_row, actual_light, changed_light, actual_income, changed_income])
                key = str(node)
                period['leaf_gains'][key] = period['leaf_gains'].get(key, 0) + changed_income - actual_income
        if changes or removed != totals['fixed'][FOCAL]:
            period['changed'].append(dict(tick=tick, sun=cursor['sun'], fixed=totals['fixed'][FOCAL],
                cursor=totals['cursor'][FOCAL], without_neighbor=removed, leaves=changes))
    for arm in capture.ARMS:
        require(periods['winter'][arm] == diagnosis['analysis']['critical_budget'][arm]['energy']['income'],
                'winter interval differs from diagnosed income')
    require(periods['winter']['samples'] == (CRITICAL_STOP - CRITICAL_START) // STEP,
            'wrong terminal interval exposure')
    return dict(validated_grids=len(ticks) * 2, paired_samples=matched,
                matching_other_sources=source_matches, matching_focal_geometry=geometry_matches,
                mismatches=mismatches, focal_coordinates=[list(c) for c in sorted(focal_coordinates)], periods=periods,
                proves_long_run_rescue=False, original_harm_gate_passes=False)


def make_value(receipt, rows):
    require(energy.capture.sweep.fingerprint(receipt) == CAPTURE_SHA, 'changed replay receipt')
    original, diagnosis = inputs()
    return dict(rule=RULE, input_sha256=energy.INPUT_SHA, energy_sha256=ENERGY_SHA,
                raw_manifest_sha256=MANIFEST_SHA, capture=receipt, rows=rows,
                analysis=analyze(rows, original, diagnosis))


def check_value(value):
    require(value == make_value(value['capture'], value['rows']), 'shadow diagnosis differs')


def extract(bundle):
    require(capture.digest(bundle / 'manifest.json') == MANIFEST_SHA, 'bundle manifest changed')
    manifest = json.loads((bundle / 'manifest.json').read_text())
    for name, expected in manifest['artifacts'].items():
        require(capture.digest(bundle / name) == expected, 'bundle file changed: ' + name)
    receipt = json.loads((bundle / 'capture.json').read_text())
    rows = {}
    for arm in capture.ARMS:
        run = receipt['runs'][arm]
        for meta in run['traces'].values():
            sha, size = hashlib.sha256(), 0
            with gzip.open(bundle / meta['path'], 'rb') as stream:
                while block := stream.read(1024 * 1024):
                    sha.update(block)
                    size += len(block)
            require(sha.hexdigest() == meta['raw_sha256'] and size == meta['raw_bytes'], 'restored bytes differ')
        rows[arm] = list(capture.uptake_rows(bundle / run['traces']['uptake']['path'], run['result']))
    return make_value(receipt, rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--out', type=Path)
    mode.add_argument('--verify', type=Path)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--origin', type=Path)
    args = parser.parse_args()
    if args.verify:
        with gzip.open(args.verify, 'rt') as stream:
            value = json.load(stream)
        check_value(value)
        if args.bundle:
            require(value == extract(args.bundle), 'raw shadow re-extraction differs')
    else:
        require(args.bundle is not None, '--out requires --bundle')
        value = extract(args.bundle)
        energy.capture.sweep.write_gzip(args.out, value)
    if args.origin:
        require(args.bundle is not None, '--origin requires --bundle')
        original = energy.load_input()
        for arm in capture.ARMS:
            count = capture.compare_stand(args.origin, args.bundle, original, arm)
            require(count == value['capture']['runs'][arm]['matching_stand_samples'], 'stand count changed')
    print(json.dumps({k: v for k, v in value['analysis'].items() if k != 'periods'}, indent=2))
    print(json.dumps({name: {k: v for k, v in p.items() if k != 'changed'}
                      for name, p in value['analysis']['periods'].items()}, indent=2))


if __name__ == '__main__':
    main()
