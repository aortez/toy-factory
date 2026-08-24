/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_SCENE_RENDERER_H_
#define PICOSYSTEM_SCENE_RENDERER_H_

#include <stdbool.h>
#include <stdint.h>

#include "graphics.h"
#include "granular_world.h"
#include "physics_world.h"

#define PICOSYSTEM_SCENE_JOINT_DAMAGE_SEGMENT_COUNT 3U
#define PICOSYSTEM_SCENE_REVOLUTE_JOINT_RADIUS      3U
#define PICOSYSTEM_SCENE_CONVEYOR_PHASE_COUNT       16U
#define PICOSYSTEM_SCENE_MAX_BOX_SENSORS            1U
#define PICOSYSTEM_SCENE_JOINT_SPRING_FLAG          UINT16_C(0x8000)
#define PICOSYSTEM_SCENE_JOINT_TARGET_RADIUS_MASK   UINT16_C(0x7fff)
#define PICOSYSTEM_SCENE_MAX_SEGMENTS                                                              \
	(PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS + (2U * PICOSYSTEM_PHYSICS_MAX_PRISMATIC_JOINTS))

struct picosystem_scene_body {
	int16_t center_x;
	int16_t center_y;
	union {
		struct {
			int16_t x;
			int16_t y;
		} vertices[PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT];
		struct {
			uint8_t orientation;
			uint8_t render_style;
		} circle;
	} geometry;
	uint16_t radius;
	uint16_t id;
	uint8_t shape;
	uint8_t sleeping;
};

struct picosystem_scene_segment {
	int16_t start_x;
	int16_t start_y;
	int16_t end_x;
	int16_t end_y;
};

struct picosystem_scene_joint {
	int16_t anchor_a_x;
	int16_t anchor_a_y;
	int16_t anchor_b_x;
	int16_t anchor_b_y;
	uint16_t id;
	/* Zero selects the moving body-to-body line representation. */
	uint16_t target_radius;
};

struct picosystem_scene_box_sensor {
	struct picosystem_rect bounds;
	uint16_t id;
	uint8_t active;
};

struct picosystem_scene_rope {
	struct {
		int16_t x;
		int16_t y;
	} particles[PICOSYSTEM_PHYSICS_MAX_ROPE_PARTICLES];
	uint16_t id;
	uint8_t particle_count;
};

struct picosystem_scene_grain {
	uint8_t x;
	uint8_t y;
};

struct picosystem_scene_rigid_payload {
	uint32_t conveyor_forward_segment_mask;
	uint32_t conveyor_reverse_segment_mask;
	struct picosystem_scene_body bodies[PICOSYSTEM_PHYSICS_MAX_BODIES];
	struct picosystem_scene_segment static_segments[PICOSYSTEM_SCENE_MAX_SEGMENTS];
	struct picosystem_scene_joint distance_joints[PICOSYSTEM_PHYSICS_MAX_DISTANCE_JOINTS];
	struct picosystem_scene_joint revolute_joints[PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS];
	struct picosystem_scene_box_sensor box_sensors[PICOSYSTEM_SCENE_MAX_BOX_SENSORS];
	struct picosystem_scene_rope ropes[PICOSYSTEM_PHYSICS_MAX_ROPES];
};

struct picosystem_scene_granular_payload {
	struct picosystem_scene_segment boundaries[PICOSYSTEM_GRANULAR_MAX_BOUNDARIES];
	struct picosystem_scene_grain grains[PICOSYSTEM_GRANULAR_MAX_PARTICLES];
};

/* Immutable, self-contained input copied to the auxiliary core before rasterization. */
struct picosystem_scene_snapshot {
	int64_t published_uptime_ticks;
	uint32_t sequence;
	uint32_t logic_tick_count;
	uint32_t redraw_request_sequence;
	uint32_t sensor_entry_count;
	uint16_t granular_particle_count;
	uint16_t granular_lower_particle_count;
	uint8_t scene_id;
	uint8_t body_count;
	uint8_t static_segment_count;
	uint8_t distance_joint_count;
	uint8_t revolute_joint_count;
	uint8_t box_sensor_count;
	uint8_t rope_count;
	uint8_t granular_particle_radius;
	/* scene_id tags the only payload valid for this immutable snapshot. */
	union {
		struct picosystem_scene_rigid_payload rigid;
		struct picosystem_scene_granular_payload granular;
	} payload;
};

