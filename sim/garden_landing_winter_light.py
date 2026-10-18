#!/usr/bin/env python3
"""Reconcile saved winter leaf income and diagnose shade on frozen geometry."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from functools import cache
import gzip
import json
from pathlib import Path
import sys

import garden_landing_energy_history as history
import garden_landing_uptake as uptake
import garden_landing_winter_light_capture as capture
from garden_experiments import digest
from garden_landing_founders import write_gzip
from garden_landing_root_allocation_audit import fingerprint, pack
from garden_resources import require

ROOT, STEP, STOP = history.ROOT, history.STEP, history.STOP
SIDES, SPANS = tuple(capture.ARMS), capture.SPANS
TARGET = history.SUBJECT['id']
RAW_MANIFEST_SHA = 'bc9d7567bfc210e92faf9f5ddd482d4ca66d694512987bff6181f3a9245b817c'
PERIODS = (('winter_morning', 974400, 975345), ('winter_afternoon', 975360, 976305),
           ('dawn_to_refill', 978240, 979230))
SOURCES = ('sim/garden_landing_winter_light.py', 'sim/garden_landing_uptake.py',
           'sim/garden_landing_energy_history.py', 'sim/garden_landing_population.py',
           'sim/garden_landing_adults.py', 'sim/garden_landing_root_allocation_audit.py',
           'sim/garden_landing_founders.py', 'sim/garden_landing_light_audit.py',
           *capture.SOURCES)
LIGHT_KEYS = ('tick', 'sun', 'sources', 'leaves', 'light')
ADULT_KEYS = ('tick', 'sun', 'cold', 'season', 'plants')


def ticks(prior=False):
    return [tick for start, end in SPANS for tick in range(start - (STEP if prior else 0), end + STEP, STEP)]


@cache
def saved_history():
    capture.provenance()
    with gzip.open(ROOT / list(capture.INPUTS)[0], 'rt') as stream: value = json.load(stream)
    history.check_value(value)
    return value


def extract(bundle, value):
    out = {}
    wanted = set(ticks(prior=True))
    for side, run in value['runs'].items():
        observations = [{k: row[k] for k in LIGHT_KEYS} for row in uptake.observation_rows(
            bundle / run['traces']['uptake']['path'], SPANS, run['result'])]
        adults = [{k: row[k] for k in ADULT_KEYS} for row in history.population.trace_rows(
            bundle / run['traces']['adult']['path'], 'adult', run['result']) if row['tick'] in wanted]
        out[side] = dict(uptake=observations, adult=adults)
        print(side + ': raw winter-light and adult receipts extracted', flush=True)
    return out


def alive(lives, identity, tick):
    require(identity in lives and lives[identity]['birth_tick'] < tick, 'unknown/unborn shade lineage')
    return lives[identity]['death_tick'] is None or lives[identity]['death_tick'] >= tick


def validate_light(row, lives):
    require(set(row) == set(LIGHT_KEYS), 'wrong light receipt fields')
    tick = row['tick']
    require(type(tick) is int and tick % STEP == 0 and type(row['sun']) is list and len(row['sun']) == 3 and
            all(type(n) is int for n in row['sun']), 'invalid light clock/sun')
    phase, strength, ray = row['sun']
    require(phase == (64 + tick // STEP) % 256 and 24 <= strength <= 255 and
            ray == uptake.previous.light.ray_step(phase), 'wrong light clock/sun')
    sources = tuple(tuple(s) for s in row['sources'])
    require(len(sources) <= 256 and all(uptake.vector(list(s), 7, 0xffffffff) and
            s[0] < 256 and s[2] in (0, 1) and s[3] < 28 and s[4] < 14 and
            s[5] <= 255 and s[6] == s[5] // 3 for s in sources), 'invalid shade source')
    require([s[0] for s in sources] == sorted({s[0] for s in sources}), 'duplicate/unordered shade source')
    for s in sources:
        require(bool(s[2]) != alive(lives, s[1], tick), 'wrong live/dead shade identity')
        require(s[5] == (26, 38, 32)[lives[s[1]]['species']], 'wrong species opacity')
    recorded = list(bytes.fromhex(row['light']))
    require(len(recorded) == 392 and uptake.field(uptake.opacity(sources, 0, 'actual'), strength, ray) == recorded,
            'light field reconstruction differs')
    incomes, counts, identities = Counter(), Counter(), []
    for leaf in row['leaves']:
        require(uptake.vector(leaf, 6, 0xffffffff), 'invalid leaf record')
        node, owner, col, y, local, income = leaf
        require(node < 256 and col < 28 and y < 14 and alive(lives, owner, tick), 'invalid leaf identity')
        require(local == recorded[y * 28 + col] and income == local // 64, 'leaf light/income differs')
        identities.append((node, owner, col, y))
        incomes[owner] += income
        counts[owner] += 1
    require(len(identities) == len({i[0] for i in identities}) and sorted(identities) ==
            sorted((s[0], s[1], s[3], s[4]) for s in sources if not s[2]), 'live source/leaf identity differs')
    return sources, incomes, counts


def target_leaves(row):
    # Node indices may move after compaction. Coordinates retain multiplicity.
    return sorted(leaf[2:] for leaf in row['leaves'] if leaf[1] == TARGET)


def target_shade(row):
    return sorted(s[2:] for s in row['sources'] if s[1] == TARGET)


def income_at(grid, strength, ray, leaves):
    field = uptake.field(grid, strength, ray)
    return sum(field[y * 28 + col] // 64 for col, y, _, _ in leaves)


def frozen_income(row):
    sources, leaves = tuple(tuple(s) for s in row['sources']), target_leaves(row)
    _, strength, ray = row['sun']
    actual = sum(leaf[3] for leaf in leaves)
    modes = {mode: (len(leaves) * (strength // 64) if mode == 'open' else
                   income_at(uptake.opacity(sources, TARGET, mode), strength, ray, leaves))
             for mode in uptake.ENERGY}
    removals = {str(owner): income_at(uptake.opacity(tuple(s for s in sources if s[1] != owner), 0, 'actual'),
                                    strength, ray, leaves) - actual for owner in sorted({s[1] for s in sources})}
    require(modes['actual'] == actual and all(actual <= n <= modes['open'] for n in modes.values()) and
            all(0 <= n <= modes['open'] - actual for n in removals.values()), 'invalid frozen-shade bound')
    return dict(tick=row['tick'], income=modes, single_owner_gain=removals, leaves=leaves)


def ray_witness(row, col, y):
    """Keep all geometric ray cells, marking the runtime floor's early exit."""
    _, strength, ray = row['sun']
    remaining = strength - 24
    cells = []
    for cell in uptake.rays(ray)[y * 28 + col]:
        c, r = cell % 28, cell // 28
        sources = []
        for node, owner, dead, x, sy, center, side in row['sources']:
            amount = center if c == x else side if abs(c - x) == 1 else 0
            if sy == r and amount:
                sources.append(dict(node=node, owner=owner, dead=bool(dead),
                                    part='center' if c == x else 'neighbor', opacity=amount))
        total = sum(s['opacity'] for s in sources)
        opacity = min(255, total)
        used = min(remaining, opacity)
        cells.append(dict(column=c, row=r, sources=sources, raw_opacity=total, cell_opacity=opacity,
                          cell_clipped=total - opacity, visited=remaining > 0, effective_reduction=used))
        remaining -= used
    local = 24 + remaining
    require(local == bytes.fromhex(row['light'])[y * 28 + col], 'ray witness differs from recorded light')
    return dict(column=col, row=y, light=local, income=local // 64, cells=cells,
                ray_cell_opacity=sum(c['cell_opacity'] for c in cells), effective_reduction=strength - local,
                floor_clipped=sum(c['cell_opacity'] for c in cells) - (strength - local))


