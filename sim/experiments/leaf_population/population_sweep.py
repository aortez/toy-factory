#!/usr/bin/env python3
"""Whole-population repair light-threshold sweep on fresh weather; no training or selection."""

import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import dataclasses
from datetime import datetime, timezone
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path
import random
import re
import subprocess
import sys
import time

import population_repair_opportunities as opportunities

collect, prepare, score = opportunities.collect, opportunities.prepare, opportunities.score
sys.path.insert(0, str(collect.ROOT / 'sim/experiments/leaf_model_tools'))
import leaf_model  # noqa: E402

PROTOCOL = collect.ROOT / 'benchmarks/garden-seasons/leaf-population-threshold-sweep-protocol.md'
BASELINE = collect.ROOT / 'benchmarks/garden-seasons/leaf-population-results.json.gz'
BASELINE_SHA = '3aae48b92ed9787f9dc1601052330cdbf96ed9d72f3d845e0b9932d50112af49'
SEED_LABEL = 'toy-factory/garden-repair-threshold-sweep-v1/weather-{:02d}'
SEED_COUNT = 16
# Light-feature gates on 0-127; 65 reproduces fixed wear (light >= 131) and 128 never renews.
FEATURES = (0, 32, 48, 56, 61, 65, 68, 71, 74, 80, 96, 128)
REFERENCES = ('s1-g3-c4', 's2-g3-c1')
FIXED, SEARCH = 'light-065', 's1-g3-c4'
ANCHORS = (('light-065', 'initial'), ('s1-g3-c4', 's1-g3-c4'), ('s2-g3-c1', 's2-g3-c1'))
ANCHOR_SEED, ANCHOR_LAYOUT = '58d7d6ca', 'rainfed'
WORKERS, CALL_SECONDS, BUDGET_SECONDS = 12, 300, 90 * 60
BOOTSTRAP_DRAWS, BOOTSTRAP_SEED = 10000, 20261018
STOP = 1376 * score.DAY
SHRUB = 1
SCHEMA = 'garden-threshold-sweep-v1'


def seeds():
    """First four SHA256 bytes of each fixed label, read little-endian."""
    return [f"{int.from_bytes(hashlib.sha256(SEED_LABEL.format(i).encode()).digest()[:4], 'little'):08x}"
            for i in range(1, SEED_COUNT + 1)]


def audit():
    """Whole-word seed tokens in tracked files outside this sweep, including gzip JSON."""
    pattern = re.compile(rb'\b(?:' + b'|'.join(s.encode() for s in seeds()) + rb')\b')
    names = subprocess.run(['git', 'ls-files', '-z'], cwd=collect.ROOT, capture_output=True,
                           check=True).stdout.decode().split('\0')
    own = {Path(__file__).name, 'test_population_sweep.py'}
    scanned, found = 0, {}
    for name in filter(None, names):
        path = collect.ROOT / name
        if path.name in own or path.name.startswith('leaf-population-threshold-sweep'):
            continue
        raw = path.read_bytes()
        if path.suffix == '.gz':
            raw = gzip.decompress(raw)
        scanned += 1
        for match in pattern.finditer(raw):
            found.setdefault(match.group().decode(), []).append(name)
    return dict(files=scanned, seeds=seeds(), occurrences=found)


def threshold_model(base, feature):
    """Fixed wear with only its light-gate bias moved; every other parameter is unchanged."""
    model = leaf_model.decode(base)
    score.require(model.hidden_shift == 6 and model.hidden_bias[0] == 64 * 65 and
                  model.hidden_weights[:11] == (0, -64) + (0,) * 9, 'fixed-wear light gate differs')
    score.require(score.integer(feature, 0, 128), 'invalid light threshold')
    return leaf_model.encode(dataclasses.replace(
        model, hidden_bias=(64 * feature,) + model.hidden_bias[1:]))


