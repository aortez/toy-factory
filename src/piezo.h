/*
 * Copyright (c) 2026 PicoSystem Playground contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_PIEZO_H
#define PICOSYSTEM_PIEZO_H

#include <stdint.h>

/* Configure the transducer's PWM output and leave it silent. */
int picosystem_piezo_init(void);

/* Start a bounded tone; a delayed work item returns the output to silence. */
int picosystem_piezo_play(uint32_t frequency_hz, uint32_t duration_ms);

#endif /* PICOSYSTEM_PIEZO_H */
