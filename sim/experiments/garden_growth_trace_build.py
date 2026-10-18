#!/usr/bin/env python3
"""Build a passive, shorter-horizon diagnostic from the saved reserve kernel.

Only command/recorder/test plumbing changes in the copied archive. Never edit
the saved comparison or kernel, and never launch research runs from preparation.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ORIGIN = ROOT / 'artifacts/garden-maintenance-reserve-tools-v3'
ORIGIN_SHA = 'b70d788f4ed85f5313853cc5e2ee397e7dd29b17f0356ebb41317ce536488658'
OVERLAY = ('garden_growth_trace.h', 'garden_growth_trace.c', 'garden_growth_trace_test.c',
           'garden_growth_trace.cmake')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write('\n')


def replace(text, old, new, count=1):
    require(text.count(old) == count, 'unexpected overlay anchor: ' + repr(old))
    return text.replace(old, new)


def command(text):
    text = replace(text, '#include "garden_maintenance_command.h"',
                   '#include "garden_maintenance_command.h"\n#include "garden_growth_trace.h"')
    text = replace(text, '\tDAY304_FRAME,\n\tEND_FRAME,', '\tGROWTH,')
    text = replace(text, '"day304.raw",\n\t\t\t\t\t   "end.raw",', '"growth.jsonl",')
    text = replace(text, '{0U, 737280U, 1167360U, TOY_FACTORY_MAINTENANCE_RUN_STOP}', '{0U, 737280U}')
    text = replace(text, 'static struct toy_factory_maintenance_daily daily;',
                   'static struct toy_factory_maintenance_daily daily;\n'
                   'static struct toy_factory_growth_trace growth_trace;')
    text = text.replace('TOY_FACTORY_MAINTENANCE_RUN_STOP', 'TOY_FACTORY_GROWTH_TRACE_STOP')
    text = text.replace('2334720', '737280')
    text = replace(text, 'index >= 4U', 'index >= 2U')
    text = replace(text, 'captures < 4U', 'captures < 2U')
    text = replace(text, 'captures == 4U', 'captures == 2U')
    text = replace(text, '\\"captures\\":4', '\\"captures\\":2', 2)
    # The public phase switch now controls only growth tracing. Both phases keep
    # the exact same resource recorder to compare every complete daily row.
    text = replace(text, 'if (err == 0 && config->trace)', 'if (err == 0)', 2)
    text = replace(text, 'if (ecology && config->trace)', 'if (ecology)', 2)
    text = replace(text, 'if (err == 0) {\n\t\tfprintf(outputs[SNAPSHOTS].stream,',
        'if (err == 0 && config->trace) {\n'
        '\t\terr = toy_factory_maintenance_output_open(&outputs[GROWTH], directory,\n'
        '\t\t\toutput_names[GROWTH], TOY_FACTORY_GROWTH_TRACE_BYTES);\n'
        '\t\tif (err == 0) {\n'
        '\t\t\terr = toy_factory_growth_trace_init(&growth_trace, outputs[GROWTH].stream,\n'
        '\t\t\t\t&run.growth.root_choice);\n\t\t}\n\t}\n'
        '\tif (err == 0) {\n\t\tfprintf(outputs[SNAPSHOTS].stream,')
    text = replace(text, '\t\terr = toy_factory_maintenance_run_step(&run, &deaths, &seeds, &resources, NULL);',
        '\t\tconst struct toy_factory_garden_growth_observer observer = {\n'
        '\t\t\t.observe = toy_factory_growth_trace_observe, .context = &growth_trace,\n'
        '\t\t\t.reproduction = &growth_trace.reproduction};\n'
        '\t\tif (ecology && config->trace) {\n'
        '\t\t\terr = toy_factory_growth_trace_begin(&growth_trace, &before);\n\t\t}\n'
        '\t\tif (err == 0) {\n'
        '\t\t\terr = toy_factory_maintenance_run_step(&run, &deaths, &seeds, &resources,\n'
        '\t\t\t\tecology && config->trace ? &observer : NULL);\n\t\t}\n'
        '\t\tif (err == 0 && ecology && config->trace) {\n'
        '\t\t\terr = toy_factory_growth_trace_publish(&growth_trace, &run.growth.base.world);\n\t\t}')
    text = replace(text, 'if (err == 0) {\n\t\terr = toy_factory_maintenance_daily_finish(&daily);\n\t}',
        'if (err == 0) {\n\t\terr = toy_factory_maintenance_daily_finish(&daily);\n\t}\n'
        '\tif (err == 0 && config->trace) {\n'
        '\t\terr = toy_factory_growth_trace_finish(&growth_trace);\n\t}')
    text = replace(text, 'if (config == NULL)',
        'if (config == NULL || config->seed != UINT32_C(0x970788ba) ||\n'
        '\t    config->leaf_mode != TOY_FACTORY_MAINTENANCE_RESERVE)')
    return text


def transforms():
    base = ORIGIN / 'source/maintenance-fixture'
    read = lambda name: (base / name).read_text()
    daily = replace(read('garden_maintenance_daily.c'), '2334720', '737280')
    daily = replace(daily, '608U', '192U', 2)
    header = replace(read('garden_maintenance_daily.h'), '2334720U', '737280U')
    header = replace(header, '609U', '193U')
    header = replace(header, 'day 608', 'day 192')
    test = replace(read('garden_maintenance_daily_test.c'), '609U', '193U')
    test = replace(test, '2334735U', '737295U')
    cmake = read('CMakeLists.txt') + '\ninclude(${CMAKE_CURRENT_LIST_DIR}/garden_growth_trace.cmake)\n'
    return {'garden_maintenance_command.c': command(read('garden_maintenance_command.c')),
            'garden_maintenance_daily.c': daily, 'garden_maintenance_daily.h': header,
            'garden_maintenance_daily_test.c': test, 'CMakeLists.txt': cmake}


def check_origin():
    require(digest(ORIGIN / 'manifest.json') == ORIGIN_SHA, 'saved preparation manifest changed')
    pins = json.loads((ORIGIN / 'manifest.json').read_text())
    require(all(digest(ORIGIN / name) == sha for name, sha in pins.items()),
            'saved preparation contents changed')
    return pins


def source_pins():
    return {name: digest(ROOT / 'sim/experiments' / name) for name in
            (*OVERLAY, 'garden_growth_trace_build.py')}


def prepare(out):
    old = check_origin()
    require(not out.exists(), 'fresh preparation path required')
    out.mkdir(parents=False)
    try:
        shutil.copytree(ORIGIN / 'source', out / 'source')
        for name, content in transforms().items():
            (out / 'source/maintenance-fixture' / name).write_text(content)
        for name in OVERLAY:
            shutil.copy2(ROOT / 'sim/experiments' / name, out / 'source/maintenance-fixture' / name)
        shutil.copy2(ORIGIN / 'model.tgl', out / 'model.tgl')
        commands = [
            ['cmake', '-S', out / 'source/maintenance-fixture', '-B', out / 'native', '-G', 'Ninja'],
            ['cmake', '--build', out / 'native', '--parallel', '2'],
            ['ctest', '--test-dir', out / 'native', '--output-on-failure', '-R',
             '^(growth-trace-native|maintenance-(step|daily|bridge|state|run|reserve)-native)$']]
        for index, args in enumerate(commands):
            child = subprocess.run(list(map(str, args)), capture_output=True, text=True, timeout=180)
            write_json(out / f'build-{index}.json', dict(args=list(map(str, args)),
                returncode=child.returncode, stdout=child.stdout, stderr=child.stderr))
            require(child.returncode == 0, child.stdout[-8000:] + child.stderr[-8000:])
        require(check_origin() == old, 'original changed during preparation')
        write_json(out / 'build.json', dict(schema='garden-growth-trace-build-v1', research_calls=0,
            origin_sha256=ORIGIN_SHA, source_sha256=source_pins(),
            staged_sha256={str(p.relative_to(out / 'source')): digest(p)
                          for p in sorted((out / 'source').rglob('*')) if p.is_file()},
            binary_sha256=digest(out / 'native/maintenance-command'),
            model_sha256=digest(out / 'model.tgl')))
    except BaseException as error:
        write_json(out / 'failure.json', dict(error=str(error), research_calls=0))
        raise
    print('Growth-trace preparation and focused fixtures passed: ' + str(out), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    prepare(parser.parse_args().out.resolve())
