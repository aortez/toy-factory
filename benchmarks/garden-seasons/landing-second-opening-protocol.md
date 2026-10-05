# Second controlled opening: day 288 to day 320

Frozen before treatment runs. Host-only mechanism test; no training, device
defaults, capacity changes, mortality changes, or promotion decision.

## Question

After the first controlled death allowed one recruit in each of five selected
worlds, does another opening let those recruits establish the next generation?
Compare each saved first-death history continuing unchanged with the same history
receiving a second named death. A germination is not yet establishment; report
one-, sixteen-, and thirty-two-day survival separately, including censoring.

All five histories share one weather seed and model. They are paired selected
histories, not five independent weather replicates. The older 12/16 harm-screen
failures remain unresolved; success here cannot promote the research settings.

## Frozen inputs and targets

Input capture: `landing-disturbance-capture.json.gz`, SHA-256
`8677447bbb1609522e48c25a425a17e0dbbb9efa5c133810b1a72a8204750e39`.
Its raw manifest is
`0726b1cf464c09e0d835aa2e888a10e8e1ff38d959ec5a7b17b7186b1206d712`.
Input audit: `landing-disturbance-results.json.gz`, SHA-256
`0cd9571fa218c7c511db98572c15a56d3982ea66129b748c4919302c614f66d2`.
Keep the same model bytes, seed `f7ee4528`, guard/allocator/order settings,
32-node per-plant cap, uptake limit, dispersal and wicking variants.

Select the oldest living non-focal plant at the saved day-288 endpoint, breaking
birth-time ties by lineage ID. The first recruits are not excluded by rule; the
older incumbents below win. Do not retarget based on future outcomes.

| World (order/guard/allocator/arm) | Original focal IDs | First death at 256 | First recruit | Second death at 288 (column) |
| --- | --- | --- | --- | --- |
| W1 fixed/candidate/candidate/wide-cap-wick | 30 | 17 | 31 | 20 (3) |
| W2 fixed/candidate/control/wide-cap | 33, 34 | 17 | 35 | 19 (18) |
| W3 rotating/candidate/candidate/wide-cap | 33 | 20 | 34 | 26 (12) |
| W4 rotating/candidate/control/wide-cap | 33, 34 | 17 | 35 | 19 (18) |
| W5 rotating/control/candidate/wide-cap-wick | 30 | 18 | 31 | 19 (13) |

One day is 3,840 logic ticks, one ecology step is 15. Retain the first death at
983,040. The second death is at 1,105,920, **after** that tick's ordinary
simulation and observations. Observe the interval (1,105,920, 1,228,800], with a
pre-event anchor at 1,105,920. Both deaths leave their bodies for normal
decomposition, preserve the seed bank/soil/RNG, and are labeled environmental,
not starvation or export. No gardener, irrigation, forced germination or reset.

## Calls and identity gates

Exactly 25 complete native replays, at most four concurrent, no parameter search:

1. Five day-288 baselines under the new binary, with only the original death.
   All results, frames and four traces must equal the saved treatment byte for
   byte before any later phase starts.
2. Five controls to day 320 with the first death only.
3. Five treatments to day 320 with both deaths.
4. Five exact treatment repeats, including all observations.
5. Five untraced treatments for observer neutrality; keep every policy flag and
   framebuffer capture, removing only observation flags/window arguments.

Retain stand, adult-resource and direction traces from day 256 through the
endpoint, plus full reach traces. Compare all common raw observation rows through
day 288 against the validated baseline (excluding horizon-dependent headers and
footers). Final repeats must match results, images and all four traces; untraced
runs must match results and images. The second event's pre-death world/core-run
hashes must equal the saved day-288 endpoint. Undoing only that explicit death
and future ledger fates/counts must reconstruct the saved day-288 ledger.

Keep the old single-event JSON/hash identity unchanged. Two-event runs have a
distinct kind and second probe; nest the existing `GLT1` run-hash wrapper in
chronological order, retaining the underlying placement hash. Reject incomplete,
duplicate, out-of-order, same-lineage and out-of-horizon event arguments. Applying
an invalid event must leave the world, lifetime ledger and event receipt intact.

Capture source archive, runtime and analysis hashes, build settings/binaries,
model, protocol, commands, results, raw/compressed traces and final frames. Only
the host CLI, event printer, environmental ledger export and their native test
may differ from the first capture's runtime. No core simulation change is needed.
Use fresh outputs and refuse an existing path before launching a native process.

## Complete paired accounting

Keep every post-boundary observation, not just successful recruits or seed
producers. Reconcile lineage/seed ledgers, body inventory, ordered reproduction,
seed-slot residence, all germination masks and complete resource conservation.
Verify climate, timestamps, missing/duplicate samples, purchase costs and resource
debits independently. Include the anchor to detect a discontinuity across the
imposed death; report its discarded stores separately from natural maintenance.

Report for each arm/world:

- Original seven focal plants and all five first recruits: survival, morphology,
  resource shortfalls, reproduction eligibility, bank access, seed production,
  seed fates, children with survival windows, and grandchildren.
- All seeds present at day 288, including the two first-recruit seeds, plus all
  later purchases. Distinguish a surviving pending seed from a confirmed failure
  or offspring. Attribute refills by parent and pre-/post-boundary purchase.
- Second death, body reclamation, temporary global slot availability, newly clear
  columns, first germination and its delay. A refill elsewhere is not evidence
  that the killed plant's exact column became suitable.
- New natural mortality (excluding both imposed deaths), final living/stored
  plants, nodes and seed count. Compare maintenance payments and unpaid resources
  for matched pre-event survivors, excluding the second victim and post-event
  numeric IDs, whose ancestry may diverge between arms.

Produce a paired day-320 contact sheet for manual review. Recompute the portable
analysis offline, then re-extract it byte-identically from authenticated raw
traces with process launches disabled. Negative tests must reject changed
boundaries, event identities, incomplete samples and derived results.

If refills are unrelated to the first recruits, distinguish placement/light/
spacing/capacity from reproduction or survival using the retained observations.
Do not add a third event or relax a capacity to manufacture a generation in this
test. The result determines the next proposal, not an automatic further sweep.
