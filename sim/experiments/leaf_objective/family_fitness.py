#!/usr/bin/env python3
"""Approved renewal-first family score; pure arithmetic, no search or run selection."""

from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from garden_descendants import index_records

RULE = 'garden-leaf-family-renewal-v1'
DAY, ESTABLISHMENT_DAYS, WINDOW_DAYS, CAPACITY, WINDOW_CAP = 3840, 32, 64, 8, 2


def require(ok, message):
    if not ok:
        raise ValueError(message)


def integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


@dataclass(frozen=True)
class FamilyScore:
    founder: int
    start_day: int
    window_count: int
    renewal_children: tuple[int, ...]
    established_descendant_ticks: int

    def __post_init__(self):
        require(integer(self.founder, 1, CAPACITY) and integer(self.start_day, 0, 608)
                and integer(self.window_count, 1, 9)
                and self.stop_day <= 608, 'invalid founder or scoring horizon')
        require(type(self.renewal_children) is tuple and len(self.renewal_children) == self.window_count
                and all(integer(n, 0, 4096) for n in self.renewal_children), 'invalid renewal counts')
        require(integer(self.established_descendant_ticks, 0, self.occupancy_denominator),
                'invalid descendant occupancy')

    @property
    def stop_day(self):
        return self.start_day + WINDOW_DAYS * self.window_count + ESTABLISHMENT_DAYS

    @property
    def occupancy_denominator(self):
        return CAPACITY * WINDOW_DAYS * self.window_count * DAY

    @property
    def key(self):
        # Tuple comparison gives occupancy no ability to outweigh renewal.
        return (Fraction(sum(min(WINDOW_CAP, n) for n in self.renewal_children),
                         WINDOW_CAP * self.window_count),
                Fraction(self.established_descendant_ticks, self.occupancy_denominator))

    def record(self):
        return dict(rule=RULE, founder=self.founder, start_day=self.start_day,
            window_days=WINDOW_DAYS, window_count=self.window_count, stop_day=self.stop_day,
            establishment_days=ESTABLISHMENT_DAYS, window_cap=WINDOW_CAP,
            renewal_children=list(self.renewal_children),
            established_descendant_ticks=self.established_descendant_ticks,
            key=[[part.numerator, part.denominator] for part in self.key])


def score_family(history, founder, *, start_day, window_count):
    """Score a complete validated ledger, not an authenticated replay artifact.

    The caller must separately verify model, controller routing, build identity,
    condition roles and successful execution. Shared-policy histories can be
    analyzed offline but are never thereby candidate-versus-resident evidence.
    Explicit windows avoid silently selecting a training horizon.
    """
    # Validate parameters before reading timestamps or allocating window state.
    require(integer(window_count, 1, 9), 'invalid window count')
    template = FamilyScore(founder, start_day, window_count, (0,) * window_count, 0)
    start = start_day * DAY
    end = (template.stop_day - ESTABLISHMENT_DAYS) * DAY
    stop = template.stop_day * DAY
    require(type(history) is dict and history.get('complete') is True
            and integer(history.get('ledger_start_tick'), 0, 0)
            and integer(history.get('tick'), stop, stop), 'complete exact-horizon history required')
    plants, seeds = history['lineages'], history['seeds']
    by_id, _ = index_records(plants, seeds, 0, stop)
    require(founder in by_id and by_id[founder]['parent'] == 0, 'selected founder missing')
    ordered = sorted(plants, key=lambda p: p['id'])
    require(len(plants) <= 4096 and
            [p['id'] for p in ordered] == list(range(1, len(plants) + 1)),
            'contiguous lineage identities required')
    founders = [p['id'] for p in ordered if p['parent'] == 0]
    require(founders == list(range(1, len(founders) + 1)) and
            all(a['birth_tick'] <= b['birth_tick'] for a, b in zip(ordered, ordered[1:])),
            'initial founders and chronological births required')
    roots, established, changes = {}, {}, Counter()
    for plant in ordered:
        identity, parent = plant['id'], plant['parent']
        birth, death = plant['birth_tick'], plant['death_tick']
        require(type(parent) is int and 0 <= parent < identity
                and not plant.get('environmental_death', False), 'invalid ancestry or imposed death')
        if parent == 0:
            require(birth == 0 and plant['generation'] == 0 and identity <= CAPACITY, 'invalid founder')
        else:
            require(plant['generation'] == by_id[parent]['generation'] + 1 and
                    plant['species'] == by_id[parent]['species'], 'inheritance differs')
        roots[identity] = roots[parent] if parent else identity
        due = birth + ESTABLISHMENT_DAYS * DAY
        established[identity] = due <= stop and (death is None or death > due)
        changes[birth] += 1
        if death is not None:
            changes[death] -= 1
    living = 0
    for tick in sorted(changes):
        living += changes[tick]
        require(0 <= living <= CAPACITY, 'living population exceeds fixed capacity')
    counts = [0] * window_count
    occupied = 0
    for plant in ordered:
        identity, parent = plant['id'], plant['parent']
        if roots[identity] != founder or parent == 0 or not established[identity]:
            continue
        birth, death = plant['birth_tick'], plant['death_tick']
        first = max(start + 1, birth + ESTABLISHMENT_DAYS * DAY)
        last = min(end, death - 1 if death is not None else end)
        occupied += max(0, last - first + 1)
        if start < birth <= end and by_id[parent]['parent'] != 0 and established[parent]:
            window = (birth - start - 1) // (WINDOW_DAYS * DAY)
            counts[window] += 1
    return FamilyScore(founder, start_day, window_count, tuple(counts), occupied)


def aggregate(matches, *, expected_roles):
    """Equal condition weights, equal founder weights within each condition.

    expected_roles is a predeclared condition -> tuple of all initial founder IDs.
    Missing/extinct families may not be omitted. This returns a lexicographic
    pair of exact fractions; it does not set selection rules or model tie order.
    """
    require(type(matches) is dict and type(expected_roles) is dict and expected_roles
            and set(matches) == set(expected_roles),
            'missing or extra conditions')
    total = [Fraction(0), Fraction(0)]
    profile = None
    for condition, roles in expected_roles.items():
        require(type(roles) is tuple and roles and
                all(integer(role, 1, CAPACITY) for role in roles) and
                set(roles) == set(range(1, len(roles) + 1)) and len(set(roles)) == len(roles),
                'complete founder roster required')
        require(type(matches[condition]) is dict and
                all(integer(role, 1, CAPACITY) for role in matches[condition]) and
                set(matches[condition]) == set(roles), 'missing or extra founder role')
        for founder in roles:
            score = matches[condition][founder]
            require(type(score) is FamilyScore and score.founder == founder, 'score identity differs')
            current = (score.start_day, score.window_count)
            if profile is None:
                profile = current
            require(current == profile, 'mixed scoring windows')
            for axis, value in enumerate(score.key):
                total[axis] += value / len(roles) / len(expected_roles)
    return tuple(total)
