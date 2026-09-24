# Dark spending guard: fixed host-only paired experiment

Implement the [exact dark budget](renewal-dark-budget.md) as one experimental
guard, then measure actual ecological feedback. This is a selected-world
diagnostic, not held-out qualification, training, fitness adoption or firmware
promotion. Protocol fixed before collection; no alternative thresholds or worlds
will be selected after seeing outcomes.

## One rule

After current income/maintenance, consider each otherwise affordable expense in
native order: leaf renewal or the winning growth/finish decision, then seed
production. Predict that expense's post-debit energy and future energy upkeep;
an extension adds a node only if its proposed execution can actually append one.
FINISH or a blocked extension still costs energy but adds no node.

Project the existing energy/stress mechanics only through the immediately
following guaranteed zero-income interval. The first potentially productive
step is excluded. Deny the expense iff that post-expense budget predicts stress
eight before light could next pay income, assuming adequate water and no further
expenses. Keep transient shortages that stop below eight. Leave out-of-scope
daylight and zero-payment cases unchanged; do not replace ordinary affordability,
cooldown, capacity, flowering or daylight rules. No safety factor is fitted.

Re-evaluate each subsequent expense, including later stages in the same step.
Record both pre/post budgets to distinguish newly fatal expenses from already
fatal starting states. A rejection is not a claim of rescue: future actions and
competition can change. Water shortage and delayed actual morning income remain
outside this guard's guarantee.

Growth rejection occurs after normal winner selection, without reranking. It
does not commit memory/RNG, tip scheduling, topology, expense or a growth decision;
the normal later reproduction stage still runs. Renewal rejection preserves the
leaf, stores and proposed memory, and allows the ordinary growth fallback.
Seed rejection preserves stores, flower eligibility, seed bank and RNG; the
ordinary cooldown decrement has already happened. Existing age, uptake,
maintenance and environmental updates are never rolled back.

Add a host-only compile option OFF by default, forbidden in Zephyr and mutually
exclusive with the old seed reserve/focal quota/drainage/large seed bank. Keep
diagnostic event records bounded and outside the authoritative state hash. Unit
tests must verify rejection atomicity and matching OFF behavior. Default host
automation must explicitly reset the new option OFF.

## Frozen panel and execution budget

Use the ordinary control from `artifacts/garden-renewal-seed-veto-v1`, manifest
SHA-256 `dd44e765e15d4be5ed0c5c99273699718358ac8e5790af838162121620bcb5ae`.
Pin the preceding dark-budget summary SHA-256
`73e02cc1c4a3455dd50d1ef56f36d37fc2ef1844cc1ed01268f122cdff1549f7`.

- Two arms only: rebuilt **ordinary control** and **dark guard**. No focal quota
  in either arm. All other configuration and frozen source are identical.
- Same world `0d983a80`, patch seed `05d87ca0`, rainfed-crowded setup, automatic
  gardener off, wide dispersal, storage-headroom water uptake, 512 nodes, eight
  plants/eight seeds, leaf maintenance and selective renewal, no-night-growth
  policy. Patch events begin at day 16, beyond this eight-day trial.
- Background/descendants use N `01b9d94a`; only founder 5 uses W `c9ea07fd`.
  Never substitute fresh models or train/mutate controllers.
- Stop at **30,720 logic ticks / eight Garden days**. Capture every ecology
  step and all bids/guard events, with exact independent repeats in both arms:
  **four trace calls**.
- Capture independent native framebuffers at ticks **4,800, 6,720, 7,680,
  30,720**, repeated in both arms: **16 replay calls**. Total **20 experimental
  native calls**; native unit/regression tests are separate validation.
- Rebuilt control must match all 16,775 saved control records and all four saved
  frames. With diagnostic metadata removed, first divergence is expected at
  tick **945**, founder 5's growth expense, as identified in the fixed audit.
  An earlier divergence or inconsistent guard projection blocks interpretation.

## Evidence and analysis

Freeze source, build settings, binaries, models, protocol and commands before
collection. Never overwrite old bundles or silently rerun a failed capture.
Record allowed, rejected and out-of-scope candidates with expense kind, selected
node, current stores/body/stress, prospective node count and both forecasts.
Verify all native forecasts against the existing independent Python dark-budget
reference. Audit original bid groups and rejected winners before removing only
uncommitted growth bids for the existing resource/tip reconciler; preserve raw
traces and a reproducible derived accounting trace.

Compare founder and descendant survival, death causes, births, seeds bought and
expired, species representation, generation, living-plant exposure and tipless
exposure, including quarter-day checkpoints. Report counts of denials, retries,
already-fatal budgets and permitted transient shortages. Reconcile live resource,
leaf-condition and tip ledgers; terminal cleared income stays unaccounted. Verify
native screenshots against census hashes and byte-identical repeats; retain a
portable summary and contact sheet for visual review.

Success is not fewer expenses by itself. Determine whether any early survival
gain persists through day eight and supports reproduction/descendants, and
whether costs or deaths move to neighbors. Disclose the short horizon, reused
world, shared prefix, birth-identity divergence and unqualified morning/water
risks. Update issue 30 and the roadmap. No commit, push or device deployment is
included; discuss findings before expanding the panel or promoting the rule.
