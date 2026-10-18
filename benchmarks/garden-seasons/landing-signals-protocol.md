# Landing signal-content probe v1

Frozen before collecting probe outcomes. This is a bounded mechanistic follow-up
to [whole-mask validation](landing-validation.md), not training, controller
selection, a new generalization test, or a device/default change.

## Fixed controllers and environment

Use all three current-only, final training-selected controllers from the pilot:
search `6d697833` / `g1-c0`, `6d697834` / `g1-c2`, `6d697835` / `g1-c1`.
Include the controller whose prior ablation improved the score. Do not select
among generations or rerun training. History-trained models are outside this
pass: the question is the four currently active signals, not history/warmup
interactions. All canonical model bytes remain unchanged in every probe.

Use the pinned pilot model archive and summary hashes from
`landing-validation-protocol.md`. Require live and all-neutral probe controls
to reproduce the previously retained validation histories in
`landing-validation-results.json.gz` (SHA-256
`091e263598ffe6cb20c668152299e71e18d203c670d024c740a2955f55e2927d`).

Reuse all 16 development conditions: seeds `25185eeb`, `d60c94c0`, `8377cb18`,
`30358096`, rainfed/rainfed-crowded, steady/seasonal. Ordinary production ecology,
256 nodes, eight plants/eight seeds, no research flags, no gardener/irrigation.
Every world runs to day 192 (737280 logic ticks); the individual bounded-renewal
objective, four late windows and follow-ups remain unchanged.

## Explicit probe semantics

Use a distinct host `probe-replay` command and probe-aware run identity. Do not
change the model mask/file, legacy observations, policy weights, real shared
cache, recurrent memory directly, ecology, RNG, or normal replay behavior.
Transform a copy of the real packet immediately before inference. Apply the
same substitution to the common landing source and all **valid** candidate
landing sources. Root, absent and out-of-bounds sources stay masked. Thus even
fully fixed probes retain the normal source-validity/body-role gating.

Two groups:

- Occupancy: `space_free`, `dead_only`.
- Resources: `water_now`, `light_now` (tested together, not separately).

All constants below are raw unsigned packet bytes, before subtracting 128.
`neutral` occupancy is (128,128), giving zero neural inputs; it is a synthetic
ablation, not a claim of a physically neutral site. `occupied` is (0,0), a live
occupied site; `open` is (255,0), a completely open site. Resource `low`, `mid`,
`high` are (0,0), (128,128), (255,255), respectively. `mid` gives zero neural
inputs; it is not an empirically measured average. Constants are prespecified,
never fitted to outcomes. History and warmup remain masked by the original
current-only model configuration.

| Probe | Occupancy | Resources |
|---|---|---|
| live | live | live |
| water-light-only | neutral | live |
| occupancy-only | live | mid |
| neutral | neutral | mid |
| occupied | occupied | live |
| open | open | live |
| low-resources | live | low |
| high-resources | live | high |
| fixed-occupied | occupied | mid |
| fixed-open | open | mid |

**Ten probes × three models × 16 conditions = 480 primary evaluations.**
This is not an exhaustive constant grid: fully fixed low/high-resource
combinations are not tested. It cannot rule out every useful constant policy.
The all-neutral probe must match the same controller's prior off-mask biological
trajectory; live must match its prior current-mask trajectory. Probe identity,
kind and model metadata may differ, but world state, ledgers and scores may not.

## Evidence, comparisons and stopping

Retain all complete lineages and seed receipts. Reuse the existing scorer after
strictly validating the explicit probe metadata. Compare each intervention to
its own live controller, both overall and by seed/layout/climate, with per-world
paired keys, endpoint tiers, zero-credit windows, and weakest-window credit.
Do not reinterpret a majority of world wins as the aggregate objective.

Repeat the complete panel with one worker, captures off, requiring identical
probe identities, results and scores. Freeze/hash the binary, source, inputs,
protocol and outputs; failures remain incomplete. Independently rerun the
frozen bundle. Sources/builds must not change during collection.

Prespecified gallery: every model/probe on seasonal seed `25185eeb`, both
layouts, **day 192** (60 images). Independently capture from reset and require
the complete final result to match its headless evaluation. Keep empty frames.
Inspect every image. This pass uses one late checkpoint, not a chosen best frame.

Fixed substitutes are out-of-distribution interventions. A loss does not prove
optimal sensing; matching/improving live behavior shows live values are not
necessary in those tested conditions, not that the information is never useful.
Retained validity gating and unchanged legacy sensing still convey information;
these are not blind controllers. Group probes do not identify water versus
light independently. Stop after this panel and report, with no automatic
training, new constants, reselection, ecological tuning or promotion.
