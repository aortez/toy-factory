#!/usr/bin/env python3
"""Fixed panel, raw-candidate accounting, provenance and native/reference parity."""
import argparse
import copy
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import garden_renewal_dark_guard as audit
import test_garden_renewal_seed_forecast as fixtures

BUILD = None


def event(tick=945, **changes):
    e = {"id": 5, "kind": "growth", "node": 1, "energy": 148, "water": 285,
         "nodes_before": 33, "nodes_after": 34, "energy_cost": 9, "water_cost": 5,
         "stress": 0, "invalid": False, **changes}
    e["before"] = audit.native_budget(tick, e["energy"], e["nodes_before"], e["stress"])
    e["after"] = audit.native_budget(tick, e["energy"]-e["energy_cost"], e["nodes_after"], e["stress"])
    e["denied"] = e["after"]["supported"] and e["after"]["death_step"] != 0
    return e


def accounting_fixture(denied=False):
    p = fixtures.plant(nodes=4 if denied else 5, roots=2, energy=64 if denied else 56,
                       water=24 if denied else 19, parent=1,
                       agent={"decisions": 0 if denied else 1, "extend": 0 if denied else 1, "wait": 0, "finish": 0})
    e = event(15, id=2, nodes_before=4, nodes_after=5, energy=64, water=24, energy_cost=8)
    e["denied"] = denied
    a = {"type": "world", "tick": 0, "sun_phase": 64, "plants": [],
         "dark_guard": {"rule": audit.GUARD, "overflow": False, "events": [], "evaluated": [0,0,0], "denied": [0,0,0]}}
    bid = {"type": "bid", "tick": 15, "id": 2, "priority": 0, "action": 1,
           "tip_index": 1, "candidates": [{"flags": 3}]}
    b = {"type": "world", "tick": 15, "sun_phase": 65, "plants": [p],
         "dark_guard": {"rule": audit.GUARD, "overflow": False, "events": [e], "evaluated": [1,0,0], "denied": [int(denied),0,0]}}
    return [a, bid, b]


