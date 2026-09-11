/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "garden_evaluation.h"
#include "garden_light.h"
#include "garden_model_file.h"

#define INSPECTION_CYCLE_TICKS                                                                     \
	(PICOSYSTEM_GARDEN_SUN_CYCLE_TICKS * PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR)
#define INSPECTION_CYCLES 24U

struct inspection_context {
	uint32_t previous_births;
	uint32_t previous_deaths;
};

static void print_plant(const struct picosystem_garden_world *world, uint8_t plant_index)
{
	const struct picosystem_garden_plant *const plant = &world->plants[plant_index];
	uint16_t tips = 0U;
	uint16_t leaves = 0U;
	uint16_t flowers = 0U;
	uint16_t spent_flowers = 0U;
	uint16_t roots = 0U;
	for (uint16_t index = 0U; index < world->node_count; ++index) {
		const struct picosystem_garden_node *const node = &world->nodes[index];
		if (node->plant_index != plant_index) {
			continue;
		}
		tips += ((node->flags & PICOSYSTEM_GARDEN_NODE_TIP) != 0U) ? 1U : 0U;
		leaves += ((node->flags & PICOSYSTEM_GARDEN_NODE_LEAF) != 0U) ? 1U : 0U;
		flowers += ((node->flags & PICOSYSTEM_GARDEN_NODE_FLOWER) != 0U) ? 1U : 0U;
		spent_flowers +=
			((node->flags & PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED) != 0U) ? 1U : 0U;
		if (node->kind == PICOSYSTEM_GARDEN_NODE_ROOT) {
			++roots;
		}
	}
	printf("{\"id\":%" PRIu32 ",\"parent\":%" PRIu32 ",\"species\":\"%s\","
	       "\"generation\":%u,\"age_ecology_ticks\":%u,\"column\":%u,"
	       "\"dead\":%s,\"energy\":%u,\"water\":%u,\"stress\":%u,"
	       "\"nodes\":%u,\"roots\":%u,\"tips\":%u,\"leaves\":%u,"
	       "\"flowers\":%u,\"spent_flowers\":%u,\"genome\":[%d,%d,%d,%d,%d,%d,%d,%d]}",
	       plant->lineage_id, plant->parent_lineage_id,
	       picosystem_garden_species_name((enum picosystem_garden_species_id)plant->species_id),
	       plant->generation, plant->age_ecology_ticks, plant->base_column,
	       ((plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) != 0U) ? "true" : "false",
	       plant->stored_energy, plant->stored_water, plant->stress, plant->node_count, roots,
	       tips, leaves, flowers, spent_flowers, plant->genome.growth_rate,
	       plant->genome.shoot_bias, plant->genome.light_seeking, plant->genome.water_seeking,
	       plant->genome.branching, plant->genome.stature, plant->genome.reserve_strategy,
	       plant->genome.dispersal);
}

static int print_world(const struct picosystem_garden_world *world)
{
	printf("{\"tick\":%" PRIu32 ",\"hash\":\"%08" PRIx32 "\",\"living\":%u,"
	       "\"nodes\":%u,\"births\":%" PRIu32 ",\"deaths\":%" PRIu32 ","
	       "\"seeds_created\":%" PRIu32 ",\"seeds_expired\":%" PRIu32 ","
	       "\"max_generation\":%u,\"plants\":[",
	       world->logic_tick_count, picosystem_garden_world_hash(world),
	       picosystem_garden_world_living_plant_count(world), world->node_count,
	       world->germination_count, world->death_count, world->seed_creation_count,
	       world->seed_expiration_count, world->maximum_generation);
	for (uint8_t index = 0U; index < world->plant_count; ++index) {
		if (index != 0U) {
			putchar(',');
		}
		print_plant(world, index);
	}
	printf("],\"seeds\":[");
	for (uint8_t index = 0U; index < world->seed_count; ++index) {
		const struct picosystem_garden_seed *const seed = &world->seeds[index];
		uint8_t blockers;
		const int err =
			picosystem_garden_world_seed_germination_blockers(world, index, &blockers);
		if (err != 0) {
			return err;
		}
		printf("%s{\"parent\":%" PRIu32 ",\"generation\":%u,\"column\":%u,"
		       "\"blockers\":%u}",
		       (index == 0U) ? "" : ",", seed->parent_lineage_id, seed->generation,
		       seed->column, blockers);
	}
	printf("]}\n");
	return ferror(stdout) ? -EIO : 0;
}

static int observe(const struct picosystem_garden_world *world, bool ecology_sample, void *context)
{
	if (!ecology_sample) {
		return 0;
	}
	struct inspection_context *const inspection = context;
	bool ready_seed = false;
	for (uint8_t index = 0U; index < world->seed_count; ++index) {
		uint8_t blockers;
		const int err =
			picosystem_garden_world_seed_germination_blockers(world, index, &blockers);
		if (err != 0) {
			return err;
		}
		ready_seed = ready_seed || (blockers == 0U);
	}
	const bool changed = (world->germination_count != inspection->previous_births) ||
			     (world->death_count != inspection->previous_deaths);
	inspection->previous_births = world->germination_count;
	inspection->previous_deaths = world->death_count;
	return (changed || ready_seed || ((world->logic_tick_count % INSPECTION_CYCLE_TICKS) == 0U))
		       ? print_world(world)
		       : 0;
}

int main(int argc, char **argv)
{
	if (argc != 5) {
		fprintf(stderr, "Usage: %s MODEL SCENARIO POLICY WORLD_SEED\n", argv[0]);
		return 2;
	}
	errno = 0;
	char *end;
	const unsigned long parsed = strtoul(argv[4], &end, 0);
	if ((errno != 0) || (*argv[4] == '-') || (*end != '\0') || (parsed == 0U) ||
	    (parsed > UINT32_MAX)) {
		return 2;
	}
	const struct toy_factory_garden_evaluation_scenario *scenario = NULL;
	for (size_t index = 0U; index < TOY_FACTORY_GARDEN_EVALUATION_SCENARIO_COUNT; ++index) {
		if (strcmp(argv[2], toy_factory_garden_evaluation_scenarios[index].name) == 0) {
			scenario = &toy_factory_garden_evaluation_scenarios[index];
		}
	}
	if (scenario == NULL) {
		return 2;
	}
	struct picosystem_garden_neural_model model;
	struct picosystem_garden_agent_policy neural_policy;
	const struct picosystem_garden_agent_policy *policy;
	int err = 0;
	if (strcmp(argv[3], "neural-candidate") == 0) {
		err = toy_factory_garden_model_read(argv[1], &model, NULL);
		if (err == 0) {
			err = picosystem_garden_neural_policy_init(&model, &neural_policy);
		}
		policy = &neural_policy;
	} else if (strcmp(argv[3], "adaptive") == 0) {
		policy = picosystem_garden_agent_adaptive_policy();
	} else if (strcmp(argv[3], "baseline") == 0) {
		policy = picosystem_garden_agent_baseline_policy();
	} else {
		return 2;
	}
	struct picosystem_garden_world world;
	struct inspection_context inspection = {0};
	if (err == 0) {
		err = toy_factory_garden_evaluation_reset(&world, scenario, (uint32_t)parsed);
	}
	if (err == 0) {
		err = print_world(&world);
	}
	if (err == 0) {
		err = toy_factory_garden_evaluation_advance(
			&world, scenario, policy, INSPECTION_CYCLES * INSPECTION_CYCLE_TICKS,
			observe, &inspection);
	}
	if (err != 0) {
		fprintf(stderr, "Garden inspection failed (%d)\n", err);
		return 1;
	}
	return 0;
}
