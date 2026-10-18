#!/usr/bin/env python3
"""Forty-eight fixed family matches; no search, mutation or promotion."""

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import gzip
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / 'leaf_owned_check'))
import compare_leaf_owned as replay
import collect_leaf_owned as evidence
from family_fitness import aggregate, score_family
sys.path.insert(0, str(ROOT / 'sim'))
from garden_gallery import contact_sheet, rgb565be_to_rgb888, write_png

RULE = 'garden-leaf-family-controls-v1'
PROTOCOL = ROOT / 'benchmarks/garden-seasons/leaf-family-controls-protocol.md'
BASELINE = ROOT / 'benchmarks/garden-seasons/leaf-family-owned-results.json.gz'
BASELINE_SHA = 'bbef398294d75ee33705425c710bff3dea22e4e1fc8a53b8bea6263a1e015872'
TEST_BUILD = ROOT / 'artifacts/garden-leaf-replay-tools-v8'
TEST_BUILD_SHA = '30936de399ced613f77e1683fd6f8eb4c33fbb124dd57b39b3e6a31404ede2fd'
SEEDS = ('3c308d3b', '97806ca5')
LAYOUTS = (('rainfed', 3), ('rainfed-crowded', 5))
MODELS = ('wait', 'renew', 'light')
require, read, save, digest = replay.require, replay.read, replay.save, replay.digest


def condition(case):
    return case['seed'] + '-' + case['scenario']


def plan():
    result = []
    for seed in SEEDS:
        for scenario, count in LAYOUTS:
            for founder in range(1, count + 1):
                for model in MODELS:
                    name = f'{seed}-{scenario}-f{founder}-{model}'
                    case = dict(name=name, seed=seed, scenario=scenario, founder=founder, model=model)
                    result.append(dict(label=name, case=case, days=608, capture=True,
                                       binary='owned', timeout_seconds=180))
    return result


def source_pins():
    # Preserve the actual local Python import closure, including the scorer's
    # existing ledger validators and the established PNG/gallery implementation.
    paths = {PROTOCOL}
    for module in tuple(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if filename:
            path = Path(filename).resolve()
            if path.suffix == '.py' and path.is_relative_to(ROOT):
                paths.add(path)
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(paths)}


def verify_inputs():
    require(digest(BASELINE) == BASELINE_SHA, 'owned comparison evidence differs')
    baseline = evidence.verify(json.loads(gzip.decompress(BASELINE.read_bytes())))
    identities = baseline['result']['scope']['identities']
    meta = read(replay.NEW / 'build.json')
    require(digest(replay.NEW / 'build.json') == identities['new_build_sha256'], 'runtime build differs')
    require(meta['module_sha256'] == replay.build.inventory(replay.NEW / 'modules') and
            meta['staged_sha256'] == replay.build.inventory(replay.NEW / 'source'), 'runtime sources differ')
    require(all(digest(replay.NEW / 'native' / name) == value for name, value in meta['binary_sha256'].items()),
            'runtime binary differs')
    require(digest(replay.NEW / 'model.tgl') == identities['growth_model_sha256'], 'W2 differs')
    require(digest(TEST_BUILD / 'build.json') == TEST_BUILD_SHA, 'follow-up test build differs')
    tested = read(TEST_BUILD / 'build.json')
    require(tested['source_sha256'] == replay.build.pins(), 'current replay sources differ from tested sources')
    changed = {path for path in set(meta['source_sha256']) | set(tested['source_sha256'])
               if meta['source_sha256'].get(path) != tested['source_sha256'].get(path)}
    require(changed == {'sim/experiments/leaf_replay/garden_leaf_owned_test.c'} and
            meta['staged_sha256'] == tested['staged_sha256'] and
            meta['growth_model_sha256'] == tested['growth_model_sha256'], 'runtime changed after comparison')
    for folder in (replay.NEW, TEST_BUILD):
        tests = read(folder / 'build-2.json')
        require(tests['returncode'] == 0 and '100% tests passed, 0 tests failed out of 25' in tests['stdout'],
                'incomplete integration tests')
    replay.build.origin.verify(replay.build.PREPARED)
    return identities, baseline


def bounded_calls(calls, execute):
    """At most two submitted calls; failures never enqueue the remaining work."""
    pending, results = {}, {}
    iterator = iter(calls)
    with ThreadPoolExecutor(max_workers=2) as pool:
        for _ in range(2):
            call = next(iterator, None)
            if call is not None:
                pending[pool.submit(execute, call)] = call
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            ordered = sorted(done, key=lambda f: pending[f]['label'])
            # Resolve every completed future before submitting replacements.
            completed = [(pending[f], f.result()) for f in ordered]
            for future in ordered:
                del pending[future]
            for call, result in completed:
                results[call['label']] = result
            for _ in completed:
                call = next(iterator, None)
                if call is not None:
                    pending[pool.submit(execute, call)] = call
    return results


def rational_key(key):
    return [[part.numerator, part.denominator] for part in key]


