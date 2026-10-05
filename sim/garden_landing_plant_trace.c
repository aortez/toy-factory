/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_plant_trace.h"
#include "garden_climate_cli.h"
#include "garden_landing_root_direction.h"

#include <errno.h>
#include <inttypes.h>
#include <string.h>

static bool has_daylight(enum toy_factory_garden_plant_trace_scope scope)
{
	return (scope == TOY_FACTORY_GARDEN_TRACE_DAYLIGHT) ||
	       (scope == TOY_FACTORY_GARDEN_TRACE_DAWN);
}

static bool has_afternoon(enum toy_factory_garden_plant_trace_scope scope)
{
	return (scope == TOY_FACTORY_GARDEN_TRACE_AFTERNOON) || has_daylight(scope);
}

static bool is_selected(const struct toy_factory_garden_plant_trace *trace, uint32_t id)
{
	if (trace->scope != TOY_FACTORY_GARDEN_TRACE_FOUNDERS) {
		return true;
	}
	for (uint8_t i = 0U; i < trace->founder_count; ++i) {
		if (trace->founders[i] == id) {
			return true;
		}
	}
	return false;
}

int toy_factory_garden_plant_trace_init(struct toy_factory_garden_plant_trace *trace, FILE *stream,
					const struct picosystem_garden_world *initial,
					uint8_t limit, uint8_t budget_mode, uint32_t start,
					uint32_t stop,
					enum toy_factory_garden_plant_trace_scope scope)
{
	if ((trace == NULL) || (stream == NULL) || (initial == NULL) ||
	    (initial->logic_tick_count != 0U) ||
	    ((unsigned int)scope >= TOY_FACTORY_GARDEN_TRACE_SCOPES) ||
	    (initial->plant_count > PICOSYSTEM_GARDEN_MAX_PLANTS) ||
	    ((limit != 0U) && (limit != TOY_FACTORY_GARDEN_LANDING_GROWTH_LIMIT)) ||
	    (budget_mode >= TOY_FACTORY_GARDEN_BUDGET_COUNT) ||
	    (((scope == TOY_FACTORY_GARDEN_TRACE_CHOICE) ||
	      (scope == TOY_FACTORY_GARDEN_TRACE_ENERGY) || has_afternoon(scope)) &&
	     (budget_mode != TOY_FACTORY_GARDEN_BUDGET_SHOOT)) ||
	    ((budget_mode != TOY_FACTORY_GARDEN_BUDGET_LEGACY) &&
	     (limit != TOY_FACTORY_GARDEN_LANDING_GROWTH_LIMIT)) ||
	    (start == 0U) || (stop < start) ||
	    (start % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR != 0U) ||
	    (stop % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR != 0U)) {
		return -EINVAL;
	}
	memset(trace, 0, sizeof(*trace));
	trace->stream = stream;
	trace->scope = scope;
	trace->budget_mode = budget_mode;
	for (uint8_t i = 0U; i < initial->plant_count; ++i) {
		const struct picosystem_garden_plant *const p = &initial->plants[i];
		if (p->parent_lineage_id == 0U) {
			trace->founders[trace->founder_count++] = p->lineage_id;
		}
	}
	fprintf(stream,
		"{\"schema\":\"%s\",\"node_limit\":%u,"
		"\"start\":%" PRIu32 ",\"stop\":%" PRIu32,
		(scope == TOY_FACTORY_GARDEN_TRACE_DAWN)      ? "landing-dawn-stand-trace-v1"
		: has_daylight(scope)                         ? "landing-daylight-stand-trace-v1"
		: has_afternoon(scope)                        ? "landing-afternoon-stand-trace-v1"
		: (scope == TOY_FACTORY_GARDEN_TRACE_ENERGY)  ? "landing-root-energy-stand-trace-v1"
		: (scope == TOY_FACTORY_GARDEN_TRACE_CHOICE)  ? "landing-root-choice-stand-trace-v1"
		: (scope == TOY_FACTORY_GARDEN_TRACE_ORDERED) ? "landing-ordered-stand-trace-v1"
		: (scope == TOY_FACTORY_GARDEN_TRACE_ALL)     ? "landing-stand-trace-v1"
		: budget_mode                                 ? "landing-budget-founder-trace-v1"
							      : "landing-founder-trace-v1",
		limit, start, stop);
	if (scope == TOY_FACTORY_GARDEN_TRACE_FOUNDERS) {
		fputs(",\"founders\":[", stream);
		for (uint8_t i = 0U; i < trace->founder_count; ++i) {
			fprintf(stream, "%s%" PRIu32, i ? "," : "", trace->founders[i]);
		}
		fputc(']', stream);
	}
	if (budget_mode != TOY_FACTORY_GARDEN_BUDGET_LEGACY) {
		fprintf(stream, ",\"budget_mode\":%u", budget_mode);
	}
	fputs("}\n", stream);
	return ferror(stream) ? -EIO : 0;
}

