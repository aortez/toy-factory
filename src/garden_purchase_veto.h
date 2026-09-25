/* SPDX-License-Identifier: Apache-2.0 */
#ifndef PICOSYSTEM_GARDEN_PURCHASE_VETO_H_
#define PICOSYSTEM_GARDEN_PURCHASE_VETO_H_

#include "garden_dark_guard.h"

#if defined(__ZEPHYR__) || !defined(TOY_FACTORY_GARDEN_DARK_GUARD)
#error "Purchase veto is a host-only diagnostic requiring the unchanged dark guard"
#endif

#define PICOSYSTEM_GARDEN_PURCHASE_VETO_RULE "isolated-purchase-veto-v1"
#define PICOSYSTEM_GARDEN_FINISH_RETRY_RULE  "finish-retry-v1"

enum picosystem_garden_purchase_selection {
	PICOSYSTEM_GARDEN_PURCHASE_NONE,
	PICOSYSTEM_GARDEN_PURCHASE_EXTENSION,
	PICOSYSTEM_GARDEN_PURCHASE_FINISH,
	PICOSYSTEM_GARDEN_PURCHASE_FINISH_RETRY,
	PICOSYSTEM_GARDEN_PURCHASE_COUNT,
};

/* World-owned diagnostic state, cleared on reset and excluded from the hash.
 * Selection is fixed before stepping; receipt expectations are not tunable.
 */
struct picosystem_garden_purchase_veto {
	enum picosystem_garden_purchase_selection selection;
	uint8_t hits;
};

int picosystem_garden_purchase_parse(const char *name,
				     enum picosystem_garden_purchase_selection *selection);
/* Only call for an eligible winning purchase accepted by the ordinary guard.
 * -ECANCELED rejects the selected transaction; other errors abort the run.
 * FINISH_RETRY has two fixed receipts and stops before the covered interval.
 */
int picosystem_garden_purchase_check(struct picosystem_garden_purchase_veto *veto, uint32_t tick,
				     const struct picosystem_garden_dark_event *event,
				     uint8_t action);
int picosystem_garden_purchase_validate(const struct picosystem_garden_purchase_veto *veto,
					uint32_t tick);
/* Optional JSON object fragment, with a trailing comma. Disabled emits nothing. */
int picosystem_garden_purchase_print(const struct picosystem_garden_purchase_veto *veto,
				     uint32_t tick);
#endif
