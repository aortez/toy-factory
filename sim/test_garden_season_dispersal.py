#!/usr/bin/env python3
"""The fixed scattering screen cannot trade durable renewal for raw births."""

import copy
import unittest

from garden_season_dispersal import screen


class ScreenTests(unittest.TestCase):
    @staticmethod
    def cases():
        return [{"mode": mode, "policy": "adaptive", "scenario": "rainfed", "seed": "ed52188b",
                 "empty_day": None, "environment": {"node_capacity": 256},
                 "daily": [{"hash": "unchanged"}, {"viable_species": ["flower", "shrub"]}],
                 "closing_births": 2,
                 "closing_lifetimes": {"cycle_survivors": 1, "durable_parents": 1},
                 "lifetimes": {"births": 4, "eligible": 4, "cycle_survivors": 2, "durable_parents": 2},
                 "deaths": []} for mode in ("steady", "seasonal")]

    def test_requires_closing_improvement(self):
        control = self.cases()
        self.assertFalse(screen(control, copy.deepcopy(control))["passes_screen"])
        candidate = copy.deepcopy(control)
        candidate[1]["closing_lifetimes"]["cycle_survivors"] += 1
        self.assertTrue(screen(control, candidate)["passes_screen"])

    def test_raw_births_cannot_offset_worse_renewal_or_diversity(self):
        for field in ("historical", "closing", "diversity", "extinction"):
            with self.subTest(field=field):
                control = self.cases()
                candidate = copy.deepcopy(control)
                candidate[1]["closing_births"] += 10
                candidate[1]["closing_lifetimes"]["cycle_survivors"] += 1
                if field == "historical":
                    candidate[1]["lifetimes"]["durable_parents"] = 1
                elif field == "closing":
                    candidate[1]["closing_lifetimes"]["durable_parents"] = 0
                elif field == "diversity":
                    candidate[1]["daily"][-1]["viable_species"] = ["flower"]
                else:
                    candidate[0]["empty_day"] = 12
                self.assertFalse(screen(control, candidate)["passes_screen"])

    def test_rejects_changed_controls_and_mismatched_panels(self):
        mutations = [lambda c: c.pop(), lambda c: c.append(c[0]),
                     lambda c: c[0].update(seed="another"),
                     lambda c: c[0]["daily"][0].update(hash="changed"),
                     lambda c: c[0]["environment"].update(node_capacity=512)]
        for mutate in mutations:
            control = self.cases()
            candidate = copy.deepcopy(control)
            mutate(candidate)
            with self.assertRaises(RuntimeError):
                screen(control, candidate)


if __name__ == "__main__":
    unittest.main()
