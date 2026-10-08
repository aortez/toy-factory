# Competitive renewal through day 512

Status at declaration: collector and extended runs are not implemented or
started. This is a host-only environment diagnostic, not a training objective.

Test whether the six gardens keep renewing after the initial vacancies fill,
while allowing individuals to die through competition. Compare the existing
fixed-order and purchase-cursor histories without changing either ecology.
The preceding [shade attribution](landing-cursor-shade.md) explains one adult
death; it does not answer this population-level question. The original
[cursor experiment](landing-seed-cursor.md) still fails its original harm gate.
These prospective criteria do not reclassify that result.

## Fixed histories and observation window

Use unchanged W2, seasonal rain, the two existing rain-fed layouts and the
ordered seeds `3a7e45e6`, `366928c6`, `275c8982` (S1, S2, S3). Run ordinary
then crowded for each seed, retaining both arms of every pair. Layouts sharing
a seed are not independent weather replicates; none is a new held-out case.

Both arms retain all fifteen four-column dieback events at days 192–304.
There are no new sweeps, gardener actions, irrigation or other interventions.
The cursor remains active strictly after day 320, with its existing state;
do not restart it at day 384. Fixed order is the prior dieback treatment with
fixed reproduction order, not the historical no-dieback control. Keep all
construction/resource guards, uptake/dispersal settings, placement, costs,
256 nodes, eight plant slots, eight seed slots and 32-day seed viability.

The source results are [landing-seed-cursor-results.json.gz](landing-seed-cursor-results.json.gz),
SHA-256 `cf6ba820eee40259fcaededb7188708517a8b282541ac78ff4b292f68d43af8a`.
Model SHA-256 is
`f2dc989380339614dc512f64f11f2bf03f7079c465c4c9bd18895044ec3e1567`.
Use the recorded build settings, including sanitizers; the saved executable
SHA-256 is `82cb8901a7ba39b539fe32d422d7290864acc775fad0e07c23691bf7127ece9a`.

Observe `(384,512]`: 128 added Garden days, eight complete 16-day seasonal
cycles. One day is 3,840 logic ticks. The boundaries are day 384 = 1,474,560
ticks and day 512 = 1,966,080 ticks. Replays start from tick zero; there is no
portable day-384 world-save loader.

Enroll births in three fixed windows: `(384,416]`, `(416,448]`, `(448,480]`.
The final 32 days supply complete potential follow-up for every enrolled birth.
Births in `(480,512]` remain visible but are not added to the primary cohort.
Report their eligible, confirmed, failed and censored observations separately.
Do not extend the horizon in response to disappointing results.

## Measurements and operational thresholds

Report each arm and pair before totals. These thresholds are declared research
criteria for this small eight-slot environment, not validated biological
constants or a replacement for the existing training score.

### Population viability

Reconstruct living population `L(t)` from the complete birth/death ledger,
using post-step state: birth at `t` is included, death at `t` is excluded.
Between ecology steps the population is constant. A world passes this axis if:

- It has at least one living plant at every logic tick in `(384,512]`.
- Its time-weighted mean living population is at least four in **each** of
  the eight consecutive 16-day blocks beginning at day 384 (open on the left,
  closed on the right, like the full observation interval).
- It ends day 512 with at least four living plants.

Four is half the available plant capacity. This permits turnover and temporary
population dips without accepting a lone persistent survivor as a healthy
population. Publish minima, block means, endpoint counts and every empty
interval, even when a pending seed later repopulates the world. Living-plant
absence and extinction of both living plants and pending seeds are distinct.
Use exact plant-tick sums for comparisons, not rounded display values.

### Sustained descendant renewal

An age-D survivor is alive at its birth tick plus `D * 3840`, with that boundary
observed. Death exactly at the boundary fails. The primary age is 32 days
(two seasonal cycles); also report 16-day survival. No eligible births means
an undefined survival rate, not zero percent, although the renewal count is zero.

A world passes this axis only if:

- Each of the three enrollment windows produces at least one 32-day survivor.
- At least one direct parent–child pair has **both** births in `(384,480]`
  and both individuals survive 32 days by the final observation.

The second requirement tests whether a new recruit itself produces a durable
recruit, not merely whether older adults keep producing seedlings. The parent
need not still be alive when its seed germinates, and seed purchase need not
wait until age 32. Both individual survival conditions must eventually hold.
Neither plant must still be alive on day 512 after passing its age boundary.
Carry-in parents and their offspring remain a separate, reported category.
These cohort definitions do not change the native evaluator's established
plant predicate or silently substitute its shorter-age lifetime totals.

Retain birth/death ticks and ancestry for every qualifying pair, distinct
parents, deepest established chain, all deaths, seed purchases and seed fates.
Measure chain depth as the number of plants connected by qualifying primary
parent–child edges, not the stored generation number inherited from earlier runs.
A seed purchase, a full bank or a long-lived old population cannot pass renewal.
The window requirement asks for a durable recruit in each fixed two-cycle
window, not continuous births or reproduction on a particular day.

### Diversity and competition costs

The saved day-384 baseline is:

| Garden | Living, fixed / cursor | Living species, both arms | Living founder families, both arms |
| --- | ---: | ---: | ---: |
| S1 ordinary | 8 / 8 | 2 | 2 |
| S1 crowded | 8 / 8 | 1 | 2 |
| S2 ordinary | 7 / 7 | 1 | 1 |
| S2 crowded | 8 / 8 | 1 | 2 |
| S3 ordinary | 7 / 7 | 2 | 2 |
| S3 crowded | 6 / 8 | 2 | 3 |

