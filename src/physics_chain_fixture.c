/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "physics_chain_fixture.h"

#include <errno.h>
#include <stddef.h>
#include <stdint.h>

#define CHAIN_FIXTURE_HALF_LENGTH_PIXELS 4
#define CHAIN_FIXTURE_HALF_HEIGHT_PIXELS 2
#define CHAIN_FIXTURE_PIN_X_PIXELS       128
#define CHAIN_FIXTURE_PIN_Y_PIXELS       112
#define CHAIN_FIXTURE_FIRST_BODY_ID      1U
#define CHAIN_FIXTURE_FIRST_JOINT_ID     301U
#define FIXED(value)                     PICOSYSTEM_PHYSICS_FIXED_FROM_INT(value)
#define RATIO(numerator, denominator)    PICOSYSTEM_PHYSICS_FIXED_RATIO(numerator, denominator)

_Static_assert(PICOSYSTEM_PHYSICS_CHAIN_FIXTURE_MAX_LINKS <= PICOSYSTEM_PHYSICS_MAX_BODIES,
	       "chain fixture links must fit body storage");
_Static_assert(PICOSYSTEM_PHYSICS_CHAIN_FIXTURE_MAX_LINKS <= PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS,
	       "chain fixture links must fit revolute-joint storage");

int picosystem_physics_chain_fixture_reset(struct picosystem_game_world *world, uint16_t link_count)
{
	if (world == NULL) {
		return -EINVAL;
	}
	if ((link_count < PICOSYSTEM_PHYSICS_CHAIN_FIXTURE_MIN_LINKS) ||
	    (link_count > PICOSYSTEM_PHYSICS_CHAIN_FIXTURE_MAX_LINKS)) {
		return -ERANGE;
	}

	int err = picosystem_physics_world_init(&world->physics, FIXED(5));
	if (err != 0) {
		return err;
	}
	world->logic_tick_count = 0U;

	for (uint16_t index = 0U; index < link_count; ++index) {
		const int32_t center_x =
			CHAIN_FIXTURE_PIN_X_PIXELS +
			((2 * (int32_t)index + 1) * CHAIN_FIXTURE_HALF_LENGTH_PIXELS);
		const struct picosystem_physics_box_config link = {
			.center = {.x = FIXED(center_x), .y = FIXED(CHAIN_FIXTURE_PIN_Y_PIXELS)},
			.half_extent = {.x = FIXED(CHAIN_FIXTURE_HALF_LENGTH_PIXELS),
					.y = FIXED(CHAIN_FIXTURE_HALF_HEIGHT_PIXELS)},
			.inverse_mass = PICOSYSTEM_PHYSICS_FIXED_ONE,
			.restitution = RATIO(1, 4),
			.friction = RATIO(1, 5),
			.id = (uint16_t)(CHAIN_FIXTURE_FIRST_BODY_ID + index),
		};
		err = picosystem_physics_world_add_box(&world->physics, &link);
		if (err != 0) {
			return err;
		}
	}

	for (uint16_t index = 0U; index < link_count; ++index) {
		struct picosystem_physics_revolute_joint_config joint = {
			.local_anchor_a = {.x = (index == 0U)
							? -FIXED(CHAIN_FIXTURE_HALF_LENGTH_PIXELS)
							: FIXED(CHAIN_FIXTURE_HALF_LENGTH_PIXELS)},
			.anchor_b = {.x = (index == 0U) ? FIXED(CHAIN_FIXTURE_PIN_X_PIXELS)
							: -FIXED(CHAIN_FIXTURE_HALF_LENGTH_PIXELS),
				     .y = (index == 0U) ? FIXED(CHAIN_FIXTURE_PIN_Y_PIXELS) : 0},
			.id = (uint16_t)(CHAIN_FIXTURE_FIRST_JOINT_ID + index),
			.body_a_id = (index == 0U)
					     ? CHAIN_FIXTURE_FIRST_BODY_ID
					     : (uint16_t)(CHAIN_FIXTURE_FIRST_BODY_ID + index - 1U),
			.body_b_id = (index == 0U)
					     ? PICOSYSTEM_PHYSICS_WORLD_BODY_ID
					     : (uint16_t)(CHAIN_FIXTURE_FIRST_BODY_ID + index),
		};
		err = picosystem_physics_world_add_revolute_joint(&world->physics, &joint);
		if (err != 0) {
			return err;
		}
	}

	return 0;
}
