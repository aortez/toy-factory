#!/usr/bin/env python3
"""Executable design sketch, not a simulation observer or a neural ABI.

The proposed sensor receives only a contemporaneous terrain sample. It keeps
causal, column-anchored traces and projects them through a declared dispersal
rule. No world, plant IDs, RNG state, future weather or outcomes are inputs.
"""

from dataclasses import dataclass

COLUMNS = 28
DAY = 256
MAX_Q = 255 * 256
LIVE, DEAD = 1, 2
VERSION = 1
FIELDS = ("space_free", "dead_only", "water_now", "light_now", "wet_ema", "light_ema",
          "wet_light_ema", "open_wet_light_ema")
RULES = {"narrow-v1": (5, 3), "wide-v1": (3, 7)}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def byte_vector(values):
    return isinstance(values, tuple) and len(values) == COLUMNS and all(
        type(v) is int and 0 <= v <= 255 for v in values)


@dataclass(frozen=True)
class Terrain:
    water: tuple[int, ...]
    light: tuple[int, ...]
    occupied: tuple[int, ...]

    def __post_init__(self):
        require(byte_vector(self.water) and byte_vector(self.light) and byte_vector(self.occupied) and
                all(v <= LIVE | DEAD for v in self.occupied), "Invalid terrain sample")


def terrain(water, light, plants):
    """Plants are (base column, dead) pairs; dead slots remain occupied."""
    require(len(plants) <= 8 and all(len(p) == 2 and type(p[0]) is int and 0 <= p[0] < COLUMNS and
            type(p[1]) is bool for p in plants), "Invalid occupied plant slots")
    occupied = []
    for c in range(COLUMNS):
        mask = 0
        for base, dead in plants:
            if abs(c - base) < 3:
                mask |= DEAD if dead else LIVE
        occupied.append(mask)
    return Terrain(tuple(water), tuple(light), tuple(occupied))


@dataclass(frozen=True)
class History:
    tick: int
    samples: int
    current: Terrain
    traces: tuple[tuple[int, ...], ...]

    def __post_init__(self):
        require(type(self.tick) is int and 0 <= self.tick <= 0xffffffff and
                type(self.samples) is int and self.samples == min(self.tick, DAY) and
                isinstance(self.current, Terrain) and isinstance(self.traces, tuple) and len(self.traces) == 4 and
                all(isinstance(row, tuple) and len(row) == COLUMNS and
                    all(type(q) is int and 0 <= q <= MAX_Q for q in row) for row in self.traces),
                "Invalid history state")


def reset(initial):
    require(isinstance(initial, Terrain), "Invalid initial terrain")
    return History(0, 0, initial, ((0,) * COLUMNS,) * 4)


def trace_step(q, active):
    require(type(q) is int and 0 <= q <= MAX_Q and type(active) is bool, "Invalid trace sample")
    target = MAX_Q if active else 0
    # Match signed C division truncated toward zero without a negative shift.
    return q + (target - q) // 256 if target >= q else q - (q - target) // 256


def sample(previous, tick, current):
    require(isinstance(previous, History) and type(tick) is int and tick == previous.tick + 1 and
            tick <= 0xffffffff and isinstance(current, Terrain), "Missing, duplicated or invalid ecology sample")
    wet = tuple(v >= 12 for v in current.water)
    lit = tuple(v >= 80 for v in current.light)
    joint = tuple(w and light for w, light in zip(wet, lit))
    open_joint = tuple(j and not o for j, o in zip(joint, current.occupied))
    traces = tuple(tuple(trace_step(q, v) for q, v in zip(row, observations))
                   for row, observations in zip(previous.traces, (wet, lit, joint, open_joint)))
    return History(tick, min(tick, DAY), current, traces)


def pixel_column(x):
    require(type(x) is int and 0 <= x <= 255, "Invalid pixel coordinate")
    return min(COLUMNS - 1, max(0, (x - 8) // 8))


def landings(origin, trait, rule="wide-v1"):
    require(type(origin) is int and 0 <= origin < COLUMNS and type(trait) is int and -2 <= trait <= 2 and
            rule in RULES, "Invalid origin, trait or dispersal rule")
    minimum, choices = RULES[rule]
    result = []
    for choice in range(2 * choices):
        offset = (1 if choice & 1 else -1) * (minimum + trait + choice // 2)
        target = origin + offset
        if not 0 <= target < COLUMNS:
            target = origin - offset
        result.append(min(COLUMNS - 1, max(0, target)))
    return tuple(result)


def project(history, origin, trait, rule="wide-v1"):
    require(isinstance(history, History), "Invalid history")
    positions = landings(origin, trait, rule)
    current = history.current
    planes = (tuple(255 if v == 0 else 0 for v in current.occupied),
              tuple(255 if v == DEAD else 0 for v in current.occupied), current.water, current.light,
              *(tuple((q + 128) // 256 for q in row) for row in history.traces))
    # Uniform nominal branch mass, retaining duplicate edge-reflected landings.
    return tuple((sum(plane[c] for c in positions) + len(positions) // 2) // len(positions)
                 for plane in planes)


def packet(history, tip_x, candidate_xs, base, trait, *, stem=True, origin_rule="flower", rule="wide-v1"):
    require(isinstance(history, History) and type(stem) is bool and origin_rule in ("base", "flower") and
            rule in RULES and type(base) is int and 0 <= base < COLUMNS and type(trait) is int and
            -2 <= trait <= 2 and type(tip_x) is int and 8 <= tip_x < 232 and len(candidate_xs) == 5 and
            all(x is None or type(x) is int and 8 <= x < 232 for x in candidate_xs), "Invalid tip context")
    positions = (tip_x, *candidate_xs)
    valid = sum(1 << i for i, x in enumerate(positions) if stem and x is not None)
    projected = {}
    values = []
    for i, x in enumerate(positions):
        if not valid & (1 << i):
            values.append((0,) * len(FIELDS))
            continue
        origin = base if origin_rule == "base" else pixel_column(x)
        if origin not in projected:
            projected[origin] = project(history, origin, trait, rule)
        values.append(projected[origin])
    return {"version": VERSION, "valid": valid, "samples": history.samples, "values": tuple(values)}
