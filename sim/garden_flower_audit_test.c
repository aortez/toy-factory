/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_evaluation.h"
#include "garden_flower_audit.h"

static void ready(struct picosystem_garden_world *world, uint8_t count)
{
	assert(picosystem_garden_world_reset(world, 123U) == 0);
	world->auto_gardener_enabled = false;
	for (uint8_t i = 0U; i < count; ++i) {
		assert(picosystem_garden_world_plant_seed(world, PICOSYSTEM_GARDEN_SPECIES_FLOWER,
							  (uint8_t)(i * 3U)) == 0);
		world->plants[i].stored_energy = 256U;
		world->plants[i].stored_water = 512U;
		world->plants[i].reproduction_cooldown = 0U;
		world->plants[i].growth_cooldown = 1U;
		world->plants[i].genome.dispersal = 0;
	}
	for (uint16_t i = 0U; i < world->node_count; ++i) {
		world->nodes[i].kind = PICOSYSTEM_GARDEN_NODE_STEM;
		world->nodes[i].flags = PICOSYSTEM_GARDEN_NODE_FLOWER;
		world->nodes[i].growth_progress = UINT8_MAX;
	}
	memset(world->moisture, UINT8_MAX, sizeof(world->moisture));
	world->logic_tick_count = 899U;
	world->ecology_tick_count = 59U;
}

static uint8_t origin(uint8_t x)
{
	int column = x < 8U ? 0 : ((int)x - 8) / 8;
	return (uint8_t)(column > 27 ? 27 : column);
}

static uint32_t support(uint8_t column, int trait)
{
	uint32_t result = 0U;
	for (unsigned int distance = 0U; distance < PICOSYSTEM_GARDEN_DISPERSAL_CHOICES;
	     ++distance) {
		for (int direction = -1; direction <= 1; direction += 2) {
			const int offset = direction * (PICOSYSTEM_GARDEN_DISPERSAL_MINIMUM +
							trait + (int)distance);
			int landing = (int)column + offset;
			if ((landing < 0) || (landing > 27)) {
				landing = (int)column - offset;
			}
			assert((landing >= 0) && (landing < 28));
			result |= UINT32_C(1) << landing;
		}
	}
	return result;
}

static void same_step(struct picosystem_garden_world *world,
		      const struct picosystem_garden_agent_policy *policy,
		      struct picosystem_garden_flower_audit *audit)
{
	struct picosystem_garden_world plain = *world;
	struct picosystem_garden_reproduction_audit old;
	assert(picosystem_garden_world_step_reproduction_audit(&plain, policy, &old) == 0);
	assert(picosystem_garden_world_step_flower_audit(world, policy, audit) == 0);
	assert(memcmp(world, &plain, sizeof(plain)) == 0);
	assert(memcmp(&old, &audit->production, sizeof(old)) == 0);
	uint16_t captured = 0U;
	uint8_t purchased = 0U;
	for (uint8_t i = 0U; i < old.count; ++i) {
		const struct picosystem_garden_reproduction_visit *const v = &old.visits[i];
		if (!v->produced) {
			continue;
		}
		assert(purchased < audit->count);
		const struct picosystem_garden_flower_purchase *const p =
			&audit->purchases[purchased++];
		assert(p->lineage == v->lineage && p->flower_count == v->ready_flowers);
		assert(p->flower_offset == captured && p->selected_flower == v->flower_index);
		assert(p->columns == support(p->origin, p->dispersal));
		assert(p->choice < 2U * PICOSYSTEM_GARDEN_DISPERSAL_CHOICES);
		assert(world->seeds[v->seed_count].column == p->landed_column);
		for (uint16_t j = 0U; j < p->flower_count; ++j) {
			const struct picosystem_garden_flower_reach *const f =
				&audit->flowers[captured++];
			const struct picosystem_garden_node *const n = &world->nodes[f->node_index];
			assert(n->plant_index == i && n->x == f->x && n->y == f->y);
			assert(f->columns == support(origin(f->x), p->dispersal));
			assert(j == 0U ? f->node_index == p->selected_flower
				       : f->node_index > audit->flowers[captured - 2U].node_index);
		}
	}
	assert(purchased == audit->count && captured == audit->flower_count);
	if (audit->count != 0U) {
		struct picosystem_garden_seed_sites sites;
		assert(picosystem_garden_world_seed_sites(world, &sites) == 0);
		for (uint8_t i = 0U; i < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++i) {
			assert(audit->sites[i].blockers == sites.blockers[i]);
			assert(audit->sites[i].moisture == world->moisture[i]);
			assert(audit->sites[i].light == world->light[13U * 28U + i]);
		}
	} else {
		const struct picosystem_garden_flower_site empty[PICOSYSTEM_GARDEN_GRID_COLUMNS] = {
			0};
		assert(memcmp(audit->sites, empty, sizeof(empty)) == 0);
	}
}

