/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_wicking.h"
#include "garden_world.h"

#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

static uint32_t total(const uint8_t *cells)
{
	uint32_t sum = 0U;
	for (size_t i = 0U; i < PICOSYSTEM_GARDEN_SOIL_CELL_COUNT; ++i) {
		sum += cells[i];
	}
	return sum;
}

static void test_edges_and_cadence(void)
{
	uint8_t cells[PICOSYSTEM_GARDEN_SOIL_CELL_COUNT] = {0};
	cells[28] = 255U;
	const uint32_t first = PICOSYSTEM_GARDEN_WICKING_AFTER_TICK + 60U;
	const uint8_t before[PICOSYSTEM_GARDEN_SOIL_CELL_COUNT] = {[28] = 255U};
	assert(picosystem_garden_wicking_step(NULL, sizeof(cells), first) == -EINVAL);
	assert(picosystem_garden_wicking_step(cells, sizeof(cells) - 1U, first) == -EINVAL);
	assert(picosystem_garden_wicking_step(cells, sizeof(cells) + 1U, first) == -EINVAL);
	for (uint32_t tick = first - 60U; tick < first; ++tick) {
		assert(picosystem_garden_wicking_step(cells, sizeof(cells), tick) == 0);
		assert(memcmp(cells, before, sizeof(cells)) == 0);
	}
	assert(picosystem_garden_wicking_step(cells, sizeof(cells), first) == 1);
	assert(cells[0] == 1U && cells[28] == 254U && total(cells) == 255U);
	memset(cells, UINT8_MAX, sizeof(cells));
	assert(picosystem_garden_wicking_step(cells, sizeof(cells), first) == 0);
	memset(cells, 0, sizeof(cells));
	cells[28] = 1U;
	assert(picosystem_garden_wicking_step(cells, sizeof(cells), first) == 0);
	cells[28] = 2U;
	assert(picosystem_garden_wicking_step(cells, sizeof(cells), first) == 1);
	assert(cells[0] == 1U && cells[28] == 1U);
}

static void test_one_edge_per_pass_and_conservation(void)
{
	uint8_t cells[PICOSYSTEM_GARDEN_SOIL_CELL_COUNT] = {0};
	cells[280] = 200U;
	assert(picosystem_garden_wicking_step(cells, sizeof(cells), 626640U) == 1);
	assert(cells[280] == 199U && cells[252] == 1U && cells[224] == 0U);
	uint32_t random = 123U;
	for (unsigned trial = 0U; trial < 1000U; ++trial) {
		for (size_t i = 0U; i < sizeof(cells); ++i) {
			random = random * UINT32_C(1664525) + UINT32_C(1013904223);
			cells[i] = (uint8_t)(random >> 24U);
		}
		uint8_t again[sizeof(cells)];
		memcpy(again, cells, sizeof(cells));
		const uint32_t before = total(cells);
		const int moved = picosystem_garden_wicking_step(cells, sizeof(cells), 626640U);
		assert(moved >= 0 && moved <= 280 && total(cells) == before);
		assert(picosystem_garden_wicking_step(again, sizeof(again), 626640U) == moved);
		assert(memcmp(cells, again, sizeof(cells)) == 0);
	}
}

static void test_world_integration(void)
{
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_reset(&world, 123U) == 0);
	assert(picosystem_garden_world_set_auto_gardener(&world, false) == 0);
	memset(world.moisture, 0, sizeof(world.moisture));
	world.moisture[280] = 16U;
	world.moisture_total = 16U;
	world.logic_tick_count = 626639U;
	world.ecology_tick_count = world.logic_tick_count / PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR;
	assert(picosystem_garden_world_step(&world) == 0);
	assert(world.moisture_total == 16U && world.logic_tick_count == 626640U);
#if defined(TOY_FACTORY_GARDEN_SOIL_WICKING)
	assert(world.moisture[252] == 1U && world.moisture[253] == 1U);
	assert(world.moisture[280] == 13U && world.moisture[281] == 1U);
#else
	assert(world.moisture[252] == 0U && world.moisture[253] == 0U);
	assert(world.moisture[280] == 14U && world.moisture[281] == 2U);
#endif
}

int main(void)
{
	test_edges_and_cadence();
	test_one_edge_per_pass_and_conservation();
	test_world_integration();
	puts("Garden wicking boundaries, conservation, cadence and integration passed");
	return 0;
}
