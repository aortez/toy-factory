#!/usr/bin/env python3
"""Fixed-panel completeness and deterministic visual grouping checks."""
import copy
import unittest

import garden_policy_diagnostic as diagnostic


class PanelTest(unittest.TestCase):
    def setUp(self):
        self.manifest = {"status":"complete", "kind":"garden-bottom-drainage",
            "node_capacity":512, "horizon":diagnostic.HORIZON, "rule":diagnostic.drainage.RULE}
        worlds = [(scenario,seed) for scenario in sorted(diagnostic.experiment.SCENARIOS)
            for seed in diagnostic.experiment.trial_seeds(0x6d617463,8)]
        self.cases = [{"id":str(index), "scenario":scenario, "seed":seed, "arm":arm}
            for index,(scenario,seed) in enumerate(worlds,33) for arm in diagnostic.diversity.SCHEDULES]

    def test_complete_capacities_and_default_scope(self):
        for capacity in (256,512):
            manifest = {**self.manifest,"node_capacity":capacity}
            full = diagnostic.panel_cases(manifest,self.cases,"full")
            self.assertEqual(len(full),80)
            self.assertEqual(full,diagnostic.panel_cases(manifest,list(reversed(self.cases)),"full"))
            focused = diagnostic.panel_cases(manifest,self.cases,"focused")
            self.assertEqual(len(focused),10)
            self.assertEqual({(c["scenario"],c["seed"]) for c in focused},
                {("rainfed",seed) for seed in diagnostic.SEEDS})

    def test_bad_manifest_and_scope(self):
        for key,value in (("status","started"),("kind","unrelated"),("node_capacity",1024),
                ("horizon",256*diagnostic.DAY),("rule","different")):
            with self.assertRaises(RuntimeError):
                diagnostic.panel_cases({**self.manifest,key:value},self.cases,"full")
        with self.assertRaises(RuntimeError):
            diagnostic.panel_cases(self.manifest,self.cases,"unknown")

    def test_bad_panel(self):
        variants = [self.cases[:-1], self.cases+[self.cases[-1]], self.cases[:-1]+[self.cases[0]]]
        for key,value in (("id","../../bad"),("id","34"),("scenario","rainfed-crowded"),
                ("seed","00000000"),("arm","unknown")):
            bad = copy.deepcopy(self.cases)
            bad[0][key] = value
            variants.append(bad)
        for cases in variants:
            for panel in ("focused","full"):
                with self.assertRaises(RuntimeError):
                    diagnostic.panel_cases(self.manifest,cases,panel)

    def test_group_columns_and_layouts(self):
        results = [{**case,"frames":[{"id":f"{case['id']}.{case['arm']}.{setting}.{policy}"}]}
            for case in self.cases for setting in ("off","on") for policy in ("neural","reserve")]
        worlds = sorted({(c["scenario"],c["seed"]) for c in self.cases})
        groups = diagnostic.frame_groups(results,worlds)
        self.assertEqual(len(groups),80)
        self.assertEqual(len({f["id"] for g in groups for f in g}),320)
        for group in groups:
            self.assertEqual([f["id"].split(".")[-2:] for f in group],
                [[setting,policy] for setting in ("off","on") for policy in ("neural","reserve")])


if __name__ == "__main__":
    unittest.main()
