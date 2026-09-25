# Individual weakest-period renewal: fixed offline protocol

Investigate the approved next aggregation, not adopted training fitness. Keep
bounded-age credit, survival tiers, periods, worlds and controllers unchanged.
No new native simulation, training, screenshot, objective installation, model
promotion, commit or deployment. Freeze this protocol before the new comparison.

## Fixed inputs

Use the sustained-renewal bundle with manifest SHA-256
`37b3a11704b365b3bcfee1b043188739a0b96642a331f9e6a8cbf091eef77a75`.
Verify that bundle completely, including its saved input fingerprints, sampled
credit arithmetic and original-primary equality. Copy its manifest and results
into a fresh analysis bundle. This analysis reaggregates the **same 128 saved
world-period cases**, not newly collected independent evidence.

Original `dc5e849d`, broad G2 `556a5dd2`, broad final `c7c1b31e`, narrow final
`449c35fe`; four review seeds `eb300b12`, `1824c139`, `4d5f9ee1`, `fe1dd56f`,
each with fresh-1 and fresh-2. Periods **(62,94], (94,126], (126,158], (158,190]**,
each with its existing two-day terminal follow-up. Same 32-day post-confirmation
credit cap, sample boundaries and ancestry requirements. No other horizons,
seed panels, rejected candidates, age caps or aggregation variants are searched.

## The single new ordering

Let R(world, period) be the already verified bounded-age renewal ticks.
Keep survival first, maximizing the four-component integer key:

1. Minimum terminal tier across all world-period endpoints.
2. Sum of those terminal tiers.
3. **Sum over worlds of each world's minimum R across the four periods.**
4. Total R over all world-periods.

Equal keys remain ties, with no additional selector. World-count denominators
are equal within every comparison, so integer sums order identically to means.
This is not a minimum across worlds, a percentile, a zero-gap gate, or a reward
for diversity. No such constraint is added if this candidate also has limitations.

Compare only against the previous pooled-period key, whose third component was
the minimum over periods of the sum across worlds. Preserve and report the
previous primary and all previous views unchanged; do not replace their results.

## Diagnostics and invariants

Report every world's minimum, all tied weakest periods, total credit, zero-credit
period count and terminal tiers. For each group report sorted individual minima,
zero-minimum worlds, per-period totals, the old and new keys, and
`pooling_gap = old pooled minimum - sum of individual minima`, which must be
nonnegative. The difference is credit previously supplied by different worlds'
noncoincident weak periods, not newly lost plant lifetime.

For each controller, the new credit component and total credit must equal the
sum of the components of disjoint schedule groups. With tied terminal tiers
(as in the existing native panel), losing on both schedules must not become a
pooled win. Do not generalize that assertion to arbitrary unequal survival tiers.
With one world, old and new keys must be identical. Per-world comparisons must
therefore exactly match the previous paired results. Total credit and survival
components must remain identical in every old/new group comparison.

Retain all five fixed controller comparisons: G2/original, broad/original,
narrow/original, broad/narrow, broad/G2. Report overall, eight paired worlds,
each schedule, and four blocked leave-one-world-seed-out groups (omit both
schedules of a seed). Explain each pair's third-component delta as the sum of
its eight per-world minimum deltas; do not match plant IDs across controllers.

## Constructed challenges and stop

Reuse all ten prior synthetic lifetime cases without changing them. Verify that
steady replacement beats the bigger one-off burst, sterile survivors receive no
renewal, terminal recovery/seed-only/extinction retain their priorities, and the
complementary-slump panel no longer gains continuity from pooling phases.

Add one declared compensation challenge using validated synthetic lifetimes:
one garden with three staggered replacement children per period plus one sterile
garden, versus two gardens with one replacement child per period. Test and report
whether high individual minima can still compensate for a different world's
zero. This is a limitation test, not grounds to silently install a hard gate.

Unit-test complete fixed panels, wrong rules/clocks/age limits, missing follow-up,
input non-mutation, numeric/credit-ledger consistency, tied minima, exact ties,
world-order invariance, schedule partition additivity, single-world identity and
blocked omissions. Preserve protocol/source/input fingerprints, repeat analysis
identically, and publish a complete manifest only after checks succeed. Exports
are new files outside the frozen evidence. The copied baseline's fingerprints
anchor original lifetime verification; the new bundle verifies aggregation from
that frozen score ledger, not native replay or reconstructed screenshots.

Stop after this one candidate. Discuss whether its tolerated cross-world tradeoffs
match the intended behavior; no ranking is grounds for model promotion or a new
training run. These are already inspected review worlds, not a reserved final
test set, and the four periods share trajectories rather than independent trials.
