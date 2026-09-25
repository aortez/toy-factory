#!/usr/bin/env python3
"""Synthetic checks for the saved node/death audit; no simulator execution."""
import copy
import hashlib
import unittest
from unittest import mock

import garden_renewal_node_pressure as audit


def plant(identity, count, *, dead=False, parent=0, tips=1):
    return {"id": identity, "nodes": count, "roots": min(2, count), "dead": dead,
            "parent": parent, "tips": tips, "species": "shrub", "vigor": 0,
            "energy": 64, "water": 24, "leaves": 1, "active_leaves": 1,
            "stress": 0, "flags": 0, "energy_income": 0, "water_income": 0,
            "leaf": {"conditions": [255]}}


def row(plants, tick=audit.AFTER, births=0):
    return {"tick": tick, "births": births, "plants": plants,
            "nodes": sum(p["nodes"] for p in plants)}


def values():
    return dict.fromkeys((*audit.light.resources.TOTAL_KEYS, "energy_renewal", "water_renewal"), 0)


class LedgerTests(unittest.TestCase):
    def test_stage_order_and_no_input_mutation(self):
        before = row([plant(1, 100), plant(2, 50, dead=True), plant(3, 30)])
        after = row([plant(1, 101), plant(3, 31), plant(4, 5, parent=1)], audit.AFTER+15, 1)
        frozen = copy.deepcopy((before, after))
        stages = audit.ledger(before, after)
        self.assertEqual(stages, {"seed_entry_nodes": 130, "growth_entry_nodes": 134,
            "plant_entry_nodes": {1: 134, 3: 135, 4: 136}, "reclaimed_nodes": 50,
            "reclaimed_plants": 1, "seedling_nodes": 4, "growth_nodes": 3})
        self.assertEqual((before, after), frozen)

    def test_final_allocation_blocks_later_owner_not_earlier_one(self):
        before = row([plant(1, 256), plant(2, 255)])
        after = row([plant(1, 257), plant(2, 255)], audit.AFTER+15)
        stages = audit.ledger(before, after)
        self.assertEqual(stages["plant_entry_nodes"], {1: 511, 2: 512})
        self.assertEqual(stages["seed_entry_nodes"], 511)

    def test_full_pool_death_does_not_free_nodes(self):
        before = row([plant(1, 256), plant(2, 256)])
        after = row([plant(1, 256, dead=True), plant(2, 256)], audit.AFTER+15)
        stages = audit.ledger(before, after)
        self.assertEqual(stages["reclaimed_nodes"], 0)
        self.assertEqual(stages["plant_entry_nodes"], {1: 512, 2: 512})

    def test_birth_reservation_precedes_all_growth(self):
        before = row([plant(1, 508)])
        after = row([plant(1, 508), plant(2, 4, parent=1)], audit.AFTER+15, 1)
        stages = audit.ledger(before, after)
        self.assertEqual(stages["seed_entry_nodes"], 508)
        self.assertEqual(stages["plant_entry_nodes"], {1: 512, 2: 512})

    def test_bad_ledgers_fail_closed(self):
        for bad in ("tick", "unowned", "live_removal", "order", "birth", "growth", "root", "duplicate", "overfull", "revived"):
            before = row([plant(1, 50), plant(2, 30, dead=True)])
            after = row([plant(1, 51), plant(2, 30, dead=True)], audit.AFTER+15)
            if bad == "tick": after["tick"] += 15
            if bad == "unowned": after["nodes"] -= 1
            if bad == "live_removal": after = row([plant(2, 30, dead=True)], audit.AFTER+15)
            if bad == "order": after["plants"].reverse()
            if bad == "birth": after["births"] = 1
            if bad == "growth": after["plants"][0]["nodes"] += 1; after["nodes"] += 1
            if bad == "root": after["plants"][0]["roots"] += 2
            if bad == "duplicate": after["plants"].append(after["plants"][0]); after["nodes"] += 51
            if bad == "overfull": after["plants"][0]["nodes"] = 500; after["nodes"] = 530
            if bad == "revived": after["plants"][1]["dead"] = False
            with self.subTest(bad=bad), self.assertRaises(RuntimeError): audit.ledger(before, after)


