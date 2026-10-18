/* SPDX-License-Identifier: Apache-2.0 */
#include "research_session.h"
#include "research_models.h"
#include "garden_leaf_owned.h"
#include "garden_renewal_model.h"
#include "garden_evaluation.h"
#include "garden_landing_ledger.h"
#include "game_snapshot.h"
#include "graphics_raster.h"

#include <errno.h>
#include <inttypes.h>
#include <stdlib.h>
#include <string.h>

#define GROWTH_SHA "f2dc989380339614dc512f64f11f2bf03f7079c465c4c9bd18895044ec3e1567"

_Static_assert(RESEARCH_STOP_TICK == TOY_FACTORY_MAINTENANCE_RUN_STOP, "Fixed research horizon");
_Static_assert(sizeof(research_model_bytes[0]) == TOY_FACTORY_LEAF_NEURAL_FILE_SIZE, "Model size");

struct research_session {
	struct research_options options;
	struct toy_factory_leaf_owned *owner;
	struct toy_factory_leaf_family snapshot;
	struct toy_factory_garden_lifetimes lifetimes;
	struct toy_factory_garden_landing_ledger history;
	int failure;
};

static const struct picosystem_garden_world *world(const struct research_session *session)
{
	return &session->snapshot.candidate.base.growth.base.world;
}

const char *research_model_name(uint8_t model)
{
	return model < 3U ? research_model_names[model] : NULL;
}

const char *research_layout_name(uint8_t layout)
{
	return layout < TOY_FACTORY_GARDEN_RAINFED_SCENARIO_COUNT
		       ? toy_factory_garden_rainfed_scenarios[layout].name
		       : NULL;
}

static bool known_seed(uint32_t seed)
{
	static const uint32_t seeds[] = {UINT32_C(0x58d7d6ca), UINT32_C(0x9a903368),
					 UINT32_C(0x6b9c1a3e), UINT32_C(0x59818bc3),
					 UINT32_C(0x98a89374)};
	for (size_t index = 0U; index < sizeof(seeds) / sizeof(seeds[0]); ++index) {
		if (seed == seeds[index]) {
			return true;
		}
	}
	return false;
}

static int births(struct research_session *session)
{
	const struct picosystem_garden_world *const state = world(session);
	for (uint8_t i = 0U; i < state->plant_count; ++i) {
		const struct picosystem_garden_plant *const plant = &state->plants[i];
		if ((plant->lineage_id == 0U) ||
		    (plant->lineage_id > TOY_FACTORY_GARDEN_EVALUATION_MAX_TRACKED_LINEAGES)) {
			return -ENOSPC;
		}
		if (plant->lineage_id > session->lifetimes.count) {
			const int err = toy_factory_garden_lifetimes_birth(
				&session->lifetimes, plant->lineage_id, plant->parent_lineage_id,
				plant->species_id, state->logic_tick_count);
			if (err != 0) {
				return err;
			}
		}
		if (((plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) != 0U) !=
		    (session->lifetimes.records[plant->lineage_id].death_cause !=
		     TOY_FACTORY_GARDEN_LIFETIME_CAUSES)) {
			return -EFAULT;
		}
	}
	return session->lifetimes.count == state->lineage_sequence ? 0 : -EFAULT;
}

int research_session_open(const struct research_options *options, struct research_session **out)
{
	if ((options == NULL) || (out == NULL) || (research_model_name(options->model) == NULL) ||
	    (research_layout_name(options->layout) == NULL) || !known_seed(options->seed)) {
		return -EINVAL;
	}
	const struct toy_factory_garden_evaluation_scenario *const scenario =
		&toy_factory_garden_rainfed_scenarios[options->layout];
	if ((options->founder == 0U) || (options->founder > scenario->plant_count)) {
		return -EINVAL;
	}
	struct research_session *const session = calloc(1U, sizeof(*session));
	if (session == NULL) {
		return -ENOMEM;
	}
	session->options = *options;
	struct toy_factory_garden_landing_model growth;
	struct toy_factory_leaf_neural_model leaf;
	int err = toy_factory_garden_landing_model_decode(
		toy_factory_renewal_model_file, sizeof(toy_factory_renewal_model_file), &growth);
	if (err == 0) {
		err = toy_factory_leaf_neural_decode(research_model_bytes[options->model],
						     sizeof(research_model_bytes[0]), &leaf);
	}
	struct picosystem_garden_world initial;
	if (err == 0) {
		err = toy_factory_garden_evaluation_reset(&initial, scenario, options->seed);
	}
	if (err == 0) {
		err = picosystem_garden_world_set_climate(&initial,
							  PICOSYSTEM_GARDEN_CLIMATE_SEASONAL);
	}
	if (err == 0) {
		err = toy_factory_leaf_family_init(&initial, &growth, &leaf, options->founder,
						   TOY_FACTORY_MAINTENANCE_SELECTIVE,
						   &session->snapshot);
	}
	if (err == 0) {
		err = toy_factory_leaf_owned_open(&session->snapshot, &session->owner);
	}
	if (err == 0) {
		err = toy_factory_garden_lifetimes_reset(&session->lifetimes);
	}
	if (err == 0) {
		err = births(session);
	}
	if (err == 0) {
		err = toy_factory_garden_landing_ledger_reset(&session->history, world(session),
							      &session->lifetimes);
	}
	if (err != 0) {
		research_session_close(session);
		return err;
	}
	*out = session;
	return 0;
}

