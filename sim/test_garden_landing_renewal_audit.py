#!/usr/bin/env python3
"""Exact lifetime boundaries, seed censoring and frozen renewal accounting."""

import copy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import garden_landing_renewal_audit as audit

DAY, STEP = audit.DAY, audit.STEP


def fixture(specs, extra=(), purchases=None):
    plants = [{"id": i, "parent": parent, "birth_tick": birth, "death_tick": death,
               "environmental_death": False, "column": i, "generation": i - 1,
               "species": 0} for i, parent, birth, death in specs]
    seeds = [{"parent": p["parent"], "birth_tick": (purchases or {}).get(p["id"], p["birth_tick"] - 120),
              "end_tick": p["birth_tick"], "child_id": p["id"], "outcome": "germinated",
              "column": p["column"], "generation": p["generation"], "species": 0,
              "lifetime_ecology_ticks": 8192} for p in plants if p["parent"]]
    for parent, birth in extra:
        end = birth + 8192 * STEP
        seeds.append({"parent": parent, "birth_tick": birth, "end_tick": end if end <= audit.training.STOP else None,
                      "child_id": None, "outcome": "expired" if end <= audit.training.STOP else "pending",
                      "column": 0, "generation": 1, "species": 0, "lifetime_ecology_ticks": 8192})
    for p in plants:
        p["seeds_created"] = p["late_seeds_created"] = sum(s["parent"] == p["id"] for s in seeds)
    audit.descendants.index_records(plants, seeds, 0, audit.training.STOP)
    return {"lineages": plants, "seeds": seeds}