def analyze(values):
    """Score complete bound histories; raw pixels/receipts are checked by the caller."""
    calls = plan()
    require(set(values) == {c['label'] for c in calls}, 'incomplete role/model roster')
    roles = {f'{seed}-{scenario}': tuple(range(1, count + 1)) for seed in SEEDS for scenario, count in LAYOUTS}
    scores = {model: {key: {} for key in roles} for model in MODELS}
    details = {}
    for call in calls:
        case, value = call['case'], values[call['label']]
        require(value['seed'] == case['seed'] and value['scenario'] == case['scenario'] and
                type(value['candidate_founder']) is int and value['candidate_founder'] == case['founder'] and
                type(value['ticks']) is int and value['ticks'] == 608 * replay.DAY and
                value['leaf_model_hex'] == replay.models()[case['model']].hex() and
                value['resident_policy'] == replay.RESIDENT, 'score binding differs')
        score = score_family(value | {'tick': value['ticks']}, case['founder'], start_day=192, window_count=6)
        scores[case['model']][condition(case)][case['founder']] = score
        family = [p for p in value['lineages'] if value['family_roots'][p['id'] - 1] == case['founder']]
        living = [p for p in value['lineages'] if p['death_tick'] is None]
        details[call['label']] = dict(score=score.record(), family_end_alive=sum(p['death_tick'] is None for p in family),
            family_max_generation=max(p['generation'] for p in family), garden_end_alive=len(living),
            garden_end_species=sorted({p['species'] for p in living}))
    summary = {}
    for model in MODELS:
        flat = [score for per_role in scores[model].values() for score in per_role.values()]
        summary[model] = dict(key=rational_key(aggregate(scores[model], expected_roles=roles)),
            roles_with_renewal=sum(score.key[0] > 0 for score in flat), roles=16,
            raw_renewal_links=sum(sum(score.renewal_children) for score in flat),
            conditions={key: rational_key(aggregate({key: scores[model][key]}, expected_roles={key: roster}))
                        for key, roster in roles.items()})
    return dict(rule='garden-leaf-family-renewal-v1', start_day=192, window_count=6, stop_day=608,
                summary=summary, matches=details, selected_model=None)


def render_gallery(out):
    entries, sheets = {}, {}
    for call in plan():
        folder = out / call['label']
        target = folder / 'frame.png'
        require(not target.exists(), 'new PNG required')
        write_png(target, 240, 240, rgb565be_to_rgb888((folder / 'frame.raw').read_bytes()))
        entries[call['label']] = dict(png=str(target.relative_to(out)), sha256=digest(target),
                                     framebuffer_sha256=digest(folder / 'frame.raw'))
    for seed in SEEDS:
        for scenario, count in LAYOUTS:
            key = seed + '-' + scenario
            folder = out / 'gallery' / key
            folder.mkdir(parents=True)
            groups = [[dict(id=f'{key}-f{founder}-{model}',
                            framebuffer=f'../../{key}-f{founder}-{model}/frame.raw')
                       for model in MODELS] for founder in range(1, count + 1)]
            sheets[key] = contact_sheet(folder, groups) | dict(path=str((folder / 'contact-sheet.png').relative_to(out)),
                                                             sha256=digest(folder / 'contact-sheet.png'))
    return dict(columns=list(MODELS), frames=entries, sheets=sheets)


def main(out):
    require(out.parent == ROOT / 'artifacts' and not out.exists() and not out.is_symlink(), 'fresh output required')
    require(shutil.disk_usage(ROOT).free >= 2 * 1024**3, 'less than 2 GiB free')
    identities, baseline = verify_inputs()
    calls = plan()
    require(len(calls) == len({c['label'] for c in calls}) == 48, 'wrong diagnostic budget')
    pins = source_pins()
    scope = dict(rule=RULE, calls=calls, maximum_native_calls=48, maximum_parallel_processes=2,
        timeout_seconds=180, automatic_retry=False, already_running_calls_may_finish_after_failure=True,
        training_runs=0, selected_model=None, baseline_sha256=BASELINE_SHA, identities=identities,
        followup_test_build_sha256=TEST_BUILD_SHA, source_sha256=pins)
    out.mkdir()
    save(out / 'started.json', scope)
    try:
        for name in pins:
            target = out / 'source' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
            require(digest(target) == pins[name], 'source changed while copying')
        shutil.copy2(replay.NEW / 'model.tgl', out / 'growth.tgl')
        for name, data in replay.models().items():
            (out / (name + '.tlf')).write_bytes(data)
        receipts = bounded_calls(calls, lambda call: replay.execute(out, call, identities))
        values = {}
        for call in calls:
            folder, receipt = out / call['label'], receipts[call['label']]
            require(digest(folder / 'stdout.json') == receipt['stdout_sha256'] and
                    digest(folder / 'frame.raw') == receipt['framebuffer_sha256'], 'completed output changed')
            values[call['label']] = replay.check_output(read(folder / 'stdout.json'), call,
                identities['growth_model_sha256'], (folder / 'frame.raw').read_bytes())
        for case in replay.CASES:
            name = f'{case["seed"]}-{case["scenario"]}-f{case["founder"]}-{case["model"]}'
            old = 'owned-' + case['name']
            require((out / name / 'stdout.json').read_text() == baseline['runs'][old]['stdout'], 'anchor output differs')
            pixels = bytes.fromhex(baseline['frames'][baseline['result']['receipts'][old]['framebuffer_sha256']])
            require((out / name / 'frame.raw').read_bytes() == pixels, 'anchor pixels differ')
        analysis = analyze(values)
        gallery = render_gallery(out)
        require(all(gallery['frames'][label]['framebuffer_sha256'] == row['framebuffer_sha256']
                    for label, row in receipts.items()), 'frame changed during rendering')
        require(verify_inputs()[0] == identities and pins == source_pins(), 'panel inputs changed')
        require(digest(out / 'growth.tgl') == identities['growth_model_sha256'] and
                all((out / (name + '.tlf')).read_bytes() == data for name, data in replay.models().items()),
                'copied model changed')
        save(out / 'result.json', dict(scope=scope, receipts=receipts, analysis=analysis, gallery=gallery,
                                      exact_prior_anchors=True, training_runs=0, selected_model=None))
        print('All 48 matched controls, 3 exact anchors, scores and endpoint images complete.', flush=True)
    except BaseException as error:
        save(out / 'failure.json', dict(error=str(error), automatic_retry=False, training_runs=0))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    main(parser.parse_args().out.absolute())
