#!/usr/bin/env python3
"""Verify the frozen seed handoff, including dead slots and within-loop capacity."""

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

import garden_landing_seed_handoff_capture as capture
import garden_landing_adults as adults
import garden_landing_window as window
from garden_landing_founders import write_gzip
from garden_resources import require

ROOT, STEP, STOP = capture.ROOT, capture.STEP, capture.STOP
RULE = 'garden-landing-seed-handoff-v1'
MANIFEST_SHA = 'f103c843333b087006e899ca95e5cd536aeaae2ffa7a11e4c6b8880c6960bb46'
CAPTURE_SHA = 'e8f8b26d9bfbce145f88ea0e899b999236c60571fae0c0b31286eb0aec00e56c'
FOCAL, OLDER = (35, 1755480), (31, 1716600)
BLOCKERS = ('dormancy', 'moisture', 'light', 'plant_capacity', 'node_capacity', 'spacing', 'cold')


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def records(raw, kind, result):
    require(raw.endswith('\n'), 'unterminated trace')
    rows = [json.loads(line) for line in raw.splitlines()]
    header = dict(schema='landing-adult-resources-v1', start=capture.FIRST, stop=capture.LAST)
    footer = dict(complete=True, tick=STOP)
    if kind == 'stand':
        header.update(schema='landing-dawn-stand-trace-v1', node_limit=32, budget_mode=2)
        footer['run_hash'] = result['run_hash']
    require(kind in capture.KINDS and len(rows) >= 3 and rows[0] == header and rows[-1] == footer and
            [r['tick'] for r in rows[1:-1]] == list(range(capture.FIRST, capture.LAST + STEP, STEP)),
            'trace bounds, coverage or footer changed')
    return rows


