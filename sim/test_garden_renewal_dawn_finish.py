#!/usr/bin/env python3
"""Bounded intervention inventory, receipts, transaction isolation and CLI guards."""
import argparse
import copy
from pathlib import Path
import subprocess
import unittest
from unittest import mock

import garden_renewal_dawn_finish as trial

BUILD = None


def fixture():
    agent = {"decisions": 10, "finish": 0}
    plant = {"id": 12, "energy": 251, "water": 512, "tips": 1, "nodes": 61, "dead": False, "agent": agent}
    old = {"type": "world", "tick": trial.FIRST-15, "plants": [plant], "hash": "before",
           "sun_phase": 117, "dark_guard": {"events": []}}
    event = {"id": 12, "kind": "growth", "node": 378, "nodes_before": 61, "nodes_after": 61,
             "energy": 251, "water": 512, "energy_cost": 8, "water_cost": 5, "stress": 0,
             "denied": False, "invalid": False, "before": {"supported": True, "death_step": 0},
             "after": {"supported": True, "death_step": 0}}
    bid = {"type": "bid", "tick": trial.FIRST, "id": 12, "tip_index": 378, "priority": 32767, "action": 2,
           "x": 47, "y": 193, "depth": 9, "maximum_depth": 9, "tissue": 1, "tip_flags": 1}
    control = {**copy.deepcopy(old), "tick": trial.FIRST, "sun_phase": 118, "hash": "e0b8351f",
               "dark_guard": {"events": [event]}}
    control["plants"][0].update(energy=243, water=507, tips=0, agent={"decisions": 11, "finish": 1})
    deferred = {**copy.deepcopy(control), "hash": "deferred", "dawn_finish": trial.metadata(1, trial.FIRST, 378)}
    deferred["plants"] = [copy.deepcopy(plant)]
    return [old, bid, control], [{**copy.deepcopy(old), "dawn_finish": trial.metadata()}, copy.deepcopy(bid), deferred]


