/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/util.h>

#include "battery.h"
#include "core1_runtime.h"
#include "diagnostic_shell.h"
#include "display_sync.h"
#include "fixed_rate_scheduler.h"
#include "game_control.h"
#include "game_demo.h"
#include "piezo.h"
#include "power_status.h"

LOG_MODULE_REGISTER(toy_factory, LOG_LEVEL_INF);

#define PIEZO_TEST_FREQUENCY_HZ         440U
#define PIEZO_TEST_DURATION_MS          180U
#define DIAGNOSTIC_INTERVAL_MS          100
#define STACK_SAMPLE_INTERVAL_MS        1000
#define STATUS_LOG_INTERVAL_MS          30000
#define PAUSED_POLL_INTERVAL_MS         8
#define OVERLOAD_RECOVERY_MS            1
#define OVERLOAD_RECOVERY_BACKLOG_TICKS 2U

BUILD_ASSERT(CONFIG_MAIN_THREAD_PRIORITY < CONFIG_SHELL_THREAD_PRIORITY);

struct named_gpio {
	const char *name;
	struct gpio_dt_spec gpio;
};

struct game_runtime_control {
	struct picosystem_game_input remote_input;
	bool paused;
	bool remote_input_enabled;
};

static const struct named_gpio buttons[PICOSYSTEM_BUTTON_COUNT] = {
	[PICOSYSTEM_BUTTON_UP] = {.name = "UP",
				  .gpio = GPIO_DT_SPEC_GET(DT_NODELABEL(button_up), gpios)},
	[PICOSYSTEM_BUTTON_DOWN] =
		{
			.name = "DOWN",
			.gpio = GPIO_DT_SPEC_GET(DT_NODELABEL(button_down), gpios),
		},
	[PICOSYSTEM_BUTTON_LEFT] =
		{
			.name = "LEFT",
			.gpio = GPIO_DT_SPEC_GET(DT_NODELABEL(button_left), gpios),
		},
	[PICOSYSTEM_BUTTON_RIGHT] =
		{
			.name = "RIGHT",
			.gpio = GPIO_DT_SPEC_GET(DT_NODELABEL(button_right), gpios),
		},
	[PICOSYSTEM_BUTTON_A] = {.name = "A",
				 .gpio = GPIO_DT_SPEC_GET(DT_NODELABEL(button_a), gpios)},
	[PICOSYSTEM_BUTTON_B] = {.name = "B",
				 .gpio = GPIO_DT_SPEC_GET(DT_NODELABEL(button_b), gpios)},
	[PICOSYSTEM_BUTTON_X] = {.name = "X",
				 .gpio = GPIO_DT_SPEC_GET(DT_NODELABEL(button_x), gpios)},
	[PICOSYSTEM_BUTTON_Y] = {.name = "Y",
				 .gpio = GPIO_DT_SPEC_GET(DT_NODELABEL(button_y), gpios)},
};

static const struct gpio_dt_spec led_red = GPIO_DT_SPEC_GET(DT_NODELABEL(led_red), gpios);
static const struct gpio_dt_spec led_green = GPIO_DT_SPEC_GET(DT_NODELABEL(led_green), gpios);
static const struct gpio_dt_spec led_blue = GPIO_DT_SPEC_GET(DT_NODELABEL(led_blue), gpios);

static int configure_input(const struct named_gpio *input)
{
	if (!gpio_is_ready_dt(&input->gpio)) {
		LOG_ERR("%s GPIO controller is not ready", input->name);
		return -ENODEV;
	}

	const int err = gpio_pin_configure_dt(&input->gpio, GPIO_INPUT);
	if (err != 0) {
		LOG_ERR("Failed to configure %s button (%d)", input->name, err);
		return err;
	}

	return 0;
}

static int configure_output(const char *name, const struct gpio_dt_spec *output)
{
	if (!gpio_is_ready_dt(output)) {
		LOG_ERR("%s GPIO controller is not ready", name);
		return -ENODEV;
	}

	const int err = gpio_pin_configure_dt(output, GPIO_OUTPUT_INACTIVE);
	if (err != 0) {
		LOG_ERR("Failed to configure %s output (%d)", name, err);
		return err;
	}

	return 0;
}

