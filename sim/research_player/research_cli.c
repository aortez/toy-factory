/* SPDX-License-Identifier: Apache-2.0 */
#include "research_session.h"

#include <errno.h>
#include <inttypes.h>
#include <stdbool.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

static int number(const char *text, int base, uint32_t maximum, uint32_t *out)
{
	if ((text == NULL) || (*text == '\0')) {
		return -EINVAL;
	}
	for (const char *p = text; *p != '\0'; ++p) {
		if (!((*p >= '0' && *p <= '9') || (base == 16 && *p >= 'a' && *p <= 'f'))) {
			return -EINVAL;
		}
	}
	errno = 0;
	char *end;
	const unsigned long value = strtoul(text, &end, base);
	if ((errno != 0) || (*end != '\0') || (value > maximum)) {
		return -ERANGE;
	}
	*out = (uint32_t)value;
	return 0;
}

/* Exactly one model file; the session validates its contents when it opens. */
static int read_model(const char *path, uint8_t *out)
{
	FILE *const stream = fopen(path, "rb");
	if (stream == NULL) {
		return -ENOENT;
	}
	uint8_t extra;
	const size_t size = fread(out, 1U, RESEARCH_MODEL_FILE_BYTES, stream);
	const bool longer = fread(&extra, 1U, 1U, stream) != 0U;
	const bool failed = ferror(stream) != 0;
	fclose(stream);
	if (failed) {
		return -EIO;
	}
	return ((size == RESEARCH_MODEL_FILE_BYTES) && !longer) ? 0 : -EMSGSIZE;
}

static int capture(struct research_session *session, const char *path, uint32_t *crc)
{
	uint8_t pixels[RESEARCH_FRAME_BYTES];
	int err = research_session_render(session, pixels, sizeof(pixels), crc);
	if (err != 0) {
		return err;
	}
	FILE *const stream = fopen(path, "wbx");
	if (stream == NULL) {
		return -errno;
	}
	if (fwrite(pixels, 1U, sizeof(pixels), stream) != sizeof(pixels)) {
		err = -EIO;
	}
	if (fclose(stream) != 0) {
		err = -EIO;
	}
	return err;
}

static int checkpoint(struct research_session *session, const char *directory, uint32_t tick,
		      uint32_t *crc)
{
	char path[1024];
	const int length =
		snprintf(path, sizeof(path), "%s/tick-%010" PRIu32 ".raw", directory, tick);
	if ((length < 0) || ((size_t)length >= sizeof(path))) {
		return -ENAMETOOLONG;
	}
	int err = capture(session, path, crc);
	if (err != 0) {
		return err;
	}
	/* The JSON suffix is one byte longer than the already bounded raw suffix. */
	const int json_length =
		snprintf(path, sizeof(path), "%s/tick-%010" PRIu32 ".json", directory, tick);
	if ((json_length < 0) || ((size_t)json_length >= sizeof(path))) {
		return -ENAMETOOLONG;
	}
	FILE *const stream = fopen(path, "wx");
	if (stream == NULL) {
		return -errno;
	}
	err = research_session_write_json(session, stream, crc);
	if (fclose(stream) != 0) {
		err = -EIO;
	}
	return err;
}

enum diagnostic_depth {
	DIAGNOSTIC_BASE,
	DIAGNOSTIC_REPRODUCTION,
	DIAGNOSTIC_BUDGET,
	DIAGNOSTIC_FOLIAGE,
	DIAGNOSTIC_CANOPY,
};

