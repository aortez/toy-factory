#!/usr/bin/env python3
"""Startup accounting, censored history checks and immutable diagnostic contracts."""
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zlib

import garden_renewal_startup as audit


def fixture(death=None):
    plant = {"id": 1, "parent": 0, "species": "flower", "generation": 0, "column": 3,
             "dead": False, "energy": 128, "water": 32, "stress": 0, "flags": 0,
             "nodes": 4, "roots": 2, "tips": 3, "leaves": 1, "active_leaves": 1,
             "vigor": 1, "energy_income": 0, "water_income": 0, "reproduction_cooldown": 0,
             "root_cells": [[3, 0, 0, 100], [3, 1, 1, 100]],
             "leaf": {"observations": 0, "proposals": 0, "renewals": 0, "restored": 0, "worn": 0, "conditions": [240]},
             "agent": dict.fromkeys(("decisions", "wait", "extend", "finish", "root_extend", "shoot_extend"), 0)}
    rows = []
    for tick in range(0, 121, 15):
        if tick and not plant["dead"]:
            plant.update(energy_income=1, water_income=1)
            plant["energy"] += 1
            plant["water"] += 1
            if tick % 60 == 0:
                plant["energy"] -= 1
                plant["water"] -= 1
        if tick in (15, 45):
            action, tissue = (0, 0) if tick == 15 else (1, 1)
            bid = {"type": "bid", "tick": tick, "id": 1, "tip_audit_version": 1,
                   "tip_index": 0, "depth": 1, "maximum_depth": 5, "tip_flags": 1,
                   "tissue": tissue, "x": 40, "y": 120, "priority": 10, "action": action,
                   "original_priority": 10, "original_action": action, "probe_original_action": action,
                   "probe": "no-night-growth-v1", "sun_phase": 64 + tick // 15,
                   "energy": plant["energy"], "water": plant["water"],
                   "candidates": [{"flags": 3} for _ in range(5 if tissue == 0 else 3)]}
            rows.append(bid)
            if tick == 15:
                rows.append({**bid, "tip_index": 1, "action": 2, "original_action": 2, "probe_original_action": 2})
            plant["agent"]["decisions"] += 1
            plant["agent"]["wait" if tick == 15 else "extend"] += 1
            plant["agent"].update({"last_" + k: bid[k] for k in ("priority", "action", "tissue", "x", "y")})
            if tick == 45:
                plant["nodes"] += 1
                plant["roots"] += 1
                plant["root_cells"].append([3, 2, 2, 100])
                plant["agent"]["root_extend"] += 1
                plant["energy"] -= 8
                plant["water"] -= 5
        if tick == 30:
            rows.append({"type": "leaf-bid", "tick": tick, "id": 1, "action": 1})
            plant["leaf"].update(observations=1, proposals=1, renewals=1, restored=15, conditions=[255])
            plant["energy"] -= 9
            plant["water"] -= 5
        if tick == death:
            plant.update(dead=True, flags=3, stress=8, tips=0, energy=0, water=0,
                         energy_income=0, water_income=0)
        rows.append({"type": "world", "tick": tick, "hash": f"{tick:08x}", "sun_phase": 64 + tick // 15,
                     "sun_strength": 255, "living": int(not plant["dead"]), "births": 0,
                     "deaths": int(plant["dead"]), "nodes": plant["nodes"], "seeds": [],
                     "plants": [copy.deepcopy(plant)], "node_capacity": 512,
                     "leaf_environment": "leaf-maintenance-v1", "leaf_policy": "selective"})
    trial = {"lineages": [{"id": 1, "parent": 0, "birth_tick": 0, "death_tick": death,
                            "environmental_death": False, "species": 0, "generation": 0, "column": 3}],
             "checkpoints": [{**{k: rows[0][k] for k in ("tick", "hash", "nodes", "living", "births", "deaths")}, "seeds": 0}]}
    return rows, trial


def analyze(rows, trial):
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "trace.gz"
        with gzip.open(path, "wt") as stream:
            for row in rows:
                stream.write(json.dumps(row) + "\n")
        with patch.object(audit, "STOP", 120), patch.object(audit, "DAY", 60):
            return audit.analyze_trace(path, [trial, copy.deepcopy(trial)])


