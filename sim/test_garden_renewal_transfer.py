#!/usr/bin/env python3
"""Fixed transfer design, exact contrasts and native boundary bookkeeping."""
from concurrent.futures import ThreadPoolExecutor
import copy
import json
from dataclasses import FrozenInstanceError
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zlib

import garden_renewal_transfer as run
import test_garden_renewal_training as fixtures


def groups(deltas=(160, 480, 160, 400)):
    return {cell: {"control": {"key": [1, len(run.conditions(cell)), 1000]},
                   "candidate": {"key": [1, len(run.conditions(cell)), 1000+delta]},
                   "pairs": [{"condition": k} for k, *_ in run.conditions(cell)]}
            for cell, delta in zip(run.CELLS, deltas, strict=True)}


def as_fraction(value):
    return Fraction(value["numerator"], value["denominator"])


class DesignTests(unittest.TestCase):
    def test_partition_reuse_and_exact_budget(self):
        self.assertEqual([len(run.conditions(c)) for c in run.CELLS], [16, 16, 8, 8])
        self.assertEqual([c for c in run.CELLS if run.reused(c)], ["tt", "rr"])
        all_cases = [(m.name, seed, p) for m in run.MODELS for c in run.CELLS for _, _, seed, p in run.conditions(c)]
        self.assertEqual(len(all_cases), 240)
        self.assertEqual(len(set(all_cases)), 240)
        self.assertEqual(len(run.events()), 300)
        self.assertEqual(sum(e["kind"] == "trial" for e in run.events()), 240)
        self.assertEqual(sum(e["kind"] == "frame" for e in run.events()), 60)
        self.assertEqual(sum(k.startswith("ledgers/") for k in run.copies()), 120)
        self.assertTrue(all("mutate" not in n for n in run.copies()))
        for function in (run.seeds, run.patches, run.conditions, run.reused):
            with self.assertRaises(RuntimeError):
                function("wrong")

    def test_immutable_models_and_detached_settings(self):
        with self.assertRaises(FrozenInstanceError):
            run.MODELS[0].crc = "other"
        settings = run.settings()
        settings["models"][0]["crc"] = "other"
        settings["budget"]["native_processes"] = 0
        settings["cells"]["tt"]["seeds"].clear()
        self.assertEqual(run.MODELS[0].crc, "dc5e849d")
        self.assertEqual(run.settings()["budget"]["native_processes"], 300)
        self.assertEqual(len(run.seeds("tt")), 8)

    def test_fixed_final_and_original_provenance(self):
        baseline = {"rule": run.previous.RULE, "settings": run.previous.settings(), "replicas": {}}
        for m in run.MODELS:
            arm = baseline["replicas"].setdefault(m.replica, {"arms": {}})["arms"].setdefault(m.arm,
                {"search": {"champions": ["initial"]*4, "candidates": []}, "review": [{} for _ in range(4)]})
            arm["search"]["champions"][m.generation] = m.candidate
            arm["search"]["candidates"].append({"id": m.candidate, "model_crc32": m.crc})
            arm["review"][m.generation] = {"champion": m.candidate}
        run.validate_models(baseline)
        bad = copy.deepcopy(baseline)
        bad["replicas"]["r2"]["arms"]["renewal"]["search"]["champions"][3] = "g2-c2"
        with self.assertRaises(RuntimeError):
            run.validate_models(bad)
        bad = copy.deepcopy(baseline)
        bad["replicas"]["r1"]["arms"]["v2"]["search"]["candidates"][0]["model_crc32"] = "other"
        with self.assertRaises(RuntimeError):
            run.validate_models(bad)

    def test_reused_source_paths_cover_diagonals_and_original_generation_zero(self):
        copied = run.copies()
        for m in run.MODELS:
            for cell in run.CELLS:
                for key, *_ in run.conditions(cell):
                    dest = run.ledger(m, cell, key)
                    self.assertEqual(dest in copied, run.reused(cell))
                    if cell == "rr":
                        self.assertIn(f"/review/g{m.generation}.", copied[dest])
                    if cell == "tt":
                        self.assertIn(f"/search/{m.candidate}.", copied[dest])

    def test_fixed_gallery_all_models_cells_schedules_and_reuse(self):
        plan = run.frame_plan()
        self.assertEqual(len(plan), 40)
        self.assertEqual(sum(c == "rr" for _, c, *_ in plan), 10)
        frames = [{"id": run.identity(m, c, k)} for m, c, k, *_ in plan]
        self.assertEqual([len(row) for row in run.frame_rows({"frames": frames})], [5]*8)
        self.assertTrue(all(seed == run.seeds(c)[0] for _, c, _, _, seed, _ in plan))
        frames[0], frames[1] = frames[1], frames[0]
        with self.assertRaises(RuntimeError):
            run.frame_rows({"frames": frames})


