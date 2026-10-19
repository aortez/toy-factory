#!/usr/bin/env python3
"""Offline repair selection and gate decisions on authenticated foliage snapshots."""

import argparse
from collections import Counter
import json
from pathlib import Path
import tempfile

import population_exposure as exposure
import population_gates as gates

foliage = exposure.foliage
collect, prepare, score, shadow = exposure.collect, exposure.prepare, exposure.score, gates.shadow
ARCHIVE, ARCHIVE_SHA = exposure.ARCHIVE, exposure.ARCHIVE_SHA
MODEL_SHA = '5e474190b02fb0d5d66ca58b391cae8961062aefbbc6617bafa7cc4d1ad4c51a'
PERIODS = (('before_dawn', foliage.FIRST, foliage.DAWN),
           ('dawn', foliage.DAWN, foliage.OPENING),
           ('after_opening', foliage.OPENING, foliage.END))
COUNTS = ('samples', 'productive', 'light_pass', 'condition_pass', 'would_renew', 'selected',
          'selected_productive', 'selected_light_pass', 'selected_would_renew', 'renewals',
          'unselected_would_renew', 'zero_condition', 'selected_zero_condition',
          'wait_light_only', 'wait_condition_only', 'wait_both', 'renewal_rejected')


def decision_model(raw):
    model = shadow.decode(raw)
    _, output_shift, _, weights, biases, outputs = model
    # Only two hidden units reach the output. Missing water/base/upkeep inputs
    # can be ignored only after proving that they cannot influence these units.
    score.require(output_shift == 6 and biases == (0, 64) and
                  outputs == (0,) * 8 + (-64, -64) + (0,) * 6, 'unsupported decision output')
    score.require(weights[1] < 0 and weights[11] > 0 and
                  all(weights[i] == 0 for i in range(11) if i not in (1, 4, 10)) and
                  all(weights[11 + i] == 0 for i in range(1, 11)),
                  'unrecorded input or coupled decision gate')
    return model


def evaluate(model, condition, light, count):
    score.require(score.integer(condition, 0, 255) and score.integer(light, 0, 255) and
                  score.integer(count, 1, 32), 'invalid decision inputs')
    # Zeros below are algebraically irrelevant placeholders, not claimed
    # observations of water, relative geometry, energy, or maintenance costs.
    inputs = [condition, light, 0, 0, count, 0, 0, 0, 0, 9, 5]
    _, hidden, scores = shadow.network(model, inputs)
    light_pass, condition_pass = hidden[0] == 0, hidden[1] == 0
    action = int(scores[1] > scores[0])
    score.require(action == int(light_pass and condition_pass) and
                  scores == [0, 1 - hidden[0] - hidden[1]], 'gate decomposition differs')
    return dict(action=action, light_hidden=hidden[0], condition_hidden=hidden[1],
                light_pass=light_pass, condition_pass=condition_pass, scores=scores)


def thresholds(model, count):
    light = [v for v in range(256) if evaluate(model, 0, v, count)['light_pass']]
    condition = [v for v in range(256) if evaluate(model, v, 255, count)['condition_pass']]
    score.require(light and condition and light == list(range(light[0], 256)) and
                  condition == list(range(condition[-1] + 1)), 'unsupported gate thresholds')
    return dict(light_minimum=light[0], condition_maximum=condition[-1])


def windows(ticks):
    """Inclusive, chronological tick intervals; never wrap afternoon into morning."""
    result = []
    for tick in ticks:
        score.require(score.integer(tick, foliage.FIRST + 15, foliage.END) and tick % 15 == 0 and
                      (not result or tick > result[-1]['last_tick']), 'invalid window order')
        if result and tick == result[-1]['last_tick'] + 15:
            result[-1]['last_tick'] = tick
            result[-1]['steps'] += 1
        else:
            result.append(dict(first_tick=tick, last_tick=tick, steps=1))
    return result


