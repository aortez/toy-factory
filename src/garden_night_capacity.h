/* SPDX-License-Identifier: Apache-2.0 */
#ifndef PICOSYSTEM_GARDEN_NIGHT_CAPACITY_H_
#define PICOSYSTEM_GARDEN_NIGHT_CAPACITY_H_

#include "garden_dark_guard.h"

#if defined(__ZEPHYR__) || !defined(TOY_FACTORY_GARDEN_NIGHT_CAPACITY) ||                          \
	!defined(TOY_FACTORY_GARDEN_DARK_GUARD) || defined(TOY_FACTORY_GARDEN_PURCHASE_VETO)
#error "Night capacity is a separate host-only experiment requiring the ordinary dark guard"
#endif

#define PICOSYSTEM_GARDEN_NIGHT_CAPACITY_RULE "full-night-capacity-guard-v1"
#if defined(TOY_FACTORY_GARDEN_PLANT_SLOTS)
#define PICOSYSTEM_GARDEN_NIGHT_EVENTS 16U
#else
#define PICOSYSTEM_GARDEN_NIGHT_EVENTS 8U
#endif

struct picosystem_garden_night_event {
	struct picosystem_garden_dark_budget budget;
	uint8_t expense_index;
	bool denied;
};

/* World-owned diagnostics, excluded from the hash. Reset count each ecology
 * step; evaluated/denied are cumulative until world reset. No allocation.
 */
struct picosystem_garden_night_audit {
	struct picosystem_garden_night_event events[PICOSYSTEM_GARDEN_NIGHT_EVENTS];
	uint32_t evaluated;
	uint32_t denied;
	uint8_t count;
	bool overflow;
};

/* Full stores, zero stress, fixed body, adequate water and no optional costs.
 * Invalid input/alignment returns -EINVAL without changing the output.
 */
int picosystem_garden_night_project(uint16_t nodes, struct picosystem_garden_dark_budget *result);
/* Called only after the ordinary guard allows the selected growth expense.
 * No-node actions pass without an event. -ECANCELED refuses a node addition;
 * other errors abort stepping. Overflow is latched and never silently dropped.
 */
int picosystem_garden_night_check(struct picosystem_garden_night_audit *audit,
				  const struct picosystem_garden_dark_event *expense,
				  uint8_t expense_index);
/* JSON fragment with trailing comma, shared by native inspector and replayer. */
int picosystem_garden_night_print(const struct picosystem_garden_night_audit *audit);

#endif
