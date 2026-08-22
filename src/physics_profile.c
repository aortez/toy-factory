/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "physics_profile.h"

#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <zephyr/kernel.h>

#include "game_world.h"
#include "physics_chain_fixture.h"

#define PROFILE_YIELD_INTERVAL_TICKS 32U
#define PROFILE_CLOCK_SAMPLE_COUNT   256U

struct profile_stage_accumulator {
	uint64_t total_cycles;
	uint32_t histogram[PICOSYSTEM_PHYSICS_PROFILE_HISTOGRAM_BIN_COUNT];
	uint32_t sample_count;
	uint32_t minimum_cycles;
	uint32_t maximum_cycles;
	uint32_t budget_violation_count;
};

struct authoritative_snapshot {
	struct picosystem_physics_body bodies[PICOSYSTEM_PHYSICS_MAX_BODIES];
	struct picosystem_physics_static_segment
		static_segments[PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS];
	struct picosystem_physics_distance_joint
		distance_joints[PICOSYSTEM_PHYSICS_MAX_DISTANCE_JOINTS];
	struct picosystem_physics_revolute_joint
		revolute_joints[PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS];
	struct picosystem_physics_prismatic_joint
		prismatic_joints[PICOSYSTEM_PHYSICS_MAX_PRISMATIC_JOINTS];
	struct picosystem_physics_box_sensor box_sensors[PICOSYSTEM_PHYSICS_MAX_BOX_SENSORS];
	struct picosystem_physics_rope ropes[PICOSYSTEM_PHYSICS_MAX_ROPES];
	uint16_t active_body_contact_masks[PICOSYSTEM_PHYSICS_MAX_BODIES];
	uint8_t active_segment_contact_masks[PICOSYSTEM_PHYSICS_MAX_BODIES];
	uint8_t active_sensor_contact_masks[PICOSYSTEM_PHYSICS_MAX_BODIES];
	uint16_t sleeping_body_mask;
	uint16_t sleep_quiet_tick_counts[PICOSYSTEM_PHYSICS_MAX_BODIES];
	struct picosystem_physics_vector last_global_acceleration_per_tick;
	picosystem_physics_fixed_t max_speed_per_tick;
	uint32_t logic_tick_count;
	uint32_t sensor_entry_count;
	uint16_t body_count;
	uint16_t static_segment_count;
	uint16_t distance_joint_count;
	uint16_t revolute_joint_count;
	uint16_t prismatic_joint_count;
	uint16_t box_sensor_count;
	uint16_t rope_count;
};

struct profile_workspace {
	struct picosystem_game_world world;
	struct authoritative_snapshot grid_final_state;
	struct profile_stage_accumulator stages[PICOSYSTEM_PHYSICS_PROFILE_STAGE_COUNT];
};

static struct profile_workspace workspace;
K_MUTEX_DEFINE(profile_mutex);

_Static_assert(PICOSYSTEM_PHYSICS_PROFILE_WARMUP_TICKS == PICOSYSTEM_GAME_TICK_RATE_HZ,
	       "physics profile warm-up must remain one simulation second");

static const char *const fixture_names[] = {
	"canonical",
	"revolute_chain",
	"canonical_neutral",
};

static const char *const mode_names[] = {
	"grid",
	"reference",
};

static const char *const stage_names[] = {
	"force_integrate",
	"box_geometry",
	"broad_phase",
	"narrow_body_body",
	"narrow_body_segment",
	"narrow_body_sensor",
	"position_correction",
	"velocity_solver",
	"rope",
	"final_clamp",
	"other",
	"total",
};

static const char *const work_names[] = {
	"possible_pairs",
	"candidate_pairs",
	"grid_cell_insertions",
	"occupied_grid_cells",
	"maximum_grid_cell_occupancy",
	"body_body_tests",
	"body_segment_tests",
	"body_sensor_tests",
	"joint_collision_filters",
	"manifolds",
	"contact_points",
	"active_contact_pairs",
	"sensor_overlaps",
	"contact_begin_events",
	"contact_stay_events",
	"contact_end_events",
	"position_correction_visits",
	"solver_iterations",
	"solver_contact_visits",
	"solver_cached_contacts",
	"solver_changed_contacts",
	"distance_joints",
	"revolute_joints",
	"revolute_motors",
	"revolute_limits",
	"prismatic_joints",
	"prismatic_motors",
	"prismatic_limits",
	"joint_position_correction_visits",
	"joint_limit_position_correction_visits",
	"joint_limit_position_correction_changes",
	"joint_solver_visits",
	"joint_solver_changes",
	"joint_motor_solver_visits",
	"joint_motor_solver_changes",
	"joint_limit_solver_visits",
	"joint_limit_solver_changes",
	"broad_phase_fallbacks",
	"awake_bodies",
	"sleeping_bodies",
	"body_sleep_transitions",
	"body_wake_transitions",
	"sleeping_contacts",
	"sleeping_joints",
	"spring_joints",
	"spring_solver_visits",
	"spring_solver_changes",
	"conveyor_contacts",
	"conveyor_solver_visits",
	"conveyor_solver_changes",
	"ropes",
	"rope_particles",
	"rope_solver_iterations",
	"rope_constraint_visits",
	"rope_constraint_changes",
	"rope_body_correction_visits",
	"rope_body_correction_changes",
	"rope_body_velocity_visits",
	"rope_body_velocity_changes",
	"rope_collision_possible_pairs",
	"rope_collision_candidate_pairs",
	"rope_collision_contacts",
	"rope_collision_position_changes",
	"rope_collision_velocity_changes",
};

_Static_assert(sizeof(fixture_names) / sizeof(fixture_names[0]) ==
		       PICOSYSTEM_PHYSICS_PROFILE_FIXTURE_COUNT,
	       "profile fixture names must cover every fixture");
_Static_assert(PICOSYSTEM_PHYSICS_PROFILE_FIXTURE_COUNT <= UINT8_MAX,
	       "profile fixture identifiers must fit in one byte");
_Static_assert(sizeof(mode_names) / sizeof(mode_names[0]) == PICOSYSTEM_PHYSICS_PROFILE_MODE_COUNT,
	       "profile mode names must cover every mode");
_Static_assert(sizeof(stage_names) / sizeof(stage_names[0]) ==
		       PICOSYSTEM_PHYSICS_PROFILE_STAGE_COUNT,
	       "profile stage names must cover every stage");
