# Seed bank ownership and access audit protocol

Explain the bank-access barrier identified by the
[recovery-gate trace](landing-recovery-gates.md), using only saved data.
Distinguish long residence from same-step allocation order before proposing
an intervention. This audit runs no new simulation, training or firmware.
Freeze these definitions before computing the new ownership/access results.

## Fixed inputs and coverage

Use the complete six-model, two-arm recovery panel, including Single /33 with
no established early replacement. Pin `landing-recovery-gates-results.json.gz`
at SHA-256 `3fabe95f2d3fa20c6a4d1b97074e15d98d3095f13ba038c02fdc3884044df223`
and its source bundle manifest at
`08c27340adc56e1acff156d2a7fbcec76f3a4c2b4ef799a8f075834c1b88abb1`.
Preserve the existing five focal lineage identities, historical results and
all plant and seed ledgers through day 256.

Read all ordered production visits over the original trace window: ecology
steps immediately after day 158 through day 218 inclusive. Export only those
visits into a portable, hash-linked excerpt, preserving order and exact values.
Keep the full row clock, including steps with no purchases or no eligible
plants. Reconcile the excerpt against the frozen production summaries and,
when the local bundle is available, against the original compressed traces.

## Access accounting

Reconstruct bank occupancy after seed ageing/germination but before the first
production visit from the lifetime ledger. Apply every successful purchase
in recorded visit order and require the count at each parent's visit and at
the end of the step to match. No end-of-step count substitutes for entry
capacity or a parent's actual turn.

Classify each living visit into four exclusive outcomes: another gate fails;
bank full at loop entry with all other gates passing; earlier visits fill the
bank with all other gates passing; or an actual purchase. Also retain all
simultaneous masks and the earlier report's ready-flower, daylight,
maintenance-cadence, cooldown-clear subset. Record each otherwise-eligible
miss at a step that began with space, naming the earlier buyers and the
released seeds. These are observed checks, not independent chances or a
prediction of how many seeds an alternative order would produce.

Audit all parents. Report the five focal replacements separately, without
pooling them with old occupants or later post-drought parents. Use the frozen
day-158 control census to label incumbent owners in both arms; retain the
exported parent separately from natural deaths.

## Ownership and residence

For every seed occupying at least one post-step sample in the trace window,
record owner, age range, purchase and exit times, outcome at day 256 and
post-step slot-samples. One slot-day means 256 occupied post-step samples.
The accounting window contains 15,360 samples; its capacity is eight times
that count per arm. Keep empty capacity explicit. Carry-in seeds count only
for their overlap, not their whole lifetime.

Partition occupied samples by owner identity, incumbent/focal/other owner,
living/dead/exported parent status, seed age (under 1, 1–under 16, 16–under 32
days), and eventual germination/expiry/pending outcome. Pending seeds are
right-censored; never label them failed or assign an invented expiry. Record
all releases during the observation window and whether the same step refills
the bank. Keep germination and expiry releases separate.

Follow each observed resident seed's eventual germination through day 256.
Identify posthumous versus post-export births separately and check the child's
first-day survival, death or unresolved follow-up. Compare residence during
the five focal lifetimes as well as over the full trace window. Long-lived
seed supply may bridge drought or parent death; residence alone is not proof
that a seed should be evicted.

## Verification and decision

Use no-clobber portable outputs, pin input/excerpt/protocol hashes, and support
offline reanalysis with no native executable. Test clock gaps, duplicate or
reordered visits, wrong masks/counts/purchases, same-step release-and-refill,
window boundaries, death versus export and censored seed/child outcomes.
Re-extract saved rows independently before reporting the results. Leave the
raw bundle and all earlier evidence unchanged.

If only a few otherwise-eligible checks lose newly opened capacity, distinguish
that limited ordering effect from the larger residence problem. If useful
posthumous recruitment depends on retained seeds, do not infer that shortening
viability or indiscriminate eviction would improve renewal. Any subsequent
capacity, allocation, residence or environmental experiment requires a separate
bounded proposal and must measure establishment, not just purchases.
