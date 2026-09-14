#!/usr/bin/env python3
"""Objective arithmetic/provenance cases; synthetic evidence is not native ecology."""
import copy
from fractions import Fraction
import unittest

import garden_allocation_objectives as objective


def evidence(**changes):
    return {"birth": 0, "through": 8 * objective.DAY, "reason": "horizon", "death": None,
            "seed_ticks": [], "shortage_ticks": []} | changes


def score(e):
    return objective.scores(objective.features(e))


class ObjectiveTests(unittest.TestCase):
    def test_establishment_and_death_sample_boundary(self):
        day = objective.DAY
        for death, expected_gate in ((day, 0), (day + 15, 1)):
            f = objective.features(evidence(death={"tick": death, "cause": "water"}))
            self.assertEqual(f["gate"], expected_gate)
            self.assertEqual(f["alive_steps"], (death - 15) // 15)
            self.assertEqual(f["total_steps"], 2048)

    def test_early_death_keeps_full_denominator(self):
        f = objective.features(evidence(death={"tick": 60, "cause": "energy"}))
        self.assertEqual(objective.scores(f)["survival"], Fraction(3, 2048))
        self.assertEqual(f["total_steps"], 2048)

    def test_short_window_is_unscorable_not_zero(self):
        for through in (0, objective.DAY - 15):
            f = objective.features(evidence(through=through, reason="patch"))
            self.assertFalse(f["scorable"])
            with self.assertRaises(RuntimeError): objective.scores(f)
        self.assertTrue(objective.features(evidence(through=objective.DAY))["scorable"])

    def test_first_future_dawn_at_birth_dawn(self):
        f = objective.features(evidence(birth=2880, through=2880 + objective.DAY,
            death={"tick": 2880 + objective.DAY, "cause": "water"}))
        self.assertEqual(f["gate"], 0)

    def test_equally_durable_productivity_and_caps(self):
        inactive = score(evidence())
        productive = score(evidence(seed_ticks=[i * objective.DAY for i in range(1, 7)]))
        for variant in productive:
            if variant == "survival":
                self.assertEqual(productive[variant], inactive[variant])
            else:
                self.assertGreater(productive[variant], inactive[variant])
        self.assertEqual(productive["confirmed-days:1/4"], Fraction(9, 4))
        self.assertEqual(productive["raw-seeds:1/4"], Fraction(9, 4))

    def test_burst_cannot_multiply_productive_days(self):
        day = objective.DAY
        burst = evidence(seed_ticks=[day + 60 * i for i in range(1, 9)])
        spread = evidence(seed_ticks=[day, 2 * day, 3 * day, 4 * day])
        b, s = score(burst), score(spread)
        self.assertEqual(b["raw-seeds:1/4"], s["raw-seeds:1/4"])
        self.assertLess(b["confirmed-days:1/4"], s["confirmed-days:1/4"])
        self.assertEqual(objective.features(burst)["confirmed_day_bins"], [1])

    def test_burst_then_starve(self):
        fixtures = objective.arithmetic_fixtures()
        burst = fixtures["burst-then-die"]
        self.assertEqual(burst["features"]["confirmed_seeds"], 0)
        self.assertEqual(burst["features"]["seed_status_counts"], {"natural-failure": 8})
        for variant in burst["scores"]:
            self.assertLess(burst["scores"][variant]["decimal"],
                            fixtures["inactive"]["scores"][variant]["decimal"])

    def test_death_exactly_at_confirmation_fails(self):
        tick = 2 * objective.DAY
        f = objective.features(evidence(seed_ticks=[tick],
            death={"tick": tick + objective.DAY, "cause": "water"}))
        self.assertEqual(f["seed_events"][0]["status"], "natural-failure")

    def test_shortage_interval_boundaries_and_recovery(self):
        day = objective.DAY
        for shortage, expected in ((day, "confirmed"), (day + 60, "resource-shortage"),
                                   (2 * day, "resource-shortage"), (2 * day + 60, "confirmed")):
            f = objective.features(evidence(seed_ticks=[day], shortage_ticks=[shortage]))
            self.assertEqual(f["seed_events"][0]["status"], expected)

    def test_known_failure_precedes_incomplete_followup(self):
        day = objective.DAY
        e = evidence(through=2 * day, seed_ticks=[2 * day - 120],
                     shortage_ticks=[2 * day - 60])
        self.assertEqual(objective.features(e)["seed_events"][0]["status"], "resource-shortage")
        e["death"] = {"tick": 2 * day, "cause": "energy"}
        self.assertEqual(objective.features(e)["seed_events"][0]["status"], "natural-failure")

    def test_patch_and_horizon_censoring(self):
        day = objective.DAY
        for reason in ("patch", "horizon"):
            f = objective.features(evidence(through=2 * day, reason=reason, seed_ticks=[day + 15]))
            self.assertEqual(f["seed_status_counts"], {reason + "-censored": 1})
            self.assertEqual(f["confirmed_seeds"], 0)
            self.assertEqual(objective.scores(f)["confirmed-days:1/4"], 2)
        exact = objective.features(evidence(through=2 * day, seed_ticks=[day]))
        self.assertEqual(exact["seed_status_counts"], {"confirmed": 1})

    def test_additive_reward_retains_late_collapse_tradeoff(self):
        fixtures = objective.arithmetic_fixtures()
        for weight in objective.WEIGHTS:
            key = f"confirmed-days:{weight}"
            self.assertGreater(fixtures["late-collapse"]["scores"][key]["decimal"],
                               fixtures["inactive"]["scores"][key]["decimal"])
        self.assertLess(fixtures["late-collapse"]["scores"]["survival"]["decimal"], 2)

    def test_no_shape_resource_or_action_reward(self):
        original = evidence(seed_ticks=[objective.DAY])
        changed = original | {"nodes": 500, "roots": 500, "energy": 256, "water": 512,
                              "actions": {"root_extend": 1000000}}
        self.assertEqual(score(original), score(changed))

    def test_exact_ties_not_decimal_ties(self):
        values = dict.fromkeys(objective.allocation.ARMS, Fraction(1))
        self.assertEqual(objective.ranking(values), [list(objective.allocation.ARMS)])
        values["candidate"] += Fraction(1, 10**9)
        self.assertEqual(objective.exact(values["candidate"])["decimal"], 1)
        self.assertEqual(objective.ranking(values)[0], ["candidate"])

    def test_same_bin_boundary_and_duplicate_rejection(self):
        f = objective.features(evidence(seed_ticks=[objective.DAY - 15, objective.DAY]))
        self.assertEqual(f["confirmed_day_bins"], [0, 1])
        with self.assertRaises(RuntimeError):
            objective.features(evidence(seed_ticks=[objective.DAY, objective.DAY]))

    def test_followup_diagnostic_is_separate_from_objective(self):
        e = evidence(seed_ticks=[objective.DAY], shortage_ticks=[objective.DAY + 60])
        f = objective.features(e)
        self.assertEqual(f["seed_events"][0]["status"], "resource-shortage")
        self.assertEqual(objective.confirmation_survival(f["seed_events"][0], e), "alive")
        self.assertEqual(objective.scores(f)["confirmed-days:1/4"], 2)
        e["through"] = 2 * objective.DAY - 15
        self.assertEqual(objective.confirmation_survival(f["seed_events"][0], e), "horizon-censored")

    def test_shortage_diagnostic_severity_and_gaps(self):
        rows = [{"tick": t, "sun_phase": 4, "plant": {"flags": flags, "stress": stress,
                 "energy": 0, "water": 20}} for t, flags, stress in
                ((60, 2, 1), (120, 2, 2), (180, 0, 1), (240, 2, 1), (300, 0, 0))]
        d = objective.shortage_summary(rows)
        self.assertEqual(d["maintenance_samples"], 5)
        self.assertEqual(d["shortage_samples"], 3)
        self.assertEqual(d["longest_consecutive_shortage_samples"], 2)
        self.assertEqual(d["peak_observed_stress"], 2)

    def test_invalid_evidence(self):
        for change in ({"birth": -15}, {"through": 17}, {"reason": "death"},
                       {"seed_ticks": [-15]}, {"seed_ticks": [16]},
                       {"shortage_ticks": [15]}, {"seed_ticks": [60, 30]},
                       {"death": {"tick": 30, "cause": "patch"}},
                       {"seed_ticks": [60], "death": {"tick": 60, "cause": "water"}}):
            with self.assertRaises(RuntimeError): objective.features(evidence(**change))

    def test_common_window_does_not_depend_on_policy_death(self):
        spec = objective.allocation.SPECS[0]
        events = [e for e in objective.schedule(0xe4d65e6f, spec["end"]) if e["tick"] >= spec["birth"]]
        ref = {"spec": spec, "events": events, "lineage": {"column": 12, "death_tick": 618600}}
        a = objective.common_window(spec, ref)
        ref["lineage"]["death_tick"] = None
        self.assertEqual(a, objective.common_window(spec, ref))
        self.assertEqual(a["reason"], "patch")
        self.assertEqual(a["through"], 635430 - 15)
        wrong = copy.deepcopy(ref)
        wrong["events"][0]["tick"] += 15
        with self.assertRaises(RuntimeError): objective.common_window(spec, wrong)


if __name__ == "__main__":
    unittest.main()
