#!/usr/bin/env python3
"""Read-only purchase-time comparison of the four fixed early repair variants."""

from collections import Counter
import json
import zlib

import population_gates_early as early

panel = early.panel
follow, gates, collect, prepare, score = panel.follow, panel.gates, panel.collect, panel.prepare, panel.score
BASELINE_SHA = early.ARCHIVE_SHA
PROTOCOL = collect.ROOT / 'benchmarks/garden-seasons/leaf-population-purchases-protocol.md'
ARCHIVE_SCHEMA = 'garden-population-purchases-evidence-v1'
SEED = '9a903368'
FIRST, END = 30 * score.DAY, 35 * score.DAY


def roster():
    return [c for c in panel.roster() if c['seed'] == SEED]


def arguments(call):
    return ['--purchase-panel', SEED, call['variant'], call['mode']]


def inputs():
    baseline = early.archive(early.ARCHIVE, BASELINE_SHA, panel.ARCHIVE_SCHEMA)
    _, models, size = collect.archive_inputs()
    return baseline, models, size


def integer(value, low, high):
    score.require(type(value) is int and low <= value <= high, 'purchase integer out of range')
    return value


def columns(origin, trait):
    result = []
    for i in range(6):
        offset = (5 + trait + i // 2) * (1 if i % 2 else -1)
        column = origin + offset
        if not 0 <= column < 28:
            column = origin - offset
        result.append(max(0, min(27, column)))
    return result


def validate_trace(value, final, *, fewest=False):
    score.require(set(value) == {'schema', 'first_tick', 'end_tick_exclusive', 'limit', 'purchases'} and
                  value['schema'] == 'garden-purchase-trace-v1' and
                  (value['first_tick'], value['end_tick_exclusive'], value['limit']) == (FIRST, END, 256),
                  'purchase trace identity differs')
    rows = value['purchases']
    score.require(type(rows) is list and len(rows) <= 256, 'purchase record limit exceeded')
    expected = Counter((s['birth_tick'], s['parent'], s['column']) for s in final['seeds']
                       if FIRST <= s['birth_tick'] < END)
    actual = Counter()
    previous = FIRST
    focal = []
    for r in rows:
        score.require(set(r) == {'tick', 'parent', 'random', 'origin', 'dispersal', 'blocked_choices',
            'ordinary', 'selected', 'clear', 'legal', 'node_count', 'seed_count', 'columns',
            'site_blockers', 'plants'}, 'purchase fields differ')
        tick = integer(r['tick'], previous, END - 1)
        previous = tick
        score.require(tick % score.STEP == 0, 'purchase tick not aligned')
        parent = integer(r['parent'], 1, len(final['lineages']))
        integer(r['random'], 0, 2**32 - 1)
        integer(r['origin'], 0, 27)
        integer(r['dispersal'], -2, 2)
        # The frozen late-dispersal build reserves fourteen entries. At this
        # early window only six are active; the remaining entries are zero.
        active = columns(r['origin'], r['dispersal'])
        score.require(r['columns'] == active + [0] * 8, 'reachable columns differ')
        integer(r['node_count'], 0, 512)
        integer(r['seed_count'], 0, 15)  # Before appending the paid seed.
        integer(r['ordinary'], 0, 5)
        integer(r['selected'], 0, 5)
        integer(r['blocked_choices'], 0, 63)
        integer(r['clear'], 0, 2**28 - 1)
        integer(r['legal'], 0, 2**28 - 1)
        plants = r['plants']
        score.require(type(plants) is list and 1 <= len(plants) <= 8, 'invalid purchase roster')
        ids = []
        for p in plants:
            score.require(set(p) == {'id', 'parent', 'age_ecology_ticks', 'column', 'species', 'dead',
                'energy', 'water', 'stress', 'nodes', 'last_energy_income', 'last_water_income'},
                'purchase plant fields differ')
            integer(p['id'], 1, len(final['lineages']))
            ids.append(p['id'])
            life = final['lineages'][p['id'] - 1]
            score.require(life['birth_tick'] <= tick and p['parent'] == life['parent'] and
                          p['column'] == life['column'] and p['species'] == life['species'] and
                          type(p['dead']) is bool and p['dead'] ==
                          (life['death_tick'] is not None and life['death_tick'] <= tick),
                          'purchase roster history differs')
            integer(p['age_ecology_ticks'], 0, tick // score.STEP + 1)
            for name in ('energy', 'water', 'nodes'):
                integer(p[name], 0, 65535)
            for name in ('stress', 'last_energy_income', 'last_water_income'):
                integer(p[name], 0, 255)
        score.require(len(set(ids)) == len(ids) and parent in ids and
                      sum(p['nodes'] for p in plants) == r['node_count'], 'purchase roster counts differ')
        living = {p['id'] for p in final['lineages'] if p['birth_tick'] <= tick and
                  (p['death_tick'] is None or p['death_tick'] > tick)}
        score.require({p['id'] for p in plants if not p['dead']} == living, 'living roster incomplete')
        buyer = next(p for p in plants if p['id'] == parent)
        score.require(not buyer['dead'] and buyer['column'] == r['origin'] and
                      buyer['energy'] >= 48 and buyer['water'] >= 24, 'buyer not affordable')
        blockers = {c: [p['id'] for p in plants if abs(c - p['column']) < 3] for c in range(28)}
        clear = sum(1 << c for c in range(28) if not blockers[c])
        legal = clear & sum(1 << c for c in set(active))
        blocked = sum(1 << i for i, c in enumerate(active) if blockers[c])
        score.require((clear, legal, blocked) == (r['clear'], r['legal'], r['blocked_choices']),
                      'spacing masks differ')
        available = [i for i in range(6) if not blocked & (1 << i)]
        ordinary = r['random'] % 6
        if available and blocked & (1 << ordinary):
            ordinary = available[(r['random'] // 6) % len(available)]
        score.require(r['ordinary'] == ordinary, 'ordinary selection differs')
        selected = ordinary
        if fewest and legal == 0 and final['family_roots'][parent - 1] == 2:
            selected = min(((ordinary + i) % 6 for i in range(6)),
                           key=lambda i: len(blockers[active[i]]))
        score.require((legal == 0 and r['selected'] == selected) or
                      (legal & (1 << r['columns'][r['selected']])), 'selected destination not legal')
        score.require(type(r['site_blockers']) is list and len(r['site_blockers']) == 28,
                      'site blocker roster differs')
        for c, mask in enumerate(r['site_blockers']):
            integer(mask, 0, 126)
            score.require(not mask & 1 and bool(mask & 32) == bool(blockers[c]), 'site spacing differs')
        key = (tick, parent, r['columns'][r['selected']])
        actual[key] += 1
        if final['family_roots'][parent - 1] == 2:
            matched = [s for s in final['seeds'] if (s['birth_tick'], s['parent'], s['column']) == key]
            score.require(len(matched) == 1, 'purchase missing from seed history')
            focal.append(dict(observation=r, alternatives=[dict(column=c, blockers=blockers[c])
                             for c in sorted(set(active))], retrospective_seed_outcome=matched[0]))
    score.require(actual == expected, 'purchase coverage differs')
    return dict(total_purchases=len(rows), focal_purchases=len(focal),
                focal_all_blocked=sum(r['observation']['legal'] == 0 for r in focal), focal=focal)


def validate_outputs(out, baseline, models, size):
    if (out / 'recovery.json').exists():
        from population_purchases_recovery import validate_recovery
        validate_recovery(out)
    analyses = {}
    for call in roster():
        folder = out / 'runs' / call['id']
        prefix = f"runs/{call['id']}"
        final_bytes = (folder / 'stdout.json').read_bytes()
        score.require(final_bytes == prepare.blob(baseline, prefix + '/stdout.json'),
                      'archived final output differs')
        final = json.loads(final_bytes)
        expected = {f'tick-{d * score.DAY:010d}.{ext}' for d in follow.DAYS for ext in ('raw', 'json')}
        for day in follow.DAYS:
            name = f'tick-{day * score.DAY:010d}'
            path = folder / 'timeline' / name
            encoded, raw = path.with_suffix('.json').read_bytes(), path.with_suffix('.raw').read_bytes()
            value = json.loads(encoded)
            gates.underlying(value, call['variant'], models, size, day * score.DAY, seed=SEED, after_tick=0)
            score.require(len(raw) == 115200 and value['framebuffer_crc32'] == f'{zlib.crc32(raw):08x}',
                          'capture differs')
            score.require(encoded == prepare.blob(baseline, prefix + '/timeline/' + name + '.json') and
                          raw == prepare.blob(baseline, prefix + '/timeline/' + name + '.raw'),
                          'archived checkpoint differs')
            if call['mode'] == 'on':
                other = out / 'runs' / f"{SEED}-{call['variant']}-off" / 'timeline' / name
                score.require(encoded == other.with_suffix('.json').read_bytes() and
                              raw == other.with_suffix('.raw').read_bytes(), 'trace changed checkpoint')
        if call['mode'] == 'on':
            expected.update(('trace.json', 'purchases.json'))
            score.require((folder / 'timeline/trace.json').read_bytes() ==
                          prepare.blob(baseline, prefix + '/timeline/trace.json'), 'resource trace differs')
            analyses[call['variant']] = validate_trace(json.loads((folder / 'timeline/purchases.json').read_bytes()), final)
        score.require({p.name for p in (folder / 'timeline').iterdir()} == expected, 'output roster differs')
    return analyses


EXPERIMENT = follow.Experiment('garden-population-purchases-collection-v1', ARCHIVE_SCHEMA,
                              BASELINE_SHA, PROTOCOL, inputs, arguments, validate_outputs, roster)


if __name__ == '__main__':
    follow.main(__doc__, experiment=EXPERIMENT)
