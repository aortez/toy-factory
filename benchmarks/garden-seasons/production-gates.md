# Seed-production gate audit: the bank is full

The eight-slot seed bank is the immediate production constraint in these frozen
worlds. Of the 35 guarded late established descendants that never produced a
seed, **31 had at least one exact visit where bank capacity was the only failed
condition**. Two others had ready flowers but always lacked energy during their
otherwise suitable windows; two never developed a ready flower.

This is a diagnosis, not a capacity intervention. No controller, seed lifespan,
ecology default, fitness rule or device firmware was changed. More available
slots have not yet been shown to yield more established/reproducing descendants.

## Fixed scope and observation point

The [predeclared protocol](production-gates-protocol.md) replays all 32 matched
worlds, both arms, from the [fresh reserve confirmation](seedling-confirmation.md)
through day 128. The wide-scattering host candidate and unchanged combined
first-day offspring guard are retained. These are eight shared weather blocks,
two layouts and two controllers, not 64 independent weather replicates.

The host-only observer records every sequential reproduction visit after growth,
dawn flower renewal and cooldown decrement, before a seed debit. It records
immature/spent/ready flowers, bank occupancy, cooldown, stress, light, stored and
required resources, overlapping gate flags and actual production. The production
decision and observer share the same reserve calculation. No observer state is
added to the world or firmware; caller-owned output is 292 bytes in this build.

The first set bit follows the ordinary short-circuit order. Other set bits are
simultaneous limits evaluated from that same state, not claims that those later
checks were reached. Removing the first blocker alone need not permit production.
An earlier plant can fill the last bank slot on the same ecology step; the receipt
captures the occupancy at each plant's own turn.

## Cohorts and denominators

As in the [funnel audit](reproduction-funnel.md), established parents are
descendants that survived a full Garden day. The closing cohort was born strictly
after day 112. Dead parents remain included; pending follow-up is not permanent
infertility. The results below describe plants with **no seed production by day
128**, not all plants without germinated children.

A candidate window is a living plant's maintenance-cadence visit with cooldown
clear, sufficient daylight and at least one mature, unspent flower. It does **not**
filter on bank, stress, generation or resource sufficiency. Counts are repeated
visits weighted by observation duration, not independent trials or plant counts.

| No-seed cohort | Control, whole history | Guard, whole history | Control, closing | Guard, closing |
|---|---:|---:|---:|---:|
| Established parents | 329 | 424 | 20 | 35 |
| Still alive at horizon | 47 | 65 | 14 | 29 |
| Ever had a ready flower/window | 322 | 398 | 20 | 33 |
| Ever blocked by bank alone | 315 | 379 | 19 | 31 |
| Candidate-window visits | 130,297 | 142,264 | 2,607 | 5,999 |
| Bank-full visits | 129,401 | 141,500 | 2,571 | 5,947 |
| Bank as the sole failed condition | 70,106 | 77,484 | 1,212 | 2,969 |

Ready-flower and candidate-window parent counts happen to coincide here; they
are measured separately. Whole-cohort mean observed living time is 13.53 control
and 11.91 guarded days; closing-cohort means are 4.69 and 6.97. The populations
and durations differ, so these are not matched individual causal effects.

## The 35 guarded late nonproducers

The bank is full in 5,947/5,999 candidate visits (99.13%). It is the sole failed
condition in 2,969 visits across 31 parents. For these plants, the missing flower
is not simply immature and the resource thresholds are not always unaffordable.

Of the remaining 52 bank-free visits, energy is the first failed condition in
46 and water in six. One of the energy failures also lacks water. Energy
shortfalls in those bank-free visits range from 4 to 183, with a visit-weighted
median of 116; this is not generally a one-unit rounding problem. Water is short
in seven visits by 22–34 units, median 28.

Across all 5,999 visits, overlapping limits include energy in 2,876, water in
230 and stress in 50. Those counts overlap each other and bank saturation.
Zero visits meet both resource requirements while a bank slot is free.

The four exceptions to a bank-only opportunity are retained explicitly:

| World / lineage | Observed limitation |
|---|---|
| rainfed, baseline, `ed52188c`, #48 | Ready flower; all 42 candidate visits lack energy and have a full bank; dies at tick 481260 |
| rainfed, baseline, `647001a8`, #84 | Ready flower; all four candidate visits lack energy and have a full bank; dies at tick 482340 |
| rainfed, adaptive, `4f0b9247`, #22 | No ready flower by day 128; still alive |
| rainfed-crowded, adaptive, `0bb887d1`, #34 | No ready flower by day 128; still alive |

