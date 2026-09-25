#!/usr/bin/env python3
"""Reserve threshold/deadline, exact old-arm inventory and independent receipts."""
import argparse
import copy
from pathlib import Path
import subprocess
import unittest
from unittest import mock

import garden_renewal_dawn_reserve as trial
import test_garden_renewal_dawn_finish as old_tests

BUILD = None


def fixture():
    _, rows = old_tests.fixture()
    for row in rows:
        if row["type"] == "world":
            old = row["dawn_finish"]
            row["dawn_finish"] = trial.metadata(old["hits"], old["last_tick"], old["last_node"])
    return rows


def append_attempt(rows, tick, energy, *, paid=False, denied=False, node=378):
    bid, row = copy.deepcopy(rows[-2:])
    bid.update(tick=tick, tip_index=node)
    row.update(tick=tick, sun_phase=(64+tick//15)%256)
    event = row["dark_guard"]["events"][0]
    event.update(energy=energy, water=512, node=node, denied=denied)
    plant = row["plants"][0]
    plant.update(energy=energy, water=512, tips=1)
    if paid:
        plant.update(energy=energy-8, water=507, tips=0)
        plant["agent"]["decisions"] += 1
        plant["agent"]["finish"] += 1
    state = row["dawn_finish"]
    if trial.FIRST <= tick < trial.NOON and not state["handoff_tick"] and not denied:
        if tick > trial.LAST and energy >= 16:
            state.update(handoff_tick=tick, handoff_energy=energy, handoff_node=node)
        else:
            state.update(hits=state["hits"]+1, last_tick=tick, last_node=node)
    rows += [bid, row]


def prefix_fixture():
    control, deferred = old_tests.fixture()
    a, b = copy.deepcopy(control), copy.deepcopy(deferred)
    for rows, arm in ((a, "defer"), (b, "reserve")):
        rows[0].update(tick=68370, sun_phase=14)
        rows[0]["plants"][0].update(energy=6, stress=7)
        rows[1].update(tick=trial.DIVERGENCE)
        rows[2].update(tick=trial.DIVERGENCE, sun_phase=15)
        event = rows[2]["dark_guard"]["events"][0]
        event.update(energy=9, stress=7)
        rows[2]["plants"][0].update(energy=1 if arm == "defer" else 9, stress=7)
        rows[0]["dawn_finish"] = (trial.parent.metadata(10, 66225, 378) if arm == "defer"
                                  else trial.metadata(10, 66225, 378))
        rows[2]["dawn_finish"] = (trial.parent.metadata(10, 66225, 378) if arm == "defer"
                                  else trial.metadata(11, trial.DIVERGENCE, 378))
    return a, b


class ReserveTests(unittest.TestCase):
    def test_fixed_inventory_old_arms_first(self):
        calls = trial.commands()
        self.assertEqual(len(calls), 36)
        self.assertEqual(calls[:24], trial.parent.commands())
        self.assertEqual(len({p for p, _ in calls}), 36)
        self.assertEqual(sum(p.endswith(".gz") for p, _ in calls), 12)
        self.assertEqual(sum(c[0] == "bin/replay" for _, c in calls), 24)
        self.assertEqual(trial.FRAMES, (66075, 68340, 69120, 245760))
        for target, command in calls[24:]:
            self.assertIn("/reserve.", target)
            self.assertEqual(command[command.index("--dawn-finish")+1], "reserve")
            self.assertEqual(command[command.index("--wet-germination-after")+1], "46080")

    def test_old_endpoint_then_threshold_and_handoff(self):
        rows = fixture()
        append_attempt(rows, trial.LAST, 251)
        append_attempt(rows, trial.LAST+15, 15, node=300)
        append_attempt(rows, trial.LAST+30, 16, paid=True, node=300)
        original, audit = copy.deepcopy(rows), {}
        vetoes, receipts = trial.check_refusals(rows, "reserve", audit=audit)
        self.assertEqual(rows, original)
        self.assertEqual(vetoes, {(trial.FIRST, 12), (trial.LAST, 12), (trial.LAST+15, 12)})
        self.assertEqual(len(receipts), 3)
        self.assertEqual(audit["handoff"]["remaining_energy"], 8)
        self.assertEqual(audit["handoff"]["tick"], trial.LAST+30)
        self.assertEqual(audit["final_receipt"]["handoff_node"], 300)

    def test_fifteen_cannot_commit_and_sixteen_must_commit(self):
        for energy, paid in ((15, True), (16, False)):
            rows = fixture()
            append_attempt(rows, trial.LAST+15, energy, paid=paid)
            with self.subTest(energy=energy), self.assertRaises(RuntimeError):
                trial.check_refusals(rows, "reserve")

    def test_exclusive_noon_cutoff_does_not_record_handoff(self):
        rows, audit = fixture(), {}
        append_attempt(rows, trial.NOON-15, 15)
        append_attempt(rows, trial.NOON, 15, paid=True)
        vetoes, _ = trial.check_refusals(rows, "reserve", audit=audit)
        self.assertEqual(vetoes, {(trial.FIRST, 12), (trial.NOON-15, 12)})
        self.assertIsNone(audit["handoff"])
        self.assertEqual(audit["disposition"], "no-handoff-before-cutoff")
        rows[-1]["dawn_finish"]["hits"] += 1
        with self.assertRaises(RuntimeError): trial.check_refusals(rows, "reserve")

    def test_ordinary_denial_has_precedence(self):
        rows = fixture()
        append_attempt(rows, trial.LAST+15, 16, denied=True)
        vetoes, _ = trial.check_refusals(rows, "reserve")
        self.assertEqual(vetoes, {(trial.FIRST, 12)})

    def test_missing_or_corrupted_receipt(self):
        for defect in ("id", "cost", "tip", "energy", "hits", "receipt", "bid", "ordinary-denial", "duplicate"):
            rows = fixture()
            event = rows[-1]["dark_guard"]["events"][0]
            if defect == "id": event["id"] = 13
            elif defect == "cost": event["energy_cost"] = 7
            elif defect == "tip": rows[-2]["x"] = 48
            elif defect == "energy": rows[-1]["plants"][0]["energy"] -= 8
            elif defect == "hits": rows[-1]["dawn_finish"]["hits"] += 1
            elif defect == "receipt": del rows[-1]["dawn_finish"]
            elif defect == "bid": del rows[-2]
            elif defect == "ordinary-denial": event["denied"] = True
            else: rows[-1]["dark_guard"]["events"].append(copy.deepcopy(event))
            with self.subTest(defect=defect), self.assertRaises(RuntimeError):
                trial.check_refusals(rows, "reserve")

    def test_wrong_handoff_diagnostic_fails(self):
        for key in ("handoff_tick", "handoff_energy", "handoff_node", "hits", "cutoff_tick", "reserve"):
            rows = fixture()
            append_attempt(rows, trial.LAST+15, 16, paid=True)
            rows[-1]["dawn_finish"][key] += 1
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                trial.check_refusals(rows, "reserve")

    def test_common_prefix_preserves_neighbors_and_guard(self):
        a, b = prefix_fixture()
        original = copy.deepcopy((a, b))
        self.assertEqual(trial.check_prefix(a, b)["matching_raw_records"], 2)
        self.assertEqual((a, b), original)
        for defect in ("when", "energy", "water", "tips", "memory", "other", "guard", "extra", "missing"):
            a, b = prefix_fixture()
            row = b[-1]
            if defect == "when": row["tick"] += 15
            elif defect in ("energy", "water", "tips"): row["plants"][0][defect] += 1
            elif defect == "memory": row["plants"][0]["agent"]["decisions"] += 1
            elif defect == "other": row["plants"].append({"id": 99})
            elif defect == "guard": row["dark_guard"]["events"][0]["denied"] = True
            elif defect == "extra": row["unexpected"] = 1
            else: b.pop()
            with self.subTest(defect=defect), self.assertRaises(RuntimeError):
                trial.check_prefix(a, b)

    def test_historical_inventory_includes_every_frame_and_trace(self):
        for arm in trial.parent.ARMS:
            self.assertEqual(len(trial.historical_files(arm)), 10)
            self.assertEqual(sum(p.endswith(".rgb565") for p in trial.historical_files(arm)), 4)

    def test_analysis_only_finish_never_calls_native(self):
        with mock.patch.object(trial, "check_capture", side_effect=RuntimeError("stop")), \
                mock.patch.object(trial.experiment, "command_run") as run:
            with self.assertRaises(RuntimeError): trial.finish(Path("/missing-reserve-fixture"))
            run.assert_not_called()

    def test_checker_cannot_apply_to_an_old_arm(self):
        with self.assertRaises(RuntimeError): trial.check_refusals(fixture(), "defer")

    def test_native_cli_invalid_scope_and_duplicates(self):
        if BUILD is None: self.skipTest("native CLI requires --build")
        for tool in ("inspect", "replay"):
            base = [str(BUILD/("toy-factory-garden-"+tool)), "-", "rainfed", "adaptive", "123", "--ticks", "15"]
            for extra in (["--dawn-finish", "reserve"], ["--dawn-finish", "invalid"],
                          ["--dawn-finish", "reserve", "--dawn-finish", "reserve"],
                          ["--dawn-finish", "defer", "--dawn-finish", "reserve"]):
                result = subprocess.run([*base, *extra], capture_output=True)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    args, remaining = parser.parse_known_args()
    BUILD = args.build.resolve() if args.build else None
    unittest.main(argv=[__file__, *remaining])
