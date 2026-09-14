#!/usr/bin/env python3
"""Exercise winner attribution and the living/dead/newborn tip ledger."""

import copy
import json
import unittest

import garden_tip_audit as audit


def bid(tick, action, *, index=1, priority=10, depth=2, maximum=5, flags=None, identity=1):
    return {"type": "bid", "tick": tick, "id": identity, "tip_audit_version": 1,
            "tip_index": index, "depth": depth, "maximum_depth": maximum,
            "tissue": 0, "x": 40, "y": 60, "priority": priority, "action": action,
            "original_priority": priority, "original_action": action,
            "candidates": [{"flags": f} for f in (flags if flags is not None else [3]*5)]}


def trace():
    plant = {"id": 1, "parent": 0, "species": "flower", "dead": False,
             "nodes": 4, "tips": 3, "reproduction_cooldown": 0,
             "agent": dict.fromkeys(("decisions", "extend", "wait", "finish"), 0)}
    rows = [{"type": "world", "tick": 0, "plants": [copy.deepcopy(plant)]}]
    actions = {15: bid(15, 1), 30: bid(30, 0), 45: bid(45, 2, depth=5),
               60: bid(60, 2, flags=[0]*5), 75: bid(75, 2, flags=[5, 9, 13, 0, 0]),
               90: bid(90, 2)}
    for tick in range(15, 181, 15):
        if tick in actions:
            winner = actions[tick]
            rows.append(winner)
            if tick == 15:
                # A tied later FINISH bid loses; it must not terminate anything.
                rows.append(bid(tick, 2, index=2, depth=5))
                plant["nodes"] += 1
                plant["tips"] += 1
            action = ("wait", "extend", "finish")[winner["action"]]
            plant["agent"]["decisions"] += 1
            plant["agent"][action] += 1
            plant["agent"].update({"last_"+k: winner[k] for k in ("action", "priority", "tissue", "x", "y")})
            if action == "finish":
                plant["tips"] -= 1
        plant["reproduction_cooldown"] = 16 if tick == 120 else 0
        if tick == 150:
            plant["dead"] = True
        rows.append({"type": "world", "tick": tick, "plants": [copy.deepcopy(plant)]})
    return rows


def analyze(rows):
    return audit.analyze_stream(map(json.dumps, rows), 180, 60, 256)


class TipTests(unittest.TestCase):
    def test_winner_reasons_and_exposure(self):
        result = analyze(trace())
        self.assertEqual(result["totals"]["offered_bids"], 7)
        self.assertEqual(result["totals"]["committed"], 6)
        self.assertEqual(result["totals"]["branch_tips"], 1)
        self.assertEqual(result["totals"]["terminated_tips"], 4)
        self.assertEqual(result["totals"]["final_tips"], 0)
        self.assertEqual([e["reason"] for e in result["terminations"]],
                         ["depth_limit", "no_available_candidate", "no_available_candidate", "policy_finish_available"])
        self.assertEqual(result["terminations"][1]["in_bounds"], 0)
        self.assertEqual(result["terminations"][2]["own_blocked"], 2)
        self.assertEqual(result["terminations"][2]["foreign_blocked"], 2)
        self.assertEqual(result["windows"]["late"]["finish"], 2)
        self.assertEqual(result["windows"]["whole"]["living_steps"], 10)
        self.assertEqual(result["windows"]["whole"]["tipless_steps"], 4)
        lineage = result["lineages"][0]
        self.assertEqual((lineage["tipless_tick"], lineage["last_decision_tick"], lineage["death_tick"]), (90, 90, 150))
        self.assertEqual(lineage["tipless_ticks"], 60)
        self.assertEqual(lineage["seeds_after_tipless"], 1)

    def test_active_death_does_not_count_as_finish(self):
        rows = [r for r in trace() if r["tick"] <= 45]
        plant = copy.deepcopy(rows[-1]["plants"][0])
        plant.update(dead=True, tips=0)
        rows.extend({"type": "world", "tick": t, "plants": [plant]} for t in range(60, 181, 15))
        result = analyze(rows)
        self.assertEqual(result["totals"]["death_tips"], 3)
        self.assertEqual(result["totals"]["terminated_tips"], 1)
        self.assertIsNone(result["lineages"][0]["tipless_tick"])

    def test_failed_extension_is_a_distinct_action(self):
        rows = trace()
        for r in rows:
            if r["tick"] == 60 and r["type"] == "bid":
                r.update(action=1, original_action=1)
            if r["tick"] >= 60 and r["type"] == "world":
                agent = r["plants"][0]["agent"]
                agent["finish"] -= 1
                agent["extend"] += 1
                if r["tick"] == 60:
                    agent["last_action"] = 1
        self.assertEqual(analyze(rows)["totals"]["failed_extensions"], 1)

    def test_corruption_is_not_attributed(self):
        for mode in ("missing_tick", "truncated", "metadata", "winner", "tip_delta", "node_delta", "duplicate", "override", "no_bid"):
            with self.subTest(mode=mode):
                rows = trace()
                if mode == "missing_tick":
                    rows = [r for r in rows if r["tick"] != 120]
                elif mode == "truncated":
                    rows.pop()
                elif mode == "metadata":
                    rows[1].pop("maximum_depth")
                elif mode == "winner":
                    rows[2].update(priority=11, original_priority=11)
                elif mode == "tip_delta":
                    rows[3]["plants"][0]["tips"] += 1
                elif mode == "node_delta":
                    rows[3]["plants"][0]["nodes"] += 1
                elif mode == "duplicate":
                    rows[2]["tip_index"] = 1
                elif mode == "override":
                    rows[1]["original_action"] = 2
                else:
                    rows = [r for r in rows if r["type"] != "bid"]
                with self.assertRaises((RuntimeError, KeyError)):
                    analyze(rows)

    def test_newborn_action_and_empty_world(self):
        rows = trace()
        initial = {"type": "world", "tick": 0, "plants": []}
        rows[0] = initial
        result = analyze(rows)
        self.assertEqual(result["totals"]["initial_tips"], 0)
        self.assertEqual(result["totals"]["newborn_tips"], 3)
        empty = [{"type": "world", "tick": t, "plants": []} for t in range(0, 181, 15)]
        self.assertEqual(analyze(empty)["totals"]["final_tips"], 0)


if __name__ == "__main__":
    unittest.main()
