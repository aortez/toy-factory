# Test bounded upward soil transfer in the existing late worlds

Status: **FROZEN before candidate runs**. Follow the [root reachability audit](
landing-root-reachability.md) with one host-only transport experiment, not a
parameter search or a firmware change.

## One fixed rule

Ordinary behavior is unchanged through logic tick **626580**. Afterwards, on
logic ticks divisible by 60 (every four ecology steps), add a pass between
ordinary lateral transport and surface evaporation. For every column and
adjacent vertical pair, move exactly one unit from the lower cell to the upper
cell only when lower moisture exceeds upper moisture by at least two units.
Visit upper rows zero through nine in ascending order. Newly lifted water
cannot cross another upward edge in the same pass. The first eligible tick is
626640. This is a bounded game-model rule, not a calibrated physical soil model.

The pass conserves water, cannot exceed byte bounds, adds no RNG draws and
allocates no persistent world state. Rain, downward/lateral transfer, evaporation,
root geometry and uptake limits, genomes, body budgets, spending guards and
controller bytes stay unchanged. Plant decisions may subsequently diverge in
response to changed moisture; do not claim their evolved bodies stay identical.
Use a separate explicitly enabled host build. Ordinary host and device defaults
remain off. Record the rule in run metadata and hash identity.

## Fixed comparisons and calls

Pin `landing-root-reachability-results.json.gz` at SHA-256
`9ee2de6709856f1df93a6a4ae51f7029421ce03dce25162e0bb3a6c0f4f1011a` and
`landing-root-allocation-results.json.gz` at
`8877c4e6f7f951ec06c546c5fc6f3e0ea0175a250b70e21596e734cd8fa63d76`.
Use all four existing fixed/rotating and daylight/dawn cases, both allocation
arms, the same model, weather seed and 983040-tick horizon. These remain
diagnostic histories from one weather seed, not a fresh generalization panel.

Run **24 full trials**: eight rebuilt ordinary controls, checked against the
saved ordinary results/traces/pixels, plus eight wicking trials with an exact
repeat of each. Unit and short integration tests are separate from this trial
count. No training, extra long trials, early stopping, parameter tuning or
selection of only favorable arms. Stop and report if provenance, historical
neutrality, repeatability or conservation checks fail.

Retain ordinary stand, adult and direction traces for every run. Add passive
uptake observations on 626520–660480 inclusive, covering pre-intervention soil,
the first changed transport and the following dry interval. Keep terminal
screenshots for all comparisons, with no extra screenshot replays. Archive
both binaries, build settings, sources, model bytes and a complete manifest.

## Evidence and outcomes

Require identical stand/adult/direction observations through 626580 and
identical pre-intervention uptake. Identify the first changed soil update.
Reconstruct all observed cell transitions independently, including intervening
germination withdrawals. Check upward conservation and per-pass limits. Record
water by depth, rain/evaporation, uptake and cumulative upward transfers during
the observation window. Separate repeated internal transfers from net gains
in accessible water; cumulative edge movement is not new water supply.

For the same pre-intervention daylight lineage 16 and dawn lineage 17, retain
birth identity, death time, offspring production and energy/water accounts.
Compare post-intervention income and maintenance shortfalls both through the
old common endpoints (639480/644700) and over actual lifetimes. Do not let
longer exposure masquerade as worse or better maintenance efficiency.

Retain the established whole-population summaries, matched/unmatched births,
survival, seed production and resource shortfalls. Compare each wicking run
against its own ordinary allocation/guard/order control, not against a different
policy. Report every arm and any regressions. Inspect drought days separately:
unchanged absence of rain does not by itself prove drought pressure is retained.

A useful diagnostic result needs greater actual root supply and improved
survival or reproduction, not just wetter shallow cells. Report whether the
existing population non-regression checks also pass. Either outcome remains
insufficient for promotion: a broader climate/seed panel and a from-start test
would be separate follow-ups. Do not change defaults based on this panel.

## Validation

Test onset and cadence boundaries, zero/full cells, the two-unit gradient,
conservation, no same-pass multi-row ascent, invalid inputs and deterministic
results. Run ordinary host regression tests and focused integration checks for
the enabled build. Portable verification must rederive summaries offline;
raw verification must rehash artifacts and reextract observations without
running native code. Preserve all earlier captures and use a fresh output path.
