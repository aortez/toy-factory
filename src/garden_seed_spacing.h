/* SPDX-License-Identifier: Apache-2.0 */
#ifndef PICOSYSTEM_GARDEN_SEED_SPACING_H_
#define PICOSYSTEM_GARDEN_SEED_SPACING_H_

#include <stdbool.h>
#include <stdint.h>

#if defined(__ZEPHYR__) || !defined(TOY_FACTORY_GARDEN_SEED_SPACING) ||                            \
	!defined(TOY_FACTORY_GARDEN_SEED_ORDER)
#error "Seed spacing is a host-only post-noon establishment experiment"
#endif

#define PICOSYSTEM_GARDEN_SEED_SPACING_RULE  "post-noon-spacing-two-v1"
#define PICOSYSTEM_GARDEN_SEED_SPACING_AFTER 69120U

/* Run configuration, not a controller action. The boundary remains unchanged. */
uint8_t picosystem_garden_seed_spacing_minimum(bool enabled, uint32_t tick);
int picosystem_garden_seed_spacing_parse(const char *name, bool *enabled);
/* JSON fragment including trailing comma; disabled support emits nothing. */
int picosystem_garden_seed_spacing_print(bool enabled, uint32_t tick);

#endif
