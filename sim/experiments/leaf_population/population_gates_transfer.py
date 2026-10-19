#!/usr/bin/env python3
"""Eight fixed gate replays on the second eligible rainfed weather seed."""

import gzip
import json
import zlib

import population_gates_long as follow

gates, collect, prepare, score, trace = follow.gates, follow.collect, follow.prepare, follow.score, follow.trace
SEED = '59818bc3'
BASELINE = trace.losses.ARCHIVE
BASELINE_SHA = trace.losses.ARCHIVE_SHA
BASE_RUN = f'runs/s1-g3-c4-{SEED}-rainfed-primary'
PROTOCOL = collect.ROOT / 'benchmarks/garden-seasons/leaf-population-gates-transfer-protocol.md'
ARCHIVE_SCHEMA = 'garden-population-gates-transfer-evidence-v1'


def inputs():
    raw = BASELINE.read_bytes()
    score.require(prepare.sha(raw) == BASELINE_SHA, 'population baseline differs')
    baseline = json.loads(gzip.decompress(raw))
    score.require(baseline['schema'] == 'garden-population-evidence-v1', 'population schema differs')
    _, models, size = collect.archive_inputs()
    original = json.loads(prepare.blob(baseline, BASE_RUN + '/stdout.json'))
    score.validate_record(original, models['s1-g3-c4'], seed=SEED, layout='rainfed',
                          ticks=1376 * score.DAY, uniform_bytes=size)
    switch = score.history_prefix(original, gates.AFTER)
    living = [p['id'] for p in switch['lineages'] if switch['family_roots'][p['id'] - 1] == 2 and
              p['death_tick'] is None]
    pending = [s for s in switch['seeds'] if switch['family_roots'][s['parent'] - 1] == 2 and
               s['outcome'] == 'pending']
    score.require(living == [7, 18] and not pending and switch['lineages'][1]['death_tick'] is not None,
                  'switch eligibility differs')
    return baseline, models, size


def qualifying_children(value, *, after_tick=gates.AFTER):
    """Label shared-prefix credits without changing the existing scoring rule."""
    plants, result = value['lineages'], []
    for p, root in zip(plants, value['family_roots'], strict=True):
        if (root != 2 or not p['parent'] or not plants[p['parent'] - 1]['parent'] or
                not 192 * score.DAY < p['birth_tick'] <= 576 * score.DAY or
                not trace.losses.established(p, follow.STOP) or
                not trace.losses.established(plants[p['parent'] - 1], follow.STOP)):
            continue
        result.append(dict(lineage=p['id'], parent=p['parent'], birth_tick=p['birth_tick'],
                           shared_prefix=p['birth_tick'] <= after_tick,
                           window=(p['birth_tick'] - 192 * score.DAY - 1) // (64 * score.DAY)))
    expected = score.family_score(value, 2, 192)['renewal_children']
    score.require([sum(p['window'] == w for p in result) for w in range(6)] == expected,
                  'renewal child accounting differs')
    return result


def summarize(value):
    result = follow.summarize(value)
    return result | dict(qualifying_children=qualifying_children(value),
                         switch_survivors=[p for p in result['shrub_lineages'] if p['id'] in (7, 18)])


def validate_outputs(out, baseline, models, size):
    analyses, checkpoints, logs = {}, {}, {}
    original = json.loads(prepare.blob(baseline, BASE_RUN + '/stdout.json'))
    for call in gates.roster():
        folder = out / 'runs' / call['id']
        variant = call['variant']
        final = json.loads((folder / 'stdout.json').read_bytes())
        expected = {f'tick-{d * score.DAY:010d}.{ext}' for d in follow.DAYS for ext in ('raw', 'json')}
        for day in follow.DAYS:
            name = f'tick-{day * score.DAY:010d}'
            prefix = folder / 'timeline' / name
            encoded, raw = prefix.with_suffix('.json').read_bytes(), prefix.with_suffix('.raw').read_bytes()
            value = json.loads(encoded)
            projected = gates.underlying(value, variant, models, size, day * score.DAY, seed=SEED)
            score.require(len(raw) == 115200 and value['framebuffer_crc32'] == f'{zlib.crc32(raw):08x}',
                          'capture differs')
            score.require(score.history_prefix(final, day * score.DAY) == score.history_prefix(value, day * score.DAY),
                          'history prefix differs')
            checkpoints[call['id'], day] = projected, raw
            if call['mode'] == 'on':
                other = out / 'runs' / f'{variant}-off' / 'timeline' / name
                score.require(encoded == other.with_suffix('.json').read_bytes() and
                              raw == other.with_suffix('.raw').read_bytes(), 'trace changed checkpoint')
            if day in (0, 32, 192) or (variant == 'none' and day == 608):
                old = BASE_RUN + '/timeline/' + name
                score.require(projected == json.loads(prepare.blob(baseline, old + '.json')) and
                              raw == prepare.blob(baseline, old + '.raw'), 'archived population checkpoint differs')
            if day == 208:
                score.require(score.history_prefix(value, gates.AFTER) == score.history_prefix(original, gates.AFTER),
                              'archived switch history differs')
        score.require(final == value, 'stdout differs from endpoint')
        if call['mode'] == 'on':
            expected.add('trace.json')
            resources = json.loads((folder / 'timeline/trace.json').read_bytes())
            anchor = json.loads((folder / 'timeline' / f'tick-{gates.STOP:010d}.json').read_bytes())
            trace.validate_trace(resources, anchor)
            logs[variant] = resources
            analyses[variant] = summarize(final)
        score.require({p.name for p in (folder / 'timeline').iterdir()} == expected, 'output roster differs')
    for variant in gates.VARIANTS:
        for day in (0, 32, 192, 208):
            score.require(checkpoints[f'{variant}-on', day] == checkpoints['none-on', day],
                          'intervention changed pre-switch trajectory')
        before = lambda d: [r for r in d['plant_days'] if r['day'] < 208]
        score.require(before(logs[variant]) == before(logs['none']) and
                      logs[variant]['seed_days'][:208] == logs['none']['seed_days'][:208],
                      'intervention changed pre-switch trace')
    return analyses


def arguments(call):
    return ['--gate-transfer', call['variant'], call['mode']]


EXPERIMENT = follow.Experiment('garden-population-gates-transfer-collection-v1', ARCHIVE_SCHEMA,
                              BASELINE_SHA, PROTOCOL, inputs, arguments, validate_outputs)


if __name__ == '__main__':
    follow.main(__doc__, experiment=EXPERIMENT)
