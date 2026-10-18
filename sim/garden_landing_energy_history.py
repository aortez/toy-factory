#!/usr/bin/env python3
"""Trace a selected mature plant's saved energy shortfalls; never run simulations."""

from __future__ import annotations

import argparse
from collections import Counter
from functools import cache
import gzip
import json
from pathlib import Path
import sys

import garden_landing_dispersal_energy_audit as previous
from garden_experiments import digest
from garden_landing_founders import write_gzip
from garden_landing_root_allocation_audit import fingerprint, pack, unpack
from garden_resources import require

ROOT, STEP, STOP, AFTER = previous.ROOT, previous.STEP, previous.STOP, previous.AFTER
population, adults = previous.population, previous.population.adults
SIDES = previous.SIDES
RULE = 'garden-landing-energy-history-v1'
PROTOCOL = 'benchmarks/garden-seasons/landing-energy-history-protocol.md'
PROTOCOL_SHA = 'c8fb37a9c3f897d7972009759a2ff4ef44e989c63244d86893c8e49999573c54'
INPUT = 'benchmarks/garden-seasons/landing-dispersal-energy-audit-results.json.gz'
INPUT_SHA = '998796b9b79732d1a37e62b4a9c145f4b18fa05bde49028d9cbdd15699d4b5fb'
INPUTS = {INPUT: INPUT_SHA, **previous.INPUTS}
MANIFEST_SHA = '4a94df9dcc4f53c980e3631b58dc3fd853c3f03a68678d335127ab09f7a83001'
SUBJECT = dict(case='f7ee4528-fixed-candidate', allocator='candidate', water='cap',
               id=20, birth=590640, column=3, first_deficit=978420, last_deficit=978540)
SOURCES = ('sim/garden_landing_energy_history.py', 'sim/garden_landing_dispersal_energy_audit.py',
           'sim/garden_landing_population.py', 'sim/garden_landing_adults.py',
           'sim/garden_landing_root_allocation_audit.py', 'sim/garden_landing_founders.py')


def provenance():
    require(digest(ROOT / PROTOCOL) == PROTOCOL_SHA and
            all(digest(ROOT / p) == sha for p, sha in INPUTS.items()), 'frozen evidence/protocol changed')
    return dict(rule=RULE, inputs=INPUTS, protocol_sha256=PROTOCOL_SHA,
                raw_manifest_sha256=MANIFEST_SHA, native_runs=0, training_runs=0, subject=SUBJECT)


@cache
def inputs():
    provenance()
    with gzip.open(ROOT / INPUT, 'rt') as stream: prior = json.load(stream)
    previous.check_value(prior)
    worlds, pairs = previous.inputs()
    selected = [p for p in pairs if p['case']['id'] == SUBJECT['case'] and
                p['allocator'] == SUBJECT['allocator'] and p['water'] == SUBJECT['water']]
    require(len(selected) == 1, 'wrong selected case')
    pair = selected[0]
    require([SUBJECT['id'], SUBJECT['id']] in population.matched_births(
        *(worlds[pair['worlds'][a]]['result'] for a in SIDES))['matched'], 'selected ancestry differs')
    out = {}
    for a in SIDES:
        name, world = pair['worlds'][a], worlds[pair['worlds'][a]]
        plant = next(p for p in world['analysis']['plants'] if p['life']['id'] == SUBJECT['id'])
        life = plant['life']
        require(life['birth_tick'] == SUBJECT['birth'] and life['column'] == SUBJECT['column'] and
                life['death_tick'] is None and life['parent'] == 7 and life['generation'] == 2,
                'wrong selected life')
        saved = next(p for p in prior['analysis']['worlds'][name]['plants'] if p['life']['id'] == SUBJECT['id'])
        require(saved['life'] == life and saved['resources'] == plant['resources'], 'selected audit differs')
        out[a] = dict(name=name, result=world['result'], plant=plant, trace=world['traces']['adult'])
    require([e['tick'] for e in out['candidate']['plant']['shortages'] if e['energy']['unpaid']] ==
            [978420, 978480, 978540], 'selected deficit episode changed')
    return out


