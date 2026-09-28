#!/usr/bin/env python3
"""Design-only landing sensor invariants and host/Cortex-M0+ layout budgets."""

import argparse
from dataclasses import replace
import random
import subprocess
import unittest

import garden_landing_contract as draft
import garden_season_flower_sites as flower

CC = None
ARM = False


def terrain(water=12, light=80, plants=()):
    return draft.terrain([water] * 28, [light] * 28, plants)


class LandingContractTests(unittest.TestCase):
    def test_spacing_counts_dead_slots_and_overlapping_live_neighbors(self):
        t = terrain(plants=((4, False), (8, True)))
        self.assertEqual(t.occupied[:12], (0, 0, 1, 1, 1, 1, 3, 2, 2, 2, 2, 0))
        h = draft.reset(t)
        self.assertEqual(draft.project(h, 0, 0)[:2], (0, 109))
        cleared = terrain(plants=((4, False),))
        self.assertEqual(cleared.occupied[8], 0)
        self.assertEqual(t.occupied[8], draft.DEAD)

    def test_every_wide_origin_trait_matches_existing_branch_geometry(self):
        for origin in range(28):
            for trait in range(-2, 3):
                self.assertEqual(list(draft.landings(origin, trait)), flower.placements(origin, trait))
                self.assertTrue(all(0 <= p < 28 for p in draft.landings(origin, trait, "narrow-v1")))
        self.assertEqual(draft.landings(0, 0), tuple(c for c in range(3, 10) for _ in range(2)))
        for pixel, column in ((0, 0), (15, 0), (16, 1), (231, 27), (255, 27)):
            self.assertEqual(draft.pixel_column(pixel), column)

    def test_projection_counts_reflected_multiplicity_not_unique_sites(self):
        # At origin 3, columns 0 and 6..12 have unequal nominal branch mass.
        water = tuple(255 if c == 6 else 0 for c in range(28))
        h = draft.reset(draft.terrain(water, [80] * 28, ()))
        positions = draft.landings(3, 0)
        expected = (positions.count(6) * 255 + 7) // 14
        unique_mean = (255 + len(set(positions)) // 2) // len(set(positions))
        self.assertEqual(draft.project(h, 3, 0)[2], expected)
        self.assertNotEqual(expected, unique_mean)

    def test_zero_warmup_and_integer_trace_definition(self):
        h = draft.reset(terrain())
        self.assertEqual((h.tick, h.samples), (0, 0))
        self.assertEqual(draft.project(h, 14, 0)[4:], (0, 0, 0, 0))
        h = draft.sample(h, 1, terrain())
        self.assertEqual(h.traces, ((255,) * 28,) * 4)
        self.assertEqual(draft.project(h, 14, 0)[4:], (1, 1, 1, 1))
        for tick in range(2, 257):
            h = draft.sample(h, tick, terrain())
        self.assertEqual(h.samples, 256)
        self.assertTrue(159 <= draft.project(h, 14, 0)[4] <= 162)
        # An EMA is deliberately not a full-window occupancy fraction.
        self.assertLess(draft.project(h, 14, 0)[4], 255)
        h = draft.sample(h, 257, terrain())
        self.assertEqual(h.samples, 256)

    def test_integer_traces_are_bounded_and_close_to_exact_decay(self):
        generator = random.Random(123)
        for initial in (0, draft.MAX_Q):
            q, exact = initial, float(initial)
            for _ in range(4096):
                wet = generator.randrange(4) == 0
                q = draft.trace_step(q, wet)
                exact += ((draft.MAX_Q if wet else 0) - exact) / 256
                self.assertTrue(0 <= q <= draft.MAX_Q)
                self.assertLess(abs(q - exact), 256)
        self.assertEqual(draft.trace_step(255, False), 255)  # Defined truncation dead band.
        self.assertEqual(draft.trace_step(256, False), 255)

    def test_marginal_histories_do_not_invent_joint_opportunity(self):
        h = draft.reset(terrain(0, 24))
        for tick in range(1, 513):
            h = draft.sample(h, tick, terrain(12, 24) if tick & 1 else terrain(0, 80))
        wet, light, joint, open_joint = draft.project(h, 14, 0)[4:]
        self.assertGreater(wet, 100)
        self.assertGreater(light, 100)
        self.assertEqual((joint, open_joint), (0, 0))
        h = draft.sample(h, 513, terrain())
        self.assertGreater(h.traces[2][0], 0)

    def test_open_joint_history_retains_occupancy_separately(self):
        t = terrain(plants=((3, False), (9, False), (15, False), (21, False), (27, False)))
        h = draft.reset(t)
        for tick in range(1, 129):
            h = draft.sample(h, tick, t)
        self.assertGreater(h.traces[2][15], 0)
        self.assertEqual(h.traces[3][15], 0)
        h = draft.sample(h, 129, terrain())
        self.assertGreater(h.traces[3][15], 0)
        self.assertLess(h.traces[3][15], h.traces[2][15])

    def test_queries_are_pure_order_independent_and_column_anchored(self):
        t = draft.terrain(tuple(range(28)), [100] * 28, ())
        h = draft.sample(draft.reset(t), 1, t)
        saved = h
        queries = [(20, (15, 17, 20, 23, 25)), (220, (215, 217, 220, 223, 225))]
        results = [draft.packet(h, tip, xs, 8, 0) for tip, xs in queries]
        reversed_results = [draft.packet(h, tip, xs, 8, 0) for tip, xs in reversed(queries)]
        self.assertEqual(results, list(reversed(reversed_results)))
        self.assertIs(h, saved)
        self.assertEqual(h.tick, 1)
        self.assertNotEqual(results[0]["values"][0], results[1]["values"][0])
        # The target soil's past is not reassigned to a moving body's previous tip.
        self.assertEqual(results[1]["values"][0], draft.project(h, draft.pixel_column(220), 0))

    def test_reset_replay_and_invalid_steps_are_transactional(self):
        t = terrain()
        initial = draft.reset(t)
        a = draft.sample(initial, 1, t)
        b = draft.sample(draft.reset(t), 1, t)
        self.assertEqual(a, b)
        for tick in (0, 1, 3, True, 0x100000000):
            with self.assertRaises(ValueError):
                draft.sample(a, tick, t)
        self.assertEqual(a, b)
        self.assertEqual(draft.reset(t), initial)
        end = replace(a, tick=0xffffffff, samples=256)
        with self.assertRaises(ValueError):
            draft.sample(end, 0x100000000, t)

    def test_root_invalid_candidates_and_base_origin_negative_control(self):
        h = draft.reset(draft.terrain(tuple(range(28)), [100] * 28, ()))
        result = draft.packet(h, 8, (None, None, 8, 11, 13), 14, 0)
        self.assertEqual(result["valid"], 0b111001)
        self.assertEqual(result["values"][1:3], ((0,) * 8,) * 2)
        root = draft.packet(h, 8, (None, None, 8, 11, 13), 14, 0, stem=False)
        self.assertEqual(root["valid"], 0)
        self.assertEqual(root["values"], ((0,) * 8,) * 6)
        base = draft.packet(h, 100, (95, 97, 100, 103, 105), 14, 0, origin_rule="base")
        self.assertEqual(len(set(base["values"])), 1)
        other_tip = draft.packet(h, 220, (215, 217, 220, 223, 225), 14, 0, origin_rule="base")
        self.assertEqual(base, other_tip)

    def test_real_shoot_offsets_need_at_most_three_distinct_columns(self):
        maximum = 0
        for x in range(8, 232):
            positions = (x, *(x + dx for dx in (-5, -3, 0, 3, 5) if 8 <= x + dx < 232))
            maximum = max(maximum, len({draft.pixel_column(p) for p in positions}))
        self.assertEqual(maximum, 3)

    def test_bad_inputs_are_rejected(self):
        for water, light, plants in (([0] * 27, [0] * 28, ()), ([256] * 28, [0] * 28, ()),
                                     ([0] * 28, [0] * 28, ((28, False),)),
                                     ([0] * 28, [0] * 28, ((2, 1),))):
            with self.assertRaises(ValueError):
                draft.terrain(water, light, plants)
        for origin, trait, rule in ((28, 0, "wide-v1"), (0, 3, "wide-v1"), (0, 0, "unknown")):
            with self.assertRaises(ValueError):
                draft.landings(origin, trait, rule)
        with self.assertRaises(ValueError):
            draft.packet(draft.reset(terrain()), 8, (8,) * 5, 0, 0, origin_rule="unknown")

    def test_c_layout_budget_without_changing_current_abi(self):
        if CC is None:
            self.skipTest("compiler not supplied")
        source = r'''
#include "garden_agent_neural.h"
#include <stddef.h>

struct landing_cache_draft {
        uint32_t ecology_tick;
        uint16_t warmup_samples;
        uint8_t version;
        uint8_t flags;
        uint16_t traces[4][28];
        uint8_t water[28];
        uint8_t light[28];
        uint8_t occupied[28];
};
struct landing_packet_draft {
        uint8_t version;
        uint8_t valid;
        uint16_t warmup_samples;
        uint8_t values[6][8];
};
struct observation_budget_draft {
        struct picosystem_garden_agent_observation current;
        struct landing_packet_draft landing;
};
struct features_budget_draft {
        int8_t common[32 + 9];
        int8_t candidates[5][9 + 8];
};
/* A weights-only budget, not the future wire layout or a loadable model. */
struct model_budget_draft {
        struct picosystem_garden_neural_model current;
        int8_t common_extra_weights[16][9];
        int8_t candidate_extra_weights[8][8];
};
_Static_assert(sizeof(struct landing_cache_draft) == 316, "cache budget");
_Static_assert(offsetof(struct landing_cache_draft, traces) == 8, "trace alignment");
_Static_assert(sizeof(struct landing_packet_draft) == 52, "packet budget");
_Static_assert(sizeof(struct picosystem_garden_agent_observation) == 104, "current observation");
_Static_assert(sizeof(struct observation_budget_draft) == 156, "augmented observation budget");
_Static_assert(sizeof(struct picosystem_garden_neural_features) == 77, "current features");
_Static_assert(sizeof(struct features_budget_draft) == 126, "feature budget");
_Static_assert(sizeof(struct model_budget_draft) == 1412, "model budget");
_Static_assert(PICOSYSTEM_GARDEN_AGENT_OBSERVATION_VERSION == 4, "ABI unchanged");
_Static_assert(PICOSYSTEM_GARDEN_NEURAL_MODEL_VERSION == 1, "model unchanged");
_Static_assert(PICOSYSTEM_GARDEN_NEURAL_FEATURE_VERSION == 1, "features unchanged");
_Static_assert(PICOSYSTEM_GARDEN_NEURAL_MODEL_SIZE == 1204, "model bytes unchanged");
_Static_assert(PICOSYSTEM_GARDEN_GRID_COLUMNS == 28, "grid geometry");
_Static_assert(PICOSYSTEM_GARDEN_DAY_TICKS == 256, "trace timescale");
'''
        command = [CC, "-std=c11", "-Wall", "-Wextra", "-Werror", "-Wconversion", "-Wsign-conversion",
                   "-fsyntax-only", "-I", str(flower.ROOT / "src"), "-xc", "-"]
        if ARM:
            command[1:1] = ["-mcpu=cortex-m0plus", "-mthumb"]
        result = subprocess.run(command, input=source, text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cc")
    parser.add_argument("--arm", action="store_true")
    args, rest = parser.parse_known_args()
    CC, ARM = args.cc, args.arm
    unittest.main(argv=[__file__, *rest])