class StartupTests(unittest.TestCase):
    def test_live_resources_winner_ties_leaf_renewal_and_trace_immutability(self):
        rows, trial = fixture()
        before = copy.deepcopy((rows, trial))
        result, samples = analyze(rows, trial)
        self.assertEqual(result["counts"]["world_samples"], 9)
        self.assertEqual(result["counts"]["checked_live_steps"], 8)
        self.assertEqual(result["counts"]["committed_decisions"], 2)
        self.assertEqual(result["resource_totals"]["energy_growth"], 8)
        self.assertEqual(result["resource_totals"]["energy_renewal"], 9)
        self.assertEqual(result["tip_audit"]["totals"]["successful_extensions"], 1)
        record = result["lineages"][0]
        self.assertEqual(record["decisions"][0]["winner"]["action"], 0)
        self.assertEqual(record["marks"]["first_root_extension"]["tick"], 45)
        self.assertEqual(result["saved_checkpoints_checked"], [1, 1])
        self.assertTrue(record["alive_at_end"])
        self.assertEqual((rows, trial), before)
        self.assertEqual(samples[120]["plants"][0]["energy"], 117)

    def test_terminal_clears_are_not_interpreted_as_spending(self):
        result, _ = analyze(*fixture(death=90))
        p = result["lineages"][0]
        self.assertEqual(p["death_shortage"], "energy")
        self.assertEqual(p["marks"]["last_living"]["tick"], 75)
        self.assertEqual(result["counts"]["checked_live_steps"], 5)
        self.assertEqual(result["counts"]["terminal_steps_not_reconstructed"], 1)
        self.assertEqual(result["resource_totals"]["energy_income"], 5)
        self.assertFalse(p["alive_at_end"])

    def test_history_censors_only_after_horizon(self):
        rows, trial = fixture()
        trial["lineages"][0].update(death_tick=135, environmental_death=True)
        result, _ = analyze(rows, trial)
        self.assertIsNone(result["lineages"][0]["death_tick"])
        trial["lineages"][0]["death_tick"] = 120
        with self.assertRaisesRegex(RuntimeError, "mortality"):
            analyze(rows, trial)

    def test_terminal_at_horizon_is_not_censored(self):
        result, _ = analyze(*fixture(death=120))
        self.assertEqual(result["lineages"][0]["death_tick"], 120)

    def test_history_rejects_different_species_birth_death_and_hash(self):
        for field, value in (("species", 1), ("birth_tick", 15), ("id", 2), ("column", 4)):
            with self.subTest(field=field):
                rows, trial = fixture()
                trial["lineages"][0][field] = value
                with self.assertRaises(RuntimeError):
                    analyze(rows, trial)
        rows, trial = fixture()
        trial["checkpoints"][0]["hash"] = "different"
        with self.assertRaisesRegex(RuntimeError, "checkpoint"):
            analyze(rows, trial)

    def test_missing_trailing_duplicated_world_or_bid_rejected(self):
        rows, trial = fixture()
        variants = [rows[:-1], rows + [rows[-1]], [r for r in rows if r["tick"] != 60],
                    rows + [{"type": "bid", "id": 1, "tick": 135}]]
        for altered in variants:
            with self.assertRaises(RuntimeError):
                analyze(altered, trial)

    def test_changed_rules_resources_and_conditions_rejected(self):
        for field, value in (("node_capacity", 256), ("growth_policy", "neural"), ("sun_phase", 99)):
            rows, trial = fixture()
            rows[-1][field] = value
            with self.assertRaises(RuntimeError):
                analyze(rows, trial)
        for field in ("energy", "water"):
            rows, trial = fixture()
            rows[-1]["plants"][0][field] += 1
            with self.assertRaisesRegex(RuntimeError, "budget"):
                analyze(rows, trial)
        rows, trial = fixture()
        rows[-1]["plants"][0]["leaf"]["conditions"][0] -= 1
        with self.assertRaisesRegex(RuntimeError, "condition"):
            analyze(rows, trial)

    def test_uncommitted_or_mismatched_bid_rejected(self):
        for change in ("override", "winner", "orphan", "stores"):
            rows, trial = fixture()
            if change == "override":
                rows[1]["original_action"] = 2
            elif change == "winner":
                rows[2].update(priority=11, original_priority=11)
            elif change == "orphan":
                rows[1]["id"] = 2
            else:
                rows[2]["energy"] += 1
            with self.assertRaises(RuntimeError):
                analyze(rows, trial)

    def test_leaf_bid_must_reconcile_with_telemetry(self):
        rows, trial = fixture()
        for row in rows:
            if row["type"] == "leaf-bid":
                row["action"] = 0
        with self.assertRaisesRegex(RuntimeError, "leaf observation/proposal"):
            analyze(rows, trial)

    def test_command_panel_has_no_training_and_complete_repeats(self):
        commands = audit.commands()
        self.assertEqual(len(commands), 30)
        self.assertEqual(len({name for name, _ in commands}), 30)
        counts = {name: sum(c[0] == name for _, c in commands) for name in ("bin/garden-inspect", "bin/garden-replay")}
        self.assertEqual(counts, {"bin/garden-inspect": 6, "bin/garden-replay": 24})
        for target, cmd in commands:
            self.assertIn("0x0d983a80", cmd)
            self.assertIn("0x05d87ca0", cmd)
            self.assertEqual(cmd[cmd.index("--leaf-policy") + 1], "selective")
            if target.endswith(".gz"):
                self.assertEqual(cmd[-1], "30720")

    def test_copy_panel_is_fixed_models_two_histories_and_no_mutator(self):
        files = audit.copies()
        self.assertEqual(len([n for n in files if n.endswith(".tgm")]), 3)
        self.assertEqual(len([n for n in files if n.endswith(".json")]), 6)
        self.assertEqual({n for n in files if n.startswith("bin/")}, {"bin/garden-inspect", "bin/garden-replay"})
        self.assertEqual([m.crc for m in audit.MODELS], ["dc5e849d", "01b9d94a", "c9ea07fd"])

    def test_untraced_frame_identity_counts_and_crc(self):
        sample = {k: 0 for k in ("living", "nodes", "births", "deaths", "sun_phase", "sun_strength",
                                  "rain_rate", "rain_deposited", "rain_runoff", "moisture")}
        sample.update(hash="abc", plants=[], seeds=[])
        raw = bytes(audit.gallery.FRAME_BYTES)
        result = {"schema_version": 1, "scenario": "rainfed-crowded", "seed": audit.SEED,
                  "policy": audit.experiment.NIGHT_POLICY, "model_crc32": audit.MODELS[0].crc,
                  "node_capacity": 512, "seed_dispersal": "wide-v1", "water_uptake": "headroom-v1",
                  "leaf_policy": "selective", "leaf_environment": "leaf-maintenance-v1",
                  "disturbance_protocol": "patch-death-v1", "disturbance_seed": audit.PATCH,
                  "tick": 960, "plant_slots": 0, "seed_bank": 0,
                  "framebuffer_crc32": f"{zlib.crc32(raw):08x}",
                  **{k: v for k, v in sample.items() if k not in ("plants", "seeds")}}
        audit.check_frame(result, sample, audit.MODELS[0], 960, raw)
        for key, value in (("hash", "bad"), ("model_crc32", "bad"), ("living", 1), ("seed_bank", 1)):
            with self.assertRaises(RuntimeError):
                audit.check_frame({**result, key: value}, sample, audit.MODELS[0], 960, raw)
        with self.assertRaises(RuntimeError):
            audit.check_frame(result, sample, audit.MODELS[0], 960, raw[:-1])

    def test_sealed_capture_rejects_missing_changed_or_extra_call(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            commands = [("trace.gz", ["bin/inspect"]),
                        ("frame.json", ["bin/replay", "--framebuffer", "frame.raw"])]
            for name in ("trace.gz", "frame.json", "frame.raw"):
                (root / name).write_bytes(b"fixture")
            audit.experiment.write_json(root / "started.json", {"frozen": {}})
            capture = {"rule": audit.RULE, "settings": audit.settings(),
                       "calls": [{"artifact": t, "command": c} for t, c in commands],
                       "artifacts": {p.name: audit.experiment.digest(p) for p in root.iterdir()}}
            audit.experiment.write_json(root / "capture.json", capture)
            with patch.object(audit, "commands", return_value=commands), patch.object(audit, "check_inputs"):
                self.assertEqual(audit.check_capture(root), capture)
                for mode in ("missing", "changed", "extra_call"):
                    altered = copy.deepcopy(capture)
                    if mode == "missing":
                        del altered["artifacts"]["frame.raw"]
                    elif mode == "changed":
                        altered["artifacts"]["frame.raw"] = "0" * 64
                    else:
                        altered["calls"].append(altered["calls"][0])
                    (root / "capture.json").write_text(json.dumps(altered))
                    with self.assertRaises(RuntimeError):
                        audit.check_capture(root)

    def test_recovery_does_not_execute_native_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "failure.json").write_text('{"error":"legacy metadata"}')
            (root / "capture.json").write_text('{}')
            audit.experiment.write_json(root / "started.json", {"sources": {audit.PROTOCOL: "abc"}})
            frame = {"id": "fixture", "tick": 960, "png": "frame.png", "framebuffer": "frame.raw"}
            (root / "frame.raw").write_bytes(bytes(audit.gallery.FRAME_BYTES))
            sources = {audit.PROTOCOL: "abc"}
            capture = {"capture_seconds": None, "calls": [], "timing_note": "unavailable"}
            with patch.object(audit, "check_capture", return_value=capture), \
                 patch.object(audit.experiment, "source_files", return_value=sources), \
                 patch.object(audit.experiment, "snapshot_sources"), \
                 patch.object(audit, "analyze", return_value={"frames": [frame]}), \
                 patch.object(audit, "FRAME_TICKS", (960,)), \
                 patch.object(audit, "verify") as verify, \
                 patch.object(audit.experiment, "command_run", side_effect=AssertionError("No native commands")):
                audit.finish(root, recovered=True)
                verify.assert_called_once_with(root)
                self.assertEqual(audit.experiment.read_json(root / "manifest.json")["analysis_sources"], sources)
                self.assertEqual(audit.experiment.read_json(root / "timings.json")["recovery_native_calls"], 0)
                with self.assertRaisesRegex(RuntimeError, "completed"):
                    audit.finish(root, recovered=True)


if __name__ == "__main__":
    unittest.main()
