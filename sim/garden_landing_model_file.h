/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_LANDING_MODEL_FILE_H_
#define TOY_FACTORY_GARDEN_LANDING_MODEL_FILE_H_

#include "garden_landing_neural.h"

/* Exact TGL2 files only, no implicit import. Read leaves output unchanged on
 * any failure, including close. Write validates before exclusively creating a
 * new file; never overwrites, removes its partial file on write/close failure.
 * Caller exclusively owns the destination pathname; not crash-durable storage.
 */
int toy_factory_garden_landing_model_read(const char *path,
					  struct toy_factory_garden_landing_model *model);
int toy_factory_garden_landing_model_write_new(
	const char *path, const struct toy_factory_garden_landing_model *model);

#endif
