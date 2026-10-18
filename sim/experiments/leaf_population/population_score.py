"""Population diagnostics and unchanged renewal arithmetic; no model selection."""

from collections import Counter, defaultdict
from fractions import Fraction
import struct

DAY, STEP, CAPACITY, SEED_CAPACITY = 3840, 15, 8, 16
DAYS = (0, 32, 192, 608, 992, 1376)
PERIODS = (192, 576, 960)
SEEDS = ('58d7d6ca', '9a903368', '6b9c1a3e', '59818bc3')
LAYOUTS = {'rainfed': 3, 'rainfed-crowded': 5}
MODELS = ('initial', 's1-g3-c4', 's2-g3-c1')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, low, high):
    return type(value) is int and low <= value <= high


def rational(value):
    return [value.numerator, value.denominator]


def validate_history(value):
    end = value['ticks']
    require(value.get('complete') is True and value.get('ledger_start_tick') == 0 and
            integer(end, 0, 1376 * DAY) and end % STEP == 0, 'invalid history horizon')
    plants, seeds = value['lineages'], value['seeds']
    founders = LAYOUTS[value['scenario']]
    require(founders <= len(plants) <= 4096 and len(seeds) <= 65536, 'invalid ledger size')
    require([p['id'] for p in plants] == list(range(1, len(plants) + 1)), 'lineage order differs')
    require(len(value['death_causes']) == len(plants), 'death roster differs')
    by_id, roots = {}, []
    previous_birth = 0
    for p, cause in zip(plants, value['death_causes'], strict=True):
        identity, parent, birth, death = (p[k] for k in ('id', 'parent', 'birth_tick', 'death_tick'))
        require(integer(identity, 1, 4096) and integer(parent, 0, identity - 1) and
                integer(birth, previous_birth, end) and birth % STEP == 0 and
                (death is None or integer(death, birth, end) and death % STEP == 0),
                'invalid identity or lifetime')
        require(p.get('environmental_death') is False and integer(cause, 0, 4) and
                (cause == 4) == (death is None), 'invalid/imposed death')
        require(integer(p['species'], 0, 2) and integer(p['column'], 0, 27) and
                integer(p['generation'], 0, 65535), 'invalid plant traits')
        if parent:
            require(identity > founders and by_id[parent]['birth_tick'] < birth and
                    p['species'] == by_id[parent]['species'] and
                    p['generation'] == by_id[parent]['generation'] + 1, 'inheritance differs')
            root = roots[parent - 1]
        else:
            require(identity <= founders and birth == 0 and p['generation'] == 0, 'invalid founder')
            root = identity
        roots.append(root)
        by_id[identity] = p
        previous_birth = birth
    require(roots == value['family_roots'], 'ancestry ledger differs')
    seen, children, purchases = set(), set(), Counter()
    for s in seeds:
        parent, birth, finish = s['parent'], s['birth_tick'], s['end_tick']
        require(integer(parent, 1, len(plants)) and integer(birth, STEP, end) and
                birth % STEP == 0 and (parent, birth) not in seen, 'invalid/duplicate seed')
        seen.add((parent, birth))
        p = by_id[parent]
        require(p['birth_tick'] <= birth and (p['death_tick'] is None or p['death_tick'] > birth),
                'seed purchased by a dead/unborn parent')
        require(integer(s['lifetime_ecology_ticks'], 9, 65535) and
                s['generation'] == p['generation'] + 1 and s['species'] == p['species'] and
                integer(s['column'], 0, 27), 'invalid seed traits')
        expiry = birth + s['lifetime_ecology_ticks'] * STEP
        if s['outcome'] == 'pending':
            require(finish is None and s['child_id'] is None and expiry > end, 'invalid pending seed')
        else:
            require(integer(finish, birth + STEP, min(expiry, end)) and finish % STEP == 0,
                    'invalid seed endpoint')
            if s['outcome'] == 'expired':
                require(finish == expiry and s['child_id'] is None, 'invalid expiry')
            else:
                child = s['child_id']
                require(s['outcome'] == 'germinated' and integer(child, 1, len(plants)) and
                        child not in children and birth + 8 * STEP <= finish < expiry,
                        'invalid/duplicate germination')
                c = by_id[child]
                require(c['parent'] == parent and c['birth_tick'] == finish and
                        all(c[k] == s[k] for k in ('column', 'generation', 'species')),
                        'seed and child differ')
                children.add(child)
        purchases[parent] += 1
    require(children == {p['id'] for p in plants if p['parent']}, 'unmatched child birth')
    require(all(p['seeds_created'] == p['late_seeds_created'] == purchases[p['id']] for p in plants),
            'purchase totals differ')
    return by_id


