# Energy shortfalls after broader late dispersal

Completed 2026-10-03. The energy regression is **not just failed seedlings or
extra population exposure**. Most post-intervention deficits in the broader
worlds belong to recruits confirmed to survive 32 garden days. Ten comparisons
also contain a matched individual with worse energy shortfalls over identical
exposure and maintenance demand. Prior occupants improve in aggregate, but
that improvement hides several individual regressions.

Keep broader dispersal host-only and off by default. The subsequent
[saved-history audit](landing-energy-history.md) examines a matched, mature
plant with unchanged lifespan and demand and identifies lower winter income,
without extra spending in the deficit episode. It still does not justify
changing costs, light or the harm screen.

## Evidence and accounting

This follows the [frozen offline protocol](landing-dispersal-energy-audit-protocol.md)
and consumes the [late dispersal result](landing-late-dispersal.md) and its pinned
uptake-cap control analyses. No native simulation, training, raw-trace extraction
or device operation was performed. All sixteen comparisons remain, including
the six energy-rate improvements and two seed-parent regressions. The settings
share one examined weather seed and controller; they are not independent trials.

Whole-life accounts retain the original harm screen. Post-intervention accounts
include maintenance strictly after tick 626580 through tick 983040. Newborns do
not pay on their birth step; death-step payments are included. Body histories
reconstruct energy demand as `ceil(nodes/8)` and water demand as
`ceil((nodes-roots)/8)`, using the body before each maintenance step. All
**877 plant histories and 2,999,512 payments** reconcile with recorded paid
upkeep and shortfalls. Founders have no post-intervention exposure here.

## Established recruits incur most deficits

Counts below pool eight settings per water treatment. Values are unpaid energy
units, not plants or failed payments. Cohorts are retrospective: a confirmed
32-day survivor may subsequently die, and its total includes earlier deficits.
Censored cohorts have insufficient follow-up and are not classified as failures.

| Cohort | Cap narrow | Cap broader | Cap and wicking narrow | Cap and wicking broader |
|---|---:|---:|---:|---:|
| Alive when intervention began | 100 | 41 | 68 | 39 |
| Later recruits dying by one day | 0 | 8 | 16 | 0 |
| Later recruits dying after one day through 32 days | 0 | 60 | 0 | 65 |
| Later recruits confirmed to survive 32 days | 194 | 274 | 50 | 199 |
| One-day follow-up censored | 0 | 4 | 0 | 7 |
| One day confirmed and 32-day follow-up censored | 0 | 0 | 0 | 9 |
| Total after intervention | 294 | 387 | 134 | 319 |

Confirmed 32-day recruits account for **473 of 706 units, or 67%**, in the
broader worlds. Deficits also occur late in individual lives: across all cohorts,
501 of those 706 units occur at ages of at least 32 days. The problem therefore
cannot be addressed solely as a first-day establishment failure.

Pooled post-intervention exposure rises from 278,039 to 363,316 payments with
the cap alone and from 301,805 to 360,728 with both water rules. Unpaid energy
per thousand payments changes **1.057 → 1.065** and **0.444 → 0.884**, respectively.
Those are exposure-weighted descriptive totals, not equal-weight independent
trials. Removing the shared early history does not remove the regression.

## Equal exposure reveals individual losses

Births are matched by recursive ancestry, birth tick, origin column and species,
not lineage number. Common post-intervention exposure ends at the earlier death
or the horizon; unequal survival tails remain separate. Every matched common
interval has equal payment counts **and equal total energy and water demand**.

| Energy account | Cap narrow | Cap broader | Cap and wicking narrow | Cap and wicking broader |
|---|---:|---:|---:|---:|
| Shared pre-intervention history | 100 | 100 | 100 | 100 |
| Prior occupants over common exposure | 100 | 40 | 68 | 38 |
| Prior occupants over unequal survival tails | 0 | 1 | 0 | 1 |
| Matched later recruits over common exposure | 194 | 132 | 0 | 98 |
| Matched later recruits over unequal survival tails | 0 | 0 | 0 | 0 |
| Unmatched later recruits | 0 | 214 | 66 | 182 |
| Whole descendant lifetime total | 394 | 487 | 234 | 419 |

With the cap alone, improved matched accounts coexist with 214 units in the
changed recruitment cohort. With wicking, both changed recruits and matched
later recruits add deficits. The unmatched category includes established plants;
it is not synonymous with failed recruitment. Unequal survival tails account
for only one candidate energy unit per water treatment.

Nine of the ten comparisons that worsen the original energy rate also contain
an individual matched regression. The exception is fixed/daylight/ordinary with
wicking, whose extra deficits all belong to unmatched recruits. Conversely,
fixed/dawn/focal with wicking passes the original aggregate screen while a
matched recruit worsens **0 → 34 units**. Its lineage IDs are 28 and 29, illustrating
why numeric-ID matching would be wrong. Aggregate improvement is not a promise
that every individual benefits.

The portable result includes exact rational rate contributions for all groups.
They use each arm's whole-population denominator and sum to the original rate
difference. Even unchanged early shortfalls have a negative contribution when
the denominator increases; that is dilution, not a benefit to the early plants.

## All sixteen comparisons

Rates below are unpaid energy units per **thousand maintenance payments**,
narrow → broader. Common deficits sum matched prior occupants and later recruits
over equal post-intervention exposure. Individual changes can cancel in that
sum, so the portable result also retains every matched pair separately.

