#!/usr/bin/env python3
"""Wet-rule isolation, boundary/receipt validation, native CLI parity and build guards."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import garden_renewal_wet_germination as trial
from test_garden_renewal_controlled_gap import boundary
from test_garden_renewal_germination_trace import fixture


def activated(kind="world"):
    before, exported, event = boundary(kind)
    exported["seeds"][0]["blockers"] = 4
    after = copy.deepcopy(exported)
    after.update(hash="rule-on", germination_rule=trial.NATIVE)
    after["seeds"][0]["blockers"] = 0
    if kind == "seed-sites":
        exported["sites"][10] = [4, 42, 24]
        after["sites"][10] = [0, 42, 24]
    activation = {"type": "germination-rule", "rule": trial.NATIVE, "tick": trial.AT,
                  "before_hash": exported["hash"], "after_hash": after["hash"]}
    return before, exported, event, after, activation


class WetTests(unittest.TestCase):
    def test_fixed_twenty_eight_call_inventory(self):
        calls = trial.commands()
        self.assertEqual(len(calls), 28)
        self.assertEqual(sum("bin/seed-attempts" == c[0] for _, c in calls), 4)
        self.assertEqual(sum("bin/replay" == c[0] for _, c in calls), 16)
        self.assertEqual((trial.AT, trial.STOP, trial.LATE), (46080, 245760, 184320))
        for path, cmd in calls:
            self.assertEqual("--wet-germination-after" in cmd, "optional." in path)
            self.assertEqual(cmd[cmd.index("--gap-lineage")+1], "1")

    def test_activation_only_changes_rule_hash_and_light_masks(self):
        for kind in ("world", "seed-sites"):
            _, exported, _, after, event = activated(kind)
            original = copy.deepcopy((exported, after, event))
            trial.activation(exported, after, event)
            self.assertEqual((exported, after, event), original)

    def test_activation_rejects_resource_time_ancestry_or_other_gate_changes(self):
        for defect in ("hash", "rule", "tick", "water", "parent", "gate", "extra"):
            _, exported, _, after, event = activated("seed-sites")
            if defect == "hash": after["hash"] = exported["hash"]
            elif defect == "rule": after["germination_rule"] = "unknown"
            elif defect == "tick": event["tick"] += 15
            elif defect == "water": after["sites"][10][1] += 1
            elif defect == "parent": after["seeds"][0]["parent"] += 1
            elif defect == "gate": after["seeds"][0]["blockers"] = 2
            else: after["unrelated"] = 1
            with self.subTest(defect=defect), self.assertRaises(RuntimeError):
                trial.activation(exported, after, event)

    def test_boundaries_do_not_advance_ecology_twice(self):
        before, exported, event, after, rule = activated()
        rows, actual_export, actual_rule = trial.split_census([before, event, exported, rule, after], "optional")
        self.assertEqual(rows, [before])
        self.assertEqual(actual_export["after"], exported)
        self.assertEqual(actual_rule["after"], after)

    def test_missing_reordered_or_unrequested_activation_fails(self):
        before, exported, event, after, rule = activated()
        for rows, arm in (([before, event, exported], "optional"),
                ([before, event, exported, rule, after], "required"),
                ([before, rule, after], "optional"),
                ([before, event, exported, rule, after, rule, after], "optional"),
                ([before, event, exported, rule], "optional")):
            with self.assertRaises(RuntimeError): trial.split_census(rows, arm)

    def test_optional_light_requires_explicit_matching_rule(self):
        for value, enabled in (({}, True), ({"germination_rule": trial.NATIVE}, False),
                               ({"germination_rule": "unknown"}, True)):
            with self.assertRaises(RuntimeError): trial.check_rule(value, enabled)

    def test_old_validator_remains_strict_and_optional_mode_still_checks_water(self):
        rows, worlds, sites, _ = fixture()
        row, old, world, s = rows[-1], worlds[0], worlds[15], sites[15]
        trial.audit.check_step(row, old, world, s, 512)
        row = copy.deepcopy(row)
        row["sites_before"] = [m & ~4 for m in row["sites_before"]]
        a = row["attempts"][0]
        a.update(blockers=2, moisture=0, sites=[m & ~4 for m in a["sites"]])
        a["sites"][14] = 2
        row["sites_before"][14] = 2
        trial.audit.check_step(row, old, world, s, 512, light_required=False)
        with self.assertRaises(RuntimeError): trial.audit.check_step(row, old, world, s, 512)
        a["moisture"] = 12
        with self.assertRaises(RuntimeError): trial.audit.check_step(row, old, world, s, 512, light_required=False)

    def test_occupancy_uses_after_state_and_half_open_interval(self):
        worlds = [{"tick": t, "plants": [1]*8, "seeds": [1]*8, "living": 8, "nodes": 512} for t in (0, 15, 30)]
        after = {**worlds[1], "plants": [1]*7, "living": 7}
        with mock.patch.multiple(trial, AT=15, STOP=30, LATE=15):
            result = trial.occupancy(worlds, after)
        self.assertEqual(result["whole"]["steps"], 2)
        self.assertEqual(result["whole"]["plant_slot_steps"], 15)
        self.assertEqual(result["post_export"]["plant_full_steps"], 0)
        self.assertEqual(result["late"]["seed_full_steps"], 1)


def parse_fixture(rows, kind, start=0):
    ordinary, boundaries, before = {}, [], None
    iterator = iter(rows)
    for row in iterator:
        if row["type"] in ("gap", "germination-rule"):
            if row["tick"] < start:
                boundaries.append({"before": None, "event": row, "after": None})
                continue
            after = next(iterator)
            boundaries.append({"before": before, "event": row, "after": after})
            before = after
        elif row["type"] == kind:
            ordinary[row["tick"]] = row
            before = row
    return ordinary, boundaries


def cli_checks(build):
    if not (build/"toy-factory-garden-wet-germination-test").exists():
        return
    with tempfile.TemporaryDirectory(prefix="wet-germination-cli-") as temporary:
        model = Path(temporary)/"fixture.tgm"
        subprocess.run([str(build/"toy-factory-garden-water-audit-test"), str(model)], check=True, timeout=60)
        base = [str(model), "rainfed-crowded", trial.experiment.NIGHT_POLICY, "123"]
        control = ["--focal-model", str(model), "--focal-founder", "5", "--leaf-policy", "selective"]
        end, at = 7680, 3840

        def run(tool, args):
            return subprocess.run([str(build/f"toy-factory-garden-{tool}"), *base, *args], capture_output=True, text=True, timeout=60)

        def records(tool, args):
            r = run(tool, args)
            trial.require(r.returncode == 0, r.stderr)
            return [json.loads(l) for l in r.stdout.splitlines()]

        initial = records("inspect", [*control, "--ecology", "--ticks", str(at)])
        before = [r for r in initial if r["type"] == "world"][-1]
        target = next(p["id"] for p in before["plants"] if not p["dead"] and p["age_ecology_ticks"] >= 256)
        options = ["--gap-at", str(at), "--gap-lineage", str(target)]
        wet = ["--wet-germination-after", str(at)]
        for arm in trial.ARMS:
            extras = options + (wet if arm == "optional" else [])
            wrows = records("inspect", [*control, *extras, "--ecology", "--ticks", str(end)])
            srows = records("inspect", [*control, *extras, "--seed-sites", "--ticks", str(end)])
            worlds, wb = parse_fixture(wrows, "world")
            sites, sb = parse_fixture(srows, "seed-sites")
            rows = records("seed-attempts", ["0", "0", str(end), *control[:-2], *extras])
            # The fixture model and world deliberately differ from the experimental inputs.
            with mock.patch.object(trial.trace, "expected_header", return_value=rows[0]), mock.patch.object(trial, "AT", at):
                result = trial.seed_receipts(rows, worlds, sites, list(zip(wb, sb, strict=True)), arm, stop=end)
                for bad in (rows[:-1], rows+[rows[-1]], [r for r in rows if r["type"] != "gap"]):
                    try: trial.seed_receipts(bad, worlds, sites, list(zip(wb, sb, strict=True)), arm, stop=end)
                    except RuntimeError: pass
                    else: raise AssertionError("malformed native receipt trace accepted")
            assert result["totals"]["whole"]["steps"] == end//15
            replay = records("replay", [*control, *extras, "--ticks", str(end)])[0]
            assert replay["hash"] == worlds[end]["hash"]
            if arm == "optional":
                trial.activation(wb[1]["before"], wb[1]["after"], wb[1]["event"], at)
                trial.activation(sb[1]["before"], sb[1]["after"], sb[1]["event"], at)
            # Origins before, at, and after the export all keep explicit boundary receipts.
            for start in (at, at+15):
                part = records("seed-attempts", ["0", str(start), str(end), *control[:-2], *extras])
                normal, bs = parse_fixture(part[1:], "seed-step", start)
                assert sorted(normal) == list(range(start, end+1, 15))
                assert normal[start]["stages"] == [] and normal[end]["hash"] == worlds[end]["hash"]
                assert len(bs) == (2 if arm == "optional" else 1)
        for tool in ("inspect", "replay", "seed-attempts"):
            prefix = (["0", "0", str(end), *control[:-2]] if tool == "seed-attempts" else [*control, "--ticks", str(end)])
            for args in (wet, [*options, *wet, *wet], [*options, "--wet-germination-after", "0"],
                         [*options, "--wet-germination-after", "3841"], [*options, "--wet-germination-after", "3855"],
                         ["--gap-at", str(at), *wet], [*options, "--wet-germination-after"]):
                assert run(tool, [*prefix, *args]).returncode == 2
    print("Wet CLI: full receipts, in-window boundaries, replay parity and invalid requests passed", flush=True)


def guards(cc):
    root = trial.experiment.ROOT
    flags = ["-D"+name+"=1" for name in ("TOY_FACTORY_GARDEN_COMBINED_EXPERIMENT", "TOY_FACTORY_GARDEN_WIDE_DISPERSAL",
        "TOY_FACTORY_GARDEN_WATER_HEADROOM", "TOY_FACTORY_GARDEN_LARGE_POOL", "TOY_FACTORY_GARDEN_LEAF_MAINTENANCE",
        "TOY_FACTORY_GARDEN_DARK_GUARD", "TOY_FACTORY_GARDEN_NIGHT_CAPACITY", "TOY_FACTORY_GARDEN_WET_GERMINATION")]
    for mode in ("valid", "device", "no-capacity", "disabled"):
        selected = [f for f in flags if not ((mode == "no-capacity" and "NIGHT_CAPACITY" in f) or
                                           (mode == "disabled" and "WET_GERMINATION" in f))]
        if mode == "device": selected.append("-D__ZEPHYR__=1")
        code = '#include "garden_world.h"\nint main(void) { struct picosystem_garden_world w = {0}; return w.wet_germination_enabled; }\n'
        r = subprocess.run([cc, "-std=c11", "-Werror", "-fsyntax-only", "-I", str(root/"src"), *selected, "-xc", "-"],
                           input=code, capture_output=True, text=True, timeout=30)
        assert (r.returncode == 0) == (mode == "valid"), r.stderr
    helper = root/"scripts/container/host-garden-defaults.sh"
    defaults = subprocess.check_output(
        ["bash", "-eu", "-c", 'source "$1"; printf "%s\\n" "${garden_default_cmake_options[@]}"',
         "garden-defaults", str(helper)], text=True).splitlines()
    assert "-DTOY_FACTORY_GARDEN_WET_GERMINATION=OFF" in defaults
    for name in ("host-build.sh", "host-player-build.sh", "host-profile-build.sh"):
        wrapper = (root/"scripts/container"/name).read_text()
        assert 'source "$app_dir/scripts/container/host-garden-defaults.sh"' in wrapper
        assert '"${garden_default_cmake_options[@]}"' in wrapper
    print("Wet opt-in/device/normal-build guards passed", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    parser.add_argument("--cc", default="cc")
    args, remaining = parser.parse_known_args()
    result = unittest.main(argv=[sys.argv[0], *remaining], exit=False).result
    if not result.wasSuccessful(): raise SystemExit(1)
    guards(args.cc)
    if args.build: cli_checks(args.build.resolve())
