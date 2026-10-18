#!/usr/bin/env python3
"""Four fixed repair variants from day zero across the four archived rainfed seeds."""

import gzip
import json
import zlib

import population_gates_transfer as transfer

follow, gates, collect = transfer.follow, transfer.gates, transfer.collect
prepare, score, trace = transfer.prepare, transfer.score, transfer.trace
BASELINE, BASELINE_SHA = transfer.BASELINE, transfer.BASELINE_SHA
PROTOCOL = collect.ROOT / 'benchmarks/garden-seasons/leaf-population-gates-panel-protocol.md'
ARCHIVE_SCHEMA = 'garden-population-gates-panel-evidence-v1'


def base_run(seed):
    return f'runs/s1-g3-c4-{seed}-rainfed-primary'


def roster():
    return [dict(id=f'{seed}-{variant}-{mode}', seed=seed, variant=variant, mode=mode)
            for seed in score.SEEDS for variant in gates.VARIANTS for mode in ('off', 'on')]


def arguments(call):
    return ['--gate-panel', call['seed'], call['variant'], call['mode']]


def inputs():
    raw = BASELINE.read_bytes()
    score.require(prepare.sha(raw) == BASELINE_SHA, 'population baseline differs')
    baseline = json.loads(gzip.decompress(raw))
    score.require(baseline['schema'] == 'garden-population-evidence-v1', 'population schema differs')
    _, models, size = collect.archive_inputs()
    for seed in score.SEEDS:
        original = json.loads(prepare.blob(baseline, base_run(seed) + '/stdout.json'))
        score.validate_record(original, models['s1-g3-c4'], seed=seed, layout='rainfed',
                              ticks=1376 * score.DAY, uniform_bytes=size)
    return baseline, models, size


def summarize(value):
    result = follow.summarize(value, after_tick=0)
    return result | dict(qualifying_children=transfer.qualifying_children(value, after_tick=0),
                         max_shrub_generation=max(p['generation'] for p in result['shrub_lineages']))


def aggregate(seeds):
    """Descriptive totals over four conditions, never over the logging repeats."""
    score.require(set(seeds) == set(score.SEEDS) and
                  all(set(s) == set(gates.VARIANTS) for s in seeds.values()), 'summary roster differs')
    result = {}
    for variant in gates.VARIANTS:
        rows = [seeds[seed][variant] for seed in score.SEEDS]
        shrubs = [r['families'][1] for r in rows]
        result[variant] = dict(
            conditions=len(rows), maximum_renewal_credits=12 * len(rows),
            capped_renewal_credits=sum(min(2, n) for r in rows for n in r['renewal']['2']['renewal_children']),
            shrub_status=trace.losses.counter((f['status'] for f in shrubs), ('living', 'dormant', 'extinct')),
            founders_alive=sum(f['founder_death_tick'] is None for f in shrubs),
            offspring={k: sum(f['offspring'][k] for f in shrubs)
                       for k in ('born', 'established', 'early_deaths', 'young_alive')},
            competitor_losses={str(f): sum(r['families'][f - 1]['status'] == 'extinct' for r in rows)
                               for f in (1, 3)})
    return result


def validate_outputs(out, baseline, models, size):
    analyses = {seed: {} for seed in score.SEEDS}
    originals = {seed: json.loads(prepare.blob(baseline, base_run(seed) + '/stdout.json'))
                 for seed in score.SEEDS}
    for call in roster():
        folder = out / 'runs' / call['id']
        variant, seed = call['variant'], call['seed']
        final = json.loads((folder / 'stdout.json').read_bytes())
        expected = {f'tick-{d * score.DAY:010d}.{ext}' for d in follow.DAYS for ext in ('raw', 'json')}
        for day in follow.DAYS:
            name = f'tick-{day * score.DAY:010d}'
            prefix = folder / 'timeline' / name
            encoded, raw = prefix.with_suffix('.json').read_bytes(), prefix.with_suffix('.raw').read_bytes()
            value = json.loads(encoded)
            projected = gates.underlying(value, variant, models, size, day * score.DAY,
                                         seed=seed, after_tick=0)
            score.require(len(raw) == 115200 and value['framebuffer_crc32'] == f'{zlib.crc32(raw):08x}',
                          'capture differs')
            score.require(score.history_prefix(final, day * score.DAY) == score.history_prefix(value, day * score.DAY),
                          'history prefix differs')
            if call['mode'] == 'on':
                other = out / 'runs' / f'{seed}-{variant}-off' / 'timeline' / name
                score.require(encoded == other.with_suffix('.json').read_bytes() and
                              raw == other.with_suffix('.raw').read_bytes(), 'trace changed checkpoint')
            if day == 0 or (variant == 'none' and day in (32, 192, 608)):
                old = base_run(seed) + '/timeline/' + name
                score.require(projected == json.loads(prepare.blob(baseline, old + '.json')) and
                              raw == prepare.blob(baseline, old + '.raw'), 'archived population checkpoint differs')
            if variant == 'none':
                score.require(score.history_prefix(value, day * score.DAY) ==
                              score.history_prefix(originals[seed], day * score.DAY), 'unchanged history differs')
        score.require(final == value, 'stdout differs from endpoint')
        if call['mode'] == 'on':
            expected.add('trace.json')
            resources = json.loads((folder / 'timeline/trace.json').read_bytes())
            anchor = json.loads((folder / 'timeline' / f'tick-{gates.STOP:010d}.json').read_bytes())
            trace.validate_trace(resources, anchor)
            analyses[seed][variant] = summarize(final)
        score.require({p.name for p in (folder / 'timeline').iterdir()} == expected, 'output roster differs')
    return dict(seeds=analyses, aggregate=aggregate(analyses))


EXPERIMENT = follow.Experiment('garden-population-gates-panel-collection-v1', ARCHIVE_SCHEMA,
                              BASELINE_SHA, PROTOCOL, inputs, arguments, validate_outputs, roster)


if __name__ == '__main__':
    follow.main(__doc__, experiment=EXPERIMENT)