void research_session_close(struct research_session *session)
{
	if (session != NULL) {
		toy_factory_leaf_owned_close(session->owner);
		free(session);
	}
}

int research_session_reset(struct research_session **session)
{
	if ((session == NULL) || (*session == NULL)) {
		return -EINVAL;
	}
	struct research_session *fresh = NULL;
	const int err = research_session_open(&(*session)->options, &fresh);
	if (err == 0) {
		research_session_close(*session);
		*session = fresh;
	}
	return err;
}

static int step_once(struct research_session *session)
{
	const uint32_t tick = world(session)->logic_tick_count + 1U;
	struct picosystem_garden_death_audit deaths;
	struct picosystem_garden_seed_audit seeds;
	struct picosystem_garden_resource_audit resources;
	int err = toy_factory_leaf_owned_step(session->owner, &deaths, &seeds, &resources, NULL);
	if (err == 0) {
		err = toy_factory_leaf_owned_snapshot(session->owner, &session->snapshot);
	}
	if (err != 0) {
		return err;
	}
	const bool ecology = tick % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR == 0U;
	if ((world(session)->logic_tick_count != tick) || (deaths.ecology_step != ecology) ||
	    (seeds.ecology_step != ecology)) {
		return -EFAULT;
	}
	for (uint8_t i = 0U; (err == 0) && (i < deaths.count); ++i) {
		err = toy_factory_garden_lifetimes_death(&session->lifetimes,
							 deaths.events[i].lineage_id, tick,
							 deaths.events[i].flags);
	}
	if ((err == 0) && ecology) {
		err = births(session);
		if (err == 0) {
			err = toy_factory_garden_landing_ledger_step(
				&session->history, world(session), &session->lifetimes, &seeds);
		}
	}
	return err;
}

int research_session_step(struct research_session *session, uint32_t ticks)
{
	if (session == NULL) {
		return -EINVAL;
	}
	if (session->failure != 0) {
		return session->failure;
	}
	if (ticks > RESEARCH_STOP_TICK - world(session)->logic_tick_count) {
		return -ERANGE;
	}
	for (uint32_t i = 0U; i < ticks; ++i) {
		const int err = step_once(session);
		if (err != 0) {
			session->failure = err;
			return err;
		}
	}
	return 0;
}

int research_session_status(const struct research_session *session, struct research_status *out)
{
	if ((session == NULL) || (out == NULL)) {
		return -EINVAL;
	}
	if (session->failure != 0) {
		return session->failure;
	}
	const struct picosystem_garden_world *const state = world(session);
	struct research_status result = {.tick = state->logic_tick_count};
	const uint8_t *const roots = session->snapshot.owners.root;
	for (uint8_t i = 0U; i < state->plant_count; ++i) {
		const struct picosystem_garden_plant *const plant = &state->plants[i];
		if ((roots[plant->lineage_id] == session->options.founder) &&
		    ((plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) == 0U)) {
			++result.living;
		}
	}
	for (uint8_t i = 0U; i < state->seed_count; ++i) {
		if (roots[state->seeds[i].parent_lineage_id] == session->options.founder) {
			++result.pending;
		}
	}
	*out = result;
	return 0;
}

int research_session_encode(const struct research_session *session, uint8_t *out, size_t capacity,
			    size_t *size)
{
	if (session == NULL) {
		return -EINVAL;
	}
	if (session->failure != 0) {
		return session->failure;
	}
	return toy_factory_leaf_family_encode(&session->snapshot, out, capacity, size);
}

