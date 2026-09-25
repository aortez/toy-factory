#!/usr/bin/env python3
"""Recruitment blocker accounting and native observer-neutrality regressions."""
import argparse
import copy
import gzip
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import garden_recruitment as audit


class RecruitmentTests(unittest.TestCase):
    @staticmethod
    def row(mask=0, age=8, seeds=True):
        return {"sites": [[mask, 100, 200] for _ in range(28)], "plants": [],
                "seeds": [{"age": age, "blockers": mask | int(age < 8)}] if seeds else []}

    def test_overlapping_blockers(self):
        r = self.row(16 | 8 | 4)
        v = audit.site_counts(r)
        self.assertEqual(v["mature_seed_samples"], 1)
        for name in ("node_capacity", "plant_capacity", "light"):
            self.assertEqual(v["blocked_" + name], 1)
            self.assertEqual(v["only_" + name], 0)
        self.assertEqual(v["any_open_relax_all_space_limits"], 0)
        self.assertEqual(v["actual_open_relax_nodes"], 0)
        v = audit.site_counts(self.row(16 | 8))
        self.assertEqual(v["any_open_relax_all_space_limits"], 1)
        self.assertEqual(v["actual_open_relax_all_space_limits"], 1)
        self.assertEqual(v["actual_open_relax_nodes"], 0)
        v = audit.site_counts(self.row(2))
        self.assertEqual(v["only_moisture"], 1)
        self.assertEqual(v["actual_open_relax_moisture"], 1)

    def test_supply_and_dormancy(self):
        for r in (self.row(seeds=False), self.row(age=7)):
            v = audit.site_counts(r)
            self.assertEqual(v["mature_seed_samples"], 0)
            self.assertEqual(v["any_open_without_mature_seed"], 1)
            self.assertEqual(v["mature_bank_any_open"], 0)
            self.assertEqual(v["actual_open_relax_none"], 0)
        v = audit.site_counts(self.row())
        self.assertEqual(v["mature_bank_any_open"], 1)
        self.assertEqual(v["actual_open_relax_none"], 1)

    def test_identity(self):
        for capacity in (256, 512):
            for side in ("neural", "reserve"):
                r = {"node_capacity": capacity}
                if side == "reserve":
                    r["growth_policy"] = audit.policy.RESERVE
                audit.site_identity(r, capacity, side)
                for bad in ({**r, "node_capacity": 768-capacity},
                            {**r, "growth_policy": "unknown"},
                            {**r, "drainage_rule": "bottom-drainage-v1"}):
                    with self.assertRaises(RuntimeError):
                        audit.site_identity(bad, capacity, side)
                with self.assertRaises(RuntimeError):
                    audit.site_identity(r, capacity, "adaptive")
        with self.assertRaises(RuntimeError):
            audit.site_identity({}, 512, "neural")
        with self.assertRaises(RuntimeError):
            audit.site_identity({}, 256, "reserve")

    def test_geometry_and_phase(self):
        for mask in (1, 64, -1):
            with self.assertRaises(RuntimeError):
                audit.site_counts(self.row(mask))
        r = self.row()
        r["plants"] = [{"column": 0, "dead": True}]
        with self.assertRaises(RuntimeError):
            audit.site_counts(r)
        for column in range(3):
            r["sites"][column][0] = 32
        self.assertEqual(audit.site_counts(r)["spacing_open_columns"], 25)
        for sun, strength, expected in ((0, 127, "twilight"), (64, 128, "bright"), (128, 0, "night")):
            self.assertEqual(audit.phase({"sun_phase": sun, "sun_strength": strength}), expected)


def integration(build):
    horizon = 18 * audit.DAY
    with tempfile.TemporaryDirectory(prefix="garden-recruitment-test-") as temp:
        root = Path(temp)
        model = root / "model.tgm"
        subprocess.run([str(build / "toy-factory-garden-water-audit-test"), str(model)],
                       check=True, timeout=60)
        for side in ("neural", "reserve"):
            folder = root / side
            folder.mkdir()
            schedule = audit.diversity.SCHEDULES["fresh-4"]
            args = [str(model), "rainfed-crowded", audit.policy.POLICIES[side], "0xb61837dc",
                    "--leaf-policy", "selective", "--disturbance-seed", str(schedule)]
            bounds = {}
            for kind, flag in (("world", "--ecology"), ("sites", "--seed-sites"), ("population", "--population")):
                bounds[kind] = audit.diversity.disturbance.capture(
                    [str(build / "toy-factory-garden-inspect"), *args, flag, "--ticks", str(horizon)],
                    folder / f"{kind}.gz", root, "seed-sites" if kind == "sites" else "world", schedule, horizon)
            with gzip.open(folder / "world.gz", "rt") as stream:
                first = json.loads(next(stream))
            capacity = first.get("node_capacity", 256)
            prior = audit.diversity.analyze(folder / "population.gz", bounds["population"],
                capacity, horizon, schedule, growth_policy=audit.policy.RESERVE if side == "reserve" else None)

            def run(boundaries=bounds, world_path=folder / "world.gz", site_path=folder / "sites.gz",
                    sparse_path=folder / "population.gz"):
                return audit.analyze(world_path, site_path, boundaries, prior,
                    sparse_path, capacity, side, horizon, 2)

            result = run()
            assert result["seeds"]["checkpoints_verified"] == horizon // 15 + 1
            assert sum(v["samples"] for v in result["spatial"]["late"].values()) == 512
            assert len(result["patches"]) == 1
            assert result["patches"][0]["event"]["tick"] == 16 * audit.DAY
            assert sum(v["samples"] for v in result["patches"][0]["spatial"].values()) == 513
            replay = json.loads(subprocess.check_output([str(build / "toy-factory-garden-replay"),
                *args, "--ticks", str(horizon)], text=True, timeout=60))
            assert replay["hash"] == result["world"]["final"]["hash"]
            assert result["world"]["windows"]["whole"]["budget_checked_live_steps"] > 0

            for kind, argument in (("world", "world_path"), ("sites", "site_path"),
                                   ("population", "sparse_path")):
                with gzip.open(folder / f"{kind}.gz", "rt") as stream:
                    rows = list(stream)
                truncated = folder / f"{kind}.truncated.gz"
                with gzip.open(truncated, "wt") as stream:
                    stream.writelines(rows[:-1])
                with unittest.TestCase().assertRaises(RuntimeError):
                    run(**{argument: truncated})
            bad = copy.deepcopy(bounds)
            bad["sites"] = []
            with unittest.TestCase().assertRaises(RuntimeError):
                run(boundaries=bad)
            bad = copy.deepcopy(bounds)
            bad["sites"][0]["after"]["hash"] = "00000000"
            with unittest.TestCase().assertRaises(RuntimeError):
                run(boundaries=bad)
            bad = copy.deepcopy(bounds)
            bad["world"][0]["after"]["growth_policy"] = "unknown"
            with unittest.TestCase().assertRaises(RuntimeError):
                run(boundaries=bad)
            print(f"Native {capacity}/{side} recruitment neutrality passed", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path)
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RecruitmentTests)
    if not unittest.TextTestRunner().run(suite).wasSuccessful():
        raise SystemExit(1)
    if args.build:
        integration(args.build.resolve())
