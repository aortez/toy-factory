"""Immutable host representation of the existing TLF1 repair model.

This module only encodes and decodes models. It does not choose a search,
mutate weights, run inference, or launch a simulator. Weight tuples are flat,
row-major, with the same ordering as the native codec.
"""

from dataclasses import dataclass
import hashlib
import struct
import zlib

INPUTS, HIDDEN, ACTIONS = 11, 8, 2
MAX_SHIFT, MAX_BIAS = 15, 1_000_000
HEADER_SIZE, PAYLOAD_SIZE, FILE_SIZE = 16, 156, 172
HEADER = struct.Struct('<4sHHII')
PREFIX = struct.Struct('<4sHHBBBB')


def _integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{name} must be an integer in [{low}, {high}]')


def _vector(values, count, low, high, name):
    if type(values) is not tuple or len(values) != count:
        raise ValueError(f'{name} must be an immutable tuple of length {count}')
    for value in values:
        _integer(value, low, high, name)


@dataclass(frozen=True, slots=True)
class Model:
    hidden_shift: int = 0
    output_shift: int = 0
    hidden_bias: tuple[int, ...] = (0,) * HIDDEN
    hidden_weights: tuple[int, ...] = (0,) * (HIDDEN * INPUTS)
    action_bias: tuple[int, ...] = (0,) * ACTIONS
    action_weights: tuple[int, ...] = (0,) * (ACTIONS * HIDDEN)

    def __post_init__(self):
        validate(self)


def validate(model):
    """Reject mutable vectors, bool/float parameters, and native-invalid bounds."""
    if type(model) is not Model:
        raise ValueError('expected a TLF1 Model')
    _integer(model.hidden_shift, 0, MAX_SHIFT, 'hidden_shift')
    _integer(model.output_shift, 0, MAX_SHIFT, 'output_shift')
    _vector(model.hidden_bias, HIDDEN, -MAX_BIAS, MAX_BIAS, 'hidden_bias')
    _vector(model.hidden_weights, HIDDEN * INPUTS, -128, 127, 'hidden_weights')
    _vector(model.action_bias, ACTIONS, -MAX_BIAS, MAX_BIAS, 'action_bias')
    _vector(model.action_weights, ACTIONS * HIDDEN, -128, 127, 'action_weights')


def encode(model):
    """Return the exact canonical 172 bytes, validating before producing output."""
    validate(model)
    payload = PREFIX.pack(b'LFN1', 1, 1, model.hidden_shift, model.output_shift, 0, 0)
    payload += struct.pack('<8i', *model.hidden_bias)
    payload += struct.pack('<88b', *model.hidden_weights)
    payload += struct.pack('<2i', *model.action_bias)
    payload += struct.pack('<16b', *model.action_weights)
    return HEADER.pack(b'TLF1', 1, HEADER_SIZE, PAYLOAD_SIZE, zlib.crc32(payload)) + payload


def decode(data):
    """Validate container, CRC, identities and bounds; return independent values."""
    if type(data) not in (bytes, bytearray) or len(data) != FILE_SIZE:
        raise ValueError('TLF1 requires exactly 172 bytes')
    raw = bytes(data)
    magic, version, header_size, payload_size, crc = HEADER.unpack_from(raw)
    if (magic, version, header_size, payload_size) != (b'TLF1', 1, HEADER_SIZE, PAYLOAD_SIZE):
        raise ValueError('unsupported TLF1 header')
    payload = raw[HEADER_SIZE:]
    if zlib.crc32(payload) != crc:
        raise ValueError('TLF1 payload CRC differs')
    tag, model_version, feature_version, hidden_shift, output_shift, reserved0, reserved1 = PREFIX.unpack_from(payload)
    if (tag, model_version, feature_version, reserved0, reserved1) != (b'LFN1', 1, 1, 0, 0):
        raise ValueError('unsupported LFN1 model/feature identity or reserved bytes')
    return Model(hidden_shift, output_shift,
                 struct.unpack_from('<8i', payload, 12),
                 struct.unpack_from('<88b', payload, 44),
                 struct.unpack_from('<2i', payload, 132),
                 struct.unpack_from('<16b', payload, 140))


def fingerprint(model):
    """SHA256 of the same complete model bytes consumed by the native runner."""
    return hashlib.sha256(encode(model)).hexdigest()
