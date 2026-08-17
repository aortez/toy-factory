/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "physics_world.h"

#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define PHYSICS_POSITION_LIMIT       PICOSYSTEM_PHYSICS_FIXED_FROM_INT(1024)
#define PHYSICS_VELOCITY_LIMIT       PICOSYSTEM_PHYSICS_FIXED_FROM_INT(8)
#define PHYSICS_ACCELERATION_LIMIT   PICOSYSTEM_PHYSICS_FIXED_ONE
#define PHYSICS_RADIUS_LIMIT         PICOSYSTEM_PHYSICS_FIXED_FROM_INT(128)
#define PHYSICS_INVERSE_MASS_MINIMUM (PICOSYSTEM_PHYSICS_FIXED_ONE / 16)
#define PHYSICS_INVERSE_MASS_MAXIMUM (PICOSYSTEM_PHYSICS_FIXED_ONE * 4)
#define PHYSICS_POSITION_SLOP        (PICOSYSTEM_PHYSICS_FIXED_ONE / 256)
#define PHYSICS_BOUNCE_THRESHOLD     (PICOSYSTEM_PHYSICS_FIXED_ONE / 64)
#define PHYSICS_HASH_VERSION         UINT32_C(1)
#define FNV1A_OFFSET_BASIS           UINT32_C(2166136261)
#define FNV1A_PRIME                  UINT32_C(16777619)
#define STATIC_BODY_INDEX            UINT8_MAX
#define STATIC_SEGMENT_INDEX         UINT8_MAX

_Static_assert(PICOSYSTEM_PHYSICS_MAX_BODIES <= UINT8_MAX, "body indices must fit in one byte");
_Static_assert(PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS <= UINT8_MAX,
	       "segment indices must fit in one byte");
_Static_assert(PICOSYSTEM_PHYSICS_MAX_CONTACTS <= UINT16_MAX,
	       "contact count must fit in the public world field");
_Static_assert(PICOSYSTEM_PHYSICS_MAX_CONTACTS >=
		       (((PICOSYSTEM_PHYSICS_MAX_BODIES * (PICOSYSTEM_PHYSICS_MAX_BODIES - 1U)) /
			 2U) +
			(PICOSYSTEM_PHYSICS_MAX_BODIES * PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS)),
	       "contact storage must cover every brute-force candidate");

static picosystem_physics_fixed_t fixed_minimum(picosystem_physics_fixed_t left,
						picosystem_physics_fixed_t right)
{
	return (left < right) ? left : right;
}

static picosystem_physics_fixed_t fixed_clamp(picosystem_physics_fixed_t value,
					      picosystem_physics_fixed_t minimum,
					      picosystem_physics_fixed_t maximum)
{
	if (value < minimum) {
		return minimum;
	}
	if (value > maximum) {
		return maximum;
	}
	return value;
}

static picosystem_physics_fixed_t fixed_multiply(picosystem_physics_fixed_t left,
						 picosystem_physics_fixed_t right)
{
	return (picosystem_physics_fixed_t)(((int64_t)left * right) / PICOSYSTEM_PHYSICS_FIXED_ONE);
}

static picosystem_physics_fixed_t fixed_divide(picosystem_physics_fixed_t numerator,
					       picosystem_physics_fixed_t denominator)
{
	return (picosystem_physics_fixed_t)(((int64_t)numerator * PICOSYSTEM_PHYSICS_FIXED_ONE) /
					    denominator);
}

static picosystem_physics_fixed_t vector_dot(const struct picosystem_physics_vector *left,
					     const struct picosystem_physics_vector *right)
{
	const int64_t raw = ((int64_t)left->x * right->x) + ((int64_t)left->y * right->y);
	return (picosystem_physics_fixed_t)(raw / PICOSYSTEM_PHYSICS_FIXED_ONE);
}

static uint64_t vector_length_squared_raw(const struct picosystem_physics_vector *vector)
{
	return (uint64_t)(((int64_t)vector->x * vector->x) + ((int64_t)vector->y * vector->y));
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

	return (uint32_t)result;
}

static uint32_t integer_square_root_ceiling(uint64_t value)
{
	uint32_t result = integer_square_root(value);
	if (((uint64_t)result * result) < value) {
		++result;
	}
	return result;
}