class DawnTests(unittest.TestCase):
    def test_fixed_scope(self):
        calls = trial.commands()
        self.assertEqual(len(calls), 24)
        self.assertEqual(len({p for p, _ in calls}), 24)
        self.assertEqual(sum(p.endswith(".gz") for p, _ in calls), 8)
        self.assertEqual(sum(c[0] == "bin/replay" for _, c in calls), 16)
        self.assertEqual(trial.FRAMES, (66075, 68340, 69120, 245760))
        for p, c in calls:
            self.assertEqual(c.count("--dawn-finish"), int("/defer." in p))
            self.assertEqual(c[c.index("--wet-germination-after")+1], "46080")
            self.assertNotIn("bin/seed-attempts", c)

    def test_exact_prefix_and_target_delta(self):
        control, deferred = fixture()
        original = copy.deepcopy((control, deferred))
        self.assertEqual(trial.check_prefix(control, deferred)["matching_raw_records"], 2)
        self.assertEqual((control, deferred), original)
        vetoes, receipts = trial.check_refusals(deferred, "defer")
        self.assertEqual(vetoes, {(trial.FIRST, 12)})
        self.assertEqual(len(receipts), 1)
        self.assertEqual(trial.check_refusals(control, "control"), (set(), []))

    def test_prefix_corruption_fails(self):
        for defect in ("when", "energy", "water", "tips", "memory", "other", "guard", "extra", "missing"):
            control, deferred = fixture()
            row = deferred[-1]
            if defect == "when": row["tick"] += 15
            elif defect in ("energy", "water", "tips"): row["plants"][0][defect] += 1
            elif defect == "memory": row["plants"][0]["agent"]["decisions"] += 1
            elif defect == "other": row["plants"].append({"id": 99})
            elif defect == "guard": row["dark_guard"]["events"][0]["denied"] = True
            elif defect == "extra": row["unexpected"] = 1
            else: deferred.pop()
            with self.subTest(defect=defect), self.assertRaises(RuntimeError):
                trial.check_prefix(control, deferred)

    def test_wrong_or_missing_receipt_fails(self):
        for defect in ("id", "cost", "tip", "energy", "hits", "receipt", "bid", "ordinary-denial"):
            _, rows = fixture()
            event = rows[-1]["dark_guard"]["events"][0]
            if defect == "id": event["id"] = 13
            elif defect == "cost": event["energy_cost"] = 7
            elif defect == "tip": rows[-2]["x"] = 48
            elif defect == "energy": rows[-1]["plants"][0]["energy"] -= 8
            elif defect == "hits": rows[-1]["dawn_finish"]["hits"] += 1
            elif defect == "receipt": del rows[-1]["dawn_finish"]
            elif defect == "bid": del rows[-2]
            else: event["denied"] = True
            with self.subTest(defect=defect), self.assertRaises(RuntimeError):
                trial.check_refusals(rows, "defer")

    def test_retry_compaction_end_inclusive_and_release(self):
        _, rows = fixture()
        bid, row = copy.deepcopy(rows[-2:])
        bid.update(tick=trial.LAST, tip_index=300)
        row.update(tick=trial.LAST, sun_phase=12, dawn_finish=trial.metadata(2, trial.LAST, 300))
        row["dark_guard"]["events"][0]["node"] = 300
        rows += [bid, row]
        released = copy.deepcopy(row)
        released.update(tick=trial.LAST+15)
        released["dark_guard"]["events"][0]["energy"] -= 8
        rows += [{**bid, "tick": trial.LAST+15}, released]
        vetoes, _ = trial.check_refusals(rows, "defer")
        self.assertEqual(vetoes, {(trial.FIRST, 12), (trial.LAST, 12)})
        rows[-1]["dawn_finish"]["hits"] += 1
        with self.assertRaises(RuntimeError): trial.check_refusals(rows, "defer")

    def test_ordinary_denial_is_not_experimental(self):
        _, rows = fixture()
        bid, row = copy.deepcopy(rows[-2:])
        bid["tick"] += 15
        row["tick"] += 15
        row["dark_guard"]["events"][0]["denied"] = True
        rows += [bid, row]
        vetoes, _ = trial.check_refusals(rows, "defer")
        self.assertEqual(vetoes, {(trial.FIRST, 12)})

    def test_control_cannot_be_selected(self):
        _, rows = fixture()
        with self.assertRaises(RuntimeError): trial.check_refusals(rows, "control")

    def test_analysis_only_finish_never_runs_native(self):
        with mock.patch.object(trial, "check_capture", side_effect=RuntimeError("stop")), \
                mock.patch.object(trial.experiment, "command_run") as run:
            with self.assertRaises(RuntimeError): trial.finish(Path("/missing-dawn-fixture"))
            run.assert_not_called()

    def test_partial_analysis_reuses_only_matching_derived_census(self):
        path = mock.Mock()
        path.exists.return_value = True
        worlds = [{"tick": 0}, {"tick": 15}]
        with mock.patch.object(trial.gap.guard, "write_accounting") as write, \
                mock.patch.object(trial.gap, "read_trace", return_value=iter(worlds)):
            trial.derived_census(path, worlds, True)
            write.assert_not_called()
        with mock.patch.object(trial.gap.guard, "write_accounting") as write, \
                mock.patch.object(trial.gap, "read_trace", return_value=iter([{"tick": 0}])):
            with self.assertRaises(RuntimeError):
                trial.derived_census(path, worlds, True)
            write.assert_not_called()

    def test_fresh_derived_census_written_once_and_checked(self):
        path = mock.Mock()
        path.exists.return_value = False
        worlds = [{"tick": 0}]
        with mock.patch.object(trial.gap.guard, "write_accounting") as write, \
                mock.patch.object(trial.gap, "read_trace", return_value=iter(worlds)):
            trial.derived_census(path, worlds, True)
            write.assert_called_once_with(path, worlds)

    def test_native_cli_invalid_scope_and_duplicates(self):
        if BUILD is None: self.skipTest("native CLI requires --build")
        for tool in ("inspect", "replay"):
            base = [str(BUILD/("toy-factory-garden-"+tool)), "-", "rainfed", "adaptive", "123", "--ticks", "15"]
            for extra in (["--dawn-finish", "none"], ["--dawn-finish", "defer"],
                          ["--dawn-finish", "defer", "--dawn-finish", "defer"]):
                result = subprocess.run([*base, *extra], capture_output=True)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    args, remaining = parser.parse_known_args()
    BUILD = args.build.resolve() if args.build else None
    unittest.main(argv=[__file__, *remaining])
