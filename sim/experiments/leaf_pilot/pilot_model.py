"""The approved, deterministic local repair search; no simulation or file I/O."""

from dataclasses import replace
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'leaf_model_tools'))
from leaf_model import Model, decode, encode, fingerprint

INITIAL_SHA = 'd21d5b9143de76d97367e9e9b5ba2a373be2fbdd6d765b86ae76a44ae2f4d620'
SEARCH_SEEDS = (0x72657031, 0x72657032)
DELTAS = (-8, -4, -2, -1, 1, 2, 4, 8)


def initial_model():
    weights, bias, output = [0] * 88, [0] * 8, [0] * 16
    for unit, feature in enumerate((1, 0, 2, 3, 4, 7, 8, 1)):
        weights[unit * 11 + feature] = -64 if unit == 1 else 64
    bias[0], bias[1], output[8] = -4032, 8128, 64
    result = Model(6, 6, tuple(bias), tuple(weights), (64, 0), tuple(output))
    if fingerprint(result) != INITIAL_SHA:
        raise ValueError('initializer differs from approved protocol')
    return result


def next_random(state):
    if type(state) is not int or not 0 < state <= 0xffffffff:
        raise ValueError('nonzero 32-bit RNG state required')
    state ^= (state << 13) & 0xffffffff
    state ^= state >> 17
    state ^= (state << 5) & 0xffffffff
    return state


def mutate(parent, state):
    if (parent.hidden_shift, parent.output_shift) != (6, 6):
        raise ValueError('fixed shifts required')
    values = list(parent.hidden_weights + parent.action_weights + parent.hidden_bias + parent.action_bias)
    before, edits = state, []
    for _ in range(8):
        draw_index = next_random(state)
        state = next_random(draw_index)
        index, delta = draw_index % 114, DELTAS[state % 8]
        scale, low, high = (1, -128, 127) if index < 104 else (64, -1_000_000, 1_000_000)
        old = values[index]
        values[index] = min(high, max(low, old + scale * delta))
        edits.append(dict(index=index, delta=delta, scale=scale, before=old, after=values[index],
                          index_draw=draw_index, delta_draw=state))
    child = replace(parent, hidden_weights=tuple(values[:88]), action_weights=tuple(values[88:104]),
                    hidden_bias=tuple(values[104:112]), action_bias=tuple(values[112:]))
    return child, state, dict(parent=fingerprint(parent), child=fingerprint(child), rng_before=before,
                             rng_after=state, edits=edits)


def select(incumbent, ordered_children, scores):
    """Exact tuples; incumbent wins ties, then earliest declared better child."""
    best = incumbent
    for candidate in ordered_children:
        if scores[candidate] > scores[best]:
            best = candidate
    return best


def infer(model, features):
    """Independent integer specification used only for initializer tests."""
    if len(features) != 11 or any(type(x) is not int or not -128 <= x <= 127 for x in features):
        raise ValueError('eleven signed byte features required')
    def divide(value, shift):
        return (1 if value >= 0 else -1) * (abs(value) // (1 << shift))
    hidden = [min(127, max(0, divide(model.hidden_bias[u] + sum(
        model.hidden_weights[u * 11 + f] * features[f] for f in range(11)), model.hidden_shift)))
        for u in range(8)]
    return tuple(divide(model.action_bias[a] + sum(model.action_weights[a * 8 + u] * hidden[u]
                 for u in range(8)), model.output_shift) for a in range(2))
