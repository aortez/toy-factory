/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "garden_agent.h"

#include "garden_light.h"

#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stdint.h>

_Static_assert(sizeof(struct picosystem_garden_agent_observation) == 104U,
	       "Garden agent observation layout changed");
_Static_assert(sizeof(struct picosystem_garden_agent_proposal) == 12U,
	       "Garden agent proposal layout changed");
_Static_assert(sizeof(struct picosystem_garden_agent_memory) == 8U,
	       "Garden agent memory must remain densely packed");
_Static_assert(sizeof(struct picosystem_garden_agent_decision) == 20U,
	       "Garden agent decision layout changed");
_Static_assert(PICOSYSTEM_GARDEN_AGENT_MAX_CANDIDATES <= 8U,
	       "candidate validation uses one byte as a visited mask");

enum garden_adaptive_memory_index {
	GARDEN_ADAPTIVE_MEMORY_ENERGY_PRESSURE,
	GARDEN_ADAPTIVE_MEMORY_WATER_PRESSURE,
	GARDEN_ADAPTIVE_MEMORY_ROOT_BALANCE,
	GARDEN_ADAPTIVE_MEMORY_STRESS,
	GARDEN_ADAPTIVE_MEMORY_ENERGY_INCOME,
	GARDEN_ADAPTIVE_MEMORY_WATER_INCOME,
	GARDEN_ADAPTIVE_MEMORY_CROWDING,
	GARDEN_ADAPTIVE_MEMORY_CHOICE_STREAK,
	GARDEN_ADAPTIVE_MEMORY_COUNT,
};

_Static_assert(GARDEN_ADAPTIVE_MEMORY_COUNT == PICOSYSTEM_GARDEN_AGENT_MEMORY_WIDTH,
	       "adaptive policy must define every memory byte");

#define GARDEN_ADAPTIVE_PRESSURE_CENTER       64
#define GARDEN_ADAPTIVE_ALLOCATION_STEP       8
#define GARDEN_ADAPTIVE_ALLOCATION_LIMIT      64
#define GARDEN_ADAPTIVE_CHOICE_STREAK_LIMIT   8
#define GARDEN_ADAPTIVE_CROWDING_STEP         24
#define GARDEN_ADAPTIVE_INCOME_SAMPLE_SCALE   4
#define GARDEN_ADAPTIVE_INCOME_DEFICIT_TARGET 24
#define GARDEN_ADAPTIVE_SHORTAGE_BONUS        96
#define GARDEN_ADAPTIVE_MINIMUM_LEAVES        3U
#define GARDEN_ADAPTIVE_BOOTSTRAP_SHOOT_BONUS 256
#define GARDEN_ADAPTIVE_RESERVE_LIGHT_LIMIT   128U
#define GARDEN_ADAPTIVE_TERMINAL_PRIORITY     30000
#define GARDEN_ADAPTIVE_BLOCKED_PRIORITY      29000

