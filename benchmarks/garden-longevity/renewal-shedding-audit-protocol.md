# Saved-trace shedding feasibility audit

Freeze before computing results. This is a read-only design audit, not a new
pruning policy, counterfactual replay or environment qualification.

## Evidence and scope

- Parent `artifacts/garden-renewal-full-pool-v1`, manifest SHA-256
  `c35c3ab8ec8479312e6bf2b14a9a78867a536b72693a5ce492cc6d64bd03a97a`.
- Portable parent SHA-256
  `4a99f3776ba5ac5fae4bdd45ac60f5ca8e5109224c9035c07dcc0ad28621c873`.
- Both saved arms, unchanged 512 nodes, eight seeds and sixteen-slot admission.
- Audit every ecology checkpoint after 69,120 through 245,760; separately
  report the closing `(184320,245760]` window and endpoint. One day is 3,840
  logic ticks, ecology interval 15. Do not extend the horizon.
- **Zero new native research calls**, training, captures or screenshots. Reuse
  parent observations and verify all historical derived results/images.
- No C/header, model, ecology, capacity, firmware or default changes. New offline
  audit/tests, one exact CMake test registration and documentation only.

## Questions and limits

1. Count living leaf nodes at condition zero, separately from roots, other
   shoots, dead ownership and free slots. `active_leaves` is maturity, not
   condition or productivity. Do not sum leaf/flower/tip flags as separate nodes.
2. A zero-condition leaf has zero direct photosynthesis/shade under the current
   formula, but might be internal structure, a growth site or a flower and may
   later renew. It is not automatically removable or biologically dead.
3. Use the inspected append-only living leaf order to track `(lineage, leaf
   ordinal)`, never a raw node index across compaction. Validate conditions
   position-by-position against wear/renewal and appended leaves. Track zero
   spells, exits by renewal versus owner death, endpoint censoring, and an
   observed-zero-for-at-least-one-day subset. That day is a fixed diagnostic
   interval, not a proposed shedding threshold. Death steps are not live income
   observations. Never infer persistence from repeated aggregate counts.
4. At each post-step census, report a deliberately optimistic bound: removing
   all living zero-condition leaf nodes, regardless of unknown topology and
   retained roles. Also report the one-day subset. Safe lower bound remains
   zero; an upper bound is not a pruning opportunity or a rescued birth.
5. Compare the bound to four-node seedling headroom and quantized per-owner
   upkeep `(nodes+7)//8`, `(shoots+7)//8`. Sum per-owner savings, not rounded
   global counts. Report instantaneous price differences only, not inferred
   paid/survival gains. Post-step fullness is not an earlier rejection receipt.
6. Describe exactly which parent/child, node-role, policy-reference and
   productivity information is absent. Document the native compaction/ownership
   invariants needed for a later terminal-node operation. No greedy simulated
   deletion, automatic stem contraction, root removal or forced regrowth.

## Verification and stop

Parent/native/source receipts intact; parent reanalysis exact; new analysis
repeats identically and verifies independently in Docker. Synthetic tests cover
zero versus immature/night/shade, append order, renewal/death/censoring, one-day
boundary, quantization, per-owner rounding, missing/duplicate records and wrong
metadata. Run default/experimental regression suites. Preserve prior evidence
and strict verifiers; record the exact allowed audit registration separately.

Update report, roadmap and issue #30 with bounds and limitations. Recommend a
bounded topology census only if exact eligible storage cannot be identified
from saved data; do not implement shedding on the basis of an optimistic bound.
Stop uncommitted/unpushed, without native research execution or device changes.
