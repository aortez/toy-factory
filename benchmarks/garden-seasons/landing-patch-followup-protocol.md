# Spatial dieback follow up through day 352

Extend all six paired worlds from the [day 320 confirmation](landing-patch-confirmation.md)
to day 352. Resolve survival observations that were incomplete at the original
endpoint, and measure births after openings cease. This is observation of the
same deterministic histories, not a new rule, model search or training run.
The original confirmation result and its acceptance criterion remain unchanged.

## Fixed conditions and compatibility gate

Use the same W2 recipe, model bytes, three seeds and both layouts as the
[confirmation protocol](landing-patch-confirmation-protocol.md). Keep all
capacities, climate, uptake, dispersal, controller, root and construction
guards unchanged. No gardener or irrigation is introduced. The fifteen
four-column dieback events remain on days 192, 200, …, 304, with their original
victims and event hashes. There are no events after day 304.

The old executable rejects horizons beyond day 320. The only permitted runtime
source change is the host CLI limit and corresponding help text, from 320 to
352 days. Training and evaluator limits remain unchanged. Rebuild W2 with its
recorded compiler options, retaining sanitizers. Before any extended run,
replay all six controls and all six treatments at day 320. Require exact result
JSON, all three compressed traces and framebuffer bytes against the original
capture. A mismatch stops the batch and preserves the evidence.

The input is `landing-patch-confirmation-results.json.gz`, SHA256
`13a46abbfe805bb58c5895b9417c622c05067d6f9c18c31cb7447da7c4657656`.
Its raw bundle manifest is SHA256
`7e0e1babb1ead8ebcbbb17256cf7673fe18a968a87cc4fb849244957c1f72b6c`.
The frozen model is SHA256
`f2dc989380339614dc512f64f11f2bf03f7079c465c4c9bd18895044ec3e1567`.

## Calls and retained observations

Exactly 36 research calls, at most two concurrently:

1. Six day 320 controls, then six day 320 treatments, as compatibility gates.
2. Six day 352 controls and six day 352 treatments.
3. Six exact traced treatment repeats at day 352.
4. Six observer-free treatment repeats at day 352.

The extension changes only `--ticks`, `--stand-stop` and `--adult-stop` in
the original arguments. The stand and adult traces still begin on day 192;
the reach trace still begins at the first ecology step. Every observation row
through day 320 must be byte-identical to its authenticated earlier trace.
The extension's complete event/seed ledger prefix must match that earlier
result. Require repeat equality of results, traces and pixels, and plain-run
equality of results and pixels. Retain every endpoint frame; the review gallery
contains all six control/treatment pairs at day 352 in the original order.

Save source snapshots, compiler configuration, executable, model, arguments,
results, trace hashes and completion receipts. Keep traces compressed only
after verifying decompression against their raw SHA256 and persisting the
restoration metadata. The new bundle manifest intentionally lists gzip files,
not removed temporary raw files. Do not alter historical bundles or collectors.
Use fresh output paths; no automatic overwrite, retry or resume.

## Outcomes and limits

First, retain the fixed cohort born strictly after day 192 and no later than
day 320. Reclassify its 1, 16 and 32 day survival at day 352, separating
confirmed survival, imposed death, natural death and censoring. All those
births now have 32 days of potential follow-up. Report how many previously
censored observations become survival versus death; do not drop failures or
silently add later births to this denominator.

Second, report established parent–child pairs and ancestry depth for that
fixed cohort and for the expanded cohort through day 352. Both plants must
individually survive 16 days to qualify; the parent need not be alive when
its seed germinates. Retain imposed failures even when later descendants
survive. Report new births, natural deaths, seed purchases and seed fates
after day 320, endpoint species, and daily living/stored/seed counts.

Display birth counts in six consecutive eight-day windows ending on days
312, 320, 328, 336, 344 and 352. These intervals are open on the left and
closed on the right. They distinguish the immediate aftermath of the last
sweep from the added observation period. Censor late new births appropriately.

This follow-up checks population and seed census against every tail stand
observation. It does not make a new resource-budget comparison; the original
confirmation retains the full day 192 to 320 resource accounting. Survival
and continuing births are descriptive outcomes, not a new promotion gate.
No sustained-evolution, species-diversity or training-readiness claim follows
from a positive result alone. An empty population, a species loss, or cessation
of births is retained and reported rather than retuned away.
