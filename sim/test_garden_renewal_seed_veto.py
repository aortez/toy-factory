#!/usr/bin/env python3
"""Strict counterfactual identity, prefix and host-only build guard tests."""
import copy
import subprocess
import tempfile
import unittest

import garden_renewal_seed_veto as audit


def divergence():
    plant = {"id": 2, "energy": 201, "water": 317, "spent_flowers": 4, "reproduction_cooldown": 16}
    control = {"type": "world", "tick": 4620, "hash": "control", "plants": [plant]}
    veto = {**control, "hash": "veto", "seed_veto_rule": audit.VETO_RULE,
            "plants": [plant | {"energy": 249, "water": 341, "spent_flowers": 3, "reproduction_cooldown": 0}]}
    return control, veto


class SeedVetoTests(unittest.TestCase):
    def test_fixed_panel_and_build_selection(self):
        commands = audit.commands()
        self.assertEqual(len(commands), 20)
        self.assertEqual(len({n for n, _ in commands}), 20)
        self.assertEqual(sum(n.endswith(".gz") for n, _ in commands), 4)
        self.assertEqual(sum("--framebuffer" in c for _, c in commands), 16)
        self.assertEqual(audit.FRAME_TICKS, (4800, 6720, 7680, 30720))
        for case in audit.CASES:
            selected = [(n, c) for n, c in commands if n.split("/")[1].startswith(case + ".")]
            self.assertEqual(len(selected), 10)
            for name, command in selected:
                self.assertTrue(command[0].startswith("bin/" + case + "-"))
                self.assertEqual(command[1:5], ["models/r2-n.tgm", "rainfed-crowded", "neural-no-night-growth", "0x0d983a80"])
                self.assertEqual(command[command.index("--focal-founder") + 1], "5")
                self.assertEqual(command[command.index("--focal-model") + 1], "models/r2-w.tgm")
                self.assertEqual(command[command.index("--disturbance-seed") + 1], "0x05d87ca0")
                if "--framebuffer" in command:
                    self.assertEqual(command[-1], name.removesuffix(".json") + ".rgb565")

    def test_contract_and_saved_controls(self):
        self.assertEqual(audit.settings()["daylight_interval"], [2880, 4800])
        self.assertEqual(audit.settings()["purchase_limit"], 3)
        self.assertEqual(audit.settings()["observed_founder"], 2)
        self.assertEqual(audit.copies()["input/control.jsonl.gz"], "traces/neighbor-5-w.jsonl.gz")
        self.assertEqual(len(audit.copies()), 10)
        self.assertFalse(set(audit.copies()) & {n for n, _ in audit.commands()})

    def test_only_declared_metadata_ignored(self):
        row = {"type": "world", "seed_veto_rule": audit.VETO_RULE, "extra": 1, "hash": "a"}
        original = copy.deepcopy(row)
        self.assertEqual(audit.without_veto(row), {"type": "world", "extra": 1, "hash": "a"})
        self.assertEqual(row, original)

    def test_metadata_on_world_only_and_absent_from_control(self):
        rows = [{"type": "bid"}, {"type": "leaf-bid"}, {"type": "world", "seed_veto_rule": audit.VETO_RULE}]
        self.assertEqual(audit.check_metadata(rows, "veto"), 1)
        with self.assertRaises(RuntimeError): audit.check_metadata(rows, "control")
        for broken in ([{"type": "world"}], [{"type": "world", "seed_veto_rule": "wrong"}],
                       [{"type": "bid", "seed_veto_rule": audit.VETO_RULE}]):
            with self.assertRaises(RuntimeError): audit.check_metadata(broken, "veto")

    def test_control_requires_every_record_and_field(self):
        records = [{"type": "bid", "priority": 3}, {"type": "world", "hash": "abc"}]
        self.assertEqual(audit.check_control(records, records), 2)
        for changed in ([], records[:1], records + records, [{"type": "bid", "priority": 4}, records[1]],
                        [records[0], records[1] | {"seed_veto_rule": audit.VETO_RULE}]):
            with self.assertRaises(RuntimeError): audit.check_control(changed, records)
        with self.assertRaises(RuntimeError): audit.check_control([], [])

    def test_exact_divergence_with_unmodified_inputs(self):
        left, right = divergence()
        records = [{"type": "world", "tick": 0}, {"type": "bid", "tick": 4620}]
        tagged = [records[0] | {"seed_veto_rule": audit.VETO_RULE}, records[1]]
        saved = copy.deepcopy((left, right, records, tagged))
        result = audit.check_prefix(records + [left], tagged + [right])
        self.assertEqual(result["matching_records"], 2)
        self.assertEqual(result["tick"], 4620)
        self.assertEqual((left, right, records, tagged), saved)

    def test_wrong_tick_wrong_record_or_earlier_change_rejected(self):
        left, right = divergence()
        for tick in (4605, 4635):
            with self.assertRaises(RuntimeError): audit.check_prefix([left | {"tick": tick}], [right | {"tick": tick}])
        with self.assertRaises(RuntimeError): audit.check_prefix([left | {"type": "bid"}], [right | {"type": "bid"}])
        with self.assertRaises(RuntimeError): audit.check_prefix([{"type": "world", "tick": 0}, left],
            [{"type": "world", "tick": 0, "new_hidden_change": 1}, right])

    def test_debit_flags_and_retry_cooldown_must_match(self):
        left, right = divergence()
        for key, value in (("energy", 248), ("water", 340), ("spent_flowers", 4), ("reproduction_cooldown", 16)):
            wrong = copy.deepcopy(right)
            wrong["plants"][0][key] = value
            with self.assertRaisesRegex(RuntimeError, "debit"):
                audit.check_prefix([left], [wrong])

    def test_absent_veto_or_missing_rows_rejected(self):
        left, right = divergence()
        for a, b in (([], []), ([left], []), ([], [right]), ([left], [left])):
            with self.assertRaises(RuntimeError): audit.check_prefix(a, b)

    def test_compiler_guards(self):
        required = {"TOY_FACTORY_GARDEN_FOCAL_SEED_VETO", "TOY_FACTORY_GARDEN_LEAF_MAINTENANCE",
            "TOY_FACTORY_GARDEN_LARGE_POOL", "TOY_FACTORY_GARDEN_COMBINED_EXPERIMENT",
            "TOY_FACTORY_GARDEN_WIDE_DISPERSAL", "TOY_FACTORY_GARDEN_WATER_HEADROOM"}
        def compile_header(defines):
            return subprocess.run(["cc", "-x", "c", "-fsyntax-only", "-I", str(audit.experiment.ROOT / "src"),
                *["-D" + d + "=1" for d in sorted(defines)], "-"],
                input='#include "garden_world.h"\n', text=True, capture_output=True, check=False)
        self.assertEqual(compile_header(required).returncode, 0)
        self.assertEqual(compile_header(set()).returncode, 0)
        for missing in required - {"TOY_FACTORY_GARDEN_FOCAL_SEED_VETO"}:
            self.assertNotEqual(compile_header(required - {missing}).returncode, 0, missing)
        for conflict in ("__ZEPHYR__", "TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE",
                         "TOY_FACTORY_GARDEN_SEED_RESERVE", "TOY_FACTORY_GARDEN_LARGE_SEED_BANK"):
            self.assertNotEqual(compile_header(required | {conflict}).returncode, 0, conflict)

    def test_cmake_rejects_incompatible_default_ecology(self):
        with tempfile.TemporaryDirectory(prefix="seed-veto-guard-") as directory:
            result = subprocess.run(["cmake", "-S", str(audit.experiment.ROOT / "sim"), "-B", directory,
                "-DTOY_FACTORY_GARDEN_FOCAL_SEED_VETO=ON"], text=True, capture_output=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Focal seed veto requires", result.stderr)


if __name__ == "__main__":
    unittest.main()