static int timeline(const struct research_options *options, uint32_t ticks, const char *directory,
		    uint8_t trace_founder, bool shadow, uint8_t gate, bool from_start,
		    bool purchases, bool fallback, enum diagnostic_depth depth)
{
	if (options->scope != RESEARCH_SCOPE_POPULATION) {
		return -EINVAL;
	}
	struct research_session *session = NULL;
	int err = research_session_open(options, &session);
	if ((err == 0) && (gate != UINT8_MAX)) {
		err = from_start ? research_session_gate_start_early(session, gate)
				 : research_session_gate_start(session, gate);
	}
	if ((err == 0) && (trace_founder != 0U)) {
		err = research_session_trace_start(session, trace_founder);
	}
	if ((err == 0) && shadow) {
		err = research_session_shadow_start(session, trace_founder, 208U, 224U);
	}
	if ((err == 0) && purchases && trace_founder != 0U) {
		err = research_session_purchase_start(session);
	}
	if ((err == 0) && fallback) {
		err = research_session_fallback_start(session);
	}
	if ((err == 0) && depth >= DIAGNOSTIC_REPRODUCTION && trace_founder != 0U) {
		err = research_session_reproduction_start(session);
	}
	if ((err == 0) && depth == DIAGNOSTIC_BUDGET && trace_founder != 0U) {
		err = research_session_budget_start(session);
	}
	if ((err == 0) && depth >= DIAGNOSTIC_FOLIAGE && trace_founder != 0U) {
		err = research_session_foliage_start(session);
	}
	if ((err == 0) && depth == DIAGNOSTIC_CANOPY && trace_founder != 0U) {
		err = research_session_canopy_start(session);
	}
	if ((err == 0) && (mkdir(directory, 0755) != 0)) {
		err = -errno;
	}
	static const uint32_t normal_days[] = {0U, 32U, 192U, 608U, 992U, 1376U};
	static const uint32_t gate_days[] = {0U,   32U,  192U, 208U, 220U, 222U,
					     224U, 256U, 384U, 512U, 608U};
	const uint32_t *const days = gate == UINT8_MAX ? normal_days : gate_days;
	const size_t day_count = gate == UINT8_MAX ? sizeof(normal_days) / sizeof(normal_days[0])
						   : sizeof(gate_days) / sizeof(gate_days[0]);
	uint32_t previous = 0U, crc = 0U;
	for (size_t i = 0U; (err == 0) && (i < day_count); ++i) {
		const uint32_t next = days[i] * RESEARCH_DAY_TICKS;
		if (next > ticks) {
			break;
		}
		err = research_session_step(session, next - previous);
		if (err == 0) {
			err = checkpoint(session, directory, next, &crc);
		}
		if ((err == 0) && (gate != UINT8_MAX) && (days[i] == 256U) && (next < ticks)) {
			err = research_session_gate_continue(session);
		}
		previous = next;
	}
	if ((err == 0) && (previous < ticks)) {
		err = research_session_step(session, ticks - previous);
		if (err == 0) {
			err = checkpoint(session, directory, ticks, &crc);
		}
	}
	const struct {
		const char *name;
		int (*write)(const struct research_session *, FILE *);
	} outputs[] = {
		{"trace", research_session_trace_write},
		{purchases ? "purchases" : "shadow",
		 purchases ? research_session_purchase_write : research_session_shadow_write},
		{"reproduction", research_session_reproduction_write},
		{depth >= DIAGNOSTIC_FOLIAGE ? "foliage" : "budget",
		 depth >= DIAGNOSTIC_FOLIAGE ? research_session_foliage_write
					     : research_session_budget_write},
		{"canopy", research_session_canopy_write},
	};
	const size_t output_count = depth == DIAGNOSTIC_CANOPY         ? 5U
				    : depth >= DIAGNOSTIC_BUDGET       ? 4U
				    : depth == DIAGNOSTIC_REPRODUCTION ? 3U
				    : (shadow || purchases)            ? 2U
								       : 1U;
	for (size_t i = 0U; (err == 0) && (trace_founder != 0U) && i < output_count; ++i) {
		char path[1024];
		const int length =
			snprintf(path, sizeof(path), "%s/%s.json", directory, outputs[i].name);
		if ((length < 0) || ((size_t)length >= sizeof(path))) {
			err = -ENAMETOOLONG;
		} else {
			FILE *const stream = fopen(path, "wx");
			if (stream == NULL) {
				err = -errno;
			} else {
				err = outputs[i].write(session, stream);
				if (fclose(stream) != 0) {
					err = -EIO;
				}
			}
		}
	}
	if (err == 0) {
		err = research_session_write_json(session, stdout, &crc);
	}
	research_session_close(session);
	return err;
}