def validate_record(value, model_bytes, *, seed, layout, ticks, uniform_bytes):
    require(value['schema'] == 'garden-leaf-population-replay-v1' and
            value['controller_assignment'] == 'whole-population' and
            value['candidate_founder'] is None and value['resident_policy'] is None and
            value['objective'] is None and value['gardener'] is False and
            value['climate'] == 'seasonal' and value['seed'] == seed and
            value['scenario'] == layout and value['ticks'] == ticks, 'run conditions differ')
    require(value['growth_model_sha256'] ==
            'f2dc989380339614dc512f64f11f2bf03f7079c465c4c9bd18895044ec3e1567' and
            bytes.fromhex(value['leaf_model_hex']) == model_bytes, 'model identity differs')
    validate_history(value)
    state = bytes.fromhex(value['state_hex'])
    count = len(value['lineages'])
    require(len(state) == 12 + count + uniform_bytes and
            state[:8] == b'TPR1\0\0' + bytes((LAYOUTS[layout], 0)) and
            struct.unpack_from('<I', state, 8)[0] == count and
            list(state[12:12 + count]) == value['family_roots'] and
            state[12 + count:16 + count] == b'TLR1' and
            state[16 + count:16 + count + len(model_bytes)] == model_bytes,
            'canonical population envelope differs')


def history_prefix(value, tick):
    require(integer(tick, 0, value['ticks']) and tick % STEP == 0, 'invalid history cutoff')
    seeds = []
    for s in value['seeds']:
        if s['birth_tick'] <= tick:
            seed = dict(s)
            if seed['end_tick'] is not None and seed['end_tick'] > tick:
                seed.update(end_tick=None, child_id=None, outcome='pending')
            seeds.append(seed)
    purchases = Counter(s['parent'] for s in seeds)
    plants, causes = [], []
    for p, cause in zip(value['lineages'], value['death_causes'], strict=True):
        if p['birth_tick'] <= tick:
            plant = p | dict(seeds_created=purchases[p['id']], late_seeds_created=purchases[p['id']])
            if plant['death_tick'] is not None and plant['death_tick'] > tick:
                plant['death_tick'], cause = None, 4
            plants.append(plant)
            causes.append(cause)
    return dict(lineages=plants, seeds=seeds, death_causes=causes,
                family_roots=value['family_roots'][:len(plants)])


