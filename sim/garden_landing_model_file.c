/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_model_file.h"

#include <errno.h>
#include <stdio.h>

int toy_factory_garden_landing_model_read(const char *path,
					  struct toy_factory_garden_landing_model *model)
{
	if ((path == NULL) || (*path == '\0') || (model == NULL)) {
		return -EINVAL;
	}
	FILE *const stream = fopen(path, "rb");
	if (stream == NULL) {
		return errno != 0 ? -errno : -EIO;
	}
	uint8_t bytes[TOY_FACTORY_GARDEN_LANDING_FILE_SIZE];
	const size_t read = fread(bytes, 1U, sizeof(bytes), stream);
	const int trailing = fgetc(stream);
	const bool failed = ferror(stream) != 0;
	const int closed = fclose(stream);
	if (failed || (closed != 0)) {
		return -EIO;
	}
	if ((read != sizeof(bytes)) || (trailing != EOF)) {
		return -EINVAL;
	}
	return toy_factory_garden_landing_model_decode(bytes, sizeof(bytes), model);
}

int toy_factory_garden_landing_model_write_new(const char *path,
					       const struct toy_factory_garden_landing_model *model)
{
	if ((path == NULL) || (*path == '\0')) {
		return -EINVAL;
	}
	uint8_t bytes[TOY_FACTORY_GARDEN_LANDING_FILE_SIZE];
	int err = toy_factory_garden_landing_model_encode(model, bytes, sizeof(bytes));
	if (err != 0) {
		return err;
	}
	FILE *const stream = fopen(path, "wbx");
	if (stream == NULL) {
		return errno != 0 ? -errno : -EIO;
	}
	const size_t written = fwrite(bytes, 1U, sizeof(bytes), stream);
	const int closed = fclose(stream);
	if ((written != sizeof(bytes)) || (closed != 0)) {
		(void)remove(path);
		return -EIO;
	}
	return 0;
}
