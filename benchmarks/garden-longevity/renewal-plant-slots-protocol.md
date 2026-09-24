# Plant admission: fixed eight-versus-sixteen host comparison

Protocol fixed before native outcome capture. Follow the
[allocation audit](renewal-allocation-blockers.md), using the saved fractional
canopy arm as control. Test whether removing the eight-plant admission ceiling
allows durable descendant reproduction, or merely transfers pressure elsewhere.

## Single intervention

The host-only experimental build has storage for 16 plants. Both arms retain
an effective admission limit of **8 through tick 69,120 inclusive**. Only the
`sixteen` arm changes that limit to 16 afterward; the first ecology update that
can use it is 69,135. Both direct planting and germination/site queries use the
same limit. The control remains eight throughout. Dead plants still occupy
slots until normal decomposition. No eviction, slot reservation or allocation
priority change. Grow diagnostic buffers to preserve complete observations;
this does not change guard decisions. Configuration is per world, reset off,
excluded from the physical hash and explicitly recorded in candidate metadata.

Keep **512 nodes**, **8 seeds**, fractional canopy transmission, wet germination,
two-column establishment spacing, rotating seed purchases, all costs, guards,
controllers, weather, timing and export boundaries unchanged. With 28 columns
and two-column spacing, 16 storage slots need not mean 16 simultaneous living
plants. Do not reduce spacing to fill the array.

## Frozen comparison and receipts

- Parent `artifacts/garden-renewal-canopy-transmission-v1`, manifest SHA-256
  `ea243a36dccd49eda1db5cbfc30956ebf281e81013fec5a4adc8e69bc7212b69`.
- Parent portable summary SHA-256
  `ad7c804d94fb9ac687a7d0c5175982579ba2b118336f425b1316fb3a857ccc60`.
- Allocation audit SHA-256
  `e7c591c0b094c94e788ae9ca91992bbd6f1214123353dd0f38d64c5e7ca7ef37`.
- Use the parent's **transmission** arm, `rainfed-crowded` seed `0d983a80`,
  N background/descendants and W founder 5, unchanged model bytes and routing.
- Stop at 245,760 (64 garden days), closing window `(184320,245760]`.
- Exactly **20 research native calls**: ecology and site traces in both arms,
  each repeated; native frames at 69,120, 72,960 and 245,760, each repeated.
  Six predetermined images, including unsuccessful outcomes. Tests are separate.
- Rebuilt control traces, frame JSON and pixels must reproduce the parent's
  transmission arm byte-for-byte before candidate capture. Both arms' physical
  prefixes and boundary pixels must agree through 69,120. Only new admission
  metadata may differ. First physical divergence may be later than activation.
- Freeze source/binary/build/model/protocol inputs; whitelist native changes to
  admission/storage, associated diagnostics, CLI metadata and targeted tests.
  Generalize analysis capacity bounds with an explicit validated rule, default
  eight for historical traces. Reconcile all old control-derived results.

## Evaluation fixed in advance

Count post-boundary births, full-day eligibility and survivors, new full-day
parents with full-day-surviving children, endpoint survivors, natural deaths,
closing-window renewal, incumbent losses and endpoint species/founder families.
Do not identify corresponding post-split plants using their numeric IDs.

A positive selected-world signal needs **more than two new full-day survivors**,
**at least one new full-day parent with a full-day-surviving child**, no more
than **one incumbent death**, and no fewer endpoint species or families than
control (two species, three families). This is not broader-environment
qualification or authorization to promote defaults, even if every gate passes.

Report peak/endpoint node and plant use; actual-limit and old-eight-limit
occupancy separately; retained mature seed masks and seed lifetimes; resource
budgets/stress and cause of death; founder flower 5's history and new children's
budgets/light. Distinguish correlated post-step masks from actual in-loop
rejections. Never infer unseen terminal-step budgets. Look explicitly for a
shift to node, moisture, spacing or maintenance pressure.

## Validation and stop

Strict warnings/UBSan, parser/dependency/firmware rejection, reset and per-world
isolation, exact boundary, both capacity gates, full/one-past bounds, node limit,
unchanged seed bank, failure preservation and expanded diagnostic coverage.
Normal build scripts explicitly disable the option. Run default and experimental
regressions, repeated analysis, independent Docker portable verification and
review all six images. If analysis fails after capture, repair offline without
new simulations or replacing observations. Stop uncommitted, document the result
and issue #30 progress, then discuss the next step. No sweep, training, firmware
flash, horizon extension, default promotion, commit or push.