int toy_factory_garden_plant_trace_observe(const struct picosystem_garden_world *world,
					   const struct picosystem_garden_agent_observation *o,
					   const struct picosystem_garden_agent_decision *raw,
					   const struct picosystem_garden_agent_decision *applied,
					   void *context)
{
	struct toy_factory_garden_plant_trace *const trace = context;
	if ((world == NULL) || (o == NULL) || (raw == NULL) || (applied == NULL) ||
	    (trace == NULL) || (o->plant_index >= world->plant_count) ||
	    (o->candidate_count > PICOSYSTEM_GARDEN_AGENT_MAX_CANDIDATES) ||
	    (applied->proposal.candidate_count > PICOSYSTEM_GARDEN_AGENT_MAX_CANDIDATES)) {
		return -EINVAL;
	}
	const uint32_t lineage = world->plants[o->plant_index].lineage_id;
	if (!is_selected(trace, lineage)) {
		return 0;
	}
	if (trace->count >= PICOSYSTEM_GARDEN_MAX_NODES) {
		return -ENOSPC;
	}
	const bool choice_trace = (trace->scope == TOY_FACTORY_GARDEN_TRACE_CHOICE) ||
				  (trace->scope == TOY_FACTORY_GARDEN_TRACE_ENERGY) ||
				  has_afternoon(trace->scope);
	if ((!choice_trace && (raw->proposal.priority != applied->proposal.priority)) ||
	    (raw->proposal.tip_index != applied->proposal.tip_index) ||
	    (memcmp(&raw->next_memory, &applied->next_memory, sizeof(raw->next_memory)) != 0)) {
		return -EFAULT;
	}
	struct toy_factory_garden_seedling_reserve_forecast water = {0};
	bool water_active = false;
	struct toy_factory_garden_root_allocation_receipt allocation = {0};
	if (trace->root_allocation.version != 0U) {
		if (trace->scope != TOY_FACTORY_GARDEN_TRACE_DAWN) {
			return -EINVAL;
		}
		struct picosystem_garden_agent_decision expected = *raw;
		int err = toy_factory_garden_root_choice_apply(world, o, &trace->root_choice,
							       trace->budget_mode, &expected);
		if (err == 0) {
			err = toy_factory_garden_root_allocation_apply(
				world, o, &trace->root_allocation, &trace->root_choice,
				trace->budget_mode, &expected, &allocation);
		}
		if (err != 0) {
			return err;
		}
		if (expected.proposal.priority != applied->proposal.priority) {
			return -EFAULT;
		}
	}
	if (choice_trace) {
		struct picosystem_garden_agent_decision expected = *raw;
		expected.proposal.priority = applied->proposal.priority;
		if (trace->root_choice.wet_direction) {
			const int err = toy_factory_garden_root_direction_apply(
				world, o, &trace->root_choice, trace->budget_mode, &expected);
			if (err != 0) {
				return err;
			}
		}
		if ((raw->proposal.action != applied->proposal.action) ||
		    (raw->proposal.candidate_count != applied->proposal.candidate_count) ||
		    (memcmp(expected.proposal.candidate_order, applied->proposal.candidate_order,
			    sizeof(raw->proposal.candidate_order)) != 0)) {
			return -EFAULT;
		}
		const int err =
			toy_factory_garden_seedling_reserve_forecast(o, &applied->proposal, &water);
		if (err != 0) {
			return err;
		}
		const struct toy_factory_garden_seedling_reserve_context reserve = {
			.world = world, .all_offspring = true};
		water_active = toy_factory_garden_seedling_reserve_active(&reserve, o);
	}
	struct toy_factory_garden_budget_receipt budget = {0};
	if (trace->budget_mode != TOY_FACTORY_GARDEN_BUDGET_LEGACY) {
		const int err = toy_factory_garden_landing_budget_assess(
			world, o, applied, trace->budget_mode, &budget);
		if (err != 0) {
			return err;
		}
	}
	struct toy_factory_garden_afternoon_forecast afternoon = {0};
	if (has_afternoon(trace->scope)) {
		const int err = toy_factory_garden_afternoon_forecast(o, applied->proposal.action,
								      &afternoon);
		if (err != 0) {
			return err;
		}
	}
	struct toy_factory_garden_daylight_forecast daylight = {0};
	if (has_daylight(trace->scope)) {
		const int err = toy_factory_garden_daylight_forecast(o, applied->proposal.action,
								     &daylight);
		if (err != 0) {
			return err;
		}
	}
	struct toy_factory_garden_dawn_forecast dawn = {0};
	if (trace->scope == TOY_FACTORY_GARDEN_TRACE_DAWN) {
		const int err =
			toy_factory_garden_dawn_forecast(o, applied->proposal.action, &dawn);
		if (err != 0) {
			return err;
		}
	}
	const bool energy_active =
		toy_factory_garden_root_energy_active(world, o, &trace->root_choice);
	trace->bids[trace->count++] = (struct toy_factory_garden_plant_bid){
		.lineage = lineage,
		.observation = *o,
		.raw_action = raw->proposal.action,
		.action = applied->proposal.action,
		.priority = applied->proposal.priority,
		.raw_priority = raw->proposal.priority,
		.budget = budget,
		.water = water,
		.water_active = water_active,
		.energy_active = energy_active,
		.afternoon_active = energy_active && trace->root_choice.afternoon_reserve,
		.afternoon = afternoon,
		.daylight_active = energy_active && trace->root_choice.daylight_energy,
		.daylight = daylight,
		.dawn_active = energy_active && trace->root_choice.dawn_reserve,
		.dawn = dawn,
		.allocation = allocation,
		.direction = applied->proposal,
		.raw_direction = raw->proposal};
	if (trace->directions_enabled) {
		/* Same pre-execution snapshot as the candidates. Own-root cell coverage
		 * differs from the three-pixel collision test and needs its own record.
		 */
		uint8_t *const cells = trace->bids[trace->count - 1U].root_cells;
		for (uint16_t n = 0U; n < world->node_count; ++n) {
			const struct picosystem_garden_node *const node = &world->nodes[n];
			if ((node->plant_index != o->plant_index) ||
			    (node->kind != PICOSYSTEM_GARDEN_NODE_ROOT)) {
				continue;
			}
			const unsigned int column = (node->x - PICOSYSTEM_GARDEN_ORIGIN_X_PIXELS) /
						    PICOSYSTEM_GARDEN_CELL_PIXELS;
			const unsigned int row = (node->y - PICOSYSTEM_GARDEN_SOIL_TOP_PIXELS) /
						 PICOSYSTEM_GARDEN_CELL_PIXELS;
			const unsigned int cell = row * PICOSYSTEM_GARDEN_GRID_COLUMNS + column;
			cells[cell / 8U] |= (uint8_t)(1U << (cell % 8U));
		}
	}
	return 0;
}