static picosystem_physics_fixed_t
normalize_vector(const struct picosystem_physics_vector *vector,
		 struct picosystem_physics_vector *normal,
		 const struct picosystem_physics_vector *zero_fallback)
{
	const uint32_t length = integer_square_root(vector_length_squared_raw(vector));
	if (length == 0U) {
		*normal = *zero_fallback;
		return 0;
	}

	normal->x =
		(picosystem_physics_fixed_t)(((int64_t)vector->x * PICOSYSTEM_PHYSICS_FIXED_ONE) /
					     length);
	normal->y =
		(picosystem_physics_fixed_t)(((int64_t)vector->y * PICOSYSTEM_PHYSICS_FIXED_ONE) /
					     length);
	return (picosystem_physics_fixed_t)length;
}

static bool fixed_is_bounded(picosystem_physics_fixed_t value, picosystem_physics_fixed_t limit)
{
	return (value >= -limit) && (value <= limit);
}

static bool material_is_valid(picosystem_physics_fixed_t coefficient)
{
	return (coefficient >= 0) && (coefficient <= PICOSYSTEM_PHYSICS_FIXED_ONE);
}

static bool vector_is_bounded(const struct picosystem_physics_vector *vector,
			      picosystem_physics_fixed_t limit)
{
	return fixed_is_bounded(vector->x, limit) && fixed_is_bounded(vector->y, limit);
}

static bool speed_is_bounded(const struct picosystem_physics_vector *velocity,
			     picosystem_physics_fixed_t maximum)
{
	const uint64_t speed_squared = vector_length_squared_raw(velocity);
	const uint64_t maximum_squared = (uint64_t)((int64_t)maximum * maximum);
	return speed_squared <= maximum_squared;
}

static bool body_config_is_valid(const struct picosystem_physics_circle_config *config,
				 const struct picosystem_physics_world *world)
{
	return (config != NULL) && (config->id != 0U) &&
	       vector_is_bounded(&config->center, PHYSICS_POSITION_LIMIT) &&
	       vector_is_bounded(&config->velocity_per_tick, PHYSICS_VELOCITY_LIMIT) &&
	       speed_is_bounded(&config->velocity_per_tick, world->max_speed_per_tick) &&
	       (config->radius > 0) && (config->radius <= PHYSICS_RADIUS_LIMIT) &&
	       (config->inverse_mass >= PHYSICS_INVERSE_MASS_MINIMUM) &&
	       (config->inverse_mass <= PHYSICS_INVERSE_MASS_MAXIMUM) &&
	       material_is_valid(config->restitution) && material_is_valid(config->friction);
}

static bool segment_config_is_valid(const struct picosystem_physics_segment_config *config)
{
	if ((config == NULL) || (config->id == 0U) ||
	    !vector_is_bounded(&config->start, PHYSICS_POSITION_LIMIT) ||
	    !vector_is_bounded(&config->end, PHYSICS_POSITION_LIMIT) ||
	    !material_is_valid(config->restitution) || !material_is_valid(config->friction)) {
		return false;
	}

	const struct picosystem_physics_vector extent = {
		.x = config->end.x - config->start.x,
		.y = config->end.y - config->start.y,
	};
	const uint64_t minimum_length_squared =
		(uint64_t)PICOSYSTEM_PHYSICS_FIXED_ONE * PICOSYSTEM_PHYSICS_FIXED_ONE;
	return vector_length_squared_raw(&extent) >= minimum_length_squared;
}

static bool body_is_valid(const struct picosystem_physics_body *body,
			  const struct picosystem_physics_world *world)
{
	const struct picosystem_physics_circle_config config = {
		.center = body->center,
		.velocity_per_tick = body->velocity_per_tick,
		.radius = body->radius,
		.inverse_mass = body->inverse_mass,
		.restitution = body->restitution,
		.friction = body->friction,
		.id = body->id,
	};
	return body_config_is_valid(&config, world);
}

static bool segment_is_valid(const struct picosystem_physics_static_segment *segment)
{
	const struct picosystem_physics_segment_config config = {
		.start = segment->start,
		.end = segment->end,
		.restitution = segment->restitution,
		.friction = segment->friction,
		.id = segment->id,
	};
	return segment_config_is_valid(&config);
}

