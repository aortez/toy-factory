/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "core1_runtime.h"

#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <zephyr/device.h>
#include <zephyr/drivers/mbox.h>
#include <zephyr/irq.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/util.h>

#include <hardware/regs/intctrl.h>
#include <hardware/regs/psm.h>
#include <hardware/regs/sio.h>
#include <hardware/structs/psm.h>
#include <hardware/structs/scb.h>
#include <hardware/structs/sio.h>
#include <hardware/structs/timer.h>
#include <hardware/sync.h>

#define CORE1_PROTOCOL_MAGIC       0x54463143U
#define CORE1_PROTOCOL_VERSION     6U
#define CORE1_RESERVED_BANK_BYTES  4096U
#define CORE1_STACK_BYTES          4096U
#define CORE1_STACK_WORDS          (CORE1_STACK_BYTES / sizeof(uint32_t))
#define CORE1_STACK_CANARY         0xa5a5a5a5U
#define CORE1_HANDSHAKE_TIMEOUT_MS 50
#define CORE1_COMMAND_TIMEOUT_MS   50
#define CORE1_VECTOR_COUNT         48U
#define CORE1_PING_XOR             0x6d5a56a9U
#define CORE1_FIFO_EVENT           0x54464556U
#define CORE1_SCENE_STRIP_ROWS     120U
#define CORE1_SCENE_STRIP_COUNT    DIV_ROUND_UP(PICOSYSTEM_GRAPHICS_HEIGHT, CORE1_SCENE_STRIP_ROWS)
#define CORE1_STORAGE_SECTION      __attribute__((section(".core1_ram"), aligned(4096), used))

enum core1_command {
	CORE1_COMMAND_NONE,
	CORE1_COMMAND_PING,
	CORE1_COMMAND_DRAW_DENSE,
	CORE1_COMMAND_RENDER_SCENE,
	CORE1_COMMAND_RENDER_SCENE_STREAM,
	CORE1_COMMAND_STOP,
};

struct core1_mailbox {
	uint32_t magic;
	uint32_t protocol_version;
	volatile uint32_t state;
	volatile uint32_t core_id;
	volatile uint32_t command;
	volatile uint32_t requested_sequence;
	volatile uint32_t completed_sequence;
	volatile uint32_t request_value;
	volatile uint32_t response_value;
	volatile uint32_t dense_stage_time_us[PICOSYSTEM_DENSE_SCENE_STAGE_COUNT];
	volatile uint32_t dense_total_time_us;
	struct picosystem_scene_snapshot scene_snapshot;
	volatile uint32_t scene_raster_time_us;
	struct picosystem_scene_render_progress scene_progress;
	volatile uint32_t ready_strip_count;
	volatile uint32_t scene_strip_count;
	volatile uint32_t heartbeat_count;
	volatile int32_t error;
};

struct core1_storage {
	struct core1_mailbox mailbox;
	uint8_t mailbox_bank_padding[CORE1_RESERVED_BANK_BYTES - sizeof(struct core1_mailbox)];
	uint32_t stack[CORE1_STACK_WORDS];
};

static struct core1_storage core1_storage CORE1_STORAGE_SECTION;
static bool core1_ready;
static const struct device *const core1_mailbox = DEVICE_DT_GET(DT_NODELABEL(mbox));

K_MUTEX_DEFINE(core1_command_mutex);
K_SEM_DEFINE(core1_event, 0U, 1U);

BUILD_ASSERT(sizeof(struct core1_mailbox) <= CORE1_RESERVED_BANK_BYTES);
BUILD_ASSERT(sizeof(struct core1_storage) == (2U * CORE1_RESERVED_BANK_BYTES));
BUILD_ASSERT((CORE1_STACK_BYTES % sizeof(uint32_t)) == 0U);
BUILD_ASSERT(CORE1_VECTOR_COUNT >= 48U);

static inline void core1_memory_barrier(void)
{
	__asm__ volatile("dmb" ::: "memory");
}