_Static_assert(sizeof(work_names) / sizeof(work_names[0]) ==
		       PICOSYSTEM_PHYSICS_PROFILE_WORK_METRIC_COUNT,
	       "profile work names must cover every metric");

const char *picosystem_physics_profile_mode_name(size_t mode_index)
{
	return (mode_index < PICOSYSTEM_PHYSICS_PROFILE_MODE_COUNT) ? mode_names[mode_index] : NULL;
}

const char *picosystem_physics_profile_fixture_name(size_t fixture_index)
{
	return (fixture_index < PICOSYSTEM_PHYSICS_PROFILE_FIXTURE_COUNT)
		       ? fixture_names[fixture_index]
		       : NULL;
}

const char *picosystem_physics_profile_stage_name(size_t stage_index)
{
	return (stage_index < PICOSYSTEM_PHYSICS_PROFILE_STAGE_COUNT) ? stage_names[stage_index]
								      : NULL;
}

const char *picosystem_physics_profile_work_name(size_t metric_index)
{
	return (metric_index < PICOSYSTEM_PHYSICS_PROFILE_WORK_METRIC_COUNT)
		       ? work_names[metric_index]
		       : NULL;
}

static uint32_t profile_clock_now(void *context)
{
	ARG_UNUSED(context);
	return k_cycle_get_32();
}

static struct picosystem_game_input replay_input(uint32_t tick)
{
	static const struct picosystem_game_input inputs[] = {
		{.horizontal = 1},
		{.vertical = 1},
		{.horizontal = -1},
		{.vertical = -1},
		{.horizontal = 1, .vertical = 1},
		{.horizontal = -1, .vertical = -1},
		{0},
		{.horizontal = 1, .vertical = -1},
	};
	const size_t input_index = (tick / PICOSYSTEM_GAME_TICK_RATE_HZ) % ARRAY_SIZE(inputs);
	return inputs[input_index];
}

static struct picosystem_game_input profile_input(enum picosystem_physics_profile_fixture fixture,
						  uint32_t tick)
{
	if ((fixture == PICOSYSTEM_PHYSICS_PROFILE_FIXTURE_REVOLUTE_CHAIN) ||
	    (fixture == PICOSYSTEM_PHYSICS_PROFILE_FIXTURE_CANONICAL_NEUTRAL)) {
		return (struct picosystem_game_input){0};
	}
	return replay_input(tick);
}

static uint32_t work_value(const struct picosystem_physics_work_counters *work,
			   enum picosystem_physics_profile_work_metric metric)
{
	switch (metric) {
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_POSSIBLE_PAIRS:
		return work->possible_pair_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_CANDIDATE_PAIRS:
		return work->candidate_pair_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_GRID_CELL_INSERTIONS:
		return work->grid_cell_insertion_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_OCCUPIED_GRID_CELLS:
		return work->occupied_grid_cell_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_MAXIMUM_GRID_CELL_OCCUPANCY:
		return work->maximum_grid_cell_occupancy;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_BODY_BODY_TESTS:
		return work->body_body_narrow_phase_test_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_BODY_SEGMENT_TESTS:
		return work->body_segment_narrow_phase_test_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_BODY_SENSOR_TESTS:
		return work->body_sensor_narrow_phase_test_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_JOINT_COLLISION_FILTERS:
		return work->joint_collision_filter_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_MANIFOLDS:
		return work->manifold_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_CONTACT_POINTS:
		return work->contact_point_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_ACTIVE_CONTACT_PAIRS:
		return work->active_contact_pair_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_SENSOR_OVERLAPS:
		return work->sensor_overlap_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_CONTACT_BEGIN_EVENTS:
		return work->contact_begin_event_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_CONTACT_STAY_EVENTS:
		return work->contact_stay_event_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_CONTACT_END_EVENTS:
		return work->contact_end_event_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_POSITION_CORRECTION_VISITS:
		return work->position_correction_visit_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_SOLVER_ITERATIONS:
		return work->solver_iteration_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_SOLVER_CONTACT_VISITS:
		return work->solver_contact_visit_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_SOLVER_CACHED_CONTACTS:
		return work->solver_cached_contact_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_SOLVER_CHANGED_CONTACTS:
		return work->solver_changed_contact_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_DISTANCE_JOINTS:
		return work->distance_joint_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_REVOLUTE_JOINTS:
		return work->revolute_joint_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_REVOLUTE_MOTORS:
		return work->revolute_motor_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_REVOLUTE_LIMITS:
		return work->revolute_limit_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_PRISMATIC_JOINTS:
		return work->prismatic_joint_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_PRISMATIC_MOTORS:
		return work->prismatic_motor_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_PRISMATIC_LIMITS:
		return work->prismatic_limit_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_JOINT_POSITION_CORRECTION_VISITS:
		return work->joint_position_correction_visit_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_JOINT_LIMIT_POSITION_CORRECTION_VISITS:
		return work->joint_limit_position_correction_visit_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_JOINT_LIMIT_POSITION_CORRECTION_CHANGES:
		return work->joint_limit_position_correction_changed_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_JOINT_SOLVER_VISITS:
		return work->joint_solver_visit_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_JOINT_SOLVER_CHANGES:
		return work->joint_solver_changed_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_JOINT_MOTOR_SOLVER_VISITS:
		return work->joint_motor_solver_visit_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_JOINT_MOTOR_SOLVER_CHANGES:
		return work->joint_motor_solver_changed_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_JOINT_LIMIT_SOLVER_VISITS:
		return work->joint_limit_solver_visit_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_JOINT_LIMIT_SOLVER_CHANGES:
		return work->joint_limit_solver_changed_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_BROAD_PHASE_FALLBACKS:
		return work->broad_phase_fallback_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_AWAKE_BODIES:
		return work->awake_body_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_SLEEPING_BODIES:
		return work->sleeping_body_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_BODY_SLEEP_TRANSITIONS:
		return work->body_sleep_transition_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_BODY_WAKE_TRANSITIONS:
		return work->body_wake_transition_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_SLEEPING_CONTACTS:
		return work->sleeping_contact_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_SLEEPING_JOINTS:
		return work->sleeping_joint_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_SPRING_JOINTS:
		return work->spring_joint_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_SPRING_SOLVER_VISITS:
		return work->spring_solver_visit_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_SPRING_SOLVER_CHANGES:
		return work->spring_solver_changed_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_CONVEYOR_CONTACTS:
		return work->conveyor_contact_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_CONVEYOR_SOLVER_VISITS:
		return work->conveyor_solver_visit_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_CONVEYOR_SOLVER_CHANGES:
		return work->conveyor_solver_changed_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_ROPES:
		return work->rope_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_ROPE_PARTICLES:
		return work->rope_particle_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_ROPE_SOLVER_ITERATIONS:
		return work->rope_solver_iteration_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_ROPE_CONSTRAINT_VISITS:
		return work->rope_constraint_visit_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_ROPE_CONSTRAINT_CHANGES:
		return work->rope_constraint_changed_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_ROPE_BODY_CORRECTION_VISITS:
		return work->rope_body_correction_visit_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_ROPE_BODY_CORRECTION_CHANGES:
		return work->rope_body_correction_changed_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_ROPE_BODY_VELOCITY_VISITS:
		return work->rope_body_velocity_visit_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_ROPE_BODY_VELOCITY_CHANGES:
		return work->rope_body_velocity_changed_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_ROPE_COLLISION_POSSIBLE_PAIRS:
		return work->rope_collision_possible_pair_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_ROPE_COLLISION_CANDIDATE_PAIRS:
		return work->rope_collision_candidate_pair_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_ROPE_COLLISION_CONTACTS:
		return work->rope_collision_contact_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_ROPE_COLLISION_POSITION_CHANGES:
		return work->rope_collision_position_changed_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_ROPE_COLLISION_VELOCITY_CHANGES:
		return work->rope_collision_velocity_changed_count;
	case PICOSYSTEM_PHYSICS_PROFILE_WORK_METRIC_COUNT:
	default:
		return 0U;
	}
}

