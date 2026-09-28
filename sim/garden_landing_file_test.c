/* SPDX-License-Identifier: Apache-2.0 */
#define _POSIX_C_SOURCE 200809L
#include "garden_landing_model_file.h"

#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(void)
{
	char directory[] = "/tmp/toy-factory-landing-file-XXXXXX";
	assert(mkdtemp(directory) != NULL);
	char path[128];
	const int n = snprintf(path, sizeof(path), "%s/model.tgl", directory);
	assert(n > 0 && (size_t)n < sizeof(path));
	const struct toy_factory_garden_landing_feature_config config = {.version = 1U, .mode = 2U};
	struct toy_factory_garden_landing_model model;
	assert(toy_factory_garden_landing_model_import(picosystem_garden_neural_reference_model(),
						       &config, &model) == 0);
	struct toy_factory_garden_landing_model output;
	memset(&output, 0xa5, sizeof(output));
	const struct toy_factory_garden_landing_model sentinel = output;
	assert(toy_factory_garden_landing_model_read(path, &output) == -ENOENT);
	assert(memcmp(&output, &sentinel, sizeof(output)) == 0);
	assert(toy_factory_garden_landing_model_read(NULL, &output) == -EINVAL);
	assert(toy_factory_garden_landing_model_read("", &output) == -EINVAL);
	assert(toy_factory_garden_landing_model_read(path, NULL) == -EINVAL);
	assert(memcmp(&output, &sentinel, sizeof(output)) == 0);
	assert(toy_factory_garden_landing_model_write_new(path, &sentinel) != 0);
	assert(access(path, F_OK) != 0);
	assert(toy_factory_garden_landing_model_write_new(NULL, &model) == -EINVAL);
	assert(toy_factory_garden_landing_model_write_new("", &model) == -EINVAL);
	assert(toy_factory_garden_landing_model_write_new(path, NULL) == -EINVAL);
	assert(toy_factory_garden_landing_model_write_new(path, &model) == 0);
	assert(toy_factory_garden_landing_model_write_new(path, &model) == -EEXIST);
	assert(toy_factory_garden_landing_model_read(path, &output) == 0);
	assert(memcmp(&output, &model, sizeof(model)) == 0);
	output = sentinel;
	FILE *stream = fopen(path, "ab");
	assert(stream != NULL && fputc(0, stream) == 0 && fclose(stream) == 0);
	assert(toy_factory_garden_landing_model_read(path, &output) != 0);
	assert(memcmp(&output, &sentinel, sizeof(output)) == 0);
	stream = fopen(path, "wb");
	assert(stream != NULL && fputs("short", stream) >= 0 && fclose(stream) == 0);
	assert(toy_factory_garden_landing_model_read(path, &output) != 0);
	assert(memcmp(&output, &sentinel, sizeof(output)) == 0);
	assert(toy_factory_garden_landing_model_read(directory, &output) != 0);
	assert(memcmp(&output, &sentinel, sizeof(output)) == 0);
	assert(unlink(path) == 0 && rmdir(directory) == 0);
	puts("Landing model files: exact reads, no clobber, failure preservation passed");
	return 0;
}
