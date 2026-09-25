# Rescued-shrub controlled gap — fixed host A/B

Test whether a rescued seed-producing shrub establishes descendants when one
known blocking neighbor is removed. This follows the
[saved seed audit](renewal-rescued-seeds.md), not a new training campaign or
held-out validation. Freeze this protocol before collecting either new arm.

## Fixed contrast

- World `0d983a80`, `rainfed-crowded`, no recurring patches or gardener.
- Both arms retain the ordinary dark-spending guard and full-night capacity
  guard, selective leaf maintenance, 512 nodes, eight plant/seed slots, wide
  dispersal and water headroom. All other experimental overrides remain off.
- Preserve N (`01b9d94a`) background/descendant routing and W (`c9ea07fd`) for
  reset founder 5, with the unchanged no-night-growth wrapper. Freeze both
  exact model files, source archive, compiler/build flags and executable hashes.
- Control: no removal. Treatment: **export founder flower 1, column 3, after
  the ordinary ecology step at tick 46,080 / day 12**. Require it to be living,
  at least one day old, and still the declared founder at that boundary.
  The saved boundary has 36 nodes, 240 energy, 510 water and hash `5eea8cea`.
  If this reference differs, stop; do not choose another target or time.
- Use the existing host-only immediate export primitive: remove its body and
  stored resources, compact indices, recompute light. Do not kill/decompose it,
  refund resources, alter the seed bank, advance time/RNG, or change survivors'
  state. Count the export separately from natural deaths. The plant's remaining
  seeds retain their original ancestry.
- Keep rescued shrub 7 at column 0 and its parent, founder shrub 2 at column 8.
  This removal opens part of shrub 7's known dispersal range without removing
  its own parent. It is not an attempt to isolate spacing from shade, moisture,
  plant capacity or competition, all of which can respond to a canopy gap.
- End at tick 245,760 / day 64. Retain day-48–64 closing metrics separately.
  No timing sweep, adaptive follow-up, extra removal, rule change or model search.

## Capture budget and reference gates

Exactly **24 experimental native calls** on one rebuilt host configuration:

1. Full bid/world ecology trace and a separate compact site/aged-seed census
   for each arm, each repeated: **eight calls**.
2. Native 240 × 240 framebuffer replays at **days 12, 13, 16 and 64** for
   each arm, each repeated: **sixteen calls**, eight unique fixed frames.
   The treatment day-12 frame is post-export; the control is pre-export.

The control's complete world/bid trace must reproduce the saved capacity arm
byte-for-byte before treatment collection. Its day-12/day-64 state and images
must match the existing capture. Both arms' raw prefixes through the day-12
ordinary step must match exactly. World and site traces independently agree
on hashes/counters/bank identities; treatment boundary triples agree on export
metadata. Repeat traces and framebuffers must be exact.

Input bundle: `artifacts/garden-renewal-capacity-guard-v1`, manifest SHA-256
`f8e7237a0db166e15fe802c12e78b5a0f76b539fd853888d7fbc2efdc7a33d2f`.
Input rescued-seed portable audit SHA-256:
`5dbf08356e6968cb33e52f835c2f775bdbc7e77b27712d13a37b79612378a913`.
Verify frozen input inventory/provenance and restrict native changes to host gap
selection, its CLI plumbing and tests. No production `src/` or firmware changes.
Routine synthetic/native regression tests are outside the experiment-call budget.

## Required outcomes and interpretation

- Every seed's creation, destination, age, germination/expiry/censoring and child
  ancestry. Reconcile all ordered bank transitions and per-parent counters,
  independently cross-checking reconstruction against the logged seed ages.
- Separate seeds already in the bank at export from later purchases. Report
  shrub 7's complete offspring and the competing parents that occupy the gap;
  keep seeds from the removed flower in the analysis rather than discarding them.
- Post-export and closing births, natural deaths, plant/seed species, full-day
  eligible offspring, full-day survivors and durable descendant parents.
  Recent offspring/seeds are censored, not automatically failed. Do not match
  later newborn IDs across diverged arms.
- Site opening duration and seed exposure in the removed adult's spacing
  footprint (columns 1–5), with first recruitment/occupation and parentage.
  Separate actual-seed destinations from the parent's possible dispersal support.
  Report post-step light/water/spacing/capacity queries as snapshots, not exact
  pre-germination decision receipts or independent probabilities.
- Compare whole-world costs and the rescued parent's continued survival and
  reproduction. Opening a site is not success unless recruitment occurs, and
  germination is not success unless seedlings survive the declared first day.
- Validate both guards' receipts, all live resource budgets and boundary state;
  retain complete lineage and seed histories, fixed images and machine-readable
  provenance. Repeat the analysis, verify the portable export, and run focused
  gap/focal-routing tests plus proportional host regression suites.

Stop with a report and issue-30 update, then discuss the next step. No commit,
push, firmware deployment, new training, permanent adult lifetime or ecological
rule promotion is part of this diagnostic. A single selected deterministic gap
cannot qualify a general environmental-turnover schedule or species coexistence.
