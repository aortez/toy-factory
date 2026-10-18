#!/usr/bin/env python3
"""Offline species cohorts, censoring, allocation, saved evidence and corruption checks."""

import copy
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_species as audit

PORTABLE = audit.ROOT / "benchmarks/garden-seasons/landing-species-results.json.gz"
D, S = audit.DAY, audit.STEP


class SpeciesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = audit.load(audit.ROOT / audit.INPUT)
        with patch.object(audit.previous.training, "native", side_effect=AssertionError("offline audit ran simulation")):
            cls.result = audit.analyze(cls.data)

    def test_portable_recomputes_offline_preserving_all_cases_and_scores(self):
        self.assertEqual(json.loads(gzip.decompress(PORTABLE.read_bytes())), self.result)
        self.assertEqual(self.result["unchanged_comparison"], self.data["comparison"])
        self.assertEqual(audit.digest(audit.ROOT / audit.INPUT), audit.INPUT_SHA)
        self.assertEqual((self.result["native_runs"], self.result["training_runs"]), (0, 0))
        self.assertEqual(len(self.result["worlds"]), 12)
        for old, new in zip(self.data["worlds"], self.result["worlds"], strict=True):
            self.assertEqual(new["id"], old["id"])
            for arm in audit.ARMS:
                self.assertEqual(new["arms"][arm]["unchanged_history"], old["arms"][arm]["history"])
                self.assertEqual(new["arms"][arm]["unchanged_metrics"], old["arms"][arm]["metrics"])
                self.assertEqual(new["arms"][arm]["trace_sha256"], old["arms"][arm]["trace_sha256"])

    def test_independent_species_survival_seed_and_credit_partitions(self):
        for old, new in zip(self.data["worlds"], self.result["worlds"], strict=True):
            for arm in audit.ARMS:
                source, result = old["arms"][arm], new["arms"][arm]
                plants = source["result"]["lineages"]
                for species, name in enumerate(audit.SPECIES):
                    group = result["species"][name]
                    selected = [p for p in plants if p["species"] == species]
                    self.assertEqual(group["plants"], len(selected))
                    self.assertEqual(group["seeds"]["seeds"], sum(p["seeds_created"] for p in selected))
                    for t in audit.AGES:
                        cohort = [p for p in selected if p["parent"] and p["birth_tick"] <= audit.STOP - t]
                        alive = [p for p in cohort if p["death_tick"] is None or p["death_tick"] - p["birth_tick"] > t]
                        saved = group["descendant_survival"][str(t)]
                        self.assertEqual((saved["full_possible_followup"], saved["alive_at_age"]), (len(cohort), len(alive)))
                    for age in audit.BODY_AGES:
                        saved = group["bodies"][str(age)]
                        self.assertEqual(sum(saved["coverage"].values()), group["births"])
                        self.assertEqual(saved["living_only"]["nodes"]["count"], saved["coverage"].get("observed", 0))
                self.assertEqual(sum(g["credit_ticks"] for g in result["species"].values()), source["metrics"]["total_ticks"])
                self.assertEqual(sum(g["fresh_renewal_confirmations"] for g in result["species"].values()),
                                 source["metrics"]["late_renewal_confirmations"])

    def test_frozen_species_succession_and_counterexamples(self):
        groups = self.result["groups"]
        for arm, seeds, births, survivors in (("off", (416, 0, 7), (162, 0, 5), (61, 0, 0)),
                                             ("32", (0, 48, 399), (0, 17, 219), (0, 7, 100))):
            rows = [groups["seasonal"][arm][s] for s in audit.SPECIES]
            self.assertEqual(tuple(r["seeds"]["seeds"] for r in rows), seeds)
            self.assertEqual(tuple(r["births"] for r in rows), births)
            self.assertEqual(tuple(r["late_first_day"]["outcomes"].get("confirmed", 0) for r in rows), survivors)
        capped = groups["steady"]["32"]
        self.assertEqual([capped[s]["founders_alive_at_end"] for s in audit.SPECIES], [10, 10, 6])
        self.assertEqual(sum(capped[s]["credit_ticks"] for s in audit.SPECIES), 0)
        ground = groups["seasonal"]["32"]["ground-cover"]["descendant_survival"]
        self.assertEqual([(ground[str(t)]["alive_at_age"], ground[str(t)]["full_possible_followup"])
                          for t in audit.AGES], [(128, 219), (123, 217), (9, 173)])
        counter = next(w for w in self.result["worlds"] if w["model"] == "multi-s6d697834-live" and
                       w["case"]["climate"] == "seasonal")
        self.assertEqual([counter["arms"][a]["unchanged_metrics"]["total_ticks"] for a in audit.ARMS], [1146195, 785580])

    def test_stalled_worlds_have_seed_supply_and_overlapping_spacing_masks(self):
        rows = [w["arms"]["32"] for w in self.result["worlds"] if w["case"]["climate"] == "steady" and
                w["arms"]["32"]["unchanged_metrics"]["births"] == 0]
        self.assertEqual(len(rows), 4)
        self.assertEqual(sum(r["whole_run_seed_checks"]["mature_checks"] for r in rows), 1561760)
        for r in rows:
            self.assertEqual(r["unchanged_metrics"]["deaths"], 0)
            checks = r["whole_run_seed_checks"]
            self.assertEqual(checks["outcomes"], {"expired": 40, "pending": 8})
            self.assertEqual(checks["blocker_checks"]["spacing"], checks["mature_checks"])
            self.assertEqual(checks["blocker_checks"]["plant_capacity"], 0)
            self.assertEqual(checks["blocker_checks"]["node_capacity"], 0)
            self.assertGreater(sum(checks["blocker_checks"].values()), checks["mature_checks"])

    def test_age_boundaries_and_censoring_are_not_observed_lifetimes(self):
        plants = [{"birth_tick": 0, "death_tick": D}, {"birth_tick": 0, "death_tick": D + S},
                  {"birth_tick": 2 * D, "death_tick": 2 * D + S}, {"birth_tick": 2 * D, "death_tick": None}]
        self.assertEqual(audit.survival(plants, D, 2 * D + S), {"cohort": 4, "full_possible_followup": 2,
            "alive_at_age": 1, "died_by_age": 1, "insufficient_possible_followup": 2})
        self.assertEqual(audit.survival([], D, audit.STOP)["full_possible_followup"], 0)
        for bad in (0, True, 1, -S):
            with self.assertRaises(RuntimeError):
                audit.survival(plants, bad, audit.STOP)
        # Death-row leaf fields describe decomposition: never count them as productive leaves.
        dead = {"birth_tick": 0, "death_tick": D, "rows": [{"tick": D, "active_leaves": 255}]}
        self.assertEqual(audit.body_at_age(dead, D, 2 * D), {"status": "dead"})
        self.assertEqual(audit.body_at_age(dead, D, D - S), {"status": "insufficient-followup"})
        alive = {"birth_tick": 0, "death_tick": None, "rows": []}
        with self.assertRaises(RuntimeError):
            audit.body_at_age(alive, D, 2 * D)

    def test_corrupt_history_inheritance_budgets_and_inventory_fail(self):
        original = self.data["worlds"][0]
        for field in ("history", "species", "seed_species", "duplicate", "resource", "mask"):
            broken = copy.deepcopy(original["arms"]["off"])
            if field == "history":
                broken["history"]["combined_ticks"] += S
            elif field == "species":
                p = next(p for p in broken["result"]["lineages"] if p["parent"])
                p["species"] = (p["species"] + 1) % 3
            elif field == "seed_species":
                broken["result"]["seeds"][0]["species"] = 7
            elif field == "duplicate":
                broken["audit"]["plants"].append(broken["audit"]["plants"][0])
            elif field == "resource":
                broken["audit"]["plants"][0]["resources"]["energy"]["growth"] += 1
            else:
                masks = broken["audit"]["seeds"][0]["mature_masks"]
                masks[next(iter(masks))] += 1
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                audit.analyze_arm(broken, "off", original["case"], self.data["models"][original["model"]]["metadata"])
        for worlds in (self.data["worlds"][:-1], [self.data["worlds"][0]] * 12):
            with self.assertRaises(RuntimeError):
                audit.analyze({**self.data, "worlds": worlds})

    def test_cli_exact_roundtrip_input_identity_and_no_clobber(self):
        def run(*args):
            return subprocess.run([sys.executable, "-W", "error", str(audit.ROOT / "sim/garden_landing_species.py"),
                                   *map(str, args)], capture_output=True, timeout=60)
        with tempfile.TemporaryDirectory(prefix="landing-species-") as directory:
            output = Path(directory) / "audit.json.gz"
            self.assertEqual(run("--out", output).returncode, 0)
            self.assertEqual(output.read_bytes(), PORTABLE.read_bytes())
            self.assertNotEqual(run("--out", output).returncode, 0)
            self.assertEqual(output.read_bytes(), PORTABLE.read_bytes())
            self.assertEqual(run("--verify", output).returncode, 0)
            bad = Path(directory) / "bad.json"
            bad.write_text("{}\n")
            self.assertNotEqual(run("--verify", bad).returncode, 0)
            absent = Path(directory) / "absent.json"
            self.assertNotEqual(run("--input", bad, "--out", absent).returncode, 0)
            self.assertFalse(absent.exists())


if __name__ == "__main__":
    unittest.main()
