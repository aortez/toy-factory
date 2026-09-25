#!/usr/bin/env python3
"""Structural classification, malformed evidence and inspector neutrality tests."""
import argparse
import copy
import gzip
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import garden_renewal_topology as trial

BUILD = None


def fixture():
    nodes = [dict(index=i, owner=0, parent=trial.NONE if i == 0 else 0, x=20+i, y=100,
                  kind=int(i == 2), flags=trial.LEAF if i == 1 else 0, progress=255,
                  depth=int(i != 0), children=2 if i == 0 else 0, condition=0) for i in range(3)]
    plant = dict(index=0, id=1, flags=0, base=0, last_shoot_tip=trial.NONE, last_root_tip=trial.NONE)
    census = dict(id=1, flags=0, dead=False, nodes=3, roots=1, leaves=1, active_leaves=1,
                  tips=0, flowers=0, spent_flowers=0, leaf=dict(conditions=[0], renewals=0, restored=0, worn=0))
    world = dict(type="world", tick=3840, hash="01234567", nodes=3, plants=[census])
    top = dict(type="topology", schema_version=1, tick=3840, hash=world["hash"],
               node_capacity=512, nodes=nodes, plants=[plant])
    return top, world


class AnalysisTests(unittest.TestCase):
    def test_conservative_terminal_and_day_boundary(self):
        top, world = fixture()
        before = copy.deepcopy((top, world))
        found = trial.census(top, world, {(1, 0): 0})
        self.assertEqual(found["counts"]["eligible"], 1)
        self.assertEqual(found["counts"]["day_eligible"], 1)
        self.assertEqual(found["candidates"][0]["leaf_ordinal"], 0)
        self.assertEqual(found["upkeep_price_reduction_upper"]["eligible"], {"energy": 0, "water": 0})
        self.assertEqual((top, world), before)
        self.assertEqual(trial.census(top, world, {(1, 0): 15})["counts"]["day_eligible"], 0)

    def test_overlapping_roles_and_previous_tip_are_protected(self):
        top, world = fixture()
        top["nodes"][1]["flags"] |= trial.TIP | trial.PENDING | trial.FLOWER | 32
        top["plants"][0]["last_shoot_tip"] = 1
        world["plants"][0].update(tips=1, flowers=1, spent_flowers=1)
        counts = trial.census(top, world, {(1, 0): 0})["counts"]
        self.assertEqual(counts["eligible"], 0)
        self.assertTrue(all(counts[k] == 1 for k in ("tip", "branch_pending", "flower", "previous_tip")))

    def test_internal_leaf_is_not_a_terminal_tip(self):
        top, world = fixture()
        top["nodes"][2]["parent"] = 1
        top["nodes"][0]["children"] = 1
        top["nodes"][1]["children"] = 1
        self.assertEqual(trial.census(top, world, {(1, 0): 0})["counts"]["internal"], 1)
        self.assertEqual(trial.census(top, world, {(1, 0): 0})["counts"]["eligible"], 0)

    def test_root_and_base_reasons_are_independent(self):
        top, _ = fixture()
        p = top["plants"][0]
        node = dict(top["nodes"][0], kind=1, flags=trial.LEAF)
        self.assertEqual(trial.reasons(node, p, {0: 2}), ["base", "root", "internal"])

    def test_positive_and_dead_not_counted_as_zero(self):
        top, world = fixture()
        top["nodes"][1]["condition"] = 42
        world["plants"][0]["leaf"]["conditions"] = [42]
        counts = trial.census(top, world, {})["counts"]
        self.assertEqual((counts["zero"], counts["unprotected_terminal_positive"]), (0, 1))
        top["plants"][0]["flags"] = 1
        world["plants"][0].update(flags=1, dead=True)
        self.assertEqual(trial.census(top, world, {})["counts"]["unprotected_terminal_positive"], 0)

    def test_bad_structure_hash_condition_counts_and_references_fail(self):
        for case in ("count", "self", "owner", "base", "reference", "ordinal", "hash", "index", "bounds", "root"):
            top, world = fixture()
            if case == "count": top["nodes"][0]["children"] = 1
            if case == "self": top["nodes"][1]["parent"] = 1
            if case == "owner": top["nodes"][1]["owner"] = 1
            if case == "base": top["plants"][0]["base"] = 1
            if case == "reference": top["plants"][0]["last_shoot_tip"] = 3
            if case == "ordinal": top["nodes"][1]["condition"] = 255
            if case == "hash": top["hash"] = "00000000"
            if case == "index": top["nodes"][1]["index"] = 2
            if case == "bounds": top["nodes"][1]["depth"] = -1
            if case == "root": top["nodes"][1]["parent"] = trial.NONE
            with self.subTest(case=case), self.assertRaises(RuntimeError): trial.validate(top, world)

    def test_zero_history_is_required(self):
        top, world = fixture()
        with self.assertRaises(RuntimeError): trial.census(top, world, {})
        with self.assertRaises(RuntimeError): trial.census(top, world, {(1, 0): 3855})

    def test_quantized_price_is_per_owner(self):
        _, world = fixture()
        p = world["plants"][0]
        p.update(nodes=17, roots=8)
        self.assertEqual(trial.prior.upper_savings(p, 1), {"energy": 1, "water": 1})
        p.update(nodes=16, roots=8)
        self.assertEqual(trial.prior.upper_savings(p, 1), {"energy": 0, "water": 0})

    def test_history_identity_survives_owner_compaction_but_not_renewal(self):
        _, world = fixture()
        a, b, c, d = [copy.deepcopy(world) for _ in range(4)]
        for tick, row in zip((0, 15, 30, 45), (a, b, c, d), strict=True): row["tick"] = tick
        for row in (a, b, c, d): row["plants"][0]["id"] = 5
        removed = copy.deepcopy(a["plants"][0]); removed["id"] = 1
        a["plants"].insert(0, removed)
        c["plants"][0]["leaf"]["conditions"] = [255]
        with mock.patch.object(trial.prior, "leaf_transition"):
            found = trial.history([a, b, c, d], (0, 15, 30, 45))
            self.assertEqual(found[15][1], {(5, 0): 0})
            self.assertEqual(found[30][1], {})
            self.assertEqual(found[45][1], {(5, 0): 45})
            with self.assertRaises(RuntimeError): trial.history([a, c], (0, 30))

    def test_neutrality_checks_all_bytes_and_complete_checkpoint_inventory(self):
        top, world = fixture()
        line = json.dumps(world).encode()+b"\n"
        extra = json.dumps(top).encode()+b"\n"
        with tempfile.TemporaryDirectory() as tmp:
            original, observed = Path(tmp)/"old.gz", Path(tmp)/"new.gz"
            with gzip.open(original, "wb") as f: f.write(line)
            for payload, valid in ((line+extra, True), (line, False), (line+extra+extra, False),
                                   (extra+line, False), (line+b" "+extra, True),
                                   (line.replace(b"3840", b"3855")+extra, False), (b"", False)):
                with gzip.open(observed, "wb") as f: f.write(payload)
                if valid:
                    self.assertEqual(trial.neutral_trace(observed, original, [3840]), ([top], 1))
                else:
                    with self.assertRaises(RuntimeError): trial.neutral_trace(observed, original, [3840])


