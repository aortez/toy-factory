/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_TOPOLOGY_H_
#define TOY_FACTORY_GARDEN_TOPOLOGY_H_

#include <stdio.h>

#include "garden_world.h"

/* Host-only structural census. Validate all links/counts before output; never
 * mutate the world. An I/O failure can leave a partial record in the stream.
 */
int toy_factory_garden_topology_print(const struct picosystem_garden_world *world, FILE *output);

#endif
