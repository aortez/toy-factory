/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "display_sync.h"

#include <errno.h>
#include <stdbool.h>
#include <stdint.h>

#include <zephyr/device.h>
#include <zephyr/display/mipi_display.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/mipi_dbi.h>
#include <zephyr/drivers/spi.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/atomic.h>
#include <zephyr/sys/util.h>

LOG_MODULE_REGISTER(picosystem_display_sync, LOG_LEVEL_INF);

#define PICOSYSTEM_DISPLAY_NODE      DT_CHOSEN(zephyr_display)
#define PICOSYSTEM_DISPLAY_SYNC_NODE DT_NODELABEL(lcd_sync)
#define PICOSYSTEM_MIPI_DBI_NODE     DT_PHANDLE(PICOSYSTEM_DISPLAY_SYNC_NODE, mipi_dbi)

/* Zephyr's generic DBI TE path waits forever; application ownership permits safe fallback. */
#define TE_VBLANK_ONLY        0x00U
#define TE_MIN_PERIOD_SAMPLES 4U
#define TE_MIN_PERIOD_US      15000U
#define TE_MAX_PERIOD_US      18500U
#define TE_SIGNAL_STALE_US    25000U
#define TE_WAIT_TIMEOUT_MS    20

struct timing_accumulator {
	uint64_t sum_cycles;
	uint32_t min_cycles;
	uint32_t max_cycles;
	uint32_t samples;
};

struct display_sync_metrics {
	struct timing_accumulator period;
	struct timing_accumulator high;
	struct timing_accumulator low;
	uint32_t rising_edges;
	uint32_t falling_edges;
	uint32_t gpio_read_errors;
	uint32_t rising_sequence;
	uint32_t last_period_cycles;
	uint32_t previous_rising_cycles;
	uint32_t previous_falling_cycles;
	uint32_t last_edge_uptime_ms;
	uint32_t synchronized_presents;
	uint32_t bypassed_presents;
	uint32_t timed_out_presents;
	uint32_t last_wait_cycles;
	uint32_t max_wait_cycles;
	int initialization_error;
	bool have_rising;
	bool have_falling;
	bool have_edge;
	bool panel_te_enabled;
	bool signal_high;
};

struct display_sync_signal_snapshot {
	uint32_t rising_sequence;
	uint32_t last_period_cycles;
	uint32_t last_edge_uptime_ms;
	uint32_t period_samples;
	int initialization_error;
	bool have_edge;
	bool panel_te_enabled;
};

static const struct gpio_dt_spec te_gpio = GPIO_DT_SPEC_GET(PICOSYSTEM_DISPLAY_SYNC_NODE, te_gpios);
static const struct device *const mipi_dbi = DEVICE_DT_GET(PICOSYSTEM_MIPI_DBI_NODE);
static const struct mipi_dbi_config mipi_dbi_config =
	MIPI_DBI_CONFIG_DT(PICOSYSTEM_DISPLAY_NODE, SPI_WORD_SET(8) | SPI_OP_MODE_MASTER, 0);

static struct k_spinlock metrics_lock;
static struct k_sem rising_edge_sem;
static struct gpio_callback te_callback;
static atomic_t synchronization_requested = ATOMIC_INIT(1);
static struct display_sync_metrics metrics = {
	.initialization_error = -EAGAIN,
};

BUILD_ASSERT(DT_SAME_NODE(PICOSYSTEM_MIPI_DBI_NODE, DT_PARENT(PICOSYSTEM_DISPLAY_NODE)));

static void increment_saturated(uint32_t *value)
{
	if (*value < UINT32_MAX) {
		++*value;
	}
}

static void timing_accumulator_add(struct timing_accumulator *accumulator, uint32_t cycles)
{
	if (accumulator->samples == UINT32_MAX) {
		return;
	}

	if ((accumulator->samples == 0U) || (cycles < accumulator->min_cycles)) {
		accumulator->min_cycles = cycles;
	}
	if ((accumulator->samples == 0U) || (cycles > accumulator->max_cycles)) {
		accumulator->max_cycles = cycles;
	}

	accumulator->sum_cycles += cycles;
	++accumulator->samples;
}