static void stage_accumulator_reset(struct profile_stage_accumulator *accumulator)
{
	memset(accumulator, 0, sizeof(*accumulator));
	accumulator->minimum_cycles = UINT32_MAX;
}

static void accumulators_reset(void)
{
	for (size_t stage = 0U; stage < PICOSYSTEM_PHYSICS_PROFILE_STAGE_COUNT; ++stage) {
		stage_accumulator_reset(&workspace.stages[stage]);
	}
}

static void stage_accumulate(struct profile_stage_accumulator *accumulator, uint32_t cycles,
			     uint32_t fine_bin_cycles, uint32_t coarse_bin_cycles,
			     uint32_t budget_cycles)
{
	accumulator->total_cycles += cycles;
	++accumulator->sample_count;
	if (cycles < accumulator->minimum_cycles) {
		accumulator->minimum_cycles = cycles;
	}
	if (cycles > accumulator->maximum_cycles) {
		accumulator->maximum_cycles = cycles;
	}
	if ((budget_cycles != 0U) && (cycles > budget_cycles)) {
		++accumulator->budget_violation_count;
	}

	const uint32_t fine_limit =
		PICOSYSTEM_PHYSICS_PROFILE_HISTOGRAM_FINE_BIN_COUNT * fine_bin_cycles;
	uint32_t bin = cycles / fine_bin_cycles;
	if (cycles >= fine_limit) {
		bin = PICOSYSTEM_PHYSICS_PROFILE_HISTOGRAM_FINE_BIN_COUNT +
		      ((cycles - fine_limit) / coarse_bin_cycles);
	}
	if (bin >= PICOSYSTEM_PHYSICS_PROFILE_HISTOGRAM_BIN_COUNT) {
		bin = PICOSYSTEM_PHYSICS_PROFILE_HISTOGRAM_BIN_COUNT - 1U;
	}
	++accumulator->histogram[bin];
}

static uint32_t histogram_percentile(const struct profile_stage_accumulator *accumulator,
				     uint32_t fine_bin_cycles, uint32_t coarse_bin_cycles,
				     uint32_t percentile)
{
	const uint32_t rank = ((accumulator->sample_count * percentile) + 99U) / 100U;
	uint32_t cumulative = 0U;
	for (uint32_t bin = 0U; bin < PICOSYSTEM_PHYSICS_PROFILE_HISTOGRAM_BIN_COUNT; ++bin) {
		cumulative += accumulator->histogram[bin];
		if (cumulative < rank) {
			continue;
		}
		if (bin == (PICOSYSTEM_PHYSICS_PROFILE_HISTOGRAM_BIN_COUNT - 1U)) {
			return accumulator->maximum_cycles;
		}
		if (bin < PICOSYSTEM_PHYSICS_PROFILE_HISTOGRAM_FINE_BIN_COUNT) {
			return (bin + 1U) * fine_bin_cycles;
		}
		const uint32_t coarse_bin =
			bin - PICOSYSTEM_PHYSICS_PROFILE_HISTOGRAM_FINE_BIN_COUNT;
		return (PICOSYSTEM_PHYSICS_PROFILE_HISTOGRAM_FINE_BIN_COUNT * fine_bin_cycles) +
		       ((coarse_bin + 1U) * coarse_bin_cycles);
	}
	return accumulator->maximum_cycles;
}

static void summarize_stages(struct picosystem_physics_profile_mode_result *mode_result,
			     uint32_t fine_bin_cycles, uint32_t coarse_bin_cycles)
{
	for (size_t stage = 0U; stage < PICOSYSTEM_PHYSICS_PROFILE_STAGE_COUNT; ++stage) {
		const struct profile_stage_accumulator *const accumulator =
			&workspace.stages[stage];
		mode_result->stages[stage] = (struct picosystem_physics_profile_stage_summary){
			.sample_count = accumulator->sample_count,
			.mean_cycles =
				(uint32_t)(accumulator->total_cycles / accumulator->sample_count),
			.minimum_cycles = accumulator->minimum_cycles,
			.percentile_50_cycles = histogram_percentile(accumulator, fine_bin_cycles,
								     coarse_bin_cycles, 50U),
			.percentile_95_cycles = histogram_percentile(accumulator, fine_bin_cycles,
								     coarse_bin_cycles, 95U),
			.percentile_99_cycles = histogram_percentile(accumulator, fine_bin_cycles,
								     coarse_bin_cycles, 99U),
			.maximum_cycles = accumulator->maximum_cycles,
			.budget_violation_count = accumulator->budget_violation_count,
		};
	}
}

