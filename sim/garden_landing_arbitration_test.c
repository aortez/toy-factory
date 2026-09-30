/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_water.h"

#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <string.h>

struct fixture {
	int16_t priority[2];
	uint8_t action[2];
	bool allowed[2];
	int error;
	uint16_t *first;
};

static int scripted(const struct picosystem_garden_agent_observation *o,
		    const struct picosystem_garden_agent_memory *memory,
		    struct picosystem_garden_agent_decision *d, const void *context)
{
	const struct fixture *const f = context;
	assert(memory->hidden[0] == 0);
	if (*f->first == UINT16_MAX) {
		*f->first = o->tip_index;
	}
	*d = (struct picosystem_garden_agent_decision){
		.proposal = {.tip_index = o->tip_index,
			     .priority = f->priority[o->tissue_kind],
			     .action = f->action[o->tissue_kind]},
		.next_memory = *memory};
	d->next_memory.hidden[0] = (int8_t)(o->tip_index + 1U);
	return 0;
}

static int eligible(const struct picosystem_garden_agent_observation *o,
		    const struct picosystem_garden_agent_decision *d, bool *allowed,
		    const void *context)
{
	(void)d;
	const struct fixture *const f = context;
	*allowed = f->allowed[o->tissue_kind];
	return f->error;
}

static struct picosystem_garden_world initial_world(void)
{
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_reset(&world, 3U) == 0);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 3U) ==
	       0);
	world.logic_tick_count = 14U;
	return world;
}

static void selection_tests(void)
{
	const struct picosystem_garden_world initial = initial_world();
	uint16_t first = UINT16_MAX;
	struct fixture f = {.priority = {INT16_MAX, INT16_MIN},
			    .action = {2U, 2U},
			    .allowed = {false, true},
			    .first = &first};
	struct picosystem_garden_agent_policy policy = {
		.decide = scripted,
		.context = &f,
		.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS,
		.eligible = eligible,
		.eligibility_context = &f};
	for (unsigned int test = 0U; test < 6U; ++test) {
		struct picosystem_garden_world world = initial;
		first = UINT16_MAX;
		if (test == 1U) { /* All denied: original highest wins as WAIT. */
			f.allowed[1] = false;
		} else if (test == 2U) { /* Genuine WAIT beats an eligible paid bid. */
			f.allowed[0] = true;
			f.allowed[1] = true;
			f.action[0] = 0U;
		} else if (test == 3U) { /* Equal minimum priorities still have a winner. */
			f.priority[0] = INT16_MIN;
			f.action[0] = 2U;
		} else if (test == 4U) { /* Equal maximum priorities retain first-wins. */
			f.priority[0] = INT16_MAX;
			f.priority[1] = INT16_MAX;
		} else if (test == 5U) { /* NULL hook leaves ordinary selection intact. */
			policy.eligible = NULL;
			f.allowed[0] = false;
			f.allowed[1] = false;
		}
		assert(picosystem_garden_world_step_with_policy(&world, &policy) == 0);
		const struct picosystem_garden_plant *const p = &world.plants[0];
		assert(first != UINT16_MAX);
		const uint8_t expected_tissue = test == 0U  ? 1U
						: test < 3U ? 0U
							    : initial.nodes[first].kind;
		assert(p->agent_telemetry.last_tissue_kind == expected_tissue);
		assert(p->agent_telemetry.last_action == ((test == 1U || test == 2U) ? 0U : 2U));
		const uint16_t chosen =
			expected_tissue == 0U ? p->last_shoot_tip_index : p->last_root_tip_index;
		assert(p->agent_memory.hidden[0] == (int8_t)(chosen + 1U));
		assert(p->random_state != initial.plants[0].random_state);
		if (test >= 3U) {
			assert(chosen == first);
		}
	}
	policy.eligible = eligible;
	f.error = -EIO;
	struct picosystem_garden_world world = initial;
	assert(picosystem_garden_world_step_with_policy(&world, &policy) == -EIO);
	f.error = 1;
	world = initial;
	assert(picosystem_garden_world_step_with_policy(&world, &policy) == -EINVAL);
	policy.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_PHASED;
	world = initial;
	assert(picosystem_garden_world_step_with_policy(&world, &policy) == -EINVAL);
	assert(memcmp(&world, &initial, sizeof(world)) == 0);
}

