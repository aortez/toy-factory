#!/usr/bin/env python3
"""Population scope, frozen calls, no-clobber CLI, accounting and comparison checks."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest

import garden_landing_population as screen
from test_garden_landing_tools import run

BUILD = None


class ContractTests(unittest.TestCase):
    def test_frozen_panel_and_one_difference(self):
        self.assertEqual(screen.FRESH, ("f7ee4528", "04fa8f03", "5181d0db"))
        self.assertEqual(len(screen.CASES), 8)
        paths = []
        for case in screen.CASES:
            for label in screen.LABELS:
                a, b = [screen.arguments(case, arm, label) for arm in screen.ARMS]
                self.assertEqual(b[-1], "--root-dawn-reserve")
                self.assertEqual([arg.replace("-candidate-", "-control-") for arg in b[:-1]], a)
                self.assertNotIn("--root-choice-at", a)
                for args in (a, b):
                    paths.append(args[args.index("--framebuffer") + 1])
        self.assertEqual(len(set(paths)), 32)

    def test_payment_uses_pre_growth_roots_and_ignores_stale_flags(self):
        p = {"uptake": [[0] * 6] * 2, "stages": [[2, 0, 0, 0, 17], [0, 0, 1, 6, 17]], "roots": 10}
        r = {"energy": {"upkeep": 2}, "water": {"upkeep": 0}}
        self.assertIsNone(screen.payment(p, r, 8, 75, 69))
        e = screen.payment(p, r, 8, 60, 68)
        self.assertEqual(e["energy"], {"due": 3, "paid": 2, "unpaid": 1})
        self.assertEqual(e["water"], {"due": 2, "paid": 0, "unpaid": 2})
        p["stages"][1][3] = 0
        with self.assertRaises(RuntimeError):
            screen.payment(p, r, 8, 60, 68)

    def test_saved_birth_and_adult_receipts_with_population_validator(self):
        with gzip.open(screen.ROOT / screen.INPUT, "rt") as stream:
            saved = json.load(stream)
        for entry in saved["cases"]:
            for arm in screen.ARMS:
                focal = entry["arms"][arm]["analysis"]
                life, before = focal["focal"]["life"], None
                for step in screen.dawn.steps(focal):
                    if step["bids"]:
                        screen.check_growth({"tick": step["tick"]}, {"sun": step["sun"], "plants": [step["plant"]]},
                                            life, step["bids"], step["body"], before, arm)
                    before = step["body"]

    def test_censoring_and_identity_matching(self):
        life = {"birth_tick": 100, "death_tick": None}
        self.assertEqual(screen.survival(life, 100 + screen.DAY - 1, 1), "censored")
        self.assertEqual(screen.survival(life, 100 + screen.DAY, 1), "confirmed")
        life["death_tick"] = 100 + screen.DAY
        self.assertEqual(screen.survival(life, 100 + screen.DAY, 1), "died")
        founder = {"id": 1, "parent": 0, "birth_tick": 0, "column": 3, "species": 0}
        child = {**founder, "id": 5, "parent": 1, "birth_tick": 300, "column": 8}
        a = {"lineages": [founder, child]}
        b = {"lineages": [{**founder, "id": 2}, {**child, "id": 9, "parent": 2}]}
        self.assertEqual(screen.matched_births(a, b)["matched"], [[1, 2], [5, 9]])
        b["lineages"][1]["column"] += 1
        self.assertEqual(screen.matched_births(a, b)["control_only"], [5])

    def test_blocked_extension_still_pays_but_wait_and_denied_do_not(self):
        bid = {"action": 1, "available": 0, "energy_gate": {"vigor": 0}}
        stages = [None, None, [50, 20], [41, 15]]
        screen.check_spending(stages, bid, True, 0)
        for eligible, action in ((False, 1), (True, 0)):
            bid["action"] = action
            with self.assertRaises(RuntimeError):
                screen.check_spending(stages, bid, eligible, 0)
            screen.check_spending([None, None, [50, 20], [50, 20]], bid, eligible, 0)

    def test_exposure_and_harm_not_hidden_by_totals(self):
        a = dict(living=2, species=[0, 1], seed_parents=1, successful_parents=1, founder_credit=100,
                 closing_credit=100, first_empty_tick=None, survival={"1": {"confirmed": 2}, "32": {"confirmed": 1}},
                 resources={"offspring": {"payments": 100, "energy": {"unpaid": 10}, "water": {"unpaid": 0}}})
        b = copy.deepcopy(a)
        b["resources"]["offspring"].update(payments=10, energy={"unpaid": 5})
        self.assertFalse(screen.comparison(a, b)["passes_harm_screen"])
        b["resources"]["offspring"]["payments"] = 100
        self.assertTrue(screen.comparison(a, b)["passes_harm_screen"])
        b["living"] = 1
        self.assertFalse(screen.comparison(a, b)["passes_harm_screen"])
        b["resources"]["offspring"]["payments"] = 0
        self.assertIsNone(screen.comparison(a, b)["unpaid_rate_comparison"]["energy"])


class FrozenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = screen.ROOT / "benchmarks/garden-seasons/landing-population-results.json.gz"
        screen.require(screen.experiment.digest(path) ==
            "c823c7b9d1c19d476403a5741a6ff25996ad60847f4340e2207ba2260091fa2a", "population evidence changed")
        with gzip.open(path, "rt") as stream:
            cls.value = json.load(stream)

    def test_offline_evidence_and_failed_qualification(self):
        screen.check_value(self.value)
        self.assertEqual(self.value["summary"], {
            "diagnostic": {"cases": 2, "harm_passes": 0, "improved_rate_pairs": 2},
            "fresh": {"cases": 6, "harm_passes": 2, "improved_rate_pairs": 4}, "passes_screen": False})
        self.assertEqual([e["first_effect"]["tick"] for e in self.value["cases"]],
                         [219675, 219675, 403545, 403545, 35025, 35025, 123825, 123825])
        for index, counts in ((0, (29, 3)), (1, (16, 3)), (2, (6, 36)), (3, (37, 47)),
                              (4, (35, 16)), (5, (38, 16)), (6, (4, 0)), (7, (10, 0))):
            self.assertEqual(tuple(self.value["cases"][index]["arms"][a]["metrics"]["resources"]["offspring"]["energy"]["shortages"]
                                   for a in screen.ARMS), counts)

    def test_corrupted_scope_receipts_comparison_and_coverage_rejected(self):
        for fault in ("identity", "payment", "coverage", "comparison", "effect", "matching"):
            value = copy.deepcopy(self.value)
            entry = value["cases"][0]
            arm = entry["arms"]["candidate"]
            if fault == "identity":
                arm["result"]["run_hash"] = "00000000"
            elif fault == "payment":
                p = next(p for p in arm["analysis"]["plants"] if p["shortages"])
                p["shortages"][0]["energy"]["due"] += 1
            elif fault == "coverage":
                arm["analysis"]["plants"][0]["samples"] -= 1
            elif fault == "comparison":
                entry["comparison"]["passes_harm_screen"] = True
            elif fault == "matching":
                entry["birth_matching"]["matched"].pop()
            else:
                entry["first_effect"]["matching_prior_samples"] += 1
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                screen.check_value(value)


class NativeTests(unittest.TestCase):
    def setUp(self):
        if BUILD is None:
            self.skipTest("pass --build for native tests")
        temporary = tempfile.TemporaryDirectory(prefix="garden-population-")
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name)
        (self.path / "frames").mkdir()
        (self.path / "model.tgl").write_bytes(screen.load_model()[1])
        self.binary = BUILD / "toy-factory-garden-landing"

    def native(self, args, valid=True):
        output = run([self.binary, *args], cwd=self.path, valid=valid)
        return json.loads(output) if output else None

    def test_short_full_stream_repeat_and_scope_identity(self):
        case = screen.CASES[0]
        captures = []
        for arm in screen.ARMS:
            args = screen.arguments(case, arm, "trace", stop=960)
            result = self.native(args)
            paths = [self.path / args[args.index("--" + kind + "-trace") + 1] for kind in ("stand", "adult")]
            analysis = screen.analyze(*paths, result, case, arm)
            screen.check_analysis(analysis, result)
            self.assertIsNone(analysis["first_choice"])
            normalized = screen.common_result(result, case, arm)
            captures.append((normalized, analysis))
            bad = copy.deepcopy(result)
            bad["root_all_offspring_probe"]["version"] = True
            with self.assertRaises(RuntimeError):
                screen.common_result(bad, case, arm)
            broken = self.path / (arm + "-broken.jsonl")
            lines = paths[0].read_text().splitlines(keepends=True)
            broken.write_text("".join(lines[:3] + lines[4:]))
            with self.assertRaises(RuntimeError):
                screen.analyze(broken, paths[1], result, case, arm)
        self.assertEqual(captures[0], captures[1])
        repeat = screen.arguments(case, "candidate", "repeat", stop=960)
        # Flags are order independent, including scope before/after prerequisites.
        repeat.remove("--root-all-offspring")
        repeat.append("--root-all-offspring")
        self.assertEqual(screen.common_result(self.native(repeat), case, "candidate"), captures[0][0])

    def test_invalid_scope_options_do_not_create_or_clobber_files(self):
        base = screen.arguments(screen.CASES[0], "control", "trace", stop=60)
        for remove, extra in ((None, ["--root-all-offspring"]), ("--root-daylight-energy", []),
                ("--root-continuous-energy", []), ("--root-afternoon-reserve", []), ("--root-energy-reserve", []),
                (None, ["--root-choice-at", "15", "--root-choice-lineage", "1"])):
            args = base.copy()
            if remove:
                args.remove(remove)
            self.native(args + extra, valid=False)
            self.assertEqual(list((self.path / "frames").iterdir()), [])
            self.assertEqual(list(self.path.glob("*.jsonl")), [])
        path = self.path / base[base.index("--stand-trace") + 1]
        path.write_bytes(b"preserve")
        self.native(base, valid=False)
        self.assertEqual(path.read_bytes(), b"preserve")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve() if args.build else None
    unittest.main(argv=[__file__, *rest])
