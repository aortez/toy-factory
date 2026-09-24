/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_agent.h"
#include "garden_light.h"

static uint16_t cell(uint8_t column, uint8_t row)
{
	return (uint16_t)((uint16_t)row * PICOSYSTEM_GARDEN_GRID_COLUMNS + column);
}

static void test_solver(void)
{
	uint8_t shade[PICOSYSTEM_GARDEN_LIGHT_CELL_COUNT] = {0};
	uint8_t light[PICOSYSTEM_GARDEN_LIGHT_CELL_COUNT];
	uint8_t before[PICOSYSTEM_GARDEN_LIGHT_CELL_COUNT];
	const struct picosystem_garden_sun noon = picosystem_garden_sun_at(0U);
	memset(light, 91, sizeof(light));
	memcpy(before, light, sizeof(before));
	assert(picosystem_garden_light_solve_transmission(NULL, &noon, light) == -EINVAL);
	assert(picosystem_garden_light_solve_transmission(shade, NULL, light) == -EINVAL);
	assert(picosystem_garden_light_solve_transmission(shade, &noon, NULL) == -EINVAL);
	assert(picosystem_garden_light_solve_transmission(light, &noon, light) == -EINVAL);
	for (int direction = -13; direction <= 13; direction += 26) {
		struct picosystem_garden_sun invalid = noon;
		invalid.ray_step_x_q4 = (int8_t)direction;
		assert(picosystem_garden_light_solve_transmission(shade, &invalid, light) ==
		       -ERANGE);
	}
	struct picosystem_garden_sun invalid = noon;
	invalid.strength = 23U;
	assert(picosystem_garden_light_solve_transmission(shade, &invalid, light) == -ERANGE);
	assert(memcmp(light, before, sizeof(light)) == 0);
	for (uint16_t tick = 0U; tick < 256U; ++tick) {
		const struct picosystem_garden_sun sun = picosystem_garden_sun_at(tick);
		assert(picosystem_garden_light_solve_transmission(shade, &sun, light) == 0);
		for (uint16_t i = 0U; i < sizeof(light); ++i) {
			assert(light[i] == sun.strength);
		}
	}
	shade[cell(5U, 1U)] = 128U;
	assert(picosystem_garden_light_solve_transmission(shade, &noon, light) == 0);
	assert(light[cell(5U, 1U)] == 255U && light[cell(5U, 2U)] == 139U);
	shade[cell(5U, 2U)] = 128U;
	assert(picosystem_garden_light_solve_transmission(shade, &noon, light) == 0);
	assert(light[cell(5U, 3U)] == 81U);
	shade[cell(5U, 3U)] = 128U;
	assert(picosystem_garden_light_solve_transmission(shade, &noon, light) == 0);
	assert(light[cell(5U, 4U)] == 52U);
	memset(shade, 0, sizeof(shade));
	shade[cell(5U, 1U)] = 128U;
	struct picosystem_garden_sun angled = noon;
	angled.ray_step_x_q4 = 12;
	assert(picosystem_garden_light_solve_transmission(shade, &angled, light) == 0);
	assert(light[cell(6U, 2U)] == 139U && light[cell(7U, 3U)] == 139U);
	assert(light[cell(5U, 3U)] == 255U);
	angled.ray_step_x_q4 = -12;
	assert(picosystem_garden_light_solve_transmission(shade, &angled, light) == 0);
	assert(light[cell(4U, 2U)] == 139U && light[cell(3U, 3U)] == 139U);
	shade[cell(5U, 1U)] = UINT8_MAX;
	assert(picosystem_garden_light_solve_transmission(shade, &noon, light) == 0);
	assert(light[cell(5U, 2U)] == 24U);
	memset(shade, 255, sizeof(shade));
	for (uint16_t tick = 64U; tick <= 192U; ++tick) {
		const struct picosystem_garden_sun night = picosystem_garden_sun_at(tick);
		assert(picosystem_garden_light_solve_transmission(shade, &night, light) == 0);
		for (uint16_t i = 0U; i < sizeof(light); ++i) {
			assert(light[i] == 24U && light[i] / 64U == 0U);
		}
	}
}

static int wait_decide(const struct picosystem_garden_agent_observation *observation,
		       const struct picosystem_garden_agent_memory *memory,
		       struct picosystem_garden_agent_decision *decision, const void *context)
{
	(void)context;
	*decision = (struct picosystem_garden_agent_decision){
		.next_memory = *memory,
		.proposal = {.tip_index = observation->tip_index,
			     .action = PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT},
	};
	return 0;
}