static void predicate_tests(void)
{
	struct picosystem_garden_world world = initial_world();
	struct picosystem_garden_agent_observation o;
	uint16_t tip = 0U;
	while (picosystem_garden_agent_observe_tip(&world, 0U, tip, 42U, &o) != 0) {
		assert(++tip < world.node_count);
	}
	o.age_ecology_ticks = 1U;
	o.stored_water = 5U;
	struct picosystem_garden_agent_decision d = {.proposal = {.tip_index = tip, .action = 2U}};
	const struct toy_factory_garden_seedling_reserve_context ctx = {.world = &world,
									.all_offspring = true};
	bool allowed = false;
	assert(toy_factory_garden_landing_water_eligible(&o, &d, &allowed, &ctx) == 0 && allowed);
	world.plants[0].generation = 1U;
	for (uint16_t age = 0U; age <= 257U; ++age) {
		o.age_ecology_ticks = age;
		assert(toy_factory_garden_landing_water_eligible(&o, &d, &allowed, &ctx) == 0);
		assert(allowed == (age == 0U || age == 257U));
	}
	o.age_ecology_ticks = 1U;
	d.proposal.action = 0U;
	assert(toy_factory_garden_landing_water_eligible(&o, &d, &allowed, &ctx) == 0 && allowed);
	d.proposal.action = PICOSYSTEM_GARDEN_AGENT_ACTION_COUNT;
	assert(toy_factory_garden_landing_water_eligible(&o, &d, &allowed, &ctx) == -EINVAL &&
	       allowed);
	assert(toy_factory_garden_landing_water_eligible(&o, &d, NULL, &ctx) == -EINVAL);
}

static void run_tests(void)
{
	struct picosystem_garden_world world = initial_world();
	world.logic_tick_count = 0U;
	world.plants[0].generation = 1U;
	world.plants[0].parent_lineage_id = 99U;
	world.maximum_generation = 1U;
	world.germination_count = 1U;
	world.plants[0].stored_water = 8U;
	memset(world.moisture, 0, sizeof(world.moisture));
	world.moisture_total = 0U;
	struct toy_factory_garden_landing_model model;
	const struct toy_factory_garden_landing_feature_config features = {.version = 1U,
									   .mode = 1U};
	assert(toy_factory_garden_landing_model_import(picosystem_garden_neural_reference_model(),
						       &features, &model) == 0);
	struct toy_factory_garden_landing_water_config config = {.version = 2U, .enabled = 1U};
	struct toy_factory_garden_landing_water_run run, other;
	uint32_t hashes[2];
	for (uint8_t mode = 0U; mode < 2U; ++mode) {
		config.eligible = mode;
		assert(toy_factory_garden_landing_water_init(&world, &model, &config, &run) == 0);
		run.base.world.logic_tick_count = 14U;
		other = run;
		assert(toy_factory_garden_landing_water_hash(&run, &hashes[mode]) == 0);
		struct picosystem_garden_death_audit deaths, other_deaths;
		struct picosystem_garden_seed_audit seeds, other_seeds;
		struct picosystem_garden_resource_audit resources;
		struct toy_factory_garden_landing_water_audit audit;
		for (unsigned int tick = 0U; tick < 3840U; ++tick) {
			assert(toy_factory_garden_landing_water_step(&run, &deaths, &seeds,
								     &resources, &audit) == 0);
			assert(toy_factory_garden_landing_water_step(
				       &other, &other_deaths, &other_seeds, NULL, NULL) == 0);
			assert(memcmp(&run, &other, sizeof(run)) == 0);
			assert(memcmp(&deaths, &other_deaths, sizeof(deaths)) == 0);
			assert(memcmp(&seeds, &other_seeds, sizeof(seeds)) == 0);
			FILE *stream = tmpfile();
			assert(stream != NULL);
			assert(toy_factory_garden_landing_water_print(stream, &run, &audit) == 0);
			assert(fclose(stream) == 0);
		}
		/* A failure after observing one bid must roll back every output. */
		assert(toy_factory_garden_landing_water_init(&world, &model, &config, &run) == 0);
		run.base.world.logic_tick_count = 14U;
		run.base.world.nodes[3].x = 0U;
		other = run;
		memset(&audit, 0xa5, sizeof(audit));
		memset(&resources, 0xa5, sizeof(resources));
		const struct toy_factory_garden_landing_water_audit saved_audit = audit;
		const struct picosystem_garden_resource_audit saved_resources = resources;
		other_deaths = deaths;
		other_seeds = seeds;
		assert(toy_factory_garden_landing_water_step(&run, &deaths, &seeds, &resources,
							     &audit) != 0);
		assert(memcmp(&run, &other, sizeof(run)) == 0);
		assert(memcmp(&audit, &saved_audit, sizeof(audit)) == 0);
		assert(memcmp(&resources, &saved_resources, sizeof(resources)) == 0);
		assert(memcmp(&deaths, &other_deaths, sizeof(deaths)) == 0);
		assert(memcmp(&seeds, &other_seeds, sizeof(seeds)) == 0);
	}
	assert(hashes[0] != hashes[1]);
	for (unsigned int test = 0U; test < 3U; ++test) {
		config = (struct toy_factory_garden_landing_water_config){
			.version = 2U, .enabled = 1U, .eligible = 1U};
		if (test == 0U) {
			config.enabled = 0U;
		}
		if (test == 1U) {
			config.eligible = 2U;
		}
		if (test == 2U) {
			config.version = 1U;
		}
		assert(toy_factory_garden_landing_water_init(&world, &model, &config, &run) ==
		       -ERANGE);
		assert(memcmp(&run, &other, sizeof(run)) == 0);
	}
}

int main(void)
{
	selection_tests();
	predicate_tests();
	run_tests();
	return 0;
}
