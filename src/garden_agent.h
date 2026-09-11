/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_GARDEN_AGENT_H_
#define PICOSYSTEM_GARDEN_AGENT_H_

#include <stdint.h>

#include "garden_world.h"

#define PICOSYSTEM_GARDEN_AGENT_OBSERVATION_VERSION 4U
#define PICOSYSTEM_GARDEN_AGENT_MAX_CANDIDATES      5U
#define PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE      UINT8_MAX

enum picosystem_garden_agent_candidate_flag {
	PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS = 1U << 0,
	PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE = 1U << 1,
	PICOSYSTEM_GARDEN_AGENT_CANDIDATE_OWN_NEAR = 1U << 2,
	PICOSYSTEM_GARDEN_AGENT_CANDIDATE_FOREIGN_NEAR = 1U << 3,
};

#define PICOSYSTEM_GARDEN_AGENT_CANDIDATE_VALID_MASK                                               \
	(PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS |                                             \
	 PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE |                                             \
	 PICOSYSTEM_GARDEN_AGENT_CANDIDATE_OWN_NEAR |                                              \
	 PICOSYSTEM_GARDEN_AGENT_CANDIDATE_FOREIGN_NEAR)

enum picosystem_garden_agent_action {
	PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT,
	PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND,
	PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP,
	PICOSYSTEM_GARDEN_AGENT_ACTION_COUNT,
};

/* One canonical growth direction and the resources available at its endpoint. */
struct picosystem_garden_agent_candidate {
	int8_t delta_x;
	int8_t delta_y;
	uint8_t x;
	uint8_t y;
	uint8_t light;
	uint8_t moisture;
	uint8_t clearance_squared;
	uint8_t flags;
};

/* Fixed-capacity, caller-owned input suitable for scripted or learned policies. */
struct picosystem_garden_agent_observation {
	uint32_t decision_nonce;
	uint16_t tip_index;
	uint16_t stored_energy;
	uint16_t stored_water;
	uint16_t age_ecology_ticks;
	uint16_t plant_node_count;
	uint16_t shoot_node_count;
	uint16_t root_node_count;
	uint16_t leaf_node_count;
	uint16_t active_tip_count;
	int16_t parent_delta_x;
	int16_t parent_delta_y;
	uint8_t version;
	uint8_t plant_index;
	uint8_t species_id;
	uint8_t tissue_kind;
	uint8_t depth;
	uint8_t tip_x;
	uint8_t tip_y;
	uint8_t tip_light;
	uint8_t tip_moisture;
	uint8_t base_x;
	uint8_t maximum_depth;
	uint8_t flower_depth;
	uint8_t growth_phase;
	uint8_t growth_cooldown;
	uint8_t tip_flags;
	int8_t lean;
	int8_t vigor;
	int8_t horizontal_tendency;
	uint8_t candidate_count;
	uint8_t sun_phase;
	uint8_t sun_strength;
	int8_t sun_ray_step_x_q4;
	uint8_t stress;
	uint8_t maintenance_energy_cost;
	uint8_t maintenance_water_cost;
	uint8_t maintenance_phase;
	uint8_t last_energy_income;
	uint8_t last_water_income;
	uint8_t plant_flags;
	struct picosystem_garden_genome genome;
	struct picosystem_garden_agent_candidate candidates[PICOSYSTEM_GARDEN_AGENT_MAX_CANDIDATES];
};

/* A policy ranks canonical candidate indexes; the world remains the mutation authority. */
struct picosystem_garden_agent_proposal {
	uint16_t tip_index;
	int16_t priority;
	uint8_t action;
	uint8_t candidate_count;
	uint8_t candidate_order[PICOSYSTEM_GARDEN_AGENT_MAX_CANDIDATES];
};

/* Observe one active tip without mutating the world. */
int picosystem_garden_agent_observe_tip(const struct picosystem_garden_world *world,
					uint8_t plant_index, uint16_t tip_index,
					uint32_t decision_nonce,
					struct picosystem_garden_agent_observation *observation);

/* Reproduce the original deterministic hand-authored growth choice. */
int picosystem_garden_agent_baseline_propose(
	const struct picosystem_garden_agent_observation *observation,
	struct picosystem_garden_agent_proposal *proposal);

#endif /* PICOSYSTEM_GARDEN_AGENT_H_ */
