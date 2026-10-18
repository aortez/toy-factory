#!/usr/bin/env python3
"""Build isolated saved-model replays without editing the frozen preparation."""

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(DIRECTORY.parent))
import garden_productive_build as origin

PREPARED = origin.ROOT / 'artifacts/garden-productive-tools-v2'
PREPARED_SHA = 'fd8451ce7f78ab573168aae60850a90d5eec386d54af2f277ff239a94bf78c78'
REFERENCE = origin.ROOT / 'benchmarks/garden-seasons/leaf-family-throughput.json'


def pins():
    return {str(path.relative_to(origin.ROOT)): origin.digest(path)
            for folder in (DIRECTORY, DIRECTORY.parent / 'leaf_neural')
            for path in sorted(folder.iterdir()) if path.is_file()}


def staged_runner():
    source = (PREPARED / 'source/sim/garden_landing_run.c').read_text()
    start = source.index('static int step(')
    body = source.index('\n{\n', start)
    end = source.index('\nint toy_factory_garden_landing_run_step(', body)
    declaration = source[start:body]
    arguments = ['run', 'audit', 'seeds', 'probe', 'observe', 'observer_context', 'resources',
                 'water', 'water_audit', 'node_limit', 'budget_mode', 'growth_observer',
                 'placement', 'placement_audit', 'seed_order_after', 'root_choice',
                 'root_allocation', 'seed_cursor', 'seed_wait', 'priority']
    # Preserve every existing caller through the identical NULL-override wrapper.
    changed = declaration.replace('static int step(', 'static int step_with_leaf(', 1)
    origin.require(changed.endswith(')'), 'private step signature changed')
    changed = changed[:-1] + ',\n const struct picosystem_garden_leaf_policy *leaf_override,\n' \
        'const struct toy_factory_leaf_replay_route *route)'
    implementation = source[body:end]
    needle = '.leaf_policy = toy_factory_maintenance_leaf_policy(run->maintenance_leaf_mode),'
    origin.require(implementation.count(needle) == 1, 'leaf binding changed')
    implementation = implementation.replace(needle, '.leaf_policy = leaf_override != NULL ? '
        'leaf_override : toy_factory_maintenance_leaf_policy(run->maintenance_leaf_mode),')
    before_policy = '\tconst struct picosystem_garden_agent_policy base_policy = {'
    origin.require(implementation.count(before_policy) == 1, 'base policy location changed')
    implementation = implementation.replace(before_policy,
        '\tconst struct leaf_route_context leaf_context = {\n'
        '\t\t.world = &world, .candidate = leaf_override, .route = route};\n'
        '\tconst struct picosystem_garden_leaf_policy routed = {\n'
        '\t\t.decide = routed_leaf_decide, .context = &leaf_context};\n'
        '\tif (route != NULL) {\n'
        '\t\tif ((route->decide == NULL) || (leaf_override == NULL)) { return -EINVAL; }\n'
        '\t\tleaf_override = &routed;\n\t}\n' + before_policy)
    wrapper = declaration + '\n{\n return step_with_leaf(' + ', '.join(arguments) + ', NULL, NULL);\n}\n'
    result = source[:start] + '#include "garden_leaf_replay_route.inc"\n\n' + changed + implementation \
        + '\n' + wrapper + source[end:]
    result += '\n#include "garden_leaf_replay_bridge.inc"\n'
    return subprocess.run(['clang-format', '--style=file:' + str(origin.ROOT / '.clang-format')],
        input=result, text=True, capture_output=True, check=True, timeout=30).stdout


def inventory(root):
    return {str(path.relative_to(root)): origin.digest(path)
            for path in sorted(root.rglob('*')) if path.is_file()}