static inline void core1_send_event(void)
{
	if ((sio_hw->cpuid == 1U) && ((sio_hw->fifo_st & SIO_FIFO_ST_RDY_BITS) != 0U)) {
		sio_hw->fifo_wr = CORE1_FIFO_EVENT;
	}
	__asm__ volatile("sev" ::: "memory");
}

static inline void core1_wait_for_event(void)
{
	__asm__ volatile("wfe" ::: "memory");
}

static inline void core1_disable_interrupts(void)
{
	__asm__ volatile("cpsid i" ::: "memory");
}

static uint32_t ping_response(uint32_t challenge)
{
	return ((challenge << 7U) | (challenge >> 25U)) ^ CORE1_PING_XOR;
}

static int core1_draw_dense(uint32_t frame_index)
{
	const uint32_t total_start_us = timer_hw->timerawl;
	for (enum picosystem_dense_scene_stage stage = PICOSYSTEM_DENSE_SCENE_STAGE_BACKGROUND;
	     stage < PICOSYSTEM_DENSE_SCENE_STAGE_COUNT; ++stage) {
		const uint32_t stage_start_us = timer_hw->timerawl;
		const int err = picosystem_dense_scene_draw_stage(stage, frame_index);
		core1_storage.mailbox.dense_stage_time_us[stage] =
			timer_hw->timerawl - stage_start_us;
		if (err != 0) {
			core1_storage.mailbox.dense_total_time_us =
				timer_hw->timerawl - total_start_us;
			return err;
		}
	}
	core1_storage.mailbox.dense_total_time_us = timer_hw->timerawl - total_start_us;
	return 0;
}

static int core1_render_scene_stream(void)
{
	const uint32_t raster_start_us = timer_hw->timerawl;
	core1_storage.mailbox.scene_raster_time_us = 0U;
	core1_storage.mailbox.ready_strip_count = 0U;
	core1_storage.mailbox.scene_strip_count = CORE1_SCENE_STRIP_COUNT;
	core1_storage.mailbox.scene_progress = (struct picosystem_scene_render_progress){0};

	for (uint32_t strip_index = 0U; strip_index < CORE1_SCENE_STRIP_COUNT; ++strip_index) {
		const uint16_t y = strip_index * CORE1_SCENE_STRIP_ROWS;
		const struct picosystem_rect region = {
			.x = 0U,
			.y = y,
			.width = PICOSYSTEM_GRAPHICS_WIDTH,
			.height = MIN(CORE1_SCENE_STRIP_ROWS, PICOSYSTEM_GRAPHICS_HEIGHT - y),
		};
		const int err = picosystem_scene_render_region_observed(
			&core1_storage.mailbox.scene_snapshot, &region,
			&core1_storage.mailbox.scene_progress);
		if (err != 0) {
			core1_storage.mailbox.scene_raster_time_us =
				timer_hw->timerawl - raster_start_us;
			return err;
		}

		core1_memory_barrier();
		core1_storage.mailbox.ready_strip_count = strip_index + 1U;
		core1_send_event();
	}

	core1_storage.mailbox.scene_raster_time_us = timer_hw->timerawl - raster_start_us;
	return 0;
}

static void core1_publish_fault(int error) __attribute__((noreturn));

static void core1_publish_fault(int error)
{
	core1_storage.mailbox.error = error;
	core1_storage.mailbox.state = PICOSYSTEM_CORE1_STATE_FAULT;
	core1_memory_barrier();
	core1_send_event();

	while (true) {
		core1_wait_for_event();
	}
}

static void core1_fault_handler(void) __attribute__((noreturn));

static void core1_fault_handler(void)
{
	core1_publish_fault(-EFAULT);
}

static void core1_entry(void) __attribute__((noreturn));

