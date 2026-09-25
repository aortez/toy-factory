# Sustained renewal: frozen offline candidate protocol

Test the approved continuous recent-renewal and weakest-period proposal as a
candidate evaluation rule, not adopted training fitness. Freeze this protocol
before scoring saved native histories. No native trials, training, mutation,
ecology edits, new images, controller promotion, commit or deployment.

## Fixed inputs and periods

Use the complete coverage bundle, manifest SHA-256
`a9142bff1570b3912b7f7d5dc71dbf4575c3db6df10249cf9b3539643abaf460`.
Verify it first; copy its manifest, results and all 32 selected review histories.
Controllers: original `dc5e849d`, broad G2 `556a5dd2`, broad final `c7c1b31e`,
narrow final `449c35fe`. Generation 1 repeats the original and is omitted.
Four already inspected review seeds (`eb300b12`, `1824c139`, `4d5f9ee1`,
`fe1dd56f`) crossed with fresh-1 `e4d65e6f` and fresh-2 `17c29444`; these are not
a fresh final test set. No development-panel or rejected-mutant sweep.

Four consecutive main periods: **(62,94], (94,126], (126,158], (158,190] days**.
They cover 128 days ending at the existing main deadline, after 62 unscored days.
Each uses its own two-day terminal follow-up (96, 128, 160, 192). Day = 3840
ticks, sample = 15 ticks. All histories are already available through day 192.
No horizon/window-length sweep or favorable endpoint selection follows.

## Candidate credit

At each scored sample, a living non-founder offspring qualifies if it survived
its first full day and its non-founder parent also survived its first full day.
The parent need not still be alive. Its confirmation necessarily predates the
child's confirmation; future parent survival must not be consulted.

Let confirmation be birth + one day. Credit exactly 15 ticks at samples in
`[confirmation, confirmation + 32 days)` while the child is alive (death sample
excluded) and inside the main period `(start, end]`. Thus maximum lifetime
renewal credit is exactly 32 days per child, not 32 days plus one sample.
Confirmation before the period start does not remove credit: carry-in live time
within the age limit counts. Older plants still affect survival but do not earn
indefinite renewal credit. No size, species, energy or resource reward is added.

Validate full original lifetimes, ancestry and counters before projecting each
period to its own terminal deadline. Preserve the existing persistence-v2
terminal tiers and follow-up semantics. Future births/deaths/seed outcomes must
not leak backward. Incomplete follow-up is rejected, not assigned a score.

## Fixed candidate ordering

For the same rectangular panel of worlds and periods, maximize lexicographically:

1. Minimum existing terminal tier across every world-period endpoint.
2. Sum of those terminal tiers.
3. Minimum, across periods, of the sum of credited ticks across worlds.
4. Total credited ticks across all worlds and periods.

All panels have the same number of worlds in each period. Integer period sums
therefore order identically to period means, without floating-point rounding.
No additional tiebreaker: equal four-component keys are ties. The minimum is
taken **after** summing worlds, not summed separately from each world's minimum.
Tier 1 requires a living established descendant, tier 0 preserves living-only
or unresolved new seed-bank continuation, and tier −1 is observed extinction.
These tiers describe finite endpoints, not indefinite viability; no new penalty
for seed-only gaps is invented.

Diagnostics retain all per-world/per-period credit, carry-in versus newly
confirmed credit, bounded available time/death losses, credited child IDs,
terminal classifications, weakest-period identity, individual minimum period,
and zero-renewal world-period counts. Averaging can hide asynchronous individual
slumps: report that limitation, do not silently change the objective to fix it.

## Comparisons and attribution

There are **128 world-period cases**. For each compute unchanged v2 and candidate
credit, and independently check candidate ticks using direct sampled timestamp
arithmetic. For each history, candidate credit must add exactly across the four
periods to credit over their combined interval. Every full original primary
v2 evaluation must still match the saved result.

Use these fixed diagnostic views, not competing objectives to select among:

- unchanged original single-primary v2 ordering;
- old v2 credit under the declared multi-period survival/weakest/total ordering;
- candidate credit at the original single-primary period (terminal min/sum,
  credit sum; exact ties stay ties);
- candidate multi-period ordering above.

This separates changing which periods are assessed from changing credit itself.
For a 32-day period, candidate credit = old v2 credit + bounded carry-in credit;
require exact per-case reconciliation. For all five earlier fixed controller
comparisons (G2/original, broad/original, narrow/original, broad/narrow, broad/G2),
report overall, per-world pairs, each schedule, and blocked leave-one-world-seed-out
results, removing both schedules together. Do not infer light/water causes.

## Arithmetic challenges, provenance and stop

Before native-history analysis, test steady replacement versus a larger one-off
burst, established sterile survivors, founder-only survival, pre-confirmation
deaths, parent qualification/death, seed-only recovery/unconfirmed continuation/
extinction, death/confirmation/age-cap boundaries, and zero-credit ties. Require
credit additivity under arbitrary aligned partitions and a one-sample window
shift affecting only its removed/added samples. Preserve input records.
Check all existing 18 persistence fixtures and original counter validation.
Include an explicit complementary-slump panel showing how different individual
weak periods can be masked by averaging; keep this as a known limitation.

Keep protocol/source/input hashes, original primary identities, per-child credit,
synthetic challenge outcomes and all fixed comparisons. Repeat the complete
analysis identically before a complete manifest is published. Export portable
results after collection; frozen artifacts must not be overwritten.

Stop for discussion after this diagnostic. New rankings are not evidence of
generalization or grounds to promote a controller. Non-overlapping periods still
share trajectories and are not independent replicates. No new training objective
is installed, no longer-than-192-day run is implied, and the original primary
findings remain intact.