static void capture_authoritative_state(const struct picosystem_game_world *world,
					struct authoritative_snapshot *snapshot)
{
	*snapshot = (struct authoritative_snapshot){
		.max_speed_per_tick = world->physics.max_speed_per_tick,
		.logic_tick_count = world->logic_tick_count,
		.sensor_entry_count = world->sensor_entry_count,
		.body_count = world->physics.body_count,
		.static_segment_count = world->physics.static_segment_count,
		.distance_joint_count = world->physics.distance_joint_count,
		.revolute_joint_count = world->physics.revolute_joint_count,
		.prismatic_joint_count = world->physics.prismatic_joint_count,
		.box_sensor_count = world->physics.box_sensor_count,
		.rope_count = world->physics.rope_count,
		.sleeping_body_mask = world->physics.sleeping_body_mask,
		.last_global_acceleration_per_tick =
			world->physics.last_global_acceleration_per_tick,
	};
	memcpy(snapshot->sleep_quiet_tick_counts, world->physics.sleep_quiet_tick_counts,
	       sizeof(snapshot->sleep_quiet_tick_counts));
	memcpy(snapshot->bodies, world->physics.bodies,
	       world->physics.body_count * sizeof(snapshot->bodies[0]));
	memcpy(snapshot->static_segments, world->physics.static_segments,
	       world->physics.static_segment_count * sizeof(snapshot->static_segments[0]));
	memcpy(snapshot->distance_joints, world->physics.distance_joints,
	       world->physics.distance_joint_count * sizeof(snapshot->distance_joints[0]));
	memcpy(snapshot->revolute_joints, world->physics.revolute_joints,
	       world->physics.revolute_joint_count * sizeof(snapshot->revolute_joints[0]));
	memcpy(snapshot->prismatic_joints, world->physics.prismatic_joints,
	       world->physics.prismatic_joint_count * sizeof(snapshot->prismatic_joints[0]));
	memcpy(snapshot->box_sensors, world->physics.box_sensors,
	       world->physics.box_sensor_count * sizeof(snapshot->box_sensors[0]));
	memcpy(snapshot->ropes, world->physics.ropes,
	       world->physics.rope_count * sizeof(snapshot->ropes[0]));
	memcpy(snapshot->active_body_contact_masks, world->physics.active_body_contact_masks,
	       sizeof(snapshot->active_body_contact_masks));
	memcpy(snapshot->active_segment_contact_masks, world->physics.active_segment_contact_masks,
	       sizeof(snapshot->active_segment_contact_masks));
	memcpy(snapshot->active_sensor_contact_masks, world->physics.active_sensor_contact_masks,
	       sizeof(snapshot->active_sensor_contact_masks));
}

static bool body_equal(const struct picosystem_physics_body *left,
		       const struct picosystem_physics_body *right)
{
	return (left->center.x == right->center.x) && (left->center.y == right->center.y) &&
	       (left->velocity_per_tick.x == right->velocity_per_tick.x) &&
	       (left->velocity_per_tick.y == right->velocity_per_tick.y) &&
	       (left->half_extent.x == right->half_extent.x) &&
	       (left->half_extent.y == right->half_extent.y) && (left->radius == right->radius) &&
	       (left->inverse_mass == right->inverse_mass) &&
	       (left->inverse_inertia == right->inverse_inertia) &&
	       (left->restitution == right->restitution) && (left->friction == right->friction) &&
	       (left->angular_velocity_per_tick == right->angular_velocity_per_tick) &&
	       (left->angle_turns == right->angle_turns) && (left->id == right->id) &&
	       (left->shape == right->shape);
}

static bool segment_equal(const struct picosystem_physics_static_segment *left,
			  const struct picosystem_physics_static_segment *right)
{
	return (left->start.x == right->start.x) && (left->start.y == right->start.y) &&
	       (left->end.x == right->end.x) && (left->end.y == right->end.y) &&
	       (left->normal.x == right->normal.x) && (left->normal.y == right->normal.y) &&
	       (left->restitution == right->restitution) && (left->friction == right->friction) &&
	       (left->surface_speed_per_tick == right->surface_speed_per_tick) &&
	       (left->id == right->id);
}

static bool sensor_equal(const struct picosystem_physics_box_sensor *left,
			 const struct picosystem_physics_box_sensor *right)
{
	return (left->center.x == right->center.x) && (left->center.y == right->center.y) &&
	       (left->half_extent.x == right->half_extent.x) &&
	       (left->half_extent.y == right->half_extent.y) && (left->id == right->id);
}

static bool rope_equal(const struct picosystem_physics_rope *left,
		       const struct picosystem_physics_rope *right)
{
	if ((left->anchor_a.x != right->anchor_a.x) || (left->anchor_a.y != right->anchor_a.y) ||
	    (left->anchor_b.x != right->anchor_b.x) || (left->anchor_b.y != right->anchor_b.y) ||
	    (left->segment_length != right->segment_length) || (left->id != right->id) ||
	    (left->body_a_id != right->body_a_id) || (left->body_b_id != right->body_b_id) ||
	    (left->body_a_index != right->body_a_index) ||
	    (left->body_b_index != right->body_b_index) ||
	    (left->particle_count != right->particle_count) || (left->pin_a != right->pin_a) ||
	    (left->pin_b != right->pin_b)) {
		return false;
	}
	for (uint8_t index = 0U; index < left->particle_count; ++index) {
		if ((left->particles[index].position.x != right->particles[index].position.x) ||
		    (left->particles[index].position.y != right->particles[index].position.y) ||
		    (left->particles[index].previous_position.x !=
		     right->particles[index].previous_position.x) ||
		    (left->particles[index].previous_position.y !=
		     right->particles[index].previous_position.y)) {
			return false;
		}
	}
	return true;
}

static bool distance_joint_equal(const struct picosystem_physics_distance_joint *left,
				 const struct picosystem_physics_distance_joint *right)
{
	return (left->local_anchor_a.x == right->local_anchor_a.x) &&
	       (left->local_anchor_a.y == right->local_anchor_a.y) &&
	       (left->anchor_b.x == right->anchor_b.x) && (left->anchor_b.y == right->anchor_b.y) &&
	       (left->target_distance == right->target_distance) &&
	       (left->spring_angular_frequency_per_tick ==
		right->spring_angular_frequency_per_tick) &&
	       (left->spring_damping_ratio == right->spring_damping_ratio) &&
	       (left->maximum_spring_impulse_per_tick == right->maximum_spring_impulse_per_tick) &&
	       (left->id == right->id) && (left->body_a_id == right->body_a_id) &&
	       (left->body_b_id == right->body_b_id) &&
	       (left->body_a_index == right->body_a_index) &&
	       (left->body_b_index == right->body_b_index) &&
	       (left->spring_enabled == right->spring_enabled);
}

