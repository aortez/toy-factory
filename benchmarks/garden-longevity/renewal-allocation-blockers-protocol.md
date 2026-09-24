# Saved-trace allocation-only germination audit

Follow the [fractional-canopy comparison](renewal-canopy-transmission.md) without
changing ecology or running another world. Determine whether the eight-plant
limit blocks otherwise admissible seeds, separately from overlapping spacing,
moisture and node gates. This protocol precedes the new numerical analysis.

## Fixed inputs and scope

- Parent: `artifacts/garden-renewal-canopy-transmission-v1`, manifest SHA-256
  `ea243a36dccd49eda1db5cbfc30956ebf281e81013fec5a4adc8e69bc7212b69`.
- Portable parent: `renewal-canopy-transmission-summary.json`, SHA-256
  `ad7c804d94fb9ac687a7d0c5175982579ba2b118336f425b1316fb3a857ccc60`.
- Both arms, every seed lifetime and every recorded site checkpoint through
  tick 245,760. Report exposure windows `(69120,245760]` and `(184320,245760]`;
  purchases within those windows are separate cohorts from seeds observed there.
- Track all producing parents, including the candidate's two new parents 13/14,
  with arm-local identities. No cross-arm matching of post-divergence IDs.
- Zero new experimental native calls, training calls, screenshots, model or
  device changes. Reuse the six existing images. Stop uncommitted/unpushed.

## Evidence and limits

Reconcile logged age/ordered identity against the frozen complete seed ledger.
Seed masks are post-step queries, not recorded germination attempts. Count
dormant seeds separately; mature means ages 8–255 ecology steps. Germinated and
expired seeds are removed before the query. Do not invent terminal samples or
count expiry as a germination attempt.

For every mature retained seed, partition post-step masks into plant-capacity
only (`8`), plant capacity plus other gates, and no plant-capacity gate. Also
keep exact overlapping masks. Join native 28-column site masks/moisture/light,
plant/dead-slot inventory and node use. Count hypothetical unseeded columns
separately; an available column is not a seed waiting to use it.

Code-order inference is permitted only with its prerequisites verified. In this
saved wet-germination setup, rain, transport, uptake, decomposition and plant
maintenance precede the seed loop. After that loop, growth and reproduction
consume plant stores, not surface soil; they do not remove/reposition plants or
remove nodes. Light is refreshed afterward, but germination has no light gate.
If a step has no germination, no 12-unit germination fee changes the surface
water. Its post-step plant/spacing/moisture gates therefore match the seed-loop
gates. A post-step absence of node-capacity blocking also proves sufficient
nodes earlier, before growth can add them.

Thus a mature retained seed with post-step mask `8`, eight non-newborn occupants
and no births on that step has a **code-order-supported allocation-only
rejection**. Preserve first/last witnesses and contiguous sampled runs. Count
post-step-only mask-8 samples on birth steps separately; do not label them exact
attempts. Stable old spacing occupants and stable full plant arrays are
additional conservative witnesses, including unreclaimed dead occupants.

Report sample counts, distinct seeds, outcomes/censoring, parents, columns,
living/dead occupancy and timing. Repeated samples of one seed are not independent
opportunities or probabilities. Even confirmed exclusive blocking does not mean
all such seeds would germinate with one extra slot: an earlier seed could consume
it and change later spacing, water, growth and competition. Do not forecast
survival or sustainable renewal from these masks.

## Validation and stopping

Verify the immutable parent inventory, source/model/image hashes, historical
analysis dependencies and native-source identity. Permit only the exact shared
CMake registration for this new Python test. Re-run the parent saved-data
analysis without executing its binaries, reconcile the portable parent, repeat
the new analysis and independently check its portable output in Docker.

Test dormancy/expiry boundaries, exclusive versus overlapping masks, wet-light
semantics, moisture threshold, node slack, dead/newborn occupants, missing and
reordered seed records, arm-local scope, contiguous runs/censoring, exact CMake
delta, invalid input preservation and the zero-native-call verification path.

If exclusive allocation blocking is observed, it supports discussing a bounded
capacity diagnostic, not automatically raising the limit. Otherwise focus on
the overlapping resource/space gates. Write the report, update issue #30 and
roadmap, then discuss the next experiment. No capacity increase, forced adult
death, opacity tuning, longer horizon, training or promotion in this task.
