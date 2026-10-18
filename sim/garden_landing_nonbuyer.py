#!/usr/bin/env python3
"""Audit a frozen non-buyer's full lifetime of eligibility and ordered bank access."""

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

import garden_landing_nonbuyer_capture as capture
import garden_landing_bank_access as bank
import garden_landing_window as window
from garden_landing_founders import write_gzip
from garden_resources import require

ROOT, STEP, STOP = capture.ROOT, capture.STEP, capture.STOP
RULE = 'garden-landing-nonbuyer-v1'
MANIFEST_SHA = '6476ed2b0ccc43e7a8f4f14fa9933241b3a25ace6c9057378461c6a77e407c7b'
CAPTURE_SHA = 'ae6916a1705d7446c6d3bbe1a34110266a2c47f598fc43ed044cb679b9e558d4'
EXCERPT_SHA = 'e50774d8e5068a638f9f122a000a0da3041a3ceb4fd7383b158714f58a24cd40'
BLOCKERS = ('cooldown', 'cadence', 'bank', 'dead', 'stress', 'daylight',
            'generation', 'energy', 'water', 'flower')


def excerpt_identity(value):
    """Authenticate canonical JSON without depending on the verifier's zlib version."""
    encoded = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()
    return hashlib.sha256(encoded).hexdigest()


def analyze(excerpt, result):
    require(set(excerpt) == {'fields', 'rows'} and excerpt['fields'] == list(bank.FIELDS),
            'wrong excerpt fields')
    rows = excerpt['rows']
    access = bank.analyze_visits([[r['tick'], r['reproduction']] for r in rows],
                                result, capture.FIRST, capture.LAST)
    lives = {p['id']: p for p in result['lineages']}
    focal = lives[capture.FOCAL]
    require(focal['birth_tick'] == capture.FIRST and focal['death_tick'] is None and
            focal['seeds_created'] == 0 and result['tick'] == STOP, 'wrong focal lifetime')
    last_buyer = [s['parent'] for s in result['seeds']
                  if 1228800 < s['birth_tick'] < capture.FIRST][-1]
    release_map = {r['tick']: r for r in access['release_events']}
    changes, visits, openings, first_ready, previous_body = [], [], [], None, None
    bid_count = 0
    for row in rows:
        require(set(row) == {'tick', 'climate', 'plant_order', 'reproduction', 'body', 'bids'},
                'wrong excerpt row fields')
        tick, slots, raw = row['tick'], row['plant_order'], row['reproduction']
        cursor_before = last_buyer
        alive = {i for i, p in lives.items() if capture.origin_capture.audit.previous.at(p, tick)}
        require(type(slots) is list and len(slots) == len(set(slots)) <= 8 and alive <= set(slots) and
                all(i in lives and lives[i]['birth_tick'] <= tick for i in slots), 'wrong stored order')
        expected_order = slots
        if tick % (4 * STEP) == 0:
            successor = min((i for i in alive if i > last_buyer), default=min(alive))
            pivot = slots.index(successor)
            expected_order = slots[pivot:] + slots[:pivot]
        require([v[0] for v in raw] == expected_order, 'purchase cursor or stored visit order differs')
        buyers = [v[0] for v in raw if v[-1]]
        if buyers:
            last_buyer = buyers[-1]
        climate, _, strength = window.previous.sun_at(int(result['seed'], 16), tick)
        require(row['climate'] == climate and all(v[13] == strength for v in raw),
                'climate or sun differs')
        visit = dict(zip(bank.FIELDS, next(v for v in raw if v[0] == capture.FOCAL), strict=True))
        body = row['body']
        require(set(body) == {'id', 'species', 'nodes', 'roots', 'flowers', 'maximum_stem_depth', 'tips'} and
                body['id'] == capture.FOCAL and body['species'] == focal['species'] and
                1 <= body['nodes'] <= 32 and 0 <= body['roots'] <= body['nodes'] and
                body['flowers'] == sum(visit[k] for k in ('immature', 'spent', 'ready')) <= body['nodes'],
                'focal flower/body accounting differs')
        for bid in row['bids']:
            require(bid['id'] == capture.FOCAL and 1 <= bid['nodes'] <= body['nodes'],
                    'wrong focal growth bid')
        bid_count += len(row['bids'])
        state = {k: v for k, v in body.items() if k != 'tips'}
        if state != previous_body:
            changes.append(dict(tick=tick, body=state))
            previous_body = state
        if visit['ready'] and first_ready is None:
            first_ready = tick
        visits.append(visit)
        entry = raw[0][bank.FIELDS.index('bank')]
        if entry < 8:
            openings.append(dict(tick=tick, last_buyer_before=cursor_before,
                order=expected_order, bank_at_entry=entry, focal_visit=visit,
                buyers=buyers, release=release_map.get(tick)))
    parent = next(p for p in access['plants'] if p['id'] == capture.FOCAL)
    counts = {name: sum(bool(v['blockers'] & (1 << bit)) for v in visits)
              for bit, name in enumerate(BLOCKERS)}
    return dict(focal=focal, samples=len(rows), first_tick=capture.FIRST, last_tick=capture.LAST,
        first_ready_tick=first_ready, body_changes=changes, focal_growth_bids=bid_count,
        overlapping_blockers=counts, focal_access=parent,
        ranges={k: [min(v[k] for v in visits), max(v[k] for v in visits)] for k in
                ('energy', 'water', 'energy_required', 'water_required', 'ready', 'cooldown', 'stress')},
        bank=access['bank'], openings=openings,
        opening_masks=dict(Counter(str(r['focal_visit']['blockers']) for r in openings)),
        open_at_focal_turn=sum(r['focal_visit']['bank'] < 8 for r in openings),
        all_parent_access=[dict(id=p['id'], access=p['access'], purchases=p['purchases'])
                           for p in access['plants']])


