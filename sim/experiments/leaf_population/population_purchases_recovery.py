#!/usr/bin/env python3
"""Validate retained native outputs after the purchase array-padding parser fix."""

import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path

import population_purchases as purchase

follow, collect, prepare, score = purchase.follow, purchase.collect, purchase.prepare, purchase.score
ERROR = "ValueError('reachable columns differ')"
FIXES = ('sim/experiments/leaf_population/population_purchases.py',
         'sim/experiments/leaf_population/test_population_purchases.py',
         'sim/experiments/leaf_population/population_purchases_recovery.py')


def inventory(root):
    result = {}
    for path in sorted(root.rglob('*')):
        score.require(not path.is_symlink(), 'symlink in recovery input')
        if path.is_file():
            result[str(path.relative_to(root))] = prepare.sha(path.read_bytes())
    return result


def elapsed(root):
    receipts = [json.loads((root / 'runs' / c['id'] / 'process.json').read_bytes()) for c in purchase.roster()]
    starts = [datetime.fromisoformat(r['started_utc']) for r in receipts]
    ends = [start + timedelta(seconds=r['elapsed_seconds']) for start, r in zip(starts, receipts, strict=True)]
    return (max(ends) - min(starts)).total_seconds()


def validate_recovery(out):
    record = json.loads((out / 'recovery.json').read_bytes())
    score.require(record['schema'] == 'garden-purchase-offline-recovery-v1' and
                  record['native_calls_added'] == 0 and record['error'] == ERROR,
                  'recovery identity differs')
    actual = inventory(out)
    for name, digest in record['original_files'].items():
        prepare.relative(name)
        destination = 'recovery/original-failure.json' if name == 'failure.json' else name
        score.require(actual[destination] == digest, 'retained attempt changed')
    score.require(json.loads((out / 'recovery/original-failure.json').read_bytes()) == dict(error=ERROR),
                  'original validation failure differs')
    score.require(set(record['validation_sources']) == set(FIXES), 'recovery source roster differs')
    for name, digest in record['validation_sources'].items():
        score.require(actual['recovery/source/' + name] == digest, 'recovery source differs')
    score.require(record['native_interval_seconds'] == elapsed(out), 'recovery timing differs')


def recover(attempt, out):
    score.require(not out.exists() and not out.is_symlink(), 'fresh recovery directory required')
    original = inventory(attempt)
    score.require('result.json' not in original and 'manifest.json' not in original and
                  json.loads((attempt / 'failure.json').read_bytes()) == dict(error=ERROR),
                  'expected validation-only failed attempt')
    started = json.loads((attempt / 'started.json').read_bytes())
    current = follow.sources(purchase.EXPERIMENT)
    changed = {p for p in current.keys() | started['sources'].keys()
               if current.get(p) != started['sources'].get(p)}
    score.require(changed <= set(FIXES), 'non-validator source changed')
    analyses = purchase.validate_outputs(attempt, *purchase.inputs())
    interval = elapsed(attempt)
    out.mkdir(parents=True)
    for name in original:
        path = out / ('recovery/original-failure.json' if name == 'failure.json' else name)
        path.parent.mkdir(parents=True, exist_ok=True)
        collect.write(path, (attempt / name).read_bytes())
    fixed = {}
    for name in FIXES:
        raw = (collect.ROOT / name).read_bytes()
        fixed[name] = prepare.sha(raw)
        path = out / 'recovery/source' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        collect.write(path, raw)
    collect.save(out / 'recovery.json', dict(schema='garden-purchase-offline-recovery-v1',
        error=ERROR, native_calls_added=0, original_files=original,
        validation_sources=fixed, native_interval_seconds=interval,
        timing_basis='first native call start through last native call completion'))
    collect.save(out / 'result.json', dict(complete=True, calls=8, elapsed_seconds=interval,
        analyses=analyses, validation_recovered_offline=True))
    collect.save(out / 'manifest.json', inventory(out))
    result = follow.verify(out, experiment=purchase.EXPERIMENT)
    score.require(original == inventory(attempt), 'original attempt changed')
    print(json.dumps(dict(complete=True, calls=result['calls'], native_calls_added=0,
                         elapsed_seconds=interval)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    recover(args.attempt, args.out)
