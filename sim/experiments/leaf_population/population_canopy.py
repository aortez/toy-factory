#!/usr/bin/env python3
"""Read-only dawn canopy sources and exact ray attribution for two frozen shrubs."""

from collections import Counter
import gzip
import json

import population_foliage as foliage

collect, prepare, score, follow = foliage.collect, foliage.prepare, foliage.score, foliage.follow
BASELINE = collect.ROOT / 'benchmarks/garden-seasons/leaf-population-foliage-results.json.gz'
BASELINE_SHA = '7462461ae0057387c2e5d1cb68fb61ab5b6671f3601640ecd1cac32b51ce5cf2'
PROTOCOL = collect.ROOT / 'benchmarks/garden-seasons/leaf-population-canopy-protocol.md'
ARCHIVE_SCHEMA = 'garden-population-canopy-evidence-v1'
FIELDS = ['lineage', 'node', 'column', 'row', 'center', 'neighbor', 'dead']
TICKS = list(range(foliage.DAWN + 15, foliage.OPENING + 1, 15))
roster = foliage.roster


def inputs():
    raw = BASELINE.read_bytes()
    score.require(prepare.sha(raw) == BASELINE_SHA, 'foliage baseline differs')
    baseline = json.loads(gzip.decompress(raw))
    score.require(baseline['schema'] == foliage.ARCHIVE_SCHEMA, 'foliage schema differs')
    _, models, size = collect.archive_inputs()
    return baseline, models, size


def arguments(call):
    return ['--canopy-panel', foliage.fallback.SEED, 'condition', call['policy'], call['mode']]


def offset(ray, distance):
    product = ray * distance
    return (abs(product) + 8) // 16 * (1 if product >= 0 else -1)


def field(sources):
    cells = [Counter() for _ in range(28 * 14)]
    for lineage, _, column, row, center, neighbor, _ in sources:
        for col, opacity in ((column, center), (column - 1, neighbor), (column + 1, neighbor)):
            if 0 <= col < 28 and opacity:
                cells[row * 28 + col][lineage] += opacity
    return cells


def cast(cells, column, row, strength, ray, *, keep=None):
    """Record only cells actually visited before floor/boundary termination.

    Per-lineage opacity is raw, before cell and beam caps, so it cannot be
    presented as an additive split of lost energy. keep is a fixed-snapshot
    optical ablation; it neither repairs nor moves any plant.
    """
    reduction, visited, raw = 0, [], Counter()
    if strength == 24:
        return dict(light=24, stop='ambient', cells=visited, raw=raw)
    stop = 'top'
    for distance in range(1, row + 1):
        col = column - offset(ray, distance)
        if not 0 <= col < 28:
            stop = 'left' if col < 0 else 'right'
            break
        r = row - distance
        contributions = {k: v for k, v in cells[r * 28 + col].items() if keep is None or keep(k)}
        opacity = min(255, sum(contributions.values()))
        applied = min(opacity, strength - 24 - reduction)
        visited.append([col, r, opacity, applied])
        raw.update(contributions)
        reduction += applied
        if reduction == strength - 24:
            stop = 'floor'
            break
    return dict(light=strength - reduction, stop=stop, cells=visited, raw=raw)


def aggregate(samples):
    result = dict(samples=len(samples), stops=dict(sorted(Counter(s['stop'] for s in samples).items())))
    for key in ('bands', 'weighted', 'no_self_bands', 'no_self_weighted', 'no_other_bands',
                'no_other_weighted', 'unshaded_bands', 'unshaded_weighted'):
        result[key] = sum(s[key] for s in samples)
    raw = Counter()
    for s in samples:
        raw.update(s['raw'])
    result['raw_opacity_by_lineage'] = {str(k): v for k, v in sorted(raw.items())}
    return result