static bool revolute_joint_equal(const struct picosystem_physics_revolute_joint *left,
				 const struct picosystem_physics_revolute_joint *right)
{
	return (left->local_anchor_a.x == right->local_anchor_a.x) &&
	       (left->local_anchor_a.y == right->local_anchor_a.y) &&
	       (left->anchor_b.x == right->anchor_b.x) && (left->anchor_b.y == right->anchor_b.y) &&
	       (left->motor_speed_per_tick == right->motor_speed_per_tick) &&
	       (left->maximum_motor_impulse_per_tick == right->maximum_motor_impulse_per_tick) &&
	       (left->lower_angle_radians == right->lower_angle_radians) &&
	       (left->upper_angle_radians == right->upper_angle_radians) &&
	       (left->reference_angle_turns == right->reference_angle_turns) &&
	       (left->id == right->id) && (left->body_a_id == right->body_a_id) &&
	       (left->body_b_id == right->body_b_id) &&
	       (left->body_a_index == right->body_a_index) &&
	       (left->body_b_index == right->body_b_index) &&
	       (left->collide_connected == right->collide_connected) &&
	       (left->motor_enabled == right->motor_enabled) &&
	       (left->limit_enabled == right->limit_enabled);
}

static bool prismatic_joint_equal(const struct picosystem_physics_prismatic_joint *left,
				  const struct picosystem_physics_prismatic_joint *right)
{
	return (left->local_anchor_a.x == right->local_anchor_a.x) &&
	       (left->local_anchor_a.y == right->local_anchor_a.y) &&
	       (left->anchor_b.x == right->anchor_b.x) && (left->anchor_b.y == right->anchor_b.y) &&
	       (left->axis_b.x == right->axis_b.x) && (left->axis_b.y == right->axis_b.y) &&
	       (left->motor_speed_per_tick == right->motor_speed_per_tick) &&
	       (left->maximum_motor_impulse_per_tick == right->maximum_motor_impulse_per_tick) &&
	       (left->lower_translation == right->lower_translation) &&
	       (left->upper_translation == right->upper_translation) &&
	       (left->reference_translation == right->reference_translation) &&
	       (left->reference_angle_turns == right->reference_angle_turns) &&
	       (left->id == right->id) && (left->body_a_id == right->body_a_id) &&
	       (left->body_b_id == right->body_b_id) &&
	       (left->body_a_index == right->body_a_index) &&
	       (left->body_b_index == right->body_b_index) &&
	       (left->collide_connected == right->collide_connected) &&
	       (left->motor_enabled == right->motor_enabled) &&
	       (left->limit_enabled == right->limit_enabled);
}

static bool authoritative_state_matches(const struct picosystem_game_world *world,
					const struct authoritative_snapshot *snapshot)
{
	if ((world->logic_tick_count != snapshot->logic_tick_count) ||
	    (world->sensor_entry_count != snapshot->sensor_entry_count) ||
	    (world->physics.max_speed_per_tick != snapshot->max_speed_per_tick) ||
	    (world->physics.body_count != snapshot->body_count) ||
	    (world->physics.static_segment_count != snapshot->static_segment_count) ||
	    (world->physics.distance_joint_count != snapshot->distance_joint_count) ||
	    (world->physics.revolute_joint_count != snapshot->revolute_joint_count) ||
	    (world->physics.prismatic_joint_count != snapshot->prismatic_joint_count) ||
	    (world->physics.box_sensor_count != snapshot->box_sensor_count) ||
	    (world->physics.rope_count != snapshot->rope_count) ||
	    (world->physics.sleeping_body_mask != snapshot->sleeping_body_mask) ||
	    (world->physics.last_global_acceleration_per_tick.x !=
	     snapshot->last_global_acceleration_per_tick.x) ||
	    (world->physics.last_global_acceleration_per_tick.y !=
	     snapshot->last_global_acceleration_per_tick.y)) {
		return false;
	}
	for (uint16_t index = 0U; index < snapshot->body_count; ++index) {
		if (!body_equal(&world->physics.bodies[index], &snapshot->bodies[index])) {
			return false;
		}
		if (world->physics.sleep_quiet_tick_counts[index] !=
		    snapshot->sleep_quiet_tick_counts[index]) {
			return false;
		}
		if ((world->physics.active_body_contact_masks[index] !=
		     snapshot->active_body_contact_masks[index]) ||
		    (world->physics.active_segment_contact_masks[index] !=
		     snapshot->active_segment_contact_masks[index]) ||
		    (world->physics.active_sensor_contact_masks[index] !=
		     snapshot->active_sensor_contact_masks[index])) {
			return false;
		}
	}
	for (uint16_t index = 0U; index < snapshot->static_segment_count; ++index) {
		if (!segment_equal(&world->physics.static_segments[index],
				   &snapshot->static_segments[index])) {
			return false;
		}
	}
	for (uint16_t index = 0U; index < snapshot->box_sensor_count; ++index) {
		if (!sensor_equal(&world->physics.box_sensors[index],
				  &snapshot->box_sensors[index])) {
			return false;
		}
	}
	for (uint16_t index = 0U; index < snapshot->rope_count; ++index) {
		if (!rope_equal(&world->physics.ropes[index], &snapshot->ropes[index])) {
			return false;
		}
	}
	for (uint16_t index = 0U; index < snapshot->distance_joint_count; ++index) {
		if (!distance_joint_equal(&world->physics.distance_joints[index],
					  &snapshot->distance_joints[index])) {
			return false;
		}
	}
	for (uint16_t index = 0U; index < snapshot->revolute_joint_count; ++index) {
		if (!revolute_joint_equal(&world->physics.revolute_joints[index],
					  &snapshot->revolute_joints[index])) {
			return false;
		}
	}
	for (uint16_t index = 0U; index < snapshot->prismatic_joint_count; ++index) {
		if (!prismatic_joint_equal(&world->physics.prismatic_joints[index],
					   &snapshot->prismatic_joints[index])) {
			return false;
		}
	}
	return true;
}

