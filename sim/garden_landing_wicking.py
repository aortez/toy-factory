#!/usr/bin/env python3
"""Frozen late soil-wicking experiment; capture once, audit saved receipts offline."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from functools import cache
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zlib

import garden_landing_root_allocation_audit as historical
import garden_landing_soil_audit as soil
import garden_landing_uptake as uptake
from garden_experiments import compress, digest, snapshot_sources, source_files, write_json
from garden_gallery import contact_sheet
from garden_landing_energy_audit import archived_sources
from garden_resources import require

ROOT, STEP, STOP = historical.ROOT, historical.STEP, historical.STOP
population, allocation, adults = historical.population, historical.previous, historical.adults
RULE = 'garden-landing-wicking-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-wicking-protocol.md'
INPUTS = {historical.INPUT: historical.INPUT_SHA,
          'benchmarks/garden-seasons/landing-root-reachability-results.json.gz':
          '9ee2de6709856f1df93a6a4ae51f7029421ce03dce25162e0bb3a6c0f4f1011a'}
AFTER, START, END = 626580, 626520, 660480
PERIOD, SEED = 60, 0xf7ee4528
ENVIRONMENT = dict(version=1, after=AFTER, period=PERIOD, limit=1)
KINDS, ARMS = ('stand', 'adult', 'direction', 'uptake'), ('off', 'on')
SUBJECTS = {'control': (16, 639480), 'candidate': (17, 644700)}
MODEL_SHA = 'f2dc989380339614dc512f64f11f2bf03f7079c465c4c9bd18895044ec3e1567'


@cache
def inputs():
    require(all(digest(ROOT / p) == sha for p, sha in INPUTS.items()), 'wicking input changed')
    return historical.load_input()


def arguments(saved):
    require(not any(a.startswith('--uptake-') for a in saved['args']), 'input already has uptake observer')
    return saved['args'] + ['--uptake-trace', 'uptake.jsonl', '--uptake-window', f'{START}:{END}']


def check_result(result, case, allocator, arm):
    value = dict(result)
    marker = value.pop('soil_wicking_probe', None)
    require(marker == (ENVIRONMENT if arm == 'on' else None), 'wrong soil environment')
    allocation.common_result(value, case, allocator)
    require(value['tick'] == STOP, 'wrong wicking horizon')


def check_settings(settings, arm):
    name = 'TOY_FACTORY_GARDEN_SOIL_WICKING'
    require(settings.get(name) == ('ON' if arm == 'on' else 'OFF') and
            all(v == 'OFF' for k, v in settings.items() if k.startswith('TOY_FACTORY_GARDEN_') and k != name) and
            settings.get('TOY_FACTORY_SIMULATOR_SANITIZERS') == 'ON' and
            settings.get('TOY_FACTORY_SIMULATOR_PROFILING') == 'ON', 'wrong isolated wicking build')


def build_settings(path, arm):
    settings = dict(line.split(':BOOL=', 1) for line in path.read_text().splitlines()
                    if line.startswith('TOY_FACTORY_') and ':BOOL=' in line)
    check_settings(settings, arm)
    return settings


def same_run(a, b, *, ordinary=False):
    require(a['result'] == b['result'] and a['frame']['sha256'] == b['frame']['sha256'] and
            all(a['traces'][k]['sha256'] == b['traces'][k]['sha256']
                for k in KINDS if not ordinary or k != 'uptake'),
            'historical control changed' if ordinary else 'wicking repeat changed')


def wick(grid, tick, enabled):
    """Independent reference; return a new grid and upward edge-unit counts by row."""
    require(len(grid) == 308 and all(type(v) is int and 0 <= v <= 255 for v in grid) and
            type(tick) is int and tick >= 0 and type(enabled) is bool, 'invalid upward transfer')
    out, moved = list(grid), [0] * 10
    if enabled and tick > AFTER and tick % PERIOD == 0:
        for upper in range(280):
            lower = upper + 28
            if out[lower] - out[upper] >= 2:
                out[lower] -= 1
                out[upper] += 1
                moved[upper // 28] += 1
    require(sum(out) == sum(grid) and all(0 <= v <= 28 for v in moved), 'upward conservation failed')
    return out, moved


def transition(opening, tick, enabled):
    step = soil.transition(opening, SEED, tick // STEP)
    grid, moved = wick(step['grids']['lateral'], tick, enabled)
    rain = sum(step['grids']['rain']) - sum(opening)
    evaporation = sum(v > 0 for v in grid[:28]) if tick % PERIOD == 0 else 0
    if tick % PERIOD == 0:
        grid[:28] = [max(0, v - 1) for v in grid[:28]]
    require(sum(grid) == sum(opening) + rain - evaporation, 'soil transition does not balance')
    return grid, dict(rain=rain, evaporation=evaporation, upward=moved, weather=step['weather'])


def after_births(grid, tick, lives):
    out = list(grid)
    for p in lives:
        if p['parent'] and p['birth_tick'] == tick:
            out[p['column']] -= 12
    require(all(0 <= v <= 255 for v in out), 'birth withdrew unavailable soil water')
    return out


def soil_account(rows, result, enabled, *, capped_after=None):
    require([r['tick'] for r in rows] == list(range(START, END + STEP, STEP)), 'incomplete soil window')
    totals = dict(rain=0, evaporation=0, uptake=0, overflow=0, germination=0, drought_uptake=0,
                  drought_steps=0, drought_rain=0, transitions=0, cell_transitions=0)
    upward, samples, prior = [0] * 10, [], None
    for row in rows:
        tick = row['tick']
        before, after = soil.decode(row['before']), soil.decode(row['after'])
        if prior is not None:
            expected, transport = transition(prior, tick, enabled)
            require(expected == before, f'soil transport differs at {tick}')
            totals['transitions'] += 1
            totals['cell_transitions'] += 308
            for k in ('rain', 'evaporation'): totals[k] += transport[k]
            upward = [a + b for a, b in zip(upward, transport['upward'], strict=True)]
            if transport['weather']['drought']: totals['drought_rain'] += transport['rain']
        resources = {p[0]: p[1] for p in row['plants']}
        require(len(resources) == len(row['plants']), 'duplicate adult resource receipt')
        grid, taken, overflow, stores, nodes, last = before.copy(), Counter(), Counter(), {}, set(), (-1, -1)
        for root in row['roots']:
            require(uptake.vector(root, 11, 0xffffffff), 'invalid root receipt')
            node, owner, slot, col, y, limit, opening, amount, closing, stored, final = root
            require(owner in resources and resources[owner] is not None, 'root lacks adult resource receipt')
            expected_amount = min(limit, opening)
            if capped_after is not None and tick > capped_after:
                expected_amount = min(expected_amount, 512 - stored)
            require(node < 256 and node not in nodes and slot < 8 and 0 <= col < 28 and 0 <= y < 11 and
                    1 <= limit <= 3 and (slot, node) > last and 0 <= stored <= 512 and
                    opening == grid[y * 28 + col] and amount == expected_amount and
                    closing == opening - amount and final == min(512, stored + amount) and
                    stores.get(owner, resources[owner][0]) == stored, 'root transfer/order differs')
            nodes.add(node)
            last, stores[owner] = (slot, node), final
            grid[y * 28 + col] = closing
            taken[owner] += amount
            overflow[owner] += stored + amount - final
        require(grid == after, 'uptake cell balance differs')
        require(set(taken) <= set(resources) and
                all((r is None and taken[i] == overflow[i] == 0) or
                    (r is not None and r[1] == taken[i] and r[2] == overflow[i]) for i, r in resources.items()),
                'soil uptake differs from adult resource receipts')
        prior = after_births(after, tick, result['lineages'])
        require(sum(prior) == row['end_total'], 'post-germination total differs')
        totals['uptake'] += sum(taken.values())
        totals['overflow'] += sum(overflow.values())
        totals['germination'] += sum(after) - sum(prior)
        dry = soil.weather(SEED, tick // STEP)['drought']
        totals['drought_steps'] += dry
        if dry: totals['drought_uptake'] += sum(taken.values())
        samples.append([tick, [sum(prior[n:n + 28]) for n in range(0, 308, 28)],
                        sum(taken.values()), sum(overflow.values())])
    opening, closing = sum(soil.decode(rows[0]['before'])), sum(prior)
    require(opening + totals['rain'] - totals['evaporation'] - totals['uptake'] -
            totals['germination'] == closing and totals['drought_rain'] == 0, 'window balance/drought differs')
    return dict(totals, opening=opening, closing=closing, upward=upward, samples=samples)


def focal_accounts(rows, life, common_end):
    end = life['death_tick'] or STOP
    require(life['birth_tick'] == 590640 and [r['tick'] for r in rows] ==
            list(range(life['birth_tick'], end + STEP, STEP)), 'incomplete selected lifetime')
    bounds = {'lifetime': (life['birth_tick'], end), 'post': (AFTER + STEP, end),
              'fixed': (AFTER + STEP, min(end, common_end))}
    accounts = {k: dict(start=a, end=b, samples=0, payments=0, resources=adults.budget(),
                       energy_unpaid=0, water_unpaid=0) for k, (a, b) in bounds.items()}
    previous = None
    for row in rows:
        require(row['id'] == life['id'] and row['birth'] == life['birth_tick'], 'selected identity changed')
        receipt = adults.transfers(row, life, previous['stages'][-1] if previous else None)
        event = population.payment(row, receipt, previous['roots'] if previous else None,
                                   row['tick'], (64 + row['tick'] // STEP) % 256)
        for account in accounts.values():
            if account['start'] <= row['tick'] <= account['end']:
                adults.accumulate(account['resources'], receipt, account['samples'] == 0)
                account['samples'] += 1
                if event:
                    account['payments'] += 1
                    for r in ('energy', 'water'): account[r + '_unpaid'] += event[r]['unpaid']
        previous = row
    return accounts


def drought_accounts(analysis):
    """After-intervention exposure, not a claim that every death is caused by drought."""
    groups = {k: dict(payments=0, energy_unpaid=0, water_unpaid=0, energy_shortages=0,
                      water_shortages=0, deaths=0) for k in ('drought', 'other')}
    def group(tick): return groups['drought' if soil.weather(SEED, tick // STEP)['drought'] else 'other']
    for p in analysis['plants']:
        life, end = p['life'], p['life']['death_tick'] or STOP
        start = (max(AFTER, life['birth_tick']) // PERIOD + 1) * PERIOD
        for tick in range(start, end + 1, PERIOD): group(tick)['payments'] += 1
        if life['death_tick'] is not None and life['death_tick'] > AFTER:
            group(life['death_tick'])['deaths'] += 1
        for event in p['shortages']:
            if event['tick'] > AFTER:
                for r in ('energy', 'water'):
                    group(event['tick'])[r + '_unpaid'] += event[r]['unpaid']
                    group(event['tick'])[r + '_shortages'] += event[r]['unpaid'] > 0
    return groups


def name_for(case, allocator, arm, label):
    return case['id'] + '-' + allocator + '-' + arm + '-' + label


def calls():
    return [(e, allocator, arm, label) for e in inputs() for allocator in historical.ARMS
            for arm in ARMS for label in (('trace',) if arm == 'off' else historical.LABELS)]


def check_capture(value):
    require(value['rule'] == RULE and value['inputs'] == INPUTS and value['full_replays'] == 24 and
            value['training_runs'] == 0 and value['environment'] == ENVIRONMENT and
            value['protocol_sha256'] == digest(ROOT / PROTOCOL) and value['model_sha256'] == MODEL_SHA and
            value['source_sha256'].get(PROTOCOL) == value['protocol_sha256'] and
            all(value['source_sha256'].get(p) == sha for p, sha in INPUTS.items()), 'wrong wicking provenance')
    require(set(value['builds']) == set(ARMS), 'wrong build panel')
    for arm in ARMS: check_settings(value['builds'][arm]['settings'], arm)
    x, y = (value['builds'][a]['settings'] for a in ARMS)
    require({k for k in x.keys() | y.keys() if x.get(k) != y.get(k)} ==
            {'TOY_FACTORY_GARDEN_SOIL_WICKING'}, 'unrelated build difference')
    require(set(value['runs']) == {name_for(e['case'], a, arm, label) for e, a, arm, label in calls()},
            'wrong comparison/repeat panel')
    for entry, allocator, arm, label in calls():
        name = name_for(entry['case'], allocator, arm, label)
        run, saved = value['runs'][name], entry['arms'][allocator]['runs']['trace']
        check_result(run['result'], entry['case'], allocator, arm)
        require(run['args'] == arguments(saved) and set(run['traces']) == set(KINDS), 'wrong comparison arguments')
        for kind in KINDS:
            file = run['args'][run['args'].index('--' + kind + '-trace') + 1]
            require(run['traces'][kind]['path'] == name + '/' + file + '.gz', 'wrong trace location')
        require(run['frame']['path'] == name + '/' + run['args'][run['args'].index('--framebuffer') + 1],
                'wrong frame location')
        if arm == 'off': same_run(run, saved, ordinary=True)
        if label == 'repeat': same_run(run, value['runs'][name_for(entry['case'], allocator, arm, 'trace')])


def collect(build, variant, out, jobs):
    require(not out.exists() and not out.is_symlink() and
            (out.is_relative_to(ROOT / 'artifacts') or not out.is_relative_to(ROOT)), 'fresh wicking output required')
    inputs()
    sources = source_files()
    out.mkdir(parents=True)
    (out / 'bin').mkdir()
    value = dict(rule=RULE, inputs=INPUTS, full_replays=24, training_runs=0, environment=ENVIRONMENT,
                 protocol_sha256=digest(ROOT / PROTOCOL), model_sha256=MODEL_SHA,
                 source_sha256=sources, builds={}, runs={})
    for arm, directory in (('off', build), ('on', variant)):
        binary, settings = directory / 'toy-factory-garden-landing', directory / 'CMakeCache.txt'
        value['builds'][arm] = dict(binary=digest(binary), cache=digest(settings), settings=build_settings(settings, arm))
        shutil.copy2(binary, out / ('bin/' + arm))
        shutil.copy2(settings, out / (arm + '-CMakeCache.txt'))
    shutil.copy2(ROOT / PROTOCOL, out / 'protocol.md')
    snapshot_sources(out, sources)
    model = population.load_model()[1]
    require(hashlib.sha256(model).hexdigest() == MODEL_SHA, 'wrong model bytes')
    with (out / 'model.tgl').open('xb') as stream: stream.write(model)

    def capture(call):
        entry, allocator, arm, label = call
        case, saved = entry['case'], entry['arms'][allocator]['runs']['trace']
        name = name_for(case, allocator, arm, label)
        directory = out / name
        directory.mkdir()
        (directory / 'frames').mkdir()
        shutil.copy2(out / 'model.tgl', directory / 'model.tgl')
        args = arguments(saved)
        result = population.order.training.native(out / ('bin/' + arm), directory, *args)
        check_result(result, case, allocator, arm)
        write_json(directory / 'result.json', result)
        traces = {}
        for kind in KINDS:
            file = args[args.index('--' + kind + '-trace') + 1]
            target = directory / (file + '.gz')
            compress(directory / file, target)
            traces[kind] = dict(path=name + '/' + file + '.gz', sha256=digest(target))
        frame = args[args.index('--framebuffer') + 1]
        raw = (directory / frame).read_bytes()
        require(len(raw) == 115200 and f'{zlib.crc32(raw):08x}' == result['framebuffer_crc32'], 'wrong captured pixels')
        run = dict(args=args, result=result, traces=traces,
                   frame=dict(path=name + '/' + frame, sha256=digest(directory / frame)))
        if arm == 'off': same_run(run, saved, ordinary=True)
        write_json(directory / 'run.json', run)
        print(name + ': captured', flush=True)
        return name, run

    # A separate analysis command can be retried offline without any extra trials.
    with ThreadPoolExecutor(max_workers=jobs) as pool: value['runs'] = dict(pool.map(capture, calls()))
    check_capture(value)
    gallery = []
    for entry in inputs():
        for allocator in historical.ARMS:
            gallery.append([dict(id=name_for(entry['case'], allocator, arm, 'trace'),
                                 framebuffer=value['runs'][name_for(entry['case'], allocator, arm, 'trace')]['frame']['path'])
                            for arm in ARMS])
    value['gallery'] = contact_sheet(out, gallery)
    value['gallery']['sha256'] = digest(out / 'contact-sheet.png')
    require(source_files() == sources and all(digest(d / 'toy-factory-garden-landing') == value['builds'][a]['binary'] and
            digest(d / 'CMakeCache.txt') == value['builds'][a]['cache'] for a, d in (('off', build), ('on', variant))),
            'source/build changed during wicking capture')
    write_json(out / 'capture.json', value)
    write_json(out / 'manifest.json', dict(rule=RULE, artifacts={str(p.relative_to(out)): digest(p)
                                          for p in sorted(out.rglob('*')) if p.is_file()}))
    return value


def load_bundle(directory):
    manifest = json.loads((directory / 'manifest.json').read_text())
    require(manifest['rule'] == RULE, 'wrong raw comparison')
    for name, sha in manifest['artifacts'].items():
        path = (directory / name).resolve()
        require(path.is_relative_to(directory) and digest(path) == sha, 'raw artifact changed: ' + name)
    value = json.loads((directory / 'capture.json').read_text())
    check_capture(value)
    require(archived_sources(directory / 'source.tar.gz') == value['source_sha256'] and
            digest(directory / 'protocol.md') == value['protocol_sha256'] and
            digest(directory / 'model.tgl') == MODEL_SHA and
            digest(directory / 'contact-sheet.png') == value['gallery']['sha256'], 'frozen provenance changed')
    for arm in ARMS:
        require(digest(directory / ('bin/' + arm)) == value['builds'][arm]['binary'] and
                digest(directory / (arm + '-CMakeCache.txt')) == value['builds'][arm]['cache'] and
                build_settings(directory / (arm + '-CMakeCache.txt'), arm) == value['builds'][arm]['settings'],
                'frozen build changed')
    for name, run in value['runs'].items():
        for item in (run['frame'], *run['traces'].values()):
            require(manifest['artifacts'].get(item['path']) == item['sha256'], 'run/manifest mismatch')
        require(json.loads((directory / name / 'run.json').read_text()) == run and
                json.loads((directory / name / 'result.json').read_text()) == run['result'] and
                digest(directory / name / 'model.tgl') == MODEL_SHA, 'raw call identity changed')
    return value


def prefix(directory, left, right):
    """Hash identical observation prefixes; exclude environment-tagged footers."""
    out = {}
    for kind in KINDS:
        readers = [uptake.observation_rows(directory / r['traces'][kind]['path'], [[START, END]], r['result'])
                   if kind == 'uptake' else
                   allocation.previous.direction_rows(directory / r['traces'][kind]['path'], r['result'], False)
                   if kind == 'direction' else
                   population.trace_rows(directory / r['traces'][kind]['path'], kind, r['result']) for r in (left, right)]
        hashes, count, first = [hashlib.sha256(), hashlib.sha256()], 0, None
        try:
            for a, b in zip(*readers, strict=True):
                require(a['tick'] == b['tick'], 'unequal comparison clocks')
                if a != b and first is None: first = a['tick']
                if a['tick'] <= AFTER:
                    require(a == b, 'wicking changed pre-intervention observations')
                    count += 1
                    for h, row in zip(hashes, (a, b), strict=True):
                        h.update(json.dumps(row, sort_keys=True, separators=(',', ':')).encode() + b'\n')
        finally:
            for reader in readers: reader.close()
        out[kind] = dict(samples=count, sha256=[h.hexdigest() for h in hashes], first_difference=first)
    return out


def extract(directory, run, identity):
    selected, window = [], {}
    for row in population.trace_rows(directory / run['traces']['adult']['path'], 'adult', run['result']):
        plant = next((p for p in row['plants'] if p['id'] == identity), None)
        if plant: selected.append(dict(tick=row['tick'], **plant))
        if START <= row['tick'] <= END: window[row['tick']] = row
    rows = []
    for observed in uptake.observation_rows(directory / run['traces']['uptake']['path'], [[START, END]], run['result']):
        adult = window[observed['tick']]
        rows.append(dict(tick=observed['tick'], before=observed['soil_before'], after=observed['soil_after'],
                         roots=observed['roots'], end_total=adult['soil_water'],
                         plants=[[p['id'], p['uptake'][1] if p['uptake'] else None] for p in adult['plants']]))
    return dict(soil=rows, selected=selected)


def analyze_arm(directory, run, case, allocator):
    return population.analyze_receipts(*(directory / run['traces'][k]['path'] for k in ('stand', 'adult')),
            run['result'], case['guard'], priority_check=allocation.check_priority if allocator == 'candidate' else None)


def derive(receipt, analysis, result, case, arm):
    identity, common_end = SUBJECTS[case['guard']]
    plant = next(p for p in analysis['plants'] if p['life']['id'] == identity)
    selected = focal_accounts(receipt['selected'], plant['life'], common_end)
    full = selected['lifetime']
    require(full['resources'] == plant['resources'] and full['payments'] == plant['payments'] and
            all(full[r + '_unpaid'] == sum(s[r]['unpaid'] for s in plant['shortages']) for r in ('energy', 'water')),
            'selected/population account differs')
    return dict(soil=soil_account(receipt['soil'], result, arm == 'on'), selected=selected,
                drought=drought_accounts(analysis), metrics=population.metrics(result, analysis))


def paired(arms):
    a, b = (arms[k] for k in ARMS)
    first = next((x['tick'] for x, y in zip(a['receipt']['soil'], b['receipt']['soil'], strict=True)
                  if x['before'] != y['before']), None)
    require(first is None or first >= AFTER + PERIOD, 'soil changed before enabled cadence')
    return dict(first_soil_difference=first,
                screen=population.comparison(a['derived']['metrics'], b['derived']['metrics']),
                matching=population.matched_births(a['result'], b['result']))


def check_value(value):
    capture = value['capture']
    check_capture(capture)
    expected = [(e, a) for e in inputs() for a in historical.ARMS]
    require(len(value['pairs']) == len(expected), 'wrong analyzed comparison panel')
    for pair, (entry, allocator) in zip(value['pairs'], expected, strict=True):
        require(pair['case'] == entry['case'] and pair['allocator'] == allocator and set(pair['arms']) == set(ARMS),
                'wrong analyzed case')
        for arm in ARMS:
            a = pair['arms'][arm]
            run = capture['runs'][name_for(entry['case'], allocator, arm, 'trace')]
            require(a['result'] == run['result'], 'analyzed result differs')
            population.check_analysis(a['analysis'], a['result'])
            require(a['derived'] == derive(a['receipt'], a['analysis'], a['result'], entry['case'], arm),
                    'wicking derived account differs')
            if arm == 'off': require(a['analysis'] == entry['arms'][allocator]['analysis'], 'ordinary population changed')
            life = next(p for p in a['result']['lineages'] if p['id'] == SUBJECTS[entry['case']['guard']][0])
            saved = next(p for p in entry['arms'][allocator]['result']['lineages'] if p['id'] == life['id'])
            require(all(life[k] == saved[k] for k in ('birth_tick', 'parent', 'generation', 'species', 'column')),
                    'selected birth identity changed')
        for kind in KINDS:
            p = pair['prefix'][kind]
            require(p['samples'] == ((AFTER - START) // STEP + 1 if kind == 'uptake' else AFTER // STEP) and
                    p['sha256'][0] == p['sha256'][1] and (p['first_difference'] is None or p['first_difference'] >= AFTER + PERIOD),
                    'invalid shared prefix')
        require(pair['comparison'] == paired(pair['arms']), 'paired result differs')


def analyze(directory, capture):
    value = dict(capture=capture, raw_manifest_sha256=digest(directory / 'manifest.json'), pairs=[])
    for entry in inputs():
        for allocator in historical.ARMS:
            arms, runs = {}, {arm: capture['runs'][name_for(entry['case'], allocator, arm, 'trace')] for arm in ARMS}
            shared = prefix(directory, runs['off'], runs['on'])
            for arm in ARMS:
                run = runs[arm]
                analysis = analyze_arm(directory, run, entry['case'], allocator)
                receipt = extract(directory, run, SUBJECTS[entry['case']['guard']][0])
                arms[arm] = dict(result=run['result'], analysis=analysis, receipt=receipt,
                                 derived=derive(receipt, analysis, run['result'], entry['case'], arm))
            value['pairs'].append(dict(case=entry['case'], allocator=allocator, arms=arms,
                                      prefix=shared, comparison=paired(arms)))
            print(entry['case']['id'] + '/' + allocator + ': complete receipts reconciled', flush=True)
    check_value(value)
    return value


def verify(path, bundle=None):
    with gzip.open(path, 'rt') as stream: value = json.load(stream)
    check_value(value)
    if bundle:
        require(digest(bundle / 'manifest.json') == value['raw_manifest_sha256'] and
                load_bundle(bundle) == value['capture'], 'wrong raw source for saved analysis')
        require(analyze(bundle, value['capture']) == value, 'raw re-extraction differs')
    print('Verified wicking controls, repeats, soil balance and population accounts (offline).')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=ROOT / 'build-host')
    parser.add_argument('--variant', type=Path, default=ROOT / 'build-host-wicking')
    parser.add_argument('--out', type=Path, default=ROOT / 'artifacts/garden-landing-wicking-v1')
    parser.add_argument('--jobs', type=int, choices=range(1, 5), default=4)
    parser.add_argument('--analyze', type=Path, help='Analyze an existing raw bundle; never run native code')
    parser.add_argument('--verify', type=Path)
    parser.add_argument('--bundle', type=Path, help='Also rehash/reextract this raw bundle when verifying')
    args = parser.parse_args()
    if args.verify:
        verify(args.verify.resolve(), args.bundle.resolve() if args.bundle else None)
    elif args.analyze:
        require(not args.out.exists() and not args.out.is_symlink(), 'fresh analysis output required')
        directory = args.analyze.resolve()
        value = analyze(directory, load_bundle(directory))
        population.order.recovery.founders.write_gzip(args.out, value)
    else:
        require(args.bundle is None, '--bundle requires --verify')
        collect(args.build.resolve(), args.variant.resolve(), args.out.resolve(), args.jobs)
        print('Capture complete. Run --analyze on this bundle to produce the offline report.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, TypeError, OSError, StopIteration) as error:
        print('wicking comparison failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
