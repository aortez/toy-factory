/* SPDX-License-Identifier: Apache-2.0 */
#include <inttypes.h>
#include <stdio.h>
#include "garden_model_file.h"
#include "garden_model_mutation.h"
#include "garden_pilot_parse.h"

int main(int argc, char **argv)
{
	uint32_t seed, count;
	if ((argc != 5) || (toy_factory_garden_pilot_u32(argv[3], UINT32_MAX, &seed) != 0) ||
	    (toy_factory_garden_pilot_u32(argv[4], 4096U, &count) != 0) || (count == 0U)) {
		fprintf(stderr, "Usage: %s INPUT_MODEL NEW_OUTPUT RNG_STATE MUTATIONS\n", argv[0]);
		return 2;
	}
	/* Reserve the final path exclusively; the canonical writer atomically
	 * replaces only this process's placeholder. A failed write remains visible.
	 */
	struct picosystem_garden_neural_model model;
	struct toy_factory_garden_mutation_rng rng = {.state = seed};
	uint32_t before, after;
	int err = toy_factory_garden_model_read(argv[1], &model, &before);
	if (err == 0) {
		err = toy_factory_garden_model_mutate(&model, &rng, count);
	}
	if (err == 0) {
		FILE *const reserved = fopen(argv[2], "wbx");
		if (reserved == NULL) {
			err = -EIO;
		} else if (fclose(reserved) != 0) {
			err = -EIO;
		}
	}
	if (err == 0) {
		err = toy_factory_garden_model_write_binary(argv[2], &model, &after);
	}
	if (err == 0) {
		printf("{\"before\":\"%08" PRIx32 "\",\"after\":\"%08" PRIx32
		       "\",\"rng_before\":%" PRIu32 ",\"rng_after\":%" PRIu32 "}\n",
		       before, after, seed, rng.state);
		if (fflush(stdout) != 0 || ferror(stdout)) {
			err = -EIO;
		}
	}
	if (err != 0) {
		fprintf(stderr, "Model mutation failed (%d)\n", err);
	}
	return err == 0 ? 0 : 1;
}
