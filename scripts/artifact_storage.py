#!/usr/bin/env python3
"""Plan, verify and remove redundant raw traces; restore them from retained gzip files."""

import argparse
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

VERSION = 'artifact-storage-v1'
KEEP = ('garden-landing-patch-sweep-v1', 'garden-landing-patch-confirmation-v1')
CHUNK = 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def hashed(stream, destination=None):
    digest, size = hashlib.sha256(), 0
    while data := stream.read(CHUNK):
        digest.update(data)
        size += len(data)
        if destination is not None:
            destination.write(data)
    return digest.hexdigest(), size


def digest(path):
    with path.open('rb') as stream:
        return hashed(stream)[0]


def safe_path(root, relative, missing=False):
    path = Path(relative)
    require(not path.is_absolute() and path.parts and all(p not in ('.', '..') for p in path.parts),
            'unsafe relative path: ' + str(relative))
    result = root
    for part in path.parts:
        result /= part
        require(not result.is_symlink(), 'symlink refused: ' + str(result))
    require(result.resolve().is_relative_to(root), 'path outside artifact root')
    if not (missing and not result.exists()):
        require(stat.S_ISREG(result.stat().st_mode), 'not a regular file: ' + str(result))
    return result


def identity(path):
    info = path.stat()
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def durable_json(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(path.parent)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def plan(root, keep):
    require(root.is_dir() and root.name == 'artifacts', 'expected an artifacts directory')
    records = []
    for bundle in sorted(root.iterdir()):
        if not bundle.name.startswith('garden-landing-') or bundle.name in keep or not bundle.is_dir():
            continue
        require(not bundle.is_symlink(), 'symlink bundle refused')
        manifests = []
        for path in sorted(bundle.glob('*manifest*.json')):
            safe_path(root, str(path.relative_to(root)))
            value = json.loads(path.read_text())
            if isinstance(value.get('artifacts'), dict):
                manifests.append((path, digest(path), value['artifacts']))
        for raw in sorted(bundle.rglob('*.jsonl')):
            packed = raw.with_suffix(raw.suffix + '.gz')
            if not packed.exists():
                continue
            a, b = str(raw.relative_to(bundle)), str(packed.relative_to(bundle))
            matches = [(p, h, v) for p, h, v in manifests if a in v and b in v]
            if not matches:
                continue
            safe_path(root, str(raw.relative_to(root)))
            safe_path(root, str(packed.relative_to(root)))
            require(raw.stat().st_nlink == 1, 'hardlinked raw trace refused')
            p, h, v = matches[0]
            require(all((other[a], other[b]) == (v[a], v[b]) for _, _, other in matches),
                    'conflicting manifest entries')
            records.append(dict(raw=str(raw.relative_to(root)), gzip=str(packed.relative_to(root)),
                                raw_sha256=v[a], gzip_sha256=v[b], size=raw.stat().st_size,
                                allocated=raw.stat().st_blocks * 512,
                                manifest=str(p.relative_to(root)), manifest_sha256=h))
    return dict(version=VERSION, root=str(root), keep=sorted(keep), files=records,
                raw_bytes=sum(r['size'] for r in records), allocated_bytes=sum(r['allocated'] for r in records))


def load_plan(path):
    value = json.loads(path.read_text())
    root = Path(value['root'])
    require(value['version'] == VERSION and root.is_absolute() and root.resolve() == root and
            root.is_dir() and root.name == 'artifacts', 'invalid plan root/version')
    seen = set()
    for record in value['files']:
        raw = Path(record['raw'])
        require(len(raw.parts) >= 2 and raw.parts[0].startswith('garden-landing-') and
                raw.parts[0] not in {*value['keep'], *KEEP} and raw.suffix == '.jsonl' and
                record['gzip'] == record['raw'] + '.gz' and record['raw'] not in seen and
                Path(record['manifest']).parts[0] == raw.parts[0], 'invalid or protected target')
        seen.add(record['raw'])
        for field in ('raw', 'gzip', 'manifest'):
            safe_path(root, record[field], missing=field == 'raw')
    require(value['raw_bytes'] == sum(r['size'] for r in value['files']), 'invalid planned byte count')
    return value, root


def verify(root, record):
    raw = safe_path(root, record['raw'], missing=True)
    packed = safe_path(root, record['gzip'])
    manifest = safe_path(root, record['manifest'])
    before = {p: identity(p) for p in (raw, packed, manifest) if p.exists()}
    require(digest(manifest) == record['manifest_sha256'], 'manifest changed')
    entries = json.loads(manifest.read_text())['artifacts']
    bundle = root / Path(record['raw']).parts[0]
    require(entries[str(raw.relative_to(bundle))] == record['raw_sha256'] and
            entries[str(packed.relative_to(bundle))] == record['gzip_sha256'], 'manifest does not authenticate pair')
    require(digest(packed) == record['gzip_sha256'], 'compressed file changed: ' + record['gzip'])
    with gzip.open(packed, 'rb') as stream:
        restored = hashed(stream)
    require(restored == (record['raw_sha256'], record['size']), 'decompressed bytes differ: ' + record['raw'])
    require(raw.exists() == (raw in before), 'raw path appeared/disappeared during verification')
    if raw.exists():
        require(raw.stat().st_nlink == 1 and digest(raw) == record['raw_sha256'] and
                raw.stat().st_size == record['size'], 'raw file changed: ' + record['raw'])
    for p, stamp in before.items():
        require(identity(p) == stamp, 'file changed during verification: ' + str(p))
    return raw, packed, before


def apply(plan_path):
    value, root = load_plan(plan_path)
    removed, saved, already_absent = 0, 0, 0
    # Persist the complete restoration index before any unlink. Each verified intent is also
    # flushed before deletion, so an interrupted run remains recoverable from this same plan.
    journal_path = plan_path.with_suffix('.journal.jsonl')
    with plan_path.open('r') as lock, journal_path.open('a') as journal:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for i, record in enumerate(value['files'], 1):
            raw, packed, before = verify(root, record)
            if raw not in before:
                require(not raw.exists(), 'raw path appeared after verification')
                already_absent += 1
                continue
            journal.write(json.dumps(dict(action='verified-unlink', record=record)) + '\n')
            journal.flush()
            os.fsync(journal.fileno())
            sync_directory(journal_path.parent)
            for p, stamp in before.items():
                safe_path(root, str(p.relative_to(root)))
                require(identity(p) == stamp, 'file changed before unlink')
            raw.unlink()
            sync_directory(raw.parent)
            removed += 1
            saved += record['allocated']
            print(f'{i}/{len(value["files"])} removed {record["raw"]}; reclaimed {saved / 2**30:.2f} GiB', flush=True)
        summary = dict(action='complete', removed=removed, already_absent=already_absent,
                       allocated_bytes_reclaimed=saved, plan_sha256=digest(plan_path))
        journal.write(json.dumps(summary) + '\n')
        journal.flush()
        os.fsync(journal.fileno())
    return summary


def restore(plan_path, bundle=None, selected=None):
    value, root = load_plan(plan_path)
    records = [r for r in value['files'] if (bundle and Path(r['raw']).parts[0] == bundle) or r['raw'] == selected]
    require(records, 'no matching files in restoration index')
    count = 0
    with plan_path.open('r') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for record in records:
            raw, packed, before = verify(root, record)
            if raw.exists():
                continue
            fd, temporary = tempfile.mkstemp(prefix='.restore-', dir=raw.parent)
            temporary = Path(temporary)
            try:
                with os.fdopen(fd, 'wb') as output, gzip.open(packed, 'rb') as stream:
                    require(hashed(stream, output) == (record['raw_sha256'], record['size']), 'restore bytes differ')
                    output.flush()
                    os.fsync(output.fileno())
                for p, stamp in before.items():
                    safe_path(root, str(p.relative_to(root)))
                    require(identity(p) == stamp, 'source changed during restoration')
                safe_path(root, record['raw'], missing=True)
                os.link(temporary, raw)  # Exclusive: never overwrite a path another process created.
                count += 1
            finally:
                temporary.unlink()
                sync_directory(raw.parent)
            print('restored ' + record['raw'], flush=True)
    return dict(restored=count)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('plan', help='read-only inventory; write an explicit restoration index')
    p.add_argument('--root', type=Path, default=Path('artifacts'))
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--keep', action='append', default=list(KEEP))
    p = commands.add_parser('apply', help='verify each indexed pair before deleting only its redundant raw file')
    p.add_argument('index', type=Path)
    p = commands.add_parser('restore', help='restore one old bundle or file without overwriting anything')
    p.add_argument('index', type=Path)
    which = p.add_mutually_exclusive_group(required=True)
    which.add_argument('--bundle')
    which.add_argument('--file', dest='selected')
    args = parser.parse_args()
    if args.command == 'plan':
        value = plan(args.root.resolve(), args.keep)
        durable_json(args.out, value)
        print(json.dumps(dict(files=len(value['files']), raw_gib=value['raw_bytes'] / 2**30,
                              allocated_gib=value['allocated_bytes'] / 2**30, index=str(args.out))))
    else:
        print(json.dumps(apply(args.index) if args.command == 'apply' else restore(args.index, args.bundle, args.selected)))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, EOFError) as error:
        sys.exit(str(error))
