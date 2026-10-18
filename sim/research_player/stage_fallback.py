#!/usr/bin/env python3
"""Thread an explicit placement route through copies of the frozen host wrappers."""

from pathlib import Path
import sys

import stage_purchase_observer


def once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('frozen fallback binding differs: ' + old[:80])
    return source.replace(old, new)


def extend(source, name, replacement, arguments, parameter):
    if source.count('static int ' + name + '(') != 1 or ('static int ' + replacement + '(') in source:
        raise ValueError('private step binding differs')
    start = source.index('static int ' + name + '(')
    end = source.index('\n{\n', start)
    signature = source[start:end]
    if not signature.endswith(')'):
        raise ValueError('private step signature differs')
    extended = signature.replace('static int ' + name + '(', 'static int ' + replacement + '(', 1)
    extended = extended[:-1] + ',\n ' + parameter + ')'
    source = source[:start] + extended + source[end:]
    # The wrapper is declared before the renamed implementation and defined
    # afterwards, preserving every original caller with a NULL policy route.
    source = source[:start] + signature + ';\n\n' + source[start:]
    source += '\n' + signature + '\n{\n return ' + replacement + '(' + ', '.join(arguments) + ', NULL);\n}\n'
    return source


def landing(source):
    source = stage_purchase_observer.adapt(source)
    args = ['run', 'audit', 'seeds', 'probe', 'observe', 'observer_context', 'resources',
            'water', 'water_audit', 'node_limit', 'budget_mode', 'growth_observer',
            'placement', 'placement_audit', 'seed_order_after', 'root_choice',
            'root_allocation', 'seed_cursor', 'seed_wait', 'priority', 'leaf_override', 'route']
    source = extend(source, 'step_with_leaf', 'step_with_placement', args,
                    'const struct research_fallback_route *fallback')
    source = once(source, '.base = &placement_context, .observer = growth_observer};',
                  '.base = &placement_context, .observer = growth_observer, .fallback = fallback};')
    return '#include "research_fallback.h"\n' + source + '\n#include "research_fallback_bridge.h"\n'


def replay(source):
    source = extend(source, 'step', 'step_with_fallback',
                    ['run', 'deaths', 'seeds', 'resources', 'observer', 'route', 'checked'],
                    'const struct research_fallback_route *fallback')
    old = '''err = toy_factory_leaf_replay_step_internal(&result.base, &policy, &death_result,
\t\t\t\t\t\t    &seed_result, &resource_result,
\t\t\t\t\t\t    observer == NULL ? NULL : &local, route);'''
    new = '''if (fallback != NULL) {
        err = research_fallback_step_internal(&result.base, &policy, &death_result,
            &seed_result, &resource_result, observer == NULL ? NULL : &local, route, fallback);
    } else {
        ''' + old + '\n    }'
    source = once(source, old, new)
    source += '''
int research_fallback_step_owned(struct toy_factory_leaf_replay *run,
    struct picosystem_garden_death_audit *deaths, struct picosystem_garden_seed_audit *seeds,
    struct picosystem_garden_resource_audit *resources,
    const struct toy_factory_garden_growth_observer *observer,
    const struct toy_factory_leaf_replay_route *leaf,
    const struct research_fallback_route *placement)
{
    if (placement == NULL || placement->owners == NULL) { return -EINVAL; }
    return step_with_fallback(run, deaths, seeds, resources, observer, leaf, false, placement);
}
'''
    return '#include "research_fallback.h"\n' + source


if __name__ == '__main__':
    runtime, out = map(Path, sys.argv[1:])
    (out / 'research_purchase_runner.c').write_text(landing((runtime / 'source/sim/garden_landing_run.c').read_text()))
    (out / 'research_fallback_replay.c').write_text(replay((runtime / 'modules/leaf_replay/garden_leaf_replay.c').read_text()))
