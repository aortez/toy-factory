/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_evaluation.h"
#include "garden_seedling_reserve.h"

static int base_decide(const struct picosystem_garden_agent_observation *observation,
		       const struct picosystem_garden_agent_memory *memory,
		       struct picosystem_garden_agent_decision *decision, const void *context)
{
	*decision = (struct picosystem_garden_agent_decision){
		.next_memory = *memory,
		.proposal = {.tip_index = observation->tip_index,
			     .priority = 123,
			     .action = PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND,
			     .candidate_count = observation->candidate_count},
	};
	decision->next_memory.hidden[0] = 17;
	for (uint8_t i = 0U; i < observation->candidate_count; ++i) {
		decision->proposal.candidate_order[i] = i;
	}
	return *(const int *)context;
}

int main(void)
{
	struct picosystem_garden_world world;
	assert(toy_factory_garden_evaluation_reset(&world, &toy_factory_garden_rainfed_scenarios[0],
						   123U) == 0);
	struct picosystem_garden_agent_observation o;
	bool found = false;
	for (uint16_t i = 0U; i < world.node_count; ++i) {
		if (picosystem_garden_agent_observe_tip(&world, 0U, i, 42U, &o) == 0) {
			found = true;
			break;
		}
	}
	assert(found && o.candidate_count >= 2U);
	o.species_id = PICOSYSTEM_GARDEN_SPECIES_FLOWER;
	o.vigor = 0;
	o.plant_node_count = 10U;
	o.root_node_count = 2U;
	o.tissue_kind = PICOSYSTEM_GARDEN_NODE_STEM;
	o.sun_phase = 64U;
	o.maintenance_phase = 0U;
	o.stored_energy = 256U;
	o.stored_water = 13U;
	o.last_energy_income = 4U;
	o.tip_moisture = 1U;
	for (uint8_t i = 0U; i < o.candidate_count; ++i) {
		o.candidates[i].flags = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS |
					PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE;
		o.candidates[i].y = PICOSYSTEM_GARDEN_SOIL_TOP_PIXELS;
		o.candidates[i].moisture = 5U;
	}
	int base_error = 0;
	const struct picosystem_garden_agent_memory memory = {.hidden = {3, -7}};
	struct picosystem_garden_agent_decision original;
	assert(base_decide(&o, &memory, &original, &base_error) == 0);
	struct picosystem_garden_agent_proposal p = original.proposal;
	struct toy_factory_garden_seedling_reserve_forecast f;
	/* A ninth non-root node crosses the water upkeep boundary. */
	assert(toy_factory_garden_seedling_reserve_forecast(&o, &p, &f) == 0 && f.allowed);
	assert(f.water_upkeep == 2U && f.water_reserve == 8U && !f.wet_root);
	--o.stored_water;
	assert(toy_factory_garden_seedling_reserve_forecast(&o, &p, &f) == 0 && !f.allowed &&
	       f.energy.allowed && !f.water_allowed);
	p.action = PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP;
	p.candidate_count = 0U;
	o.stored_water = 9U;
	assert(toy_factory_garden_seedling_reserve_forecast(&o, &p, &f) == 0 && f.allowed &&
	       f.water_upkeep == 1U && f.water_reserve == 4U);
	o.tissue_kind = PICOSYSTEM_GARDEN_NODE_ROOT;
	o.candidate_count = 3U;
	assert(base_decide(&o, &memory, &original, &base_error) == 0);
	p = original.proposal;
	o.stored_water = 6U;
	assert(toy_factory_garden_seedling_reserve_forecast(&o, &p, &f) == 0 && f.allowed &&
	       f.wet_root && f.water_reserve == 1U && f.destination == 0U);
	--o.stored_water;
	assert(toy_factory_garden_seedling_reserve_forecast(&o, &p, &f) == 0 && !f.allowed);
	o.stored_water = 6U;
	o.candidates[0].moisture = o.tip_moisture;
	o.candidates[1].moisture = 30U;
	assert(toy_factory_garden_seedling_reserve_forecast(&o, &p, &f) == 0 && !f.allowed &&
	       !f.wet_root && f.destination == 0U);
	/* The exception follows execution order, not the wettest visible candidate. */
	p.candidate_order[0] = 1U;
	p.candidate_order[1] = 0U;
	assert(toy_factory_garden_seedling_reserve_forecast(&o, &p, &f) == 0 && f.allowed &&
	       f.wet_root && f.destination == 1U);
	p = original.proposal;
	o.candidates[0].flags = 0U;
	assert(toy_factory_garden_seedling_reserve_forecast(&o, &p, &f) == 0 && f.allowed &&
	       f.destination == 1U);
	o.candidates[1].y = PICOSYSTEM_GARDEN_SOIL_TOP_PIXELS - 1U;
	assert(toy_factory_garden_seedling_reserve_forecast(&o, &p, &f) == 0 && !f.wet_root);
	o.candidates[1].y = PICOSYSTEM_GARDEN_SOIL_TOP_PIXELS;
	o.stored_energy = 9U;
	o.last_energy_income = 0U;
	o.sun_phase = 125U;
	assert(toy_factory_garden_seedling_reserve_forecast(&o, &p, &f) == 0 && !f.allowed &&
	       f.water_allowed && !f.energy.allowed);
	o.sun_phase = 128U;
	o.stored_energy = 256U;
	assert(toy_factory_garden_seedling_reserve_forecast(&o, &p, &f) == 0 && !f.allowed);
	p.action = PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT;
	p.candidate_count = 0U;
	o.stored_water = 0U;
	assert(toy_factory_garden_seedling_reserve_forecast(&o, &p, &f) == 0 && f.allowed &&
	       f.water_cost == 0U && f.water_reserve == 0U);
	p = original.proposal;
	o.stored_water = 512U;
	o.sun_phase = 64U;
	o.last_energy_income = 4U;
	for (uint8_t species = 0U; species < PICOSYSTEM_GARDEN_SPECIES_COUNT; ++species) {
		o.species_id = species;
		assert(toy_factory_garden_seedling_reserve_forecast(&o, &p, &f) == 0 && f.allowed);
		assert(f.water_cost ==
		       (species == PICOSYSTEM_GARDEN_SPECIES_GROUND_COVER ? 4U : 5U));
		const uint32_t cost = f.energy.growth_cost;
		o.vigor = 1;
		assert(toy_factory_garden_seedling_reserve_forecast(&o, &p, &f) == 0 &&
		       f.energy.growth_cost == cost - 1U);
		o.vigor = 0;
	}
	const struct toy_factory_garden_seedling_reserve_forecast saved = f;
	assert(toy_factory_garden_seedling_reserve_forecast(NULL, &p, &f) == -EINVAL);
	assert(toy_factory_garden_seedling_reserve_forecast(&o, NULL, &f) == -EINVAL);
	assert(toy_factory_garden_seedling_reserve_forecast(&o, &p, NULL) == -EINVAL);
	p.candidate_order[1] = p.candidate_order[0];
	assert(toy_factory_garden_seedling_reserve_forecast(&o, &p, &f) == -EINVAL);
	p.candidate_order[0] = o.candidate_count;
	assert(toy_factory_garden_seedling_reserve_forecast(&o, &p, &f) == -EINVAL);
	p = original.proposal;
	p.action = PICOSYSTEM_GARDEN_AGENT_ACTION_COUNT;
	assert(toy_factory_garden_seedling_reserve_forecast(&o, &p, &f) == -EINVAL);
	p = original.proposal;
	++p.tip_index;
	assert(toy_factory_garden_seedling_reserve_forecast(&o, &p, &f) == -EINVAL);
	p = original.proposal;
	p.candidate_count = 0U;
	assert(toy_factory_garden_seedling_reserve_forecast(&o, &p, &f) == -EINVAL);
	assert(memcmp(&f, &saved, sizeof(f)) == 0);

	struct picosystem_garden_agent_policy base = {
		.decide = base_decide,
		.context = &base_error,
		.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_PHASED};
	struct picosystem_garden_agent_policy policy;
	struct toy_factory_garden_seedling_reserve_context context;
	assert(toy_factory_garden_seedling_reserve_init(&base, &world, 77U,
							TOY_FACTORY_GARDEN_SEEDLING_BOTH, &context,
							&policy) == 0);
	assert(policy.arbitration == base.arbitration);
	o.age_ecology_ticks = 1U;
	world.plants[o.plant_index].lineage_id = 77U;
	world.plants[o.plant_index].generation = 0U;
	assert(!toy_factory_garden_seedling_reserve_active(&context, &o));
	world.plants[o.plant_index].generation = 1U;
	assert(toy_factory_garden_seedling_reserve_active(&context, &o));
	o.age_ecology_ticks = 256U;
	assert(toy_factory_garden_seedling_reserve_active(&context, &o));
	o.age_ecology_ticks = 257U;
	assert(!toy_factory_garden_seedling_reserve_active(&context, &o));
	o.age_ecology_ticks = 0U;
	assert(!toy_factory_garden_seedling_reserve_active(&context, &o));
	o.age_ecology_ticks = 1U;
	world.plants[o.plant_index].flags |= PICOSYSTEM_GARDEN_PLANT_DEAD;
	assert(!toy_factory_garden_seedling_reserve_active(&context, &o));
	world.plants[o.plant_index].flags &= (uint8_t)~PICOSYSTEM_GARDEN_PLANT_DEAD;
	context.lineage = 78U;
	assert(!toy_factory_garden_seedling_reserve_active(&context, &o));
	context.lineage = 0U;
	assert(!toy_factory_garden_seedling_reserve_active(&context, &o));
	context.lineage = 77U;
	assert(!toy_factory_garden_seedling_reserve_active(NULL, &o));
	assert(!toy_factory_garden_seedling_reserve_active(&context, NULL));
	const struct picosystem_garden_world world_before = world;
	const struct picosystem_garden_agent_observation observation_before = o;
	struct picosystem_garden_agent_decision decision;
	assert(picosystem_garden_agent_decide(&policy, &o, &memory, &decision) == 0 &&
	       decision.proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND);
	assert(memcmp(&world, &world_before, sizeof(world)) == 0);
	assert(memcmp(&o, &observation_before, sizeof(o)) == 0);
	o.stored_water = 0U;
	assert(picosystem_garden_agent_decide(&policy, &o, &memory, &decision) == 0 &&
	       decision.proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT);
	assert(decision.proposal.priority == 123 && decision.next_memory.hidden[0] == 17 &&
	       memory.hidden[0] == 3 && decision.proposal.candidate_count == 0U);
	for (uint8_t i = 0U; i < PICOSYSTEM_GARDEN_AGENT_MAX_CANDIDATES; ++i) {
		assert(decision.proposal.candidate_order[i] ==
		       PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE);
	}
	o.age_ecology_ticks = 257U;
	assert(picosystem_garden_agent_decide(&policy, &o, &memory, &decision) == 0 &&
	       decision.proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND);
	base_error = -EIO;
	assert(picosystem_garden_agent_decide(&policy, &o, &memory, &decision) == -EIO);
	const struct picosystem_garden_agent_policy saved_policy = policy;
	const struct toy_factory_garden_seedling_reserve_context saved_context = context;
	assert(toy_factory_garden_seedling_reserve_init(NULL, &world, 77U,
							TOY_FACTORY_GARDEN_SEEDLING_BOTH, &context,
							&policy) == -EINVAL);
	assert(toy_factory_garden_seedling_reserve_init(&base, NULL, 77U,
							TOY_FACTORY_GARDEN_SEEDLING_BOTH, &context,
							&policy) == -EINVAL);
	assert(toy_factory_garden_seedling_reserve_init(&base, &world, 77U,
							TOY_FACTORY_GARDEN_SEEDLING_BOTH, NULL,
							&policy) == -EINVAL);
	assert(toy_factory_garden_seedling_reserve_init(&base, &world, 77U,
							TOY_FACTORY_GARDEN_SEEDLING_BOTH, &context,
							NULL) == -EINVAL);
	assert(toy_factory_garden_seedling_reserve_init(&policy, &world, 77U,
							TOY_FACTORY_GARDEN_SEEDLING_BOTH, &context,
							&policy) == -EINVAL);
	assert(toy_factory_garden_seedling_reserve_init(&policy, &world, 77U,
							TOY_FACTORY_GARDEN_SEEDLING_BOTH, &context,
							&base) == -EINVAL);
	assert(toy_factory_garden_seedling_reserve_init(
		       &base, &world, 77U, (enum toy_factory_garden_seedling_component)99, &context,
		       &policy) == -EINVAL);
	assert(memcmp(&policy, &saved_policy, sizeof(policy)) == 0);
	assert(memcmp(&context, &saved_context, sizeof(context)) == 0);
	/* Selection changes only which unchanged forecast is enforced. */
	base_error = 0;
	o = observation_before;
	o.age_ecology_ticks = 1U;
	for (unsigned int mask = 0U; mask < 4U; ++mask) {
		o.stored_energy = (mask & 1U) != 0U ? 256U : 0U;
		o.stored_water = (mask & 2U) != 0U ? 512U : 0U;
		assert(base_decide(&o, &memory, &original, &base_error) == 0);
		assert(toy_factory_garden_seedling_reserve_forecast(&o, &original.proposal, &f) ==
		       0);
		for (unsigned int mode = 0U; mode < 3U; ++mode) {
			const enum toy_factory_garden_seedling_component component =
				(enum toy_factory_garden_seedling_component)mode;
			const bool expected =
				mode == 0U ? mask == 3U : (mask & (mode == 1U ? 1U : 2U)) != 0U;
			assert(toy_factory_garden_seedling_reserve_allows(&f, component) ==
			       expected);
			assert(toy_factory_garden_seedling_reserve_init(
				       &base, &world, 77U, component, &context, &policy) == 0);
			assert(policy.arbitration == base.arbitration);
			assert(picosystem_garden_agent_decide(&policy, &o, &memory, &decision) ==
			       0);
			assert(decision.proposal.action ==
			       (expected ? PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND
					 : PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT));
			assert(decision.proposal.priority == original.proposal.priority &&
			       memcmp(&decision.next_memory, &original.next_memory,
				      sizeof(decision.next_memory)) == 0);
			if (expected) {
				assert(memcmp(&decision, &original, sizeof(decision)) == 0);
			} else {
				assert(decision.proposal.candidate_count == 0U);
				for (uint8_t i = 0U; i < PICOSYSTEM_GARDEN_AGENT_MAX_CANDIDATES;
				     ++i) {
					assert(decision.proposal.candidate_order[i] ==
					       PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE);
				}
			}
		}
	}
	o.sun_phase = 128U;
	assert(toy_factory_garden_seedling_reserve_forecast(&o, &original.proposal, &f) == 0);
	assert(!toy_factory_garden_seedling_reserve_allows(&f, TOY_FACTORY_GARDEN_SEEDLING_ENERGY));
	assert(toy_factory_garden_seedling_reserve_allows(&f, TOY_FACTORY_GARDEN_SEEDLING_WATER));
	assert(!toy_factory_garden_seedling_reserve_allows(NULL, TOY_FACTORY_GARDEN_SEEDLING_BOTH));
	assert(!toy_factory_garden_seedling_reserve_allows(
		&f, (enum toy_factory_garden_seedling_component)99));
	enum toy_factory_garden_seedling_component selected = TOY_FACTORY_GARDEN_SEEDLING_BOTH;
	assert(toy_factory_garden_seedling_component_parse(NULL, &selected) == -EINVAL);
	assert(toy_factory_garden_seedling_component_parse("energy", NULL) == -EINVAL);
	assert(toy_factory_garden_seedling_component_parse("unknown", &selected) == -EINVAL);
	assert(selected == TOY_FACTORY_GARDEN_SEEDLING_BOTH);
	assert(toy_factory_garden_seedling_component_name(
		       (enum toy_factory_garden_seedling_component)99) == NULL);
	for (unsigned int mode = 0U; mode < 3U; ++mode) {
		const enum toy_factory_garden_seedling_component component =
			(enum toy_factory_garden_seedling_component)mode;
		assert(toy_factory_garden_seedling_component_parse(
			       toy_factory_garden_seedling_component_name(component), &selected) ==
		       0);
		assert(selected == component);
	}
	assert(memcmp(&world, &world_before, sizeof(world)) == 0);
	assert(toy_factory_garden_seedling_reserve_offspring_init(&base, &world, &context,
								  &policy) == 0);
	assert(context.all_offspring && context.lineage == 0U &&
	       context.component == TOY_FACTORY_GARDEN_SEEDLING_BOTH);
	o = observation_before;
	o.stored_water = 0U;
	for (uint16_t generation = 0U; generation < 3U; ++generation) {
		world.plants[o.plant_index].generation = generation;
		for (uint16_t age = 0U; age <= 257U; ++age) {
			o.age_ecology_ticks = age;
			const bool eligible = (generation != 0U) && (age >= 1U) && (age <= 256U);
			assert(toy_factory_garden_seedling_reserve_active(&context, &o) ==
			       eligible);
			assert(picosystem_garden_agent_decide(&policy, &o, &memory, &decision) ==
			       0);
			assert(decision.proposal.action ==
			       (eligible ? PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT
					 : PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND));
			assert(decision.proposal.priority == 123 &&
			       decision.next_memory.hidden[0] == 17);
		}
	}
	o.age_ecology_ticks = 1U;
	world.plants[o.plant_index].lineage_id = UINT32_MAX;
	assert(toy_factory_garden_seedling_reserve_active(&context, &o));
	world.plants[o.plant_index].flags |= PICOSYSTEM_GARDEN_PLANT_DEAD;
	assert(!toy_factory_garden_seedling_reserve_active(&context, &o));
	const struct toy_factory_garden_seedling_reserve_context all_context = context;
	const struct picosystem_garden_agent_policy all_policy = policy;
	assert(toy_factory_garden_seedling_reserve_offspring_init(NULL, &world, &context,
								  &policy) == -EINVAL);
	assert(toy_factory_garden_seedling_reserve_offspring_init(&base, NULL, &context, &policy) ==
	       -EINVAL);
	assert(toy_factory_garden_seedling_reserve_offspring_init(&base, &world, NULL, &policy) ==
	       -EINVAL);
	assert(toy_factory_garden_seedling_reserve_offspring_init(&base, &world, &context, NULL) ==
	       -EINVAL);
	assert(toy_factory_garden_seedling_reserve_offspring_init(&policy, &world, &context,
								  &policy) == -EINVAL);
	assert(memcmp(&context, &all_context, sizeof(context)) == 0);
	assert(memcmp(&policy, &all_policy, sizeof(policy)) == 0);
	assert(toy_factory_garden_seedling_reserve_init(&base, &world, 0U,
							TOY_FACTORY_GARDEN_SEEDLING_BOTH, &context,
							&policy) == 0);
	assert(!context.all_offspring && !toy_factory_garden_seedling_reserve_active(&context, &o));
	puts("First-day reserve, component selection and named/all-offspring boundaries passed");
	return 0;
}