static uint32_t measure_clock_delta(void)
{
	uint64_t total = 0U;
	k_sched_lock();
	for (uint32_t sample = 0U; sample < PROFILE_CLOCK_SAMPLE_COUNT; ++sample) {
		const uint32_t start = k_cycle_get_32();
		total += k_cycle_get_32() - start;
	}
	k_sched_unlock();
	return (uint32_t)(total / PROFILE_CLOCK_SAMPLE_COUNT);
}

static uint32_t integer_square_root(uint64_t value)
{
	uint64_t result = 0U;
	uint64_t bit = UINT64_C(1) << 62U;
	while (bit > value) {
		bit >>= 2U;
	}
	while (bit != 0U) {
		if (value >= (result + bit)) {
			value -= result + bit;
			result = (result >> 1U) + bit;
		} else {
			result >>= 1U;
		}
		bit >>= 2U;
	}
	return (result <= UINT32_MAX) ? (uint32_t)result : UINT32_MAX;
}

static int maximum_revolute_anchor_error_squared(const struct picosystem_game_world *world,
						 uint64_t *maximum_squared)
{
	uint64_t maximum = 0U;
	for (uint16_t index = 0U; index < world->physics.revolute_joint_count; ++index) {
		struct picosystem_physics_vector anchor_a;
		struct picosystem_physics_vector anchor_b;
		const int err = picosystem_physics_world_revolute_joint_anchors(
			&world->physics, index, &anchor_a, &anchor_b);
		if (err != 0) {
			return err;
		}
		const int64_t delta_x = (int64_t)anchor_b.x - anchor_a.x;
		const int64_t delta_y = (int64_t)anchor_b.y - anchor_a.y;
		const uint64_t squared = (uint64_t)((delta_x * delta_x) + (delta_y * delta_y));
		if (squared > maximum) {
			maximum = squared;
		}
	}
	*maximum_squared = maximum;
	return 0;
}

static int maximum_revolute_limit_violation(const struct picosystem_game_world *world,
					    uint32_t *maximum_violation)
{
	uint32_t maximum = 0U;
	for (uint16_t index = 0U; index < world->physics.revolute_joint_count; ++index) {
		const struct picosystem_physics_revolute_joint *const joint =
			&world->physics.revolute_joints[index];
		if (joint->limit_enabled == 0U) {
			continue;
		}

		picosystem_physics_fixed_t angle;
		const int err = picosystem_physics_world_revolute_joint_angle(&world->physics,
									      index, &angle);
		if (err != 0) {
			return err;
		}

		uint32_t violation = 0U;
		if (angle < joint->lower_angle_radians) {
			violation = (uint32_t)(joint->lower_angle_radians - angle);
		} else if (angle > joint->upper_angle_radians) {
			violation = (uint32_t)(angle - joint->upper_angle_radians);
		}
		if (violation > maximum) {
			maximum = violation;
		}
	}
	*maximum_violation = maximum;
	return 0;
}

static int maximum_prismatic_quality(const struct picosystem_game_world *world,
				     uint32_t *maximum_lateral_error,
				     uint32_t *maximum_angular_error,
				     uint32_t *maximum_limit_violation)
{
	uint32_t lateral_maximum = 0U;
	uint32_t angular_maximum = 0U;
	uint32_t limit_maximum = 0U;
	for (uint16_t index = 0U; index < world->physics.prismatic_joint_count; ++index) {
		const struct picosystem_physics_prismatic_joint *const joint =
			&world->physics.prismatic_joints[index];
		struct picosystem_physics_vector anchor_a;
		struct picosystem_physics_vector anchor_b;
		struct picosystem_physics_vector axis;
		int err = picosystem_physics_world_prismatic_joint_geometry(
			&world->physics, index, &anchor_a, &anchor_b, &axis);
		if (err != 0) {
			return err;
		}
		const int64_t delta_x = (int64_t)anchor_a.x - anchor_b.x;
		const int64_t delta_y = (int64_t)anchor_a.y - anchor_b.y;
		const int64_t lateral =
			((delta_x * -axis.y) + (delta_y * axis.x)) / PICOSYSTEM_PHYSICS_FIXED_ONE;
		const uint32_t lateral_absolute = (uint32_t)((lateral < 0) ? -lateral : lateral);
		if (lateral_absolute > lateral_maximum) {
			lateral_maximum = lateral_absolute;
		}

		picosystem_physics_fixed_t angle;
		err = picosystem_physics_world_prismatic_joint_angle(&world->physics, index,
								     &angle);
		if (err != 0) {
			return err;
		}
		const uint32_t angular_absolute = (uint32_t)((angle < 0) ? -angle : angle);
		if (angular_absolute > angular_maximum) {
			angular_maximum = angular_absolute;
		}

		if (joint->limit_enabled == 0U) {
			continue;
		}
		picosystem_physics_fixed_t translation;
		err = picosystem_physics_world_prismatic_joint_translation(&world->physics, index,
									   &translation);
		if (err != 0) {
			return err;
		}
		uint32_t violation = 0U;
		if (translation < joint->lower_translation) {
			violation = (uint32_t)(joint->lower_translation - translation);
		} else if (translation > joint->upper_translation) {
			violation = (uint32_t)(translation - joint->upper_translation);
		}
		if (violation > limit_maximum) {
			limit_maximum = violation;
		}
	}
	*maximum_lateral_error = lateral_maximum;
	*maximum_angular_error = angular_maximum;
	*maximum_limit_violation = limit_maximum;
	return 0;
}

static uint32_t maximum_rope_segment_error(const struct picosystem_game_world *world)
{
	uint32_t maximum = 0U;
	for (uint16_t rope_index = 0U; rope_index < world->physics.rope_count; ++rope_index) {
		const struct picosystem_physics_rope *const rope =
			&world->physics.ropes[rope_index];
		for (uint8_t particle = 0U; particle < (rope->particle_count - 1U); ++particle) {
			const struct picosystem_physics_vector *const left =
				&rope->particles[particle].position;
			const struct picosystem_physics_vector *const right =
				&rope->particles[particle + 1U].position;
			const int64_t delta_x = (int64_t)right->x - left->x;
			const int64_t delta_y = (int64_t)right->y - left->y;
			const uint32_t distance = integer_square_root(
				(uint64_t)((delta_x * delta_x) + (delta_y * delta_y)));
			const uint32_t target = (uint32_t)rope->segment_length;
			const uint32_t error =
				(distance >= target) ? distance - target : target - distance;
			if (error > maximum) {
				maximum = error;
			}
		}
	}
	return maximum;
}

