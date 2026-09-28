/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "garden_evaluation.h"
#include "garden_reproduction_audit.h"

static void ready(struct picosystem_garden_world *world)
{
	assert(picosystem_garden_world_reset(world, 123U) == 0);
	world->auto_gardener_enabled = false;
	assert(picosystem_garden_world_plant_seed(world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 13U) ==
	       0);
	world->plants[0].stored_energy = 145U;
	world->plants[0].stored_water = 65U;
	world->plants[0].genome.reserve_strategy = 0;
	world->plants[0].reproduction_cooldown = 0U;
	world->plants[0].growth_cooldown = 1U;
	for (uint16_t i = 0U; i < world->node_count; ++i) {
		world->nodes[i].kind = PICOSYSTEM_GARDEN_NODE_STEM;
		world->nodes[i].flags = (i == 0U) ? PICOSYSTEM_GARDEN_NODE_FLOWER : 0U;
		world->nodes[i].growth_progress = UINT8_MAX;
	}
	world->logic_tick_count = 899U;
	world->ecology_tick_count = 59U;
}

static uint32_t next_random(uint32_t value)
{
	value ^= value << 13U;
	value ^= value >> 17U;
	value ^= value << 5U;
	return value;
}

static uint8_t expected_column(int origin, int trait, unsigned int choice)
{
	const int distance = PICOSYSTEM_GARDEN_DISPERSAL_MINIMUM + trait + (int)(choice / 2U);
	const int direction = ((choice & 1U) != 0U) ? 1 : -1;
	int column = origin + direction * distance;
	if ((column < 0) || (column >= 28)) {
		column = origin - direction * distance;
	}
	assert((column >= 0) && (column < 28));
	return (uint8_t)column;
}

static void step(struct picosystem_garden_world *world)
{
	struct picosystem_garden_reproduction_audit audit;
	assert(picosystem_garden_world_step_reproduction_audit(
		       world, picosystem_garden_agent_adaptive_policy(), &audit) == 0);
	assert(audit.count == 1U && audit.visits[0].produced);
	assert(world->seed_count == 1U && world->seeds[0].age_ecology_ticks == 0U);
	assert(world->plants[0].stored_energy == audit.visits[0].energy - 48U);
	assert(world->plants[0].stored_water == audit.visits[0].water - 24U);
	assert(world->plants[0].reproduction_cooldown == 16U);
}

static uint32_t support(const struct picosystem_garden_world *world)
{
	const struct picosystem_garden_world before = *world;
	struct picosystem_garden_seed_sites sites;
	assert(picosystem_garden_world_seed_sites(world, &sites) == 0);
	assert(memcmp(world, &before, sizeof(before)) == 0);
	return sites.dispersal_columns[0];
}

static void check_positions(void)
{
	/* Find RNG preimages for every direction/distance, including both extremes. */
	uint32_t states[2U * PICOSYSTEM_GARDEN_DISPERSAL_CHOICES] = {0};
	for (uint32_t state = 1U; state < 10000U; ++state) {
		const uint32_t value = next_random(state);
		const uint32_t choice =
			((value >> 1U) % PICOSYSTEM_GARDEN_DISPERSAL_CHOICES) * 2U + (value & 1U);
		states[choice] = state;
	}
	for (int x = 0; x <= UINT8_MAX; ++x) {
		for (int trait = -2; trait <= 2; ++trait) {
			struct picosystem_garden_world initial;
			ready(&initial);
			initial.plants[0].genome.dispersal = (int8_t)trait;
			struct picosystem_garden_world moved = initial;
			moved.nodes[0].x = (uint8_t)x;
			int origin = 13;
#if defined(TOY_FACTORY_GARDEN_FLOWER_DISPERSAL)
			origin = x < 8 ? 0 : (x - 8) / 8;
			if (origin > 27) {
				origin = 27;
			}
#endif
			const uint32_t sites = support(&moved);
			uint32_t reached = 0U;
			for (unsigned int choice = 0U;
			     choice < 2U * PICOSYSTEM_GARDEN_DISPERSAL_CHOICES; ++choice) {
				assert(states[choice] != 0U);
				initial.plants[0].random_state = states[choice];
				struct picosystem_garden_world aligned = initial;
				moved = initial;
				moved.nodes[0].x = (uint8_t)x;
				step(&aligned);
				step(&moved);
				assert(aligned.seeds[0].column ==
				       expected_column(13, trait, choice));
				assert(moved.seeds[0].column ==
				       expected_column(origin, trait, choice));
				assert(moved.plants[0].random_state ==
				       next_random(next_random(states[choice])));
				reached |= UINT32_C(1) << moved.seeds[0].column;
				/* Normalize only the relocated flower and landing column. This also
				 * checks hidden RNG, mutation, resource, memory and counter state.
				 */
				moved.nodes[0].x = aligned.nodes[0].x;
				moved.seeds[0].column = aligned.seeds[0].column;
				assert(memcmp(&moved, &aligned, sizeof(moved)) == 0);
			}
			assert(reached == sites);
		}
	}
}

