/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "simulator.h"

#include <errno.h>
#include <stddef.h>
#include <stdint.h>

#include "graphics_raster.h"

int toy_factory_simulator_init(struct toy_factory_simulator *simulator,
			       enum picosystem_game_scene_id scene_id)
{
	if (simulator == NULL) {
		return -EINVAL;
	}

	*simulator = (struct toy_factory_simulator){0};
	return toy_factory_simulator_reset(simulator, scene_id);
}

int toy_factory_simulator_reset(struct toy_factory_simulator *simulator,
				enum picosystem_game_scene_id scene_id)
{
	if (simulator == NULL) {
		return -EINVAL;
	}

	const int err = picosystem_game_world_reset_scene(&simulator->world, scene_id);
	if (err != 0) {
		return err;
	}

	simulator->rendered = false;
	return 0;
}

int toy_factory_simulator_step(struct toy_factory_simulator *simulator,
			       const struct picosystem_game_input *input, uint32_t tick_count)
{
	if ((simulator == NULL) || (input == NULL)) {
		return -EINVAL;
	}

	for (uint32_t tick = 0U; tick < tick_count; ++tick) {
		const int err = picosystem_game_world_step(&simulator->world, input);
		if (err != 0) {
			return err;
		}
	}

	simulator->rendered = false;
	return 0;
}

int toy_factory_simulator_apply_action(struct toy_factory_simulator *simulator,
				       enum picosystem_game_scene_action action)
{
	if (simulator == NULL) {
		return -EINVAL;
	}

	const int err = picosystem_game_world_apply_scene_action(&simulator->world, action);
	if (err == 0) {
		simulator->rendered = false;
	}
	return err;
}

int toy_factory_simulator_render(struct toy_factory_simulator *simulator)
{
	if (simulator == NULL) {
		return -EINVAL;
	}

	const uint32_t sequence = simulator->snapshot_sequence + 1U;
	int err = picosystem_game_snapshot_build(&simulator->world, sequence, 0U,
						 (int64_t)simulator->world.logic_tick_count,
						 &simulator->snapshot);
	if (err != 0) {
		return err;
	}

	err = picosystem_scene_render_full(&simulator->snapshot);
	if (err != 0) {
		return err;
	}

	simulator->snapshot_sequence = sequence;
	simulator->rendered = true;
	return 0;
}

uint32_t toy_factory_simulator_state_hash(const struct toy_factory_simulator *simulator)
{
	if (simulator == NULL) {
		return 0U;
	}

	return picosystem_game_world_hash(&simulator->world);
}

uint32_t toy_factory_simulator_framebuffer_crc32(const struct toy_factory_simulator *simulator)
{
	if ((simulator == NULL) || !simulator->rendered) {
		return 0U;
	}

	return picosystem_graphics_raster_crc32();
}