All weather blocks with guarded late nonproducers show bank saturation; block
`c629bb63` has no such late cohort and is not assigned a zero-success denominator.
In the whole-history guarded nonproducer cohort, bank-full shares of candidate
visits range from 98.78% to 99.90% across the eight weather blocks. Both layouts,
both controllers and all three species show the same immediate limit. Detailed
partitions and every parent remain in the retained evidence.

Seed-producing established parents are also bank-constrained: control/guard
whole-history candidate visits are 302,714/307,374, of which 296,645/301,653 have
a full bank. Their actual purchases total 1,353/1,226. The limit is not exclusive
to parents that end with zero production.

## What this does and does not imply

Long-lived seeds compete for a finite eight-entry bank. Keeping a seed viable
for 32 days can preserve a lineage, but can also occupy space while its landing
site remains unsuitable. Earlier audits show that germination can occur after a
parent dies; do not discard those seeds merely because the parent is gone.

The new observation establishes an immediate admission constraint. It does not
establish that doubling capacity fixes recruitment, preserves diversity, or
avoids extra reproductive spending and later parent deaths. All ecological
outcomes and all eight [previously verified images](seedling-confirmation.md#fixed-screenshots)
remain exactly those of the confirmation panel. No new screenshots are needed.

Next proposal: a **bounded host-only eight-versus-sixteen seed-bank comparison**,
keeping the 32-day lifespan, wide scattering, first-day guard and all resource
rules fixed. Freeze a matched panel and acceptance criteria before running it.
Judge full-day establishment, durable descendant reproduction, extinctions,
species retention and parent mortality, not seed throughput alone. Measure the
actual storage cost before considering device adoption. If a larger bank merely
fills and shifts the problem, discuss bounded admission/replacement separately.
Neither experiment nor policy promotion is implemented in this observer pass.

Follow-up: the [isolated sixteen-slot comparison](seed-bank-capacity.md) has now
run with those rules fixed. It improves historical reproduction but fails its
late-renewal/survival gates; the larger bank remains almost always full. See that
report for the paired costs and retained negative result. Defaults stay at eight.

## Evidence and verification

- All 64 trajectories were captured twice with byte-identical receipts, then
  independently reanalyzed from the unchanged files.
- Every one of 2,097,216 ecology snapshots matches the saved state hash and seed
  creation count. All 9,484,875 sequential visits reconcile, including retained
  dead plants; the cohort analysis counts living visits separately.
- All 3,892 seed productions match the prior creation ledger and sequential
  parent order. Stored resources, debits, cooldowns, flowers, requirements and
  bank occupancy are independently checked against the frozen inspector output.
- Native tests compare complete world bytes with ordinary stepping under both
  controllers, and exercise exact resource/maturity boundaries, cooldown, dawn
  renewal, the final bank slot, stress, death, cadence, generation and errors.
- All 114 default and 116 research CTests passed. After installing the portable
  evidence, the new Python suite and native/funnel tests were rerun successfully.
  The player rebuilt and its smoke test passed.
- Firmware rebuilt at the unchanged 257,596 bytes flash, 223,004 bytes main RAM
  and 8 KiB Core 1 RAM. No observer symbols appear in its map. No device flash.

The [portable parent aggregates](production-gates-parents.json.gz) include
per-parent histograms, ancestry/follow-up and source/build/trace provenance.
Decompressed SHA-256:
`646131b9f7e2c599ca7bcc436d51e8cf5b9143c4899913119d3eae40bb79ec15`.
The [summary](production-gates-summary.json) includes all cohorts and partitions;
SHA-256: `b2a5ff0777a4aabd84b297b6978dba355919a0b0063dfbcbc061ced414a25ef6`.
The fixed input ledger SHA-256 is
`b420df72e0a4dc64ca6d47817ed1df4a2847e670c5149c45260bbdb2c570ebd0`.

```sh
python3 sim/garden_season_production_gates.py collect \
  --build artifacts/build-host-production-gates \
  --bundle artifacts/garden-seasonal-seedling-confirmation \
  --out artifacts/garden-seasonal-production-gates-new --jobs 4
python3 sim/garden_season_production_gates.py verify \
  --build artifacts/build-host-production-gates \
  --bundle artifacts/garden-seasonal-seedling-confirmation \
  --out artifacts/garden-seasonal-production-gates-new --jobs 4
```

Collection requires a new directory and the isolated wide-scattering build;
it rejects changed non-observer dependencies or ecology flags. The verifier
rereads both receipt files and original traces without new simulations.
Portable CTests need neither the ignored raw traces nor a native build for the
aggregate checks. Full receipts and build/check logs remain under ignored
`artifacts/garden-seasonal-production-gates*` / `artifacts/garden-production-gates*`.
