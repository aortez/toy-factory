# Seed handoff diagnostic protocol

Status at declaration: no diagnostic replay has run. This is a passive follow-up
to the [recruit seed audit](landing-recruit-seeds.md), not a rule comparison or
training experiment. It asks whether the short living-population vacancy in
S2 crowded was also a usable stored-plant opening for the recruit's seed.

## Fixed case and observation window

Use the cursor arm of `366928c6-rainfed-crowded` from the completed day-512
competitive-renewal capture. Retain W2, weather, capacities, placement policy,
purchase cursor and the original fifteen dieback events ending on day 304.
Parent 35 dies at tick 1,838,400. Its seed bought at tick 1,755,480 lands at
column 15. Parent 31's older seed, bought at tick 1,716,600, germinates there at
tick 1,839,345 and creates plant 36. These are already recorded ledger events,
not outcomes discovered by this diagnostic.

Record inclusive ticks **1,838,385 through 1,839,360**, every 15 logic ticks:
66 ecology samples, one before the death through one after the refill. Use
existing `--adult-trace` and `--stand-trace --stand-dawn` observers. Do not add
an unwindowed reach or recruitment trace, change the simulation or widen the
window automatically.

## Frozen replay and validity checks

Run exactly two identical calls through day 512, in fresh separate directories,
using the original saved executable and model. Both complete result objects,
including lifetime and seed ledgers, must equal the saved endpoint. Both endpoint
frames must match the saved pixels. Both bounded traces must be byte-identical
across the two replays. The original capture already includes a matching
observer-free endpoint; no additional control simulation is planned.

Authenticate the original manifest, binary and model before and after collection.
Retain call arguments, process outcomes, raw traces and file hashes. Reference
the original executable and source archive instead of copying another build
bundle. Preserve failures; no automatic retry or substitute history.

## Interpretation

Join every seed visit to its purchase identity and lifetime. Verify visit order,
stored plant inventory, living/dead distinction, node counts and blocker masks,
including earlier germinations within a step. Report the focal seed's blockers
on all 63 previously unresolved checks, the exact reclamation/refill tick, and
which seed consumes any opening first. Preserve simultaneous blockers rather
than attributing everything to the first failing gate.

A stored slot released and consumed in one seed loop is not a multi-step
opportunity. A seed that wins first does not by itself establish that reversing
the order improves long-run renewal. Do not modify priorities, decomposition,
expiry, population floors or the prior acceptance criteria. Purchase eligibility
of non-buyers remains outside this diagnostic.
