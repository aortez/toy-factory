/* SPDX-License-Identifier: Apache-2.0 */
#ifndef PICOSYSTEM_GARDEN_CANOPY_TRANSMISSION_H_
#define PICOSYSTEM_GARDEN_CANOPY_TRANSMISSION_H_

#include <stdbool.h>
#include <stdint.h>

#if defined(__ZEPHYR__) || !defined(TOY_FACTORY_GARDEN_CANOPY_TRANSMISSION) ||                     \
	!defined(TOY_FACTORY_GARDEN_SEED_SPACING)
#error "Canopy transmission is a host-only post-noon spacing follow-up"
#endif

#define PICOSYSTEM_GARDEN_CANOPY_TRANSMISSION_RULE  "post-noon-fractional-transmission-v1"
#define PICOSYSTEM_GARDEN_CANOPY_TRANSMISSION_AFTER 69120U

/* Run configuration only; the split checkpoint retains the original solver. */
bool picosystem_garden_canopy_transmission_active(bool enabled, uint32_t tick);
int picosystem_garden_canopy_transmission_parse(const char *name, bool *enabled);
/* Disabled support emits nothing; enabled output is a trailing-comma JSON field. */
int picosystem_garden_canopy_transmission_print(bool enabled, uint32_t tick);

#endif
