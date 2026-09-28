#!/usr/bin/env python3
"""Independent landing-input-extension v1 encoder; no world or learned model."""

import struct

VERSION = 1
MODES = ("off", "current", "history")
VARIANTS = (("off", False), ("current", False), ("history", False),
            ("current", True), ("history", True))
NAMES = ("off", "current", "history", "current-no-dead", "history-no-dead")
REQUEST_SIZE, RESPONSE_SIZE = 62, 53


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def validate(kind, flags, packet, mode, omit_dead, version):
    require(integer(version, VERSION, VERSION) and mode in MODES and type(omit_dead) is bool,
            "Invalid feature configuration")
    require(integer(kind, 0, 1) and len(flags) == (5 if kind == 0 else 3), "Invalid tissue/candidate count")
    require(all(integer(f, 0, 15) and (not f & 2 or f == 3) and (not f & 12 or f & 1)
                for f in flags), "Invalid canonical flags")
    if packet is None:
        require(mode == "off", "Missing active landing packet")
        return
    require(set(packet) == {"version", "valid", "samples", "values"} and
            integer(packet["version"], 1, 1) and integer(packet["samples"], 0, 256) and
            integer(packet["valid"], 0, 63), "Invalid packet header")
    expected = 1 + sum(1 << (i + 1) for i, f in enumerate(flags) if f & 1) if kind == 0 else 0
    require(packet["valid"] == expected, "Validity disagrees with canonical tissue/bounds")
    require(len(packet["values"]) == 6 and all(len(row) == 8 and all(integer(v, 0, 255) for v in row)
            for row in packet["values"]), "Invalid packet payload")
    for i, row in enumerate(packet["values"]):
        require(expected & (1 << i) or not any(row), "Invalid rows must be zero")
        require(packet["samples"] or not any(row[4:]), "Cold-start history must be zero")
        require(row[0] + row[1] <= 256 and row[7] <= row[6] <= min(row[4:6]), "Inconsistent projected fields")


def encode(kind, flags, packet, mode="history", omit_dead=False, version=VERSION):
    validate(kind, flags, packet, mode, omit_dead, version)
    common, candidates = [0] * 9, [[0] * 8 for _ in range(5)]
    if mode != "off" and kind == 0:
        with_history = mode == "history"
        count = 8 if with_history and packet["samples"] > 0 else 4
        for i, output in enumerate([common, *candidates]):
            if not packet["valid"] & (1 << i):
                continue
            for f in range(count):
                if not (omit_dead and f == 1):
                    output[f] = packet["values"][i][f] - 128
        if with_history:
            common[8] = (packet["samples"] * 255 + 128) // 256 - 128
    return {"common": common, "candidates": candidates}


def request(kind, flags, packet, mode, omit_dead=False):
    """The test-probe transport, not a model file or public device protocol."""
    validate(kind, flags, packet, mode, omit_dead, VERSION)
    require(packet is not None, "Probe requires an explicit packet")
    result = bytes([VERSION, MODES.index(mode), int(omit_dead), 0, kind,
                    *flags, *([0] * (5 - len(flags))), packet["version"], packet["valid"]])
    result += struct.pack("<H", packet["samples"])
    result += bytes(value for row in packet["values"] for value in row)
    require(len(result) == REQUEST_SIZE, "Request framing")
    return result


def response(data):
    require(len(data) == RESPONSE_SIZE, "Response framing")
    error = struct.unpack("<i", data[:4])[0]
    values = list(struct.unpack("49b", data[4:]))
    return error, {"common": values[:9], "candidates": [values[i:i + 8] for i in range(9, 49, 8)]}
