# Fresh-weather confirmation of wider scattering v1

Predeclared after the original [screen](dispersal-protocol.md) passed, before
running any of the following new seeds. This tests the frozen candidate; it
does not choose another dispersal range, change costs/capacities/weather, train
controllers or change normal host/device defaults.

## Fixed environment and panel

Keep 128 Garden days (eight seasonal years), baseline and adaptive policies,
rainfed and rainfed-crowded layouts, steady and combined climates, and the
normal 256-node/eight-plant/eight-seed limits. Narrow is `5–7 + trait`; wide is
the same existing `3–9 + trait` option used in the first screen. The wide
inspector/replayer bytes must match that screen's retained digests; all C/header
sources and the shared collector must also match. Both builds' flags are
checked: only wide scattering differs, and all other research options are off.

Eight fresh weather/world seeds derive from base `0x73656134` with the existing
trial formula, without inspecting outcomes:

`ed52188d`, `4f0b9246`, `a9c30c1f`, `0bb887d0`,
`647001a9`, `c629bb62`, `20e1353b`, `82deacfc`.

The seeds are disjoint from the earlier seasonal screening/model panels and
were not found in the retained repo reports or local seasonal bundles. This is
a fresh-seed confirmation panel for this candidate, not a forever-untouched
test set once its results have been viewed.

There are **128 trajectories**: eight seeds × two layouts × two policies × two
climates × two scattering rules. Within each rule/climate there are 32 worlds,
but only eight weather seeds; layouts/policies sharing a seed are not independent
weather replicates. Do not pool the previous exploratory panel into the pass/fail
decision. Report it separately for comparison.

## Unchanged acceptance screen

Apply the existing `garden_season_dispersal.screen` to these new matched pairs.
In combined seasons, wider must retain or improve each fresh narrow-control count:

- worlds with births in the final year `(112, 128]`;
- final-year offspring surviving a complete day;
- final-year durable descendant parents;
- whole-run durable descendant parents;
- endpoints with multiple viable species, including the seed bank.

At least one of the first three closing-renewal measures must strictly improve.
No new observed living-plus-seed empty world is allowed in either climate.
Use the same full-day survival/censoring rules, including death on the boundary
failing the survival check. A durable parent and at least one child each survive
a full day; this is not a guarantee of future survival.

Also retain every matched result, eligible denominators, first-year outcomes,
policy/layout breakdowns, per-weather-seed results, and per-world win/tie/loss
counts. These descriptive breakdowns do not retroactively change the gates.
In particular, do not hide the original crowded-layout or mortality tradeoffs
behind pooled improvements. Seed-blocker observations are post-step samples,
not exact germination-decision receipts or independent vacancies.

## Checks and stopping rule

- Match all initial daily states across rules. Check offered rainfall
  (`deposited + runoff`) across rules/layouts/policies for every seed/day/climate.
- Collect seed-site snapshots with daily hash agreement, and reconcile full
  birth/death histories and closing cohorts using the existing runner.
- Repeat the first seed's four seasonal cases in **both** arms, requiring exact
  reports, trace digests and site summaries. No re-selection after results.
- Capture the first seed's rainfed/adaptive steady/seasonal pair at days 16 and
  128 in both arms: eight native-rendered images, checked against state hashes,
  framebuffer CRCs and a second rendering.
- Freeze inputs, source dependencies, binaries, build caches and protocol at
  collection start and verify them again at completion. Output directories are
  new; old evidence is preserved. Test the collector's validation and aggregation.
- Keep full reports in ignored artifacts; retain compact matched evidence,
  numeric results, limitations and the fixed images in the repo.

A failed gate ends this confirmation without searching more seeds, changing
thresholds or trying another parameter. A pass supports a discussion of adoption
and the remaining diversity/training limitations; it does not automatically
promote the rule or close environment qualification. No device flash is needed
for this host-only confirmation.
