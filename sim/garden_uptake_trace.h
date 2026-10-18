/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_UPTAKE_TRACE_H_
#define TOY_FACTORY_GARDEN_UPTAKE_TRACE_H_

#include "garden_uptake_audit.h"
#include <stdio.h>

#define TOY_FACTORY_GARDEN_UPTAKE_WINDOWS 64U
struct toy_factory_garden_uptake_window {
	uint32_t start, stop;
};

/* Inclusive, ecology-aligned, strictly ordered/disjoint windows. Invalid
 * requests write no header. Borrowed FILE is closed by the caller on all paths.
 */
int toy_factory_garden_uptake_header(FILE *stream,
				     const struct toy_factory_garden_uptake_window *windows,
				     size_t count, uint32_t stop);
bool toy_factory_garden_uptake_selected(const struct toy_factory_garden_uptake_window *windows,
					size_t count, uint32_t tick);
int toy_factory_garden_uptake_print(FILE *stream,
				    const struct picosystem_garden_uptake_audit *audit);

#endif
