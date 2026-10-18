# Attribute the cursor adult winter income loss

This bounded diagnostic follows the [offline energy diagnosis](landing-cursor-energy.md).
It asks whether the new neighbor, plant 39, accounts for adult 37's missing
income in S2 ordinary (`366928c6-rainfed`). It does not change an ecology rule,
controller, capacity, seed allocation or acceptance gate.

## Frozen comparison

Use the exact executable, model, build settings and runtime sources retained
in `artifacts/garden-landing-seed-cursor-v1`. The input capture SHA-256 is
`cf6ba820eee40259fcaededb7188708517a8b282541ac78ff4b292f68d43af8a`.
The energy diagnosis SHA-256 is
`60d9d2d2a581cd1fd10183935eb21d1c549c077dbb8f9bf3ebbc0676b324664c`.

Run exactly two replays through day 384: fixed reproduction order and the
purchase-driven cursor. Copy each original command, remove the redundant adult
and reach traces, narrow stand bounds to the enclosing observation interval,
and add the existing passive uptake observer. No other argument changes.
Both complete results and framebuffer bytes must match their original runs.
Compare the overlapping stand rows exactly, not just endpoint hashes.
Preserve failed calls rather than retrying or expanding the panel silently.

## Observation windows

Windows are inclusive, at 15-logic-tick ecology steps, identical in both arms.

| Window | First tick | Last tick | Samples per arm | Purpose |
| --- | ---: | ---: | ---: | --- |
| Establishment | 1263045 | 1267200 | 278 | From one step before neighbor birth to day 330 |
| Winter | 1463640 | 1470015 | 426 | Last shared full-energy uptake through the first fixed-arm income after the death |

For the terminal energy account, use **(1463640,1470000]** in both arms,
excluding the starting sample and the post-death sample. This is the previously
identified 424-sample interval with income 172 versus 142. Do not select new
windows after examining shadow attribution.

## Analysis and interpretation

Reconstruct every recorded light grid independently from shade sources and
the sun ray. Reconcile each leaf's light and integer `light / 64` income, and
the focal total against the original resource history. Check stable leaf
coordinates and whether removing plant 39 leaves the same shade sources as
fixed order, through the focal death's pre-maintenance uptake.

On each recorded cursor state, remove **only plant 39's shade sources** and
recompute light and focal income. Keep all other leaves, bodies, weather and
water unchanged. Report actual fixed/cursor income, same-state income without
39's shade, residual differences, affected leaves and tick/phase ranges.
Account for saturation by rebuilding the shade grid from retained sources,
not subtracting opacity from an already clamped grid.

If this reconstructs the 30-unit gap, it establishes the local shadow mechanism.
It does not demonstrate long-run survival under a changed world, justify a new
protection rule or retroactively pass the original harm gate. Report any residual
instead of attributing all changed income to the new neighbor by assumption.

## Retention and checks

Use a fresh bundle, at most two concurrent replays and no training. Keep the
frozen executable, model, source archive, protocol, commands, results, endpoint
frames and compressed traces. Remove only newly generated raw duplicates after
lossless compression and durable receipts. Existing evidence stays untouched.
Retain a portable diagnosis with enough leaf/source evidence to repeat the light
calculation, plus tests for ray rounding, saturation, quantization, missing
samples and altered evidence. Full verification must work without native calls.
