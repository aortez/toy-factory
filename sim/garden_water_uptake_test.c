/* SPDX-License-Identifier: Apache-2.0 */

#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_agent.h"
#include "garden_world.h"

static int wait_decide(const struct picosystem_garden_agent_observation *observation,
		       const struct picosystem_garden_agent_memory *memory,
		       struct picosystem_garden_agent_decision *decision, const void *context)
{
	(void)context;
	*decision = (struct picosystem_garden_agent_decision){
		.proposal = {.tip_index = observation->tip_index,
			     .action = PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT},
		.next_memory = *memory,
	};
	return 0;
}

static const struct picosystem_garden_agent_policy wait_policy = {.decide = wait_decide};

static void setup(struct picosystem_garden_world *world, enum picosystem_garden_species_id species,
		  uint8_t moisture)
{
	assert(picosystem_garden_world_reset(world, 123U) == 0);
	assert(picosystem_garden_world_plant_seed(world, species, 0U) == 0);
	memset(world->moisture, moisture, sizeof(world->moisture));
	world->logic_tick_count = 14U;
	/* Two roots share column zero. Uniform soil does not flow on this step. */
	assert(world->node_count == 4U);
	world->nodes[1].growth_progress = UINT8_MAX;
}

static void step(struct picosystem_garden_world *world)
{
	assert(picosystem_garden_world_step_with_policy(world, &wait_policy) == 0);
}

static void check_boundaries(void)
{
	const uint16_t stores[] = {0U, 32U, 505U, 506U, 509U, 510U, 511U, 512U};
	const uint8_t moistures[] = {0U, 1U, 2U, 5U, 10U, UINT8_MAX};
	for (int species = 0; species < PICOSYSTEM_GARDEN_SPECIES_COUNT; ++species) {
		for (size_t water = 0U; water < sizeof(stores) / sizeof(stores[0]); ++water) {
			for (size_t soil = 0U; soil < sizeof(moistures); ++soil) {
				struct picosystem_garden_world world;
				setup(&world, (enum picosystem_garden_species_id)species,
				      moistures[soil]);
				world.plants[0].stored_water = stores[water];
				const uint16_t potential =
					(species == PICOSYSTEM_GARDEN_SPECIES_GROUND_COVER) ? 4U
											    : 6U;
				uint16_t uptake =
					(moistures[soil] < potential) ? moistures[soil] : potential;
				const uint16_t headroom = (uint16_t)(512U - stores[water]);
#if defined(TOY_FACTORY_GARDEN_WATER_HEADROOM)
				if (uptake > headroom) {
					uptake = headroom;
				}
#endif
				step(&world);
				const uint16_t retained = (uptake < headroom) ? uptake : headroom;
				assert(world.plants[0].stored_water == stores[water] + retained);
				assert(world.plants[0].last_water_income == uptake);
				assert(world.moisture[0] == moistures[soil] - uptake);
				uint32_t soil_total = 0U;
				for (size_t cell = 0U; cell < sizeof(world.moisture); ++cell) {
					soil_total += world.moisture[cell];
				}
				assert(soil_total ==
				       PICOSYSTEM_GARDEN_SOIL_CELL_COUNT * moistures[soil] -
					       uptake);
				assert(world.moisture_total ==
				       ((soil_total > UINT16_MAX) ? UINT16_MAX : soil_total));
				/* A full water store must not short-circuit photosynthesis. */
				assert(world.plants[0].last_energy_income > 0U);
				assert(world.plants[0].stored_energy > 128U);
				assert(world.node_count == 4U);
			}
		}
	}
}

static void check_competition(void)
{
	for (int full = 0; full <= 1; ++full) {
		struct picosystem_garden_world world;
		setup(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 5U);
		assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER,
							  6U) == 0);
		/* Valid controlled topology: both plants draw from the same soil cell. */
		world.nodes[6].x = world.nodes[2].x;
		world.nodes[7].x = world.nodes[3].x;
		world.plants[0].stored_water = full ? 512U : 32U;
		step(&world);
#if defined(TOY_FACTORY_GARDEN_WATER_HEADROOM)
		const uint8_t first = full ? 0U : 5U;
#else
		const uint8_t first = 5U;
#endif
		assert(world.plants[0].last_water_income == first);
		assert(world.plants[1].last_water_income == 5U - first);
		assert(world.moisture[0] == 0U);
		assert(world.moisture_total == PICOSYSTEM_GARDEN_SOIL_CELL_COUNT * 5U - 5U);
	}
}

static void check_upkeep_and_failures(void)
{
	struct picosystem_garden_world world;
	setup(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 10U);
	world.plants[0].stored_water = 512U;
	world.ecology_tick_count = 3U;
	world.logic_tick_count = 59U;
	step(&world);
	assert(world.plants[0].stored_water == 511U);
#if defined(TOY_FACTORY_GARDEN_WATER_HEADROOM)
	assert(world.plants[0].last_water_income == 0U);
#endif
	for (uint32_t tick = 0U; tick < 15U; ++tick) {
		step(&world);
	}
	assert(world.plants[0].stored_water == 512U);
#if defined(TOY_FACTORY_GARDEN_WATER_HEADROOM)
	assert(world.plants[0].last_water_income == 1U);
#endif
	world.plants[0].stored_water = 513U;
	const struct picosystem_garden_world before = world;
	assert(picosystem_garden_world_step_with_policy(&world, &wait_policy) == -EINVAL);
	assert(memcmp(&world, &before, sizeof(world)) == 0);
	world.plants[0].stored_water = 512U;
	step(&world);
	setup(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 10U);
	world.plants[0].flags = PICOSYSTEM_GARDEN_PLANT_DEAD;
	world.plants[0].stress = PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD;
	step(&world);
	assert(world.plants[0].last_water_income == 0U);
	assert(world.moisture_total == PICOSYSTEM_GARDEN_SOIL_CELL_COUNT * 10U);
}

int main(void)
{
	check_boundaries();
	check_competition();
	check_upkeep_and_failures();
	puts("PASS: root uptake/storage/soil accounting, shared-cell ordering, light, upkeep and "
	     "recovery");
	return 0;
}
