#!/usr/bin/env python3
"""Offline renewal-gate audit of the frozen four-arm uptake-cap panel."""

from __future__ import annotations

import argparse
from collections import Counter, deque
from concurrent.futures import ProcessPoolExecutor
from functools import cache
import gzip
import json
import lzma
from multiprocessing import get_context
from pathlib import Path
import shutil
import sys

import garden_landing_germination as germination
import garden_landing_uptake_limit as previous
from garden_landing_bank_access import FIELDS
from garden_landing_founders import write_gzip
from garden_experiments import digest
from garden_resources import require

ROOT, STEP, STOP, START = previous.ROOT, previous.STEP, previous.STOP, previous.AFTER
DAY = previous.population.DAY
LATE = STOP - 32 * DAY
RULE = 'garden-landing-renewal-gates-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-renewal-gates-protocol.md'
PROTOCOL_SHA = '43970e04c346e2d43d5d4b3ae7382b6df89651963dc43a6514e8c539fd223a3d'
INPUT = 'benchmarks/garden-seasons/landing-uptake-limit-results.json.gz'
INPUT_SHA = '687f354bbeb04b71dc2c8d81b57bccefba0a1f6e2cfa6677f9dd14d517647768'
MANIFEST_SHA = '7b69ecde2d36817c141811f267c8538a467a0d9120703358c8631b790cbd0857'
BLOCKERS = ('cooldown', 'cadence', 'bank', 'dead', 'stress', 'dark', 'generation',
            'energy', 'water', 'flower')
ROW_FIELDS = ('tick', 'sun', 'cold', 'bank', 'plant_order', 'seeds', 'visits', 'resources', 'climate')
RESOURCE_FIELDS = ('id', 'energy_before', 'water_before', 'energy_after', 'water_after', 'flowers', 'nodes')
SEASONS = ('spring', 'summer', 'autumn', 'winter')
population = previous.population


