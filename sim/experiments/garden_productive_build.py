#!/usr/bin/env python3
"""Prepare a light-64 policy on the frozen conditions core; no research replay."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import garden_maintenance_conditions_build as previous

ROOT = previous.ROOT
ORIGIN = ROOT / 'artifacts/garden-maintenance-conditions-tools-v2'
ORIGIN_SHA = '4bc7d237ca10f8fc625125df116ac4eac986545c9b4ebeeff9ca8aa2b1904cb9'
PROTOCOL = ROOT / 'benchmarks/garden-seasons/landing-renewal-productive-repair-protocol.md'
require, digest, write_json = previous.require, previous.digest, previous.write_json
replace = previous.base.replace
FILES = ('garden_productive_repair.h', 'garden_productive_repair.c',
         'garden_productive_repair_test.c', 'garden_productive_repair.cmake', 'test_garden_productive_native.py')
BINARIES = (*previous.BINARIES, 'productive-repair-test')


def origin():
    require(digest(ORIGIN / 'build.json') == ORIGIN_SHA, 'frozen conditions preparation differs')
    return previous.verify(ORIGIN)


def transforms():
    fixture = ORIGIN / 'source/maintenance-fixture'
    read = lambda name: (fixture / name).read_text()
    binding = replace(read('garden_maintenance_binding.h'), '\tTOY_FACTORY_MAINTENANCE_RESERVE,\n',
        '\tTOY_FACTORY_MAINTENANCE_RESERVE,\n\tTOY_FACTORY_MAINTENANCE_PRODUCTIVE,\n')
    run = replace(read('garden_maintenance_run.c'), '#include "garden_maintenance_reserve.h"',
        '#include "garden_maintenance_reserve.h"\n#include "garden_productive_repair.h"')
    run = replace(run, '{NULL, "none", "all", "selective", "reserve-only"}',
        '{NULL, "none", "all", "selective", "reserve-only", "productive"}')
    run = replace(run, '\tif (mode == TOY_FACTORY_MAINTENANCE_RESERVE) {',
        '\tif (mode == TOY_FACTORY_MAINTENANCE_PRODUCTIVE) {\n'
        '\t\treturn toy_factory_productive_repair_policy();\n\t}\n'
        '\tif (mode == TOY_FACTORY_MAINTENANCE_RESERVE) {')
    command = replace(read('garden_maintenance_conditions.c'), '#include "garden_maintenance_conditions.h"',
        '#include "garden_maintenance_conditions.h"\n#include "garden_productive_repair.h"')
    command = replace(command, '(config->leaf_mode == TOY_FACTORY_MAINTENANCE_RESERVE));',
        '(config->leaf_mode == TOY_FACTORY_MAINTENANCE_RESERVE) ||\n'
        '\t\t(config->leaf_mode == TOY_FACTORY_MAINTENANCE_PRODUCTIVE));')
    command = replace(command, 'char *legacy[] = {argv[0], argv[1], "32dc6afd", argv[3], argv[4], argv[5]};',
        'const bool productive = strcmp(argv[3], "productive") == 0;\n'
        '\tchar *legacy[] = {argv[0], argv[1], "32dc6afd", productive ? "selective" : argv[3], argv[4], argv[5]};')
    command = replace(command, '\tresult.seed = seed;',
        '\tif (productive) {\n\t\tresult.leaf_mode = TOY_FACTORY_MAINTENANCE_PRODUCTIVE;\n\t}\n'
        '\tresult.seed = seed;')
    tests = replace(read('garden_maintenance_run_test.c'), 'if (mode >= 1U && mode <= 4U)',
        'if (mode >= 1U && mode <= 5U)')
    result = dict(zip(('garden_maintenance_binding.h', 'garden_maintenance_run.c',
                      'garden_maintenance_conditions.c', 'garden_maintenance_run_test.c', 'CMakeLists.txt'),
        (binding, run, command, tests, read('CMakeLists.txt') +
         '\ninclude(${CMAKE_CURRENT_LIST_DIR}/garden_productive_repair.cmake)\n'), strict=True))
    result.update({name: Path(__file__).with_name(name).read_text() for name in FILES})
    for name in tuple(result):
        if name.endswith(('.c', '.h')):
            result[name] = subprocess.run(['clang-format', '--style=file:' + str(ROOT / '.clang-format')],
                input=result[name], text=True, capture_output=True, check=True, timeout=30).stdout
    return {'maintenance-fixture/' + name: source for name, source in result.items()}


def pins():
    return {str(path.relative_to(ROOT)): digest(path) for path in
        (Path(__file__), ROOT / '.clang-format', PROTOCOL, *(Path(__file__).with_name(name) for name in FILES))}


def verify(out):
    inherited = origin()
    value = json.loads((out / 'build.json').read_text())
    require(value['schema'] == 'garden-productive-preparation-v1' and value['research_calls'] == 0 and
            value['origin_sha256'] == ORIGIN_SHA and value['source_sha256'] == pins(), 'preparation identity differs')
    expected = inherited['staged_sha256'] | {name: hashlib.sha256(source.encode()).hexdigest()
                                           for name, source in transforms().items()}
    require(previous.inventory(out) == value['staged_sha256'] == expected, 'unexpected source change')
    require(digest(out / 'model.tgl') == value['model_sha256'] == inherited['model_sha256'], 'model changed')
    require(value['binary_sha256'] == {name: digest(out / 'native' / name) for name in BINARIES}, 'binary changed')
    require(len({value['binary_sha256'][name] for name in BINARIES[:3]}) == 3,
            'research, fake and sentinel binaries coincide')
    records = [json.loads((out / f'build-{i}.json').read_text()) for i in range(4)]
    require(all(record['returncode'] == 0 for record in records) and
            '100% tests passed, 0 tests failed out of 16' in records[2]['stdout'], 'preparation suites differ')
    require(value['resets'] == inherited['resets'] ==
            [json.loads(line) for line in records[3]['stdout'].splitlines()], 'initial world fixtures changed')
    return value


def prepare(out):
    inherited = origin()
    require(not out.exists() and not out.is_symlink(), 'fresh productive preparation required')
    out.mkdir()
    try:
        shutil.copytree(ORIGIN / 'source', out / 'source')
        shutil.copy2(ORIGIN / 'model.tgl', out / 'model.tgl')
        for name, source in transforms().items():
            (out / 'source' / name).write_text(source)
        commands = [
            ['cmake', '-S', out / 'source/maintenance-fixture', '-B', out / 'native', '-G', 'Ninja'],
            ['cmake', '--build', out / 'native', '--parallel', '2'],
            ['ctest', '--test-dir', out / 'native', '--output-on-failure'],
            [out / 'native/maintenance-conditions-test', '--resets']]
        env = os.environ | {'PYTHONPATH': os.pathsep.join(map(str, (ROOT / 'sim', ROOT / 'scripts/container'))),
                            'PYTHONDONTWRITEBYTECODE': '1'}
        for index, args in enumerate(commands):
            child = subprocess.run(list(map(str, args)), env=env, capture_output=True, text=True, timeout=180)
            write_json(out / f'build-{index}.json', dict(args=list(map(str, args)), returncode=child.returncode,
                stdout=child.stdout, stderr=child.stderr))
            require(child.returncode == 0, child.stdout[-10000:] + child.stderr[-10000:])
        require(origin() == inherited, 'frozen preparation changed')
        write_json(out / 'build.json', dict(schema='garden-productive-preparation-v1', research_calls=0,
            origin_sha256=ORIGIN_SHA, source_sha256=pins(), staged_sha256=previous.inventory(out),
            model_sha256=digest(out / 'model.tgl'),
            binary_sha256={name: digest(out / 'native' / name) for name in BINARIES}, resets=inherited['resets']))
        verify(out)
    except BaseException as error:
        write_json(out / 'failure.json', dict(error=str(error), research_calls=0))
        raise
    print('Productive policy prepared: sixteen native suites and unchanged reset fixtures passed; no research replay.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    prepare(parser.parse_args().out.resolve())
