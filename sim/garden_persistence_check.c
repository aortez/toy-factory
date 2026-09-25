/* SPDX-License-Identifier: Apache-2.0 */
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include "garden_persistence.h"
#include "garden_pilot_parse.h"

static struct toy_factory_garden_persistence_lifetime
	records[TOY_FACTORY_GARDEN_PERSISTENCE_MAX_LINEAGES + 1U];

static int read_row(uint32_t *values, size_t count)
{
	char line[128];
	if ((fgets(line, sizeof(line), stdin) == NULL) || (strchr(line, '\n') == NULL)) {
		return -EINVAL;
	}
	char *token = strtok(line, " \t\r\n");
	for (size_t i = 0U; i < count; ++i) {
		if (toy_factory_garden_pilot_u32(token, UINT32_MAX, &values[i]) != 0) {
			return -EINVAL;
		}
		token = strtok(NULL, " \t\r\n");
	}
	return token == NULL ? 0 : -EINVAL;
}

int main(void)
{
	uint32_t header[5];
	if ((read_row(header, 5U) != 0) ||
	    (header[4] > TOY_FACTORY_GARDEN_PERSISTENCE_MAX_LINEAGES)) {
		return 2;
	}
	for (uint32_t id = 1U; id <= header[4]; ++id) {
		uint32_t row[3];
		if (read_row(row, 3U) != 0) {
			return 2;
		}
		records[id] = (struct toy_factory_garden_persistence_lifetime){
			.parent = row[0], .birth = row[1], .death = row[2]};
	}
	if ((getchar() != EOF) || ferror(stdin)) {
		return 2;
	}
	struct toy_factory_garden_persistence_score score;
	const int err = toy_factory_garden_persistence_score(
		records, header[4], header[3], header[0], header[1], header[2], &score);
	if (err != 0) {
		return 1;
	}
	printf("[%" PRId64 ",%" PRId64 ",%" PRId64 ",%" PRId64 ",%" PRId64 "]\n", score.key[0],
	       score.key[1], score.key[2], score.key[3], score.key[4]);
	return fflush(stdout) == 0 && !ferror(stdout) ? 0 : 1;
}