@cache
def source():
    """Trust the pinned, previously verified panel; do not repeat its soil audit."""
    require(digest(ROOT / INPUT) == INPUT_SHA, 'uptake-cap source changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream:
        data = json.load(stream)
    capture = data['capture']
    require(capture['rule'] == previous.RULE and capture['full_replays'] == 48 and
            capture['training_runs'] == 0 and data['raw_manifest_sha256'] == MANIFEST_SHA,
            'wrong uptake-cap capture')
    panel = []
    for order in ('fixed', 'rotating'):
        for guard in ('control', 'candidate'):
            for allocator in ('control', 'candidate'):
                case = f'f7ee4528-{order}-{guard}'
                for arm in previous.ARMS:
                    key = f'{case}-{allocator}-{arm}-trace'
                    run = capture['runs'][key]
                    require(run['result']['tick'] == STOP and run['result']['ledger_start_tick'] == 0,
                            'wrong ledger horizon')
                    panel.append(dict(id=key, case=case, order=order, guard=guard,
                                      allocator=allocator, arm=arm))
    require(len(panel) == 32 and len({p['id'] for p in panel}) == 32, 'wrong primary panel')
    return capture, panel


def header():
    require(digest(ROOT / PROTOCOL) == PROTOCOL_SHA, 'frozen renewal protocol changed')
    return dict(rule=RULE + '-windows', input_sha256=INPUT_SHA, manifest_sha256=MANIFEST_SHA,
                protocol_sha256=PROTOCOL_SHA, window_ticks=[START, STOP], sample_step=STEP,
                row_fields=list(ROW_FIELDS), visit_fields=list(FIELDS), resource_fields=list(RESOURCE_FIELDS))


def packed_row(stand, adult):
    tick = stand['tick']
    require(tick == adult['tick'] and stand['climate']['cold'] == adult['cold'] and
            type(adult['season']) is int and 0 <= adult['season'] < len(SEASONS) and
            stand['climate']['season'] == SEASONS[adult['season']], 'trace climate/clock differs')
    resources = {p['id']: p for p in adult['plants']}
    require(len(resources) == len(adult['plants']) and
            all(set(v) == set(FIELDS) for v in stand['reproduction']), 'trace fields/inventory differ')
    plants = []
    for body in stand['bodies']:
        stages = resources[body['id']]['stages']
        plants.append([body['id'], *stages[3][:2], *stages[4][:2], body['flowers'], body['nodes']])
    return [tick, adult['sun'], adult['cold'], adult['bank'], stand['plant_order'], adult['seeds'],
            [[v[k] for k in FIELDS] for v in stand['reproduction']], plants, stand['climate']]


def extract(bundle, item, capture):
    run = capture['runs'][item['id']]
    traces = {k: run['traces'][k] for k in ('stand', 'adult')}
    manifest = json.loads((bundle / 'manifest.json').read_text())
    paths = {}
    for kind, meta in traces.items():
        path = (bundle / meta['path']).resolve()
        require(path.is_relative_to(bundle) and
                manifest['artifacts'].get(meta['path']) == digest(path) == meta['sha256'],
                'consumed trace changed: ' + meta['path'])
        paths[kind] = path
    rows = []
    for stand, adult in zip(*(population.trace_rows(paths[k], k, run['result'])
                              for k in ('stand', 'adult')), strict=True):
        if START < stand['tick'] <= STOP:
            rows.append(packed_row(stand, adult))
    require(all(digest(paths[k]) == traces[k]['sha256'] for k in paths), 'trace changed while reading')
    return dict(id=item['id'], traces=traces, rows=rows)


def histogram(masks):
    total = sum(masks.values())
    return dict(visits=total, masks=dict(sorted(masks.items(), key=lambda p: int(p[0]))),
                blockers={b: sum(n for m, n in masks.items() if int(m) & (1 << i))
                          for i, b in enumerate(BLOCKERS)},
                sole_blockers={b: masks.get(str(1 << i), 0) for i, b in enumerate(BLOCKERS)})


def bank_access(mask, entry):
    return ('purchased' if mask == 0 else 'other_gates' if mask != 4 else
            'full_at_entry' if entry == 8 else 'earlier_buyers_fill')


def period(result, rows, start, end):
    """Validate all visits; describe only living, daylight, on-cadence visits."""
    require(all(isinstance(r, list) and len(r) == len(ROW_FIELDS) for r in rows), 'wrong packed row')
    seeds = germination.seed_window(result, [dict(tick=r[0], seeds=r[5]) for r in rows], start, end)
    lives = {p['id']: p for p in result['lineages']}
    require(len(lives) == len(result['lineages']), 'duplicate lineage')
    masks, ready_masks, flowers, access, bank = (Counter() for _ in range(5))
    counts = Counter()
    parents = {}
    for values in rows:
        require(len(values) == len(ROW_FIELDS), 'wrong packed row')
        tick, sun, cold, closing, slots, attempts, packed, resources, climate = values
        require(type(cold) is bool and cold == climate['cold'] == (climate['light_percent'] < 65) and
                sun[0] == (64 + tick // STEP) % 256 and
                sun[1] == population.dawn.previous.audit.strength(sun[0], climate['light_percent']) and
                type(closing) is int and 0 <= closing <= 8, 'wrong climate/sun/bank receipt')
        living = {i for i, p in lives.items() if p['birth_tick'] <= tick and
                  (p['death_tick'] is None or p['death_tick'] > tick)}
        rr = {p[0]: p for p in resources}
        require(len(rr) == len(resources) and set(rr) == living and
                all(len(p) == len(RESOURCE_FIELDS) and all(type(v) is int for v in p) and
                    all(0 <= v <= 512 for v in p[1:5]) and 0 <= p[5] <= p[6] <= 32 for p in resources),
                'wrong living resource inventory')
        visits = []
        for packed_visit in packed:
            require(len(packed_visit) == len(FIELDS) and type(packed_visit[-1]) is bool and
                    all(type(v) is int and v >= 0 for v in packed_visit[:-1]), 'wrong visit fields')
            v = dict(zip(FIELDS, packed_visit, strict=True))
            require(v['blockers'] < 1024 and v['bank'] <= 8 and
                    (v['flower'] < 256 or v['flower'] == 65535), 'invalid visit bounds')
            require(v['ready'] + v['immature'] + v['spent'] <= 256 and
                    (v['flower'] == 65535) == (v['ready'] == 0), 'ready flower/index differs')
            if v['id'] in living:
                require(v['ready'] + v['immature'] + v['spent'] == rr[v['id']][5], 'flower census differs')
            visits.append(v)
        resource = dict(sun=sun, bank=closing, plants=[dict(id=p[0], stages=[None, None, None,
                                p[1:3], p[3:5]]) for p in resources])
        population.check_visits(dict(tick=tick, plant_order=slots, reproduction=visits),
                                resource, result, lives, living)
        for attempt in attempts:
            mask, outcome, opened = attempt[3], attempt[8], attempt[10]
            if outcome == 1:
                continue  # Expiry receipts have no germination mask or site census.
            require(bool(mask & 64) == cold and (not mask & (8 | 16 | 64) or opened == 0) and
                    (mask & ~1 != 0 or opened >= 1), 'cold/open-site receipt contradicts gates')
        bank[str(closing)] += 1
        counts['samples_no_seed_at_checks'] += not attempts
        counts['samples_expiry_only'] += bool(attempts) and all(s[8] == 1 for s in attempts)
        mature = [s for s in attempts if s[8] != 1 and s[1] >= 8]
        for bit, label in ((8, 'plant_capacity'), (16, 'node_capacity'), (32, 'spacing'), (64, 'cold')):
            counts['samples_with_' + label] += any(s[3] & bit for s in mature)
        counts['all_visits'] += len(visits)
        counts['living_visits'] += len(living)
        entry = visits[0]['bank'] if visits else closing
        for v in visits:
            if v['id'] not in living or tick % 60 or v['sun'] <= 24:
                continue
            mask = str(v['blockers'])
            masks[mask] += 1
            state = ('ready' if v['ready'] else 'immature_without_ready' if v['immature'] else
                     'spent_only' if v['spent'] else 'absent')
            flowers[state] += 1
            outcome = bank_access(v['blockers'], entry)
            access[outcome] += 1
            p = parents.setdefault(str(v['id']), dict(masks=Counter(), access=Counter()))
            p['masks'][mask] += 1
            p['access'][outcome] += 1
            if v['ready'] and not v['cooldown']:
                ready_masks[mask] += 1
    purchases = [s for s in result['seeds'] if start < s['birth_tick'] <= end]
    require(masks.get('0', 0) == len(purchases), 'purchase denominator omitted births')
    return dict(seed_window=seeds, exposure=dict(counts), bank_post_step=dict(sorted(bank.items())),
                reproduction=dict(daylight_payment=histogram(masks), ready_cooldown_clear=histogram(ready_masks),
                    flowers=dict(flowers), access=dict(access), parents={i: dict(
                        daylight_payment=histogram(p['masks']), access=dict(p['access'])) for i, p in parents.items()}))


def analyze(item, excerpt, capture):
    run = capture['runs'][item['id']]
    require(set(excerpt) == {'id', 'traces', 'rows'} and excerpt['id'] == item['id'] and
            excerpt['traces'] == {k: run['traces'][k] for k in ('stand', 'adult')}, 'wrong excerpt identity')
    require(len(excerpt['rows']) == (STOP - START) // STEP and
            all(r[0] == t for r, t in zip(excerpt['rows'], range(START + STEP, STOP + STEP, STEP), strict=True)),
            'wrong excerpt clock')
    return dict(**item, windows={label: period(run['result'], [r for r in excerpt['rows'] if start < r[0] <= STOP],
                                              start, STOP) for label, start in (('post', START), ('late32', LATE))})


def check_bundle(bundle, capture):
    require(not (bundle / 'FAILED.txt').exists() and digest(bundle / 'manifest.json') == MANIFEST_SHA,
            'wrong/incomplete source bundle')
    manifest = json.loads((bundle / 'manifest.json').read_text())
    require(manifest['rule'] == previous.RULE and
            digest(bundle / 'capture.json') == manifest['artifacts']['capture.json'] and
            json.loads((bundle / 'capture.json').read_text()) == capture, 'raw capture differs from pinned panel')


def extract_one(task):
    bundle, out, item, capture = task
    excerpt = extract(bundle, item, capture)
    result = analyze(item, excerpt, capture)
    write_gzip(out / (item['id'] + '.json.gz'), excerpt)
    print(item['id'] + ': seed and reproduction gates reconciled', flush=True)
    return result


def result_value(worlds, windows):
    require(digest(ROOT / PROTOCOL) == PROTOCOL_SHA and digest(ROOT / INPUT) == INPUT_SHA,
            'renewal-gate input/protocol changed')
    return dict(rule=RULE, input_sha256=INPUT_SHA, manifest_sha256=MANIFEST_SHA,
                protocol_sha256=PROTOCOL_SHA, windows_sha256=digest(windows),
                native_runs=0, training_runs=0, worlds=worlds)


def collect(bundle, out, jobs):
    require(1 <= jobs <= 4 and not out.exists() and not out.is_symlink(), 'fresh output and 1..4 jobs required')
    capture, panel = source()
    check_bundle(bundle, capture)
    out.mkdir(parents=True)
    with ProcessPoolExecutor(max_workers=jobs, mp_context=get_context('fork')) as pool:
        worlds = list(pool.map(extract_one, ((bundle, out, item, capture) for item in panel)))
    windows = out / 'windows.jsonl.xz'
    join_windows(out, windows, panel)
    check_bundle(bundle, capture)
    value = result_value(worlds, windows)
    write_gzip(out / 'results.json.gz', value)
    return value


def join_windows(parts, windows, panel):
    """Lossless standard XZ compression keeps the portable excerpt manageable."""
    with lzma.open(windows, 'xb', preset=6) as zipped:
        zipped.write((json.dumps(header(), sort_keys=True, separators=(',', ':')) + '\n').encode())
        for item in panel:
            with gzip.open(parts / (item['id'] + '.json.gz'), 'rb') as part:
                shutil.copyfileobj(part, zipped)


def verify_one(item, excerpt, capture, bundle):
    if bundle is not None:
        require(extract(bundle, item, capture) == excerpt, 'raw re-extraction differs')
    value = analyze(item, excerpt, capture)
    print(item['id'] + ': verified offline', flush=True)
    return value


def verify(windows, saved, bundle=None, jobs=4):
    require(1 <= jobs <= 4, 'verification needs 1..4 jobs')
    capture, panel = source()
    if bundle is not None:
        check_bundle(bundle, capture)
    worlds = []
    with lzma.open(windows, 'rt') as stream, ProcessPoolExecutor(
            max_workers=jobs, mp_context=get_context('fork')) as pool:
        require(json.loads(next(stream)) == header(), 'wrong window provenance/layout')
        pending = deque()
        for item in panel:
            excerpt = json.loads(next(stream))
            pending.append(pool.submit(verify_one, item, excerpt, capture, bundle))
            if len(pending) >= jobs:
                worlds.append(pending.popleft().result())
        require(not stream.read(), 'extra window records')
        worlds.extend(f.result() for f in pending)
    if bundle is not None:
        check_bundle(bundle, capture)
    value = result_value(worlds, windows)
    with gzip.open(saved, 'rt') as stream:
        require(json.load(stream) == value, 'saved renewal-gate analysis differs')
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--verify', type=Path, help='saved results.json.gz')
    parser.add_argument('--windows', type=Path, help='portable windows.jsonl.xz')
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args(argv)
    if args.verify:
        require(args.windows is not None and args.out is None, 'verification needs windows, not output')
        verify(args.windows.resolve(), args.verify.resolve(), args.bundle.resolve() if args.bundle else None, args.jobs)
    else:
        require(args.bundle is not None and args.out is not None and args.windows is None,
                'extraction needs bundle and fresh output')
        collect(args.bundle.resolve(), args.out.absolute(), args.jobs)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, IndexError, StopIteration) as error:
        print('renewal-gate audit failed: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
