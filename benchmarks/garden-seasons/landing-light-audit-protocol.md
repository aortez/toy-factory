# Daylight income forecast audit protocol

Audit the complete saved focal histories from the continuous-energy comparison
before choosing another spending rule. Explain which forecast errors follow from
unproductive dim light, and which remain attributable only to aggregate canopy
effects or body changes. Include successful growth, not only the known failure.

## Frozen input and limits

Use all five cases and both arms in `landing-continuous-energy-results.json.gz`,
SHA-256 `143cfbb3a1064cadbe0b46b8c0907684928e7e2dc7e54b0a0502324648c3d1b5`.
Validate the input using its existing checker. Retain every focal ecology sample
through death or world day 256. Report raw and deduplicated counts; duplicates
require identical lifetime and physical history after removing only scope and
eligibility annotations. These overlapping worlds are not independent trials.

Pin the captured source versions governing light, uptake, observations, resource
trace timing and the original forecast. Require the captured default build with
leaf-maintenance and canopy-transmission experiments disabled. The audit does
not need the native executable or raw trace bundle; its saved portable input
contains the required observations and transfers.

Budget: zero native simulation calls, zero training and zero new screenshots.
No firmware, ecology, policy, controller, commit, push or PR changes. Use a fresh
no-clobber output directory with source, input and protocol hashes. A repeated
export from the same source must have identical portable results.

## Accounting and illumination

Reconcile every sample's energy and water transfers. Analyze every paid daylight
action over the full saved lifetime, including FINISH and within-band growth.
Retain paid night actions separately; their original forecast denies night
spending and does not supply a daylight projection. Verify actual execution and
arbitration rather than inferring a purchase from a bid.

For each daylight purchase, reuse the existing post-action-to-sunset accounting,
including subsequent growth, upkeep, reproduction, overflow, discard and the
forecast cap. Retain death and censored endpoints; never fill missing future
samples with invented zero income. Separate clean windows from those with later
spending or changing mature-leaf counts.

Recompute recorded sun strength from phase and the recorded current seasonal
light percentage using the source's integer arithmetic. For each living,
nonbirth sample, compare income with the instantaneous unshaded bound
`active_leaves * floor(sun_strength / 64)`. Source ordering makes the recorded
mature-leaf count valid for that uptake: maturation occurs before uptake, new
growth is immature, and FINISH does not remove leaves. Exclude terminal samples
from this bound because death changes leaf growth progress. When global strength
is below 64, require zero income regardless of leaf count or shade.

For a complete living daylight window with initial income I and N future
pre-sunset steps, split `floor(I*N/2) - actual_income` into exact half-energy
units: `I * dim_steps`, `I * lit_steps - 2*actual_income`, and the final rounding
term `-(I*N % 2)`. Dim means recorded unshaded strength below 64. This is an
accounting partition of the heuristic, not a claim that it models per-step
income. Also retain the actual-body unshaded bound and its difference from
income. That is a simultaneous illumination bound, not a no-shade simulation.

Keep light-percentage changes, mature-leaf changes and sun-ray changes visible.
The input does not record per-leaf light, positions or occluder identities; it
cannot isolate self-shade from neighbors or reconstruct a frozen-canopy raycast.
Do not assign the unexplained remainder to one of those causes.

## One diagnostic correction

Compare the original arithmetic with one predeclared afternoon-only correction,
not a parameter sweep. Preserve its half-current-income factor and all costs.
Estimate later global strength using current phase and sun strength only:

`estimated_strength(q) = 24 + floor(base_beam(q) * current_beam / base_beam(now))`

Here `base_beam` is the known unscaled daily sun curve, and `current_beam` is
current observed sun strength minus 24. Count future pre-sunset steps q whose
estimated strength is at least 64, and credit `floor(I * useful_steps / 2)`.
Keep morning credit unchanged; current globally dim afternoon light earns zero
credit. Use no future weather, body, income or shade observation in this
diagnostic. Current attenuation is held fixed, not asserted to predict the
seasonal ramp. Retain errors against actual future income, including any
underestimates and successful actions it would reject. Do not use future outcome
to choose a margin, cutoff or exception.

These are same-observation decisions, not simulated rescues. Record separately
whether a changed forecast would alter a purchase after the unguarded birth step,
and whether sunset actually covers the forecast's nominal night requirement.

## Dawn and deliverables

For every observed dawn, retain the initial balance and all samples through the
first positive income or the next noon, death or capture endpoint. Separate
maintenance paid from maintenance due and shortages. A night funded exactly to
dawn need not fund the following dim interval. Mark missing follow-up explicitly.

Export all event receipts, dawn windows, case outcomes, raw and deduplicated
summaries, and the evidence limitations. Offline verification must recompute the
entire analysis from the pinned input and reject corrupted clocks, illumination,
income bounds, budgets, alternative estimates and deduplication. Use the result
to propose a bounded next step, not to promote or implement the diagnostic rule.