static bool world_is_valid(const struct picosystem_physics_world *world)
{
	if ((world == NULL) || (world->max_speed_per_tick <= 0) ||
	    (world->max_speed_per_tick > PHYSICS_VELOCITY_LIMIT) ||
	    (world->body_count > PICOSYSTEM_PHYSICS_MAX_BODIES) ||
	    (world->static_segment_count > PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS) ||
	    (world->contact_count > PICOSYSTEM_PHYSICS_MAX_CONTACTS)) {
		return false;
	}

	for (uint16_t body_index = 0U; body_index < world->body_count; ++body_index) {
		if (!body_is_valid(&world->bodies[body_index], world)) {
			return false;
		}
		for (uint16_t prior = 0U; prior < body_index; ++prior) {
			if (world->bodies[prior].id == world->bodies[body_index].id) {
				return false;
			}
		}
	}

	for (uint16_t segment_index = 0U; segment_index < world->static_segment_count;
	     ++segment_index) {
		if (!segment_is_valid(&world->static_segments[segment_index])) {
			return false;
		}
		for (uint16_t prior = 0U; prior < segment_index; ++prior) {
			if (world->static_segments[prior].id ==
			    world->static_segments[segment_index].id) {
				return false;
			}
		}
	}

	return true;
}

static void clamp_body_speed(struct picosystem_physics_body *body,
			     picosystem_physics_fixed_t maximum)
{
	const uint64_t speed_squared = vector_length_squared_raw(&body->velocity_per_tick);
	const uint64_t maximum_squared = (uint64_t)((int64_t)maximum * maximum);
	if (speed_squared <= maximum_squared) {
		return;
	}

	/* A floor root can scale to a vector a few raw units above the promised limit. */
	const uint32_t speed = integer_square_root_ceiling(speed_squared);
	body->velocity_per_tick.x =
		(picosystem_physics_fixed_t)(((int64_t)body->velocity_per_tick.x * maximum) /
					     speed);
	body->velocity_per_tick.y =
		(picosystem_physics_fixed_t)(((int64_t)body->velocity_per_tick.y * maximum) /
					     speed);
}

static void clamp_body_position(struct picosystem_physics_body *body)
{
	body->center.x =
		fixed_clamp(body->center.x, -PHYSICS_POSITION_LIMIT, PHYSICS_POSITION_LIMIT);
	body->center.y =
		fixed_clamp(body->center.y, -PHYSICS_POSITION_LIMIT, PHYSICS_POSITION_LIMIT);
}

static picosystem_physics_fixed_t
contact_inverse_mass_sum(const struct picosystem_physics_world *world,
			 const struct picosystem_physics_contact *contact)
{
	picosystem_physics_fixed_t sum = world->bodies[contact->body_a_index].inverse_mass;
	if (contact->type == PICOSYSTEM_PHYSICS_CONTACT_BODY) {
		sum += world->bodies[contact->body_b_index].inverse_mass;
	}
	return sum;
}

static struct picosystem_physics_vector
contact_relative_velocity(const struct picosystem_physics_world *world,
			  const struct picosystem_physics_contact *contact)
{
	const struct picosystem_physics_vector velocity_a =
		world->bodies[contact->body_a_index].velocity_per_tick;
	if (contact->type == PICOSYSTEM_PHYSICS_CONTACT_STATIC_SEGMENT) {
		return (struct picosystem_physics_vector){
			.x = -velocity_a.x,
			.y = -velocity_a.y,
		};
	}

	const struct picosystem_physics_vector velocity_b =
		world->bodies[contact->body_b_index].velocity_per_tick;
	return (struct picosystem_physics_vector){
		.x = velocity_b.x - velocity_a.x,
		.y = velocity_b.y - velocity_a.y,
	};
}

static picosystem_physics_fixed_t contact_friction(const struct picosystem_physics_world *world,
						   const struct picosystem_physics_contact *contact)
{
	const picosystem_physics_fixed_t friction_a = world->bodies[contact->body_a_index].friction;
	if (contact->type == PICOSYSTEM_PHYSICS_CONTACT_STATIC_SEGMENT) {
		return fixed_minimum(friction_a,
				     world->static_segments[contact->segment_index].friction);
	}
	return fixed_minimum(friction_a, world->bodies[contact->body_b_index].friction);
}

static picosystem_physics_fixed_t
contact_restitution(const struct picosystem_physics_world *world,
		    const struct picosystem_physics_contact *contact)
{
	const picosystem_physics_fixed_t restitution_a =
		world->bodies[contact->body_a_index].restitution;
	if (contact->type == PICOSYSTEM_PHYSICS_CONTACT_STATIC_SEGMENT) {
		return fixed_minimum(restitution_a,
				     world->static_segments[contact->segment_index].restitution);
	}
	return fixed_minimum(restitution_a, world->bodies[contact->body_b_index].restitution);
}

