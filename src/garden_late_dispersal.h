/* SPDX-License-Identifier: Apache-2.0 */
#ifndef PICOSYSTEM_GARDEN_LATE_DISPERSAL_H_
#define PICOSYSTEM_GARDEN_LATE_DISPERSAL_H_

#if defined(__ZEPHYR__)
#error "Late broader dispersal is an unqualified host-only experiment"
#endif
#if !defined(TOY_FACTORY_GARDEN_LATE_UPTAKE_LIMIT) ||                                              \
	defined(TOY_FACTORY_GARDEN_WIDE_DISPERSAL) || defined(TOY_FACTORY_GARDEN_FLOWER_DISPERSAL)
#error "Late dispersal requires capped uptake and excludes from-start dispersal experiments"
#endif

#include <stdint.h>

#define PICOSYSTEM_GARDEN_LATE_DISPERSAL_VERSION    1U
#define PICOSYSTEM_GARDEN_LATE_DISPERSAL_AFTER_TICK UINT32_C(626580)
#define PICOSYSTEM_GARDEN_LATE_DISPERSAL_MINIMUM    3U
#define PICOSYSTEM_GARDEN_LATE_DISPERSAL_DISTANCES  7U

#endif
