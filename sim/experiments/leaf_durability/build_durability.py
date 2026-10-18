#!/usr/bin/env python3
"""Isolate a longer host horizon; never modify the authenticated old builds."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'leaf_generalization'))
import run_generalization as previous

pilot, ROOT = previous.pilot, previous.ROOT
require, read, save, digest = previous.require, previous.read, previous.save, previous.digest
OLD = pilot.controls.TEST_BUILD
OUT = ROOT / 'artifacts/garden-leaf-durability-tools-v2'
DAYS, TICKS = 1376, 1376 * pilot.DAY
PROTOCOL = ROOT / 'benchmarks/garden-seasons/leaf-family-durability-protocol.md'
CHANGES = {
    'source/maintenance-fixture/garden_maintenance_run.h':
        [('TOY_FACTORY_MAINTENANCE_RUN_STOP        2334720U',
          f'TOY_FACTORY_MAINTENANCE_RUN_STOP        {TICKS}U')],
    'source/sim/garden_daylight_policy.h':
        [('TOY_FACTORY_DAYLIGHT_STOP  (608U * 3840U)', f'TOY_FACTORY_DAYLIGHT_STOP  ({DAYS}U * 3840U)'),
         ('TOY_FACTORY_DAYLIGHT_LIMIT 2048U', 'TOY_FACTORY_DAYLIGHT_LIMIT 6144U')],
    'modules/leaf_replay/test_leaf_family.py': [('2334721', str(TICKS + 1))],
    'modules/leaf_replay/test_leaf_replay.py': [('2334721', str(TICKS + 1))],
}
TARGETS = ('leaf-replay', 'leaf-family-replay', 'leaf-family-owned', 'leaf-replay-test',
           'leaf-family-test', 'leaf-owned-test', 'leaf-neural-test', 'leaf-neural-world-test',
           'maintenance-run-test')
BINARIES = {name: (name if name.startswith(('leaf-replay', 'leaf-family', 'leaf-owned')) else
                  'neural/' + name if name.startswith('leaf-neural') else 'neural/frozen-core/' + name)
            for name in TARGETS}
TESTS = ('leaf-replay-native', 'leaf-family-native', 'leaf-owned-native', 'leaf-replay-cli',
         'leaf-family-cli', 'leaf-owned-cli', 'leaf-neural-native', 'leaf-neural-world',
         'leaf-neural-codec-independent', 'maintenance-run-native', 'maintenance-run-decoder')


def inventory(path):
    return pilot.controls.replay.build.inventory(path)


def expected_sources():
    require(digest(OLD / 'build.json') == pilot.controls.TEST_BUILD_SHA, 'old build receipt differs')
    meta = read(OLD / 'build.json')
    require(inventory(OLD / 'source') == meta['staged_sha256'] and
            inventory(OLD / 'modules') == meta['module_sha256'], 'old source inventory differs')
    result = {f'{group}/{name}': identity for group, field in
              (('source', 'staged_sha256'), ('modules', 'module_sha256'))
              for name, identity in meta[field].items()}
    for name, replacements in CHANGES.items():
        raw = (OLD / name).read_text()
        for before, after in replacements:
            require(raw.count(before) == 1, 'ambiguous horizon edit: ' + name)
            raw = raw.replace(before, after)
        result[name] = previous.sha(raw.encode())
    return result


def verify(out=OUT, native=True):
    require(not (out / 'failure.json').exists(), 'failed build is not usable')
    meta = read(out / 'build.json')
    require(meta['schema'] == 'garden-leaf-durability-build-v1' and meta['days'] == DAYS and
            meta['old_build_sha256'] == pilot.controls.TEST_BUILD_SHA and
            meta['changes'] == {k: [list(pair) for pair in v] for k, v in CHANGES.items()} and
            meta['recipe_sha256'] == digest(HERE / 'build_durability.py') and
            meta['protocol_sha256'] == digest(PROTOCOL), 'build scope differs')
    require(meta['files'] == expected_sources(), 'unexpected build delta')
    for name, identity in meta['files'].items():
        require(digest(out / name) == identity, 'staged build file differs')
    require(digest(out / 'model.tgl') == previous.sha(previous.baseline()['growth']), 'W2 differs')
    for index in range(3):
        receipt = read(out / f'build-{index}.json')
        require(receipt['returncode'] == 0, 'build/test failed')
        if index == 2:
            require('100% tests passed, 0 tests failed out of 11' in receipt['stdout'], 'incomplete contract tests')
    if native:
        for name, identity in meta['binary_sha256'].items():
            require(digest(out / 'native' / BINARIES[name]) == identity, 'new binary differs')
    return meta


def main():
    require(not OUT.exists() and not OUT.is_symlink(), 'fresh build directory required')
    pilot.controls.verify_inputs()
    expected = expected_sources()
    OUT.mkdir()
    try:
        for group in ('source', 'modules'):
            shutil.copytree(OLD / group, OUT / group)
        for name in ('model.tgl', 'reference.json'):
            shutil.copy2(OLD / name, OUT / name)
        for name, replacements in CHANGES.items():
            path = OUT / name
            raw = path.read_text()
            for before, after in replacements:
                require(raw.count(before) == 1, 'ambiguous staged edit')
                raw = raw.replace(before, after)
            path.write_text(raw)
        require({f'{group}/{name}': h for group in ('source', 'modules')
                 for name, h in inventory(OUT / group).items()} == expected, 'unexpected staged edits')
        commands = [
            ['cmake', '-S', OUT / 'modules/leaf_replay', '-B', OUT / 'native', '-G', 'Ninja',
             '-DTOY_FACTORY_LEAF_CORE=' + str(OUT / 'source'), '-DCMAKE_C_FLAGS=-O2',
             '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
             '-DTOY_FACTORY_LEAF_REFERENCE_RESULTS=' + str(OUT / 'reference.json')],
            ['cmake', '--build', OUT / 'native', '--parallel', '2', '--target', *TARGETS],
            ['ctest', '--test-dir', OUT / 'native', '--output-on-failure', '-R', '^(' + '|'.join(TESTS) + ')$']]
        env = os.environ | {'PYTHONPATH': os.pathsep.join(map(str, (ROOT / 'sim', ROOT / 'scripts/container'))),
                            'PYTHONDONTWRITEBYTECODE': '1'}
        for index, args in enumerate(commands):
            print(f'Durability build/check {index + 1}/3', flush=True)
            process = subprocess.run(list(map(str, args)), capture_output=True, text=True, env=env, timeout=240)
            save(OUT / f'build-{index}.json', dict(args=list(map(str, args)), returncode=process.returncode,
                                                stdout=process.stdout, stderr=process.stderr))
            require(process.returncode == 0, process.stdout[-12000:] + process.stderr[-12000:])
        save(OUT / 'build.json', dict(schema='garden-leaf-durability-build-v1', days=DAYS,
            old_build_sha256=pilot.controls.TEST_BUILD_SHA, changes=CHANGES, files=expected,
            recipe_sha256=digest(HERE / 'build_durability.py'), protocol_sha256=digest(PROTOCOL),
            binary_sha256={name: digest(OUT / 'native' / BINARIES[name]) for name in TARGETS}))
        verify()
        pilot.controls.verify_inputs()
    except BaseException as error:
        save(OUT / 'failure.json', dict(error=repr(error), research_runs=0))
        raise
    print('Eleven contract suites passed; old builds unchanged; no research calls.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        verify()
    else:
        main()
