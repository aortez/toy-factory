/* SPDX-License-Identifier: Apache-2.0 */

#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

#include "game_world.h"

#define EXPECTED_RESET_HASH          UINT32_C(0x482ffd98)
#define EXPECTED_RIGHT_30_HASH       UINT32_C(0xb8f03552)
#define EXPECTED_RIGHT_30_UP_15_HASH UINT32_C(0xe60b17ef)
#define SPRITE_SPEED_FIXED           (INT32_C(125) * PICOSYSTEM_GAME_FIXED_ONE)
#define SPRITE_MIN_X_FIXED                                                                         \
	((int32_t)PICOSYSTEM_GAME_SPRITE_MIN_X_PIXELS * PICOSYSTEM_GAME_FIXED_ONE)
#define SPRITE_MAX_X_FIXED                                                                         \
	((int32_t)PICOSYSTEM_GAME_SPRITE_MAX_X_PIXELS * PICOSYSTEM_GAME_FIXED_ONE)
#define SPRITE_MIN_Y_FIXED                                                                         \
	((int32_t)PICOSYSTEM_GAME_SPRITE_MIN_Y_PIXELS * PICOSYSTEM_GAME_FIXED_ONE)
#define SPRITE_MAX_Y_FIXED                                                                         \
	((int32_t)PICOSYSTEM_GAME_SPRITE_MAX_Y_PIXELS * PICOSYSTEM_GAME_FIXED_ONE)

static void assert_world_equal(const struct picosystem_game_world *left,
			       const struct picosystem_game_world *right)
{
	assert(left->sprite_x_fixed == right->sprite_x_fixed);
	assert(left->sprite_y_fixed == right->sprite_y_fixed);
	assert(left->velocity_x_fixed_per_second == right->velocity_x_fixed_per_second);
	assert(left->velocity_y_fixed_per_second == right->velocity_y_fixed_per_second);
	assert(left->logic_tick_count == right->logic_tick_count);
}

static void step_many(struct picosystem_game_world *world,
		      const struct picosystem_game_input *input, uint32_t count)
{
	for (uint32_t step = 0U; step < count; ++step) {
		assert(picosystem_game_world_step(world, input) == 0);
	}
}

static void test_canonical_reset_and_golden_replay(void)
{
	struct picosystem_game_world world = {
		.sprite_x_fixed = -1,
		.sprite_y_fixed = -1,
		.velocity_x_fixed_per_second = -1,
		.velocity_y_fixed_per_second = -1,
		.logic_tick_count = UINT32_MAX,
	};

	assert(picosystem_game_world_reset(&world) == 0);
	assert(world.sprite_x_fixed == (INT32_C(112) * PICOSYSTEM_GAME_FIXED_ONE));
	assert(world.sprite_y_fixed == (INT32_C(124) * PICOSYSTEM_GAME_FIXED_ONE));
	assert(world.velocity_x_fixed_per_second == SPRITE_SPEED_FIXED);
	assert(world.velocity_y_fixed_per_second == SPRITE_SPEED_FIXED);
	assert(world.logic_tick_count == 0U);
	assert(picosystem_game_world_hash(&world) == EXPECTED_RESET_HASH);

	const struct picosystem_game_input right = {.horizontal = 1};
	step_many(&world, &right, 30U);
	assert(world.logic_tick_count == 30U);
	assert(picosystem_game_world_hash(&world) == EXPECTED_RIGHT_30_HASH);

	const struct picosystem_game_input up = {.vertical = -1};
	step_many(&world, &up, 15U);
	assert(world.logic_tick_count == 45U);
	assert(picosystem_game_world_hash(&world) == EXPECTED_RIGHT_30_UP_15_HASH);

	assert(picosystem_game_world_reset(&world) == 0);
	assert(picosystem_game_world_hash(&world) == EXPECTED_RESET_HASH);
}

