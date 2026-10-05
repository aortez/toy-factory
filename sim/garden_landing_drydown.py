#!/usr/bin/env python3
"""Replay a pinned executable with passive, bounded root/soil observations."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from functools import cache
import gzip
import json
from pathlib import Path
import shutil
import sys

import garden_landing_seed_spending_audit as spending
import garden_landing_uptake as uptake
from garden_experiments import compress, digest, snapshot_sources, source_files, write_json
from garden_landing_energy_audit import archived_sources
from garden_resources import require

ROOT, STEP, STOP = spending.ROOT, spending.STEP, spending.STOP
population = spending.population
ARMS, LABELS = spending.ARMS, spending.LABELS
RULE = 'garden-landing-drydown-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-drydown-protocol.md'
INPUT = 'benchmarks/garden-seasons/landing-seed-spending-audit-results.json.gz'
INPUTS = spending.INPUTS | {INPUT: '2a1de1c9c6a2574a6e47d9bd7bb787038a87a4e19a0af4f5e8b6268e3736baef'}
START, END = 626520, 629760
SPANS = [[START, END]]
ANCHORS = {'control': 626580, 'candidate': 626520}
KINDS = ('stand', 'adult', 'direction', 'uptake')
NATIVE_FILES = {
    'manifest.json': spending.previous.MANIFEST_SHA,
    'capture.json': '881ec337bd11c4f1e98773c0aa0d48292378670922c5d43ab01012c32d5bfb8b',
    'source.tar.gz': '15e30782272394b4afa03f92558ec82e9bee5f30c4fc1bca3b45f0f75b9d1314',
    'CMakeCache.txt': 'f93e432ba3d6c2704864bf10ffb3dddcc93e442878d605864862a5180184b0e6',
    'bin/garden-landing': 'd8aff498a26245936959222e4beadad935bc3484a20cd7fd0e897e26e6e34639',
}
MODEL_SHA = 'f2dc989380339614dc512f64f11f2bf03f7079c465c4c9bd18895044ec3e1567'


@cache
def inputs():
    require(all(digest(ROOT / p) == sha for p, sha in INPUTS.items()), 'drying input changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream:
        saved = json.load(stream)
    subjects = [dict(s) for s in spending.inputs()]
    require([a['case']['id'] for a in saved['analysis']] ==
            [s['entry']['case']['id'] for s in subjects], 'wrong drying panel')
    for subject, analysis in zip(subjects, saved['analysis'], strict=True):
        anchor = analysis['last_shared_capacity']
        require(anchor['stage'] == 'after_uptake_before_maintenance' and
                anchor['tick'] == ANCHORS[subject['entry']['case']['guard']], 'wrong drying anchor')
        subject['drying_anchor'] = anchor
    return subjects


def arguments(historical):
    require(not any(arg.startswith('--uptake-') for arg in historical['args']), 'baseline already observed')
    return historical['args'] + ['--uptake-trace', 'uptake.jsonl', '--uptake-window', f'{START}:{END}']


def check_run(run, historical, name):
    args = arguments(historical)
    require(run['args'] == args and run['result'] == historical['result'] and
            set(run['traces']) == set(KINDS), 'observer changed result/arguments')
    for kind in KINDS:
        item = run['traces'][kind]
        require(item['path'] == name + '/' + args[args.index('--' + kind + '-trace') + 1] + '.gz',
                'wrong trace path')
        if kind != 'uptake':
            require(item['sha256'] == historical['traces'][kind]['sha256'], 'observer changed ordinary trace')
    require(run['frame']['path'] == name + '/' + args[args.index('--framebuffer') + 1] and
            run['frame']['sha256'] == historical['frame']['sha256'], 'observer changed pixels')


def root_water(row, identity):
    """Cell-local ordered water attribution, independently reconciled below."""
    before = bytes.fromhex(row['soil_before'])
    consumers, cells = defaultdict(Counter), {}
    for root in row['roots']:
        _, owner, _, col, y, limit, opening, taken, _, stored, final = root
        cell = y * 28 + col
        if owner == identity:
            own = consumers[cell][owner]
            other = sum(consumers[cell].values()) - own
            values = (limit, taken, limit - min(limit, before[cell]), min(limit, before[cell]) - taken,
                      min(limit, opening + own) - taken, min(limit, opening + other) - taken,
                      stored + taken - final)
            total = cells.setdefault(cell, [0] * len(uptake.WATER))
            cells[cell] = [a + b for a, b in zip(total, values, strict=True)]
        consumers[cell][owner] += taken
    return cells


def soil_budget(rows):
    """All-cell balance; between-step changes include every non-uptake process."""
    require(bool(rows), 'empty soil window')
    first, last = bytes.fromhex(rows[0]['soil_before']), bytes.fromhex(rows[-1]['soil_after'])
    net, positive, negative = [0] * 308, [0] * 308, [0] * 308
    consumers, visits = defaultdict(Counter), defaultdict(Counter)
    prior = None
    for row in rows:
        before, after = bytes.fromhex(row['soil_before']), bytes.fromhex(row['soil_after'])
        require(len(before) == len(after) == 308, 'wrong soil size')
        if prior is not None:
            for cell, (a, b) in enumerate(zip(prior, before, strict=True)):
                net[cell] += b - a
                positive[cell] += max(0, b - a)
                negative[cell] += max(0, a - b)
        taken = Counter()
        for r in row['roots']:
            cell = r[4] * 28 + r[3]
            taken[cell] += r[7]
            consumers[cell][str(r[1])] += r[7]
            visits[cell][str(r[1])] += 1
        require(all(a - taken[c] == b for c, (a, b) in enumerate(zip(before, after, strict=True))),
                'soil step balance differs')
        prior = after
    out = []
    for cell in range(308):
        require(first[cell] + net[cell] - sum(consumers[cell].values()) == last[cell], 'soil balance differs')
        out.append({'cell': cell, 'column': cell % 28, 'row': cell // 28, 'opening': first[cell],
                    'closing': last[cell], 'between_step_net': net[cell], 'between_step_positive': positive[cell],
                    'between_step_negative': negative[cell], 'consumed': dict(consumers[cell]),
                    'root_visits': dict(visits[cell])})
    return out


def extract(out, run):
    result = run['result']
    observations = list(uptake.observation_rows(out / run['traces']['uptake']['path'], SPANS, result))
    adults = [r for r in population.trace_rows(out / run['traces']['adult']['path'], 'adult', result)
              if START - STEP <= r['tick'] <= END]
    return {'uptake': observations, 'adult': adults}


def analyze(subject, arm, receipt):
    result = subject['entry']['arms'][arm]['result']
    identity, anchor = subject['id'], subject['drying_anchor']['tick']
    rows, adults = receipt['uptake'], receipt['adult']
    require([r['tick'] for r in rows] == list(range(START, END + STEP, STEP)) and
            [r['tick'] for r in adults] == list(range(START - STEP, END + STEP, STEP)), 'incomplete drying window')
    lives = {p['id']: p for p in result['lineages']}
    totals, cells, samples, geometry = [0] * len(uptake.WATER), {}, [], []
    counts = {k: 0 for k in ('frames', 'roots', 'leaves', 'sources')}
    for n, row in enumerate(rows):
        adult, prior = adults[n + 1], {p['id']: p for p in adults[n]['plants']}
        resources = {p['id']: p for p in adult['plants']}
        require(len(resources) == len(adult['plants']) and len(prior) == len(adults[n]['plants']) and
                adult['sun'] == row['sun'][:2], 'duplicate adult or different sun')
        expected = {i for i, p in lives.items() if p['birth_tick'] <= row['tick'] and
                    (p['death_tick'] is None or p['death_tick'] >= row['tick'])}
        require(set(resources) == expected, 'incomplete adult population')
        require(Counter(r[1] for r in row['roots']) == Counter({
            i: prior.get(i, p)['roots'] for i, p in resources.items() if p['uptake'] is not None}),
            'missing/extra pre-growth root visit')
        observed = uptake.attribute(row, resources, lives)
        target = resources[identity]
        packed = [target[k] for k in spending.previous.PACKED_FIELDS]
        require(packed == subject['resources'][arm][(row['tick'] - spending.START) // STEP],
                'target historical resource receipt differs')
        parts = root_water(row, identity)
        water = [sum(v[j] for v in parts.values()) for j in range(len(uptake.WATER))]
        require(water == observed[identity]['water'] and water[0] == sum(water[1:4]), 'cell attribution differs')
        samples.append([row['tick'], water])
        shape = [r[:6] for r in row['roots'] if r[1] == identity]
        if not geometry or shape != geometry[-1]['roots']:
            geometry.append({'tick': row['tick'], 'roots': shape})
        counts['frames'] += 1
        for k in ('roots', 'leaves', 'sources'): counts[k] += len(row[k])
        if row['tick'] <= anchor:
            continue
        totals = [a + b for a, b in zip(totals, water, strict=True)]
        for cell, values in parts.items():
            cells[cell] = [a + b for a, b in zip(cells.get(cell, [0] * len(totals)), values, strict=True)]
    budget = subject['drying_anchor']['arms'][arm]['resources']['water']
    require(totals[1] == budget['income'] and totals[-1] == budget['overflow'], 'terminal water budget differs')
    return {'id': identity, 'anchor': anchor, 'counts': counts, 'geometry': geometry, 'samples': samples,
            'post_anchor_water': dict(zip(uptake.WATER, totals, strict=True)),
            'last_positive': max((tick for tick, w in samples if w[1]), default=None),
            'target_cells': [{'cell': c, 'column': c % 28, 'row': c // 28,
                              **dict(zip(uptake.WATER, values, strict=True))} for c, values in sorted(cells.items())],
            'soil': soil_budget(rows), 'post_anchor_soil': soil_budget([r for r in rows if r['tick'] > anchor])}


def compare(arms):
    cells = {a: {r['cell']: r for r in arms[a]['analysis']['target_cells']} for a in ARMS}
    out = []
    for cell in sorted(set(cells['control']) | set(cells['candidate'])):
        values = {a: cells[a].get(cell, dict.fromkeys(uptake.WATER, 0)) for a in ARMS}
        out.append({'cell': cell, 'column': cell % 28, 'row': cell // 28,
                    'arms': {a: {k: values[a][k] for k in uptake.WATER} for a in ARMS},
                    'retained_delta': values['candidate']['taken'] - values['candidate']['overflow'] -
                                      values['control']['taken'] + values['control']['overflow']})
    return out


def check_value(value):
    subjects = inputs()
    require(value['rule'] == RULE and value['inputs'] == INPUTS and value['full_replays'] == 16 and
            value['training_runs'] == 0 and value['window'] == SPANS and value['native_files'] == NATIVE_FILES and
            value['model_sha256'] == MODEL_SHA and value['protocol_sha256'] == digest(ROOT / PROTOCOL) and
            value['source_sha256'].get(PROTOCOL) == value['protocol_sha256'] and
            all(value['source_sha256'].get(p) == sha for p, sha in INPUTS.items()) and
            [c['case'] for c in value['cases']] == [s['entry']['case'] for s in subjects], 'wrong drying provenance/panel')
    for subject, case in zip(subjects, value['cases'], strict=True):
        require(set(case['arms']) == set(ARMS), 'wrong drying arms')
        for arm in ARMS:
            a = case['arms'][arm]
            historical = subject['entry']['arms'][arm]['runs']['trace']
            require(set(a['runs']) == set(LABELS), 'wrong drying repeats')
            for label, run in a['runs'].items():
                check_run(run, historical, case['case']['id'] + '-' + arm + '-' + label)
            require(len({r['traces']['uptake']['sha256'] for r in a['runs'].values()}) == 1, 'uptake repeat differs')
            require(spending.previous.fingerprint(a['receipt']) == a['receipt_sha256'], 'drying receipt changed')
            require(analyze(subject, arm, a['receipt']) == a['analysis'], 'drying analysis differs')
        require(case['cells'] == compare(case['arms']), 'paired cell comparison differs')


def check_native(bundle):
    require(all(digest(bundle / p) == sha for p, sha in NATIVE_FILES.items()), 'archived executable/provenance changed')
    capture = json.loads((bundle / 'capture.json').read_text())
    require(archived_sources(bundle / 'source.tar.gz') == capture['source_sha256'], 'native source archive differs')
    return capture


def collect(bundle, out, jobs):
    require(not out.exists() and (out.is_relative_to(ROOT / 'artifacts') or not out.is_relative_to(ROOT)),
            'fresh drying output required')
    subjects = inputs()
    check_native(bundle)
    model = population.load_model()[1]
    sources = source_files()
    out.mkdir(parents=True)
    for name in NATIVE_FILES:
        target = out / 'native' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundle / name, target)
    shutil.copy2(ROOT / PROTOCOL, out / 'protocol.md')
    snapshot_sources(out, sources)
    value = {'rule': RULE, 'inputs': INPUTS, 'full_replays': 16, 'training_runs': 0, 'window': SPANS,
             'native_files': NATIVE_FILES, 'model_sha256': MODEL_SHA, 'protocol_sha256': digest(ROOT / PROTOCOL),
             'source_sha256': sources, 'cases': []}
    write_json(out / 'capture.json', value)

    def capture(call):
        subject, arm, label = call
        name = subject['entry']['case']['id'] + '-' + arm + '-' + label
        directory = out / name
        directory.mkdir()
        (directory / 'frames').mkdir()
        with (directory / 'model.tgl').open('xb') as stream: stream.write(model)
        require(digest(directory / 'model.tgl') == MODEL_SHA, 'model changed')
        historical = subject['entry']['arms'][arm]['runs']['trace']
        args = arguments(historical)
        result = population.order.training.native(out / 'native/bin/garden-landing', directory, *args)
        write_json(directory / 'result.json', result)
        traces = {}
        for kind in KINDS:
            file = args[args.index('--' + kind + '-trace') + 1]
            target = directory / (file + '.gz')
            compress(directory / file, target)
            traces[kind] = {'path': name + '/' + target.name, 'sha256': digest(target)}
        frame = args[args.index('--framebuffer') + 1]
        run = {'args': args, 'result': result, 'traces': traces,
               'frame': {'path': name + '/' + frame, 'sha256': digest(directory / frame)}}
        write_json(directory / 'run.json', run)
        check_run(run, historical, name)
        print(name + ': observer neutral against historical result, traces and pixels', flush=True)
        return run

    calls = [(s, arm, label) for s in subjects for arm in ARMS for label in LABELS]
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        captured = iter(pool.map(capture, calls))
        # Exhaust before analysis; scheduling still preserves the frozen call order.
        results = list(captured)
    captured = iter(results)
    for subject in subjects:
        arms = {}
        for arm in ARMS:
            runs = {label: next(captured) for label in LABELS}
            receipt = extract(out, runs['trace'])
            arms[arm] = {'runs': runs, 'receipt': receipt,
                         'receipt_sha256': spending.previous.fingerprint(receipt),
                         'analysis': analyze(subject, arm, receipt)}
            print(subject['entry']['case']['id'] + '/' + arm + ': every observed uptake reconciled', flush=True)
        value['cases'].append({'case': subject['entry']['case'], 'arms': arms, 'cells': compare(arms)})
    check_value(value)
    require(source_files() == sources and archived_sources(out / 'source.tar.gz') == sources, 'capture sources changed')
    check_native(out / 'native')
    population.order.recovery.founders.write_gzip(out / 'results.json.gz', value)
    write_json(out / 'manifest.json', {'rule': RULE, 'status': 'complete', 'artifacts': {
        str(p.relative_to(out)): digest(p) for p in sorted(out.rglob('*')) if p.is_file()}})
    return value


def verify(path):
    out = path if path.is_dir() else None
    if out:
        manifest = json.loads((out / 'manifest.json').read_text())
        require(manifest['rule'] == RULE and manifest['status'] == 'complete' and not (out / 'FAILED.txt').exists(),
                'incomplete drying bundle')
        require(set(manifest['artifacts']) == {str(p.relative_to(out)) for p in out.rglob('*')
                if p.is_file() and p != out / 'manifest.json'}, 'drying inventory differs')
        for name, sha in manifest['artifacts'].items():
            p = (out / name).resolve()
            require(p.is_relative_to(out) and digest(p) == sha, 'drying artifact changed')
        path = out / 'results.json.gz'
    with gzip.open(path, 'rt') as stream: value = json.load(stream)
    check_value(value)
    if out:
        check_native(out / 'native')
        require(archived_sources(out / 'source.tar.gz') == value['source_sha256'] and
                digest(out / 'protocol.md') == value['protocol_sha256'], 'frozen analysis sources differ')
        require(json.loads((out / 'capture.json').read_text()) == value | {'cases': []}, 'capture metadata differs')
        for case in value['cases']:
            for arm, a in case['arms'].items():
                for label, run in a['runs'].items():
                    directory = out / (case['case']['id'] + '-' + arm + '-' + label)
                    require(json.loads((directory / 'run.json').read_text()) == run and
                            json.loads((directory / 'result.json').read_text()) == run['result'] and
                            digest(directory / 'model.tgl') == MODEL_SHA, 'raw run/model differs')
                    for item in (run['frame'], *run['traces'].values()):
                        require(digest(out / item['path']) == item['sha256'], 'raw receipt differs')
                require(extract(out, a['runs']['trace']) == a['receipt'], 'raw observation extraction differs')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, default=ROOT / 'artifacts/garden-landing-root-allocation-v1')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--verify', type=Path)
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    if args.verify:
        require(args.out is None, 'verification cannot capture')
        verify(args.verify.resolve())
        print('Verified drying receipts, water attribution and exact historical neutrality; no native calls.')
    else:
        require(args.out is not None and 1 <= args.jobs <= 16, 'fresh output and 1..16 jobs required')
        out = args.out.resolve()
        require(not out.exists(), 'fresh drying output required')
        try:
            collect(args.bundle.resolve(), out, args.jobs)
        except Exception as error:
            if out.is_dir():
                with (out / 'FAILED.txt').open('x') as stream: stream.write(str(error) + '\n')
            raise
        print('Completed all 16 passive replays; no policy change.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError, KeyError, StopIteration) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
