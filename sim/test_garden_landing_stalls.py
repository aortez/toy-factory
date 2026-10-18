#!/usr/bin/env python3
"""Read-only streak boundaries, censored observations and retained counterexamples."""

import copy
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_stalls as audit

PORTABLE = audit.ROOT / "benchmarks/garden-seasons/landing-stalls-results.json.gz"


class StallsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = audit.load(audit.ROOT / audit.INPUT)
        with patch.object(audit.previous.training, "native", side_effect=AssertionError("offline diagnosis launched a native run")):
            cls.result = audit.analyze(cls.data)

    def test_portable_result_recomputes_without_altering_history(self):
        self.assertEqual(json.loads(gzip.decompress(PORTABLE.read_bytes())), self.result)
        self.assertEqual(self.result["unchanged_comparison"], self.data["comparison"])
        self.assertEqual(self.result["input_sha256"], audit.INPUT_SHA)
        self.assertEqual(audit.digest(audit.ROOT / audit.INPUT), audit.INPUT_SHA)
        for old, new in zip(self.data["worlds"], self.result["worlds"], strict=True):
            self.assertEqual(new["id"], old["id"])
            for arm in audit.previous.ARMS:
                x = new["arms"][arm]
                self.assertEqual(x["unchanged_history"], old["arms"][arm]["history"])
                self.assertEqual(x["summary"]["all"]["resource_totals"],
                                 old["arms"][arm]["audit"]["summary"]["late_children"]["resources"])
                for k in ("trace_sha256", "water_trace_sha256"):
                    self.assertEqual(x[k], old["arms"][arm][k])
                for p in x["children"]:
                    self.assertTrue(62 * audit.DAY < p["birth_tick"] <= 190 * audit.DAY)
                    self.assertNotEqual(p["outcome"], "pending")
                    self.assertEqual(sum(s["samples"] for s in p["streaks"]), p["conflict_samples"])
                    for s in p["streaks"]:
                        self.assertEqual(s["span_ticks"], (s["samples"] - 1) * audit.STEP)
                        self.assertEqual(s["next_sample"]["tick"], s["last_tick"] + audit.STEP)

    def test_all_streak_endings_and_unfunded_continuations_are_kept(self):
        g = self.result["groups"]["all"]["water"]["all"]
        self.assertEqual((g["children"], g["affected_children"], g["conflict_samples"], g["streaks"]), (135, 77, 680, 174))
        self.assertEqual(g["streak_sample_distribution"], {"count": 174, "minimum": 1, "median": 2, "maximum": 25})
        self.assertEqual(g["next_sample_classes"], {"root_growth": 66, "shoot_growth": 70, "wait_without_funded_root": 38})
        self.assertEqual(g["wait_streak_samples"], {"count": 244, "minimum": 1, "median": 2, "maximum": 47})
        self.assertEqual(g["applied_waits"], 1282)
        self.assertEqual(g["initial_root_conflict_samples"], 621)
        self.assertEqual(g["streaks_with_later_root"], 136)
        self.assertEqual(sum(g["streak_sample_histogram"].values()), 174)
        self.assertEqual(sum(int(n) * count for n, count in g["streak_sample_histogram"].items()), 680)

    def test_survivors_failures_and_conditional_root_delay_are_distinct(self):
        g = self.result["groups"]["all"]["water"]
        self.assertEqual(g["with_conflict"]["outcomes"], {"confirmed": 38, "died": 39})
        self.assertEqual(g["without_conflict"]["outcomes"], {"confirmed": 22, "died": 36})
        self.assertEqual(g["with_conflict"]["death_shortages"], {"water": 24, "energy": 14, "energy+water": 1})
        self.assertEqual(g["with_conflict"]["children_with_root_after_conflict"], 59)
        self.assertEqual(g["with_conflict"]["root_expanded_before_conflict"], 4)
        self.assertEqual(g["with_conflict"]["children_never_expanding_roots_in_first_day"], 18)
        self.assertEqual(g["with_conflict"]["root_delay_ticks_conditional_on_observed_root"],
                         {"count": 59, "minimum": 15, "median": 135, "maximum": 1065})
        self.assertEqual({k: v["children_with_root_after_conflict"] for k, v in g["affected_outcomes"].items()},
                         {"survived": 38, "water": 7, "energy": 14, "energy+water": 0})
        self.assertEqual(g["with_conflict"]["conflict_shortage_timing"]["water"], {"before": 37, "no_shortage": 40})
        steady = self.result["groups"]["steady"]["water"]
        self.assertEqual(steady["with_conflict"]["outcomes"], {"died": 5})
        self.assertEqual(steady["without_conflict"]["outcomes"], {"confirmed": 1})
        self.assertEqual(steady["all"]["next_sample_classes"], {"shoot_growth": 2, "wait_without_funded_root": 7})

    def test_controls_are_actual_growth_not_waits_or_matched_descendants(self):
        g = self.result["groups"]["all"]["control"]["all"]
        self.assertEqual((g["children"], g["affected_children"], g["conflict_samples"], g["streaks"]), (127, 68, 99, 98))
        self.assertEqual(g["applied_waits"], 0)
        self.assertEqual(g["streak_sample_histogram"], {"1": 97, "2": 1})
        self.assertEqual(g["next_sample_classes"], {"no_recorded_winner": 87, "root_growth": 2, "shoot_growth": 9})
        for arm in audit.previous.ARMS:
            children = [p for w in self.result["worlds"] for p in w["arms"][arm]["children"]]
            self.assertLess(len({p["id"] for p in children}), len(children))
            self.assertEqual(audit.aggregate(children), self.result["groups"]["all"][arm]["all"])

    def test_streaks_do_not_bridge_gaps_or_accept_reordering(self):
        self.assertEqual(audit.consecutive([]), [])
        self.assertEqual(audit.consecutive([15, 30, 60, 75, 90]), [[15, 30], [60, 75, 90]])
        for invalid in ([15, 15], [30, 15], [16], [-15], [0], [True]):
            with self.assertRaises(RuntimeError):
                audit.consecutive(invalid)
        self.assertEqual(audit.distribution([]), {"count": 0, "minimum": None, "median": None, "maximum": None})

    def test_next_sample_preserves_unknown_death_and_guard_release(self):
        birth, tick = 15, 45
        row = {"stages": [[10, 5, 0, 0, 4]] * 5, "roots": 2}
        self.assertEqual(audit.next_sample(tick, birth, {}, {})["classification"], "followup_ended")
        self.assertEqual(audit.next_sample(tick, birth, {tick: row}, {})["classification"], "no_recorded_winner")
        wait = {"applied": False, "result_action": 0, "destination": None}
        self.assertEqual(audit.next_sample(tick, birth, {tick: row}, {tick: wait})["classification"], "policy_wait")
        end = birth + audit.DAY
        self.assertEqual(audit.next_sample(end, birth, {end: row}, {})["classification"], "guard_ended")
        dead = copy.deepcopy(row)
        dead["stages"][4][3] = 1
        self.assertEqual(audit.next_sample(tick, birth, {tick: dead}, {})["classification"], "died")

    def test_corrupt_receipts_and_resource_gaps_are_rejected_without_mutation(self):
        original = self.data["worlds"][0]["arms"]["water"]
        for kind in ("duplicate", "order", "water", "age", "action", "missing", "summary"):
            broken = copy.deepcopy(original)
            ws = broken["water_audit"]["winners"]
            if kind == "duplicate":
                ws.insert(0, ws[0])
            elif kind == "order":
                ws[0], ws[-1] = ws[-1], ws[0]
            elif kind == "water":
                ws[0]["water"] += 1
            elif kind == "age":
                ws[0]["age"] = 257
            elif kind == "action":
                next(w for w in ws if w["applied"])["result_action"] = 1
            elif kind == "missing":
                ws.remove(next(w for w in ws if w["result_action"] != 0))
            else:
                broken["water_audit"]["all"]["winners"] += 1
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                audit.validate_receipts(broken, True)
        by_id = audit.validate_receipts(original, True)
        p = next(p for p in original["audit"]["plants"] if by_id[p["id"]])
        before = copy.deepcopy(p)
        audit.summarize_child(p, by_id[p["id"]], audit.STOP)
        self.assertEqual(p, before)
        broken = copy.deepcopy(p)
        del broken["rows"][2]
        with self.assertRaises(RuntimeError):
            audit.summarize_child(broken, by_id[p["id"]], audit.STOP)

    def test_cli_roundtrip_no_clobber_and_invalid_inputs(self):
        script = audit.ROOT / "sim/garden_landing_stalls.py"
        def run(*args):
            return subprocess.run([sys.executable, "-W", "error", str(script), *map(str, args)],
                                  capture_output=True, timeout=45)
        with tempfile.TemporaryDirectory(prefix="landing-stalls-test-") as directory:
            output = Path(directory) / "diagnosis.json.gz"
            self.assertEqual(run("--out", output).returncode, 0)
            self.assertEqual(output.read_bytes(), PORTABLE.read_bytes())
            self.assertNotEqual(run("--out", output).returncode, 0)
            self.assertEqual(output.read_bytes(), PORTABLE.read_bytes())
            self.assertEqual(run("--verify", output).returncode, 0)
            bad = Path(directory) / "bad.json"
            bad.write_text("{}\n")
            self.assertNotEqual(run("--verify", bad).returncode, 0)
            unused = Path(directory) / "unused.json"
            self.assertNotEqual(run("--input", bad, "--out", unused).returncode, 0)
            self.assertFalse(unused.exists())


if __name__ == "__main__":
    unittest.main()
