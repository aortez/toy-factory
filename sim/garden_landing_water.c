/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_water.h"
#include "garden_landing_run_internal.h"

#include <errno.h>
#include <inttypes.h>
#include <string.h>

static int validate_config(const struct toy_factory_garden_landing_water_config *config)
{
	if (config == NULL) {
		return -EINVAL;
	}
	return (((config->version == TOY_FACTORY_GARDEN_LANDING_WATER_VERSION) &&
		 (config->enabled <= 1U) && (config->eligible == 0U)) ||
		((config->version == TOY_FACTORY_GARDEN_LANDING_ARBITRATION_VERSION) &&
		 (config->enabled == 1U) && (config->eligible <= 1U)))
		       ? 0
		       : -ERANGE;
}

int toy_factory_garden_landing_water_init(
	const struct picosystem_garden_world *world,
	const struct toy_factory_garden_landing_model *model,
	const struct toy_factory_garden_landing_water_config *config,
	struct toy_factory_garden_landing_water_run *run)
{
	if (run == NULL) {
		return -EINVAL;
	}
	int err = validate_config(config);
	if (err != 0) {
		return err;
	}
	struct toy_factory_garden_landing_water_run result = {.config = *config};
	err = toy_factory_garden_landing_run_init(world, model, &result.base);
	if (err != 0) {
		return err;
	}
	if (result.base.rules != 0U) {
		return -ENOTSUP;
	}
	*run = result;
	return 0;
}

int toy_factory_garden_landing_water_step(struct toy_factory_garden_landing_water_run *run,
					  struct picosystem_garden_death_audit *deaths,
					  struct picosystem_garden_seed_audit *seeds,
					  struct picosystem_garden_resource_audit *resources,
					  struct toy_factory_garden_landing_water_audit *audit)
{
	if ((run == NULL) || (deaths == NULL) || (seeds == NULL)) {
		return -EINVAL;
	}
	const int err = validate_config(&run->config);
	if (err != 0) {
		return err;
	}
	if (run->base.rules != 0U) {
		return -ENOTSUP;
	}
	return toy_factory_garden_landing_run_step_water_internal(&run->base, &run->config, deaths,
								  seeds, resources, audit);
}

int toy_factory_garden_landing_water_hash(const struct toy_factory_garden_landing_water_run *run,
					  uint32_t *hash)
{
	if ((run == NULL) || (hash == NULL)) {
		return -EINVAL;
	}
	int err = validate_config(&run->config);
	if (err != 0) {
		return err;
	}
	uint32_t base;
	err = toy_factory_garden_landing_run_hash(&run->base, &base);
	if (err != 0) {
		return err;
	}
	if (run->base.rules != 0U) {
		return -ENOTSUP;
	}
	const uint8_t bytes[] = {
		'G',
		'W',
		run->config.version == TOY_FACTORY_GARDEN_LANDING_WATER_VERSION ? 'P' : 'A',
		'1',
		(uint8_t)base,
		(uint8_t)(base >> 8U),
		(uint8_t)(base >> 16U),
		(uint8_t)(base >> 24U),
		run->config.version,
		run->config.enabled};
	uint32_t h = UINT32_C(2166136261);
	for (size_t i = 0U; i < sizeof(bytes); ++i) {
		h = (h ^ bytes[i]) * UINT32_C(16777619);
	}
	if (run->config.version == TOY_FACTORY_GARDEN_LANDING_ARBITRATION_VERSION) {
		h = (h ^ run->config.eligible) * UINT32_C(16777619);
	}
	*hash = h;
	return 0;
}