int main(void)
{
	struct picosystem_garden_world world;
	const struct picosystem_garden_agent_policy *const policy =
		picosystem_garden_agent_adaptive_policy();
	struct picosystem_garden_flower_audit audit;
	memset(&audit, 0x5a, sizeof(audit));
	const struct picosystem_garden_flower_audit sentinel = audit;
	ready(&world, 1U);
	const struct picosystem_garden_world before = world;
	assert(picosystem_garden_world_step_flower_audit(NULL, policy, &audit) == -EINVAL);
	assert(picosystem_garden_world_step_flower_audit(&world, NULL, &audit) == -EINVAL);
	assert(picosystem_garden_world_step_flower_audit(&world, policy, NULL) == -EINVAL);
	assert(memcmp(&world, &before, sizeof(world)) == 0);
	world.node_count = PICOSYSTEM_GARDEN_MAX_NODES + 1U;
	assert(picosystem_garden_world_step_flower_audit(&world, policy, &audit) == -EINVAL);
	world = before;
	world.auto_gardener_enabled = true;
	assert(picosystem_garden_world_step_flower_audit(&world, policy, &audit) == -EINVAL);
	assert(memcmp(&audit, &sentinel, sizeof(audit)) == 0);

	ready(&world, 2U);
	world.nodes[0].flags |= PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED;
	world.nodes[1].growth_progress = 73U;
	world.nodes[2].x = 0U;
	world.nodes[3].x = UINT8_MAX;
	world.nodes[4].growth_progress = 74U;
	same_step(&world, policy, &audit);
	assert(audit.count == 2U && audit.flower_count == 6U);
	assert(audit.purchases[0].selected_flower == 2U &&
	       audit.purchases[1].selected_flower == 4U);
	assert(world.nodes[1].growth_progress == 95U && world.nodes[4].growth_progress == 96U);
	assert(audit.purchases[0].flower_offset == 0U && audit.purchases[1].flower_offset == 2U);

	ready(&world, 1U);
	for (uint16_t i = 0U; i < world.node_count; ++i) {
		world.nodes[i].flags |= PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED;
	}
	world.logic_tick_count = 2879U;
	world.ecology_tick_count = 191U;
	same_step(&world, policy, &audit);
	assert(audit.production.visits[0].ready_flowers == 4U);
	/* Dawn may still fail daylight; eligibility renewal must nevertheless be exact. */
	assert(audit.production.visits[0].spent_flowers == 0U);

	ready(&world, 2U);
	world.seed_count = 7U;
	for (uint8_t i = 0U; i < world.seed_count; ++i) {
		world.seeds[i] = (struct picosystem_garden_seed){
			.parent_lineage_id = 1U,
			.generation = 1U,
			.column = 14U,
		};
	}
	same_step(&world, policy, &audit);
	assert(audit.count == 1U && audit.flower_count == 4U);
	assert(audit.production.visits[1].blockers == PICOSYSTEM_GARDEN_REPRODUCTION_BANK);

	ready(&world, 8U);
	for (uint16_t i = world.node_count; i < PICOSYSTEM_GARDEN_MAX_NODES; ++i) {
		const uint8_t owner = (uint8_t)(i % 8U);
		world.nodes[i] = world.nodes[4U * owner];
		world.nodes[i].parent_index = (uint16_t)(4U * owner);
		++world.plants[owner].node_count;
	}
	world.node_count = PICOSYSTEM_GARDEN_MAX_NODES;
	same_step(&world, policy, &audit);
	assert(audit.count == 8U && audit.flower_count == PICOSYSTEM_GARDEN_MAX_NODES);
	for (uint8_t i = 0U; i < 28U; ++i) {
		assert((audit.sites[i].blockers & (PICOSYSTEM_GARDEN_SEED_BLOCKED_PLANT_CAPACITY |
						   PICOSYSTEM_GARDEN_SEED_BLOCKED_NODE_CAPACITY)) ==
		       24U);
	}

	ready(&world, 1U);
	world.plants[0].flags = PICOSYSTEM_GARDEN_PLANT_DEAD;
	world.plants[0].stress = PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD;
	same_step(&world, policy, &audit);
	assert(audit.count == 0U);
	const struct picosystem_garden_flower_audit zero = {0};
	for (uint8_t controller = 0U; controller < 2U; ++controller) {
		assert(toy_factory_garden_evaluation_reset(
			       &world, &toy_factory_garden_rainfed_scenarios[1], 0xed52188cU) == 0);
		assert(picosystem_garden_world_set_climate(
			       &world, PICOSYSTEM_GARDEN_CLIMATE_SEASONAL) == 0);
		const struct picosystem_garden_agent_policy *const p =
			controller == 0U ? picosystem_garden_agent_baseline_policy() : policy;
		for (uint32_t tick = 1U; tick <= 18U * 3840U; ++tick) {
			same_step(&world, p, &audit);
			if (!audit.production.ecology_step) {
				assert(memcmp(&audit, &zero, sizeof(audit)) == 0);
			}
		}
	}
	printf("Flower observation boundaries/noninterference passed; caller storage=%zu bytes\n",
	       sizeof(audit));
	return 0;
}