static int reset_profile_world(enum picosystem_physics_profile_fixture fixture,
			       uint16_t chain_link_count)
{
	switch (fixture) {
	case PICOSYSTEM_PHYSICS_PROFILE_FIXTURE_CANONICAL:
	case PICOSYSTEM_PHYSICS_PROFILE_FIXTURE_CANONICAL_NEUTRAL:
		return picosystem_game_world_reset(&workspace.world);
	case PICOSYSTEM_PHYSICS_PROFILE_FIXTURE_REVOLUTE_CHAIN:
		return picosystem_physics_chain_fixture_reset(&workspace.world, chain_link_count);
	case PICOSYSTEM_PHYSICS_PROFILE_FIXTURE_COUNT:
	default:
		return -EINVAL;
	}
}

static int prepare_profile_tick(enum picosystem_physics_profile_fixture fixture)
{
	if (fixture != PICOSYSTEM_PHYSICS_PROFILE_FIXTURE_REVOLUTE_CHAIN) {
		return 0;
	}

	/* Keep the chain benchmark measuring active constraint work after it settles. */
	return picosystem_physics_world_wake_body(&workspace.world.physics, 0U);
}

static int run_mode(size_t mode_index, enum picosystem_physics_profile_fixture fixture,
		    uint16_t chain_link_count, uint32_t measured_tick_count,
		    uint32_t fine_bin_cycles, uint32_t coarse_bin_cycles, uint32_t budget_cycles,
		    struct picosystem_physics_profile_mode_result *mode_result)
{
	const enum picosystem_physics_step_mode mode =
		(mode_index == 0U) ? PICOSYSTEM_PHYSICS_STEP_MODE_GRID
				   : PICOSYSTEM_PHYSICS_STEP_MODE_REFERENCE;
	int err = reset_profile_world(fixture, chain_link_count);
	if (err != 0) {
		return err;
	}
	memset(mode_result, 0, sizeof(*mode_result));
	mode_result->minimum_clock_reads_per_step = UINT32_MAX;

	for (uint32_t tick = 0U; tick < PICOSYSTEM_PHYSICS_PROFILE_WARMUP_TICKS; ++tick) {
		err = prepare_profile_tick(fixture);
		if (err != 0) {
			return err;
		}
		const struct picosystem_game_input input = profile_input(fixture, tick);
		k_sched_lock();
		err = picosystem_game_world_step_profiled(&workspace.world, &input, mode, NULL,
							  NULL);
		k_sched_unlock();
		if (err != 0) {
			return err;
		}
	}

	accumulators_reset();
	const struct picosystem_physics_clock clock = {
		.now = profile_clock_now,
	};
	uint64_t maximum_anchor_error_squared = 0U;
	uint32_t maximum_limit_violation = 0U;
	uint32_t maximum_prismatic_lateral_error = 0U;
	uint32_t maximum_prismatic_angular_error = 0U;
	uint32_t maximum_prismatic_limit_violation = 0U;
	uint32_t maximum_rope_error = 0U;
	for (uint32_t measured_tick = 0U; measured_tick < measured_tick_count; ++measured_tick) {
		err = prepare_profile_tick(fixture);
		if (err != 0) {
			return err;
		}
		const uint32_t replay_tick =
			PICOSYSTEM_PHYSICS_PROFILE_WARMUP_TICKS + measured_tick;
		const struct picosystem_game_input input = profile_input(fixture, replay_tick);
		struct picosystem_physics_step_profile profile;
		k_sched_lock();
		err = picosystem_game_world_step_profiled(&workspace.world, &input, mode, &clock,
							  &profile);
		k_sched_unlock();
		if (err != 0) {
			return err;
		}
		uint64_t anchor_error_squared;
		err = maximum_revolute_anchor_error_squared(&workspace.world,
							    &anchor_error_squared);
		if (err != 0) {
			return err;
		}
		if (anchor_error_squared > maximum_anchor_error_squared) {
			maximum_anchor_error_squared = anchor_error_squared;
		}
		uint32_t limit_violation;
		err = maximum_revolute_limit_violation(&workspace.world, &limit_violation);
		if (err != 0) {
			return err;
		}
		if (limit_violation > maximum_limit_violation) {
			maximum_limit_violation = limit_violation;
		}
		uint32_t prismatic_lateral_error;
		uint32_t prismatic_angular_error;
		uint32_t prismatic_limit_violation;
		err = maximum_prismatic_quality(&workspace.world, &prismatic_lateral_error,
						&prismatic_angular_error,
						&prismatic_limit_violation);
		if (err != 0) {
			return err;
		}
		if (prismatic_lateral_error > maximum_prismatic_lateral_error) {
			maximum_prismatic_lateral_error = prismatic_lateral_error;
		}
		if (prismatic_angular_error > maximum_prismatic_angular_error) {
			maximum_prismatic_angular_error = prismatic_angular_error;
		}
		if (prismatic_limit_violation > maximum_prismatic_limit_violation) {
			maximum_prismatic_limit_violation = prismatic_limit_violation;
		}
		const uint32_t rope_error = maximum_rope_segment_error(&workspace.world);
		if (rope_error > maximum_rope_error) {
			maximum_rope_error = rope_error;
		}

		for (size_t stage = 0U; stage < PICOSYSTEM_PHYSICS_PROFILE_STAGE_COUNT; ++stage) {
			const uint32_t stage_budget =
				(stage == PICOSYSTEM_PHYSICS_PROFILE_TOTAL) ? budget_cycles : 0U;
			stage_accumulate(&workspace.stages[stage], profile.stage_cycles[stage],
					 fine_bin_cycles, coarse_bin_cycles, stage_budget);
		}
		for (enum picosystem_physics_profile_work_metric metric =
			     PICOSYSTEM_PHYSICS_PROFILE_WORK_POSSIBLE_PAIRS;
		     metric < PICOSYSTEM_PHYSICS_PROFILE_WORK_METRIC_COUNT; ++metric) {
			const uint32_t value = work_value(&profile.work, metric);
			mode_result->work[metric].total += value;
			if (value > mode_result->work[metric].maximum) {
				mode_result->work[metric].maximum = value;
			}
		}
		if (profile.clock_read_count < mode_result->minimum_clock_reads_per_step) {
			mode_result->minimum_clock_reads_per_step = profile.clock_read_count;
		}
		if (profile.clock_read_count > mode_result->maximum_clock_reads_per_step) {
			mode_result->maximum_clock_reads_per_step = profile.clock_read_count;
		}

		if (((measured_tick + 1U) % PROFILE_YIELD_INTERVAL_TICKS) == 0U) {
			k_yield();
		}
	}

