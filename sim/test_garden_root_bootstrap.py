#!/usr/bin/env python3
"""Independent override audit and opt-in native CLI checks."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import unittest

import garden_root_bootstrap as audit
import garden_root_bids as bids


def example():
    return {"generation": 1, "vigor": 0, "species": "shrub"}, {
        "tick": audit.START + 15, "id": 8, "tissue": 1, "depth": 1, "y": 149,
        "original_action": 1, "action": 1, "original_priority": 20, "priority": 32767,
        "energy": 64, "water": 24,
        "candidates": [{"flags": 3, "y": 154, "moisture": 10},
                       {"flags": 3, "y": 155, "moisture": 20},
                       {"flags": 3, "y": 154, "moisture": 20}],
        "root_bootstrap": {"rule": audit.RULE, "after": audit.START, "age": 1,
            "roots": 2, "tip_moisture": 0, "original_order": [2, 0, 1], "order": [2, 0, 1]}}


class RootAuditTests(unittest.TestCase):
    def test_reference_and_tie_order(self):
        p, b = example()
        self.assertTrue(audit.expected_override(b, p))
        b["candidates"][1]["moisture"] = 21
        with self.assertRaises(RuntimeError): audit.expected_override(b, p)
        b["root_bootstrap"]["order"] = [1, 2, 0]
        self.assertTrue(audit.expected_override(b, p))

    def test_no_override_boundaries(self):
        for change in ("founder", "old", "age", "root", "dry", "blocked", "poor", "wait"):
            p, b = example()
            b["priority"] = b["original_priority"]
            if change == "founder": p["generation"] = 0
            if change == "old": b["tick"] = audit.START
            if change == "age": b["root_bootstrap"]["age"] = 257
            if change == "root": b["root_bootstrap"]["roots"] = 3
            if change == "poor": b["water"] = 4
            if change == "wait":
                b.update(action=0, original_action=0)
                b["root_bootstrap"].update(order=[], original_order=[])
            for c in b["candidates"]:
                if change == "dry": c["moisture"] = 0
                if change == "blocked": c["flags"] = 1
            self.assertFalse(audit.expected_override(b, p), change)
        p, b = example()
        b["root_bootstrap"]["after"] -= 15
        with self.assertRaises(RuntimeError): audit.expected_override(b, p)

    def test_identity_is_opt_in(self):
        checker = audit.trial.bank.competition.maintenance.check_identity
        row = {"leaf_environment": "leaf-maintenance-v1", "leaf_policy": "selective", "node_capacity": 512,
               "root_bootstrap_rule": audit.RULE, "root_bootstrap_after": audit.START}
        with self.assertRaises(RuntimeError): checker(row, "selective", 512)
        checker(row, "selective", 512, root_bootstrap_after=audit.START)
        for change in ({"root_bootstrap_rule": "unknown"}, {"root_bootstrap_after": audit.START + 15}):
            with self.assertRaises(RuntimeError): checker(row | change, "selective", 512, root_bootstrap_after=audit.START)

    def test_observer_checks_winning_bid_and_counter_delta(self):
        p, b = example()
        b.update(tip_index=1, priority=20, original_priority=20, x=100, maximum_depth=8, sun_phase=64)
        p.update(id=8, agent={"decisions": 1, "last_priority": 20, "last_action": 1,
                             "last_tissue": 1, "last_x": 100, "last_y": 149})
        self.assertEqual(bids.bid_group([b], p, None, b["tick"])["wet_extending_roots"], 1)
        with self.assertRaises(RuntimeError): bids.bid_group([], p, None, b["tick"])
        with self.assertRaises(RuntimeError): bids.bid_group([b, b], p, None, b["tick"])
        self.assertIsNone(bids.bid_group([], p, p, b["tick"] + 15))


def cli_checks(build):
    root = Path(__file__).resolve().parents[1]
    model = root / "artifacts/garden-seed-reserve-v3/model.tgm"
    # Bad-option checks never need a model. Positive CLI equivalence additionally
    # runs when this local experiment's frozen model is available.
    cache = (build / "CMakeCache.txt").read_text()
    enabled = all(f"TOY_FACTORY_GARDEN_{k}:BOOL=ON" in cache for k in ("LARGE_POOL", "LEAF_MAINTENANCE")) and "TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE:BOOL=OFF" in cache
    for tool in ("inspect", "replay"):
        command = [str((build / f"toy-factory-garden-{tool}").resolve()), str(model), "rainfed-crowded",
                   "neural-no-night-growth", "123", "--ticks", "60"]
        ordinary = ["--leaf-policy", "selective", "--disturbance-seed", str(audit.trial.bank.SCHEDULE)]
        if tool == "inspect": ordinary += ["--ecology"]
        bad = (["--root-bootstrap-after", "0"], ["--root-bootstrap-after", "16"],
               ["--root-bootstrap-after", "75"], ["--root-bootstrap-after"],
               ["--root-bootstrap-after", "15", "--root-bootstrap-after", "15"],
               ["--root-bootstrap-after", "15", "--gap-at", "30"])
        for options in bad:
            result = subprocess.run(command + ordinary + options, capture_output=True, timeout=10)
            assert result.returncode == 2, (tool, options, result.stderr)
        if not enabled:
            result = subprocess.run(command + ["--root-bootstrap-after", "15"], capture_output=True, timeout=10)
            assert result.returncode == 2
        elif model.exists():
            values = []
            for options in ([], ["--root-bootstrap-after", "15"]):
                result = subprocess.run(command + ordinary + options, capture_output=True, text=True, timeout=15)
                assert result.returncode == 0, result.stderr
                rows = [json.loads(l) for l in result.stdout.splitlines()]
                values.append([r for r in rows if r.get("type") == "world" or "schema_version" in r])
            assert len(values[0]) == len(values[1])
            for a, b in zip(*values, strict=True):
                assert b["root_bootstrap_rule"] == audit.RULE and b["root_bootstrap_after"] == 15
                assert a == {k: v for k, v in b.items() if not k.startswith("root_bootstrap_")}
    print("Native bootstrap CLI guards passed; positive pre-birth equivalence:",
          "passed" if enabled and model.exists() else "not applicable/model unavailable")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path)
    args = parser.parse_args()
    if args.build:
        cli_checks(args.build)
    unittest.main(argv=[sys.argv[0]])