class DarkGuardTests(unittest.TestCase):
    def test_fixed_scope_is_twenty_calls_with_no_quota_or_training(self):
        commands = audit.commands()
        self.assertEqual(len(commands), 20)
        self.assertEqual(len(set(name for name, _ in commands)), 20)
        self.assertEqual(sum(name.endswith(".gz") for name, _ in commands), 4)
        self.assertEqual(sum("--framebuffer" in c for _, c in commands), 16)
        self.assertEqual(audit.CASES, ("control", "guard"))
        self.assertEqual(audit.FRAME_TICKS, (4800, 6720, 7680, 30720))
        self.assertFalse(any("veto" in part for name, c in commands for part in [name, *c]))
        for _, c in commands:
            tick = int(c[c.index("--ticks")+1])
            if "inspect" in c[0]:
                self.assertEqual(tick, 30720)
            else:
                self.assertIn(tick, audit.FRAME_TICKS)
            self.assertEqual(c[c.index("--focal-founder")+1], "5")
            self.assertEqual(c[c.index("--focal-model")+1], "models/r2-w.tgm")

    def test_known_first_denial_and_survivable_shortage(self):
        e = event()
        audit.check_event(e, 945)
        self.assertTrue(e["denied"])
        self.assertEqual(e["before"]["death_step"], 0)
        self.assertEqual(945 + e["after"]["death_step"]*15, 3000)
        p = audit.native_budget(4635, 256, 55, 0)
        self.assertEqual((p["energy"], p["stress"], p["death_step"]), (0, 1, 0))

    def test_corrupt_forecast_decision_cost_and_invalid_flag_fail(self):
        for defect in ("forecast", "decision", "cost", "invalid", "node"):
            e = event()
            if defect == "forecast": e["after"]["stress"] -= 1
            elif defect == "decision": e["denied"] = False
            elif defect == "cost": e["energy_cost"] = 256
            elif defect == "node": e["node"] = 512
            else: e["invalid"] = True
            with self.subTest(defect=defect), self.assertRaises(RuntimeError): audit.check_event(e, 945)

    def test_daylight_is_unsupported_not_a_dark_survival_claim(self):
        p = audit.native_budget(4620, 0, 512, 7)
        self.assertFalse(p["supported"])
        self.assertEqual((p["energy"], p["stress"], p["payments"], p["death_step"]), (0, 7, 0, 0))

    def test_allowed_native_candidate_and_census_are_not_rewritten(self):
        rows = accounting_fixture()
        old = copy.deepcopy(rows)
        with patch.object(audit.startup, "STOP", 15):
            transformed, counts = audit.accounting_rows(rows, "guard")
        self.assertEqual(rows, old)
        self.assertEqual(transformed, rows)
        self.assertEqual(counts["evaluated"], {"growth": 1})
        self.assertEqual(counts["counts"]["out-of-scope"], 1)

    def test_only_denied_uncommitted_growth_bids_are_removed(self):
        rows = accounting_fixture(denied=True)
        # Budget parity is tested separately; isolate a rejected candidate's bookkeeping.
        with patch.object(audit.startup, "STOP", 15), patch.object(audit, "check_event"):
            transformed, counts = audit.accounting_rows(rows, "guard")
        self.assertEqual(transformed, [rows[0], rows[2]])
        self.assertEqual(counts["counts"]["uncommitted_bids_removed"], 1)
        self.assertEqual(counts["denied"], {"growth": 1})

    def test_missing_event_wrong_node_or_counter_cannot_hide_an_action(self):
        for defect in ("event", "counter", "node", "duplicate", "order", "missing_census", "overflow"):
            rows = accounting_fixture()
            a = rows[-1]["dark_guard"]
            if defect == "event": a["events"] = []
            elif defect == "counter": a["evaluated"] = [0,0,0]
            elif defect == "node": a["events"][0]["node"] = 2
            elif defect == "duplicate": a["events"] *= 2; a["evaluated"] = [2,0,0]
            elif defect == "order": rows[1]["tick"] = 30
            elif defect == "missing_census": rows.pop()
            else: a["overflow"] = True
            with self.subTest(defect=defect), patch.object(audit.startup, "STOP", 15), self.assertRaises(RuntimeError):
                audit.accounting_rows(rows, "guard")

    def test_control_refuses_guard_metadata(self):
        with patch.object(audit.startup, "STOP", 15), self.assertRaisesRegex(RuntimeError, "control unexpectedly"):
            audit.accounting_rows(accounting_fixture(), "control")

    def test_first_divergence_requires_native_expense_isolation(self):
        a = {"type": "world", "tick": 945, "plants": [{"id": 5, "energy": 139, "water": 280, "nodes": 34}]}
        b = {"type": "world", "tick": 945, "plants": [{"id": 5, "energy": 148, "water": 285, "nodes": 33}],
             "dark_guard": {"events": [event()]}}
        self.assertEqual(audit.check_prefix([a], [b])["tick"], 945)
        b["plants"][0]["energy"] += 1
        with self.assertRaisesRegex(RuntimeError, "isolate"): audit.check_prefix([a], [b])
        b["tick"] = 930
        with self.assertRaisesRegex(RuntimeError, "declared"): audit.check_prefix([a], [b])

    def test_native_compile_guards_forbid_firmware_and_invalid_ecology(self):
        root = audit.experiment.ROOT
        common = ["cc", "-E", "-x", "c", "-I", str(root/"src"), "-DTOY_FACTORY_GARDEN_DARK_GUARD=1"]
        options = ["LEAF_MAINTENANCE", "LARGE_POOL", "COMBINED_EXPERIMENT", "WIDE_DISPERSAL", "WATER_HEADROOM"]
        valid = [f"-DTOY_FACTORY_GARDEN_{x}=1" for x in options]
        for extra in ([], valid + ["-D__ZEPHYR__=1"], valid + ["-DTOY_FACTORY_GARDEN_SEED_RESERVE=1"],
                      valid + ["-DTOY_FACTORY_GARDEN_FOCAL_SEED_VETO=1"], valid + ["-DTOY_FACTORY_GARDEN_BOTTOM_DRAINAGE=1"]):
            r = subprocess.run([*common, *extra, "-"], input='#include "garden_world.h"\n', text=True, capture_output=True)
            self.assertNotEqual(r.returncode, 0)
        r = subprocess.run([*common, *valid, "-"], input='#include "garden_world.h"\n', text=True, capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_all_6144_native_reference_cases_match_independent_python(self):
        if BUILD is None:
            self.skipTest("pass --build for native reference matrix")
        result = subprocess.run([str(BUILD/"toy-factory-garden-dark-guard-test"), "--reference"],
                                check=True, text=True, capture_output=True)
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), 6144)
        for line in lines:
            phase, energy, nodes, stress, supported, *fields = map(int, line.split())
            p = audit.native_budget(((phase-64) % 256)*15, energy, nodes, stress)
            self.assertEqual(bool(supported), p.pop("supported"))
            self.assertEqual(fields, [p[k] for k in ("energy", "stress", "peak_stress", "upkeep", "dark_steps",
                                                    "payments", "first_shortage_step", "death_step")])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve() if args.build else None
    unittest.main(argv=[__file__, *rest])
