/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_vacancy.h"

#include <errno.h>
#include <inttypes.h>

int toy_factory_garden_landing_vacancy_apply(struct toy_factory_garden_landing_growth_run *run,
					     struct toy_factory_garden_lifetimes *ledger,
					     uint32_t lineage_id,
					     struct toy_factory_garden_landing_vacancy *result)
{
	if ((run == NULL) || (ledger == NULL) || (result == NULL)) {
		return -EINVAL;
	}
	if ((ledger->count > TOY_FACTORY_GARDEN_EVALUATION_MAX_TRACKED_LINEAGES) ||
	    (ledger->count != run->base.world.lineage_sequence) || (lineage_id == 0U) ||
	    (lineage_id > ledger->count)) {
		return -ERANGE;
	}
	struct toy_factory_garden_landing_vacancy event = {0};
	int err = toy_factory_garden_landing_growth_hash(run, &event.before_run_hash);
	if (err != 0) {
		return err;
	}
	struct toy_factory_garden_landing_growth_run candidate = *run;
	err = toy_factory_garden_gap_apply_named(&candidate.base.world, lineage_id, &event.gap);
	if (err == 0) {
		err = toy_factory_garden_landing_growth_hash(&candidate, &event.after_run_hash);
	}
	if (err == 0) {
		err = toy_factory_garden_lifetimes_remove_adult(
			ledger, lineage_id, candidate.base.world.logic_tick_count);
	}
	if (err == 0) {
		*run = candidate;
		*result = event;
	}
	return err;
}

uint32_t toy_factory_garden_landing_vacancy_hash(uint32_t base, uint32_t tick, uint32_t lineage_id)
{
	uint32_t hash = 2166136261U;
	const uint8_t tag[] = {'G', 'L', 'V', '1'};
	for (size_t i = 0U; i < sizeof(tag); ++i) {
		hash = (hash ^ tag[i]) * 16777619U;
	}
	const uint32_t words[] = {base, tick, lineage_id};
	for (size_t i = 0U; i < sizeof(words) / sizeof(words[0]); ++i) {
		for (uint8_t byte = 0U; byte < 4U; ++byte) {
			hash = (hash ^ (uint8_t)(words[i] >> (byte * 8U))) * 16777619U;
		}
	}
	return hash;
}

int toy_factory_garden_landing_vacancy_print(
	FILE *stream, uint32_t tick, uint32_t lineage_id,
	const struct toy_factory_garden_landing_vacancy *result)
{
	if ((stream == NULL) || (result == NULL)) {
		return -EINVAL;
	}
	fprintf(stream,
		"\"vacancy_probe\":{\"version\":1,\"tick\":%" PRIu32 ",\"lineage\":%" PRIu32
		",\"event\":",
		tick, lineage_id);
	const struct toy_factory_garden_gap *const gap = &result->gap;
	if (gap->lineage_id == 0U) {
		fputs("null},", stream);
	} else {
		fprintf(stream,
			"{\"tick\":%" PRIu32 ",\"id\":%" PRIu32
			",\"column\":%u,\"nodes\":%u,\"energy\":%u,\"water\":%u,"
			"\"before_world_hash\":\"%08" PRIx32 "\",\"after_world_hash\":\"%08" PRIx32
			"\",\"before_run_hash\":\"%08" PRIx32 "\",\"after_run_hash\":\"%08" PRIx32
			"\"}},",
			gap->tick, gap->lineage_id, gap->column, gap->nodes, gap->energy,
			gap->water, gap->before_hash, gap->after_hash, result->before_run_hash,
			result->after_run_hash);
	}
	return ferror(stream) ? -EIO : 0;
}
