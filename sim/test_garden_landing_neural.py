#!/usr/bin/env python3
"""Independent extended inference arithmetic and canonical model file checks."""

import argparse
import json
from pathlib import Path
import struct
import subprocess
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
BUILD, CC, ARM = None, None, False


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


def decide(row):
    m = decode(bytes.fromhex(row["model"]))

    def dot(a, b):
        assert len(a) == len(b)
        return sum(x * y for x, y in zip(a, b))

    def scaled(value, shift):
        # Avoid Python's negative floor division and any float conversion.
        return (1 if value >= 0 else -1) * (abs(value) // (2 ** shift))

    def clip(value, low, high):
        return min(high, max(low, value))

    hidden = [clip(scaled(m["hidden_bias"][u] + dot(m["hidden_weights"][u], row["common"] + row["memory"]) +
                         dot(m["extra_common"][u], row["landing_common"]), m["shift"]), 0, 127) for u in range(16)]
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
    return result


def crc_repair(file, nested=False):
    file = bytearray(file)
    if nested:
        struct.pack_into("<I", file, 28, zlib.crc32(file[32:1236]))
    struct.pack_into("<I", file, 12, zlib.crc32(file[16:]))
    return bytes(file)


class NeuralTests(unittest.TestCase):
    def probe(self, operation, data=b"", valid=True):
        result = subprocess.run([str(BUILD / "toy-factory-garden-landing-codec-probe"), operation],
                                input=data, capture_output=True, timeout=30)
        self.assertEqual(result.returncode == 0, valid, result.stderr.decode(errors="replace"))
        if not valid:
            self.assertEqual(result.stdout, b"")
        return result.stdout

    def test_explicit_import_and_canonical_bytes(self):
        legacy = self.probe("reference")
        file = self.probe("import", legacy)
        model = decode(file)
        self.assertEqual(file[16:1236], legacy)
        self.assertEqual(file[1236:1240], bytes([1, 2, 0, 0]))
        self.assertEqual(file[1240:], bytes(208))
        self.assertEqual(model["mode"], 2)
        self.assertEqual(self.probe("roundtrip", file), file)
        self.probe("roundtrip", legacy, valid=False)
        self.probe("import", file, valid=False)
        # Every signed weight and mask is encoded byte-exactly, even when masked.
        for mode in range(3):
            for flag in range(2):
                changed = bytearray(file)
                changed[1237:1239] = bytes([mode, flag])
                changed[1240:] = bytes((i * 137 + 128) % 256 for i in range(208))
                changed = crc_repair(changed)
                decode(changed)
                self.assertEqual(self.probe("roundtrip", changed), changed)

    def test_malformed_even_with_valid_crcs(self):
        file = self.probe("import", self.probe("reference"))
        for value in (file[:-1], file + b"\0", b"", file[:16]):
            self.probe("roundtrip", value, valid=False)
        for offset, value in ((0, 0), (4, 1), (5, 1), (6, 15), (7, 1), (8, 0),
                              (1236, 2), (1237, 3), (1238, 2), (1239, 1),
                              (42, 16), (43, 16), (44, 16), (45, 1)):
            changed = bytearray(file)
            changed[offset] = value
            self.probe("roundtrip", crc_repair(changed, nested=True), valid=False)
        for bias in (-1000001, 1000001, -2147483648, 2147483647):
            changed = bytearray(file)
            struct.pack_into("<i", changed, 48, bias)
            self.probe("roundtrip", crc_repair(changed, nested=True), valid=False)

    def test_independent_integer_decisions(self):
        command = [str(BUILD / "toy-factory-garden-landing-neural-test"), "--vectors"]
        data = subprocess.check_output(command, timeout=60)
        self.assertEqual(data, subprocess.check_output(command, timeout=60))
        rows = [json.loads(line) for line in data.splitlines()]
        self.assertEqual(len(rows), 512)
        for row in rows:
            self.assertEqual(row["actual"], decide(row))
        self.assertEqual({r["actual"]["action"] for r in rows}, {0, 1, 2})
        self.assertTrue(any(r["actual"]["count"] == 3 for r in rows))
        self.assertTrue(any(r["actual"]["count"] == 5 for r in rows))
        self.assertEqual({decode(bytes.fromhex(r["model"]))["shift"] for r in rows}, set(range(16)))
        # At least one nonzero extension must change a decision, not just execute.
        changed = 0
        for row in rows:
            plain = dict(row)
            file = bytearray.fromhex(row["model"])
            file[1240:] = bytes(208)
            plain["model"] = crc_repair(file).hex()
            changed += decide(plain) != row["actual"]
        self.assertGreater(changed, 0)

    def test_layout_and_host_only_guard(self):
        if CC is None:
            self.skipTest("No layout compiler selected")
        source = '''
#include <stddef.h>
#include "garden_landing_run.h"
_Static_assert(sizeof(struct toy_factory_garden_landing_model) == 1416, "model");
_Static_assert(sizeof(struct toy_factory_garden_landing_run) == 6092, "complete checkpoint");
_Static_assert(offsetof(struct toy_factory_garden_landing_model, config) == 1204, "v1 prefix");
_Static_assert(offsetof(struct toy_factory_garden_landing_model, common_weights) == 1208, "weights");
_Static_assert(TOY_FACTORY_GARDEN_LANDING_FILE_SIZE == 1448, "file");
'''
        command = [CC, "-std=c11", "-Wall", "-Wextra", "-Werror", "-Wconversion", "-Wsign-conversion", "-fsyntax-only",
                   "-I", str(ROOT / "src"), "-I", str(ROOT / "sim"), "-xc", "-"]
        if ARM:
            command[1:1] = ["-mcpu=cortex-m0plus", "-mthumb"]
        result = subprocess.run(command, input=source, text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([*command, "-D__ZEPHYR__=1"], input=source, text=True, capture_output=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("host-only", result.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--cc")
    parser.add_argument("--arm", action="store_true")
    args, rest = parser.parse_known_args()
    BUILD, CC, ARM = args.build, args.cc, args.arm
    unittest.main(argv=[__file__, *rest])