def main(out):
    origin.require(not out.exists() and not out.is_symlink(), 'fresh replay build directory required')
    origin.require(origin.digest(PREPARED / 'build.json') == PREPARED_SHA, 'frozen preparation differs')
    baseline = origin.verify(PREPARED)
    reference_sha = origin.digest(REFERENCE)
    sources = pins()
    staged = staged_runner()
    expected = baseline['staged_sha256'] | {'sim/garden_landing_run.c':
                                           hashlib.sha256(staged.encode()).hexdigest()}
    out.mkdir()
    try:
        shutil.copytree(PREPARED / 'source', out / 'source')
        shutil.copy2(PREPARED / 'model.tgl', out / 'model.tgl')
        shutil.copy2(REFERENCE, out / 'reference.json')
        (out / 'source/sim/garden_landing_run.c').write_text(staged)
        origin.require(inventory(out / 'source') == expected, 'unexpected staged source change')
        # Compile the recorded source bytes, not mutable live prototype paths.
        modules = {}
        for name, sha in sources.items():
            relative = str(Path(name).relative_to('sim/experiments'))
            destination = out / 'modules' / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origin.ROOT / name, destination)
            modules[relative] = sha
        origin.require(inventory(out / 'modules') == modules, 'module snapshot differs')
        commands = [
            ['cmake', '-S', out / 'modules/leaf_replay', '-B', out / 'native', '-G', 'Ninja',
             '-DTOY_FACTORY_LEAF_CORE=' + str(out / 'source'), '-DCMAKE_C_FLAGS=-O2',
             '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
             '-DTOY_FACTORY_LEAF_REFERENCE_RESULTS=' + str(out / 'reference.json')],
            ['cmake', '--build', out / 'native', '--parallel', '2'],
            ['ctest', '--test-dir', out / 'native', '--output-on-failure']]
        env = os.environ | {'PYTHONPATH': os.pathsep.join(map(str, (origin.ROOT / 'sim',
                origin.ROOT / 'scripts/container'))), 'PYTHONDONTWRITEBYTECODE': '1'}
        for index, args in enumerate(commands):
            print('Replay build/check ' + str(index + 1) + '/3', flush=True)
            child = subprocess.run(list(map(str, args)), env=env, capture_output=True, text=True, timeout=180)
            origin.write_json(out / f'build-{index}.json', dict(args=list(map(str, args)),
                returncode=child.returncode, stdout=child.stdout, stderr=child.stderr))
            origin.require(child.returncode == 0, child.stdout[-14000:] + child.stderr[-14000:])
            if index == 2:
                origin.require('100% tests passed, 0 tests failed out of 25' in child.stdout,
                               'expected complete 25-suite matrix')
        origin.require(origin.verify(PREPARED) == baseline, 'frozen preparation changed')
        origin.require(sources == pins(), 'replay source changed during build')
        origin.require(inventory(out / 'source') == expected, 'staged source changed during build')
        origin.require(inventory(out / 'modules') == modules, 'module snapshot changed during build')
        origin.require(origin.digest(out / 'model.tgl') == baseline['model_sha256'], 'growth model changed')
        origin.require(origin.digest(REFERENCE) == reference_sha == origin.digest(out / 'reference.json'),
                       'archived prefix evidence changed')
        origin.write_json(out / 'build.json', dict(schema='garden-leaf-replay-preparation-v1',
            training_runs=0, research_runs=0, origin_sha256=PREPARED_SHA,
            growth_model_sha256=baseline['model_sha256'], source_sha256=sources,
            reference_results_sha256=reference_sha,
            staged_sha256=expected, module_sha256=modules,
            binary_sha256={name: origin.digest(out / 'native' / name)
                for name in ('leaf-replay', 'leaf-replay-test', 'leaf-family-replay',
                             'leaf-family-test', 'leaf-family-owned', 'leaf-owned-test')}))
    except BaseException as error:
        origin.write_json(out / 'failure.json', dict(error=str(error), training_runs=0, research_runs=0))
        raise
    print('Saved-model replay: 25 suites passed; frozen sources unchanged; no search or research panel.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    main(parser.parse_args().out.resolve())