static void core1_entry(void)
{
	core1_disable_interrupts();
	if ((core1_storage.mailbox.magic != CORE1_PROTOCOL_MAGIC) ||
	    (core1_storage.mailbox.protocol_version != CORE1_PROTOCOL_VERSION)) {
		core1_publish_fault(-EPROTO);
	}
	if (sio_hw->cpuid != 1U) {
		core1_publish_fault(-ENODEV);
	}

	core1_storage.mailbox.core_id = sio_hw->cpuid;
	core1_storage.mailbox.error = 0;
	core1_storage.mailbox.state = PICOSYSTEM_CORE1_STATE_IDLE;
	core1_memory_barrier();
	core1_send_event();

	uint32_t completed_sequence = core1_storage.mailbox.completed_sequence;
	while (true) {
		core1_memory_barrier();
		const uint32_t requested_sequence = core1_storage.mailbox.requested_sequence;
		if (requested_sequence == completed_sequence) {
			core1_wait_for_event();
			continue;
		}

		core1_storage.mailbox.state = PICOSYSTEM_CORE1_STATE_RUNNING;
		core1_storage.mailbox.error = 0;
		core1_memory_barrier();

		switch ((enum core1_command)core1_storage.mailbox.command) {
		case CORE1_COMMAND_PING:
			core1_storage.mailbox.response_value =
				ping_response(core1_storage.mailbox.request_value);
			break;
		case CORE1_COMMAND_DRAW_DENSE:
			for (size_t stage = 0U; stage < PICOSYSTEM_DENSE_SCENE_STAGE_COUNT;
			     ++stage) {
				core1_storage.mailbox.dense_stage_time_us[stage] = 0U;
			}
			core1_storage.mailbox.dense_total_time_us = 0U;
			core1_storage.mailbox.error =
				core1_draw_dense(core1_storage.mailbox.request_value);
			break;
		case CORE1_COMMAND_RENDER_SCENE: {
			const uint32_t raster_start_us = timer_hw->timerawl;
			core1_storage.mailbox.scene_raster_time_us = 0U;
			core1_storage.mailbox.scene_progress =
				(struct picosystem_scene_render_progress){0};
			core1_storage.mailbox.error = picosystem_scene_render_full_observed(
				&core1_storage.mailbox.scene_snapshot,
				&core1_storage.mailbox.scene_progress);
			core1_storage.mailbox.scene_raster_time_us =
				timer_hw->timerawl - raster_start_us;
			break;
		}
		case CORE1_COMMAND_RENDER_SCENE_STREAM:
			core1_storage.mailbox.error = core1_render_scene_stream();
			break;
		case CORE1_COMMAND_STOP:
			core1_storage.mailbox.state = PICOSYSTEM_CORE1_STATE_STOPPED;
			core1_storage.mailbox.completed_sequence = requested_sequence;
			core1_memory_barrier();
			core1_send_event();
			while (true) {
				core1_wait_for_event();
			}
		case CORE1_COMMAND_NONE:
		default:
			core1_storage.mailbox.error = -ENOTSUP;
			break;
		}

		completed_sequence = requested_sequence;
		if (core1_storage.mailbox.heartbeat_count != UINT32_MAX) {
			++core1_storage.mailbox.heartbeat_count;
		}
		core1_storage.mailbox.state = PICOSYSTEM_CORE1_STATE_IDLE;
		core1_memory_barrier();
		core1_storage.mailbox.completed_sequence = completed_sequence;
		core1_send_event();
	}
}

static const uintptr_t core1_vector_table[CORE1_VECTOR_COUNT]
	__attribute__((aligned(256), used)) = {
		[0] = (uintptr_t)&core1_storage.stack[CORE1_STACK_WORDS],
		[1] = (uintptr_t)core1_entry,
		[2 ... CORE1_VECTOR_COUNT - 1U] = (uintptr_t)core1_fault_handler,
};

static bool deadline_expired(int64_t deadline_ms)
{
	return k_uptime_get() >= deadline_ms;
}

static void core1_mailbox_callback(const struct device *device, mbox_channel_id_t channel,
				   void *user_data, struct mbox_msg *message)
{
	ARG_UNUSED(device);
	ARG_UNUSED(channel);
	ARG_UNUSED(user_data);
	ARG_UNUSED(message);

	k_sem_give(&core1_event);
}

