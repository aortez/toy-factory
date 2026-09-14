/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_evaluation.h"
#include "garden_reserve_policy.h"

static int base_decide(const struct picosystem_garden_agent_observation *observation,
		       const struct picosystem_garden_agent_memory *memory,
		       struct picosystem_garden_agent_decision *decision, const void *context)
{
	const int result = *(const int *)context;
	*decision = (struct picosystem_garden_agent_decision){
		.next_memory = *memory,
		.proposal = {.tip_index = observation->tip_index,
			     .priority = 123,
			     .action = PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND,
			     .candidate_count = observation->candidate_count},
	};
	decision->next_memory.hidden[0] = 17;
	for (uint8_t index = 0U; index < observation->candidate_count; ++index) {
		decision->proposal.candidate_order[index] = index;
	}
	return result;
}

int main(void)
{
	struct picosystem_garden_world world;
	assert(toy_factory_garden_evaluation_reset(&world, &toy_factory_garden_rainfed_scenarios[0],
						   123U) == 0);
	struct picosystem_garden_agent_observation o;
	bool found = false;
	for (uint16_t index = 0U; index < world.node_count; ++index) {
		if (picosystem_garden_agent_observe_tip(&world, 0U, index, 42U, &o) == 0) {
			found = true;
			break;
		}
	}
	assert(found);
	o.species_id = PICOSYSTEM_GARDEN_SPECIES_SHRUB;
	o.vigor = 0;
	o.plant_node_count = 8U;
	o.sun_phase = 64U;
	o.maintenance_phase = 0U;
	o.last_energy_income = 0U;
	for (uint8_t index = 0U; index < o.candidate_count; ++index) {
		o.candidates[index].flags = 0U;
	}
	o.candidates[0].flags = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS |
				PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE;
	struct toy_factory_garden_reserve_forecast f;
	/* EXTEND crosses the eight-node upkeep boundary; FINISH does not. */
	o.stored_energy = 104U;
	assert(toy_factory_garden_reserve_forecast(&o, 1U, &f) == 0 && f.allowed);
	assert(f.post_nodes == 9U && f.maintenance_cost == 2U && f.projected_sunset == 64 &&
	       f.night_upkeep == 64U);
	--o.stored_energy;
	assert(toy_factory_garden_reserve_forecast(&o, 1U, &f) == 0 && !f.allowed);
	o.stored_energy = 56U;
	assert(toy_factory_garden_reserve_forecast(&o, 2U, &f) == 0 && f.allowed);
	assert(f.post_nodes == 8U && f.maintenance_cost == 1U);
	--o.stored_energy;
	assert(toy_factory_garden_reserve_forecast(&o, 2U, &f) == 0 && !f.allowed);
	o.vigor = 1;
	assert(toy_factory_garden_reserve_forecast(&o, 2U, &f) == 0 && f.allowed &&
	       f.growth_cost == 7U);
	o.vigor = 0;
	o.candidates[0].flags = 0U;
	o.stored_energy = 56U;
	assert(toy_factory_garden_reserve_forecast(&o, 1U, &f) == 0 && f.allowed &&
	       f.post_nodes == 8U);
	o.candidates[0].flags = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS |
				PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE;
	for (uint8_t species = 0U; species < PICOSYSTEM_GARDEN_SPECIES_COUNT; ++species) {
		o.species_id = species;
		assert(toy_factory_garden_reserve_forecast(&o, 1U, &f) == 0 &&
		       f.growth_cost == 9U - species);
	}
	o.species_id = PICOSYSTEM_GARDEN_SPECIES_SHRUB;
	o.sun_phase = 127U;
	o.maintenance_phase = 3U;
	o.stored_energy = 74U;
	assert(toy_factory_garden_reserve_forecast(&o, 1U, &f) == 0 && f.allowed &&
	       f.daylight_upkeep == 2U);
	--o.stored_energy;
	assert(toy_factory_garden_reserve_forecast(&o, 1U, &f) == 0 && !f.allowed);
	o.sun_phase = 128U;
	o.maintenance_phase = 0U;
	assert(toy_factory_garden_reserve_forecast(&o, 1U, &f) == 0 && !f.allowed);
	assert(toy_factory_garden_reserve_forecast(&o, 0U, &f) == 0 && f.allowed);
	/* Even large credited income cannot finance a night beyond storage capacity. */
	o.sun_phase = 64U;
	o.stored_energy = 256U;
	o.last_energy_income = 255U;
	o.plant_node_count = 64U;
	assert(toy_factory_garden_reserve_forecast(&o, 1U, &f) == 0 && !f.allowed &&
	       f.projected_sunset == 256);
	o.plant_node_count = UINT16_MAX;
	assert(toy_factory_garden_reserve_forecast(&o, 1U, &f) == 0 && !f.allowed &&
	       f.post_nodes == 65536U);
	o.plant_node_count = 8U;
	o.last_energy_income = 4U;
	o.stored_energy = 9U;
	assert(toy_factory_garden_reserve_forecast(&o, 1U, &f) == 0 && !f.allowed &&
	       f.projected_sunset >= 64);
	const struct toy_factory_garden_reserve_forecast saved = f;
	assert(toy_factory_garden_reserve_forecast(NULL, 1U, &f) == -EINVAL &&
	       memcmp(&f, &saved, sizeof(f)) == 0);
	assert(toy_factory_garden_reserve_forecast(&o, 3U, &f) == -EINVAL);
	assert(toy_factory_garden_reserve_forecast(&o, 1U, NULL) == -EINVAL);
	int result = 0;
	struct picosystem_garden_agent_policy base = {
		.decide = base_decide,
		.context = &result,
		.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS};
	struct picosystem_garden_agent_policy policy;
	assert(toy_factory_garden_reserve_init(&base, &policy) == 0);
	assert(policy.arbitration == base.arbitration);
	const struct picosystem_garden_agent_memory memory = {.hidden = {3, -7}};
	const struct picosystem_garden_agent_observation before = o;
	struct picosystem_garden_agent_decision decision;
	assert(picosystem_garden_agent_decide(&policy, &o, &memory, &decision) == 0);
	assert(decision.proposal.action == 0U && decision.proposal.priority == 123 &&
	       decision.proposal.tip_index == o.tip_index);
	assert(decision.proposal.candidate_count == 0U && decision.next_memory.hidden[0] == 17 &&
	       memory.hidden[0] == 3);
	for (uint8_t i = 0U; i < PICOSYSTEM_GARDEN_AGENT_MAX_CANDIDATES; ++i) {
		assert(decision.proposal.candidate_order[i] ==
		       PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE);
	}
	assert(memcmp(&o, &before, sizeof(o)) == 0);
	o.stored_energy = 104U;
	assert(picosystem_garden_agent_decide(&policy, &o, &memory, &decision) == 0 &&
	       decision.proposal.action == 1U);
	result = -EIO;
	assert(picosystem_garden_agent_decide(&policy, &o, &memory, &decision) == -EIO);
	const struct picosystem_garden_agent_policy saved_policy = policy;
	assert(toy_factory_garden_reserve_init(NULL, &policy) == -EINVAL);
	assert(toy_factory_garden_reserve_init(&base, NULL) == -EINVAL);
	assert(toy_factory_garden_reserve_init(&policy, &policy) == -EINVAL);
	assert(toy_factory_garden_reserve_init(&policy, &base) == -EINVAL);
	assert(memcmp(&policy, &saved_policy, sizeof(policy)) == 0);
	puts("Reserve forecast and wrapper boundary checks passed");
	return 0;
}
