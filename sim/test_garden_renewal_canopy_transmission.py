#!/usr/bin/env python3
"""Canopy protocol, bounded optics reference, provenance and native guards."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import unittest
from unittest import mock

import garden_renewal_canopy_transmission as trial

BUILD = None
CC = None


def reference(shade, strength, direction):
    if len(shade) != 28*14 or not 24 <= strength <= 255 or not -12 <= direction <= 12:
        raise ValueError("invalid ray fixture")
    result = []
    for row in range(14):
        for column in range(28):
            beam = strength-24
            for distance in range(1, row+1):
                displacement = (abs(direction*distance)+8)//16
                source = column-displacement if direction >= 0 else column+displacement
                if not 0 <= source < 28:
                    break
                opacity = shade[(row-distance)*28+source]
                if not 0 <= opacity <= 255:
                    raise ValueError("invalid opacity")
                beam = (beam*(255-opacity)+127)//255
            result.append(24+beam)
    return result


def row(tick, arm):
    result = {"type": "world", "tick": tick, "hash": "same",
              "seed_spacing": {"rule": trial.prior.NATIVE, "after": trial.AFTER,
                               "minimum": 2 if tick > trial.AFTER else 3}}
    if arm == "transmission":
        result["canopy_transmission"] = {"rule": trial.NATIVE, "after": trial.AFTER, "active": tick > trial.AFTER}
    return result


def case(survivors=6, parents=0, deaths=3, species=1, families=2):
    return {"new_cohort": {"cycle_survivors": survivors, "cycle_survivors_with_surviving_child": parents},
            "resources": {str(i): {"incumbent": True, "lineage": {"death_tick": 100 if i < deaths else None}}
                          for i in range(7)},
            "outcomes": {"final": {"species": list(range(species)), "families": list(range(families))}}}


class CanopyTests(unittest.TestCase):
    def test_fixed_calls_use_two_column_control(self):
        calls = trial.commands()
        old = [(p, c) for p, c in trial.prior.commands() if "/two." in p]
        self.assertEqual(len(calls), 20)
        self.assertEqual(len(set(p for p, _ in calls)), 20)
        self.assertEqual(sum(p.endswith(".gz") for p, _ in calls), 8)
        self.assertEqual(trial.FRAMES, (69120, 72960, 245760))
        for i, (path, cmd) in enumerate(calls):
            arm = "control" if i < 10 else "transmission"
            before_path, before_cmd = old[i%10]
            self.assertEqual(path, before_path.replace("/two.", "/"+arm+"."))
            expected = [s.replace("frames/two.", "frames/"+arm+".") for s in before_cmd]
            self.assertEqual(cmd, expected+([] if i < 10 else ["--canopy-transmission", "fractional"]))
            self.assertEqual(cmd[cmd.index("--seed-spacing")+1], "2")
        self.assertEqual(trial.settings()["budget"], {"native_calls": 20, "training_calls": 0})

    def test_exact_metadata_and_boundary(self):
        for tick in (0, 69119, 69120, 69121, 69135, 245760):
            for arm in trial.ARMS:
                trial.check_rule(row(tick, arm), arm)
            with self.assertRaises(RuntimeError): trial.check_rule(row(tick, "control"), "transmission")
            with self.assertRaises(RuntimeError): trial.check_rule(row(tick, "transmission"), "control")
            for field in ("rule", "after", "active"):
                bad = row(tick, "transmission")
                bad["canopy_transmission"][field] = "bad"
                with self.assertRaises(RuntimeError): trial.check_rule(bad, "transmission")

    def test_prefix_preserves_every_field_except_optical_metadata(self):
        control, candidate = ([row(t, a) for t in (69105, 69120)] for a in trial.ARMS)
        before = copy.deepcopy(candidate)
        self.assertEqual(trial.check_prefix(control, candidate), 2)
        self.assertEqual(candidate, before)
        for field in ("hash", "seed_spacing", "seed_order"):
            bad = copy.deepcopy(candidate)
            bad[0][field] = "bad"
            with self.assertRaises(RuntimeError): trial.check_prefix(control, bad)
        with self.assertRaises(RuntimeError): trial.check_prefix(control, candidate[:1])

    def test_signal_requires_survival_descendants_and_retention(self):
        def decision(candidate):
            return trial.decision({"control": case(), "transmission": candidate})
        self.assertFalse(decision(case())["positive_selected_world_signal"])
        self.assertTrue(decision(case(survivors=7, parents=1))["positive_selected_world_signal"])
        for bad in (case(survivors=6, parents=1), case(survivors=7), case(survivors=7, parents=1, deaths=4),
                    case(survivors=7, parents=1, species=0), case(survivors=7, parents=1, families=1)):
            self.assertFalse(decision(bad)["positive_selected_world_signal"])
        self.assertFalse(decision(case(survivors=7, parents=1))["broader_environment_qualified"])

    def test_reference_single_stacked_opaque_and_night(self):
        shade = [0]*(28*14)
        self.assertEqual(set(reference(shade, 255, 0)), {255})
        shade[28+5] = 128
        self.assertEqual(reference(shade, 255, 0)[2*28+5], 139)
        shade[2*28+5] = 128
        self.assertEqual(reference(shade, 255, 0)[3*28+5], 81)
        shade[3*28+5] = 128
        self.assertEqual(reference(shade, 255, 0)[4*28+5], 52)
        self.assertEqual(set(reference(shade, 24, -12)), {24})
        shade[28+5] = 255
        self.assertEqual(reference(shade, 255, 0)[2*28+5], 24)

    def test_native_reference_all_phases_and_cells(self):
        binary = BUILD/"toy-factory-garden-canopy-transmission-test" if BUILD else None
        if binary is None or not binary.exists(): self.skipTest("requires optical build")
        output = subprocess.check_output([str(binary), "--dump-reference"], text=True)
        rows = [json.loads(line) for line in output.splitlines()]
        self.assertEqual([r["tick"] for r in rows], list(range(256)))
        shade = [(i*73+i//7*19)%256 for i in range(28*14)]
        for r in rows:
            phase = (64+r["tick"])%256
            strength = trial.light_audit.sun_strength(phase)
            traversal = phase if phase <= 128 else 256-phase
            direction = 12-(traversal*24+64)//128
            self.assertEqual(r["light"], reference(shade, strength, direction), r["tick"])

    def test_analysis_recovery_never_invokes_native(self):
        with mock.patch.object(trial, "check_capture", side_effect=RuntimeError("stop")), \
                mock.patch.object(trial.experiment, "command_run") as run:
            with self.assertRaises(RuntimeError): trial.finish(Path("/missing-canopy-fixture"))
            run.assert_not_called()

    def test_native_cli_rejects_malformed_or_out_of_scope(self):
        if BUILD is None: self.skipTest("requires --build")
        for tool in ("inspect", "replay"):
            base = [str(BUILD/("toy-factory-garden-"+tool)), "-", "rainfed", "adaptive", "123", "--ticks", "15"]
            for options in (["--canopy-transmission"], ["--canopy-transmission", "bad"],
                            ["--canopy-transmission", "fractional"],
                            ["--canopy-transmission", "fractional", "--canopy-transmission", "fractional"],
                            ["--canopy-transmission", "fractional", "--seed-spacing", "2"]):
                p = subprocess.run([*base, *options], capture_output=True)
                self.assertEqual((p.returncode, p.stdout), (2, b""), (tool, options, p.stderr))

    def test_header_excludes_firmware_and_missing_dependency(self):
        if CC is None: self.skipTest("requires --cc")
        header = b'#include "garden_canopy_transmission.h"\n'
        enabled = ["-DTOY_FACTORY_GARDEN_CANOPY_TRANSMISSION=1", "-DTOY_FACTORY_GARDEN_SEED_SPACING=1"]
        for flags, valid in ((enabled, True), ([], False), (enabled[:1], False), (enabled+["-D__ZEPHYR__"], False)):
            p = subprocess.run([CC, "-x", "c", "-fsyntax-only", "-I", str(trial.experiment.ROOT/"src"), *flags, "-"],
                               input=header, capture_output=True)
            self.assertEqual(p.returncode == 0, valid, p.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    parser.add_argument("--cc")
    args, remaining = parser.parse_known_args()
    BUILD = args.build.resolve() if args.build else None
    CC = args.cc
    unittest.main(argv=[__file__, *remaining])