static int append_contact(struct picosystem_physics_world *world,
			  const struct picosystem_physics_contact *contact)
{
	if (world->contact_count >= PICOSYSTEM_PHYSICS_MAX_CONTACTS) {
		return -EOVERFLOW;
	}

	world->contacts[world->contact_count++] = *contact;
	return 0;
}

static void initialize_contact_target(struct picosystem_physics_world *world,
				      struct picosystem_physics_contact *contact)
{
	const struct picosystem_physics_vector relative = contact_relative_velocity(world, contact);
	const picosystem_physics_fixed_t normal_velocity = vector_dot(&relative, &contact->normal);
	if (normal_velocity < -PHYSICS_BOUNCE_THRESHOLD) {
		contact->target_normal_velocity =
			-fixed_multiply(contact_restitution(world, contact), normal_velocity);
	}
}

static int generate_body_contact(struct picosystem_physics_world *world, uint8_t body_a_index,
				 uint8_t body_b_index)
{
	const struct picosystem_physics_body *const body_a = &world->bodies[body_a_index];
	const struct picosystem_physics_body *const body_b = &world->bodies[body_b_index];
	const struct picosystem_physics_vector delta = {
		.x = body_b->center.x - body_a->center.x,
		.y = body_b->center.y - body_a->center.y,
	};
	const picosystem_physics_fixed_t combined_radius = body_a->radius + body_b->radius;
	const uint64_t radius_squared = (uint64_t)((int64_t)combined_radius * combined_radius);
	if (vector_length_squared_raw(&delta) >= radius_squared) {
		return 0;
	}

	const struct picosystem_physics_vector fallback = {
		.x = (body_a->id < body_b->id) ? PICOSYSTEM_PHYSICS_FIXED_ONE
					       : -PICOSYSTEM_PHYSICS_FIXED_ONE,
	};
	struct picosystem_physics_contact contact = {
		.body_a_index = body_a_index,
		.body_b_index = body_b_index,
		.segment_index = STATIC_SEGMENT_INDEX,
		.type = PICOSYSTEM_PHYSICS_CONTACT_BODY,
	};
	const picosystem_physics_fixed_t distance =
		normalize_vector(&delta, &contact.normal, &fallback);
	contact.penetration = combined_radius - distance;
	initialize_contact_target(world, &contact);
	return append_contact(world, &contact);
}

static struct picosystem_physics_vector
closest_point_on_segment(const struct picosystem_physics_vector *point,
			 const struct picosystem_physics_static_segment *segment)
{
	const struct picosystem_physics_vector extent = {
		.x = segment->end.x - segment->start.x,
		.y = segment->end.y - segment->start.y,
	};
	const struct picosystem_physics_vector from_start = {
		.x = point->x - segment->start.x,
		.y = point->y - segment->start.y,
	};
	const int64_t projection_raw =
		((int64_t)from_start.x * extent.x) + ((int64_t)from_start.y * extent.y);
	const int64_t length_squared_raw = (int64_t)vector_length_squared_raw(&extent);
	if (projection_raw <= 0) {
		return segment->start;
	}
	if (projection_raw >= length_squared_raw) {
		return segment->end;
	}

	const int64_t reduced_projection = projection_raw / PICOSYSTEM_PHYSICS_FIXED_ONE;
	const int64_t reduced_length = length_squared_raw / PICOSYSTEM_PHYSICS_FIXED_ONE;
	const picosystem_physics_fixed_t fraction =
		(picosystem_physics_fixed_t)((reduced_projection * PICOSYSTEM_PHYSICS_FIXED_ONE) /
					     reduced_length);
	return (struct picosystem_physics_vector){
		.x = segment->start.x + fixed_multiply(extent.x, fraction),
		.y = segment->start.y + fixed_multiply(extent.y, fraction),
	};
}

