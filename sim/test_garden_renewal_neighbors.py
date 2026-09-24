#!/usr/bin/env python3
"""Neighbor routing, fixed-budget and conservative tie-evidence tests."""
import copy
import unittest
from unittest.mock import patch

import garden_renewal_neighbors as audit


def routing_rows(case):
    plants = [{"id": identity, "parent": 0, "generation": 0, "species": species,
               "column": column, "dead": False} for identity, (species, column) in audit.FOUNDERS.items()]
    rows = [{"type": "world", "tick": 0, "focal_policy": audit.routing(case), "plants": plants}]
    for identity in range(1, 7):
        model = case.override_model if identity == case.override_id else case.background
        rows.append({"type": "bid", "tick": 15, "id": identity,
                     "controller_model_crc32": audit.prior.MODELS[model].crc})
    rows.append({"type": "leaf-bid", "tick": 15, "id": 2})
    return rows


def bid(index, x, priority=17):
    return {"tick": 15, "type": "bid", "id": 2, "tip_index": index,
            "controller_model_crc32": "01b9d94a", "priority": priority,
            "action": 1, "tissue": 0, "x": x, "y": 100, "depth": 3,
            "energy": 100, "water": 50, "candidates": [{"flags": 3, "light": 10, "x": x, "y": 93}]}


