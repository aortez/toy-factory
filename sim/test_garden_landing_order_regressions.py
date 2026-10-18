#!/usr/bin/env python3
"""Saved-event provenance, allocation chains, survival and censoring; no replay."""

import copy
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_order_regressions as audit

D = audit.DAY
RESULTS = "benchmarks/garden-seasons/landing-order-regressions-results.json.gz"
RESULTS_SHA = "9163a9ba3839ecd07dcc35773d8945aa90830add3ea44e33f201a369bb6a20d6"


class RegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = audit.load(audit.ROOT / audit.INPUT, audit.INPUT_SHA)
        cls.events = audit.load(audit.ROOT / audit.EVENTS, audit.EVENTS_SHA)
        cls.saved = audit.load(audit.ROOT / RESULTS, RESULTS_SHA)

    def test_exact_recomputation_and_full_panel_without_simulation(self):
        before = copy.deepcopy((self.data, self.events))
        with patch.object(audit.previous.training, "native", side_effect=AssertionError("ran simulation")):
            actual = audit.analyze(self.data, self.events)
        self.assertEqual(actual, self.saved)
        self.assertEqual((self.data, self.events), before)
        self.assertEqual((actual["native_runs"], actual["training_runs"], len(actual["panel"])), (0, 0, 12))
        self.assertEqual(actual["screen_unchanged"], self.data["summary"])

    def test_event_union_and_first_divergence_observations(self):
        self.assertEqual([len(c["arms"]["fixed"]["rows"]) for c in self.events["cases"]], [133, 115, 119])
        for (w, context), case in zip(audit.selected(self.data), self.events["cases"], strict=True):
            expected = audit.event_ticks(w["contexts"][context])
            self.assertEqual(expected[0], audit.AT)
            for arm in audit.ARMS:
                self.assertEqual([r["tick"] for r in case["arms"][arm]["rows"]], expected)
        self.assertEqual([c["first_allocation_change"]["tick"] for c in self.saved["cases"]], [649740, 613980, 610860])
        self.assertTrue(all(c["first_allocation_change"][k] for c in self.saved["cases"]
                            for k in ("previous_observations_equal", "pre_purchase_observations_equal")))

    def test_s34_new_owner_landing_and_release_refill_chain(self):
        case = self.saved["cases"][0]
        first = case["first_allocation_change"]["arms"]
        fixed, rotated = (first[a]["purchases"][0] for a in audit.ARMS)
        self.assertEqual([(s["seed"]["parent"], s["seed"]["column"], s["seed"]["outcome"])
                          for s in (fixed, rotated)], [(18, 11, "germinated"), (19, 18, "expired")])
        masks = rotated["observed_checks"]["mature_masks"]
        self.assertEqual(sum(masks.values()), 8184)
        self.assertTrue(all(int(m) & 34 == 34 for m in masks))
        tick = next(e for e in case["early_bank_timeline"] if e["tick"] == 661020)
        self.assertEqual([tick["arms"][a]["bank_at_entry"] for a in audit.ARMS], [7, 8])
        self.assertEqual([s["parent"] for s in tick["arms"]["fixed"]["purchases"]], [18])
        self.assertEqual(tick["arms"]["rotating"]["purchases"], [])
        children = case["arms"]["fixed"]["early"]["children"]
        self.assertEqual([p["first_day"] for p in children], ["died", "died", "confirmed"])
        self.assertEqual([p["resource_window"]["death_shortage"] for p in children], ["energy", "energy", "water"])
        self.assertEqual((children[-1]["life"]["seeds_created"], children[-1]["confirmed_children"]), (0, []))
        # The same numeric ID in the diverged run is a different birth event.
        rotated26 = next(p for p in case["arms"]["rotating"]["new_plants"] if p["life"]["id"] == 26)
        self.assertNotEqual(children[-1]["birth_seed"], rotated26["birth_seed"])

    def test_s34_incumbent_survival_is_not_a_seed_fee_death(self):
        case = self.saved["cases"][0]
        for identity, fixed_tick, rotated_tick, fixed_water in ((18, 767820, 828840, 492), (23, 767760, 828900, 491)):
            pair = [next(p for p in case["arms"][a]["incumbents"] if p["plant"]["life"]["id"] == identity)
                    for a in audit.ARMS]
            self.assertEqual([p["plant"]["life"]["death_tick"] for p in pair], [fixed_tick, rotated_tick])
            self.assertEqual([p["days"]["196"]["resources"]["water"]["initial"] for p in pair], [fixed_water, 512])
            for p in pair:
                for day in range(196, 200):
                    self.assertEqual(p["days"][str(day)]["resources"]["water"]["reproduction"], 0)
            self.assertEqual(pair[1]["days"]["199"]["resources"]["water"]["final"], 6)
            self.assertLess(pair[1]["days"]["200"]["max_stress"], 8)

    def test_s35_supply_deaths_and_late_pending_are_separate(self):
        pair = self.saved["cases"][1]["arms"]
        fixed, rotated = (pair[a]["closing"] for a in audit.ARMS)
        self.assertEqual([len(c["purchases"]) for c in (fixed, rotated)], [10, 11])
        self.assertEqual([c["confirmations"] for c in (fixed, rotated)], [[45, 46], []])
        self.assertEqual([c["birth_outcomes"] for c in (fixed, rotated)], [{"confirmed": 2}, {"died": 3}])
        self.assertTrue(all(p["resource_window"] is None for p in rotated["children"]))
        tail = pair["rotating"]["tail"]
        self.assertEqual(tail["birth_outcomes"], {"pending": 2})
        self.assertTrue(all(p["life"]["death_tick"] is None and p["life"]["birth_tick"] + D > audit.STOP
                            for p in tail["children"]))

    def test_m33_all_four_misses_are_bank_only_but_buyers_are_not_all_sterile(self):
        p = self.saved["cases"][2]["arms"]["rotating"]["early_opening_misses"][0]
        self.assertEqual(p["id"], 28)
        self.assertEqual([m["rank"] for m in p["misses"]], [4, 4, 3, 3])
        self.assertTrue(all(m["visit"]["blockers"] == 4 and m["bank_at_entry"] == 7 and
                            m["visit"]["energy"] >= m["visit"]["energy_required"] and
                            m["visit"]["water"] >= m["visit"]["water_required"] for m in p["misses"]))
        self.assertEqual([m["purchased_seeds"][0]["child"]["first_day"] if m["purchased_seeds"][0]["child"] else
                          m["purchased_seeds"][0]["seed"]["outcome"] for m in p["misses"]],
                         ["died", "confirmed", "expired", "died"])

    def test_ancestry_is_within_run_and_has_exact_birth_seed_links(self):
        for case in self.saved["cases"]:
            for arm in case["arms"].values():
                for entry in arm["ancestry"]:
                    path = entry["path"]
                    self.assertEqual(path[0]["parent"], 0)
                    self.assertEqual(path[-1]["id"], entry["id"])
                    for a, b in zip(path, path[1:]):
                        self.assertEqual(b["parent"], a["id"])
                        self.assertEqual(b["birth_seed"]["child_id"], b["id"])
                        self.assertEqual(b["birth_seed"]["end_tick"], b["birth_tick"])

    def test_cohort_boundaries_death_on_due_tick_and_horizon(self):
        start, stop = 222 * D, 254 * D
        lives = [{"id": i, "parent": 0, "birth_tick": birth, "death_tick": death}
                 for i, birth, death in ((1, start, None), (2, start + audit.STEP, start + audit.STEP + D),
                    (3, stop, None), (4, stop + audit.STEP, None), (5, audit.STOP - audit.STEP, None))]
        a = {"result": {"lineages": lives, "seeds": []}, "audit": {"gates": {"resources": {"plants": [], "seeds": []}}}}
        c = audit.cohort(a, start, stop)
        self.assertEqual([p["life"]["id"] for p in c["children"]], [2, 3])
        self.assertEqual(c["birth_outcomes"], {"died": 1, "confirmed": 1})
        self.assertEqual(c["confirmations"], [1])
        self.assertEqual(audit.cohort(a, stop, audit.STOP)["birth_outcomes"], {"confirmed": 1, "pending": 1})

    def test_missing_event_wrong_identity_order_gate_or_debit_rejected(self):
        for fault in ("missing", "identity", "order", "gate", "debit"):
            bad = copy.deepcopy(self.events)
            raw = bad["cases"][0]["arms"]["fixed"]
            row = raw["rows"][0]
            if fault == "missing":
                raw["rows"].pop()
            elif fault == "identity":
                raw["traces"]["stand"]["sha256"] = "0" * 64
            elif fault == "order":
                row["stand"]["reproduction"].reverse()
            elif fault == "gate":
                row["stand"]["reproduction"][0]["blockers"] ^= 4
            else:
                row["adult"]["plants"][0]["stages"][-1][0] -= 1
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                audit.validate_events(self.data, bad)

    def test_no_clobber_and_corrupt_inputs_fail_without_replay(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "existing.gz"
            path.write_bytes(b"preserve")
            with patch.object(audit.sys, "argv", ["audit", "--out", str(path)]), patch.object(audit, "load", side_effect=AssertionError("read before validation")), patch("sys.stderr", new=io.StringIO()):
                self.assertEqual(audit.main(), 1)
            self.assertEqual(path.read_bytes(), b"preserve")
            with self.assertRaises(RuntimeError):
                audit.load(path, audit.INPUT_SHA)
            with patch.object(audit, "digest", return_value="bad"), self.assertRaises(RuntimeError):
                audit.extract(Path(root), self.data)


if __name__ == "__main__":
    unittest.main()
