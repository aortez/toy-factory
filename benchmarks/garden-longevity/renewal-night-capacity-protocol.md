# Full-night body-capacity shadow audit — scope and limits

Offline follow-up to the recruitment audit. Prior reports and the native rules
have been inspected: this is explanatory reuse, not blinded validation. Freeze
this specification before computing the new aggregate results.

## Inputs and scope

- Main panel: all 16 trajectories in `artifacts/garden-renewal-dark-panel-v1`,
  manifest SHA-256
  `d62a870fea9ecfede3a32cebe1465097c0391f53a0cf781358574fc2db2e4ae8`.
  Keep four world seeds, two conditions and two arms separate. Conditions share
  prefixes; these are not 16 independent worlds.
- Supplemental case study: only `finish-retry` from
  `artifacts/garden-renewal-finish-retry-v1`, manifest SHA-256
  `7e3fd0628912287cdd36954d3f9b38e7471d012f1df31b87cfacde009d044d45`.
  Do not pool it with the panel or count its unchanged references again.
- Re-verify both complete frozen bundles, including source/capture provenance,
  resource/tip/guard accounting, patch boundaries and saved frames. Check current
  native sources against the retry archive; the older panel has its own frozen
  source revision. No new experimental native calls, screenshots, training,
  runtime rules, firmware deployment, commit or push. Regression tests are allowed.

## Fixed advisory predicate

Use the existing exact dark-budget reference at canonical tick 795 / phase 117,
starting from energy **256**, stress **0**, a fixed proposed body, adequate water,
no optional spending and no income. Phases 118–255 and 0–10 are guaranteed to
pay no energy: 149 ecology steps, including 37 maintenance payments. The first
possibly productive step is excluded; do not assume any morning earnings.

Upkeep is `ceil(nodes / 8)`; the eighth unpaid maintenance is fatal. Independently
cross-check all legal node counts against the closed-form minimum reserve
`upkeep * (37 - 7)`. This predicts a structural boundary at 64/65 nodes, rather
than selecting a ceiling from the observed deaths. It is a necessary energy
capacity check for an intact body facing a complete night, not a sufficient
survival test or forecast from the current phase/stores. Its classification
must not use future trace state, lineage identity, species or observed outcome.

## Coverage and outcome accounting

1. The common denominator is every **paid extension that actually adds a node**
   in each trajectory. Reconcile node deltas with committed EXTEND counters and
   guard receipts where available. FINISH and blocked EXTEND add no node and
   are excluded. Newborns begin with four nodes; patches are not extra steps.
2. Separately audit ordinary-dark-guard-denied positive-node proposals in the
   guarded arms. These receipts describe the selected eligible proposal, not
   all candidate/non-winning bids. Do not add denied proposals to the common
   paid denominator. The retry-specific forced refusals are FINISH and cannot
   enter either positive-node denominator.
3. Distinguish **newly unsafe** (safe before, unsafe after) and **already unsafe**
   extensions. Keep paid versus denied counts, per-lineage counts, first/last
   records, exact newly-unsafe paid crossings and phase distribution. Group
   denied retries by lineage/selected tip/body size with explicit counts; do not
   call repeated attempts separate rescue opportunities. Later actions on an
   unchanged trace are not a simulated response to enforcement.
4. Retain every observed lineage, first crossing, maximum body size, eventual
   natural/patch death or endpoint survival, seed production and offspring
   outcomes. At a paid crossing, record the actual remaining-dark projection
   separately from the phase-independent full-night capacity predicate.
5. Follow the first full-night anchor at or after each paid crossing. Distinguish
   death before that anchor, patch censoring, endpoint censoring, and observed
   dark-window outcomes. Retain resource/body/water/optional-spending assumption
   breaks; do not reconstruct cleared natural-terminal budgets. Include any
   flagged survivor or unflagged death, rather than only confirming examples.
6. Report natural-death coverage by prior paid crossing and last-live body
   size, separately for each condition/arm and the retry case. Explicitly revisit
   the six post-intervention first-day deaths in the retry study, without treating
   that selected set as validation. A capacity predicate intentionally does not
   solve insufficient current reserves, water failures or species retention.

## Verification and delivery

Test 64/65 and upkeep-tier edges, all 512 legal body sizes, canonical alignment,
the distinction from a short remaining night, FINISH/blocked extensions, paid
versus denied actions/retries, newborn accounting, patch/endpoint censoring and
corrupt/missing input. Require exact repeated analysis, unchanged input and
native-source hashes, and portable JSON equality. Export a concise report,
update the roadmap/experiment notes and issue 30, then discuss a next proposal.
Do not claim that flags are causal rescues or adopt a general hard cap here.