def light_minimum(feature):
    """Smallest observed light whose clipped feature reaches the gate, or None."""
    return next((light for light in range(256) if light * 127 // 255 >= feature), None)


def verify_model(raw, feature):
    """Exhaustive light/condition check; decision_model proves other inputs cannot matter."""
    model = opportunities.decision_model(raw)
    score.require(model[3][4] == model[3][10] == 0, 'light gate depends on body size or price')
    minimum = light_minimum(feature)
    for light in range(256):
        for condition in range(256):
            renew = opportunities.evaluate(model, condition, light, 21)['action']
            score.require(renew == int(minimum is not None and light >= minimum and condition <= 192),
                          'threshold decision differs')
    return dict(feature=feature, light_minimum=minimum,
                condition_maximum=None if minimum is None else 192)


def policies(named):
    result = {f'light-{feature:03d}': threshold_model(named['initial'], feature)
              for feature in FEATURES}
    score.require(result[FIXED] == named['initial'], 'fixed-wear reconstruction differs')
    return result | {name: named[name] for name in REFERENCES}


def roster(names):
    return [dict(id=f'{policy}-{seed}-{layout}', policy=policy, seed=seed, layout=layout)
            for seed in seeds() for layout in score.LAYOUTS for policy in names]


def summarize(value):
    analysis = score.analyze_world(value)
    last = analysis['checkpoints']['1376']
    retained = [a + b > 0 for a, b in zip(last['living_species'], last['pending_species'], strict=True)]
    return dict(
        renewal={start: analysis['periods'][start]['key'][0] for start in ('192', '576', '960')},
        closing_window_families=analysis['periods']['960']['closing_window_families'],
        family_status=last['family_status'], retained_species=retained, living=last['living'],
        pending=last['pending'], offspring_born=last['offspring_born'],
        established_offspring=last['established_offspring'],
        died_before_establishment=last['died_before_establishment'], deaths=last['deaths'],
        empty_living_intervals=len(analysis['empty_living_intervals']),
        extinction_tick=analysis['extinction_tick'])


def interval(values, rng):
    """95% percentile interval of a mean over seeds resampled with replacement."""
    draws = sorted(sum(rng.choices(values, k=len(values))) / len(values)
                   for _ in range(BOOTSTRAP_DRAWS))
    return [draws[int(0.025 * BOOTSTRAP_DRAWS)], draws[int(0.975 * BOOTSTRAP_DRAWS) - 1]]


def aggregate(rows, names):
    """Equal weight per world; both layouts of a weather seed resample together."""
    by = {(r['policy'], r['seed'], r['layout']): r for r in rows}
    score.require(len(by) == len(rows) == len(names) * SEED_COUNT * len(score.LAYOUTS) and
                  set(by) == {(p, s, l) for p in names for s in seeds() for l in score.LAYOUTS},
                  'sweep roster differs')
    late = {p: [sum(Fraction(*by[p, s, l]['renewal']['960']) for l in score.LAYOUTS) / len(score.LAYOUTS)
                for s in seeds()] for p in names}
    losses = {p: [sum(by[p, s, l]['family_status'].count('extinct') for l in score.LAYOUTS)
                  for s in seeds()] for p in names}
    rng = random.Random(BOOTSTRAP_SEED)
    result = {}
    for p in names:
        worlds = [by[p, s, l] for s in seeds() for l in score.LAYOUTS]
        species = [sum(w['retained_species']) for w in worlds]
        result[p] = dict(
            renewal={start: score.rational(sum(Fraction(*w['renewal'][start]) for w in worlds) /
                                           len(worlds)) for start in ('192', '576', '960')},
            late_renewal=float(sum(late[p]) / len(late[p])),
            late_renewal_interval=interval([float(v) for v in late[p]], rng),
            late_minus_search=interval([float(a - b) for a, b in zip(late[p], late[SEARCH])], rng),
            founders=sum(len(w['family_status']) for w in worlds),
            extinct_families=sum(losses[p]),
            extinct_minus_fixed=interval([a - b for a, b in zip(losses[p], losses[FIXED])], rng),
            dormant_families=sum(w['family_status'].count('dormant') for w in worlds),
            single_species_gardens=sum(n == 1 for n in species),
            mean_retained_species=sum(species) / len(species),
            shrub_gardens=sum(w['retained_species'][SHRUB] for w in worlds),
            empty_gardens=sum(w['empty_living_intervals'] > 0 or w['extinction_tick'] is not None
                              for w in worlds),
            closing_window_families=sum(w['closing_window_families'] for w in worlds),
            offspring_born=sum(w['offspring_born'] for w in worlds),
            established_offspring=sum(w['established_offspring'] for w in worlds),
            died_before_establishment=sum(w['died_before_establishment'] for w in worlds),
            living=sum(w['living'] for w in worlds), pending=sum(w['pending'] for w in worlds))
    return result


def decide(result):
    """Predeclared criteria: Search 1's late renewal with fixed wear's variety, no empty garden."""
    fixed, search = result[FIXED], result[SEARCH]
    both = [p for p in result if p.startswith('light-') and result[p]['empty_gardens'] == 0 and
            result[p]['late_renewal'] >= search['late_renewal'] and
            result[p]['extinct_families'] <= fixed['extinct_families'] and
            result[p]['single_species_gardens'] <= fixed['single_species_gardens']]
    return dict(tradeoff_reproduced=search['late_renewal'] > fixed['late_renewal'] and
                search['extinct_families'] > fixed['extinct_families'], both=both)


def save(path, value):
    collect.save(path, value)


def bounded(calls, worker):
    """At most WORKERS concurrent calls; stop submitting after any observed failure."""
    iterator, completed = iter(calls), []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        active = {pool.submit(worker, call) for call in [next(iterator) for _ in range(min(WORKERS, len(calls)))]}
        while active:
            done, active = wait(active, return_when=FIRST_COMPLETED)
            for future in done:
                completed.append(future.result())
                print(f'Verified {completed[-1]} ({len(completed)}/{len(calls)})', flush=True)
            for _ in done:
                call = next(iterator, None)
                if call is not None:
                    active.add(pool.submit(worker, call))
    return completed


def sources():
    paths = [Path(__file__), PROTOCOL, collect.ROOT / 'sim/experiments/leaf_model_tools/leaf_model.py']
    paths += [p for p in (collect.ROOT / 'sim/research_player').iterdir() if p.suffix in ('.c', '.h', '.txt')]
    return {str(p.relative_to(collect.ROOT)): prepare.sha(p.read_bytes()) for p in sorted(paths)}


def anchor(binary, out, models, named, size):
    """Custom-path replays must equal the archived population runs, apart from rendering."""
    raw = BASELINE.read_bytes()
    score.require(prepare.sha(raw) == BASELINE_SHA, 'population baseline differs')
    baseline = json.loads(gzip.decompress(raw))
    (out / 'anchors').mkdir()
    for policy, archived in ANCHORS:
        folder = out / 'anchors' / policy
        stdout = collect.process_call([str(binary), str(out / 'models' / f'{policy}.tlf'), ANCHOR_SEED,
                                       ANCHOR_LAYOUT, str(STOP), 'all'], folder, CALL_SECONDS)
        value = json.loads(stdout)
        score.validate_record(value, models[policy], seed=ANCHOR_SEED, layout=ANCHOR_LAYOUT,
                              ticks=STOP, uniform_bytes=size)
        reference = json.loads(prepare.blob(baseline, f'runs/{archived}-{ANCHOR_SEED}-{ANCHOR_LAYOUT}-primary/stdout.json'))
        score.require(models[policy] == named[archived] and value['framebuffer_crc32'] is None and
                      {k: v for k, v in value.items() if k != 'framebuffer_crc32'} ==
                      {k: v for k, v in reference.items() if k != 'framebuffer_crc32'},
                      f'archived replay differs: {policy}')
        print(f'Anchor {policy} matches archived {archived}', flush=True)
    return [policy for policy, _ in ANCHORS]


def call(binary, out, models, size, deadline, entry):
    remaining = deadline - time.monotonic()
    score.require(remaining > 0, 'collection time budget exhausted')
    folder = out / 'runs' / entry['id']
    stdout = collect.process_call([str(binary), str(out / 'models' / f"{entry['policy']}.tlf"),
                                   entry['seed'], entry['layout'], str(STOP), 'all'],
                                  folder, min(CALL_SECONDS, remaining))
    value = json.loads(stdout)
    score.validate_record(value, models[entry['policy']], seed=entry['seed'], layout=entry['layout'],
                          ticks=STOP, uniform_bytes=size)
    save(folder / 'summary.json', entry | summarize(value) | dict(stdout_sha256=prepare.sha(stdout)))
    return entry['id']


def run(binary, out):
    score.require(not out.exists() and not out.is_symlink(), 'fresh output directory required')
    score.require(PROTOCOL.exists(), 'protocol must be fixed before collection')
    _, named, size = collect.archive_inputs()
    models = policies(named)
    thresholds = {p: verify_model(models[p], int(p.removeprefix('light-'))) for p in models
                  if p.startswith('light-')}
    names, plan, pinned = list(models), roster(list(models)), sources()
    binary_hash = prepare.sha(binary.read_bytes())
    out.mkdir(parents=True)
    (out / 'models').mkdir()
    for name, raw in models.items():
        collect.write(out / 'models' / f'{name}.tlf', raw)
    save(out / 'started.json', dict(schema=SCHEMA + '-collection', plan=plan, seeds=seeds(),
        seed_label=SEED_LABEL, policies=names, thresholds=thresholds,
        models={n: prepare.sha(raw) for n, raw in models.items()}, workers=WORKERS,
        timeout_per_call=CALL_SECONDS, collection_seconds=BUDGET_SECONDS, binary_sha256=binary_hash,
        sources=pinned, uniform_bytes=size, started_utc=datetime.now(timezone.utc).isoformat(),
        training=False))
    try:
        began = time.monotonic()
        deadline = began + BUDGET_SECONDS
        anchored = anchor(binary, out, models, named, size)
        (out / 'runs').mkdir()
        completed = bounded(plan, lambda entry: call(binary, out, models, size, deadline, entry))
        score.require(len(completed) == len(plan) and time.monotonic() <= deadline,
                      'collection budget differs')
        score.require(binary_hash == prepare.sha(binary.read_bytes()) and pinned == sources(),
                      'binary or sources changed during collection')
        rows = [json.loads((out / 'runs' / e['id'] / 'summary.json').read_bytes()) for e in plan]
        analysis = aggregate(rows, names)
        save(out / 'result.json', dict(schema=SCHEMA + '-result', complete=True, calls=len(plan),
            anchors=anchored, elapsed_seconds=time.monotonic() - began, analysis=analysis,
            decision=decide(analysis)))
        files = {str(p.relative_to(out)): prepare.sha(p.read_bytes()) for p in sorted(out.rglob('*'))
                 if p.is_file()}
        save(out / 'manifest.json', dict(schema=SCHEMA + '-files', files=files))
        print(json.dumps(dict(complete=True, calls=len(plan), decision=decide(analysis))), flush=True)
    except BaseException as error:
        save(out / 'failure.json', dict(error=repr(error)))
        raise


def check(out):
    """Offline re-validation of every retained output; never executes the simulator."""
    started = json.loads((out / 'started.json').read_bytes())
    result = json.loads((out / 'result.json').read_bytes())
    manifest = json.loads((out / 'manifest.json').read_bytes())
    _, named, size = collect.archive_inputs()
    models = policies(named)
    score.require(started['models'] == {n: prepare.sha(raw) for n, raw in models.items()} and
                  started['seeds'] == seeds() and started['plan'] == roster(list(models)) and
                  started['uniform_bytes'] == size, 'collection plan differs')
    score.require(all(prepare.sha((out / name).read_bytes()) == digest
                      for name, digest in manifest['files'].items()), 'retained file differs')
    rows = []
    for entry in started['plan']:
        folder = out / 'runs' / entry['id']
        stdout = (folder / 'stdout.json').read_bytes()
        value = json.loads(stdout)
        score.validate_record(value, models[entry['policy']], seed=entry['seed'],
                              layout=entry['layout'], ticks=STOP, uniform_bytes=size)
        row = entry | summarize(value) | dict(stdout_sha256=prepare.sha(stdout))
        score.require(row == json.loads((folder / 'summary.json').read_bytes()), 'summary differs')
        rows.append(row)
    analysis = aggregate(rows, list(models))
    score.require(result['analysis'] == json.loads(json.dumps(analysis)) and
                  result['decision'] == decide(analysis), 'analysis differs')
    return dict(calls=len(rows), decision=result['decision'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('audit')
    models = sub.add_parser('models')
    models.add_argument('out', type=Path)
    collection = sub.add_parser('run')
    collection.add_argument('--binary', type=Path, required=True)
    collection.add_argument('--out', type=Path, required=True)
    verify = sub.add_parser('check')
    verify.add_argument('out', type=Path)
    args = parser.parse_args()
    if args.command == 'audit':
        print(json.dumps(audit(), indent=2, sort_keys=True))
    elif args.command == 'models':
        _, named, _ = collect.archive_inputs()
        built = policies(named)
        args.out.mkdir(parents=True)
        for name, raw in built.items():
            collect.write(args.out / f'{name}.tlf', raw)
        print(json.dumps({name: dict(sha256=prepare.sha(raw)) |
                          (verify_model(raw, int(name.removeprefix('light-')))
                           if name.startswith('light-') else {})
                          for name, raw in built.items()}, indent=2))
    elif args.command == 'run':
        # Do not resolve the destination: a symlink must be rejected, not followed.
        run(args.binary.resolve(), args.out.absolute())
    else:
        print(json.dumps(check(args.out), indent=2))


if __name__ == '__main__':
    main()
