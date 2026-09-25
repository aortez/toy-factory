#!/usr/bin/env python3
"""Swap neutrality, fixed-budget and routing guards; optional native CLI checks."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

import garden_renewal_swap as audit


def fixture(case):
    return [{"type": "world", "tick": 0, "focal_policy": audit.routing(case),
             "plants": [{"id": 2, "parent": 0, "generation": 0, "species": "shrub", "column": 8, "dead": False}]},
            {"type": "bid", "tick": 15, "id": 2, "controller_model_crc32": audit.MODELS[case.focal].crc},
            {"type": "bid", "tick": 15, "id": 6, "controller_model_crc32": audit.MODELS[case.background].crc},
            {"type": "leaf-bid", "tick": 15, "id": 2},
            {"type": "world", "tick": 15, "focal_policy": audit.routing(case), "plants": []}]


class SwapTests(unittest.TestCase):
    def test_routing_and_noninheritance(self):
        for case in audit.CASES:
            rows = fixture(case)
            before = copy.deepcopy(rows)
            result = audit.check_routing(rows, case)
            self.assertEqual(result, {"reset": 1, "worlds": 2, "focal_bids": 1, "background_bids": 1})
            self.assertEqual(rows, before)

    def test_wrong_model_or_absent_routing_rejected(self):
        case = audit.CASES[1]
        for index in (0, 1, 2, 4):
            rows = fixture(case)
            field = "focal_policy" if index in (0, 4) else "controller_model_crc32"
            rows[index].pop(field)
            with self.assertRaises(RuntimeError): audit.check_routing(rows, case)
        rows = fixture(case)
        rows[2]["controller_model_crc32"] = audit.MODELS[case.focal].crc
        with self.assertRaisesRegex(RuntimeError, "routed growth"): audit.check_routing(rows, case)

    def test_wrong_founder_ancestry_slot_identity_or_duplicate_rejected(self):
        for field, value in (("id", 1), ("parent", 1), ("generation", 1), ("species", "flower"),
                             ("column", 18), ("dead", True)):
            rows = fixture(audit.CASES[0])
            rows[0]["plants"][0][field] = value
            with self.assertRaisesRegex(RuntimeError, "reset founder"):
                audit.check_routing(rows, audit.CASES[0])
        rows = fixture(audit.CASES[0])
        rows[0]["plants"] *= 2
        with self.assertRaises(RuntimeError): audit.check_routing(rows, audit.CASES[0])

    def test_missing_reset_no_focal_or_no_background_bids_rejected(self):
        for index in (0, 1, 2):
            rows = fixture(audit.CASES[0])
            rows.pop(index)
            with self.assertRaises(RuntimeError): audit.check_routing(rows, audit.CASES[0])

    def test_no_neural_leaf_routing_or_extra_intervention(self):
        rows = fixture(audit.CASES[0])
        rows[3]["controller_model_crc32"] = audit.MODELS["r2-n"].crc
        with self.assertRaises(RuntimeError): audit.check_routing(rows, audit.CASES[0])
        rows[3] = {"type": "disturbance", "tick": 15}
        with self.assertRaises(RuntimeError): audit.check_routing(rows, audit.CASES[0])

    def test_complete_control_not_just_final_hash(self):
        rows = fixture(audit.CASES[0])
        old = [audit.without_routing(r) for r in rows]
        self.assertEqual(audit.check_control(rows, old), len(rows))
        for changed in (old[:-1], old + [old[-1]], list(reversed(old))):
            with self.assertRaises(RuntimeError): audit.check_control(rows, changed)
        old[1]["tick"] += 15
        with self.assertRaisesRegex(RuntimeError, "record 1"): audit.check_control(rows, old)
        with self.assertRaises(RuntimeError): audit.check_control([], [])

    def test_neutrality_does_not_strip_undeclared_metadata(self):
        rows = fixture(audit.CASES[0])
        old = [audit.without_routing(r) for r in rows]
        rows[0]["new_override"] = "not allowed"
        with self.assertRaises(RuntimeError): audit.check_control(rows, old)

    def test_fixed_protocol_and_call_budget(self):
        commands = audit.commands()
        self.assertEqual(len(commands), 40)
        self.assertEqual(len({n for n, _ in commands}), 40)
        self.assertEqual(sum(n.endswith(".gz") for n, _ in commands), 8)
        self.assertEqual(sum("--framebuffer" in c for _, c in commands), 32)
        self.assertEqual([c.name for c in audit.CASES], ["n-in-n", "w-in-n", "n-in-w", "w-in-w"])
        self.assertEqual(audit.settings()["models"], {"r2-n": "01b9d94a", "r2-w": "c9ea07fd"})
        for case in audit.CASES:
            calls = [(n, c) for n, c in commands if Path(n).name.startswith(case.name + ".")]
            self.assertEqual(len(calls), 10)
            for _, c in calls:
                self.assertEqual(c[1:5], [f"models/{case.background}.tgm", "rainfed-crowded", "neural-no-night-growth", "0x0d983a80"])
                self.assertEqual(c[c.index("--focal-model") + 1], f"models/{case.focal}.tgm")
                self.assertEqual(c[c.index("--focal-founder") + 1], "2")
                self.assertNotIn("--founder-exit", c)
                self.assertNotIn("--root-bootstrap-after", c)
                self.assertTrue(c[0] in ("bin/garden-inspect", "bin/garden-replay"))

    def test_framebuffer_references_and_copied_controls(self):
        for target, command in audit.commands():
            if target.endswith(".json"):
                self.assertEqual(command[-1], target.removesuffix(".json") + ".rgb565")
        copied = audit.copies()
        self.assertEqual(len(copied), 22)
        self.assertEqual(copied["input/controls/r2-n.jsonl.gz"], "traces/r2-n.jsonl.gz")
        self.assertNotIn("bin/garden-train", copied)


def cli_checks(build):
    model = audit.experiment.ROOT / "artifacts/garden-renewal-startup-v1/models/r2-n.tgm"
    cache = (build / "CMakeCache.txt").read_text()
    leaf = "TOY_FACTORY_GARDEN_LEAF_MAINTENANCE:BOOL=ON" in cache
    bad_options = (["--focal-model"], ["--focal-founder"], ["--focal-founder", "2"],
        ["--focal-model", str(model)], ["--focal-model", "", "--focal-founder", "2"],
        ["--focal-model", str(model), "--focal-model", str(model), "--focal-founder", "2"],
        ["--focal-model", str(model), "--focal-founder", "2", "--focal-founder", "2"])
    guards, checks = 0, 0
    for tool in ("inspect", "replay"):
        base = [str((build / f"toy-factory-garden-{tool}").resolve()), str(model), "rainfed-crowded",
                "neural-no-night-growth", "0x0d983a80", "--ticks", "60"]
        if tool == "inspect": base += ["--ecology"]
        if leaf: base += ["--leaf-policy", "selective", "--disturbance-seed", "0x05d87ca0"]
        focal = ["--focal-model", str(model), "--focal-founder", "2"]
        bad = list(bad_options) + [focal[:-1] + [value] for value in ("0", "-1", "4294967296", "junk")]
        bad += [focal + ["--root-bootstrap-after", "15"], focal + ["--gap-at", "15"]]
        if tool == "inspect":
            bad += [focal + ["--root-first", "2"], focal + ["--night-wait", "2"]]
        else:
            bad += [focal + ["--founder-exit", "15"]]
        for options in bad:
            result = subprocess.run(base + options, capture_output=True, timeout=10)
            audit.require(result.returncode != 0, f"accepted invalid options: {tool} {options}")
            guards += 1
        invalid_policy = base.copy()
        invalid_policy[3] = "neural-candidate"
        result = subprocess.run(invalid_policy + focal, capture_output=True, timeout=10)
        audit.require(result.returncode == 2, "accepted wrong policy")
        guards += 1
        if model.is_file():
            result = subprocess.run(base + focal[:-1] + ["99"], capture_output=True, timeout=10)
            audit.require(result.returncode != 0, "accepted absent founder")
            guards += 1
            values = []
            for options in ([], focal):
                result = subprocess.run(base + options, capture_output=True, text=True, timeout=15)
                audit.require(result.returncode == 0, f"native self-routing failed: {result.stderr}")
                values.append([json.loads(line) for line in result.stdout.splitlines()])
            checks += audit.check_control(values[1], values[0])
    print(f"Native focal CLI: {guards} rejection checks; {checks} self-routing records "
          f"({'saved model available' if model.is_file() else 'positive checks skipped: saved model unavailable'})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    args = parser.parse_args()
    if args.build:
        cli_checks(args.build)
    unittest.main(argv=[sys.argv[0]])