static int execute(const struct research_options *options, uint32_t ticks, uint32_t render_every,
		   const char *frame)
{
	struct research_session *session = NULL;
	int err = research_session_open(options, &session);
	uint8_t pixels[RESEARCH_FRAME_BYTES];
	uint32_t crc = 0U;
	for (uint32_t done = 0U; (err == 0) && (done < ticks);) {
		uint32_t count = ticks - done;
		if ((render_every != 0U) && (count > render_every)) {
			count = render_every;
		}
		err = research_session_step(session, count);
		done += count;
		if ((err == 0) && (render_every != 0U)) {
			err = research_session_render(session, pixels, sizeof(pixels), &crc);
		}
	}
	if ((err == 0) && (frame != NULL)) {
		err = capture(session, frame, &crc);
	}
	if (err == 0) {
		err = research_session_write_json(session, stdout, frame == NULL ? NULL : &crc);
	}
	research_session_close(session);
	return err;
}

int main(int argc, char **argv)
{
	if ((argc >= 2) && ((strcmp(argv[1], "--fallback-panel") == 0) ||
			    (strcmp(argv[1], "--reproduction-panel") == 0) ||
			    (strcmp(argv[1], "--foliage-panel") == 0) ||
			    (strcmp(argv[1], "--canopy-panel") == 0) ||
			    (strcmp(argv[1], "--budget-panel") == 0))) {
		const enum diagnostic_depth depth =
			strcmp(argv[1], "--canopy-panel") == 0         ? DIAGNOSTIC_CANOPY
			: strcmp(argv[1], "--foliage-panel") == 0      ? DIAGNOSTIC_FOLIAGE
			: strcmp(argv[1], "--budget-panel") == 0       ? DIAGNOSTIC_BUDGET
			: strcmp(argv[1], "--reproduction-panel") == 0 ? DIAGNOSTIC_REPRODUCTION
								       : DIAGNOSTIC_BASE;
		uint8_t variant = UINT8_MAX;
		if (argc == 7) {
			for (uint8_t i = 0U; i < 4U; ++i) {
				if (strcmp(argv[3], research_gate_name(i)) == 0) {
					variant = i;
				}
			}
		}
		if (variant == UINT8_MAX || (depth >= DIAGNOSTIC_REPRODUCTION && variant != 2U) ||
		    (depth == DIAGNOSTIC_BUDGET && strcmp(argv[4], "fewest") != 0) ||
		    strcmp(argv[2], "9a903368") != 0 ||
		    (strcmp(argv[4], "original") != 0 && strcmp(argv[4], "fewest") != 0) ||
		    (strcmp(argv[5], "on") != 0 && strcmp(argv[5], "off") != 0)) {
			fputs("usage: research-replay "
			      "--fallback-panel|--reproduction-panel|--budget-panel|--foliage-"
			      "panel|--canopy-panel "
			      "9a903368 "
			      "none|light|condition|both "
			      "original|fewest on|off NEW_DIR\n",
			      stderr);
			return 2;
		}
		if (signal(SIGPIPE, SIG_IGN) == SIG_ERR) {
			return 1;
		}
		const struct research_options options = {.seed = UINT32_C(0x9a903368),
							 .model = 1U,
							 .scope = RESEARCH_SCOPE_POPULATION};
		const int err = timeline(&options, 608U * RESEARCH_DAY_TICKS, argv[6],
					 strcmp(argv[5], "on") == 0 ? 2U : 0U, false, variant, true,
					 true, strcmp(argv[4], "fewest") == 0, depth);
		if (err != 0) {
			fprintf(stderr,
				"fallback replay failed: %d; partial outputs are not complete\n",
				err);
		}
		return err == 0 ? 0 : 1;
	}
	if ((argc >= 2) && ((strcmp(argv[1], "--gate-panel") == 0) ||
			    (strcmp(argv[1], "--purchase-panel") == 0))) {
		const bool purchases = strcmp(argv[1], "--purchase-panel") == 0;
		struct research_options options = {.model = 1U, .scope = RESEARCH_SCOPE_POPULATION};
		uint8_t variant = UINT8_MAX;
		if (argc == 6) {
			for (uint8_t i = 0U; i < 4U; ++i) {
				if (strcmp(argv[3], research_gate_name(i)) == 0) {
					variant = i;
				}
			}
		}
		if ((variant == UINT8_MAX) || (strlen(argv[2]) != 8U) ||
		    (number(argv[2], 16, UINT32_MAX, &options.seed) != 0) ||
		    (purchases && options.seed != UINT32_C(0x9a903368)) ||
		    ((strcmp(argv[4], "on") != 0) && (strcmp(argv[4], "off") != 0))) {
			fputs("usage: research-replay --gate-panel|--purchase-panel SEED_HEX "
			      "none|light|condition|both on|off NEW_DIR\n",
			      stderr);
			return 2;
		}
		if (signal(SIGPIPE, SIG_IGN) == SIG_ERR) {
			return 1;
		}
		const int err = timeline(&options, 608U * RESEARCH_DAY_TICKS, argv[5],
					 strcmp(argv[4], "on") == 0 ? 2U : 0U, false, variant, true,
					 purchases, false, DIAGNOSTIC_BASE);
		if (err != 0) {
			fprintf(stderr,
				"gate panel replay failed: %d; partial outputs are not complete\n",
				err);
		}
		return err == 0 ? 0 : 1;
	}
	if ((argc >= 2) &&
	    ((strcmp(argv[1], "--gate") == 0) || (strcmp(argv[1], "--gate-long") == 0) ||
	     (strcmp(argv[1], "--gate-transfer") == 0))) {
		uint8_t variant = UINT8_MAX;
		if (argc == 5) {
			for (uint8_t i = 0U; i < 4U; ++i) {
				if (strcmp(argv[2], research_gate_name(i)) == 0) {
					variant = i;
				}
			}
		}
		if ((variant == UINT8_MAX) ||
		    ((strcmp(argv[3], "on") != 0) && (strcmp(argv[3], "off") != 0))) {
			fputs("usage: research-replay --gate|--gate-long|--gate-transfer "
			      "none|light|condition|both "
			      "on|off "
			      "NEW_DIR\n",
			      stderr);
			return 2;
		}
		if (signal(SIGPIPE, SIG_IGN) == SIG_ERR) {
			return 1;
		}
		const bool transfer = strcmp(argv[1], "--gate-transfer") == 0;
		const struct research_options options = {.seed = transfer ? UINT32_C(0x59818bc3)
									  : UINT32_C(0x58d7d6ca),
							 .model = 1U,
							 .scope = RESEARCH_SCOPE_POPULATION};
		const uint32_t days = strcmp(argv[1], "--gate") == 0 ? 256U : 608U;
		const int err = timeline(&options, days * RESEARCH_DAY_TICKS, argv[4],
					 strcmp(argv[3], "on") == 0 ? 2U : 0U, false, variant,
					 false, false, false, DIAGNOSTIC_BASE);
		if (err != 0) {
			fprintf(stderr,
				"gate replay failed: %d; partial outputs are not complete\n", err);
		}
		return err == 0 ? 0 : 1;
	}
	if ((argc < 6) || (argc > 9)) {
		fputs("usage: research-replay POLICY SEED_HEX LAYOUT TICKS FOUNDER|all "
		      "[NEW_FRAME.raw "
		      "[RENDER_EVERY]]\n"
		      "       research-replay POLICY SEED_HEX LAYOUT TICKS all --timeline NEW_DIR\n"
		      "       research-replay POLICY SEED_HEX LAYOUT TICKS all --trace FOUNDER "
		      "NEW_DIR\n"
		      "       research-replay POLICY SEED_HEX LAYOUT TICKS all --shadow FOUNDER "
		      "NEW_DIR (days 208..224; includes trace)\n"
		      "       research-replay --gate none|light|condition|both on|off NEW_DIR\n"
		      "       research-replay --gate-long none|light|condition|both on|off "
		      "NEW_DIR\n"
		      "       research-replay --gate-transfer none|light|condition|both on|off "
		      "NEW_DIR\n"
		      "       research-replay --gate-panel SEED_HEX none|light|condition|both "
		      "on|off NEW_DIR\n"
		      "policies: initial, s1-g3-c4, s2-g3-c1, or a 172-byte TLF1 model file "
		      "(any seed); layouts: rainfed, rainfed-crowded\n",
		      stderr);
		return 2;
	}
	struct research_options options = {.model = UINT8_MAX, .layout = UINT8_MAX};
	for (uint8_t model = 0U; model < 3U; ++model) {
		if (strcmp(argv[1], research_model_name(model)) == 0) {
			options.model = model;
		}
	}
	if ((options.model == UINT8_MAX) && (read_model(argv[1], options.custom_model) == 0)) {
		options.model = RESEARCH_MODEL_CUSTOM;
	}
	for (uint8_t layout = 0U; layout < 2U; ++layout) {
		if (strcmp(argv[3], research_layout_name(layout)) == 0) {
			options.layout = layout;
		}
	}
	uint32_t ticks = 0U, founder = 0U, render_every = 0U;
	uint32_t trace_founder = 0U;
	const bool population = strcmp(argv[5], "all") == 0;
	const bool capture_timeline = (argc == 8) && (strcmp(argv[6], "--timeline") == 0);
	const bool shadow = (argc == 9) && (strcmp(argv[6], "--shadow") == 0);
	const bool trace = shadow || ((argc == 9) && (strcmp(argv[6], "--trace") == 0));
	if (((argc >= 7) && (strcmp(argv[6], "--timeline") == 0) && !capture_timeline) ||
	    ((argc >= 7) && (strcmp(argv[6], "--trace") == 0) && !trace) ||
	    ((argc >= 7) && (strcmp(argv[6], "--shadow") == 0) && !shadow) ||
	    ((argc == 9) && !trace) ||
	    (trace && ((number(argv[7], 10, 5U, &trace_founder) != 0) || (trace_founder == 0U))) ||
	    (strlen(argv[2]) != 8U) || (number(argv[2], 16, UINT32_MAX, &options.seed) != 0) ||
	    (number(argv[4], 10, RESEARCH_STOP_TICK, &ticks) != 0) ||
	    (!population && (number(argv[5], 10, UINT8_MAX, &founder) != 0)) ||
	    ((argc == 8) && !capture_timeline &&
	     (number(argv[7], 10, RESEARCH_STOP_TICK, &render_every) != 0))) {
		fputs("invalid condition or horizon\n", stderr);
		return 2;
	}
	options.founder = (uint8_t)founder;
	options.scope = population ? RESEARCH_SCOPE_POPULATION : RESEARCH_SCOPE_FAMILY;
	if (trace && ((ticks > 256U * RESEARCH_DAY_TICKS) ||
		      (shadow && (ticks < 224U * RESEARCH_DAY_TICKS)))) {
		fputs("invalid diagnostic horizon\n", stderr);
		return 2;
	}
	if (signal(SIGPIPE, SIG_IGN) == SIG_ERR) {
		return 1;
	}
	const int err =
		(capture_timeline || trace)
			? timeline(&options, ticks, argv[trace ? 8 : 7], (uint8_t)trace_founder,
				   shadow, UINT8_MAX, false, false, false, DIAGNOSTIC_BASE)
			: execute(&options, ticks, render_every, argc >= 7 ? argv[6] : NULL);
	if (err != 0) {
		fprintf(stderr, "research replay failed: %d; partial outputs are not complete\n",
			err);
	}
	return err == 0 ? 0 : 1;
}
