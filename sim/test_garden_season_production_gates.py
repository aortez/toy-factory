#!/usr/bin/env python3
"""Exact gate boundaries, denominator semantics and portable production evidence."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import garden_season_production_gates as audit

BUILD = None


def fixture():
    plant = {"id": 1, "nodes": 4, "roots": 0, "genome": [0] * 8, "dead": False,
             "generation": 0, "energy": 96, "water": 40, "reproduction_cooldown": 16,
             "stress": 0, "flowers": 1, "spent_flowers": 1}
    values = [1, 0, 144, 64, 144, 64, 0, 0, 1, 0, 0, 7, 0, 255, True]
    return plant, values


class GateTests(unittest.TestCase):
    def test_resource_equality_debits_and_boundary_masks(self):
        plant, values = fixture()
        self.assertTrue(audit.decode(values, 60, plant, 255)["produced"])
        for index, gate in ((2, "energy"), (3, "water")):
            p, v = fixture()
            v[index] -= 1
            v[1], v[-1] = audit.BITS[gate], False
            p.update(energy=v[2], water=v[3], reproduction_cooldown=0, spent_flowers=0)
            self.assertFalse(audit.decode(v, 60, p, 255)["produced"])
            v[1] = 0
            with self.assertRaises(RuntimeError):
                audit.decode(v, 60, p, 255)
        for mutate in (lambda v: v.pop(), lambda v: v.__setitem__(0, 2),
                       lambda v: v.__setitem__(4, 143), lambda v: v.__setitem__(9, 65535),
                       lambda v: v.__setitem__(11, 8), lambda v: v.__setitem__(14, 1)):
            changed = values.copy()
            mutate(changed)
            with self.assertRaises(RuntimeError):
                audit.decode(changed, 60, plant, 255)

    def test_reserve_trait_upkeep_and_store_cap(self):
        p, _ = fixture()
        p["genome"][6] = -2
        self.assertEqual(audit.required_resources(p), (112, 56))
        p["genome"][6] = 2
        self.assertEqual(audit.required_resources(p), (176, 72))
        p.update(nodes=256)
        self.assertEqual(audit.required_resources(p), (224, 480))
        p["roots"] = 256
        self.assertEqual(audit.required_resources(p), (224, 64))

    def test_window_first_failure_and_overlapping_shortfalls(self):
        counts = audit.empty_counts()
        p, values = fixture()
        v = audit.decode(values, 60, p, 255)
        v.update(blockers=audit.BITS["bank"] | audit.BITS["energy"] | audit.BITS["water"],
                 energy=140, water=63, bank=8, produced=False)
        audit.add_visit(counts, v, 60)
        v["blockers"] |= audit.BITS["cadence"]
        audit.add_visit(counts, v, 75)
        v["blockers"] |= audit.BITS["dead"]
        audit.add_visit(counts, v, 90)
        self.assertEqual((counts["visits"], counts["live_visits"]), (3, 2))
        self.assertEqual(counts["shortfalls"], {"4,1,8": 1})
        result = audit.summarize([{"plant": {"death_tick": 90}, "counts": counts}])
        self.assertEqual(result["window"]["first_failed"]["bank"], 1)
        self.assertEqual(result["window"]["first_failed"]["energy"], 0)
        self.assertEqual(result["window"]["overlap"]["energy"], 1)
        self.assertEqual(result["window_parent_sufficient"]["resources"], 0)
        self.assertEqual(result["alive"], 0)

    def test_cohorts_keep_deaths_and_exclude_founders_and_one_day_boundary(self):
        parents = []
        for ident, parent, birth, death in ((1, 0, 0, None), (2, 1, 60, 60 + audit.DAY),
                (3, 1, 60, 75 + audit.DAY), (4, 1, audit.END - audit.DAY, None),
                (5, 1, audit.END - audit.DAY + 15, None)):
            parents.append({"plant": {"id": ident, "parent": parent, "birth_tick": birth,
                            "death_tick": death, "species": "flower"}, "counts": audit.empty_counts()})
        result = audit.aggregate([{"parents": parents}])
        self.assertEqual(result["whole"]["no_seed"]["parents"], 2)
        self.assertEqual(result["whole"]["no_seed"]["alive"], 1)
        self.assertEqual(result["closing"]["no_seed"]["parents"], 1)

    def test_native_cli_and_observed_hashes(self):
        if BUILD is None:
            self.skipTest("native build not supplied")
        binary = str(BUILD / "toy-factory-garden-production-audit")
        for args in ([], ["rainfed", "baseline", "123", "typo", "120"],
                     ["rainfed", "baseline", "0", "control", "120"],
                     ["rainfed", "baseline", "123", "control", "121"],
                     ["rainfed", "neural-reference", "123", "control", "120"]):
            self.assertEqual(subprocess.run([binary] + args, capture_output=True, timeout=30).returncode, 2)
        for arm in ("control", "guard"):
            command = [binary, "rainfed", "adaptive", "123", arm, "3840"]
            raw = subprocess.check_output(command, timeout=30)
            self.assertEqual(raw, subprocess.check_output(command, timeout=30))
            rows = [json.loads(line) for line in raw.splitlines()]
            self.assertEqual(rows[0]["fields"], list(audit.FIELDS))
            command = [str(BUILD / "toy-factory-garden-inspect"), "-", "rainfed", "adaptive",
                       "123", "--ticks", "3840", "--climate", "seasonal", "--death-audit"]
            if arm == "guard":
                command += ["--seedling-reserve", "all"]
            ordinary = [json.loads(line) for line in subprocess.check_output(command, timeout=30).splitlines()]
            worlds = [w for w in ordinary if w["type"] == "world"]
            self.assertEqual([(r["tick"], r["hash"], r["created"]) for r in rows[1:]],
                             [(w["tick"], w["hash"], w["seeds_created"]) for w in worlds])
            for row, world in zip(rows[2:], worlds[1:]):
                self.assertEqual(len(row["visits"]), len(world["plants"]))
                for v, plant in zip(row["visits"], world["plants"]):
                    audit.decode(v, row["tick"], plant, world["sun_strength"], rows[0].get("seed_capacity", 8))

    def test_trace_missing_visits_hashes_identity_and_truncation(self):
        spec = {"mode": "seasonal", "scenario": "rainfed", "policy": "baseline", "seed": "ed52188c"}
        header = {"version": 1, "scenario": "rainfed", "policy": "baseline", "seed": spec["seed"],
                  "arm": "control", "end": 15, "climate": "seasonal", "dispersal": "wide-v1",
                  "fields": list(audit.FIELDS)}
        worlds = [{"tick": t, "hash": "deadbeef", "seeds_created": 0, "plants": [], "seeds": []}
                  for t in (0, 15)]
        native = [{"tick": t, "hash": "deadbeef", "created": 0, "visits": []} for t in (0, 15)]
        with tempfile.TemporaryDirectory() as folder:
            original, trace = Path(folder) / "old.gz", Path(folder) / "new.gz"
            original.write_bytes(gzip.compress(b"unchanged source"))
            old = {"case": spec, "arm": "control", "trace_sha256": audit.digest(original),
                   "ledger": {"parents": [], "seeds": []}}
            def run(rows):
                with gzip.open(trace, "wt") as stream:
                    stream.write("\n".join(json.dumps(r) for r in rows) + "\n")
                with patch.object(audit, "END", 15), patch.object(audit.funnel.population.reserve,
                        "groups", return_value=iter((w, [], []) for w in worlds)):
                    return audit.audit_trace(trace, original, old, 15)
            self.assertEqual(run([header] + native)["worlds"], 2)
            for mutate in (lambda r: r.pop(), lambda r: r[0].update(arm="guard"),
                           lambda r: r[2].update(hash="changed"), lambda r: r[2].update(tick=30),
                           lambda r: r[2].update(created=1), lambda r: r[2]["visits"].append([])):
                rows = copy.deepcopy([header] + native)
                mutate(rows)
                with self.assertRaises(RuntimeError):
                    run(rows)

    def test_portable_evidence_and_tampering(self):
        folder = audit.ROOT / "benchmarks/garden-seasons"
        path = folder / "production-gates-parents.json.gz"
        if not path.exists():
            self.skipTest("gate evidence not collected yet")
        report = json.loads(gzip.decompress(path.read_bytes()))
        prior = audit.load_input()
        audit.validate_report(report, prior)
        self.assertEqual(audit.compact(report), json.loads((folder / "production-gates-summary.json").read_text()))
        for cases in (report["cases"][:-1], report["cases"][:-1] + [report["cases"][0]]):
            with self.assertRaises(RuntimeError):
                audit.analysis(cases)
        for mutate in (lambda c: c["parents"].pop(),
                       lambda c: c["parents"][0]["counts"].update(productions=999),
                       lambda c: c["parents"][0]["counts"].update(live_visits=0),
                       lambda c: c["parents"][0]["counts"]["window_masks"].update({"1": 1}),
                       lambda c: c["parents"][0]["counts"]["shortfalls"].update({"-1,0,0": 1})):
            changed = copy.deepcopy(report["cases"][0])
            mutate(changed)
            with self.assertRaises(RuntimeError):
                audit.validate_case(changed, prior["cases"][0])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve() if args.build else None
    unittest.main(argv=[__file__] + rest)
