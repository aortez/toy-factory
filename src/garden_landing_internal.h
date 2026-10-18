/* SPDX-License-Identifier: Apache-2.0 */
#ifndef PICOSYSTEM_GARDEN_LANDING_INTERNAL_H_
#define PICOSYSTEM_GARDEN_LANDING_INTERNAL_H_

#include "garden_landing.h"

bool picosystem_garden_landing_cache_is_valid(const struct picosystem_garden_landing_cache *cache);

/* Internal phase boundary only. World is validated by the authoritative step;
 * reset captures initial terrain, update requires the next ecology tick.
 * Transactional cache update; no callbacks, world writes or light re-solve.
 */
int picosystem_garden_landing_capture(const struct picosystem_garden_world *world, bool reset,
				      struct picosystem_garden_landing_cache *cache);

#endif
