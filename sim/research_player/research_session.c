/* SPDX-License-Identifier: Apache-2.0 */
#include "research_session.h"
#include "research_trace.h"
#include "research_shadow.h"
#include "research_gate.h"
#include "research_purchase.h"
#include "research_reproduction.h"
#include "research_budget.h"
#include "research_foliage.h"
#include "research_fallback.h"
#include "research_models.h"
#include "garden_leaf_owned.h"
#include "garden_leaf_owned_internal.h"
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
#define SESSION_STATE_BYTES                                                                        \
	(TOY_FACTORY_LEAF_FAMILY_MAX_STATE_BYTES + RESEARCH_GATE_HEADER_BYTES +                    \
	 RESEARCH_FALLBACK_HEADER_BYTES)

_Static_assert(RESEARCH_STOP_TICK == TOY_FACTORY_MAINTENANCE_RUN_STOP, "Fixed research horizon");
_Static_assert(sizeof(research_model_bytes[0]) == TOY_FACTORY_LEAF_NEURAL_FILE_SIZE, "Model size");
_Static_assert(PICOSYSTEM_GARDEN_MAX_NODES <= RESEARCH_FAMILY_MAX_NODES, "Family node capacity");
_Static_assert(PICOSYSTEM_GARDEN_MAX_SEEDS <= RESEARCH_FAMILY_MAX_SEEDS, "Family seed capacity");

struct research_session {
	struct research_options options;
	struct toy_factory_leaf_owned *owner;
	/* Population scope owns candidate directly. The family envelope is used
	 * only for ancestry validation; exported population identity is TPR1.
	 */
	struct toy_factory_leaf_family snapshot;
	struct toy_factory_garden_lifetimes lifetimes;
	struct toy_factory_garden_landing_ledger history;
	struct research_trace *trace;
	struct research_shadow *shadow;
	struct research_gate *gate;
	struct research_purchase *purchases;
	struct research_reproduction *reproduction;
	struct research_budget *budget;
	struct research_foliage *foliage;
	bool gate_extended;
	bool fallback;
	int failure;
};

static const struct picosystem_garden_world *world(const struct research_session *session)
{
	return &session->snapshot.candidate.base.growth.base.world;
}

static bool selected_root(const struct research_session *session, uint8_t root)
{
	return (session->options.scope == RESEARCH_SCOPE_POPULATION) ||
	       (root == session->options.founder);
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
			if (session->options.scope == RESEARCH_SCOPE_POPULATION) {
				struct toy_factory_leaf_family_owners *const owners =
					&session->snapshot.owners;
				const uint32_t id = plant->lineage_id;
				if (id > owners->count) {
					const uint32_t parent = plant->parent_lineage_id;
					if ((id != owners->count + 1U) || (parent == 0U) ||
					    (parent > owners->count) ||
					    (owners->root[parent] == 0U) ||
					    (owners->root[parent] > owners->founders)) {
						return -ERANGE;
					}
					owners->root[id] = owners->root[parent];
					owners->count = id;
				}
			}
		}
		if (((plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) != 0U) !=
		    (session->lifetimes.records[plant->lineage_id].death_cause !=
		     TOY_FACTORY_GARDEN_LIFETIME_CAUSES)) {
			return -EFAULT;
		}
	}
	return ((session->lifetimes.count == state->lineage_sequence) &&
		(session->snapshot.owners.count == state->lineage_sequence))
		       ? 0
		       : -EFAULT;
}

