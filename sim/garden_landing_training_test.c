/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_mutation.h"
#include "garden_landing_ledger.h"

#include <assert.h>
#include <errno.h>
#include <string.h>

static struct toy_factory_garden_landing_ledger history;
static struct toy_factory_garden_lifetimes lifetimes;

static void mutations(void)
{
	struct toy_factory_garden_landing_model model;
	const struct toy_factory_garden_landing_feature_config config = {.version = 1U, .mode = 2U};
	assert(toy_factory_garden_landing_model_import(picosystem_garden_neural_reference_model(),
						       &config, &model) == 0);
	const struct toy_factory_garden_landing_model initial = model;
	const uint32_t starts[] = {0U, 1U, UINT32_MAX, 0x6d697833U};
	for (size_t i = 0U; i < sizeof(starts) / sizeof(starts[0]); ++i) {
		struct toy_factory_garden_mutation_rng rng = {.state = starts[i]}, old_rng = rng;
		struct picosystem_garden_neural_model old = model.legacy;
		assert(toy_factory_garden_model_mutate(&old, &old_rng, 4096U) == 0);
		assert(toy_factory_garden_landing_mutate(&model, &rng, 4096U, 0U) == 0);
		assert(memcmp(&model.legacy, &old, sizeof(old)) == 0);
		assert(rng.state == old_rng.state);
		const struct picosystem_garden_neural_model before = model.legacy;
		assert(toy_factory_garden_landing_mutate(&model, &rng, 0U, 4096U) == 0);
		assert(memcmp(&model.legacy, &before, sizeof(before)) == 0);
		assert(memcmp(&model.config, &initial.config, sizeof(config)) == 0);
		assert(toy_factory_garden_landing_model_validate(&model) == 0);
	}
	struct toy_factory_garden_mutation_rng rng = {.state = 123U};
	const struct toy_factory_garden_landing_model saved = model;
	assert(toy_factory_garden_landing_mutate(&model, &rng, 0U, 0U) == -EINVAL);
	assert(toy_factory_garden_landing_mutate(&model, &rng, 4097U, 1U) == -EINVAL);
	assert(toy_factory_garden_landing_mutate(&model, &rng, 1U, 4097U) == -EINVAL);
	assert(toy_factory_garden_landing_mutate(NULL, &rng, 1U, 1U) == -EINVAL);
	assert(toy_factory_garden_landing_mutate(&model, NULL, 1U, 1U) == -EINVAL);
	assert(rng.state == 123U && memcmp(&model, &saved, sizeof(model)) == 0);
	model.config.mode = 3U;
	assert(toy_factory_garden_landing_mutate(&model, &rng, 1U, 1U) == -EINVAL);
	assert(rng.state == 123U && model.config.mode == 3U);
}

static void ledger_boundaries(void)
{
	struct picosystem_garden_world world;
	assert(toy_factory_garden_evaluation_reset(&world, &toy_factory_garden_rainfed_scenarios[0],
						   1U) == 0);
	assert(toy_factory_garden_lifetimes_reset(&lifetimes) == 0);
	for (uint8_t i = 0U; i < world.plant_count; ++i) {
		assert(toy_factory_garden_lifetimes_birth(&lifetimes, world.plants[i].lineage_id,
							  0U, world.plants[i].species_id, 0U) == 0);
	}
	assert(toy_factory_garden_landing_ledger_reset(&history, &world, &lifetimes) == 0);
	assert(history.count == world.lineage_sequence && history.seed_count == 0U);
	const struct picosystem_garden_seed_audit audit = {.ecology_step = true};
	assert(toy_factory_garden_landing_ledger_step(&history, &world, &lifetimes, &audit) ==
	       -EINVAL);
	world.logic_tick_count = PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR;
	assert(toy_factory_garden_landing_ledger_step(&history, &world, &lifetimes, &audit) == 0);
	world.logic_tick_count += PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR;
	world.seed_count = 1U;
	world.seeds[0].parent_lineage_id = 1U;
	history.seed_count = TOY_FACTORY_GARDEN_LANDING_MAX_PURCHASES;
	assert(toy_factory_garden_landing_ledger_step(&history, &world, &lifetimes, &audit) ==
	       -ENOSPC);
	assert(history.seed_count == TOY_FACTORY_GARDEN_LANDING_MAX_PURCHASES);
	assert(toy_factory_garden_landing_ledger_reset(&history, &world, &lifetimes) == -EINVAL);
	assert(toy_factory_garden_landing_ledger_print(NULL, &history, &lifetimes) == -EINVAL);
}

int main(void)
{
	mutations();
	ledger_boundaries();
	return 0;
}