static void te_gpio_callback(const struct device *port, struct gpio_callback *callback,
			     gpio_port_pins_t pins)
{
	ARG_UNUSED(callback);
	ARG_UNUSED(pins);

	const int level = gpio_pin_get_raw(port, te_gpio.pin);
	const uint32_t now_cycles = k_cycle_get_32();
	const uint32_t now_uptime_ms = k_uptime_get_32();
	const k_spinlock_key_t key = k_spin_lock(&metrics_lock);

	if (level < 0) {
		increment_saturated(&metrics.gpio_read_errors);
		k_spin_unlock(&metrics_lock, key);
		return;
	}

	if (level != 0) {
		++metrics.rising_sequence;
		increment_saturated(&metrics.rising_edges);
		if (metrics.have_rising) {
			metrics.last_period_cycles = now_cycles - metrics.previous_rising_cycles;
			timing_accumulator_add(&metrics.period, metrics.last_period_cycles);
		}
		if (metrics.have_falling) {
			timing_accumulator_add(&metrics.low,
					       now_cycles - metrics.previous_falling_cycles);
		}
		metrics.previous_rising_cycles = now_cycles;
		metrics.have_rising = true;
	} else {
		increment_saturated(&metrics.falling_edges);
		if (metrics.have_rising) {
			timing_accumulator_add(&metrics.high,
					       now_cycles - metrics.previous_rising_cycles);
		}
		metrics.previous_falling_cycles = now_cycles;
		metrics.have_falling = true;
	}

	metrics.last_edge_uptime_ms = now_uptime_ms;
	metrics.have_edge = true;
	metrics.signal_high = level != 0;
	k_spin_unlock(&metrics_lock, key);

	if (level != 0) {
		k_sem_give(&rising_edge_sem);
	}
}

static uint32_t cycles_to_us(uint32_t cycles)
{
	return k_cyc_to_us_floor32(cycles);
}

static void copy_timing_stats(const struct timing_accumulator *source, uint32_t *samples,
			      uint32_t *mean_us, uint32_t *min_us, uint32_t *max_us)
{
	*samples = source->samples;
	if (source->samples == 0U) {
		*mean_us = 0U;
		*min_us = 0U;
		*max_us = 0U;
		return;
	}

	*mean_us = cycles_to_us((uint32_t)(source->sum_cycles / source->samples));
	*min_us = cycles_to_us(source->min_cycles);
	*max_us = cycles_to_us(source->max_cycles);
}

static void stop_gpio_capture(void)
{
	const int interrupt_err =
		gpio_pin_interrupt_configure(te_gpio.port, te_gpio.pin, GPIO_INT_DISABLE);
	if (interrupt_err != 0) {
		LOG_ERR("Failed to disable GP8 TE interrupt (%d)", interrupt_err);
	}

	const int callback_err = gpio_remove_callback(te_gpio.port, &te_callback);
	if (callback_err != 0) {
		LOG_ERR("Failed to remove GP8 TE callback (%d)", callback_err);
	}
}

static int record_initialization_error(int err)
{
	const k_spinlock_key_t key = k_spin_lock(&metrics_lock);
	metrics.initialization_error = err;
	k_spin_unlock(&metrics_lock, key);
	return err;
}

static struct display_sync_metrics read_metrics_snapshot(void)
{
	const k_spinlock_key_t key = k_spin_lock(&metrics_lock);
	const struct display_sync_metrics snapshot = metrics;
	k_spin_unlock(&metrics_lock, key);
	return snapshot;
}

static struct display_sync_signal_snapshot read_signal_snapshot(void)
{
	const k_spinlock_key_t key = k_spin_lock(&metrics_lock);
	const struct display_sync_signal_snapshot snapshot = {
		.rising_sequence = metrics.rising_sequence,
		.last_period_cycles = metrics.last_period_cycles,
		.last_edge_uptime_ms = metrics.last_edge_uptime_ms,
		.period_samples = metrics.period.samples,
		.initialization_error = metrics.initialization_error,
		.have_edge = metrics.have_edge,
		.panel_te_enabled = metrics.panel_te_enabled,
	};
	k_spin_unlock(&metrics_lock, key);
	return snapshot;
}

