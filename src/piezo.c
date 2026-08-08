/*
 * Copyright (c) 2026 PicoSystem Playground contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "piezo.h"

#include <errno.h>
#include <stdbool.h>
#include <stdint.h>

#include <zephyr/drivers/pwm.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(picosystem_piezo, LOG_LEVEL_INF);

#define PIEZO_MIN_FREQUENCY_HZ 100U
#define PIEZO_MAX_FREQUENCY_HZ 4000U
#define PIEZO_MAX_DURATION_MS  1000U
#define PIEZO_DRIVE_PULSE_NS   PWM_USEC(25U)

static const struct pwm_dt_spec piezo_pwm = PWM_DT_SPEC_GET(DT_NODELABEL(piezo));
static bool piezo_initialized;

static int silence(void)
{
	return pwm_set_pulse_dt(&piezo_pwm, 0U);
}

static void silence_work_handler(struct k_work *work)
{
	ARG_UNUSED(work);

	const int err = silence();
	if (err != 0) {
		LOG_ERR("Failed to silence piezo (%d)", err);
		return;
	}

	LOG_INF("Tone complete; piezo silent");
}

K_WORK_DELAYABLE_DEFINE(silence_work, silence_work_handler);

int picosystem_piezo_init(void)
{
	if (!pwm_is_ready_dt(&piezo_pwm)) {
		LOG_ERR("Piezo PWM controller is not ready");
		return -ENODEV;
	}

	const int err = silence();
	if (err != 0) {
		LOG_ERR("Failed to initialize piezo in the silent state (%d)", err);
		return err;
	}

	piezo_initialized = true;
	return 0;
}

int picosystem_piezo_validate(uint32_t frequency_hz, uint32_t duration_ms)
{
	if ((frequency_hz < PIEZO_MIN_FREQUENCY_HZ) || (frequency_hz > PIEZO_MAX_FREQUENCY_HZ) ||
	    (duration_ms == 0U) || (duration_ms > PIEZO_MAX_DURATION_MS)) {
		return -EINVAL;
	}

	return 0;
}

int picosystem_piezo_play(uint32_t frequency_hz, uint32_t duration_ms)
{
	if (!piezo_initialized) {
		return -EACCES;
	}

	const int validation_err = picosystem_piezo_validate(frequency_hz, duration_ms);
	if (validation_err != 0) {
		return validation_err;
	}

	struct k_work_sync sync;

	(void)k_work_cancel_delayable_sync(&silence_work, &sync);

	const uint32_t period_ns = PWM_SEC(1U) / frequency_hz;
	int err = pwm_set_dt(&piezo_pwm, period_ns, PIEZO_DRIVE_PULSE_NS);
	if (err != 0) {
		LOG_ERR("Failed to start %u Hz piezo tone (%d)", frequency_hz, err);
		const int silence_err = silence();
		if (silence_err != 0) {
			LOG_ERR("Failed to silence piezo after start error (%d)", silence_err);
		}
		return err;
	}

	err = k_work_reschedule(&silence_work, K_MSEC(duration_ms));
	if (err < 0) {
		LOG_ERR("Failed to schedule piezo shutoff (%d)", err);
		const int silence_err = silence();
		if (silence_err != 0) {
			LOG_ERR("Failed to silence piezo after scheduling error (%d)", silence_err);
		}
		return err;
	}

	LOG_INF("Playing %u Hz tone for %u ms", frequency_hz, duration_ms);
	return 0;
}
