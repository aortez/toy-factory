# Landing sensor: shadow checkpoint

The proposed sensor is implemented and independently checked, **without changing
any controller decision or activating a neural input**. It exposes spatial
differences on the flower-origin trajectories; it does not yet demonstrate a
survival, reproduction or diversity benefit. Keep both experimental dispersal
and this observer host-only.

## What changed

`src/garden_landing.c` owns no global state. A caller supplies one 316-byte cache
per world and a 52-byte output packet. The cache samples after sequential seed
admission and before growth, even when no plant bids. It uses the existing early
light solve, not an extra solve or the final post-growth light map. Four Q8.8
traces stay attached to soil columns, separate from private plant memory.

The projector shares the production dispersal transform, never draws RNG, and
memoizes repeated source columns within each query. Roots/OOB endpoints remain
explicitly invalid and zero; an occupied but in-bounds endpoint still receives
a reading. The existing growth-availability flags decide whether it is an
actual option. Base-origin mode deliberately gives every source the same
footprint. The pure helper extraction changes no placement arithmetic.

The private world-step observer arguments are now one typed, optional aggregate.
Only the landing wrapper populates its new member. Cache reset, sampling and
queries have explicit failure contracts; sampling errors restore the cache,
but an already-advanced world must be reset/replayed rather than resumed with
stale history. The embedded-C conventions guided bounded caller-owned storage,
transactional outputs, and these explicit ownership/recovery rules.

There are no world/snapshot layout, policy, observation-v4, neural-v1, ecology,
seed-bank, firmware-default or active device changes.

## Fixed panel and noninterference

The [predeclared protocol](landing-shadow-protocol.md) selected the first and
last weather seeds of the saved flower-origin panel (`ed52188c`, `82deacfd`),
both layouts, both baseline/adaptive controllers, and both origin arms through
day 128. This is 16 worlds but only **two shared weather realizations**. All use
eight seed slots, wide scattering, seasonal climate and the unchanged offspring
first-day reserve guard. This is an instrumentation check, not a new ecology
qualification or held-out policy test.

- All 16 complete captures repeat byte-for-byte.
- All **524,304** recorded world hashes and seed-creation counts match the saved
  original trajectories, including ticks with no policy queries.
- All **160,477** bids match the old tip/coordinates/candidate flags and proposed
  action/priority. The wrapper forwards the original policy's decision.
- Python independently reconstructs every history recurrence, occupied mask and
  packet, including reflected branch multiplicity. Native tests additionally
  compare entire world bytes at every logic step for both ordinary controllers.
- A second dense-trace analysis reproduces the portable evidence exactly.

The cache is observational and absent from current world hashes. If a future
controller consumes it, deterministic checkpoints/hashing must include it or
replay its full prefix; merely preserving today's world struct would be wrong.

## Do available directions receive different readings?

Yes, on these trajectories. Flower-origin generated 54,340 stem and 19,157 root
queries. Of **39,049** stem queries with at least two available endpoints,
**29,513 (75.6%)** had at least one differing packet field. The corresponding
base-origin count is **0 / 43,690**, as required by its geometry.

After day one the flower-origin fraction is 24,777 / 32,089 (**77.2%**). In the
closing 16 days it is 642 / 740 (**86.8%**), with substantially fewer queries.
Whole-run individual-world fractions range from 64.7% to 90.6%; retain every
world, including days with no bids. These are query-weighted descriptive rates,
not independent ecological replicates or measures of useful decision quality.

| Field | Flower queries with available-endpoint variation | Projected byte range |
| --- | ---: | ---: |
| Free establishment space | 16,974 / 39,049 (43.5%) | 0–255 |
| Dead-only blockage | 256 / 39,049 (0.7%) | 0–219 |
| Current surface water | 8,664 / 39,049 (22.2%) | 0–37 |
| Current ground light | 10,593 / 39,049 (27.1%) | 24–251 |
| Wet history | 23,953 / 39,049 (61.3%) | 0–195 |
| Lit history | 25,121 / 39,049 (64.3%) | 1–123 |
| Joint wet/lit history | 18,378 / 39,049 (47.1%) | 0–67 |
| Joint open/wet/lit history | 12,806 / 39,049 (32.8%) | 0–63 |

Ranges are **projected averages**, not extremes of individual soil cells. A
difference of one byte counts here; neither meaningful ranking margins nor
improved choices are established. Variation in occupied endpoints and invalid
zero payloads is excluded from the available-choice denominator.

Three observations matter for the next experiment:

1. History is not simply constant padding: it varies spatially in many actual
   queries. Native queries require at most three distinct projections, matching
   the design bound.
2. Simultaneous wet/lit history is lower than the minimum of the two separate
   histories in 302,561 / 323,913 valid flower-origin source readings (93.4%).
   This supports keeping the distinction between marginal and simultaneous
   resource exposure. It is not a seed-success probability or exact trailing-day
   percentage; integer EMA rounding also affects very small values.
