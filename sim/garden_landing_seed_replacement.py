#!/usr/bin/env python3
"""Fixed paid-own-seed replacement comparison; collect once, reanalyze offline."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import copy
from functools import cache
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zlib

import garden_landing_second_opening_audit as previous
import garden_landing_opening_opportunities as opportunities
from garden_experiments import compress, digest, snapshot_sources, source_files, write_json
from garden_gallery import contact_sheet
from garden_landing_energy_audit import archived_sources
from garden_landing_founders import write_gzip
from garden_landing_root_allocation_audit import fingerprint
from garden_landing_training import native
from garden_resources import require

ROOT, BASE, STOP, STEP = previous.ROOT, previous.BASE, previous.STOP, previous.STEP
capture, window = previous.capture, previous.window
followup, bank, late = capture.followup, window.bank, opportunities.late
DAY, FIRST = capture.DAY, capture.FIRST
RULE = 'garden-landing-seed-replacement-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-seed-replacement-protocol.md'
PROTOCOL_SHA = '394cbfce5b7945b2acaa77c1589d09bf7f9b4a13d37e32877271ddadc025f279'
INPUT = 'benchmarks/garden-seasons/landing-opening-opportunities-results.json.gz'
INPUT_SHA = '5ea9fab6e1a8d4d5a9fc4aa90683959851d331196bb7192cbf9b47bc46d019ce'
PHASES = ('control', 'treatment', 'repeat', 'plain')
KINDS = (*capture.KINDS, 'replacement')
SOURCES = tuple(sorted({*opportunities.SOURCES, 'sim/garden_landing_seed_replacement.py'}))
CHANGED_RUNTIME = {'src/garden_agent.h', 'src/garden_seed_audit.h', 'src/garden_world.c',
                   'sim/garden_landing_placement.h', 'sim/garden_landing_growth.c',
                   'sim/garden_landing_run.c', 'sim/garden_landing_ledger.h',
                   'sim/garden_landing_ledger.c', 'sim/garden_landing_cli.c',
                   'sim/garden_landing_seed_replacement_test.c'}


@cache
def inputs():
    require(digest(ROOT / PROTOCOL) == PROTOCOL_SHA and digest(ROOT / INPUT) == INPUT_SHA,
            'replacement protocol/input changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream:
        opportunities.check_value(json.load(stream))
    return previous.inputs()


def tagged(base, after):
    h = 2166136261
    for byte in b'GLX1' + int(base, 16).to_bytes(4, 'little') + after.to_bytes(4, 'little'):
        h = ((h ^ byte) * 16777619) & 0xffffffff
    return f'{h:08x}'


def arguments(key, phase):
    require(key in inputs()['panel'] and phase in PHASES, 'wrong replacement call')
    args = list(inputs()['runs']['treatment'][key]['args'])
    if phase != 'control':
        args += ['--seed-replace-after', str(BASE)]
    if phase == 'plain':
        for flag in ('--stand-trace', '--stand-start', '--stand-stop', '--adult-trace', '--adult-start',
                     '--adult-stop', '--direction-trace', '--reach-trace'):
            i = args.index(flag)
            del args[i:i + 2]
        args.remove('--stand-dawn')
    else:
        args += ['--replacement-trace', 'replacement.jsonl']
    return args


def index_result(result):
    """Validate the unchanged subledger, then the explicit new terminal fate."""
    lives = {p['id']: p for p in result['lineages']}
    seeds = {(s['parent'], s['birth_tick']): s for s in result['seeds']}
    require(len(seeds) == len(result['seeds']), 'duplicate replacement seed identity')
    replaced = [s for s in seeds.values() if s['outcome'] == 'replaced']
    counts = Counter(s['parent'] for s in replaced)
    projected = copy.deepcopy(result['lineages'])
    for p in projected:
        p['seeds_created'] -= counts[p['id']]
        p['late_seeds_created'] -= counts[p['id']]
    # Omit replaced entries, never relabel them as expiries or pending seeds.
    # This validates all ancestry and all unchanged seed fates/counts.
    bank.descendants.index_records(projected, [s for s in seeds.values() if s['outcome'] != 'replaced'], 0, STOP)
    for s in replaced:
        p, birth, end = lives[s['parent']], s['birth_tick'], s['end_tick']
        require(type(birth) is int and type(end) is int and 0 < birth < end <= STOP and
                BASE < end < birth + 8192 * STEP and birth % STEP == end % STEP == 0 and
                p['birth_tick'] <= birth and (p['death_tick'] is None or end < p['death_tick']) and
                s['child_id'] is None and s['lifetime_ecology_ticks'] == 8192 and
                s['species'] == p['species'] and s['generation'] == p['generation'] + 1 and
                type(s['column']) is int and 0 <= s['column'] < 28, 'invalid replaced fate')
    require(result['births'] == sum(p['parent'] != 0 for p in lives.values()) and
            result['deaths'] == sum(p['death_tick'] is not None for p in lives.values()) and
            result['living'] == len(lives) - result['deaths'] and
            result['seed_bank'] == sum(s['outcome'] == 'pending' for s in seeds.values()), 'ledger totals differ')
    return lives, seeds


def check_result(result, key, phase):
    saved = inputs()['runs']['treatment'][key]['result']
    active = phase != 'control'
    require(set(result) == set(saved) | ({'seed_replacement_probe'} if active else set()), 'wrong result schema')
    if not active:
        require(result == saved, 'archived control result changed')
    else:
        require(result['seed_replacement_probe'] == dict(version=1, after=BASE), 'wrong replacement rule')
    for name in ('tick', 'schema_version', 'kind', 'scenario', 'seed', 'model', 'rules', 'run_version',
                 'gardener', 'irrigation', 'seed_lifetime_ecology_ticks', 'ledger_start_tick', 'climate',
                 *(k for k in saved if k.endswith('_probe') and k not in ('turnover_probe', 'second_turnover_probe'))):
        require(result[name] == saved[name], 'unrelated configuration changed: ' + name)
    for name in ('turnover_probe', 'second_turnover_probe'):
        expected = dict(saved[name])
        if active:
            for field in ('before_run_hash', 'after_run_hash'):
                expected[field] = tagged(expected[field], BASE)
        require(result[name] == expected, 'pre-onset event changed')
    require(followup.prefix_ledgers(result, BASE) == followup.prefix_ledgers(saved, BASE), 'pre-onset ledger changed')
    world = inputs()['panel'][key]
    h = capture.first.probe_hash(result['placement_run_hash'], FIRST, world['first_target'])
    require(result['run_hash'] == capture.first.probe_hash(h, BASE, world['target']), 'wrong event run hash')
    index_result(result)


def replacement_rows(path, after):
    with gzip.open(path, 'rt') as stream:
        require(json.loads(next(stream)) == dict(schema='landing-seed-replacement-trace-v1', after=after),
                'wrong replacement header')
        for tick in range(STEP, STOP + STEP, STEP):
            row = json.loads(next(stream))
            require(set(row) == {'tick', 'replacements'} and row['tick'] == tick and
                    type(row['replacements']) is list and len(row['replacements']) <= 8 and
                    (tick > after > 0 or not row['replacements']), 'replacement clock/onset differs')
            yield row
        require(json.loads(next(stream)) == dict(complete=True, tick=STOP) and not stream.read(),
                'incomplete replacement trace')


def survival(life, days):
    due = life['birth_tick'] + days * DAY
    if life['death_tick'] is not None and life['death_tick'] <= min(due, STOP):
        return 'failed'
    return 'confirmed' if due <= STOP else 'censored'


def summary(result, world):
    lives, seeds = index_result(result)
    members = {}
    groups = dict(focal=world['focal'], first_recruit=world['first_recruits'],
                  later=[i for i, p in lives.items() if p['birth_tick'] > BASE])
    for cohort, ids in groups.items():
        members[cohort] = {}
        for identity in ids:
            children = [p for p in lives.values() if p['parent'] == identity and p['birth_tick'] > BASE]
            members[cohort][str(identity)] = dict(
                life=lives[identity], purchases=sum(s['parent'] == identity and s['birth_tick'] > BASE for s in seeds.values()),
                replacements=sum(s['parent'] == identity and s['outcome'] == 'replaced' for s in seeds.values()),
                children=[dict(life=p, survival={str(d): survival(p, d) for d in (1, 16, 32)}) for p in children],
                living_descendants=[i for i, p in lives.items() if p['death_tick'] is None and is_descendant(i, identity, lives)])
    born = [p for p in lives.values() if p['birth_tick'] > BASE]
    return dict(cohorts=members, births=born,
                established={str(d): sum(survival(p, d) == 'confirmed' for p in born) for d in (1, 16, 32)},
                natural_deaths=[p for p in lives.values() if p['death_tick'] is not None and p['death_tick'] > BASE
                                and not p['environmental_death']],
                seed_fates=dict(Counter(s['outcome'] for s in seeds.values() if s['birth_tick'] > BASE)),
                final={k: result[k] for k in ('living', 'plant_slots', 'nodes', 'seed_bank', 'species_lifetimes')})


def is_descendant(identity, ancestor, lives):
    parent = lives[identity]['parent']
    while parent:
        if parent == ancestor:
            return True
        parent = lives[parent]['parent']
    return False


def analyze_paths(paths, result, key, phase):
    """Reconcile every post-onset check, purchase, replacement and plant budget."""
    lives, seeds = index_result(result)
    world = inputs()['panel'][key]
    trace = {kind: followup.trace_rows(paths[kind], kind, STEP if kind == 'reach' else FIRST, STOP, result)
             for kind in ('stand', 'adult', 'reach')}
    streams = [(r for r, raw in source if r['tick'] >= BASE) for source in trace.values()]
    replacements = {r['tick']: r['replacements'] for r in replacement_rows(paths['replacement'],
                                                                         0 if phase == 'control' else BASE)
                    if r['replacements']}
    by_end = {}
    for s in seeds.values():
        if s['outcome'] == 'replaced':
            by_end.setdefault(s['end_tick'], []).append(s)
    require(set(by_end) == set(replacements), 'missing replacement ticks')
    previous_stores, resource_totals, events = {}, {}, []
    active = {k for k, s in seeds.items() if s['birth_tick'] <= BASE < (s['end_tick'] or STOP + STEP)}
    require(len(active) == 8, 'wrong initial bank')
    for stand, adult, reach in zip(*streams, strict=True):
        tick = stand['tick']
        require(tick == adult['tick'] == reach['tick'], 'mismatched trace clocks')
        slots, visits = stand['plant_order'], stand['reproduction']
        window.previous.visit_order(tick, slots, [[v['id']] for v in visits], result)
        if tick == BASE:
            previous_stores = {p['id']: p['stages'][-1] for p in adult['plants'] if p['id'] != world['target']}
            continue  # This observation precedes the second imposed death.
        climate, sun_phase, sun = window.previous.sun_at(int(result['seed'], 16), tick)
        require(stand['climate'] == climate and adult['sun'] == [sun_phase, sun] and adult['cold'] == climate['cold'],
                'climate changed')
        born = {i for i, p in lives.items() if p['birth_tick'] == tick}
        check_slots = [i for i in slots if i not in born]
        checked = set()
        for raw, observed in zip(adult['seeds'], reach['checks'], strict=True):
            seed_key = raw[0], tick - raw[1] * STEP
            require(seed_key in active and seed_key not in checked and observed[:4] == raw[:4] and
                    observed[4:6] == raw[8:10], 'missing/duplicate/mismatched seed check')
            checked.add(seed_key)
            s = seeds[seed_key]
            # A replacement still WAITs during seed admission, before its later
            # production-phase exit. Present that check with its current pending fate.
            gate_seed = dict(s, outcome='pending', end_tick=None) if s['outcome'] == 'replaced' else s
            window.previous.seed_check(raw, observed[6], tick, gate_seed, check_slots, lives, climate['cold'])
            if raw[8] == 2:
                check_slots.append(raw[9])
            if raw[8] != 0:
                active.remove(seed_key)
        expected_checks = {k for k, s in seeds.items() if s['birth_tick'] < tick <= (s['end_tick'] or STOP)}
        require(checked == expected_checks and check_slots == slots, 'incomplete seed admission')
        arrivals = {s['parent']: s for s in seeds.values() if s['birth_tick'] == tick}
        purchases = {p['parent']: p for p in reach['purchases']}
        require(set(arrivals) == set(purchases) and len(purchases) == len(reach['purchases']), 'purchase coverage differs')
        replace = {r['parent']: r for r in replacements.get(tick, [])}
        require(len(replace) == len(replacements.get(tick, [])) and set(replace) <= set(arrivals), 'unpaid replacement')
        resources = {p['id']: p for p in adult['plants']}
        living = {i for i, p in lives.items() if p['birth_tick'] <= tick and
                  (p['death_tick'] is None or p['death_tick'] > tick)}
        dying = {i for i, p in lives.items() if p['death_tick'] == tick}
        require(set(resources) == living | dying and {v['id'] for v in visits} == set(slots), 'plant coverage differs')
        for v in visits:
            identity = v['id']
            mask = sum((1 << j) for j, blocked in enumerate((v['cooldown'] != 0, tick % 60 != 0, len(active) == 8,
                        identity not in living, v['stress'] != 0, sun <= 24, lives[identity]['generation'] == 65535,
                        v['energy'] < v['energy_required'], v['water'] < v['water_required'], v['flower'] == 65535)) if blocked)
            require(v['blockers'] == mask and v['bank'] == len(active) and v['sun'] == sun and
                    v['produced'] == (identity in arrivals), 'production mask/inventory differs')
            if identity in arrivals:
                p, s = purchases[identity], arrivals[identity]
                late.purchase_check(p, slots, lives, s, True)
                require(not (mask & ~bank.BANK), 'non-bank production gate bypassed')
                if identity in replace:
                    r = replace[identity]
                    old_key = identity, tick - r['age'] * STEP
                    require(set(r) == {'parent', 'age', 'column', 'generation', 'species', 'new_column'} and
                            old_key in active and len(active) == 8 and len(slots) < 8 and
                            not (late.sites_decode(p['sites'])[p['column']] & (8 | 16 | 32)),
                            'replacement ownership/capacity differs')
                    old = seeds[old_key]
                    require(old['outcome'] == 'replaced' and old['end_tick'] == tick and
                            all(old[k] == r[k] for k in ('parent', 'column', 'generation', 'species')) and
                            r['new_column'] == p['column'] and
                            any(abs(lives[i]['column'] - old['column']) < 3 for i in slots) and
                            all(abs(lives[i]['column'] - p['column']) >= 3 for i in slots), 'replacement landing/fate differs')
                    candidates = [seeds[k] for k in active if k[0] == identity and
                                  any(abs(lives[i]['column'] - seeds[k]['column']) < 3 for i in slots)]
                    require(old['birth_tick'] == min(s['birth_tick'] for s in candidates), 'replacement is not oldest owned blocked seed')
                    events.append(dict(tick=tick, old=old, purchase=p, visit=v, slots=slots))
                    active.remove(old_key)
                else:
                    require(mask == 0 and len(active) < 8, 'unreceipted full-bank purchase')
                active.add((identity, tick))
        require(len(active) == adult['bank'] <= 8 and active == {k for k, s in seeds.items()
                if s['birth_tick'] <= tick < (s['end_tick'] or STOP + STEP)}, 'post-production bank does not balance')
        for identity, row in resources.items():
            p = lives[identity]
            require(row['birth'] == p['birth_tick'] and (identity in previous_stores or identity in born),
                    'missing resource predecessor')
            transfers = window.adults.transfers(dict(row, tick=tick), p, previous_stores.get(identity))
            total = resource_totals.setdefault(str(identity), dict(samples=0, maintenance=0, shortfalls=0,
                                                                  energy=window.adults.budget()['energy'],
                                                                  water=window.adults.budget()['water']))
            for name, cost in (('energy', 48), ('water', 24)):
                require(transfers[name]['reproduction'] == cost * (identity in arrivals), 'wrong fresh seed debit')
            if identity in living:
                v = next(v for v in visits if v['id'] == identity)
                require(row['stages'][3][:3] == [v['energy'], v['water'], v['stress']], 'pre-purchase resources differ')
            window.adults.accumulate({k: total[k] for k in ('energy', 'water')}, transfers, total['samples'] == 0)
            total['samples'] += 1
            if tick % 60 == 0 and identity not in born:
                total['maintenance'] += 1
                total['shortfalls'] += bool(row['stages'][1][3] & 6)
            previous_stores[identity] = row['stages'][-1]
    require(len(events) == sum(s['outcome'] == 'replaced' for s in seeds.values()), 'replacement count differs')
    return dict(summary=summary(result, world), replacements=events, resources=resource_totals)


def compare(control, treatment, key):
    world = inputs()['panel'][key]
    old = inputs()['runs']['treatment'][key]['result']
    residents = [p['id'] for p in old['lineages'] if p['birth_tick'] <= BASE and
                 (p['death_tick'] is None or p['death_tick'] > BASE)]
    matched = {str(i): {phase: a['resources'][str(i)] for phase, a in (('control', control), ('treatment', treatment))}
               for i in residents}
    old_seeds = {(s['parent'], s['birth_tick']): s for s in old['seeds']}
    displaced = [dict(old=e['old'], control=old_seeds.get((e['old']['parent'], e['old']['birth_tick']))
                      if e['old']['birth_tick'] <= BASE else None,
                      matched_prefix_seed=e['old']['birth_tick'] <= BASE)
                 for e in treatment['replacements']]
    first_gains = [i for i in world['first_recruits'] if
                   sum(c['survival']['16'] == 'confirmed' for c in treatment['summary']['cohorts']['first_recruit'][str(i)]['children']) >
                   sum(c['survival']['16'] == 'confirmed' for c in control['summary']['cohorts']['first_recruit'][str(i)]['children'])]
    established = {phase: Counter(p['parent'] for p in a['summary']['births'] if survival(p, 16) == 'confirmed')
                   for phase, a in (('control', control), ('treatment', treatment))}
    deaths = {phase: {p['id']: p['death_tick'] for p in a['summary']['natural_deaths']}
              for phase, a in (('control', control), ('treatment', treatment))}
    return dict(matched=matched, displaced=displaced, first_recruit_gains=first_gains,
                extra_matched_shortfalls=[i for i, pair in matched.items()
                                          if pair['treatment']['shortfalls'] > pair['control']['shortfalls']],
                extra_matched_natural_deaths=[i for i in residents if i in deaths['treatment'] and
                                               deaths['treatment'][i] < deaths['control'].get(i, STOP + STEP)],
                established_parent_losses=[dict(parent=p['id'], control=established['control'][p['id']],
                                                 treatment=established['treatment'][p['id']])
                                            for p in old['lineages'] if p['birth_tick'] <= BASE and
                                            established['treatment'][p['id']] < established['control'][p['id']]],
                established_16_delta=treatment['summary']['established']['16'] - control['summary']['established']['16'])


def first_effects(root, control, treatment):
    """Compare data rows, excluding deliberately different run-identity footers."""
    effects = {}
    for kind in capture.KINDS:
        sources = [followup.trace_rows(root / r['traces'][kind]['path'], kind,
                                      STEP if kind == 'reach' else FIRST, STOP, r['result'])
                   for r in (control, treatment)]
        prefix, first = hashlib.sha256(), None
        try:
            for a, b in zip(*sources, strict=True):
                require(a[0]['tick'] == b[0]['tick'], 'paired trace clocks differ')
                if first is None:
                    if a[1] == b[1]:
                        prefix.update(a[1])
                    else:
                        first = a[0]['tick']
        finally:
            for source in sources:
                source.close()
        effects[kind] = dict(first_tick=first, common_prefix_sha256=prefix.hexdigest())
    actual = [e['first_tick'] for e in effects.values() if e['first_tick'] is not None]
    swaps = treatment['analysis']['replacements']
    require((min(actual) if actual else None) == (swaps[0]['tick'] if swaps else None),
            'first observed effect is not the first paid replacement')
    return effects


def verdict(comparisons):
    return dict(first_recruit_gain=any(c['first_recruit_gains'] for c in comparisons.values()),
                no_extra_matched_shortfall=not any(c['extra_matched_shortfalls'] for c in comparisons.values()),
                no_extra_matched_natural_death=not any(c['extra_matched_natural_deaths'] for c in comparisons.values()),
                no_establishment_loss_elsewhere=not any(c['established_parent_losses'] or c['established_16_delta'] < 0
                                                        for c in comparisons.values()))


def verify_capture(value):
    saved = inputs()
    require(value['rule'] == RULE and value['protocol_sha256'] == PROTOCOL_SHA and
            value['input_sha256'] == INPUT_SHA and value['native_runs'] == 20 and value['training_runs'] == 0 and
            value['panel'] == saved['panel'] and value['model_sha256'] == saved['model_sha256'] and
            value['analysis_sources'] == {p: digest(ROOT / p) for p in SOURCES} and
            set(value['runs']) == set(PHASES), 'capture provenance differs')
    require(set(value['builds']) == set(capture.BUILDS), 'wrong research builds')
    for arm, build in value['builds'].items():
        require(build['settings'] == saved['builds'][arm]['settings'], 'build settings changed')
    for phase in PHASES:
        require(set(value['runs'][phase]) == set(saved['panel']), 'missing world')
        for key, run in value['runs'][phase].items():
            check_result(run['result'], key, phase)
            require(run['args'] == arguments(key, phase) and
                    set(run['traces']) == (set() if phase == 'plain' else set(KINDS)), 'wrong call/trace identity')
            if phase == 'control':
                late.same_run(run, saved['runs']['treatment'][key], capture.KINDS)
            if phase in ('repeat', 'plain'):
                late.same_run(run, value['runs']['treatment'][key], () if phase == 'plain' else KINDS)
                require(phase == 'plain' or run['analysis'] == value['runs']['treatment'][key]['analysis'],
                        'repeat accounting changed')
            if phase != 'plain':
                require(run['analysis']['summary'] == summary(run['result'], saved['panel'][key]), 'summary changed')
                for kind in capture.KINDS:
                    require(all(run['receipts'][kind][k] == saved['runs']['treatment'][key]['receipts'][kind][k]
                                for k in ('prefix_sha256', 'boundary_sha256')), 'pre-onset observations changed')
    require(value['comparisons'] == {key: compare(value['runs']['control'][key]['analysis'],
                                                  value['runs']['treatment'][key]['analysis'], key) for key in saved['panel']},
            'paired summary differs')
    require(value['verdict'] == verdict(value['comparisons']) and set(value['first_effects']) == set(saved['panel']),
            'verdict/effect panel differs')
    for key, effects in value['first_effects'].items():
        require(set(effects) == set(capture.KINDS), 'incomplete first-effect receipt')
        ticks = [e['first_tick'] for e in effects.values() if e['first_tick'] is not None]
        swaps = value['runs']['treatment'][key]['analysis']['replacements']
        require((min(ticks) if ticks else None) == (swaps[0]['tick'] if swaps else None), 'first-effect receipt differs')
    require(value['receipt_sha256'] == fingerprint({k: v for k, v in value.items() if k != 'receipt_sha256'}),
            'capture receipt differs')


def collect(out, original, jobs):
    require(not out.exists() and not out.is_symlink() and 1 <= jobs <= 4 and
            shutil.disk_usage(out.parent).free >= 10 * 1024 ** 3, 'fresh output, 10 GiB free and 1..4 jobs required')
    saved = inputs()
    require(digest(original / 'manifest.json') == previous.MANIFEST_SHA and
            digest(original / 'model.tgl') == saved['model_sha256'], 'wrong archived raw bundle')
    sources = source_files()
    runtime = {p: h for p, h in sources.items() if p.startswith(('src/', 'sim/')) and p.endswith(('.c', '.h'))}
    old_runtime = {p: h for p, h in saved['source_sha256'].items()
                   if p.startswith(('src/', 'sim/')) and p.endswith(('.c', '.h'))}
    require({p for p in runtime.keys() | old_runtime.keys() if runtime.get(p) != old_runtime.get(p)} <= CHANGED_RUNTIME,
            'unrelated runtime changed')
    out.mkdir(parents=True)
    (out / 'bin').mkdir()
    snapshot_sources(out, sources)
    shutil.copy2(ROOT / PROTOCOL, out / 'protocol.md')
    shutil.copy2(original / 'model.tgl', out / 'model.tgl')
    value = dict(rule=RULE, protocol_sha256=PROTOCOL_SHA, input_sha256=INPUT_SHA, native_runs=20, training_runs=0,
                 panel=saved['panel'], model_sha256=saved['model_sha256'], source_sha256=sources,
                 analysis_sources={p: sources[p] for p in SOURCES}, builds={}, runs={})
    for arm, build in capture.BUILDS.items():
        binary, settings = ROOT / build / 'toy-factory-garden-landing', ROOT / build / 'CMakeCache.txt'
        options = late.settings_at(settings, arm)
        require(options == saved['builds'][arm]['settings'], 'build options changed')
        value['builds'][arm] = dict(binary=digest(binary), settings=options, cache=digest(settings))
        shutil.copy2(binary, out / ('bin/' + arm))
        shutil.copy2(settings, out / (arm + '-CMakeCache.txt'))
    write_json(out / 'started.json', value)

    def trial(key, phase):
        args, directory = arguments(key, phase), out / phase / key
        directory.mkdir(parents=True)
        (directory / 'frames').mkdir()
        shutil.copy2(out / 'model.tgl', directory / 'model.tgl')
        result = native(out / ('bin/' + saved['panel'][key]['arm']), directory, *args)
        write_json(directory / 'result.json', result)
        check_result(result, key, phase)
        run = dict(directory=str(directory.relative_to(out)), args=args, result=result, traces={}, receipts={})
        paths = {}
        for kind in (() if phase == 'plain' else KINDS):
            name = args[args.index('--' + kind + '-trace') + 1]
            path = directory / (name + '.gz')
            compress(directory / name, path)
            paths[kind] = path
            run['traces'][kind] = dict(path=str(path.relative_to(out)), sha256=digest(path))
            if kind != 'replacement':
                run['receipts'][kind] = capture.receipt(path, kind, result)
        frame = directory / args[args.index('--framebuffer') + 1]
        require(len(frame.read_bytes()) == 115200 and f'{zlib.crc32(frame.read_bytes()):08x}' == result['framebuffer_crc32'],
                'frame identity differs')
        run['frame'] = dict(path=str(frame.relative_to(out)), sha256=digest(frame))
        if phase != 'plain':
            run['analysis'] = analyze_paths(paths, result, key, phase)
        if phase == 'control':
            late.same_run(run, saved['runs']['treatment'][key], capture.KINDS)
        elif phase in ('repeat', 'plain'):
            late.same_run(run, value['runs']['treatment'][key], () if phase == 'plain' else KINDS)
        write_json(directory / 'run.json', run)
        print(phase + '/' + key + ': verified', flush=True)
        return key, run

    try:
        for phase in PHASES:
            with ThreadPoolExecutor(max_workers=jobs) as pool:
                value['runs'][phase] = dict(pool.map(lambda key: trial(key, phase), sorted(saved['panel'])))
            write_json(out / (phase + '.json'), value['runs'][phase])
            print(phase + ': complete', flush=True)
        value['comparisons'] = {k: compare(value['runs']['control'][k]['analysis'],
                                            value['runs']['treatment'][k]['analysis'], k) for k in saved['panel']}
        value['first_effects'] = {k: first_effects(out, value['runs']['control'][k], value['runs']['treatment'][k])
                                  for k in saved['panel']}
        value['verdict'] = verdict(value['comparisons'])
        groups = [[dict(id=phase + '/' + key, framebuffer=value['runs'][phase][key]['frame']['path'])
                   for phase in ('control', 'treatment')] for key in sorted(saved['panel'])]
        value['gallery'] = contact_sheet(out, groups)
        value['gallery']['sha256'] = digest(out / 'contact-sheet.png')
        require(all(digest(ROOT / p) == h for p, h in runtime.items()) and
                all(digest(ROOT / p) == sources[p] for p in (*SOURCES, PROTOCOL)), 'capture sources changed')
        value['receipt_sha256'] = fingerprint(value)
        verify_capture(value)
        write_json(out / 'capture.json', value)
        write_json(out / 'manifest.json', dict(rule=RULE, artifacts={str(p.relative_to(out)): digest(p)
                                              for p in sorted(out.rglob('*')) if p.is_file()}))
    except Exception as error:
        write_json(out / 'FAILED.json', dict(error=str(error)))
        raise
    return value


def verify_bundle(root, value):
    verify_capture(value)
    manifest = json.loads((root / 'manifest.json').read_text())
    require(manifest['rule'] == RULE and not (root / 'FAILED.json').exists() and
            archived_sources(root / 'source.tar.gz') == value['source_sha256'] and
            json.loads((root / 'capture.json').read_text()) == value and
            digest(root / 'protocol.md') == PROTOCOL_SHA and digest(root / 'model.tgl') == value['model_sha256'],
            'raw provenance differs')
    for path, sha in manifest['artifacts'].items():
        followup.artifact(root, dict(path=path, sha256=sha))
    for phase, calls in value['runs'].items():
        if phase == 'plain':
            continue
        for key, run in calls.items():
            paths = {k: followup.artifact(root, p) for k, p in run['traces'].items()}
            require(analyze_paths(paths, run['result'], key, phase) == run['analysis'], 'raw accounting differs')
            require({k: capture.receipt(paths[k], k, run['result']) for k in capture.KINDS} == run['receipts'],
                    'raw prefix receipt differs')
    require({k: first_effects(root, value['runs']['control'][k], value['runs']['treatment'][k])
             for k in value['panel']} == value['first_effects'], 'raw first-effect receipt differs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--collect', type=Path)
    mode.add_argument('--verify', type=Path)
    parser.add_argument('--original', type=Path, default=ROOT / 'artifacts/garden-landing-second-opening-v1')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    require(bool(args.out) == bool(args.collect) and not (args.collect and args.bundle), 'invalid output mode')
    if args.collect:
        require(not args.out.exists() and not args.out.is_symlink() and
                not args.collect.exists() and not args.collect.is_symlink(), 'fresh outputs required')
        write_gzip(args.out, collect(args.collect.resolve(), args.original.resolve(), args.jobs))
    else:
        with gzip.open(args.verify, 'rt') as stream:
            value = json.load(stream)
        verify_capture(value)
        if args.bundle:
            verify_bundle(args.bundle.resolve(), value)
    print('verified ' + RULE)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, TypeError, IndexError, OSError) as error:
        print('error: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
