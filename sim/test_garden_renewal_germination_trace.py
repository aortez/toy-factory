#!/usr/bin/env python3
"""Frozen germination scope, ordered receipt validation and host replay CLI parity."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import garden_renewal_germination_trace as trace


def fixture(start=0):
    parent = {"id": 1, "nodes": 4, "column": 0, "dead": False}
    seed = {"parent": 1, "age": 7, "generation": 1, "column": 14, "species": 0, "blockers": 5}
    old = {"type": "world", "tick": start, "hash": "old", "nodes": 4, "plants": [parent], "seeds": [seed],
           "births": 0, "seeds_created": 1, "seeds_expired": 0}
    world = {**old, "tick": start+15, "hash": "new", "seeds": [{**seed, "age": 8, "blockers": 4}]}
    masks = [4 | (32 if c < 3 else 0) for c in range(28)]
    sites = {w["tick"]: {**w, "type": "seed-sites", "sun_phase": 1, "sun_strength": 20,
                        "sites": [[m, 20, 20] for m in masks]} for w in (old, world)}
    rows = [{"type": "seed-step", "tick": w["tick"], "hash": w["hash"], "nodes": 4, "plants": 1,
             "seeds": 1, "births": 0, "expired": 0, "created": 1, "sun_phase": 1, "sun_strength": 20,
             "stages": [], "sites_before": [], "attempts": []} for w in (old, world)]
    rows[1].update(stages=[[4, 1, 1]]*5, sites_before=masks,
                   attempts=[{**seed, "age": 8, "blockers": 4, "child": 0, "nodes": 4, "plants": 1,
                              "moisture": 20, "light": 20, "outcome": 0, "sites": masks}])
    header = {**trace.expected_header("control"), "from": start, "end": start+15}
    return [header, *rows], {w["tick"]: w for w in (old, world)}, sites, header


def lifetime(outcome="expired"):
    seed = {"parent": 7, "birth_tick": 0, "column": 3, "generation": 2,
            "end_tick": 3840 if outcome == "expired" else 120, "outcome": outcome,
            "child_id": None if outcome == "expired" else 10}
    visits = []
    for age in range(1, seed["end_tick"]//15+1):
        mask = 2 if age % 2 else 4
        visits.append({"parent": 7, "tick": age*15, "column": 3, "generation": 2, "age": age,
            "moisture": 0 if mask == 2 else 20, "light": 100 if mask == 2 else 20,
            "sun_strength": 100, "blockers": mask | int(age < 8), "outcome": 0, "child": 0,
            "post_site": [mask, 20, 20], "post_seed_mask": mask | int(age < 8)})
    if outcome == "expired":
        visits[-1].update(outcome=1, blockers=0, moisture=0, light=0, post_seed_mask=None)
    else:
        visits[-1].update(outcome=2, blockers=0, moisture=20, light=100, child=10,
                          post_site=[34, 8, 100], post_seed_mask=None)
    return visits, seed


class TraceTests(unittest.TestCase):
    def test_frozen_window_targets_and_four_calls(self):
        self.assertEqual((trace.START, trace.END), (49545, 57360))
        self.assertEqual(trace.FOCAL, ((7, 49560, 3, 2), (7, 53400, 4, 2), (2, 57240, 5, 1)))
        calls = trace.commands()
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[0][1], calls[1][1])
        self.assertEqual(calls[2][1], calls[3][1])
        for path, cmd in calls:
            self.assertEqual(cmd[5:8], ["0", "49545", "57360"])
            self.assertEqual("--gap-at" in cmd, "gap." in path)
            self.assertNotIn("--framebuffer", cmd)

    def test_valid_trace_and_state_preservation(self):
        args = fixture()
        original = copy.deepcopy(args)
        result, _ = trace.validate_trace(*args)
        self.assertEqual((result["checkpoints"], result["totals"]["mature_checks"]), (2, 1))
        self.assertEqual(args, original)

    def test_hash_header_order_origin_and_counts_rejected(self):
        for defect in ("hash", "sun", "header", "missing", "duplicate", "origin", "nodes", "counter"):
            rows, worlds, sites, header = copy.deepcopy(fixture())
            header = copy.deepcopy(header)
            if defect == "hash": rows[-1]["hash"] = "bad"
            elif defect == "sun": rows[-1]["sun_strength"] += 1
            elif defect == "header": rows[0]["model_crc32"] = "bad"
            elif defect == "missing": rows.pop()
            elif defect == "duplicate": rows.append(rows[-1])
            elif defect == "origin": rows[1]["stages"] = [[4, 1, 1]]*5
            elif defect == "nodes": rows[-1]["nodes"] += 1
            else: sites[15]["seeds_expired"] += 1
            with self.subTest(defect=defect), self.assertRaises(RuntimeError):
                trace.validate_trace(rows, worlds, sites, header)

    def test_ordered_visit_age_resource_and_stage_rejected(self):
        for defect in ("age", "column", "moisture", "light", "blockers", "stage", "missing"):
            rows, worlds, sites, header = copy.deepcopy(fixture())
            a = rows[-1]["attempts"][0]
            if defect == "stage": rows[-1]["stages"][1] = [3, 1, 1]
            elif defect == "missing": rows[-1]["attempts"] = []
            elif defect in ("moisture", "light"): a[defect] = 255 if defect == "light" else 0
            else: a[defect] += 1
            with self.subTest(defect=defect), self.assertRaises(RuntimeError):
                trace.validate_trace(rows, worlds, sites, header)

    def test_export_must_match_and_precede_origin(self):
        rows, worlds, sites, header = fixture(30)
        event = {"type": "gap", "tick": 15, "id": 1}
        trace.validate_trace([rows[0], event, *rows[1:]], worlds, sites, header, event)
        for events in ([], [event, event], [{**event, "id": 2}]):
            with self.assertRaises(RuntimeError):
                trace.validate_trace([rows[0], *events, *rows[1:]], worlds, sites, header, event)
        with self.assertRaises(RuntimeError):
            trace.validate_trace([rows[0], {**event, "tick": 30}, *rows[1:]], worlds, sites, header, {**event, "tick": 30})

    def test_expiry_is_not_a_resource_check(self):
        visits, seed = lifetime()
        result = trace.summarize_seed(visits, seed)
        self.assertEqual(result["mature_checks"], 248)
        self.assertEqual(result["mature_masks"], {"2": 124, "4": 124})
        self.assertEqual(result["joint_resource_pass_checks"], 0)
        self.assertEqual(sum(result["dormant_masks"].values()), 7)

    def test_birth_post_site_is_not_a_failed_attempt(self):
        result = trace.summarize_seed(*lifetime("germinated"))
        self.assertEqual(result["mature_masks"], {"0": 1})
        self.assertEqual(result["actual_to_post_site_masks"], {"0->34": 1})
        self.assertEqual(result["waiting_seed_post_mask_differences"], 0)

    def test_focal_lifetime_identity_outcome_and_order_required(self):
        for defect in ("missing", "order", "age", "parent", "child", "outcome"):
            visits, seed = lifetime()
            if defect == "missing": visits.pop(2)
            elif defect == "order": visits[1], visits[2] = visits[2], visits[1]
            elif defect in ("age", "parent"): visits[2][defect] += 1
            else: visits[-1][defect] += 1
            with self.subTest(defect=defect), self.assertRaises(RuntimeError):
                trace.summarize_seed(visits, seed)

    def test_runs_count_inclusive_samples_not_elapsed_gaps(self):
        result = trace.runs([{"tick": t, "pass": t != 30} for t in (15, 30, 45, 60)], lambda r: r["pass"])
        self.assertEqual(result, [{"first_tick": 15, "last_tick": 15, "checks": 1},
                                  {"first_tick": 45, "last_tick": 60, "checks": 2}])


def cli_checks(build):
    if not (build/"toy-factory-garden-seed-attempts").exists():
        return
    with tempfile.TemporaryDirectory(prefix="germination-cli-") as temporary:
        model = Path(temporary)/"fixture.tgm"
        subprocess.run([str(build/"toy-factory-garden-water-audit-test"), str(model)], check=True, timeout=60)
        base = [str(model), "rainfed-crowded", trace.experiment.NIGHT_POLICY, "123"]
        route = ["--focal-model", str(model), "--focal-founder", "5"]

        def run(tool, args):
            return subprocess.run([str(build/f"toy-factory-garden-{tool}"), *base, *args],
                                  capture_output=True, text=True, timeout=60)

        def records(tool, args):
            r = run(tool, args)
            trace.require(r.returncode == 0, r.stderr)
            return [json.loads(line) for line in r.stdout.splitlines()]

        plain = records("inspect", ["--leaf-policy", "selective", "--ecology", "--ticks", "4005"])
        before = next(r for r in plain if r["type"] == "world" and r["tick"] == 3840)
        adult = next(p["id"] for p in before["plants"] if not p["dead"] and p["age_ecology_ticks"] >= 256)
        gap_args = ["--gap-at", "3840", "--gap-lineage", str(adult)]
        for extras, start in ((route, 0), (route, 3855), (gap_args, 3855), (route+gap_args, 3855)):
            references = []
            event = None
            for flag, kind in (("--ecology", "world"), ("--seed-sites", "seed-sites")):
                data = records("inspect", ["--leaf-policy", "selective", flag, "--ticks", "4005", *extras])
                references.append({r["tick"]: r for r in data if r["type"] == kind and r["tick"] >= start})
                if gap_args[0] in extras:
                    event = next(r for r in data if r["type"] == "gap")
            data = records("seed-attempts", ["0", str(start), "4005", *extras])
            result, _ = trace.validate_trace(data, *references, data[0], event)
            assert result["checkpoints"] == (4005-start)//15+1
            if gap_args[0] not in extras:
                expected = {r["tick"]: r["hash"] for r in plain if r["type"] == "world"}
                assert all(r["hash"] == expected[r["tick"]] for r in data[1:])
        malformed = [["--unknown", "1"], ["--focal-model"], ["--focal-model", ""],
            ["--focal-model", str(model)], ["--focal-founder", "5"], route+route,
            ["--focal-founder", "0", "--focal-model", str(model)],
            ["--gap-at", "3840"], ["--gap-lineage", "1"], gap_args+gap_args,
            ["--gap-at", "4020", "--gap-lineage", "1"], ["--gap-at", "3841", "--gap-lineage", "1"],
            ["--gap-at", "0", "--gap-lineage", "1"], ["--gap-at", "-15", "--gap-lineage", "1"],
            ["--gap-at", "4294967296", "--gap-lineage", "1"]]
        for extras in malformed:
            assert run("seed-attempts", ["0", "3855", "4005", *extras]).returncode == 2
        for extras in (route, gap_args):
            assert run("seed-attempts", ["123", "3855", "4005", *extras]).returncode == 2
        for extras in (["--focal-model", str(model), "--focal-founder", "999"],
                       ["--gap-at", "3840", "--gap-lineage", "999"]):
            assert run("seed-attempts", ["0", "3855", "4005", *extras]).returncode == 1
        base[2] = trace.audit.recruitment.policy.RESERVE
        assert run("seed-attempts", ["0", "3855", "4005", *route]).returncode == 2
    print("Germination CLI: self-routing neutrality, named export parity and invalid requests verified", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    args, remaining = parser.parse_known_args()
    result = unittest.main(argv=[sys.argv[0], *remaining], exit=False).result
    if not result.wasSuccessful():
        raise SystemExit(1)
    if args.build:
        cli_checks(args.build.resolve())
