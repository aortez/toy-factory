/* SPDX-License-Identifier: Apache-2.0 */

#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

#include "game_scene_selector.h"

static enum picosystem_game_scene_selector_action
sample(struct picosystem_game_scene_selector *selector, int64_t now_ms, bool pressed)
{
	enum picosystem_game_scene_selector_action action = PICOSYSTEM_GAME_SCENE_SELECTOR_NONE;
	assert(picosystem_game_scene_selector_update(selector, now_ms, pressed, &action) == 0);
	return action;
}

static void test_short_press_resets_on_release(void)
{
	struct picosystem_game_scene_selector selector = {0};

	assert(sample(&selector, 100, false) == PICOSYSTEM_GAME_SCENE_SELECTOR_NONE);
	assert(sample(&selector, 120, true) == PICOSYSTEM_GAME_SCENE_SELECTOR_NONE);
	assert(sample(&selector, 869, true) == PICOSYSTEM_GAME_SCENE_SELECTOR_NONE);
	assert(sample(&selector, 869, false) == PICOSYSTEM_GAME_SCENE_SELECTOR_RESET);
	assert(sample(&selector, 900, false) == PICOSYSTEM_GAME_SCENE_SELECTOR_NONE);
}

static void test_hold_changes_scene_once(void)
{
	struct picosystem_game_scene_selector selector = {0};

	assert(sample(&selector, 1000, true) == PICOSYSTEM_GAME_SCENE_SELECTOR_NONE);
	assert(sample(&selector, 1749, true) == PICOSYSTEM_GAME_SCENE_SELECTOR_NONE);
	assert(sample(&selector, 1750, true) == PICOSYSTEM_GAME_SCENE_SELECTOR_NEXT);
	assert(sample(&selector, 2500, true) == PICOSYSTEM_GAME_SCENE_SELECTOR_NONE);
	assert(sample(&selector, 2501, false) == PICOSYSTEM_GAME_SCENE_SELECTOR_NONE);

	assert(sample(&selector, 3000, true) == PICOSYSTEM_GAME_SCENE_SELECTOR_NONE);
	assert(sample(&selector, 3010, false) == PICOSYSTEM_GAME_SCENE_SELECTOR_RESET);
}

static void test_invalid_samples_preserve_state(void)
{
	struct picosystem_game_scene_selector selector = {0};
	enum picosystem_game_scene_selector_action action = PICOSYSTEM_GAME_SCENE_SELECTOR_NEXT;

	assert(picosystem_game_scene_selector_update(NULL, 0, false, &action) == -EINVAL);
	assert(picosystem_game_scene_selector_update(&selector, 0, false, NULL) == -EINVAL);
	assert(sample(&selector, 100, true) == PICOSYSTEM_GAME_SCENE_SELECTOR_NONE);
	const struct picosystem_game_scene_selector baseline = selector;
	assert(picosystem_game_scene_selector_update(&selector, 99, true, &action) == -ERANGE);
	assert(action == PICOSYSTEM_GAME_SCENE_SELECTOR_NEXT);
	assert(selector.press_start_ms == baseline.press_start_ms);
	assert(selector.previous_sample_ms == baseline.previous_sample_ms);
	assert(selector.initialized == baseline.initialized);
	assert(selector.pressed == baseline.pressed);
	assert(selector.hold_handled == baseline.hold_handled);
}

int main(void)
{
	test_short_press_resets_on_release();
	test_hold_changes_scene_once();
	test_invalid_samples_preserve_state();
	puts("game-scene-selector tests passed");
	return 0;
}