| Setting | Water rules | Whole-life rate | Post-intervention rate | Common deficits |
|---|---|---:|---:|---:|
| Fixed daylight ordinary | Cap | 0.283 → 1.084 | 0.000 → 1.311 | 0 → 13 |
| Fixed daylight ordinary | Cap and wicking | 0.283 → 0.947 | 0.000 → 1.102 | 0 → 0 |
| Fixed daylight focal | Cap | 1.815 → 0.662 | 2.460 → 0.565 | 100 → 10 |
| Fixed daylight focal | Cap and wicking | 0.498 → 1.548 | 0.252 → 1.959 | 9 → 41 |
| Fixed dawn ordinary | Cap | 0.844 → 1.413 | 1.181 → 2.028 | 47 → 59 |
| Fixed dawn ordinary | Cap and wicking | 0.314 → 0.162 | 0.297 → 0.048 | 2 → 2 |
| Fixed dawn focal | Cap | 0.077 → 0.177 | 0.000 → 0.195 | 0 → 9 |
| Fixed dawn focal | Cap and wicking | 1.303 → 0.660 | 1.995 → 0.952 | 42 → 37 |
| Rotating daylight ordinary | Cap | 0.283 → 0.584 | 0.000 → 0.555 | 0 → 6 |
| Rotating daylight ordinary | Cap and wicking | 0.283 → 0.672 | 0.000 → 0.688 | 0 → 9 |
| Rotating daylight focal | Cap | 1.815 → 0.838 | 2.460 → 0.844 | 100 → 7 |
| Rotating daylight focal | Cap and wicking | 0.498 → 1.589 | 0.252 → 2.030 | 9 → 41 |
| Rotating dawn ordinary | Cap | 0.844 → 1.468 | 1.181 → 2.114 | 47 → 59 |
| Rotating dawn ordinary | Cap and wicking | 0.164 → 0.162 | 0.049 → 0.048 | 2 → 2 |
| Rotating dawn focal | Cap | 0.066 → 0.589 | 0.000 → 0.870 | 0 → 9 |
| Rotating dawn focal | Cap and wicking | 0.222 → 0.108 | 0.266 → 0.085 | 4 → 4 |

The original screen remains four passes. Combined-water fixed/dawn/ordinary and
rotating/dawn/focal still lose seed-producing parents; the latter also loses a
successful parent. All sixteen retain the previously measured water-rate
improvements. This audit changes neither the screen nor those outcomes.

## Timing and the next diagnostic case

All 245 post-intervention energy-shortfall events in the broader worlds occur
in sun phases 0–63 or 192–255. These are the dawn-to-noon and late-night quarters
of the existing clock, not measurements of illumination at individual leaves.
None of those events has a simultaneous unpaid water bill. Of the 706 unpaid
energy units, 622 occur in 32-node bodies. These observations locate the
problem; they do not establish shading or rule out effects of earlier water
availability on growth and neighboring plants.

The clearest next witness is the **fixed/dawn/focal cap-only** world's existing
plant 20, born at tick 590640 at column 3. It survives to the horizon in both
arms. Both owe 23,764 energy units over 5,941 post-intervention payments. The
broader world introduces three deficits at ticks **978420, 978480 and 978540**,
owing 4, 4 and 1 unpaid units; all water bills at those steps are fully paid.

Its lifetime energy budget has equal initial/final stores and equal construction
costs. Broader dispersal lowers gross income by 14,410 units and overflow by
14,113, leaving **297 fewer retained units**. It also produces six fewer seeds,
saving 288 units, while paid maintenance falls by nine. These equal-lifetime
accounts balance exactly, but do not identify the initiating cause: lower
retained income can also follow reduced spending and more time at full storage.

Read the saved adult receipts backward from these deficits to a shared funded
checkpoint, then compare step-by-step income, overflow, stores and spending.
That can distinguish an income shortfall from differently timed seed purchases
without another simulation. Keep the full panel as context and treat this as
an explicitly selected diagnostic example. If the existing receipts cannot
attribute reduced income to particular leaves or blockers, report that gap
before considering a new passive trace. No ecology change is proposed yet.

## Verification and retained result

All **19 new tests pass** on the host and in the Docker environment. Three
related offline CTest entries pass: this audit, the earlier allocation audit
and the dispersal-timing audit. Tests cover birth/death boundaries, same-step
growth, exhaustive survival/censoring groups, ancestry renumbering, changed
denominators, zero exposure, body-history reconciliation, tampering and output
preservation. A separate per-payment walk verifies the segment-based demand
calculation for all saved bodies.

Portable verification and a byte-identical second export pass with subprocess
launching forbidden. No new raw-file verification was claimed; source trace
identities are carried from the previously verified capture. The full native
and firmware suites were not rerun because no runtime code changed.

The [108 KiB portable result](landing-dispersal-energy-audit-results.json.gz)
retains all plant accounts, post-intervention energy events, paired comparisons
and source identities. See the [tool instructions](../../docs/garden-landing-tools.md#dispersal-energy-audit)
for offline export and verification commands.

| Artifact | SHA-256 |
|---|---|
| Frozen protocol | `21a10d1e1d7711fa365a3e6ada8a3f9fea8b234a92da4b987595220263681d23` |
| Late dispersal input | `390669aba064732072c82e2170ad1d6f7872612710bc1c6501ad3351c8ad3b62` |
| Uptake-cap input | `687f354bbeb04b71dc2c8d81b57bccefba0a1f6e2cfa6677f9dd14d517647768` |
| Audit result | `998796b9b79732d1a37e62b4a9c145f4b18fa05bde49028d9cbdd15699d4b5fb` |
