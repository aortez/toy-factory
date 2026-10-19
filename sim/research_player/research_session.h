/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_RESEARCH_SESSION_H_
#define TOY_FACTORY_RESEARCH_SESSION_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

#define RESEARCH_DAY_TICKS        3840U
#define RESEARCH_STOP_TICK        (1376U * RESEARCH_DAY_TICKS)
#define RESEARCH_FRAME_BYTES      115200U
#define RESEARCH_FAMILY_MAX_NODES 512U
#define RESEARCH_FAMILY_MAX_SEEDS 16U
#define RESEARCH_MODEL_CUSTOM     3U
#define RESEARCH_MODEL_FILE_BYTES 172U

enum research_scope {
	RESEARCH_SCOPE_FAMILY = 0,
	RESEARCH_SCOPE_POPULATION,
};

struct research_options {
	uint32_t seed;
	uint8_t model;   /* 0=fixed wear, 1=Search 1, 2=Search 2, 3=custom_model. */
	uint8_t layout;  /* 0=rainfed, 1=rainfed-crowded */
	uint8_t founder; /* 1..founders for family scope; zero for population scope. */
	enum research_scope scope;
	/* TLF1 repair model file, used only by RESEARCH_MODEL_CUSTOM and copied with
	 * these options. Named models run only on the documented seeds; a custom
	 * model accepts any seed, so its caller fixes the conditions.
	 */
	uint8_t custom_model[RESEARCH_MODEL_FILE_BYTES];
};

struct research_status {
	uint32_t tick;
	uint32_t living;
	uint32_t pending;
};

struct research_family_segment {
	uint32_t lineage;
	uint8_t start_x;
	uint8_t start_y;
	uint8_t end_x;
	uint8_t end_y;
	bool base;
};

struct research_family_seed {
	uint32_t parent;
	uint8_t x;
	uint8_t y;
};

struct research_family_view {
	uint32_t tick;
	uint16_t segment_count;
	uint8_t living;
	uint8_t seed_count;
	struct research_family_segment segments[RESEARCH_FAMILY_MAX_NODES];
	struct research_family_seed seeds[RESEARCH_FAMILY_MAX_SEEDS];
};

/* Host-only owner of the simulation and diagnostic ledgers. One allocation for
 * population scope, two for family scope, none while stepping. Exclusive access
 * required. Rendering also owns
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

/* Optional population-only read-only trace, enabled once at tick zero. One
 * additional bounded host allocation; reset disables it. Traced sessions stop
 * at day 256. The canonical simulation/history JSON is unchanged. Stream errors
 * can leave partial output, as with write_json. No frozen types escape this API.
 */
int research_session_trace_start(struct research_session *session, uint8_t founder);
int research_session_trace_write(const struct research_session *session, FILE *stream);

/* Population-only shadow inference on actual observations in (first_day,
 * end_day], at most 16 days within day 256. One bounded host allocation at
 * tick zero, no step allocation; reset disables it. Only the original policy
 * is applied. Write requires the complete window, independent of trace mode.
 */
int research_session_shadow_start(struct research_session *session, uint8_t founder,
				  uint16_t first_day, uint16_t end_day);
int research_session_shadow_write(const struct research_session *session, FILE *stream);

/* Fixed-case host intervention, enabled once at tick zero: Search 1 population,
 * seeds 58d7d6ca or 59818bc3, rainfed; only family 2 after day 208. Variants 0=none, 1=light,
 * 2=condition, 3=both. Immutable derived model, one bounded allocation, day-256
 * limit. Cannot combine with shadow. Reset disables it. Identity becomes TGR1
 * plus the underlying TPR1: 4-byte magic, variant/founder/two reserved zeros,
 * after-tick u32 LE, derived TLF1 model (172 bytes), then complete TPR1.
 */
int research_session_gate_start(struct research_session *session, uint8_t variant);
/* Same family intervention from the first decision after tick zero. Restricted
 * to the four original rainfed panel seeds: 58d7d6ca, 9a903368, 6b9c1a3e,
 * 59818bc3. Other requirements match gate_start. TGR1 after-tick is zero.
 */