int research_session_render(struct research_session *session, uint8_t *out, size_t capacity,
			    uint32_t *crc)
{
	if ((session == NULL) || (out == NULL) || (crc == NULL) ||
	    (capacity < RESEARCH_FRAME_BYTES)) {
		return -EINVAL;
	}
	uint8_t before[TOY_FACTORY_LEAF_FAMILY_MAX_STATE_BYTES];
	uint8_t after[TOY_FACTORY_LEAF_FAMILY_MAX_STATE_BYTES];
	size_t before_size, after_size;
	int err = research_session_encode(session, before, sizeof(before), &before_size);
	if (err != 0) {
		return err;
	}
	const struct picosystem_game_world render_world = {
		.garden = *world(session),
		.logic_tick_count = world(session)->logic_tick_count,
		.scene_id = PICOSYSTEM_GAME_SCENE_GARDEN};
	struct picosystem_scene_snapshot snapshot;
	err = picosystem_game_snapshot_build(&render_world, 1U, 0U,
					     (int64_t)render_world.logic_tick_count, &snapshot);
	if (err == 0) {
		err = picosystem_scene_render_full(&snapshot);
	}
	if (err == 0) {
		err = research_session_encode(session, after, sizeof(after), &after_size);
	}
	if ((err == 0) &&
	    ((after_size != before_size) || (memcmp(before, after, before_size) != 0) ||
	     (picosystem_graphics_raster_byte_count() != RESEARCH_FRAME_BYTES))) {
		err = -EFAULT;
	}
	if (err == 0) {
		err = toy_factory_maintenance_state_encode(
			&render_world.garden, &session->snapshot.candidate.base.growth.base.cache,
			after, sizeof(after), &after_size);
		if ((err == 0) &&
		    ((after_size != TOY_FACTORY_MAINTENANCE_STATE_BYTES) ||
		     (memcmp(before + before_size - after_size, after, after_size) != 0))) {
			err = -EFAULT;
		}
	}
	if (err != 0) {
		session->failure = err;
		return err;
	}
	memcpy(out, picosystem_graphics_raster_bytes(), RESEARCH_FRAME_BYTES);
	*crc = picosystem_graphics_raster_crc32();
	return 0;
}

static void print_hex(FILE *stream, const uint8_t *data, size_t size)
{
	for (size_t i = 0U; i < size; ++i) {
		fprintf(stream, "%02x", (unsigned int)data[i]);
	}
}

int research_session_write_json(const struct research_session *session, FILE *stream,
				const uint32_t *crc)
{
	if ((session == NULL) || (stream == NULL)) {
		return -EINVAL;
	}
	uint8_t state[TOY_FACTORY_LEAF_FAMILY_MAX_STATE_BYTES];
	size_t size;
	int err = research_session_encode(session, state, sizeof(state), &size);
	if (err != 0) {
		return err;
	}
	fprintf(stream,
		"{\"schema\":\"garden-leaf-family-replay-v1\",\"controller_assignment\":"
		"\"founder-family\",\"objective\":null,\"seed\":\"%08" PRIx32
		"\",\"scenario\":\"%s\","
		"\"climate\":\"seasonal\",\"gardener\":false,\"ticks\":%" PRIu32
		",\"growth_model_sha256\":\"" GROWTH_SHA "\",\"leaf_model_hex\":\"",
		session->options.seed, research_layout_name(session->options.layout),
		world(session)->logic_tick_count);
	print_hex(stream, research_model_bytes[session->options.model],
		  sizeof(research_model_bytes[0]));
	fputs("\",\"state_hex\":\"", stream);
	print_hex(stream, state, size);
	fputs("\",\"framebuffer_crc32\":", stream);
	if (crc == NULL) {
		fputs("null", stream);
	} else {
		fprintf(stream, "\"%08" PRIx32 "\"", *crc);
	}
	fprintf(stream,
		",\"candidate_founder\":%u,\"resident_policy\":\"selective\",\"family_roots\":[",
		(unsigned int)session->options.founder);
	for (uint32_t id = 1U; id <= session->snapshot.owners.count; ++id) {
		fprintf(stream, "%s%u", id == 1U ? "" : ",",
			(unsigned int)session->snapshot.owners.root[id]);
	}
	fputs("],", stream);
	err = toy_factory_garden_landing_ledger_print(stream, &session->history,
						      &session->lifetimes);
	if (err == 0) {
		fputs(",\"death_causes\":[", stream);
		for (uint32_t i = 1U; i <= session->lifetimes.count; ++i) {
			fprintf(stream, "%s%u", i == 1U ? "" : ",",
				(unsigned int)session->lifetimes.records[i].death_cause);
		}
		fputs("],\"complete\":true}\n", stream);
	}
	return ((err != 0) || ferror(stream) || (fflush(stream) != 0)) ? -EIO : 0;
}
