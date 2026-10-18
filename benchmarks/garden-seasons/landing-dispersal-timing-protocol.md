# Audit seed dispersal reach and crowding timing

Status: **FROZEN before calculating the new results.** Follow the
[renewal-gate audit](landing-renewal-gates.md) to distinguish seeds purchased
into occupied sites from sites occupied later, and local dispersal limits
from world-wide crowding. Use saved evidence only. No simulation, training,
firmware, ecology change or default promotion.

## Inputs and coverage

Pin the renewal results at SHA-256
`20d269d868b2cc1135e93d4b0f4ebe37ef667e3316d92e280d1d7488b38bd255`,
its portable windows at
`d7ff641241c1cc0f242e68628648a04ce82e1ffe5046f0a4221a2485b7c61026`,
and the uptake-cap result/lineage ledger at
`687f354bbeb04b71dc2c8d81b57bccefba0a1f6e2cfa6677f9dd14d517647768`.
Retain all 32 primary worlds, not exact repeats, from one examined weather
seed and controller. Reuse `(626580, 983040]` and `(860160, 983040]` with
15-tick samples. Keep per-world results; pooled checks are descriptive.

The existing excerpt contains post-step plant slot IDs, including decomposing
occupants, and sequential seed attempts. Resolve bases through the lineage
ledger. Check the archived implementation and build identities: base-origin,
narrow dispersal, spacing-aware placement enabled, minimum plant spacing three,
and no compiled spacing/flower/wide-dispersal variant. Reproduction changes
neither bases nor slots. Before each seed check, remove this-step newborns
from the final slot census and reinsert earlier germinations in recorded order.
Require exact slot counts and spacing bits, including retained dead plants.

## Purchase timing

For every seed purchased after the excerpt starts, save the exact purchase
slot census and the plants blocking its selected column. Follow all non-expired
checks through germination, expiry or the fixed horizon. Record spacing-witness
runs, first observed check, first mature check, and first clear/blocked times.
Classify blocked at purchase, initially clear then blocked, initially clear
through observation, or no follow-up. Distinguish siblings from other parents
among newly arriving blockers. Do not assume an expired receipt performed a
germination check or a pending seed failed.

Carry-in seeds may lack purchase-time context. Label that gap rather than
substituting the first observed check. All seeds observed in the final 32 days
must have purchase context in this excerpt because viability is 32 days and
the excerpt starts earlier than day 192. Report purchase cohorts separately
from mature-check cohorts, which can include carry-in seeds.

## Reach with missing traits

The saved four-arm traces omit the parent's dispersal trait and production
random draw. Do not invent them. For each parent, enumerate all five legal
traits `-2..2`, preserving all six reflected choices for each. Retain traits
whose support contains every recorded landing by that parent. Parent traits
are constant; seed mutation does not mutate its parent. This is a retrospective
constraint using the whole ledger, not information available to the policy.
Do not infer traits across worlds or assume a particular mutation history.

Retain this landing-only bound. Also derive a separately labeled bound using
the implemented spacing-aware policy: if it selects an occupied column, all
six choices must be occupied. A contradictory or empty candidate set fails
the audit. Never present this rule-dependent deduction as a directly recorded
trait, draw or independent test of the policy's correctness.

At purchase, count globally spacing-clear columns and min/max reachable clear
columns across each retained trait set. At mature checks, reconstruct the
spacing-clear set and use the saved count of all-gates-open columns. Their
coordinates are not saved. Bound the intersection with each possible dispersal
support by set cardinality, honoring whether the actual chosen column is known
open or blocked. Report no globally open site, definitely unreachable,
definitely reachable, or unresolved. Keep landing-only and policy-constrained
bounds separate. Spacing-clear does not imply adequate water/light/capacity.

These describe supports available at the original purchase location; seeds do
not move or retry dispersal. Later reachable vacancies are diagnostic, not
actions that an already-dropped seed can take. No bound predicts child survival.

## Verification and decision

Keep compact purchase contexts, witness runs and mature-check context/count
histograms linked to the pinned excerpt. Reconcile both windows' seed counts,
mask totals, open-site counts and fates with the preceding audit. Support
portable reanalysis and independent excerpt re-extraction with native process
creation forbidden. Use no-clobber output and preserve all earlier evidence.

Test reflection aliases and all legal traits, ambiguity and contradictions,
same-step newborn ordering, dead occupants, new sibling/other-parent crowding,
expiry and window edges, missing/duplicate evidence, and exact intersection
bounds against exhaustive small-set enumeration. Record uncertainty rather
than running new captures to fill gaps in this step. Use the findings to propose
one bounded spatial diagnostic or counterfactual, not a mechanics promotion.
