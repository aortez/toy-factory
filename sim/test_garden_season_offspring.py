#!/usr/bin/env python3
"""Cohort partitions, survival/censor boundaries and death-record integrity."""

import copy
import unittest

import garden_season_offspring as audit
from garden_seasons import DAY_TICKS as DAY


def fixture():
    # A durable parent, a death exactly at one day, a day survivor without a
    # child, a parent with a censored living child, and a censored dead child.
    specs = [(1, 0, 0, None), (2, 1, DAY, None), (3, 2, 2 * DAY, None),
             (4, 1, 3 * DAY, 4 * DAY), (5, 1, 4 * DAY, None),
             (6, 1, 125 * DAY, None), (7, 6, 128 * DAY - 60, None),
             (8, 1, 128 * DAY - 120, 128 * DAY - 60)]
    plants = {}
    for ident, parent, born, died in specs:
        plants[ident] = {"id": ident, "parent": parent, "birth_tick": born, "death_tick": died,
                         "species": "flower", "family": 1,
                         "generation": plants[parent]["generation"] + 1 if parent else 0}
    climate = {"mode": "seasonal", "drought": False, "light_percent": 100, "cold": False}
    deaths = [{**p, "tick": p["death_tick"], "flags": 3, "climate": dict(climate)}
              for p in plants.values() if p["death_tick"] is not None]
    return {"plants": list(plants.values()), "deaths": deaths,
            "daily": [{"climate": dict(climate)} for _ in range(129)]}


class OffspringTests(unittest.TestCase):
    def test_funnel_censoring_and_parent_boundaries(self):
        plants, deaths = audit.validate_history(fixture())
        result = audit.cohort(plants, deaths, 0)
        totals = result["totals"]
        expected = {"births": 7, "eligible": 5, "censored": 2, "censored_dead": 1,
                    "first_day_deaths": 1, "day_survivors": 4, "durable_parents": 1,
                    "no_child": 2, "child_without_day_survivor": 1,
                    "nondurable_alive": 3, "nondurable_dead": 0,
                    "nondurable_with_young_child": 1, "early_age_day": 1,
                    "early_energy_ordinary": 1}
        self.assertEqual(totals, {key: expected.get(key, 0) for key in audit.METRICS})
        self.assertEqual(result["species"]["flower"], totals)
        self.assertEqual(audit.cohort(plants, deaths, 112 * DAY + 1)["totals"]["births"], 3)
        self.assertEqual(audit.cohort(plants, deaths, 3 * DAY + 1)["totals"]["first_day_deaths"], 0)
        # A child dying exactly at the boundary does not confer durable status.
        plants[3]["death_tick"] = 3 * DAY
        deaths[3] = {**plants[3], "tick": 3 * DAY, "flags": 5,
                     "climate": {"drought": True, "light_percent": 100}}
        self.assertEqual(audit.cohort(plants, deaths, 0)["totals"]["durable_parents"], 0)

    def test_shortage_weather_age_buckets_and_later_death(self):
        for age, age_bucket, flags, resource, drought, light, weather in (
            (DAY // 4, "quarter", 3, "energy", False, 100, "ordinary"),
            (DAY // 2, "half", 5, "water", True, 100, "drought"),
            (DAY, "day", 7, "both", False, 60, "dim")):
            with self.subTest(age=age):
                plants, deaths = audit.validate_history(fixture())
                plants[4]["death_tick"] = plants[4]["birth_tick"] + age
                deaths[4] = {**plants[4], "flags": flags,
                             "climate": {"drought": drought, "light_percent": light}}
                totals = audit.cohort(plants, deaths, 0)["totals"]
                self.assertEqual(totals["early_age_" + age_bucket], 1)
                self.assertEqual(totals[f"early_{resource}_{weather}"], 1)
        plants, deaths = audit.validate_history(fixture())
        plants[5]["death_tick"] = 6 * DAY
        totals = audit.cohort(plants, deaths, 0)["totals"]
        self.assertEqual(totals["day_survivors"], 4)
        self.assertEqual(totals["nondurable_dead"], 1)

    def test_rejects_missing_duplicate_inconsistent_or_unknown_history(self):
        mutations = [lambda c: c["deaths"].pop(),
                     lambda c: c["deaths"].append(c["deaths"][0]),
                     lambda c: c["plants"].append(c["plants"][0]),
                     lambda c: c["plants"][1].update(parent=999),
                     lambda c: c["plants"][1].update(generation=9),
                     lambda c: c["plants"][0].update(birth_tick=15),
                     lambda c: c["deaths"][0].update(tick=7),
                     lambda c: c["deaths"][0].update(parent=999),
                     lambda c: c["deaths"][0].update(flags=1),
                     lambda c: c["deaths"][0]["climate"].update(drought=True)]
        for mutate in mutations:
            case = copy.deepcopy(fixture())
            mutate(case)
            with self.assertRaises(RuntimeError):
                audit.validate_history(case)

    def test_aggregation_preserves_partitions(self):
        plants, deaths = audit.validate_history(fixture())
        case = {"windows": {"whole": audit.cohort(plants, deaths, 0),
                            "closing": audit.cohort(plants, deaths, 112 * DAY + 1)}}
        result = audit.aggregate([case, case])
        self.assertEqual(result["worlds"], 2)
        self.assertEqual(result["windows"]["whole"]["totals"]["births"], 14)
        self.assertEqual(result["windows"]["closing"]["totals"]["births"], 6)
        self.assertTrue(all(n == 0 for n in audit.aggregate([])["windows"]["whole"]["totals"].values()))

    def test_intra_day_light_uses_event_with_census_bounds(self):
        case = fixture()
        case["plants"][3]["death_tick"] = 4 * DAY + 60
        case["deaths"][0].update(tick=4 * DAY + 60, death_tick=4 * DAY + 60)
        case["daily"][4]["climate"].update(light_percent=66)
        case["daily"][5]["climate"].update(light_percent=60, cold=True)
        case["deaths"][0]["climate"].update(light_percent=64, cold=True)
        audit.validate_history(case)
        case["deaths"][0]["climate"].update(cold=False)
        with self.assertRaisesRegex(RuntimeError, "intra-day"):
            audit.validate_history(case)
        case["deaths"][0]["climate"].update(light_percent=59, cold=True)
        with self.assertRaisesRegex(RuntimeError, "intra-day"):
            audit.validate_history(case)


if __name__ == "__main__":
    unittest.main()
