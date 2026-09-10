/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "garden_agent.h"

#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stdint.h>

_Static_assert(sizeof(struct picosystem_garden_agent_observation) == 88U,
	       "Garden agent observation layout changed");
_Static_assert(sizeof(struct picosystem_garden_agent_proposal) == 12U,
	       "Garden agent proposal layout changed");
_Static_assert(PICOSYSTEM_GARDEN_AGENT_MAX_CANDIDATES <= 8U,
	       "candidate validation uses one byte as a visited mask");

static bool observation_is_valid(const struct picosystem_garden_agent_observation *observation)
{
	if ((observation == NULL) ||
	    (observation->version != PICOSYSTEM_GARDEN_AGENT_OBSERVATION_VERSION) ||
	    (observation->plant_index >= PICOSYSTEM_GARDEN_MAX_PLANTS) ||
	    (observation->tip_index >= PICOSYSTEM_GARDEN_MAX_NODES) ||
	    (observation->species_id >= PICOSYSTEM_GARDEN_SPECIES_COUNT) ||
	    (observation->tissue_kind >= PICOSYSTEM_GARDEN_NODE_KIND_COUNT) ||
	    (observation->maximum_depth == 0U)) {
		return false;
	}

	const uint8_t expected_candidate_count =
		(observation->tissue_kind == PICOSYSTEM_GARDEN_NODE_STEM) ? 5U : 3U;
	if (observation->candidate_count != expected_candidate_count) {
		return false;
	}
	for (uint8_t index = 0U; index < observation->candidate_count; ++index) {
		const uint8_t flags = observation->candidates[index].flags;
		const uint8_t nearby_flags = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_OWN_NEAR |
					     PICOSYSTEM_GARDEN_AGENT_CANDIDATE_FOREIGN_NEAR;
		if (((flags & (uint8_t)~PICOSYSTEM_GARDEN_AGENT_CANDIDATE_VALID_MASK) != 0U) ||
		    (((flags & PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE) != 0U) &&
		     (((flags & PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS) == 0U) ||
		      ((flags & nearby_flags) != 0U))) ||
		    (((flags & nearby_flags) != 0U) &&
		     ((flags & PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS) == 0U))) {
			return false;
		}
	}
	return true;
}

static void initialize_proposal(uint16_t tip_index,
				struct picosystem_garden_agent_proposal *proposal)
{
	*proposal = (struct picosystem_garden_agent_proposal){
		.tip_index = tip_index,
		.action = PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT,
	};
	for (uint8_t index = 0U; index < PICOSYSTEM_GARDEN_AGENT_MAX_CANDIDATES; ++index) {
		proposal->candidate_order[index] = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE;
	}
}

static int8_t shoot_candidate_score(const struct picosystem_garden_agent_observation *observation,
				    uint8_t candidate_index)
{
	const struct picosystem_garden_agent_candidate *const candidate =
		&observation->candidates[candidate_index];
	if ((candidate->flags & PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS) == 0U) {
		return INT8_MIN;
	}

	const int8_t centered_step = (int8_t)candidate_index - 2;
	const int32_t absolute_step = (centered_step < 0) ? -(int32_t)centered_step : centered_step;
	int32_t score = candidate->light / 8U;
	score += (int32_t)centered_step * observation->lean;
	score += absolute_step * observation->horizontal_tendency;
	if ((observation->tip_flags & PICOSYSTEM_GARDEN_NODE_PRUNED) != 0U) {
		score += absolute_step * 8;
	}
	if (score < INT8_MIN) {
		return INT8_MIN;
	}
	return (score > INT8_MAX) ? INT8_MAX : (int8_t)score;
}

static uint8_t
preferred_shoot_candidate(const struct picosystem_garden_agent_observation *observation,
			  int16_t *priority)
{
	uint8_t preferred = 2U;
	int8_t best_score = INT8_MIN;
	const uint8_t random_offset =
		(uint8_t)(observation->decision_nonce % observation->candidate_count);
	for (uint8_t offset = 0U; offset < observation->candidate_count; ++offset) {
		const uint8_t candidate_index =
			(uint8_t)((random_offset + offset) % observation->candidate_count);
		const int8_t score = shoot_candidate_score(observation, candidate_index);
		if (score > best_score) {
			best_score = score;
			preferred = candidate_index;
		}
	}

	if ((observation->tip_flags & PICOSYSTEM_GARDEN_NODE_BRANCH_PENDING) != 0U) {
		preferred = (observation->tip_x <= observation->base_x) ? 4U : 0U;
		best_score = shoot_candidate_score(observation, preferred);
	}
	*priority = best_score;
	return preferred;
}

static uint8_t
preferred_root_candidate(const struct picosystem_garden_agent_observation *observation,
			 int16_t *priority)
{
	uint8_t preferred = 1U;
	uint8_t best_moisture = 0U;
	const uint8_t random_offset =
		(uint8_t)(observation->decision_nonce % observation->candidate_count);
	for (uint8_t offset = 0U; offset < observation->candidate_count; ++offset) {
		const uint8_t candidate_index =
			(uint8_t)((random_offset + offset) % observation->candidate_count);
		const struct picosystem_garden_agent_candidate *const candidate =
			&observation->candidates[candidate_index];
		if ((candidate->flags & PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS) == 0U) {
			continue;
		}
		if (candidate->moisture >= best_moisture) {
			best_moisture = candidate->moisture;
			preferred = candidate_index;
		}
	}
	*priority = best_moisture;
	return preferred;
}

int picosystem_garden_agent_baseline_propose(
	const struct picosystem_garden_agent_observation *observation,
	struct picosystem_garden_agent_proposal *proposal)
{
	if (proposal == NULL) {
		return -EINVAL;
	}
	initialize_proposal((observation != NULL) ? observation->tip_index : 0U, proposal);
	if (observation == NULL) {
		return -EINVAL;
	}
	if (!observation_is_valid(observation)) {
		return -ERANGE;
	}
	if (observation->depth >= observation->maximum_depth) {
		proposal->action = PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP;
		return 0;
	}

	uint8_t preferred;
	if (observation->tissue_kind == PICOSYSTEM_GARDEN_NODE_STEM) {
		preferred = preferred_shoot_candidate(observation, &proposal->priority);
	} else {
		preferred = preferred_root_candidate(observation, &proposal->priority);
	}
	proposal->action = PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND;
	proposal->candidate_count = observation->candidate_count;
	for (uint8_t offset = 0U; offset < proposal->candidate_count; ++offset) {
		proposal->candidate_order[offset] =
			(uint8_t)((preferred + offset) % proposal->candidate_count);
	}
	return 0;
}