static bool signal_is_qualified(const struct display_sync_signal_snapshot *snapshot,
				uint32_t now_uptime_ms)
{
	if ((snapshot->initialization_error != 0) || !snapshot->panel_te_enabled ||
	    !snapshot->have_edge || (snapshot->period_samples < TE_MIN_PERIOD_SAMPLES)) {
		return false;
	}

	const uint32_t last_period_us = cycles_to_us(snapshot->last_period_cycles);
	const uint32_t last_edge_age_ms = now_uptime_ms - snapshot->last_edge_uptime_ms;

	return (last_period_us >= TE_MIN_PERIOD_US) && (last_period_us <= TE_MAX_PERIOD_US) &&
	       (last_edge_age_ms <= DIV_ROUND_UP(TE_SIGNAL_STALE_US, USEC_PER_MSEC));
}

static void record_sync_result(bool synchronized, bool timed_out, uint32_t wait_cycles)
{
	const k_spinlock_key_t key = k_spin_lock(&metrics_lock);

	if (synchronized) {
		increment_saturated(&metrics.synchronized_presents);
		metrics.last_wait_cycles = wait_cycles;
		metrics.max_wait_cycles = MAX(metrics.max_wait_cycles, wait_cycles);
	} else if (timed_out) {
		increment_saturated(&metrics.timed_out_presents);
		metrics.last_wait_cycles = wait_cycles;
		metrics.max_wait_cycles = MAX(metrics.max_wait_cycles, wait_cycles);
	} else {
		increment_saturated(&metrics.bypassed_presents);
	}

	k_spin_unlock(&metrics_lock, key);
}

int picosystem_display_sync_init(void)
{
	if (!gpio_is_ready_dt(&te_gpio)) {
		LOG_ERR("GP8 TE GPIO controller is not ready");
		return record_initialization_error(-ENODEV);
	}
	if (!device_is_ready(mipi_dbi)) {
		LOG_ERR("MIPI DBI controller is not ready");
		return record_initialization_error(-ENODEV);
	}

	int err = gpio_pin_configure_dt(&te_gpio, GPIO_INPUT);
	if (err != 0) {
		LOG_ERR("Failed to configure GP8 as the TE input (%d)", err);
		return record_initialization_error(err);
	}

	k_sem_init(&rising_edge_sem, 0U, 1U);
	gpio_init_callback(&te_callback, te_gpio_callback, BIT(te_gpio.pin));
	err = gpio_add_callback(te_gpio.port, &te_callback);
	if (err != 0) {
		LOG_ERR("Failed to add GP8 TE callback (%d)", err);
		return record_initialization_error(err);
	}

	err = gpio_pin_interrupt_configure(te_gpio.port, te_gpio.pin, GPIO_INT_EDGE_BOTH);
	if (err != 0) {
		LOG_ERR("Failed to enable GP8 TE edge interrupts (%d)", err);
		const int callback_err = gpio_remove_callback(te_gpio.port, &te_callback);
		if (callback_err != 0) {
			LOG_ERR("Failed to remove GP8 callback after setup error (%d)",
				callback_err);
		}
		return record_initialization_error(err);
	}

	const uint8_t te_mode = TE_VBLANK_ONLY;
	err = mipi_dbi_command_write(mipi_dbi, &mipi_dbi_config, MIPI_DCS_SET_TEAR_ON, &te_mode,
				     sizeof(te_mode));
	if (err != 0) {
		LOG_ERR("Failed to enable the ST7789 vertical-blank TE output (%d)", err);
		stop_gpio_capture();
		return record_initialization_error(err);
	}

	const int initial_level = gpio_pin_get_raw(te_gpio.port, te_gpio.pin);
	const k_spinlock_key_t key = k_spin_lock(&metrics_lock);
	metrics.panel_te_enabled = true;
	metrics.initialization_error = 0;
	if (initial_level >= 0) {
		metrics.signal_high = initial_level != 0;
	} else {
		increment_saturated(&metrics.gpio_read_errors);
	}
	k_spin_unlock(&metrics_lock, key);

	LOG_INF("ST7789 vertical-blank TE measurement enabled on GP8; sync will qualify "
		"automatically");
	return 0;
}

