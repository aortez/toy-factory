/* SPDX-License-Identifier: Apache-2.0 */
#include <errno.h>
#include <string.h>

#include "garden_leaf_policies.h"

static int decide(const struct picosystem_garden_leaf_observation *observation,
		  const struct picosystem_garden_agent_memory *memory,
		  struct picosystem_garden_leaf_decision *decision, const void *context)
{
	if ((observation == NULL) || (memory == NULL) || (decision == NULL) || (context == NULL)) {
		return -EINVAL;
	}
	const unsigned int mode = *(const unsigned int *)context;
	*decision = (struct picosystem_garden_leaf_decision){
		.node_index = observation->node_index,
		.next_memory = *memory,
		.action = PICOSYSTEM_GARDEN_LEAF_WAIT,
	};
	if ((mode == 0U) || (observation->condition > 128U)) {
		return 0;
	}
	unsigned int energy = observation->renewal_energy;
	unsigned int water = observation->renewal_water;
	if (mode == 2U) {
		if (observation->light < 128U) {
			return 0;
		}
		const unsigned int energy_reserve = observation->maintenance_energy * 40U;
		const unsigned int water_reserve = observation->maintenance_water * 40U;
		energy += energy_reserve < 128U ? energy_reserve : 128U;
		water += water_reserve < 256U ? water_reserve : 256U;
	}
	if ((observation->stored_energy >= energy) && (observation->stored_water >= water)) {
		decision->action = PICOSYSTEM_GARDEN_LEAF_RENEW;
	}
	return 0;
}

const struct picosystem_garden_leaf_policy *toy_factory_garden_leaf_policy(const char *name)
{
	static const unsigned int modes[] = {0U, 1U, 2U};
	static const char *const names[] = {"none", "all", "selective"};
	static const struct picosystem_garden_leaf_policy policies[] = {
		{.decide = decide, .context = &modes[0]},
		{.decide = decide, .context = &modes[1]},
		{.decide = decide, .context = &modes[2]},
	};
	for (size_t index = 0U; index < sizeof(modes) / sizeof(modes[0]); ++index) {
		if ((name != NULL) && (strcmp(name, names[index]) == 0)) {
			return &policies[index];
		}
	}
	return NULL;
}
