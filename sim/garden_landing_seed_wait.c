/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_seed_wait.h"

#include <errno.h>

#define PURCHASE_PERIOD                                                                            \
	(PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR * PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR)

static uint32_t since(const struct toy_factory_garden_seed_wait *state, uint32_t lineage,
		      uint32_t birth)
{
	for (uint8_t i = 0U; i < state->count; ++i) {
		if (state->entries[i].lineage == lineage) {
			return state->entries[i].since;
		}
	}
	return birth;
}

int toy_factory_garden_seed_wait_init(const struct picosystem_garden_world *world, uint32_t after,
				      struct toy_factory_garden_seed_wait *state)
{
	if ((world == NULL) || (state == NULL)) {
		return -EINVAL;
	}
	if ((world->logic_tick_count != 0U) ||
	    (world->plant_count > PICOSYSTEM_GARDEN_MAX_PLANTS) ||
	    (after % PURCHASE_PERIOD != 0U)) {
		return -ERANGE;
	}
	struct toy_factory_garden_seed_wait result = {.after = after};
	if (after != 0U) {
		result.count = world->plant_count;
		for (uint8_t i = 0U; i < result.count; ++i) {
			result.entries[i].lineage = world->plants[i].lineage_id;
		}
	}
	*state = result;
	return 0;
}

int toy_factory_garden_seed_wait_validate(const struct toy_factory_garden_seed_wait *state,
					  const struct picosystem_garden_world *world)
{
	if ((state == NULL) || (world == NULL)) {
		return -EINVAL;
	}
	if ((state->after % PURCHASE_PERIOD != 0U) ||
	    (world->plant_count > PICOSYSTEM_GARDEN_MAX_PLANTS) ||
	    (state->count != (state->after != 0U ? world->plant_count : 0U))) {
		return -ERANGE;
	}
	for (uint8_t i = 0U; i < PICOSYSTEM_GARDEN_MAX_PLANTS; ++i) {
		const struct toy_factory_garden_seed_wait_entry *const e = &state->entries[i];
		if (i < state->count) {
			if ((e->lineage != world->plants[i].lineage_id) || (e->lineage == 0U) ||
			    (e->since > world->logic_tick_count) ||
			    (e->since % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR != 0U)) {
				return -ERANGE;
			}
		} else if ((e->lineage != 0U) || (e->since != 0U)) {
			return -ERANGE;
		}
	}
	return 0;
}

int toy_factory_garden_seed_wait_order(const struct picosystem_garden_world *world, uint8_t *order,
				       size_t capacity, const void *context)
{
	const struct toy_factory_garden_seed_wait *const state = context;
	if ((world == NULL) || (order == NULL) || (state == NULL)) {
		return -EINVAL;
	}
	if ((state->count > PICOSYSTEM_GARDEN_MAX_PLANTS) ||
	    (world->plant_count > PICOSYSTEM_GARDEN_MAX_PLANTS) ||
	    (capacity < world->plant_count)) {
		return -ERANGE;
	}
	uint32_t stamps[PICOSYSTEM_GARDEN_MAX_PLANTS];
	for (uint8_t i = 0U; i < world->plant_count; ++i) {
		stamps[i] = since(state, world->plants[i].lineage_id, world->logic_tick_count);
		order[i] = i;
	}
	/* Eligibility stays in the production loop. An ineligible older parent
	 * is skipped rather than reserving a slot or changing another's resources.
	 */
	for (uint8_t i = 1U; i < world->plant_count; ++i) {
		const uint8_t selected = order[i];
		uint8_t j = i;
		while (j > 0U) {
			const uint8_t previous = order[j - 1U];
			if ((stamps[previous] < stamps[selected]) ||
			    ((stamps[previous] == stamps[selected]) &&
			     (world->plants[previous].lineage_id <
			      world->plants[selected].lineage_id))) {
				break;
			}
			order[j] = previous;
			--j;
		}
		order[j] = selected;
	}
	return 0;
}

void toy_factory_garden_seed_wait_advance(const struct toy_factory_garden_seed_wait *state,
					  const struct picosystem_garden_world *world,
					  struct toy_factory_garden_seed_wait *next)
{
	struct toy_factory_garden_seed_wait result = {.after = state->after,
						      .count = world->plant_count};
	for (uint8_t i = 0U; i < result.count; ++i) {
		const uint32_t id = world->plants[i].lineage_id;
		result.entries[i] = (struct toy_factory_garden_seed_wait_entry){
			.lineage = id, .since = since(state, id, world->logic_tick_count)};
		/* Age-zero seeds persist between ecology steps; never count those
		 * intervening logic ticks as additional paid purchases.
		 */
		if (world->logic_tick_count % PURCHASE_PERIOD == 0U) {
			for (uint8_t s = 0U; s < world->seed_count; ++s) {
				if ((world->seeds[s].parent_lineage_id == id) &&
				    (world->seeds[s].age_ecology_ticks == 0U)) {
					result.entries[i].since = world->logic_tick_count;
				}
			}
		}
	}
	*next = result;
}

static uint32_t hash_word(uint32_t hash, uint32_t value)
{
	for (uint8_t b = 0U; b < 4U; ++b) {
		hash = (hash ^ (uint8_t)(value >> (8U * b))) * UINT32_C(16777619);
	}
	return hash;
}

uint32_t toy_factory_garden_seed_wait_hash(const struct toy_factory_garden_seed_wait *state,
					   uint32_t base)
{
	if (state->after == 0U) {
		return base;
	}
	uint32_t hash = UINT32_C(2166136261);
	const uint8_t tag[] = {'G', 'S', 'W', '1'};
	for (size_t i = 0U; i < sizeof(tag); ++i) {
		hash = (hash ^ tag[i]) * UINT32_C(16777619);
	}
	hash = hash_word(hash_word(hash_word(hash, base), state->after), state->count);
	for (uint8_t i = 0U; i < state->count; ++i) {
		hash = hash_word(hash_word(hash, state->entries[i].lineage),
				 state->entries[i].since);
	}
	return hash;
}
