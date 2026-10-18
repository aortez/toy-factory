/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_water.h"
#include "garden_evaluation.h"

#include <assert.h>
#include <errno.h>
#include <string.h>

int main(void)
{
	struct picosystem_garden_world world;
	assert(toy_factory_garden_evaluation_reset(&world, &toy_factory_garden_rainfed_scenarios[1],
						   0x940cfdc4U) == 0);
	/* Controlled dry offspring fixture exercises a refusal immediately, without
	 * relying on a particular reference model producing descendants in 32 days.
	 */
	world.plants[1].generation = 1U;
	world.plants[1].parent_lineage_id = world.plants[0].lineage_id;
	world.plants[1].stored_water = 8U;
	world.maximum_generation = 1U;
	world.germination_count = 1U;
	memset(world.moisture, 0, sizeof(world.moisture));
	world.moisture_total = 0U;
	struct toy_factory_garden_landing_model model;
	const struct toy_factory_garden_landing_feature_config features = {.version = 1U,
									   .mode = 1U};
	assert(toy_factory_garden_landing_model_import(picosystem_garden_neural_reference_model(),
						       &features, &model) == 0);
	const struct toy_factory_garden_landing_water_config off = {.version = 1U, .enabled = 0U};
	const struct toy_factory_garden_landing_water_config on = {.version = 1U, .enabled = 1U};
	struct toy_factory_garden_landing_water_run control, guarded;
	assert(toy_factory_garden_landing_water_init(&world, &model, &off, &control) == 0);
	assert(toy_factory_garden_landing_water_init(&world, &model, &on, &guarded) == 0);
	uint32_t a, b;
	assert(toy_factory_garden_landing_water_hash(&control, &a) == 0);
	assert(toy_factory_garden_landing_water_hash(&guarded, &b) == 0 && a != b);
	struct toy_factory_garden_landing_run ordinary = control.base;
	struct toy_factory_garden_landing_water_run untraced = guarded;
	struct picosystem_garden_death_audit deaths, other_deaths;
	struct picosystem_garden_seed_audit seeds, other_seeds;
	struct picosystem_garden_resource_audit resources;
	struct toy_factory_garden_landing_water_audit audit;
	bool seen = false, denied = false;
	for (uint32_t tick = 0U; tick < 32U * 3840U; ++tick) {
		assert(toy_factory_garden_landing_water_step(&control, &deaths, &seeds, NULL,
							     &audit) == 0);
		assert(toy_factory_garden_landing_run_step_audits(&ordinary, &other_deaths,
								  &other_seeds) == 0);
		assert(memcmp(&control.base, &ordinary, sizeof(ordinary)) == 0);
		assert(memcmp(&deaths, &other_deaths, sizeof(deaths)) == 0);
		assert(memcmp(&seeds, &other_seeds, sizeof(seeds)) == 0);
		assert(toy_factory_garden_landing_water_step(&guarded, &deaths, &seeds, &resources,
							     &audit) == 0);
		assert(toy_factory_garden_landing_water_step(&untraced, &other_deaths, &other_seeds,
							     NULL, NULL) == 0);
		assert(memcmp(&guarded, &untraced, sizeof(guarded)) == 0);
		assert(memcmp(&deaths, &other_deaths, sizeof(deaths)) == 0);
		assert(memcmp(&seeds, &other_seeds, sizeof(seeds)) == 0);
		for (uint8_t i = 0U; i < PICOSYSTEM_GARDEN_MAX_PLANTS; ++i) {
			const struct toy_factory_garden_landing_water_winner *const w =
				&audit.plants[i];
			if (w->lineage == 0U) {
				continue;
			}
			seen = true;
			denied |= !w->forecast.water_allowed;
			const struct picosystem_garden_plant *const p =
				&guarded.base.world.plants[i];
			assert(p->lineage_id == w->lineage && p->generation != 0U);
			assert(w->observation.age_ecology_ticks >= 1U &&
			       w->observation.age_ecology_ticks <= 256U);
			assert(memcmp(&p->agent_memory, &w->original.next_memory,
				      sizeof(p->agent_memory)) == 0);
			assert(p->agent_telemetry.last_priority == w->original.proposal.priority);
			assert(p->agent_telemetry.last_action ==
			       (w->forecast.water_allowed ? w->original.proposal.action
							  : PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT));
		}
	}
	assert(seen && denied);
	assert(memcmp(&model, &guarded.base.model, sizeof(model)) == 0);
	/* Invalid config/init never replaces a valid checkpoint. */
	const struct toy_factory_garden_landing_water_run saved = guarded;
	const struct toy_factory_garden_landing_water_config invalid = {.version = 1U,
									.enabled = 2U};
	assert(toy_factory_garden_landing_water_init(&world, &model, &invalid, &guarded) ==
	       -ERANGE);
	assert(memcmp(&saved, &guarded, sizeof(saved)) == 0);
	assert(toy_factory_garden_landing_water_init(&world, &model, NULL, &guarded) == -EINVAL);
	assert(toy_factory_garden_landing_water_step(NULL, &deaths, &seeds, &resources, &audit) ==
	       -EINVAL);
	assert(toy_factory_garden_landing_water_step(&guarded, NULL, &seeds, &resources, &audit) ==
	       -EINVAL);
	assert(toy_factory_garden_landing_water_step(&guarded, &deaths, NULL, &resources, &audit) ==
	       -EINVAL);
	/* Fail after entering the real step, not just at its argument boundary. */
	assert(picosystem_garden_world_reset(&world, 3U) == 0);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 3U) ==
	       0);
	assert(toy_factory_garden_landing_water_init(&world, &model, &on, &guarded) == 0);
	guarded.base.world.logic_tick_count = 14U;
	guarded.base.world.nodes[1].x = 0U;
	const struct toy_factory_garden_landing_water_run failing = guarded;
	memset(&audit, 0xa5, sizeof(audit));
	memset(&resources, 0xa5, sizeof(resources));
	memset(&deaths, 0xa5, sizeof(deaths));
	memset(&seeds, 0xa5, sizeof(seeds));
	const struct toy_factory_garden_landing_water_audit audit_before = audit;
	const struct picosystem_garden_resource_audit resource_before = resources;
	other_deaths = deaths;
	other_seeds = seeds;
	assert(toy_factory_garden_landing_water_step(&guarded, &deaths, &seeds, &resources,
						     &audit) != 0);
	assert(memcmp(&guarded, &failing, sizeof(failing)) == 0);
	assert(memcmp(&audit, &audit_before, sizeof(audit)) == 0);
	assert(memcmp(&resources, &resource_before, sizeof(resources)) == 0);
	assert(memcmp(&deaths, &other_deaths, sizeof(deaths)) == 0);
	assert(memcmp(&seeds, &other_seeds, sizeof(seeds)) == 0);
	/* Failure does not poison a later fresh run. */
	assert(toy_factory_garden_landing_water_init(&world, &model, &on, &guarded) == 0);
	assert(toy_factory_garden_landing_water_step(&guarded, &deaths, &seeds, &resources,
						     &audit) == 0);
	return 0;
}
