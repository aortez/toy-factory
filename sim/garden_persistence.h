/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_PERSISTENCE_H_
#define TOY_FACTORY_GARDEN_PERSISTENCE_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define TOY_FACTORY_GARDEN_PERSISTENCE_DAY          3840U
#define TOY_FACTORY_GARDEN_PERSISTENCE_STEP         15U
#define TOY_FACTORY_GARDEN_PERSISTENCE_MAX_LINEAGES 4096U
#define TOY_FACTORY_GARDEN_PERSISTENCE_MAX_TICKS    737280U
#define TOY_FACTORY_GARDEN_PERSISTENCE_ALIVE        UINT32_MAX

/* Dense ID-indexed ledger; slot zero unused. Death ALIVE means still alive.
 * Host-owned records outlive reclaimed world slots. Other fields are export
 * diagnostics and do not affect the score.
 */
struct toy_factory_garden_persistence_lifetime {
	uint32_t parent;
	uint32_t birth;
	uint32_t death;
	uint32_t purchases;
	uint32_t closing_purchases;
	uint16_t generation;
	uint8_t column;
	uint8_t species;
	bool patch;
};

struct toy_factory_garden_persistence_score {
	/* terminal tier, renewing-child time, descendant time, renewing parents,
	 * establishments. Exact garden-lineage-persistence-v2 world order.
	 */
	int64_t key[5];
};

/* Complete fixed two-day follow-up required. No allocation or world mutation;
 * invalid clocks, lifetimes or ancestry leave output unchanged. Seed ledger
 * consistency is separately checked by the trial collector and Python oracle.
 */
int toy_factory_garden_persistence_score(
	const struct toy_factory_garden_persistence_lifetime *records, size_t count,
	uint32_t pending_seeds, uint32_t start, uint32_t end, uint32_t stop,
	struct toy_factory_garden_persistence_score *out);

#endif
