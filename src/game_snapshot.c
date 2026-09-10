/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "game_snapshot.h"

#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "garden_light.h"
#include "portable_util.h"

#define JOINT_PIXEL_QUANTUM 4

static int16_t fixed_to_pixel(int32_t value)
{
	return (int16_t)(value / PICOSYSTEM_GAME_FIXED_ONE);
}

static int32_t fixed_multiply(int32_t left, int32_t right)
{
	return (int32_t)(((int64_t)left * right) / PICOSYSTEM_GAME_FIXED_ONE);
}

static int16_t quantize_joint_pixel(int16_t value)
{
	const int32_t adjusted = (value >= 0) ? (int32_t)value + (JOINT_PIXEL_QUANTUM / 2)
					      : (int32_t)value - (JOINT_PIXEL_QUANTUM / 2);
	return (int16_t)((adjusted / JOINT_PIXEL_QUANTUM) * JOINT_PIXEL_QUANTUM);
}

static int append_prismatic_guides(const struct picosystem_game_world *world,
				   struct picosystem_scene_snapshot *snapshot)
{
	struct picosystem_scene_rigid_payload *const rigid = &snapshot->payload.rigid;

	for (uint16_t index = 0U; index < world->physics.prismatic_joint_count; ++index) {
		const struct picosystem_physics_prismatic_joint *const joint =
			&world->physics.prismatic_joints[index];
		if ((joint->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) ||
		    (joint->limit_enabled == 0U)) {
			continue;
		}
		if ((snapshot->static_segment_count + 2U) >
		    TOY_FACTORY_ARRAY_SIZE(rigid->static_segments)) {
			return -ENOSPC;
		}

		const struct picosystem_physics_body *const body =
			&world->physics.bodies[joint->body_a_index];
		int32_t guide_offset = body->radius;
		if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_BOX) {
			guide_offset = TOY_FACTORY_MAX(body->half_extent.x, body->half_extent.y);
		} else if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_CAPSULE) {
			guide_offset = body->half_extent.x + body->radius;
		}
		guide_offset += PICOSYSTEM_PHYSICS_FIXED_FROM_INT(4);
		const int32_t lower = joint->reference_translation + joint->lower_translation;
		const int32_t upper = joint->reference_translation + joint->upper_translation;
		const struct picosystem_physics_vector perpendicular = {
			.x = -joint->axis_b.y,
			.y = joint->axis_b.x,
		};
		const struct picosystem_physics_vector lower_center = {
			.x = joint->anchor_b.x + fixed_multiply(joint->axis_b.x, lower),
			.y = joint->anchor_b.y + fixed_multiply(joint->axis_b.y, lower),
		};
		const struct picosystem_physics_vector upper_center = {
			.x = joint->anchor_b.x + fixed_multiply(joint->axis_b.x, upper),
			.y = joint->anchor_b.y + fixed_multiply(joint->axis_b.y, upper),
		};
		const struct picosystem_physics_vector offset = {
			.x = fixed_multiply(perpendicular.x, guide_offset),
			.y = fixed_multiply(perpendicular.y, guide_offset),
		};

		rigid->static_segments[snapshot->static_segment_count++] =
			(struct picosystem_scene_segment){
				.start_x = fixed_to_pixel(lower_center.x + offset.x),
				.start_y = fixed_to_pixel(lower_center.y + offset.y),
				.end_x = fixed_to_pixel(upper_center.x + offset.x),
				.end_y = fixed_to_pixel(upper_center.y + offset.y),
			};
		rigid->static_segments[snapshot->static_segment_count++] =
			(struct picosystem_scene_segment){
				.start_x = fixed_to_pixel(lower_center.x - offset.x),
				.start_y = fixed_to_pixel(lower_center.y - offset.y),
				.end_x = fixed_to_pixel(upper_center.x - offset.x),
				.end_y = fixed_to_pixel(upper_center.y - offset.y),
			};
	}
	return 0;
}

