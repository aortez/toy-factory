#!/usr/bin/env python3
"""Fresh-panel completeness, matched weather, frozen candidate and unchanged gates."""

import copy
import unittest

import garden_season_confirmation as confirmation
from garden_seasons import DAY_TICKS, life_summary


def case(spec, bonus=False):
    births = [(1, 0, 0, 0), (2, 1, DAY_TICKS + 15, 1),
              (3, 2, 113 * DAY_TICKS + 15, 2), (4, 3, 114 * DAY_TICKS + 15, 3)]
    if bonus:
        births.append((5, 4, 116 * DAY_TICKS + 15, 4))
    plants = {ident: {"id": ident, "parent": parent, "birth_tick": tick, "death_tick": None,
                       "generation": generation, "species": "flower", "family": 1}
              for ident, parent, tick, generation in births}
    daily = [{"day": d, "hash": f"{d:08x}", "births": sum(0 < b <= d * DAY_TICKS for _, _, b, _ in births),
              "deaths": 0, "rain_deposited": d * 100, "rain_runoff": d * 2,
              "living": 1, "seed_bank": 4, "viable_species": ["flower"],
              "climate": {"mode": spec["mode"], "version": 1}} for d in range(129)]
    return {**spec, "environment": dict(confirmation.ENVIRONMENT), "daily": daily,
            "plants": list(plants.values()), "deaths": [], "empty_day": None,
            "lifetimes": life_summary(plants, 128 * DAY_TICKS),
            "closing_lifetimes": life_summary(plants, 128 * DAY_TICKS, 112 * DAY_TICKS + 1),
            "closing_births": len(births) - 2,
            "seed_audit": {"window_days": 16, "ecology_samples": 4096,
                           "mature_seed_samples": 1000, "mask_histogram": {"32": 1000}}}


class ConfirmationTests(unittest.TestCase):
    def panel(self, bonus=False):
        return [case(spec, bonus) for spec in confirmation.specification()]

    def test_fixed_fresh_panel_and_complete_pair_counts(self):
        self.assertEqual(confirmation.SEEDS, ("ed52188d", "4f0b9246", "a9c30c1f", "0bb887d0",
                                              "647001a9", "c629bb62", "20e1353b", "82deacfc"))
        before, after = self.panel(), self.panel(True)
        result = confirmation.analysis(before, after)
        self.assertTrue(result["passes_screen"])
        self.assertEqual(result["groups"]["seasonal"]["control"]["worlds"], 32)
        self.assertEqual(result["seasonal_pairs"]["closing_survivors"],
                         {"increased": 32, "unchanged": 0, "decreased": 0})
        self.assertEqual(len(result["by_seed"]), 8)
        self.assertTrue(all(group["control"]["worlds"] == 4 for group in result["by_seed"].values()))
        self.assertEqual(result["first_year"]["seasonal"]["control"],
                         result["first_year"]["seasonal"]["wide"])
        self.assertFalse(confirmation.analysis(before, self.panel())["passes_screen"])

    def test_rejects_incomplete_duplicate_or_unmatched_panels(self):
        mutations = [lambda p: p.pop(), lambda p: p.append(p[0]),
                     lambda p: p[0].update(seed="ed52188b"),
                     lambda p: p[0]["daily"].pop(),
                     lambda p: p[0]["daily"][0].update(hash="changed"),
                     lambda p: p[0]["daily"][50].update(rain_runoff=99999),
                     lambda p: p[0]["daily"][50]["climate"].update(mode="drought"),
                     lambda p: p[0]["environment"].update(node_capacity=512),
                     lambda p: p[0]["seed_audit"].update(mature_seed_samples=999),
                     lambda p: p[0]["closing_lifetimes"].update(durable_parents=999),
                     lambda p: p[0].update(closing_births=999),
                     lambda p: p[0].update(empty_day=42),
                     lambda p: p[0]["plants"].append(p[0]["plants"][0])]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                before, after = self.panel(), self.panel()
                mutate(after)
                with self.assertRaises(RuntimeError):
                    confirmation.analysis(before, after)

    def test_export_recomputes_analysis_and_checks_identity(self):
        before, after = self.panel(), self.panel(True)
        for c in (*before, *after):
            c["trace_sha256"] = "example"
        report = {"protocol": "seasonal-dispersal-confirmation-v1", "seeds": list(confirmation.SEEDS),
                  "cases": {"control": before, "wide": after},
                  "analysis": confirmation.analysis(before, after)}
        summary = confirmation.summarize(report)
        self.assertEqual(len(summary["cases"]["control"]), 64)
        self.assertEqual(len(summary["cases"]["wide"][0]["daily_hashes"]), 129)
        report["analysis"]["passes_screen"] = False
        with self.assertRaises(RuntimeError):
            confirmation.summarize(report)
        report["seeds"][0] = "old"
        with self.assertRaises(RuntimeError):
            confirmation.summarize(report)

    def test_frozen_candidate_rejects_source_binary_flags_and_reused_seeds(self):
        flags = {"TOY_FACTORY_GARDEN_WIDE_DISPERSAL:BOOL": "ON", "ANOTHER:BOOL": "OFF"}
        wide = {"source_sha256": {"file": "source"}, "build_flags": flags,
                "inspector_sha256": "inspector", "replayer_sha256": "renderer"}
        prior = {"wide": wide, "audit": {"cases": [{"seed": "ed52188b"}]}}
        frozen = {"source_sha256": dict(wide["source_sha256"]), "builds": {
            "control": {"flags": {**flags, "TOY_FACTORY_GARDEN_WIDE_DISPERSAL:BOOL": "OFF"}},
            "wide": {"flags": dict(flags), "inspector_sha256": "inspector", "replayer_sha256": "renderer"}}}
        confirmation.check_frozen_candidate(frozen, prior)
        mutations = [lambda f: f["source_sha256"].update(file="changed"),
                     lambda f: f["builds"]["wide"].update(inspector_sha256="changed"),
                     lambda f: f["builds"]["wide"].update(replayer_sha256="changed"),
                     lambda f: f["builds"]["control"]["flags"].update({"ANOTHER:BOOL": "ON"}),
                     lambda f: f["builds"]["wide"]["flags"].update({"ANOTHER:BOOL": "ON"})]
        for mutate in mutations:
            other = copy.deepcopy(frozen)
            mutate(other)
            with self.assertRaises(RuntimeError):
                confirmation.check_frozen_candidate(other, prior)
        prior["audit"]["cases"][0]["seed"] = confirmation.SEEDS[0]
        with self.assertRaises(RuntimeError):
            confirmation.check_frozen_candidate(frozen, prior)


if __name__ == "__main__":
    unittest.main()
