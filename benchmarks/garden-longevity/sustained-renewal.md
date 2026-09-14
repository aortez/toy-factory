# Sustained renewal: useful credit rule, pooling hides individual slumps

Bounded-age renewal credit passes the intended arithmetic checks: it rewards
steady replacement over a larger one-off burst, stops crediting old sterile
survivors, and removes the previous whole-cohort window-boundary effect.
However, **the proposed pooled weakest-period ordering should not be adopted
yet**. In the saved runs it rewards a controller with two complete zero-credit
world-periods; it can also reverse comparisons when disturbance schedules are
pooled. Those are important limitations for a goal of reliable individual gardens.

[Frozen protocol](sustained-renewal-protocol.md) ·
[All scores, child credit, synthetic challenges and comparisons](sustained-renewal-summary.json)

## What was evaluated

Same four frozen controllers and eight already inspected review conditions as
the [coverage experiment](training-coverage.md), using their saved complete
histories. Four main periods: **(62,94], (94,126], (126,158], (158,190] days**,
each with two days of terminal follow-up. This gives 128 world-period cases,
each scored with both the unchanged v2 rule and the candidate credit.
**Zero new native simulations, training runs or captures.** No fitness or ecology
was changed, no controller was promoted, and the original primary remains intact.

Candidate credit is sampled living time during the 32 days following full-cycle
confirmation, for offspring of an established non-founder parent. Confirmation
is included; death and the exact age-expiry sample are excluded. Credit can carry
into the next period, but each child earns at most 32 days over its whole life.
The parent can die after establishment without revoking the child's eligibility.

The proposed panel key maximizes, in order:

1. Minimum existing terminal tier over all world-period endpoints.
2. Sum of those tiers.
3. Minimum period credit summed over the declared worlds.
4. Total credit across all worlds and periods.

Every period has the same world count, so using integer sums orders exactly like
means. Importantly, the minimum is taken **after** pooling worlds. The diagnostics
also retain each world's own minimum; that is not silently made part of fitness.

## Constructed challenges

These are validated synthetic lifetime ledgers, not native-reachable examples
or claims about the trained controllers.

| Challenge | Candidate result |
|---|---|
| Steady replacement | Weakest-period credit 119,055; total 487,695 |
| Large one-off burst | Weakest-period credit 0; total 2,949,120; loses to steady replacement |
| Old sterile descendants | Survival tier 1, zero renewal credit |
| Founder-only survival | Survival tier 0, zero renewal credit |
| Child dies exactly at confirmation | No renewal credit |
| Seed-only recovery / new unresolved seed / extinction | Final tiers 1 / 0 / −1; no follow-up credit leaks into main periods |
| Two gardens with complementary slumps | Each has two zero-credit periods, but every pooled period has 122,880 ticks |

The last case is an explicit counterexample to interpreting the pooled score as
individual continuity. It follows from full synthetic lifetimes, not merely
edited score fields. The other tests cover exact confirmation, death and age-cap
boundaries, parent qualification, arbitrary aligned partitions, future-event
exclusion, input preservation, invalid counters and incomplete follow-up.

Credit adds exactly across adjacent periods. Moving a period by one sample
changes only the credit at its removed/added edge samples; it does not retroactively
remove the entire contribution of an older confirmation cohort.

## Frozen controllers under the proposed ordering

All 128 endpoints retain established descendants: candidate aggregate keys begin
with `[1,32]`. The following credit numbers sum plant ticks across eight worlds,
not CPU time. CRCs identify frozen controllers, not newly trained models.

| Controller / CRC | (62,94] | (94,126] | (126,158] | (158,190] | Weakest period total | Zero-credit world-periods |
|---|---:|---:|---:|---:|---:|---:|
| Original `dc5e849d` | 2,198,790 | 1,991,520 | 1,779,285 | 2,717,115 | 1,779,285 | 0 / 32 |
| Broad G2 `556a5dd2` | 2,186,640 | 2,649,645 | 2,316,150 | 3,010,110 | 2,186,640 | 0 / 32 |
| Broad final `c7c1b31e` | 2,352,735 | 2,246,100 | 2,387,340 | 2,785,335 | 2,246,100 | 2 / 32 |
| Narrow final `449c35fe` | 2,192,025 | 2,407,095 | 2,172,795 | 2,715,090 | 2,172,795 | 0 / 32 |

The proposed ordering is broad final, broad G2, narrow final, original. This is
a **changed yardstick applied retrospectively**, not evidence that training has
improved or that any model generalizes.

Broad final's weakest-period total is 26.24% above the original, and its total
credit is 12.49% higher. The aggregate advantage survives all four blocked seed
omissions, but broad wins only **3/8 individual-world comparisons** under the
same rule. It loses on fresh-1 and wins on fresh-2.