def summarize(samples):
    result = {key: sum(s[key] for s in samples) for key in COUNTS}
    result['selected_energy_minimum'] = min((s['energy'] for s in samples if s['selected']), default=None)
    result['selected_energy_shortages'] = sum(s['selected'] and s['energy'] < 9 for s in samples)
    score.require(result['selected'] == result['selected_would_renew'] + result['wait_light_only'] +
                  result['wait_condition_only'] + result['wait_both'] and
                  result['selected_would_renew'] == result['renewals'] + result['renewal_rejected'] and
                  result['would_renew'] == result['selected_would_renew'] + result['unselected_would_renew'],
                  'opportunity counts do not reconcile')
    return result


def classify(samples):
    """Why a leaf had no accepted repair within this recorded day, not its lifetime."""
    if any(s['renewals'] for s in samples):
        return 'renewed'
    if not any(s['light_pass'] for s in samples):
        return 'never_reaches_light_gate'
    if not any(s['would_renew'] for s in samples):
        return 'no_joint_gate_window'
    if not any(s['selected_would_renew'] for s in samples):
        return 'joint_gate_windows_not_selected'
    return 'requested_but_not_accepted'


def attribute(data, raw_model):
    """Input trace is fully ledger-validated by diagnose; enforce all new joins here."""
    model = decision_model(raw_model)
    lineage = data['lineage']
    rows = data['rows']
    score.require([r['tick'] for r in rows] == foliage.TICKS and
                  all(r['phase'] == (r['tick'] // 15 + 64) % 256 for r in rows), 'opportunity coverage differs')
    positions = [f[1:5] for f in rows[0]['leaves']]
    count = len(positions)
    score.require((lineage, count) in foliage.TARGETS.values() and
                  all([f[1:5] for f in r['leaves']] == positions for r in rows), 'opportunity body differs')
    limits = thresholds(model, count)
    samples, decisions = [], []
    for row in rows:
        tick = row['tick']
        nodes = [f[0] for f in row['leaves']]
        score.require(nodes == sorted(set(nodes)) and row['selected'] in nodes, 'invalid selected leaf')
        selected = nodes.index(row['selected'])
        score.require(selected == (tick // 15 + lineage) % count, 'round-robin selection differs')
        score.require(score.integer(row['action'], 0, 1) and score.integer(row['renewals'], 0, row['action']),
                      'invalid action or renewal')
        energy = row['energy']['points'][3]  # After germination, before focal repair/growth.
        score.require(score.integer(energy, 0, 256), 'invalid pre-repair energy')
        for ordinal, f in enumerate(row['leaves']):
            light, condition = f[5:7]
            decision = evaluate(model, condition, light, count)
            light_pass, condition_pass = decision['light_pass'], decision['condition_pass']
            score.require(light_pass == (light >= limits['light_minimum']) and
                          condition_pass == (condition <= limits['condition_maximum']), 'threshold differs')
            chosen = ordinal == selected
            accepted = chosen and row['renewals'] == 1
            would = decision['action'] == 1
            s = dict(tick=tick, ordinal=ordinal, row=f[4], light=light, condition=condition, energy=energy,
                samples=1, productive=int(light >= 64), light_pass=int(light_pass), condition_pass=int(condition_pass),
                would_renew=int(would), selected=int(chosen), selected_productive=int(chosen and light >= 64),
                selected_light_pass=int(chosen and light_pass), selected_would_renew=int(chosen and would),
                renewals=int(accepted), unselected_would_renew=int(not chosen and would),
                zero_condition=int(condition == 0), selected_zero_condition=int(chosen and condition == 0),
                wait_light_only=int(chosen and not light_pass and condition_pass),
                wait_condition_only=int(chosen and light_pass and not condition_pass),
                wait_both=int(chosen and not light_pass and not condition_pass),
                renewal_rejected=int(chosen and would and not accepted))
            samples.append(s)
            if chosen:
                score.require(decision['action'] == row['action'], 'recorded controller decision differs')
                score.require(not accepted or energy >= 9, 'accepted renewal lacks energy')
                decisions.append(dict(tick=tick, phase=row['phase'], ordinal=ordinal, node=f[0],
                    row=f[4], column=f[3], condition=condition, light=light, energy=energy,
                    **decision, renewed=accepted, restored=row['restored']))
    leaves = []
    for ordinal, (x, y, column, row) in enumerate(positions):
        group = [s for s in samples if s['ordinal'] == ordinal]
        final = group[-1]
        leaves.append(dict(ordinal=ordinal, x=x, y=y, column=column, row=row,
            first_condition=group[0]['condition'], final_condition=255 if final['renewals'] else final['condition'],
            zero_all_day=all(s['condition'] == 0 and not s['renewals'] for s in group),
            maximum_light=max(s['light'] for s in group),
            maximum_selected_light=max(s['light'] for s in group if s['selected']),
            selected_ticks=[s['tick'] for s in group if s['selected']],
            productive_windows=windows([s['tick'] for s in group if s['productive']]),
            light_gate_windows=windows([s['tick'] for s in group if s['light_pass']]),
            joint_gate_windows=windows([s['tick'] for s in group if s['would_renew']]),
            outcome=classify(group), day=summarize(group)))
    heights = {}
    for label, lo, hi in (('upper', 0, 7), ('lower', 7, 14)):
        group = [s for s in samples if lo <= s['row'] < hi]
        body = [leaf for leaf in leaves if lo <= leaf['row'] < hi]
        heights[label] = dict(leaves=len(body), day=summarize(group),
            outcomes=dict(sorted(Counter(leaf['outcome'] for leaf in body).items())),
            zero_all_day=[leaf['ordinal'] for leaf in body if leaf['zero_all_day']],
            periods={label: summarize([s for s in group if first < s['tick'] <= last])
                     for label, first, last in PERIODS})
    total = summarize(samples)
    score.require(total['renewals'] == sum(r['renewals'] for r in rows) and
                  total['selected'] == len(decisions) == 256 and all(
                      total[k] == sum(l['day'][k] for l in leaves) ==
                      sum(h['day'][k] for h in heights.values()) for k in COUNTS), 'spatial totals differ')
    return dict(lineage=lineage, leaf_count=count, thresholds=limits, day=total,
                heights=heights, leaves=leaves, decisions=decisions)


def diagnose():
    score.require(prepare.sha(ARCHIVE.read_bytes()) == ARCHIVE_SHA, 'foliage archive identity differs')
    cases, inputs = {}, {}
    _, models, _ = collect.archive_inputs()
    raw_model = gates.derive(models, 'condition')
    score.require(prepare.sha(raw_model) == MODEL_SHA, 'repair model identity differs')
    with tempfile.TemporaryDirectory(prefix='garden-repair-opportunities-') as directory:
        root = Path(directory) / 'evidence'
        verified = foliage.follow.unpack(ARCHIVE, root, experiment=foliage.EXPERIMENT)
        for policy in foliage.TARGETS:
            prefix = f'runs/9a903368-condition-{policy}-on/'
            final_raw = (root / (prefix + 'stdout.json')).read_bytes()
            final = json.loads(final_raw)
            score.require(final['intervention']['leaf_model_hex'] == raw_model.hex(), 'applied model differs')
            name = prefix + 'timeline/foliage.json'
            raw = (root / name).read_bytes()
            inputs[name] = prepare.sha(raw)
            inputs[prefix + 'stdout.json'] = prepare.sha(final_raw)
            cases[policy] = attribute(json.loads(raw), raw_model)
            score.require(cases[policy]['day']['renewals'] == verified['analyses'][policy]['day']['renewals'],
                          'archived daily renewals differ')
    return dict(schema='garden-repair-opportunities-v1', native_calls=0, foliage_archive_sha256=ARCHIVE_SHA,
        model_sha256=MODEL_SHA, model_hex=raw_model.hex(), inputs=inputs, seed=foliage.fallback.SEED,
        first_tick_exclusive=foliage.FIRST, end_tick=foliage.END,
        periods=[dict(name=label, first_tick_exclusive=first, end_tick=last) for label, first, last in PERIODS],
        cases=cases)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--out', type=Path, help='new derived JSON; never overwrite')
    mode.add_argument('--check', type=Path, help='verify an existing derivation')
    args = parser.parse_args()
    result = diagnose()
    if args.check:
        score.require(json.loads(args.check.read_bytes()) == result, 'repair opportunity derivation differs')
    else:
        collect.save(args.out, result)
    print('Verified 512 actual decisions and 12800 leaf snapshots; zero native calls.')