static int wait_for_core1_event(int64_t deadline_ms)
{
	const int64_t remaining_ms = deadline_ms - k_uptime_get();
	if (remaining_ms <= 0) {
		return -ETIMEDOUT;
	}

	const int err = k_sem_take(&core1_event, K_MSEC(remaining_ms));
	return (err == -EAGAIN) ? -ETIMEDOUT : err;
}

static int wait_for_fifo_value(uint32_t *value, int64_t deadline_ms)
{
	while ((sio_hw->fifo_st & SIO_FIFO_ST_VLD_BITS) == 0U) {
		if (deadline_expired(deadline_ms)) {
			return -ETIMEDOUT;
		}
		k_busy_wait(1U);
	}

	*value = sio_hw->fifo_rd;
	return 0;
}

static int write_fifo_value(uint32_t value, int64_t deadline_ms)
{
	while ((sio_hw->fifo_st & SIO_FIFO_ST_RDY_BITS) == 0U) {
		if (deadline_expired(deadline_ms)) {
			return -ETIMEDOUT;
		}
		k_busy_wait(1U);
	}

	sio_hw->fifo_wr = value;
	core1_send_event();
	return 0;
}

static void drain_fifo(void)
{
	while ((sio_hw->fifo_st & SIO_FIFO_ST_VLD_BITS) != 0U) {
		(void)sio_hw->fifo_rd;
	}
	sio_hw->fifo_st = SIO_FIFO_ST_ROE_BITS | SIO_FIFO_ST_WOF_BITS;
}

static int reset_core1(int64_t deadline_ms)
{
	hw_set_bits(&psm_hw->frce_off, PSM_FRCE_OFF_PROC1_BITS);
	while ((psm_hw->frce_off & PSM_FRCE_OFF_PROC1_BITS) == 0U) {
		if (deadline_expired(deadline_ms)) {
			return -ETIMEDOUT;
		}
	}

	drain_fifo();
	hw_clear_bits(&psm_hw->frce_off, PSM_FRCE_OFF_PROC1_BITS);

	uint32_t response;
	const int err = wait_for_fifo_value(&response, deadline_ms);
	if (err != 0) {
		return err;
	}
	return (response == 0U) ? 0 : -EPROTO;
}

static int launch_core1(int64_t deadline_ms)
{
	const uint32_t stack_pointer = (uint32_t)(uintptr_t)&core1_storage.stack[CORE1_STACK_WORDS];
	const uint32_t commands[] = {
		0U,
		0U,
		1U,
		(uint32_t)(uintptr_t)core1_vector_table,
		stack_pointer,
		(uint32_t)(uintptr_t)core1_entry,
	};

	size_t command_index = 0U;
	while (command_index < ARRAY_SIZE(commands)) {
		const uint32_t command = commands[command_index];
		if (command == 0U) {
			drain_fifo();
			core1_send_event();
		}

		int err = write_fifo_value(command, deadline_ms);
		if (err != 0) {
			return err;
		}

		uint32_t response;
		err = wait_for_fifo_value(&response, deadline_ms);
		if (err != 0) {
			return err;
		}
		command_index = (response == command) ? command_index + 1U : 0U;
	}

	return 0;
}

static int wait_for_state(enum picosystem_core1_state state, int64_t deadline_ms)
{
	while (true) {
		core1_memory_barrier();
		if (core1_storage.mailbox.state == (uint32_t)state) {
			return 0;
		}
		if (core1_storage.mailbox.state == PICOSYSTEM_CORE1_STATE_FAULT) {
			return (core1_storage.mailbox.error != 0) ? core1_storage.mailbox.error
								  : -EIO;
		}
		if (deadline_expired(deadline_ms)) {
			return -ETIMEDOUT;
		}
		k_usleep(50U);
	}
}

static void mark_core1_unavailable(int error)
{
	core1_ready = false;
	hw_set_bits(&psm_hw->frce_off, PSM_FRCE_OFF_PROC1_BITS);
	core1_storage.mailbox.error = error;
	core1_storage.mailbox.state = PICOSYSTEM_CORE1_STATE_FAULT;
	core1_memory_barrier();
}

