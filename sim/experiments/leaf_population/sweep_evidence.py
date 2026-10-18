#!/usr/bin/env python3
"""Verify and package the threshold sweep offline, without replaying any native code.

The collection module stays byte-identical to the digest pinned in its evidence,
so archive handling lives here.
"""

import argparse
from functools import lru_cache
import gzip
import io
import json
from pathlib import Path

import population_sweep as sweep

collect, prepare, score = sweep.collect, sweep.prepare, sweep.score
EVIDENCE = sweep.SCHEMA + '-evidence'


@lru_cache(maxsize=None)
def proof(raw, feature):
    """Exhaustive gate proofs are pure and slow, so prove each exact model once per process."""
    return sweep.verify_model(raw, feature)


def verify(out):
    """The file set, receipts, anchors and fixed protocol, then the collection's own check.

    The structural checks are cheap, so tampering fails before the full recomputation.
    """
    manifest = json.loads((out / 'manifest.json').read_bytes())
    actual = {}
    for path in out.rglob('*'):
        score.require(not path.is_symlink(), 'symlink in evidence')
        if path.is_file() and path != out / 'manifest.json':
            actual[str(path.relative_to(out))] = prepare.sha(path.read_bytes())
    score.require(manifest['schema'] == sweep.SCHEMA + '-files' and actual == manifest['files'] and
                  'failure.json' not in actual, 'evidence files differ')
    started = json.loads((out / 'started.json').read_bytes())
    result = json.loads((out / 'result.json').read_bytes())
    _, named, size = collect.archive_inputs()
    models = sweep.policies(named)
    thresholds = {p: dict(proof(raw, int(p.removeprefix('light-')))) for p, raw in models.items()
                  if p.startswith('light-')}
    score.require(started['schema'] == sweep.SCHEMA + '-collection' and started['training'] is False and
                  started['policies'] == list(models) and started['seed_label'] == sweep.SEED_LABEL and
                  started['thresholds'] == thresholds and started['workers'] == sweep.WORKERS and
                  started['timeout_per_call'] == sweep.CALL_SECONDS and
                  started['collection_seconds'] == sweep.BUDGET_SECONDS and
                  all((out / 'models' / f'{n}.tlf').read_bytes() == raw for n, raw in models.items()),
                  'protocol differs')
    score.require(result['schema'] == sweep.SCHEMA + '-result' and result['complete'] is True and
                  result['calls'] == len(started['plan']) and
                  result['anchors'] == [p for p, _ in sweep.ANCHORS] and
                  0 < result['elapsed_seconds'] <= sweep.BUDGET_SECONDS, 'result receipt differs')
    score.require({p.name for p in (out / 'runs').iterdir()} == {e['id'] for e in started['plan']} and
                  {p.name for p in (out / 'anchors').iterdir()} == {p for p, _ in sweep.ANCHORS},
                  'run directory roster differs')
    calls = [(out / 'runs' / e['id'], e['policy'], e['seed'], e['layout']) for e in started['plan']]
    calls += [(out / 'anchors' / p, p, sweep.ANCHOR_SEED, sweep.ANCHOR_LAYOUT) for p, _ in sweep.ANCHORS]
    for folder, policy, seed, layout in calls:
        receipt = json.loads((folder / 'process.json').read_bytes())
        score.require(receipt.get('returncode') == 0 and receipt.get('timed_out') is False and
                      0 < receipt['timeout_seconds'] <= sweep.CALL_SECONDS and
                      (folder / 'stderr.txt').read_bytes() == b'', 'process receipt differs')
        score.require(Path(receipt['args'][1]).parts[-2:] == ('models', f'{policy}.tlf') and
                      receipt['args'][2:] == [seed, layout, str(sweep.STOP), 'all'],
                      'recorded process arguments differ')
    # The anchors are the custom path's link to the archived population runs.
    raw = sweep.BASELINE.read_bytes()
    score.require(prepare.sha(raw) == sweep.BASELINE_SHA, 'population baseline differs')
    baseline = json.loads(gzip.decompress(raw))
    for policy, archived in sweep.ANCHORS:
        value = json.loads((out / 'anchors' / policy / 'stdout.json').read_bytes())
        score.validate_record(value, models[policy], seed=sweep.ANCHOR_SEED, layout=sweep.ANCHOR_LAYOUT,
                              ticks=sweep.STOP, uniform_bytes=size)
        reference = json.loads(prepare.blob(
            baseline, f'runs/{archived}-{sweep.ANCHOR_SEED}-{sweep.ANCHOR_LAYOUT}-primary/stdout.json'))
        score.require(models[policy] == named[archived] and value['framebuffer_crc32'] is None and
                      {k: v for k, v in value.items() if k != 'framebuffer_crc32'} ==
                      {k: v for k, v in reference.items() if k != 'framebuffer_crc32'},
                      f'archived replay differs: {policy}')
    return sweep.check(out)


def package(out, target):
    verify(out)
    files, blobs = {}, {}
    for path in sorted(out.rglob('*')):
        if not path.is_file():
            continue
        raw = path.read_bytes()
        digest = prepare.sha(raw)
        files[str(path.relative_to(out))] = digest
        blobs[digest] = raw.hex()
    raw = json.dumps(dict(schema=EVIDENCE, files=files, blobs=blobs), sort_keys=True,
                     separators=(',', ':')).encode()
    # GzipFile keeps the same neutral header across Python versions.
    compressed = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed, mode='wb', filename='', compresslevel=9, mtime=0) as stream:
        stream.write(raw)
    collect.write(target, compressed.getvalue())
    return prepare.sha(target.read_bytes())


def unpack(archive, target):
    score.require(not target.exists() and not target.is_symlink(), 'fresh unpack directory required')
    bundle = json.loads(gzip.decompress(archive.read_bytes()))
    score.require(bundle['schema'] == EVIDENCE, 'wrong evidence schema')
    # Validate every path and blob before creating anything. Never execute or import archived code.
    files = {}
    for name, digest in bundle['files'].items():
        prepare.relative(name)
        raw = bytes.fromhex(bundle['blobs'][digest])
        score.require(prepare.sha(raw) == digest, 'archive blob differs')
        files[name] = raw
    target.mkdir(parents=True)
    for name, raw in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        collect.write(path, raw)
    return verify(target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('verify', 'pack', 'unpack'):
        p = commands.add_parser(name)
        p.add_argument('source', type=Path)
        if name != 'verify':
            p.add_argument('target', type=Path)
    args = parser.parse_args()
    if args.command == 'verify':
        print(json.dumps(verify(args.source), indent=2))
    elif args.command == 'pack':
        print(package(args.source, args.target))
    else:
        print(json.dumps(unpack(args.source, args.target), indent=2))
    print('Verified threshold sweep evidence; no simulator execution.')
