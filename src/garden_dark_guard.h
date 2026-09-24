/* SPDX-License-Identifier: Apache-2.0 */
#ifndef PICOSYSTEM_GARDEN_DARK_GUARD_H_
#define PICOSYSTEM_GARDEN_DARK_GUARD_H_

#include <stdbool.h>
#include <stdint.h>

#if !defined(TOY_FACTORY_GARDEN_DARK_GUARD) || defined(__ZEPHYR__)
#error "The dark spending guard is an explicit host-only experiment"
#endif

#define PICOSYSTEM_GARDEN_DARK_GUARD_NAME "dark-spending-guard-v1"
#if defined(TOY_FACTORY_GARDEN_PLANT_SLOTS)
#define PICOSYSTEM_GARDEN_DARK_EVENTS 48U
#else
#define PICOSYSTEM_GARDEN_DARK_EVENTS 24U
#endif

enum picosystem_garden_expense_kind {
	PICOSYSTEM_GARDEN_EXPENSE_GROWTH,
	PICOSYSTEM_GARDEN_EXPENSE_RENEWAL,
	PICOSYSTEM_GARDEN_EXPENSE_SEED,
	PICOSYSTEM_GARDEN_EXPENSE_COUNT,
};

/* Zero death_step means no predicted death; offsets are future ecology steps. */
struct picosystem_garden_dark_budget {
	uint16_t energy;
	uint8_t stress;
	uint8_t peak_stress;
	uint8_t upkeep;
	uint8_t dark_steps;
	uint8_t payments;
	uint8_t first_shortage_step;
	uint8_t death_step;
	bool supported;
};

/* Diagnostic only: neither records nor counters participate in the world hash. */
struct picosystem_garden_dark_event {
	struct picosystem_garden_dark_budget before;
	struct picosystem_garden_dark_budget after;
	uint32_t lineage_id;
	uint16_t node_index;
	uint16_t nodes_before;
	uint16_t nodes_after;
	uint16_t energy;
	uint16_t water;
	uint8_t kind;
	uint8_t energy_cost;
	uint8_t water_cost;
	uint8_t stress;
	bool denied;
	bool invalid;
};

struct picosystem_garden_dark_audit {
	struct picosystem_garden_dark_event events[PICOSYSTEM_GARDEN_DARK_EVENTS];
	uint32_t evaluated[PICOSYSTEM_GARDEN_EXPENSE_COUNT];
	uint32_t denied[PICOSYSTEM_GARDEN_EXPENSE_COUNT];
	uint8_t count;
	bool overflow;
};

/* Pure post-step budget, through strictly before the next possible income.
 * Adequate water, fixed nodes and no further spending are assumptions, not grants.
 * Invalid input returns -EINVAL and leaves the output untouched.
 */
int picosystem_garden_dark_project(uint16_t energy, uint16_t nodes, uint8_t stress,
				   uint8_t sun_phase, struct picosystem_garden_dark_budget *result);

#endif /* PICOSYSTEM_GARDEN_DARK_GUARD_H_ */
