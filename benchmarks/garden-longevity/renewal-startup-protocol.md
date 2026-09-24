# Frozen-model startup diagnostic protocol

Accepted after the [cohort audit](renewal-cohorts.md), before collecting startup
traces. This explains one already-inspected world; it is not a new qualification
panel, training run, reward change, or causal intervention.

## Fixed comparison

- Original `dc5e849d`, R2 N3 `01b9d94a`, R2 W3 `c9ea07fd`; exact saved models.
- World `0d983a80`, rainfed-crowded, through eight garden days (30,720 logic ticks).
- The same 512-node, eight-plant/eight-seed, wide-dispersal/headroom-uptake,
  undrained ecology, selective leaf maintenance and nighttime-growth veto.
- Review-1 disturbance seed `05d87ca0`. Its first event is day 16, outside this
  diagnostic. Check both saved review schedules' startup lifetimes; they are not
  independent startup observations. No gardener or manual resource additions.
- Reuse the frozen inspector from `garden-renewal-stalls-v1` and replayer/models
  from `garden-renewal-return-v1`. Verify native source/configuration identity
  between bundles. Do not rebuild from later native changes.

Pinned manifests:

- Return: `7b20a1dc42516b6d5c13cb2e5335fea9133cb6084c7811049c3d8c263d3c2b98`.
- Inspector: `7e2b0136cfc43babd2d8ffd9442fefe6239eaa3a5ce1a73e588df58ddcb7c1ca`.

## Measurements and budget

Capture every ecology step from reset (2,049 census states per controller), all
growth bids and leaf bids. Repeat each complete trace byte-for-byte. Reconcile
live-step energy/water income, overflow, upkeep, growth, reproduction and leaf
renewal with stores; check committed winners, node/tip ownership and leaf wear.
Record every plant's birth/death, shortage flags, first actions, body size, root
cells, foliage, quarter-day snapshots and daily/first-night resource totals.

Compare all observed births/deaths and available startup hashes to both saved
192-day ledgers, censoring later events. IDs can be matched across controllers
only for identical reset founders, not their divergent descendants.

Capture unchanged native-renderer frames at days 0.25 (first sunset), 0.75
(first dawn), 2 and 8, in original/N/W order. Independently repeat each replay
and framebuffer; require replay state hashes/census to match the traced world.
The fixed budget is **six traces plus 24 frame replays = 30 native calls**, no
training/mutation calls. Verification and reanalysis run offline.

## Interpretation and stopping rule

Keep terminal-step income explicitly unaccounted: ordinary death clears stores
and income telemetry. Distinguish energy versus water shortage flags at death,
and observe preceding stress/resources rather than inventing the final debit.
Separate proposed bids, committed decisions, successful extensions and seed
production. Living absence can recover from the seed bank. Trace accounting is
not a counterfactual estimate of preventing a cost or changing a decision.

Report all three trajectories, exact reproducibility checks, native frames,
and remaining uncertainty. Stop after diagnosing startup and proposing the next
bounded test; do not retune policies, change ecology/fitness, select a new model,
train, deploy, commit, or push as part of this diagnostic.
