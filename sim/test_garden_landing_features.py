#!/usr/bin/env python3
"""Landing-input extension arithmetic, native protocol, masking and frozen evidence."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import subprocess
import unittest

import garden_landing_features as f
import garden_landing_encoding as audit

BUILD, CC, ARM = None, None, False


def packet(value=0, samples=1, valid=63):
    return {"version": 1, "valid": valid, "samples": samples,
            "values": [[value, 0, value, value, value if samples else 0,
                        value if samples else 0, value if samples else 0, value if samples else 0]
                       if valid & (1 << i) else [0] * 8 for i in range(6)]}


class FeatureTests(unittest.TestCase):
    def test_all_bytes_are_lossless(self):
        values = []
        for v in range(256):
            result = f.encode(0, [3] * 5, packet(v))
            self.assertEqual(result["common"][:8], [v - 128, -128, *([v - 128] * 6)])
            self.assertTrue(all(row == result["common"][:8] for row in result["candidates"]))
            values.append(result["common"][0])
        self.assertEqual(values, list(range(-128, 128)))

    def test_warmup_and_cold_start(self):
        values = []
        for samples in range(257):
            result = f.encode(0, [3] * 5, packet(samples=samples))
            values.append(result["common"][8])
            self.assertEqual(result["common"][4:8], [-128 if samples else 0] * 4)
        self.assertEqual(values, sorted(values))
        self.assertEqual((values[0], values[-1]), (-128, 127))
        self.assertEqual(values.count(127), 1)
        self.assertEqual(values[128:130], [0, 0])
        self.assertEqual(len(set(values)), 256)

    def test_no_history_clock_leak(self):
        result = f.encode(0, [3] * 5, packet(127, 256), "current")
        changed = f.encode(0, [3] * 5, packet(127, 0), "current")
        self.assertEqual(result, changed)
        self.assertEqual(result["common"][4:], [0] * 5)
        self.assertTrue(all(row[4:] == [0] * 4 for row in result["candidates"]))
        self.assertEqual(f.encode(0, [3] * 5, None, "off"), f.encode(0, [3] * 5, packet(255), "off"))
        with self.assertRaises(ValueError):
            f.encode(0, [3] * 5, None, "history")

    def test_roots_oob_and_unavailable(self):
        zero = {"common": [0] * 9, "candidates": [[0] * 8 for _ in range(5)]}
        self.assertEqual(f.encode(1, [3] * 3, packet(samples=256, valid=0)), zero)
        result = f.encode(0, [5, 0, 3, 3, 3], packet(18, valid=59))
        self.assertEqual(result["candidates"][0][0], -110)
        self.assertEqual(result["candidates"][1], [0] * 8)

    def test_omit_dead_and_permutation(self):
        raw = packet()
        raw["values"][1][1] = 200
        raw["values"][5][2] = 81
        expected = f.encode(0, [3] * 5, raw)
        omitted = f.encode(0, [3] * 5, raw, omit_dead=True)
        masked = copy.deepcopy(expected)
        for row in [masked["common"], *masked["candidates"]]:
            row[1] = 0
        self.assertEqual(masked, omitted)
        raw["values"][1], raw["values"][5] = raw["values"][5], raw["values"][1]
        actual = f.encode(0, [3] * 5, raw)
        self.assertEqual(actual["candidates"][0], expected["candidates"][4])
        self.assertEqual(actual["candidates"][4], expected["candidates"][0])

    def test_invalid_packet_even_when_masked(self):
        for key, value in (("version", 2), ("valid", 127), ("samples", 257), ("samples", True)):
            raw = packet()
            raw[key] = value
            for mode in f.MODES:
                with self.assertRaises(ValueError):
                    f.encode(0, [3] * 5, raw, mode)
        for field in (4, 5, 6, 7):
            raw = packet(samples=0)
            raw["values"][0][field] = 1
            with self.assertRaises(ValueError):
                f.encode(0, [3] * 5, raw, "current")
        for field in (6, 7):
            raw = packet()
            raw["values"][0][field] = 1
            with self.assertRaises(ValueError):
                f.encode(0, [3] * 5, raw, "off")
        raw = packet()
        raw["values"][0][0:2] = [128, 128]
        f.encode(0, [3] * 5, raw)
        raw["values"][0][0] = 129
        with self.assertRaises(ValueError):
            f.encode(0, [3] * 5, raw, omit_dead=True)
        with self.assertRaises(ValueError):
            f.encode(0, [3] * 5, packet(), version=2)

    def test_separation_denominators_and_partitions(self):
        bid = {"kind": 0, "candidates": [[12, 3], [14, 3], [16, 5], [0, 0], [0, 0]], "packet": packet(valid=15)}
        # History differs only at a real alternative. An unavailable water value
        # and masked zeros must not inflate the current-only comparison.
        bid["packet"]["values"][2][4] = 16
        bid["packet"]["values"][3][2] = 255
        flags = [x[1] for x in bid["candidates"]]
        encoded = {name: f.encode(0, flags, bid["packet"], mode, omit)
                   for name, (mode, omit) in zip(f.NAMES, f.VARIANTS)}
        stats = audit.new_stats()
        audit.add_bid(stats, bid, encoded)
        result = audit.summary(stats)
        self.assertEqual(result["choices"], 1)
        self.assertEqual(result["history_added"], 1)
        self.assertEqual(result["masks"]["history"]["ge_16"], 1)
        self.assertEqual(result["masks"]["current"]["ge_1"], 0)
        self.assertEqual(audit.separation(encoded["history"], [0]), 0)

    def test_native_crosscheck_and_errors(self):
        probe = None if BUILD is None else BUILD / "toy-factory-garden-landing-features-probe"
        if probe is None or not probe.is_file():
            self.skipTest("This build has no landing feature probe")
        records, expected = [], []
        for value in range(256):
            for mode, omit in f.VARIANTS:
                raw = packet(value)
                records.append(f.request(0, [3] * 5, raw, mode, omit))
                expected.append(f.encode(0, [3] * 5, raw, mode, omit))
        for samples in range(257):
            raw = packet(samples=samples)
            records.append(f.request(0, [3] * 5, raw, "history"))
            expected.append(f.encode(0, [3] * 5, raw))
        for kind, flags, raw in ((1, [3] * 3, packet(valid=0)), (0, [5, 0, 3, 3, 3], packet(valid=59))):
            records.append(f.request(kind, flags, raw, "history"))
            expected.append(f.encode(kind, flags, raw))
        output = audit.native(probe, b"".join(records))
        for i, values in enumerate(expected):
            self.assertEqual(f.response(output[i * 53:(i + 1) * 53]), (0, values))
        valid = f.request(0, [3] * 5, packet(), "history")
        malformed = []
        for offset, value in ((0, 2), (1, 3), (2, 2), (3, 1), (4, 2), (5, 2), (10, 2), (11, 127), (13, 2), (20, 1)):
            bad = bytearray(valid)
            bad[offset] = value
            malformed.append(bytes(bad))
        output = audit.native(probe, b"".join(malformed))
        for i in range(len(malformed)):
            record = output[i * 53:(i + 1) * 53]
            self.assertLess(f.response(record)[0], 0)
            self.assertEqual(record[4:], b"\xa5" * 49)
        partial = subprocess.run([str(probe)], input=valid[:-1], capture_output=True, timeout=30)
        self.assertEqual(partial.returncode, 2)
        self.assertEqual(partial.stdout, b"")

    def test_compiled_layout_and_legacy_abi(self):
        if CC is None:
            self.skipTest("No compiler selected")
        source = '''
#include <stddef.h>
#include "garden_landing_features.h"
_Static_assert(sizeof(struct toy_factory_garden_landing_feature_config) == 4, "metadata");
_Static_assert(sizeof(struct toy_factory_garden_landing_inputs) == 49, "extension");
_Static_assert(sizeof(struct toy_factory_garden_landing_features) == 126, "combined");
_Static_assert(offsetof(struct toy_factory_garden_landing_features, landing) == 77, "legacy prefix");
_Static_assert(PICOSYSTEM_GARDEN_NEURAL_FEATURE_VERSION == 1, "old feature version");
_Static_assert(PICOSYSTEM_GARDEN_NEURAL_MODEL_VERSION == 1, "old model version");
_Static_assert(PICOSYSTEM_GARDEN_NEURAL_FILE_VERSION == 1, "old file version");
_Static_assert(sizeof(struct picosystem_garden_neural_model) == 1204, "old model size");
_Static_assert(PICOSYSTEM_GARDEN_NEURAL_FILE_SIZE == 1220, "old file size");
'''
        command = [CC, "-std=c11", "-Wall", "-Wextra", "-Werror", "-Wconversion", "-Wsign-conversion", "-fsyntax-only",
                   "-I", str(audit.ROOT / "src"), "-I", str(audit.ROOT / "sim"), "-xc", "-"]
        if ARM:
            command[1:1] = ["-mcpu=cortex-m0plus", "-mthumb"]
        result = subprocess.run(command, input=source, text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        guard = subprocess.run([*command, "-D__ZEPHYR__=1"], input=source, text=True, capture_output=True, timeout=30)
        self.assertNotEqual(guard.returncode, 0)
        self.assertIn("host-only", guard.stderr)

    def test_portable_evidence_when_present(self):
        folder = audit.ROOT / "benchmarks/garden-seasons"
        evidence = folder / "landing-encoding-histories.json.gz"
        if not evidence.is_file():
            self.skipTest("No encoding replay evidence collected yet")
        old = audit.load_input()
        report = json.loads(gzip.decompress(evidence.read_bytes()))
        audit.validate_report(report, old)
        self.assertEqual(audit.compact(report), json.loads((folder / "landing-encoding-summary.json").read_text()))
        bad = copy.deepcopy(report["cases"][0])
        bad["days"][0]["stats"]["separation"]["current"][1] += 1
        with self.assertRaises(RuntimeError):
            audit.validate_case(bad, old["cases"][0])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    parser.add_argument("--cc")
    parser.add_argument("--arm", action="store_true")
    args, rest = parser.parse_known_args()
    BUILD, CC, ARM = args.build, args.cc, args.arm
    unittest.main(argv=[__file__, *rest])
