#!/usr/bin/env python3
"""Bounded 60-call collector; day-384 compatibility gates every extended replay."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zlib

import garden_landing_competitive_renewal as analysis
from garden_experiments import digest, source_files, snapshot_sources, write_json
from garden_gallery import contact_sheet, rgb565be_to_rgb888, write_png
from garden_landing_energy_audit import archived_sources
from garden_landing_founders import write_gzip
from garden_resources import require

ROOT = analysis.ROOT
ORIGIN_MANIFEST = '245c2f70f8876d4aa9f30e6734215c423fd0a362655444ebda193930bd9de5dd'


def sources_now():
    # Archive build/analysis inputs, not half a gigabyte of historical results.
    prefixes = ('src/', 'sim/', 'scripts/', 'docker/', 'boards/', 'dts/')
    explicit = {'Makefile', 'CMakeLists.txt', 'compose.yaml', '.gitignore', '.clang-format',
                analysis.PROTOCOL, analysis.INPUT}
    return {p: sha for p, sha in source_files().items() if p.startswith(prefixes) or p in explicit}


def runtime(sources):
    # Standalone *_test.c executables are retained in the snapshot but are not
    # linked into the replay executable. One old cursor fixture was reformatted.
    return {p: sha for p, sha in sources.items() if p.startswith(('src/', 'sim/')) and
            p.endswith(('.c', '.h')) and not p.endswith('_test.c')}


def check_runtime(sources, cli_bytes):
    old = runtime(analysis.prior()['source_sha256'])
    new = runtime(sources)
    require({p for p in old.keys() | new.keys() if old.get(p) != new.get(p)} == {'sim/garden_landing_cli.c'},
            'runtime change beyond host CLI bound')
    restored = cli_bytes.replace(b'(512U * TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS)',
                                 b'(384U * TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS)')
    restored = restored.replace(b'0..1966080 logic ticks (512 Garden days)',
                                 b'0..1474560 logic ticks (384 Garden days)')
    require(hashlib.sha256(cli_bytes).hexdigest() == new['sim/garden_landing_cli.c'] and
            hashlib.sha256(restored).hexdigest() == old['sim/garden_landing_cli.c'],
            'host CLI changed beyond limit/help')


def safe_artifact(root, name):
    p = Path(name)
    require(not p.is_absolute() and '..' not in p.parts and str(p) == name, 'unsafe artifact path')
    path = root / p
    require(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()) and path.is_file(),
            'missing or escaped artifact')
    return path


def frame_bytes(path, result):
    raw = path.read_bytes()
    require(len(raw) == 115200 and f'{zlib.crc32(raw):08x}' == result['framebuffer_crc32'], 'frame CRC/size differs')
    return raw


def call(out, value, phase, arm, key):
    directory = f'{phase}/{arm}/{key}'
    dest = out / directory
    (dest / 'frames').mkdir(parents=True)
    shutil.copy2(out / 'model.tgl', dest / 'model.tgl')
    args = analysis.arguments(key, arm, phase)
    write_json(dest / 'started.json', dict(phase=phase, arm=arm, key=key, args=args))
    process = subprocess.run([str(out / 'bin/garden-landing'), *args], cwd=dest,
                             capture_output=True, text=True, timeout=900)
    write_json(dest / 'process.json', dict(returncode=process.returncode, stderr=process.stderr,
                                          stdout=process.stdout))
    require(process.returncode == 0 and not process.stderr, 'native replay failed or emitted diagnostics')
    result = json.loads(process.stdout)
    write_json(dest / 'result.json', result)
    analysis.check_result(result, key, arm, phase)
    frame = None
    if phase != 'plain':
        path = dest / 'frames/end.raw'
        raw = frame_bytes(path, result)
        frame = dict(path=str(path.relative_to(out)), sha256=digest(path))
        write_png(dest / 'frames/end.png', 240, 240, rgb565be_to_rgb888(raw))
        if phase == 'anchor':
            require(frame['sha256'] == analysis.prior()['runs'][arm][key]['frame']['sha256'], 'anchor pixels differ')
    else:
        require(result['framebuffer_crc32'] is None and not any((dest / 'frames').iterdir()),
                'capture-free replay wrote a frame')
    if phase == 'endpoint':
        middle = value['runs']['middle'][arm][key]['result']
        require(analysis.previous.sweep.prefix(result, middle['tick']) ==
                (middle['lineages'], middle['seeds']), 'day-448 prefix changed')
    if phase in ('repeat', 'plain'):
        reference = value['runs']['endpoint'][arm][key]
        expected = dict(reference['result'])
        if phase == 'plain':
            expected['framebuffer_crc32'] = None
        require(result == expected and (phase == 'plain' or frame['sha256'] == reference['frame']['sha256']),
                'repeat/capture dependence')
    run = dict(directory=directory, args=args, result=result, frame=frame)
    write_json(dest / 'run.json', run)
    print(f'{directory}: verified day {result["tick"] // analysis.DAY}; living {result["living"]}', flush=True)
    return arm, key, run


def groups(value):
    return [[dict(id=f'{phase}/{arm}/{key}', framebuffer=value['runs'][phase][arm][key]['frame']['path'])
             for phase in ('middle', 'endpoint') for arm in analysis.ARMS] for key in analysis.PANEL]


def collect(out, output, origin, build, jobs):
    require(not out.exists() and not out.is_symlink() and not output.exists() and not output.is_symlink() and
            not output.is_relative_to(out) and out.is_relative_to(ROOT / 'artifacts') and
            output.is_relative_to(ROOT / 'artifacts'), 'fresh separate artifact paths required; no automatic resume')
    require(1 <= jobs <= 2 and shutil.disk_usage(out.parent).free >= 1024 ** 3, 'need 1 GiB free and 1..2 jobs')
    require(digest(ROOT / analysis.PROTOCOL) == analysis.PROTOCOL_SHA, 'protocol changed')
    prior = analysis.prior()
    require(digest(origin / 'manifest.json') == ORIGIN_MANIFEST, 'original manifest changed')
    manifest = json.loads((origin / 'manifest.json').read_text())['artifacts']
    require(digest(origin / 'model.tgl') == prior['model_sha256'] == manifest['model.tgl'], 'model changed')
    sources = sources_now()
    check_runtime(sources, (ROOT / 'sim/garden_landing_cli.c').read_bytes())
    settings = analysis.previous.sweep.late.settings_at(build / 'CMakeCache.txt', 'wide-cap')
    require(settings == prior['build']['settings'], 'build settings changed')
    out.mkdir()
    try:
        (out / 'bin').mkdir()
        snapshot_sources(out, sources)
        require(archived_sources(out / 'source.tar.gz') == sources, 'snapshot changed while freezing')
        for src, target in ((origin / 'model.tgl', 'model.tgl'),
                            (build / 'toy-factory-garden-landing', 'bin/garden-landing'),
                            (build / 'CMakeCache.txt', 'CMakeCache.txt'),
                            (ROOT / analysis.PROTOCOL, 'protocol.md')):
            shutil.copy2(src, out / target)
        value = dict(rule=analysis.RULE, protocol_sha256=analysis.PROTOCOL_SHA, input_sha256=analysis.INPUT_SHA,
                     origin_manifest_sha256=ORIGIN_MANIFEST, model_sha256=prior['model_sha256'],
                     panel=analysis.PANEL, native_runs=60, training_runs=0, source_sha256=sources,
                     build=dict(binary=digest(out / 'bin/garden-landing'), cache=digest(out / 'CMakeCache.txt'),
                                settings=settings), runs={})
        write_json(out / 'started.json', value)
        for phase in analysis.PHASES:
            value['runs'][phase] = {a: {} for a in analysis.ARMS}
            calls = [(a, k) for k in analysis.PANEL for a in analysis.ARMS]
            with ThreadPoolExecutor(max_workers=jobs) as pool:
                for offset in range(0, len(calls), jobs):
                    require(shutil.disk_usage(out).free >= 512 * 1024 ** 2, 'low disk space; outputs retained')
                    tasks = [pool.submit(call, out, value, phase, a, k) for a, k in calls[offset:offset + jobs]]
                    for task in tasks:
                        a, k, run = task.result()
                        value['runs'][phase][a][k] = run
            write_json(out / (phase + '.json'), value['runs'][phase])
            print(f'Completed {phase}: 12/12; no retries.', flush=True)
        value['outcomes'] = {a: {k: analysis.analyze(value['runs']['endpoint'][a][k]['result'])
                                 for k in analysis.PANEL} for a in analysis.ARMS}
        value['decision'] = analysis.decision(value['outcomes'])
        value['gallery'] = contact_sheet(out, groups(value))
        value['gallery']['sha256'] = digest(out / 'contact-sheet.png')
        require(sources_now() == sources, 'sources changed during collection')
        require(digest(out / 'model.tgl') == value['model_sha256'] and
                digest(out / 'bin/garden-landing') == value['build']['binary'] and
                digest(out / 'CMakeCache.txt') == value['build']['cache'], 'frozen inputs changed')
        value['receipt_sha256'] = analysis.fingerprint(value)
        analysis.check_capture(value)
        write_json(out / 'capture.json', value)
        write_json(out / 'manifest.json', dict(rule=analysis.RULE, artifacts={str(p.relative_to(out)): digest(p)
                   for p in sorted(out.rglob('*')) if p.is_file()}))
        verify_bundle(out, value)
        write_gzip(output, value)
    except Exception as error:
        write_json(out / 'failure.json', dict(error=str(error), automatic_retry=False))
        raise
    return value


def verify_bundle(root, value):
    """Offline byte/derived-image verification. Never executes a saved binary."""
    analysis.check_capture(value)
    manifest = json.loads((root / 'manifest.json').read_text())
    require(manifest['rule'] == analysis.RULE and
            set(manifest['artifacts']) == {str(p.relative_to(root)) for p in root.rglob('*')
                if p.is_file() and p != root / 'manifest.json'}, 'bundle inventory differs')
    for name, sha in manifest['artifacts'].items():
        require(digest(safe_artifact(root, name)) == sha, 'artifact changed: ' + name)
    require(json.loads((root / 'capture.json').read_text()) == value and
            archived_sources(root / 'source.tar.gz') == value['source_sha256'], 'capture/snapshot differs')
    for name, expected in (('protocol.md', analysis.PROTOCOL_SHA), ('model.tgl', value['model_sha256']),
                           ('bin/garden-landing', value['build']['binary']), ('CMakeCache.txt', value['build']['cache'])):
        require(digest(root / name) == expected, 'frozen input differs: ' + name)
    import tarfile
    with tarfile.open(root / 'source.tar.gz', 'r:gz') as archive:
        with archive.extractfile('sim/garden_landing_cli.c') as stream:
            check_runtime(value['source_sha256'], stream.read())
    require(value['source_sha256'][analysis.PROTOCOL] == analysis.PROTOCOL_SHA and
            value['source_sha256'][analysis.INPUT] == analysis.INPUT_SHA, 'snapshot protocol/input differs')
    for phase in analysis.PHASES:
        require(json.loads((root / (phase + '.json')).read_text()) == value['runs'][phase], 'phase receipt differs')
        for arm in analysis.ARMS:
            for key, run in value['runs'][phase][arm].items():
                dest = root / run['directory']
                require(json.loads((dest / 'run.json').read_text()) == run and
                        json.loads((dest / 'result.json').read_text()) == run['result'] and
                        digest(dest / 'model.tgl') == value['model_sha256'], 'run receipt differs')
                process = json.loads((dest / 'process.json').read_text())
                require(process['returncode'] == 0 and not process['stderr'] and
                        json.loads(process['stdout']) == run['result'], 'process receipt differs')
                if run['frame']:
                    path = safe_artifact(root, run['frame']['path'])
                    require(digest(path) == run['frame']['sha256'], 'frame hash differs')
                    frame_bytes(path, run['result'])
    with tempfile.TemporaryDirectory(prefix='competitive-renewal-images-') as temp:
        temporary = Path(temp)
        frames = groups(value)
        for row in frames:
            for frame in row:
                raw_path = root / frame['framebuffer']
                png = temporary / 'frame.png'
                write_png(png, 240, 240, rgb565be_to_rgb888(raw_path.read_bytes()))
                require(digest(png) == digest(raw_path.with_suffix('.png')), 'PNG does not match framebuffer')
                frame['framebuffer'] = str(raw_path)
        gallery = contact_sheet(temporary, frames)
        gallery['sha256'] = digest(temporary / 'contact-sheet.png')
        require(gallery == value['gallery'] and digest(root / 'contact-sheet.png') == gallery['sha256'],
                'gallery does not reproduce')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--origin', type=Path, default=ROOT / 'artifacts/garden-landing-seed-cursor-v1')
    parser.add_argument('--build', type=Path, default=ROOT / 'build-host-competitive-renewal')
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    value = collect(args.collect.resolve(), args.out.resolve(), args.origin.resolve(), args.build.resolve(), args.jobs)
    print(json.dumps(value['decision'], indent=2))


if __name__ == '__main__':
    main()