class ContrastTests(unittest.TestCase):
    def test_unequal_sizes_do_not_create_effect_from_equal_means(self):
        result = run.contrasts(groups((160, 160, 80, 80)))
        self.assertEqual([as_fraction(v) for v in result["means"].values()], [10]*4)
        self.assertEqual(as_fraction(result["interaction"]), 0)
        self.assertTrue(all(as_fraction(v) == 0 for v in result["schedule_shifts"].values()))

    def test_schedule_world_and_interaction_signs(self):
        result = run.contrasts(groups())
        self.assertEqual([as_fraction(result["means"][c]) for c in run.CELLS], [10, 30, 20, 50])
        self.assertEqual([as_fraction(v) for v in result["schedule_shifts"].values()], [20, 30])
        self.assertEqual([as_fraction(v) for v in result["world_set_shifts"].values()], [10, 20])
        self.assertEqual(as_fraction(result["interaction"]), 10)
        self.assertTrue(result["terminal_prefixes_equal"])

    def test_exact_fraction_and_survival_flag(self):
        inputs = groups((1, 2, 3, 4))
        inputs["tr"]["candidate"]["key"][0] = -1
        result = run.contrasts(inputs)
        self.assertEqual(as_fraction(result["means"]["tt"]), Fraction(1,16))
        self.assertEqual(as_fraction(result["interaction"]), Fraction(1,16))
        self.assertFalse(result["terminal_prefixes_equal"])
        inputs.pop("rr")
        with self.assertRaises(RuntimeError):
            run.contrasts(inputs)

    def test_real_score_views_and_omissions_drop_seed_from_both_cells(self):
        sterile, steady = fixtures.world("sterile"), fixtures.world("steady")
        comparisons = {}
        for cell in run.CELLS:
            a = {k: copy.deepcopy(sterile) for k, *_ in run.conditions(cell)}
            b = {k: copy.deepcopy(steady if seed != run.seeds(cell)[0] else sterile)
                 for k, _, seed, _ in run.conditions(cell)}
            comparisons[cell] = run.scoring.comparison(a, b, run.seeds(cell), patches=run.patches(cell))
        original = copy.deepcopy(comparisons)
        axes = run.axis_diagnostics(comparisons)
        self.assertEqual(comparisons, original)
        for view in run.scoring.ARMS:
            a = axes[view]
            self.assertEqual(len(a["leave_one_world_seed_out"]), 12)
            omitted = a["leave_one_world_seed_out"][run.previous.TRAIN[0]]["means"]
            full = a["full"]["means"]
            self.assertGreater(as_fraction(omitted["tt"]), as_fraction(full["tt"]))
            self.assertEqual(omitted["tt"], omitted["tr"])
            self.assertEqual(omitted["rt"], full["rt"])
            self.assertEqual(omitted["rr"], full["rr"])
            self.assertTrue(all(as_fraction(s["shift"]) == 0 for group in a["per_world_schedule_shifts"].values() for s in group.values()))