static int generate_segment_contact(struct picosystem_physics_world *world, uint8_t body_index,
				    uint8_t segment_index)
{
	const struct picosystem_physics_body *const body = &world->bodies[body_index];
	const struct picosystem_physics_static_segment *const segment =
		&world->static_segments[segment_index];
	const struct picosystem_physics_vector closest =
		closest_point_on_segment(&body->center, segment);
	const struct picosystem_physics_vector body_to_segment = {
		.x = closest.x - body->center.x,
		.y = closest.y - body->center.y,
	};
	const uint64_t radius_squared = (uint64_t)((int64_t)body->radius * body->radius);
	if (vector_length_squared_raw(&body_to_segment) >= radius_squared) {
		return 0;
	}

	const struct picosystem_physics_vector segment_extent = {
		.x = segment->end.x - segment->start.x,
		.y = segment->end.y - segment->start.y,
	};
	const struct picosystem_physics_vector fallback_raw = {
		.x = -segment_extent.y,
		.y = segment_extent.x,
	};
	const struct picosystem_physics_vector unit_x = {
		.x = PICOSYSTEM_PHYSICS_FIXED_ONE,
	};
	struct picosystem_physics_vector fallback;
	(void)normalize_vector(&fallback_raw, &fallback, &unit_x);

	struct picosystem_physics_contact contact = {
		.body_a_index = body_index,
		.body_b_index = STATIC_BODY_INDEX,
		.segment_index = segment_index,
		.type = PICOSYSTEM_PHYSICS_CONTACT_STATIC_SEGMENT,
	};
	const picosystem_physics_fixed_t distance =
		normalize_vector(&body_to_segment, &contact.normal, &fallback);
	contact.penetration = body->radius - distance;
	initialize_contact_target(world, &contact);
	return append_contact(world, &contact);
}

static int build_contacts(struct picosystem_physics_world *world)
{
	world->contact_count = 0U;
	world->last_candidate_pair_count = 0U;

	for (uint8_t body_a = 0U; body_a < world->body_count; ++body_a) {
		for (uint8_t body_b = body_a + 1U; body_b < world->body_count; ++body_b) {
			++world->last_candidate_pair_count;
			const int err = generate_body_contact(world, body_a, body_b);
			if (err != 0) {
				return err;
			}
		}

		for (uint8_t segment = 0U; segment < world->static_segment_count; ++segment) {
			++world->last_candidate_pair_count;
			const int err = generate_segment_contact(world, body_a, segment);
			if (err != 0) {
				return err;
			}
		}
	}

	return 0;
}

static void apply_position_correction(struct picosystem_physics_world *world,
				      const struct picosystem_physics_contact *contact)
{
	const picosystem_physics_fixed_t depth = contact->penetration - PHYSICS_POSITION_SLOP;
	if (depth <= 0) {
		return;
	}

	const picosystem_physics_fixed_t inverse_mass_sum =
		contact_inverse_mass_sum(world, contact);
	const picosystem_physics_fixed_t correction_impulse = fixed_divide(depth, inverse_mass_sum);
	struct picosystem_physics_body *const body_a = &world->bodies[contact->body_a_index];
	const picosystem_physics_fixed_t correction_a =
		fixed_multiply(correction_impulse, body_a->inverse_mass);
	body_a->center.x -= fixed_multiply(contact->normal.x, correction_a);
	body_a->center.y -= fixed_multiply(contact->normal.y, correction_a);

	if (contact->type == PICOSYSTEM_PHYSICS_CONTACT_BODY) {
		struct picosystem_physics_body *const body_b =
			&world->bodies[contact->body_b_index];
		const picosystem_physics_fixed_t correction_b =
			fixed_multiply(correction_impulse, body_b->inverse_mass);
		body_b->center.x += fixed_multiply(contact->normal.x, correction_b);
		body_b->center.y += fixed_multiply(contact->normal.y, correction_b);
	}
}

static void apply_contact_impulse(struct picosystem_physics_world *world,
				  const struct picosystem_physics_contact *contact,
				  const struct picosystem_physics_vector *direction,
				  picosystem_physics_fixed_t impulse)
{
	struct picosystem_physics_body *const body_a = &world->bodies[contact->body_a_index];
	const picosystem_physics_fixed_t velocity_change_a =
		fixed_multiply(impulse, body_a->inverse_mass);
	body_a->velocity_per_tick.x -= fixed_multiply(direction->x, velocity_change_a);
	body_a->velocity_per_tick.y -= fixed_multiply(direction->y, velocity_change_a);

	if (contact->type == PICOSYSTEM_PHYSICS_CONTACT_BODY) {
		struct picosystem_physics_body *const body_b =
			&world->bodies[contact->body_b_index];
		const picosystem_physics_fixed_t velocity_change_b =
			fixed_multiply(impulse, body_b->inverse_mass);
		body_b->velocity_per_tick.x += fixed_multiply(direction->x, velocity_change_b);
		body_b->velocity_per_tick.y += fixed_multiply(direction->y, velocity_change_b);
	}
}