int picosystem_game_snapshot_build(const struct picosystem_game_world *world, uint32_t sequence,
				   uint32_t redraw_request_sequence, int64_t published_uptime_ticks,
				   struct picosystem_scene_snapshot *snapshot)
{
	if ((world == NULL) || (snapshot == NULL)) {
		return -EINVAL;
	}

	*snapshot = (struct picosystem_scene_snapshot){
		.published_uptime_ticks = published_uptime_ticks,
		.sequence = sequence,
		.logic_tick_count = world->logic_tick_count,
		.redraw_request_sequence = redraw_request_sequence,
		.sensor_entry_count = world->sensor_entry_count,
		.scene_id = world->scene_id,
	};
	if (world->scene_id == PICOSYSTEM_GAME_SCENE_HOURGLASS) {
		struct picosystem_scene_granular_payload *const granular =
			&snapshot->payload.granular;
		if ((world->granular.boundary_count >
		     TOY_FACTORY_ARRAY_SIZE(granular->boundaries)) ||
		    (world->granular.particle_count > TOY_FACTORY_ARRAY_SIZE(granular->grains))) {
			return -ENOSPC;
		}
		snapshot->static_segment_count = (uint8_t)world->granular.boundary_count;
		snapshot->granular_particle_count = world->granular.particle_count;
		snapshot->granular_particle_radius =
			(uint8_t)fixed_to_pixel(world->granular.particle_radius);
		snapshot->granular_lower_particle_count =
			picosystem_granular_world_lower_particle_count(&world->granular);
		for (uint16_t index = 0U; index < snapshot->static_segment_count; ++index) {
			const struct picosystem_granular_boundary *const boundary =
				&world->granular.boundaries[index];
			granular->boundaries[index] = (struct picosystem_scene_segment){
				.start_x = fixed_to_pixel(boundary->start.x),
				.start_y = fixed_to_pixel(boundary->start.y),
				.end_x = fixed_to_pixel(boundary->end.x),
				.end_y = fixed_to_pixel(boundary->end.y),
			};
		}
		for (uint16_t index = 0U; index < snapshot->granular_particle_count; ++index) {
			const struct picosystem_granular_particle *const particle =
				&world->granular.particles[index];
			const int16_t particle_x = fixed_to_pixel(particle->position.x);
			const int16_t particle_y = fixed_to_pixel(particle->position.y);
			if ((particle_x < 0) || (particle_x >= PICOSYSTEM_GRAPHICS_WIDTH) ||
			    (particle_y < 0) || (particle_y >= PICOSYSTEM_GRAPHICS_HEIGHT)) {
				return -ERANGE;
			}
			granular->grains[index] = (struct picosystem_scene_grain){
				.x = (uint8_t)particle_x,
				.y = (uint8_t)particle_y,
			};
		}
		return 0;
	}
	if (world->scene_id == PICOSYSTEM_GAME_SCENE_GARDEN) {
		const struct picosystem_garden_world *const garden_world = &world->garden;
		struct picosystem_scene_garden_payload *const garden = &snapshot->payload.garden;
		if ((garden_world->node_count > TOY_FACTORY_ARRAY_SIZE(garden->nodes)) ||
		    (garden_world->plant_count > PICOSYSTEM_GARDEN_MAX_PLANTS)) {
			return -ENOSPC;
		}
		garden->node_count = garden_world->node_count;
		garden->moisture_total = garden_world->moisture_total;
		garden->plant_count = garden_world->plant_count;
		garden->cursor_column = garden_world->cursor_column;
		garden->cursor_row = garden_world->cursor_row;
		garden->selected_tool = garden_world->selected_tool;
		garden->auto_target_column = garden_world->auto_target_column;
		garden->auto_target_row = garden_world->auto_target_row;
		garden->auto_target_tool = garden_world->auto_target_tool;
		garden->auto_gardener_enabled = garden_world->auto_gardener_enabled ? 1U : 0U;
		garden->auto_target_valid = garden_world->auto_target_valid ? 1U : 0U;
		const struct picosystem_garden_sun sun =
			picosystem_garden_sun_at(garden_world->ecology_tick_count);
		garden->sun_phase = sun.phase;
		garden->sun_strength = sun.strength;
		garden->sun_ray_step_x_q4 = sun.ray_step_x_q4;
		memcpy(garden->moisture, garden_world->moisture, sizeof(garden->moisture));
		for (uint16_t index = 0U; index < garden->node_count; ++index) {
			const struct picosystem_garden_node *const source =
				&garden_world->nodes[index];
			if ((source->plant_index >= garden_world->plant_count) ||
			    (garden_world->plants[source->plant_index].species_id >=
			     PICOSYSTEM_GARDEN_SPECIES_COUNT)) {
				return -ERANGE;
			}
			uint8_t parent_distance = 0U;
			if (source->parent_index != PICOSYSTEM_GARDEN_NODE_NONE) {
				if (source->parent_index >= index) {
					return -ERANGE;
				}
				const uint16_t distance = (uint16_t)(index - source->parent_index);
				if (distance > UINT8_MAX) {
					return -ERANGE;
				}
				parent_distance = (uint8_t)distance;
			}
			const struct picosystem_garden_plant *const plant =
				&garden_world->plants[source->plant_index];
			uint8_t style =
				plant->species_id & PICOSYSTEM_SCENE_GARDEN_STYLE_SPECIES_MASK;
			if (source->kind == PICOSYSTEM_GARDEN_NODE_ROOT) {
				style |= PICOSYSTEM_SCENE_GARDEN_STYLE_ROOT;
			}
			if ((source->flags & PICOSYSTEM_GARDEN_NODE_LEAF) != 0U) {
				style |= PICOSYSTEM_SCENE_GARDEN_STYLE_LEAF;
			}
			if ((source->flags & PICOSYSTEM_GARDEN_NODE_FLOWER) != 0U) {
				style |= PICOSYSTEM_SCENE_GARDEN_STYLE_FLOWER;
			}
			if ((source->flags & PICOSYSTEM_GARDEN_NODE_PRUNED) != 0U) {
				style |= PICOSYSTEM_SCENE_GARDEN_STYLE_PRUNED;
			}
			if (plant->stress > 0U) {
				style |= PICOSYSTEM_SCENE_GARDEN_STYLE_STRESSED;
			}
			if ((plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) != 0U) {
				style |= PICOSYSTEM_SCENE_GARDEN_STYLE_DEAD;
			}
			garden->nodes[index] = (struct picosystem_scene_garden_node){
				.x = source->x,
				.y = source->y,
				.parent_distance = parent_distance,
				.growth_progress = source->growth_progress,
				.style = style,
			};
		}
		return 0;
	}
	struct picosystem_scene_rigid_payload *const rigid = &snapshot->payload.rigid;
	if ((world->physics.body_count > TOY_FACTORY_ARRAY_SIZE(rigid->bodies)) ||
	    (world->physics.static_segment_count >
	     TOY_FACTORY_ARRAY_SIZE(rigid->static_segments)) ||
	    (world->physics.distance_joint_count >
	     TOY_FACTORY_ARRAY_SIZE(rigid->distance_joints)) ||
	    (world->physics.revolute_joint_count >
	     TOY_FACTORY_ARRAY_SIZE(rigid->revolute_joints)) ||
	    (world->physics.box_sensor_count > TOY_FACTORY_ARRAY_SIZE(rigid->box_sensors)) ||
	    (world->physics.rope_count > TOY_FACTORY_ARRAY_SIZE(rigid->ropes))) {
		return -ENOSPC;
	}
	snapshot->body_count = (uint8_t)world->physics.body_count;
	snapshot->static_segment_count = (uint8_t)world->physics.static_segment_count;
	snapshot->distance_joint_count = (uint8_t)world->physics.distance_joint_count;
	snapshot->revolute_joint_count = (uint8_t)world->physics.revolute_joint_count;
	snapshot->box_sensor_count = (uint8_t)world->physics.box_sensor_count;
	snapshot->rope_count = (uint8_t)world->physics.rope_count;
	for (uint16_t index = 0U; index < snapshot->body_count; ++index) {
		const struct picosystem_physics_body *const body = &world->physics.bodies[index];
		rigid->bodies[index] = (struct picosystem_scene_body){
			.center_x = fixed_to_pixel(body->center.x),
			.center_y = fixed_to_pixel(body->center.y),
			.radius = (uint16_t)fixed_to_pixel(body->radius),
			.id = body->id,
			.shape = body->shape,
			.sleeping =
				picosystem_physics_world_body_is_sleeping(&world->physics, index),
		};
		rigid->bodies[index].geometry.circle.orientation =
			(uint8_t)(body->angle_turns >> 26U);
		rigid->bodies[index].geometry.circle.render_style =
			(uint8_t)picosystem_game_world_body_render_style(world, index);
		if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_BOX) {
			struct picosystem_physics_vector
				vertices[PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT];
			const int err = picosystem_physics_body_box_vertices(body, vertices);
			if (err != 0) {
				return err;
			}
			for (size_t vertex = 0U; vertex < PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT;
			     ++vertex) {
				rigid->bodies[index].geometry.vertices[vertex].x =
					fixed_to_pixel(vertices[vertex].x);
				rigid->bodies[index].geometry.vertices[vertex].y =
					fixed_to_pixel(vertices[vertex].y);
			}
		} else if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_CAPSULE) {
			struct picosystem_physics_vector
				vertices[PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT];
			const int err = picosystem_physics_body_capsule_vertices(body, vertices);
			if (err != 0) {
				return err;
			}
			for (size_t vertex = 0U; vertex < PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT;
			     ++vertex) {
				rigid->bodies[index].geometry.vertices[vertex].x =
					fixed_to_pixel(vertices[vertex].x);
				rigid->bodies[index].geometry.vertices[vertex].y =
					fixed_to_pixel(vertices[vertex].y);
			}
		} else if (body->shape != PICOSYSTEM_PHYSICS_SHAPE_CIRCLE) {
			return -ERANGE;
		}
	}
	for (uint16_t index = 0U; index < world->physics.static_segment_count; ++index) {
		const struct picosystem_physics_static_segment *const segment =
			&world->physics.static_segments[index];
		rigid->static_segments[index] = (struct picosystem_scene_segment){
			.start_x = fixed_to_pixel(segment->start.x),
			.start_y = fixed_to_pixel(segment->start.y),
			.end_x = fixed_to_pixel(segment->end.x),
			.end_y = fixed_to_pixel(segment->end.y),
		};
		const uint32_t segment_mask = UINT32_C(1) << index;
		if (segment->surface_speed_per_tick > 0) {
			rigid->conveyor_forward_segment_mask |= segment_mask;
		} else if (segment->surface_speed_per_tick < 0) {
			rigid->conveyor_reverse_segment_mask |= segment_mask;
		}
	}
	for (uint16_t index = 0U; index < snapshot->box_sensor_count; ++index) {
		const struct picosystem_physics_box_sensor *const sensor =
			&world->physics.box_sensors[index];
		const int16_t left = fixed_to_pixel(sensor->center.x - sensor->half_extent.x);
		const int16_t top = fixed_to_pixel(sensor->center.y - sensor->half_extent.y);
		const int16_t right = fixed_to_pixel(sensor->center.x + sensor->half_extent.x);
		const int16_t bottom = fixed_to_pixel(sensor->center.y + sensor->half_extent.y);
		if ((left < 0) || (top < 0) || (right < left) || (bottom < top) ||
		    (right >= PICOSYSTEM_GRAPHICS_WIDTH) ||
		    (bottom >= PICOSYSTEM_GRAPHICS_HEIGHT)) {
			return -ERANGE;
		}
		bool active = false;
		const uint8_t sensor_mask = (uint8_t)(UINT8_C(1) << index);
		for (uint16_t body = 0U; body < world->physics.body_count; ++body) {
			active |= (world->physics.active_sensor_contact_masks[body] &
				   sensor_mask) != 0U;
		}
		rigid->box_sensors[index] = (struct picosystem_scene_box_sensor){
			.bounds =
				{
					.x = (uint16_t)left,
					.y = (uint16_t)top,
					.width = (uint16_t)(right - left + 1),
					.height = (uint16_t)(bottom - top + 1),
				},
			.id = sensor->id,
			.active = active ? 1U : 0U,
		};
	}
	for (uint16_t index = 0U; index < snapshot->rope_count; ++index) {
		const struct picosystem_physics_rope *const rope = &world->physics.ropes[index];
		if (rope->particle_count > PICOSYSTEM_PHYSICS_MAX_ROPE_PARTICLES) {
			return -ERANGE;
		}
		rigid->ropes[index].id = rope->id;
		rigid->ropes[index].particle_count = rope->particle_count;
		for (uint8_t particle = 0U; particle < rope->particle_count; ++particle) {
			rigid->ropes[index].particles[particle].x =
				fixed_to_pixel(rope->particles[particle].position.x);
			rigid->ropes[index].particles[particle].y =
				fixed_to_pixel(rope->particles[particle].position.y);
		}
	}
	int err = append_prismatic_guides(world, snapshot);
	if (err != 0) {
		return err;
	}
	for (uint16_t index = 0U; index < snapshot->distance_joint_count; ++index) {
		struct picosystem_physics_vector anchor_a;
		struct picosystem_physics_vector anchor_b;
		err = picosystem_physics_world_distance_joint_endpoints(&world->physics, index,
									&anchor_a, &anchor_b);
		if (err != 0) {
			return err;
		}
		const struct picosystem_physics_distance_joint *const joint =
			&world->physics.distance_joints[index];
		const bool world_anchored = joint->body_b_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID;
		uint16_t target_radius =
			world_anchored ? (uint16_t)fixed_to_pixel(joint->target_distance) : 0U;
		if (joint->spring_enabled != 0U) {
			target_radius |= PICOSYSTEM_SCENE_JOINT_SPRING_FLAG;
		}
		int16_t anchor_a_x = fixed_to_pixel(anchor_a.x);
		int16_t anchor_a_y = fixed_to_pixel(anchor_a.y);
		int16_t anchor_b_x = fixed_to_pixel(anchor_b.x);
		int16_t anchor_b_y = fixed_to_pixel(anchor_b.y);
		if (!world_anchored) {
			anchor_a_x = quantize_joint_pixel(anchor_a_x);
			anchor_a_y = quantize_joint_pixel(anchor_a_y);
			anchor_b_x = quantize_joint_pixel(anchor_b_x);
			anchor_b_y = quantize_joint_pixel(anchor_b_y);
		}
		rigid->distance_joints[index] = (struct picosystem_scene_joint){
			.anchor_a_x = anchor_a_x,
			.anchor_a_y = anchor_a_y,
			.anchor_b_x = anchor_b_x,
			.anchor_b_y = anchor_b_y,
			.id = joint->id,
			.target_radius = target_radius,
		};
	}
	for (uint16_t index = 0U; index < snapshot->revolute_joint_count; ++index) {
		struct picosystem_physics_vector anchor_a;
		struct picosystem_physics_vector anchor_b;
		err = picosystem_physics_world_revolute_joint_anchors(&world->physics, index,
								      &anchor_a, &anchor_b);
		if (err != 0) {
			return err;
		}
		const struct picosystem_physics_revolute_joint *const joint =
			&world->physics.revolute_joints[index];
		rigid->revolute_joints[index] = (struct picosystem_scene_joint){
			.anchor_a_x = fixed_to_pixel(anchor_a.x),
			.anchor_a_y = fixed_to_pixel(anchor_a.y),
			.anchor_b_x = fixed_to_pixel(anchor_b.x),
			.anchor_b_y = fixed_to_pixel(anchor_b.y),
			.id = joint->id,
		};
	}
	return 0;
}