static void check_selection(void)
{
	struct picosystem_garden_world world;
	ready(&world);
	world.nodes[0].flags |= PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED;
	world.nodes[1].flags = PICOSYSTEM_GARDEN_NODE_FLOWER;
	world.nodes[1].growth_progress = 73U;
	world.nodes[2].flags = PICOSYSTEM_GARDEN_NODE_FLOWER;
	world.nodes[2].x = 20U;
	world.nodes[3].flags = PICOSYSTEM_GARDEN_NODE_FLOWER;
	world.nodes[3].x = 212U;
	const uint32_t sites = support(&world);
	step(&world);
	assert(world.nodes[1].growth_progress == 95U);
	assert((world.nodes[1].flags & PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED) == 0U);
	assert((world.nodes[2].flags & PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED) != 0U);
	assert((world.nodes[3].flags & PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED) == 0U);
	assert((sites & (UINT32_C(1) << world.seeds[0].column)) != 0U);
	/* Immature -> ready boundary uses the updated progress, not a stale origin. */
	ready(&world);
	world.nodes[0].flags |= PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED;
	world.nodes[1].flags = PICOSYSTEM_GARDEN_NODE_FLOWER;
	world.nodes[1].growth_progress = 74U;
	world.nodes[1].x = 220U;
	step(&world);
	assert(world.nodes[1].growth_progress == PICOSYSTEM_GARDEN_LEAF_ACTIVE_PROGRESS);
	assert((world.nodes[1].flags & PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED) != 0U);
	/* A landed seed cannot follow a flower that moves afterward. */
	const uint8_t landing = world.seeds[0].column;
	world.nodes[1].x = 12U;
	for (unsigned int i = 0U; i < 15U; ++i) {
		assert(picosystem_garden_world_step(&world) == 0);
	}
	assert(world.seed_count == 1U && world.seeds[0].column == landing);

	ready(&world);
	const uint32_t base_support = support(&world);
	for (unsigned int condition = 0U; condition < 4U; ++condition) {
		ready(&world);
		if (condition == 0U) {
			world.nodes[0].flags = 0U;
		} else if (condition == 1U) {
			world.nodes[0].growth_progress = 0U;
		} else if (condition == 2U) {
			world.nodes[0].flags |= PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED;
		} else {
			world.plants[0].flags = PICOSYSTEM_GARDEN_PLANT_DEAD;
			world.plants[0].stress = PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD;
		}
		uint32_t expected = condition == 3U ? 0U : base_support;
#if defined(TOY_FACTORY_GARDEN_FLOWER_DISPERSAL)
		(void)base_support;
		expected = 0U;
#endif
		assert(support(&world) == expected);
		assert(picosystem_garden_world_step(&world) == 0);
		assert(world.seed_count == 0U);
	}
	/* A ready flower belonging to another plant must not give this one reach. */
	ready(&world);
	world.nodes[0].flags = 0U;
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 24U) ==
	       0);
	world.nodes[4].flags = PICOSYSTEM_GARDEN_NODE_FLOWER;
	world.nodes[4].growth_progress = UINT8_MAX;
#if defined(TOY_FACTORY_GARDEN_FLOWER_DISPERSAL)
	assert(support(&world) == 0U);
#else
	assert(support(&world) == base_support);
#endif
}

int main(void)
{
	check_positions();
	check_selection();
	puts("PASS: dispersal origin, support, boundary, RNG, selection and seed costs");
	return 0;
}