class NeighborTests(unittest.TestCase):
    def test_panel_keeps_observed_shrub_and_descendants_on_n(self):
        self.assertEqual([c.override_id for c in audit.NEW_CASES], [1, 3, 4, 5])
        self.assertTrue(all(c.background == "r2-n" and c.override_model == "r2-w" for c in audit.NEW_CASES))
        self.assertEqual(audit.FOCAL, 2)
        for case in audit.CASES:
            rows = routing_rows(case)
            saved = copy.deepcopy(rows)
            counts, groups = audit.check_routing(rows, case)
            self.assertEqual(counts, {"reset": 1, "worlds": 1, "override_bids": 1,
                "background_bids": 5, "observed_shrub_bids": 1})
            self.assertEqual(groups[15], [rows[2]])
            self.assertEqual(rows, saved)

    def test_wrong_override_model_and_inherited_routing_rejected(self):
        case = audit.NEW_CASES[0]
        for index in (1, 2, 6):
            rows = routing_rows(case)
            rows[index]["controller_model_crc32"] = "wrong"
            with self.assertRaisesRegex(RuntimeError, "routed growth"):
                audit.check_routing(rows, case)
        rows = routing_rows(case)
        rows[6]["controller_model_crc32"] = audit.prior.MODELS["r2-w"].crc
        with self.assertRaises(RuntimeError): audit.check_routing(rows, case)

    def test_wrong_founder_identity_and_duplicate_rejected(self):
        case = audit.NEW_CASES[1]
        for key, value in (("parent", 1), ("generation", 1), ("dead", True), ("species", "shrub"), ("column", 8)):
            rows = routing_rows(case)
            rows[0]["plants"][2][key] = value
            with self.assertRaises(RuntimeError): audit.check_routing(rows, case)
        rows = routing_rows(case)
        rows[0]["plants"].append(rows[0]["plants"][0])
        with self.assertRaises(RuntimeError): audit.check_routing(rows, case)

    def test_missing_evidence_and_unknown_events_rejected(self):
        case = audit.NEW_CASES[0]
        for index in (0, 1, 2):
            rows = routing_rows(case)
            rows.pop(index)
            with self.assertRaises(RuntimeError): audit.check_routing(rows, case)
        rows = routing_rows(case)
        rows[-1]["type"] = "disturbance"
        with self.assertRaises(RuntimeError): audit.check_routing(rows, case)
        rows = routing_rows(case)
        rows[-1]["controller_model_crc32"] = "01b9d94a"
        with self.assertRaises(RuntimeError): audit.check_routing(rows, case)

    def test_metadata_or_observed_model_change_rejected(self):
        case = audit.NEW_CASES[0]
        rows = routing_rows(case)
        rows[0]["focal_policy"]["founder"] = 2
        with self.assertRaises(RuntimeError): audit.check_routing(rows, case)
        unsupported = audit.Case("wrong", 2, "r2-w")
        with self.assertRaisesRegex(RuntimeError, "must stay N"):
            audit.check_routing(routing_rows(unsupported), unsupported)

    def test_fixed_forty_calls_and_reused_references(self):
        commands = audit.commands()
        self.assertEqual(len(commands), 40)
        self.assertEqual(len({name for name, _ in commands}), 40)
        self.assertEqual(sum(name.endswith(".gz") for name, _ in commands), 8)
        self.assertEqual(sum("--framebuffer" in c for _, c in commands), 32)
        self.assertEqual(audit.settings()["budget"]["reference_replays"], 0)
        for case in audit.NEW_CASES:
            selected = [(name, c) for name, c in commands if case.name in name]
            self.assertEqual(len(selected), 10)
            for name, command in selected:
                self.assertEqual(command[1:5], ["models/r2-n.tgm", "rainfed-crowded", "neural-no-night-growth", "0x0d983a80"])
                self.assertEqual(command[command.index("--focal-founder") + 1], str(case.override_id))
                self.assertEqual(command[command.index("--focal-model") + 1], "models/r2-w.tgm")
                self.assertEqual(command[command.index("--disturbance-seed") + 1], "0x05d87ca0")
                self.assertTrue(command[0] in ("bin/garden-inspect", "bin/garden-replay"))
                if "--framebuffer" in command:
                    self.assertEqual(command[-1], name.removesuffix(".json") + ".rgb565")
        self.assertEqual(len(audit.copies()), 43)
        self.assertEqual(audit.copies()["bin/garden-inspect"], "bin/garden-inspect")
        self.assertEqual(audit.copies()["traces/n-in-w.repeat.jsonl.gz"], "traces/n-in-w.repeat.jsonl.gz")
        self.assertFalse({name for name, _ in commands} & audit.copies().keys())

    def test_equal_recorded_bid_multiset_different_tie_winner(self):
        left = {15: [bid(1, 10), bid(2, 20)]}
        right = {15: [bid(91, 20), bid(92, 10)]}
        saved = copy.deepcopy((left, right))
        result = audit.bid_comparison(left, right)
        self.assertEqual(result["equal_recorded_bidsets_with_different_winners"], 1)
        event = result["first_equal_recorded_bids_different_winner"]
        self.assertEqual(event["tick"], 15)
        self.assertEqual((event["control_winner"]["x"], event["case_winner"]["x"]), (10, 20))
        self.assertEqual(event["control_max_priority_ties"], 2)
        self.assertEqual((left, right), saved)

    def test_input_priority_action_candidate_or_unknown_change_not_pure_order(self):
        for key, value in (("energy", 99), ("water", 49), ("priority", 18), ("action", 0),
                           ("candidates", []), ("extra_observation", 1)):
            left = {15: [bid(1, 10), bid(2, 20)]}
            right = {15: [bid(91, 20), bid(92, 10)]}
            right[15][0][key] = value
            result = audit.bid_comparison(left, right)
            self.assertIsNone(result["first_equal_recorded_bids_different_winner"], key)
            self.assertEqual(result["equal_recorded_bidsets_with_different_winners"], 0)

    def test_global_indices_alone_do_not_change_physical_winner(self):
        result = audit.bid_comparison({15: [bid(1, 10), bid(2, 20)]}, {15: [bid(99, 10), bid(98, 20)]})
        self.assertIsNone(result["first_recorded_sequence_difference"])
        self.assertIsNone(result["first_physical_winner_difference"])

    def test_wait_tie_is_not_an_extend_event(self):
        left = {15: [bid(1, 10) | {"action": 0}, bid(2, 20) | {"action": 0}]}
        result = audit.bid_comparison(left, {15: list(reversed(left[15]))})
        self.assertIsNotNone(result["first_tied_winner_difference"])
        self.assertIsNone(result["first_extend_winner_difference"])

    def test_strict_maximum_not_first_bid_and_missing_bid_not_a_tie(self):
        result = audit.bid_comparison({15: [bid(1, 10, 10), bid(2, 20, 20)]}, {15: [bid(2, 20, 20), bid(1, 10, 10)]})
        self.assertIsNone(result["first_physical_winner_difference"])
        result = audit.bid_comparison({15: [bid(1, 10), bid(2, 20)]}, {15: [bid(2, 20)]})
        self.assertIsNone(result["first_equal_recorded_bids_different_winner"])
        result = audit.bid_comparison({15: [bid(1, 10)]}, {})
        self.assertIsNotNone(result["first_recorded_sequence_difference"])
        self.assertIsNone(result["first_physical_winner_difference"])

    def test_earliest_difference_and_disappearance(self):
        a = {30: {"energy": 20}, 15: {"energy": 10}, 45: None}
        b = {15: {"energy": 9}, 30: {"energy": 0}, 45: None}
        self.assertEqual(audit.first_plant_difference(a, b, ("energy",)),
                         {"tick": 15, "differences": {"energy": {"control": 10, "case": 9}}})
        self.assertIsNone(audit.first_plant_difference(a, a, ("energy",)))
        self.assertEqual(audit.first_plant_difference({0: None}, {0: {"energy": 1}}, ("energy",)),
                         {"tick": 0, "control_present": False, "case_present": True})

    def test_seed_events_preserve_exact_timings_and_exclude_terminal_clear(self):
        plant = {"dead": False, "energy": 128, "nodes": 24, "flowers": 2, "spent_flowers": 0}
        states = {0: plant, 15: plant | {"energy": 80, "spent_flowers": 1},
                  30: plant | {"dead": True, "energy": 0}, 45: None}
        with patch.object(audit.startup.resources, "budget", return_value={"energy_seeds": 48, "water_seeds": 24}) as budget:
            result = audit.seed_events(states)
        self.assertEqual(budget.call_count, 1)
        self.assertEqual(result, [{"tick": 15, "energy_spent": 48, "water_spent": 24, "energy_before": 128,
            "energy_after": 80, "nodes": 24, "flowers": 2, "spent_flowers": 1}])
        with self.assertRaisesRegex(RuntimeError, "unobserved"):
            audit.seed_events({15: plant})

    def test_first_seed_comparison_uses_cost_not_incidental_body_fields(self):
        control = {"plants": {}, "bids": {}, "seed_events": [{"tick": 30, "energy_spent": 48, "nodes": 20}]}
        changed = {"plants": {}, "bids": {}, "seed_events": [{"tick": 30, "energy_spent": 48, "nodes": 21}]}
        self.assertIsNone(audit.compare(control, changed)["first_seed_spending_difference"])
        changed["seed_events"].append({"tick": 15, "energy_spent": 48})
        self.assertEqual(audit.compare(control, changed)["first_seed_spending_difference"],
                         {"tick": 15, "control_spent": 0, "case_spent": 48})


if __name__ == "__main__":
    unittest.main()