def sampled_occupancy(plants, start, end):
    """Brute-force oracle; no production classification or interval helper."""
    records = {p["id"]: p for p in plants}
    counts = dict.fromkeys(audit.BUCKETS, 0)
    for tick in range(start + STEP, end + STEP, STEP):
        for p in plants:
            if p["birth_tick"] > tick or p["death_tick"] is not None and p["death_tick"] <= tick:
                continue
            due = p["birth_tick"] + DAY
            if p["parent"] == 0:
                key = "founder"
            elif tick < due:
                key = "unconfirmed_descendant"
            else:
                parent = records[p["parent"]]
                parent_due = parent["birth_tick"] + DAY
                if parent["parent"] == 0:
                    key = "founder_child"
                elif parent_due > due or parent["death_tick"] is not None and parent["death_tick"] <= parent_due:
                    key = "unconfirmed_parent_child"
                else:
                    key = "credit_eligible" if tick - due < 32 * DAY else "aged_out_eligible"
            counts[key] += STEP
    return counts


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="landing-renewal-audit-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.input = audit.ROOT / "benchmarks/garden-seasons" / audit.INPUT

    def test_sampled_partition_confirmation_expiry_and_dead_parent_boundaries(self):
        trial = fixture([(1, 0, 0, None), (2, 1, DAY, 3 * DAY),
                         (3, 2, 2 * DAY + 240, None),
                         (4, 1, DAY + STEP, 2 * DAY + STEP), (5, 4, DAY + 240, None),
                         (6, 2, 2 * DAY + 480, 3 * DAY + 480),
                         (7, 2, 2 * DAY + 720, 3 * DAY + 720 + STEP)])
        plants = trial["lineages"]
        for a, b in ((0, 40 * DAY), (3 * DAY, 35 * DAY), (35 * DAY, 67 * DAY)):
            value = audit.occupancy(plants, a, b)
            self.assertEqual(value["ticks"], sampled_occupancy(plants, a, b))
            self.assertEqual(value, audit.occupancy(list(reversed(plants)), a, b))
            self.assertEqual(value["ticks"]["credit_eligible"], audit.rolling.credit(plants, a, b)["ticks"])
        records = {p["id"]: p for p in plants}
        child = records[3]
        due = child["birth_tick"] + DAY
        self.assertEqual(audit.bucket_at(child, records, due - STEP), "unconfirmed_descendant")
        self.assertEqual(audit.bucket_at(child, records, due), "credit_eligible")
        self.assertEqual(audit.bucket_at(child, records, due + 32 * DAY - STEP), "credit_eligible")
        self.assertEqual(audit.bucket_at(child, records, due + 32 * DAY), "aged_out_eligible")
        self.assertEqual(audit.bucket_at(records[5], records, 4 * DAY), "unconfirmed_parent_child")
        self.assertIsNone(audit.bucket_at(records[6], records, records[6]["death_tick"]))
        with self.assertRaisesRegex(RuntimeError, "interval"):
            audit.occupancy(plants, 1, DAY)

    def test_long_lived_seeds_carry_in_followup_and_future_expiry(self):
        trial = fixture([(1, 0, 0, None), (2, 1, DAY, None), (3, 2, 62 * DAY + STEP, None)],
                        extra=[(2, 60 * DAY), (2, 63 * DAY), (2, 93 * DAY), (2, 95 * DAY)],
                        purchases={3: 61 * DAY})
        block = audit.rolling.history(trial["lineages"], trial["seeds"], 0, audit.training.STOP)["blocks"][0]
        before = copy.deepcopy(trial)
        p = audit.audit_period(trial, block)
        self.assertEqual(trial, before)
        self.assertEqual(len(p["births"]), 1)
        self.assertEqual(p["births"][0]["id"], 3)
        self.assertEqual(p["seed_cohorts"]["carry_in"]["counts"]["seeds"], 2)
        purchased = p["seed_cohorts"]["purchased"]
        self.assertEqual(purchased["counts"]["seeds"], 2)
        self.assertEqual((purchased["counts"]["expired"], purchased["counts"]["pending"]), (1, 1))
        self.assertEqual(purchased["counts"]["full_possible_followup"], 1)
        late = next(r for r in purchased["rows"] if r["purchase_tick"] == 93 * DAY)
        self.assertEqual((late["outcome"], late["end_tick"]), ("pending", None))
        self.assertEqual(len(p["snapshots"][-1]["pending_seeds"]), 2)

    def test_followup_establishment_is_not_credit_in_prior_window(self):
        trial = fixture([(1, 0, 0, None), (2, 1, DAY, None), (3, 2, 94 * DAY + STEP, None)],
                        purchases={3: 93 * DAY})
        block = audit.rolling.history(trial["lineages"], trial["seeds"], 0, audit.training.STOP)["blocks"][0]
        p = audit.audit_period(trial, block)
        self.assertEqual(p["credit"]["earned_ticks"], 0)
        self.assertEqual(p["seed_cohorts"]["purchased"]["counts"]["renewal_eligible"], 1)
        self.assertEqual(p["births"], [])
        self.assertEqual(p["confirmations"], [])
        self.assertIn("founder_child_only_established_occupancy", p["zero_credit_signatures"])
        self.assertIn("endpoint_established", p["zero_credit_signatures"])
        self.assertNotIn("aged_out_eligible_occupancy", p["zero_credit_signatures"])

    def test_aged_out_and_first_generation_are_distinct(self):
        trial = fixture([(1, 0, 0, None), (2, 1, DAY, None), (3, 2, 3 * DAY, None)])
        block = audit.rolling.history(trial["lineages"], trial["seeds"], 0, audit.training.STOP)["blocks"][0]
        p = audit.audit_period(trial, block)
        self.assertEqual(p["credit"]["earned_ticks"], 0)
        self.assertIn("aged_out_eligible_occupancy", p["zero_credit_signatures"])
        self.assertNotIn("founder_child_only_established_occupancy", p["zero_credit_signatures"])
        self.assertIn("no_purchases", p["zero_credit_signatures"])
        self.assertEqual(p["occupancy"]["ticks"]["aged_out_eligible"], 32 * DAY)

    def test_all_saved_histories_reconcile_without_native_calls_or_mutation(self):
        panel = audit.load_panel(self.input)
        before = json.dumps(panel, sort_keys=True)
        with patch.object(audit.training, "native", side_effect=AssertionError("native call")), \
             patch.object(audit.controls.signals, "run_world", side_effect=AssertionError("native replay")):
            result = audit.analyze(panel)
        self.assertEqual(json.dumps(panel, sort_keys=True), before)
        self.assertEqual((result["histories"], result["world_windows"], result["native_calls"]), (224, 896, 0))
        self.assertEqual(len(result["pairs"]), 6)
        self.assertEqual(sum(len(w["periods"]) for worlds in result["worlds"].values() for w in worlds.values()), 896)
        for key, summaries in result["summaries"].items():
            self.assertEqual(summaries["all"]["all"]["world_windows"], 64)
            self.assertEqual(summaries["all"]["all"]["credit"]["earned_ticks"],
                             panel["evaluations"][key]["aggregate"]["key"][3])
            self.assertEqual(summaries["all"]["zero"]["world_windows"],
                             panel["evaluations"][key]["aggregate"]["zero_world_periods"])

    def test_portable_evidence_censuses_parent_partitions_and_report_counts(self):
        directory = self.input.parent
        retained = json.loads(gzip.decompress((directory / "landing-renewal-audit-results.json.gz").read_bytes()))
        summary = json.loads((directory / "landing-renewal-audit-summary.json").read_text())
        panel = audit.load_panel(self.input)
        self.assertEqual(audit.analyze(panel), retained)
        for key, value in retained.items():
            if key != "worlds":
                self.assertEqual(summary[key], value)
        canonical = (json.dumps(retained, sort_keys=True, indent=2) + "\n").encode()
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), summary["results_sha256"])
        self.assertEqual(audit.digest(audit.ROOT / audit.PROTOCOL), summary["protocol_sha256"])
        self.assertEqual(summary["source_sha256"], audit.INPUT_SHA)
        self.assertEqual(summary["manifest_sha256"],
                         "47df95fbab6382b95adb13a68c65340c3ab8f1479f96752bcc4174e6c1992b0c")
        self.assertIs(summary["repeat_verified"], True)
        self.assertIs(summary["independent_frozen_verification"], True)
        persistent = []
        for model, worlds in retained["worlds"].items():
            for case, world in worlds.items():
                blocks = panel["evaluations"][model]["worlds"][case]["history"]["blocks"]
                for period, block in zip(world["periods"], blocks, strict=True):
                    terminal = block["terminal"]
                    last = period["snapshots"][-1]
                    groups = last["plants"]
                    self.assertEqual(sorted(p for b in audit.BUCKETS[2:] for p in groups[b]),
                                     sorted(terminal["established_descendants"]))
                    self.assertEqual(groups["unconfirmed_descendant"], sorted(terminal["young_descendants"]))
                    self.assertEqual(len(groups["founder"]), terminal["living_founders"])
                    self.assertEqual(len(last["pending_seeds"]), terminal["pending_seeds"])
                    for cohort in period["seed_cohorts"].values():
                        for field in audit.FUNNEL_FIELDS:
                            self.assertEqual(cohort["counts"][field],
                                             sum(c[field] for c in cohort["parent_classes"].values()))
                    if period["terminal_tier"] == 1 and not period["credit"]["earned_ticks"]:
                        persistent.append((world["climate"], period))
        self.assertEqual(len(persistent), 390)
        self.assertEqual(sum(c == "steady" for c, _ in persistent), 317)
        self.assertTrue(all(p["seed_cohorts"]["purchased"]["counts"]["seeds"] > 0 for _, p in persistent))
        for suffix, purchased, germinated, descendants, aged in (("34", 211, 3, 69, 24), ("35", 222, 14, 89, 20)):
            model = "multi-s6d6978" + suffix + "-live"
            focused = [p for w in retained["worlds"][model].values() if w["climate"] == "steady"
                       for p in w["periods"] if p["terminal_tier"] == 1 and not p["credit"]["earned_ticks"]]
            self.assertEqual(len(focused), 26)
            totals = summary["summaries"][model]["steady"]["persistent_zero"]
            carry = totals["seed_cohorts"]["carry_in"]
            self.assertEqual((carry["seeds"], carry["expired"], carry["germinated"]), (208, 208, 0))
            new = totals["seed_cohorts"]["purchased"]
            self.assertEqual((new["seeds"], new["germinated"], new["child_died"], new["confirmed"]),
                             (purchased, germinated, germinated, 0))
            self.assertEqual(sum(p["seed_cohorts"]["purchased"]["parent_classes"]
                                 ["established-descendant"]["seeds"] for p in focused), descendants)
            self.assertEqual(totals["zero_signatures"]["aged_out_eligible_occupancy"], aged)

    def test_wrong_input_inventory_and_source_changes_fail_closed(self):
        bad = self.root / "bad.json.gz"
        bad.write_bytes(b"invalid")
        with self.assertRaisesRegex(RuntimeError, "wrong frozen input"):
            audit.collect(bad, self.root / "out")
        self.assertFalse((self.root / "out").exists())
        panel = audit.load_panel(self.input)
        panel["models"].pop()
        with self.assertRaisesRegex(RuntimeError, "missing/duplicate"):
            audit.analyze(panel)
        output = self.root / "failed"
        with patch.object(audit, "snapshot_sources"), patch.object(audit, "analyze", return_value={}), \
             patch.object(audit, "source_files", side_effect=[
                 {audit.PROTOCOL: audit.digest(audit.ROOT / audit.PROTOCOL)}, {"changed": "hash"}]):
            with self.assertRaisesRegex(RuntimeError, "source/input changed"):
                audit.collect(self.input, output)
        self.assertTrue((output / "FAILED.txt").exists())
        self.assertFalse((output / "manifest.json").exists())
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            audit.verify(output)


if __name__ == "__main__":
    unittest.main()
