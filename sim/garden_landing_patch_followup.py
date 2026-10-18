#!/usr/bin/env python3
"""Observation-only day-352 follow-up, gated by all twelve day-320 histories."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from functools import cache
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import zlib

import garden_landing_patch_confirmation as confirm
from garden_resources import require

sweep = confirm.sweep
ROOT, DAY, STEP = confirm.ROOT, confirm.DAY, sweep.STEP
BASE, STOP = confirm.STOP, 352 * DAY
RULE = 'garden-landing-patch-followup-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-patch-followup-protocol.md'
PROTOCOL_SHA = 'b8ef868bfe0c7f6a6ef53405f24d0dd174afca1815f03c17a577ed2a33ffac59'
INPUT = 'benchmarks/garden-seasons/landing-patch-confirmation-results.json.gz'
INPUT_SHA = '13a46abbfe805bb58c5895b9417c622c05067d6f9c18c31cb7447da7c4657656'
ORIGIN_MANIFEST = '7e0e1babb1ead8ebcbbb17256cf7673fe18a968a87cc4fb849244957c1f72b6c'
PHASES = ('anchor-control', 'anchor-treatment', 'control', 'treatment', 'repeat', 'plain')
CLI = 'sim/garden_landing_cli.c'
CLI_SHA = 'fb18d45c7226788144e66b0d6d50fec53b62864089e08e9653da15e46fcc97db'
SOURCES = tuple(sorted({*confirm.SOURCES, 'sim/garden_landing_patch_followup.py',
                        'sim/test_garden_landing_patch_followup.py'}))


@cache
def prior():
    require(sweep.digest(ROOT / INPUT) == INPUT_SHA and sweep.digest(ROOT / PROTOCOL) == PROTOCOL_SHA,
            'follow-up input/protocol changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream:
        value = json.load(stream)
    confirm.check_capture(value)
    return value


def arm(phase):
    return 'control' if phase in ('anchor-control', 'control') else 'treatment'


def horizon(phase):
    return BASE if phase.startswith('anchor-') else STOP


def arguments(key, phase):
    require(phase in PHASES and key in confirm.panel(), 'unknown follow-up call')
    args = confirm.arguments(key, 'plain' if phase == 'plain' else arm(phase))
    for flag in ('--ticks', '--stand-stop', '--adult-stop'):
        if flag in args:
            args[args.index(flag) + 1] = str(horizon(phase))
    return args


def check_result(result, key, phase):
    old = prior()['runs'][arm(phase)][key]['result']
    stop = horizon(phase)
    if stop == BASE:
        require(result == old, 'day-320 result changed')
        return
    require(set(result) == set(old) and result['tick'] == stop, 'wrong result schema/horizon')
    for k in ('schema_version', 'kind', 'run_version', 'rules', 'scenario', 'seed', 'model',
              'gardener', 'irrigation', 'seed_lifetime_ecology_ticks', 'ledger_start_tick',
              'warmup_samples', *(k for k in old if k.endswith('_probe'))):
        require(result[k] == old[k], 'changed setting/event history: ' + k)
    require(result['climate'] == sweep.followup.previous.climate(int(result['seed'], 16), stop), 'wrong climate')
    lives, seeds = sweep.index_records(result['lineages'], result['seeds'], 0, stop)
    require(sweep.prefix(result, BASE) == (old['lineages'], old['seeds']), 'day-320 ledger prefix changed')
    require(len(lives) <= 4096 and len(seeds) <= 65536 and
            result['births'] == sum(p['parent'] != 0 for p in lives.values()) and
            result['deaths'] == sum(p['death_tick'] is not None for p in lives.values()) and
            result['living'] == len(lives) - result['deaths'] and
            result['seed_bank'] == sum(s['outcome'] == 'pending' for s in seeds.values()) and
            0 <= result['living'] <= result['plant_slots'] <= 8 and 0 <= result['nodes'] <= 256 and
            result['seed_bank'] <= 8, 'ledger/capacity differs')
    if arm(phase) == 'treatment':
        sweep.events(result)
        require(result['run_hash'] == sweep.tagged(result['placement_run_hash']), 'wrong tagged hash')
    else:
        require(not any(p['environmental_death'] for p in lives.values()), 'imposed death in control')


def cohort(result, birth_stop):
    stop = result['tick']
    plants = sorted((p for p in result['lineages'] if sweep.BASE < p['birth_tick'] <= birth_stop),
                    key=lambda p: (p['birth_tick'], p['id']))
    depths, established, pairs = {}, {}, []
    rows = []
    for p in plants:
        status = {str(d): sweep.survival(p, d, stop) for d in (1, 16, 32)}
        rows.append(dict(life=p, survival=status))
        depths[p['id']] = 1 + depths.get(p['parent'], 0)
        if status['16'] == 'confirmed':
            established[p['id']] = 1 + established.get(p['parent'], 0)
            if p['parent'] in established:
                pairs.append([p['parent'], p['id']])
    return dict(cohort=rows, qualifying_pairs=pairs,
                deepest_born_chain=max(depths.values(), default=0),
                deepest_16_day_chain=max(established.values(), default=0),
                survival={str(d): dict(Counter(r['survival'][str(d)] for r in rows)) for d in (1, 16, 32)})


def analyze(result, old):
    lives = {p['id']: p for p in result['lineages']}
    fixed = cohort(result, BASE)
    require(all('censored' not in counts for counts in fixed['survival'].values()), 'fixed cohort still censored')
    resolved = {str(d): [dict(id=p['id'], outcome=sweep.survival(lives[p['id']], d, STOP))
                         for p in old['lineages'] if p['birth_tick'] > sweep.BASE and
                         sweep.survival(p, d, BASE) == 'censored'] for d in (1, 16, 32)}
    seeds = [s for s in result['seeds'] if s['birth_tick'] > BASE]
    return dict(fixed_cohort=fixed, expanded_cohort=cohort(result, STOP), resolved=resolved,
                new_births=[p for p in lives.values() if p['birth_tick'] > BASE],
                new_deaths=[p for p in lives.values() if p['death_tick'] is not None and p['death_tick'] > BASE],
                purchases=len(seeds), seed_fates=dict(Counter(s['outcome'] for s in seeds)),
                old_pending=[s for s in result['seeds'] if s['birth_tick'] <= BASE and
                             (s['end_tick'] is None or s['end_tick'] > BASE)],
                birth_windows=[dict(start=(d - 8) * DAY, stop=d * DAY,
                                    count=sum((d - 8) * DAY < p['birth_tick'] <= d * DAY for p in lives.values()))
                               for d in range(312, 353, 8)],
                species=dict(Counter(str(p['species']) for p in lives.values() if p['death_tick'] is None)),
                final={k: result[k] for k in ('living', 'plant_slots', 'nodes', 'seed_bank')})


def trace_receipt(path, kind, result):
    """Hash the authenticated old prefix, then validate tail clocks and population census."""
    stop, start = result['tick'], STEP if kind == 'reach' else sweep.BASE
    schemas = dict(stand='landing-dawn-stand-trace-v1', adult='landing-adult-resources-v1',
                   reach='landing-reach-trace-v1')
    header = dict(schema=schemas[kind])
    if kind != 'reach':
        header.update(start=start, stop=stop)
    if kind == 'stand':
        header.update(node_limit=32, budget_mode=2)
    footer = dict(complete=True, tick=stop)
    if kind == 'stand':
        footer['run_hash'] = result['run_hash']
    prefix, boundary, daily, occupancy, purchases = hashlib.sha256(), None, [], Counter(), []
    lives = {p['id']: p for p in result['lineages']}
    last = None
    with gzip.open(path, 'rb') as stream:
        require(json.loads(stream.readline()) == header, 'wrong trace header')
        for tick in range(start, stop + STEP, STEP):
            raw = stream.readline()
            require(raw.endswith(b'\n'), 'truncated trace row')
            if tick <= BASE:
                prefix.update(raw)
            if tick < BASE:
                continue  # Full prefix hash is checked against the byte-identical day-320 anchor.
            row = json.loads(raw)
            require(type(row.get('tick')) is int and row['tick'] == tick, 'trace gap/order differs')
            if tick == BASE:
                boundary = sweep.fingerprint(row)
            if kind == 'stand':
                live = {i for i, p in lives.items() if p['birth_tick'] <= tick and
                        (p['death_tick'] is None or p['death_tick'] > tick)}
                slots = row['plant_order']
                require(len(slots) == len(set(slots)) <= 8 and live <= set(slots) <= set(lives) and
                        len(row['bodies']) == len(live) and {b['id'] for b in row['bodies']} == live and
                        all(b['species'] == lives[b['id']]['species'] for b in row['bodies']) and
                        row['climate'] == sweep.followup.previous.climate(int(result['seed'], 16), tick) and
                        row['seed_lifetime_ecology_ticks'] == 8192, 'tail stand census differs')
                if last is not None:
                    sweep.window.prior.slot_change(last, slots, tick, lives)
                last = slots
                if tick > BASE:
                    occupancy[str(len(live)) + '/' + str(len(slots))] += 1
                if tick % DAY == 0:
                    daily.append(dict(tick=tick, living=sorted(live), stored=slots))
            elif kind == 'adult':
                bank = sum(s['birth_tick'] <= tick < (s['end_tick'] or stop + STEP) for s in result['seeds'])
                require(row['bank'] == bank <= 8, 'tail seed census differs')
                if tick % DAY == 0:
                    daily.append(dict(tick=tick, bank=bank))
            elif tick > BASE:
                purchases.extend([p['parent'], tick] for p in row['purchases'])
        require(json.loads(stream.readline()) == footer and not stream.read(), 'wrong trace footer/trailing bytes')
    if kind == 'stand':
        require(len(last) == result['plant_slots'] and len(daily[-1]['living']) == result['living'], 'endpoint census differs')
    if kind == 'reach':
        require(sorted(purchases) == sorted([s['parent'], s['birth_tick']] for s in result['seeds']
                                            if s['birth_tick'] > BASE), 'tail purchase census differs')
    return dict(prefix_sha256=prefix.hexdigest(), boundary_sha256=boundary, daily=daily,
                occupancy=dict(occupancy), purchases=purchases)


def compressed_trace(raw, packed):
    def identity():
        info = raw.stat()
        return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns
    before = identity()
    raw_sha = sweep.digest(raw)
    sweep.compress(raw, packed)
    digest, size = hashlib.sha256(), 0
    with gzip.open(packed, 'rb') as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
            size += len(block)
    require((digest.hexdigest(), size) == (raw_sha, before[2]) and identity() == before,
            'compression did not preserve trace bytes')
    return dict(raw_sha256=raw_sha, raw_bytes=size)


def write_receipt(path, value):
    sweep.write_json(path, value)
    with path.open('rb') as stream:
        os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def call(out, value, key, phase):
    args, name = arguments(key, phase), phase + '/' + key
    directory = out / name
    (directory / 'frames').mkdir(parents=True)
    shutil.copy2(out / 'model.tgl', directory / 'model.tgl')
    result = sweep.native(out / 'bin/garden-landing', directory, *args)
    write_receipt(directory / 'result.json', result)
    check_result(result, key, phase)
    run = dict(args=args, directory=name, result=result, traces={}, receipts={})
    raw_paths = []
    for kind in (() if phase == 'plain' else sweep.KINDS):
        raw = directory / (kind + '.jsonl')
        packed = raw.with_suffix('.jsonl.gz')
        metadata = compressed_trace(raw, packed)
        run['traces'][kind] = dict(path=str(packed.relative_to(out)), sha256=sweep.digest(packed), **metadata)
        run['receipts'][kind] = trace_receipt(packed, kind, result)
        raw_paths.append(raw)
    frame = directory / 'frames/end.raw'
    data = frame.read_bytes()
    require(len(data) == 115200 and f'{zlib.crc32(data):08x}' == result['framebuffer_crc32'], 'frame CRC differs')
    run['frame'] = dict(path=str(frame.relative_to(out)), sha256=sweep.digest(frame))
    if horizon(phase) != BASE:
        run['analysis'] = analyze(result, prior()['runs'][arm(phase)][key]['result'])
    check_run(run, key, phase, value['runs'])
    write_receipt(directory / 'run.json', run)
    # Only freshly generated, already audited traces are removed; their gzip copies,
    # raw hashes and lengths have been persisted. Historical collectors stay frozen.
    for raw in raw_paths:
        require(not raw.is_symlink() and sweep.digest(raw) == run['traces'][raw.stem]['raw_sha256'],
                'raw trace changed before compaction')
        with raw.with_suffix('.jsonl.gz').open('rb') as stream:
            os.fsync(stream.fileno())
        raw.unlink()
    print('verified: ' + name, flush=True)
    return key, run


def check_run(run, key, phase, runs):
    kinds = () if phase == 'plain' else sweep.KINDS
    require(set(run) == {'args', 'directory', 'result', 'traces', 'receipts', 'frame'} |
            ({'analysis'} if horizon(phase) != BASE else set()) and run['args'] == arguments(key, phase) and
            run['directory'] == phase + '/' + key and set(run['traces']) == set(run['receipts']) == set(kinds),
            'wrong follow-up call/fields')
    check_result(run['result'], key, phase)
    require(run['frame']['path'] == run['directory'] + '/frames/end.raw' and all(
        v['path'] == run['directory'] + '/' + k + '.jsonl.gz' and set(v) == {'path', 'sha256', 'raw_sha256', 'raw_bytes'}
        for k, v in run['traces'].items()), 'wrong artifact paths/fields')
    for kind, receipt in run['receipts'].items():
        check_receipt(receipt, kind, run['result'])
    if horizon(phase) == BASE:
        sweep.late.same_run(run, prior()['runs'][arm(phase)][key], kinds)
    else:
        require(run['analysis'] == analyze(run['result'], prior()['runs'][arm(phase)][key]['result']), 'wrong analysis')
        for k, receipt in run['receipts'].items():
            original = runs['anchor-' + arm(phase)][key]['receipts'][k]
            require(all(receipt[f] == original[f] for f in ('prefix_sha256', 'boundary_sha256')), 'old trace prefix differs')
    if phase in ('repeat', 'plain'):
        other = runs['treatment'][key]
        sweep.late.same_run(run, other, kinds)
        require(run['analysis'] == other['analysis'] and (phase == 'plain' or run['receipts'] == other['receipts']),
                'repeat analysis/observations differ')


def check_receipt(receipt, kind, result):
    stop = result['tick']
    require(set(receipt) == {'prefix_sha256', 'boundary_sha256', 'daily', 'occupancy', 'purchases'} and
            all(isinstance(receipt[k], str) and len(receipt[k]) == 64 and len(bytes.fromhex(receipt[k])) == 32
                for k in ('prefix_sha256', 'boundary_sha256')), 'wrong trace receipt')
    lives = result['lineages']
    days = list(range(BASE, stop + DAY, DAY)) if kind != 'reach' else []
    require([d['tick'] for d in receipt['daily']] == days, 'daily census gaps')
    for row in receipt['daily']:
        tick = row['tick']
        if kind == 'stand':
            live = sorted(p['id'] for p in lives if p['birth_tick'] <= tick and
                          (p['death_tick'] is None or p['death_tick'] > tick))
            require(set(row) == {'tick', 'living', 'stored'} and row['living'] == live and
                    len(row['stored']) == len(set(row['stored'])) <= 8 and set(live) <= set(row['stored']) and
                    set(row['stored']) <= {p['id'] for p in lives if p['birth_tick'] <= tick}, 'daily stand census differs')
        else:
            require(set(row) == {'tick', 'bank'} and row['bank'] == sum(
                s['birth_tick'] <= tick < (s['end_tick'] or stop + STEP) for s in result['seeds']), 'daily bank differs')
    if kind == 'stand':
        observed = Counter()
        for name, count in receipt['occupancy'].items():
            living, stored = map(int, name.split('/'))
            require(0 <= living <= stored <= 8 and type(count) is int and count > 0, 'invalid occupancy bucket')
            observed[living] += count
        changes = Counter()
        live = result['living']
        for p in lives:
            if p['birth_tick'] > BASE:
                changes[p['birth_tick']] += 1
            if p['death_tick'] is not None and p['death_tick'] > BASE:
                changes[p['death_tick']] -= 1
        live -= sum(changes.values())
        expected = Counter()
        for tick in range(BASE + STEP, stop + STEP, STEP):
            live += changes[tick]
            expected[live] += 1
        require(observed == expected and len(receipt['daily'][-1]['stored']) == result['plant_slots'] and
                not receipt['purchases'], 'occupancy exposure differs')
    else:
        require(not receipt['occupancy'], 'occupancy on non-stand trace')
    purchases = sorted([s['parent'], s['birth_tick']] for s in result['seeds'] if s['birth_tick'] > BASE)
    require(sorted(receipt['purchases']) == (purchases if kind == 'reach' else []), 'purchase receipt differs')


def groups(value):
    return [[dict(id=p + '/' + k, framebuffer=value['runs'][p][k]['frame']['path'])
             for p in ('control', 'treatment')] for k in confirm.panel()]


def check_capture(value):
    original = prior()
    require(value['rule'] == RULE and value['protocol_sha256'] == PROTOCOL_SHA and value['input_sha256'] == INPUT_SHA and
            value['origin_manifest_sha256'] == ORIGIN_MANIFEST and value['native_runs'] == 36 and value['training_runs'] == 0 and
            value['panel'] == confirm.panel() and value['model_sha256'] == original['model_sha256'] and
            value['build']['settings'] == original['build']['settings'] and
            value['analysis_sources'] == {p: sweep.digest(ROOT / p) for p in SOURCES}, 'wrong follow-up provenance')
    sources, old = confirm.runtime(value['source_sha256']), confirm.runtime(original['source_sha256'])
    require({p for p in sources.keys() | old.keys() if sources.get(p) != old.get(p)} == {CLI} and
            sources[CLI] == value['cli_sha256'] == CLI_SHA and value['source_sha256'][INPUT] == INPUT_SHA and
            value['source_sha256'][PROTOCOL] == PROTOCOL_SHA and
            all(value['source_sha256'][p] == sha for p, sha in value['analysis_sources'].items()), 'unrelated source change')
    require(set(value['runs']) == set(PHASES), 'missing phase')
    for phase in PHASES:
        require(set(value['runs'][phase]) == set(confirm.panel()), 'missing case')
        for key, run in value['runs'][phase].items():
            check_run(run, key, phase, value['runs'])
    require(value['gallery']['rows'] == [[f['id'] for f in row] for row in groups(value)] and
            (value['gallery']['width'], value['gallery']['height'], value['gallery']['gap']) == (504, 1496, 8) and
            value['receipt_sha256'] == sweep.fingerprint({k: v for k, v in value.items() if k != 'receipt_sha256'}),
            'gallery/receipt differs')


def origin_inputs(origin):
    require(sweep.digest(origin / 'manifest.json') == ORIGIN_MANIFEST, 'origin manifest changed')
    manifest = json.loads((origin / 'manifest.json').read_text())['artifacts']
    for name in ('model.tgl', 'source.tar.gz'):
        sweep.followup.artifact(origin, dict(path=name, sha256=manifest[name]))
    require(sweep.digest(origin / 'model.tgl') == prior()['model_sha256'], 'model changed')
    with tarfile.open(origin / 'source.tar.gz', 'r:gz') as archive:
        old = archive.extractfile(CLI).read()
    require(hashlib.sha256(old).hexdigest() == prior()['source_sha256'][CLI], 'archived CLI differs')
    expected = old.replace(b'(320U * TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS)',
                           b'(352U * TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS)').replace(
                           b'0..1228800 logic ticks (320 Garden days)', b'0..1351680 logic ticks (352 Garden days)')
    require((ROOT / CLI).read_bytes() == expected and expected != old, 'CLI changed beyond run limit/help')


def collect(out, output, origin, build, jobs):
    confirm.fresh(out, output)
    require(1 <= jobs <= 2 and shutil.disk_usage(out.parent).free >= 4 * 1024 ** 3, 'need 4 GiB free and 1..2 jobs')
    original = prior()
    origin_inputs(origin)
    sources = sweep.source_files()
    require(sources[CLI] == CLI_SHA, 'CLI limit implementation changed')
    require({p for p in confirm.runtime(sources).keys() | confirm.runtime(original['source_sha256']).keys()
             if sources.get(p) != original['source_sha256'].get(p)} == {CLI}, 'unrelated runtime changes')
    settings = sweep.late.settings_at(build / 'CMakeCache.txt', confirm.ARM)
    require(settings == original['build']['settings'], 'build options changed')
    out.mkdir(parents=True)
    (out / 'bin').mkdir()
    sweep.snapshot_sources(out, sources)
    shutil.copy2(ROOT / PROTOCOL, out / 'protocol.md')
    for src, dest in ((origin / 'model.tgl', 'model.tgl'), (build / 'toy-factory-garden-landing', 'bin/garden-landing'),
                      (build / 'CMakeCache.txt', 'CMakeCache.txt')):
        shutil.copy2(src, out / dest)
    value = dict(rule=RULE, protocol_sha256=PROTOCOL_SHA, input_sha256=INPUT_SHA, origin_manifest_sha256=ORIGIN_MANIFEST,
                 native_runs=36, training_runs=0, panel=confirm.panel(), source_sha256=sources, cli_sha256=sources[CLI],
                 analysis_sources={p: sources[p] for p in SOURCES}, model_sha256=original['model_sha256'],
                 build=dict(binary=sweep.digest(out / 'bin/garden-landing'), cache=sweep.digest(out / 'CMakeCache.txt'),
                            settings=settings), runs={})
    write_receipt(out / 'started.json', value)
    try:
        for phase in PHASES:
            value['runs'][phase] = {}
            keys = list(confirm.panel())
            with ThreadPoolExecutor(max_workers=jobs) as pool:
                for start in range(0, len(keys), jobs):
                    require(shutil.disk_usage(out).free >= 3 * 1024 ** 3, 'low disk space; evidence retained')
                    tasks = [pool.submit(call, out, value, k, phase) for k in keys[start:start + jobs]]
                    value['runs'][phase].update(task.result() for task in tasks)
            write_receipt(out / (phase + '.json'), value['runs'][phase])
        value['gallery'] = sweep.contact_sheet(out, groups(value))
        value['gallery']['sha256'] = sweep.digest(out / 'contact-sheet.png')
        require(all(sweep.digest(ROOT / p) == sources[p] for p in (*confirm.runtime(sources), *SOURCES, PROTOCOL)),
                'sources changed during follow-up')
        require(sweep.digest(out / 'bin/garden-landing') == value['build']['binary'] and
                sweep.digest(out / 'CMakeCache.txt') == value['build']['cache'] and
                sweep.digest(out / 'model.tgl') == value['model_sha256'], 'captured inputs changed')
        value['receipt_sha256'] = sweep.fingerprint(value)
        check_capture(value)
        write_receipt(out / 'capture.json', value)
        write_receipt(out / 'manifest.json', dict(rule=RULE, artifacts={str(p.relative_to(out)): sweep.digest(p)
                      for p in sorted(out.rglob('*')) if p.is_file()}))
        sweep.write_gzip(output, value)
    except Exception as error:
        write_receipt(out / 'failure.json', dict(error=str(error), automatic_retry=False))
        raise
    return value


def verify_bundle(root, value):
    check_capture(value)
    manifest = json.loads((root / 'manifest.json').read_text())
    require(manifest['rule'] == RULE and json.loads((root / 'capture.json').read_text()) == value and
            set(manifest['artifacts']) == {str(p.relative_to(root)) for p in root.rglob('*')
                                         if p.is_file() and p != root / 'manifest.json'} and
            sweep.archived_sources(root / 'source.tar.gz') == value['source_sha256'], 'bundle inventory/snapshot differs')
    for name, sha in manifest['artifacts'].items():
        sweep.followup.artifact(root, dict(path=name, sha256=sha))
    for name, sha in (('protocol.md', PROTOCOL_SHA), ('bin/garden-landing', value['build']['binary']),
                      ('CMakeCache.txt', value['build']['cache']), ('model.tgl', value['model_sha256'])):
        require(sweep.digest(root / name) == sha, 'bundle input differs')
    for phase in PHASES:
        for key, run in value['runs'][phase].items():
            directory = root / run['directory']
            require(json.loads((directory / 'run.json').read_text()) == run and
                    json.loads((directory / 'result.json').read_text()) == run['result'], 'run receipt differs')
            data = sweep.followup.artifact(root, run['frame']).read_bytes()
            require(len(data) == 115200 and f'{zlib.crc32(data):08x}' == run['result']['framebuffer_crc32'], 'frame differs')
            for kind, item in run['traces'].items():
                path = sweep.followup.artifact(root, item)
                require(trace_receipt(path, kind, run['result']) == run['receipts'][kind], 'raw observations differ')
                digest, size = hashlib.sha256(), 0
                with gzip.open(path, 'rb') as stream:
                    while block := stream.read(1024 * 1024):
                        digest.update(block)
                        size += len(block)
                require((digest.hexdigest(), size) == (item['raw_sha256'], item['raw_bytes']), 'restoration bytes differ')
            print('offline verified: ' + phase + '/' + key, flush=True)
    require(sweep.digest(root / 'contact-sheet.png') == value['gallery']['sha256'], 'gallery file differs')
    with tempfile.TemporaryDirectory(prefix='patch-followup-gallery-') as tmp:
        frames = groups(value)
        for row in frames:
            for frame in row:
                frame['framebuffer'] = str(root / frame['framebuffer'])
        found = sweep.contact_sheet(Path(tmp), frames)
        found['sha256'] = sweep.digest(Path(tmp) / 'contact-sheet.png')
        require(found == value['gallery'], 'gallery does not reproduce')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--collect', type=Path)
    mode.add_argument('--verify', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--origin', type=Path, default=ROOT / 'artifacts/garden-landing-patch-confirmation-v1')
    parser.add_argument('--build', type=Path, default=ROOT / 'build-host-late-dispersal')
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    require(bool(args.collect) == bool(args.out) and not (args.collect and args.bundle), 'invalid output/mode')
    if args.collect:
        confirm.fresh(args.collect, args.out)
        collect(args.collect.resolve(), args.out.resolve(), args.origin.resolve(), args.build.resolve(), args.jobs)
    else:
        with gzip.open(args.verify, 'rt') as stream:
            value = json.load(stream)
        check_capture(value)
        if args.bundle:
            verify_bundle(args.bundle.resolve(), value)
    print('follow-up verified')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, TypeError, OSError, StopIteration) as error:
        sys.exit(str(error))
