/* SPDX-License-Identifier: Apache-2.0 */
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>

#include "garden_night_capacity.h"
#include "garden_world.h"

int picosystem_garden_night_project(uint16_t nodes, struct picosystem_garden_dark_budget *result)
{
	if (result == NULL) {
		return -EINVAL;
	}
	struct picosystem_garden_dark_budget budget;
	const int err = picosystem_garden_dark_project(256U, nodes, 0U, 117U, &budget);
	if ((err != 0) || !budget.supported || (budget.dark_steps != 149U) ||
	    (budget.payments != 37U)) {
		return -EINVAL;
	}
	*result = budget;
	return 0;
}

int picosystem_garden_night_check(struct picosystem_garden_night_audit *audit,
				  const struct picosystem_garden_dark_event *expense,
				  uint8_t expense_index)
{
	_Static_assert(PICOSYSTEM_GARDEN_NIGHT_EVENTS >= PICOSYSTEM_GARDEN_MAX_PLANTS,
		       "At most one winning growth proposal per plant and step");
	if ((audit == NULL) || (expense == NULL) ||
	    (expense_index >= PICOSYSTEM_GARDEN_DARK_EVENTS) ||
	    (expense->kind != PICOSYSTEM_GARDEN_EXPENSE_GROWTH) || expense->denied ||
	    expense->invalid || (expense->nodes_before == 0U) ||
	    (expense->nodes_after > PICOSYSTEM_GARDEN_MAX_NODES) ||
	    (expense->nodes_after < expense->nodes_before) ||
	    (expense->nodes_after > expense->nodes_before + 1U)) {
		return -EINVAL;
	}
	if (audit->overflow || (audit->count > PICOSYSTEM_GARDEN_NIGHT_EVENTS) ||
	    (audit->denied > audit->evaluated)) {
		return -EOVERFLOW;
	}
	if (expense->nodes_after == expense->nodes_before) {
		return 0;
	}
	if ((audit->count == PICOSYSTEM_GARDEN_NIGHT_EVENTS) || (audit->evaluated == UINT32_MAX)) {
		audit->overflow = true;
		return -EOVERFLOW;
	}
	struct picosystem_garden_night_event event = {.expense_index = expense_index};
	const int err = picosystem_garden_night_project(expense->nodes_after, &event.budget);
	if (err != 0) {
		return err;
	}
	event.denied = event.budget.death_step != 0U;
	audit->events[audit->count++] = event;
	++audit->evaluated;
	if (event.denied) {
		++audit->denied;
		return -ECANCELED;
	}
	return 0;
}

int picosystem_garden_night_print(const struct picosystem_garden_night_audit *audit)
{
	if (audit == NULL) {
		return -EINVAL;
	}
	if (audit->overflow || (audit->count > PICOSYSTEM_GARDEN_NIGHT_EVENTS) ||
	    (audit->denied > audit->evaluated)) {
		return -EOVERFLOW;
	}
	if (printf("\"night_capacity\":{\"rule\":\"%s\",\"evaluated\":%" PRIu32
		   ",\"denied\":%" PRIu32 ",\"events\":[",
		   PICOSYSTEM_GARDEN_NIGHT_CAPACITY_RULE, audit->evaluated, audit->denied) < 0) {
		return -EIO;
	}
	for (uint8_t i = 0U; i < audit->count; ++i) {
		const struct picosystem_garden_night_event *const event = &audit->events[i];
		const struct picosystem_garden_dark_budget *const b = &event->budget;
		if (printf("%s{\"expense\":%u,\"denied\":%s,\"budget\":{\"supported\":%s,"
			   "\"energy\":%u,\"stress\":%u,\"peak_stress\":%u,\"upkeep\":%u,"
			   "\"dark_steps\":%u,\"payments\":%u,\"first_shortage_step\":%u,"
			   "\"death_step\":%u}}",
			   i == 0U ? "" : ",", event->expense_index,
			   event->denied ? "true" : "false", b->supported ? "true" : "false",
			   b->energy, b->stress, b->peak_stress, b->upkeep, b->dark_steps,
			   b->payments, b->first_shortage_step, b->death_step) < 0) {
			return -EIO;
		}
	}
	return printf("]},") < 0 ? -EIO : 0;
}
