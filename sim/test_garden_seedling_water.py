#!/usr/bin/env python3
"""Offline seedling accounting, root aliasing, censoring and integrity checks."""
import copy
import json
import unittest

import garden_seedling_water as audit


def plant():
    return {"id": 2, "parent": 1, "species": "shrub", "generation": 1, "column": 12,
        "dead": False, "energy": 64, "water": 24, "vigor": 0, "energy_income": 0,
        "water_income": 0, "nodes": 4, "roots": 2, "stress": 0, "flags": 0,
        "reproduction_cooldown": 0, "root_cells": [[12, 0, 1, 9], [12, 0, 1, 9]],
        "agent": {"decisions": 0, "root_extend": 0, "shoot_extend": 0, "extend": 0,
                  "finish": 0, "wait": 0, "last_action": 1}}


def world(tick, plants):
    return {"type": "world", "tick": tick, "hash": f"{tick:08x}",
        "sun_phase": (64 + tick // 15) % 256, "rain_rate": 0, "soil": {"water": 100},
        "leaf_environment": "leaf-maintenance-v1", "leaf_policy": "selective",
        "node_capacity": 512, "plants": copy.deepcopy(plants)}


def fixture(end=1920):
    p = plant()
    rows = [world(0, [])]
    for tick in range(15, end + 1, 15):
        if tick % 60 == 0:
            p["energy"] -= 1
            if p["water"]:
                p["water"] -= 1
            else:
                p["stress"] += 1
                p["flags"] = 4
        if tick == 1920:
            p.update(dead=True, energy=0, water=0, flags=5)
        rows.append(world(tick, [p]))
    record = {k: p[k] for k in ("id", "parent", "species", "generation", "column")}
    record.update(birth_tick=15, death_tick=1920 if end == 1920 else None, death_flags=5)
    return rows, {"lineages": [record]}


class SeedlingWaterTests(unittest.TestCase):
    def run_trace(self, rows, ref, end=1920):
        return audit.analyze_stream(map(json.dumps, rows), [], ref, "test.neural.8", "off", 0, end)

    def test_root_alias_and_uptake_order(self):
        p = plant()
        self.assertEqual(audit.cells(p), {(12, 0): 9})
        earlier = copy.deepcopy(p)
        earlier["id"] = 10  # Order, not numerical lineage ID, matters.
        later = copy.deepcopy(p)
        later["id"] = 1
        r = audit.point(world(15, [earlier, p, later]), p, None)
        self.assertEqual(r["root_post_water"], 9)
        self.assertEqual(r["unique_root_cells"], 1)
        self.assertEqual(r["earlier_live_root_overlap"], [{"id": 10, "cells": [(12, 0)]}])
        earlier["dead"] = True
        self.assertFalse(audit.point(world(15, [earlier, p]), p, None)["earlier_live_root_overlap"])
        for roots in ([[12, 0, 1, 9]], [[12, 0, 1, 9], [12, 0, 1, 8]],
                      [[28, 0, 1, 9], [28, 0, 1, 9]]):
            bad = copy.deepcopy(p)
            bad["root_cells"] = roots
            with self.assertRaises(RuntimeError): audit.cells(bad)

    def test_birth_order_and_action_deltas(self):
        p = plant()
        p.update(energy=56, water=19, nodes=5)
        p["agent"].update(decisions=1, extend=1, shoot_extend=1)
        first = audit.point(world(60, [p]), p, None)
        self.assertEqual(first["budget"]["water_upkeep"], 0)
        self.assertEqual(first["budget"]["water_growth"], 5)
        # The unchanged last action must not be charged again during cooldown.
        second = audit.point(world(75, [p]), p, p)
        self.assertEqual(second["actions"]["shoot_extend"], 0)
        self.assertEqual(second["budget"]["water_growth"], 0)

    def test_failed_extension_is_not_deeper_access(self):
        old, p = plant(), plant()
        p.update(energy=56, water=19)
        p["agent"].update(decisions=1, root_extend=1, extend=1)
        r = audit.point(world(30, [p]), p, old)
        self.assertEqual(r["actions"]["root_extend"], 1)
        self.assertEqual(r["deepest_root_row"], 0)
        self.assertEqual(r["budget"]["water_growth"], 5)

    def test_water_gate_and_terminal_clear(self):
        rows, ref = fixture()
        r, histories = self.run_trace(rows, ref)
        p = r["seedlings"][0]
        self.assertEqual(r["outcomes"], {"water": 1})
        self.assertEqual(r["checked_live_budgets"], 127)
        self.assertEqual(p["budget"]["water_upkeep"], 24)
        self.assertEqual(p["last_alive"]["tick"], 1905)
        self.assertEqual(p["last_alive"]["plant"]["energy"], 33)
        self.assertIsNone(p["terminal_step_budget"])
        self.assertEqual(p["first_water_shortage"]["tick"], 1500)
        self.assertGreater(p["below_water_growth_cost_samples"], 0)
        self.assertEqual(len(histories[2]), 127)

    def test_corrupt_or_incomplete_trace_rejected(self):
        rows, ref = fixture()
        for bad in (rows[:-1], rows[:2] + rows[3:], rows[:2] + [rows[1]] + rows[2:]):
            with self.assertRaises(RuntimeError): self.run_trace(bad, ref)
        for index, field, value in ((1, "water", 23), (-1, "energy_income", 1),
                                    (-1, "stress", 7), (-1, "flags", 3)):
            bad = copy.deepcopy(rows)
            bad[index]["plants"][0][field] = value
            with self.assertRaises(RuntimeError): self.run_trace(bad, ref)
        bad = copy.deepcopy(rows)
        bad[1]["seed_reserve_rule"] = audit.trial.RULE
        with self.assertRaises(RuntimeError): self.run_trace(bad, ref)
        bad = copy.deepcopy(ref)
        bad["lineages"][0]["death_tick"] = 1905
        with self.assertRaises(RuntimeError): self.run_trace(rows, bad)

    def test_survival_boundary_patch_and_censoring(self):
        r = {"birth_tick": 15, "death_tick": 15 + audit.DAY, "death_flags": 5}
        self.assertEqual(audit.outcome(r, 15 + audit.DAY), "water")
        self.assertEqual(audit.outcome(r, audit.DAY), "censored")
        r["environmental_death"] = True
        self.assertEqual(audit.outcome(r, 15 + audit.DAY), "patch")
        r["death_tick"] = 30 + audit.DAY
        self.assertEqual(audit.outcome(r, 15 + audit.DAY), "survived")
        rows, ref = fixture(120)
        result, histories = self.run_trace(rows, ref, 120)
        self.assertEqual(result["outcomes"], {"censored": 1})
        # Patch application occurs after the trace row; include that live budget.
        r = ref["lineages"][0] | {"death_tick": 120, "environmental_death": True}
        self.assertEqual(audit.summarize(r, histories[2], 120)["last_alive"]["tick"], 120)
        with self.assertRaises(RuntimeError): audit.summarize(r, histories[2][:-1], 120)


if __name__ == "__main__":
    unittest.main()
