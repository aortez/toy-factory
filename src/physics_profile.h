/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_PHYSICS_PROFILE_H_
#define PICOSYSTEM_PHYSICS_PROFILE_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "physics_world.h"

#define PICOSYSTEM_PHYSICS_PROFILE_SCHEMA_VERSION             6U
#define PICOSYSTEM_PHYSICS_PROFILE_DEFAULT_TICKS              2000U
#define PICOSYSTEM_PHYSICS_PROFILE_MAX_TICKS                  10000U
#define PICOSYSTEM_PHYSICS_PROFILE_WARMUP_TICKS               120U
#define PICOSYSTEM_PHYSICS_PROFILE_HISTOGRAM_FINE_BIN_US      32U
#define PICOSYSTEM_PHYSICS_PROFILE_HISTOGRAM_FINE_BIN_COUNT   64U
#define PICOSYSTEM_PHYSICS_PROFILE_HISTOGRAM_COARSE_BIN_US    128U
#define PICOSYSTEM_PHYSICS_PROFILE_HISTOGRAM_COARSE_BIN_COUNT 64U
#define PICOSYSTEM_PHYSICS_PROFILE_HISTOGRAM_BIN_COUNT                                             \
	(PICOSYSTEM_PHYSICS_PROFILE_HISTOGRAM_FINE_BIN_COUNT +                                     \
	 PICOSYSTEM_PHYSICS_PROFILE_HISTOGRAM_COARSE_BIN_COUNT)
#define PICOSYSTEM_PHYSICS_PROFILE_MODE_COUNT 2U

enum picosystem_physics_profile_fixture {
	PICOSYSTEM_PHYSICS_PROFILE_FIXTURE_CANONICAL,
	PICOSYSTEM_PHYSICS_PROFILE_FIXTURE_REVOLUTE_CHAIN,
	PICOSYSTEM_PHYSICS_PROFILE_FIXTURE_COUNT,
};

enum picosystem_physics_profile_work_metric {
	PICOSYSTEM_PHYSICS_PROFILE_WORK_POSSIBLE_PAIRS,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_CANDIDATE_PAIRS,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_GRID_CELL_INSERTIONS,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_OCCUPIED_GRID_CELLS,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_MAXIMUM_GRID_CELL_OCCUPANCY,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_BODY_BODY_TESTS,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_BODY_SEGMENT_TESTS,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_JOINT_COLLISION_FILTERS,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_MANIFOLDS,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_CONTACT_POINTS,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_POSITION_CORRECTION_VISITS,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_SOLVER_ITERATIONS,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_SOLVER_CONTACT_VISITS,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_SOLVER_CACHED_CONTACTS,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_SOLVER_CHANGED_CONTACTS,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_DISTANCE_JOINTS,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_REVOLUTE_JOINTS,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_REVOLUTE_MOTORS,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_REVOLUTE_LIMITS,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_PRISMATIC_JOINTS,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_PRISMATIC_MOTORS,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_PRISMATIC_LIMITS,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_JOINT_POSITION_CORRECTION_VISITS,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_JOINT_LIMIT_POSITION_CORRECTION_VISITS,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_JOINT_LIMIT_POSITION_CORRECTION_CHANGES,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_JOINT_SOLVER_VISITS,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_JOINT_SOLVER_CHANGES,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_JOINT_MOTOR_SOLVER_VISITS,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_JOINT_MOTOR_SOLVER_CHANGES,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_JOINT_LIMIT_SOLVER_VISITS,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_JOINT_LIMIT_SOLVER_CHANGES,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_BROAD_PHASE_FALLBACKS,
	PICOSYSTEM_PHYSICS_PROFILE_WORK_METRIC_COUNT,
};

struct picosystem_physics_profile_stage_summary {
	uint32_t sample_count;
	uint32_t mean_cycles;
	uint32_t minimum_cycles;
	uint32_t percentile_50_cycles;
	uint32_t percentile_95_cycles;
	uint32_t percentile_99_cycles;
	uint32_t maximum_cycles;
	uint32_t budget_violation_count;
};

struct picosystem_physics_profile_work_summary {
	uint64_t total;
	uint32_t maximum;
};

struct picosystem_physics_profile_mode_result {
	struct picosystem_physics_profile_stage_summary
		stages[PICOSYSTEM_PHYSICS_PROFILE_STAGE_COUNT];
	struct picosystem_physics_profile_work_summary
		work[PICOSYSTEM_PHYSICS_PROFILE_WORK_METRIC_COUNT];
	uint32_t final_hash;
	uint32_t minimum_clock_reads_per_step;
	uint32_t maximum_clock_reads_per_step;
	uint32_t maximum_revolute_anchor_error_q16;
	uint32_t maximum_revolute_limit_violation_q16;
	uint32_t maximum_prismatic_lateral_error_q16;
	uint32_t maximum_prismatic_angular_error_q16;
	uint32_t maximum_prismatic_limit_violation_q16;
};

struct picosystem_physics_profile_result {
	struct picosystem_physics_profile_mode_result modes[PICOSYSTEM_PHYSICS_PROFILE_MODE_COUNT];
	uint32_t schema_version;
	uint32_t measured_tick_count;
	uint32_t warmup_tick_count;
	uint32_t clock_frequency_hz;
	uint32_t histogram_fine_bin_cycles;
	uint32_t histogram_coarse_bin_cycles;
	uint32_t back_to_back_clock_delta_cycles;
	uint16_t chain_link_count;
	uint8_t fixture;
	bool hashes_match;
	bool states_match;
};

/* Run an isolated canonical replay. The caller owns result; internal scratch is serialized. */
int picosystem_physics_profile_compare(uint32_t measured_tick_count,
				       struct picosystem_physics_profile_result *result);
int picosystem_physics_profile_compare_chain(uint16_t link_count, uint32_t measured_tick_count,
					     struct picosystem_physics_profile_result *result);

const char *picosystem_physics_profile_fixture_name(size_t fixture_index);
const char *picosystem_physics_profile_mode_name(size_t mode_index);
const char *picosystem_physics_profile_stage_name(size_t stage_index);
const char *picosystem_physics_profile_work_name(size_t metric_index);

#endif /* PICOSYSTEM_PHYSICS_PROFILE_H_ */
