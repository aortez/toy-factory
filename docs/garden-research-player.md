# Garden research player

Watch the fixed wear controller or either learned repair policy under the exact
research conditions used in the [durability comparison](../benchmarks/garden-seasons/leaf-family-durability.md).
This is a separate host-only viewer: ordinary `make host-play` and PicoSystem
firmware keep their existing behavior.

## Launch

```sh
make host-play-research ARGS="--policy s1-g3-c4 --speed 256"
```

Use `initial` for the fixed wear control, `s1-g3-c4` for Search 1, or `s2-g3-c1`
for Search 2. Neither finalist is promoted as a replacement default.

The default condition is rainfed founder 1 on weather `58d7d6ca`. To watch a
different founder in the crowded plot:

```sh
make host-play-research \
  ARGS="--policy s2-g3-c1 --layout rainfed-crowded --founder 4 --seed 9a903368 --speed 256"
```

To apply the chosen repair policy to every plant, including all descendants:

```sh
make host-play-research ARGS="--policy s1-g3-c4 --founder all --speed 256"
```

This opt-in population mode displays `ALL` and whole-world living/seed counts.
It is a different experiment from one candidate family competing with selective
residents; it does not change the default launch or the archived family runs.
The [population comparison](../benchmarks/garden-seasons/leaf-population.md)
reports renewal and diversity across the matched panel and retains every capture.

Rainfed has founders 1–3; rainfed-crowded has founders 1–5. The four panel seeds
are `58d7d6ca`, `9a903368`, `6b9c1a3e`, and `59818bc3`; the archived reference
seed `98a89374` is also accepted. Use eight lowercase hexadecimal digits without
`0x`. Changing a condition or policy requires a fresh launch, so a model is
never replaced midway through a family's life.

The Docker build prepares the frozen sources and models from the committed
evidence archive, then compiles the session adapter and pinned SDL3 viewer.
It does not need the old experiment build directories, install host development
dependencies, or execute saved binaries. The first build may download SDL.

## Controls and time

| Key | Action |
|---|---|
| Space or P | Pause or resume |
| N or period | Pause and advance one logic tick |
| D | Pause and advance one Garden day |
| R | Reset the same policy and conditions |
| Minus or plus | Select 1x, 16x, 256x, or maximum speed |
| M | Maximum speed |
| H | Toggle the selected family's overlay |
| S | Save a screenshot and complete state/history record |
| Escape | Quit |

A Garden day is 3,840 logic ticks: 64 seconds at 1x, or about a quarter-second
at 256x when the host keeps up. The header shows the requested speed and measured
effective speed. Presentation is capped near 30 frames per second; faster
playback can skip display frames but still executes every simulation tick.
Stepping is split into bounded work slices to keep keyboard handling responsive.
Playback pauses at day 1376; reset or quit from there.

Repeated N, period or D presses queue their steps, up to the run's stop tick;
holding a key does not auto-repeat. Pause/resume or reset cancels any queued
steps. A screenshot records the current completed tick, not queued future work.

With a numeric `--founder`, the candidate policy belongs to one founder family and follows its descendants.
Other families retain the selective resident controller. The header's `live`
and `bank` counts refer only to the candidate family, not the whole garden.
A populated garden can therefore have an extinct candidate family. W2 growth,
seasonal rain and the fixed ecology remain unchanged. Gardener keys do nothing.

Press H to trace the selected family's living stems and roots in cyan, with
small squares at their bases. Pink diamonds mark that family's pending seeds,
including seeds whose parents have died. Dead plants are not highlighted.
With `--founder all`, the overlay covers every living plant and pending seed.
The overlay follows lineage identity through reproduction and plant-slot reuse;
it does not identify family membership by location or appearance.

The overlay starts off. Add `--highlight-family` to start with it enabled:

```sh
make host-play-research ARGS="--policy s1-g3-c4 --speed 256 --highlight-family"
```

Highlighting does not advance the world or cancel queued steps. It changes only
the viewer display; saved captures retain the original pixels without overlays.

## Captures

`S` creates a fresh `shot-*` directory under `artifacts/garden-research-captures`:

- `frame.png`: the unmodified 240-by-240 garden image, without viewer text or overlays;
- `frame.raw`: its exact RGB565 big-endian bytes;
- `state.json`: the canonical state, model identity, conditions and full histories;
- `manifest.json`: the frozen runtime archive identity, policy name and frame CRC.

