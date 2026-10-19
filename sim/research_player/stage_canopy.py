#!/usr/bin/env python3
"""Append a read-only projection entry point to a build-directory world copy."""

from pathlib import Path
import sys


def adapt(source):
    for signature in ('static void update_node_growth_progress(', 'static void wear_leaves(',
                      'static int update_light_observed(', 'static bool world_is_valid('):
        if source.count(signature) != 1:
            raise ValueError('frozen canopy binding differs: ' + signature)
    return source + '''
#include "research_canopy.h"
int research_canopy_project(const struct picosystem_garden_world *before,
                           struct picosystem_garden_uptake_audit *out)
{
    if (before == NULL || out == NULL || !world_is_valid(before) ||
        before->auto_gardener_enabled || before->logic_tick_count == UINT32_MAX ||
        (before->logic_tick_count + 1U) % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR != 0U) {
        return -EINVAL;
    }
#if defined(TOY_FACTORY_GARDEN_CANOPY_TRANSMISSION)
    return -ENOTSUP;
#else
    struct picosystem_garden_world copy = *before;
    struct picosystem_garden_uptake_audit result = {0};
    ++copy.logic_tick_count;
    update_node_growth_progress(&copy);
    ++copy.ecology_tick_count;
    wear_leaves(&copy);
    const int err = update_light_observed(&copy, &result);
    if (err != 0) { return err; }
    result.tick = copy.logic_tick_count;
    result.sun = picosystem_garden_world_sun(&copy);
    result.ecology_step = true;
    memcpy(result.light, copy.light, sizeof(result.light));
    *out = result;
    return 0;
#endif
}
'''


if __name__ == '__main__':
    Path(sys.argv[2]).write_text(adapt(Path(sys.argv[1]).read_text()))
