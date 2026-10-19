#!/usr/bin/env python3
"""Offline per-leaf space/phase attribution of the authenticated foliage trace."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import tempfile

import population_foliage as foliage

collect, prepare, score = foliage.collect, foliage.prepare, foliage.score
ARCHIVE = collect.ROOT / 'benchmarks/garden-seasons/leaf-population-foliage-results.json.gz'
ARCHIVE_SHA = '7462461ae0057387c2e5d1cb68fb61ab5b6671f3601640ecd1cac32b51ce5cf2'
PHASE_ENDS = tuple(range(32, 257, 32))
ADDITIVE = ('samples', 'light_bands', 'unshaded_bands', 'weighted_numerator',
            'productive_samples', 'productive_zero_condition_samples')


def phase_end(phase):
    score.require(score.integer(phase, 0, 255), 'invalid sun phase')
    # Sunrise phase 0 closes the preceding night; dawn is phases 1..32.
    return ((phase - 1) // 32 + 1) * 32 if phase else 256


def metrics(samples):
    """Samples are (local light, condition, unshaded sun strength), not stocks."""
    score.require(bool(samples), 'empty leaf sample group')
    score.require(all(all(score.integer(x, 0, 255) for x in s) and s[0] <= s[2]
                      for s in samples), 'invalid leaf light or condition')
    result = dict(samples=len(samples), light_bands=sum(light // 64 for light, _, _ in samples),
        unshaded_bands=sum(sun // 64 for _, _, sun in samples),
        weighted_numerator=sum((light // 64) * condition for light, condition, _ in samples),
        productive_samples=sum(light >= 64 for light, _, _ in samples),
        productive_zero_condition_samples=sum(light >= 64 and condition == 0 for light, condition, _ in samples))
    return result


def total(groups):
    return {k: sum(g[k] for g in groups) for k in ADDITIVE}


def attribute(data):
    """Requires a validated foliage trace; also rejects misaligned spatial joins."""
    rows = data['rows']
    score.require([r['tick'] for r in rows] == foliage.TICKS and
                  all(r['phase'] == (r['tick'] // 15 + 64) % 256 for r in rows), 'phase coverage differs')
    positions = [f[1:5] for f in rows[0]['leaves']]
    score.require(positions and all([f[1:5] for f in r['leaves']] == positions for r in rows),
                  'leaf body/order differs')
    windows = {end: [r for r in rows if phase_end(r['phase']) == end] for end in PHASE_ENDS}
    score.require(all(len(group) == 32 and all(b['tick'] - a['tick'] == 15 for a, b in zip(group, group[1:]))
                      for group in windows.values()), 'phase window is not contiguous')
    leaves = []
    cells = defaultdict(list)
    for ordinal, (x, y, column, row) in enumerate(positions):
        periods = [dict(phase_end=end, **metrics([(r['leaves'][ordinal][5], r['leaves'][ordinal][6],
                                                  r['strength']) for r in group]))
                   for end, group in windows.items()]
        lit = [r for r in windows[32] if r['leaves'][ordinal][5] >= 64]
        paid = [r for r in lit if r['leaves'][ordinal][6] > 0]
        leaves.append(dict(ordinal=ordinal, x=x, y=y, column=column, row=row,
            node_first=rows[0]['leaves'][ordinal][0], node_last=rows[-1]['leaves'][ordinal][0],
            dawn_first_lit_phase=lit[0]['phase'] if lit else None,
            dawn_first_contributing_phase=paid[0]['phase'] if paid else None,
            periods=periods, day=total(periods)))
        cells[column, row].append(ordinal)
    mapped_cells = []
    for (column, row), ordinals in sorted(cells.items(), key=lambda item: (item[0][1], item[0][0])):
        mapped_cells.append(dict(column=column, row=row, ordinals=ordinals,
            periods=[dict(phase_end=end, **total([leaves[o]['periods'][i] for o in ordinals]))
                     for i, end in enumerate(PHASE_ENDS)]))
    periods = []
    for i, (end, group) in enumerate(windows.items()):
        m = total([leaf['periods'][i] for leaf in leaves])
        s = foliage.summary(group)
        score.require(m['light_bands'] == s['healthy_at_recorded_light'] and
                      m['weighted_numerator'] == s['condition_weighted_numerator'] and
                      divmod(s['remainder_before'] + m['weighted_numerator'], 255) ==
                      (s['energy']['income'], s['remainder_after']), 'phase attribution differs')
        periods.append(dict(phase_first=end - 31, phase_end=end, first_tick=group[0]['tick'],
            last_tick=group[-1]['tick'], energy=s['energy'], remainder_before=s['remainder_before'],
            remainder_after=s['remainder_after'], **m))
    day = total(periods)
    score.require(day == total([leaf['day'] for leaf in leaves]) and
                  all(total([c['periods'][i] for c in mapped_cells]) ==
                      {k: p[k] for k in ADDITIVE} for i, p in enumerate(periods)), 'spatial totals differ')
    # These geometric halves are fixed grid rows, not selected from the outcomes.
    height = []
    for label, first, end in (('upper', 0, 7), ('lower', 7, 14)):
        selected = [leaf for leaf in leaves if first <= leaf['row'] < end]
        height.append(dict(label=label, first_row=first, end_row_exclusive=end, leaves=len(selected),
                           dark_leaves=sum(leaf['periods'][0]['light_bands'] == 0 for leaf in selected),
                           contributing_leaves=sum(leaf['periods'][0]['weighted_numerator'] > 0 for leaf in selected),
                           lit_zero_income_leaves=sum(leaf['periods'][0]['light_bands'] > 0 and
                               leaf['periods'][0]['weighted_numerator'] == 0 for leaf in selected),
                           **total([leaf['periods'][0] for leaf in selected])))
    return dict(lineage=data['lineage'], leaf_count=len(leaves), leaves=leaves, cells=mapped_cells,
        periods=periods, day=day, dawn_by_height=height,
        dawn_productive_leaves=sum(leaf['periods'][0]['productive_samples'] > 0 for leaf in leaves),
        dawn_contributing_leaves=sum(leaf['periods'][0]['weighted_numerator'] > 0 for leaf in leaves),
        dawn_dark_but_later_lit=[leaf['ordinal'] for leaf in leaves
            if leaf['periods'][0]['light_bands'] == 0 and leaf['day']['light_bands'] > 0])


def diagnose():
    score.require(prepare.sha(ARCHIVE.read_bytes()) == ARCHIVE_SHA, 'foliage archive identity differs')
    cases, inputs = {}, {}
    # Authenticate and fully revalidate the existing collection offline. The
    # temporary extraction contains only data; no archived code is executed.
    with tempfile.TemporaryDirectory(prefix='garden-exposure-') as directory:
        root = Path(directory) / 'evidence'
        verified = foliage.follow.unpack(ARCHIVE, root, experiment=foliage.EXPERIMENT)
        for policy in foliage.TARGETS:
            name = f'runs/9a903368-condition-{policy}-on/timeline/foliage.json'
            raw = (root / name).read_bytes()
            inputs[name] = prepare.sha(raw)
            data = json.loads(raw)
            case = attribute(data)
            old = verified['analyses'][policy]
            score.require(case['day']['weighted_numerator'] == old['day']['condition_weighted_numerator'] and
                          case['periods'][0]['energy'] == old['dawn']['energy'], 'published summary differs')
            cases[policy] = case
    return dict(schema='garden-population-exposure-v1', native_calls=0,
        foliage_archive_sha256=ARCHIVE_SHA, inputs=inputs, seed=foliage.fallback.SEED,
        first_tick_exclusive=foliage.FIRST, end_tick=foliage.END, cases=cases)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--out', type=Path, help='new derived JSON; never overwrite')
    mode.add_argument('--check', type=Path, help='verify an existing derivation')
    args = parser.parse_args()
    result = diagnose()
    if args.check:
        score.require(json.loads(args.check.read_bytes()) == result, 'exposure derivation differs')
    else:
        collect.save(args.out, result)
    print('Verified 50 leaves across 256 phases; zero native calls.')