3. `dead_only` is nonzero in just 2,115 / 323,913 readings (0.65%) and is always
   zero in the closing window. Keep its evidence, but do not assume this rare
   feature deserves a permanent NN input just because it was easy to compute.

## Cost and storage

The declared host timing case was flower-origin/rainfed-crowded/adaptive,
`ed52188c`, 128 days, GCC 13.3 Release with sanitizers off on a Ryzen 7 9800X3D.
Five repeats per mode, rotated ordering, process CPU time, no dense output in
the timed loop. Every run ends at hash `1aff7040` with 44 seed purchases; observer
runs project 7,528 bids.

| Mode | Median CPU time | Observed range |
| --- | ---: | ---: |
| Ordinary stepping | 233.810 ms | 230.386–235.387 ms |
| Cache sampler/wrapper | 318.538 ms | 317.795–323.015 ms |
| Sampler plus every-bid projection | 319.287 ms | 317.240–320.878 ms |

The full diagnostic adds about **36.6%** to this host case, or 85.5 ms over
491,520 logic steps. Sampling-only and projection ranges overlap; do not claim
the small median difference precisely isolates projection cost. The defensive
wrapper revalidates the world/cache and preserves a rollback copy on every
logic tick, in addition to sampling at ecology cadence. These checks are part
of the measurement, not the irreducible cost of the sensor.

This long trajectory includes quiet periods and is neither worst-case all-tip
cost nor an RP2040 estimate. Before device adoption, profile active periods,
the intended NN integration, and the full stack call chain on target. Avoid
paying duplicate validation at 60 Hz if a safe authoritative integration can
validate once and sample at ecology cadence.

Both host and Cortex-M0+ compilation confirm a **316-byte persistent cache** and
**52-byte packet**. Current world/garden snapshot remain 4,352 / 1,624 bytes;
scene snapshot remains 1,664 bytes. Collector receipt storage is larger and
host-only, and is not included in that embedded cache budget.

The standalone ARM observer object (`-mcpu=cortex-m0plus -mthumb -Os`, GCC 14.3)
reports static frames of 16 bytes for cache validation, 368 for capture, and
152 for observation. Capture's transactional 316-byte temporary is not extra
persistent storage. These are individual compiler frames, **not a measured
call-chain high-water mark**. The landing world wrapper separately preserves
another 316-byte copy. No target stack/timing claim is made.

## Validation and retained evidence

Focused native/reference tests cover phase ordering, germination water debit,
dead/live overlap, slot-order independence, reset/overflow, failed-step recovery,
checkpoint replay, repeated/reordered queries and geometry. Full suites pass:
**124 default and 123 representative older-research CTests**. The ordinary
Zephyr build succeeds; the observer is not compiled into firmware. No flash.

An auxiliary standalone ARM compilation of the existing world source encountered
its pre-existing unsigned-enum `-Wtype-limits` warning; a follow-up probe retained
that warning with `-Wno-error=type-limits`. The new observer object passes strict
conversion/sign warnings without an exception, and the actual Zephyr build passes.

- [Portable daily histograms and first-stem receipts](landing-shadow-histories.json.gz)
- [Recomputed summaries and source/build hashes](landing-shadow-summary.json)
- [All timing repetitions and provenance](landing-shadow-profile.json)
- [Standalone observer static frames](landing-shadow-stack.txt)

The portable bundle is about 363 KiB compressed. It contains all 2,048 world-day
records, including empty days, plus the first stem query per day when present.
It reproduces aggregate summaries and checks those sample packets; it cannot
replace full dense-trace revalidation. The complete repeated traces (about
212 MiB) remain in `artifacts/garden-landing-shadow/` with saved hash identities.
Older raw bundles and frozen executables are untouched.

```sh
# Independent native/reference + portable-evidence checks.
docker compose run --rm -T firmware python3 -W error \
  sim/test_garden_landing_shadow.py \
  --build artifacts/build-host-landing-shadow-flower

# Requires original and new dense artifact bundles and matching frozen sources.
docker compose run --rm -T firmware python3 -W error \
  sim/garden_landing_shadow.py verify --out artifacts/garden-landing-shadow --jobs 4
```

## Next decision

Review the virtual-sensing permission and define a versioned neural encoding,
with explicit masking and warmup. Then compare unchanged inputs, current landing
signals only, and current-plus-history under **identical dispersal and ecology**.
Keep the rare dead-only signal an explicit ablation question. Do not change seed
release mechanics or promote flower-origin alongside the input experiment.

This checkpoint establishes a tested instrument and a possible source of
information, not environmental qualification, a trained policy or a new fitness
function. Durable reproduction and diversity remain the evaluation goals.
