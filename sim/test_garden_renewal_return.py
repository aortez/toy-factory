#!/usr/bin/env python3
"""Frozen-final provenance, exact reuse/call budget and old-panel return checks."""
from concurrent.futures import ThreadPoolExecutor
import copy
from dataclasses import FrozenInstanceError
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_renewal_return as run
import test_garden_renewal_training as fixtures


def inputs():
    old = {"rule": run.transfer.RULE, "settings": run.transfer.settings(), "models": {}}
    wide = {"rule": run.coverage.RULE, "settings": run.coverage.settings(), "replicas": {}}
    for model in run.MODELS:
        arm = wide["replicas"].setdefault(model.replica, {"arms": {}})["arms"].setdefault(model.arm,
            {"search": {"champions": ["initial"]*4, "candidates": []}, "review": [{} for _ in range(4)]})
        arm["search"]["champions"][model.generation] = model.candidate
        arm["search"]["candidates"].append({"id": model.candidate, "model_crc32": model.crc, "model_sha256": model.crc*8})
        worlds = {k: {**copy.deepcopy(fixtures.world("steady")), "terminal_species": [1], "terminal_families": [1]} for k, *_ in
                  run.mixed.conditions(run.coverage.REVIEW, dict(run.coverage.previous.REVIEW_PATCHES))}
        arm["review"][model.generation] = {"champion": model.candidate, "worlds": worlds}
        if not model.new:
            old["models"][model.control_name] = {"model_crc32": model.crc, "model_sha256": model.crc*8}
    return old, wide