class InspectorTests(unittest.TestCase):
    def run_inspector(self, options, ticks=30):
        if BUILD is None: self.skipTest("requires --build")
        return subprocess.run([str(BUILD/"toy-factory-garden-inspect"), "-", "rainfed", "adaptive",
                               "123", "--ticks", str(ticks), *options], capture_output=True, timeout=20)

    def test_capture_off_on_repeat_and_leaf_mode(self):
        base = self.run_inspector(["--ecology"])
        options = ["--ecology", "--topology-at", "0", "--topology-at", "15", "--topology-at", "30"]
        enabled, repeat = self.run_inspector(options), self.run_inspector(options)
        self.assertEqual((base.returncode, enabled.returncode, repeat.returncode), (0, 0, 0), enabled.stderr)
        self.assertEqual(enabled.stdout, repeat.stdout)
        old, tops, previous = [], [], None
        for line in enabled.stdout.splitlines(keepends=True):
            row = json.loads(line)
            if row["type"] == "topology":
                trial.validate(row, previous)
                tops.append(row["tick"])
            else:
                old.append(line); previous = row
        self.assertEqual(b"".join(old), base.stdout)
        self.assertEqual(tops, [0, 15, 30])

    def test_bad_cli_and_checkpoint_bound(self):
        cases = [["--topology-at"], ["--topology-at", "no"], ["--topology-at", "-15"],
                 ["--topology-at", "4294967296"], ["--topology-at", "1"], ["--topology-at", "45"],
                 ["--topology-at", "0", "--topology-at", "0"],
                 ["--topology-at", "15", "--topology-at", "0"],
                 ["--seed-sites", "--topology-at", "0"]]
        for options in cases:
            p = self.run_inspector(["--ecology", *options])
            self.assertEqual((p.returncode, p.stdout), (2, b""), p.stderr)
        p = self.run_inspector(["--topology-at", "0"])
        self.assertEqual((p.returncode, p.stdout), (2, b""))
        points = [s for tick in range(0, 255, 15) for s in ("--topology-at", str(tick))]
        self.assertEqual(self.run_inspector(["--ecology", *points[:-2]], 300).returncode, 0)
        p = self.run_inspector(["--ecology", *points], 300)
        self.assertEqual((p.returncode, p.stdout), (2, b""))

    def test_event_tick_has_separately_adjacent_topologies(self):
        help_result = subprocess.run([str(BUILD/"toy-factory-garden-inspect"), "--help"], capture_output=True) if BUILD else None
        if help_result is None or b"--gap-at" not in help_result.stdout: self.skipTest("requires maintenance experiment")
        options = ["--ecology", "--gap-at", "3840", "--topology-at", "3840"]
        base = self.run_inspector(options[:-2], 3855)
        enabled = self.run_inspector(options, 3855)
        self.assertEqual((base.returncode, enabled.returncode), (0, 0), enabled.stderr)
        remaining, tops, previous = [], [], None
        for line in enabled.stdout.splitlines(keepends=True):
            row = json.loads(line)
            if row["type"] == "topology":
                trial.validate(row, previous); tops.append(row)
            else:
                remaining.append(line); previous = row
        self.assertEqual(b"".join(remaining), base.stdout)
        self.assertEqual(len(tops), 2)
        self.assertNotEqual(tops[0]["hash"], tops[1]["hash"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    args, rest = parser.parse_known_args()
    BUILD = args.build.resolve() if args.build else None
    unittest.main(argv=[__file__, *rest])
