/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_root_direction.h"
#include "garden_landing_growth.h"
#include "garden_landing_plant_trace.h"
#include "garden_evaluation.h"

#include <assert.h>
#include <errno.h>
#include <string.h>

static struct toy_factory_garden_root_choice config(void)
{
	return (struct toy_factory_garden_root_choice){.all_offspring = true,
						       .energy_reserve = true,
						       .afternoon_reserve = true,
						       .continuous_energy = true,
						       .daylight_energy = true,
						       .wet_direction = true};
}

static void fixture(struct picosystem_garden_world *world,
		    struct picosystem_garden_agent_observation *o,
		    struct picosystem_garden_agent_decision *d)
{
	assert(picosystem_garden_world_reset(world, 3U) == 0);
	world->auto_gardener_enabled = false;
	assert(picosystem_garden_world_plant_seed(world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 12U) ==
	       0);
	world->plants[0].generation = 1U;
	world->plants[0].parent_lineage_id = 1U;
	world->maximum_generation = 1U;
	world->plants[0].age_ecology_ticks = 1U;
	world->logic_tick_count = 15U;
	assert(picosystem_garden_agent_observe_tip(world, 0U, 2U, 42U, o) == 0);
	o->stored_energy = 256U;
	o->stored_water = 256U;
	o->tip_moisture = 0U;
	*d = (struct picosystem_garden_agent_decision){
		.next_memory = {.hidden = {3, -7, 12}},
		.proposal = {.tip_index = 2U,
			     .action = PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND,
			     .priority = 21,
			     .candidate_count = 3U,
			     .candidate_order = {2U, 1U, 0U}}};
	assert(o->candidate_count == 3U);
	for (uint8_t i = 0U; i < o->candidate_count; ++i) {
		o->candidates[i].flags = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE |
					 PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS;
		o->candidates[i].moisture = (uint8_t)(9U - 4U * i);
	}
}

static void guarded_ranking(void)
{
	for (uint8_t fault = 0U; fault < 18U; ++fault) {
		struct picosystem_garden_world world;
		struct picosystem_garden_agent_observation o;
		struct picosystem_garden_agent_decision d;
		fixture(&world, &o, &d);
		struct toy_factory_garden_root_choice choice = config();
		int error = 0;
		uint8_t winner = 1U;
		switch (fault) {
		case 1:
			choice.wet_direction = false;
			winner = 2U;
			break;
		case 2:
			o.candidates[2].moisture = 3U;
			winner = 2U;
			break;
		case 3:
			o.candidates[1].flags = 1U;
			winner = 0U;
			break;
		case 4:
			o.candidates[0].flags = 1U;
			o.candidates[1].flags = 1U;
			winner = 2U;
			break;
		case 5:
			o.stored_water = 8U;
			winner = 2U;
			break;
		case 6:
			o.stored_energy = 0U;
			winner = 2U;
			break;
		case 7:
			o.depth = o.maximum_depth;
			winner = 2U;
			break;
		case 8:
			d.proposal.action = PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP;
			d.proposal.candidate_count = 0U;
			winner = 2U;
			break;
		case 9:
			assert(picosystem_garden_agent_observe_tip(&world, 0U, 1U, 42U, &o) == 0);
			d.proposal.tip_index = o.tip_index;
			d.proposal.candidate_count = o.candidate_count;
			d.proposal.candidate_order[3] = 3U;
			d.proposal.candidate_order[4] = 4U;
			winner = 2U;
			break;
		case 10:
			world.node_count = 32U;
			world.plants[0].node_count = 32U;
			o.plant_node_count = 32U;
			o.shoot_node_count = 30U;
			winner = 2U;
			break;
		case 11:
			d.proposal.candidate_order[0] = 1U;
			error = -ERANGE;
			winner = 2U;
			break;
		case 12:
			choice.all_offspring = false;
			error = -ERANGE;
			winner = 2U;
			break;
		case 13:
			o.species_id = PICOSYSTEM_GARDEN_SPECIES_GROUND_COVER;
			o.candidates[2].moisture = 2U;
			winner = 2U;
			break;
		case 14:
			o.age_ecology_ticks = 2U;
			world.plants[0].age_ecology_ticks = 2U;
			world.logic_tick_count = 30U;
			o.stored_energy = 9U;
			o.sun_phase = PICOSYSTEM_GARDEN_SUN_SUNSET_PHASE;
			winner = 2U;
			break;
		case 15:
			world.plants[0].generation = 0U;
			world.plants[0].parent_lineage_id = 0U;
			o.stored_water = 5U;
			break;
		case 16:
			o.candidates[2].flags = 1U;
			winner = 2U;
			break;
		case 17:
			o.candidates[1].moisture = 2U;
			winner = 0U;
			break;
		default:
			break;
		}
		const struct picosystem_garden_world saved_world = world;
		const struct picosystem_garden_agent_observation saved_o = o;
		struct picosystem_garden_agent_decision expected = d;
		if (winner == 1U) {
			expected.proposal.candidate_order[0] = 1U;
			expected.proposal.candidate_order[1] = 2U;
		} else if (winner == 0U) {
			expected.proposal.candidate_order[0] = 0U;
			expected.proposal.candidate_order[1] = 2U;
			expected.proposal.candidate_order[2] = 1U;
		}
		const int actual = toy_factory_garden_root_direction_apply(
			&world, &o, &choice, TOY_FACTORY_GARDEN_BUDGET_SHOOT, &d);
		if (actual != error) {
			fprintf(stderr, "root direction case %u: expected %d, got %d\n", fault,
				error, actual);
		}
		assert(actual == error);
		assert(memcmp(&d, &expected, sizeof(d)) == 0);
		assert(memcmp(&world, &saved_world, sizeof(world)) == 0);
		assert(memcmp(&o, &saved_o, sizeof(o)) == 0);
	}
}

