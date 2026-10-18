"""Independent integer reference used by inference tests and read-only traces."""

import struct
import zlib


def decode(file):
    assert len(file) == 1448
    assert struct.unpack_from("<4sHHI", file) == (b"TGL2", 2, 16, 1432)
    assert struct.unpack_from("<I", file, 12)[0] == zlib.crc32(file[16:])
    legacy = file[16:1236]
    assert struct.unpack_from("<4sHHI", legacy) == (b"TGM1", 1, 16, 1204)
    assert struct.unpack_from("<I", legacy, 12)[0] == zlib.crc32(legacy[16:])
    body = legacy[16:]
    assert struct.unpack_from("<IHHH", body) == (0x314E4E47, 1, 1, 1204)
    assert body[13:16] == bytes(3) and all(s <= 15 for s in body[10:13])
    offset = 16

    def values(count, code):
        nonlocal offset
        result = list(struct.unpack_from("<" + code * count, body, offset))
        offset += struct.calcsize("<" + code * count)
        return result

    def matrix(rows, columns):
        return [values(columns, "b") for _ in range(rows)]

    model = {"shift": body[10], "out_shift": body[11], "candidate_shift": body[12]}
    model["hidden_bias"], model["hidden_weights"] = values(16, "i"), matrix(16, 40)
    model["action_bias"], model["action_weights"] = values(3, "i"), matrix(3, 16)
    model["priority_bias"], model["priority_weights"] = values(1, "i")[0], values(16, "b")
    model["memory_bias"], model["memory_weights"] = values(8, "i"), matrix(8, 16)
    model["candidate_bias"] = values(8, "i")
    model["candidate_hidden"], model["candidate_features"] = matrix(8, 16), matrix(8, 9)
    model["candidate_out_bias"], model["candidate_out"] = values(1, "i")[0], values(8, "b")
    assert offset == len(body)
    version, mode, flags, reserved = file[1236:1240]
    assert version == 1 and mode < 3 and flags < 2 and reserved == 0
    model["mode"], model["flags"] = mode, flags
    model["extra_common"] = [list(struct.unpack_from("<9b", file, 1240 + u * 9)) for u in range(16)]
    model["extra_candidate"] = [list(struct.unpack_from("<8b", file, 1384 + u * 8)) for u in range(8)]
    return model


def explain(row, model=None):
    """Return integer intermediates too; never alter input state or model."""
    m = decode(bytes.fromhex(row["model"])) if model is None else model

    def dot(a, b):
        assert len(a) == len(b)
        return sum(x * y for x, y in zip(a, b))

    def scaled(value, shift):
        # Avoid Python's negative floor division and any float conversion.
        return (1 if value >= 0 else -1) * (abs(value) // (2 ** shift))

    def clip(value, low, high):
        return min(high, max(low, value))

    sums = [m["hidden_bias"][u] + dot(m["hidden_weights"][u], row["common"] + row["memory"]) +
            dot(m["extra_common"][u], row["landing_common"]) for u in range(16)]
    hidden = [clip(scaled(value, m["shift"]), 0, 127) for value in sums]
    logits = [scaled(m["action_bias"][a] + dot(m["action_weights"][a], hidden), m["out_shift"]) for a in range(3)]
    result = {"action": max(range(3), key=lambda a: logits[a]),
              "priority": clip(scaled(m["priority_bias"] + dot(m["priority_weights"], hidden), m["out_shift"]), -32768, 32767),
              "memory": [clip(scaled(m["memory_bias"][i] + dot(m["memory_weights"][i], hidden), m["out_shift"]), -128, 127)
                         for i in range(8)], "count": 0, "order": [255] * 5}
    if row["depth"] >= row["maximum"]:
        result.update(action=2, priority=32767)
    elif not any(flags & 2 for flags in row["flags"]):
        result.update(action=2, priority=32766)
    elif result["action"] == 1:
        scores = []
        for c in range(row["count"]):
            layer = [clip(scaled(m["candidate_bias"][u] + dot(m["candidate_hidden"][u], hidden) +
                                dot(m["candidate_features"][u], row["candidates"][c]) +
                                dot(m["extra_candidate"][u], row["landing_candidates"][c]), m["candidate_shift"]), 0, 127)
                     for u in range(8)]
            scores.append(scaled(m["candidate_out_bias"] + dot(m["candidate_out"], layer), m["out_shift"]))
        rotation = row["nonce"] % row["count"]
        ordered = [(rotation + i) % row["count"] for i in range(row["count"])]
        result["count"] = row["count"]
        result["order"] = sorted(ordered, key=lambda c: -scores[c]) + [255] * (5 - row["count"])
    return {"decision": result, "hidden_sum": sums, "hidden": hidden, "logits": logits}


def decide(row):
    return explain(row)["decision"]