static void test_validation_preserves_state(void)
{
	struct picosystem_game_world world;
	assert(picosystem_game_world_reset(&world) == 0);

	const struct picosystem_game_world baseline = world;
	const struct picosystem_game_input invalid_horizontal = {.horizontal = 2};
	assert(picosystem_game_world_step(&world, &invalid_horizontal) == -ERANGE);
	assert_world_equal(&world, &baseline);

	const struct picosystem_game_input invalid_vertical = {.vertical = -2};
	assert(picosystem_game_world_step(&world, &invalid_vertical) == -ERANGE);
	assert_world_equal(&world, &baseline);

	const struct picosystem_game_input neutral = {0};
	world.sprite_x_fixed = SPRITE_MIN_X_FIXED - 1;
	const struct picosystem_game_world invalid_world = world;
	assert(picosystem_game_world_step(&world, &neutral) == -ERANGE);
	assert_world_equal(&world, &invalid_world);

	assert(picosystem_game_world_reset(&world) == 0);
	world.sprite_y_fixed = SPRITE_MAX_Y_FIXED + 1;
	const struct picosystem_game_world past_maximum = world;
	assert(picosystem_game_world_step(&world, &neutral) == -ERANGE);
	assert_world_equal(&world, &past_maximum);

	assert(picosystem_game_world_reset(&world) == 0);
	world.velocity_x_fixed_per_second = INT32_MIN;
	const struct picosystem_game_world invalid_velocity = world;
	assert(picosystem_game_world_step(&world, &neutral) == -ERANGE);
	assert_world_equal(&world, &invalid_velocity);

	assert(picosystem_game_world_reset(NULL) == -EINVAL);
	assert(picosystem_game_world_step(NULL, &neutral) == -EINVAL);
	assert(picosystem_game_world_step(&world, NULL) == -EINVAL);
	assert(picosystem_game_world_hash(NULL) == 0U);
}

static void test_bounded_motion_and_saturated_tick(void)
{
	struct picosystem_game_world world;
	assert(picosystem_game_world_reset(&world) == 0);
	const struct picosystem_game_input neutral = {0};
	bool saw_negative_x = false;
	bool saw_positive_x_after_bounce = false;
	bool saw_negative_y = false;
	bool saw_positive_y_after_bounce = false;

	for (uint32_t step = 0U; step < 2000U; ++step) {
		assert(picosystem_game_world_step(&world, &neutral) == 0);
		assert(world.sprite_x_fixed >= SPRITE_MIN_X_FIXED);
		assert(world.sprite_x_fixed <= SPRITE_MAX_X_FIXED);
		assert(world.sprite_y_fixed >= SPRITE_MIN_Y_FIXED);
		assert(world.sprite_y_fixed <= SPRITE_MAX_Y_FIXED);

		if (world.velocity_x_fixed_per_second < 0) {
			saw_negative_x = true;
		} else if (saw_negative_x) {
			saw_positive_x_after_bounce = true;
		}
		if (world.velocity_y_fixed_per_second < 0) {
			saw_negative_y = true;
		} else if (saw_negative_y) {
			saw_positive_y_after_bounce = true;
		}
	}

	assert(saw_negative_x);
	assert(saw_positive_x_after_bounce);
	assert(saw_negative_y);
	assert(saw_positive_y_after_bounce);

	world.logic_tick_count = UINT32_MAX;
	assert(picosystem_game_world_step(&world, &neutral) == 0);
	assert(world.logic_tick_count == UINT32_MAX);
}

static void replay_pattern(struct picosystem_game_world *world)
{
	static const struct picosystem_game_input inputs[] = {
		{.horizontal = 1},
		{.vertical = -1},
		{.horizontal = -1, .vertical = 1},
		{0},
	};

	for (uint32_t step = 0U; step < 10000U; ++step) {
		const size_t input_index = step % (sizeof(inputs) / sizeof(inputs[0]));
		assert(picosystem_game_world_step(world, &inputs[input_index]) == 0);
	}
}

static void test_reset_replay_is_bit_exact(void)
{
	struct picosystem_game_world first;
	assert(picosystem_game_world_reset(&first) == 0);
	replay_pattern(&first);

	struct picosystem_game_world second;
	assert(picosystem_game_world_reset(&second) == 0);
	replay_pattern(&second);

	assert_world_equal(&first, &second);
	assert(picosystem_game_world_hash(&first) == picosystem_game_world_hash(&second));
}

int main(void)
{
	test_canonical_reset_and_golden_replay();
	test_validation_preserves_state();
	test_bounded_motion_and_saturated_tick();
	test_reset_replay_is_bit_exact();
	puts("game-world tests passed");
	return 0;
}