The manifest is published last. A folder without a complete manifest is a
failed/partial capture, not evidence of a completed save. Existing captures are
never overwritten. `--capture-dir DIR` chooses a different directory; its parent
must exist. Capture or simulation errors stop the viewer with an error message.

For automation, `--stop-tick COUNT` exits at that exact tick,
`--paused --frames 1` presents the initial world, and `--capture-on-exit` saves
the final image and state. Successful exit prints the same JSON record as the
headless research runner. Canonical state records identify a run; loading them
to resume playback is not implemented.

The headless runner accepts a numeric founder or `all` in its final condition
argument, followed by an optional new raw-frame path and render cadence:

```sh
artifacts/garden-research-player-build-v1/research-replay \
  s1-g3-c4 58d7d6ca rainfed 245760 all
```

That example advances 64 Garden days without rendering. Population records use
`garden-leaf-population-replay-v1`, `controller_assignment: whole-population`,
and a `TPR1` state envelope. Candidate founder and resident policy are null;
ancestry and complete lifetime/seed histories remain present. Numeric-founder
runs retain the original family schema and `TFR1` encoding.

To collect matched checkpoints from one continuous population run:

```sh
artifacts/garden-research-player-build-v1/research-replay \
  s1-g3-c4 58d7d6ca rainfed 5283840 all --timeline artifacts/new-population-timeline
```

The fresh directory receives raw pixels and complete JSON at days 0, 32, 192,
608, 992, and 1376. A shorter horizon captures the scheduled dates up to that
point and the requested endpoint. Existing directories are rejected; failed
partial captures are retained but do not receive successful final stdout.

For a bounded read-only resource and germination trace of one family within a
uniform population, use `--trace FOUNDER NEW_DIR` instead of `--timeline`:

```sh
artifacts/garden-research-player-build-v1/research-replay \
  s1-g3-c4 58d7d6ca rainfed 983040 all --trace 2 artifacts/new-shrub-trace
```

This records the same checkpoints plus `trace.json`, with per-lineage daily
budgets and per-seed blocker histograms. The simulation/history JSON is
unchanged. Tracing is host-only, limited to day 256, and uses bounded storage
allocated at activation rather than per-step logs. It must be enabled at tick
zero; resetting the session disables it. Numeric-founder family competition
does not support this trace. See the [trace protocol](../benchmarks/garden-seasons/leaf-population-trace-protocol.md)
for units, capacities, and interpretation, and the
[six-run result](../benchmarks/garden-seasons/leaf-population-trace.md) for validation.

Use `--shadow FOUNDER NEW_DIR` for the fixed winter observation comparison:

```sh
artifacts/garden-research-player-build-v1/research-replay \
  s1-g3-c4 58d7d6ca rainfed 983040 all --shadow 2 artifacts/new-shrub-shadow
```

This includes the resource trace and adds `shadow.json`: every selected-family
leaf observation during days `(208,224]`, evaluated by all three frozen repair
controllers. Only the original controller's decision is applied. The endpoint
must be between days 224 and 256. The diagnostic uses one additional bounded
host allocation and is disabled on reset. See the
[comparison protocol](../benchmarks/garden-seasons/leaf-population-shadow-protocol.md)
and [results](../benchmarks/garden-seasons/leaf-population-shadow.md). The frozen
simulation and canonical state format are unchanged.

For the fixed-case scheduled gate intervention:

```sh
artifacts/garden-research-player-build-v1/research-replay \
  --gate light on artifacts/new-shrub-gate
```

The arms are `none`, `light`, `condition`, and `both`; `on`/`off` selects only
resource tracing. Unlike shadow mode, this applies a derived controller to
family 2 after day 208, with Search 1 elsewhere. The seed, layout, activation,
day-256 endpoint, and eight capture dates are fixed by the
[protocol](../benchmarks/garden-seasons/leaf-population-gates-protocol.md).
These runs use distinct `TGR1` state and `garden-leaf-gate-replay-v1` JSON,
including their exact derived model. They cannot be combined with shadow mode,
and reset disables the intervention. Ordinary viewer and firmware defaults
remain unchanged. See the [results](../benchmarks/garden-seasons/leaf-population-gates.md).

Use `--gate-long` instead of `--gate` for the fixed day-608 follow-up. It keeps
all eight earlier captures, adds days 384, 512, and 608, and explicitly freezes
resource tracing at day 256 while continuing complete history tracking.
`trace.json` therefore describes the day-256 prefix, not the longer endpoint.
State identity and the applied intervention are unchanged. See the
[follow-up protocol](../benchmarks/garden-seasons/leaf-population-gates-long-protocol.md)
and [results](../benchmarks/garden-seasons/leaf-population-gates-long.md).

