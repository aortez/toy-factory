/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef TOY_FACTORY_PORTABLE_UTIL_H_
#define TOY_FACTORY_PORTABLE_UTIL_H_

#include <stddef.h>

#define TOY_FACTORY_ARRAY_SIZE(array)            (sizeof(array) / sizeof((array)[0]))
#define TOY_FACTORY_BIT(bit)                     (1UL << (bit))
#define TOY_FACTORY_DIV_ROUND_UP(value, divisor) (((value) + (divisor) - 1U) / (divisor))
#define TOY_FACTORY_MIN(left, right)             ((left) < (right) ? (left) : (right))
#define TOY_FACTORY_MAX(left, right)             ((left) > (right) ? (left) : (right))

#endif /* TOY_FACTORY_PORTABLE_UTIL_H_ */