class PressureTests(unittest.TestCase):
    def test_full_entry_has_unknown_request_not_rejected_extend(self):
        old = plant(1, 50)
        result = audit.pressure(old, old, audit.AFTER+15, 512, [], values())
        self.assertEqual(result["full_entry_tip_no_renewal_affordable"], 1)
        self.assertEqual(result["allocated_nodes"], 0)
        self.assertNotIn("rejected_extensions", result)

    def test_leaf_renewal_can_succeed_at_capacity(self):
        p, v = plant(1, 50), values()
        v.update(energy_renewal=9, water_renewal=5)
        result = audit.pressure(p, p, audit.AFTER+15, 512, [], v)
        self.assertEqual(result["full_entry_renewals"], 1)
        self.assertEqual(result["full_entry_tip_no_renewal"], 0)

    def test_tipless_or_poor_owner_is_not_growth_ready(self):
        p = plant(1, 50, tips=0)
        self.assertEqual(audit.pressure(p, p, audit.AFTER+15, 512, [], values())["full_entry_with_tips"], 0)
        p["tips"], p["water"] = 1, 4
        self.assertEqual(audit.pressure(p, p, audit.AFTER+15, 512, [], values())["full_entry_tip_no_renewal_affordable"], 0)

    def test_seed_expense_is_after_growth_stage(self):
        p, v = plant(1, 50), values()
        p["energy"], p["water"] = 0, 0
        v.update(energy_seeds=48, water_seeds=24)
        self.assertEqual(audit.pressure(p, p, audit.AFTER+15, 512, [], v)["full_entry_tip_no_renewal_affordable"], 1)

    def test_end_fullness_does_not_prove_earlier_gate(self):
        p = plant(1, 50)
        result = audit.pressure(p, p, audit.AFTER+15, 511, [{"action": 1}], values())
        self.assertEqual(result["full_entry"], 0)
        self.assertEqual(result["offered_bid_steps"], 1)
        with self.assertRaises(RuntimeError): audit.pressure(p, p, audit.AFTER+15, 512, [{"action": 0}], values())
        for action in ("extensions", "finishes", "waits"):
            v = {**values(), action: 1}
            with self.subTest(action=action), self.assertRaises(RuntimeError):
                audit.pressure(p, p, audit.AFTER+15, 512, [], v)


class BoundaryTests(unittest.TestCase):
    def test_matched_window_excludes_start_and_terminal_step(self):
        death = audit.AFTER+2*audit.DAY
        entries = [{"state": {"tick": t, "phase": (64+t//15) % 256, "dead": t == death},
                    "terminal": "natural" if t == death else None, "budget": values()}
                   for t in range(death-audit.DAY, death+15, 15)]
        with mock.patch.object(audit, "summarize_history", return_value={}) as summarize:
            audit.matched_window(entries, death)
            selected, origin = summarize.call_args.args
            self.assertEqual(len(selected), 255)
            self.assertEqual(selected[0]["state"]["tick"], death-audit.DAY+15)
            self.assertEqual(selected[-1]["state"]["tick"], death-15)
            self.assertEqual(origin["tick"], death-audit.DAY)
        for broken in (entries[1:], entries[:50]+entries[51:], entries[:50]+entries[49:]):
            with self.assertRaises(RuntimeError): audit.matched_window(broken, death)

    def test_terminal_budget_stays_unknown(self):
        old, p = plant(1, 50), plant(1, 50, dead=True, tips=0)
        old["stress"] = 7
        p.update(stress=8, flags=3, energy=0, water=0)
        result = audit.terminal(old, p, audit.AFTER+60, [], None)
        self.assertIsNone(result["budget"])
        for bad in ("income", "stress", "tick", "bid", "leaf"):
            q, tick, bids, leaf = copy.deepcopy(p), audit.AFTER+60, [], None
            if bad == "income": q["energy_income"] = 1
            if bad == "stress": q["stress"] = 7
            if bad == "tick": tick += 15
            if bad == "bid": bids = [{}]
            if bad == "leaf": leaf = {}
            with self.subTest(bad=bad), self.assertRaises(RuntimeError): audit.terminal(old, q, tick, bids, leaf)

    def test_full_runs_split_at_gap(self):
        runs = []
        for tick in (100, 115, 145): audit.append_run(runs, tick)
        self.assertEqual(runs, [{"first_tick": 100, "last_tick": 115, "samples": 2},
                               {"first_tick": 145, "last_tick": 145, "samples": 1}])

    def test_only_exact_new_build_registration_is_allowed(self):
        original = ("prefix"+audit.REGISTRATION_ANCHOR+" suffix").encode()
        sha = hashlib.sha256(original).hexdigest()
        current = original.replace(audit.REGISTRATION_ANCHOR.encode(),
                                   (audit.REGISTRATION+audit.REGISTRATION_ANCHOR).encode())
        audit.check_build_registration(original, current, sha)
        for bad in (original, current+b"extra", current.replace(b"prefix", b"changed")):
            with self.assertRaises(RuntimeError): audit.check_build_registration(original, bad, sha)
        with self.assertRaises(RuntimeError): audit.check_build_registration(original, current, "0"*64)

    def test_cli_cannot_capture_or_run_experiments(self):
        with mock.patch("sys.argv", ["audit", "--collect"]), mock.patch("sys.stderr"), self.assertRaises(SystemExit):
            audit.main()


if __name__ == "__main__":
    unittest.main()
