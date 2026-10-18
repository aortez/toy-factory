#!/usr/bin/env python3
"""Reconstruct the frozen research sources and policies, never archived executables."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]

ARCHIVE = ROOT / 'benchmarks/garden-seasons/leaf-family-durability-results.json.gz'
ARCHIVE_SHA = '5dc495ec0e33f83c121b1c6eaa09603033bd824476e175c8a72f347ef272744f'
MODELS = ('initial', 's1-g3-c4', 's2-g3-c1')
SCHEMA = 'garden-research-runtime-v1'
DEFAULT = ROOT / 'artifacts/garden-research-runtime-v1'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def relative(name):
    path = PurePosixPath(name)
    require(name == str(path) and path.parts and not path.is_absolute() and
            '..' not in path.parts and '\\' not in name, 'unsafe archive path')
    return path


def load_archive(path=ARCHIVE):
    raw = path.read_bytes()
    require(sha(raw) == ARCHIVE_SHA, 'durability archive identity differs')
    bundle = json.loads(gzip.decompress(raw))
    # The complete archive was independently audited before this hash was
    # pinned. Authenticate its exact bytes here; do not couple the desktop
    # build to the historical scoring/serial-tool import graph.
    require(bundle['schema'] == 'garden-leaf-family-durability-evidence-v1', 'wrong archive schema')
    return bundle


def blob(bundle, name):
    relative(name)
    identity = bundle['files'][name]
    raw = bytes.fromhex(bundle['blobs'][identity])
    require(sha(raw) == identity, 'archive blob differs')
    return raw


def expected_files(bundle):
    files = {}
    for name in bundle['files']:
        relative(name)
        if name.startswith(('runtime/source/', 'runtime/modules/')):
            files[name.removeprefix('runtime/')] = blob(bundle, name)
    require('modules/leaf_replay/CMakeLists.txt' in files and
            'source/maintenance-fixture/CMakeLists.txt' in files, 'missing research runtime')
    files['model.tgl'] = blob(bundle, 'growth.tgl')
    header = ['/* Generated from the authenticated durability archive. */',
              '#ifndef TOY_FACTORY_RESEARCH_MODELS_H_', '#define TOY_FACTORY_RESEARCH_MODELS_H_',
              '#include <stdint.h>', f'#define RESEARCH_ARCHIVE_SHA "{ARCHIVE_SHA}"',
              'static const char *const research_model_names[3] = {',
              *[f'    "{name}",' for name in MODELS], '};',
              'static const uint8_t research_model_bytes[3][172] = {']
    for name in MODELS:
        raw = blob(bundle, f'models/{name}.tlf')
        require(len(raw) == 172, 'wrong repair model size')
        files[f'models/{name}.tlf'] = raw
        header.append('    {' + ','.join(f'0x{value:02x}' for value in raw) + '},')
    header.extend(['};', '#endif', ''])
    files['generated/research_models.h'] = '\n'.join(header).encode()
    plan = json.loads(blob(bundle, 'started.json'))['plan']
    selected = [call for call in plan if call['phase'] == 'anchor' or
                (call['phase'] == 'panel' and call['seed'] == '58d7d6ca' and
                 call['layout'] == 'rainfed' and call['founder'] == 1)]
    require(len(selected) == 6, 'reference roster differs')
    references = []
    for call in selected:
        label = ('anchor' if call['phase'] == 'anchor' else 'late') + '-' + call['model']
        for source, target in (('stdout.json', 'json'), ('frame.raw', 'raw')):
            files[f'references/{label}.{target}'] = blob(bundle, f"runs/{call['id']}/{source}")
        references.append(dict(label=label, **call))
    files['references.json'] = (json.dumps(references, indent=2) + '\n').encode()
    return files


def manifest(files):
    return dict(schema=SCHEMA, archive_sha256=ARCHIVE_SHA,
                files={name: sha(raw) for name, raw in sorted(files.items())})


def check(out, files):
    require(out.is_dir() and not out.is_symlink(), 'runtime must be a real directory')
    found = set()
    for path in out.rglob('*'):
        require(not path.is_symlink(), 'symlink in prepared runtime')
        if not path.is_dir():
            require(path.is_file(), 'nonregular runtime entry')
            found.add(path.relative_to(out).as_posix())
    require(found == set(files) | {'manifest.json'}, 'runtime inventory differs')
    require(json.loads((out / 'manifest.json').read_bytes()) == manifest(files), 'runtime manifest differs')
    for name, raw in files.items():
        require((out / name).read_bytes() == raw, 'prepared runtime file differs: ' + name)


def prepare(out, bundle):
    files = expected_files(bundle)
    if out.exists() or out.is_symlink():
        check(out, files)
        return
    out.mkdir(parents=True)
    # Only a complete preparation receives a manifest. Failed partial trees are
    # retained and refused on reuse; never repair or overwrite an existing tree.
    for name, raw in files.items():
        path = out / relative(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    with (out / 'manifest.json').open('x') as stream:
        json.dump(manifest(files), stream, indent=2)
        stream.write('\n')
    check(out, files)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=DEFAULT)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    saved = load_archive()
    if args.check:
        check(args.out, expected_files(saved))
    else:
        prepare(args.out, saved)
    print(f'Verified research runtime: {args.out}; no archived binaries extracted or executed.')