int picosystem_display_sync_get_stats(struct picosystem_display_sync_stats *stats)
{
	if (stats == NULL) {
		return -EINVAL;
	}

	const uint32_t now_uptime_ms = k_uptime_get_32();
	const struct display_sync_metrics snapshot = read_metrics_snapshot();
	const struct display_sync_signal_snapshot signal_snapshot = {
		.rising_sequence = snapshot.rising_sequence,
		.last_period_cycles = snapshot.last_period_cycles,
		.last_edge_uptime_ms = snapshot.last_edge_uptime_ms,
		.period_samples = snapshot.period.samples,
		.initialization_error = snapshot.initialization_error,
		.have_edge = snapshot.have_edge,
		.panel_te_enabled = snapshot.panel_te_enabled,
	};
	uint32_t last_edge_age_us = UINT32_MAX;
	if (snapshot.have_edge) {
		const uint32_t last_edge_age_ms = now_uptime_ms - snapshot.last_edge_uptime_ms;
		if (last_edge_age_ms <= (UINT32_MAX / USEC_PER_MSEC)) {
			last_edge_age_us = last_edge_age_ms * USEC_PER_MSEC;
		}
	}

	*stats = (struct picosystem_display_sync_stats){
		.rising_edges = snapshot.rising_edges,
		.falling_edges = snapshot.falling_edges,
		.gpio_read_errors = snapshot.gpio_read_errors,
		.last_edge_age_us = last_edge_age_us,
		.panel_te_enabled = snapshot.panel_te_enabled,
		.signal_high = snapshot.signal_high,
		.signal_qualified = signal_is_qualified(&signal_snapshot, now_uptime_ms),
		.synchronization_requested = atomic_get(&synchronization_requested) != 0,
		.synchronized_presents = snapshot.synchronized_presents,
		.bypassed_presents = snapshot.bypassed_presents,
		.timed_out_presents = snapshot.timed_out_presents,
		.last_wait_us = cycles_to_us(snapshot.last_wait_cycles),
		.max_wait_us = cycles_to_us(snapshot.max_wait_cycles),
	};
	copy_timing_stats(&snapshot.period, &stats->period_samples, &stats->period_mean_us,
			  &stats->period_min_us, &stats->period_max_us);
	copy_timing_stats(&snapshot.high, &stats->high_samples, &stats->high_mean_us,
			  &stats->high_min_us, &stats->high_max_us);
	copy_timing_stats(&snapshot.low, &stats->low_samples, &stats->low_mean_us,
			  &stats->low_min_us, &stats->low_max_us);

	return snapshot.initialization_error;
}

int picosystem_display_sync_set_enabled(bool enabled)
{
	const struct display_sync_signal_snapshot snapshot = read_signal_snapshot();
	if (enabled && (snapshot.initialization_error != 0)) {
		return snapshot.initialization_error;
	}

	atomic_set(&synchronization_requested, enabled ? 1 : 0);
	return 0;
}

bool picosystem_display_sync_wait_for_vblank(void)
{
	if (atomic_get(&synchronization_requested) == 0) {
		record_sync_result(false, false, 0U);
		return false;
	}

	const uint32_t qualification_uptime_ms = k_uptime_get_32();
	struct display_sync_signal_snapshot snapshot = read_signal_snapshot();
	if (!signal_is_qualified(&snapshot, qualification_uptime_ms)) {
		record_sync_result(false, false, 0U);
		return false;
	}

	const uint32_t initial_rising_sequence = snapshot.rising_sequence;
	const uint32_t start_cycles = k_cycle_get_32();
	const int64_t deadline_ms = k_uptime_get() + TE_WAIT_TIMEOUT_MS;

	while (true) {
		const int64_t remaining_ms = deadline_ms - k_uptime_get();
		if (remaining_ms <= 0) {
			break;
		}

		const int err = k_sem_take(&rising_edge_sem, K_MSEC(remaining_ms));
		if (err != 0) {
			break;
		}

		snapshot = read_signal_snapshot();
		if (snapshot.rising_sequence != initial_rising_sequence) {
			const uint32_t wait_cycles = k_cycle_get_32() - start_cycles;
			record_sync_result(true, false, wait_cycles);
			return true;
		}
	}

	const uint32_t wait_cycles = k_cycle_get_32() - start_cycles;
	record_sync_result(false, true, wait_cycles);
	return false;
}
