# Lineage fitness v1: fixed evaluation contract and offline test

Define and test one candidate evaluation function, without wiring it into the
trainer, changing ecology, or searching weights/models. This follows the
descendant-outcome analysis. All real cases have already been inspected; this
is exploratory objective design, not a blind or held-out policy evaluation.
Freeze this contract before computing its new scores/rankings.

## Inputs and scope

Reverify the full `artifacts/garden-descendant-outcomes-v1` analysis, manifest
SHA-256 `529c8ce6cda02dd720c1bac7d6d9a5fdfd316e9cdb4ba84707b1c260f3b11ae1`,
against both original native bundles named there. Retain all eight worlds,
paired as the same four capacity/world/schedule conditions for both frozen
neural and reserve policies. These include two experimental RAM capacities;
the mixture is a diagnostic suite, not a selected production environment.

The scoring window is `(day 160, day 192]`. Read complete lineage and seed
histories, including founders, reclaimed parents, pre-window descendants and
seeds still banked at the horizon. Do not reset ancestry at the window boundary.

## World score: a lexicographic integer tuple

Higher is better; compare left to right, stopping at the first difference:

`(terminal_tier, renewing_parents, new_establishments, descendant_live_ticks)`

1. **Terminal tier:** `1` if at least one established non-founder is alive at
   the horizon; `0` if living plants remain but none is an established
   non-founder; `-1` for observed extinction (no living plants and no pending
   seeds). A seed-only ending returns `needs-followup`, with **no comparable
   key**. A suite containing such a result cannot silently drop that case or
   claim a winner. A fixed follow-up policy must be agreed before training.
2. **Renewing parents:** distinct non-founder plants that themselves survived
   a day and have at least one child completing a day alive during the scoring
   window. Count each parent once per window, not per seed or per child. A
   founder's first generation counts below, not here. A parent's later death
   does not erase credit; it need not still be alive at child confirmation.
3. **New establishments:** distinct non-founder plants that complete their
   first day alive during the scoring window. A child born before day 160 can
   count if its confirmation is after day 160. A late birth not yet confirmed
   earns no establishment credit yet, but is censored rather than failed.
4. **Descendant live ticks:** sum the ordinary sample-time coverage of all
   established non-founders while alive in the window, including older ones.
   Count sample times `t` with `start < t <= end`, `t >= birth + 3840`, and
   no death at/before `t`, then multiply by the 15-tick ecology step. This is
   a discrete observed-occupancy tie-breaker, not continuous-time extrapolation.

One day is 3840 ticks. Death exactly at age one day is not confirmation.
Patch death before/at confirmation is censored natural-survival follow-up,
not starvation. Patch death after confirmation stops observed occupancy but
does not revoke the established event. At a same-tick patch, use post-patch
status for establishment/terminal presence; retain the patch label.

This deliberately changes the event cohort from the previous **seed-creation**
funnel to **establishment confirmations within a fixed window**. Neither a
seed's creation time nor its parent's age selects the new-establishment cohort.
Both contracts remain named and versioned; do not silently compare their counts
as identical. No inferred future survival or opportunity-adjusted denominator.

## Diagnostics, ties and aggregation

Keep terminal living founders, young descendants, established descendants and
pending seeds visible. Retain natural versus patch deaths, recent unconfirmed
births, first-day outcomes, founder/non-founder parent attribution, and the
identities/times contributing to each scored component. Resource/opportunity
diagnostics remain in the unchanged source analysis.

No direct reward for seeds, plant size, roots/shoots, stores, action counts,
numeric generation labels or founder longevity. Descendants are identified by
actual parent links, not a large `generation` number. Duplicate identities or
inconsistent seed/child/lifetime ledgers are errors. Exact tuple ties stay ties.

For a complete fixed suite, aggregate as:

`(minimum terminal tier, sum of terminal tiers, sum of renewing parents,
  sum of new establishments, sum of descendant live ticks)`

The weakest terminal tier comes first so a good world cannot compensate for
an observed extinction elsewhere. Conditions and their multiplicity must match
between candidates. Report all four paired world comparisons, the aggregate
and all four leave-one-condition-out comparisons. These are descriptive ranks,
not statistical significance or policy promotion.

## Tradeoffs and challenges to test before real rankings

Lexicographic order removes adjustable weights, **not value judgments**:

- One extra renewing parent outranks any amount of the two lower components
  at the same terminal tier. More establishments can outrank much longer
  descendant occupancy. Show these exchanges explicitly.
- One established non-founder alive at the endpoint can change the terminal
  tier. Expose the one-sample endpoint sensitivity; this is a finite-window
  candidate, not a robustness guarantee.
- Founder-only survival and seed production without established children tie
  if neither has descendant evidence. This plateau may hinder learning from
  scratch; the available frozen controller already reproduces.
- Successful parent death must not erase child credit. Extinct historical
  reproductive bursts must lose to a surviving world. A young reproducing
  parent that never survives its own first day cannot count as an established
  renewing parent, but its independently established child still counts.
- Late seed bursts earn nothing by themselves. Seed-only endings require more
  observation rather than fabricated viability or an excluded bad trial.
- Old sterile descendants can have occupancy/terminal credit but no new
  establishment or renewal events. Test these against productive lineages.
- Death/patch/confirmation boundaries, cohort boundaries, ancestry relabeling,
  reordered records, cap-free unique-parent counting, empty windows and exact
  aggregation/ties must have regression tests.

Do not tune this order after looking at the real results. If the tests reveal
an unacceptable tradeoff, document it and leave the trainer unchanged. A result
that ranks these saved cases plausibly is a candidate for a small controlled
training experiment, not evidence that optimization cannot exploit it.
