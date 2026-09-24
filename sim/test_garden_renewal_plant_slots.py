#!/usr/bin/env python3
"""Fixed protocol, variable admission accounting and native scope guards."""
import argparse
import copy
from pathlib import Path
import subprocess
import unittest
from unittest import mock

import garden_renewal_plant_slots as trial
import garden_node_audit as nodes
from test_garden_node_audit import plant

BUILD = None
CC = None


def row(tick, arm="sixteen"):
    value = {"type": "world", "tick": tick, "hash": "same",
             "seed_spacing": {"rule": trial.prior.NATIVE, "after": trial.AFTER,
                              "minimum": 2 if tick > trial.AFTER else 3},
             "canopy_transmission": {"rule": trial.parent.NATIVE, "after": trial.AFTER,
                                     "active": tick > trial.AFTER}}
    if arm == "sixteen":
        value["plant_admission"] = {"rule": trial.NATIVE, "after": trial.AFTER,
                                   "limit": 16 if tick > trial.AFTER else 8}
    return value


def case(survivors=2, parents=0, deaths=1, species=2, families=3):
    return {"new_cohort": {"cycle_survivors": survivors, "cycle_survivors_with_surviving_child": parents},
            "resources": {str(i): {"incumbent": True, "lineage": {"death_tick": 100 if i < deaths else None}}
                          for i in range(7)},
            "outcomes": {"final": {"species": list(range(species)), "families": list(range(families))}}}


