# Garden research playback plan

Build an interactive host viewer for the three frozen repair policies from the
[durability comparison](../benchmarks/garden-seasons/leaf-family-durability.md).
The purpose is to watch growth, leaf replacement and family turnover under the
conditions already evaluated, including failed families. The first implementation
is now available; see the [launch guide and verification results](garden-research-player.md).
This remains a host inspection tool, not another training run or a firmware promotion.

## Preserve the research world

The ordinary [host player](host-simulator.md) owns a `toy_factory_simulator` and
advances the normal game scene. Its build script explicitly disables research
switches. Loading repair weights into that player would not reproduce the
experiment's maintenance, W2 growth, seasonal setup and family assignment.

Add a separate `host-play-research` target and executable. Prepare it from the
verified durability archive's `runtime/source` and `runtime/modules` in a fresh
ignored directory, then compile with the existing Docker host-player toolchain.
Do not execute archived binaries or modify the archived sources in place. This
also removes the new viewer's dependence on the old local v7/v8 build folders.

Keep the fixed wear controller and both learned finalists available, without
choosing a winner. Each world assigns one policy to one founder and its
descendants; other families keep the selective resident policy. W2 and its
memory, seeded seasonal rain, the two layouts, no gardener, and the day-1376
ceiling remain fixed. The initial interface selects among the four archived
weather seeds and each layout's valid founder roles.

## Separate simulation ownership from presentation

The research runtime already exposes `toy_factory_leaf_owned_open`, `step`,
`snapshot` and `close`. It privately owns a validated checkpoint and provides
independent value snapshots. Reuse this owner in a small research session adapter;
do not introduce a second implementation of repair or growth.

Move the CLI's initialization and per-tick lineage, seed and death accounting
into that adapter in a separate working copy. Both a headless test entry point
and the viewer should use it. Preserve operation order, failure propagation,
fixed capacities and canonical state encoding. A failure stops playback visibly;
it must not silently reset a family or discard a ledger entry.

Use the archived snapshot builder and software renderer, then upload the native
240-by-240 framebuffer through SDL. Rendering operates on a copied snapshot and
must leave authoritative state unchanged. One thread owns simulation and the
process-global raster buffer. Multiple simulation workers and browser playback
are outside this first step.

## First viewer controls

- Select policy, weather seed, layout and candidate founder at launch. Changing
  a condition starts a fresh run rather than replacing a policy mid-life.
- Pause/resume, reset, advance one simulation tick, and advance one Garden day.
  Label the units: one day is 3,840 logic ticks, or 64 seconds at normal speed.
- Offer normal speed and accelerated playback. Bound each work slice so pause
  and quit remain responsive; skip display frames when needed, never simulation
  ticks. Report actual progress when the host cannot achieve the requested speed.
- Save an unmodified framebuffer plus condition, model, tick and state identities
  to a fresh capture path. Do not overwrite previous captures.
- Show the policy, seed, layout, founder, day, and candidate-family living/pending
  counts outside the canonical pixels. Keep gardener input disabled. A garden
  full of resident plants must not be presented as candidate-family survival.

Start with one garden at a time. Side-by-side worlds, family highlighting,
backward seeking and resumable checkpoint files can follow if useful. Existing
canonical encodings identify state; they are not an authenticated resume format.

## Acceptance checks

1. Prepare and build from a clean checkout plus committed archives, without any
   historical `artifacts/` directory. Reject altered archive/model/source bytes,
   invalid roles and unsafe extraction paths. Leave original archives intact.
2. Match the three archived day-608 anchors and the day-1376 rainfed founder-1
   runs on weather `58d7d6ca` for all three policies, including full histories,
   canonical state and raw pixels. These are replay checks, not new selection
   or scoring conditions.
3. Run the same inputs with no intermediate rendering and with frequent
   rendering. Check exact final equality, pause/step/reset behavior and an SDL
   off-screen smoke test. Speed controls must not change results at a given tick.
4. Run the existing normal-player smoke and default-isolation checks. Confirm
   that neither `host-play` nor firmware configuration changed.

Implement preparation and the tested session adapter first, then connect the
viewer. This makes the first interactive display a faithful view of the measured
simulation rather than a visually similar new experiment.