`--gate-transfer` uses the same day-608 schedule on the second fixed rainfed
seed, `59818bc3`. Only the weather seed differs from `--gate-long`; the four
model variants, family assignment after day 208, captures, and day-256 trace
freeze are unchanged. Its founder is already dead at the switch, so its
descendants receive the intervention. See the
[second-seed protocol](../benchmarks/garden-seasons/leaf-population-gates-transfer-protocol.md)
and [results](../benchmarks/garden-seasons/leaf-population-gates-transfer.md).

For the from-start four-seed comparison:

```sh
artifacts/garden-research-player-build-v1/research-replay \
  --gate-panel 58d7d6ca both on artifacts/new-shrub-gate-panel
```

This accepts only `58d7d6ca`, `9a903368`, `6b9c1a3e`, or `59818bc3`, and
applies the chosen variant to family 2 from the first decision after tick zero.
Other families still use Search 1. Activation tick zero is included in both
the canonical state and JSON identity; this is not the day-208 intervention.
The day-608 endpoint, eleven captures, and day-256 trace freeze are unchanged.
See the [panel protocol](../benchmarks/garden-seasons/leaf-population-gates-panel-protocol.md)
and [results](../benchmarks/garden-seasons/leaf-population-gates-panel.md).

For the read-only purchase-time diagnostic of the contrasting early handoff:

```sh
artifacts/garden-research-player-build-v1/research-replay \
  --purchase-panel 9a903368 both on artifacts/new-purchase-trace
```

This fixed-seed command has the same eleven captures and day-608 endpoint.
With `on`, it adds `purchases.json` for all paid purchases during `[30,35)` days,
plus the usual resource trace. `off` disables both diagnostics. The observer
borrows current plant and placement state; it does not change policy or RNG.
The frozen preparation remains intact; CMake stages a separate callback-binding
adapter in the build directory. See the
[bounded protocol](../benchmarks/garden-seasons/leaf-population-purchases-protocol.md)
and [results](../benchmarks/garden-seasons/leaf-population-purchases.md).
The trace's destination array has fourteen storage slots, with six active
entries and eight trailing zeros during this window. Padding is not reachable
space; the offline validator checks and excludes it.

For the host-only fewer-blocker placement experiment:

```sh
artifacts/garden-research-player-build-v1/research-replay \
  --fallback-panel 9a903368 both fewest on artifacts/new-blocker-fallback
```

Choose `original|fewest` independently of `none|light|condition|both` repair
and `on|off` logging. The fixed seed, day-608 horizon, eleven captures, and
trace windows match `--purchase-panel`. Only family 2 uses the new placement
rule: retain clear-site behavior; if all reachable sites are blocked, prefer
the fewest stored spacing blockers, with cyclic ties from the existing draw.
Retained dead plants count, and reflected aliases keep their choice indices.
The policy uses an explicit borrowed route, not observer activation, and does
not allocate while stepping or draw additional random numbers.

New-policy JSON has schema `garden-blocker-fallback-replay-v1` and explicit
`placement_intervention` metadata. Its canonical bytes prefix `TGR1` with a
12-byte `TBF1` header: version 1, founder 2, two reserved zero bytes, and
little-endian activation tick zero. Original mode retains the exact previous
identity. The [comparison](../benchmarks/garden-seasons/leaf-population-fallback.md)
finds mixed effects; this is not a viewer or firmware default.

For ordered reproduction access in the condition-only placement comparison:

```sh
artifacts/garden-research-player-build-v1/research-replay \
  --reproduction-panel 9a903368 condition fewest on artifacts/new-reproduction-trace
```

This command accepts only `condition` repair and `original|fewest` placement.
With `on`, it adds `reproduction.json` alongside the unchanged resource and
purchase traces. It counts all reproduction-cadence visits in `(128,232]`
days and retains ordered receipts on ticks where a seed slot is open. Later
visits after that slot is filled are included. `off` disables all diagnostics;
neither setting changes canonical identity or policy. Histograms retain
simultaneous blockers, so a full bank does not imply an otherwise eligible
plant. The trace is session-owned, has fixed bounds, and refuses publication
after recording failure. See the
[protocol](../benchmarks/garden-seasons/leaf-population-reproduction-protocol.md)
and [results](../benchmarks/garden-seasons/leaf-population-reproduction.md).

For step-level resource budgets around the eight missed openings of shrub 17:

```sh
artifacts/garden-research-player-build-v1/research-replay \
  --budget-panel 9a903368 condition fewest on artifacts/new-budget-trace
```

This narrower diagnostic accepts only `condition` repair and `fewest` placement.
With `on`, it retains the three preceding traces and adds `budget.json`: 2,244
ecology steps across eight overlapping windows, one day before and a quarter
day after each focal visit. Six resource payment points separate income,
storage overflow, upkeep, growth, repair, and seed purchases. Reproduction
cadence rows also retain the actual eligibility thresholds and blockers.
`off` disables all diagnostics without changing policy or replay identity.
The host-only collector has fixed storage, no step allocation, and refuses
incomplete or failed traces. See the
[bounded protocol](../benchmarks/garden-seasons/leaf-population-budget-protocol.md)
and [results](../benchmarks/garden-seasons/leaf-population-budget.md).

For matched leaf light and condition during day 152:

```sh
artifacts/garden-research-player-build-v1/research-replay \
  --foliage-panel 9a903368 condition original on artifacts/new-foliage-trace
```

Use `original` for shrub 19 or `fewest` for shrub 17. With `on`, this retains
the three preceding traces and adds `foliage.json`: 256 ecology steps in
`(152,153]` days, each with actual uptake light, pre-repair leaf condition,
positions, repair selection, fractional energy, and payment stages. Wear has
already occurred at the observation point; repair has not. Every step must
reconstruct the ledger's income exactly. `off` disables diagnostics without
changing policy. These are fixed-case host measurements, not a new controller
or a change to firmware. See the
[protocol](../benchmarks/garden-seasons/leaf-population-foliage-protocol.md)
and [results](../benchmarks/garden-seasons/leaf-population-foliage.md).

For the same replays with dawn shadow-source attribution:

```sh
artifacts/garden-research-player-build-v1/research-replay \
  --canopy-panel 9a903368 condition original on artifacts/new-canopy-trace
```

This retains the four preceding traces and adds `canopy.json` for the 32 ecology
steps in `(152.75,152.875]`. The host adapter reconstructs pre-uptake opacity on
a private world copy using the frozen builder, then requires every projected
light cell to equal actual uptake light before accepting it. Sources retain
lineage, cell, center/neighbor opacity, and dead status. The existing frozen
uptake-audit restriction remains intact. Storage is session-owned and bounded;
reset disables the diagnostic. See the
[protocol](../benchmarks/garden-seasons/leaf-population-canopy-protocol.md)
and [results](../benchmarks/garden-seasons/leaf-population-canopy.md).

## Verification

```sh
make host-research-player-check
```

Checks cover ownership, independent sessions, reset and allocation failure,
latched audit errors, render-state preservation, actual SDL keyboard events,
queued tick/day presses and stop boundaries, speed-independent results, invalid
inputs, capture safety, and PNG-to-native pixel equality. Overlay checks cover
actual H events and displayed marker pixels, exact restoration after toggling
off, unchanged captures for all three policies, and a 64-day lineage replay with
descendants, dead plants, reused slots and posthumous seeds. Preparation tests reject
changed archives, models, sources, manifests, unsafe paths, symlinks and partial
output directories. The new C code
builds with strict warnings and undefined-behavior sanitization.

Population checks compare the private owned path with the checked uniform
replay, exercise all three policies and both layouts, and verify ancestry across
births and slot reuse. They also cover scope validation, allocation failures,
reset, latched audit failures, capture identity, rendering cadence, and viewer
capture/overlay parity. Timeline, renewal-scoring, bounded-collector, and offline
evidence tests run in the same check target. The population adapter reuses the frozen uniform kernel;
it does not patch the authenticated runtime or change ecological rules.

Nine longer checks also matched complete archived stdout and raw pixels:
three day-608 anchors, three day-1376 rainfed founder-1 runs on `58d7d6ca`, and
those three late runs with rendering after every Garden day. They completed in
257.3 seconds in a clean Git-tree export without historical artifacts or network
access. Results are retained in `artifacts/garden-research-parity-v1`.

To repeat that bounded check, use a fresh output directory:

```sh
docker compose run --rm -T host-player python3 -B sim/research_player/check_replay.py \
  --binary artifacts/garden-research-player-build-v1/research-replay \
  --out artifacts/garden-research-parity-v2
```

The implementation follows the [playback plan](garden-research-playback-plan.md).
Side-by-side worlds, backward seeking, browser playback,
new training and firmware deployment remain separate work.