class SlotsTests(unittest.TestCase):
    def test_fixed_calls_use_fractional_control(self):
        calls = trial.commands()
        old = [(p, c) for p, c in trial.parent.commands() if "/transmission." in p]
        self.assertEqual((len(calls), len(set(p for p, _ in calls))), (20, 20))
        self.assertEqual(sum(p.endswith(".gz") for p, _ in calls), 8)
        self.assertEqual(trial.FRAMES, (69120, 72960, 245760))
        for i, (path, cmd) in enumerate(calls):
            arm = "control" if i < 10 else "sixteen"
            p, c = old[i % 10]
            self.assertEqual(path, p.replace("/transmission.", "/"+arm+"."))
            expected = [s.replace("frames/transmission.", "frames/"+arm+".") for s in c]
            self.assertEqual(cmd, expected+([] if i < 10 else ["--plant-slots", "16"]))
        self.assertEqual(trial.settings()["limits"],
                         {"before": 8, "control_after": 8, "sixteen_after": 16, "nodes": 512, "seeds": 8})
        self.assertEqual(trial.settings()["budget"], {"native_calls": 20, "training_calls": 0})

    def test_metadata_boundary_and_old_frame_count(self):
        self.assertEqual(trial.plant_capacity({"plant_slots": 8}), 8)  # Existing replay count, not rule.
        for tick in (0, 69119, 69120, 69121, 69135, 245760):
            self.assertEqual(trial.check_rule(row(tick, "control"), "control"), 8)
            self.assertEqual(trial.check_rule(row(tick), "sixteen"), 16 if tick > 69120 else 8)
            for source, target in (("control", "sixteen"), ("sixteen", "control")):
                with self.assertRaises(RuntimeError): trial.check_rule(row(tick, source), target)
        for field, value in (("rule", "bad"), ("after", 0), ("after", 69120.0), ("limit", 8),
                             ("limit", 16.0), ("limit", True), ("extra", 1)):
            bad = row(69135)
            bad["plant_admission"][field] = value
            with self.assertRaises(RuntimeError): trial.plant_capacity(bad)
        for value in (None, 16, []):
            with self.assertRaises(RuntimeError): trial.plant_capacity({**row(69135), "plant_admission": value})

    def test_prefix_is_read_only_and_exact(self):
        a, b = ([row(t, arm) for t in (69105, 69120)] for arm in trial.ARMS)
        original = copy.deepcopy(b)
        self.assertEqual(trial.check_prefix(a, b), 2)
        self.assertEqual(b, original)
        for field in ("hash", "canopy_transmission", "seed_spacing"):
            bad = copy.deepcopy(b)
            bad[0][field] = "bad"
            with self.assertRaises(RuntimeError): trial.check_prefix(a, bad)
        with self.assertRaises(RuntimeError): trial.check_prefix(a, b[:1])

    def test_node_ownership_tracks_effective_not_storage_capacity(self):
        for tick, count, arm, valid, full in ((69120, 8, "sixteen", True, True),
                (69120, 9, "sixteen", False, False), (69135, 9, "control", False, False),
                (69135, 8, "sixteen", True, False), (69135, 16, "sixteen", True, True),
                (69135, 17, "sixteen", False, False)):
            value = {**row(tick, arm), "nodes": count*4, "node_capacity": 512, "living": count,
                     "plants": [plant(i+1, 4, 2) for i in range(count)], "seeds": []}
            if valid:
                actual = nodes.ownership(value, 512)
                self.assertEqual(actual["plant_full"], full)
                self.assertEqual(actual["live_plant_full"], full)
                self.assertEqual(actual["free_nodes"], 512-count*4)
            else:
                with self.assertRaises(RuntimeError): nodes.ownership(value, 512)

    def test_seed_snapshot_capacity_mask_and_unchanged_node_gate(self):
        for arm, count, mask in (("control", 8, 8), ("sixteen", 8, 0), ("sixteen", 16, 8)):
            value = {**row(69135, arm), "nodes": 508,
                     "plants": [{"id": i, "column": 0, "dead": False} for i in range(count)]}
            seed = {"column": 27, "blockers": mask}
            record = {"birth_tick": 69015}
            result = trial.gap.ledger.snapshot(value, seed, record, minimum_spacing=2)
            self.assertEqual(result["plant_slots"], count)
            with self.assertRaises(RuntimeError):
                trial.gap.ledger.snapshot(value, {**seed, "blockers": mask ^ 8}, record, minimum_spacing=2)
            value["nodes"] = 509
            with self.assertRaises(RuntimeError): trial.gap.ledger.snapshot(value, seed, record, minimum_spacing=2)
            trial.gap.ledger.snapshot(value, {**seed, "blockers": mask | 16}, record, minimum_spacing=2)

    def test_rotation_uses_actual_count_without_loosening_legacy(self):
        with self.assertRaises(RuntimeError): trial.order.start_index(69180, 9)
        for count in range(17):
            first = trial.order.start_index(69180, count, 16)
            self.assertEqual(first, 1 % count if count else 0)
            value = {**row(69180), "plants": list(range(count)),
                     "seed_order": {"rule": trial.order.NATIVE, "after": 69120, "start": first}}
            self.assertEqual(trial.order.check_order(value, "rotating"), first)

    def test_decision_needs_durable_reproduction_and_retention(self):
        def decision(candidate): return trial.decision({"control": case(), "sixteen": candidate})
        self.assertFalse(decision(case())["positive_selected_world_signal"])
        self.assertTrue(decision(case(survivors=3, parents=1))["positive_selected_world_signal"])
        for bad in (case(survivors=2, parents=1), case(survivors=3), case(survivors=3, parents=1, deaths=2),
                    case(survivors=3, parents=1, species=1), case(survivors=3, parents=1, families=2)):
            self.assertFalse(decision(bad)["positive_selected_world_signal"])
        self.assertFalse(decision(case(survivors=3, parents=1))["broader_environment_qualified"])

    def test_analysis_recovery_never_recaptures(self):
        with mock.patch.object(trial, "check_capture", side_effect=RuntimeError("stop")), \
                mock.patch.object(trial.experiment, "command_run") as run:
            with self.assertRaises(RuntimeError): trial.finish(Path("/missing-plant-slots-fixture"))
            run.assert_not_called()

    def test_cli_rejects_invalid_and_out_of_scope_before_output(self):
        if BUILD is None: self.skipTest("requires --build")
        for tool in ("inspect", "replay"):
            base = [str(BUILD/("toy-factory-garden-"+tool)), "-", "rainfed", "adaptive", "123", "--ticks", "15"]
            for options in (["--plant-slots"], ["--plant-slots", "8"], ["--plant-slots", "17"],
                    ["--plant-slots", "bad"], ["--plant-slots", "16"],
                    ["--plant-slots", "16", "--plant-slots", "16"],
                    ["--plant-slots", "16", "--canopy-transmission", "fractional"]):
                p = subprocess.run([*base, *options], capture_output=True, timeout=10)
                self.assertEqual((p.returncode, p.stdout), (2, b""), (tool, options, p.stderr))

    def test_header_rejects_firmware_and_missing_dependency(self):
        if CC is None: self.skipTest("requires --cc")
        enabled = ["-DTOY_FACTORY_GARDEN_PLANT_SLOTS=1", "-DTOY_FACTORY_GARDEN_CANOPY_TRANSMISSION=1"]
        for flags, valid in ((enabled, True), ([], False), (enabled[:1], False), (enabled+["-D__ZEPHYR__"], False)):
            p = subprocess.run([CC, "-x", "c", "-fsyntax-only", "-I", str(trial.experiment.ROOT/"src"), *flags, "-"],
                               input=b'#include "garden_plant_slots.h"\n', capture_output=True, timeout=10)
            self.assertEqual(p.returncode == 0, valid, p.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    parser.add_argument("--cc")
    args, remaining = parser.parse_known_args()
    BUILD = args.build.resolve() if args.build else None
    CC = args.cc
    unittest.main(argv=[__file__, *remaining])