Its two zero-credit periods are both **(62,94] on fresh-2**, seeds `1824c139`
and `4d5f9ee1`. These gardens are not extinct: at the day-96 deadlines each has
five living established descendants, two founders and eight pending seeds.
The periods even contain four and one new full-cycle establishments respectively
under the old diagnostic. What is absent is qualifying recent offspring of
established non-founder parents, not necessarily all births or reproduction.

Broad versus narrow is only **+3.37%** on the weakest pooled period, wins **3/8**
worlds, and reverses under three of four blocked seed omissions. Broad versus
G2 is **+2.72%**, also only **3/8** wins, and reverses under one omission. There
is no basis here for choosing broad final as a reliably superior controller.

## The pooling reversal is visible in real saved histories

Narrow final loses to original under the candidate rule on **each schedule
separately**, yet beats it when both schedules are pooled before taking the minimum:

| Panel | Original weakest-period total | Narrow weakest-period total | Narrow comparison |
|---|---:|---:|---|
| Fresh-1, four worlds | 1,430,580 | 1,416,195 | Worse |
| Fresh-2, four worlds | 256,170 | 209,400 | Worse |
| Both, eight worlds | 1,779,285 | 2,172,795 | Better |

The operation is nonlinear: the schedules' weak periods do not necessarily
coincide, and one schedule can compensate for another. No arithmetic is wrong,
but the pooled minimum measures consistency of the *combined panel*, not a
guarantee for each garden or even each schedule. Non-overlapping periods still
share trajectories; they are not independent experimental replicates.

## Separating the credit change from the period change

The four diagnostic views were declared before analysis. They are not a sweep
from which to select the most favorable fitness:

| View | Broad final vs original, deciding credit component |
|---|---:|
| Original single-primary v2 | −8.22% |
| Old v2 credit, proposed four-period aggregation | +1.78% |
| Bounded-age credit, single primary | +2.51% |
| Bounded-age credit, proposed four-period aggregation | +26.24% |

For every 32-day period, candidate credit equals old v2 credit plus bounded
carry-in credit, exactly. At the primary interval, broad gains 1,314,435 carry-in
ticks and original gains 1,114,545. Their old margin −131,670 becomes +68,220.
This attribution does not establish resource causes or invalidate the original
objective's result. The score definitions answer different questions.

## Recommendation and stop

Keep bounded-age credit as a promising candidate, but discuss **where to apply
the continuity requirement** before adopting an ordering. If individual gardens
must keep renewing, assess each world's weak periods before pooling, or explicitly
limit sustained individual failures. Choosing that rule and its tolerance is a
behavioral design decision, not an automatic fix after seeing the rankings.

Do not add another training run yet. First compare an explicitly agreed
individual-continuity rule against the same burst/recovery/complementary-slump
challenges. That follow-up was not run here. Diversity remains diagnostic; no
new species reward, minimum-population threshold or penalty was introduced.
Original primary results, native binaries and device state remain unchanged.

## Verification and reproduction

**17 new unit tests and seven relevant pure-Python CTests pass.** All 18 existing
persistence fixtures preserve their original evaluations. Every candidate case
matches a separate direct sampled oracle, every combined interval equals its
four period credits, all original full primary scores/aggregates reproduce,
and all comparisons retain exact paired/schedule/blocked panels. The previous
coverage bundle also re-verifies. Native simulation regression tests were not
rerun during this offline analysis.

Analysis plus deterministic repeat: **3.36 seconds**, excluding initial input
verification/copying and the final verification pass. Frozen bundle: 40 artifact
files, **12.99 MiB**, manifest SHA-256
`37b3a11704b365b3bcfee1b043188739a0b96642a331f9e6a8cbf091eef77a75`.
The portable JSON includes all 128 cases, per-child bounded credit, all four
comparison views, ten synthetic cases and the complementary-slump panel.
Raw source histories and source snapshot remain in ignored local artifacts.

```sh
# Requires the original frozen coverage input; chooses a fresh output directory.
python3 -W error sim/garden_sustained_renewal.py \
  --output artifacts/NEW-sustained-renewal

# Recompute/check all frozen scores and the portable export; no native runs.
python3 -W error sim/garden_sustained_renewal.py \
  --output artifacts/garden-sustained-renewal-v1 --verify \
  --check-export benchmarks/garden-longevity/sustained-renewal-summary.json

# Optional new portable export; existing files are never overwritten.
python3 -W error sim/garden_sustained_renewal.py \
  --output artifacts/garden-sustained-renewal-v1 --verify \
  --export artifacts/NEW-sustained-summary.json
```

Only the previous [day-192 captures](training-coverage-gallery.md) are available.
No images of these earlier periods were generated or implied.
