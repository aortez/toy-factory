#!/usr/bin/env python3
"""Offline family-loss diagnostics for the fixed population panel; no new simulations."""

import argparse
from collections import Counter
import json
from pathlib import Path
import tempfile

import collect_population as collect
import population_evidence as evidence
import population_score as score
import prepare

ARCHIVE = collect.ROOT / 'benchmarks/garden-seasons/leaf-population-results.json.gz'
ARCHIVE_SHA = '3aae48b92ed9787f9dc1601052330cdbf96ed9d72f3d845e0b9932d50112af49'
SPECIES = ('flower', 'shrub', 'ground-cover')
CAUSES = ('energy', 'water', 'combined', 'other')
PATHS = ('no-seed-purchases', 'no-offspring', 'no-established-offspring', 'established-then-lost')


def counter(values, names):
    counts = Counter(values)
    score.require(set(counts) <= set(names), 'unexpected diagnostic category')
    return {name: counts[name] for name in names}


def established(plant, stop):
    due = plant['birth_tick'] + 32 * score.DAY
    return due <= stop and (plant['death_tick'] is None or plant['death_tick'] > due)


def family_rows(value):
    score.validate_history(value)
    timeline = score.event_timeline(value)
    result = []
    for founder in range(1, score.LAYOUTS[value['scenario']] + 1):
        plants = [p for p, root in zip(value['lineages'], value['family_roots'], strict=True) if root == founder]
        seeds = [s for s in value['seeds'] if value['family_roots'][s['parent'] - 1] == founder]
        children = plants[1:]
        adults = [p for p in children if established(p, value['ticks'])]
        living = [p for p in plants if p['death_tick'] is None]
        pending = [s for s in seeds if s['outcome'] == 'pending']
        status = 'living' if living else 'dormant' if pending else 'extinct'
        extinction = next((r['tick'] for r in timeline if
            r['living_families'][founder - 1] == r['pending_families'][founder - 1] == 0), None)
        score.require((extinction is not None) == (status == 'extinct'), 'extinct family revived')
        path = None
        if status == 'extinct':
            path = ('no-seed-purchases' if not seeds else 'no-offspring' if not children else
                    'no-established-offspring' if not adults else 'established-then-lost')
        last_death = None if living else max(p['death_tick'] for p in plants)
        final_deaths, final_seeds = [], []
        if last_death is not None:
            for p in plants:
                if p['death_tick'] != last_death:
                    continue
                cause = value['death_causes'][p['id'] - 1]
                score.require(0 <= cause < len(CAUSES), 'missing final-death flags')
                final_deaths.append(dict(lineage=p['id'], tick=last_death,
                    age_ticks=last_death - p['birth_tick'], shortage_flag=CAUSES[cause],
                    # Frozen climate calendar: 16 days/year, winter days 12--15.
                    # A calendar label is not a measured cold or light blocker.
                    year_day=last_death // score.DAY % 16))
            final_seeds = [dict(s) for s in seeds if s['birth_tick'] <= last_death and
                           (s['end_tick'] is None or s['end_tick'] > last_death)]
            if status == 'extinct':
                score.require(all(s['outcome'] == 'expired' for s in final_seeds),
                              'seed germinated after final living death')
                score.require(extinction == max([last_death] + [s['end_tick'] for s in final_seeds]),
                              'terminal sequence disagrees with timeline')
        born, reached, early, young = len(children), len(adults), 0, 0
        for p in children:
            due = p['birth_tick'] + 32 * score.DAY
            early += p['death_tick'] is not None and p['death_tick'] <= due
            young += p['death_tick'] is None and due > value['ticks']
        score.require(born == reached + early + young, 'offspring outcomes do not reconcile')
        first = lambda rows, field: min((r[field] for r in rows), default=None)
        result.append(dict(founder=founder, species=SPECIES[plants[0]['species']],
            founder_column=plants[0]['column'], status=status, loss_path=path,
            founder_death_tick=plants[0]['death_tick'], first_seed_tick=first(seeds, 'birth_tick'),
            first_offspring_tick=first(children, 'birth_tick'),
            first_established_tick=min((p['birth_tick'] + 32 * score.DAY for p in adults), default=None),
            living=len(living), seed_outcomes=counter((s['outcome'] for s in seeds), ('germinated', 'expired', 'pending')),
            offspring=dict(born=born, established=reached, early_deaths=early, young_alive=young),
            last_living_death_tick=last_death, final_deaths=final_deaths,
            seeds_at_last_living_death=final_seeds, extinction_tick=extinction,
            terminal_event=('seed-expiry' if final_seeds else 'last-death') if status == 'extinct' else None,
            terminal_seed_only_ticks=extinction - last_death if status == 'extinct' else None))
    return result


def summarize(rows):
    lost = [r for r in rows if r['status'] == 'extinct']
    final_deaths = [d for r in lost for d in r['final_deaths']]
    species = {}
    for name in SPECIES:
        selected = [r for r in rows if r['species'] == name]
        species[name] = dict(founders=len(selected),
            status=counter((r['status'] for r in selected), ('living', 'dormant', 'extinct')),
            losses=counter((r['loss_path'] for r in selected if r['status'] == 'extinct'), PATHS))
    return dict(families=len(rows), status=counter((r['status'] for r in rows), ('living', 'dormant', 'extinct')),
        species=species, loss_paths=counter((r['loss_path'] for r in lost), PATHS),
        terminal_events=counter((r['terminal_event'] for r in lost), ('seed-expiry', 'last-death')),
        terminal_pending_seeds=sum(len(r['seeds_at_last_living_death']) for r in lost),
        final_death_flags=counter((d['shortage_flag'] for d in final_deaths), CAUSES),
        final_death_year_days={str(day): sum(d['year_day'] == day for d in final_deaths) for day in range(16)},
        final_winter_energy_deaths=sum(d['year_day'] >= 12 and d['shortage_flag'] == 'energy' for d in final_deaths),
        losses_by_day={str(day): sum(r['extinction_tick'] <= day * score.DAY for r in lost) for day in score.DAYS})


def panel(records):
    expected = {(m, seed, layout) for m in score.MODELS for seed in score.SEEDS for layout in score.LAYOUTS}
    score.require(set(records) == expected, 'complete 24-world roster required')
    rows = []
    for model in score.MODELS:
        for seed in score.SEEDS:
            for layout in score.LAYOUTS:
                value = records[model, seed, layout]
                score.require(value['ticks'] == 1376 * score.DAY and value['seed'] == seed and
                              value['scenario'] == layout, 'diagnostic condition differs')
                rows += [dict(model=model, seed=seed, layout=layout, **r) for r in family_rows(value)]
    summaries = {model: summarize([r for r in rows if r['model'] == model]) for model in score.MODELS}
    index = {(r['model'], r['seed'], r['layout'], r['founder']): r for r in rows}
    contrasts = {}
    for model in score.MODELS[1:]:
        groups = {k: [] for k in ('additional_losses', 'rescued', 'lost_in_both', 'retained_in_both')}
        for seed in score.SEEDS:
            for layout, founders in score.LAYOUTS.items():
                for founder in range(1, founders + 1):
                    base, other = (index[m, seed, layout, founder] for m in ('initial', model))
                    score.require((base['species'], base['founder_column']) ==
                                  (other['species'], other['founder_column']), 'paired founder differs')
                    was_lost, now_lost = base['status'] == 'extinct', other['status'] == 'extinct'
                    group = ('lost_in_both' if was_lost and now_lost else 'additional_losses' if now_lost else
                             'rescued' if was_lost else 'retained_in_both')
                    groups[group].append(dict(seed=seed, layout=layout, founder=founder,
                        species=other['species'], control_status=base['status'], candidate_status=other['status'],
                        loss_path=other['loss_path'], extinction_tick=other['extinction_tick']))
        contrasts[model] = groups
    return dict(schema='garden-population-losses-v1', native_calls=0,
                evidence_sha256=ARCHIVE_SHA, summaries=summaries, contrasts=contrasts, families=rows)


def diagnose(archive=ARCHIVE):
    score.require(prepare.sha(archive.read_bytes()) == ARCHIVE_SHA, 'population evidence identity differs')
    with tempfile.TemporaryDirectory(prefix='garden-population-losses-') as temporary:
        root = Path(temporary) / 'evidence'
        evidence.unpack(archive, root)
        records = {(c['model'], c['seed'], c['layout']): json.loads(
            (root / 'runs' / c['id'] / 'stdout.json').read_bytes())
            for c in collect.roster() if c['phase'] == 'primary'}
        result = panel(records)
        result['inputs'] = {c['id']: prepare.sha((root / 'runs' / c['id'] / 'stdout.json').read_bytes())
                           for c in collect.roster() if c['phase'] == 'primary'}
        result['frozen_runtime_archive_sha256'] = prepare.ARCHIVE_SHA
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=ARCHIVE)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--out', type=Path, help='new derived JSON; existing output is never overwritten')
    mode.add_argument('--check', type=Path, help='recompute and compare an existing derived JSON')
    args = parser.parse_args()
    result = diagnose(args.archive)
    if args.check:
        score.require(json.loads(args.check.read_bytes()) == result, 'derived loss diagnostics differ')
    else:
        collect.save(args.out, result)
    print('Verified 96 founder families in 24 worlds; zero new simulator calls.')
