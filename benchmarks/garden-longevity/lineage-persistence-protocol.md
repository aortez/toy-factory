# Lineage persistence v2: frozen offline test contract

Address v1's preference for numerous brief establishments and its unresolved
seed-only endpoint. Keep v1, ecology, controllers and trainer unchanged. This
is an offline candidate test, not a training run or qualification milestone.
Freeze this contract before computing v2 native rankings; do not tune it to
favor either already-inspected controller.

## Fixed clocks and evidence

Reproduce the complete v1 analysis from its frozen original inputs. The v1
bundle manifest SHA-256 is
`3229d3962af2298a303a9b68cfe43a390112a185c3edad7a5091f1fd64fcb3e8`.
Use all eight saved native histories, with four matched conditions, unchanged
policies and their recorded deterministic weather/patch histories.

Set the scoring window to **(day 158, day 190]**, keeping a 32-day duration.
Reserve **(day 190, day 192]** for follow-up for every world, not only failures.
This moves the scoring window two days earlier than v1's original experiment;
therefore rescore v1 on the identical new main window as a named control. Do
not compare a new number directly with the old 160–192 score as a formula-only
effect. Retain both main-horizon and follow-up terminal states.

One day = 3,840 ticks; one ecology sample = 15 ticks. Full seed lifetime is
one day. Two days allow every seed already pending at the main horizon either
to expire or to germinate and reach its child's first-day deadline. New seeds
can be produced during follow-up; the budget does not extend recursively.

Derive main-horizon records by projecting the complete validated histories:
exclude future births/purchases, hide later deaths, and mark seed outcomes
after the cutoff as pending. Recompute window counters only after validating
the original ledger. No future outcome may change main-window event credit.

## Score and terminal follow-up

Maximize lexicographically:

`(terminal_tier, renewing_child_live_ticks, descendant_live_ticks,
  renewing_parents, new_establishments)`

**Renewing child live ticks** are the main-window occupancy of children whose
first-day confirmation falls inside the main window and whose parent is an
established non-founder. Sum their observed alive samples at/after confirmation,
multiplied by 15. Unlike a count, four children each dying one sample after
confirmation earn 60 ticks, not four whole establishment rewards. A parent may
be dead by confirmation: its own first-day establishment remains sufficient.
Each child contributes its own live samples once; later ancestors do not earn
extra copies of the same child's time. Older confirmed children do not earn
this recent-renewal component, but do contribute to all-descendant occupancy.

The other main-window metrics retain v1's exact definitions: established
non-founder occupancy, distinct established non-founder renewing parents, and
new first-day establishments. Event counts are now only tie-breakers after
observed live time. Seeds, body size, stores, actions, numeric generation
labels and founder lifespan still have no direct reward.

**Terminal tier** is determined at the common follow-up horizon, not adaptively
at the first good result:

- `1`: at least one established non-founder is alive.
- `0`: living plants remain without an established non-founder, OR there are
  pending seeds but no living plants. The latter is labeled
  `seed-only-unconfirmed`, not demonstrated survival, extinction or healthy
  recovery. It has no direct renewal/occupancy credit from its seeds.
- `-1`: no living plants and no pending seeds: observed extinction.

A seed-only ending at the main horizon therefore gets a fixed observation
budget. Expiry, early natural/patch death, established recovery, later collapse
and new-generation seed-only continuation remain separate diagnostics. An
original pending seed still pending at the follow-up deadline is an accounting
error. A newly produced pending seed is allowed but remains unconfirmed. A
short/truncated history returns no comparable key for the entire suite; it must
not silently shorten the budget or drop a world. Exact longer/extra follow-up
outside the declared deadline is rejected rather than used opportunistically.

All terminal outcomes use post-patch state at the exact boundary. A child
confirmed during follow-up does not earn retroactive main-window event or live
time credit. A later death stops occupancy where it occurs but does not revoke
already observed samples. The terminal tier can still change on one sample.

Aggregate as minimum terminal tier, sum of terminal tiers, then sums of the
four remaining components in declared order. Require matching conditions,
main windows and follow-up deadlines. Report paired, aggregate and all four
leave-one-condition-out ranks, retaining ties. These are descriptive ranks,
not significance or policy selection. The mixed capacities remain a diagnostic
panel, not one selected production environment.

## Predeclared challenges and limits

- The existing four-brief-children fixture must lose to one longer-lived child
  at the same terminal tier. Total observed child-time, not raw count, decides.
- Compare brief grandchildren from multiple renewing parents against the same
  long-lived-child case, preventing unique-parent count from bypassing the fix.
- Preserve independent child credit after parent death; a first-day-failed
  parent cannot create renewing-child credit, but its child can earn ordinary
  descendant occupancy. Founder reproduction alone is not further-generation
  renewal. Natural/patch/confirmation/cohort boundaries must remain exact.
- Test seed-only expiry, recovered established offspring, natural and patch
  failure, later death, fresh seed-only continuation at the deadline, missing
  follow-up, and original-seed/child identity reconciliation.
- Future events must not leak into main-window components. Test cutoff
  projection, input mutation, bad counters/identities, record order, exact ties,
  and mismatched suite windows/deadlines.
- A living old sterile descendant can still persist without earning recent
  renewal. A tiny positive amount of recent renewal still outranks arbitrarily
  greater sterile occupancy. More simultaneous descendants can sum to more
  live time; this is a population-time objective, not a minimum child lifespan.
- An event just before the window loses recent-renewal credit; one near the end
  has less time to accumulate it. Seed-only-unconfirmed tier 0 ranks above
  observed extinction but below demonstrated established presence. Those are
  explicit finite-window preferences, not proofs of indefinite sustainability.

Use synthetic histories to demonstrate score semantics, not claim native
reachability. All original fixtures remain visible, including adverse ones.
After this bounded test, report whether the targeted preference improved and
what adoption decisions remain. Do not expand into another ecology sweep or
train against an unreviewed result.
