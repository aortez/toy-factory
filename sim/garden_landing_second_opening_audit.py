#!/usr/bin/env python3
"""Offline paired accounting of the frozen day-288 second opening."""

import argparse
from functools import cache
import gzip
import json
from pathlib import Path
import sys

import garden_landing_second_opening as capture
import garden_landing_window as window
from garden_experiments import digest
from garden_landing_founders import write_gzip
from garden_landing_root_allocation_audit import fingerprint
from garden_resources import require

ROOT, BASE, STOP, STEP = capture.ROOT, capture.BASE, capture.STOP, capture.STEP
RULE = 'garden-landing-second-opening-audit-v1'
INPUT = 'benchmarks/garden-seasons/landing-second-opening-capture.json.gz'
INPUT_SHA = '4364639b5bf3b3445b22883ab3ec347f845f309d79af29dd8d7b78ff8827fc63'
MANIFEST_SHA = '30d684a178f6686ebb52126c22d7d95cd96ad923f0d961f5a99f0ec2de0b6238'
PHASES = ('control', 'treatment')
SOURCES = tuple(sorted({*window.prior.SOURCES, *capture.SOURCES,
                        'sim/garden_landing_window.py', 'sim/garden_landing_second_opening_audit.py'}))


@cache
def inputs():
    require(digest(ROOT / INPUT) == INPUT_SHA, 'second-opening capture changed')
    with gzip.open(ROOT / INPUT, 'rt') as stream:
        value = json.load(stream)
    capture.check_capture(value)
    return value


def provenance():
    saved = inputs()
    return dict(rule=RULE, input_sha256=INPUT_SHA, protocol_sha256=capture.PROTOCOL_SHA,
                raw_manifest_sha256=MANIFEST_SHA, native_runs=0, training_runs=0,
                interval=[BASE + STEP, STOP], boundary_tick=BASE, panel=saved['panel'],
                sources={p: digest(ROOT / p) for p in SOURCES})


def analyze(run, world, evidence):
    return window.analyze_world(run, world, evidence, BASE, STOP, 'second_turnover_probe')


def check_value(value):
    saved, expected = inputs(), provenance()
    require(set(value) == {*expected, 'evidence', 'analysis', 'comparisons', 'receipt_sha256'} and
            all(value[k] == v for k, v in expected.items()), 'audit provenance differs')
    require(set(value['evidence']) == set(value['analysis']) == set(value['comparisons']) == set(saved['panel']),
            'wrong audit panel')
    for key, world in saved['panel'].items():
        require(set(value['evidence'][key]) == set(value['analysis'][key]) == set(PHASES), 'wrong paired phases')
        require(value['evidence'][key]['control']['boundary'] == value['evidence'][key]['treatment']['boundary'],
                'paired pre-event evidence changed')
        for phase in PHASES:
            require(value['analysis'][key][phase] == analyze(saved['runs'][phase][key], world, value['evidence'][key][phase]),
                    'derived audit differs: ' + phase + '/' + key)
        require(value['comparisons'][key] == window.compare(value['analysis'][key], world), 'paired comparison differs')
    require(value['receipt_sha256'] == fingerprint({k: v for k, v in value.items() if k != 'receipt_sha256'}),
            'audit receipt changed')


def extract(bundle):
    saved, expected = inputs(), provenance()
    require(digest(bundle / 'manifest.json') == MANIFEST_SHA, 'wrong raw manifest')
    capture.verify_bundle(bundle, saved)
    value = dict(expected, evidence={}, analysis={}, comparisons={})
    for key, world in saved['panel'].items():
        value['evidence'][key], value['analysis'][key] = {}, {}
        for phase in PHASES:
            run = saved['runs'][phase][key]
            paths = {k: capture.followup.artifact(bundle, v) for k, v in run['traces'].items()}
            evidence = window.extract_world(paths, run, capture.FIRST, BASE, STOP)
            value['evidence'][key][phase] = evidence
            value['analysis'][key][phase] = analyze(run, world, evidence)
            require(all(digest(paths[k]) == run['traces'][k]['sha256'] for k in paths), 'trace changed during extraction')
            print(phase + '/' + key + ': resources, bank, seeds and second opening verified', flush=True)
        value['comparisons'][key] = window.compare(value['analysis'][key], world)
    require(digest(bundle / 'manifest.json') == MANIFEST_SHA and provenance() == expected and
            digest(ROOT / INPUT) == INPUT_SHA, 'audit inputs changed')
    value['receipt_sha256'] = fingerprint(value)
    check_value(value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--extract-from', type=Path)
    mode.add_argument('--verify', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    require(bool(args.out) == bool(args.extract_from), 'extraction requires a fresh --out; verify takes no output')
    if args.extract_from:
        require(not args.out.exists() and not args.out.is_symlink(), 'fresh output required')
        write_gzip(args.out, extract(args.extract_from.resolve()))
    else:
        with gzip.open(args.verify, 'rt') as stream:
            value = json.load(stream)
        check_value(value)
    print('verified ' + RULE)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, TypeError, IndexError, OSError) as error:
        print('error: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
