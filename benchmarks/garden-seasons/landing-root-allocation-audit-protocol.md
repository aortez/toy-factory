# Offline root allocation population audit

Separate changed recruitment and lifetime exposure from resource regressions
in comparable plants in the completed focal root allocation experiment. This
is an accounting investigation of saved histories, not a new experiment or a
change to the population harm screen. Run no simulator, training or firmware
deployment, and do not change any policy or threshold.

## Fixed evidence and coverage

Use all four baseline pairs through tick 983040, with no selection of favorable
plants or time windows. The portable input is
`landing-root-allocation-results.json.gz`, SHA-256
`8877c4e6f7f951ec06c546c5fc6f3e0ea0175a250b70e21596e734cd8fa63d76`.
The corresponding raw manifest SHA-256 is
`b2aab73b6ed9fadf1e28d1dd32e28911202661ca0ff593cc3c1a3641f4195972`.
Verify adult trace hashes, including exact repeats, before extracting receipts.
Preserve the original capture, protocol and result without edits.

Match births by recursive ancestry, birth tick, column and species, using the
existing matcher. Numeric lineage IDs alone do not identify comparable plants.
Separate founders, the focal shrub, matched nonfocal offspring and unmatched
offspring. Matched nonfocal plants are not necessarily spatial neighbors or
unaffected controls. Include deaths and endpoint censoring explicitly.

## Exact population decomposition

For each arm retain every plant's full lifetime maintenance opportunities,
unpaid energy and water, resource accounts and survival. Reconcile group totals
to the saved population metrics. Founders are separate because the existing
harm screen measures offspring, not founders.

For each matched pair, define the common endpoint as the earlier of both
recorded deaths or the fixed stop. Include all ecology samples from birth
(tick 15 for founders) through that endpoint, including a terminal payment.
Both arms therefore have the same maintenance opportunities in this window.
Keep the rest of either lifetime as a separate unmatched exposure tail; do
not count removed bills as a resource improvement. Newborns receive no payment
opportunity at their birth tick. A zero opportunity rate is unavailable.

Partition offspring exposure into focal common window, focal tail, nonfocal
matched common windows, nonfocal matched tails and unmatched births. Sum unpaid
units and payment opportunities rather than averaging individual plant rates.
For each resource, report exact rational rates and each group's signed
contribution `U_candidate_group / P_candidate_total -
U_control_group / P_control_total`. These sum exactly to the observed rate
change, even for absent groups. Also report raw changes in unpaid units and
opportunities. Contributions are an arithmetic decomposition, not causal
attribution or independent experimental effects.

## Matched resource histories

Stream the saved adult receipts and retain every matched plant's complete
common-window receipt sequence, deduplicating identical sequences. Validate
birth and death stages, resource continuity, income, overflow, construction,
reproduction, paid upkeep, terminal discard, payment counts and shortages.
Full-window summaries must agree with the existing lifetime analysis whenever
the common endpoint is that arm's end. Shortage lists must agree for every
common window. Retain both energy and water, not only the resource that failed.

For every pair report first differences in gross income, overflow, retained
income, stores, body counts, growth, reproduction, paid and unpaid upkeep.
Retain exact ticks and both values; absence means no difference over the
observed common window. Compare water deficits over the same opportunities,
and distinguish loss of retained income from extra spending, storage changes
or terminal discard. Do not infer local water theft from uptake differences
alone: body geometry, canopy, recurrent decisions, reproduction and later
cohorts may also differ.

## Verification and stopping point

Provide a no-clobber offline tool, tests of identity matching, denominator
changes, common-window boundaries, zero exposure, accounting and corrupt
evidence rejection. Repeated exports must be byte-identical. Portable
verification rederives every summary; raw verification additionally reextracts
all selected receipts from hash-checked complete streams. Neither may launch
a process. Record all four outcomes and any unresolved mechanism before
proposing the next bounded investigation. No revised allocation rule is part
of this audit.
