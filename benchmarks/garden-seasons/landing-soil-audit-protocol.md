# Reconstruct the soil supply during the saved drying interval

Status: **FROZEN before analysis**. Follow the
[passive drying capture](landing-drydown.md) with saved-data accounting only.

## Inputs and scope

Pin `landing-drydown-results.json.gz` at SHA-256
`2107de1ed88bef2ef66d8b168f4fd8d3338329b02c8dc8aff5b919aa487a6a29`.
Keep all four cases, both allocation arms and their archived repeat/neutrality
checks. Reuse the existing 626520–629760 observations; no new native calls,
training, policy changes, firmware builds or flashes. Do not extend the window
or add counterfactual ecological runs in this audit.

Read the exact C implementation retained with the capture. Preserve the
original native capture metadata and relevant source files in the portable
audit, with hashes verified against the pinned native archive. Keep these
historical implementation receipts distinct from the new Python analysis.

## Reconstruction before attribution

There are 216 adjacent transitions per arm, 1728 in total. Begin each at the
recorded post-uptake soil grid and predict the next pre-uptake grid. Independently
implement the existing unsigned weather calculation, seasonal drought gate,
saturating surface rainfall, in-place downward flow, alternating lateral pairs
and surface evaporation. Preserve exact integer thresholds, limits and stage
order. Require exact agreement at all 308 cells, or stop without attributing
the residual to an unobserved process.

Check the supported conditions explicitly: no gardener, manual/recurring
irrigation or bottom drainage; no germinations within this interval. Germination
would consume surface water after the observer, so this audit must reject such
a history rather than silently treating its post-uptake grid as end-of-step
soil. Cross-check each recorded adult soil total against the post-uptake grid.
No first transition into 626520 is available; do not invent one.

## Accounts and retained evidence

Retain stage totals, all-cell water accounts and every attempted boundary edge
touching the target footprint, including zero transfers and the actual source
and destination water values at that stage. Compare per-edge and per-stage
control/candidate changes without selecting only negative examples.

Report both the whole observed interval after its first uptake and the interval
after the existing shared-capacity anchors: daylight 626580, dawn 626520. For
the latter, start at the anchor's post-uptake soil, so the first following soil
update is included. Reconcile incoming rain/flow, outgoing flow, evaporation,
actual root collection, overflow and closing soil with the already verified
40/23-unit retained-water differences.

For context retain fixed Manhattan-distance regions of radius 0, 1, 2 and 4
around the unchanged target endpoints, with all consumers. Also retain soil
water by depth at the common anchor and window endpoint, distinguishing water
below the deepest root from water in reachable rows. Depth alone is not proof
that every cell within those rows is accessible.

Reconstruct observed transfers, not plant-removal or altered-physics rescues.
A difference in lateral inflow identifies its immediate edge and gradient;
it does not establish which earlier plant or event created that gradient.
Separate inherited soil differences from within-window transfers. Identical
fixed/rotating observations remain duplicates, not independent replications.
Do not recommend a mechanics change until this account and its limits are
reviewed. If earlier history is required, propose it separately.