def validate_trace(data, leaves, policy):
    target, count = foliage.TARGETS[policy]
    score.require(data['schema'] == 'garden-canopy-sources-v1' and data['lineage'] == target and
                  (data['first_tick_exclusive'], data['end_tick']) == (foliage.DAWN, foliage.OPENING) and
                  data['source_fields'] == FIELDS, 'canopy identity differs')
    score.require([r['tick'] for r in data['rows']] == TICKS, 'canopy coverage differs')
    focal = {r['tick']: r for r in leaves['rows']}
    samples, paths = [], []
    for row in data['rows']:
        leaf = focal[row['tick']]
        score.require((row['phase'], row['strength']) == (leaf['phase'], leaf['strength']) and
                      score.integer(row['ray'], -12, 12) and
                      row['ray'] == 12 - (row['phase'] * 24 + 64) // 128 and
                      score.integer(row['strength'], 24, 255), 'canopy sun differs')
        sources = row['sources']
        score.require(0 < len(sources) <= 256 and all(len(s) == 7 and
            score.integer(s[0], 1, 0xffffffff) and score.integer(s[1], 0, 255) and
            score.integer(s[2], 0, 27) and score.integer(s[3], 0, 13) and
            score.integer(s[4], 0, 38) and score.integer(s[5], 0, 12) and
            type(s[6]) is bool for s in sources), 'invalid canopy source')
        nodes = [s[1] for s in sources]
        score.require(nodes == sorted(set(nodes)), 'source node order differs')
        own = [s for s in sources if s[0] == target]
        # Join by body order: actual callback indices may follow reclamation.
        score.require(len(own) == count == len(leaf['leaves']) and all(
            s[2:6] == [f[3], f[4], 38 * f[6] // 255, 12 * f[6] // 255] and not s[6]
            for s, f in zip(own, leaf['leaves'], strict=True)), 'focal shade/wear differs')
        cells = field(sources)
        score.require(len(row['light']) == 392 and all(score.integer(v, 24, 255) for v in row['light']),
                      'invalid canopy light grid')
        solved = [cast(cells, col, r, row['strength'], row['ray'])['light']
                  for r in range(14) for col in range(28)]
        score.require(solved == row['light'], 'independent light solve differs')
        for ordinal, f in enumerate(leaf['leaves']):
            _, _, _, col, r, light, condition = f
            actual = cast(cells, col, r, row['strength'], row['ray'])
            score.require(actual['light'] == light, 'actual uptake join differs')
            no_self = cast(cells, col, r, row['strength'], row['ray'], keep=lambda k: k != target)['light']
            no_other = cast(cells, col, r, row['strength'], row['ray'], keep=lambda k: k == target)['light']
            s = dict(ordinal=ordinal, column=col, row=r, stop=actual['stop'], raw=actual['raw'])
            for label, value in (('', light), ('no_self_', no_self), ('no_other_', no_other),
                                 ('unshaded_', row['strength'])):
                s[label + 'bands'] = value // 64
                s[label + 'weighted'] = value // 64 * condition
            samples.append(s)
            paths.append(dict(tick=row['tick'], ordinal=ordinal, column=col, row=r, light=light,
                condition=condition, stop=actual['stop'], cells=actual['cells'],
                raw_opacity_by_lineage={str(k): v for k, v in sorted(actual['raw'].items())},
                no_self_light=no_self, no_other_light=no_other))
    total = aggregate(samples)
    expected = foliage.summary([focal[t] for t in TICKS])
    score.require(total['bands'] == expected['healthy_at_recorded_light'] and
                  total['weighted'] == expected['condition_weighted_numerator'], 'dawn totals differ')
    return dict(lineage=target, leaves=count, full_grid_cells_checked=32 * 392, total=total,
        heights={label: aggregate([s for s in samples if lo <= s['row'] < hi])
                 for label, lo, hi in (('upper', 0, 7), ('lower', 7, 14))},
        columns={str(col): aggregate([s for s in samples if s['column'] == col])
                 for col in sorted({s['column'] for s in samples})}, paths=paths)


def validate_outputs(out, baseline, models, size):
    foliage.validate_outputs(out, baseline, models, size, extra_names=('canopy.json',))
    analyses = {}
    for call in roster():
        if call['mode'] != 'on':
            continue
        name = 'runs/' + call['id'] + '/timeline/'
        raw = (out / (name + 'foliage.json')).read_bytes()
        score.require(raw == prepare.blob(baseline, name + 'foliage.json'), 'foliage baseline differs')
        analyses[call['policy']] = validate_trace(json.loads((out / (name + 'canopy.json')).read_bytes()),
                                                 json.loads(raw), call['policy'])
    return analyses


EXPERIMENT = follow.Experiment('garden-population-canopy-collection-v1', ARCHIVE_SCHEMA,
                              BASELINE_SHA, PROTOCOL, inputs, arguments, validate_outputs, roster)


if __name__ == '__main__':
    follow.main(__doc__, experiment=EXPERIMENT)
