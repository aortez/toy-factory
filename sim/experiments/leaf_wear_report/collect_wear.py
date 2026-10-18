#!/usr/bin/env python3
"""Package the fixed wear comparison; check using saved bytes, never a simulator."""

import argparse
import gzip
import json
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'leaf_wear'))
import run_wear as wear

SCHEMA = 'garden-leaf-family-wear-evidence-v1'
require = wear.require


def pack(source):
    summary = wear.check(source)
    require(summary == wear.read(source / 'result.json'), 'saved result differs')
    files, blobs = {}, {}
    for path in sorted(source.rglob('*')):
        require(not path.is_symlink(), 'symlink in evidence')
        if path.is_file():
            raw = path.read_bytes()
            identity = wear.sha(raw)
            files[str(path.relative_to(source))] = identity
            blobs[identity] = raw.hex()
    return dict(schema=SCHEMA, files=files, blobs=blobs, summary=summary)


def verify(bundle):
    require(bundle['schema'] == SCHEMA and set(bundle['files'].values()) == set(bundle['blobs']),
            'wrong schema or unbound blob')
    total = 0
    with tempfile.TemporaryDirectory(prefix='leaf-wear-evidence-') as temporary:
        root = Path(temporary)
        for name, identity in bundle['files'].items():
            relative = Path(name)
            require(name == str(relative) and not relative.is_absolute() and relative.parts and
                    '..' not in relative.parts, 'unsafe evidence path')
            raw = bytes.fromhex(bundle['blobs'][identity])
            total += len(raw)
            require(total < wear.MAX_BYTES and wear.sha(raw) == identity, 'archive size/hash differs')
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(raw)
        result = wear.check(root)
        require(result == bundle['summary'] == wear.read(root / 'result.json'), 'summary differs')
        return result


def short(summary):
    return dict(native_calls=summary['native_calls'], exact_anchors=summary['exact_anchors'],
        exact_serial_capture_checks=summary['exact_serial_capture_checks'],
        models={name: dict(keys={panel: value['key'] for panel, value in rows['panels'].items()},
            founders_alive_day1=rows['founder_day1_survivors'],
            founders_alive_day32=rows['founder_day32_survivors'],
            families_with_descendants=rows['families_with_descendants'],
            roles_with_renewal=rows['panels']['combined']['roles_with_renewal'])
            for name, rows in summary['analysis'].items()})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--check', type=Path)
    parser.add_argument('--images', type=Path)
    args = parser.parse_args()
    if args.check:
        require(args.source is None and args.out is None and args.images is None, 'check cannot collect')
        result = verify(json.loads(gzip.decompress(args.check.read_bytes())))
    else:
        require(args.source is not None and args.out is not None and not args.out.exists(),
                'source and fresh output required')
        if args.images:
            require(args.images.is_dir() and all(not (args.images / f'leaf-family-wear-{seed}.png').exists()
                    for seed in wear.SEEDS), 'existing image directory with fresh image names required')
        bundle = pack(args.source.resolve())
        result = verify(bundle)
        raw = (json.dumps(bundle, sort_keys=True, separators=(',', ':')) + '\n').encode()
        with args.out.open('xb') as stream:
            stream.write(gzip.compress(raw, mtime=0))
        if args.images:
            for seed in wear.SEEDS:
                source = args.source / 'gallery' / seed / 'contact-sheet.png'
                target = args.images / f'leaf-family-wear-{seed}.png'
                shutil.copy2(source, target)
                require(wear.digest(source) == wear.digest(target), 'copied image differs')
    print(json.dumps(short(result), indent=2))