static bool observation_is_valid(const struct picosystem_garden_agent_observation *observation)
{
	if ((observation == NULL) ||
	    (observation->version != PICOSYSTEM_GARDEN_AGENT_OBSERVATION_VERSION) ||
	    (observation->plant_index >= PICOSYSTEM_GARDEN_MAX_PLANTS) ||
	    (observation->tip_index >= PICOSYSTEM_GARDEN_MAX_NODES) ||
	    (observation->species_id >= PICOSYSTEM_GARDEN_SPECIES_COUNT) ||
	    (observation->tissue_kind >= PICOSYSTEM_GARDEN_NODE_KIND_COUNT) ||
	    (observation->maximum_depth == 0U) ||
	    (observation->sun_strength < PICOSYSTEM_GARDEN_LIGHT_MINIMUM) ||
	    (observation->sun_ray_step_x_q4 < -PICOSYSTEM_GARDEN_SUN_MAX_RAY_STEP_X_Q4) ||
	    (observation->sun_ray_step_x_q4 > PICOSYSTEM_GARDEN_SUN_MAX_RAY_STEP_X_Q4) ||
	    (observation->stress >= PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD) ||
	    (observation->maintenance_energy_cost == 0U) ||
	    (observation->maintenance_water_cost == 0U) ||
	    (observation->maintenance_phase >= PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR) ||
	    ((observation->plant_flags & (uint8_t)~PICOSYSTEM_GARDEN_PLANT_VALID_FLAGS) != 0U) ||
	    ((observation->plant_flags & PICOSYSTEM_GARDEN_PLANT_DEAD) != 0U) ||
	    (observation->genome.growth_rate < PICOSYSTEM_GARDEN_GENOME_TRAIT_MIN) ||
	    (observation->genome.growth_rate > PICOSYSTEM_GARDEN_GENOME_TRAIT_MAX) ||
	    (observation->genome.shoot_bias < PICOSYSTEM_GARDEN_GENOME_TRAIT_MIN) ||
	    (observation->genome.shoot_bias > PICOSYSTEM_GARDEN_GENOME_TRAIT_MAX) ||
	    (observation->genome.light_seeking < PICOSYSTEM_GARDEN_GENOME_TRAIT_MIN) ||
	    (observation->genome.light_seeking > PICOSYSTEM_GARDEN_GENOME_TRAIT_MAX) ||
	    (observation->genome.water_seeking < PICOSYSTEM_GARDEN_GENOME_TRAIT_MIN) ||
	    (observation->genome.water_seeking > PICOSYSTEM_GARDEN_GENOME_TRAIT_MAX) ||
	    (observation->genome.branching < PICOSYSTEM_GARDEN_GENOME_TRAIT_MIN) ||
	    (observation->genome.branching > PICOSYSTEM_GARDEN_GENOME_TRAIT_MAX) ||
	    (observation->genome.stature < PICOSYSTEM_GARDEN_GENOME_TRAIT_MIN) ||
	    (observation->genome.stature > PICOSYSTEM_GARDEN_GENOME_TRAIT_MAX) ||
	    (observation->genome.reserve_strategy < PICOSYSTEM_GARDEN_GENOME_TRAIT_MIN) ||
	    (observation->genome.reserve_strategy > PICOSYSTEM_GARDEN_GENOME_TRAIT_MAX) ||
	    (observation->genome.dispersal < PICOSYSTEM_GARDEN_GENOME_TRAIT_MIN) ||
	    (observation->genome.dispersal > PICOSYSTEM_GARDEN_GENOME_TRAIT_MAX)) {
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

static void initialize_decision(uint16_t tip_index,
				struct picosystem_garden_agent_decision *decision)
{
	*decision = (struct picosystem_garden_agent_decision){0};
	initialize_proposal(tip_index, &decision->proposal);
}

static int8_t clamp_i8(int32_t value)
{
	if (value < INT8_MIN) {
		return INT8_MIN;
	}
	return (value > INT8_MAX) ? INT8_MAX : (int8_t)value;
}

static int16_t clamp_i16(int32_t value)
{
	if (value < INT16_MIN) {
		return INT16_MIN;
	}
	return (value > INT16_MAX) ? INT16_MAX : (int16_t)value;
}

static int8_t smooth_memory(int8_t previous, int32_t sample)
{
	return clamp_i8((((int32_t)previous * 3) + sample) / 4);
}

static int8_t resource_pressure(uint16_t stored, uint8_t scale_shift)
{
	uint16_t level = (uint16_t)(stored >> scale_shift);
	if (level > (2U * GARDEN_ADAPTIVE_PRESSURE_CENTER)) {
		level = 2U * GARDEN_ADAPTIVE_PRESSURE_CENTER;
	}
	return (int8_t)(GARDEN_ADAPTIVE_PRESSURE_CENTER - (int16_t)level);
}

static uint8_t
available_candidate_count(const struct picosystem_garden_agent_observation *observation)
{
	uint8_t count = 0U;
	for (uint8_t index = 0U; index < observation->candidate_count; ++index) {
		if ((observation->candidates[index].flags &
		     PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE) != 0U) {
			++count;
		}
	}
	return count;
}

static void clear_candidate_order(struct picosystem_garden_agent_proposal *proposal)
{
	proposal->candidate_count = 0U;
	for (uint8_t index = 0U; index < PICOSYSTEM_GARDEN_AGENT_MAX_CANDIDATES; ++index) {
		proposal->candidate_order[index] = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE;
	}
}

static int8_t next_root_balance(int8_t current, bool chose_root)
{
	const int32_t next = (int32_t)current + (chose_root ? GARDEN_ADAPTIVE_ALLOCATION_STEP
							    : -GARDEN_ADAPTIVE_ALLOCATION_STEP);
	if (next < -GARDEN_ADAPTIVE_ALLOCATION_LIMIT) {
		return -GARDEN_ADAPTIVE_ALLOCATION_LIMIT;
	}
	return (next > GARDEN_ADAPTIVE_ALLOCATION_LIMIT) ? GARDEN_ADAPTIVE_ALLOCATION_LIMIT
							 : (int8_t)next;
}

static int8_t next_choice_streak(int8_t current, bool chose_root)
{
	if (chose_root) {
		return (current > 0) ? ((current < GARDEN_ADAPTIVE_CHOICE_STREAK_LIMIT)
						? (int8_t)(current + 1)
						: current)
				     : 1;
	}
	return (current < 0)
		       ? ((current > -GARDEN_ADAPTIVE_CHOICE_STREAK_LIMIT) ? (int8_t)(current - 1)
									   : current)
		       : -1;
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
	const int32_t light_term = (int32_t)candidate->light / 16;
	const int32_t clearance_term = (int32_t)candidate->clearance_squared / 32;
	score += (int32_t)observation->genome.light_seeking * (light_term - clearance_term);
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
	int32_t best_score = INT32_MIN;
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
		const int32_t score =
			((int32_t)candidate->moisture * 4) +
			((int32_t)observation->genome.water_seeking *
			 ((int32_t)candidate->moisture - candidate->clearance_squared));
		if (score >= best_score) {
			best_score = score;
			preferred = candidate_index;
		}
	}
	best_score /= 4;
	*priority = (best_score < INT16_MIN)
			    ? INT16_MIN
			    : ((best_score > INT16_MAX) ? INT16_MAX : (int16_t)best_score);
	return preferred;
}

static bool
maintenance_reserve_is_available(const struct picosystem_garden_agent_observation *observation)
{
	const uint16_t reserve_periods = (uint16_t)(PICOSYSTEM_GARDEN_NIGHT_RESERVE_PERIODS +
						    (observation->genome.reserve_strategy *
						     PICOSYSTEM_GARDEN_RESERVE_TRAIT_PERIOD_STEP));
	const uint16_t energy_reserve =
		(uint16_t)observation->maintenance_energy_cost * reserve_periods;
	const uint16_t water_reserve =
		(uint16_t)observation->maintenance_water_cost * reserve_periods;
	return (observation->stored_energy > energy_reserve) &&
	       (observation->stored_water > water_reserve);
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
	if ((observation->sun_strength == PICOSYSTEM_GARDEN_LIGHT_MINIMUM) &&
	    !maintenance_reserve_is_available(observation)) {
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
	for (uint8_t offset = 0U; (offset < proposal->candidate_count) &&
				  (offset < PICOSYSTEM_GARDEN_AGENT_MAX_CANDIDATES);
	     ++offset) {
		proposal->candidate_order[offset] =
			(uint8_t)((preferred + offset) % proposal->candidate_count);
	}
	return 0;
}

int picosystem_garden_agent_decide(const struct picosystem_garden_agent_policy *policy,
				   const struct picosystem_garden_agent_observation *observation,
				   const struct picosystem_garden_agent_memory *memory,
				   struct picosystem_garden_agent_decision *decision)
{
	if (decision == NULL) {
		return -EINVAL;
	}
	initialize_decision((observation == NULL) ? 0U : observation->tip_index, decision);
	if ((policy == NULL) || (policy->decide == NULL) || (observation == NULL) ||
	    (memory == NULL)) {
		return -EINVAL;
	}
	if (!observation_is_valid(observation)) {
		return -ERANGE;
	}

	const int err = policy->decide(observation, memory, decision, policy->context);
	if (err != 0) {
		initialize_decision(observation->tip_index, decision);
		return (err < 0) ? err : -EINVAL;
	}
	return 0;
}

int picosystem_garden_agent_baseline_decide(
	const struct picosystem_garden_agent_observation *observation,
	const struct picosystem_garden_agent_memory *memory,
	struct picosystem_garden_agent_decision *decision, const void *context)
{
	(void)context;
	if (decision == NULL) {
		return -EINVAL;
	}
	initialize_decision((observation == NULL) ? 0U : observation->tip_index, decision);
	if (memory == NULL) {
		return -EINVAL;
	}
	decision->next_memory = *memory;
	return picosystem_garden_agent_baseline_propose(observation, &decision->proposal);
}

static int32_t bounded_income_deficit(int8_t income)
{
	int32_t bounded_income = income;
	if (bounded_income < 0) {
		bounded_income = 0;
	} else if (bounded_income > GARDEN_ADAPTIVE_INCOME_DEFICIT_TARGET) {
		bounded_income = GARDEN_ADAPTIVE_INCOME_DEFICIT_TARGET;
	}
	return GARDEN_ADAPTIVE_INCOME_DEFICIT_TARGET - bounded_income;
}

static int16_t adaptive_priority(const struct picosystem_garden_agent_observation *observation,
				 const struct picosystem_garden_agent_memory *memory,
				 const struct picosystem_garden_agent_decision *decision)
{
	const bool chose_root = observation->tissue_kind == PICOSYSTEM_GARDEN_NODE_ROOT;
	const int32_t energy_pressure =
		decision->next_memory.hidden[GARDEN_ADAPTIVE_MEMORY_ENERGY_PRESSURE];
	const int32_t water_pressure =
		decision->next_memory.hidden[GARDEN_ADAPTIVE_MEMORY_WATER_PRESSURE];
	const int32_t root_balance = memory->hidden[GARDEN_ADAPTIVE_MEMORY_ROOT_BALANCE];
	const int32_t choice_streak = memory->hidden[GARDEN_ADAPTIVE_MEMORY_CHOICE_STREAK];
	const int32_t stress = decision->next_memory.hidden[GARDEN_ADAPTIVE_MEMORY_STRESS];
	const int32_t root_minus_shoot =
		(int32_t)observation->root_node_count - observation->shoot_node_count;
	const int32_t income_deficit = bounded_income_deficit(
		decision->next_memory.hidden[chose_root ? GARDEN_ADAPTIVE_MEMORY_WATER_INCOME
							: GARDEN_ADAPTIVE_MEMORY_ENERGY_INCOME]);
	const int32_t relevant_pressure = chose_root ? water_pressure : energy_pressure;
	const int32_t other_pressure = chose_root ? energy_pressure : water_pressure;
	const int32_t shortage_flag = chose_root ? PICOSYSTEM_GARDEN_PLANT_WATER_SHORTAGE
						 : PICOSYSTEM_GARDEN_PLANT_ENERGY_SHORTAGE;
	int32_t priority = chose_root ? (decision->proposal.priority / 4)
				      : ((int32_t)decision->proposal.priority * 2);

	priority += (3 * relevant_pressure) - (2 * other_pressure) + income_deficit;
	if (chose_root) {
		priority -= 3 * root_minus_shoot;
		priority -= (int32_t)observation->genome.shoot_bias * 16;
		priority -= 2 * root_balance;
		priority -= 8 * choice_streak;
	} else {
		priority += 3 * root_minus_shoot;
		priority += (int32_t)observation->genome.shoot_bias * 16;
		priority += 2 * root_balance;
		priority += 8 * choice_streak;
		if (observation->leaf_node_count < GARDEN_ADAPTIVE_MINIMUM_LEAVES) {
			priority += GARDEN_ADAPTIVE_BOOTSTRAP_SHOOT_BONUS;
		}
	}
	if ((observation->plant_flags & shortage_flag) != 0U) {
		priority += GARDEN_ADAPTIVE_SHORTAGE_BONUS + (2 * stress);
	}
	priority -= decision->next_memory.hidden[GARDEN_ADAPTIVE_MEMORY_CROWDING] / 2;
	return clamp_i16(priority);
}

int picosystem_garden_agent_adaptive_decide(
	const struct picosystem_garden_agent_observation *observation,
	const struct picosystem_garden_agent_memory *memory,
	struct picosystem_garden_agent_decision *decision, const void *context)
{
	(void)context;
	const int err =
		picosystem_garden_agent_baseline_decide(observation, memory, decision, NULL);
	if (err != 0) {
		return err;
	}

	const uint8_t available_count = available_candidate_count(observation);
	const bool chose_root = observation->tissue_kind == PICOSYSTEM_GARDEN_NODE_ROOT;
	decision->next_memory.hidden[GARDEN_ADAPTIVE_MEMORY_ENERGY_PRESSURE] =
		smooth_memory(memory->hidden[GARDEN_ADAPTIVE_MEMORY_ENERGY_PRESSURE],
			      resource_pressure(observation->stored_energy, 1U));
	decision->next_memory.hidden[GARDEN_ADAPTIVE_MEMORY_WATER_PRESSURE] =
		smooth_memory(memory->hidden[GARDEN_ADAPTIVE_MEMORY_WATER_PRESSURE],
			      resource_pressure(observation->stored_water, 2U));
	decision->next_memory.hidden[GARDEN_ADAPTIVE_MEMORY_STRESS] = smooth_memory(
		memory->hidden[GARDEN_ADAPTIVE_MEMORY_STRESS], (int32_t)observation->stress * 16);
	decision->next_memory.hidden[GARDEN_ADAPTIVE_MEMORY_ENERGY_INCOME] = smooth_memory(
		memory->hidden[GARDEN_ADAPTIVE_MEMORY_ENERGY_INCOME],
		(int32_t)observation->last_energy_income * GARDEN_ADAPTIVE_INCOME_SAMPLE_SCALE);
	decision->next_memory.hidden[GARDEN_ADAPTIVE_MEMORY_WATER_INCOME] = smooth_memory(
		memory->hidden[GARDEN_ADAPTIVE_MEMORY_WATER_INCOME],
		(int32_t)observation->last_water_income * GARDEN_ADAPTIVE_INCOME_SAMPLE_SCALE);
	decision->next_memory.hidden[GARDEN_ADAPTIVE_MEMORY_CROWDING] =
		smooth_memory(memory->hidden[GARDEN_ADAPTIVE_MEMORY_CROWDING],
			      (int32_t)(observation->candidate_count - available_count) *
				      GARDEN_ADAPTIVE_CROWDING_STEP);

	if ((decision->proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND) &&
	    (available_count == 0U)) {
		decision->proposal.action = PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP;
		clear_candidate_order(&decision->proposal);
		decision->proposal.priority = GARDEN_ADAPTIVE_BLOCKED_PRIORITY;
		return 0;
	}
	if (decision->proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP) {
		decision->proposal.priority = GARDEN_ADAPTIVE_TERMINAL_PRIORITY;
		return 0;
	}

	decision->proposal.priority = adaptive_priority(observation, memory, decision);
	if ((decision->proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND) &&
	    (observation->sun_strength <= GARDEN_ADAPTIVE_RESERVE_LIGHT_LIMIT) &&
	    !maintenance_reserve_is_available(observation)) {
		decision->proposal.action = PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT;
		clear_candidate_order(&decision->proposal);
		return 0;
	}
	if (decision->proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND) {
		decision->next_memory.hidden[GARDEN_ADAPTIVE_MEMORY_ROOT_BALANCE] =
			next_root_balance(memory->hidden[GARDEN_ADAPTIVE_MEMORY_ROOT_BALANCE],
					  chose_root);
		decision->next_memory.hidden[GARDEN_ADAPTIVE_MEMORY_CHOICE_STREAK] =
			next_choice_streak(memory->hidden[GARDEN_ADAPTIVE_MEMORY_CHOICE_STREAK],
					   chose_root);
	}
	return 0;
}

const struct picosystem_garden_agent_policy *picosystem_garden_agent_baseline_policy(void)
{
	static const struct picosystem_garden_agent_policy policy = {
		.decide = picosystem_garden_agent_baseline_decide,
		.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_PHASED,
	};
	return &policy;
}

const struct picosystem_garden_agent_policy *picosystem_garden_agent_adaptive_policy(void)
{
	static const struct picosystem_garden_agent_policy policy = {
		.decide = picosystem_garden_agent_adaptive_decide,
		.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS,
	};
	return &policy;
}