class DesignTests(unittest.TestCase):
    def test_exact_cross_and_new_vs_reused_partition(self):
        self.assertEqual([len(run.conditions(c)) for c in run.CELLS], [16,16,8,8])
        cases = {(m.name, seed, p) for m in run.MODELS for c in run.CELLS for _, _, seed, p in run.conditions(c)}
        self.assertEqual(len(cases), 240)
        self.assertEqual(len(run.events()), 224)
        self.assertEqual(sum(e["kind"] == "trial" for e in run.events()), 192)
        self.assertEqual(sum(e["kind"] == "frame" for e in run.events()), 32)
        self.assertEqual({e["model"] for e in run.events()}, {"r1-w", "r2-w"})
        copied = run.copies()
        self.assertEqual(sum(k.startswith("ledgers/") and ".repeat." not in k for k in copied), 144)
        self.assertEqual(sum(k.startswith("ledgers/") and ".repeat." in k for k in copied), 72)
        self.assertFalse(any("mutate" in k for k in copied))
        self.assertEqual(run.BUDGET["native_processes"], 224)

    def test_control_rename_reuse_and_wide_model_mapping(self):
        copied = run.copies()
        for model in run.MODELS:
            bundle, source = copied[f"models/{model.name}.tgm"]
            self.assertEqual(bundle, "coverage" if model.new else "transfer")
            if model.new:
                self.assertEqual(source, f"{model.source}/search/{model.candidate}.tgm")
            for cell in run.CELLS:
                for key, *_ in run.conditions(cell):
                    dest = run.ledger(model, cell, key)
                    self.assertEqual(dest in copied, not model.new)
                    if not model.new:
                        self.assertEqual(copied[dest], ["transfer", f"ledgers/{model.control_name}/{cell}/{key}.json"])

    def test_final_provenance_rejects_wrong_generation_crc_sha_and_contract(self):
        good = inputs()
        run.validate_models(*good)
        for failure in ("generation", "crc", "sha", "review", "contract"):
            old, wide = copy.deepcopy(good)
            arm = wide["replicas"]["r2"]["arms"]["wide"]
            if failure == "generation": arm["search"]["champions"][3] = "g2-c2"
            elif failure == "crc": arm["search"]["candidates"][0]["model_crc32"] = "ffffffff"
            elif failure == "sha": old["models"]["r1-b"]["model_sha256"] = "changed"
            elif failure == "review": arm["review"][3]["champion"] = "initial"
            else: old["settings"]["budget"]["native_processes"] = 0
            with self.subTest(failure=failure), self.assertRaises(RuntimeError):
                run.validate_models(old, wide)

    def test_immutable_models_settings_and_old_protocols(self):
        old = (run.transfer.settings(), run.coverage.settings())
        with self.assertRaises(FrozenInstanceError): run.MODELS[2].candidate = "initial"
        settings = run.settings()
        settings["models"][0]["crc"] = "changed"
        settings["cells"]["rr"]["seeds"].clear()
        settings["budget"]["native_processes"] = 0
        settings["inputs"]["transfer"] = "changed"
        self.assertEqual(run.MODELS[0].crc, "dc5e849d")
        self.assertEqual(len(run.seeds("rr")), 4)
        self.assertEqual(run.settings()["budget"]["native_processes"], 224)
        self.assertEqual(old, (run.transfer.settings(), run.coverage.settings()))

    def test_fixed_gallery_and_reuse_are_model_based_not_cell_based(self):
        plan = run.frame_plan()
        self.assertEqual(len(plan), 40)
        self.assertEqual(sum(not m.new for m, *_ in plan), 24)
        self.assertTrue(all(seed == run.seeds(cell)[0] for _, cell, _, _, seed, _ in plan))
        rows = [{"id": run.identity(m, c, k)} for m,c,k,*_ in plan]
        self.assertEqual([len(r) for r in run.frame_rows({"frames": rows})], [5]*8)
        for m,c,k,label,seed,pseed in plan:
            with patch.object(run.transfer,"checked_frame",return_value={"id":run.identity(m,c,k),"reused":c == "rr"}):
                self.assertEqual(run.checked_frame(Path("/unused"),m,c,k,label,seed,pseed)["reused"],not m.new)
        rows[0], rows[1] = rows[1], rows[0]
        with self.assertRaises(RuntimeError): run.frame_rows({"frames": rows})

    def test_fresh_context_keeps_final_identity_denominator_and_pairs(self):
        old, wide = inputs()
        before = copy.deepcopy(wide)
        context = run.fresh_context(wide)
        self.assertEqual(wide, before)
        self.assertEqual(set(context["models"]), {m.name for m in run.MODELS})
        self.assertEqual(set(context["comparisons"]), {n for n, *_ in run.PAIRS})
        self.assertEqual(len(run.conditions("rr")), 8)
        for values in context["models"].values():
            for view in values["views"].values():
                self.assertEqual(view["condition_count"], 16)
                mean = view["mean_credit_ticks"]
                self.assertEqual(Fraction(mean["numerator"],mean["denominator"]),Fraction(view["aggregate"]["key"][2],16))
        for pair in context["comparisons"].values():
            for view in pair.values():
                self.assertEqual(len(view["overall"]["pairs"]),16)
                self.assertEqual(set(view["leave_one_world_seed_out"]),set(run.coverage.REVIEW))
                self.assertTrue(all(len(v["pairs"]) == 14 for v in view["leave_one_world_seed_out"].values()))

    def test_same_means_do_not_create_cross_effect_with_unequal_sizes(self):
        groups = {c:{"control":{"key":[1,len(run.conditions(c)),0]},
                     "candidate":{"key":[1,len(run.conditions(c)),10*len(run.conditions(c))]},
                     "pairs":[{"condition":k} for k,*_ in run.conditions(c)]} for c in run.CELLS}
        contrast = run.transfer.contrasts(groups)
        self.assertEqual(set((v["numerator"],v["denominator"]) for v in contrast["means"].values()),{(10,1)})
        self.assertEqual(contrast["interaction"],{"numerator":0,"denominator":1})


