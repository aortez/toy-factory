/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_PILOT_PARSE_H_
#define TOY_FACTORY_GARDEN_PILOT_PARSE_H_

#include <errno.h>
#include <stdint.h>
#include <stdlib.h>

static inline int toy_factory_garden_pilot_u32(const char *text, uint32_t maximum, uint32_t *out)
{
	if ((text == NULL) || (out == NULL) || (*text < '0') || (*text > '9')) {
		return -EINVAL;
	}
	errno = 0;
	char *end;
	const unsigned long value = strtoul(text, &end, 0);
	if ((errno != 0) || (*end != '\0') || (value > maximum)) {
		return -ERANGE;
	}
	*out = (uint32_t)value;
	return 0;
}

#endif
