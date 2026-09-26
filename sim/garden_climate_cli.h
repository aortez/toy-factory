/* SPDX-License-Identifier: Apache-2.0 */

#ifndef TOY_FACTORY_GARDEN_CLIMATE_CLI_H_
#define TOY_FACTORY_GARDEN_CLIMATE_CLI_H_

#include "garden_world.h"
#include <stdio.h>

/* Leave output unchanged on invalid input. */
int toy_factory_garden_climate_parse(const char *name, enum picosystem_garden_climate_mode *mode);

/* JSON object members with a trailing comma; caller checks its complete stream. */
void toy_factory_garden_climate_print(FILE *stream, const struct picosystem_garden_world *world);

#endif
