/* SPDX-License-Identifier: Apache-2.0 */
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#include "garden_agent.h"
#include "garden_purchase_veto.h"

struct purchase_target {
	const char *name;
	uint32_t tick;
	uint32_t lineage;
	uint16_t tip;
	uint16_t energy;
	uint16_t water;
	uint16_t nodes;
	uint8_t action;
	uint8_t added;
	uint32_t retry_tick;
	uint16_t retry_energy;
	uint16_t retry_water;
};

static const struct purchase_target targets[PICOSYSTEM_GARDEN_PURCHASE_COUNT] = {
	[PICOSYSTEM_GARDEN_PURCHASE_NONE] = {.name = "none"},
	[PICOSYSTEM_GARDEN_PURCHASE_EXTENSION] = {.name = "extension",
						  .tick = 66060U,
						  .lineage = 21U,
						  .tip = 323U,
						  .energy = 151U,
						  .water = 510U,
						  .nodes = 32U,
						  .action = PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND,
						  .added = 1U},
	[PICOSYSTEM_GARDEN_PURCHASE_FINISH] = {.name = "finish",
					       .tick = 69885U,
					       .lineage = 22U,
					       .tip = 271U,
					       .energy = 92U,
					       .water = 152U,
					       .nodes = 21U,
					       .action = PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP},
	[PICOSYSTEM_GARDEN_PURCHASE_FINISH_RETRY] =
		{.name = "finish-retry",
		 .tick = 69885U,
		 .lineage = 22U,
		 .tip = 271U,
		 .energy = 92U,
		 .water = 152U,
		 .nodes = 21U,
		 .action = PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP,
		 .retry_tick = 69900U,
		 .retry_energy = 90U,
		 .retry_water = 161U},
};

static bool valid(const struct picosystem_garden_purchase_veto *veto)
{
	return (veto != NULL) && (veto->selection >= PICOSYSTEM_GARDEN_PURCHASE_NONE) &&
	       (veto->selection < PICOSYSTEM_GARDEN_PURCHASE_COUNT) &&
	       (veto->hits <=
		(veto->selection == PICOSYSTEM_GARDEN_PURCHASE_FINISH_RETRY ? 2U : 1U));
}

int picosystem_garden_purchase_parse(const char *name,
				     enum picosystem_garden_purchase_selection *selection)
{
	if ((name == NULL) || (selection == NULL) ||
	    (*selection != PICOSYSTEM_GARDEN_PURCHASE_NONE)) {
		return -EINVAL;
	}
	for (int i = PICOSYSTEM_GARDEN_PURCHASE_EXTENSION; i < PICOSYSTEM_GARDEN_PURCHASE_COUNT;
	     ++i) {
		if (strcmp(name, targets[i].name) == 0) {
			*selection = (enum picosystem_garden_purchase_selection)i;
			return 0;
		}
	}
	return -EINVAL;
}

int picosystem_garden_purchase_check(struct picosystem_garden_purchase_veto *veto, uint32_t tick,
				     const struct picosystem_garden_dark_event *event,
				     uint8_t action)
{
	if (!valid(veto) || (event == NULL)) {
		return -EINVAL;
	}
	if (veto->selection == PICOSYSTEM_GARDEN_PURCHASE_NONE) {
		return veto->hits == 0U ? 0 : -EINVAL;
	}
	const struct purchase_target *const target = &targets[veto->selection];
	const bool retry = (target->retry_tick != 0U) && (tick == target->retry_tick);
	if ((!retry && (tick != target->tick)) || (event->lineage_id != target->lineage)) {
		return 0;
	}
	const uint8_t expected_hits = retry ? 1U : 0U;
	if (veto->hits != expected_hits) {
		return veto->hits > expected_hits ? -EALREADY : -EINVAL;
	}
	const uint16_t energy = retry ? target->retry_energy : target->energy;
	const uint16_t water = retry ? target->retry_water : target->water;
	if ((event->kind != PICOSYSTEM_GARDEN_EXPENSE_GROWTH) || event->denied || event->invalid ||
	    event->before.supported || event->after.supported || (action != target->action) ||
	    (event->node_index != target->tip) || (event->energy != energy) ||
	    (event->water != water) || (event->nodes_before != target->nodes) ||
	    (event->nodes_after != target->nodes + target->added) || (event->stress != 0U) ||
	    (event->energy_cost != 9U) || (event->water_cost != 5U)) {
		return -EINVAL;
	}
	++veto->hits;
	return -ECANCELED;
}

int picosystem_garden_purchase_validate(const struct picosystem_garden_purchase_veto *veto,
					uint32_t tick)
{
	if (!valid(veto)) {
		return -EINVAL;
	}
	const struct purchase_target *const target = &targets[veto->selection];
	const unsigned int expected =
		(unsigned int)((veto->selection != PICOSYSTEM_GARDEN_PURCHASE_NONE) &&
			       (tick >= target->tick)) +
		(unsigned int)((target->retry_tick != 0U) && (tick >= target->retry_tick));
	return veto->hits == expected ? 0 : -EINVAL;
}

int picosystem_garden_purchase_print(const struct picosystem_garden_purchase_veto *veto,
				     uint32_t tick)
{
	const int err = picosystem_garden_purchase_validate(veto, tick);
	if ((err != 0) || (veto->selection == PICOSYSTEM_GARDEN_PURCHASE_NONE)) {
		return err;
	}
	const struct purchase_target *const target = &targets[veto->selection];
	const char *const rule = target->retry_tick != 0U ? PICOSYSTEM_GARDEN_FINISH_RETRY_RULE
							  : PICOSYSTEM_GARDEN_PURCHASE_VETO_RULE;
	if (printf("\"purchase_veto\":{\"rule\":\"%s\",\"arm\":\"%s\",\"tick\":%" PRIu32
		   ",\"id\":%" PRIu32 ",\"hits\":%u",
		   rule, target->name, target->tick, target->lineage, veto->hits) < 0) {
		return -EIO;
	}
	if ((target->retry_tick != 0U) &&
	    (printf(",\"stop_tick\":%" PRIu32,
		    target->retry_tick + PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR) < 0)) {
		return -EIO;
	}
	return printf("},") < 0 ? -EIO : 0;
}
