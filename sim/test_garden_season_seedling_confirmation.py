#!/usr/bin/env python3
"""Fresh-panel identity, unchanged gates, frozen candidate and portable evidence."""

import copy
import gzip
import json
import unittest
from unittest.mock import patch

import garden_season_seedling_confirmation as trial


class ConfirmationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prior = trial.inputs()

    def remapped_panel(self):
        cases = copy.deepcopy(self.prior["cases"])
        for spec, case in zip(trial.specification(), cases):
            case["case"] = spec
        return cases

    def test_fresh_complete_panel_and_seed_reuse_rejection(self):
        self.assertEqual(trial.SEEDS, ("ed52188c", "4f0b9247", "a9c30c1e", "0bb887d1",
                                      "647001a8", "c629bb63", "20e1353a", "82deacfd"))
        panel = trial.specification()
        self.assertEqual(len(panel), 32)
        self.assertEqual(len({trial.identity(c) for c in panel}), 32)
        self.assertFalse(set(trial.SEEDS) & trial.recorded_seeds(self.prior))
        self.assertEqual(trial.recorded_seeds({"seed": "a", "nested": [{"seeds": ["b", "c"]}]}),
                         {"a", "b", "c"})
        with patch.object(trial, "SEEDS", trial.population.SEEDS):
            with self.assertRaisesRegex(RuntimeError, "Reused"):
                trial.inputs()

    def test_same_analysis_on_old_outcomes_with_only_seed_labels_changed(self):
        result = trial.analysis(self.remapped_panel())
        expected = copy.deepcopy(self.prior["analysis"])
        expected["partitions"]["seed"] = dict(zip(trial.SEEDS, expected["partitions"]["seed"].values()))
        self.assertEqual(result, expected)
        self.assertEqual(trial.population.analysis(self.prior["cases"]), self.prior["analysis"])
        self.assertEqual(trial.population.analysis(self.prior["cases"], trial.population.inputs()),
                         self.prior["analysis"])

    def test_missing_duplicate_reordered_and_unmatched_worlds_fail(self):
        mutations = (lambda p: p.pop(), lambda p: p.__setitem__(-1, p[0]), lambda p: p.reverse(),
                     lambda p: p[0]["case"].update(seed="00000001"),
                     lambda p: p[0]["arms"]["guard"]["history"]["daily"][16].update(rain_runoff=999999),
                     lambda p: p[0]["arms"]["control"]["history"]["daily"].pop())
        for mutate in mutations:
            panel = self.remapped_panel()
            mutate(panel)
            with self.assertRaises(RuntimeError):
                trial.analysis(panel)
        for mutate in (lambda p: p.pop(), lambda p: p.__setitem__(-1, p[0]),
                       lambda p: p[0].update(mode="steady")):
            spec = trial.specification()
            mutate(spec)
            with self.assertRaises(RuntimeError):
                trial.population.analysis(self.remapped_panel(), spec)

    def test_frozen_native_rule_and_dependencies_are_required(self):
        before = self.prior["frozen"]
        trial.check_candidate(before, before)
        mutations = (lambda p: p.update(inspector_sha256="changed"),
                     lambda p: p.update(replayer_sha256="changed"),
                     lambda p: p["flags"].update({"TOY_FACTORY_GARDEN_WIDE_DISPERSAL:BOOL": "OFF"}),
                     lambda p: p["sources"].update({"src/garden_world.c": "changed"}),
                     lambda p: p["sources"].update({"sim/garden_seedling_reserve.c": "changed"}),
                     lambda p: p["sources"].update({"sim/garden_season_seedling_reserve.py": "changed"}))
        for mutate in mutations:
            current = copy.deepcopy(before)
            mutate(current)
            with self.assertRaises(RuntimeError):
                trial.check_candidate(current, before)
        current = copy.deepcopy(before)
        for name in trial.ORCHESTRATION_CHANGES:
            current["sources"][name] = "explicit panel parameter or new test registration"
        trial.check_candidate(current, before)
        manifest = trial.legacy_manifest(self.prior)
        self.assertEqual(len(manifest), 4)
        self.assertEqual(len({r["path"] for r in manifest}), 4)

    def test_negative_results_are_retained_and_never_pooled_with_old_panel(self):
        cases = self.remapped_panel()
        for case in cases:
            case["arms"]["guard"] = copy.deepcopy(case["arms"]["control"])
        result = trial.analysis(cases)
        self.assertFalse(result["passes_screen"])
        self.assertFalse(result["gates"]["improve_closing_renewal"])
        self.assertTrue(all(v for k, v in result["gates"].items() if k != "improve_closing_renewal"))
        cases[0]["arms"]["guard"]["first_empty_tick"] = 60
        self.assertFalse(trial.analysis(cases)["gates"]["no_new_empty_world"])

    def test_retained_confirmation_and_tampering(self):
        folder = trial.ROOT / "benchmarks/garden-seasons"
        report = json.loads(gzip.decompress((folder / "seedling-confirmation-histories.json.gz").read_bytes()))
        trial.validate_report(report, self.prior)
        self.assertEqual(trial.population.compact(report),
                         json.loads((folder / "seedling-confirmation-summary.json").read_text()))
        count = 0
        for case in report["cases"]:
            for arm in trial.ARMS:
                data = case["arms"][arm]
                self.assertEqual(trial.population.outcomes(data["history"]), data["outcomes"])
                self.assertEqual(data["counts"]["worlds"], trial.END // 15 + 1)
                self.assertEqual(len(data["terminals"]), data["counts"]["terminal_receipts"])
                self.assertEqual(set(data["lineages"]), {str(p["id"]) for p in data["history"]["plants"]})
                for entry in data["terminals"]:
                    event = next(d for d in data["history"]["deaths"] if d["id"] == entry["receipt"]["id"])
                    self.assertEqual((event["tick"], event["climate"]),
                                     (entry["receipt"]["tick"], entry["climate"]))
            for frame in case["frames"]:
                count += 1
                self.assertEqual(trial.digest(folder / frame["png"]), frame["png_sha256"])
        self.assertEqual(count, 8)
        mutations = (lambda p: p["seeds"].__setitem__(0, trial.population.SEEDS[0]),
                     lambda p: p.update(gardener=True), lambda p: p["legacy"].pop(),
                     lambda p: p["analysis"].update(passes_screen=not p["analysis"]["passes_screen"]),
                     lambda p: p["cases"][0]["frames"].pop(),
                     lambda p: p["cases"][0]["frames"][0].update(hash="changed"),
                     lambda p: p["cases"][0]["frames"][0].update(png="frames/selected-after-the-fact.png"))
        for mutate in mutations:
            changed = copy.deepcopy(report)
            mutate(changed)
            with self.assertRaises(RuntimeError):
                trial.validate_report(changed, self.prior)


if __name__ == "__main__":
    unittest.main()
