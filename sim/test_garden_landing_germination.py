#!/usr/bin/env python3
"""Offline seed-window boundaries, living witnesses and frozen renewal regressions."""

import copy
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_germination as audit

S, D = audit.STEP, audit.DAY
PORTABLE = audit.ROOT / "benchmarks/garden-seasons/landing-budget-germination-results.json.gz"


def fixture():
    result = {"tick": 12 * S, "lineages": [
        {"id": 1, "parent": 0, "birth_tick": 0, "death_tick": None, "column": 5}],
        "seeds": [
            {"parent": 1, "birth_tick": 0, "end_tick": 10 * S, "column": 7, "species": 0,
             "child_id": None, "outcome": "expired", "lifetime_ecology_ticks": 10},
            {"parent": 1, "birth_tick": 10 * S, "end_tick": None, "column": 0, "species": 0,
             "child_id": None, "outcome": "pending", "lifetime_ecology_ticks": 10}]}
    rows = [{"tick": age * S, "seeds": [[1, age, 7, 33 if age < 8 else 32, 12, 80, 1, 32, 0, 0, 2]]}
            for age in (7, 8, 9)]
    rows.append({"tick": 10 * S, "seeds": [[1, 10, 7, 0, 0, 0, 1, 32, 1, 0, -1]]})
    return result, rows


class WindowTests(unittest.TestCase):
    def test_clipped_lifetime_dormancy_expiry_and_end_purchase(self):
        result, rows = fixture()
        original = copy.deepcopy((result, rows))
        value = audit.seed_window(result, rows, 6 * S, 10 * S)
        summary = value["summary"]
        self.assertEqual((summary["samples"], summary["checks"], summary["dormant_checks"],
                          summary["mature_checks"], summary["expiry_samples"]), (4, 3, 1, 2, 1))
        self.assertEqual(summary["always_mature_blockers"], ["spacing"])
        self.assertEqual(summary["sole_blocker_checks"]["spacing"], 2)
        self.assertEqual(summary["cohorts"], {
            "carry_in": {"seeds": 1, "outcomes_at_window_end": {"expired": 1}},
            "purchased": {"seeds": 1, "outcomes_at_window_end": {"pending": 1}}})
        self.assertEqual(value["seeds"][1]["samples"], 0)
        self.assertEqual(value["seeds"][1]["always_mature_blockers"], [])
        self.assertEqual(value["seeds"][0]["living_witnesses"], {"1": 2})
        self.assertEqual(summary["parent_spacing_checks"], 2)
        self.assertEqual(summary["samples_with_blocked_seed_and_open_elsewhere"], 2)
        self.assertEqual((result, rows), original)

    def test_dead_body_is_not_falsely_attributed_to_a_living_parent(self):
        result, rows = fixture()
        result["lineages"][0]["death_tick"] = 8 * S
        value = audit.seed_window(result, rows, 6 * S, 10 * S)
        self.assertEqual(value["summary"]["spacing_with_living_witness"], 0)
        self.assertEqual(value["summary"]["spacing_without_living_witness"], 2)
        self.assertEqual(value["seeds"][0]["living_witnesses"], {})
        # The spacing receipt can still describe retained dead tissue. There
        # is no removal timestamp in the lineage ledger, so don't invent one.
        self.assertEqual(value["summary"]["always_mature_blockers"], ["spacing"])

    def test_sequential_same_step_germination_creates_a_living_witness(self):
        result = {"tick": 9 * S, "lineages": [
            {"id": 1, "parent": 0, "column": 10, "birth_tick": 0, "death_tick": 8 * S},
            {"id": 2, "parent": 1, "column": 0, "birth_tick": 8 * S, "death_tick": None},
            {"id": 3, "parent": 0, "column": 25, "birth_tick": 0, "death_tick": None}],
            "seeds": [
                {"parent": 1, "birth_tick": 0, "end_tick": 8 * S, "column": 0, "species": 0,
                 "child_id": 2, "outcome": "germinated", "lifetime_ecology_ticks": 10},
                {"parent": 3, "birth_tick": 0, "end_tick": None, "column": 2, "species": 0,
                 "child_id": None, "outcome": "pending", "lifetime_ecology_ticks": 10}]}
        rows = [{"tick": 8 * S, "seeds": [
            [1, 8, 0, 0, 12, 80, 2, 64, 2, 2, 10],
            [3, 8, 2, 32, 12, 80, 3, 68, 0, 0, 7]]}]
        value = audit.seed_window(result, rows, 7 * S, 8 * S)
        self.assertEqual(value["seeds"][1]["living_witnesses"], {"2": 1})
        self.assertEqual(value["summary"]["other_spacing_checks"], 1)
        self.assertEqual(value["summary"]["parent_spacing_checks"], 0)
        self.assertEqual(value["germinations"], [{"tick": 8 * S, "child": 2, "seed": [1, 0], "column": 0}])

    def test_corrupt_clock_identity_masks_resources_fates_and_inventory_fail(self):
        for kind in ("missing", "extra", "clock", "identity", "duplicate", "dormancy", "moisture",
                     "light", "capacity", "living_spacing", "expiry", "child", "boolean", "birth"):
            result, rows = fixture()
            if kind == "missing":
                rows.pop()
            elif kind == "extra":
                rows.append(copy.deepcopy(rows[-1]))
            elif kind == "clock":
                rows[0]["tick"] += S
            elif kind == "identity":
                rows[0]["seeds"][0][0] = 99
            elif kind == "duplicate":
                rows[0]["seeds"].append(copy.deepcopy(rows[0]["seeds"][0]))
            elif kind == "birth":
                result["lineages"].append({"id": 2, "parent": 1, "birth_tick": 8 * S,
                                          "death_tick": None, "column": 20})
            else:
                column, value = {"dormancy": (3, 32), "moisture": (4, 11), "light": (5, 79),
                    "capacity": (6, 8), "living_spacing": (3, 1), "expiry": (3, 32),
                    "child": (9, 2), "boolean": (1, True)}[kind]
                rows[-1 if kind == "expiry" else 0]["seeds"][0][column] = value
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                audit.seed_window(result, rows, 6 * S, 10 * S)
        result, rows = fixture()
        for start, end in ((True, 10 * S), (6 * S + 1, 10 * S), (10 * S, 6 * S), (6 * S, 13 * S)):
            with self.assertRaises(RuntimeError):
                audit.seed_window(result, rows, start, end)


class FrozenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = audit.load(audit.ROOT / audit.INPUT, audit.INPUT_SHA)
        cls.windows = audit.load(audit.ROOT / audit.WINDOWS, audit.WINDOWS_SHA)
        with patch.object(audit.previous.training, "native", side_effect=AssertionError("audit ran simulation")):
            cls.result = audit.analyze(cls.data, cls.windows)

    def world(self, model, arm):
        return next(w for w in self.result["worlds"] if w["model"] == model)["arms"][arm]

    def test_frozen_portable_histories_and_input_hashes(self):
        with gzip.open(PORTABLE, "rt") as stream:
            self.assertEqual(json.load(stream), self.result)
        self.assertEqual(self.result["unchanged_comparison"], self.data["comparison"])
        self.assertEqual((self.result["native_runs"], self.result["training_runs"]), (0, 0))
        for old, new in zip(audit.panel(self.data), self.result["worlds"], strict=True):
            for arm in audit.ARMS:
                self.assertEqual(new["arms"][arm]["unchanged_history"], old["arms"][arm]["history"])
                self.assertEqual(new["arms"][arm]["unchanged_metrics"], old["arms"][arm]["metrics"])
        self.assertEqual(audit.digest(audit.ROOT / audit.INPUT), audit.INPUT_SHA)
        self.assertEqual(audit.digest(audit.ROOT / audit.WINDOWS), audit.WINDOWS_SHA)

    def test_all_four_failed_periods_have_universal_mature_spacing_blockage(self):
        for suffix in ("33", "35"):
            for mode in ("single", "multi"):
                a = self.world(mode + "-s6d6978" + suffix + "-live", "reserve")
                stats = a["seed_window"]["summary"]
                self.assertEqual(stats["always_mature_blockers"], ["spacing"])
                self.assertGreater(stats["sole_blocker_checks"]["spacing"], 0)
                self.assertEqual(stats["blocker_checks"]["plant_capacity"], 0)
                self.assertEqual(stats["blocker_checks"]["node_capacity"], 0)
                self.assertEqual(stats["spacing_with_living_witness"], stats["mature_checks"])
                self.assertEqual(stats["spacing_without_living_witness"], 0)
                self.assertEqual(stats["cohorts"]["purchased"]["seeds"], 8)
                self.assertEqual((a["bank"]["minimum_seed_bank"], a["bank"]["maximum_seed_bank"]), (8, 8))
                self.assertEqual((a["birth_cohort"]["births"], a["period"]["credit"]["earned_ticks"]), (0, 0))

    def test_both_counterexamples_and_carry_in_credit_are_retained(self):
        single = self.world("single-s6d697834-live", "reserve")
        multi = self.world("multi-s6d697834-live", "reserve")
        self.assertEqual([a["period"]["credit"]["earned_ticks"] for a in (single, multi)], [144630, 14715])
        self.assertEqual([a["birth_cohort"]["births"] for a in (single, multi)], [1, 0])
        self.assertEqual(single["birth_cohort"]["confirmed"], 0)
        self.assertEqual(single["children"][0]["id"], 27)
        for a in (single, multi):
            block = a["unchanged_history"]["blocks"][-1]
            self.assertEqual(block["rolling"]["fresh_ticks"], 0)
            self.assertEqual(block["rolling"]["carry_in_ticks"], block["rolling"]["ticks"])
        self.assertEqual(len(self.result["worlds"]), 6)

    def test_independent_receipt_counts_every_arm_and_credit_age_at_end(self):
        for w, raw in zip(self.result["worlds"], self.windows["worlds"], strict=True):
            for arm in audit.ARMS:
                a = w["arms"][arm]
                rows = [s for r in raw["arms"][arm]["rows"] for s in r["seeds"]]
                mature = [s for s in rows if s[8] != 1 and s[1] >= 8]
                stats = a["seed_window"]["summary"]
                self.assertEqual(stats["samples"], len(rows))
                self.assertEqual(stats["mature_checks"], len(mature))
                for i, blocker in enumerate(audit.recruitment.BLOCKERS):
                    self.assertEqual(stats["blocker_checks"][blocker], sum(bool(s[3] & (1 << i)) for s in mature))
                self.assertEqual(len(a["seed_window"]["germinations"]), sum(s[8] == 2 for s in rows))
                # Independently count contributions sample-by-sample, not via
                # the interval accounting used to generate the report.
                old = next(v for v in self.data["worlds"] if v["id"] == w["id"])["arms"][arm]["result"]
                plants = {p["id"]: p for p in old["lineages"]}
                ticks = 0
                for p in plants.values():
                    if not p["parent"] or not plants[p["parent"]]["parent"]:
                        continue
                    parent, due = plants[p["parent"]], p["birth_tick"] + D
                    if parent["death_tick"] is not None and parent["death_tick"] <= parent["birth_tick"] + D:
                        continue
                    for t in range(audit.START + S, audit.END + S, S):
                        if due <= t < due + 32 * D and (p["death_tick"] is None or t < p["death_tick"]):
                            ticks += S
                self.assertEqual(ticks, a["period"]["credit"]["earned_ticks"])

    def test_missing_panel_or_wrong_provenance_fails(self):
        for field, value in (("window_ticks", [audit.START + S, audit.END]), ("manifest_sha256", "wrong"),
                             ("worlds", self.windows["worlds"][:-1])):
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                audit.analyze(self.data, {**self.windows, field: value})

    def test_cli_no_clobber_wrong_inputs_and_stable_regeneration(self):
        def run(*args):
            return subprocess.run([sys.executable, "-W", "error", str(audit.ROOT / "sim/garden_landing_germination.py"),
                                   *map(str, args)], capture_output=True, timeout=180)
        with tempfile.TemporaryDirectory(prefix="landing-germination-") as directory:
            output = Path(directory) / "audit.json.gz"
            completed = run("--out", output)
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            self.assertEqual(output.read_bytes(), PORTABLE.read_bytes())
            self.assertNotEqual(run("--out", output).returncode, 0)
            self.assertEqual(output.read_bytes(), PORTABLE.read_bytes())
            wrong = Path(directory) / "wrong.json.gz"
            wrong.write_bytes(b"invalid")
            absent = Path(directory) / "absent.json.gz"
            self.assertNotEqual(run("--input", wrong, "--out", absent).returncode, 0)
            self.assertFalse(absent.exists())
            self.assertNotEqual(run("--windows", wrong, "--out", absent).returncode, 0)
            self.assertFalse(absent.exists())


if __name__ == "__main__":
    unittest.main()
