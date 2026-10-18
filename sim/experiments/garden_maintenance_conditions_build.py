#!/usr/bin/env python3
"""Prepare explicit fresh-condition command inputs on the unchanged reserve core."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import garden_growth_trace_build as base

ROOT, ORIGIN, ORIGIN_SHA = base.ROOT, base.ORIGIN, base.ORIGIN_SHA
require, digest, write_json = base.require, base.digest, base.write_json
PROTOCOL = ROOT / 'benchmarks/garden-seasons/landing-renewal-maintenance-conditions-protocol.md'
FILES = ('garden_maintenance_conditions.c', 'garden_maintenance_conditions.h',
         'garden_maintenance_conditions_test.c', 'garden_maintenance_conditions.cmake',
         'test_garden_maintenance_conditions_native.py')
BINARIES = ('maintenance-command', 'maintenance-command-fake', 'maintenance-command-preflight',
            'maintenance-conditions-test')


def conditional_block(text, first, after, replacement):
    require(text.count(first) == text.count(after) == 1, 'unexpected metadata block')
    start, end = text.index(first), text.index(after)
    old = text[start:end]
    require(start < end and old.endswith('\n'), 'invalid metadata boundaries')
    wrapped = ('\t\tif (config->condition_format) {\n\t\t\t' + replacement + '\n\t\t} else {\n' +
               ''.join('\t' + line for line in old.splitlines(keepends=True)) + '\t\t}\n')
    return text[:start] + wrapped + text[end:]


def transforms():
    fixture = ORIGIN / 'source/maintenance-fixture'
    read = lambda name: (fixture / name).read_text()
    header = base.replace(read('garden_maintenance_command.h'), '\tbool trace;\n',
        '\tbool trace;\n\tuint8_t scenario_index;\n\tbool condition_format;\n')
    config = base.replace(read('garden_maintenance_command_config.c'),
        '#include "garden_maintenance_command.h"', '#include "garden_maintenance_conditions.h"')
    config = base.replace(config, 'int toy_factory_maintenance_command_parse(',
        'int toy_factory_maintenance_legacy_parse(')
    command = base.replace(read('garden_maintenance_command.c'),
        '#include "garden_maintenance_command.h"', '#include "garden_maintenance_conditions.h"')
    command = base.replace(command, '&toy_factory_garden_rainfed_scenarios[0]',
        '&toy_factory_garden_rainfed_scenarios[config->scenario_index]')
    command = base.replace(command, 'if (config == NULL)',
        'if (!toy_factory_maintenance_conditions_valid(config))')
    command = conditional_block(command, '\t\tfprintf(outputs[SNAPSHOTS].stream,',
        '\t\terr = capture(directory, 0U, &run);',
        'err = toy_factory_maintenance_conditions_header(outputs[SNAPSHOTS].stream, config);')
    command = base.replace(command, '\t\terr = capture(directory, 0U, &run);',
        '\t\tif (err == 0) {\n\t\t\terr = capture(directory, 0U, &run);\n\t\t}')
    command = conditional_block(command, '\t\tfprintf(outputs[COMPLETE].stream,',
        '\t}\n\tconst int complete_err',
        'err = toy_factory_maintenance_conditions_complete(outputs[COMPLETE].stream, config);')
    stub = read('garden_maintenance_command_stub.c')
    start = stub.index('\tassert(strcmp(scenario->name, "rainfed")')
    end = stub.index('#if defined(TOY_FACTORY_MAINTENANCE_COMMAND_FAKE)', start)
    stub = stub[:start] + ('\tassert(scenario == &toy_factory_garden_rainfed_scenarios[0] ||\n'
        '\t       scenario == &toy_factory_garden_rainfed_scenarios[1]);\n'
        '\tassert(scenario->rain_enabled && scenario->irrigation_period_ticks == 0U &&\n'
        '\t       scenario->irrigation_water == 0U);\n') + stub[end:]
    stub = base.replace(stub, '" scenario=rainfed\\n", seed);', '" scenario=%s\\n", seed, scenario->name);')
    daily = base.replace(read('garden_maintenance_daily.c'),
        '(seed != UINT32_C(0x8fad8465))))',
        '(seed != UINT32_C(0x8fad8465)) &&\n'
        '\t     (seed != UINT32_C(0x3c308d3b)) && (seed != UINT32_C(0x97806ca5))))')
    cmake = read('CMakeLists.txt') + '\ninclude(${CMAKE_CURRENT_LIST_DIR}/garden_maintenance_conditions.cmake)\n'
    edits = dict(zip(('garden_maintenance_command.h', 'garden_maintenance_command_config.c',
                     'garden_maintenance_command.c', 'garden_maintenance_command_stub.c',
                     'garden_maintenance_daily.c', 'CMakeLists.txt'),
                    (header, config, command, stub, daily, cmake), strict=True))
    for name in tuple(edits):
        if name.endswith(('.c', '.h')):
            edits[name] = subprocess.run(['clang-format', '--style=file:' + str(ROOT / '.clang-format')],
                input=edits[name], capture_output=True, text=True, check=True, timeout=30).stdout
    edits.update({name: Path(__file__).with_name(name).read_text() for name in FILES})
    return {'maintenance-fixture/' + name: value for name, value in edits.items()}


def pins():
    return {str(p.relative_to(ROOT)): digest(p) for p in
            (Path(__file__), ROOT / '.clang-format', PROTOCOL,
             *(Path(__file__).with_name(name) for name in FILES))}


def inventory(out):
    return {str(p.relative_to(out / 'source')): digest(p)
            for p in sorted((out / 'source').rglob('*')) if p.is_file()}


def verify(out):
    origin = base.check_origin()
    value = json.loads((out / 'build.json').read_text())
    require(value['schema'] == 'garden-maintenance-conditions-build-v1' and value['research_calls'] == 0 and
            value['origin_sha256'] == ORIGIN_SHA and value['source_sha256'] == pins(),
            'condition preparation identity differs')
    expected = {name.removeprefix('source/'): sha for name, sha in origin.items() if name.startswith('source/')}
    expected.update({name: hashlib.sha256(content.encode()).hexdigest() for name, content in transforms().items()})
    require(inventory(out) == value['staged_sha256'] == expected, 'unexpected source change')
    require(digest(out / 'model.tgl') == value['model_sha256'] == origin['model.tgl'], 'model changed')
    require(value['binary_sha256'] == {name: digest(out / 'native' / name) for name in BINARIES}, 'binary changed')
    require(len({value['binary_sha256'][name] for name in BINARIES[:3]}) == 3, 'fixture and research commands coincide')
    records = [json.loads((out / f'build-{i}.json').read_text()) for i in range(4)]
    require(all(r['returncode'] == 0 for r in records) and
            '100% tests passed, 0 tests failed out of 14' in records[2]['stdout'], 'condition tests failed or differ')
    resets = [json.loads(line) for line in records[3]['stdout'].splitlines()]
    require(value['resets'] == resets and len(resets) == 4, 'condition reset fixtures differ')
    return value


def prepare(out):
    original = base.check_origin()
    require(not out.exists(), 'fresh condition preparation required')
    out.mkdir()
    try:
        shutil.copytree(ORIGIN / 'source', out / 'source')
        shutil.copy2(ORIGIN / 'model.tgl', out / 'model.tgl')
        for name, content in transforms().items():
            (out / 'source' / name).write_text(content)
        commands = [
            ['cmake', '-S', out / 'source/maintenance-fixture', '-B', out / 'native', '-G', 'Ninja'],
            ['cmake', '--build', out / 'native', '--parallel', '2'],
            ['ctest', '--test-dir', out / 'native', '--output-on-failure'],
            [out / 'native/maintenance-conditions-test', '--resets']]
        env = os.environ | {'PYTHONPATH': os.pathsep.join(map(str, (ROOT / 'sim', ROOT / 'scripts/container'))),
                            'PYTHONDONTWRITEBYTECODE': '1'}
        for i, args in enumerate(commands):
            record = subprocess.run(list(map(str, args)), env=env, capture_output=True, text=True, timeout=180)
            write_json(out / f'build-{i}.json', dict(args=list(map(str, args)), returncode=record.returncode,
                stdout=record.stdout, stderr=record.stderr))
            require(record.returncode == 0, record.stdout[-10000:] + record.stderr[-10000:])
        require(base.check_origin() == original, 'saved preparation changed')
        write_json(out / 'build.json', dict(schema='garden-maintenance-conditions-build-v1', research_calls=0,
            origin_sha256=ORIGIN_SHA, source_sha256=pins(), staged_sha256=inventory(out),
            model_sha256=digest(out / 'model.tgl'), binary_sha256={name: digest(out / 'native' / name) for name in BINARIES},
            resets=[json.loads(line) for line in record.stdout.splitlines()]))
        verify(out)
    except BaseException as error:
        write_json(out / 'failure.json', dict(error=str(error), research_calls=0))
        raise
    print('Fresh-condition preparation: fourteen native suites passed; no research trajectory executed.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.out.resolve())