static void solve_contact_velocity(struct picosystem_physics_world *world,
				   struct picosystem_physics_contact *contact)
{
	const picosystem_physics_fixed_t inverse_mass_sum =
		contact_inverse_mass_sum(world, contact);
	struct picosystem_physics_vector relative = contact_relative_velocity(world, contact);
	const picosystem_physics_fixed_t normal_velocity = vector_dot(&relative, &contact->normal);
	const picosystem_physics_fixed_t normal_delta =
		fixed_divide(contact->target_normal_velocity - normal_velocity, inverse_mass_sum);
	const picosystem_physics_fixed_t previous_normal = contact->accumulated_normal_impulse;
	contact->accumulated_normal_impulse =
		(previous_normal + normal_delta > 0) ? previous_normal + normal_delta : 0;
	apply_contact_impulse(world, contact, &contact->normal,
			      contact->accumulated_normal_impulse - previous_normal);

	relative = contact_relative_velocity(world, contact);
	const struct picosystem_physics_vector tangent = {
		.x = -contact->normal.y,
		.y = contact->normal.x,
	};
	const picosystem_physics_fixed_t tangent_velocity = vector_dot(&relative, &tangent);
	const picosystem_physics_fixed_t tangent_delta =
		fixed_divide(-tangent_velocity, inverse_mass_sum);
	const picosystem_physics_fixed_t maximum_friction = fixed_multiply(
		contact_friction(world, contact), contact->accumulated_normal_impulse);
	const picosystem_physics_fixed_t previous_tangent = contact->accumulated_tangent_impulse;
	contact->accumulated_tangent_impulse =
		fixed_clamp(previous_tangent + tangent_delta, -maximum_friction, maximum_friction);
	apply_contact_impulse(world, contact, &tangent,
			      contact->accumulated_tangent_impulse - previous_tangent);
}

static uint32_t fnv1a_u32(uint32_t hash, uint32_t value)
{
	for (uint32_t shift = 0U; shift < 32U; shift += 8U) {
		hash ^= (value >> shift) & UINT32_C(0xff);
		hash *= FNV1A_PRIME;
	}
	return hash;
}

int picosystem_physics_world_init(struct picosystem_physics_world *world,
				  picosystem_physics_fixed_t max_speed_per_tick)
{
	if (world == NULL) {
		return -EINVAL;
	}
	if ((max_speed_per_tick <= 0) || (max_speed_per_tick > PHYSICS_VELOCITY_LIMIT)) {
		return -ERANGE;
	}

	memset(world, 0, sizeof(*world));
	world->max_speed_per_tick = max_speed_per_tick;
	return 0;
}

int picosystem_physics_world_add_circle(struct picosystem_physics_world *world,
					const struct picosystem_physics_circle_config *config)
{
	if ((world == NULL) || (config == NULL)) {
		return -EINVAL;
	}
	if (!world_is_valid(world) || !body_config_is_valid(config, world)) {
		return -ERANGE;
	}
	if (world->body_count >= PICOSYSTEM_PHYSICS_MAX_BODIES) {
		return -ENOSPC;
	}
	for (uint16_t index = 0U; index < world->body_count; ++index) {
		if (world->bodies[index].id == config->id) {
			return -EEXIST;
		}
	}

	world->bodies[world->body_count++] = (struct picosystem_physics_body){
		.center = config->center,
		.velocity_per_tick = config->velocity_per_tick,
		.radius = config->radius,
		.inverse_mass = config->inverse_mass,
		.restitution = config->restitution,
		.friction = config->friction,
		.id = config->id,
	};
	return 0;
}

int picosystem_physics_world_add_static_segment(
	struct picosystem_physics_world *world,
	const struct picosystem_physics_segment_config *config)
{
	if ((world == NULL) || (config == NULL)) {
		return -EINVAL;
	}
	if (!world_is_valid(world) || !segment_config_is_valid(config)) {
		return -ERANGE;
	}
	if (world->static_segment_count >= PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS) {
		return -ENOSPC;
	}
	for (uint16_t index = 0U; index < world->static_segment_count; ++index) {
		if (world->static_segments[index].id == config->id) {
			return -EEXIST;
		}
	}

	world->static_segments[world->static_segment_count++] =
		(struct picosystem_physics_static_segment){
			.start = config->start,
			.end = config->end,
			.restitution = config->restitution,
			.friction = config->friction,
			.id = config->id,
		};
	return 0;
}

