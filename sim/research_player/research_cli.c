/* SPDX-License-Identifier: Apache-2.0 */
#include "research_session.h"

#include <errno.h>
#include <stdbool.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>

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
		err = research_session_render(session, pixels, sizeof(pixels), &crc);
		if (err == 0) {
			FILE *const stream = fopen(frame, "wbx");
			if (stream == NULL) {
				err = -errno;
			} else {
				if (fwrite(pixels, 1U, sizeof(pixels), stream) != sizeof(pixels)) {
					err = -EIO;
				}
				if ((fclose(stream) != 0) && (err == 0)) {
					err = -EIO;
				}
			}
		}
	}
	if (err == 0) {
		err = research_session_write_json(session, stdout, frame == NULL ? NULL : &crc);
	}
	research_session_close(session);
	return err;
}

int main(int argc, char **argv)
{
	if ((argc < 6) || (argc > 8)) {
		fputs("usage: research-replay POLICY SEED_HEX LAYOUT TICKS FOUNDER [NEW_FRAME.raw "
		      "[RENDER_EVERY]]\n"
		      "policies: initial, s1-g3-c4, s2-g3-c1; layouts: rainfed, rainfed-crowded\n",
		      stderr);
		return 2;
	}
	struct research_options options = {.model = UINT8_MAX, .layout = UINT8_MAX};
	for (uint8_t model = 0U; model < 3U; ++model) {
		if (strcmp(argv[1], research_model_name(model)) == 0) {
			options.model = model;
		}
	}
	for (uint8_t layout = 0U; layout < 2U; ++layout) {
		if (strcmp(argv[3], research_layout_name(layout)) == 0) {
			options.layout = layout;
		}
	}
	uint32_t ticks = 0U, founder = 0U, render_every = 0U;
	if ((strlen(argv[2]) != 8U) || (number(argv[2], 16, UINT32_MAX, &options.seed) != 0) ||
	    (number(argv[4], 10, RESEARCH_STOP_TICK, &ticks) != 0) ||
	    (number(argv[5], 10, UINT8_MAX, &founder) != 0) ||
	    ((argc == 8) && (number(argv[7], 10, RESEARCH_STOP_TICK, &render_every) != 0))) {
		fputs("invalid condition or horizon\n", stderr);
		return 2;
	}
	options.founder = (uint8_t)founder;
	if (signal(SIGPIPE, SIG_IGN) == SIG_ERR) {
		return 1;
	}
	const int err = execute(&options, ticks, render_every, argc >= 7 ? argv[6] : NULL);
	if (err != 0) {
		fprintf(stderr, "research replay failed: %d; partial outputs are not complete\n",
			err);
	}
	return err == 0 ? 0 : 1;
}