def check_capture(receipt, original):
    require(hashlib.sha256((json.dumps(receipt, indent=2, sort_keys=True) + '\n').encode()).hexdigest()
            == CAPTURE_SHA, 'non-buyer capture receipt changed')
    require(receipt['rule'] == capture.RULE and receipt['protocol_sha256'] == capture.PROTOCOL_SHA and
            capture.digest(ROOT / capture.PROTOCOL) == capture.PROTOCOL_SHA and
            receipt['input_sha256'] == capture.origin_capture.audit.INPUT_SHA and
            receipt['input_receipt_sha256'] == original['receipt_sha256'] and
            receipt['origin_manifest_sha256'] == capture.origin_capture.ORIGIN_MANIFEST and
            (receipt['case'], receipt['arm'], receipt['focal'], receipt['first'], receipt['last']) ==
            (capture.CASE, capture.ARM, capture.FOCAL, capture.FIRST, capture.LAST) and
            receipt['native_runs'] == 2 and receipt['training_runs'] == 0 and
            set(receipt['runs']) == set(capture.LABELS), 'wrong non-buyer scope')
    for label, run in receipt['runs'].items():
        require(run['args'] == capture.arguments(original) and
                run['result'] == capture.selected(original)['result'] and
                run['frame'] == dict(path=label + '/frames/end.raw',
                                     sha256=capture.selected(original)['frame']['sha256']),
                'replay differs from original endpoint')


def make_value(receipt, excerpt, original):
    check_capture(receipt, original)
    a, b = (receipt['runs'][label] for label in capture.LABELS)
    require(excerpt_identity(excerpt) == EXCERPT_SHA and
            a['excerpt']['sha256'] == b['excerpt']['sha256'] and
            all(run['excerpt']['path'] == label + '/excerpt.json.gz'
                for label, run in receipt['runs'].items()) and
            {k: v for k, v in a['trace'].items() if k != 'path'} ==
            {k: v for k, v in b['trace'].items() if k != 'path'}, 'excerpt bytes or repeat differ')
    return dict(rule=RULE, capture_sha256=CAPTURE_SHA, manifest_sha256=MANIFEST_SHA,
        capture=receipt, excerpt=excerpt, analysis=analyze(excerpt, capture.selected(original)['result']))


def check_value(saved):
    require(saved == make_value(saved['capture'], saved['excerpt'], capture.origin_capture.audit.load_input()),
            'non-buyer analysis differs')


def from_bundle(root):
    require(capture.digest(root / 'manifest.json') == MANIFEST_SHA and
            capture.digest(root / 'capture.json') == CAPTURE_SHA, 'non-buyer bundle identity differs')
    manifest = json.loads((root / 'manifest.json').read_text())
    require(manifest['rule'] == capture.RULE and set(manifest['artifacts']) ==
            {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p != root / 'manifest.json'},
            'bundle inventory differs')
    for name, expected in manifest['artifacts'].items():
        require(capture.digest(capture.origin_capture.safe_artifact(root, name)) == expected,
                'changed non-buyer artifact: ' + name)
    receipt = json.loads((root / 'capture.json').read_text())
    original = capture.origin_capture.audit.load_input()
    check_capture(receipt, original)
    excerpts = []
    for label in capture.LABELS:
        run = receipt['runs'][label]
        process = json.loads((root / label / 'process.json').read_text())
        require(process['returncode'] == 0 and process['stderr'] == '' and
                json.loads(process['stdout']) == run['result'] and
                json.loads((root / label / 'result.json').read_text()) == run['result'] and
                json.loads((root / label / 'run.json').read_text()) == run and
                capture.digest(root / label / 'model.tgl') == original['model_sha256'], 'call record differs')
        capture.origin_capture.frame_bytes(root / run['frame']['path'], run['result'])
        path = root / run['trace']['path']
        require(capture.unpacked_identity(path) == {k: run['trace'][k] for k in ('sha256', 'bytes')},
                'decompressed trace differs')
        with gzip.open(root / run['excerpt']['path'], 'rt') as stream:
            excerpt = json.load(stream)
        require(excerpt == capture.extract(path, run['result']), 'excerpt is not exact source extraction')
        excerpts.append(excerpt)
    require(excerpts[0] == excerpts[1], 'repeat extraction differs')
    return make_value(receipt, excerpts[0], original)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--out', type=Path)
    mode.add_argument('--verify', type=Path)
    parser.add_argument('--bundle', type=Path)
    args = parser.parse_args()
    if args.verify:
        with gzip.open(args.verify, 'rt') as stream:
            saved = json.load(stream)
        check_value(saved)
        if args.bundle:
            require(saved == from_bundle(args.bundle.resolve()), 'bundle does not reproduce audit')
    else:
        require(args.bundle is not None, '--out requires the completed --bundle')
        saved = from_bundle(args.bundle.resolve())
        write_gzip(args.out, saved)
    analysis = saved['analysis']
    print(json.dumps({k: analysis[k] for k in ('samples', 'first_ready_tick', 'overlapping_blockers',
                       'opening_masks', 'open_at_focal_turn')}, indent=2))
    print('Focal access:', analysis['focal_access']['access'])
    print('Non-buyer audit verified offline; no simulator executed.')


if __name__ == '__main__':
    main()