static void fixture(struct picosystem_garden_world *world)
{
	assert(picosystem_garden_world_reset(world, 123U) == 0);
	assert(!world->canopy_transmission_enabled);
	world->auto_gardener_enabled = false;
	assert(picosystem_garden_world_plant_seed(world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 5U) ==
	       0);
	for (uint16_t i = 0U; i < world->node_count; ++i) {
		if ((world->nodes[i].flags & PICOSYSTEM_GARDEN_NODE_LEAF) != 0U) {
			world->nodes[i].y = PICOSYSTEM_GARDEN_CANOPY_TOP_PIXELS + 8U;
			world->nodes[i].growth_progress = UINT8_MAX;
		}
	}
	world->logic_tick_count = 69119U;
	world->ecology_tick_count = 4607U;
}

static void test_world_boundary(void)
{
	struct picosystem_garden_world control, candidate;
	fixture(&control);
	candidate = control;
	candidate.canopy_transmission_enabled = true;
	const struct picosystem_garden_agent_policy policy = {
		.decide = wait_decide,
		.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS,
	};
	assert(picosystem_garden_world_hash(&control) == picosystem_garden_world_hash(&candidate));
	for (uint32_t t = 69120U; t <= 69135U; ++t) {
		assert(picosystem_garden_world_step_with_policy(&control, &policy) == 0);
		assert(picosystem_garden_world_step_with_policy(&candidate, &policy) == 0);
		assert(control.logic_tick_count == t && candidate.logic_tick_count == t);
		struct picosystem_garden_world plain = candidate;
		plain.canopy_transmission_enabled = false;
		if (t < 69135U) {
			assert(memcmp(&control, &plain, sizeof(control)) == 0);
		} else {
			assert(memcmp(control.light, candidate.light, sizeof(control.light)) != 0);
			assert(picosystem_garden_world_hash(&control) !=
			       picosystem_garden_world_hash(&candidate));
		}
	}
	fixture(&control);
	control.logic_tick_count = 70079U;
	control.ecology_tick_count = 4671U;
	candidate = control;
	candidate.canopy_transmission_enabled = true;
	assert(picosystem_garden_world_step_with_policy(&control, &policy) == 0);
	assert(picosystem_garden_world_step_with_policy(&candidate, &policy) == 0);
	assert(candidate.plants[0].last_energy_income == 0U);
	assert(control.plants[0].last_energy_income == 0U);
	candidate.canopy_transmission_enabled = false;
	assert(memcmp(&control, &candidate, sizeof(control)) == 0);
	candidate.canopy_transmission_enabled = true;
	assert(picosystem_garden_world_reset(&candidate, 123U) == 0);
	assert(!candidate.canopy_transmission_enabled);
}

static int dump_reference(void)
{
	uint8_t shade[PICOSYSTEM_GARDEN_LIGHT_CELL_COUNT];
	uint8_t light[PICOSYSTEM_GARDEN_LIGHT_CELL_COUNT];
	uint8_t original[PICOSYSTEM_GARDEN_LIGHT_CELL_COUNT];
	for (uint16_t i = 0U; i < sizeof(shade); ++i) {
		shade[i] = (uint8_t)(((uint32_t)i * 73U + (uint32_t)(i / 7U) * 19U) % 256U);
	}
	for (uint16_t tick = 0U; tick < 256U; ++tick) {
		const struct picosystem_garden_sun sun = picosystem_garden_sun_at(tick);
		assert(picosystem_garden_light_solve_transmission(shade, &sun, light) == 0);
		assert(picosystem_garden_light_solve(shade, &sun, original) == 0);
		printf("{\"tick\":%u,\"light\":[", tick);
		for (uint16_t i = 0U; i < sizeof(light); ++i) {
			assert(light[i] >= original[i] && light[i] <= sun.strength);
			printf("%s%u", i == 0U ? "" : ",", light[i]);
		}
		puts("]}");
	}
	return ferror(stdout) ? 1 : 0;
}

int main(int argc, char **argv)
{
	if (argc == 2 && strcmp(argv[1], "--dump-reference") == 0) {
		return dump_reference();
	}
	assert(argc == 1);
	bool enabled = false;
	assert(picosystem_garden_canopy_transmission_parse(NULL, &enabled) == -EINVAL);
	assert(picosystem_garden_canopy_transmission_parse("fractional", NULL) == -EINVAL);
	assert(picosystem_garden_canopy_transmission_parse("bad", &enabled) == -EINVAL && !enabled);
	assert(picosystem_garden_canopy_transmission_parse("fractional", &enabled) == 0 && enabled);
	assert(picosystem_garden_canopy_transmission_parse("fractional", &enabled) == -EINVAL);
	assert(!picosystem_garden_canopy_transmission_active(false, UINT32_MAX));
	assert(!picosystem_garden_canopy_transmission_active(true, 0U));
	assert(!picosystem_garden_canopy_transmission_active(true, 69120U));
	assert(picosystem_garden_canopy_transmission_active(true, 69121U));
	test_solver();
	test_world_boundary();
	puts("Canopy transmission optics, night, boundaries, world isolation and reset passed");
	return 0;
}
