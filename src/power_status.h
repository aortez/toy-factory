/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_POWER_STATUS_H
#define PICOSYSTEM_POWER_STATUS_H

#include <stdbool.h>

enum picosystem_power_state {
	PICOSYSTEM_POWER_STATE_BATTERY,
	PICOSYSTEM_POWER_STATE_USB_POWERED,
	PICOSYSTEM_POWER_STATE_USB_CHARGING,
	PICOSYSTEM_POWER_STATE_CHARGE_WITHOUT_USB,
};

struct picosystem_power_status {
	enum picosystem_power_state state;
	bool usb_power_present;
	bool charging;
};

/* Configure both status inputs while preserving the automatic charge indicator. */
int picosystem_power_status_init(void);

/* Read both inputs and return their qualified state with recent charge activity held. */
int picosystem_power_status_read(struct picosystem_power_status *status);

/* Return a stable diagnostic name for a classified power state. */
const char *picosystem_power_state_name(enum picosystem_power_state state);

#endif /* PICOSYSTEM_POWER_STATUS_H */