int research_session_open(const struct research_options *options, struct research_session **out)
{
	if ((options == NULL) || (out == NULL) || (research_model_name(options->model) == NULL) ||
	    (research_layout_name(options->layout) == NULL) || !known_seed(options->seed) ||
	    ((options->scope != RESEARCH_SCOPE_FAMILY) &&
	     (options->scope != RESEARCH_SCOPE_POPULATION))) {
		return -EINVAL;
	}
	const struct toy_factory_garden_evaluation_scenario *const scenario =
		&toy_factory_garden_rainfed_scenarios[options->layout];
	const bool population = options->scope == RESEARCH_SCOPE_POPULATION;
	if (population ? options->founder != 0U
		       : ((options->founder == 0U) || (options->founder > scenario->plant_count))) {
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
		err = toy_factory_leaf_family_init(
			&initial, &growth, &leaf, population ? 1U : options->founder,
			TOY_FACTORY_MAINTENANCE_SELECTIVE, &session->snapshot);
	}
	if ((err == 0) && !population) {
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
		research_trace_close(session->trace);
		research_shadow_close(session->shadow);
		research_gate_close(session->gate);
		research_purchase_close(session->purchases);
		research_reproduction_close(session->reproduction);
		research_budget_close(session->budget);
		research_foliage_close(session->foliage);
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

int research_session_trace_start(struct research_session *session, uint8_t founder)
{
	if ((session == NULL) || (session->options.scope != RESEARCH_SCOPE_POPULATION) ||
	    (world(session)->logic_tick_count != 0U) || (session->trace != NULL) ||
	    (founder == 0U) || (founder > session->snapshot.owners.founders)) {
		return -EINVAL;
	}
	if (session->failure != 0) {
		return session->failure;
	}
	return research_trace_open(founder, &session->trace);
}

int research_session_trace_write(const struct research_session *session, FILE *stream)
{
	if ((session == NULL) || (stream == NULL) || (session->trace == NULL)) {
		return -EINVAL;
	}
	if (session->failure != 0) {
		return session->failure;
	}
	const uint32_t tick =
		session->gate_extended ? RESEARCH_TRACE_STOP : world(session)->logic_tick_count;
	return research_trace_write(session->trace, stream, tick);
}

int research_session_shadow_start(struct research_session *session, uint8_t founder,
				  uint16_t first_day, uint16_t end_day)
{
	if ((session == NULL) || (session->options.scope != RESEARCH_SCOPE_POPULATION) ||
	    (world(session)->logic_tick_count != 0U) || (session->shadow != NULL) ||
	    (session->gate != NULL) || (founder == 0U) ||
	    (founder > session->snapshot.owners.founders)) {
		return -EINVAL;
	}
	if (session->failure != 0) {
		return session->failure;
	}
	return research_shadow_open(session->options.model, founder, first_day, end_day,
				    &session->shadow);
}

int research_session_shadow_write(const struct research_session *session, FILE *stream)
{
	if ((session == NULL) || (stream == NULL) || (session->shadow == NULL)) {
		return -EINVAL;
	}
	if (session->failure != 0) {
		return session->failure;
	}
	return research_shadow_write(session->shadow, stream, world(session)->logic_tick_count);
}

static int gate_start(struct research_session *session, uint8_t variant, bool from_start)
{
	if ((session == NULL) || (session->options.scope != RESEARCH_SCOPE_POPULATION) ||
	    (session->options.model != 1U) || (session->options.layout != 0U) ||
	    ((session->options.seed != UINT32_C(0x58d7d6ca)) &&
	     (session->options.seed != UINT32_C(0x59818bc3)) &&
	     (!from_start || ((session->options.seed != UINT32_C(0x9a903368)) &&
			      (session->options.seed != UINT32_C(0x6b9c1a3e))))) ||
	    (world(session)->logic_tick_count != 0U) || (session->shadow != NULL) ||
	    (session->gate != NULL)) {
		return -EINVAL;
	}
	if (session->failure != 0) {
		return session->failure;
	}
	return research_gate_open(variant, from_start ? 0U : RESEARCH_GATE_AFTER, &session->gate);
}

int research_session_gate_start(struct research_session *session, uint8_t variant)
{
	return gate_start(session, variant, false);
}

int research_session_gate_start_early(struct research_session *session, uint8_t variant)
{
	return gate_start(session, variant, true);
}

int research_session_gate_continue(struct research_session *session)
{
	if (session == NULL) {
		return -EINVAL;
	}
	if (session->failure != 0) {
		return session->failure;
	}
	if ((session->gate == NULL) || session->gate_extended ||
	    (world(session)->logic_tick_count != RESEARCH_TRACE_STOP)) {
		return -EINVAL;
	}
	session->gate_extended = true;
	return 0;
}

int research_session_fallback_start(struct research_session *session)
{
	if (session == NULL || session->gate == NULL || session->fallback ||
	    session->foliage != NULL || session->options.seed != UINT32_C(0x9a903368) ||
	    world(session)->logic_tick_count != 0U) {
		return -EINVAL;
	}
	if (session->failure != 0) {
		return session->failure;
	}
	uint8_t header[RESEARCH_GATE_HEADER_BYTES];
	research_gate_header(session->gate, header);
	if (header[8] != 0U || header[9] != 0U || header[10] != 0U || header[11] != 0U) {
		return -EINVAL;
	}
	session->fallback = true;
	return 0;
}

int research_session_purchase_start(struct research_session *session)
{
	if (session == NULL || session->gate == NULL || session->purchases != NULL ||
	    session->options.seed != UINT32_C(0x9a903368) ||
	    world(session)->logic_tick_count != 0U) {
		return -EINVAL;
	}
	if (session->failure != 0) {
		return session->failure;
	}
	uint8_t header[RESEARCH_GATE_HEADER_BYTES];
	research_gate_header(session->gate, header);
	if (header[8] != 0U || header[9] != 0U || header[10] != 0U || header[11] != 0U) {
		return -EINVAL;
	}
	return research_purchase_open(&session->purchases);
}

int research_session_purchase_write(const struct research_session *session, FILE *stream)
{
	if (session == NULL || session->purchases == NULL || stream == NULL) {
		return -EINVAL;
	}
	if (session->failure != 0) {
		return session->failure;
	}
	return research_purchase_write(session->purchases, world(session)->logic_tick_count,
				       stream);
}

int research_session_reproduction_start(struct research_session *session)
{
	if (session == NULL || session->gate == NULL || session->reproduction != NULL ||
	    session->options.seed != UINT32_C(0x9a903368) ||
	    world(session)->logic_tick_count != 0U) {
		return -EINVAL;
	}
	if (session->failure != 0) {
		return session->failure;
	}
	uint8_t header[RESEARCH_GATE_HEADER_BYTES];
	research_gate_header(session->gate, header);
	if (header[4] != 2U || header[8] != 0U || header[9] != 0U || header[10] != 0U ||
	    header[11] != 0U) {
		return -EINVAL;
	}
	return research_reproduction_open(&session->reproduction);
}

int research_session_reproduction_write(const struct research_session *session, FILE *stream)
{
	if (session == NULL || session->reproduction == NULL || stream == NULL) {
		return -EINVAL;
	}
	if (session->failure != 0) {
		return session->failure;
	}
	return research_reproduction_write(session->reproduction, stream);
}

int research_session_budget_start(struct research_session *session)
{
	if (session == NULL || session->reproduction == NULL || !session->fallback ||
	    session->budget != NULL || world(session)->logic_tick_count != 0U) {
		return -EINVAL;
	}
	if (session->failure != 0) {
		return session->failure;
	}
	return research_budget_open(&session->budget);
}

int research_session_budget_write(const struct research_session *session, FILE *stream)
{
	if (session == NULL || session->budget == NULL || stream == NULL) {
		return -EINVAL;
	}
	if (session->failure != 0) {
		return session->failure;
	}
	return research_budget_write(session->budget, stream);
}

int research_session_foliage_start(struct research_session *session)
{
	if (session == NULL || session->reproduction == NULL || session->foliage != NULL ||
	    world(session)->logic_tick_count != 0U) {
		return -EINVAL;
	}
	if (session->failure != 0) {
		return session->failure;
	}
	return research_foliage_open(session->fallback ? 17U : 19U, &session->foliage);
}

int research_session_foliage_write(const struct research_session *session, FILE *stream)
{
	if (session == NULL || session->foliage == NULL || stream == NULL) {
		return -EINVAL;
	}
	if (session->failure != 0) {
		return session->failure;
	}
	return research_foliage_write(session->foliage, stream);
}

int research_session_canopy_start(struct research_session *session)
{
	if (session == NULL || session->foliage == NULL || world(session)->logic_tick_count != 0U) {
		return -EINVAL;
	}
	return session->failure != 0 ? session->failure
				     : research_foliage_canopy_start(session->foliage);
}

int research_session_canopy_write(const struct research_session *session, FILE *stream)
{
	if (session == NULL) {
		return -EINVAL;
	}
	return session->failure != 0 ? session->failure
				     : research_foliage_canopy_write(session->foliage, stream);
}

static int step_once(struct research_session *session)
{
	const uint32_t tick = world(session)->logic_tick_count + 1U;
	const bool ecology = tick % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR == 0U;
	struct picosystem_garden_world before;
	const bool trace_active = (session->trace != NULL) && !session->gate_extended;
	const bool budget_active = session->budget != NULL && research_budget_active(tick);
	const bool foliage_active = session->foliage != NULL && research_foliage_active(tick);
	if (ecology && (trace_active || budget_active || foliage_active)) {
		before = *world(session);
	}
	struct picosystem_garden_death_audit deaths;
	struct picosystem_garden_seed_audit seeds;
	struct picosystem_garden_resource_audit resources;
	struct picosystem_garden_reproduction_audit reproduction;
	const bool reproduction_active =
		session->reproduction != NULL && tick > RESEARCH_REPRODUCTION_FIRST &&
		tick <= RESEARCH_REPRODUCTION_END && tick % RESEARCH_REPRODUCTION_CADENCE == 0U;
	int err;
	if (session->options.scope == RESEARCH_SCOPE_POPULATION) {
		/* The checked init owns immutable models and setup; no mutable pointer
		 * escapes this session. NULL routing applies the model to every leaf,
		 * including a seed germinating earlier in this same step. Shadow mode
		 * forwards that exact decision; its diagnostics are not routing state.
		 */
		const struct research_shadow_context context = {
			.shadow = session->shadow, .owners = &session->snapshot.owners};
		const struct toy_factory_leaf_replay_route route = {
			.decide = research_shadow_decide, .context = &context};
		const struct research_gate_context gate_context = {
			.gate = session->gate, .owners = &session->snapshot.owners};
		const struct toy_factory_leaf_replay_route gate_route = {
			.decide = research_gate_decide, .context = &gate_context};
		const struct toy_factory_leaf_replay_route *selected = NULL;
		if (session->gate != NULL) {
			selected = &gate_route;
		} else if (session->shadow != NULL) {
			selected = &route;
		}
		const struct research_foliage_context foliage_context = {
			.trace = session->foliage,
			.next = selected,
			.before = foliage_active ? &before : NULL};
		const struct toy_factory_leaf_replay_route foliage_route = {
			.decide = research_foliage_decide, .context = &foliage_context};
		if (foliage_active) {
			selected = &foliage_route;
		}
		const bool purchase_active = session->purchases != NULL && ecology &&
					     tick >= RESEARCH_PURCHASE_BEGIN &&
					     tick < RESEARCH_PURCHASE_END;
		const struct toy_factory_garden_growth_observer observer = {
			.observe = purchase_active ? research_purchase_growth
						   : research_reproduction_growth,
			.context = purchase_active ? (void *)session->purchases
						   : (void *)session->reproduction,
			.reproduction = &reproduction};
		const bool observed = purchase_active || reproduction_active;
		if (session->fallback) {
			const struct research_fallback_route placement = {
				.owners = &session->snapshot.owners};
			err = research_fallback_step_owned(
				&session->snapshot.candidate, &deaths, &seeds, &resources,
				observed ? &observer : NULL, selected, &placement);
		} else {
			err = toy_factory_leaf_replay_step_owned(
				&session->snapshot.candidate, &deaths, &seeds, &resources,
				observed ? &observer : NULL, selected);
		}
	} else {
		err = toy_factory_leaf_owned_step(session->owner, &deaths, &seeds, &resources,
						  NULL);
		if (err == 0) {
			err = toy_factory_leaf_owned_snapshot(session->owner, &session->snapshot);
		}
	}
	if (err != 0) {
		return err;
	}
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
		if (reproduction_active) {
			err = research_reproduction_record(session->reproduction, tick,
							   &reproduction);
		}
		if (err == 0 && (budget_active || foliage_active)) {
			struct toy_factory_maintenance_step step;
			err = toy_factory_maintenance_step_read(&before, world(session), &resources,
								&step);
			if (err == 0 && budget_active) {
				err = research_budget_record(session->budget, &step,
							     reproduction_active ? &reproduction
										 : NULL);
			}
			if (err == 0 && foliage_active) {
				err = research_foliage_finish(session->foliage, &before, &step);
			}
		}
		if (err != 0) {
			return err;
		}
		err = births(session);
		if (err == 0) {
			err = toy_factory_garden_landing_ledger_step(
				&session->history, world(session), &session->lifetimes, &seeds);
		}
		if ((err == 0) && trace_active) {
			err = research_trace_record(
				session->trace, &before, world(session), &resources, &seeds,
				session->snapshot.owners.root, session->snapshot.owners.count);
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
	const uint32_t stop =
		session->gate_extended ? 608U * RESEARCH_DAY_TICKS
		: (session->trace == NULL && session->shadow == NULL && session->gate == NULL)
			? RESEARCH_STOP_TICK
			: RESEARCH_TRACE_STOP;
	if (ticks > stop - world(session)->logic_tick_count) {
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
		if (selected_root(session, roots[plant->lineage_id]) &&
		    ((plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) == 0U)) {
			++result.living;
		}
	}
	for (uint8_t i = 0U; i < state->seed_count; ++i) {
		if (selected_root(session, roots[state->seeds[i].parent_lineage_id])) {
			++result.pending;
		}
	}
	*out = result;
	return 0;
}

int research_session_encode(const struct research_session *session, uint8_t *out, size_t capacity,
			    size_t *size)
{
	if ((session == NULL) || (out == NULL) || (size == NULL)) {
		return -EINVAL;
	}
	if (session->failure != 0) {
		return session->failure;
	}
	const size_t outer = session->fallback ? RESEARCH_FALLBACK_HEADER_BYTES : 0U;
	const size_t prefix = outer + (session->gate == NULL ? 0U : RESEARCH_GATE_HEADER_BYTES);
	if (capacity < prefix) {
		return -ENOSPC;
	}
	size_t inner_size;
	const int err = toy_factory_leaf_family_encode(&session->snapshot, out + prefix,
						       capacity - prefix, &inner_size);
	if ((err == 0) && (session->options.scope == RESEARCH_SCOPE_POPULATION)) {
		memcpy(out + prefix, "TPR1", 4U);
		out[prefix + 4U] = 0U;
		out[prefix + 5U] = 0U;
	}
	if (err == 0) {
		if (session->gate != NULL) {
			research_gate_header(session->gate, out + outer);
		}
		if (session->fallback) {
			const uint8_t header[RESEARCH_FALLBACK_HEADER_BYTES] = {'T', 'B', 'F',
										'1', 1U,  2U};
			memcpy(out, header, sizeof(header));
		}
		*size = prefix + inner_size;
	}
	return err;
}

int research_session_family_view(const struct research_session *session,
				 struct research_family_view *out)
{
	if ((session == NULL) || (out == NULL)) {
		return -EINVAL;
	}
	if (session->failure != 0) {
		return session->failure;
	}
	const struct picosystem_garden_world *const state = world(session);
	const struct toy_factory_leaf_family_owners *const owners = &session->snapshot.owners;
	if ((state->node_count > PICOSYSTEM_GARDEN_MAX_NODES) ||
	    (state->plant_count > PICOSYSTEM_GARDEN_MAX_PLANTS) ||
	    (state->seed_count > PICOSYSTEM_GARDEN_MAX_SEEDS) ||
	    (owners->count > TOY_FACTORY_LEAF_FAMILY_MAX_LINEAGES)) {
		return -ERANGE;
	}
	struct research_family_view result = {.tick = state->logic_tick_count};
	bool selected[PICOSYSTEM_GARDEN_MAX_PLANTS] = {false};
	for (uint8_t i = 0U; i < state->plant_count; ++i) {
		const struct picosystem_garden_plant *const plant = &state->plants[i];
		if ((plant->lineage_id == 0U) || (plant->lineage_id > owners->count)) {
			return -ERANGE;
		}
		selected[i] = selected_root(session, owners->root[plant->lineage_id]) &&
			      ((plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) == 0U);
		if (selected[i]) {
			++result.living;
		}
	}
	for (uint16_t i = 0U; i < state->node_count; ++i) {
		const struct picosystem_garden_node *const node = &state->nodes[i];
		if (node->plant_index >= state->plant_count) {
			return -ERANGE;
		}
		if (!selected[node->plant_index]) {
			continue;
		}
		struct research_family_segment segment = {
			.lineage = state->plants[node->plant_index].lineage_id,
			.start_x = node->x,
			.start_y = node->y,
			.end_x = node->x,
			.end_y = node->y,
			.base = node->parent_index == PICOSYSTEM_GARDEN_NODE_NONE};
		if (!segment.base) {
			if ((node->parent_index >= i) ||
			    (state->nodes[node->parent_index].plant_index != node->plant_index)) {
				return -ERANGE;
			}
			const struct picosystem_garden_node *const parent =
				&state->nodes[node->parent_index];
			segment.start_x = parent->x;
			segment.start_y = parent->y;
			/* Match the frozen renderer's integer growth interpolation. */
			segment.end_x =
				(uint8_t)((int32_t)parent->x +
					  (((int32_t)node->x - parent->x) * node->growth_progress) /
						  UINT8_MAX);
			segment.end_y =
				(uint8_t)((int32_t)parent->y +
					  (((int32_t)node->y - parent->y) * node->growth_progress) /
						  UINT8_MAX);
		}
		result.segments[result.segment_count++] = segment;
	}
	for (uint8_t i = 0U; i < state->seed_count; ++i) {
		const struct picosystem_garden_seed *const seed = &state->seeds[i];
		if ((seed->parent_lineage_id == 0U) || (seed->parent_lineage_id > owners->count)) {
			return -ERANGE;
		}
		if (!selected_root(session, owners->root[seed->parent_lineage_id])) {
			continue;
		}
		const int32_t x = (int32_t)(PICOSYSTEM_GARDEN_ORIGIN_X_PIXELS +
					    seed->column * PICOSYSTEM_GARDEN_CELL_PIXELS +
					    PICOSYSTEM_GARDEN_CELL_PIXELS / 2U) +
				  seed->visual_offset;
		if ((seed->column >= PICOSYSTEM_GARDEN_GRID_COLUMNS) || (x < 0) ||
		    (x >= (int32_t)PICOSYSTEM_GRAPHICS_WIDTH)) {
			return -ERANGE;
		}
		result.seeds[result.seed_count++] =
			(struct research_family_seed){.parent = seed->parent_lineage_id,
						      .x = (uint8_t)x,
						      .y = PICOSYSTEM_GARDEN_SOIL_TOP_PIXELS + 2U};
	}
	*out = result;
	return 0;
}

int research_session_render(struct research_session *session, uint8_t *out, size_t capacity,
			    uint32_t *crc)
{
	if ((session == NULL) || (out == NULL) || (crc == NULL) ||
	    (capacity < RESEARCH_FRAME_BYTES)) {
		return -EINVAL;
	}
	uint8_t before[SESSION_STATE_BYTES];
	uint8_t after[SESSION_STATE_BYTES];
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
	uint8_t state[SESSION_STATE_BYTES];
	size_t size;
	int err = research_session_encode(session, state, sizeof(state), &size);
	if (err != 0) {
		return err;
	}
	const bool population = session->options.scope == RESEARCH_SCOPE_POPULATION;
	fprintf(stream,
		"{\"schema\":\"%s\",\"controller_assignment\":"
		"\"%s\",\"objective\":null,\"seed\":\"%08" PRIx32 "\",\"scenario\":\"%s\","
		"\"climate\":\"seasonal\",\"gardener\":false,\"ticks\":%" PRIu32
		",\"growth_model_sha256\":\"" GROWTH_SHA "\",\"leaf_model_hex\":\"",
		session->fallback       ? "garden-blocker-fallback-replay-v1"
		: session->gate != NULL ? "garden-leaf-gate-replay-v1"
		: population            ? "garden-leaf-population-replay-v1"
					: "garden-leaf-family-replay-v1",
		session->fallback       ? "family-repair-and-placement"
		: session->gate != NULL ? "scheduled-founder-family"
		: population            ? "whole-population"
					: "founder-family",
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
	if (session->gate != NULL) {
		fputs(",\"intervention\":", stream);
		if (research_gate_write(session->gate, stream) != 0) {
			return -EIO;
		}
	}
	if (session->fallback) {
		fputs(",\"placement_intervention\":{\"kind\":\"fewest-blockers\",\"version\":1,"
		      "\"founder\":2,\"after_tick\":0,\"tie_break\":\"cyclic-from-existing-draw\"}",
		      stream);
	}
	if (population) {
		fputs(",\"candidate_founder\":null,\"resident_policy\":null,\"family_roots\":[",
		      stream);
	} else {
		fprintf(stream,
			",\"candidate_founder\":%u,\"resident_policy\":\"selective\",\"family_"
			"roots\":[",
			(unsigned int)session->options.founder);
	}
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
