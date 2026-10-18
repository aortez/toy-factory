"""One fixed wear-aware baseline, encoded in the existing stateless repair NN."""

from dataclasses import replace
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'leaf_pilot'))
import pilot_model as model

MAX_CONDITION = 192
MIN_LIGHT = 131


def initializer():
    original = model.initial_model()
    weights, bias = list(original.hidden_weights), list(original.hidden_bias)
    # Connected hidden units represent violations, not extra physiological rules.
    weights[1], bias[0] = -64, 65 * 64
    weights[11], bias[1] = 64, -95 * 64
    output = [0] * 16
    output[8], output[9] = -64, -64
    return replace(original, hidden_weights=tuple(weights), hidden_bias=tuple(bias),
                   action_weights=tuple(output), action_bias=(0, 64))


def rule(condition, light):
    if any(type(value) is not int or not 0 <= value <= 255 for value in (condition, light)):
        raise ValueError('raw condition and light must be bytes')
    return int(condition <= MAX_CONDITION and light >= MIN_LIGHT)
