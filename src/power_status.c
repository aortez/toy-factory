/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "power_status.h"

#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/util.h>

LOG_MODULE_REGISTER(picosystem_power_status, LOG_LEVEL_INF);

#define POWER_STATUS_NODE       DT_NODELABEL(power_status)
#define POWER_STATUS_QUALIFY_MS 250
#define CHARGE_ACTIVITY_HOLD_MS 1000

BUILD_ASSERT(CHARGE_ACTIVITY_HOLD_MS >= POWER_STATUS_QUALIFY_MS);

static const struct gpio_dt_spec vbus_detect =
	GPIO_DT_SPEC_GET(POWER_STATUS_NODE, vbus_detect_gpios);
static const struct gpio_dt_spec charge_status =
	GPIO_DT_SPEC_GET(POWER_STATUS_NODE, charge_status_gpios);
static bool power_status_initialized;
static bool qualified_status_available;
static bool charge_activity_seen;
static int64_t candidate_since_ms;
static int64_t last_charge_activity_ms;
static struct picosystem_power_status candidate_status;
static struct picosystem_power_status qualified_status;

static bool statuses_equal(const struct picosystem_power_status *left,
			   const struct picosystem_power_status *right)
{
	return (left->usb_power_present == right->usb_power_present) &&
	       (left->charging == right->charging);
}

static struct picosystem_power_status classify_status(bool usb_power_present, bool charging)
{
	enum picosystem_power_state state;

	if (usb_power_present && charging) {
		state = PICOSYSTEM_POWER_STATE_USB_CHARGING;
	} else if (usb_power_present) {
		state = PICOSYSTEM_POWER_STATE_USB_POWERED;
	} else if (charging) {
		state = PICOSYSTEM_POWER_STATE_CHARGE_WITHOUT_USB;
	} else {
		state = PICOSYSTEM_POWER_STATE_BATTERY;
	}

	const struct picosystem_power_status status = {
		.state = state,
		.usb_power_present = usb_power_present,
		.charging = charging,
	};

	return status;
}

static bool hold_charge_activity(bool usb_power_present, bool charge_active, int64_t now_ms)
{
	if (charge_active) {
		charge_activity_seen = true;
		last_charge_activity_ms = now_ms;
	} else if (charge_activity_seen &&
		   ((now_ms - last_charge_activity_ms) >= CHARGE_ACTIVITY_HOLD_MS)) {
		charge_activity_seen = false;
	}

	/* Do not carry a previous USB charge pulse into battery-only operation. */
	return charge_active || (usb_power_present && charge_activity_seen);
}

static int configure_input(const char *name, const struct gpio_dt_spec *input)
{
	if (!gpio_is_ready_dt(input)) {
		LOG_ERR("%s GPIO controller is not ready", name);
		return -ENODEV;
	}

	const int err = gpio_pin_configure_dt(input, GPIO_INPUT);
	if (err != 0) {
		LOG_ERR("Failed to configure %s input (%d)", name, err);
		return err;
	}

	return 0;
}

int picosystem_power_status_init(void)
{
	int err = configure_input("VBUS detect", &vbus_detect);
	if (err != 0) {
		return err;
	}

	err = configure_input("charge status", &charge_status);
	if (err != 0) {
		return err;
	}

	qualified_status_available = false;
	charge_activity_seen = false;
	power_status_initialized = true;
	return 0;
}

int picosystem_power_status_read(struct picosystem_power_status *status)
{
	if (status == NULL) {
		return -EINVAL;
	}

	if (!power_status_initialized) {
		return -EACCES;
	}

	const int vbus_value = gpio_pin_get_dt(&vbus_detect);
	if (vbus_value < 0) {
		LOG_ERR("Failed to read VBUS detect input (%d)", vbus_value);
		return vbus_value;
	}

	const int charge_value = gpio_pin_get_dt(&charge_status);
	if (charge_value < 0) {
		LOG_ERR("Failed to read charge status input (%d)", charge_value);
		return charge_value;
	}

	const int64_t now_ms = k_uptime_get();
	const bool usb_power_present = vbus_value != 0;
	const bool charging = hold_charge_activity(usb_power_present, charge_value != 0, now_ms);
	const struct picosystem_power_status sampled_status =
		classify_status(usb_power_present, charging);

	if (!qualified_status_available) {
		candidate_status = sampled_status;
		qualified_status = sampled_status;
		candidate_since_ms = now_ms;
		qualified_status_available = true;
	} else if (!statuses_equal(&sampled_status, &candidate_status)) {
		candidate_status = sampled_status;
		candidate_since_ms = now_ms;
	} else if (!statuses_equal(&candidate_status, &qualified_status) &&
		   ((now_ms - candidate_since_ms) >= POWER_STATUS_QUALIFY_MS)) {
		qualified_status = candidate_status;
	}

	*status = qualified_status;
	return 0;
}

const char *picosystem_power_state_name(enum picosystem_power_state state)
{
	switch (state) {
	case PICOSYSTEM_POWER_STATE_BATTERY:
		return "battery";
	case PICOSYSTEM_POWER_STATE_USB_POWERED:
		return "usb-powered";
	case PICOSYSTEM_POWER_STATE_USB_CHARGING:
		return "usb-charging";
	case PICOSYSTEM_POWER_STATE_CHARGE_WITHOUT_USB:
		return "charge-active-without-usb";
	default:
		return "unknown";
	}
}
