/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_RESEARCH_SESSION_H_
#define TOY_FACTORY_RESEARCH_SESSION_H_

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

#define RESEARCH_DAY_TICKS   3840U
#define RESEARCH_STOP_TICK   (1376U * RESEARCH_DAY_TICKS)
#define RESEARCH_FRAME_BYTES 115200U

struct research_options {
	uint32_t seed;
	uint8_t model;  /* 0=fixed wear, 1=Search 1, 2=Search 2 */
	uint8_t layout; /* 0=rainfed, 1=rainfed-crowded */
	uint8_t founder;
};

struct research_status {
	uint32_t tick;
	uint32_t living;
	uint32_t pending;
};

/* Host-only owner of the simulation and diagnostic ledgers. Two allocations
 * on open, none while stepping. Exclusive access required. Rendering also owns
 * the process-global raster for the duration of the call; do not render in
 * parallel, including with the ordinary player. No mutable state is exposed.
 */
struct research_session;

/* Open leaves *out unchanged on failure; options are copied. Reset replaces
 * the owner only after successful initialization. Close accepts NULL.
 */
int research_session_open(const struct research_options *options, struct research_session **out);
void research_session_close(struct research_session *session);
int research_session_reset(struct research_session **session);

/* Range errors do not advance. A runtime/audit failure latches: the session
 * cannot step, render or publish a successful result until reset. A batch is
 * not transactional; preceding successful ticks remain internal on failure.
 */
int research_session_step(struct research_session *session, uint32_t ticks);
int research_session_status(const struct research_session *session, struct research_status *out);
int research_session_encode(const struct research_session *session, uint8_t *out, size_t capacity,
			    size_t *size);

/* Native RGB565BE, copied to caller storage only on success. Rendering verifies
 * canonical state before/after, never advances, and retains no output pointer.
 */
int research_session_render(struct research_session *session, uint8_t *out, size_t capacity,
			    uint32_t *crc);
/* Same complete record as the archived family CLI. A NULL crc means no capture.
 * A stream error can leave partial output; callers must not mark it complete.
 */
int research_session_write_json(const struct research_session *session, FILE *stream,
				const uint32_t *crc);
const char *research_model_name(uint8_t model);
const char *research_layout_name(uint8_t layout);

#endif
