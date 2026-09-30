# Frozen model first day water reserve screen

`make host-screen-landing-water` runs the same twelve selected old/new neural
finalist worlds with the existing water-only seedling reserve disabled and
enabled. It is a host-only diagnostic, not a new trainer or device policy.

```sh
make host-screen-landing-water GARDEN_LANDING_WATER_OUT=artifacts/my-water-screen
docker compose run --rm -T firmware python3 \
  artifacts/my-water-screen/sim/garden_landing_water.py \
  --verify artifacts/my-water-screen
```

The collector accepts `--build DIR --out NEW_DIR [--jobs 1..4]`; the default
build is `build-host`. It requires ordinary ecology with all research flags
OFF and UBSan enabled. Do not edit source, protocol, inputs or the build while
collecting. Outputs must be fresh. Verification accepts no overrides and
reuses the frozen tools, binary and inputs with one worker.

The native command is explicit:

```sh
toy-factory-garden-landing water-replay model.tgl rainfed-crowded 0x940cfdc4 \
  --climate seasonal --ticks 737280 --water-reserve on --ledger \
  --recruitment-trace NEW-resources.jsonl --water-trace NEW-water.jsonl \
  --framebuffer NEW.rgb565be
```

Use `off` for the matched control. Both traces are optional but require a ledger
when requested. Paths are no-clobber; discard partial outputs from failed calls,
not their errors. Neither this command nor collection changes model bytes.

Only ages 1 through 256 ecology ticks of living descendants are eligible. The
existing predicate preserves four maintenance payments after growth, or one for
a locally available wetter-root destination. Energy forecasts are not enforced.
Rejected proposals become WAIT but retain priority and proposed memory, so
affordable root proposals can still lose arbitration. Age 257, founders and
reproduction are unguarded. See the [frozen protocol](../benchmarks/garden-seasons/landing-water-protocol.md)
for exact boundaries and acceptance criteria.

The bounded per-step audit records original selected proposals, first available
ranked destinations, water forecasts, selected vetoes, bid/denial counts and
funded wetter-root alternatives. It retains no pointers across steps and
publishes only on successful world/cache advancement. The collector recomputes
forecasts and reconciles actual growth spending/node additions against the
existing five-stage first-day observer. An available alternative is not proof
of successful future uptake or survival.

`landing-water-replay` and the versioned configuration-aware fingerprint keep
probe identity explicit; the ordinary base fingerprint is also retained. The
ordinary trainer rejects these results. The collector validates the probe tag
before checking shared replay fields and invoking the unchanged pure scorer.
Every disabled result and recruitment trace must match the archived ordinary
panel exactly. Trace on/off, repeated traces and raw captures must agree.

All 24 final screenshots are saved in fixed order, with one six-row contact
sheet per climate. Full lineage/seed ledgers, first-day resources and selected
winner receipts are retained, including regressions. The
[completed report](../benchmarks/garden-seasons/landing-water.md) records the
failed gates and limitations; no threshold tuning, promotion or flash follows
automatically from this command.