int picosystem_core1_init(void)
{
	if (core1_ready) {
		return -EALREADY;
	}
	if (!device_is_ready(core1_mailbox)) {
		return -ENODEV;
	}

	memset((void *)&core1_storage.mailbox, 0, sizeof(core1_storage.mailbox));
	for (size_t index = 0U; index < ARRAY_SIZE(core1_storage.stack); ++index) {
		core1_storage.stack[index] = CORE1_STACK_CANARY;
	}
	core1_storage.mailbox.magic = CORE1_PROTOCOL_MAGIC;
	core1_storage.mailbox.protocol_version = CORE1_PROTOCOL_VERSION;
	core1_storage.mailbox.state = PICOSYSTEM_CORE1_STATE_BOOTING;
	core1_memory_barrier();

	irq_disable(SIO_IRQ_PROC0);
	const int64_t deadline_ms = k_uptime_get() + CORE1_HANDSHAKE_TIMEOUT_MS;
	int err = reset_core1(deadline_ms);
	if (err == 0) {
		err = launch_core1(deadline_ms);
	}
	if (err != 0) {
		mark_core1_unavailable(err);
		return err;
	}

	err = wait_for_state(PICOSYSTEM_CORE1_STATE_IDLE, deadline_ms);
	if (err != 0) {
		mark_core1_unavailable(err);
		return err;
	}
	err = mbox_register_callback(core1_mailbox, 0U, core1_mailbox_callback, NULL);
	if (err == 0) {
		err = mbox_set_enabled(core1_mailbox, 0U, true);
	}
	if (err != 0) {
		mark_core1_unavailable(err);
		return err;
	}
	core1_ready = true;

	uint32_t response;
	err = picosystem_core1_ping(0x01234567U, &response);
	if ((err != 0) || (response != ping_response(0x01234567U))) {
		const int probe_err = (err != 0) ? err : -EIO;
		mark_core1_unavailable(probe_err);
		return probe_err;
	}

	return 0;
}

static int start_command_locked(enum core1_command command, uint32_t request_value,
				uint32_t *sequence)
{
	if (!core1_ready) {
		return -EAGAIN;
	}

	core1_memory_barrier();
	if ((core1_storage.mailbox.state != PICOSYSTEM_CORE1_STATE_IDLE) ||
	    (core1_storage.mailbox.requested_sequence !=
	     core1_storage.mailbox.completed_sequence)) {
		return -EBUSY;
	}

	*sequence = core1_storage.mailbox.requested_sequence + 1U;
	k_sem_reset(&core1_event);
	core1_storage.mailbox.command = command;
	core1_storage.mailbox.request_value = request_value;
	core1_memory_barrier();
	core1_storage.mailbox.requested_sequence = *sequence;
	core1_send_event();
	return 0;
}

static int wait_for_command_locked(uint32_t sequence, int64_t deadline_ms)
{
	while (true) {
		core1_memory_barrier();
		if (core1_storage.mailbox.completed_sequence == sequence) {
			break;
		}
		if (core1_storage.mailbox.state == PICOSYSTEM_CORE1_STATE_FAULT) {
			return (core1_storage.mailbox.error != 0) ? core1_storage.mailbox.error
								  : -EIO;
		}
		if (deadline_expired(deadline_ms)) {
			return -ETIMEDOUT;
		}
		const int err = wait_for_core1_event(deadline_ms);
		if (err != 0) {
			return err;
		}
	}

	core1_memory_barrier();
	if (core1_storage.mailbox.error != 0) {
		return core1_storage.mailbox.error;
	}
	return 0;
}

static int execute_command_locked(enum core1_command command, uint32_t request_value)
{
	uint32_t sequence;
	int err = start_command_locked(command, request_value, &sequence);
	if (err != 0) {
		return err;
	}

	return wait_for_command_locked(sequence, k_uptime_get() + CORE1_COMMAND_TIMEOUT_MS);
}