int picosystem_physics_world_step(
	struct picosystem_physics_world *world,
	const struct picosystem_physics_vector *global_acceleration_per_tick)
{
	if ((world == NULL) || (global_acceleration_per_tick == NULL)) {
		return -EINVAL;
	}
	if (!world_is_valid(world) ||
	    !vector_is_bounded(global_acceleration_per_tick, PHYSICS_ACCELERATION_LIMIT)) {
		return -ERANGE;
	}

	for (uint16_t index = 0U; index < world->body_count; ++index) {
		struct picosystem_physics_body *const body = &world->bodies[index];
		body->velocity_per_tick.x += global_acceleration_per_tick->x;
		body->velocity_per_tick.y += global_acceleration_per_tick->y;
		clamp_body_speed(body, world->max_speed_per_tick);
		body->center.x += body->velocity_per_tick.x;
		body->center.y += body->velocity_per_tick.y;
		clamp_body_position(body);
	}

	int err = build_contacts(world);
	if (err != 0) {
		return err;
	}

	for (uint16_t index = 0U; index < world->contact_count; ++index) {
		apply_position_correction(world, &world->contacts[index]);
	}
	for (uint32_t iteration = 0U; iteration < PICOSYSTEM_PHYSICS_SOLVER_ITERATIONS;
	     ++iteration) {
		for (uint16_t index = 0U; index < world->contact_count; ++index) {
			solve_contact_velocity(world, &world->contacts[index]);
		}
	}

	for (uint16_t index = 0U; index < world->body_count; ++index) {
		clamp_body_position(&world->bodies[index]);
		clamp_body_speed(&world->bodies[index], world->max_speed_per_tick);
	}
	return 0;
}

const struct picosystem_physics_body *
picosystem_physics_world_body_at(const struct picosystem_physics_world *world, size_t index)
{
	if ((world == NULL) || (world->body_count > PICOSYSTEM_PHYSICS_MAX_BODIES) ||
	    (index >= world->body_count)) {
		return NULL;
	}
	return &world->bodies[index];
}

uint32_t picosystem_physics_world_hash(const struct picosystem_physics_world *world)
{
	if ((world == NULL) || (world->body_count > PICOSYSTEM_PHYSICS_MAX_BODIES) ||
	    (world->static_segment_count > PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS)) {
		return 0U;
	}

	uint32_t hash = fnv1a_u32(FNV1A_OFFSET_BASIS, PHYSICS_HASH_VERSION);
	hash = fnv1a_u32(hash, (uint32_t)world->max_speed_per_tick);
	hash = fnv1a_u32(hash, world->body_count);
	hash = fnv1a_u32(hash, world->static_segment_count);
	for (uint16_t index = 0U; index < world->body_count; ++index) {
		const struct picosystem_physics_body *const body = &world->bodies[index];
		hash = fnv1a_u32(hash, body->id);
		hash = fnv1a_u32(hash, (uint32_t)body->center.x);
		hash = fnv1a_u32(hash, (uint32_t)body->center.y);
		hash = fnv1a_u32(hash, (uint32_t)body->velocity_per_tick.x);
		hash = fnv1a_u32(hash, (uint32_t)body->velocity_per_tick.y);
		hash = fnv1a_u32(hash, (uint32_t)body->radius);
		hash = fnv1a_u32(hash, (uint32_t)body->inverse_mass);
		hash = fnv1a_u32(hash, (uint32_t)body->restitution);
		hash = fnv1a_u32(hash, (uint32_t)body->friction);
	}
	for (uint16_t index = 0U; index < world->static_segment_count; ++index) {
		const struct picosystem_physics_static_segment *const segment =
			&world->static_segments[index];
		hash = fnv1a_u32(hash, segment->id);
		hash = fnv1a_u32(hash, (uint32_t)segment->start.x);
		hash = fnv1a_u32(hash, (uint32_t)segment->start.y);
		hash = fnv1a_u32(hash, (uint32_t)segment->end.x);
		hash = fnv1a_u32(hash, (uint32_t)segment->end.y);
		hash = fnv1a_u32(hash, (uint32_t)segment->restitution);
		hash = fnv1a_u32(hash, (uint32_t)segment->friction);
	}
	return hash;
}
