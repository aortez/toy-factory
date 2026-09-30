#!/usr/bin/env python3
"""Independent extended inference arithmetic and canonical model file checks."""

import argparse
import json
from pathlib import Path
import struct
import subprocess
import unittest
import zlib

from garden_landing_reference import decode, decide

ROOT = Path(__file__).resolve().parents[1]
BUILD, CC, ARM = None, None, False


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
