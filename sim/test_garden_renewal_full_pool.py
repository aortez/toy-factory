#!/usr/bin/env python3
"""Full-pool frozen protocol, receipt filtering and host-only scope tests."""
import argparse
import copy
from pathlib import Path
import subprocess
import unittest
from unittest import mock

import garden_renewal_full_pool as trial
from test_garden_renewal_plant_slots import row as parent_row, case as parent_case

BUILD = None
CC = None


def row(tick, arm="nonallocating"):
    value = parent_row(tick)
    if arm == "nonallocating":
        value["full_pool"] = {"rule": trial.NATIVE, "after": trial.AFTER, "active": tick > trial.AFTER,
                              "evaluated": [0, 0, 0], "denied": 0, "overflow": False, "events": []}
    return value


def case(*, finishes=1, exhausted=0, **kwargs):
    return {**parent_case(survivors=kwargs.get("survivors", 17), parents=kwargs.get("parents", 6),
                         deaths=kwargs.get("deaths", 6), species=kwargs.get("species", 2), families=kwargs.get("families", 2)),
            "full_pool_actions": {"receipts": {"counts": {"committed_finish": finishes,
                                                           "committed_exhausted_extend": exhausted}}}}


class ProtocolTests(unittest.TestCase):
    def test_twenty_fixed_calls_keep_sixteen_control(self):
        calls = trial.commands()
        previous = [(p, c) for p, c in trial.parent.commands() if "/sixteen." in p]
        self.assertEqual((len(calls), len(set(p for p, _ in calls))), (20, 20))
        self.assertEqual(trial.FRAMES, (69120, 72960, 245760))
        self.assertEqual(trial.settings()["limits"], {"before": 8, "both_after": 16, "nodes": 512, "seeds": 8})
        self.assertEqual(trial.settings()["budget"], {"native_calls": 20, "training_calls": 0})
        for i, (path, cmd) in enumerate(calls):
            arm = trial.ARMS[i//10]
            p, c = previous[i % 10]
            self.assertEqual(path, p.replace("/sixteen.", "/"+arm+"."))
            expected = [s.replace("frames/sixteen.", "frames/"+arm+".") for s in c]
            self.assertEqual(cmd, expected+(["--full-pool", "nonallocating"] if i >= 10 else []))

    def test_metadata_and_activation_fail_closed(self):
        for tick in (0, 69120, 69121, 69135, 245760):
            for arm in trial.ARMS: trial.check_rule(row(tick, arm), arm)
        for field, value in (("rule", "wrong"), ("after", 0), ("after", 69120.0), ("active", False),
                             ("active", 1), ("overflow", True), ("evaluated", [0, -1, 0]),
                             ("evaluated", [False, 0, 0]), ("evaluated", [0, 0]), ("denied", 1),
                             ("events", [{}]*17), ("extra", 0)):
            bad = row(69135)
            bad["full_pool"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(RuntimeError): trial.check_rule(bad, "nonallocating")
        premature = row(69120)
        premature["full_pool"]["evaluated"][0] = 1
        with self.assertRaises(RuntimeError): trial.check_rule(premature, "nonallocating")
        with self.assertRaises(RuntimeError): trial.check_rule(row(69135), "control")
        with self.assertRaises(RuntimeError): trial.check_rule(row(69135, "control"), "nonallocating")

    def test_prefix_ignores_only_new_metadata(self):
        a, b = ([row(t, arm) for t in (69105, 69120)] for arm in trial.ARMS)
        frozen = copy.deepcopy(b)
        self.assertEqual(trial.check_prefix(a, b), 2)
        self.assertEqual(b, frozen)
        for key in ("hash", "plant_admission", "seed_spacing"):
            bad = copy.deepcopy(b)
            bad[0][key] = "wrong"
            with self.assertRaises(RuntimeError): trial.check_prefix(a, bad)
        with self.assertRaises(RuntimeError): trial.check_prefix(a, b[:1])

    def test_mechanism_and_all_ecological_gates_required(self):
        def decide(candidate): return trial.decision({"control": case(), "nonallocating": candidate})
        self.assertTrue(decide(case())["positive_selected_world_signal"])
        self.assertTrue(decide(case(finishes=0, exhausted=1))["positive_selected_world_signal"])
        for bad in (case(finishes=0), case(survivors=16), case(parents=5), case(deaths=7),
                    case(species=1), case(families=1)):
            self.assertFalse(decide(bad)["positive_selected_world_signal"])
        self.assertFalse(decide(case())["broader_environment_qualified"])

    def test_selected_action_distinguishes_geometric_exhaustion(self):
        for action, available, allocates in ((0, True, False), (2, True, False), (1, True, True), (1, False, False)):
            winner = {"id": 2, "tip_index": 511, "action": action, "candidates": [{"flags": 3 if available else 1}]}
            event = {"id": 2, "node": 511, "action": action, "allocates": allocates}
            self.assertEqual(trial.check_selected(event, winner), allocates)
            for key, value in (("id", 1), ("node", 512), ("action", 3), ("allocates", not allocates), ("extra", 0)):
                with self.subTest(key=key), self.assertRaises(RuntimeError): trial.check_selected({**event, key: value}, winner)

    def test_finish_recovery_never_runs_native(self):
        with mock.patch.object(trial, "check_capture", side_effect=RuntimeError("stop")), \
                mock.patch.object(trial.experiment, "command_run") as run:
            with self.assertRaises(RuntimeError): trial.finish(Path("/missing-full-pool-fixture"))
            run.assert_not_called()


class ReceiptTests(unittest.TestCase):
    def fixture(self):
        agent = {"decisions": 0, "extend": 0, "finish": 0, "wait": 0, "root_extend": 0, "shoot_extend": 0,
                 "last_priority": 0, "last_action": 0, "last_x": 0, "last_y": 0, "last_tissue": 0}
        p = {"id": 1, "parent": 0, "nodes": 512, "roots": 2, "tips": 1, "dead": False,
             "species": "shrub", "vigor": 0, "energy": 64, "water": 24, "energy_income": 0,
             "water_income": 0, "reproduction_cooldown": 0, "agent": agent, "leaf": {"renewals": 0}}
        a = {"type": "world", "tick": 0, "nodes": 512, "births": 0, "plants": [p],
             "dark_guard": {"events": []}, "full_pool": {"events": [], "evaluated": [0, 0, 0], "denied": 0}}
        b = copy.deepcopy(a)
        b["tick"] = 15
        b["full_pool"] = {"events": [{"id": 1, "node": 1, "action": 1, "allocates": True}],
                          "evaluated": [0, 1, 0], "denied": 1}
        bid = {"type": "bid", "tick": 15, "id": 1, "tip_index": 1, "action": 1,
               "priority": 10, "candidates": [{"flags": 3}]}
        leaf = {"type": "leaf-bid", "tick": 15, "id": 1, "action": 0}
        return [a, leaf, bid, b]

    def audit(self, rows):
        with mock.patch.object(trial, "AFTER", 0), mock.patch.object(trial, "STOP", 15), \
                mock.patch.object(trial.ownership, "AFTER", 0), mock.patch.object(trial, "check_rule"):
            return trial.audit_actions(rows, "nonallocating")

    def test_only_uncommitted_allocation_bids_removed(self):
        rows = self.fixture()
        original = copy.deepcopy(rows)
        result, summary = self.audit(rows)
        self.assertEqual(rows, original)
        self.assertEqual(result, [rows[0], rows[1], rows[3]])
        self.assertEqual(summary["counts"]["allocation_refused"], 1)
        self.assertEqual(summary["counts"]["committed_finish"], 0)

    def test_missing_forged_and_charged_refusals_fail(self):
        for bad in ("missing", "duplicate", "counter", "charged", "tip", "guard", "stage"):
            rows = self.fixture()
            end = rows[-1]
            if bad == "missing": end["full_pool"]["events"] = []
            if bad == "duplicate": end["full_pool"]["events"] *= 2
            if bad == "counter": end["full_pool"]["denied"] = 0
            if bad == "charged": end["plants"][0]["energy"] -= 8
            if bad == "tip": end["plants"][0]["tips"] = 0
            if bad == "guard": end["dark_guard"]["events"] = [{"id": 1, "kind": "growth"}]
            if bad == "stage":
                for r in (rows[0], end): r["nodes"] -= 1; r["plants"][0]["nodes"] -= 1
            with self.subTest(bad=bad), self.assertRaises(RuntimeError): self.audit(rows)

    def test_birth_fills_pool_before_newborn_growth(self):
        rows = self.fixture()
        rows[0]["nodes"] = rows[0]["plants"][0]["nodes"] = 508
        end = rows[-1]
        end["plants"][0]["nodes"] = 508
        child = copy.deepcopy(end["plants"][0])
        child.update(id=2, parent=1, nodes=4, tips=3)
        end["plants"].append(child)
        end["births"] = 1
        end["full_pool"]["events"][0].update(id=2, node=509)
        rows[2].update(id=2, tip_index=509)
        result, summary = self.audit(rows)
        self.assertEqual(summary["counts"]["allocation_refused"], 1)
        self.assertEqual(result[-1]["plants"][1]["nodes"], 4)


class ScopeTests(unittest.TestCase):
    def test_cli_invalid_or_missing_dependencies_produce_no_trace(self):
        if BUILD is None: self.skipTest("requires --build")
        for tool in ("inspect", "replay"):
            base = [str(BUILD/("toy-factory-garden-"+tool)), "-", "rainfed", "adaptive", "123", "--ticks", "15"]
            for options in (["--full-pool"], ["--full-pool", "bad"], ["--full-pool", "nonallocating"],
                            ["--full-pool", "nonallocating", "--full-pool", "nonallocating"],
                            ["--full-pool", "nonallocating", "--plant-slots", "16"]):
                p = subprocess.run([*base, *options], capture_output=True, timeout=10)
                self.assertEqual((p.returncode, p.stdout), (2, b""), p.stderr)

    def test_header_firmware_and_dependency_rejection(self):
        if CC is None: self.skipTest("requires --cc")
        enabled = ["-DTOY_FACTORY_GARDEN_FULL_POOL=1", "-DTOY_FACTORY_GARDEN_PLANT_SLOTS=1"]
        for flags, valid in ((enabled, True), ([], False), (enabled[:1], False), (enabled+["-D__ZEPHYR__"], False)):
            p = subprocess.run([CC, "-x", "c", "-fsyntax-only", "-I", str(trial.experiment.ROOT/"src"), *flags, "-"],
                               input=b'#include "garden_full_pool.h"\n', capture_output=True, timeout=10)
            self.assertEqual(p.returncode == 0, valid, p.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    parser.add_argument("--cc")
    args, remaining = parser.parse_known_args()
    BUILD = args.build.resolve() if args.build else None
    CC = args.cc
    unittest.main(argv=[__file__, *remaining])