int toy_factory_garden_landing_water_eligible(
	const struct picosystem_garden_agent_observation *observation,
	const struct picosystem_garden_agent_decision *decision, bool *allowed, const void *context)
{
	if ((observation == NULL) || (decision == NULL) || (allowed == NULL) || (context == NULL)) {
		return -EINVAL;
	}
	bool result = true;
	if (toy_factory_garden_seedling_reserve_active(context, observation)) {
		struct toy_factory_garden_seedling_reserve_forecast forecast;
		const int err = toy_factory_garden_seedling_reserve_forecast(
			observation, &decision->proposal, &forecast);
		if (err != 0) {
			return err;
		}
		result = forecast.water_allowed;
	}
	*allowed = result;
	return 0;
}

int toy_factory_garden_landing_water_observe_internal(
	const struct picosystem_garden_agent_observation *observation,
	const struct picosystem_garden_agent_memory *memory,
	const struct picosystem_garden_landing_packet *packet,
	const struct picosystem_garden_agent_decision *decision, void *opaque)
{
	(void)packet;
	struct toy_factory_garden_landing_water_context *const ctx = opaque;
	const struct toy_factory_garden_seedling_reserve_context selection = {
		.world = ctx->world, .all_offspring = true};
	if (!toy_factory_garden_seedling_reserve_active(&selection, observation)) {
		return 0;
	}
	struct toy_factory_garden_seedling_reserve_forecast forecast;
	const int err = toy_factory_garden_seedling_reserve_forecast(
		observation, &decision->proposal, &forecast);
	if (err != 0) {
		return err;
	}
	if (ctx->record_bids) {
		const uint16_t n = ctx->audit->bid_count;
		if (n >= PICOSYSTEM_GARDEN_MAX_NODES) {
			return -EOVERFLOW;
		}
		ctx->audit->bids[n].observation = *observation;
		ctx->audit->bids[n].decision = *decision;
		ctx->audit->bids[n].memory = *memory;
		ctx->audit->bids[n].forecast = forecast;
		++ctx->audit->bid_count;
	}
	struct toy_factory_garden_landing_water_winner *const entry =
		&ctx->audit->plants[observation->plant_index];
	if (entry->bids >= PICOSYSTEM_GARDEN_MAX_NODES) {
		return -EOVERFLOW;
	}
	++entry->bids;
	entry->denied_bids = (uint16_t)(entry->denied_bids + (forecast.water_allowed ? 0U : 1U));
	entry->funded_wet_root_bids =
		(uint16_t)(entry->funded_wet_root_bids +
			   ((forecast.wet_root && forecast.water_allowed) ? 1U : 0U));
	/* Keep the unfiltered first-wins winner for the veto control. Version 2
	 * additionally retains all bids so eligible selection can be checked.
	 */
	if ((entry->lineage == 0U) ||
	    (decision->proposal.priority > entry->original.proposal.priority)) {
		entry->lineage = ctx->world->plants[observation->plant_index].lineage_id;
		entry->observation = *observation;
		entry->original = *decision;
		entry->forecast = forecast;
	}
	return 0;
}

static void print_receipt(FILE *stream, const struct toy_factory_garden_landing_water_winner *w,
			  bool applied)
{
	const struct picosystem_garden_agent_observation *const o = &w->observation;
	const struct toy_factory_garden_seedling_reserve_forecast *const f = &w->forecast;
	const uint8_t action =
		applied ? PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT : w->original.proposal.action;
	const bool available = f->destination != PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE;
	const struct picosystem_garden_agent_candidate *const destination =
		available ? &o->candidates[f->destination] : NULL;
	fprintf(stream,
		"{\"id\":%" PRIu32 ",\"age\":%u,\"water\":%u,\"nodes\":%u,"
		"\"roots\":%u,\"species\":%u,\"tissue\":%u,\"action\":%u,\"priority\":%d,"
		"\"tip_moisture\":%u,\"destination\":",
		w->lineage, o->age_ecology_ticks, o->stored_water, o->plant_node_count,
		o->root_node_count, o->species_id, o->tissue_kind, w->original.proposal.action,
		w->original.proposal.priority, o->tip_moisture);
	if (destination != NULL) {
		fprintf(stream, "[%u,%u]", destination->y, destination->moisture);
	} else {
		fputs("null", stream);
	}
	fprintf(stream,
		",\"cost\":%" PRIu32 ",\"upkeep\":%" PRIu32 ",\"reserve\":%" PRIu32
		",\"wet_root\":%s,\"allowed\":%s,\"applied\":%s,\"result_action\":%u,"
		"\"bids\":%u,\"denied_bids\":%u,\"funded_wet_root_bids\":%u}",
		f->water_cost, f->water_upkeep, f->water_reserve, f->wet_root ? "true" : "false",
		f->water_allowed ? "true" : "false", applied ? "true" : "false", action, w->bids,
		w->denied_bids, w->funded_wet_root_bids);
}