class BoundaryTests(unittest.TestCase):
    def timing(self):
        root = Path("/frozen-return")
        return {"command_root":str(root),"calls":[{**e,"command":run.native_command(root,e)[0],
                "artifact":run.native_command(root,e)[1],"seconds":0} for e in run.events()]}

    def test_exact_budget_rejects_duplicates_controls_and_command_tampering(self):
        timing = self.timing()
        run.check_budget(timing)
        for failure in ("missing","extra","duplicate","control","intervention","mutator","schedule","target"):
            bad = copy.deepcopy(timing)
            if failure == "missing": bad["calls"].pop()
            elif failure == "extra": bad["calls"].append(bad["calls"][0])
            elif failure == "duplicate": bad["calls"][1] = bad["calls"][0]
            elif failure == "control": bad["calls"][0]["model"] = "r1-n"
            elif failure == "intervention": bad["calls"][0]["command"].append("--founder-exit")
            elif failure == "mutator": bad["calls"][0]["command"][0] = "garden-model-mutate"
            elif failure == "schedule": bad["calls"][0]["command"][4] = "0x12345678"
            else: bad["calls"][0]["artifact"] = "wrong.json"
            with self.subTest(failure=failure),self.assertRaises(RuntimeError): run.check_budget(bad)

    def test_commands_route_each_schedule_and_followup(self):
        for event in run.events():
            command,target = run.native_command(Path("/frozen"),event)
            pseed = run.patches(event["cell"])[event["condition"].split(".")[0]]
            self.assertEqual(command[1],f"/frozen/models/{event['model']}.tgm")
            self.assertIn(event["model"],target)
            if event["kind"] == "trial":
                self.assertEqual(command[4],"0x"+pseed)
                self.assertEqual(command[-2:],[str(run.pilot.START),str(run.pilot.END)])
            else:
                self.assertEqual(command[command.index("--disturbance-seed")+1],str(int(pseed,16)))
                self.assertEqual(command[command.index("--ticks")+1],str(run.pilot.STOP))
        event = {**run.events()[0],"model":"original"}
        with self.assertRaises(RuntimeError): run.native_command(Path("/frozen"),event)

    def test_private_parallel_jobs_only_execute_224_declared_calls(self):
        def native(command,target):
            run.experiment.write_json(target,{"ok":True})
            if "--framebuffer" in command: Path(command[-1]).write_bytes(bytes(run.pilot.gallery.FRAME_BYTES))
            return {"ok":True},0
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/"frames").mkdir()
            models = [m for m in run.MODELS if m.new]
            for model in models:
                for cell in run.CELLS: (root/"ledgers"/model.name/cell).mkdir(parents=True)
            with patch.object(run.pilot,"run_json",side_effect=native),patch.object(run,"checked_trial"), \
                 patch.object(run,"checked_frame"),patch("builtins.print"):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    futures = [executor.submit(run.collect_model,root,m) for m in models]
                    rows = [f.result() for f in futures]
            self.assertEqual([len(r) for r in rows],[112,112])
            self.assertTrue(set(r["artifact"] for r in rows[0]).isdisjoint(r["artifact"] for r in rows[1]))
            run.check_budget({"command_root":str(root),"calls":rows[0]+rows[1]})
            with self.assertRaises(RuntimeError): run.collect_model(root,run.MODELS[0])

    def test_input_hash_and_binary_agreement_reject_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            priors = {n:{"artifacts":{}} for n in run.INPUTS}
            for dest,(name,src) in run.copies().items():
                p = root/dest
                p.parent.mkdir(parents=True,exist_ok=True)
                p.write_bytes(src.encode())
                priors[name]["artifacts"][src] = run.experiment.digest(p)
            for replica in run.coverage.REPLICAS:
                for arm in run.coverage.ARMS:
                    for name in ("garden-persistence-trial","garden-replay"):
                        priors["coverage"]["artifacts"][f"replicas/{replica}/arms/{arm}/bin/{name}"] = run.experiment.digest(root/f"bin/{name}")
            for name in ("native-source.tar.gz","CMakeCache.txt"):
                priors["coverage"]["artifacts"][f"input/{name}"] = run.experiment.digest(root/f"input/{name}")
            for name,manifest in priors.items(): run.experiment.write_json(root/f"input/{name}-manifest.json",manifest)
            pinned = {name:run.experiment.digest(root/f"input/{name}-manifest.json") for name in priors}
            with patch.object(run,"INPUTS",pinned):
                run.experiment.write_json(root/"input/settings.json",run.settings())
                run.check_inputs(root)
                for target in ("models/r1-w.tgm","ledgers/r1-n/rr/review-1.abf7af73.json",
                               "input/coverage-manifest.json","bin/garden-replay","input/settings.json"):
                    p = root/target
                    original = p.read_bytes()
                    p.write_bytes(b"changed")
                    with self.subTest(target=target),self.assertRaises((RuntimeError,ValueError)): run.check_inputs(root)
                    p.write_bytes(original)
                run.check_inputs(root)

    def test_incomplete_or_existing_output_never_executes(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(run.pilot,"run_json") as native:
            root = Path(directory)
            with self.assertRaises(RuntimeError): run.collect({n:root/n for n in run.INPUTS},root)
            run.experiment.write_json(root/"manifest.json",{"rule":run.RULE,"status":"failed"})
            with self.assertRaises(RuntimeError): run.verify(root)
            native.assert_not_called()


if __name__ == "__main__":
    unittest.main()