	summarize_stages(mode_result, fine_bin_cycles, coarse_bin_cycles);
	mode_result->final_hash = picosystem_game_world_hash(&workspace.world);
	mode_result->maximum_revolute_anchor_error_q16 =
		integer_square_root(maximum_anchor_error_squared);
	mode_result->maximum_revolute_limit_violation_q16 = maximum_limit_violation;
	mode_result->maximum_prismatic_lateral_error_q16 = maximum_prismatic_lateral_error;
	mode_result->maximum_prismatic_angular_error_q16 = maximum_prismatic_angular_error;
	mode_result->maximum_prismatic_limit_violation_q16 = maximum_prismatic_limit_violation;
	mode_result->maximum_rope_segment_error_q16 = maximum_rope_error;
	return 0;
}

static int compare_fixture(enum picosystem_physics_profile_fixture fixture,
			   uint16_t chain_link_count, uint32_t measured_tick_count,
			   struct picosystem_physics_profile_result *result)
{
	if (result == NULL) {
		return -EINVAL;
	}
	if ((measured_tick_count == 0U) ||
	    (measured_tick_count > PICOSYSTEM_PHYSICS_PROFILE_MAX_TICKS)) {
		return -ERANGE;
	}
	if ((((fixture == PICOSYSTEM_PHYSICS_PROFILE_FIXTURE_CANONICAL) ||
	      (fixture == PICOSYSTEM_PHYSICS_PROFILE_FIXTURE_CANONICAL_NEUTRAL)) &&
	     (chain_link_count != 0U)) ||
	    ((fixture == PICOSYSTEM_PHYSICS_PROFILE_FIXTURE_REVOLUTE_CHAIN) &&
	     ((chain_link_count < PICOSYSTEM_PHYSICS_CHAIN_FIXTURE_MIN_LINKS) ||
	      (chain_link_count > PICOSYSTEM_PHYSICS_CHAIN_FIXTURE_MAX_LINKS))) ||
	    (fixture < PICOSYSTEM_PHYSICS_PROFILE_FIXTURE_CANONICAL) ||
	    (fixture >= PICOSYSTEM_PHYSICS_PROFILE_FIXTURE_COUNT)) {
		return -ERANGE;
	}

	const int lock_err = k_mutex_lock(&profile_mutex, K_FOREVER);
	if (lock_err != 0) {
		return lock_err;
	}

	memset(result, 0, sizeof(*result));
	result->schema_version = PICOSYSTEM_PHYSICS_PROFILE_SCHEMA_VERSION;
	result->fixture = (uint8_t)fixture;
	result->chain_link_count = chain_link_count;
	result->measured_tick_count = measured_tick_count;
	result->warmup_tick_count = PICOSYSTEM_PHYSICS_PROFILE_WARMUP_TICKS;
	result->tick_rate_hz = PICOSYSTEM_GAME_TICK_RATE_HZ;
	result->clock_frequency_hz = CONFIG_SYS_CLOCK_HW_CYCLES_PER_SEC;
	result->histogram_fine_bin_cycles =
		(uint32_t)(((uint64_t)result->clock_frequency_hz *
				    PICOSYSTEM_PHYSICS_PROFILE_HISTOGRAM_FINE_BIN_US +
			    999999U) /
			   1000000U);
	result->histogram_coarse_bin_cycles =
		(uint32_t)(((uint64_t)result->clock_frequency_hz *
				    PICOSYSTEM_PHYSICS_PROFILE_HISTOGRAM_COARSE_BIN_US +
			    999999U) /
			   1000000U);
	result->back_to_back_clock_delta_cycles = measure_clock_delta();
	const uint32_t budget_cycles = result->clock_frequency_hz / PICOSYSTEM_GAME_TICK_RATE_HZ;

	int err = run_mode(0U, fixture, chain_link_count, measured_tick_count,
			   result->histogram_fine_bin_cycles, result->histogram_coarse_bin_cycles,
			   budget_cycles, &result->modes[0]);
	if (err == 0) {
		capture_authoritative_state(&workspace.world, &workspace.grid_final_state);
		err = run_mode(1U, fixture, chain_link_count, measured_tick_count,
			       result->histogram_fine_bin_cycles,
			       result->histogram_coarse_bin_cycles, budget_cycles,
			       &result->modes[1]);
	}
	if (err == 0) {
		result->hashes_match = result->modes[0].final_hash == result->modes[1].final_hash;
		result->states_match =
			authoritative_state_matches(&workspace.world, &workspace.grid_final_state);
		if (!result->hashes_match || !result->states_match) {
			err = -EILSEQ;
		}
	}

	k_mutex_unlock(&profile_mutex);
	return err;
}

int picosystem_physics_profile_compare(uint32_t measured_tick_count,
				       struct picosystem_physics_profile_result *result)
{
	return compare_fixture(PICOSYSTEM_PHYSICS_PROFILE_FIXTURE_CANONICAL, 0U,
			       measured_tick_count, result);
}

int picosystem_physics_profile_compare_neutral(uint32_t measured_tick_count,
					       struct picosystem_physics_profile_result *result)
{
	return compare_fixture(PICOSYSTEM_PHYSICS_PROFILE_FIXTURE_CANONICAL_NEUTRAL, 0U,
			       measured_tick_count, result);
}

int picosystem_physics_profile_compare_chain(uint16_t link_count, uint32_t measured_tick_count,
					     struct picosystem_physics_profile_result *result)
{
	return compare_fixture(PICOSYSTEM_PHYSICS_PROFILE_FIXTURE_REVOLUTE_CHAIN, link_count,
			       measured_tick_count, result);
}
