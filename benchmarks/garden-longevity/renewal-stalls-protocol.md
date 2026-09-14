# Renewal-stall case study: fixed timeline and visual review

Investigate the two broad-final zero-renewal cases against the original on the
same worlds. This is an outcome-selected diagnostic, not a new evaluation panel,
fitness change, intervention, model selection or training run. No firmware or
device changes; no commit/push. Reuse existing host replay/inspection binaries.

## Fixed cases and evidence

Coverage manifest SHA-256:
`a9142bff1570b3912b7f7d5dc71dbf4575c3db6df10249cf9b3539643abaf460`.
Four trajectories: original `dc5e849d` and broad final `c7c1b31e`, world seeds
`1824c139` and `4d5f9ee1`, fresh-2 disturbance seed `17c29444` only. Copy the
original ledgers, models, frozen replayer, source/config fingerprints and this
protocol into a fresh bundle after full verification. The existing population
inspector is pinned separately; verify matching source/config and native hashes.

The weak main interval remains (62,94] days; bounded credit and survival rules
are unchanged. Compare seed-purchase funnels in **(30,62], (62,94], (94,126]**,
each with its own two-day follow-up. Classify seed parents as founders,
established descendants, or not-yet-established descendants at purchase. Report
germination, expiry, full-cycle survival and qualification separately: lack of
qualifying grandchildren is not the same as no births or extinction.

Create daily lifetime censuses from day 30 through 126 and explicit offspring
confirmation records in those intervals, with ancestry and death cause. Report
first qualifying confirmation and first live qualifying credit after the gap
using only the original bounded day-192 history. If none is observed, say so;
do not extend the horizon. Attribute gap score to the unchanged candidate rule.

## Native evidence, no intervention

Capture all four trajectories at **days 62, 78, 94 and 110** (start, middle, end,
later). These give 16 native images, each independently reset/replayed once
with exact output/frame equality (32 replay calls). Run four additional headless
day-192 replays to match the saved full endpoint hashes and counts.

Run one existing `--population` inspector per trajectory through day 192, with
no policy overrides, bids, every-ecology trace or added mutation. Four census
calls make the native budget **40 processes: 36 replay + four inspector**.
Require the final world sample at every repeated tick (post-disturbance) to agree
with the original lifetime/seed ledger counts and living IDs. Match every image's
world hash to its same-tick census and the day-192 replay to the original saved
checkpoint. Inspector resource snapshots are observations, not causal interventions.
If any identity, count or hash differs, stop rather than explain divergent runs.

Native rendering must not mutate the world; use the existing separate process
and production framebuffer path. No generated/fabricated simulation pictures.
Keep all selected images, including unchanged/uninteresting frames. No best-frame
selection. Publish a labeled gallery identifying original versus broad, seed,
day, model, world hash and framebuffer CRC.

## Analysis and interpretation

Locate the stall along the chain: descendant availability → paid seeds →
germination → full-day confirmation → qualifying multigenerational renewal.
Use sampled plant structures/resources and seed blockers to explain observed
bottlenecks only to the resolution justified. Do not infer continuous water/light
causes from sparse samples or label zero credit as extinction. Do not count
future offspring outcomes before their applicable follow-up deadline.

Preserve original scores/ledgers. Test funnel ancestry, exact confirmation/death
boundaries, end-specific follow-up, recovery credit, census checks and complete
fixed panels. Deterministically reanalyze saved evidence and verify all artifact
hashes before marking the bundle complete. Source and input files must remain
unchanged during collection. Portable export follows collection; raw census,
framebuffer repeats and full lifetime inputs remain in the local bundle.

Stop after explaining these four selected trajectories and discussing whether
the observed stalls justify a reliability requirement. No new scoring gate,
ecology adjustment, training trial or additional outcome-selected replay sweep
is automatically authorized by this diagnostic.
