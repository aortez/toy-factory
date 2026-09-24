# One-neighbor controller swaps: fixed protocol

Accepted after the [reciprocal swap](renewal-swap.md), before collecting any new
outcomes. Keep observed founder shrub **2** on N. Starting from the same reset,
switch exactly one of the other four founders to W; all other plants and all
descendants remain N. No controller inheritance is introduced.

| New case | Only founder switched to W | Reset column |
|---|---|---:|
| neighbor-1-w | 1: left flower | 3 |
| neighbor-3-w | 3: ground-cover | 13 |
| neighbor-4-w | 4: right shrub | 18 |
| neighbor-5-w | 5: right flower | 23 |

Freeze existing models N `01b9d94a` and W `c9ea07fd`, world `0d983a80`, schedule
`05d87ca0`, eight garden days / 30,720 logic ticks, and the complete existing
512-node, eight-plant/eight-seed rainfed-crowded environment: wide dispersal,
headroom uptake, selective leaf maintenance, night-growth veto, no drainage or
gardener. The first scheduled patch is day 16, beyond this horizon.

## Reuse, budget and verification

Pin the prior bundle manifest SHA-256
`9f2be4fb09b00d2464273b5a53c20c478de8e39a1e060a2c68e51684a6b4d9dd`.
Reuse its native inspector, screenshot replayer, model bytes and build/source
snapshots verbatim. The existing founder router already supports these IDs;
there is no native rebuild or change to simulation, firmware or arbitration.
Check the current native source hashes against that snapshot.

Copy its complete N/N and N/W traces/repeats and frame results/bytes as fixed
references. Do not rerun or count them as new worlds. N/N is the matched control
for each individual intervention. N/W changes every nonfocal plant, including
descendants, to W; it is a contextual reference, **not** the exact all-four-
founder factorial endpoint with N descendants and not an additive prediction.

Each new case receives two full ecology traces and independent, repeated native
screenshots at ticks 960, 2,880, 7,680 and 30,720 (days 0.25, 0.75, 2 and 8).
Exactly **eight new traces + 32 new frame replays = 40 native calls**. Retain all
four cases regardless of outcomes. No extra seeds, extended horizons, combined
neighbor swaps, training, mutations, resource rescues or on-device work.

Seal input/source hashes, commands, timings and raw captures before analysis.
Do not overwrite failed outputs or automatically rerun simulation if analysis
fails. Verify full-trace repeats, each bid's controller CRC and reset identity,
no inherited routing, unchanged weather/rules, every recorded live resource and
leaf budget, node/tip ownership and winning decisions. Keep death-step resource
income explicitly unreconstructed because the engine clears it. Independent
frame replays must match traced states and repeat byte-for-byte. Copied reference
analysis must reproduce the old saved summary. Export all cases and references,
plus the native contact sheet, for manual review.

## Predeclared diagnostics

The measured focal plant is always shrub 2, not the neighbor being switched.
Record its survival, first shortages and stress, first/second-sunset body and
resources, maintenance cost, full resource windows, seed-purchase timing,
germinated offspring, and the day-eight whole-garden census. Keep founders
matched by stable identity; do not pair descendant IDs across worlds.

For each new case and the N/W reference against N/N, record the first focal
resource/body differences, changed seed spending, different physical winning
tips, and tied-winner differences. Separately flag steps whose **complete
recorded bid multisets** match after removing only global tip indices and the
declared routing CRC, but whose physical tie winner differs. A changed input,
priority, candidate record or action must not be mislabeled as pure reordering.
The trace does not expose every neural input, recurrent-memory proposal or
candidate preference; equal recorded bids do not establish identical hidden
state or prove that changing tie-breaking would rescue the plant.

## Interpretation and stopping

An individual neighbor swap that kills the focal plant is sufficient in this
selected reset, with ordinary feedback allowed. If none does, retain that result:
multiple changed neighbors or later descendants may be required. A surviving
swap can still change reproductive timing or diversity. Neither outcome proves
cooperation, physical shading as the sole mechanism, general controller ranking,
or broader environment qualification.

Report the four results, saved references, audit limitations and next bounded
proposal. Stop before changing ecology/fitness/arbitration, training, deployment,
committing or pushing. Continue using issue #30 for progress notes.
