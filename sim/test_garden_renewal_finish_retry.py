#!/usr/bin/env python3
"""Retry protocol boundaries, prefix identity and actual paid-action exports."""
import argparse
import copy
from pathlib import Path
import subprocess
import unittest

import garden_renewal_finish_retry as audit
from test_garden_renewal_purchase_veto import divergence

BUILD = None


def metadata(tick):
    return {"rule":audit.VETO,"arm":"finish-retry","tick":69885,"id":22,
            "hits":int(tick >= 69885)+int(tick >= 69900),"stop_tick":69915}


def receipt_fixture(index):
    a,b = divergence("finish")
    t = audit.TARGETS[index]
    for row,paid in ((a,True),(b,False)):
        row["tick"] = t["tick"]
        row["plants"][0].update(energy=t["energy"]-9*paid,water=t["water"]-5*paid)
        row["dark_guard"]["events"][0].update(energy=t["energy"],water=t["water"])
    b["purchase_veto"] = metadata(t["tick"])
    return a,b


class RetryTests(unittest.TestCase):
    def test_fixed_three_arm_scope(self):
        calls = audit.commands()
        self.assertEqual(len(calls),24)
        self.assertEqual(len(set(n for n,_ in calls)),24)
        self.assertEqual(sum(n.endswith(".gz") for n,_ in calls),6)
        self.assertEqual(sum("--framebuffer" in c for _,c in calls),18)
        self.assertEqual(audit.ARMS,("control","finish","finish-retry"))
        self.assertEqual(audit.FRAMES,(72960,122880,245760))
        self.assertEqual([t["tick"] for t in audit.TARGETS],[69885,69900])
        self.assertEqual(audit.HANDOFF,69915)
        for name,c in calls:
            arm = name.split("/")[1].split(".")[0]
            self.assertEqual(c.count("--purchase-veto"),int(arm != "control"))
            if arm != "control": self.assertEqual(c[c.index("--purchase-veto")+1],arm)
            self.assertNotIn("extension",c)
            self.assertIn("0xabf7af73",c)
            self.assertIn("0x05d87ca0",c)

    def test_metadata_exact_boundaries(self):
        for tick in (0,69884,69885,69899,69900,69914,69915,245760):
            audit.check_metadata({"tick":tick,"purchase_veto":metadata(tick)})
        for change in ({"hits":3},{"stop_tick":69930},{"id":23},{"rule":audit.prior.VETO}):
            with self.assertRaises(RuntimeError):
                audit.check_metadata({"tick":69915,"purchase_veto":{**metadata(69915),**change}})

    def test_both_exact_prefix_divergences(self):
        for index in (0,1):
            a,b = receipt_fixture(index)
            self.assertEqual(audit.check_prefix([a],[b],audit.TARGETS[index])["tick"],a["tick"])

    def test_second_prefix_keeps_first_intervention_history(self):
        a,b = receipt_fixture(1)
        x,y = receipt_fixture(0)
        prefix = copy.deepcopy(y)
        prefix["purchase_veto"] = {"rule":audit.prior.VETO,"arm":"finish","tick":69885,"id":22,"hits":1}
        result = audit.check_prefix([prefix,a],[y,b],audit.TARGETS[1])
        self.assertEqual(result["matching_records"],1)
        prefix["plants"][0]["energy"] += 1
        with self.assertRaises(RuntimeError): audit.check_prefix([prefix,a],[y,b],audit.TARGETS[1])

    def test_receipt_or_neighbour_corruption_fails(self):
        for defect in ("tip","energy","cost","counter","guard","other","when"):
            a,b = receipt_fixture(1)
            if defect == "tip": b["plants"][0]["tips"] -= 1
            elif defect == "energy": b["plants"][0]["energy"] += 1
            elif defect == "cost": b["dark_guard"]["events"][0]["energy_cost"] -= 1
            elif defect == "counter": b["purchase_veto"]["hits"] = 1
            elif defect == "guard": b["dark_guard"]["events"][0]["denied"] = True
            elif defect == "other":
                a["plants"].append({"id":23,"energy":45})
                b["plants"].append({"id":23,"energy":46})
            else: b["tick"] -= 15
            with self.subTest(defect=defect),self.assertRaises(RuntimeError):
                audit.check_prefix([a],[b],audit.TARGETS[1])

    def test_truncated_prefix_and_missing_divergence_fail(self):
        a,b = receipt_fixture(1)
        with self.assertRaises(RuntimeError): audit.check_prefix([a],[],audit.TARGETS[1])
        with self.assertRaises(RuntimeError): audit.check_prefix([b],[b],audit.TARGETS[1])

    def test_handoff_requires_same_tip_supported_forecast(self):
        raw = [{"type":"bid","tick":t["tick"],"id":22,"priority":32767,"action":2,"tip_index":271}
               for t in audit.TARGETS]
        event = {"id":22,"kind":"growth","node":271,"before":{"supported":True},"after":{"supported":True}}
        raw.append({"type":"world","tick":69915,"purchase_veto":metadata(69915),
                    "dark_guard":{"events":[event]},"plants":[{"id":22}]})
        self.assertEqual(audit.check_receipts(raw)["tick"],69915)
        for defect in ("support","winner","tip","missing"):
            bad = copy.deepcopy(raw)
            if defect == "support": bad[-1]["dark_guard"]["events"][0]["after"]["supported"] = False
            elif defect == "winner": bad[0]["action"] = 1
            elif defect == "tip": bad[-1]["dark_guard"]["events"][0]["node"] = 270
            else: bad.pop()
            with self.subTest(defect=defect),self.assertRaises(RuntimeError): audit.check_receipts(bad)

    def test_export_does_not_call_forced_refusal_a_paid_retry(self):
        h = [{"state":{"tick":tick,"phase":phase,"dead":False},
              "budget":{"energy_growth":cost},"events":[{"kind":"growth","denied":False}]}
             for tick,phase,cost in ((69885,115,0),(69900,116,0),(69915,117,0),(72165,11,9))]
        value = audit.portable_target({"lineage":{"id":22},"history":h})
        self.assertEqual(value["first_later_accepted_growth"]["tick"],72165)
        h[-1]["budget"]["energy_growth"] = 0
        self.assertIsNone(audit.portable_target({"lineage":{"id":22},"history":h})["first_later_accepted_growth"])

    def test_native_cli_duplicate_or_unknown_retry_fails(self):
        if BUILD is None: self.skipTest("native CLI requires --build")
        for tool in ("inspect","replay"):
            base = [str(BUILD/("toy-factory-garden-"+tool)),"-","rainfed","adaptive","123","--ticks","15"]
            for extra in (["--purchase-veto","finish-retry","--purchase-veto","finish"],
                          ["--purchase-veto","finish-retry","--purchase-veto","finish-retry"],
                          ["--purchase-veto","finish-retry-all"]):
                result = subprocess.run([*base,*extra],capture_output=True)
                self.assertEqual(result.returncode,2)
                self.assertEqual(result.stdout,b"")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build",type=Path)
    args,remaining = parser.parse_known_args()
    BUILD = args.build
    unittest.main(argv=[__file__,*remaining])
