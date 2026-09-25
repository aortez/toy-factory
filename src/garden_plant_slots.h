/* SPDX-License-Identifier: Apache-2.0 */
#ifndef PICOSYSTEM_GARDEN_PLANT_SLOTS_H_
#define PICOSYSTEM_GARDEN_PLANT_SLOTS_H_

#include <stdbool.h>
#include <stdint.h>

#if defined(__ZEPHYR__) || !defined(TOY_FACTORY_GARDEN_PLANT_SLOTS) ||                             \
	!defined(TOY_FACTORY_GARDEN_CANOPY_TRANSMISSION)
#error "Plant slots require the explicit host-only fractional canopy experiment"
#endif

#define PICOSYSTEM_GARDEN_PLANT_SLOTS_RULE  "post-noon-sixteen-plant-slots-v1"
#define PICOSYSTEM_GARDEN_PLANT_SLOTS_AFTER 69120U

/* Compiled storage and active admission are deliberately separate. */
uint8_t picosystem_garden_plant_slots_limit(bool enabled, uint32_t tick);
int picosystem_garden_plant_slots_parse(const char *name, bool *enabled);
/* JSON fragment with trailing comma; disabled control emits nothing. */
int picosystem_garden_plant_slots_print(bool enabled, uint32_t tick);

#endif