enum picosystem_scene_render_stage {
	PICOSYSTEM_SCENE_RENDER_STAGE_IDLE,
	PICOSYSTEM_SCENE_RENDER_STAGE_VALIDATE,
	PICOSYSTEM_SCENE_RENDER_STAGE_CLEAR,
	PICOSYSTEM_SCENE_RENDER_STAGE_BACKGROUND,
	PICOSYSTEM_SCENE_RENDER_STAGE_GRANULES,
	PICOSYSTEM_SCENE_RENDER_STAGE_BOX_SENSORS,
	PICOSYSTEM_SCENE_RENDER_STAGE_STATIC_SEGMENTS,
	PICOSYSTEM_SCENE_RENDER_STAGE_DISTANCE_JOINTS,
	PICOSYSTEM_SCENE_RENDER_STAGE_ROPES,
	PICOSYSTEM_SCENE_RENDER_STAGE_BODIES,
	PICOSYSTEM_SCENE_RENDER_STAGE_REVOLUTE_JOINTS,
	PICOSYSTEM_SCENE_RENDER_STAGE_HEADER,
	PICOSYSTEM_SCENE_RENDER_STAGE_COMPLETE,
};

enum picosystem_scene_render_primitive {
	PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE,
	PICOSYSTEM_SCENE_RENDER_PRIMITIVE_BOUNDS,
	PICOSYSTEM_SCENE_RENDER_PRIMITIVE_FILL_0,
	PICOSYSTEM_SCENE_RENDER_PRIMITIVE_FILL_1,
	PICOSYSTEM_SCENE_RENDER_PRIMITIVE_OUTLINE,
	PICOSYSTEM_SCENE_RENDER_PRIMITIVE_FACE,
	PICOSYSTEM_SCENE_RENDER_PRIMITIVE_HIGHLIGHT,
};

struct picosystem_scene_render_progress {
	volatile uint32_t stage;
	volatile uint32_t item_index;
	volatile uint32_t primitive;
};

bool picosystem_scene_rectangles_intersect(const struct picosystem_rect *left,
					   const struct picosystem_rect *right);
struct picosystem_rect picosystem_scene_body_bounds(const struct picosystem_scene_body *body);
struct picosystem_rect
picosystem_scene_segment_bounds(const struct picosystem_scene_segment *segment);
struct picosystem_rect
picosystem_scene_conveyor_bounds(const struct picosystem_scene_segment *segment);
struct picosystem_rect picosystem_scene_joint_bounds(const struct picosystem_scene_joint *joint);
struct picosystem_rect
picosystem_scene_revolute_joint_bounds(const struct picosystem_scene_joint *joint);
struct picosystem_rect picosystem_scene_rope_bounds(const struct picosystem_scene_rope *rope);
struct picosystem_rect
picosystem_scene_joint_segment_bounds(const struct picosystem_scene_joint *joint,
				      uint8_t segment_index);

/* These functions only rasterize into the framebuffer; they never touch the display driver. */
int picosystem_scene_render_full(const struct picosystem_scene_snapshot *snapshot);
int picosystem_scene_render_full_observed(const struct picosystem_scene_snapshot *snapshot,
					  struct picosystem_scene_render_progress *progress);
int picosystem_scene_render_region(const struct picosystem_scene_snapshot *snapshot,
				   const struct picosystem_rect *region);
int picosystem_scene_render_region_observed(const struct picosystem_scene_snapshot *snapshot,
					    const struct picosystem_rect *region,
					    struct picosystem_scene_render_progress *progress);

const char *picosystem_scene_render_stage_name(enum picosystem_scene_render_stage stage);
const char *
picosystem_scene_render_primitive_name(enum picosystem_scene_render_primitive primitive);

#endif /* PICOSYSTEM_SCENE_RENDERER_H_ */
