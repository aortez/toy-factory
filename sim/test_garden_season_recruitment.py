#!/usr/bin/env python3
"""Decision-stage classification, trace rejection and ordinary-host replay neutrality."""

import argparse
import copy
import io
import json
from pathlib import Path
import subprocess
import unittest

import garden_season_recruitment as audit
from garden_season_recruitment_evidence import portable_reference
from garden_seasons import DAY_TICKS, run_case


class ReceiptTests(unittest.TestCase):
    @staticmethod
    def fixture():
        parents = {1: {"id": 1, "parent": 0, "birth_tick": 0, "death_tick": None,
                       "generation": 0, "species": "flower"},
                   2: {"id": 2, "parent": 1, "birth_tick": 15, "death_tick": None,
                       "generation": 1, "species": "flower"}}
        previous = {"tick": 0, "births": 0, "expired": 0, "created": 2, "deaths": 0}
        sites = [32] * 28
        sites[14] = 0
        first = {"parent": 1, "child": 2, "generation": 1, "species": 0, "age": 8,
                 "column": 14, "nodes": 4, "plants": 1, "moisture": 12, "light": 80,
                 "blockers": 0, "outcome": 2, "sites": sites}
        second = {**first, "child": 0, "nodes": 8, "plants": 2, "blockers": 32,
                  "outcome": 0, "sites": [32] * 28}
        row = {"tick": 15, "births": 1, "expired": 0, "created": 2, "deaths": 0,
               "climate": {"cold": False}, "support": [1 << 14, 0, 0],
               "sites_before": sites, "sites_after": [32] * 28,
               "stages": [[4, 1, 2], [4, 1, 2], [8, 2, 1], [8, 2, 1], [8, 2, 1]],
               "attempts": [first, second]}
        return row, previous, parents

    def test_sequential_success_and_consumed_opening(self):
        row, previous, parents = self.fixture()
        stats, masks, births = audit.step_metrics(row, previous, parents)
        self.assertEqual(births, [2])
        self.assertEqual(stats["births_without_post_step_opening"], 1)
        self.assertEqual(stats["ready_steps"], 1)
        self.assertEqual(stats["mature_checks"], 2)
        self.assertEqual(masks, {0: 1, 32: 1})

    @staticmethod
    def blocked_fixture():
        row, previous, parents = ReceiptTests.fixture()
        row["births"] = 0
        row["stages"] = [[4, 1, 2] for _ in range(5)]
        for a in row["attempts"]:
            a.update(child=0, column=20, nodes=4, plants=1, outcome=0, blockers=32,
                     sites=list(row["sites_before"]))
        return row, previous, parents

    def test_failed_landing_is_not_unreachable_if_parent_can_reach(self):
        row, previous, parents = self.blocked_fixture()
        stats, _, _ = audit.step_metrics(row, previous, parents)
        self.assertEqual(stats["missed_landing_steps"], 1)
        self.assertEqual(stats["missed_within_living_support_steps"], 1)
        row["support"] = [1 << 20, 0, 0]
        stats, _, _ = audit.step_metrics(row, previous, parents)
        self.assertEqual(stats["missed_outside_living_support_steps"], 1)

    def test_structural_versus_environmental_blocks(self):
        for mask, structural in ((32, False), (64, True)):
            row, previous, parents = self.blocked_fixture()
            row["climate"]["cold"] = mask == 64
            row["sites_before"] = [mask] * 28
            for a in row["attempts"]:
                a.update(blockers=mask, sites=[mask] * 28)
            stats, _, _ = audit.step_metrics(row, previous, parents)
            self.assertEqual(stats["environment_blocked_steps"], structural)
            self.assertEqual(stats["no_structural_space_steps"], not structural)
            self.assertEqual(stats["ready_steps"], 0)

    def test_dormancy_and_expiry_are_separate(self):
        row, previous, parents = self.blocked_fixture()
        row["expired"] = 1
        row["stages"][2:] = [[4, 1, 1] for _ in range(3)]
        row["attempts"][0].update(age=8192, outcome=1, blockers=0, light=0, moisture=0,
                                  sites=[0] * 28)
        row["attempts"][1].update(age=7, blockers=33)
        stats, masks, births = audit.step_metrics(row, previous, parents)
        self.assertEqual((stats["expired"], stats["dormant_checks"], stats["mature_checks"]), (1, 1, 0))
        self.assertEqual(stats["ready_no_mature_seed_steps"], 1)
        self.assertEqual(masks, {})
        self.assertEqual(births, [])

    def test_reject_inconsistent_receipts(self):
        mutations = [lambda r: r.update(tick=30),
                     lambda r: r["attempts"].pop(),
                     lambda r: r["attempts"][1].update(nodes=4),
                     lambda r: r["attempts"][0].update(outcome=0),
                     lambda r: r["attempts"][0].update(child=999),
                     lambda r: r["attempts"][0].update(age=8192),
                     lambda r: r["attempts"][0].update(moisture=0),
                     lambda r: r["attempts"][0].update(parent=999),
                     lambda r: r["attempts"][0].update(species=1),
                     lambda r: r["attempts"][0].update(generation=9),
                     lambda r: r.update(births=0),
                     lambda r: r["sites_before"].pop(),
                     lambda r: r.update(support=[1 << 28, 0, 0]),
                     lambda r: r["stages"][2].__setitem__(2, 2)]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                row, previous, parents = self.fixture()
                mutate(row)
                with self.assertRaises(RuntimeError):
                    audit.step_metrics(row, previous, parents)


