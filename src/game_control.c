/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "game_control.h"

#include <errno.h>
#include <stddef.h>
#include <stdint.h>

#include <zephyr/kernel.h>
#include <zephyr/sys/atomic.h>

#define GAME_CONTROL_QUEUE_DEPTH 2U
#define GAME_CONTROL_TIMEOUT_MS  5000

struct game_control_response {
	struct picosystem_game_control_state state;
	uint32_t request_id;
	int result;
};

K_MUTEX_DEFINE(submit_mutex);
K_MSGQ_DEFINE(control_requests, sizeof(struct picosystem_game_control_request),
	      GAME_CONTROL_QUEUE_DEPTH, 4U);
K_MSGQ_DEFINE(control_responses, sizeof(struct game_control_response), GAME_CONTROL_QUEUE_DEPTH,
	      4U);

static atomic_t next_request_id;

static void discard_stale_responses(void)
{
	struct game_control_response stale_response;

	while (k_msgq_get(&control_responses, &stale_response, K_NO_WAIT) == 0) {
	}
}

int picosystem_game_control_submit(const struct picosystem_game_control_request *request,
				   struct picosystem_game_control_state *state)
{
	if ((request == NULL) || (state == NULL)) {
		return -EINVAL;
	}

	int err = k_mutex_lock(&submit_mutex, K_FOREVER);
	if (err != 0) {
		return err;
	}

	discard_stale_responses();
	struct picosystem_game_control_request pending = *request;
	pending.id = (uint32_t)atomic_inc(&next_request_id) + 1U;
	pending.deadline_uptime_ms = k_uptime_get() + GAME_CONTROL_TIMEOUT_MS;

	err = k_msgq_put(&control_requests, &pending, K_NO_WAIT);
	if (err != 0) {
		k_mutex_unlock(&submit_mutex);
		return err;
	}

	while (true) {
		const int64_t remaining_ms = pending.deadline_uptime_ms - k_uptime_get();
		if (remaining_ms <= 0) {
			err = -ETIMEDOUT;
			break;
		}

		struct game_control_response response;
		err = k_msgq_get(&control_responses, &response, K_MSEC(remaining_ms));
		if (err != 0) {
			break;
		}
		if (response.request_id != pending.id) {
			continue;
		}

		*state = response.state;
		err = response.result;
		break;
	}

	k_mutex_unlock(&submit_mutex);
	return err;
}

int picosystem_game_control_take(struct picosystem_game_control_request *request)
{
	if (request == NULL) {
		return -EINVAL;
	}

	while (k_msgq_get(&control_requests, request, K_NO_WAIT) == 0) {
		if (k_uptime_get() <= request->deadline_uptime_ms) {
			return 0;
		}

		const struct picosystem_game_control_state empty_state = {0};
		(void)picosystem_game_control_complete(request->id, -ETIMEDOUT, &empty_state);
	}

	return -ENOMSG;
}

int picosystem_game_control_complete(uint32_t request_id, int result,
				     const struct picosystem_game_control_state *state)
{
	if ((request_id == 0U) || (state == NULL)) {
		return -EINVAL;
	}

	const struct game_control_response response = {
		.state = *state,
		.request_id = request_id,
		.result = result,
	};

	return k_msgq_put(&control_responses, &response, K_NO_WAIT);
}