static int set_rgb(bool red, bool green, bool blue)
{
	int err = gpio_pin_set_dt(&led_red, red);
	if (err != 0) {
		return err;
	}

	err = gpio_pin_set_dt(&led_green, green);
	if (err != 0) {
		return err;
	}

	return gpio_pin_set_dt(&led_blue, blue);
}

static int run_led_self_test(void)
{
	static const bool colors[][3] = {
		{true, false, false},
		{false, true, false},
		{false, false, true},
		{false, false, false},
	};

	for (size_t i = 0; i < ARRAY_SIZE(colors); ++i) {
		const int err = set_rgb(colors[i][0], colors[i][1], colors[i][2]);
		if (err != 0) {
			return err;
		}
		k_msleep(200);
	}

	return 0;
}

static int read_buttons(uint32_t *state)
{
	uint32_t next_state = 0U;

	for (size_t i = 0; i < ARRAY_SIZE(buttons); ++i) {
		const int value = gpio_pin_get_dt(&buttons[i].gpio);
		if (value < 0) {
			LOG_ERR("Failed to read %s button (%d)", buttons[i].name, value);
			return value;
		}

		if (value != 0) {
			next_state |= BIT(i);
		}
	}

	*state = next_state;
	return 0;
}

static void log_button_changes(uint32_t previous_state, uint32_t state)
{
	const uint32_t changes = previous_state ^ state;

	for (size_t i = 0; i < ARRAY_SIZE(buttons); ++i) {
		if ((changes & BIT(i)) != 0U) {
			const bool pressed = (state & BIT(i)) != 0U;
			LOG_INF("%s %s", buttons[i].name, pressed ? "pressed" : "released");
		}
	}
}

static int read_and_log_battery(struct picosystem_battery_sample *sample)
{
	const int err = picosystem_battery_read(sample);
	if (err != 0) {
		LOG_ERR("Battery voltage read failed (%d)", err);
		return err;
	}

	if (!sample->plausible) {
		LOG_WRN("Battery voltage outside plausible LiPo range: %u mV (raw mean %u)",
			sample->millivolts, sample->raw_average);
		return 0;
	}

	LOG_INF("battery: %u mV (raw mean %u)", sample->millivolts, sample->raw_average);
	return 0;
}

static void log_power_status(const struct picosystem_power_status *status)
{
	const char *const state_name = picosystem_power_state_name(status->state);
	const char *const usb_name = status->usb_power_present ? "present" : "absent";
	const char *const charge_name = status->charging ? "active" : "inactive";

	if (status->state == PICOSYSTEM_POWER_STATE_CHARGE_WITHOUT_USB) {
		LOG_WRN("power: %s (usb=%s, charge=%s)", state_name, usb_name, charge_name);
		return;
	}

	LOG_INF("power: %s (usb=%s, charge=%s)", state_name, usb_name, charge_name);
}

static bool power_status_equal(const struct picosystem_power_status *left,
			       const struct picosystem_power_status *right)
{
	return (left->usb_power_present == right->usb_power_present) &&
	       (left->charging == right->charging);
}

static void apply_led_mode(enum picosystem_led_mode mode, bool *red, bool *green, bool *blue)
{
	switch (mode) {
	case PICOSYSTEM_LED_MODE_OFF:
		*red = false;
		*green = false;
		*blue = false;
		break;
	case PICOSYSTEM_LED_MODE_RED:
		*red = true;
		*green = false;
		*blue = false;
		break;
	case PICOSYSTEM_LED_MODE_GREEN:
		*red = false;
		*green = true;
		*blue = false;
		break;
	case PICOSYSTEM_LED_MODE_BLUE:
		*red = false;
		*green = false;
		*blue = true;
		break;
	case PICOSYSTEM_LED_MODE_WHITE:
		*red = true;
		*green = true;
		*blue = true;
		break;
	case PICOSYSTEM_LED_MODE_AUTO:
	default:
		break;
	}
}

