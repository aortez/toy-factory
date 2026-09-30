#!/usr/bin/env python3
"""Production reach, trace completeness, replay identity and portable evidence."""

import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import garden_landing_reach as reach
from test_garden_landing_tools import run

BUILD = None


class ReachTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel, cls.archive, cls.previous = reach.load_inputs(reach.ROOT / "benchmarks/garden-seasons")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="landing-reach-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cli = BUILD / "toy-factory-garden-landing"
        self.m = self.previous["models"]["multi-s6d697834-live"]
        self.model = self.root / "model.tgl"
        self.model.write_bytes(self.archive[self.m["model"]])

    def native(self, *args, **kwargs):
        value = run([self.cli, *args], **kwargs)
        return json.loads(value) if value else None

    def sample(self, ticks=16 * reach.DAY, name="sample"):
        args = [self.model, "rainfed", "0x5aa2b327", "--ticks", ticks, "--climate", "steady", "--ledger"]
        path, prior_path = self.root / (name + ".jsonl"), self.root / (name + "-prior.jsonl")
        result = self.native("replay", *args, "--reach-trace", path, "--recruitment-trace", prior_path)
        previous = reach.prior.analyze_trace(prior_path, result)
        return args, path, result, previous, reach.analyze_trace(path, result, previous)

    def test_all_origins_traits_and_reflection_multiplicity(self):
        self.assertEqual(reach.support(0, -2), [3, 3, 4, 4, 5, 5])
        self.assertEqual(reach.support(27, -2), [24, 24, 23, 23, 22, 22])
        self.assertEqual(reach.support(13, 0), [8, 18, 7, 19, 6, 20])
        for origin in range(28):
            for trait in range(-2, 3):
                values = reach.support(origin, trait)
                self.assertEqual(len(values), 6)
                self.assertTrue(all(0 <= c < 28 for c in values))
                self.assertEqual(reach.support(27 - origin, trait), [27 - c for c in values[1::-1]] +
                                 [27 - c for c in values[3:1:-1]] + [27 - c for c in values[5:3:-1]])
        for args in ((-1, 0), (28, 0), (0, -3), (0, 3)):
            with self.assertRaises(RuntimeError):
                reach.support(*args)

    def test_plain_repeat_and_partial_horizons(self):
        for ticks in (0, 14, 15, 3839, 3840, 3841, 16 * reach.DAY):
            args, path, result, previous, analysis = self.sample(ticks, str(ticks))
            self.assertEqual(self.native("replay", *args), result)
            repeated = self.root / (str(ticks) + "-repeat.jsonl")
            self.assertEqual(self.native("replay", *args, "--reach-trace", repeated), result)
            self.assertEqual(path.read_bytes(), repeated.read_bytes())
            self.assertEqual(reach.analyze_trace(repeated, result, previous), analysis)
            self.assertEqual(analysis["ecology_samples"], ticks // reach.STEP)
        self.assertTrue(analysis["seeds"])
        self.assertEqual(self.model.read_bytes(), self.archive[self.m["model"]])

    def test_corrupt_incomplete_duplicated_and_wrong_support_fail(self):
        _, path, result, previous, analysis = self.sample()
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        buy = next(i for i, r in enumerate(rows) if r.get("purchases"))
        check = next(i for i, r in enumerate(rows) if r.get("checks"))
        cases = [rows[:-1], rows[:2] + rows[3:], rows + [rows[-1]]]
        for kind in ("purchase", "missing", "duplicate", "trait", "origin", "choices", "sites", "mask", "null"):
            bad = copy.deepcopy(rows)
            if kind == "purchase":
                bad[buy]["purchases"] = []
            elif kind == "missing":
                bad[check]["checks"] = []
            elif kind == "duplicate":
                bad[check]["checks"] += bad[check]["checks"][:1]
            elif kind in ("trait", "origin", "choices"):
                p = bad[buy]["purchases"][0]
                if kind == "trait":
                    p["dispersal"] = 3
                elif kind == "origin":
                    p["origin"] = (p["origin"] + 1) % 28
                else:
                    p["choices"] = [p["column"]] * 6
            elif kind == "sites":
                bad[check]["checks"][0][6] = "01" * 28
            elif kind == "mask":
                bad[check]["checks"][0][3] ^= 32
            else:
                bad[check]["checks"][0][6] = None
            cases.append(bad)
        for i, bad in enumerate(cases):
            output = self.root / ("bad-" + str(i) + ".jsonl")
            output.write_text("".join(json.dumps(r) + "\n" for r in bad))
            with self.assertRaises((RuntimeError, StopIteration, TypeError)):
                reach.analyze_trace(output, result, previous)
        self.assertEqual(reach.analyze_trace(path, result, previous), analysis)

    def test_expiry_pending_and_open_windows(self):
        _, path, _, _, analysis = self.sample(48 * reach.DAY)
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        expired, pending = 0, 0
        for s in analysis["seeds"]:
            mature = sum(s["mature_sites"].values())
            if s["outcome"] == "expired":
                expired += 1
                self.assertEqual((s["samples"], sum(s["masks"].values()), mature), (8192, 8191, 8184))
            elif s["outcome"] == "pending":
                pending += 1
                self.assertEqual(s["samples"], sum(s["masks"].values()))
            opened = [[] for _ in range(28)]
            for row in rows[1:-1]:
                for parent, age, _, mask, outcome, _, encoded in row["checks"]:
                    if (parent, row["tick"] - age * reach.STEP) == (s["parent"], s["birth_tick"]) and not mask & 1 and outcome != 1:
                        for c, value in enumerate(reach.sites_decode(encoded)):
                            if value == 0:
                                opened[c].append(row["tick"])
            for c, ticks in enumerate(opened):
                streak, longest, last = 0, 0, None
                for tick in ticks:
                    streak = streak + 1 if last is not None and last + reach.STEP == tick else 1
                    longest, last = max(longest, streak), tick
                self.assertEqual(s["open_windows"][c], [len(ticks), ticks[0] if ticks else None, last, longest])
        self.assertTrue(expired and pending)

    def test_cli_fresh_output_ledger_exclusive_mode_and_no_overrides(self):
        args = [self.model, "rainfed", "0x1234", "--ticks", 0, "--climate", "steady"]
        path = self.root / "reach.jsonl"
        for command in (["replay", *args, "--reach-trace", path],
                        ["replay", *args, "--ledger", "--reach-trace", path, "--reach-trace", path],
                        ["trace-replay", *args, "--ledger", "--reach-trace", path],
                        ["probe-replay", *args, "--ledger", "--reach-trace", path]):
            self.native(*command, valid=False)
            self.assertFalse(path.exists())
        path.write_bytes(b"keep me")
        self.native("replay", *args, "--ledger", "--reach-trace", path, valid=False)
        self.assertEqual(path.read_bytes(), b"keep me")
        tool, out = reach.ROOT / "sim/garden_landing_reach.py", self.root / "bundle"
        run([sys.executable, tool, "--out", out, "--jobs", 0], valid=False)
        self.assertFalse(out.exists())
        run([sys.executable, tool, "--verify", out, "--jobs", 2], valid=False)

    def test_portable_histograms_identity_and_report_counts(self):
        directory = reach.ROOT / "benchmarks/garden-seasons"
        full = json.loads(gzip.decompress((directory / "landing-reach-results.json.gz").read_bytes()))
        summary = json.loads((directory / "landing-reach-summary.json").read_text())
        self.assertEqual(full["plan"], self.previous["plan"])
        self.assertEqual(full["rule"], reach.RULE)
        self.assertEqual(full["inputs"], reach.INPUTS)
        canonical = (json.dumps(full, sort_keys=True, indent=2) + "\n").encode()
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), summary["results_sha256"])
        self.assertEqual(reach.digest(reach.ROOT / reach.PROTOCOL), summary["protocol_sha256"])
        self.assertEqual(summary["manifest_sha256"],
                         "0c08a37256b2e42d6f7d553b860448d26975599ea2431442274f44e6cb288656")
        self.assertIs(summary["repeat_verified"], True)
        self.assertIs(summary["independent_frozen_verification"], True)
        self.assertEqual(summary["artifact_hashes_rechecked"], 303)
        all_seeds, late = [], {"steady": [], "seasonal": []}
        for w, old, brief in zip(full["worlds"], self.previous["worlds"], summary["worlds"], strict=True):
            self.assertEqual(w["id"], old["id"])
            self.assertEqual(w["result"], old["result"])
            self.assertEqual(w["recruitment_trace_sha256"], old["trace_sha256"])
            self.assertEqual(brief, {k: w[k] for k in ("id", "model", "case", "trace_sha256", "recruitment_trace_sha256")} |
                             {"audit": {k: v for k, v in w["audit"].items() if k != "seeds"}})
            olds = {(s["parent"], s["birth_tick"]): s for s in old["audit"]["seeds"]}
            plants = {p["id"]: p for p in w["result"]["lineages"]}
            for s in w["audit"]["seeds"]:
                p = s["purchase"]
                self.assertEqual(p["origin"], plants[s["parent"]]["column"])
                self.assertEqual(p["choices"], reach.support(p["origin"], p["dispersal"]))
                self.assertIn(s["column"], p["choices"])
                self.assertEqual(reach.opportunities(s), s["opportunities"])
                previous = olds.pop((s["parent"], s["birth_tick"]))
                for field in ("samples", "masks", "open_elsewhere_checks"):
                    self.assertEqual(s[field], previous[field])
                self.assertEqual(sum(s["mature_sites"].values()), sum(previous["mature_masks"].values()))
                for c, (count, first, last, longest) in enumerate(s["open_windows"]):
                    self.assertEqual(count, sum(n for encoded, n in s["mature_sites"].items()
                                                if not bytes.fromhex(encoded)[c]))
                    if count:
                        self.assertTrue(s["birth_tick"] + 8 * reach.STEP <= first <= last <=
                                        (s["end_tick"] or reach.STOP))
                        self.assertTrue(1 <= longest <= count <= (last - first) // reach.STEP + 1)
                    else:
                        self.assertEqual((first, last, longest), (None, None, 0))
            self.assertFalse(olds)
            rows = w["audit"]["seeds"]
            expired = [s for s in rows if s["outcome"] == "expired" and
                       62 * reach.DAY < s["end_tick"] <= 190 * reach.DAY]
            self.assertEqual(w["audit"]["summary"], {"all_seeds": reach.summarize(rows),
                             "late_expired": reach.summarize(expired)})
            all_seeds.extend(rows)
            late[w["case"]["climate"]].extend(expired)
        self.assertEqual(summary["all_seeds"], reach.summarize(all_seeds))
        self.assertEqual(summary["all_seeds"]["outcomes"], {"expired": 439, "germinated": 271, "pending": 96})
        self.assertEqual(summary["totals"], {"ecology_samples": 589824, "seed_samples": 4592849})
        for climate in late:
            self.assertEqual(summary["late_expired"][climate], reach.summarize(late[climate]))
        steady, seasonal = (summary["late_expired"][c] for c in ("steady", "seasonal"))
        self.assertEqual((steady["seeds"], steady["any_reachable_open"], steady["always_reachable_spacing_blocked"]),
                         (192, 22, 170))
        self.assertEqual((seasonal["seeds"], seasonal["any_reachable_open"], seasonal["always_reachable_spacing_blocked"]),
                         (151, 80, 44))
        self.assertEqual((steady["purchase_reachable_open"], seasonal["purchase_reachable_open"]), (6, 21))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path, required=True)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *rest])