int toy_factory_garden_plant_directions_publish(const struct toy_factory_garden_plant_trace *trace,
						const struct picosystem_garden_world *world,
						FILE *stream)
{
	if ((trace == NULL) || (world == NULL) || (stream == NULL) || !trace->directions_enabled ||
	    !trace->reproduction.ecology_step || (trace->count > PICOSYSTEM_GARDEN_MAX_NODES)) {
		return -EINVAL;
	}
	fprintf(stream, "{\"tick\":%" PRIu32 ",\"bids\":[", world->logic_tick_count);
	for (uint16_t i = 0U; i < trace->count; ++i) {
		const struct toy_factory_garden_plant_bid *const b = &trace->bids[i];
		const struct picosystem_garden_agent_observation *const o = &b->observation;
		fprintf(stream, "%s{\"id\":%" PRIu32 ",\"tip\":%u,\"at\":[%u,%u],\"order\":[",
			i ? "," : "", b->lineage, o->tip_index, o->tip_x, o->tip_y);
		for (uint8_t c = 0U; c < b->direction.candidate_count; ++c) {
			fprintf(stream, "%s%u", c ? "," : "", b->direction.candidate_order[c]);
		}
		if (trace->root_choice.wet_direction) {
			fputs("],\"raw_order\":[", stream);
			for (uint8_t c = 0U; c < b->raw_direction.candidate_count; ++c) {
				fprintf(stream, "%s%u", c ? "," : "",
					b->raw_direction.candidate_order[c]);
			}
		}
		fputs("],\"candidates\":[", stream);
		for (uint8_t c = 0U; c < o->candidate_count; ++c) {
			const struct picosystem_garden_agent_candidate *const p = &o->candidates[c];
			fprintf(stream, "%s[%d,%d,%u,%u,%u,%u,%u,%u]", c ? "," : "", p->delta_x,
				p->delta_y, p->x, p->y, p->light, p->moisture, p->clearance_squared,
				p->flags);
		}
		fputs("],\"root_cells\":\"", stream);
		for (size_t c = 0U; c < sizeof(b->root_cells); ++c) {
			fprintf(stream, "%02x", (unsigned int)b->root_cells[c]);
		}
		fputs("\"}", stream);
	}
	fputs("]}\n", stream);
	return ferror(stream) ? -EIO : 0;
}