int research_session_gate_start_early(struct research_session *session, uint8_t variant);
/* At exactly day 256, extend a gate replay once to day 608. Freezes any resource
 * trace at day 256 (trace_write continues to export that prefix); ancestry and
 * simulation continue normally. No allocation or canonical state change.
 * Reset disables the extension. Other replay modes cannot use it.
 */
int research_session_gate_continue(struct research_session *session);
const char *research_gate_name(uint8_t variant);

/* Read-only paid-purchase trace in [30,35) days, all species. Restricted to a
 * day-zero gate replay of seed 9a903368. One bounded allocation at tick zero,
 * none while stepping. Reset disables it; write requires day 35 or later.
 * Canonical identity and policy remain unchanged. Partial output on I/O error.
 */
int research_session_purchase_start(struct research_session *session);
int research_session_purchase_write(const struct research_session *session, FILE *stream);

/* Read-only ordered reproduction access on cadence ticks in (128,232] days.
 * Restricted to condition-only early gate on seed 9a903368. One bounded
 * allocation, no step allocation; reset disables it. Write requires full
 * coverage. Canonical identity is unchanged; stream failures may leave output.
 */
int research_session_reproduction_start(struct research_session *session);
int research_session_reproduction_write(const struct research_session *session, FILE *stream);

/* Fixed resource windows around the eight missed openings of lineage 17.
 * Requires the condition-only reproduction trace plus fewer-blocker placement
 * at tick zero. One bounded allocation, no step allocation, reset disables it.
 * Write requires complete coverage through day 226.140625; errors may leave
 * partial stream output. No canonical state or policy change.
 */
int research_session_budget_start(struct research_session *session);
int research_session_budget_write(const struct research_session *session, FILE *stream);

/* Read-only day-152 leaf uptake attribution, condition-only seed 9a903368.
 * Requires reproduction diagnostics at tick zero; selects lineage 19 for
 * original placement or 17 for fewer-blocker placement. One bounded allocation,
 * no step allocation, reset disables it, publication requires the complete day.
 * Recording errors latch. Stream errors may leave partial output.
 */
int research_session_foliage_start(struct research_session *session);
int research_session_foliage_write(const struct research_session *session, FILE *stream);
int research_session_canopy_start(struct research_session *session);
int research_session_canopy_write(const struct research_session *session, FILE *stream);

/* Fixed host-only all-blocked fallback for family 2, from tick zero. Requires
 * an early gate replay of seed 9a903368. No allocation, disabled by reset.
 * TBF1 prefixes the complete TGR1 state: version=1, founder=2, two zero bytes,
 * activation tick u32 LE=0 (12 bytes total). Clear-site behavior is unchanged.
 */
int research_session_fallback_start(struct research_session *session);

/* Range errors do not advance. A runtime/audit failure latches: the session
 * cannot step, render or publish a successful result until reset. A batch is
 * not transactional; preceding successful ticks remain internal on failure.
 */
int research_session_step(struct research_session *session, uint32_t ticks);
int research_session_status(const struct research_session *session, struct research_status *out);
/* Read-only native-pixel geometry for the selected scope's living plants and
 * pending seeds, including posthumous seeds. Dead bodies are excluded. The
 * caller owns the value copy; no allocation, raster access or mutation occurs.
 * Invalid arguments or a failed session leave *out unchanged.
 */
int research_session_family_view(const struct research_session *session,
				 struct research_family_view *out);
/* Family scope retains the archived TFR1 bytes. Population scope uses TPR1:
 * two reserved zero bytes, founder-count/reserved bytes, lineage count u32 LE,
 * one root byte per lineage, then the uniform TLR1 state. Not a resume format.
 */
int research_session_encode(const struct research_session *session, uint8_t *out, size_t capacity,
			    size_t *size);

/* Native RGB565BE, copied to caller storage only on success. Rendering verifies
 * canonical state before/after, never advances, and retains no output pointer.
 */
int research_session_render(struct research_session *session, uint8_t *out, size_t capacity,
			    uint32_t *crc);
/* Family scope matches the archived CLI. Population scope has its own schema,
 * no selected founder/resident policy, and the same complete ancestry/history.
 * A NULL crc means no capture.
 * A stream error can leave partial output; callers must not mark it complete.
 */
int research_session_write_json(const struct research_session *session, FILE *stream,
				const uint32_t *crc);
const char *research_model_name(uint8_t model);
const char *research_layout_name(uint8_t layout);

#endif