def native_checks(build: Path) -> None:
    binary = build / "toy-factory-garden-recruitment-audit"
    command = [str(binary), "rainfed", "adaptive", "123", "seasonal",
               str(16 * DAY_TICKS), str(16 * DAY_TICKS), str(32 * DAY_TICKS)]
    text = subprocess.check_output(command, text=True)
    require = audit.require
    require(text == subprocess.check_output(command, text=True), "Unstable native trace")
    case = run_case(build / "toy-factory-garden-inspect", 32, "rainfed", "adaptive", 123, "seasonal")
    summary = audit.analyze(iter(io.StringIO(text)), case, 16 * DAY_TICKS, 16 * DAY_TICKS, 32 * DAY_TICKS)
    require(len(summary["daily_hashes"]) == 33, "Lost native checkpoints")
    require(audit.analyze(iter(io.StringIO(text)), portable_reference(case),
                          16 * DAY_TICKS, 16 * DAY_TICKS, 32 * DAY_TICKS) == summary,
            "Portable reference lost required evidence")
    rows = [json.loads(line) for line in text.splitlines()]
    mutations = [lambda r: r.pop(), lambda r: r.pop(1), lambda r: r.pop(2),
                 lambda r: r[0].update(seed="0000007c"),
                 lambda r: r[0].update(dispersal="wide-v1"),
                 lambda r: r[0].update(seed_capacity=16),
                 lambda r: r[1].update(hash="00000000"),
                 lambda r: r.append(r[-1]),
                 lambda r: r[2]["sites_before"].__setitem__(0, 128)]
    for mutate in mutations:
        other = copy.deepcopy(rows)
        mutate(other)
        try:
            audit.analyze(iter(json.dumps(r) for r in other), case,
                          16 * DAY_TICKS, 16 * DAY_TICKS, 32 * DAY_TICKS)
        except RuntimeError:
            pass
        else:
            raise AssertionError("Accepted corrupt native trace")
    for index, value in ((1, "irrigated"), (2, "neural-reference"), (3, "0"), (3, "-1"),
                         (3, "4294967296"), (4, "summer"), (5, "7"), (6, "0"), (7, "9999999")):
        invalid = command.copy()
        invalid[index] = value
        result = subprocess.run(invalid, capture_output=True, text=True)
        require(result.returncode == 2 and not result.stdout, "Invalid CLI was accepted")
    with open("/dev/full", "wb") as full:
        require(subprocess.run([*command[:5], "0", "0", "15"], stdout=full,
                               stderr=subprocess.PIPE).returncode != 0, "Output error was ignored")
    print("Native exact recruitment: repeated traces, 33 historical daily hashes, rejection and output checks passed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    args = parser.parse_args()
    results = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(ReceiptTests))
    if not results.wasSuccessful():
        return 1
    native_checks(args.build)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
