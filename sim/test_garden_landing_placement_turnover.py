#!/usr/bin/env python3
"""Saved placement diagnosis: credit boundaries, ancestry and exact seed receipts."""

import copy
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_placement_turnover as audit

D, S = audit.DAY, audit.STEP
PORTABLE = audit.ROOT / "benchmarks/garden-seasons/landing-placement-turnover-results.json.gz"


def fixture():
    result = {"tick": 64 * D, "seeds": [], "lineages": [
        {"id": ident, "parent": parent, "birth_tick": birth * D,
         "death_tick": death * D if death is not None else None}
        for ident, parent, birth, death in ((1, 0, 0, None), (2, 1, 1, None),
            (3, 2, 3, None), (4, 2, 5, 7), (5, 2, 6, 7), (6, 2, 10, 43),
            (7, 2, 59, None), (8, 3, 8, None))]}
    seeds = [{"parent": p["parent"], "child_id": p["id"], "end_tick": p["birth_tick"],
              "outcome": "germinated", "redirected": p["id"] == 3}
             for p in result["lineages"] if p["parent"]]
    return result, seeds


class BoundaryTests(unittest.TestCase):
    def test_age_expiry_death_tie_first_day_failure_and_censoring(self):
        result, seeds = fixture()
        paths = audit.redirected_paths(result, seeds)
        exits = {p["id"]: p for p in audit.credit_exits(result, paths)}
        self.assertEqual(set(exits), {3, 4, 6, 7, 8})
        for ident, tick, reason in ((3, 36 * D, "age_limit"), (4, 7 * D, "death"),
                                   (6, 43 * D, "death_and_age_limit"), (7, None, "right_censored")):
            self.assertEqual((exits[ident]["credit_end_exclusive"], exits[ident]["credit_end_reason"]), (tick, reason))
        self.assertEqual(exits[3]["confirmation_tick"], 4 * D)
        # Ageing out is not mortality; the plant remains alive past its last credit.
        self.assertIsNone(exits[3]["death_tick"])
        self.assertEqual(exits[8]["redirected_lineage_ids"], [3])
        self.assertFalse(exits[8]["direct_redirect"])

    def test_no_credit_interval_merges_changes_and_has_exclusive_boundary(self):
        result, _ = fixture()
        gaps = audit.no_credit_intervals(result, 0, result["tick"])
        self.assertEqual([(g["first_tick"], g["end_exclusive"]) for g in gaps],
                         [(S, 4 * D), (43 * D, 60 * D)])
        self.assertTrue(gaps[0]["clipped_at_start"])
        self.assertFalse(gaps[1]["clipped_at_end"])
        self.assertEqual(gaps[1]["stats"]["no_living_plant_ticks"], 0)
        clipped = audit.no_credit_intervals(result, 45 * D, 50 * D)[0]
        self.assertTrue(clipped["clipped_at_start"] and clipped["clipped_at_end"])
        self.assertEqual(clipped["stats"]["sample_ticks"], 5 * D)

    def test_ancestry_does_not_mark_unrelated_child_and_rejects_bad_inventory(self):
        result, seeds = fixture()
        original = copy.deepcopy((result, seeds))
        paths = audit.redirected_paths(result, seeds)
        self.assertEqual(paths[3], {"direct_redirect": True, "redirected_lineage_ids": [3]})
        self.assertEqual(paths[4], {"direct_redirect": False, "redirected_lineage_ids": []})
        self.assertEqual((result, seeds), original)
        for kind in ("duplicate", "missing", "parent", "birthday", "flag", "cycle"):
            result, seeds = fixture()
            if kind == "duplicate":
                seeds.append(seeds[0])
            elif kind == "missing":
                seeds.pop()
            elif kind == "cycle":
                result["lineages"][1]["parent"] = seeds[0]["parent"] = 8
            else:
                key, value = {"parent": ("parent", 99), "birthday": ("end_tick", 0), "flag": ("redirected", 1)}[kind]
                seeds[0][key] = value
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                audit.redirected_paths(result, seeds)

    def test_cross_arm_identity_stops_at_first_changed_landing(self):
        p = {"random": 7, "selected": 1, "choices": list(range(6)), "tick": 30, "parent": 2}
        a = {"placements": {"purchases": [p, p, p]}}
        b = {"placements": {"purchases": [p, {**p, "selected": 3}, {"later": "unmatched"}]}}
        self.assertEqual(audit.first_redirect(a, b), {"matching_prior_purchases": 1,
            "tick": 30, "parent": 2, "original_column": 1, "selected_column": 3})
        self.assertIsNone(audit.first_redirect(a, a))
        bad = copy.deepcopy(b)
        bad["placements"]["purchases"][0]["parent"] = 99
        with self.assertRaises(RuntimeError):
            audit.first_redirect(a, bad)


class FrozenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = audit.germination.load(audit.ROOT / audit.INPUT, audit.INPUT_SHA)
        cls.windows = audit.germination.load(audit.ROOT / audit.WINDOWS, audit.WINDOWS_SHA)
        def state_hash():
            return hashlib.sha256(json.dumps((cls.data, cls.windows), sort_keys=True).encode()).hexdigest()
        before = state_hash()
        with patch.object(audit.previous.training, "native", side_effect=AssertionError("ran simulation")), \
                patch.object(subprocess, "run", side_effect=AssertionError("ran subprocess")):
            cls.result = audit.analyze(cls.data, cls.windows)
        if before != state_hash():
            raise AssertionError("audit mutated saved inputs")

    def world(self, model, arm):
        return next(w for w in self.result["worlds"] if w["model"] == model)["arms"][arm]

    def test_portable_and_scores_reproduce_without_simulation(self):
        with gzip.open(PORTABLE, "rt") as stream:
            self.assertEqual(json.load(stream), self.result)
        self.assertEqual(self.result["unchanged_comparison"], self.data["comparison"])
        self.assertEqual((self.result["native_runs"], self.result["training_runs"]), (0, 0))
        for old, new in zip(audit.panel(self.data), self.result["worlds"], strict=True):
            for arm in audit.ARMS:
                a = new["arms"][arm]
                self.assertEqual(a["unchanged_history"], old["arms"][arm]["history"])
                self.assertEqual(a["unchanged_metrics"], old["arms"][arm]["metrics"])
                self.assertEqual(a["established_deaths"], [])
                self.assertEqual(a["period"]["confirmations"], [])
                self.assertEqual(a["period"]["credit"]["death_lost_ticks"], 0)
                self.assertEqual(a["population_stats"]["biologically_empty_ticks"], 0)
                self.assertGreater(a["population_stats"]["minimum_seed_bank"], 0)

    def test_33_improvements_are_old_unredirected_credit_not_new_survivors(self):
        for mode, ident, ticks, expiry in (("single", 22, 50595, 657330), ("multi", 26, 22305, 629040)):
            a = self.world(mode + "-s6d697833-live", "spacing")
            self.assertEqual(a["birth_cohort"]["births"], 0)
            self.assertEqual(a["period"]["credit"]["earned_ticks"], ticks)
            self.assertEqual(len(a["final_credit_contributors"]), 1)
            c = a["final_credit_contributors"][0]
            self.assertEqual((c["id"], c["expires_exclusive"], c["carry_in"]), (ident, expiry, True))
            self.assertFalse(c["direct_redirect"] or c["redirected_lineage_ids"])
            self.assertEqual(a["no_credit_intervals"][-1]["first_tick"], expiry)

    def test_all_four_focal_candidates_have_persistent_reachable_spacing_blocks(self):
        for suffix in ("33", "34"):
            for mode in ("single", "multi"):
                a = self.world(mode + "-s6d6978" + suffix + "-live", "spacing")
                seeds, reach = a["seed_window"]["summary"], a["reach_window"]["summary"]["all"]
                self.assertEqual((seeds["seed_count"], seeds["mature_checks"]), (16, 65472))
                self.assertEqual(seeds["spacing_with_living_witness"], 65472)
                self.assertEqual(seeds["always_mature_blockers"], ["spacing"])
                self.assertGreater(seeds["sole_blocker_checks"]["spacing"], 0)
                self.assertEqual((reach["always_reachable_spacing_blocked"], reach["any_reachable_spacing_clear"]), (16, 0))
                self.assertEqual(a["birth_cohort"]["births"], 0)
                self.assertEqual((a["population_stats"]["minimum_seed_bank"],
                                  a["population_stats"]["maximum_seed_bank"]), (8, 8))
                for gate in ("plant_capacity", "node_capacity"):
                    self.assertEqual(seeds["blocker_checks"][gate], 0)

    def test_regressions_and_seedling_counterexamples_are_retained(self):
        for mode, ticks in (("single", 144630), ("multi", 14715)):
            model = mode + "-s6d697834-live"
            self.assertEqual(self.world(model, "reserve")["period"]["credit"]["earned_ticks"], ticks)
            self.assertEqual(self.world(model, "spacing")["period"]["credit"]["earned_ticks"], 0)
        for model, arm, ident, cause in (("single-s6d697834-live", "reserve", 27, "energy"),
                                       ("multi-s6d697835-live", "spacing", 29, "water")):
            a = self.world(model, arm)
            self.assertEqual(a["birth_cohort"], {"births": 1, "confirmed": 0, "died": 1, "pending": 0, "shortages": {cause: 1}})
            self.assertEqual(a["children"][0]["id"], ident)
            self.assertIsNone(a["children"][0]["first_root_tick"])
        self.assertEqual(len(self.result["worlds"]), 6)

    def test_independent_sampled_credit_and_no_credit_intervals(self):
        for old, new in zip(audit.panel(self.data), self.result["worlds"], strict=True):
            for arm in audit.ARMS:
                plants = {p["id"]: p for p in old["arms"][arm]["result"]["lineages"]}
                credits, absent = 0, []
                for t in range(62 * D + S, audit.END + S, S):
                    count = 0
                    for p in plants.values():
                        if not p["parent"]:
                            continue
                        parent, due = plants[p["parent"]], p["birth_tick"] + D
                        if parent["parent"] and parent["birth_tick"] + D <= due and \
                                (parent["death_tick"] is None or parent["death_tick"] > parent["birth_tick"] + D) and \
                                due <= t < due + 32 * D and (p["death_tick"] is None or t < p["death_tick"]):
                            count += 1
                    if not count:
                        absent.append(t)
                    if t > audit.START:
                        credits += count * S
                a = new["arms"][arm]
                self.assertEqual(credits, a["period"]["credit"]["earned_ticks"])
                self.assertEqual(absent, [t for g in a["no_credit_intervals"]
                                         for t in range(g["first_tick"], g["end_exclusive"], S)])

    def test_independent_native_blocker_counts_and_missing_children(self):
        for w, raw in zip(self.result["worlds"], self.windows["worlds"], strict=True):
            for arm in audit.ARMS:
                rows = [s for r in raw["arms"][arm]["rows"] for s in r["seeds"]]
                mature = [s for s in rows if s[8] != 1 and s[1] >= 8]
                summary = w["arms"][arm]["seed_window"]["summary"]
                self.assertEqual(summary["mature_checks"], len(mature))
                for i, gate in enumerate(audit.germination.recruitment.BLOCKERS):
                    self.assertEqual(summary["blocker_checks"][gate], sum(bool(s[3] & (1 << i)) for s in mature))
        w = audit.panel(self.data)[0]
        broken = copy.deepcopy(w["arms"]["spacing"])
        broken["audit"]["plants"].append(broken["audit"]["plants"][0])
        with self.assertRaises(RuntimeError):
            audit.analyze_arm(broken, "spacing", w["case"], self.data["models"][w["model"]]["metadata"],
                              self.windows["worlds"][0]["arms"]["spacing"])

    def test_wrong_panel_and_provenance_fail(self):
        for field, value in (("window_ticks", [audit.START + S, audit.END]), ("manifest_sha256", "wrong"),
                             ("worlds", self.windows["worlds"][:-1])):
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                audit.analyze(self.data, {**self.windows, field: value})

    def test_cli_no_clobber_hashes_and_byte_identical_regeneration(self):
        def run(*args):
            return subprocess.run([sys.executable, "-W", "error", str(audit.ROOT / "sim/garden_landing_placement_turnover.py"),
                                   *map(str, args)], capture_output=True, timeout=180)
        with tempfile.TemporaryDirectory(prefix="placement-turnover-") as directory:
            output = Path(directory) / "audit.json.gz"
            completed = run("--out", output)
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            self.assertEqual(output.read_bytes(), PORTABLE.read_bytes())
            self.assertNotEqual(run("--out", output).returncode, 0)
            self.assertEqual(output.read_bytes(), PORTABLE.read_bytes())
            self.assertEqual(run("--verify", output).returncode, 0)
            wrong = Path(directory) / "wrong.json.gz"
            wrong.write_bytes(b"invalid")
            absent = Path(directory) / "absent.json.gz"
            for option in ("--input", "--windows"):
                self.assertNotEqual(run(option, wrong, "--out", absent).returncode, 0)
                self.assertFalse(absent.exists())


if __name__ == "__main__":
    unittest.main()
