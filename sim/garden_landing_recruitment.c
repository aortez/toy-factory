/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_recruitment.h"

#include <errno.h>
#include <inttypes.h>

static void print_transfer(FILE *stream, const struct picosystem_garden_death_resource *r)
{
	fprintf(stream, "[%u,%u,%u,%u,%u,%u]", r->before, r->income, r->overflow, r->upkeep_due,
		r->upkeep_paid, r->discarded);
}

int toy_factory_garden_recruitment_print(FILE *stream, const struct picosystem_garden_world *world,
					 const struct toy_factory_garden_lifetimes *lifetimes,
					 const struct picosystem_garden_seed_audit *seeds,
					 const struct picosystem_garden_resource_audit *resources)
{
	if ((stream == NULL) || (world == NULL) || (lifetimes == NULL) || (seeds == NULL) ||
	    (resources == NULL) || !seeds->ecology_step || !resources->uptake.ecology_step ||
	    (seeds->count > PICOSYSTEM_GARDEN_MAX_SEEDS) ||
	    (resources->uptake.count > PICOSYSTEM_GARDEN_MAX_PLANTS)) {
		return -EINVAL;
	}
	fprintf(stream, "{\"tick\":%" PRIu32 ",\"seeds\":[", world->logic_tick_count);
	for (uint8_t i = 0U; i < seeds->count; ++i) {
		const struct picosystem_garden_seed_attempt *const a = &seeds->attempts[i];
		unsigned int open = 0U;
		for (uint8_t c = 0U; c < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++c) {
			open += (a->sites[c] == 0U) ? 1U : 0U;
		}
		fprintf(stream, "%s[%" PRIu32 ",%u,%u,%u,%u,%u,%u,%u,%u,%" PRIu32 ",%d]",
			i ? "," : "", a->parent, a->age, a->column, a->blockers, a->moisture,
			a->light, a->plants, a->nodes, a->outcome, a->child,
			(a->outcome == PICOSYSTEM_GARDEN_SEED_EXPIRED) ? -1 : (int)open);
	}
	fputs("],\"plants\":[", stream);
	bool first = true;
	for (uint8_t i = 0U; i < world->plant_count; ++i) {
		const struct picosystem_garden_plant *const p = &world->plants[i];
		if ((p->lineage_id == 0U) || (p->lineage_id > lifetimes->count)) {
			return -EFAULT;
		}
		const struct toy_factory_garden_lifetime *const life =
			&lifetimes->records[p->lineage_id];
		if ((life->parent_id == 0U) || (world->logic_tick_count < life->birth_tick) ||
		    (world->logic_tick_count - life->birth_tick >
		     TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS) ||
		    ((life->death_cause != TOY_FACTORY_GARDEN_LIFETIME_CAUSES) &&
		     (life->death_tick != world->logic_tick_count))) {
			continue;
		}
		fprintf(stream, "%s{\"id\":%" PRIu32 ",\"birth\":%" PRIu32 ",\"stages\":[",
			first ? "" : ",", p->lineage_id, life->birth_tick);
		first = false;
		for (uint8_t stage = 0U; stage < PICOSYSTEM_GARDEN_RESOURCE_STAGE_COUNT; ++stage) {
			if (resources->stages[stage].count > PICOSYSTEM_GARDEN_MAX_PLANTS) {
				return -EFAULT;
			}
			const struct picosystem_garden_resource_plant *found = NULL;
			for (uint8_t j = 0U; j < resources->stages[stage].count; ++j) {
				if (resources->stages[stage].plants[j].lineage_id ==
				    p->lineage_id) {
					found = &resources->stages[stage].plants[j];
					break;
				}
			}
			if (stage != 0U) {
				fputc(',', stream);
			}
			if (found == NULL) {
				fputs("null", stream);
			} else {
				fprintf(stream, "[%u,%u,%u,%u,%u]", found->energy, found->water,
					found->stress, found->flags, found->nodes);
			}
		}
		fputs("],\"uptake\":", stream);
		const struct picosystem_garden_death_event *receipt = NULL;
		for (uint8_t j = 0U; j < resources->uptake.count; ++j) {
			if (resources->uptake.events[j].lineage_id == p->lineage_id) {
				receipt = &resources->uptake.events[j];
				break;
			}
		}
		if (receipt == NULL) {
			fputs("null", stream);
		} else {
			fputc('[', stream);
			print_transfer(stream, &receipt->energy);
			fputc(',', stream);
			print_transfer(stream, &receipt->water);
			fputc(']', stream);
		}
		unsigned int roots = 0U, leaves = 0U;
		for (uint16_t j = 0U; j < world->node_count; ++j) {
			const struct picosystem_garden_node *const node = &world->nodes[j];
			if (node->plant_index == i) {
				roots += (node->kind == PICOSYSTEM_GARDEN_NODE_ROOT) ? 1U : 0U;
				leaves += ((node->flags & PICOSYSTEM_GARDEN_NODE_LEAF) &&
					   (node->growth_progress >=
					    PICOSYSTEM_GARDEN_LEAF_ACTIVE_PROGRESS))
						  ? 1U
						  : 0U;
			}
		}
		fprintf(stream, ",\"roots\":%u,\"active_leaves\":%u}", roots, leaves);
	}
	fputs("]}\n", stream);
	return ferror(stream) ? -EIO : 0;
}
