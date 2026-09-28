/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_neural.h"

#include <stdio.h>
#include <string.h>

/* Bounded stdin/stdout test adapter, not automatic format detection. */
int main(int argc, char **argv)
{
	if (argc != 2) {
		return 2;
	}
	uint8_t bytes[TOY_FACTORY_GARDEN_LANDING_FILE_SIZE];
	if (strcmp(argv[1], "reference") == 0) {
		if (picosystem_garden_neural_model_encode(
			    picosystem_garden_neural_reference_model(), bytes, sizeof(bytes)) !=
		    0) {
			return 1;
		}
		return (fwrite(bytes, 1U, PICOSYSTEM_GARDEN_NEURAL_FILE_SIZE, stdout) ==
				PICOSYSTEM_GARDEN_NEURAL_FILE_SIZE &&
			fflush(stdout) == 0)
			       ? 0
			       : 1;
	}
	const bool importing = strcmp(argv[1], "import") == 0;
	if (!importing && strcmp(argv[1], "roundtrip") != 0) {
		return 2;
	}
	const size_t size = importing ? PICOSYSTEM_GARDEN_NEURAL_FILE_SIZE : sizeof(bytes);
	if ((fread(bytes, 1U, size, stdin) != size) || (fgetc(stdin) != EOF) || ferror(stdin)) {
		return 1;
	}
	struct toy_factory_garden_landing_model model;
	int err;
	if (importing) {
		struct picosystem_garden_neural_model legacy;
		err = picosystem_garden_neural_model_decode(bytes, size, &legacy);
		if (err != 0) {
			return 1;
		}
		const struct toy_factory_garden_landing_feature_config config = {.version = 1U,
										 .mode = 2U};
		err = toy_factory_garden_landing_model_import(&legacy, &config, &model);
	} else {
		err = toy_factory_garden_landing_model_decode(bytes, size, &model);
	}
	if ((err != 0) ||
	    (toy_factory_garden_landing_model_encode(&model, bytes, sizeof(bytes)) != 0)) {
		return 1;
	}
	return (fwrite(bytes, 1U, sizeof(bytes), stdout) == sizeof(bytes) && fflush(stdout) == 0)
		       ? 0
		       : 1;
}