static void print_memory(FILE *stream, const struct picosystem_garden_agent_memory *memory)
{
	fputc('[', stream);
	for (size_t i = 0U; i < PICOSYSTEM_GARDEN_AGENT_MEMORY_WIDTH; ++i) {
		fprintf(stream, "%s%d", i == 0U ? "" : ",", memory->hidden[i]);
	}
	fputc(']', stream);
}

static int print_arbitration(FILE *stream, const struct toy_factory_garden_landing_water_run *run,
			     const struct toy_factory_garden_landing_water_audit *audit)
{
	if (audit->bid_count > PICOSYSTEM_GARDEN_MAX_NODES) {
		return -ERANGE;
	}
	fprintf(stream, "{\"tick\":%" PRIu32 ",\"plants\":[", run->base.world.logic_tick_count);
	bool first = true;
	for (uint8_t i = 0U; i < PICOSYSTEM_GARDEN_MAX_PLANTS; ++i) {
		const struct toy_factory_garden_landing_water_winner *const w = &audit->plants[i];
		if (w->lineage == 0U) {
			continue;
		}
		uint16_t original = UINT16_MAX, eligible = UINT16_MAX, count = 0U;
		uint16_t original_order = 0U, eligible_order = 0U;
		for (uint16_t n = 0U; n < audit->bid_count; ++n) {
			if (audit->bids[n].observation.plant_index != i) {
				continue;
			}
			if ((original == UINT16_MAX) ||
			    (audit->bids[n].decision.proposal.priority >
			     audit->bids[original].decision.proposal.priority)) {
				original = n;
				original_order = count;
			}
			if (audit->bids[n].forecast.water_allowed &&
			    ((eligible == UINT16_MAX) ||
			     (audit->bids[n].decision.proposal.priority >
			      audit->bids[eligible].decision.proposal.priority))) {
				eligible = n;
				eligible_order = count;
			}
			++count;
		}
		if ((count != w->bids) || (original == UINT16_MAX) ||
		    (i >= run->base.world.plant_count) ||
		    (run->base.world.plants[i].lineage_id != w->lineage)) {
			return -EFAULT;
		}
		const bool use_eligible = (run->config.eligible != 0U) && (eligible != UINT16_MAX);
		const uint16_t selected = use_eligible ? eligible : original;
		const bool fallback = !audit->bids[selected].forecast.water_allowed;
		const struct picosystem_garden_agent_decision *const d =
			&audit->bids[selected].decision;
		const struct picosystem_garden_agent_observation *const o =
			&audit->bids[selected].observation;
		const struct picosystem_garden_plant *const p = &run->base.world.plants[i];
		const struct picosystem_garden_agent_telemetry *const actual = &p->agent_telemetry;
		const uint8_t action =
			fallback ? PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT : d->proposal.action;
		if ((actual->last_action != action) ||
		    (actual->last_priority != d->proposal.priority) ||
		    (actual->last_tissue_kind != o->tissue_kind) ||
		    (actual->last_tip_x != o->tip_x) || (actual->last_tip_y != o->tip_y) ||
		    (memcmp(&p->agent_memory, &d->next_memory, sizeof(p->agent_memory)) != 0)) {
			return -EFAULT;
		}
		fprintf(stream,
			"%s{\"id\":%" PRIu32 ",\"original\":%u,\"selected\":%u,"
			"\"fallback\":%s,\"result_action\":%u,\"bids\":[",
			first ? "" : ",", w->lineage, original_order,
			use_eligible ? eligible_order : original_order, fallback ? "true" : "false",
			action);
		bool first_bid = true;
		for (uint16_t n = 0U; n < audit->bid_count; ++n) {
			if (audit->bids[n].observation.plant_index != i) {
				continue;
			}
			struct toy_factory_garden_landing_water_winner bid = *w;
			bid.observation = audit->bids[n].observation;
			bid.original = audit->bids[n].decision;
			bid.forecast = audit->bids[n].forecast;
			if ((bid.forecast.destination != PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE) &&
			    (bid.forecast.destination >= bid.observation.candidate_count)) {
				return -EFAULT;
			}
			fprintf(stream,
				"%s{\"tip\":%u,\"x\":%u,\"y\":%u,\"memory\":", first_bid ? "" : ",",
				bid.observation.tip_index, bid.observation.tip_x,
				bid.observation.tip_y);
			print_memory(stream, &audit->bids[n].memory);
			fputs(",\"next_memory\":", stream);
			print_memory(stream, &bid.original.next_memory);
			fputs(",\"proposal\":", stream);
			print_receipt(stream, &bid, false);
			fputc('}', stream);
			first_bid = false;
		}
		fputs("],\"committed_memory\":", stream);
		print_memory(stream, &p->agent_memory);
		fputc('}', stream);
		first = false;
	}
	fputs("]}\n", stream);
	return ferror(stream) ? -EIO : 0;
}

