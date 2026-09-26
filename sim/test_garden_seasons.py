#!/usr/bin/env python3
"""Seasonal cohort boundaries and native daily/site-audit reconciliation."""

import argparse
import copy
from pathlib import Path
import unittest

import garden_seasons as seasons
import garden_season_report as reports


class LifetimeTests(unittest.TestCase):
    @staticmethod
    def panel():
        daily = [{"day": d, "living": 1, "births": 2, "deaths": 0, "species": ["flower"],
                  "viable_species": ["flower"]} for d in range(33)]
        case = {"environment": {}, "daily": daily, "plants": [], "deaths": [], "empty_day": None,
                "trace_sha256": "unchanged", "lifetimes": {"durable_parents": 1},
                "closing_lifetimes": {"cycle_survivors": 1, "durable_parents": 1}, "closing_births": 1}
        return {"protocol": "garden-seasons-v2", "days": 32, "seed_base": "00000001", "seeds": ["seed"],
                "gardener": False, "irrigation": False, "source_sha256": {}, "inspector_sha256": "x",
                "replayer_sha256": None, "frames": [],
                "cases": [copy.deepcopy({**case, "mode": m, "scenario": s, "policy": p, "seed": "seed"})
                          for m in seasons.MODES for s in ("rainfed", "rainfed-crowded")
                          for p in ("baseline", "adaptive")]}

    def test_screen_does_not_trade_away_renewal(self):
        control = self.panel()
        candidate = copy.deepcopy(control)
        for c in candidate["cases"]:
            if c["mode"] == "seasonal":
                c["daily"][-1]["viable_species"].append("shrub")
        self.assertTrue(reports.screen(control, candidate)["passes_screen"])
        focal = next(c for c in candidate["cases"] if c["mode"] == "seasonal")
        focal["lifetimes"]["durable_parents"] = 0
        self.assertFalse(reports.screen(control, candidate)["passes_screen"])
        focal["lifetimes"]["durable_parents"] = 1
        focal["empty_day"] = 0
        self.assertFalse(reports.screen(control, candidate)["gates"]["no_new_empty_world"])

    def test_screen_rejects_unmatched_and_changed_controls(self):
        control = self.panel()
        for kind in ("missing", "duplicate", "seed", "prefix", "control"):
            other = copy.deepcopy(control)
            if kind == "missing":
                other["cases"].pop()
            elif kind == "duplicate":
                other["cases"].append(other["cases"][0])
            elif kind == "seed":
                other["seed_base"] = "00000002"
            elif kind == "prefix":
                other["cases"][-1]["daily"][1]["living"] = 2
            else:
                other["cases"][0]["trace_sha256"] = "changed"
            with self.assertRaises(RuntimeError):
                reports.screen(control, other)

    def test_full_day_and_censoring(self):
        day = seasons.DAY_TICKS
        plants = {
            1: {"id": 1, "parent": 0, "birth_tick": 0, "death_tick": None},
            2: {"id": 2, "parent": 1, "birth_tick": 15, "death_tick": day + 15},
            3: {"id": 3, "parent": 1, "birth_tick": 30, "death_tick": day + 45},
            4: {"id": 4, "parent": 3, "birth_tick": day + 60, "death_tick": None},
            5: {"id": 5, "parent": 3, "birth_tick": 3 * day - 15, "death_tick": None},
        }
        report = seasons.life_summary(plants, 3 * day)
        self.assertEqual(report, {"births": 4, "eligible": 3, "cycle_survivors": 2,
                                  "too_young": 1, "durable_parents": 1})
        closing = seasons.life_summary(plants, 3 * day, day + 1)
        self.assertEqual(closing["births"], 2)
        self.assertEqual(closing["eligible"], 1)
        self.assertEqual(closing["durable_parents"], 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    args = parser.parse_args()
    result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(LifetimeTests))
    if not result.wasSuccessful():
        return 1
    case = seasons.run_case(args.build / "toy-factory-garden-inspect", 32,
                            "rainfed", "adaptive", 123, "seasonal", True)
    for day in case["daily"]:
        assert sum(day["living_by_species"].values()) == day["living"]
        assert sum(day["seeds_by_species"].values()) == day["seed_bank"]
        assert set(day["species"]) <= set(day["viable_species"])
        assert set(day["living_families"]) <= set(day["viable_families"])
    audit = case["seed_audit"]
    assert sum(audit["mask_histogram"].values()) == audit["mature_seed_samples"]
    assert sum(v["samples"] for v in audit["by_species"].values()) == audit["mature_seed_samples"]
    assert audit["blockers"]["cold"] > 0
    assert case["closing_lifetimes"]["births"] == case["closing_births"]
    assert case["lifetimes"]["births"] == case["daily"][-1]["births"]
    print("Seasonal cohorts and uniform site diagnostics passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