def analyze(traces, result):
    require(set(traces) == set(capture.KINDS), 'missing trace kind')
    streams = {k: records(traces[k], k, result) for k in capture.KINDS}
    resource_audit = adults.analyze(streams['adult'], result)
    lives, seeds = capture.audit.previous.index_records(result['lineages'], result['seeds'], 0, STOP)
    death, refill = lives[FOCAL[0]]['death_tick'], seeds[OLDER]['end_tick']
    previous_slots, previous_nodes, visits, releases = None, {}, [], []
    for adult, stand in zip(streams['adult'][1:-1], streams['stand'][1:-1], strict=True):
        tick, slots = adult['tick'], stand['plant_order']
        climate, phase, strength = window.previous.sun_at(int(result['seed'], 16), tick)
        require(stand['tick'] == tick and stand['climate'] == climate and
                stand['seed_lifetime_ecology_ticks'] == result['seed_lifetime_ecology_ticks'] and
                adult['sun'] == [phase, strength] and adult['cold'] == climate['cold'] and
                adult['season'] == climate['day'] // 4, 'climate or clock mismatch')
        require(type(slots) is list and len(slots) == len(set(slots)) <= 8 and
                all(i in lives and lives[i]['birth_tick'] <= tick for i in slots), 'invalid stored inventory')
        alive = {i for i, p in lives.items() if capture.audit.previous.at(p, tick)}
        require(alive <= set(slots), 'living plant missing from stored inventory')
        plants = {p['id']: p for p in adult['plants']}
        bodies = {p['id']: p for p in stand['bodies']}
        require(len(bodies) == len(stand['bodies']) and set(bodies) == alive and all(
                bodies[i]['nodes'] == plants[i]['stages'][-1][4] and
                bodies[i]['roots'] == plants[i]['roots'] and bodies[i]['species'] == lives[i]['species']
                for i in alive), 'living morphology differs')
        born = {i for i, p in lives.items() if p['birth_tick'] == tick}
        before = [i for i in slots if i not in born]
        if previous_slots is not None:
            require(before == [i for i in previous_slots if i in before], 'stored compaction reordered plants')
            removed = [i for i in previous_slots if i not in before]
            require(all(lives[i]['death_tick'] is not None and lives[i]['death_tick'] < tick
                        for i in removed), 'premature plant reclamation')
            if removed:
                releases.append(dict(tick=tick, lineages=removed, nodes=sum(previous_nodes[i] for i in removed)))
        else:
            require(set(before) <= set(plants), 'left-censored dead-node inventory')
        # The resource observer omits old corpses. Their stored nodes remain
        # unchanged until whole-body reclamation; carry the death-step inventory.
        node_counts = {}
        for i in before:
            node_counts[i] = plants[i]['stages'][1][4] if i in plants else previous_nodes[i]
            if i not in alive and i in previous_nodes:
                require(node_counts[i] == previous_nodes[i], 'dead body changed stored nodes')
        nodes, initial_slots, checks = sum(node_counts.values()), list(before), {}
        expected_order = [k for k, s in seeds.items() if s['birth_tick'] < tick <= (s['end_tick'] or STOP)]
        for raw in adult['seeds']:
            key = raw[0], tick - raw[1] * STEP
            require(raw[6] == len(before) and raw[7] == nodes, 'seed check stored slots/nodes differ')
            if raw[8] != 1:  # Expiry precedes the blocker calculation.
                crowded = any(abs(lives[i]['column'] - raw[2]) < 3 for i in before)
                require(bool(raw[3] & 32) == crowded, 'spacing differs from stored inventory')
            checks[key] = raw
            if raw[8] == 2:
                require(raw[9] in born and raw[9] not in before, 'unexpected seedling insertion')
                before.append(raw[9])
                nodes += 4
        require(list(checks) == expected_order and before == slots, 'seed visit order or inventory differs')
        require(nodes == sum(plants[i]['stages'][2][4] if i in plants else previous_nodes[i] for i in slots),
                'post-germination node inventory differs')
        visits.append(dict(tick=tick, stored_before=initial_slots, stored_after=slots,
                           focal=checks[FOCAL], older=checks.get(OLDER), order=[list(k) for k in checks]))
        previous_slots = slots
        previous_nodes = {i: plants[i]['stages'][-1][4] if i in plants else previous_nodes[i] for i in slots}
    require(len(releases) == 1 and releases[0]['lineages'] == [FOCAL[0]], 'unexpected reclamation history')
    waiting = [v for v in visits if death <= v['tick'] < refill]
    masks = Counter(str(v['focal'][3]) for v in waiting)
    event = next(v for v in visits if v['tick'] == refill)
    return dict(ecology_samples=len(visits), seed_samples=resource_audit['seed_samples'],
                death_tick=death, reclamation=releases[0],
                delay_ecology_steps=(releases[0]['tick'] - death) // STEP,
                waiting_checks=len(waiting), waiting_masks=dict(masks),
                waiting_blockers={name: sum(n for mask, n in masks.items() if int(mask) & (1 << bit))
                                  for bit, name in enumerate(BLOCKERS)},
                waiting_usable_checks=sum(v['focal'][3] == 0 for v in waiting),
                refill=event, older_steps_until_expiry=seeds[OLDER]['lifetime_ecology_ticks'] - event['older'][1],
                after_refill=visits[-1], focal_final_outcome=seeds[FOCAL]['outcome'])


def check_capture(receipt, original):
    # The two-call receipt is already frozen; this authenticates arguments,
    # native process identities, results, frames and both raw trace hashes.
    require(sha(json.dumps(receipt, indent=2, sort_keys=True) + '\n') == CAPTURE_SHA,
            'handoff capture receipt changed')
    require(receipt['rule'] == capture.RULE and receipt['input_sha256'] == capture.audit.INPUT_SHA and
            receipt['input_receipt_sha256'] == original['receipt_sha256'] and
            receipt['protocol_sha256'] == capture.PROTOCOL_SHA and
            receipt['origin_manifest_sha256'] == capture.ORIGIN_MANIFEST and
            (receipt['case'], receipt['arm'], receipt['first'], receipt['last']) ==
            (capture.CASE, capture.ARM, capture.FIRST, capture.LAST) and
            receipt['native_runs'] == 2 and receipt['training_runs'] == 0 and
            set(receipt['runs']) == set(capture.LABELS), 'wrong handoff scope')
    for label, run in receipt['runs'].items():
        require(run['args'] == capture.arguments(original) and
                run['result'] == capture.selected(original)['result'] and
                run['frame'] == dict(path=label + '/frames/end.raw',
                                     sha256=capture.selected(original)['frame']['sha256']),
                'replay differs from original endpoint')


def make_value(receipt, traces, original):
    check_capture(receipt, original)
    for label in capture.LABELS:
        require(set(receipt['runs'][label]['traces']) == set(capture.KINDS), 'missing captured trace')
        for kind in capture.KINDS:
            require(receipt['runs'][label]['traces'][kind] ==
                    dict(path=f'{label}/{kind}.jsonl', sha256=sha(traces[kind])), 'trace bytes/repeat differ')
    return dict(rule=RULE, capture_sha256=CAPTURE_SHA, manifest_sha256=MANIFEST_SHA,
                capture=receipt, traces=traces, analysis=analyze(traces, capture.selected(original)['result']))


def check_value(saved):
    require(saved == make_value(saved['capture'], saved['traces'], capture.audit.load_input()),
            'handoff analysis differs')


def from_bundle(root):
    require(capture.digest(root / 'manifest.json') == MANIFEST_SHA and
            capture.digest(root / 'capture.json') == CAPTURE_SHA, 'handoff bundle identity changed')
    manifest = json.loads((root / 'manifest.json').read_text())
    require(manifest['rule'] == capture.RULE and set(manifest['artifacts']) ==
            {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p != root / 'manifest.json'},
            'handoff bundle inventory differs')
    for name, expected in manifest['artifacts'].items():
        require(capture.digest(capture.safe_artifact(root, name)) == expected, 'changed handoff artifact: ' + name)
    receipt = json.loads((root / 'capture.json').read_text())
    original = capture.audit.load_input()
    check_capture(receipt, original)
    for label in capture.LABELS:
        process = json.loads((root / label / 'process.json').read_text())
        run = receipt['runs'][label]
        require(process['returncode'] == 0 and process['stderr'] == '' and
                json.loads(process['stdout']) == run['result'] and
                json.loads((root / label / 'run.json').read_text()) == run and
                json.loads((root / label / 'result.json').read_text()) == run['result'] and
                capture.digest(root / label / 'model.tgl') == original['model_sha256'], 'call record differs')
        capture.frame_bytes(root / run['frame']['path'], run['result'])
    traces = {kind: (root / 'trace' / (kind + '.jsonl')).read_text() for kind in capture.KINDS}
    return make_value(receipt, traces, original)


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
    print(json.dumps(saved['analysis'], indent=2))
    print('Seed handoff verified offline; no simulator executed.')


if __name__ == '__main__':
    main()
