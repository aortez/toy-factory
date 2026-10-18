# First day water reserve comparison protocol

Test the water-allocation proposal from [the ordinary first-day diagnosis](landing-establishment.md).
Freeze this protocol before collecting the panel. This is one bounded host-only
comparison, not permission to train, retune, promote, flash, commit or publish.

## Fixed scope

Use the same twelve worlds and six archived single/multi live finalists from
searches 33 through 35 as the recruitment and range panels. Pin the four source
archives used by `garden_landing_range.INPUTS`, plus the first-day diagnosis
archive SHA-256 `0c3d3fc87c0cefd3d4d756485cd3b863af50b583d7ddd1d2ddaedeaf43cd720d`.
Both arms run through day 192 with every research ecology switch OFF, ordinary
dispersal, eight plant/seed slots, 256 nodes, fixed models, no gardener and no
irrigation. Use one UBSan host binary for both arms. Do not change observations,
costs, weather, capacities, resource grants, objective or model selection.

## Precisely one intervention

Control explicitly disables the probe. Treatment reuses the existing
`TOY_FACTORY_GARDEN_SEEDLING_WATER` component of the seedling reserve adapter
for every living descendant at ages 1 through 256 ecology ticks inclusive.
Founders, age zero and age 257 onward are unaffected. Guard all paid growth
actions, including tip finishing, but do not restrict reproduction.

A paid proposal must leave four upkeep payments for its resulting shoot count
after paying the ordinary species water cost. An EXTEND proposal for a root
whose first available ranked destination is below the soil boundary, wetter
than the tip, and contains at least the growth-water cost instead retains one
payment. Equality permits spending. Reuse the existing predicate, including its
inclusive soil boundary. No hypothetical uptake is credited. The existing
energy forecast may be evaluated but its result is never enforced in this arm.

Rejected proposals become WAIT with empty candidate order. Preserve their
priority and proposed memory, normal all-tip arbitration/tie order, and normal
winner-only memory/nonce advancement. In particular, a refused shoot can remain
the winner; do not force a root bid or retry arbitration. No threshold sweep,
different release time, additional energy rule or silent fallback.

## Identity and observer contracts

Use a separate explicit replay kind and a versioned probe fingerprint covering
the ordinary state/model/cache fingerprint and enabled/disabled mode. Preserve
the original fingerprint too. Ordinary replay/training must not accept guarded
output as an ordinary run. Off-mode biology, results, scores and recruitment
trace bytes must exactly reproduce the historical ordinary panel.

Reuse the five-stage first-day resource observer and complete seed/lineage
ledgers. Add a bounded caller-owned per-step audit of eligible bids: record the
original highest-priority winner, its water forecast, whether WAIT was applied,
bid/denial counts, and funded wetter-root alternatives. Those alternatives are
local proposals, not proven successful extensions. Publish audit outputs only
after a successful complete world/cache step. Trace collection must not change
world state, model bytes, ordinary RNG or winner memory.

## Measurements and acceptance

Use the unchanged four-window lexicographic renewal score. Births in (62,190]
receive full first-day follow-up; qualifying confirmations use confirmation
time in (62,190]. Keep these cohorts distinct. Pending seeds/recent children
are censored. Compare both climates separately, preserving all twelve paired
results and adverse cases. Do not match descendant IDs after divergence.

To pass this diagnostic screen, treatment must retain each climate's score key
and late first-day survivor count, improve at least one climate's key or late
qualifying confirmation count, and cause no earlier/new biologically empty
world. Empty means no living plant and no banked seed at an event boundary.
Report births, resource deaths, actual water/growth budgets, root allocation,
seed production/expiry, historical durable parents, terminal tiers and selected
WAITs with funded wetter-root alternatives. More seedlings or longer survival
alone cannot override a renewal regression. Even a pass requires separate
confirmation; these are retrospective diagnostic cases.

## Repetition and visual review

For each arm/case collect initial state, complete traced run, untraced final
capture, and a repeated traced final capture. Require exact full results,
recruitment/probe trace bytes, resources and raw pixels. Retain all 24 day-192
images; make one six-row sheet per climate, control left and treatment right,
in the existing fixed single/multi 33, 34, 35 order. Do not select prettier
frames. Independently reproduce the frozen panel with one worker.

Freeze binary, cache, model bytes, inputs, protocol, source and Python tools;
hash-check collection and verification. Fresh output only; mark incomplete
bundles failed. Native tests cover reserve boundaries and wetter-root exception,
age/founder gates, off equivalence, trace on/off equivalence, winner semantics,
config/hash identity, complete rollback and malformed inputs. Python checks
reconcile every receipt and portable outcome. Record limitations and stop after
the one comparison, without an automatic follow-up intervention.
