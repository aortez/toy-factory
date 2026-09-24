/* SPDX-License-Identifier: Apache-2.0 */
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#include "garden_agent.h"
#include "garden_dawn_finish.h"

int picosystem_garden_dawn_finish_parse(const char *name,
					struct picosystem_garden_dawn_finish *state)
{
	if ((name == NULL) || (state == NULL) || state->enabled ||
	    (picosystem_garden_dawn_finish_validate(state, 0U) != 0) ||
	    ((strcmp(name, "defer") != 0) && (strcmp(name, "reserve") != 0))) {
		return -EINVAL;
	}
	state->enabled = true;
	state->reserve_handoff = strcmp(name, "reserve") == 0;
	return 0;
}

static uint32_t last_tick(const struct picosystem_garden_dawn_finish *state)
{
	return state->reserve_handoff
		       ? PICOSYSTEM_GARDEN_DAWN_FINISH_NOON - PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR
		       : PICOSYSTEM_GARDEN_DAWN_FINISH_LAST;
}

int picosystem_garden_dawn_finish_validate(const struct picosystem_garden_dawn_finish *state,
					   uint32_t tick)
{
	if (state == NULL) {
		return -EINVAL;
	}
	if ((!state->enabled && state->reserve_handoff) ||
	    ((!state->reserve_handoff || (state->handoff_tick == 0U)) &&
	     ((state->handoff_tick != 0U) || (state->handoff_energy != 0U) ||
	      (state->handoff_node != 0U)))) {
		return -EINVAL;
	}
	if (!state->enabled || (tick < PICOSYSTEM_GARDEN_DAWN_FINISH_FIRST)) {
		return ((state->hits == 0U) && (state->last_tick == 0U) &&
			(state->last_node == 0U) && (state->handoff_tick == 0U))
			       ? 0
			       : -EINVAL;
	}
	const uint32_t end = tick < last_tick(state) ? tick : last_tick(state);
	if ((state->hits == 0U) || (state->last_tick < PICOSYSTEM_GARDEN_DAWN_FINISH_FIRST) ||
	    (state->last_tick > end) ||
	    ((state->last_tick % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR) != 0U) ||
	    (state->last_node >= PICOSYSTEM_GARDEN_MAX_NODES) ||
	    (state->hits > (state->last_tick - PICOSYSTEM_GARDEN_DAWN_FINISH_FIRST) /
					   PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR +
				   1U)) {
		return -EINVAL;
	}
	if ((state->handoff_tick != 0U) &&
	    ((state->handoff_tick <= PICOSYSTEM_GARDEN_DAWN_FINISH_LAST) ||
	     (state->handoff_tick > end) || (state->handoff_tick <= state->last_tick) ||
	     ((state->handoff_tick % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR) != 0U) ||
	     (state->handoff_energy < 16U) || (state->handoff_energy > 256U) ||
	     (state->handoff_node >= PICOSYSTEM_GARDEN_MAX_NODES))) {
		return -EINVAL;
	}
	return 0;
}

int picosystem_garden_dawn_finish_check(
	struct picosystem_garden_dawn_finish *state, uint32_t tick,
	const struct picosystem_garden_dark_event *event,
	const struct picosystem_garden_agent_observation *observation, uint8_t action)
{
	if ((state == NULL) || (event == NULL) || (observation == NULL) || (tick == 0U)) {
		return -EINVAL;
	}
	const uint32_t latest =
		state->handoff_tick > state->last_tick ? state->handoff_tick : state->last_tick;
	if (state->enabled && (state->hits != 0U) && (latest == tick) &&
	    (event->lineage_id == 12U)) {
		return -EALREADY;
	}
	const int err =
		picosystem_garden_dawn_finish_validate(state, latest == tick ? tick : tick - 1U);
	if (err != 0) {
		return err;
	}
	if (!state->enabled || (tick < PICOSYSTEM_GARDEN_DAWN_FINISH_FIRST) ||
	    (tick > last_tick(state)) || (event->lineage_id != 12U) ||
	    (state->handoff_tick != 0U)) {
		return 0;
	}
	if ((tick % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR) != 0U ||
	    (event->kind != PICOSYSTEM_GARDEN_EXPENSE_GROWTH) || event->denied || event->invalid ||
	    (action != PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP) || (event->nodes_before != 61U) ||
	    (event->nodes_after != 61U) || (event->energy_cost != 8U) ||
	    (event->water_cost != 5U) || (event->energy < 8U) || (event->energy > 256U) ||
	    (event->water < 5U) || (event->water > 512U) ||
	    (event->stress >= PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD) ||
	    (observation->tip_index != event->node_index) ||
	    (event->node_index >= PICOSYSTEM_GARDEN_MAX_NODES) ||
	    (observation->tissue_kind != PICOSYSTEM_GARDEN_NODE_ROOT) ||
	    (observation->tip_x != 47U) || (observation->tip_y != 193U) ||
	    (observation->depth != 9U) || (observation->maximum_depth != 9U)) {
		return -EINVAL;
	}
	if ((state->hits == 0U) &&
	    ((tick != PICOSYSTEM_GARDEN_DAWN_FINISH_FIRST) || (event->node_index != 378U) ||
	     (event->energy != 251U) || (event->water != 512U) || (event->stress != 0U) ||
	     !event->before.supported || !event->after.supported ||
	     (event->before.death_step != 0U) || (event->after.death_step != 0U))) {
		return -EINVAL;
	}
	if (state->reserve_handoff && (tick > PICOSYSTEM_GARDEN_DAWN_FINISH_LAST)) {
		const uint16_t upkeep = (uint16_t)((event->nodes_before + 7U) / 8U);
		if ((upkeep != 8U) || (observation->maintenance_energy_cost != upkeep)) {
			return -EINVAL;
		}
		if (event->energy >= event->energy_cost + upkeep) {
			state->handoff_tick = tick;
			state->handoff_energy = event->energy;
			state->handoff_node = event->node_index;
			return 0;
		}
	}
	++state->hits;
	state->last_tick = tick;
	state->last_node = event->node_index;
	return -ECANCELED;
}

int picosystem_garden_dawn_finish_print(const struct picosystem_garden_dawn_finish *state,
					uint32_t tick)
{
	const int err = picosystem_garden_dawn_finish_validate(state, tick);
	if ((err != 0) || !state->enabled) {
		return err;
	}
	const char *const rule = state->reserve_handoff ? PICOSYSTEM_GARDEN_DAWN_RESERVE_RULE
							: PICOSYSTEM_GARDEN_DAWN_FINISH_RULE;
	if (printf("\"dawn_finish\":{\"rule\":\"%s\",\"id\":12,\"first\":%u,\"last\":%" PRIu32
		   ",\"hits\":%u,\"last_tick\":%" PRIu32 ",\"last_node\":%u",
		   rule, PICOSYSTEM_GARDEN_DAWN_FINISH_FIRST, last_tick(state), state->hits,
		   state->last_tick, state->last_node) < 0) {
		return -EIO;
	}
	if (state->reserve_handoff &&
	    (printf(",\"cutoff_tick\":%u,\"reserve\":8,\"handoff_tick\":%" PRIu32
		    ",\"handoff_energy\":%u,\"handoff_node\":%u",
		    PICOSYSTEM_GARDEN_DAWN_FINISH_NOON, state->handoff_tick, state->handoff_energy,
		    state->handoff_node) < 0)) {
		return -EIO;
	}
	return printf("},") < 0 ? -EIO : 0;
}