def check_raw(bundle, source):
    require(digest(bundle / 'manifest.json') == MANIFEST_SHA, 'wrong raw manifest')
    manifest = json.loads((bundle / 'manifest.json').read_text())['artifacts']
    paths = {}
    for a in SIDES:
        entry = source[a]['trace']
        path = (bundle / entry['path']).resolve()
        require(path.is_relative_to(bundle.resolve()) and manifest.get(entry['path']) == entry['sha256'] and
                digest(path) == entry['sha256'], 'raw adult trace changed or escaped bundle')
        paths[a] = path
    return paths


def extract(bundle, source):
    paths, rows = check_raw(bundle, source), {}
    for a in SIDES:
        result = source[a]['result']
        lives = {p['id']: p for p in result['lineages']}
        selected = []
        for row in population.trace_rows(paths[a], 'adult', result):
            tick = row['tick']
            ps = {p['id']: p for p in row['plants']}
            expected = {i for i, p in lives.items() if max(STEP, p['birth_tick']) <= tick <= previous.endpoint(p)}
            require(len(ps) == len(row['plants']) and set(ps) == expected and
                    all(p['birth'] == lives[i]['birth_tick'] for i, p in ps.items()), 'raw census/identity differs')
            if SUBJECT['id'] in ps:
                selected.append({k: row[k] for k in ('tick', 'sun', 'season', 'cold')} |
                                {'plant': pack(ps[SUBJECT['id']])})
        rows[a] = selected
        print(a + ': selected complete adult history extracted', flush=True)
    return rows


def replay_energy(before, income, due, growth, seed):
    """Independent ordered store arithmetic, not a counterfactual ecology run."""
    require(all(type(v) is int and v >= 0 for v in (before, income, due, growth, seed)) and before <= 256,
            'invalid energy inputs')
    uptake = min(256, before + income)
    paid = min(due, uptake)
    maintenance = uptake - paid
    require(maintenance >= growth + seed, 'unfunded recorded spending')
    return dict(uptake=uptake, maintenance=maintenance, growth=maintenance - growth,
                final=maintenance - growth - seed, overflow=max(0, before + income - 256),
                unpaid=due - paid)