static int reject(const struct picosystem_garden_world *world,
		  const struct picosystem_garden_agent_observation *o,
		  const struct picosystem_garden_agent_decision *raw,
		  const struct picosystem_garden_agent_decision *applied, void *context)
{
	(void)world;
	(void)o;
	(void)raw;
	(void)applied;
	(void)context;
	return -ECANCELED;
}

static void rollback_and_trace(void)
{
	struct picosystem_garden_world world;
	struct picosystem_garden_agent_observation o;
	struct picosystem_garden_agent_decision d;
	fixture(&world, &o, &d);
	struct toy_factory_garden_root_choice choice = config();
	const struct picosystem_garden_agent_decision saved = d;
	assert(toy_factory_garden_root_direction_apply(NULL, &o, &choice, 2U, &d) == -EINVAL);
	assert(memcmp(&saved, &d, sizeof(d)) == 0);
	FILE *stream = tmpfile();
	assert(stream != NULL);
	world.logic_tick_count = 0U;
	static struct toy_factory_garden_plant_trace trace;
	assert(toy_factory_garden_plant_trace_init(&trace, stream, &world, 32U, 2U, 15U, 30U,
						   TOY_FACTORY_GARDEN_TRACE_DAWN) == 0);
	world.logic_tick_count = 15U;
	assert(toy_factory_garden_root_direction_apply(&world, &o, &choice, 2U, &d) == 0);
	assert(toy_factory_garden_plant_trace_observe(&world, &o, &saved, &d, &trace) == -EFAULT);
	trace.root_choice = choice;
	assert(toy_factory_garden_plant_trace_observe(&world, &o, &saved, &d, &trace) == 0);
	assert(trace.bids[0].raw_direction.candidate_order[0] == 2U);
	assert(trace.bids[0].direction.candidate_order[0] == 1U);
	d.proposal.candidate_order[0] = 0U;
	assert(toy_factory_garden_plant_trace_observe(&world, &o, &saved, &d, &trace) == -EFAULT);
	assert(fclose(stream) == 0);

	assert(toy_factory_garden_evaluation_reset(&world, &toy_factory_garden_rainfed_scenarios[1],
						   3U) == 0);
	struct toy_factory_garden_landing_model model;
	const struct toy_factory_garden_landing_feature_config features = {.version = 1U,
									   .mode = 1U};
	assert(toy_factory_garden_landing_model_import(picosystem_garden_neural_reference_model(),
						       &features, &model) == 0);
	struct toy_factory_garden_landing_growth_run run;
	assert(toy_factory_garden_landing_placement_init(&world, &model, 1U, 1U, &run) == 0);
	run.root_choice = choice;
	struct picosystem_garden_death_audit deaths;
	struct picosystem_garden_seed_audit seeds;
	struct picosystem_garden_resource_audit resources;
	struct picosystem_garden_reproduction_audit reproduction;
	for (unsigned int i = 0U; i < 14U; ++i) {
		assert(toy_factory_garden_landing_growth_step(&run, &deaths, &seeds, &resources) ==
		       0);
	}
	const struct toy_factory_garden_landing_growth_run before = run;
	memset(&deaths, 0xa5, sizeof(deaths));
	const struct picosystem_garden_death_audit saved_deaths = deaths;
	const struct toy_factory_garden_growth_observer observer = {.observe = reject,
								    .reproduction = &reproduction};
	assert(toy_factory_garden_landing_growth_step_observed(&run, &deaths, &seeds, &resources,
							       &observer) == -ECANCELED);
	assert(memcmp(&run, &before, sizeof(run)) == 0);
	assert(memcmp(&deaths, &saved_deaths, sizeof(deaths)) == 0);
	assert(toy_factory_garden_landing_growth_step(&run, &deaths, &seeds, &resources) == 0);
	uint32_t enabled, disabled;
	assert(toy_factory_garden_landing_growth_hash(&run, &enabled) == 0);
	run.root_choice.wet_direction = false;
	assert(toy_factory_garden_landing_growth_hash(&run, &disabled) == 0);
	assert(enabled != disabled);
}

int main(void)
{
	guarded_ranking();
	rollback_and_trace();
	return 0;
}
