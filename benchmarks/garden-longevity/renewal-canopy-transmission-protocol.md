# Post-noon fractional canopy transmission: fixed host-only A/B

Follow the [saved light audit](renewal-establishment-light.md) with one bounded
optical-rule comparison, not a parameter search or training run. Protocol fixed
before experimental native capture.

## Hypothesis and exact rule

Additive shade can clamp several overlapping canopy layers to the 24-unit
ambient floor. Test whether fractional transmission improves establishment and
continuing descendant reproduction without increasing incumbent losses.

Keep the existing sunlight strength/direction, ray geometry, cell shade
aggregation/saturation, leaf-condition scaling, node maturity and dead-tissue
shade. For each ray, start `beam = sun_strength - 24`. Traverse the same cells
in the existing target-to-sky order. At each cell of shade `s` (0–255), use
`beam = (beam * (255 - s) + 127) / 255`, with integer division. Output `24 + beam`.
The rounding is nearest integer, once per cell. There is no tunable coefficient.
An empty ray remains unchanged; full opacity removes all above-ambient light.
Night has beam zero and remains light 24 everywhere, producing zero energy under
the unchanged `floor(light/64) * condition` photosynthesis calculation.

The candidate uses this solver only **after tick 69,120 inclusive** (first
ecology update 69,135). Before then both arms use the original additive solver.
Use per-world host configuration reset to off, explicit metadata, and compile-
time exclusion from firmware. Retain the existing physical hash convention:
run configuration is separately recorded, not an agent observation/action.

## Fixed comparison

- Parent: `artifacts/garden-renewal-seed-spacing-v1`, manifest SHA-256
  `f230a7eeb305eb9bef28381ea618cb8fec44a3da4d5885bd5978eeb675507007`.
- Parent portable summary SHA-256:
  `bdd740f2b1a2b74488c3e2aed8b674b750a516a13dd9b56fd2b656deafc6fb0e`.
- Supporting offline audit SHA-256:
  `cc8db979c33e7e93fd23ccb0a53784bff4da6daaad828188e9e851fa3c6570e6`.
- Both arms reproduce the parent's **two-column** arm, including rotating seed
  purchases, wet germination after the named founder export, reserve-aware
  FINISH handoff, unchanged dark/full-night guards, rain, models and capacities.
  Same `rainfed-crowded` seed `0d983a80`, N background/descendants and W founder 5.
- `control`: additive light throughout. `transmission`: only the rule above.
- Stop at tick 245,760 (64 garden days); closing window `(184320,245760]`.
  No extension selected after seeing survival results.
- Exactly **20 experimental native calls**: ecology and seed-site traces for
  both arms, each repeated; frame replays at 69,120, 72,960 and 245,760 in both
  arms, each repeated. Six predetermined native images, including bad outcomes.
- Rebuilt control raw traces/frame JSON/pixels must match the historical
  two-column arm exactly before candidate capture. Candidate/control physical
  records and pixels must agree through 69,120; only new rule metadata may differ.

## Outcomes and decision rule

Count every post-boundary seedling, with full-day follow-up eligibility explicit.
Report births, early/late deaths, first-day survivors, endpoint survivors,
post-boundary parents with full-day-surviving children, closing-window renewal,
incumbent losses, species/family retention, seed outcomes, capacity and resource
budgets. Do not match post-divergence lineages between arms by their numeric IDs.
Track founder flower 5 separately because its identity precedes the split.

A positive selected-world signal requires **more than six new full-day
survivors**, **at least one post-boundary parent with a full-day-surviving child**,
no more than the control's three incumbent deaths, and no fewer endpoint species
or founder families than control. These gates do not qualify broader ecology;
otherwise report the result as mixed/negative, without tuning or recapture.
Raw births or adult rescue alone do not count as sustained renewal. Improved
light might also make adults persist and prevent later recruitment.

Summarize live resource checks and sampled leaf light/renewal, distinguish one
sampled leaf from full-canopy measurements, and leave cleared terminal budgets
unknown. Preserve boundary order, model routing, ordinary guard precedence and
sequential seed/root storage order. Never infer a specific shading neighbor
without evidence or turn the ambient floor into an energy subsidy.

## Validation and stopping

Before capture: strict warnings/UBSan, native empty/single/stacked/opaque leaf
fixtures, both ray directions, night/unshaded invariants, invalid-input output
preservation, reset and exact activation boundary, per-world isolation, parser/
firmware guards, and independent Python integer-reference coverage. Normal builds
explicitly disable the option. Test calls are separate from the fixed research
capture budget.

Freeze source/binary/model/build/protocol receipts. Repeat captures and analysis,
reconcile the old control's derived outcomes, verify portable exports separately
in Docker, review all six images and run default/experimental regression suites.
If analysis fails after capture, recover offline without new native calls or
replacing observations. Stop uncommitted, record results in the report/roadmap
and issue #30, and discuss the next step. No default promotion, firmware flash,
training, capacity/fee/weather changes, commit or push.
