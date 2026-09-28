#!/usr/bin/env python3
"""Sequential germination checks, waiting/censoring and portable evidence tests."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import garden_season_seed_waits as audit

BUILD = None


def seed(outcome="germinated", age=8):
    return {"parent": 1, "generation": 1, "column": 15, "species": "flower", "created_tick": 60,
            "resolved_tick": None if outcome == "pending" else 60 + 15 * age,
            "outcome": outcome, "child": 2 if outcome == "germinated" else None}


def purchase():
    return {"child_outcome": "durable", "sites": [[12, 80, 0] for _ in range(28)],
            "diagnostics": {"views": {"all": {"category": "world_closed"}}}}


def snapshot(age, mask):
    return {"age": age, "mask": mask, "moisture": 0 if mask & 2 else 12,
            "light": 24 if mask & 4 else 80, "sun": 24 if mask & 4 else 80, "phase": 0,
            "rain_rate": 0, "rain_deposited": 0, "nodes": 8, "plants": 2,
            "cold": bool(mask & 64), "neighbors": [1] if mask & 32 else [], "removed": []}


def simple_history():
    r = audit.new_record(0, seed(), purchase())
    for age in range(1, 9):
        audit.add_check(r, snapshot(age, 1 if age < 8 else 0))
    return r


class SeedWaitTests(unittest.TestCase):
    def test_exact_thresholds_and_simultaneous_constraints(self):
        s = seed()
        values = [1, 2, 8, 1, 15, 0, 252, 7, 12, 80, 0, 2]
        plants = [{"column": 0}] * 7
        self.assertEqual(audit.decode(values, s, 180, 252, plants, False)["outcome"], 2)
        s = seed("pending")
        blocked = [1, 0, 8, 1, 15, 0, 253, 8, 11, 79, 126, 0]
        plants.append({"column": 17})
        self.assertEqual(audit.decode(blocked, s, 180, 253, plants, True)["blockers"], 126)
        for index, value in ((2, 7), (4, 16), (6, 252), (8, 12), (9, 80), (10, 0), (11, 2)):
            bad = blocked.copy()
            bad[index] = value
            with self.assertRaises(RuntimeError):
                audit.decode(bad, s, 180, 253, plants, True)

    def test_expiry_has_no_germination_check(self):
        s = seed("expired", 8192)
        values = [1, 0, 8192, 1, 15, 0, 4, 1, 0, 0, 0, 1]
        a = audit.decode(values, s, s["resolved_tick"], 4, [{"column": 15}], True)
        self.assertEqual(a["outcome"], 1)
        for index in (1, 8, 9, 10):
            bad = values.copy()
            bad[index] = 1
            with self.assertRaises(RuntimeError):
                audit.decode(bad, s, s["resolved_tick"], 4, [{"column": 15}], True)
        r = simple_history()
        with self.assertRaises(RuntimeError):
            audit.add_check(r, snapshot(8192, 0))

    def test_run_encoding_dormancy_and_mature_exposure(self):
        r = simple_history()
        self.assertEqual(r["runs"], [[1, 7, 1, False], [8, 8, 0, False]])
        self.assertEqual(audit.exposures(r), {"mature_checks": 1, "masks": {"0": 1},
                                             "globally_dim": 0, "bright_sun_but_shaded": 0})
        result = audit.summarize([r])
        self.assertEqual(result["last_masks_before_germination"], {"1": 1})
        self.assertEqual(result["wait_age_ecology_ticks"]["median"], 8)
        self.assertEqual(result["clearance_lead_ecology_ticks"]["dormancy"], {"1": 1})
        for bad_age in (8, 10):
            with self.assertRaises(RuntimeError):
                audit.add_check(r, snapshot(bad_age, 0))

    def test_spacing_release_requires_actual_removed_neighbors(self):
        r = audit.new_record(0, seed("pending"), purchase())
        audit.add_check(r, snapshot(1, 33))
        with self.assertRaises(RuntimeError):
            audit.add_check(copy.deepcopy(r), snapshot(2, 1))
        s = snapshot(2, 1)
        s["removed"] = [1]
        audit.add_check(r, s)
        self.assertEqual(r["spacing_releases"], [{"age": 2, "ids": [1], "removed": [1]}])

    def test_last_constraint_is_not_lifetime_only_constraint(self):
        r = audit.new_record(0, seed(age=10), purchase())
        for age in range(1, 11):
            audit.add_check(r, snapshot(age, 7 if age < 8 else 6 if age == 8 else 4 if age == 9 else 0))
        result = audit.summarize([r])
        self.assertEqual(result["last_bits_before_germination"]["moisture"], 0)
        self.assertEqual(result["ever_blocked_before_birth"]["moisture"], 1)
        self.assertEqual(result["last_bits_before_germination"]["light"], 1)
        self.assertEqual(result["clearance_lead_ecology_ticks"]["moisture"], {"2": 1})
        self.assertEqual(result["exposure"]["bits"]["light"], 2)
        self.assertEqual(result["exposure"]["globally_dim"], 2)

    def test_pending_is_censored_and_empty_cohorts_retained(self):
        s = seed("pending")
        s["created_tick"] = audit.END
        p = purchase()
        p["child_outcome"] = "pending"
        r = audit.new_record(0, s, p)
        audit.validate_record(r, s, p, {})
        result = audit.summarize([r])
        self.assertEqual(result["outcomes"], {"pending": 1})
        self.assertEqual(result["wait_age_ecology_ticks"]["median"], None)
        self.assertEqual(result["exposure"]["mature_checks"], 0)
        self.assertEqual(audit.summarize([])["seeds"], 0)
        self.assertEqual([audit.age_band(i) for i in (255, 256, 1023, 1024, 4095, 4096, 8192)],
                         ["under_1_day", "1_to_4_days", "1_to_4_days", "4_to_16_days",
                          "4_to_16_days", "16_to_32_days", "16_to_32_days"])
        with self.assertRaises(RuntimeError):
            audit.analysis([])

    def test_portable_validation_rejects_incomplete_and_fabricated_checks(self):
        r, s, p = simple_history(), seed(), purchase()
        audit.validate_record(r, s, p, {})
        for mutate in (lambda v: v["runs"][0].__setitem__(1, 6), lambda v: v["runs"].pop(),
                       lambda v: v.update(child_outcome="expired"), lambda v: v.update(first_mature=None),
                       lambda v: v["terminal_pair"][-1].update(moisture=0),
                       lambda v: v["terminal_pair"][-1].update(neighbors=[7]),
                       lambda v: v["spacing_releases"].append({"age": 8, "ids": [1], "removed": [1]})):
            bad = copy.deepcopy(r)
            mutate(bad)
            with self.assertRaises(RuntimeError):
                audit.validate_record(bad, s, p, {})

    def test_native_modes_match_state_and_repeat_without_intervention(self):
        if BUILD is None or not (BUILD / "toy-factory-garden-production-audit").exists():
            self.skipTest("compatible native build not supplied")
        binary = BUILD / "toy-factory-garden-production-audit"
        command = [str(binary), "rainfed", "baseline", "123", "guard", "7680"]
        legacy = [json.loads(line) for line in subprocess.check_output(command, timeout=30).splitlines()]
        raw = subprocess.check_output([*command, "--seed-waits"], timeout=30)
        self.assertEqual(raw, subprocess.check_output([*command, "--seed-waits"], timeout=30))
        rows = [json.loads(line) for line in raw.splitlines()]
        self.assertEqual(rows[0]["site_phase"], "sequential-check")
        self.assertEqual(rows[0]["attempt_fields"], list(audit.FIELDS))
        self.assertTrue(any(r["attempts"] for r in rows[1:]))
        self.assertEqual([{k: r[k] for k in ("tick", "hash", "created")} for r in rows[1:]],
                         [{k: r[k] for k in ("tick", "hash", "created")} for r in legacy[1:]])
        for extra in (["--bad"], ["--seed-waits", "--flower-sites"], ["--seed-waits", "--seed-waits"]):
            self.assertEqual(subprocess.run([*command, *extra], capture_output=True, timeout=30).returncode, 2)

    def test_portable_evidence_recomputes_without_native_code(self):
        folder = audit.ROOT / "benchmarks/garden-seasons"
        path = folder / "seed-waits-histories.json.gz"
        if not path.exists():
            self.skipTest("waiting evidence not collected yet")
        with patch("subprocess.Popen", side_effect=AssertionError("portable check ran native code")):
            report = json.loads(gzip.decompress(path.read_bytes()))
            purchases, old = audit.load_input()
            audit.validate_report(report, purchases, old)
            self.assertEqual(audit.compact(report), json.loads((folder / "seed-waits-summary.json").read_text()))
            self.assertEqual(sum(len(c["records"]) for c in report["cases"]), 3576)
            for mutate in (lambda c: c["records"].pop(), lambda c: c.update(worlds=1),
                           lambda c: c["records"][0]["runs"].pop(), lambda c: c.update(checks=0)):
                bad = copy.deepcopy(report["cases"][0])
                mutate(bad)
                with self.assertRaises(RuntimeError):
                    audit.validate_case(bad, old["cases"][0], purchases["cases"][0])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    args, rest = parser.parse_known_args()
    BUILD = args.build
    unittest.main(argv=[__file__, *rest])