int picosystem_core1_ping(uint32_t challenge, uint32_t *response)
{
	if (response == NULL) {
		return -EINVAL;
	}

	int err = k_mutex_lock(&core1_command_mutex, K_MSEC(CORE1_COMMAND_TIMEOUT_MS));
	if (err != 0) {
		return err;
	}

	err = execute_command_locked(CORE1_COMMAND_PING, challenge);
	if (err == 0) {
		*response = core1_storage.mailbox.response_value;
	}
	k_mutex_unlock(&core1_command_mutex);
	return err;
}

int picosystem_core1_draw_dense(uint32_t frame_index, struct picosystem_core1_dense_result *result)
{
	if (result == NULL) {
		return -EINVAL;
	}
	*result = (struct picosystem_core1_dense_result){0};

	int err = k_mutex_lock(&core1_command_mutex, K_MSEC(CORE1_COMMAND_TIMEOUT_MS));
	if (err != 0) {
		return err;
	}

	err = execute_command_locked(CORE1_COMMAND_DRAW_DENSE, frame_index);
	if (err == 0) {
		for (size_t stage = 0U; stage < ARRAY_SIZE(result->stage_time_us); ++stage) {
			result->stage_time_us[stage] =
				core1_storage.mailbox.dense_stage_time_us[stage];
		}
		result->total_time_us = core1_storage.mailbox.dense_total_time_us;
	}
	k_mutex_unlock(&core1_command_mutex);
	return err;
}

int picosystem_core1_render_scene(const struct picosystem_scene_snapshot *snapshot,
				  struct picosystem_core1_scene_result *result)
{
	if ((snapshot == NULL) || (result == NULL)) {
		return -EINVAL;
	}
	*result = (struct picosystem_core1_scene_result){0};

	int err = k_mutex_lock(&core1_command_mutex, K_MSEC(CORE1_COMMAND_TIMEOUT_MS));
	if (err != 0) {
		return err;
	}

	memcpy(&core1_storage.mailbox.scene_snapshot, snapshot, sizeof(*snapshot));
	err = execute_command_locked(CORE1_COMMAND_RENDER_SCENE, 0U);
	if (err == 0) {
		result->raster_time_us = core1_storage.mailbox.scene_raster_time_us;
	}
	k_mutex_unlock(&core1_command_mutex);
	return err;
}

static int wait_for_ready_strip_locked(uint32_t sequence, uint32_t ready_count)
{
	const int64_t deadline_ms = k_uptime_get() + CORE1_COMMAND_TIMEOUT_MS;
	while (true) {
		core1_memory_barrier();
		if (core1_storage.mailbox.ready_strip_count >= ready_count) {
			return 0;
		}
		if (core1_storage.mailbox.completed_sequence == sequence) {
			return (core1_storage.mailbox.error != 0) ? core1_storage.mailbox.error
								  : -EIO;
		}
		if (core1_storage.mailbox.state == PICOSYSTEM_CORE1_STATE_FAULT) {
			return (core1_storage.mailbox.error != 0) ? core1_storage.mailbox.error
								  : -EIO;
		}
		if (deadline_expired(deadline_ms)) {
			return -ETIMEDOUT;
		}
		const int err = wait_for_core1_event(deadline_ms);
		if (err != 0) {
			return err;
		}
	}
}

int picosystem_core1_render_scene_stream(const struct picosystem_scene_snapshot *snapshot,
					 picosystem_core1_scene_strip_consumer consumer,
					 void *consumer_context,
					 struct picosystem_core1_scene_result *result)
{
	if ((snapshot == NULL) || (consumer == NULL) || (result == NULL)) {
		return -EINVAL;
	}
	*result = (struct picosystem_core1_scene_result){0};

	int err = k_mutex_lock(&core1_command_mutex, K_MSEC(CORE1_COMMAND_TIMEOUT_MS));
	if (err != 0) {
		return err;
	}

