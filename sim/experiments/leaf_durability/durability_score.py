"""The same renewal arithmetic on explicit later windows; no model selection."""

from collections import Counter
from fractions import Fraction

import build_durability as build
from garden_descendants import index_records

pilot, previous = build.pilot, build.previous
require, DAY = build.require, pilot.DAY
PERIODS = (192, 576, 960)
WINDOWS, WINDOW_DAYS, FOLLOWUP, CAPACITY, CAP = 6, 64, 32, 8, 2


def prefix(value, days):
    """Return histories only, censoring future events without inventing world state."""
    require(type(days) is int and 0 < days <= build.DAYS and days * DAY <= value['ticks'],
            'invalid history cutoff')
    end = days * DAY
    seeds = []
    for record in value['seeds']:
        if record['birth_tick'] <= end:
            seed = dict(record)
            if seed['end_tick'] is not None and seed['end_tick'] > end:
                seed.update(end_tick=None, child_id=None, outcome='pending')
            seeds.append(seed)
    counts = Counter(s['parent'] for s in seeds)
    plants, causes = [], []
    for record, cause in zip(value['lineages'], value['death_causes'], strict=True):
        require(type(cause) is int and 0 <= cause <= 4 and
                (cause == 4) == (record['death_tick'] is None), 'invalid death cause')
        if record['birth_tick'] <= end:
            plant = record | dict(seeds_created=counts[record['id']], late_seeds_created=counts[record['id']])
            if plant['death_tick'] is not None and plant['death_tick'] > end:
                plant.update(death_tick=None, environmental_death=False)
            causes.append(4 if plant['death_tick'] is None else cause)
            plants.append(plant)
    result = {k: value[k] for k in ('complete', 'ledger_start_tick', 'seed', 'scenario', 'candidate_founder')}
    result.update(ticks=end, tick=end, lineages=plants, seeds=seeds, death_causes=causes,
                  family_roots=value['family_roots'][:len(plants)])
    index_records(plants, seeds, 0, end)
    return result


def score(value, founder, start_day):
    require(type(start_day) is int and start_day in PERIODS and type(founder) is int and
            1 <= founder <= CAPACITY, 'invalid scoring profile')
    stop_day = start_day + WINDOW_DAYS * WINDOWS + FOLLOWUP
    require(value.get('complete') is True and type(value.get('ledger_start_tick')) is int and
            value['ledger_start_tick'] == 0 and value['ticks'] == stop_day * DAY,
            'complete exact-horizon history required')
    by_id, _ = index_records(value['lineages'], value['seeds'], 0, value['ticks'])
    ordered = sorted(value['lineages'], key=lambda p: p['id'])
    require(founder in by_id and by_id[founder]['parent'] == 0 and len(ordered) <= 4096 and
            [p['id'] for p in ordered] == list(range(1, len(ordered) + 1)), 'invalid founder/identities')
    founders = [p['id'] for p in ordered if p['parent'] == 0]
    require(founders == list(range(1, len(founders) + 1)) and
            all(a['birth_tick'] <= b['birth_tick'] for a, b in zip(ordered, ordered[1:])),
            'initial founders and chronological births required')
    roots, established, changes = {}, {}, Counter()
    for plant in ordered:
        identity, parent = plant['id'], plant['parent']
        birth, death = plant['birth_tick'], plant['death_tick']
        require(type(parent) is int and 0 <= parent < identity and
                not plant.get('environmental_death', False), 'invalid ancestry or imposed death')
        if parent == 0:
            require(birth == 0 and plant['generation'] == 0 and identity <= CAPACITY, 'invalid founder')
        else:
            require(plant['generation'] == by_id[parent]['generation'] + 1 and
                    plant['species'] == by_id[parent]['species'], 'inheritance differs')
        roots[identity] = roots[parent] if parent else identity
        due = birth + FOLLOWUP * DAY
        established[identity] = due <= value['ticks'] and (death is None or death > due)
        changes[birth] += 1
        if death is not None:
            changes[death] -= 1
    require(value['family_roots'] == [roots[i] for i in range(1, len(ordered) + 1)], 'family roots differ')
    living = 0
    for tick in sorted(changes):
        living += changes[tick]
        require(0 <= living <= CAPACITY, 'living population exceeds fixed capacity')
    start, end = start_day * DAY, (stop_day - FOLLOWUP) * DAY
    counts, occupied = [0] * WINDOWS, 0
    for plant in ordered:
        identity, parent = plant['id'], plant['parent']
        if roots[identity] != founder or parent == 0 or not established[identity]:
            continue
        birth, death = plant['birth_tick'], plant['death_tick']
        first = max(start + 1, birth + FOLLOWUP * DAY)
        last = min(end, death - 1 if death is not None else end)
        occupied += max(0, last - first + 1)
        if start < birth <= end and by_id[parent]['parent'] != 0 and established[parent]:
            counts[(birth - start - 1) // (WINDOW_DAYS * DAY)] += 1
    denominator = CAPACITY * WINDOW_DAYS * WINDOWS * DAY
    require(0 <= occupied <= denominator, 'invalid descendant occupancy')
    return dict(rule='garden-leaf-family-renewal-v1', founder=founder, start_day=start_day,
        window_days=WINDOW_DAYS, window_count=WINDOWS, stop_day=stop_day, establishment_days=FOLLOWUP,
        window_cap=CAP, renewal_children=counts, established_descendant_ticks=occupied,
        key=pilot.controls.rational_key((Fraction(sum(min(CAP, n) for n in counts), CAP * WINDOWS),
                                        Fraction(occupied, denominator))))


def panel(values, start_day):
    expected = pilot.roles(previous.SEEDS)
    require([(v['seed'], v['scenario'], v['candidate_founder']) for v in values] == expected,
            'incomplete/incorrect scoring roster')
    endpoint = start_day + WINDOWS * WINDOW_DAYS + FOLLOWUP
    total, matches, conditions, weighted_extinction = [Fraction(0), Fraction(0)], [], {}, Fraction(0)
    for value, (seed, layout, founder) in zip(values, expected):
        censored = prefix(value, endpoint)
        result = score(censored, founder, start_day)
        status = previous.family_status(censored)
        condition = seed + '-' + layout
        count = dict(pilot.LAYOUTS)[layout]
        condition_key = conditions.setdefault(condition, [Fraction(0), Fraction(0)])
        weight = Fraction(1, count * len(previous.SEEDS) * len(pilot.LAYOUTS))
        for axis in range(2):
            total[axis] += Fraction(*result['key'][axis]) * weight
            condition_key[axis] += Fraction(*result['key'][axis]) / count
        weighted_extinction += status['extinct'] * weight
        matches.append(dict(seed=seed, layout=layout, founder=founder, score=result, status=status))
    return dict(key=pilot.controls.rational_key(total), matches=matches,
        conditions={k: pilot.controls.rational_key(v) for k, v in conditions.items()},
        roles_with_renewal=sum(any(m['score']['renewal_children']) for m in matches),
        closing_window_families=sum(m['score']['renewal_children'][-1] > 0 for m in matches),
        every_window_families=sum(all(m['score']['renewal_children']) for m in matches),
        window_families=[sum(m['score']['renewal_children'][i] > 0 for m in matches) for i in range(WINDOWS)],
        living_families=sum(m['status']['living'] > 0 for m in matches),
        dormant_families=sum(m['status']['dormant'] for m in matches),
        extinct_families=sum(m['status']['extinct'] for m in matches),
        weighted_extinction=previous.rational(weighted_extinction))
