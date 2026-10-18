#!/usr/bin/env python3
"""Fixed placement-only comparison: prefer fewer blockers when every site is blocked."""

import json
import zlib

import population_purchases as purchase

panel, follow, gates = purchase.panel, purchase.follow, purchase.gates
collect, prepare, score = purchase.collect, purchase.prepare, purchase.score
SEED = purchase.SEED
BASELINE = collect.ROOT / 'benchmarks/garden-seasons/leaf-population-purchases-results.json.gz'
BASELINE_SHA = '2d94fda91c831ac484c906588d0c9db5f0400ee031093c7a2aff9ba532b2f24d'
PROTOCOL = collect.ROOT / 'benchmarks/garden-seasons/leaf-population-fallback-protocol.md'
ARCHIVE_SCHEMA = 'garden-population-fallback-evidence-v1'
IDENTITY = dict(kind='fewest-blockers', version=1, founder=2, after_tick=0,
                tie_break='cyclic-from-existing-draw')
HEADER = b'TBF1\x01\x02' + b'\0' * 6


def roster():
    return [dict(id=f'{SEED}-{variant}-{policy}-{mode}', seed=SEED, variant=variant,
                 policy=policy, mode=mode)
            for variant in gates.VARIANTS for policy in ('original', 'fewest') for mode in ('off', 'on')]


def arguments(call):
    return ['--fallback-panel', SEED, call['variant'], call['policy'], call['mode']]


def inputs():
    baseline = purchase.early.archive(BASELINE, BASELINE_SHA, purchase.ARCHIVE_SCHEMA)
    _, models, size = collect.archive_inputs()
    return baseline, models, size


def gate_record(value):
    """Validate the outer placement identity before an explicit comparison projection.

    The projected record is never published as a standalone original-policy run.
    """
    state = bytes.fromhex(value['state_hex'])
    score.require(value['schema'] == 'garden-blocker-fallback-replay-v1' and
                  value['controller_assignment'] == 'family-repair-and-placement' and
                  value['placement_intervention'] == IDENTITY and state.startswith(HEADER),
                  'fallback identity differs')
    result = {k: v for k, v in value.items() if k != 'placement_intervention'}
    result.update(schema='garden-leaf-gate-replay-v1', controller_assignment='scheduled-founder-family',
                  state_hex=state[len(HEADER):].hex())
    return result


def validate_outputs(out, baseline, models, size):
    analyses = {v: {} for v in gates.VARIANTS}
    for call in roster():
        variant, policy, mode = call['variant'], call['policy'], call['mode']
        folder = out / 'runs' / call['id']
        old = f'runs/{SEED}-{variant}-{mode}'
        final_bytes = (folder / 'stdout.json').read_bytes()
        final = json.loads(final_bytes)
        if policy == 'original':
            score.require(final_bytes == prepare.blob(baseline, old + '/stdout.json'),
                          'original-policy final differs')
        expected = {f'tick-{d * score.DAY:010d}.{ext}' for d in follow.DAYS for ext in ('raw', 'json')}
        for day in follow.DAYS:
            name = f'tick-{day * score.DAY:010d}'
            path = folder / 'timeline' / name
            encoded, raw = path.with_suffix('.json').read_bytes(), path.with_suffix('.raw').read_bytes()
            value = json.loads(encoded)
            projected = gate_record(value) if policy == 'fewest' else value
            gates.underlying(projected, variant, models, size, day * score.DAY, seed=SEED, after_tick=0)
            score.require(len(raw) == 115200 and value['framebuffer_crc32'] == f'{zlib.crc32(raw):08x}',
                          'capture differs')
            score.require(score.history_prefix(final, day * score.DAY) == score.history_prefix(value, day * score.DAY),
                          'history prefix differs')
            if policy == 'original':
                score.require(encoded == prepare.blob(baseline, old + '/timeline/' + name + '.json') and
                              raw == prepare.blob(baseline, old + '/timeline/' + name + '.raw'),
                              'original-policy checkpoint differs')
            elif day == 0:
                score.require(projected == json.loads(prepare.blob(baseline, old + '/timeline/' + name + '.json')) and
                              raw == prepare.blob(baseline, old + '/timeline/' + name + '.raw'),
                              'initial state differs')
            if mode == 'on':
                other = out / 'runs' / f'{SEED}-{variant}-{policy}-off' / 'timeline' / name
                score.require(encoded == other.with_suffix('.json').read_bytes() and
                              raw == other.with_suffix('.raw').read_bytes(), 'logging changed checkpoint')
        score.require(final == value, 'stdout differs from endpoint')
        if mode == 'on':
            expected.update(('trace.json', 'purchases.json'))
            for name in ('trace.json', 'purchases.json'):
                if policy == 'original':
                    score.require((folder / 'timeline' / name).read_bytes() ==
                                  prepare.blob(baseline, old + '/timeline/' + name), 'original trace differs')
            anchor = json.loads((folder / 'timeline' / f'tick-{gates.STOP:010d}.json').read_bytes())
            panel.trace.validate_trace(json.loads((folder / 'timeline/trace.json').read_bytes()), anchor)
            purchases = purchase.validate_trace(json.loads((folder / 'timeline/purchases.json').read_bytes()),
                                                final, fewest=policy == 'fewest')
            analyses[variant][policy] = dict(summary=panel.summarize(final), purchases=purchases)
        score.require({p.name for p in (folder / 'timeline').iterdir()} == expected, 'output roster differs')
    return analyses


EXPERIMENT = follow.Experiment('garden-population-fallback-collection-v1', ARCHIVE_SCHEMA,
                              BASELINE_SHA, PROTOCOL, inputs, arguments, validate_outputs, roster)


if __name__ == '__main__':
    follow.main(__doc__, experiment=EXPERIMENT)
