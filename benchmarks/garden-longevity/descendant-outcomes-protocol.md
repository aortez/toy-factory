# Seed production to established descendants: offline protocol

Use the existing eight crowded 192-day histories to connect the short-horizon
allocation diagnostic to actual offspring. This is an exploratory analysis of
already inspected development cases, not an independent validation set. Freeze
these definitions before calculating the new cross-generation tables. No new
native runs, policy changes, scalar fitness, training, or firmware deployment.

## Fixed inputs

- `artifacts/garden-crowded-recruitment`, manifest SHA-256
  `7c3e50235343b2a223e607bbacbfe6d06f55b735c0ea452fc777ed04e1b5ef77`.
- `artifacts/garden-seed-attempts`, manifest SHA-256
  `0615e91b550b20ce60050f76b6bce5d7beef8902123ebbeaa9053e0e5c37eacb`.

Retain all eight cases: both frozen neural/reserve policies in all four original
capacity/world/schedule pairs. Verify all artifact hashes and reanalyze the saved
world/site/attempt traces against the old analyses. Bind the two bundles to the
same world/site hashes, patch boundaries, model and cases. Preserve all original
bundles, analyses and reports. Existing screenshots remain review evidence;
there is no changed visual behavior to capture in this offline task.

## Cohorts, identity and follow-up

The primary cohort consists of **seeds created during (day 160, day 192]**,
identified by `(parent ID, creation tick)`. Join each germinated seed to exactly
one child, keeping birth time, parent, generation and location consistent. Check
all reconstructed seed counts against per-parent ledgers, including reclaimed
parents. A child born after day 160 from a seed created earlier is excluded from
this primary cohort; keep a reconciliation with the previous birth-based cohort.

For each purchase record separately:

1. Parent survival for a full day after purchase: confirmed, natural-failure,
   patch-censored, or horizon-censored. Shortages are not an absolute veto.
2. Seed outcome: expired, pending, or germinated.
3. Child establishment: alive at age one day, natural death at/before that
   boundary, patch-censored, or horizon-censored. A child alive at confirmation
   qualifies even if it later dies; retain its final state and cause separately.
4. Whether that established child has an actual child of its own that also
   survives one day by the horizon. This is an observed additional generation,
   not indefinite persistence. Keep both generation links explicit.

Natural death exactly at confirmation fails; an alive confirmation exactly at
the horizon qualifies. Patches at/before confirmation censor natural survival
rather than becoming starvation. Same-tick ecology precedes a patch: a seed
purchase on its parent's patch-death tick is valid, but its subsequent parent
survival is censored. No extrapolation past the horizon, no revival, and no
requirement that a parent remain alive for an independently surviving child to
count. Natural/patch parent death at child confirmation and at horizon remain
separate fields.

Report all seeds and a prespecified **full potential follow-up** subset: creation
plus one maximum seed lifetime (3840 logic ticks) plus one child day (3840 ticks)
is within the horizon. This creation-time eligibility rule does not cherry-pick
early germinations among recent purchases. Retain known recent outcomes too,
but do not mix their denominator with the full-potential subset. Patch-censored
children remain censored even in that subset; available calendar time does not
guarantee undisturbed follow-up. Do not treat expiry as seedling death.

## Parent and opportunity diagnostics

Retain every plant alive during the closing window, including newly born plants,
with its observed closing live time and terminal status. Group them descriptively
as no closing purchases, purchases without an observed established child, or
at least one established child from a closing purchase. A non-producing survivor
is **not automatically WAIT**: it may grow or have reproduced earlier.

For producers, retain raw purchases, distinct parent-age bins with full-day
parent survival, the old four-bin cap as a diagnostic only, established children,
and children with established offspring. Do not compare 32-day counts as if they
were scores from the earlier eight-day single-seedling challenge.

Attribute actual saved seed visits to the primary cohort: dormant/mature checks,
expiry, eligible actual location, any hypothetical open column, and an open
column within the seed's recorded at-creation dispersal support. Keep overlapping
blockers and missed-location checks. Repeated checks are not independent trials,
and an opening elsewhere is not proof of a possible landing, a counterfactual
birth or a surviving child. Do not divide away poor outcomes based on these
policy-dependent opportunities or construct an opportunity-adjusted reward.

Export seed-level and parent-level outcomes, per-case funnels, the creation-time
eligible subset, and descriptive totals. These cases share histories; totals
are bookkeeping, not statistical estimates or policy rankings. For illustration
select the first parent in sorted `(case key, parent ID)` order satisfying each
category, including an established child with a naturally dead parent if present.
Report absence of a category honestly, not by changing the selection rule.

## Checks and decision boundary

Test exact confirmation/censoring boundaries, posthumous germination, parent
reclamation, distinct seed/child identities, recent versus eligible cohorts,
expiry versus child death, two-generation establishment, early success followed
by later death, opportunity identity/order, and baseline immutability.

This analysis can demonstrate which signals distinguish productive allocation
from established descendants in these histories. It does not choose the relative
value of parent survival and offspring, qualify the environment, or start search.
Use the findings to propose one bounded next step; do not silently introduce new
ecology or fit a reward to these selected examples.
