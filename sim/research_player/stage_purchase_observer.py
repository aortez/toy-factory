#!/usr/bin/env python3
"""Create a separately compiled callback adapter without editing frozen inputs."""

import sys
from pathlib import Path


def adapt(source):
    old = '''\tif (placement != NULL) {
\t\tpolicy.place_seed = toy_factory_garden_placement_decide;
\t\tpolicy.placement_context = &placement_context;
\t\tpolicy.seed_replacement_after = placement->replace_after;
\t}'''
    new = '''\tconst struct research_purchase_context purchase_context = {
\t\t.base = &placement_context, .observer = growth_observer};
\tif (placement != NULL) {
\t\tpolicy.place_seed = research_purchase_decide;
\t\tpolicy.placement_context = &purchase_context;
\t\tpolicy.seed_replacement_after = placement->replace_after;
\t}'''
    if source.count(old) != 1:
        raise ValueError('frozen placement binding differs')
    return '#include "research_purchase.h"\n' + source.replace(old, new)


if __name__ == '__main__':
    Path(sys.argv[2]).write_text(adapt(Path(sys.argv[1]).read_text()))
