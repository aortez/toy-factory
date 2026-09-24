/* SPDX-License-Identifier: Apache-2.0 */
#ifndef PICOSYSTEM_GARDEN_DAWN_FINISH_H_
#define PICOSYSTEM_GARDEN_DAWN_FINISH_H_

#include "garden_dark_guard.h"

#if defined(__ZEPHYR__) || !defined(TOY_FACTORY_GARDEN_DAWN_FINISH) ||                             \
	!defined(TOY_FACTORY_GARDEN_WET_GERMINATION)
#error "Dawn FINISH is an isolated host-only wet-germination diagnostic"
#endif

#define PICOSYSTEM_GARDEN_DAWN_FINISH_RULE  "dawn-finish-deferral-v1"
#define PICOSYSTEM_GARDEN_DAWN_FINISH_FIRST 66090U
#define PICOSYSTEM_GARDEN_DAWN_FINISH_LAST  68340U
#define PICOSYSTEM_GARDEN_DAWN_RESERVE_RULE "dawn-finish-reserve-v1"
#define PICOSYSTEM_GARDEN_DAWN_FINISH_NOON  69120U

struct picosystem_garden_agent_observation;
/* World-owned diagnostic, zeroed on reset and excluded from the world hash.
 * enabled is selected before stepping; no allocations or global mutable state.
 */
struct picosystem_garden_dawn_finish {
	uint32_t last_tick;
	uint32_t handoff_tick;
	uint16_t last_node;
	uint16_t hits;
	uint16_t handoff_energy;
	uint16_t handoff_node;
	bool enabled;
	bool reserve_handoff;
};

int picosystem_garden_dawn_finish_parse(const char *name,
					struct picosystem_garden_dawn_finish *state);
/* Only called after both ordinary guards allow the winning expense. Refuse
 * before transaction commit; errors other than -ECANCELED abort the run.
 * Retry identity uses lineage + root coordinates/depth, not a compactable index.
 * reserve keeps the old deferral, then retains one upkeep bill until first noon.
 * A recorded handoff is pre-commit; the caller must still execute/pay normally.
 */
int picosystem_garden_dawn_finish_check(
	struct picosystem_garden_dawn_finish *state, uint32_t tick,
	const struct picosystem_garden_dark_event *event,
	const struct picosystem_garden_agent_observation *observation, uint8_t action);
int picosystem_garden_dawn_finish_validate(const struct picosystem_garden_dawn_finish *state,
					   uint32_t tick);
/* JSON fragment including trailing comma. Disabled support emits nothing. */
int picosystem_garden_dawn_finish_print(const struct picosystem_garden_dawn_finish *state,
					uint32_t tick);
#endif