	memcpy(&core1_storage.mailbox.scene_snapshot, snapshot, sizeof(*snapshot));
	core1_storage.mailbox.ready_strip_count = 0U;
	core1_storage.mailbox.scene_strip_count = CORE1_SCENE_STRIP_COUNT;
	uint32_t sequence;
	err = start_command_locked(CORE1_COMMAND_RENDER_SCENE_STREAM, 0U, &sequence);
	const bool command_started = err == 0;
	for (uint32_t strip_index = 0U; (err == 0) && (strip_index < CORE1_SCENE_STRIP_COUNT);
	     ++strip_index) {
		err = wait_for_ready_strip_locked(sequence, strip_index + 1U);
		if (err != 0) {
			break;
		}

		const uint16_t y = strip_index * CORE1_SCENE_STRIP_ROWS;
		const struct picosystem_rect region = {
			.x = 0U,
			.y = y,
			.width = PICOSYSTEM_GRAPHICS_WIDTH,
			.height = MIN(CORE1_SCENE_STRIP_ROWS, PICOSYSTEM_GRAPHICS_HEIGHT - y),
		};
		err = consumer(&region, consumer_context);
	}

	const int completion_err =
		command_started ? wait_for_command_locked(sequence,
							  k_uptime_get() + CORE1_COMMAND_TIMEOUT_MS)
				: err;
	if (err == 0) {
		err = completion_err;
	}
	if (completion_err == 0) {
		result->raster_time_us = core1_storage.mailbox.scene_raster_time_us;
		result->strip_count = core1_storage.mailbox.scene_strip_count;
	}
	k_mutex_unlock(&core1_command_mutex);
	return err;
}

bool picosystem_core1_is_ready(void)
{
	core1_memory_barrier();
	return core1_ready && (core1_storage.mailbox.state != PICOSYSTEM_CORE1_STATE_FAULT);
}

int picosystem_core1_get_status(struct picosystem_core1_status *status)
{
	if (status == NULL) {
		return -EINVAL;
	}

	core1_memory_barrier();
	uint32_t untouched_words = 0U;
	while ((untouched_words < ARRAY_SIZE(core1_storage.stack)) &&
	       (core1_storage.stack[untouched_words] == CORE1_STACK_CANARY)) {
		++untouched_words;
	}

	*status = (struct picosystem_core1_status){
		.requested_sequence = core1_storage.mailbox.requested_sequence,
		.completed_sequence = core1_storage.mailbox.completed_sequence,
		.heartbeat_count = core1_storage.mailbox.heartbeat_count,
		.stack_size_bytes = CORE1_STACK_BYTES,
		.stack_used_bytes = CORE1_STACK_BYTES - (untouched_words * sizeof(uint32_t)),
		.last_scene_raster_time_us = core1_storage.mailbox.scene_raster_time_us,
		.ready_strip_count = core1_storage.mailbox.ready_strip_count,
		.scene_strip_count = core1_storage.mailbox.scene_strip_count,
		.scene_item_index = core1_storage.mailbox.scene_progress.item_index,
		.core_id = core1_storage.mailbox.core_id,
		.error = core1_storage.mailbox.error,
		.scene_stage = (enum picosystem_scene_render_stage)
				       core1_storage.mailbox.scene_progress.stage,
		.scene_primitive = (enum picosystem_scene_render_primitive)
					   core1_storage.mailbox.scene_progress.primitive,
		.state = (enum picosystem_core1_state)core1_storage.mailbox.state,
		.ready = core1_ready,
	};
	return 0;
}

const char *picosystem_core1_state_name(enum picosystem_core1_state state)
{
	switch (state) {
	case PICOSYSTEM_CORE1_STATE_OFFLINE:
		return "offline";
	case PICOSYSTEM_CORE1_STATE_BOOTING:
		return "booting";
	case PICOSYSTEM_CORE1_STATE_IDLE:
		return "idle";
	case PICOSYSTEM_CORE1_STATE_RUNNING:
		return "running";
	case PICOSYSTEM_CORE1_STATE_STOPPED:
		return "stopped";
	case PICOSYSTEM_CORE1_STATE_FAULT:
		return "fault";
	default:
		return "unknown";
	}
}
