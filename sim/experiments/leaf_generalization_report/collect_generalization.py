#!/usr/bin/env python3
"""Archive and recheck fixed-policy weather evidence without native executables."""

import argparse
import gzip
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'leaf_generalization'))
import run_generalization as experiment

SCHEMA = 'garden-leaf-family-generalization-evidence-v1'
require = experiment.require


def pack(source):
    summary = experiment.check(source)
    require(summary == experiment.read(source / 'result.json'), 'saved result differs')
    files, blobs = {}, {}
    for path in sorted(source.rglob('*')):
        require(not path.is_symlink(), 'symlink in evidence')
        if path.is_file():
            raw = path.read_bytes()
            identity = experiment.sha(raw)
            files[str(path.relative_to(source))] = identity
            blobs[identity] = raw.hex()
    return dict(schema=SCHEMA, files=files, blobs=blobs, summary=summary)


def verify_images(root, images):
    for seed in experiment.SEEDS:
        source = root / 'gallery' / seed / 'contact-sheet.png'
        target = images / f'leaf-family-generalization-{seed}.png'
        require(source.read_bytes() == target.read_bytes(), 'published gallery differs')


def verify(bundle, images=None):
    require(bundle['schema'] == SCHEMA and set(bundle['files'].values()) == set(bundle['blobs']),
            'wrong schema or unbound blob')
    total = 0
    with tempfile.TemporaryDirectory(prefix='leaf-generalization-evidence-') as temporary:
        root = Path(temporary)
        for name, identity in bundle['files'].items():
            relative = Path(name)
            require(name == str(relative) and not relative.is_absolute() and relative.parts and
                    '..' not in relative.parts, 'unsafe evidence path')
            encoded = bundle['blobs'][identity]
            total += len(encoded) // 2
            require(total < experiment.MAX_BYTES, 'archive size differs')
            raw = bytes.fromhex(encoded)
            require(experiment.sha(raw) == identity, 'archive hash differs')
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(raw)
        result = experiment.check(root)
        require(result == bundle['summary'] == experiment.read(root / 'result.json'), 'derived summary differs')
        if images is not None:
            verify_images(root, images)
        return result


def images(source, target):
    require(target.is_dir(), 'existing image directory required')
    destinations = {seed: target / f'leaf-family-generalization-{seed}.png' for seed in experiment.SEEDS}
    require(all(not p.exists() and not p.is_symlink() for p in destinations.values()), 'fresh images required')
    for seed, destination in destinations.items():
        with destination.open('xb') as stream:
            stream.write((source / 'gallery' / seed / 'contact-sheet.png').read_bytes())
    verify_images(source, target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--check', type=Path)
    parser.add_argument('--images', type=Path)
    args = parser.parse_args()
    if args.check:
        require(args.source is None and args.out is None, 'check cannot collect')
        result = verify(json.loads(gzip.decompress(args.check.read_bytes())), args.images)
    else:
        require(args.source is not None and args.out is not None and not args.out.exists() and
                not args.out.is_symlink(), 'source and fresh output required')
        bundle = pack(args.source.resolve())
        result = verify(bundle)
        raw = (json.dumps(bundle, sort_keys=True, separators=(',', ':')) + '\n').encode()
        with args.out.open('xb') as stream:
            stream.write(gzip.compress(raw, mtime=0))
        if args.images:
            images(args.source.resolve(), args.images.resolve())
    print(json.dumps(experiment.short(result), indent=2))
