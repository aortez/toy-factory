/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_WET_GERMINATION_H_
#define TOY_FACTORY_GARDEN_WET_GERMINATION_H_

#include "garden_world.h"

#if !defined(TOY_FACTORY_GARDEN_WET_GERMINATION) || defined(__ZEPHYR__)
#error "Wet germination activation is an explicit host diagnostic"
#endif

/* Enable via the authoritative API and emit one boundary receipt. An output
 * failure returns -EIO after activation; the caller must stop the capture.
 */
int toy_factory_garden_wet_germination_activate(struct picosystem_garden_world *world);

#endif