static struct picosystem_game_input game_input_from_buttons(uint32_t buttons_state)
{
	struct picosystem_game_input input = {0};

	if ((buttons_state & BIT(PICOSYSTEM_BUTTON_LEFT)) != 0U) {
		--input.horizontal;
	}
	if ((buttons_state & BIT(PICOSYSTEM_BUTTON_RIGHT)) != 0U) {
		++input.horizontal;
	}
	if ((buttons_state & BIT(PICOSYSTEM_BUTTON_UP)) != 0U) {
		--input.vertical;
	}
	if ((buttons_state & BIT(PICOSYSTEM_BUTTON_DOWN)) != 0U) {
		++input.vertical;
	}

	return input;
}

static struct picosystem_game_input
selected_game_input(const struct game_runtime_control *control,
		    const struct picosystem_game_input *physical_input)
{
	return control->remote_input_enabled ? control->remote_input : *physical_input;
}

static int fill_game_control_state(const struct game_runtime_control *control,
				   const struct picosystem_game_demo_state *game,
				   const struct picosystem_game_input *physical_input,
				   struct picosystem_game_control_state *state)
{
	struct picosystem_game_demo_stats stats;
	const int err = picosystem_game_demo_get_stats(game, &stats);
	if (err != 0) {
		return err;
	}
	const struct picosystem_physics_body *const focus =
		picosystem_game_world_focus_body(&game->world);
	if (focus == NULL) {
		return -EIO;
	}

	*state = (struct picosystem_game_control_state){
		.focus_x_fixed = focus->center.x,
		.focus_y_fixed = focus->center.y,
		.focus_velocity_x_fixed_per_tick = focus->velocity_per_tick.x,
		.focus_velocity_y_fixed_per_tick = focus->velocity_per_tick.y,
		.focus_angular_velocity_fixed_per_tick = focus->angular_velocity_per_tick,
		.logic_tick_count = game->world.logic_tick_count,
		.state_hash = picosystem_game_demo_state_hash(game),
		.published_snapshot_sequence = game->snapshot_sequence,
		.presented_snapshot_sequence = stats.presented_snapshot_sequence,
		.focus_angle_turns = focus->angle_turns,
		.input = selected_game_input(control, physical_input),
		.focus_body_id = focus->id,
		.focus_shape = focus->shape,
		.paused = control->paused,
		.remote_input_enabled = control->remote_input_enabled,
	};
	return 0;
}

static int process_game_control_requests(struct game_runtime_control *control,
					 struct picosystem_game_demo_state *game,
					 struct picosystem_fixed_rate_scheduler *scheduler,
					 const struct picosystem_game_input *physical_input)
{
	while (true) {
		struct picosystem_game_control_request request;
		const int take_err = picosystem_game_control_take(&request);
		if (take_err == -ENOMSG) {
			return 0;
		}
		if (take_err != 0) {
			return take_err;
		}

		int result = 0;
		switch (request.operation) {
		case PICOSYSTEM_GAME_CONTROL_PAUSE:
			control->paused = true;
			break;
		case PICOSYSTEM_GAME_CONTROL_RUN:
			if (control->paused) {
				result = picosystem_fixed_rate_scheduler_init(
					scheduler, k_uptime_ticks(), CONFIG_SYS_CLOCK_TICKS_PER_SEC,
					PICOSYSTEM_GAME_TICK_RATE_HZ);
				if (result == 0) {
					result = picosystem_game_demo_restart_measurement(game);
				}
				if (result == 0) {
					control->paused = false;
				}
			}
			break;
		case PICOSYSTEM_GAME_CONTROL_RESET:
			if (!control->paused) {
				result = -EBUSY;
				break;
			}
			result = picosystem_game_demo_reset(game);
			if (result == 0) {
				control->remote_input = (struct picosystem_game_input){0};
				control->remote_input_enabled = true;
			}
			break;
		case PICOSYSTEM_GAME_CONTROL_STEP:
			if (!control->paused) {
				result = -EBUSY;
				break;
			}
			if ((request.step_count == 0U) ||
			    (request.step_count > PICOSYSTEM_GAME_CONTROL_MAX_STEPS)) {
				result = -ERANGE;
				break;
			}

			for (uint32_t step = 0U; step < request.step_count; ++step) {
				const struct picosystem_game_input input =
					selected_game_input(control, physical_input);
				result = picosystem_game_demo_update(game, &input);
				if (result != 0) {
					break;
				}
			}
			break;
		case PICOSYSTEM_GAME_CONTROL_SET_INPUT:
			if ((request.input.horizontal < -1) || (request.input.horizontal > 1) ||
			    (request.input.vertical < -1) || (request.input.vertical > 1)) {
				result = -ERANGE;
				break;
			}
			control->remote_input = request.input;
			control->remote_input_enabled = request.remote_input_enabled;
			break;
		case PICOSYSTEM_GAME_CONTROL_GET_STATE:
			break;
		default:
			result = -EINVAL;
			break;
		}

		struct picosystem_game_control_state response_state = {0};
		const int state_err =
			fill_game_control_state(control, game, physical_input, &response_state);
		if ((result == 0) && (state_err != 0)) {
			result = state_err;
		}

		const int complete_err =
			picosystem_game_control_complete(request.id, result, &response_state);
		if (complete_err != 0) {
			LOG_WRN("Failed to acknowledge game-control request %u (%d)", request.id,
				complete_err);
		}

		if ((result != 0) &&
		    ((request.operation == PICOSYSTEM_GAME_CONTROL_STEP) ||
		     (request.operation == PICOSYSTEM_GAME_CONTROL_RUN) ||
		     (request.operation == PICOSYSTEM_GAME_CONTROL_RESET)) &&
		    (result != -EBUSY) && (result != -ERANGE)) {
			return result;
		}
	}
}

