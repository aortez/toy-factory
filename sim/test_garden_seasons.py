#!/usr/bin/env python3
"""Seasonal cohort boundaries and native daily/site-audit reconciliation."""

import argparse
from pathlib import Path
import unittest

import garden_seasons as seasons


class LifetimeTests(unittest.TestCase):
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