def validate_history(rows, source):
    plant, result = source['plant'], source['result']
    life = plant['life']
    require(type(rows) is list and len(rows) == (STOP - life['birth_tick']) // STEP + 1,
            'incomplete selected history')
    resources, shortages, steps = adults.budget(), [], []
    before, roots, shape_n, payments = None, None, 0, 0
    shapes = plant['body_changes']
    purchases = {s['birth_tick']: s for s in result['seeds'] if s['parent'] == life['id']}
    require(len(purchases) == life['seeds_created'], 'duplicate/missing selected purchases')
    for n, row in enumerate(rows):
        tick = life['birth_tick'] + n * STEP
        require(set(row) == {'tick', 'sun', 'season', 'cold', 'plant'} and type(row['tick']) is int and
                row['tick'] == tick and adults.vector(row['sun'], 2, 255) and
                row['sun'][0] == (64 + tick // STEP) % 256 and type(row['cold']) is bool and
                type(row['season']) is int and row['season'] == (tick // population.DAY % 16) // 4,
                'wrong selected clock/environment')
        p = unpack(row['plant'], life, tick)
        receipt = adults.transfers(p, life, before)
        adults.accumulate(resources, receipt, n == 0)
        pay = population.payment(p, receipt, roots, tick, row['sun'][0])
        if pay:
            payments += 1
            if any(pay[r]['unpaid'] for r in previous.RESOURCES): shortages.append(pay)
        while shape_n + 1 < len(shapes) and shapes[shape_n + 1]['tick'] <= tick: shape_n += 1
        shape = shapes[shape_n]['body']
        require([shape['nodes'], shape['roots']] == [p['stages'][-1][4], p['roots']], 'selected body differs')
        require(all(receipt[r]['reproduction'] == cost * (tick in purchases)
                    for r, cost in (('energy', 48), ('water', 24))), 'seed ledger/debit differs')
        if before is None:
            require(receipt['energy']['initial'] == 64 and receipt['energy']['income'] == 0 and pay is None,
                    'unexpected birth resources')
        else:
            require(p['stages'][0][4] == before[4], 'pre-maintenance body changed')
        energy = receipt['energy']
        predicted = replay_energy(energy['initial'], energy['income'],
                                  ((before[4] + 7) // 8) if before is not None and tick % 60 == 0 else 0,
                                  energy['growth'], energy['reproduction'])
        require(predicted['overflow'] == energy['overflow'] and predicted['final'] == energy['final'] and
                predicted['unpaid'] == (pay['energy']['unpaid'] if pay else 0) and
                [predicted['growth'], predicted['final']] == [p['stages'][j][0] for j in (3, 4)] and
                (before is None or [predicted['uptake'], predicted['maintenance']] ==
                 [p['stages'][j][0] for j in (0, 1)]), 'independent energy reconstruction differs')
        steps.append(dict(tick=tick, resources=receipt, payment=pay))
        before, roots = p['stages'][-1], p['roots']
    require(resources == plant['resources'] and shortages == plant['shortages'] and payments == plant['payments'],
            'selected lifetime account differs')
    return dict(resources=resources, shortages=shortages, payments=payments), steps


def shared_full(rows, first, *, later=False):
    candidates = [n for n, pair in enumerate(zip(*(rows[a] for a in SIDES), strict=True))
                  if ((pair[0]['tick'] > first) if later else (pair[0]['tick'] < first)) and
                  all(r['plant'][0][-1][0] == 256 for r in pair)]
    return (candidates[0] if later else candidates[-1]) if candidates else None


def window(steps, start, end):
    """Actual transfers after a post-step anchor, inclusive of the endpoint."""
    require(0 <= end < len(steps) and (start is None or 0 <= start <= end), 'invalid history window')
    total = adults.budget()
    if start is not None:
        for r in total:
            total[r]['initial'] = total[r]['final'] = steps[start]['resources'][r]['final']
    first = 0 if start is None else start + 1
    payments, due, unpaid = 0, dict.fromkeys(total, 0), dict.fromkeys(total, 0)
    for n in range(first, end + 1):
        s = steps[n]
        adults.accumulate(total, s['resources'], start is None and n == 0)
        if s['payment']:
            payments += 1
            for r in total:
                due[r] += s['payment'][r]['due']
                unpaid[r] += s['payment'][r]['unpaid']
    require(all(total[r]['upkeep'] + unpaid[r] == due[r] for r in total), 'window demand mismatch')
    return dict(resources=total, payments=payments, due=due, unpaid=unpaid)


def features(row, step):
    e, w = (step['resources'][r] for r in previous.RESOURCES)
    pay = step['payment']
    return dict(energy_income=e['income'], energy_retained=e['income'] - e['overflow'],
                energy_store=e['final'], energy_growth=e['growth'], energy_reproduction=e['reproduction'],
                energy_due=pay['energy']['due'] if pay else 0, energy_unpaid=pay['energy']['unpaid'] if pay else 0,
                water_store=w['final'], nodes=row['plant'][0][-1][4], roots=row['plant'][2],
                active_leaves=row['plant'][3])


def differences(rows, steps, start, end):
    found = {}
    for n in range(0 if start is None else start + 1, end + 1):
        a, b = (features(rows[side][n], steps[side][n]) for side in SIDES)
        for key in a:
            if key not in found and a[key] != b[key]:
                found[key] = dict(tick=rows['control'][n]['tick'], control=a[key], candidate=b[key])
    return found


def paired_window(rows, steps, start, end):
    accounts = {a: window(steps[a], start, end) for a in SIDES}
    return dict(after=None if start is None else rows['control'][start]['tick'],
                through=rows['control'][end]['tick'], arms=accounts,
                delta={r: {k: accounts['candidate']['resources'][r][k] - accounts['control']['resources'][r][k]
                           for k in adults.FIELDS} for r in previous.RESOURCES})


def phase_blocks(rows, steps, start, end):
    first = 0 if start is None else start + 1
    blocks, begin, clock = [], first, None
    for n in range(first, end + 2):
        row = rows['control'][n] if n <= end else None
        current = [row['sun'][0] // 64, row['season'], row['cold']] if row else None
        if clock is not None and current != clock:
            block = paired_window(rows, steps, begin - 1 if begin else None, n - 1)
            block.update(first=rows['control'][begin]['tick'], phase_quarter=clock[0], season=clock[1], cold=clock[2],
                         post_step_bodies={a: [list(key) + [count] for key, count in sorted(Counter(
                             (r['plant'][0][-1][4], r['plant'][2], r['plant'][3])
                             for r in rows[a][begin:n]).items())] for a in SIDES})
            blocks.append(block)
            begin = n
        clock = current
    return blocks


def analyze(rows, source):
    require(set(rows) == set(SIDES), 'wrong history side coverage')
    histories, steps = {}, {}
    for a in SIDES: histories[a], steps[a] = validate_history(rows[a], source[a])
    require(all([x[k] for k in ('tick', 'sun', 'season', 'cold')] ==
                [y[k] for k in ('tick', 'sun', 'season', 'cold')]
                for x, y in zip(rows['control'], rows['candidate'], strict=True)), 'unequal paired environment')
    first, last = SUBJECT['first_deficit'], SUBJECT['last_deficit']
    anchor, recovered = shared_full(rows, first), shared_full(rows, last, later=True)
    last_index = (last - SUBJECT['birth']) // STEP
    repaid = next((n for n in range(last_index + 1, len(steps['candidate'])) if
                   steps['candidate'][n]['payment'] and steps['candidate'][n]['payment']['energy']['unpaid'] == 0), None)
    milestones = [{'label': 'deficit', 'index': (e['tick'] - SUBJECT['birth']) // STEP}
                  for e in histories['candidate']['shortages'] if e['energy']['unpaid']]
    if repaid is not None: milestones.append(dict(label='first_paid_maintenance', index=repaid))
    if recovered is not None: milestones.append(dict(label='shared_full_recovery', index=recovered))
    purchases = {a: [dict(tick=s['tick'], pre_energy=rows[a][n]['plant'][0][3][0],
                         post_energy=s['resources']['energy']['final'])
                     for n, s in enumerate(steps[a]) if s['resources']['energy']['reproduction']]
                 for a in SIDES}
    end = recovered if recovered is not None else len(rows['control']) - 1
    anchor_tick = None if anchor is None else rows['control'][anchor]['tick']
    return dict(history=histories, checkpoint=anchor_tick,
                checkpoints=[dict(label=m['label'], **paired_window(rows, steps, anchor, m['index'])) for m in milestones],
                first_difference=differences(rows, steps, anchor, last_index),
                purchases=purchases,
                last_prior_purchase={a: next((p for p in reversed(purchases[a]) if p['tick'] < first), None) for a in SIDES},
                episode_purchases={a: [p for p in purchases[a] if
                    (anchor_tick is None or p['tick'] > anchor_tick) and p['tick'] <= last] for a in SIDES},
                phase_blocks=phase_blocks(rows, steps, anchor, end))


def check_value(value):
    require(value['provenance'] == provenance() and
            all(type(value['provenance'][k]) is int for k in ('native_runs', 'training_runs')), 'wrong history provenance')
    source = inputs()
    require(value['sources'] == {a: source[a]['trace'] for a in SIDES}, 'wrong adult source coverage')
    require(value['source_sha256'] == {p: digest(ROOT / p) for p in SOURCES}, 'analysis source differs')
    require(set(value['receipt_sha256']) == set(value['rows']) == set(SIDES) and all(
        value['receipt_sha256'][a] == fingerprint(value['rows'][a]) for a in SIDES), 'selected receipt checksum differs')
    require(value['analysis'] == analyze(value['rows'], source), 'history analysis differs')


def export(bundle, out):
    require(not out.exists() and not out.is_symlink(), 'fresh output required')
    source = inputs()
    rows = extract(bundle, source)
    value = dict(provenance=provenance(), sources={a: source[a]['trace'] for a in SIDES},
                 source_sha256={p: digest(ROOT / p) for p in SOURCES}, rows=rows,
                 receipt_sha256={a: fingerprint(rows[a]) for a in SIDES}, analysis=analyze(rows, source))
    out.parent.mkdir(parents=True, exist_ok=True)
    write_gzip(out, value)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--out', type=Path, default=ROOT / 'artifacts/garden-landing-energy-history-v1.json.gz')
    mode.add_argument('--verify', type=Path)
    args = parser.parse_args(argv)
    if args.verify:
        with gzip.open(args.verify, 'rt') as stream: value = json.load(stream)
        check_value(value)
        if args.bundle:
            require(value['rows'] == extract(args.bundle, inputs()), 'raw history re-extraction differs')
        print('Verified selected energy history and accounts offline.')
    else:
        export(args.bundle or ROOT / 'artifacts/garden-landing-late-dispersal-v1', args.out)
        print('Saved selected energy history; no simulations.')


if __name__ == '__main__':
    try: main()
    except (RuntimeError, ValueError, KeyError, TypeError, OSError, IndexError, StopIteration) as error:
        print('energy history audit failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
