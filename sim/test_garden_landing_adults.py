#!/usr/bin/env python3
"""Adult trace inventory, accounting, window, identity and failure checks."""

import argparse
import copy
import json
from pathlib import Path
import tempfile
import unittest

import garden_landing_adults as trace
from test_garden_landing_tools import run

BUILD = None


class AdultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        models, archive = trace.arbitration.load_inputs(trace.ROOT / "benchmarks/garden-seasons")
        meta = archive["models"]["single-s6d697834-live"]
        cls.model_bytes = models[meta["model"]]

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="landing-adults-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cli = BUILD / "toy-factory-garden-landing"
        self.model = self.root / "model.tgl"
        self.model.write_bytes(self.model_bytes)

    def native(self, *args, **kwargs):
        raw = run([self.cli, *args], **kwargs)
        return json.loads(raw) if raw else None

    def sample(self, name="a", start=15, end=8 * trace.DAY, stop=None, mode="eligible"):
        stop = end if stop is None else stop
        args = ["arbitration-replay", self.model, "rainfed-crowded", "0x940cfdc4", "--ticks", stop,
                "--climate", "seasonal", "--water-arbitration", mode, "--ledger"]
        path = self.root / (name + ".jsonl")
        result = self.native(*args, "--adult-trace", path, "--adult-start", start, "--adult-stop", end)
        rows = trace.read_trace(path)
        return args, rows, result, trace.analyze(rows, result)

    def test_plain_repeat_pixels_and_window_identity(self):
        for mode in ("veto", "eligible"):
            args, rows, result, audit = self.sample(mode, mode=mode)
            self.assertEqual(self.native(*args), result)
            _, again, value, analysis = self.sample(mode + "-repeat", mode=mode)
            self.assertEqual((rows, result, audit), (again, value, analysis))
            _, clipped, value, short = self.sample(mode + "-window", start=2 * trace.DAY,
                                                  end=4 * trace.DAY, stop=result["tick"], mode=mode)
            self.assertEqual(value, result)
            self.assertEqual(clipped[1:-1], [r for r in rows[1:-1] if 2 * trace.DAY <= r["tick"] <= 4 * trace.DAY])
            self.assertTrue(any(p["left_censored"] for p in short["plants"]))
            self.assertTrue(any(p["last_tick"] - p["birth_tick"] > trace.DAY for p in audit["plants"]))
            raw, traced_raw = self.root / (mode + ".raw"), self.root / (mode + "-traced.raw")
            plain = self.native(*args, "--framebuffer", raw)
            framed = self.native(*args, "--framebuffer", traced_raw, "--adult-trace", self.root / (mode + "-framed.jsonl"),
                                 "--adult-start", 15, "--adult-stop", result["tick"])
            self.assertEqual(plain, framed)
            self.assertEqual(raw.read_bytes(), traced_raw.read_bytes())
        self.assertEqual(self.model.read_bytes(), self.model_bytes)

    def test_single_sample_and_non_ecology_horizon(self):
        for start, end, stop in ((15, 15, 15), (15, 15, 29), (60, 60, 61), (30, 75, 89)):
            _, rows, result, audit = self.sample(str(stop), start, end, stop)
            self.assertEqual(audit["ecology_samples"], (end - start) // trace.STEP + 1)
            self.assertEqual(rows[-1], {"complete": True, "tick": stop})
            self.assertEqual(trace.analyze(rows, result), audit)

    def test_existing_first_day_trace_unchanged_and_subset(self):
        args, rows, result, _ = self.sample(end=16 * trace.DAY)
        old, combined = self.root / "old.jsonl", self.root / "combined.jsonl"
        self.assertEqual(self.native(*args, "--recruitment-trace", old), result)
        self.assertEqual(self.native(*args, "--recruitment-trace", combined, "--adult-trace", self.root / "all.jsonl",
                         "--adult-start", 15, "--adult-stop", result["tick"]), result)
        self.assertEqual(old.read_bytes(), combined.read_bytes())
        first_day = trace.read_trace(old)[1:-1]
        self.assertTrue(any(r["plants"] for r in first_day))
        for a, b in zip(rows[1:-1], first_day, strict=True):
            self.assertEqual((a["tick"], a["seeds"]), (b["tick"], b["seeds"]))
            self.assertTrue(all(p in a["plants"] for p in b["plants"]))

    def test_corruption_missing_duplicate_stress_and_budgets_fail(self):
        _, rows, result, _ = self.sample(end=4 * trace.DAY)
        pi = next(i for i, r in enumerate(rows) if r.get("plants") and r["tick"] % 60 == 0)
        si = next(i for i, r in enumerate(rows) if r.get("seeds"))
        bad_cases = [rows[:-1], rows[:2] + rows[3:], rows + [rows[-1]]]
        for kind in ("missing_plant", "duplicate_plant", "income", "continuity", "stress", "mask", "seed", "bank"):
            bad = copy.deepcopy(rows)
            p = bad[pi]["plants"][0]
            if kind == "missing_plant":
                bad[pi]["plants"] = []
            elif kind == "duplicate_plant":
                bad[pi]["plants"].append(p)
            elif kind == "income":
                p["uptake"][0][1] += 1
            elif kind == "continuity":
                p["uptake"][0][0] += 1
                p["uptake"][0][2] += 1
            elif kind == "stress":
                for stage in p["stages"][1:]:
                    stage[2] = (stage[2] + 1) % 8
            elif kind == "mask":
                bad[si]["seeds"][0][3] ^= 64
            elif kind == "seed":
                bad[si]["seeds"] = []
            else:
                bad[si]["bank"] = 9
            bad_cases.append(bad)
        for bad in bad_cases:
            with self.assertRaises((RuntimeError, ValueError, TypeError, KeyError)):
                trace.analyze(bad, result)

    def test_deaths_births_and_censoring_balance(self):
        _, _, _, audit = self.sample(end=32 * trace.DAY)
        deaths = [p for p in audit["plants"] if not p["right_censored"]]
        births = [p for p in audit["plants"] if not p["left_censored"]]
        self.assertTrue(deaths)
        self.assertTrue(births)
        self.assertTrue(all(p["death_shortage"] for p in deaths))
        for p in births:
            self.assertEqual([p["resources"][r]["initial"] for r in ("energy", "water")], [64, 24])
        for p in audit["plants"]:
            self.assertEqual(p["samples"], (p["last_tick"] - p["first_tick"]) // trace.STEP + 1)
            for r in p["resources"].values():
                self.assertEqual(r["initial"] + r["income"], sum(r[k] for k in trace.FIELDS if k not in ("initial", "income")))

    def test_argument_and_output_safety(self):
        base = ["replay", self.model, "rainfed", "1", "--ticks", 60, "--climate", "steady"]
        path = self.root / "safe.jsonl"
        for start, end in ((0, 60), (15, 14), (16, 60), (15, 61), (15, 75), (-15, 60), (15, "")):
            self.native(*base, "--ledger", "--adult-trace", path, "--adult-start", start, "--adult-stop", end, valid=False)
            self.assertFalse(path.exists())
        for suffix in (("--adult-trace", path), ("--adult-start", 15, "--adult-stop", 60),
                       ("--adult-trace", path, "--adult-start", 15, "--adult-stop", 60, "--adult-start", 15)):
            self.native(*base, "--ledger", *suffix, valid=False)
            self.assertFalse(path.exists())
        options = ("--adult-trace", path, "--adult-start", 15, "--adult-stop", 60)
        self.native(*base, *options, valid=False)
        path.write_bytes(b"preserve")
        self.native(*base, "--ledger", *options, valid=False)
        self.assertEqual(path.read_bytes(), b"preserve")

    def test_saved_pair_has_balanced_adults_and_unchanged_history(self):
        path = trace.ROOT / "benchmarks/garden-seasons/landing-adult-resources-results.json.gz"
        trace.verify(path)
        import gzip
        data = json.loads(gzip.decompress(path.read_bytes()))
        eligible = data["arms"]["eligible"]["audit"]
        veto = data["arms"]["veto"]["audit"]
        self.assertEqual((eligible["ecology_samples"], eligible["plant_samples"], eligible["seed_samples"]),
                         (8705, 32234, 66816))
        self.assertEqual((veto["ecology_samples"], veto["plant_samples"], veto["seed_samples"]),
                         (8705, 37817, 68331))
        old = [p for p in eligible["plants"] if p["id"] in (25, 26, 27, 28)]
        self.assertEqual(len(old), 4)
        self.assertTrue(all(p["death_shortage"] == "energy" for p in old))
        self.assertEqual([p["resources"]["water"]["discarded"] for p in old], [510, 461, 468, 510])
        self.assertTrue(all(p["days"][str(d)]["resources"][r][expense] == 0
                            for p in old for d in (124, 125, 126) for r in ("energy", "water")
                            for expense in ("growth", "reproduction")))
        for d in (124, 125):
            self.assertEqual(eligible["days"][str(d)]["blockers"]["spacing"], 2048)
        for arm in data["arms"].values():
            for frame in arm["frames"]:
                image = trace.ROOT / "benchmarks/garden-seasons/frames" / ("landing-adults-" + frame["id"] + ".png")
                self.assertEqual(trace.digest(image), frame["sha256"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path, required=True)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve()
    unittest.main(argv=[__file__, *rest])
