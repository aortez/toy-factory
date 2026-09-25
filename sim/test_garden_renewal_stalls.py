#!/usr/bin/env python3
"""Lifetime funnels, sample consistency and frame identity; no native processes."""
import copy
import unittest
import zlib

import garden_renewal_stalls as stalls

DAY, STEP, fitness = stalls.DAY, stalls.STEP, stalls.fitness


def trial(plants, extra=()):
    f = fitness.fixture(plants, extra, start=stalls.pilot.START, end=stalls.pilot.END)
    for p in f["lineages"]:
        p["species"] = 0
    f["checkpoints"] = []
    return f


class StallTests(unittest.TestCase):
    def base(self):
        return [(1, 0, 0, None, False), (2, 1, DAY, None, False)]

    def test_parent_classes_distinguish_births_from_qualifying_grandchildren(self):
        f = trial([*self.base(), (3, 2, 64 * DAY, None, False), (4, 1, 65 * DAY, None, False),
                   (5, 2, 70 * DAY, 70 * DAY + STEP, False)], [(1, 80 * DAY)])
        original = copy.deepcopy(f)
        r = stalls.funnel(f, 62 * DAY, 94 * DAY)["classes"]
        self.assertEqual(r["founder"]["purchases"], 2)
        self.assertEqual(r["founder"]["confirmed"], 1)
        self.assertEqual(r["founder"]["qualifying"], 0)
        self.assertEqual(r["established-descendant"]["purchases"], 2)
        self.assertEqual(r["established-descendant"]["qualifying"], 1)
        self.assertEqual(r["established-descendant"]["natural_failure"], 1)
        self.assertEqual(f, original)

    def test_unconfirmed_seed_parent_can_later_qualify(self):
        f = trial([(1, 0, 0, None, False), (2, 1, 63 * DAY, None, False),
                   (3, 2, 63 * DAY + 150, None, False)])
        r = stalls.funnel(f, 62 * DAY, 94 * DAY)["classes"]["unconfirmed-descendant"]
        self.assertEqual((r["purchases"], r["confirmed"], r["qualifying"]), (1, 1, 1))

    def test_death_at_confirmation_fails_and_patch_is_separate(self):
        for patch in (False, True):
            f = trial([*self.base(), (3, 2, 64 * DAY, 65 * DAY, patch)])
            r = stalls.funnel(f, 62 * DAY, 94 * DAY)["classes"]["established-descendant"]
            self.assertEqual(r["qualifying"], 0)
            self.assertEqual(r["patch_failure" if patch else "natural_failure"], 1)

    def test_seed_followup_after_window_is_not_main_window_confirmation(self):
        f = trial([*self.base(), (3, 2, 94 * DAY + 90, None, False)])
        r = stalls.funnel(f, 62 * DAY, 94 * DAY)["classes"]["established-descendant"]
        self.assertEqual(r["qualifying"], 1)
        a = stalls.lifetime_analysis(f)
        self.assertEqual(a["gap_score"]["rolling"]["ticks"], 0)
        self.assertEqual(a["first_credit_after_gap"], {"id": 3, "tick": 95 * DAY + 90})

    def test_future_death_does_not_change_earlier_followup(self):
        a = trial([*self.base(), (3, 2, 94 * DAY + 90, 110 * DAY, True)])
        b = trial([*self.base(), (3, 2, 94 * DAY + 90, None, False)])
        self.assertEqual(stalls.funnel(a, 62 * DAY, 94 * DAY), stalls.funnel(b, 62 * DAY, 94 * DAY))

    def test_recovery_can_be_existing_carry_in_or_absent(self):
        a = trial([*self.base(), (3, 2, 80 * DAY, None, False)])
        self.assertEqual(stalls.lifetime_analysis(a)["first_credit_after_gap"], {"id": 3, "tick": 94 * DAY + STEP})
        b = stalls.lifetime_analysis(trial(self.base()))
        self.assertIsNone(b["first_credit_after_gap"])
        self.assertIsNone(b["first_qualifying_confirmation"])
        self.assertEqual(len(b["daily"]), 97)

    def test_bad_original_seed_counter_is_rejected(self):
        f = trial(self.base())
        f["lineages"][0]["late_seeds_created"] += 1
        with self.assertRaises(RuntimeError):
            stalls.funnel(f, 62 * DAY, 94 * DAY)

    def census(self, f):
        rows = []
        for day in range(193):
            t = day * DAY
            c = stalls.counts(f, t)
            rows.append({"type": "world", "tick": t, "node_capacity": 512, "leaf_policy": "selective",
                         "leaf_environment": "leaf-maintenance-v1", "hash": "12345678", "nodes": 0,
                         **{k: c[k] for k in ("living", "births", "deaths", "seeds_created", "seeds_expired")},
                         "seeds": [{}] * c["seed_bank"], "plants": [{"id": i, "dead": False} for i in c["living_ids"]]})
        return rows

    def test_census_matches_ledger_and_uses_last_post_patch_sample(self):
        f = trial([*self.base(), (3, 2, 64 * DAY, 65 * DAY, True)])
        rows = self.census(f)
        pre = copy.deepcopy(rows[65])
        pre["living"] += 1
        rows.insert(65, pre)
        values = stalls.validate_census(rows, f)
        self.assertEqual(len(values), 193)
        self.assertEqual(values[65 * DAY]["living"], 2)
        for broken in (rows[:-1], copy.deepcopy(rows)):
            if len(broken) == len(rows):
                broken[-1]["births"] += 1
            with self.assertRaises(RuntimeError):
                stalls.validate_census(broken, f)

    def test_frame_crc_and_census_identity_checked(self):
        f = trial(self.base())
        samples = stalls.validate_census(self.census(f), f)
        raw = bytes(stalls.gallery.FRAME_BYTES)
        value = {"schema_version": 1, "scenario": "rainfed-crowded", "policy": "neural-no-night-growth",
                 "seed": "1824c139", "tick": 62 * DAY, "model_crc32": "dc5e849d", "node_capacity": 512,
                 "seed_dispersal": "wide-v1", "water_uptake": "headroom-v1", "leaf_environment": "leaf-maintenance-v1",
                 "leaf_policy": "selective", "disturbance_protocol": "patch-death-v1", "disturbance_seed": stalls.PATCH,
                 "hash": "12345678", "nodes": 0, "living": 2, "births": 1, "deaths": 0, "seed_bank": 0,
                 "framebuffer_crc32": f"{zlib.crc32(raw):08x}"}
        stalls.validate_replay(value, f, "1824c139", "dc5e849d", 62, samples, raw)
        for bad in (dict(value, hash="87654321"), dict(value, root_bootstrap_rule="unexpected")):
            with self.assertRaises(RuntimeError):
                stalls.validate_replay(bad, f, "1824c139", "dc5e849d", 62, samples, raw)
        with self.assertRaises(RuntimeError):
            stalls.validate_replay(value, f, "1824c139", "dc5e849d", 62, samples, raw[:-1])

    def test_fixed_case_frame_and_process_budgets(self):
        self.assertEqual(stalls.SEEDS, ("1824c139", "4d5f9ee1"))
        self.assertEqual(stalls.FRAME_DAYS, (62, 78, 94, 110))
        self.assertEqual(len(stalls.MODELS) * len(stalls.SEEDS) * (2 * len(stalls.FRAME_DAYS) + 2), 40)

    def test_blocker_summary_is_sampled_and_excludes_dormant_or_founder_seeds(self):
        records = {1: {"parent": 0}, 2: {"parent": 1}}
        samples = {d * DAY: {"living": 8, "nodes": 280, "seeds": [
            {"parent": 1, "blockers": 40}, {"parent": 2, "blockers": 41},
            {"parent": 2, "blockers": 40}, {"parent": 2, "blockers": 32}]}
            for d in range(62, 95)}
        r = stalls.sampled_blockers(samples, records)
        self.assertEqual(r["non_dormant_descendant_seed_observations"], 66)
        self.assertEqual(r["blocker_observations"], {"moisture": 0, "light": 0, "plant_capacity": 33,
                                                   "node_capacity": 0, "spacing": 66})
        self.assertEqual(r["daily_living_histogram"], {"8": 33})


if __name__ == "__main__":
    unittest.main()
