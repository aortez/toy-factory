#!/usr/bin/env python3
"""Fixed protocol, separate veto accounting, and failure checks."""
import argparse
import copy
import subprocess
import unittest
from pathlib import Path

import garden_renewal_purchase_veto as audit
from test_garden_renewal_dark_guard import accounting_fixture

BUILD = None


def divergence(arm):
    t = audit.TARGETS[arm]
    receipt = {k:v for k,v in t.items() if k not in ("tick", "action")}
    receipt.update(kind="growth", denied=False, invalid=False, stress=0, energy_cost=9, water_cost=5)
    action = "extend" if arm == "extension" else "finish"
    p = {"id": t["id"], "energy": t["energy"]-9, "water": t["water"]-5,
         "nodes": t["nodes_after"], "tips": 1, "agent": {action: 5, "decisions": 8}}
    a = {"type": "world", "tick": t["tick"], "plants": [p], "dark_guard": {"events": [receipt]}}
    b = copy.deepcopy(a)
    b["purchase_veto"] = {"rule": audit.VETO, "arm": arm, "tick": t["tick"], "id": t["id"], "hits": 1}
    b["plants"][0].update(energy=t["energy"], water=t["water"], nodes=t["nodes_before"],
                          tips=1+int(arm == "finish"), agent={action: 4, "decisions": 7})
    return a, b


class PurchaseTests(unittest.TestCase):
    def test_fixed_scope(self):
        calls = audit.commands()
        self.assertEqual(len(calls), 24)
        self.assertEqual(len(set(n for n,_ in calls)), 24)
        self.assertEqual(sum(n.endswith(".gz") for n,_ in calls), 6)
        self.assertEqual(sum("--framebuffer" in c for _,c in calls), 18)
        self.assertEqual(audit.FRAMES, (72960, 122880, 245760))
        for name, command in calls:
            arm = name.split("/")[1].split(".")[0]
            self.assertEqual(command.count("--purchase-veto"), int(arm != "control"))
            if arm != "control": self.assertEqual(command[command.index("--purchase-veto")+1], arm)
            self.assertEqual(command[command.index("--focal-founder")+1], "5")
            self.assertIn("0x05d87ca0", command)

    def test_immediate_deltas(self):
        for arm in audit.TARGETS:
            a, b = divergence(arm)
            self.assertEqual(audit.check_prefix([a], [b], arm)["matching_records"], 0)

    def test_prefix_corruption(self):
        a, b = divergence("extension")
        prefix = {"type": "bid", "tick": 66060, "action": 1}
        self.assertEqual(audit.check_prefix([prefix,a], [prefix,b], "extension")["matching_records"], 1)
        with self.assertRaises(RuntimeError):
            audit.check_prefix([prefix,a], [{**prefix, "action": 2},b], "extension")

    def test_wrong_receipt_and_non_target_effect(self):
        for defect in ("hits", "node", "water", "denied", "tip", "other", "tick"):
            a, b = divergence("finish")
            if defect == "hits": b["purchase_veto"]["hits"] = 2
            elif defect == "node": b["dark_guard"]["events"][0]["node"] += 1
            elif defect == "water": b["plants"][0]["water"] += 1
            elif defect == "denied": b["dark_guard"]["events"][0]["denied"] = True
            elif defect == "tip": b["plants"][0]["tips"] -= 1
            elif defect == "other":
                a["plants"].append({"id": 4, "energy": 10})
                b["plants"].append({"id": 4, "energy": 11})
            else: b["tick"] -= 15
            with self.subTest(defect=defect), self.assertRaises(RuntimeError): audit.check_prefix([a], [b], "finish")

    def test_control_has_no_metadata(self):
        with self.assertRaises(RuntimeError): audit.check_metadata({"purchase_veto": {}}, "control")

    def test_forced_veto_keeps_guard_decision_unchanged(self):
        rows = accounting_fixture(denied=True)
        rows[-1]["dark_guard"]["events"][0]["denied"] = False
        rows[-1]["dark_guard"]["denied"] = [0,0,0]
        original = copy.deepcopy(rows)
        output, stats = audit.guard.accounting_rows(rows, "guard", stop=15, growth_vetoes={(15,2)})
        self.assertEqual(rows, original)
        self.assertEqual(output, [rows[0], rows[2]])
        self.assertEqual(stats["denied"], {"growth": 0})
        with self.assertRaises(RuntimeError): audit.guard.accounting_rows(rows, "guard", stop=15)

    def test_missing_or_duplicate_denial_fails(self):
        with self.assertRaises(RuntimeError):
            audit.guard.accounting_rows(accounting_fixture(), "guard", stop=15, growth_vetoes={(30,2)})
        with self.assertRaises(RuntimeError):
            audit.guard.accounting_rows(accounting_fixture(denied=True), "guard", stop=15, growth_vetoes={(15,2)})

    def test_compile_gates(self):
        common = ["cc", "-E", "-x", "c", "-I", str(audit.experiment.ROOT/"src"), "-DTOY_FACTORY_GARDEN_PURCHASE_VETO=1"]
        flags = [f"-DTOY_FACTORY_GARDEN_{n}=1" for n in ("DARK_GUARD", "LEAF_MAINTENANCE", "LARGE_POOL",
                 "COMBINED_EXPERIMENT", "WIDE_DISPERSAL", "WATER_HEADROOM")]
        for extra, good in (([],False), (flags,True), ([*flags,"-D__ZEPHYR__=1"],False)):
            result = subprocess.run([*common,*extra,"-"], input='#include "garden_world.h"\n', text=True, capture_output=True)
            self.assertEqual(result.returncode == 0, good)

    def test_portable_target_keeps_terminal_unknown_and_first_retry(self):
        target = audit.TARGETS["finish"]
        history = [
            {"state": {"tick": 69885, "phase": 115, "dead": False}, "events": []},
            {"state": {"tick": 69900, "phase": 116, "dead": False},
             "events": [{"kind": "growth", "denied": False}]},
            {"state": {"tick": 69915, "phase": 117, "dead": False}, "events": []},
            {"state": {"tick": 72000, "phase": 0, "dead": True}, "events": []},
        ]
        value = audit.portable_target({"lineage": {"id": 22}, "history": history}, target)
        self.assertEqual(value["first_later_accepted_growth"]["tick"], 69900)
        self.assertEqual(value["first_dark_entry"]["state"]["tick"], 69915)
        self.assertTrue(value["last_state"]["dead"])
        self.assertFalse(value["last_live_state"]["dead"])
        self.assertEqual(value["history_steps"], 4)

    def test_native_invalid_cli(self):
        if BUILD is None: self.skipTest("native CLI requires --build")
        for tool in ("inspect", "replay"):
            base = [str(BUILD/("toy-factory-garden-"+tool)), "-", "rainfed", "adaptive", "123", "--ticks", "15"]
            for extra in (["--purchase-veto"], ["--purchase-veto","bogus"],
                          ["--purchase-veto","extension","--purchase-veto","finish"]):
                result = subprocess.run([*base,*extra], capture_output=True)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    args, remaining = parser.parse_known_args()
    BUILD = args.build
    unittest.main(argv=[__file__, *remaining])
