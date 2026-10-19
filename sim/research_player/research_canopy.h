/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_RESEARCH_CANOPY_H_
#define TOY_FACTORY_RESEARCH_CANOPY_H_

#include "garden_uptake_audit.h"

#define RESEARCH_CANOPY_FIRST (152U * 3840U + 2880U)
#define RESEARCH_CANOPY_END   (152U * 3840U + 3360U)
#define RESEARCH_CANOPY_ROWS  32U

/* Use the frozen growth-progress/wear/shade builder on a private copy. Rain
 * and soil transport do not change opacity or the clock-based sun. The caller
 * must compare every projected light cell with actual uptake light before
 * publishing sources. Not the unsupported maintenance uptake-audit API.
 * No input mutation, global context, retained pointers, or allocation.
 */
int research_canopy_project(const struct picosystem_garden_world *before,
			    struct picosystem_garden_uptake_audit *out);

#endif
