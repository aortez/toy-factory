# Saved-trace reproductive funnel audit

Freeze this plan before aggregating new outcomes. Read only the 64 primary
trajectories from the [fresh reserve confirmation](seedling-confirmation.md):
32 matched seasonal worlds through day 128, both control and unchanged guard.
No new simulation, replay, controller tuning, environment change, training or
device flash. Keep every world, including the four late-survival and ten
historical-reproduction regressions. Do not pool earlier panels into these data.

## Exact records and limits

Check the confirmation archive's fixed hash and every compressed primary trace
against its saved hash. Seeds are logged at every ecology step. Production runs
after germination and appends at most one seed per parent per step, always at age
zero. Therefore `(parent lineage, creation tick)` identifies a seed in this
frozen implementation. Verify that invariant rather than inventing IDs or
silently resolving collisions.

Track every seed, including founder production and seeds whose parent dies or
is reclaimed. Require consecutive 15-logic-tick observations, age continuity,
stable metadata and bank order. An old seed either remains, expires at age 8192,
or germinates at ages 8..8191. Match removals to new children in native seed-bank
order using parent, species, generation and column. Reconcile all creation,
expiry and birth counters, the complete saved birth/death history and every daily
state hash. Any ambiguity, missing record or mismatch fails the audit.

Retain per-seed creation/disposition/child records and per-parent production,
children, first observed flower and follow-up. A banked seed at the horizon is
pending, not failed. A child may germinate after its parent's death; never stop
ancestry tracking at parent death or reclamation.

Record mature-seed **post-step** blocker histograms as context only. These are
not the sequential pre-germination checks, cannot establish the sole cause of
failure, and can overlap. Flower counts include immature flowers; an observed
flower is not proof of a reproduction-ready node. Do not reconstruct missing
pre-purchase gates or claim an exact energy/water/space cause from these logs.

## Cohorts and stage definitions

Main cohorts are established descendants (parent nonzero, survived a full day),
using the existing strict death boundary. Report the whole history and births
strictly after day 112, separately for each arm. Reconcile these populations and
their no-child/child-without-day-survivor/durable counts with the confirmation.
Founders and descendants that fail establishment remain in the event ledger and
seed accounting, but are not mixed into these establishment-conditioned cohorts.

Classify each established parent by its furthest observed stage:

- `no_seed`: no seed produced by the observation cutoff.
- `seeds_pending`: produced seeds, no child, at least one seed still banked.
- `seeds_expired`: produced seeds, no child, every produced seed expired.
- `children_pending`: children exist but none survived a day yet, with at least
  one living child too young for full-day follow-up.
- `children_failed`: children exist, none survived a day, and no living young
  child remains. Keep any banked seeds visible; this is not an eternal-failure claim.
- `durable`: at least one child survived a full day, regardless of whether parent
  and child are still alive at the cutoff.

Split every stage by parent alive/dead. Distinguish `no_seed` parents with no
flower ever observed from those with flower tissue; neither is a causal gate
diagnosis. Show total seed outcomes and child eligibility/survival/censoring.

Also compare fixed ages 1, 2, 4, 8 and 16 Garden days from parent birth. Require
the calendar horizon to reach each landmark, report excluded/censored counts
(alive and dead), and retain eligible parents that died before it. Compute events
strictly as observed by that landmark, without leaking later seed, child or
flower outcomes. This controls observation duration without silently conditioning
on survival to older ages. It is still a comparison of different resulting
cohorts, not individually matched descendant rescues or a causal effect estimate.

## Reporting and verification

Report full/closing funnels, age landmarks, species, weather-block, layout and
controller partitions, plus each adverse pair. Retain portable per-seed and
per-parent ledgers with source/trace hashes, a compact summary and a written
interpretation. Reuse links to the already verified eight confirmation images;
do not pick new attractive examples or generate screenshots from a different run.

Run the analysis twice from unchanged raw inputs and require identical output.
Tests must cover missing/changed seeds, duplicate creation, order/ancestry errors,
dormancy/expiry boundaries, posthumous germination, young living versus dead
children, exact one-day survival, age-landmark censoring and future-event leakage.
Recompute portable aggregates in CI without requiring the ignored raw traces.
Choose the next investigation from the measured stage breakdown, without changing
the rule or claiming environment qualification during this audit.