A founder family is ancestry traced through parent IDs to an original founder,
not an individual that must remain alive. All controllers still use W2;
species and family counts are not neural-model diversity or a measurement of
trait diversity within a family.

At day 384 and every subsequent 16-day boundary, report living counts by
species and founder family, their shares, and pending-seed representation
separately. A baseline species/family is retained through the checkpoint panel
only if it has a living representative at **every** subsequent checkpoint.
List exactly which groups lose representation and which recover from seeds.
Compare identities, not just richness totals; a different group cannot conceal
the loss of a baseline group. This checkpoint test does not imply uninterrupted
presence between checkpoints; reconstruct exact absence intervals from the ledger.

Species-variety coverage is the number of the three initially multi-species
gardens retaining at least two living species at every checkpoint. Ancestry-variety
coverage similarly uses the five initially multi-family gardens and a floor of
two living families. Also report loss of any third family separately. Monocultures
cannot count as successful multi-species evidence, nor are absent species
required to reappear. Do not combine these denominators into a single score.

Record deaths of plants alive at day 384, deaths by age 32 and deaths after
age 32 without using individual death as an automatic veto. The compact lifetime
ledger does not attribute a new death to shade versus another resource process.
Do not label every natural death competitive, or claim new energy/water-budget
findings without a separately scoped trace investigation.

## Interpretation fixed before collection

A broad **within-panel renewal signal** requires all six cursor worlds to pass
viability and at least four to pass renewal, covering all three seeds and both
layouts. Report the same classification for fixed order. This is an operational
coverage threshold, not statistical confidence or full environment qualification.

Evidence favoring further cursor confirmation additionally requires strictly
more renewal-passing worlds than fixed order. Diversity is a separate result:
if cursor loses baseline species/families that fixed retains, or has lower
variety coverage on either axis, label the outcome a **diversity tradeoff**, not
an unqualified win. Do not average away failed worlds or combine a diversity
loss with extra births into a net score. Counts and all paired regressions
remain visible even when these summary thresholds pass.

If populations persist but renewal stops, report stable occupancy without
demonstrated continued renewal. If only a few cases renew, report a limited
signal. If the arms tie, this test does not establish a cursor advantage.
If viability fails, investigate population-level depletion; do not automatically
protect the particular adult that died. Mixed diversity outcomes require
discussion before broadening the experiment. Even a positive result needs fresh
conditions before generalization; no model training or default promotion follows
from this panel, half of which already consists of monocultures.

## Implementation gates and bounded collection

The current host CLI stops at day 384. Before collection, permit day 512 by
changing only that host bound, associated help and boundary tests. Do not change
simulation stepping, rules, runtime state, evaluator/training limits or firmware.
Add a separate collector and offline analyzer; preserve the frozen older tools.
Freeze this protocol and the new collector/source identities before research calls.

Use existing complete lifetime/seed ledgers and endpoint rendering. No new
per-step observer, full bid/reach/resource trace or leaf-grid capture is needed.
The native ledgers continue their per-step census checks and explicit capacity
failures: 4,096 lifetime records and 65,536 seed purchases. Saved day-384 histories
use at most 52 and 134, respectively, but that is not permission to truncate a
longer run. Capacity exhaustion is an incomplete experiment, never extinction
or ecological failure. Test event boundaries, empty cohorts, posthumous ancestry,
species/family loss, censoring, ledger truncation and altered receipts offline.

Exactly 60 planned native calls, at most two concurrently:

1. Twelve day-384 anchors (both arms of every pair). Exact result JSON, histories
   and RGB565 pixels must match the saved cursor capture before any extension.
2. Twelve day-448 checkpoint runs, retaining all paired frames.
3. Twelve day-512 endpoint runs, retaining all paired frames.
4. Twelve exact day-512 repeats, requiring equal results, ledgers and pixels.
5. Twelve day-512 runs without framebuffer capture, requiring identical results
   except the explicitly absent framebuffer CRC. No file trace observers are
   enabled in any phase.

Verify full lifetime/seed ledger prefixes against each prior checkpoint,
including clipping later deaths and seed outcomes correctly. Reconcile births,
deaths, purchases, pending seeds, capacity and climate at each endpoint; validate
every germination's child/parent link. Freeze tests for the metric definitions
before inspecting post-384 outcomes. A changed anchor, discrepancy, missing
record, native failure or repeat mismatch stops collection and preserves the
partial bundle; no automatic retry, replacement seed or best-looking subset.

The review gallery includes all twelve worlds at days 448 and 512 in the fixed
panel/arm order, linked to the existing day-384 gallery. Publish the twelve
worlds' metrics and individual failures, not only aggregate classifications.
Retain compressed portable results, frame bytes/PNGs, arguments, binary/model,
source hashes, build settings and an offline-verifiable manifest. Snapshot actual
source inputs, excluding generated build trees; do not duplicate the historical
212 MiB archive just to preserve its already recorded identity. Use fresh paths,
preserve historical bundles and follow the [storage policy](../../docs/artifact-storage.md).

This follow-up audits outcomes and identities, not a new full resource account.
Any later causal investigation must be scoped separately instead of expanding
this collection into another full-history trace dump.
