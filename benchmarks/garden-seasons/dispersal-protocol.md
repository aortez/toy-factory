# Seasonal wider-scattering screen v1

Predeclared after the read-only recruitment pass and before running this
treatment. In the original 16 combined-season worlds, the final year contains
5,038 usable-site steps, 24 birth steps (37 births), and 5,014 missed landings.
Of the missed steps, 1,537 have no usable column within any living parent's
current support; 3,477 do. All 16 worlds have both openings and missed landings.
These are repeated samples, not independent vacancies or rescue probabilities.

## One existing treatment, no parameter search

Use the existing host-only `TOY_FACTORY_GARDEN_WIDE_DISPERSAL` option in an
isolated build: attempted distances `5–7 + trait` become `3–9 + trait`, retaining
direction, one RNG draw, reflection, mutation and the same nominal midpoint.
This broadens the possible destinations but dilutes probability at the old
ones. Do not move banked seeds, choose vacant destinations, add slots, change
seed viability/dormancy, alter weather/resources, or retrain a policy.

Compare the same four seeds, two layouts and two reference policies through
128 days in steady and combined climates (32 treatment runs). The 32 control
trajectories and their exact-check diagnosis are already retained. This is a
reused exploratory panel, not independent confirmation of the treatment.
All initial world hashes must match their controls. Record explicit narrow/wide
identity and CMake flags; hashes alone do not identify the ecological rules.

## Fixed screen

For combined seasons, retain or improve each of:

- worlds with final-year births: control 8/16;
- final-year day-surviving offspring: 30;
- final-year durable descendant parents: 6;
- whole-run durable descendant parents: 157;
- endpoints with multiple viable species, counting seeds: 1/16.

At least one of the first three closing-renewal measures must strictly improve.
No new observed living-plus-seed extinction is allowed in either climate.
Also report every matched case and policy/layout breakdown, early mortality,
births versus eligible survivors, overlapping seed blockers and any adverse
tradeoffs. A pass licenses discussion of fresh-seed confirmation, not promotion;
a failure ends this screen without another parameter search.

Capture the first seed's rainfed/adaptive steady/seasonal pair at days 16 and
128, checking native state hashes and framebuffer CRCs. Reproduce all four
first-seed seasonal trajectories byte-for-byte. Freeze source, binaries, build
configuration, parent evidence and treatment report hashes. Normal host/device
defaults remain narrow regardless of the outcome.
