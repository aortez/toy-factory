/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "game_world.h"
#include "garden_damage.h"
#include "garden_light.h"
#include "graphics_raster.h"
#include "portable_util.h"
#include "simulator.h"

#define CHECK(condition)                                                                           \
	do {                                                                                       \
		if (!(condition)) {                                                                \
			fprintf(stderr, "check failed at %s:%d: %s\n", __FILE__, __LINE__,         \
				#condition);                                                       \
			return 1;                                                                  \
		}                                                                                  \
	} while (0)

static uint16_t partial_frame[PICOSYSTEM_GRAPHICS_WIDTH * PICOSYSTEM_GRAPHICS_HEIGHT];

static struct picosystem_scene_snapshot empty_garden_snapshot(void)
{
	return (struct picosystem_scene_snapshot){
		.scene_id = PICOSYSTEM_GAME_SCENE_GARDEN,
		.payload.garden =
			{
				.cursor_column = 0U,
				.cursor_row = 0U,
				.selected_tool = PICOSYSTEM_GARDEN_TOOL_FLOWER_SEED,
				.auto_target_column = 0U,
				.auto_target_row = 0U,
				.auto_target_tool = PICOSYSTEM_GARDEN_TOOL_FLOWER_SEED,
				.sun_phase = PICOSYSTEM_GARDEN_SUN_NOON_PHASE,
				.sun_strength = UINT8_MAX,
			},
	};
}

static int expect_region(struct picosystem_garden_damage_iterator *iterator,
			 const struct picosystem_garden_damage_plan *plan, uint16_t x, uint16_t y,
			 uint16_t width, uint16_t height)
{
	struct picosystem_rect region;
	const int result = picosystem_garden_damage_next_region(plan, iterator, &region);
	CHECK(result == 1);
	CHECK(region.x == x);
	CHECK(region.y == y);
	CHECK(region.width == width);
	CHECK(region.height == height);
	return 0;
}

static int build_snapshot(const struct toy_factory_simulator *simulator, uint32_t sequence,
			  struct picosystem_scene_snapshot *snapshot)
{
	return picosystem_game_snapshot_build(&simulator->world, sequence, 0U,
					      simulator->world.logic_tick_count, snapshot);
}

static int verify_partial_reconstruction(const struct picosystem_scene_snapshot *presented,
					 const struct picosystem_scene_snapshot *current)
{
	int err = picosystem_scene_render_full(presented);
	struct picosystem_garden_damage_plan plan;
	if (err == 0) {
		err = picosystem_garden_damage_plan_build(presented, current, &plan);
	}
	struct picosystem_garden_damage_iterator iterator;
	if (err == 0) {
		err = picosystem_garden_damage_iterator_init(&iterator);
	}
	while (err == 0) {
		struct picosystem_rect region;
		const int next = picosystem_garden_damage_next_region(&plan, &iterator, &region);
		if (next < 0) {
			err = next;
			break;
		}
		if (next == 0) {
			break;
		}
		err = picosystem_scene_render_region(current, &region);
	}
	if (err != 0) {
		return err;
	}

	const uint32_t partial_crc32 = picosystem_graphics_raster_crc32();
	memcpy(partial_frame, picosystem_graphics_raster_pixels(), sizeof(partial_frame));
	err = picosystem_scene_render_full(current);
	if (err != 0) {
		return err;
	}
	const uint32_t full_crc32 = picosystem_graphics_raster_crc32();
	if (memcmp(partial_frame, picosystem_graphics_raster_pixels(), sizeof(partial_frame)) !=
	    0) {
		fprintf(stderr, "partial reconstruction mismatch: %08x != %08x\n", partial_crc32,
			full_crc32);
		return -EILSEQ;
	}
	return 0;
}

static int verify_interactive_transitions(void)
{
	struct toy_factory_simulator simulator;
	int err = toy_factory_simulator_init(&simulator, PICOSYSTEM_GAME_SCENE_GARDEN);
	struct picosystem_scene_snapshot presented;
	uint32_t sequence = 1U;
	if (err == 0) {
		err = build_snapshot(&simulator, sequence, &presented);
	}

	const enum picosystem_game_scene_action actions[] = {
		PICOSYSTEM_GAME_SCENE_ACTION_USE_TOOL,
		PICOSYSTEM_GAME_SCENE_ACTION_CYCLE_TOOL,
		PICOSYSTEM_GAME_SCENE_ACTION_CYCLE_TOOL,
		PICOSYSTEM_GAME_SCENE_ACTION_PRIMARY,
	};
	for (size_t index = 0U; (err == 0) && (index < TOY_FACTORY_ARRAY_SIZE(actions)); ++index) {
		err = toy_factory_simulator_apply_action(&simulator, actions[index]);
		struct picosystem_scene_snapshot current;
		if (err == 0) {
			err = build_snapshot(&simulator, ++sequence, &current);
		}
		if (err == 0) {
			err = verify_partial_reconstruction(&presented, &current);
		}
		if (err != 0) {
			fprintf(stderr, "interactive action %zu failed: %d\n", index, err);
		}
		if (err == 0) {
			presented = current;
		}
	}

	const struct picosystem_game_input left = {.horizontal = -1};
	if (err == 0) {
		err = toy_factory_simulator_step(&simulator, &left, 1U);
	}
	struct picosystem_scene_snapshot current;
	if (err == 0) {
		err = build_snapshot(&simulator, ++sequence, &current);
	}
	if (err == 0) {
		err = verify_partial_reconstruction(&presented, &current);
	}
	if (err != 0) {
		fprintf(stderr, "interactive cursor transition failed: %d\n", err);
	}
	if (err == 0) {
		presented = current;
	}

	const struct picosystem_game_input neutral = {0};
	if (err == 0) {
		err = toy_factory_simulator_step(&simulator, &neutral, 30U);
	}
	if (err == 0) {
		err = build_snapshot(&simulator, ++sequence, &current);
	}
	if (err == 0) {
		err = verify_partial_reconstruction(&presented, &current);
	}
	if (err != 0) {
		fprintf(stderr, "interactive growth transition failed: %d\n", err);
	}
	return err;
}

int main(void)
{
	struct picosystem_scene_snapshot presented = empty_garden_snapshot();
	struct picosystem_scene_snapshot current = presented;
	struct picosystem_garden_damage_plan plan;
	struct picosystem_garden_damage_iterator iterator;
	struct picosystem_rect region;

	CHECK(picosystem_garden_damage_plan_build(NULL, &current, &plan) == -EINVAL);
	CHECK(picosystem_garden_damage_plan_build(&presented, &current, NULL) == -EINVAL);
	CHECK(picosystem_garden_damage_iterator_init(NULL) == -EINVAL);
	CHECK(picosystem_garden_damage_next_region(NULL, &iterator, &region) == -EINVAL);
	CHECK(picosystem_garden_damage_plan_build(&presented, &current, &plan) == 0);
	CHECK(plan.dirty_tile_count == 0U);
	CHECK(picosystem_garden_damage_iterator_init(&iterator) == 0);
	CHECK(picosystem_garden_damage_next_region(&plan, &iterator, &region) == 0);

	/* A moving sun damages the bounded old/new icon area and reconstructs exactly. */
	current.payload.garden.sun_phase = PICOSYSTEM_GARDEN_SUN_NOON_PHASE + 1U;
	current.payload.garden.sun_strength = 251U;
	CHECK(picosystem_garden_damage_plan_build(&presented, &current, &plan) == 0);
	CHECK(plan.dirty_tile_count == 4U);
	CHECK(picosystem_garden_damage_iterator_init(&iterator) == 0);
	CHECK(expect_region(&iterator, &plan, 112U, 32U, 16U, 16U) == 0);
	CHECK(picosystem_garden_damage_next_region(&plan, &iterator, &region) == 0);
	CHECK(verify_partial_reconstruction(&presented, &current) == 0);
	current = empty_garden_snapshot();
	current.payload.garden.sun_ray_step_x_q4 = PICOSYSTEM_GARDEN_SUN_MAX_RAY_STEP_X_Q4 + 1;
	CHECK(picosystem_garden_damage_plan_build(&presented, &current, &plan) == -ERANGE);
	CHECK(plan.dirty_tile_count == 0U);

	/* Raw diffusion within one rendered moisture band does not damage a tile. */
	current = presented;
	presented.payload.garden.moisture[0] = 12U;
	current.payload.garden.moisture[0] = 47U;
	CHECK(picosystem_garden_damage_plan_build(&presented, &current, &plan) == 0);
	CHECK(plan.dirty_tile_count == 0U);

	/* Two vertically adjacent threshold crossings coalesce into one 8 x 16 region. */
	presented.payload.garden.moisture[0] = 47U;
	current.payload.garden.moisture[0] = 48U;
	presented.payload.garden.moisture[PICOSYSTEM_GARDEN_GRID_COLUMNS] = 11U;
	current.payload.garden.moisture[PICOSYSTEM_GARDEN_GRID_COLUMNS] = 12U;
	CHECK(picosystem_garden_damage_plan_build(&presented, &current, &plan) == 0);
	CHECK(plan.dirty_tile_count == 2U);
	CHECK(picosystem_garden_damage_iterator_init(&iterator) == 0);
	CHECK(expect_region(&iterator, &plan, 8U, 144U, 8U, 16U) == 0);
	CHECK(picosystem_garden_damage_next_region(&plan, &iterator, &region) == 0);

	/* Dormancy, readiness, and germination damage only the seed's soil tile. */
	presented = empty_garden_snapshot();
	current = presented;
	current.payload.garden.seed_count = 1U;
	current.payload.garden.seeds[0] = (struct picosystem_scene_garden_seed){
		.x = 20U,
		.style = PICOSYSTEM_GARDEN_SPECIES_FLOWER,
	};
	CHECK(picosystem_garden_damage_plan_build(&presented, &current, &plan) == 0);
	CHECK(plan.dirty_tile_count == 1U);
	CHECK(picosystem_garden_damage_iterator_init(&iterator) == 0);
	CHECK(expect_region(&iterator, &plan, 16U, 144U, 8U, 8U) == 0);
	CHECK(picosystem_garden_damage_next_region(&plan, &iterator, &region) == 0);
	CHECK(verify_partial_reconstruction(&presented, &current) == 0);
	presented = current;
	current.payload.garden.seeds[0].style |=
		PICOSYSTEM_SCENE_GARDEN_SEED_STYLE_DORMANCY_COMPLETE;
	CHECK(verify_partial_reconstruction(&presented, &current) == 0);
	presented = current;
	current.payload.garden.seed_count = 0U;
	CHECK(verify_partial_reconstruction(&presented, &current) == 0);
	current = empty_garden_snapshot();
	current.payload.garden.seed_count = 1U;
	current.payload.garden.seeds[0].x = 20U;
	current.payload.garden.seeds[0].style = UINT8_MAX;
	CHECK(picosystem_garden_damage_plan_build(&presented, &current, &plan) == -ERANGE);
	presented = empty_garden_snapshot();
	current = presented;
	current.payload.garden.seed_count = 1U;
	current.payload.garden.seeds[0].x = 0U;
	CHECK(verify_partial_reconstruction(&presented, &current) == 0);
	presented = current;
	current.payload.garden.seeds[0].x = PICOSYSTEM_GRAPHICS_WIDTH - 1U;
	CHECK(verify_partial_reconstruction(&presented, &current) == 0);

	presented = empty_garden_snapshot();
	current = presented;
	current.payload.garden.cursor_column = 2U;
	CHECK(picosystem_garden_damage_plan_build(&presented, &current, &plan) == 0);
	CHECK(plan.dirty_tile_count == 2U);
	CHECK(picosystem_garden_damage_iterator_init(&iterator) == 0);
	CHECK(expect_region(&iterator, &plan, 8U, 32U, 8U, 8U) == 0);
	CHECK(expect_region(&iterator, &plan, 24U, 32U, 8U, 8U) == 0);
	CHECK(picosystem_garden_damage_next_region(&plan, &iterator, &region) == 0);

	presented = empty_garden_snapshot();
	current = presented;
	presented.payload.garden.node_count = 2U;
	current.payload.garden.node_count = 2U;
	presented.payload.garden.nodes[0] = (struct picosystem_scene_garden_node){
		.x = 8U,
		.y = 40U,
	};
	current.payload.garden.nodes[0] = presented.payload.garden.nodes[0];
	presented.payload.garden.nodes[1] = (struct picosystem_scene_garden_node){
		.x = 16U,
		.y = 40U,
		.parent_distance = 1U,
		.style = PICOSYSTEM_GARDEN_SPECIES_FLOWER,
	};
	current.payload.garden.nodes[1] = presented.payload.garden.nodes[1];
	current.payload.garden.nodes[1].growth_progress = 1U;
	CHECK(picosystem_garden_damage_plan_build(&presented, &current, &plan) == 0);
	CHECK(plan.dirty_tile_count == 2U);
	CHECK(picosystem_garden_damage_iterator_init(&iterator) == 0);
	CHECK(expect_region(&iterator, &plan, 8U, 40U, 16U, 8U) == 0);
	CHECK(picosystem_garden_damage_next_region(&plan, &iterator, &region) == 0);
	CHECK(verify_partial_reconstruction(&presented, &current) == 0);

	/* Stress, death, and tissue removal all reconstruct from bounded damage. */
	presented = current;
	current.payload.garden.nodes[1].growth_progress = UINT8_MAX;
	current.payload.garden.nodes[1].style |= PICOSYSTEM_SCENE_GARDEN_STYLE_LEAF;
	CHECK(verify_partial_reconstruction(&presented, &current) == 0);
	presented = current;
	current.payload.garden.nodes[1].style |= PICOSYSTEM_SCENE_GARDEN_STYLE_STRESSED;
	CHECK(verify_partial_reconstruction(&presented, &current) == 0);
	presented = current;
	current.payload.garden.nodes[1].style &= (uint8_t)~PICOSYSTEM_SCENE_GARDEN_STYLE_STRESSED;
	current.payload.garden.nodes[1].style |= PICOSYSTEM_SCENE_GARDEN_STYLE_DEAD;
	current.payload.garden.nodes[1].growth_progress = 48U;
	CHECK(verify_partial_reconstruction(&presented, &current) == 0);
	presented = current;
	current.payload.garden.nodes[1].growth_progress = 0U;
	CHECK(verify_partial_reconstruction(&presented, &current) == 0);

	current.payload.garden.nodes[1].parent_distance = 2U;
	CHECK(picosystem_garden_damage_plan_build(&presented, &current, &plan) == -ERANGE);
	CHECK(plan.dirty_tile_count == 0U);
	current = empty_garden_snapshot();
	current.scene_id = PICOSYSTEM_GAME_SCENE_HOURGLASS;
	CHECK(picosystem_garden_damage_plan_build(&presented, &current, &plan) == -ENOTSUP);
	CHECK(plan.dirty_tile_count == 0U);
	CHECK(verify_interactive_transitions() == 0);
	return 0;
}