def census(row, lives):
    require(set(row) == set(ADULT_KEYS) and type(row['tick']) is int and
            history.adults.vector(row['sun'], 2, 255) and type(row['cold']) is bool and
            type(row['season']) is int and row['season'] == (row['tick'] // history.population.DAY % 16) // 4 and
            row['sun'][0] == (64 + row['tick'] // STEP) % 256, 'invalid adult environment')
    ps = {p['id']: p for p in row['plants']}
    expected = {i for i, p in lives.items() if p['birth_tick'] <= row['tick'] and
                (p['death_tick'] is None or p['death_tick'] >= row['tick'])}
    require(len(ps) == len(row['plants']) and set(ps) == expected and
            all(p['birth'] == lives[i]['birth_tick'] for i, p in ps.items()), 'wrong adult census/identity')
    return ps


def validate_receipt(receipt, side, result):
    require(set(receipt) == {'uptake', 'adult'} and [r['tick'] for r in receipt['uptake']] == ticks() and
            [r['tick'] for r in receipt['adult']] == ticks(prior=True), 'incomplete winter-light coverage')
    lives = {p['id']: p for p in result['lineages']}
    require(len(lives) == len(result['lineages']), 'duplicate ledger identity')
    adults = {r['tick']: r for r in receipt['adult']}
    population = {t: census(r, lives) for t, r in adults.items()}
    reference = saved_history()['rows'][side]
    for tick, row in adults.items():
        old = reference[(tick - history.SUBJECT['birth']) // STEP]
        require(all(row[k] == old[k] for k in ('tick', 'sun', 'cold', 'season')) and
                pack(population[tick][TARGET]) == old['plant'], 'selected energy history differs')
    counts = Counter(frames=len(receipt['uptake']), light_cells=392 * len(receipt['uptake']))
    for row in receipt['uptake']:
        tick = row['tick']
        _, incomes, leaves = validate_light(row, lives)
        require(row['sun'][:2] == adults[tick]['sun'], 'light/adult sun differs')
        current, prior = population[tick], population[tick - STEP]
        expected = {i for i, p in current.items() if p['uptake'] is not None}
        # These frozen windows contain no leaf maturation. Fail closed if that
        # ceases to hold; previous post-step counts are not a general growth model.
        require(leaves == Counter({i: prior[i]['active_leaves'] for i in expected}),
                'pre-growth leaf count differs in frozen window')
        for i, plant in current.items():
            previous = prior[i]['stages'][-1] if i in expected else None
            budget = history.adults.transfers(dict(tick=tick, **plant), lives[i], previous)
            require(budget['energy']['income'] == incomes[i], 'adult/leaf energy income differs')
            counts['adult_receipts'] += 1
        counts.update(leaves=len(row['leaves']), sources=len(row['sources']))
    return dict(counts)


def side_summary(receipt, samples, result):
    lives = {p['id']: p for p in result['lineages']}
    owners = sorted({s[1] for row in receipt['uptake'] for s in row['sources']})
    periods = []
    for label, start, end in PERIODS:
        selected = [s for s in samples if start <= s['tick'] <= end]
        periods.append(dict(label=label, first=start, through=end, samples=len(selected),
                            income={mode: sum(s['income'][mode] for s in selected) for mode in uptake.ENERGY},
                            single_owner_gain={str(i): sum(s['single_owner_gain'].get(str(i), 0)
                                                        for s in selected) for i in owners}))
    geometry = []
    for row in receipt['uptake']:
        shape = dict(leaves=[leaf[:2] for leaf in target_leaves(row)], shade=target_shade(row))
        if not geometry or geometry[-1]['shape'] != shape:
            geometry.append(dict(tick=row['tick'], shape=shape))
    return dict(periods=periods, geometry=geometry, owners=[dict(life=lives[i],
        observed_live_samples=sum(any(s[1] == i and not s[2] for s in r['sources']) for r in receipt['uptake']),
        observed_dead_samples=sum(any(s[1] == i and s[2] for s in r['sources']) for r in receipt['uptake']))
        for i in owners])


def leaf_comparison(control, candidate):
    """Pair a multiset of positions; never hide a morphological mismatch."""
    if [l[:2] for l in control] != [l[:2] for l in candidate]:
        return None
    return [dict(column=a[0], row=a[1], occurrence=n, control=a[2:], candidate=b[2:],
                 light_delta=b[2] - a[2], income_delta=b[3] - a[3])
            for n, (a, b) in enumerate(zip(control, candidate, strict=True))]


def compare(rows, samples):
    pairs, geometry = [], dict(leaf_mismatch_ticks=[], self_shade_mismatch_ticks=[])
    restored = defaultdict(lambda: Counter(compared_samples=0, equal_light_samples=0, equal_income_samples=0))
    first, first_light, threshold = None, None, None
    for n, (a, b) in enumerate(zip(rows['control']['uptake'], rows['candidate']['uptake'], strict=True)):
        require(a['sun'] == b['sun'] and a['tick'] == b['tick'], 'unequal paired light environment')
        leaves = leaf_comparison(target_leaves(a), target_leaves(b))
        if leaves is None: geometry['leaf_mismatch_ticks'].append(a['tick'])
        if target_shade(a) != target_shade(b): geometry['self_shade_mismatch_ticks'].append(a['tick'])
        pairs.append(dict(tick=a['tick'], leaves=leaves))
        if leaves is not None:
            if first_light is None and any(l['light_delta'] != 0 for l in leaves):
                first_light = dict(tick=a['tick'], sun=a['sun'], leaves=leaves)
            for leaf in leaves:
                if leaf['income_delta'] < 0 and (threshold is None or
                        leaf['light_delta'] > threshold['leaf']['light_delta']):
                    threshold = dict(tick=a['tick'], sun=a['sun'], leaf=leaf)
            for owner in sorted({s[1] for s in b['sources']}):
                sources = tuple(tuple(s) for s in b['sources'] if s[1] != owner)
                field = uptake.field(uptake.opacity(sources, 0, 'actual'), *b['sun'][1:])
                values = [field[l['row'] * 28 + l['column']] for l in leaves]
                restored[str(owner)].update(compared_samples=1,
                    equal_light_samples=all(v == l['control'][0] for v, l in zip(values, leaves, strict=True)),
                    equal_income_samples=all(v // 64 == l['control'][1] for v, l in zip(values, leaves, strict=True)))
        if first is None and samples['control'][n]['income']['actual'] != samples['candidate'][n]['income']['actual']:
            first = dict(tick=a['tick'], sun=a['sun'], leaves=leaves,
                rays={side: [ray_witness(row, col, y) for col, y in sorted({tuple(l[:2]) for l in target_leaves(row)})]
                      for side, row in zip(SIDES, (a, b), strict=True)})
    periods = []
    for label, start, end in PERIODS:
        selected = [p for p in pairs if start <= p['tick'] <= end]
        cells = defaultdict(lambda: Counter(leaf_samples=0, light_loss=0, light_gain=0, light_ties=0,
                                            income_loss=0, income_gain=0, income_ties=0))
        for p in selected:
            if p['leaves'] is None: continue
            for leaf in p['leaves']:
                cell = cells[(leaf['column'], leaf['row'])]
                cell['leaf_samples'] += 1
                for kind in ('light', 'income'):
                    delta = leaf[kind + '_delta']
                    cell[kind + '_loss'] += max(0, -delta)
                    cell[kind + '_gain'] += max(0, delta)
                    cell[kind + '_ties'] += delta == 0
        periods.append(dict(label=label, matched_samples=sum(p['leaves'] is not None for p in selected),
                            cells=[dict(column=c, row=r, **v) for (c, r), v in sorted(cells.items())]))
    return dict(geometry=geometry, first_income_difference=first, first_light_difference=first_light,
                smallest_income_losing_light_drop=threshold, periods=periods,
                candidate_owner_removal_matches={i: dict(v) for i, v in restored.items()})


def analyze(rows, value):
    require(set(rows) == set(SIDES), 'wrong winter-light arms')
    counts, samples, summary = {}, {}, {}
    for side in SIDES:
        result = value['runs'][side]['result']
        counts[side] = validate_receipt(rows[side], side, result)
        samples[side] = [frozen_income(r) for r in rows[side]['uptake']]
        summary[side] = side_summary(rows[side], samples[side], result)
    paired = compare(rows, samples)
    for n, period in enumerate(paired['periods']):
        if period['matched_samples'] == summary['control']['periods'][n]['samples']:
            delta = sum(c['income_gain'] - c['income_loss'] for c in period['cells'])
            require(delta == summary['candidate']['periods'][n]['income']['actual'] -
                    summary['control']['periods'][n]['income']['actual'], 'per-leaf period account differs')
    return dict(counts=counts, samples=samples, arms=summary, comparison=paired)


def check_value(value):
    capture.check_capture(value['capture'])
    require(value['source_sha256'] == {p: digest(ROOT / p) for p in SOURCES}, 'winter-light analysis source differs')
    require(value['raw_manifest_sha256'] == RAW_MANIFEST_SHA, 'wrong selected raw manifest')
    require(set(value['receipt_sha256']) == set(SIDES) and
            all(value['receipt_sha256'][a] == fingerprint(value['rows'][a]) for a in SIDES),
            'winter-light receipt checksum differs')
    require(value['analysis'] == analyze(value['rows'], value['capture']), 'winter-light analysis differs')


def export(bundle, out):
    require(not out.exists() and not out.is_symlink(), 'fresh analysis output required')
    require(digest(bundle / 'manifest.json') == RAW_MANIFEST_SHA, 'wrong selected raw manifest')
    captured = capture.verify_bundle(bundle)
    rows = extract(bundle, captured)
    value = dict(capture=captured, raw_manifest_sha256=digest(bundle / 'manifest.json'), rows=rows,
                 receipt_sha256={a: fingerprint(rows[a]) for a in SIDES},
                 source_sha256={p: digest(ROOT / p) for p in SOURCES}, analysis=analyze(rows, captured))
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
        if args.bundle:
            require(digest(args.bundle / 'manifest.json') == value['raw_manifest_sha256'] and
                    capture.verify_bundle(args.bundle) == value['capture'] and
                    extract(args.bundle, value['capture']) == value['rows'], 'raw light re-extraction differs')
        print('Verified winter-light fields, income and frozen-shade diagnostics offline.')
    else:
        export(args.bundle or ROOT / 'artifacts/garden-landing-winter-light-v1', args.out)
        print('Saved winter-light analysis; no simulations.')


if __name__ == '__main__':
    try: main()
    except (RuntimeError, ValueError, KeyError, TypeError, OSError, IndexError, StopIteration) as error:
        print('winter-light analysis failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