def family_score(value, founder, start_day):
    """Same six-window arithmetic as durability_score.score, on a complete history."""
    require(start_day in PERIODS and integer(founder, 1, LAYOUTS[value['scenario']]) and
            value['ticks'] >= (start_day + 416) * DAY, 'invalid scoring window')
    plants = value['lineages']
    stop, start, end = (start_day + 416) * DAY, start_day * DAY, (start_day + 384) * DAY
    established = {p['id']: p['birth_tick'] + 32 * DAY <= stop and
                   (p['death_tick'] is None or p['death_tick'] > p['birth_tick'] + 32 * DAY)
                   for p in plants}
    counts, occupied = [0] * 6, 0
    for p, root in zip(plants, value['family_roots'], strict=True):
        if root != founder or not p['parent'] or not established[p['id']]:
            continue
        birth, death = p['birth_tick'], p['death_tick']
        occupied += max(0, min(end, death - 1 if death is not None else end) -
                        max(start + 1, birth + 32 * DAY) + 1)
        if start < birth <= end and plants[p['parent'] - 1]['parent'] and established[p['parent']]:
            counts[(birth - start - 1) // (64 * DAY)] += 1
    return dict(rule='garden-leaf-family-renewal-v1', founder=founder, start_day=start_day,
        window_days=64, window_count=6, stop_day=start_day + 416, establishment_days=32,
        window_cap=2, renewal_children=counts, established_descendant_ticks=occupied,
        key=[rational(Fraction(sum(min(2, n) for n in counts), 12)),
             rational(Fraction(occupied, CAPACITY * 384 * DAY))])


def event_timeline(value):
    """Counts after each event tick; simultaneous deaths/germinations are atomic."""
    events = defaultdict(list)
    events[0] = []
    events.setdefault(value['ticks'], [])
    for p, root in zip(value['lineages'], value['family_roots'], strict=True):
        events[p['birth_tick']].append(('living', root - 1, p['species'], 1))
        if p['death_tick'] is not None:
            events[p['death_tick']].append(('living', root - 1, p['species'], -1))
    for s in value['seeds']:
        root = value['family_roots'][s['parent'] - 1]
        events[s['birth_tick']].append(('pending', root - 1, s['species'], 1))
        if s['end_tick'] is not None:
            events[s['end_tick']].append(('pending', root - 1, s['species'], -1))
    families = {k: [0] * LAYOUTS[value['scenario']] for k in ('living', 'pending')}
    species = {k: [0] * 3 for k in families}
    rows = []
    for tick, changes in sorted(events.items()):
        for kind, root, species_id, change in changes:
            families[kind][root] += change
            species[kind][species_id] += change
        require(all(n >= 0 for counts in families.values() for n in counts) and
                sum(families['living']) <= CAPACITY and sum(families['pending']) <= SEED_CAPACITY,
                'population/seed capacity accounting differs')
        rows.append(dict(tick=tick, living=sum(families['living']), pending=sum(families['pending']),
            living_families=list(families['living']), pending_families=list(families['pending']),
            living_species=list(species['living']), pending_species=list(species['pending'])))
    return rows


def demographic(value, tick, events):
    row = next(r for r in reversed(events) if r['tick'] <= tick)
    descendants = [p for p in value['lineages'] if p['parent'] and p['birth_tick'] <= tick]
    established = [p for p in descendants if p['birth_tick'] + 32 * DAY <= tick and
                   (p['death_tick'] is None or p['death_tick'] > p['birth_tick'] + 32 * DAY)]
    living = lambda p: p['death_tick'] is None or p['death_tick'] > tick
    return row | dict(tick=tick, offspring_born=len(descendants), established_offspring=len(established),
        established_offspring_living=sum(living(p) for p in established),
        young_alive=sum(living(p) and p['birth_tick'] + 32 * DAY > tick for p in descendants),
        died_before_establishment=sum(p['death_tick'] is not None and p['death_tick'] <= tick and
            p['death_tick'] <= p['birth_tick'] + 32 * DAY for p in descendants),
        deaths=sum(p['death_tick'] is not None and p['death_tick'] <= tick for p in value['lineages']),
        family_status=['living' if live else 'dormant' if seed else 'extinct'
                       for live, seed in zip(row['living_families'], row['pending_families'], strict=True)])


def analyze_world(value):
    validate_history(value)
    require(value['ticks'] == 1376 * DAY, 'full comparison horizon required')
    timeline = event_timeline(value)
    empty = []
    for i, row in enumerate(timeline):
        until = timeline[i + 1]['tick'] if i + 1 < len(timeline) else value['ticks'] + 1
        if row['living'] == 0:
            if empty and empty[-1]['until_exclusive'] == row['tick']:
                empty[-1]['until_exclusive'] = until
            else:
                empty.append(dict(start_inclusive=row['tick'], until_exclusive=until))
    periods = {}
    for start in PERIODS:
        scores = [family_score(value, f, start) for f in range(1, LAYOUTS[value['scenario']] + 1)]
        periods[str(start)] = dict(families=scores,
            key=[rational(sum((Fraction(*s['key'][axis]) for s in scores), Fraction()) / len(scores))
                 for axis in range(2)],
            raw_qualifying_children=sum(sum(s['renewal_children']) for s in scores),
            closing_window_families=sum(s['renewal_children'][-1] > 0 for s in scores))
    return dict(periods=periods, checkpoints={str(d): demographic(value, d * DAY, timeline) for d in DAYS},
        timeline=timeline, empty_living_intervals=empty,
        extinction_tick=next((r['tick'] for r in timeline if r['living'] == r['pending'] == 0), None))


def aggregate(worlds):
    expected = {(model, seed, layout) for model in MODELS for seed in SEEDS for layout in LAYOUTS}
    require(set(worlds) == expected, 'incomplete/duplicate population panel')
    result = {}
    for model in MODELS:
        selected = [worlds[model, seed, layout] for seed in SEEDS for layout in LAYOUTS]
        periods = {}
        for start in PERIODS:
            periods[str(start)] = dict(
                key=[rational(sum((Fraction(*w['periods'][str(start)]['key'][axis]) for w in selected),
                                  Fraction()) / len(selected)) for axis in range(2)],
                seed_renewal={seed: rational(sum((Fraction(*worlds[model, seed, layout]['periods'][str(start)]['key'][0])
                    for layout in LAYOUTS), Fraction()) / len(LAYOUTS)) for seed in SEEDS},
                closing_window_families=sum(w['periods'][str(start)]['closing_window_families'] for w in selected))
        last = [w['checkpoints']['1376'] for w in selected]
        result[model] = dict(periods=periods, living=sum(r['living'] for r in last),
            pending=sum(r['pending'] for r in last),
            extinct_worlds=sum(w['extinction_tick'] is not None for w in selected),
            empty_living_worlds=sum(bool(w['empty_living_intervals']) for w in selected),
            extinct_families=sum(r['family_status'].count('extinct') for r in last),
            dormant_families=sum(r['family_status'].count('dormant') for r in last),
            retained_species=[sum(a + b > 0 for a, b in zip(r['living_species'], r['pending_species'], strict=True))
                              for r in last])
    return result