int toy_factory_garden_landing_water_print(
	FILE *stream, const struct toy_factory_garden_landing_water_run *run,
	const struct toy_factory_garden_landing_water_audit *audit)
{
	if ((stream == NULL) || (run == NULL) || (audit == NULL)) {
		return -EINVAL;
	}
	const int err = validate_config(&run->config);
	if (err != 0) {
		return err;
	}
	if (run->config.version == TOY_FACTORY_GARDEN_LANDING_ARBITRATION_VERSION) {
		return print_arbitration(stream, run, audit);
	}
	fprintf(stream, "{\"tick\":%" PRIu32 ",\"winners\":[", run->base.world.logic_tick_count);
	bool first = true;
	for (uint8_t i = 0U; i < PICOSYSTEM_GARDEN_MAX_PLANTS; ++i) {
		const struct toy_factory_garden_landing_water_winner *const w = &audit->plants[i];
		if (w->lineage == 0U) {
			continue;
		}
		const struct picosystem_garden_agent_observation *const o = &w->observation;
		const struct toy_factory_garden_seedling_reserve_forecast *const f = &w->forecast;
		const bool applied = (run->config.enabled != 0U) && !f->water_allowed;
		const uint8_t action =
			applied ? PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT : w->original.proposal.action;
		if ((i >= run->base.world.plant_count) ||
		    (run->base.world.plants[i].lineage_id != w->lineage)) {
			return -EFAULT;
		}
		const struct picosystem_garden_agent_telemetry *const actual =
			&run->base.world.plants[i].agent_telemetry;
		if ((actual->last_action != action) ||
		    (actual->last_priority != w->original.proposal.priority) ||
		    (actual->last_tissue_kind != o->tissue_kind) ||
		    (actual->last_tip_x != o->tip_x) || (actual->last_tip_y != o->tip_y)) {
			return -EFAULT;
		}
		const bool available = f->destination != PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE;
		if (available && (f->destination >= o->candidate_count)) {
			return -EFAULT;
		}
		if (!first) {
			fputc(',', stream);
		}
		print_receipt(stream, w, applied);
		first = false;
	}
	fputs("]}\n", stream);
	return ferror(stream) ? -EIO : 0;
}
