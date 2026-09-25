#!/usr/bin/env python3
"""Unit checks for resource reconciliation; no device or frozen model required."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from resources import analyze, budget


def plant():
    return {
        "id": 1, "parent": 0, "generation": 0, "species": "flower",
        "dead": False, "energy": 64, "water": 24, "vigor": 0,
        "energy_income": 0, "water_income": 0, "nodes": 4, "roots": 2,
        "reproduction_cooldown": 0, "active_leaves": 1, "stress": 0,
        "flags": 0, "tips": 3,
        "agent": {"decisions": 0, "extend": 0, "finish": 0, "wait": 0, "root_extend": 0},
    }


class ResourceTests(unittest.TestCase):
    def test_birth_skips_maintenance_and_pays_growth(self):
        value = plant()
        value.update(energy=55, water=19, nodes=5)
        value["agent"].update(extend=1, decisions=1)
        result = budget(None, value, 60)
        self.assertEqual(result["energy_upkeep"], 0)
        self.assertEqual(result["energy_growth"], 9)
        self.assertEqual(result["water_growth"], 5)

    def test_saturation_old_body_upkeep_and_seeds(self):
        old = plant()
        old.update(energy=250, water=510, nodes=17, roots=8)
        new = copy.deepcopy(old)
        new.update(energy=196, water=481, nodes=18, energy_income=10, water_income=12,
                   reproduction_cooldown=16)
        new["agent"].update(extend=1, decisions=1)
        result = budget(old, new, 60)
        self.assertEqual(result["energy_overflow"], 4)
        self.assertEqual(result["water_overflow"], 10)
        self.assertEqual(result["energy_upkeep"], 3)
        self.assertEqual(result["water_upkeep"], 2)
        self.assertEqual(result["energy_seeds"], 48)

    def test_finish_and_failed_extension_still_cost_resources(self):
        for action in ("finish", "extend"):
            old = plant()
            new = copy.deepcopy(old)
            new.update(energy=55, water=19)  # No new node; both actions still pay.
            new["agent"].update({action: 1, "decisions": 1})
            self.assertEqual(budget(old, new, 15)["energy_growth"], 9)

    def test_paid_upkeep_clamps_and_wait_is_free(self):
        old = plant()
        old.update(energy=1, water=0, nodes=17)
        new = copy.deepcopy(old)
        new.update(energy=0)
        new["agent"].update(wait=1, decisions=1)
        result = budget(old, new, 60)
        self.assertEqual(result["energy_upkeep"], 1)
        self.assertEqual(result["water_upkeep"], 0)
        self.assertEqual(result["energy_growth"], 0)

    def test_unreconstructable_or_inconsistent_values_fail(self):
        old = plant()
        for change in ({"energy_income": 255}, {"dead": True}, {"energy": 63}):
            new = copy.deepcopy(old)
            new.update(change)
            with self.assertRaises(RuntimeError):
                budget(old, new, 15)

    def test_trace_cadence_and_terminal_clear(self):
        value = plant()
        initial = {"type": "world", "tick": 0, "sun_phase": 64, "hash": "12345678", "plants": [value]}
        terminal = copy.deepcopy(initial)
        terminal.update(tick=15, sun_phase=65)
        terminal["plants"][0].update(dead=True, energy=0, water=0, flags=3)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.jsonl"
            path.write_text(json.dumps(initial) + "\n" + json.dumps(terminal) + "\n")
            result = analyze(path)
            self.assertEqual(result["terminal_steps_not_reconstructed"], 1)
            self.assertEqual(result["checked_live_steps"], 0)
            self.assertEqual(result["lineages"][0]["last_living"]["energy"], 64)
            terminal["tick"] = 30
            with path.open("w") as stream:
                stream.write(json.dumps(initial) + "\n" + json.dumps(terminal) + "\n")
            with self.assertRaises(RuntimeError):
                analyze(path)
            path.write_text(json.dumps(initial) + '\n{"type":"bid","tick":15,"id":1,"priority":0,"action":0}\n')
            with self.assertRaises(RuntimeError):
                analyze(path)


if __name__ == "__main__":
    unittest.main()