static int sample_main_stack(struct picosystem_runtime_metrics *runtime)
{
	if (runtime == NULL) {
		return -EINVAL;
	}

	size_t unused_bytes;
	const int err = k_thread_stack_space_get(k_current_get(), &unused_bytes);
	if (err != 0) {
		return err;
	}

	if (unused_bytes > CONFIG_MAIN_STACK_SIZE) {
		return -ERANGE;
	}

	runtime->main_stack_size_bytes = CONFIG_MAIN_STACK_SIZE;
	runtime->main_stack_used_bytes = CONFIG_MAIN_STACK_SIZE - unused_bytes;
	return 0;
}

static int publish_diagnostic_snapshot(const struct picosystem_battery_sample *battery,
				       int64_t battery_sample_uptime_ms,
				       const struct picosystem_power_status *power,
				       const struct picosystem_game_demo_stats *game,
				       const struct picosystem_runtime_metrics *runtime,
				       uint32_t buttons_state)
{
	const struct picosystem_diagnostic_snapshot snapshot = {
		.battery = *battery,
		.power = *power,
		.game = *game,
		.runtime = *runtime,
		.snapshot_uptime_ms = k_uptime_get(),
		.battery_sample_uptime_ms = battery_sample_uptime_ms,
		.buttons = buttons_state,
	};

	return picosystem_diagnostic_shell_publish(&snapshot);
}

