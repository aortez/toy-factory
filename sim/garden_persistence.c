/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_persistence.h"

#include <errno.h>

static bool established(const struct toy_factory_garden_persistence_lifetime *p, uint32_t end)
{
	const uint32_t due = p->birth + TOY_FACTORY_GARDEN_PERSISTENCE_DAY;
	return (due <= end) &&
	       ((p->death == TOY_FACTORY_GARDEN_PERSISTENCE_ALIVE) || (p->death > due));
}

int toy_factory_garden_persistence_score(
	const struct toy_factory_garden_persistence_lifetime *records, size_t count,
	uint32_t pending_seeds, uint32_t start, uint32_t end, uint32_t stop,
	struct toy_factory_garden_persistence_score *out)
{
	if ((records == NULL) || (out == NULL) ||
	    (count > TOY_FACTORY_GARDEN_PERSISTENCE_MAX_LINEAGES) || (start >= end) ||
	    (stop > TOY_FACTORY_GARDEN_PERSISTENCE_MAX_TICKS) ||
	    (end >
	     TOY_FACTORY_GARDEN_PERSISTENCE_MAX_TICKS - 2U * TOY_FACTORY_GARDEN_PERSISTENCE_DAY) ||
	    (stop != end + 2U * TOY_FACTORY_GARDEN_PERSISTENCE_DAY) ||
	    ((start % TOY_FACTORY_GARDEN_PERSISTENCE_STEP) != 0U) ||
	    ((end % TOY_FACTORY_GARDEN_PERSISTENCE_STEP) != 0U) || (pending_seeds > 16U)) {
		return -EINVAL;
	}
	for (size_t id = 1U; id <= count; ++id) {
		const struct toy_factory_garden_persistence_lifetime *p = &records[id];
		if ((p->birth > stop) || ((p->birth % TOY_FACTORY_GARDEN_PERSISTENCE_STEP) != 0U) ||
		    ((p->death != TOY_FACTORY_GARDEN_PERSISTENCE_ALIVE) &&
		     ((p->death < p->birth) || (p->death > stop) ||
		      ((p->death % TOY_FACTORY_GARDEN_PERSISTENCE_STEP) != 0U))) ||
		    (p->parent >= id) ||
		    ((p->parent != 0U) && (records[p->parent].birth >= p->birth))) {
			return -ERANGE;
		}
	}
	struct toy_factory_garden_persistence_score result = {.key = {-1, 0, 0, 0, 0}};
	bool renewing[TOY_FACTORY_GARDEN_PERSISTENCE_MAX_LINEAGES + 1U] = {false};
	if (pending_seeds != 0U) {
		result.key[0] = 0;
	}
	for (size_t id = 1U; id <= count; ++id) {
		const struct toy_factory_garden_persistence_lifetime *p = &records[id];
		if (p->death == TOY_FACTORY_GARDEN_PERSISTENCE_ALIVE) {
			if (result.key[0] < 0) {
				result.key[0] = 0;
			}
			if ((p->parent != 0U) && established(p, stop)) {
				result.key[0] = 1;
			}
		}
		if ((p->parent == 0U) || !established(p, end)) {
			continue;
		}
		const uint32_t due = p->birth + TOY_FACTORY_GARDEN_PERSISTENCE_DAY;
		const uint32_t first =
			due > start ? due : start + TOY_FACTORY_GARDEN_PERSISTENCE_STEP;
		const uint32_t last =
			(p->death != TOY_FACTORY_GARDEN_PERSISTENCE_ALIVE) && (p->death <= end)
				? p->death - TOY_FACTORY_GARDEN_PERSISTENCE_STEP
				: end;
		const uint32_t ticks =
			last >= first ? last - first + TOY_FACTORY_GARDEN_PERSISTENCE_STEP : 0U;
		result.key[2] += ticks;
		if (due > start) {
			++result.key[4];
			const struct toy_factory_garden_persistence_lifetime *parent =
				&records[p->parent];
			if ((parent->parent != 0U) && established(parent, end)) {
				result.key[1] += ticks;
				if (!renewing[p->parent]) {
					renewing[p->parent] = true;
					++result.key[3];
				}
			}
		}
	}
	*out = result;
	return 0;
}
