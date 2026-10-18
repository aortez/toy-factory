/* SPDX-License-Identifier: Apache-2.0 */
#include "research_fallback.h"
#include "garden_leaf_family.h"
#include "garden_dispersal.h"

#include <assert.h>
#include <errno.h>
#include <string.h>

/* Exhaust the active draws, including aliases and the late-support boundary.
 * The expected rule is calculated from per-destination counts, not production rank.
 */
void research_fallback_tests(void)
{
	struct picosystem_garden_world world = {.plant_count = 6U};
	const uint8_t columns[] = {13U, 4U, 7U, 10U, 17U, 20U};
	for (uint8_t i = 0U; i < 6U; ++i) {
		world.plants[i].lineage_id = i + 2U;
		world.plants[i].base_column = columns[i];
	}
	struct toy_factory_leaf_family_owners owners = {
		.count = 7U, .founders = 3U, .root = {0U, 1U, 2U, 3U, 1U, 2U, 3U, 2U}};
	const struct research_fallback_route route = {.owners = &owners};
	const struct toy_factory_garden_placement_config config = {.version = 1U, .enabled = 1U};
	struct toy_factory_garden_placement_audit audit = {0};
	struct toy_factory_garden_placement_context base = {
		.world = &world, .config = &config, .audit = &audit};
	const uint32_t ticks[] = {130560U, 626580U, 626581U};
	unsigned int changed = 0U, clear = 0U, blocked = 0U, aliases = 0U;
	for (uint8_t dead = 0U; dead < 2U; ++dead) {
		world.plants[2].flags = dead ? PICOSYSTEM_GARDEN_PLANT_DEAD : 0U;
		for (uint8_t t = 0U; t < 3U; ++t) {
			world.logic_tick_count = ticks[t];
			const uint8_t count = picosystem_garden_dispersal_choices_at(ticks[t]);
			assert(count == (t == 2U ? 14U : 6U));
			for (uint8_t origin = 0U; origin < 28U; ++origin) {
				world.plants[0].base_column = origin;
				for (int8_t trait = -2; trait <= 2; ++trait) {
					world.plants[0].genome.dispersal = trait;
					struct picosystem_garden_seed_placement o = {
						.parent = 2U,
						.logic_tick = ticks[t],
						.origin = origin,
						.dispersal = trait};
					uint8_t counts[14] = {0};
					for (uint8_t j = 0U; j < count; ++j) {
						o.columns[j] =
							picosystem_garden_dispersed_column_at(
								origin, trait, j, ticks[t]);
						for (uint8_t p = 0U; p < world.plant_count; ++p) {
							const int gap = (int)o.columns[j] -
									world.plants[p].base_column;
							if (gap > -3 && gap < 3) {
								++counts[j];
							}
						}
						if (counts[j] != 0U) {
							o.blocked_choices |= (uint16_t)(1U << j);
						}
						if (j > 0U && o.columns[j] == o.columns[j - 1U]) {
							++aliases;
						}
					}
					for (uint8_t draw = 0U; draw < count; ++draw) {
						o.random = draw;
						uint8_t expected;
						audit.count = 0U;
						assert(research_fallback_decide(&o, &expected,
										&base, NULL) == 0);
						if (o.blocked_choices == (1U << count) - 1U) {
							++blocked;
							for (uint8_t off = 1U; off < count; ++off) {
								const uint8_t j =
									(uint8_t)((draw + off) %
										  count);
								if (counts[j] < counts[expected]) {
									expected = j;
								}
							}
						} else {
							++clear;
						}
						changed += expected != draw ? 1U : 0U;
						uint8_t selected = UINT8_MAX;
						const struct picosystem_garden_world saved = world;
						audit.count = 0U;
						assert(research_fallback_decide(
							       &o, &selected, &base, &route) == 0);
						assert(selected == expected && audit.count == 1U &&
						       audit.purchases[0].selected == expected);
						assert(memcmp(&world, &saved, sizeof(world)) == 0);
						/* Other roots retain exactly the original
						 * selection. */
						owners.root[2] = 1U;
						audit.count = 0U;
						assert(research_fallback_decide(
							       &o, &selected, &base, &route) == 0);
						assert(toy_factory_garden_placement_choose(
							       &o, 1U, &expected) == 0 &&
						       selected == expected);
						owners.root[2] = 2U;
					}
				}
			}
		}
	}
	assert(changed > 0U && clear > 0U && blocked > 0U && aliases > 0U);
	/* Known all-blocked purchase: two blockers at column 6, one at column 20. */
	world.logic_tick_count = 130560U;
	world.plants[0].base_column = 13U;
	world.plants[0].genome.dispersal = 0;
	struct picosystem_garden_seed_placement o = {.parent = 2U,
						     .origin = 13U,
						     .logic_tick = 130560U,
						     .random = 4U,
						     .blocked_choices = 63U,
						     .columns = {8U, 18U, 7U, 19U, 6U, 20U}};
	uint8_t selected = UINT8_MAX;
	audit.count = 0U;
	assert(research_fallback_decide(&o, &selected, &base, &route) == 0 && selected == 5U);
	/* Newborn can inherit a dead/absent parent's stable root before ledger update. */
	world.plants[0].lineage_id = o.parent = 8U;
	world.plants[0].parent_lineage_id = 2U;
	audit.count = 0U;
	assert(research_fallback_decide(&o, &selected, &base, &route) == 0 && selected == 5U);
	world.plants[0].parent_lineage_id = 0U;
	selected = UINT8_MAX;
	assert(research_fallback_decide(&o, &selected, &base, &route) == -ERANGE);
	assert(selected == UINT8_MAX && audit.count == 1U);
	world.plants[0].parent_lineage_id = 2U;
	o.blocked_choices = 0U;
	assert(research_fallback_decide(&o, &selected, &base, &route) == -ERANGE);
	assert(selected == UINT8_MAX && audit.count == 1U);
	o.blocked_choices = 63U;
	audit.count = PICOSYSTEM_GARDEN_MAX_SEEDS;
	assert(research_fallback_decide(&o, &selected, &base, &route) == -ENOSPC);
	assert(selected == UINT8_MAX);
}