int main(void)
{
	struct picosystem_battery_sample battery_sample;
	static struct picosystem_game_demo_state game_state;
	struct picosystem_game_demo_stats game_stats;
	struct game_runtime_control game_control = {0};
	struct picosystem_power_status power_status;
	struct picosystem_runtime_metrics runtime_metrics;

	for (size_t i = 0; i < ARRAY_SIZE(buttons); ++i) {
		const int err = configure_input(&buttons[i]);
		if (err != 0) {
			return err;
		}
	}

	int err = configure_output("red LED", &led_red);
	if (err != 0) {
		return err;
	}

	err = configure_output("green LED", &led_green);
	if (err != 0) {
		return err;
	}

	err = configure_output("blue LED", &led_blue);
	if (err != 0) {
		return err;
	}

	err = picosystem_piezo_init();
	if (err != 0) {
		LOG_ERR("Piezo initialization failed (%d)", err);
		return err;
	}

	err = picosystem_battery_init();
	if (err != 0) {
		LOG_ERR("Battery ADC initialization failed (%d)", err);
		return err;
	}

	err = picosystem_power_status_init();
	if (err != 0) {
		LOG_ERR("Power-status initialization failed (%d)", err);
		return err;
	}

	err = run_led_self_test();
	if (err != 0) {
		LOG_ERR("RGB LED self-test failed (%d)", err);
		return err;
	}

#if defined(CONFIG_TOY_FACTORY_CORE1_RUNTIME)
	err = picosystem_core1_init();
	if (err != 0) {
		LOG_WRN("Core 1 health probe failed (%d); continuing on core 0", err);
	} else {
		LOG_INF("Core 1 auxiliary runtime passed its shared-memory health probe");
	}
#endif

	err = picosystem_game_demo_init(&game_state);
	if (err != 0) {
		LOG_ERR("Framebuffer game demo failed to initialize (%d)", err);
		const int led_err = set_rgb(true, false, false);
		if (led_err != 0) {
			LOG_ERR("Failed to indicate graphics error on RGB LED (%d)", led_err);
		}
		return err;
	}

	err = picosystem_display_sync_init();
	if (err != 0) {
		LOG_WRN("Display TE measurement is unavailable (%d); continuing unsynchronized",
			err);
	}

	err = read_and_log_battery(&battery_sample);
	if (err != 0) {
		return err;
	}
	int64_t battery_sample_uptime_ms = k_uptime_get();

	err = picosystem_power_status_read(&power_status);
	if (err != 0) {
		LOG_ERR("Power-status read failed (%d)", err);
		return err;
	}
	log_power_status(&power_status);

	err = sample_main_stack(&runtime_metrics);
	if (err != 0) {
		LOG_ERR("Failed to sample main stack usage (%d)", err);
		return err;
	}

	err = picosystem_game_demo_get_stats(&game_state, &game_stats);
	if (err != 0) {
		LOG_ERR("Failed to read initial game metrics (%d)", err);
		return err;
	}

	LOG_INF("PicoSystem 120 Hz physics lab and asynchronous renderer ready");
	LOG_INF("D-pad tilts gravity for all bodies; A queues a full redraw for comparison");
	LOG_INF("B plays a short 440 Hz piezo tone; Y resets the physics world");
	LOG_INF("A=red, B=green, X=blue, Y=white on the RGB LED");
	LOG_INF("GP2 remains an input; the automatic red charge indicator is enabled");
	LOG_INF("USB diagnostics ready; enter 'picosystem -h'");

	uint32_t previous_state = 0U;
	err = publish_diagnostic_snapshot(&battery_sample, battery_sample_uptime_ms, &power_status,
					  &game_stats, &runtime_metrics, previous_state);
	if (err != 0) {
		LOG_ERR("Failed to publish initial diagnostic snapshot (%d)", err);
		return err;
	}

	struct picosystem_fixed_rate_scheduler game_scheduler;
	err = picosystem_game_demo_start_simulation(&game_state);
	if (err != 0) {
		LOG_ERR("Failed to start the measured simulation interval (%d)", err);
		return err;
	}
	err = picosystem_fixed_rate_scheduler_init(&game_scheduler, k_uptime_ticks(),
						   CONFIG_SYS_CLOCK_TICKS_PER_SEC,
						   PICOSYSTEM_GAME_TICK_RATE_HZ);
	if (err != 0) {
		LOG_ERR("Failed to initialize the game scheduler (%d)", err);
		return err;
	}
	const int64_t scheduling_start_ms = k_uptime_get();
	int64_t next_diagnostic_ms = scheduling_start_ms + DIAGNOSTIC_INTERVAL_MS;
	int64_t next_stack_sample_ms = scheduling_start_ms + STACK_SAMPLE_INTERVAL_MS;
	int64_t next_status_time = scheduling_start_ms + STATUS_LOG_INTERVAL_MS;

	while (true) {
		if (game_control.paused) {
			k_msleep(PAUSED_POLL_INTERVAL_MS);
		} else {
			const int64_t before_sleep_ticks = k_uptime_ticks();
			const int64_t sleep_ticks =
				game_scheduler.next_deadline_ticks - before_sleep_ticks;
			if (sleep_ticks > 0) {
				k_sleep(K_TICKS(sleep_ticks));
			} else if ((sleep_ticks < 0) &&
				   (picosystem_fixed_rate_scheduler_due(&game_scheduler,
									before_sleep_ticks) >=
				    OVERLOAD_RECOVERY_BACKLOG_TICKS)) {
				/* A single late tick may catch up and sleep naturally. Preserve a
				 * control-plane window once real backlog develops. */
				k_msleep(OVERLOAD_RECOVERY_MS);
			}
		}

		const int64_t tick_start_ticks = k_uptime_ticks();

		uint32_t state;
		struct picosystem_power_status next_power_status;

		err = read_buttons(&state);
		if (err != 0) {
			return err;
		}

		err = picosystem_power_status_read(&next_power_status);
		if (err != 0) {
			LOG_ERR("Power-status read failed (%d)", err);
			return err;
		}

		if (!power_status_equal(&power_status, &next_power_status)) {
			log_power_status(&next_power_status);
		}
		power_status = next_power_status;

		const int64_t now = k_uptime_get();
		const uint32_t pressed = state & ~previous_state;

		log_button_changes(previous_state, state);

		const struct picosystem_game_input physical_game_input =
			game_input_from_buttons(state);
		err = process_game_control_requests(&game_control, &game_state, &game_scheduler,
						    &physical_game_input);
		if (err != 0) {
			LOG_ERR("Game-control request failed (%d)", err);
			return err;
		}

		if ((pressed & BIT(PICOSYSTEM_BUTTON_Y)) != 0U) {
			err = picosystem_game_demo_reset(&game_state);
			if (err != 0) {
				LOG_ERR("Failed to reset physics world (%d)", err);
				return err;
			}

			if (!game_control.paused) {
				err = picosystem_fixed_rate_scheduler_init(
					&game_scheduler, tick_start_ticks,
					CONFIG_SYS_CLOCK_TICKS_PER_SEC,
					PICOSYSTEM_GAME_TICK_RATE_HZ);
				if (err != 0) {
					LOG_ERR("Failed to restart game scheduler after reset (%d)",
						err);
					return err;
				}
			}
			LOG_INF("Reset physics world from Y button");
		}

		const uint32_t due_ticks =
			game_control.paused ? 0U
					    : picosystem_fixed_rate_scheduler_due(&game_scheduler,
										  tick_start_ticks);
		if (due_ticks != 0U) {
			picosystem_game_demo_note_backlog(&game_state, due_ticks);
		}
		const uint32_t update_steps = MIN(due_ticks, PICOSYSTEM_GAME_MAX_CATCH_UP);
		for (uint32_t step = 0U; step < update_steps; ++step) {
			const struct picosystem_game_input game_input =
				selected_game_input(&game_control, &physical_game_input);
			err = picosystem_game_demo_update(&game_state, &game_input);
			if (err != 0) {
				LOG_ERR("Game logic update failed (%d)", err);
				return err;
			}

			picosystem_fixed_rate_scheduler_advance(&game_scheduler, 1U);
		}

		const uint32_t skipped_ticks = due_ticks - update_steps;
		if (skipped_ticks != 0U) {
			picosystem_game_demo_note_skipped_ticks(&game_state, skipped_ticks);
			picosystem_fixed_rate_scheduler_advance(&game_scheduler, skipped_ticks);
		}

		const bool redraw_requested = ((pressed & BIT(PICOSYSTEM_BUTTON_A)) != 0U) ||
					      picosystem_diagnostic_shell_take_redraw();
		if (redraw_requested) {
			err = picosystem_game_demo_request_redraw(&game_state);
			if (err != 0) {
				LOG_ERR("Failed to queue full framebuffer redraw (%d)", err);
				return err;
			}
			LOG_INF("Queued asynchronous full framebuffer redraw");
		}

		if ((pressed & BIT(PICOSYSTEM_BUTTON_B)) != 0U) {
			err = picosystem_piezo_play(PIEZO_TEST_FREQUENCY_HZ,
						    PIEZO_TEST_DURATION_MS);
			if (err != 0) {
				LOG_ERR("Piezo tone test failed (%d)", err);
				return err;
			}
		}

		struct picosystem_tone_request tone_request;
		err = picosystem_diagnostic_shell_take_tone(&tone_request);
		if (err == 0) {
			err = picosystem_piezo_play(tone_request.frequency_hz,
						    tone_request.duration_ms);
			if (err != 0) {
				LOG_ERR("Shell piezo tone failed (%d)", err);
				return err;
			}
		} else if (err != -ENOMSG) {
			LOG_ERR("Failed to take shell tone request (%d)", err);
			return err;
		}

		previous_state = state;

		const bool y_pressed = (state & BIT(PICOSYSTEM_BUTTON_Y)) != 0U;
		bool red = y_pressed || ((state & BIT(PICOSYSTEM_BUTTON_A)) != 0U);
		bool green = y_pressed || ((state & BIT(PICOSYSTEM_BUTTON_B)) != 0U);
		bool blue = y_pressed || ((state & BIT(PICOSYSTEM_BUTTON_X)) != 0U);

		if ((state & (BIT(PICOSYSTEM_BUTTON_A) | BIT(PICOSYSTEM_BUTTON_B) |
			      BIT(PICOSYSTEM_BUTTON_X) | BIT(PICOSYSTEM_BUTTON_Y))) == 0U) {
			blue = ((k_uptime_get() / 500) & 1) != 0;
		}

		apply_led_mode(picosystem_diagnostic_shell_led_mode(), &red, &green, &blue);

		err = set_rgb(red, green, blue);
		if (err != 0) {
			LOG_ERR("Failed to update RGB LED (%d)", err);
			return err;
		}

		err = picosystem_game_demo_renderer_error();
		if (err != 0) {
			LOG_ERR("Asynchronous renderer stopped (%d)", err);
			return err;
		}

		if (now >= next_stack_sample_ms) {
			err = sample_main_stack(&runtime_metrics);
			if (err != 0) {
				LOG_ERR("Failed to sample main stack usage (%d)", err);
				return err;
			}
			next_stack_sample_ms = now + STACK_SAMPLE_INTERVAL_MS;
		}

		const bool status_due = now >= next_status_time;
		if (status_due) {
			err = read_and_log_battery(&battery_sample);
			if (err != 0) {
				return err;
			}
			battery_sample_uptime_ms = k_uptime_get();
		}

		const bool diagnostic_due = now >= next_diagnostic_ms;
		if (diagnostic_due || status_due) {
			err = picosystem_game_demo_get_stats(&game_state, &game_stats);
			if (err != 0) {
				LOG_ERR("Failed to read game metrics (%d)", err);
				return err;
			}

			if (status_due) {
				LOG_INF("alive: uptime=%lld ms, buttons=0x%02x, power=%s, "
					"ticks=%u, frame=%u, present=%u us/%ux%u, skipped=%u, "
					"stacks=%u/%u+%u/%u bytes",
					now, state, picosystem_power_state_name(power_status.state),
					game_stats.logic_tick_count,
					game_stats.presented_frame_count,
					game_stats.graphics.last_present_time_us,
					game_stats.graphics.last_present_width,
					game_stats.graphics.last_present_height,
					game_stats.skipped_tick_count,
					runtime_metrics.main_stack_used_bytes,
					runtime_metrics.main_stack_size_bytes,
					game_stats.render_stack_used_bytes,
					game_stats.render_stack_size_bytes);
				next_status_time = now + STATUS_LOG_INTERVAL_MS;
			}

			err = publish_diagnostic_snapshot(&battery_sample, battery_sample_uptime_ms,
							  &power_status, &game_stats,
							  &runtime_metrics, state);
			if (err != 0) {
				LOG_ERR("Failed to publish diagnostic snapshot (%d)", err);
				return err;
			}

			if (diagnostic_due) {
				next_diagnostic_ms = now + DIAGNOSTIC_INTERVAL_MS;
			}
		}
	}

	return 0;
}