class NativeBoundaryTests(unittest.TestCase):
    def timing(self):
        root = Path("/frozen-transfer")
        return {"command_root": str(root), "calls": [{**e, "command": run.native_command(root,e)[0],
                    "artifact": run.native_command(root,e)[1], "seconds": 0} for e in run.events()]}

    def test_exact_commands_budget_duplicates_and_unauthorized_calls(self):
        good = self.timing()
        run.check_budget(good)
        for failure in ("missing", "extra", "duplicate", "intervention", "mutator", "schedule", "target"):
            bad = copy.deepcopy(good)
            if failure == "missing": bad["calls"].pop()
            elif failure == "extra": bad["calls"].append(bad["calls"][0])
            elif failure == "duplicate": bad["calls"][1] = bad["calls"][0]
            elif failure == "intervention": bad["calls"][0]["command"].append("--founder-exit")
            elif failure == "mutator": bad["calls"][0]["command"][0] = "garden-model-mutate"
            elif failure == "schedule": bad["calls"][0]["command"][4] = "0xe4d65e6f"
            else: bad["calls"][0]["artifact"] = "elsewhere.json"
            with self.subTest(failure=failure), self.assertRaises(RuntimeError):
                run.check_budget(bad)

    def test_explicit_schedule_model_and_followup_routing(self):
        root = Path("/frozen-transfer")
        for e in run.events():
            command, target = run.native_command(root,e)
            patch_seed = run.patches(e["cell"])[e["condition"].split(".")[0]]
            self.assertEqual(command[1], str(root/"models"/f"{e['model']}.tgm"))
            if e["kind"] == "trial":
                self.assertEqual(command[4], "0x"+patch_seed)
                self.assertEqual(command[-2:], [str(run.pilot.START),str(run.pilot.END)])
            else:
                self.assertEqual(command[command.index("--disturbance-seed")+1], str(int(patch_seed,16)))
                self.assertEqual(command[command.index("--ticks")+1], str(run.pilot.STOP))
            self.assertIn(e["model"], target)

    def test_native_repeat_is_byte_exact(self):
        m, cell = run.MODELS[0], "tr"
        key = run.conditions(cell)[0][0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a,b = (root/run.ledger(m,cell,key,r) for r in (False,True))
            a.parent.mkdir(parents=True)
            a.write_text('{"ok":true}\n')
            b.write_bytes(a.read_bytes())
            run.check_repeat(root,m,cell,key)
            b.write_text('{"ok": true}\n')
            with self.assertRaises(RuntimeError): run.check_repeat(root,m,cell,key)

    def test_frames_check_reuse_identity_repeat_and_png(self):
        m = run.MODELS[0]
        raw = bytes(run.pilot.gallery.FRAME_BYTES)
        for cell in ("tt", "rr"):
            key, schedule, seed, pseed = run.conditions(cell)[0]
            checkpoint = {"tick":run.pilot.STOP,"hash":"01234567","living":1,"births":0,"deaths":0,"nodes":1,"seeds":0}
            replay = {"schema_version":1,"scenario":"rainfed-crowded","seed":seed,"policy":"neural-no-night-growth",
                      "model_crc32":m.crc,"node_capacity":512,"leaf_policy":"selective","seed_dispersal":"wide-v1",
                      "water_uptake":"headroom-v1","leaf_environment":"leaf-maintenance-v1","disturbance_protocol":"patch-death-v1",
                      "disturbance_seed":pseed,"seed_bank":0,"framebuffer_crc32":f"{zlib.crc32(raw):08x}",
                      **{k:v for k,v in checkpoint.items() if k != "seeds"}}
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root/"frames").mkdir()
                trial = root/run.ledger(m,cell,key)
                trial.parent.mkdir(parents=True)
                run.experiment.write_json(trial,{"checkpoints":[checkpoint]})
                stem = root/"frames"/run.identity(m,cell,key)
                files = {s:Path(str(stem)+s) for s in (".rgb565",".repeat.rgb565",".replay.json",".repeat.json",".png")}
                for failure in (None,"seed","model_crc32","disturbance_seed","tick","repeat","png"):
                    value = copy.deepcopy(replay)
                    if failure in ("seed","model_crc32","disturbance_seed"): value[failure] = "ffffffff"
                    if failure == "tick": value["tick"] -= 15
                    files[".rgb565"].write_bytes(raw)
                    files[".repeat.rgb565"].write_bytes(raw if failure != "repeat" else b"\x01"+raw[1:])
                    for suffix in (".replay.json",".repeat.json"): files[suffix].write_text(json.dumps(value))
                    run.pilot.gallery.write_png(files[".png"],240,240,run.pilot.gallery.rgb565be_to_rgb888(raw))
                    if failure == "png": files[".png"].write_bytes(b"wrong")
                    if failure is None:
                        frame = run.checked_frame(root,m,cell,key,schedule,seed,pseed)
                        self.assertEqual(frame["reused"],cell == "rr")
                        self.assertEqual(frame["model_crc32"],m.crc)
                    else:
                        with self.subTest(cell=cell,failure=failure),self.assertRaises(RuntimeError):
                            run.checked_frame(root,m,cell,key,schedule,seed,pseed)

    def test_collector_two_private_model_jobs_only_execute_declared_events(self):
        def native(command, target):
            value = {"ok": True}
            run.experiment.write_json(target,value)
            if "--framebuffer" in command:
                Path(command[-1]).write_bytes(bytes(run.pilot.gallery.FRAME_BYTES))
            return value,0
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/"frames").mkdir()
            for model in run.MODELS[:2]:
                for cell in run.CELLS:
                    (root/"ledgers"/model.name/cell).mkdir(parents=True)
            with patch.object(run.pilot,"run_json",side_effect=native), patch.object(run,"checked_trial"), \
                 patch.object(run,"checked_frame"), patch("builtins.print"):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    futures = [executor.submit(run.collect_model,root,m) for m in run.MODELS[:2]]
                    rows = [f.result() for f in futures]
            for m, calls in zip(run.MODELS,rows):
                expected = [e for e in run.events() if e["model"] == m.name]
                self.assertEqual(len(calls),60)
                self.assertEqual([{k:r[k] for k in expected[0]} for r in calls],expected)
            self.assertTrue(set(r["artifact"] for r in rows[0]).isdisjoint(r["artifact"] for r in rows[1]))

    def test_existing_output_and_incomplete_manifest_are_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(run.pilot,"run_json") as native:
            root = Path(directory)
            with self.assertRaises(RuntimeError): run.collect(root/"baseline",root)
            run.experiment.write_json(root/"manifest.json",{"rule":run.RULE,"status":"failed"})
            with self.assertRaises(RuntimeError): run.verify(root)
            native.assert_not_called()


if __name__ == "__main__":
    unittest.main()
