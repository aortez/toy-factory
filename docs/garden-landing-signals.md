# Landing signal-content probes

Host-only mechanistic experiment on the three frozen current-only finalists.
The [fixed protocol](../benchmarks/garden-seasons/landing-signals-protocol.md)
compares ten live/neutral/fixed input combinations across the same 16 development
conditions. No training, ecology changes, model reselection or device defaults.
The [completed report and galleries](../benchmarks/garden-seasons/landing-signals.md)
retain every outcome, including fixed-input improvements and individual losses.

```sh
make host-probe-landing-garden \
  GARDEN_LANDING_SIGNALS_OUT=artifacts/garden-landing-signals-v1

# One explicitly identified replay; normal replay does not accept these options.
make host-landing-garden \
  ARGS="probe-replay current.tgl rainfed 0x25185eeb --ticks 737280 --climate seasonal --ledger --occupancy occupied --resources live"
```

Both probe groups must be specified. Occupancy accepts `live`, `neutral`,
`occupied`, `open`; resources accepts `live`, `mid`, `low`, `high`. Only
current-only models with flags=0 are supported. Files and all weights remain
unchanged. This is a separate experimental policy adapter, not a model loading
override or new TGL2 configuration/file format. Output kind is
`landing-signal-replay`, with explicit `signal_probe` metadata and a separate
GSP1 diagnostic fingerprint incorporating the original model/cache/world hash
and probe configuration. The copied run owns both configuration and base state.

The adapter transforms a **copy** of the packet before normal inference. It
preserves real cached measurements, the 77 legacy features, history masking,
and valid-source/body-role gating. Root and out-of-bounds sources remain zero.
The step uses the same transactional world/cache/audit path as ordinary replay.

Raw sensor values are centered by subtracting 128. Thus neutral occupancy
`(128,128)` and midpoint resources `(128,128)` contribute zero; occupied
`(0,0)` contributes `(-128,-128)`, not zero. Open occupancy is `(255,0)`.
Low/high resources are `(0,0)` / `(255,255)`. Water and light are tested jointly.
Midpoint constants are not measured averages. These counterfactual packets
retain validity gating and legacy sensing, so no variant is a blind controller.

The collector requires live and neutral worlds to reproduce the corresponding
retained current/off biological trajectories and scores before accepting them.
The scorer validates probe metadata, then reuses the unchanged renewal objective.
Every paired comparison is **intervention versus its own live control**; positive
comparison means the intervention improved the aggregate key. Preserve the
world/seed/layout/climate breakdown rather than interpreting counts as votes.

All 480 worlds repeat with one worker and no captures. Sixty independently
replayed screenshots cover each probe/controller in both layouts at day 192,
seasonal seed `25185eeb`; captures must match headless results. Gallery sheets
have ordinary/crowded layouts as columns and probes as rows. Part 1 contains
live, water-light-only, occupancy-only, neutral, occupied; part 2 contains open,
low-resources, high-resources, fixed-occupied, fixed-open. No frame selection.

The output directory must be fresh; pinned portable inputs are in the repo.
`GARDEN_LANDING_SIGNALS_ARGS="--jobs 4"` changes independent workers only (1..8).
Freeze sources/builds during collection. Interrupted/mismatched collection
leaves incomplete evidence, never a complete manifest. A source snapshot is
not proof of binary provenance. Frozen verification executes a trusted bundle:

```sh
docker compose run --rm -T firmware python3 \
  artifacts/garden-landing-signals-v1/sim/garden_landing_signals.py \
  --verify artifacts/garden-landing-signals-v1
```

Verification checks hashes and reruns all 480 worlds and 60 frames, comparing
models, complete histories, scores, raw pixels and PNGs. Out-of-distribution
fixed inputs are diagnostic: a loss does not establish optimal sensing, and a
match does not prove the information is useless. The prespecified constants
are not an exhaustive grid. Discuss outcomes before training or promotion.
