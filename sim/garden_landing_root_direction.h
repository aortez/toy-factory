/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_LANDING_ROOT_DIRECTION_H_
#define TOY_FACTORY_GARDEN_LANDING_ROOT_DIRECTION_H_

#include "garden_landing_root_choice.h"

/* Host-only, bounded, no RNG/world mutation. Reconsider only already-eligible
 * root extensions. Move a strictly higher capped-uptake endpoint to the front;
 * equal potentials keep the model order. Other decision fields stay intact.
 * Errors leave the complete decision unchanged. Disabled is an exact no-op.
 */
int toy_factory_garden_root_direction_apply(
	const struct picosystem_garden_world *world,
	const struct picosystem_garden_agent_observation *observation,
	const struct toy_factory_garden_root_choice *choice, uint8_t budget_mode,
	struct picosystem_garden_agent_decision *decision);

#endif
