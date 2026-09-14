#!/usr/bin/env python3
"""Recovery boundaries and opportunities without native processes or new ecology."""
import gzip
import json
from pathlib import Path
import tempfile
import unittest

import garden_recruitment_recovery as recovery
from test_garden_seed_attempts import sequential_fixture

DAY, STEP = recovery.DAY, recovery.STEP


def plant(identity, parent=0, birth=0, death=None, patch=False, column=3):
    return {"id": identity, "parent": parent, "birth_tick": birth, "death_tick": death,
            "environmental_death": patch, "column": column, "generation": int(bool(parent))}


class RecoveryTests(unittest.TestCase):
    def test_event_boundary_step_belongs_to_previous_patch(self):
        events = [{"tick": 100, "end_tick": 200}, {"tick": 200, "end_tick": 300}]
        self.assertIsNone(recovery.owner(events, 100))
        self.assertEqual(recovery.owner(events, 200), events[0])
        self.assertEqual(recovery.owner(events, 201), events[1])
        self.assertEqual(recovery.owner(events, 300), events[1])
        self.assertIsNone(recovery.owner(events, 301))

    def test_local_footprint_uses_victims_and_clips_edges(self):
        records = {1: plant(1, column=0), 2: plant(2, column=27)}
        self.assertEqual(recovery.local_columns({"killed": [1, 2]}, records), [0, 1, 2, 25, 26, 27])
        self.assertEqual(recovery.local_columns({"killed": []}, records), [])

    def test_dead_plants_still_block_slot_and_spacing(self):
        plants = [{"column": 3*i, "dead": i == 7} for i in range(8)]
        masks = [8 | (32 if any(abs(c-p["column"]) < 3 for p in plants) else 0) for c in range(28)]
        recovery.audit.check_sites(masks, 32, plants, 512)
        self.assertEqual(recovery.columns(masks), [])
        wrong = masks.copy()
        wrong[21] &= ~32
        with self.assertRaises(RuntimeError):
            recovery.audit.check_sites(wrong, 32, plants, 512)

    def attempt(self, column=10, blockers=32, opened=(20,)):
        masks = [32]*28
        for c in opened:
            masks[c] = 0
        return {"tick": 70*DAY, "sites_before": masks, "attempts": [
            {"parent": 2, "age": 8, "outcome": 0, "column": column, "blockers": blockers, "sites": masks}]}

    def test_anywhere_reachable_and_actual_are_distinct(self):
        row = self.attempt()
        records = {2: plant(2, 1)}
        key = (2, row["tick"]-8*STEP)
        groups, visits = recovery.attempt_exposure(row, records, {key: 1 << 20})
        counts = groups["established-descendant"]
        self.assertEqual([counts[k] for k in ("any_open", "reachable_open", "actual_open")], [1, 1, 0])
        groups, _ = recovery.attempt_exposure(row, records, {key: 1 << 22})
        self.assertEqual(groups["established-descendant"]["reachable_open"], 0)
        self.assertEqual(visits[0]["key"], key)

    def test_sequential_loss_not_inferred_from_post_step(self):
        row = self.attempt(column=20, blockers=32)
        row["attempts"][0]["sites"] = [32]*28
        groups, _ = recovery.attempt_exposure(row, {2: plant(2, 1)}, {(2, row["tick"]-8*STEP): 1 << 20})
        self.assertEqual(groups["established-descendant"]["sequentially_displaced"], 1)
        row["sites_before"][20] = 32
        groups, _ = recovery.attempt_exposure(row, {2: plant(2, 1)}, {(2, row["tick"]-8*STEP): 1 << 20})
        self.assertEqual(groups["established-descendant"]["sequentially_displaced"], 0)

    def test_existing_sequential_validator_rejects_impossible_audits(self):
        sequential_fixture()

    def test_expired_and_dormant_are_not_mature_opportunities(self):
        row = self.attempt()
        a = row["attempts"][0]
        row["attempts"] = [{**a, "age": 256, "outcome": 1}, {**a, "age": 7}]
        groups, visits = recovery.attempt_exposure(row, {2: plant(2, 1)}, {})
        self.assertEqual(groups["established-descendant"], {"visits": 2, "expired": 1, "dormant": 1})
        self.assertEqual(visits, [])

    def test_founders_and_unconfirmed_descendants_remain_separate(self):
        row = self.attempt()
        row["attempts"] *= 2
        row["attempts"] = [{**row["attempts"][0], "parent": 1}, row["attempts"][1]]
        records = {1: plant(1), 2: plant(2, 1, row["tick"]-STEP)}
        support = {(i, row["tick"]-8*STEP): 1 << 20 for i in (1, 2)}
        groups, _ = recovery.attempt_exposure(row, records, support)
        self.assertEqual(groups["founder"]["mature_checks"], 1)
        self.assertEqual(groups["unconfirmed-descendant"]["mature_checks"], 1)
        self.assertEqual(groups["established-descendant"], {})

    def test_birth_confirmation_death_boundary_and_future_exclusion(self):
        records = {1: plant(1), 2: plant(2, 1)}
        child = plant(3, 2, 70*DAY, 71*DAY, True)
        self.assertEqual(recovery.birth_record(child, records)["status"], "patch_failure")
        child["death_tick"] += STEP
        value = recovery.birth_record(child, records)
        self.assertEqual(value["status"], "confirmed")
        self.assertTrue(value["qualifying"])
        self.assertIsNone(value["early_death_tick"])
        child["death_tick"] = None
        self.assertEqual(recovery.birth_record(child, records), value)
        child["parent"] = 1
        self.assertFalse(recovery.birth_record(child, records)["qualifying"])

    def test_no_hit_event_is_not_a_local_recovery(self):
        e = recovery.new_event({"tick": 100, "killed": []}, 300, {})
        row = {"tick": 115, "sites_before": [0]*28}
        recovery.note_step(e, row, {}, [], [])
        self.assertEqual(e["first"], {"plant_slot": 115, "any_open": 115})
        self.assertEqual(e["exposure"]["local_open"], 0)
        self.assertEqual(e["births"], [])

    def test_first_birth_is_distinct_from_first_surviving_recruit(self):
        records = {1: plant(1), 2: plant(2, 1)}
        e = recovery.new_event({"index": 1, "tick": 70*DAY, "killed": [2]}, 75*DAY, records)
        child = plant(3, 1, 71*DAY, 71*DAY+STEP)
        later = plant(4, 2, 73*DAY)
        e["births"] = [recovery.birth_record(child, records, e), recovery.birth_record(later, records, e)]
        e["first"]["local_open"] = 70*DAY+STEP
        e["victim_reclamation_ticks"] = {"2": 70*DAY+STEP}
        e["exposure"]["local_open"] = 5
        result = {"cases": [{"id": "fixture", "events": [e], "births": e["births"],
            "exposure": {b: {"steps": 1, "pre_open": 1, "pre_open_no_germination": 0,
                             "pre_open_no_mature_seed": 0} for b in ("gap", "recovery")},
            "groups": {b: {n: {} for n in recovery.stalls.PARENT_CLASSES} for b in ("gap", "recovery")}}]}
        event = recovery.review_summary(result)["cases"][0]["events"][0]
        self.assertEqual(event["first_local_birth"]["id"], 3)
        self.assertEqual(event["first_local_survivor"]["id"], 4)
        self.assertEqual(event["first_local_survivor_birth_after_open_ticks"], 3*DAY-STEP)

    def test_trace_header_step_order_and_events(self):
        header = recovery.expected_header("1824c139", "dc5e849d")
        rows = [header, {"type": "seed-step", "tick": recovery.START}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"audit.gz"
            def run(values):
                with gzip.open(path, "wt") as stream:
                    for r in values:
                        stream.write(json.dumps(r)+"\n")
                return list(recovery.attempt_rows(path, header, []))
            with self.assertRaises(RuntimeError):
                run(rows)  # Truncated after origin.
            with self.assertRaises(RuntimeError):
                run([{**header, "model_crc32": "wrong"}, *rows[1:]])
            with self.assertRaises(RuntimeError):
                run([*rows, {"type": "seed-step", "tick": recovery.START+2*STEP}])

    def test_fixed_scope_and_budget(self):
        self.assertEqual((recovery.START//DAY, recovery.SPLIT//DAY, recovery.END//DAY), (62, 94, 126))
        self.assertEqual(len(recovery.stalls.MODELS)*len(recovery.stalls.SEEDS)*3, 12)


if __name__ == "__main__":
    unittest.main()
