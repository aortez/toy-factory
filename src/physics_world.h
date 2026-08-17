/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_PHYSICS_WORLD_H_
#define PICOSYSTEM_PHYSICS_WORLD_H_

#include <stddef.h>
#include <stdint.h>

#define PICOSYSTEM_PHYSICS_FIXED_FRACTION_BITS   16U
#define PICOSYSTEM_PHYSICS_FIXED_ONE             (INT32_C(1) << PICOSYSTEM_PHYSICS_FIXED_FRACTION_BITS)
#define PICOSYSTEM_PHYSICS_FIXED_FROM_INT(value) ((int32_t)(value) * PICOSYSTEM_PHYSICS_FIXED_ONE)
#define PICOSYSTEM_PHYSICS_FIXED_RATIO(numerator, denominator)                                     \
	((int32_t)(((int64_t)(numerator) * PICOSYSTEM_PHYSICS_FIXED_ONE) / (denominator)))

#define PICOSYSTEM_PHYSICS_MAX_BODIES          12U
#define PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS 8U
#define PICOSYSTEM_PHYSICS_MAX_CONTACTS                                                            \
	(((PICOSYSTEM_PHYSICS_MAX_BODIES * (PICOSYSTEM_PHYSICS_MAX_BODIES - 1U)) / 2U) +           \
	 (PICOSYSTEM_PHYSICS_MAX_BODIES * PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS))
#define PICOSYSTEM_PHYSICS_SOLVER_ITERATIONS 6U

typedef int32_t picosystem_physics_fixed_t;

struct picosystem_physics_vector {
	picosystem_physics_fixed_t x;
	picosystem_physics_fixed_t y;
};

struct picosystem_physics_circle_config {
	struct picosystem_physics_vector center;
	struct picosystem_physics_vector velocity_per_tick;
	picosystem_physics_fixed_t radius;
	picosystem_physics_fixed_t inverse_mass;
	picosystem_physics_fixed_t restitution;
	picosystem_physics_fixed_t friction;
	uint16_t id;
};

struct picosystem_physics_segment_config {
	struct picosystem_physics_vector start;
	struct picosystem_physics_vector end;
	picosystem_physics_fixed_t restitution;
	picosystem_physics_fixed_t friction;
	uint16_t id;
};

struct picosystem_physics_body {
	struct picosystem_physics_vector center;
	struct picosystem_physics_vector velocity_per_tick;
	picosystem_physics_fixed_t radius;
	picosystem_physics_fixed_t inverse_mass;
	picosystem_physics_fixed_t restitution;
	picosystem_physics_fixed_t friction;
	uint16_t id;
};

struct picosystem_physics_static_segment {
	struct picosystem_physics_vector start;
	struct picosystem_physics_vector end;
	picosystem_physics_fixed_t restitution;
	picosystem_physics_fixed_t friction;
	uint16_t id;
};

enum picosystem_physics_contact_type {
	PICOSYSTEM_PHYSICS_CONTACT_BODY,
	PICOSYSTEM_PHYSICS_CONTACT_STATIC_SEGMENT,
};

/* Scratch contact state rebuilt on every update and excluded from authoritative hashes. */
struct picosystem_physics_contact {
	struct picosystem_physics_vector normal;
	picosystem_physics_fixed_t penetration;
	picosystem_physics_fixed_t target_normal_velocity;
	picosystem_physics_fixed_t accumulated_normal_impulse;
	picosystem_physics_fixed_t accumulated_tangent_impulse;
	uint8_t body_a_index;
	uint8_t body_b_index;
	uint8_t segment_index;
	uint8_t type;
};

struct picosystem_physics_world {
	struct picosystem_physics_body bodies[PICOSYSTEM_PHYSICS_MAX_BODIES];
	struct picosystem_physics_static_segment
		static_segments[PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS];
	struct picosystem_physics_contact contacts[PICOSYSTEM_PHYSICS_MAX_CONTACTS];
	picosystem_physics_fixed_t max_speed_per_tick;
	uint32_t last_candidate_pair_count;
	uint16_t body_count;
	uint16_t static_segment_count;
	uint16_t contact_count;
};

/* Initialize an empty, caller-owned world with a bounded vector-speed limit. */
int picosystem_physics_world_init(struct picosystem_physics_world *world,
				  picosystem_physics_fixed_t max_speed_per_tick);

/* Append canonical configuration before stepping; failures preserve the world. */
int picosystem_physics_world_add_circle(struct picosystem_physics_world *world,
					const struct picosystem_physics_circle_config *config);
int picosystem_physics_world_add_static_segment(
	struct picosystem_physics_world *world,
	const struct picosystem_physics_segment_config *config);

/* Advance exactly one tick with a global acceleration expressed in pixels/tick^2. */
int picosystem_physics_world_step(
	struct picosystem_physics_world *world,
	const struct picosystem_physics_vector *global_acceleration_per_tick);

const struct picosystem_physics_body *
picosystem_physics_world_body_at(const struct picosystem_physics_world *world, size_t index);

/* Hash persistent configuration and body state, excluding contacts and diagnostics. */
uint32_t picosystem_physics_world_hash(const struct picosystem_physics_world *world);

#endif /* PICOSYSTEM_PHYSICS_WORLD_H_ */
