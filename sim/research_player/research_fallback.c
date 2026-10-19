/* SPDX-License-Identifier: Apache-2.0 */
#include "research_fallback.h"
#include "garden_leaf_family.h"
#include "garden_dispersal.h"
#include "garden_daylight_policy.h"

#include <errno.h>

static int buyer_root(const struct picosystem_garden_world *world, uint32_t buyer,
		      const struct toy_factory_leaf_family_owners *owners, uint8_t *out)
{
	if (owners == NULL || owners->count > TOY_FACTORY_LEAF_FAMILY_MAX_LINEAGES ||
	    owners->founders < 2U || owners->founders > owners->count || buyer == 0U ||
	    buyer > TOY_FACTORY_LEAF_FAMILY_MAX_LINEAGES ||
	    world->plant_count > PICOSYSTEM_GARDEN_MAX_PLANTS) {
		return -EINVAL;
	}
	for (uint8_t i = 0U; i < world->plant_count; ++i) {
		const struct picosystem_garden_plant *const p = &world->plants[i];
		if (p->lineage_id != buyer) {
			continue;
		}
		if ((p->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) != 0U) {
			return -EINVAL;
		}
		const uint32_t parent = p->parent_lineage_id;
		if (buyer > owners->count &&
		    (parent == 0U || parent > owners->count || parent >= buyer)) {
			return -ERANGE;
		}
		const uint8_t root = owners->root[buyer <= owners->count ? buyer : parent];
		if (root == 0U || root > owners->founders) {
			return -ERANGE;
		}
		*out = root;
		return 0;
	}
	return -ENOENT;
}

static int choose(const struct picosystem_garden_world *world,
		  const struct picosystem_garden_seed_placement *o, uint8_t *choice)
{
	uint8_t ordinary;
	int err = toy_factory_garden_placement_choose(o, 1U, &ordinary);
	if (err != 0) {
		return err;
	}
	struct toy_factory_placement_scene scene = {.tick = world->logic_tick_count,
						    .count = world->plant_count};
	for (uint8_t i = 0U; i < world->plant_count; ++i) {
		const struct picosystem_garden_plant *const p = &world->plants[i];
		scene.plants[i] = (struct toy_factory_placement_plant){
			.lineage = p->lineage_id,
			.column = p->base_column,
			.trait = p->genome.dispersal,
			.dead = (p->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) != 0U};
	}
	struct toy_factory_placement_scores scores;
	err = toy_factory_placement_rank(&scene, o, ordinary, &scores);
	if (err != 0 || scores.legal != 0U) {
		return err;
	}
	if (*choice != ordinary) {
		return -EFAULT;
	}
	const uint8_t count = picosystem_garden_dispersal_choices_at(o->logic_tick);
	uint8_t selected = ordinary, best = UINT8_MAX;
	for (uint8_t offset = 0U; offset < count; ++offset) {
		const uint8_t index = (uint8_t)((ordinary + offset) % count);
		uint8_t blockers = 0U;
		for (uint8_t i = 0U; i < world->plant_count; ++i) {
			const int gap = (int)o->columns[index] - world->plants[i].base_column;
			if (gap > -3 && gap < 3) {
				++blockers;
			}
		}
		if (blockers < best) {
			best = blockers;
			selected = index;
		}
	}
	*choice = selected;
	return 0;
}

int research_fallback_decide(const struct picosystem_garden_seed_placement *o, uint8_t *choice,
			     const struct toy_factory_garden_placement_context *base,
			     const struct research_fallback_route *route)
{
	if (route == NULL) {
		return toy_factory_garden_placement_decide(o, choice, base);
	}
	if (o == NULL || choice == NULL || base == NULL || base->world == NULL ||
	    base->config == NULL || base->config->version != 1U || base->config->enabled != 1U ||
	    base->config->replace_after != 0U) {
		return -EINVAL;
	}
	uint8_t root;
	int err = buyer_root(base->world, o->parent, route->owners, &root);
	if (err != 0) {
		return err;
	}
	/* Publish any optional placement receipt only after the final choice. */
	if (base->audit != NULL && base->audit->count >= PICOSYSTEM_GARDEN_MAX_SEEDS) {
		return -ENOSPC;
	}
	struct toy_factory_garden_placement_context original = *base;
	original.audit = NULL;
	uint8_t selected;
	err = toy_factory_garden_placement_decide(o, &selected, &original);
	if (err == 0 && root == 2U) {
		err = choose(base->world, o, &selected);
	}
	if (err != 0) {
		return err;
	}
	if (base->audit != NULL) {
		base->audit->purchases[base->audit->count++] =
			(struct toy_factory_garden_placement_receipt){.observation = *o,
								      .selected = selected};
	}
	*choice = selected;
	return 0;
}