int toy_factory_garden_plant_trace_publish(struct toy_factory_garden_plant_trace *trace,
					   const struct picosystem_garden_world *world)
{
	if ((trace == NULL) || (trace->stream == NULL) || (world == NULL) ||
	    !trace->reproduction.ecology_step || (trace->count > PICOSYSTEM_GARDEN_MAX_NODES) ||
	    (trace->reproduction.count > PICOSYSTEM_GARDEN_MAX_PLANTS)) {
		return -EINVAL;
	}
	FILE *const out = trace->stream;
	fprintf(out, "{\"tick\":%" PRIu32 ",", world->logic_tick_count);
	if (trace->scope != TOY_FACTORY_GARDEN_TRACE_FOUNDERS) {
		toy_factory_garden_climate_print(out, world);
	}
	if ((trace->scope == TOY_FACTORY_GARDEN_TRACE_ORDERED) ||
	    (trace->scope == TOY_FACTORY_GARDEN_TRACE_CHOICE) ||
	    (trace->scope == TOY_FACTORY_GARDEN_TRACE_ENERGY) || has_afternoon(trace->scope)) {
		/* No compaction occurs between reproduction and publication. Preserve
		 * the actual array independently of the traversal in reproduction[].
		 */
		fputs("\"plant_order\":[", out);
		for (uint8_t i = 0U; i < world->plant_count; ++i) {
			fprintf(out, "%s%" PRIu32, i ? "," : "", world->plants[i].lineage_id);
		}
		fputs("],", out);
	}
	fputs("\"bids\":[", out);
	for (uint16_t i = 0U; i < trace->count; ++i) {
		const struct toy_factory_garden_plant_bid *const b = &trace->bids[i];
		const struct picosystem_garden_agent_observation *const o = &b->observation;
		uint8_t available = 0U;
		for (uint8_t c = 0U; c < o->candidate_count; ++c) {
			available += (o->candidates[c].flags &
				      PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE)
					     ? 1U
					     : 0U;
		}
		fprintf(out,
			"%s{\"id\":%" PRIu32 ",\"tip\":%u,\"tissue\":%u,\"depth\":%u,"
			"\"maximum_depth\":%u,\"flower_depth\":%u,\"nodes\":%u,\"roots\":%u,"
			"\"shoots\":%u,\"energy\":%u,\"water\":%u,\"available\":%u,"
			"\"raw_action\":%u,\"action\":%u,\"priority\":%d",
			i ? "," : "", b->lineage, o->tip_index, o->tissue_kind, o->depth,
			o->maximum_depth, o->flower_depth, o->plant_node_count, o->root_node_count,
			o->shoot_node_count, o->stored_energy, o->stored_water, available,
			b->raw_action, b->action, b->priority);
		if ((trace->scope == TOY_FACTORY_GARDEN_TRACE_CHOICE) ||
		    (trace->scope == TOY_FACTORY_GARDEN_TRACE_ENERGY) ||
		    has_afternoon(trace->scope)) {
			fprintf(out,
				",\"raw_priority\":%d,\"water_gate\":{\"active\":%s,"
				"\"allowed\":%s,\"cost\":%" PRIu32 ",\"upkeep\":%" PRIu32
				",\"reserve\":%" PRIu32 ",\"wet_root\":%s,\"tip_moisture\":%u,"
				"\"destination\":",
				b->raw_priority, b->water_active ? "true" : "false",
				(!b->water_active || b->water.water_allowed) ? "true" : "false",
				b->water.water_cost, b->water.water_upkeep, b->water.water_reserve,
				b->water.wet_root ? "true" : "false", o->tip_moisture);
			if (b->water.destination == PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE) {
				fputs("null}", out);
			} else {
				const struct picosystem_garden_agent_candidate *const c =
					&o->candidates[b->water.destination];
				fprintf(out, "[%d,%d,%u]}", c->x, c->y, c->moisture);
			}
		}
		if ((trace->scope == TOY_FACTORY_GARDEN_TRACE_ENERGY) ||
		    has_afternoon(trace->scope)) {
			const struct toy_factory_garden_reserve_forecast *const e =
				&b->water.energy;
			fprintf(out,
				",\"energy_gate\":{\"active\":%s,\"allowed\":%s,\"forecast_"
				"allowed\":%s,"
				"\"age\":%u,\"sun_phase\":%u,\"maintenance_phase\":%u,\"income\":%"
				"u,\"vigor\":%d,"
				"\"post_nodes\":%" PRIu32 ",\"cost\":%" PRIu32
				",\"maintenance\":%" PRIu32 ",\"daylight_steps\":%" PRIu32
				",\"daylight_credit\":%" PRIu32 ",\"daylight_upkeep\":%" PRIu32
				",\"night_upkeep\":%" PRIu32 ",\"projected_sunset\":%" PRId32 "}",
				b->energy_active ? "true" : "false",
				(!b->energy_active || e->allowed) ? "true" : "false",
				e->allowed ? "true" : "false", o->age_ecology_ticks, o->sun_phase,
				o->maintenance_phase, o->last_energy_income, o->vigor,
				e->post_nodes, e->growth_cost, e->maintenance_cost,
				e->daylight_steps, e->daylight_credit, e->daylight_upkeep,
				e->night_upkeep, e->projected_sunset);
		}
		if (has_afternoon(trace->scope)) {
			fprintf(out,
				",\"afternoon_gate\":{\"active\":%s,\"allowed\":%s,\"applies\":%s,"
				"\"forecast_allowed\":%s,\"maintenance_before\":%" PRIu32
				",\"margin\":%" PRId32 "}",
				b->afternoon_active ? "true" : "false",
				(!b->afternoon_active || b->afternoon.allowed) ? "true" : "false",
				b->afternoon.applies ? "true" : "false",
				b->afternoon.allowed ? "true" : "false",
				b->afternoon.maintenance_before, b->afternoon.margin);
		}
		if (has_daylight(trace->scope)) {
			fprintf(out,
				",\"daylight_gate\":{\"active\":%s,\"allowed\":%s,\"applies\":%s,"
				"\"forecast_allowed\":%s,\"sun_strength\":%u,\"useful_steps\":"
				"%" PRIu32 ",\"daylight_credit\":%" PRIu32
				",\"projected_sunset\":%" PRId32 "}",
				b->daylight_active ? "true" : "false",
				(!b->daylight_active || b->daylight.allowed) ? "true" : "false",
				b->daylight.applies ? "true" : "false",
				b->daylight.allowed ? "true" : "false", o->sun_strength,
				b->daylight.useful_steps, b->daylight.daylight_credit,
				b->daylight.projected_sunset);
		}
		if (trace->scope == TOY_FACTORY_GARDEN_TRACE_DAWN) {
			fprintf(out,
				",\"dawn_gate\":{\"active\":%s,\"allowed\":%s,\"applies\":%s,"
				"\"forecast_allowed\":%s,\"estimate_available\":%s,"
				"\"first_light_phase\":%u,\"payment_phase\":%u,\"reserve\":%" PRIu32
				",\"projected_margin\":%" PRId32 ",\"stores_applies\":%s,"
				"\"stores_margin\":%" PRId32 "}",
				b->dawn_active ? "true" : "false",
				(!b->dawn_active || b->dawn.allowed) ? "true" : "false",
				b->dawn.applies ? "true" : "false",
				b->dawn.allowed ? "true" : "false",
				b->dawn.estimate_available ? "true" : "false",
				b->dawn.first_light_phase, b->dawn.payment_phase, b->dawn.reserve,
				b->dawn.projected_margin, b->dawn.stores_applies ? "true" : "false",
				b->dawn.stores_margin);
		}
		if (trace->budget_mode != TOY_FACTORY_GARDEN_BUDGET_LEGACY) {
			fprintf(out,
				",\"budget\":{\"leader\":%u,\"remaining\":%u,\"required\":%u,"
				"\"flower\":%s,\"allocates\":%s,\"allowed\":%s}",
				b->budget.leader, b->budget.remaining, b->budget.required,
				b->budget.flower ? "true" : "false",
				b->budget.allocates ? "true" : "false",
				b->budget.allowed ? "true" : "false");
		}
		if (trace->root_allocation.version != 0U) {
			fprintf(out,
				",\"allocation\":{\"active\":%s,\"eligible\":%s,\"prefer\":%s,"
				"\"water_income\":%u}",
				b->allocation.active ? "true" : "false",
				b->allocation.eligible ? "true" : "false",
				b->allocation.prefer ? "true" : "false", o->last_water_income);
		}
		fputc('}', out);
	}
	fputs("],\"reproduction\":[", out);
	bool first = true;
	for (uint8_t i = 0U; i < trace->reproduction.count; ++i) {
		const struct picosystem_garden_reproduction_visit *const v =
			&trace->reproduction.visits[i];
		if (!is_selected(trace, v->lineage)) {
			continue;
		}
		fprintf(out,
			"%s{\"id\":%" PRIu32 ",\"blockers\":%u,\"energy\":%u,\"water\":%u,"
			"\"energy_required\":%" PRId32 ",\"water_required\":%" PRId32 ","
			"\"immature\":%u,\"spent\":%u,\"ready\":%u,\"flower\":%u,"
			"\"cooldown\":%u,\"bank\":%u,\"stress\":%u,\"sun\":%u,\"produced\":%s}",
			first ? "" : ",", v->lineage, v->blockers, v->energy, v->water,
			v->energy_required, v->water_required, v->immature_flowers,
			v->spent_flowers, v->ready_flowers, v->flower_index, v->cooldown,
			v->seed_count, v->stress, v->sun_strength, v->produced ? "true" : "false");
		first = false;
	}
	fputs("],\"bodies\":[", out);
	first = true;
	for (uint8_t i = 0U; i < world->plant_count; ++i) {
		const struct picosystem_garden_plant *const p = &world->plants[i];
		if (!is_selected(trace, p->lineage_id) ||
		    (p->flags & PICOSYSTEM_GARDEN_PLANT_DEAD)) {
			continue;
		}
		unsigned int roots = 0U, flowers = 0U;
		uint8_t maximum_depth = 0U;
		for (uint16_t n = 0U; n < world->node_count; ++n) {
			const struct picosystem_garden_node *const node = &world->nodes[n];
			if (node->plant_index == i) {
				roots += (node->kind == PICOSYSTEM_GARDEN_NODE_ROOT) ? 1U : 0U;
				flowers += (node->flags & PICOSYSTEM_GARDEN_NODE_FLOWER) ? 1U : 0U;
				if ((node->kind == PICOSYSTEM_GARDEN_NODE_STEM) &&
				    (node->depth > maximum_depth)) {
					maximum_depth = node->depth;
				}
			}
		}
		fprintf(out,
			"%s{\"id\":%" PRIu32 ",\"species\":%u,\"nodes\":%u,\"roots\":%u,"
			"\"flowers\":%u,\"maximum_stem_depth\":%u,\"tips\":[",
			first ? "" : ",", p->lineage_id, p->species_id, p->node_count, roots,
			flowers, maximum_depth);
		first = false;
		bool first_tip = true;
		for (uint16_t n = 0U; n < world->node_count; ++n) {
			const struct picosystem_garden_node *const node = &world->nodes[n];
			if ((node->plant_index == i) &&
			    (node->flags & PICOSYSTEM_GARDEN_NODE_TIP)) {
				fprintf(out, "%s[%u,%u,%u]", first_tip ? "" : ",", n, node->kind,
					node->depth);
				first_tip = false;
			}
		}
		fputs("]}", out);
	}
	fputs("]}\n", out);
	return ferror(out) ? -EIO : 0;
}
