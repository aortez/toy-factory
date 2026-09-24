/* SPDX-License-Identifier: Apache-2.0 */
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#include "garden_full_pool.h"

bool picosystem_garden_full_pool_active(bool enabled, uint32_t tick)
{
	return enabled && tick > PICOSYSTEM_GARDEN_FULL_POOL_AFTER;
}

int picosystem_garden_full_pool_parse(const char *name, bool *enabled)
{
	if ((name == NULL) || (enabled == NULL) || *enabled ||
	    (strcmp(name, "nonallocating") != 0)) {
		return -EINVAL;
	}
	*enabled = true;
	return 0;
}

int picosystem_garden_full_pool_check(struct picosystem_garden_full_pool_audit *audit,
				      uint32_t lineage, uint16_t node, uint8_t action,
				      bool allocates)
{
	if ((audit == NULL) || !audit->enabled || (lineage == 0U) || (node >= 512U) ||
	    (action > 2U) || (allocates && (action != 1U))) {
		return -EINVAL;
	}
	if (audit->overflow || (audit->count >= PICOSYSTEM_GARDEN_FULL_POOL_EVENTS)) {
		audit->overflow = true;
		return -EOVERFLOW;
	}
	if ((audit->evaluated[action] == UINT32_MAX) ||
	    (allocates && (audit->denied == UINT32_MAX))) {
		audit->overflow = true;
		return -EOVERFLOW;
	}
	audit->events[audit->count++] = (struct picosystem_garden_full_pool_event){
		.lineage = lineage,
		.node = node,
		.action = action,
		.allocates = allocates,
	};
	++audit->evaluated[action];
	if (allocates) {
		++audit->denied;
		return -ECANCELED;
	}
	return 0;
}

int picosystem_garden_full_pool_print(const struct picosystem_garden_full_pool_audit *audit,
				      uint32_t tick)
{
	if (audit == NULL) {
		return -EINVAL;
	}
	if (!audit->enabled) {
		return 0;
	}
	if (audit->overflow || (audit->count > PICOSYSTEM_GARDEN_FULL_POOL_EVENTS) ||
	    (audit->denied > audit->evaluated[1])) {
		return -EOVERFLOW;
	}
	if (printf("\"full_pool\":{\"rule\":\"%s\",\"after\":%u,\"active\":%s,"
		   "\"evaluated\":[%" PRIu32 ",%" PRIu32 ",%" PRIu32 "],\"denied\":%" PRIu32
		   ",\"overflow\":%s,\"events\":[",
		   PICOSYSTEM_GARDEN_FULL_POOL_RULE, PICOSYSTEM_GARDEN_FULL_POOL_AFTER,
		   picosystem_garden_full_pool_active(audit->enabled, tick) ? "true" : "false",
		   audit->evaluated[0], audit->evaluated[1], audit->evaluated[2], audit->denied,
		   audit->overflow ? "true" : "false") < 0) {
		return -EIO;
	}
	for (uint8_t i = 0U; i < audit->count; ++i) {
		const struct picosystem_garden_full_pool_event *const event = &audit->events[i];
		if (printf("%s{\"id\":%" PRIu32 ",\"node\":%u,\"action\":%u,\"allocates\":%s}",
			   i == 0U ? "" : ",", event->lineage, event->node, event->action,
			   event->allocates ? "true" : "false") < 0) {
			return -EIO;
		}
	}
	return printf("]},") < 0 ? -EIO : 0;
}
